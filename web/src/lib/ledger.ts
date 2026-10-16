import { and, eq, inArray, isNull, lte, sql } from "drizzle-orm";
import type { Db } from "@/db";
import { earnings, payouts, subscriptions, users } from "@/db/schema";
import { minPayoutCents, refundHoldDays, revShareBps } from "@/env";
import { connectProvider } from "./connect";

// The referral ledger. Rules:
//  - One 'share' row per paid invoice of a subscription a referrer brought in: amount = floor(net × share), where
//    net = amount paid − tax, and share = REV_SHARE_PCT (basis points). Rounding is always down: never overpay.
//  - While REV_SHARE_PCT is unset the program isn't open: rows are still written, with amount 0 and share null.
//  - Rows are 'pending' until REFUND_HOLD_DAYS after payment, then 'available'. With no hold period decided, they stay
//    pending (nothing can be paid out).
//  - A refund or chargeback before payout lowers or reverses the row; after payout it adds a negative 'clawback' row
//    that comes off the next payout. Every write is idempotent (keyed by invoice), so webhook replays change nothing.

export function shareCents(netCents: number, bps: number | null): number {
  if (!bps || netCents <= 0) return 0;
  return Math.floor((netCents * bps) / 10000);
}

/** Net after a cumulative refund: the refunded part of the charge comes off the net proportionally. */
export function netAfterRefund(netCents: number, paidCents: number, refundedCents: number): number {
  if (paidCents <= 0 || refundedCents >= paidCents) return 0;
  return Math.floor((netCents * (paidCents - refundedCents)) / paidCents);
}

const DAY = 86400_000;

export type PaidInvoice = {
  invoiceId: string;
  stripeSubscriptionId: string;
  amountPaidCents: number;
  taxCents: number;
  currency: string;
  chargeId: string | null;
  paymentIntentId: string | null;
  paidAt: Date;
};

/** invoice.paid → a ledger row, if the subscription has a referrer. Returns the row, or null. */
export async function recordInvoiceEarning(db: Db, inv: PaidInvoice) {
  const [sub] = await db.select().from(subscriptions).where(eq(subscriptions.stripeSubscriptionId, inv.stripeSubscriptionId)).limit(1);
  if (!sub?.referrerUserId || sub.referrerUserId === sub.userId) return null;
  const bps = revShareBps();
  const net = Math.max(0, inv.amountPaidCents - inv.taxCents);
  const hold = refundHoldDays();
  const [row] = await db
    .insert(earnings)
    .values({
      referrerUserId: sub.referrerUserId,
      subscriptionId: sub.id,
      stripeInvoiceId: inv.invoiceId,
      stripeChargeId: inv.chargeId,
      stripePaymentIntentId: inv.paymentIntentId,
      kind: "share",
      invoiceNetCents: net,
      shareBps: bps,
      amountCents: shareCents(net, bps),
      currency: inv.currency,
      status: "pending",
      paidAt: inv.paidAt,
      availableAt: hold === null ? null : new Date(inv.paidAt.getTime() + hold * DAY),
      note: bps === null ? "earnings program not yet open" : null,
    })
    .onConflictDoNothing()
    .returning();
  return row || null;
}

/** charge.refunded / charge.dispute.created. refundedCents is cumulative for the charge (Stripe's amount_refunded). */
export async function applyRefund(db: Db, a: { chargeId?: string | null; paymentIntentId?: string | null; paidCents: number; refundedCents: number; reason: string }) {
  const conds = [a.chargeId ? eq(earnings.stripeChargeId, a.chargeId) : null, a.paymentIntentId ? eq(earnings.stripePaymentIntentId, a.paymentIntentId) : null].filter(Boolean);
  if (!conds.length) return null;
  const rows = await db
    .select()
    .from(earnings)
    .where(and(eq(earnings.kind, "share"), conds.length === 2 ? sql`(${conds[0]} or ${conds[1]})` : conds[0]!));
  for (const row of rows) {
    const newNet = netAfterRefund(row.invoiceNetCents, a.paidCents, a.refundedCents);
    const newAmount = shareCents(newNet, row.shareBps);
    const full = a.refundedCents >= a.paidCents;
    if (row.status === "pending" || row.status === "available") {
      await db
        .update(earnings)
        .set(full ? { status: "reversed", reversedAt: new Date(), note: a.reason } : { amountCents: Math.min(row.amountCents, newAmount), note: a.reason })
        .where(and(eq(earnings.id, row.id), inArray(earnings.status, ["pending", "available"])));
    } else if (row.status === "paid") {
      // already paid out: claw back the difference from the next payout (one clawback row per invoice, kept current)
      const owed = row.amountCents - newAmount;
      if (owed <= 0) continue;
      const [existing] = await db.select().from(earnings).where(and(eq(earnings.stripeInvoiceId, row.stripeInvoiceId!), eq(earnings.kind, "clawback"))).limit(1);
      if (!existing) {
        await db
          .insert(earnings)
          .values({
            referrerUserId: row.referrerUserId, subscriptionId: row.subscriptionId, stripeInvoiceId: row.stripeInvoiceId, stripeChargeId: row.stripeChargeId,
            stripePaymentIntentId: row.stripePaymentIntentId, kind: "clawback", invoiceNetCents: 0, shareBps: row.shareBps, amountCents: -owed,
            currency: row.currency, status: "available", availableAt: new Date(), note: a.reason,
          })
          .onConflictDoNothing();
      } else if (existing.payoutId === null && existing.amountCents !== -owed) {
        await db.update(earnings).set({ amountCents: -owed, note: a.reason }).where(eq(earnings.id, existing.id));
      }
    }
  }
  return rows.length;
}

