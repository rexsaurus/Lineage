import { and, eq } from "drizzle-orm";
import type Stripe from "stripe";
import type { Db } from "@/db";
import { families, subscriptions, users } from "@/db/schema";
import { env } from "@/env";
import { resolveReferrer } from "./refs";
import { paymentsProvider } from "./payments";
import { applyRefund, recordInvoiceEarning } from "./ledger";

// Family subscriptions. While SUB_PRICE_TBD=true (the default) a relative can only FOLLOW a family, free: read access
// to the non-private family page plus the regular updates. With a price set, they subscribe through Stripe Checkout in
// subscription mode; Stripe's webhooks keep the status current. Either way the referrer (the archivist whose link they
// came through) is recorded on the row and in the Stripe metadata.
export type Subscription = typeof subscriptions.$inferSelect;

export async function getSubscription(db: Db, familyId: string, userId: string): Promise<Subscription | null> {
  const [s] = await db.select().from(subscriptions).where(and(eq(subscriptions.familyId, familyId), eq(subscriptions.userId, userId))).limit(1);
  return s || null;
}

/** A free follow. Re-following after cancelling reactivates the row; the original referrer is kept. */
export async function follow(db: Db, a: { familyId: string; userId: string; refCode: string | null }): Promise<Subscription> {
  const existing = await getSubscription(db, a.familyId, a.userId);
  if (existing) {
    if (existing.status !== "active") {
      const [s] = await db.update(subscriptions).set({ status: "active", canceledAt: null }).where(eq(subscriptions.id, existing.id)).returning();
      return s;
    }
    return existing;
  }
  const referrer = await resolveReferrer(db, { refCode: a.refCode, familyId: a.familyId, subscriberUserId: a.userId });
  const [s] = await db
    .insert(subscriptions)
    .values({ familyId: a.familyId, userId: a.userId, kind: "follow", status: "active", referrerUserId: referrer, refCode: referrer ? a.refCode : null })
    .onConflictDoNothing()
    .returning();
  return s || (await getSubscription(db, a.familyId, a.userId))!;
}

export async function unfollow(db: Db, subscriptionId: string) {
  await db.update(subscriptions).set({ status: "canceled", canceledAt: new Date() }).where(and(eq(subscriptions.id, subscriptionId), eq(subscriptions.kind, "follow")));
}

/** Starts a paid subscription: a row in 'incomplete' and a Checkout session carrying every id in its metadata. */
export async function startPaidSubscription(db: Db, a: { familyId: string; user: { id: string; email: string }; refCode: string | null; successUrl: string; cancelUrl: string }) {
  const referrer = await resolveReferrer(db, { refCode: a.refCode, familyId: a.familyId, subscriberUserId: a.user.id });
  let row = await getSubscription(db, a.familyId, a.user.id);
  if (row && row.kind === "paid" && ["active", "past_due"].includes(row.status)) return { already: true as const, row };
  if (!row) {
    [row] = await db
      .insert(subscriptions)
      .values({ familyId: a.familyId, userId: a.user.id, kind: "paid", status: "incomplete", referrerUserId: referrer, refCode: referrer ? a.refCode : null })
      .returning();
  } else {
    // a follower upgrading, or a cancelled subscriber returning: keep the first referrer
    [row] = await db.update(subscriptions).set({ kind: "paid", status: "incomplete", referrerUserId: row.referrerUserId ?? referrer, refCode: row.referrerUserId ? row.refCode : referrer ? a.refCode : null }).where(eq(subscriptions.id, row.id)).returning();
  }
  const s = await paymentsProvider().createSubscriptionCheckout({
    userId: a.user.id,
    email: a.user.email,
    successUrl: a.successUrl,
    cancelUrl: a.cancelUrl,
    metadata: {
      subscription_row_id: row.id,
      family_id: a.familyId,
      user_id: a.user.id,
      referrer_user_id: row.referrerUserId || "",
      ref_code: row.refCode || "",
    },
  });
  await db.update(subscriptions).set({ stripeCheckoutSessionId: s.id }).where(eq(subscriptions.id, row.id));
  return { already: false as const, row, url: s.url };
}

