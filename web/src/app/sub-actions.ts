"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { eq } from "drizzle-orm";
import { getDb } from "@/db";
import { users } from "@/db/schema";
import { env } from "@/env";
import { normalizeEmail } from "@/lib/crypto";
import { currentUser, requireAdmin, requireUser } from "@/lib/auth";
import { getFamily } from "@/lib/families";
import { follow, getSubscription, startPaidSubscription, unfollow } from "@/lib/subscriptions";
import { isRefCode, REF_COOKIE } from "@/lib/refs";
import { upsertUser } from "@/lib/users";
import { createMagicLink } from "@/lib/magic";
import { sendMagicLinkEmail } from "@/lib/emails";
import { readUnsubscribeToken, setDigestFreq } from "@/lib/digest";
import { connectProvider } from "@/lib/connect";
import { payOut } from "@/lib/ledger";

async function refCode() {
  const v = (await cookies()).get(REF_COOKIE)?.value;
  return isRefCode(v) ? v : null;
}

/** /f/[familyId]: follow (free, while SUB_PRICE_TBD) or subscribe (Stripe Checkout, subscription mode). */
export async function subscribeAction(form: FormData) {
  const familyId = String(form.get("familyId") || "");
  const db = await getDb();
  const fam = await getFamily(db, familyId);
  if (!fam || fam.isDemo) redirect("/");
  const back = `/f/${fam.id}`;
  const viewer = await currentUser();
  const free = env().SUB_PRICE_TBD;

  let user = viewer;
  if (!user) {
    const email = normalizeEmail(form.get("email"));
    if (!email) redirect(`${back}?error=email`);
    if (free) {
      // a free follow needs a confirmed email: they come back signed in through the link, then follow in one tap
      await upsertUser(db, { email, src: "direct", role: "member" });
      await sendMagicLinkEmail(db, email, await createMagicLink(db, email, back));
      redirect(`${back}?sent=1`);
    }
    // a paid subscription: the payment is the confirmation (sign-in afterwards is limited, see start.ts)
    const u = await upsertUser(db, { email, src: "direct", role: "member" });
    user = { ...u, isAdmin: false };
  }
  if (free) {
    await follow(db, { familyId: fam.id, userId: user.id, refCode: await refCode() });
    redirect(`/family/${fam.id}?following=1`);
  }
  const base = env().APP_URL;
  const r = await startPaidSubscription(db, {
    familyId: fam.id,
    user: { id: user.id, email: user.email },
    refCode: await refCode(),
    successUrl: `${base}/f/${fam.id}/welcome?session_id={CHECKOUT_SESSION_ID}`,
    cancelUrl: `${base}${back}`,
  });
  if (r.already) redirect(`/family/${fam.id}`);
  redirect(r.url);
}

export async function setDigestAction(form: FormData) {
  const familyId = String(form.get("familyId") || "");
  const u = await requireUser(`/family/${familyId}/updates`);
  const freq = String(form.get("freq") || "");
  if (!["weekly", "monthly", "off"].includes(freq)) redirect(`/family/${familyId}/updates`);
  const s = await getSubscription(await getDb(), familyId, u.id);
  if (s) await setDigestFreq(await getDb(), s.id, freq as "weekly" | "monthly" | "off");
  redirect(`/family/${familyId}/updates?saved=1`);
}

export async function unfollowAction(form: FormData) {
  const familyId = String(form.get("familyId") || "");
  const u = await requireUser(`/family/${familyId}/updates`);
  const s = await getSubscription(await getDb(), familyId, u.id);
  if (s?.kind === "follow") await unfollow(await getDb(), s.id);
  redirect(`/f/${familyId}?left=1`);
}

/** The one-click unsubscribe link in every digest (signed, no sign-in needed). */
export async function unsubscribeAction(form: FormData) {
  const id = readUnsubscribeToken(String(form.get("token") || ""));
  if (id) await setDigestFreq(await getDb(), id, "off");
  redirect(`/u/${encodeURIComponent(String(form.get("token") || ""))}?done=1`);
}

/** "Get paid": create the archivist's Stripe Connect Express account (once) and send them to Stripe's onboarding. */
export async function connectOnboardAction() {
  const u = await requireUser("/earnings");
  const db = await getDb();
  const c = connectProvider();
  let acct = u.stripeConnectAccountId;
  if (!acct) {
    acct = (await c.createAccount({ email: u.email, userId: u.id })).id;
    await db.update(users).set({ stripeConnectAccountId: acct }).where(eq(users.id, u.id));
  }
  const base = env().APP_URL;
  redirect(await c.onboardingLink({ accountId: acct, refreshUrl: `${base}/earnings?retry=1`, returnUrl: `${base}/earnings/connected` }));
}

/** Admin-approved payout of an archivist's available balance in one currency. */
export async function adminPayoutAction(form: FormData) {
  const admin = await requireAdmin();
  const userId = String(form.get("userId") || "");
  const currency = String(form.get("currency") || "");
  if (!/^[0-9a-f-]{36}$/i.test(userId) || !/^[a-z]{3}$/.test(currency)) redirect("/admin/earnings");
  const r = await payOut(await getDb(), { userId, currency, approvedBy: admin.email });
  redirect(r.ok ? `/admin/earnings?paid=${r.payoutId}` : `/admin/earnings?error=${encodeURIComponent(r.reason)}`);
}