/** Pending rows past their hold become available. With a hold period now set, undated rows get their date. */
export async function releaseAvailable(db: Db, now = new Date()) {
  const hold = refundHoldDays();
  if (hold === null) return 0;
  await db
    .update(earnings)
    .set({ availableAt: sql`coalesce(${earnings.paidAt}, ${earnings.createdAt}) + make_interval(days => ${hold}::int)` })
    .where(and(eq(earnings.status, "pending"), isNull(earnings.availableAt)));
  const r = await db
    .update(earnings)
    .set({ status: "available" })
    .where(and(eq(earnings.status, "pending"), lte(earnings.availableAt, now)))
    .returning({ id: earnings.id });
  return r.length;
}

export type Balances = { currency: string; pending: number; available: number; paid: number; reversed: number }[];

export async function balances(db: Db, userId: string): Promise<Balances> {
  const r = (await db.execute(sql`
    select currency,
      coalesce(sum(amount_cents) filter (where status = 'pending'), 0) as pending,
      coalesce(sum(amount_cents) filter (where status = 'available' and payout_id is null), 0) as available,
      coalesce(sum(amount_cents) filter (where status = 'paid'), 0) as paid,
      coalesce(sum(amount_cents) filter (where status = 'reversed'), 0) as reversed
    from earnings where referrer_user_id = ${userId} group by currency order by currency`)) as unknown as { rows: Record<string, string | number>[] };
  return r.rows.map(x => ({ currency: String(x.currency), pending: Number(x.pending), available: Number(x.available), paid: Number(x.paid), reversed: Number(x.reversed) }));
}

export type PayoutResult = { ok: true; payoutId: string; amountCents: number; currency: string } | { ok: false; reason: string };

/** Pays a referrer's whole available balance in one currency through Stripe Connect (fake in development). */
export async function payOut(db: Db, a: { userId: string; currency: string; approvedBy: string }): Promise<PayoutResult> {
  const [u] = await db.select().from(users).where(eq(users.id, a.userId)).limit(1);
  if (!u?.stripeConnectAccountId || !u.connectPayoutsEnabled) return { ok: false, reason: "The archivist hasn't finished setting up payouts with Stripe." };
  const [p] = await db.insert(payouts).values({ userId: a.userId, amountCents: 0, currency: a.currency, status: "pending", approvedBy: a.approvedBy }).returning();
  // claim every available, unclaimed row atomically for this payout
  const claimed = await db
    .update(earnings)
    .set({ payoutId: p.id })
    .where(and(eq(earnings.referrerUserId, a.userId), eq(earnings.currency, a.currency), eq(earnings.status, "available"), isNull(earnings.payoutId)))
    .returning({ amount: earnings.amountCents });
  const amount = claimed.reduce((s, r) => s + r.amount, 0);
  const release = async (reason: string) => {
    await db.update(earnings).set({ payoutId: null }).where(eq(earnings.payoutId, p.id));
    await db.update(payouts).set({ status: "failed", failure: reason, amountCents: amount }).where(eq(payouts.id, p.id));
    return { ok: false as const, reason };
  };
  if (amount <= 0) return release("Nothing is available to pay out.");
  if (amount < minPayoutCents()) return release("The available balance is below the minimum payout.");
  try {
    const t = await connectProvider().transfer({ amountCents: amount, currency: a.currency, destination: u.stripeConnectAccountId, idempotencyKey: `payout-${p.id}`, metadata: { payout_id: p.id, user_id: a.userId } });
    await db.update(payouts).set({ status: "paid", stripeTransferId: t.id, amountCents: amount, paidAt: new Date() }).where(eq(payouts.id, p.id));
    await db.update(earnings).set({ status: "paid" }).where(eq(earnings.payoutId, p.id));
    return { ok: true, payoutId: p.id, amountCents: amount, currency: a.currency };
  } catch (err) {
    return release(err instanceof Error ? err.message.slice(0, 200) : "transfer failed");
  }
}

/** Optional monthly cron (PAYOUT_CRON_ENABLED): everyone with an available balance and payouts set up. */
export async function payOutEveryone(db: Db): Promise<number> {
  await releaseAvailable(db);
  const r = (await db.execute(sql`
    select e.referrer_user_id as uid, e.currency from earnings e join users u on u.id = e.referrer_user_id
    where e.status = 'available' and e.payout_id is null and u.connect_payouts_enabled
    group by 1, 2 having sum(e.amount_cents) > 0`)) as unknown as { rows: { uid: string; currency: string }[] };
  let n = 0;
  for (const x of r.rows) if ((await payOut(db, { userId: x.uid, currency: x.currency, approvedBy: "cron" })).ok) n++;
  return n;
}