/** Stripe's success URL for a subscription: confirm server-side. Stripe has already charged the first invoice when a
 * subscription checkout reports paid, so the row is activated now in case the webhook is still on its way. Signs in
 * only an account that has never signed in (see completeWelcome). */
export async function completeSubscriptionCheckout(db: Db, sessionId: string): Promise<{ ok: true; familyId: string; userId: string; signIn: boolean } | { ok: false }> {
  const s = await paymentsProvider().retrieveCheckout(sessionId);
  const rowId = s?.metadata?.subscription_row_id;
  if (!s || s.mode !== "subscription" || !s.paid || !rowId || !/^[0-9a-f-]{36}$/i.test(rowId)) return { ok: false };
  const [row] = await db.select().from(subscriptions).where(and(eq(subscriptions.id, rowId), eq(subscriptions.stripeCheckoutSessionId, s.id))).limit(1);
  if (!row) return { ok: false };
  if (row.status === "incomplete") await db.update(subscriptions).set({ status: "active" }).where(eq(subscriptions.id, row.id));
  const [u] = await db.select({ lastLoginAt: users.lastLoginAt }).from(users).where(eq(users.id, row.userId)).limit(1);
  return { ok: true, familyId: row.familyId, userId: row.userId, signIn: !!u && !u.lastLoginAt };
}

// ---- webhooks ---------------------------------------------------------------------------------------------------

function mapStatus(s: string): string {
  if (s === "active" || s === "trialing") return "active";
  if (s === "past_due" || s === "unpaid") return "past_due";
  if (s === "canceled" || s === "incomplete_expired") return "canceled";
  return "incomplete";
}

type AnySub = Stripe.Subscription & { current_period_end?: number };

/** customer.subscription.created / updated / deleted. Idempotent: it sets the row to Stripe's current state. */
export async function applyStripeSubscription(db: Db, sub: AnySub, deleted = false) {
  const meta = (sub.metadata || {}) as Record<string, string>;
  let [row] = await db.select().from(subscriptions).where(eq(subscriptions.stripeSubscriptionId, sub.id)).limit(1);
  if (!row && meta.subscription_row_id && /^[0-9a-f-]{36}$/i.test(meta.subscription_row_id)) {
    [row] = await db.select().from(subscriptions).where(eq(subscriptions.id, meta.subscription_row_id)).limit(1);
  }
  if (!row) return "ignored: unknown subscription";
  const item = sub.items?.data?.[0] as (Stripe.SubscriptionItem & { current_period_end?: number }) | undefined;
  const price = item?.price;
  const periodEnd = item?.current_period_end ?? sub.current_period_end;
  const status = deleted ? "canceled" : mapStatus(sub.status);
  await db
    .update(subscriptions)
    .set({
      stripeSubscriptionId: sub.id,
      stripeCustomerId: typeof sub.customer === "string" ? sub.customer : sub.customer?.id,
      kind: "paid",
      status,
      amountCents: price?.unit_amount ?? row.amountCents,
      currency: price?.currency ?? row.currency,
      interval: price?.recurring?.interval ?? row.interval,
      currentPeriodEnd: periodEnd ? new Date(periodEnd * 1000) : row.currentPeriodEnd,
      canceledAt: status === "canceled" ? row.canceledAt ?? new Date() : null,
    })
    .where(eq(subscriptions.id, row.id));
  return status;
}

/** checkout.session.completed in subscription mode: link the Stripe subscription id to our row. */
export async function linkCheckoutSubscription(db: Db, session: Stripe.Checkout.Session) {
  const subId = typeof session.subscription === "string" ? session.subscription : session.subscription?.id;
  const rowId = (session.metadata || {}).subscription_row_id;
  if (!subId || !rowId || !/^[0-9a-f-]{36}$/i.test(rowId)) return "ignored";
  await db.update(subscriptions).set({ stripeSubscriptionId: subId }).where(and(eq(subscriptions.id, rowId), eq(subscriptions.stripeCheckoutSessionId, session.id)));
  return "linked";
}

