import { and, eq, isNull } from "drizzle-orm";
import type { Db } from "@/db";
import { payments } from "@/db/schema";
import { env } from "@/env";
import { upsertUser, type User } from "./users";
import { markPaid, paymentsProvider, recordPending, recordReserved } from "./payments";
import { getSetting, PAYMENT_LINK_FALLBACK } from "./settings";

// /start (spec §3.1, §3.3, §6): email first, then either Stripe Checkout, the Payment Link fallback, or — while the
// price isn't set — a free reservation with no payment at all.
export type StartResult =
  | { kind: "reserved"; user: User }
  | { kind: "checkout"; user: User; url: string }
  | { kind: "payment-link"; user: User; url: string };

/** /welcome: verify the Checkout session server-side (idempotently records the payment, in case the webhook hasn't
 * arrived yet) and allow ONE on-device sign-in for it, so the archivist doesn't have to leave for their inbox. */
export async function completeWelcome(db: Db, sessionId: string): Promise<{ status: "paid"; userId: string; signIn: boolean } | { status: "unpaid" | "unknown" }> {
  const s = await paymentsProvider().retrieveCheckout(sessionId);
  if (!s) return { status: "unknown" };
  if (!s.paid) return { status: "unpaid" };
  const row = await markPaid(db, s);
  if (!row?.userId) return { status: "unknown" };
  const claimed = await db
    .update(payments)
    .set({ signinUsedAt: new Date() })
    .where(and(eq(payments.id, row.id), isNull(payments.signinUsedAt)))
    .returning({ id: payments.id });
  return { status: "paid", userId: row.userId, signIn: claimed.length === 1 };
}

export async function startSignup(db: Db, a: { email: string; src: string }): Promise<StartResult> {
  const e = env();
  const user = await upsertUser(db, { email: a.email, src: a.src });
  if (e.PRICE_TBD) {
    await recordReserved(db, { userId: user.id, src: a.src });
    return { kind: "reserved", user };
  }
  if (e.STRIPE_PAYMENT_LINK_URL && (await getSetting(db, PAYMENT_LINK_FALLBACK)) === "on") {
    const u = new URL(e.STRIPE_PAYMENT_LINK_URL);
    u.searchParams.set("client_reference_id", user.id);
    u.searchParams.set("prefilled_email", user.email);
    return { kind: "payment-link", user, url: u.toString() };
  }
  const base = e.APP_URL;
  const s = await paymentsProvider().createCheckout({
    userId: user.id,
    email: user.email,
    src: a.src,
    successUrl: `${base}/welcome?session_id={CHECKOUT_SESSION_ID}`,
    cancelUrl: `${base}/?src=${encodeURIComponent(a.src)}`,
  });
  await recordPending(db, { userId: user.id, sessionId: s.id, src: a.src });
  return { kind: "checkout", user, url: s.url };
}