type Ref = string | { id: string } | null | undefined;
/** The invoice fields we read, loosely typed: their location differs between Stripe API versions. */
export type AnyInvoice = {
  id?: string;
  amount_paid?: number;
  currency: string;
  created: number;
  status_transitions?: { paid_at?: number | null } | null;
  subscription?: Ref;
  charge?: Ref;
  payment_intent?: Ref;
  tax?: number | null;
  parent?: { subscription_details?: { subscription?: Ref } | null } | null;
  payments?: { data?: { payment?: { payment_intent?: Ref; charge?: Ref } }[] } | null;
  total_taxes?: { amount: number }[] | null;
};
const idOf = (v: Ref) => (typeof v === "string" ? v : v?.id || null);

/** The fields we need from an invoice, across Stripe API versions (old: invoice.subscription/charge; new: parent, payments). */
export function invoiceFields(inv: AnyInvoice) {
  const subscriptionId = idOf(inv.subscription) || idOf(inv.parent?.subscription_details?.subscription);
  const pay = inv.payments?.data?.[0]?.payment;
  const tax = typeof inv.tax === "number" ? inv.tax : (inv.total_taxes || []).reduce((s, t) => s + (t.amount || 0), 0);
  return {
    subscriptionId,
    chargeId: idOf(inv.charge) || idOf(pay?.charge),
    paymentIntentId: idOf(inv.payment_intent) || idOf(pay?.payment_intent),
    amountPaidCents: inv.amount_paid || 0,
    taxCents: tax || 0,
    currency: inv.currency,
    paidAt: new Date((inv.status_transitions?.paid_at || inv.created) * 1000),
  };
}

export async function onInvoicePaid(db: Db, inv: AnyInvoice) {
  const f = invoiceFields(inv);
  if (!f.subscriptionId) return "ignored: not a subscription invoice";
  await db.update(subscriptions).set({ status: "active" }).where(and(eq(subscriptions.stripeSubscriptionId, f.subscriptionId), eq(subscriptions.status, "past_due")));
  const e = await recordInvoiceEarning(db, { invoiceId: inv.id!, stripeSubscriptionId: f.subscriptionId, amountPaidCents: f.amountPaidCents, taxCents: f.taxCents, currency: f.currency, chargeId: f.chargeId, paymentIntentId: f.paymentIntentId, paidAt: f.paidAt });
  return e ? "earning recorded" : "paid";
}

export async function onInvoiceFailed(db: Db, inv: AnyInvoice) {
  const f = invoiceFields(inv);
  if (!f.subscriptionId) return "ignored";
  await db.update(subscriptions).set({ status: "past_due" }).where(and(eq(subscriptions.stripeSubscriptionId, f.subscriptionId), eq(subscriptions.status, "active")));
  return "past_due";
}

export async function onChargeRefunded(db: Db, c: Stripe.Charge) {
  return applyRefund(db, { chargeId: c.id, paymentIntentId: idOf(c.payment_intent as string | null), paidCents: c.amount_captured || c.amount, refundedCents: c.amount_refunded, reason: "refund" });
}

export async function onDispute(db: Db, d: Stripe.Dispute) {
  // a chargeback: treat the whole charge as refunded for the ledger
  return applyRefund(db, { chargeId: idOf(d.charge as string), paymentIntentId: idOf(d.payment_intent as string | null), paidCents: d.amount, refundedCents: d.amount, reason: "chargeback" });
}

export async function onAccountUpdated(db: Db, acct: Stripe.Account) {
  await db.update(users).set({ connectPayoutsEnabled: !!acct.payouts_enabled }).where(eq(users.stripeConnectAccountId, acct.id));
  return "account updated";
}

// ---- reporting --------------------------------------------------------------------------------------------------

/** Monthly recurring revenue from the database: each active paid subscription's amount, normalised to a month. */
export function monthlyCents(amountCents: number | null, interval: string | null): number {
  if (!amountCents) return 0;
  switch (interval) {
    case "year": return Math.round(amountCents / 12);
    case "week": return Math.round((amountCents * 52) / 12);
    case "day": return Math.round((amountCents * 365) / 12);
    default: return amountCents;
  }
}

export async function familyName(db: Db, familyId: string) {
  const [f] = await db.select({ name: families.name }).from(families).where(eq(families.id, familyId)).limit(1);
  return f?.name || null;
}

export const subPriceTbd = () => env().SUB_PRICE_TBD;
