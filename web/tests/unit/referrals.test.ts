import { describe, expect, it } from "vitest";
import type Stripe from "stripe";
import { NextRequest } from "next/server";
import { eq } from "drizzle-orm";
import { earnings, subscriptions, users, payouts } from "@/db/schema";
import { revShareBps } from "@/env";
import { shareCents, netAfterRefund, releaseAvailable, balances, payOut } from "@/lib/ledger";
import { createFamily, addRecord, familyForReader, listRecords } from "@/lib/families";
import { ensureRefCode, resolveReferrer, REF_COOKIE } from "@/lib/refs";
import { follow, monthlyCents } from "@/lib/subscriptions";
import { handleEvent } from "@/lib/webhooks";
import { setConnect, FakeConnect, fakeConnect } from "@/lib/connect";
import { periodKey, runDigests, unsubscribeToken, readUnsubscribeToken } from "@/lib/digest";
import { logActivity } from "@/lib/activity";
import { proxy } from "@/proxy";
import { ctx, useEnv, sent } from "./setup";

const ev = (type: string, object: object) => ({ id: `evt_${Math.random()}`, type, data: { object } }) as unknown as Stripe.Event;
const DAY = 86400_000;

async function user(email: string, name: string | null = null) {
  const [u] = await ctx.db.insert(users).values({ email, name }).returning();
  return u;
}

/** An archivist with a family, a relative subscribed through the archivist's code, linked to a Stripe subscription. */
async function referredSubscription(opts: { subId?: string } = {}) {
  const arch = await user(`arch-${Math.random()}@example.org`, "Pat");
  const rel = await user(`rel-${Math.random()}@example.org`, "Sam");
  const fam = await createFamily(ctx.db, { name: "The Calders", userId: arch.id, src: null });
  const code = await ensureRefCode(ctx.db, arch.id);
  const referrer = await resolveReferrer(ctx.db, { refCode: code, familyId: fam.id, subscriberUserId: rel.id });
  const subId = opts.subId || `sub_${Math.random().toString(36).slice(2)}`;
  const [row] = await ctx.db
    .insert(subscriptions)
    .values({ familyId: fam.id, userId: rel.id, kind: "paid", status: "incomplete", referrerUserId: referrer, refCode: code, stripeSubscriptionId: subId })
    .returning();
  return { arch, rel, fam, code, subId, row };
}

const invoice = (id: string, subId: string, paid: number, opts: { tax?: number; at?: number; charge?: string } = {}) =>
  ev("invoice.paid", { id, subscription: subId, amount_paid: paid, tax: opts.tax ?? 0, currency: "usd", charge: opts.charge ?? `ch_${id}`, payment_intent: `pi_${id}`, created: opts.at ?? Math.floor(Date.now() / 1000), status_transitions: { paid_at: opts.at ?? Math.floor(Date.now() / 1000) } });

describe("ledger math", () => {
  it("rounds down, never overpays; no share while the program isn't open", () => {
    expect(shareCents(999, 2000)).toBe(199); // 199.8 → 199
    expect(shareCents(1000, 1250)).toBe(125);
    expect(shareCents(1, 2000)).toBe(0);
    expect(shareCents(1000, null)).toBe(0);
    expect(shareCents(-5, 2000)).toBe(0);
    expect(netAfterRefund(900, 1000, 250)).toBe(675);
    expect(netAfterRefund(900, 1000, 1000)).toBe(0);
  });
  it("reads REV_SHARE_PCT as basis points, with no default", () => {
    useEnv({ REV_SHARE_PCT: "12.5" });
    expect(revShareBps()).toBe(1250);
    useEnv({});
    expect(revShareBps()).toBeNull();
    useEnv({ REV_SHARE_PCT: "150" });
    expect(() => revShareBps()).toThrow();
  });
});

describe("earnings from invoices", () => {
  it("one row per paid invoice (webhook replay is a no-op), net of tax, with the hold period", async () => {
    useEnv({ REV_SHARE_PCT: "20", REFUND_HOLD_DAYS: "14" });
    const s = await referredSubscription();
    const paidAt = Math.floor(Date.now() / 1000);
    const e = invoice("in_1", s.subId, 1099, { tax: 99, at: paidAt });
    expect(await handleEvent(ctx.db, e)).toBe("earning recorded");
    expect(await handleEvent(ctx.db, e)).toBe("paid"); // replay: nothing new
    const rows = await ctx.db.select().from(earnings);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ referrerUserId: s.arch.id, invoiceNetCents: 1000, shareBps: 2000, amountCents: 200, currency: "usd", status: "pending" });
    expect(rows[0].availableAt!.getTime()).toBe(paidAt * 1000 + 14 * DAY);
    expect(await releaseAvailable(ctx.db, new Date(paidAt * 1000 + 13 * DAY))).toBe(0);
    expect(await releaseAvailable(ctx.db, new Date(paidAt * 1000 + 14 * DAY + 1))).toBe(1);
    expect((await balances(ctx.db, s.arch.id))[0]).toMatchObject({ pending: 0, available: 200, paid: 0 });
  });

  it("program not open: tracked as 0; no hold period decided: stays pending until one is set", async () => {
    useEnv({});
    const s = await referredSubscription();
    await handleEvent(ctx.db, invoice("in_2", s.subId, 1000, { at: Math.floor((Date.now() - 400 * DAY) / 1000) }));
    const [row] = await ctx.db.select().from(earnings);
    expect(row).toMatchObject({ amountCents: 0, shareBps: null, status: "pending", availableAt: null, note: "earnings program not yet open" });
    expect(await releaseAvailable(ctx.db)).toBe(0);
    useEnv({ REFUND_HOLD_DAYS: "30" });
    expect(await releaseAvailable(ctx.db)).toBe(1); // created long ago, so past the new hold
  });

  it("no referrer, no earning; invoices of unknown subscriptions are ignored", async () => {
    useEnv({ REV_SHARE_PCT: "20" });
    const rel = await user("solo@example.org");
    const arch = await user("a2@example.org");
    const fam = await createFamily(ctx.db, { name: "F", userId: arch.id, src: null });
    await ctx.db.insert(subscriptions).values({ familyId: fam.id, userId: rel.id, kind: "paid", status: "active", stripeSubscriptionId: "sub_noref" });
    await handleEvent(ctx.db, invoice("in_3", "sub_noref", 1000));
    await handleEvent(ctx.db, invoice("in_4", "sub_unknown", 1000));
    expect(await ctx.db.select().from(earnings)).toHaveLength(0);
  });
});

describe("refunds and chargebacks", () => {
  it("partial refund lowers a pending earning; full refund reverses it; replays change nothing", async () => {
    useEnv({ REV_SHARE_PCT: "20", REFUND_HOLD_DAYS: "14" });
    const s = await referredSubscription();
    await handleEvent(ctx.db, invoice("in_5", s.subId, 1000, { charge: "ch_5" }));
    const partial = ev("charge.refunded", { id: "ch_5", payment_intent: "pi_in_5", amount: 1000, amount_captured: 1000, amount_refunded: 250, refunded: false });
    await handleEvent(ctx.db, partial);
    await handleEvent(ctx.db, partial);
    let [row] = await ctx.db.select().from(earnings);
    expect(row).toMatchObject({ amountCents: 150, status: "pending" }); // 750 × 20%
    await handleEvent(ctx.db, ev("charge.refunded", { id: "ch_5", payment_intent: "pi_in_5", amount: 1000, amount_captured: 1000, amount_refunded: 1000, refunded: true }));
    [row] = await ctx.db.select().from(earnings);
    expect(row.status).toBe("reversed");
  });

  it("a chargeback after payout claws the earning back from the next payout", async () => {
    useEnv({ REV_SHARE_PCT: "20", REFUND_HOLD_DAYS: "0" });
    setConnect(new FakeConnect());
    const s = await referredSubscription();
    const acct = await new FakeConnect().createAccount();
    fakeConnect.accounts.get(acct.id)!.payoutsEnabled = true;
    await ctx.db.update(users).set({ stripeConnectAccountId: acct.id, connectPayoutsEnabled: true }).where(eq(users.id, s.arch.id));
    await handleEvent(ctx.db, invoice("in_6", s.subId, 1000, { charge: "ch_6" }));
    await releaseAvailable(ctx.db);
    const p1 = await payOut(ctx.db, { userId: s.arch.id, currency: "usd", approvedBy: "rex" });
    expect(p1).toMatchObject({ ok: true, amountCents: 200 });
    await handleEvent(ctx.db, ev("charge.dispute.created", { id: "dp_1", charge: "ch_6", payment_intent: "pi_in_6", amount: 1000 }));
    await handleEvent(ctx.db, ev("charge.dispute.created", { id: "dp_1", charge: "ch_6", payment_intent: "pi_in_6", amount: 1000 })); // replay
    const claw = (await ctx.db.select().from(earnings)).filter(r => r.kind === "clawback");
    expect(claw).toHaveLength(1);
    expect(claw[0]).toMatchObject({ amountCents: -200, status: "available" });
    expect((await balances(ctx.db, s.arch.id))[0]).toMatchObject({ available: -200, paid: 200 });
    // next month's invoice nets against it
    await handleEvent(ctx.db, invoice("in_7", s.subId, 1500, { charge: "ch_7" }));
    await releaseAvailable(ctx.db);
    const p2 = await payOut(ctx.db, { userId: s.arch.id, currency: "usd", approvedBy: "rex" });
    expect(p2).toMatchObject({ ok: true, amountCents: 100 }); // 300 − 200
    setConnect(null);
  });
});

describe("payouts", () => {
  it("need Stripe set up, respect the minimum, pay once, and fail safely", async () => {
    useEnv({ REV_SHARE_PCT: "20", REFUND_HOLD_DAYS: "0", MIN_PAYOUT_CENTS: "500" });
    setConnect(new FakeConnect());
    const s = await referredSubscription();
    await handleEvent(ctx.db, invoice("in_8", s.subId, 1000));
    await releaseAvailable(ctx.db);
    expect(await payOut(ctx.db, { userId: s.arch.id, currency: "usd", approvedBy: "rex" })).toMatchObject({ ok: false, reason: /setting up payouts/ });
    const acct = await new FakeConnect().createAccount();
    fakeConnect.accounts.get(acct.id)!.payoutsEnabled = true;
    await ctx.db.update(users).set({ stripeConnectAccountId: acct.id, connectPayoutsEnabled: true }).where(eq(users.id, s.arch.id));
    expect(await payOut(ctx.db, { userId: s.arch.id, currency: "usd", approvedBy: "rex" })).toMatchObject({ ok: false, reason: /below the minimum/ });
    expect((await balances(ctx.db, s.arch.id))[0].available).toBe(200); // released back
    useEnv({ REV_SHARE_PCT: "20", REFUND_HOLD_DAYS: "0" });
    const ok = await payOut(ctx.db, { userId: s.arch.id, currency: "usd", approvedBy: "rex" });
    expect(ok).toMatchObject({ ok: true, amountCents: 200 });
    expect(await payOut(ctx.db, { userId: s.arch.id, currency: "usd", approvedBy: "rex" })).toMatchObject({ ok: false, reason: /Nothing is available/ });
    expect((await balances(ctx.db, s.arch.id))[0]).toMatchObject({ available: 0, paid: 200 });
    const paid = (await ctx.db.select().from(payouts)).filter(p => p.status === "paid");
    expect(paid).toHaveLength(1);
    setConnect(null);
  });
});

describe("attribution", () => {
  it("blocks self-referral, codes from non-archivists, and unknown codes", async () => {
    const arch = await user("own@example.org");
    const member = await user("mem@example.org");
    const rel = await user("r@example.org");
    const fam = await createFamily(ctx.db, { name: "F", userId: arch.id, src: null });
    const { familyMembers } = await import("@/db/schema");
    await ctx.db.insert(familyMembers).values({ familyId: fam.id, userId: member.id, role: "member" });
    const code = await ensureRefCode(ctx.db, arch.id);
    expect(await ensureRefCode(ctx.db, arch.id)).toBe(code); // stable
    expect(await resolveReferrer(ctx.db, { refCode: code, familyId: fam.id, subscriberUserId: rel.id })).toBe(arch.id);
    expect(await resolveReferrer(ctx.db, { refCode: code, familyId: fam.id, subscriberUserId: arch.id })).toBeNull(); // self
    const memberCode = await ensureRefCode(ctx.db, member.id);
    expect(await resolveReferrer(ctx.db, { refCode: memberCode, familyId: fam.id, subscriberUserId: rel.id })).toBeNull();
    expect(await resolveReferrer(ctx.db, { refCode: "zzzzzzzz", familyId: fam.id, subscriberUserId: rel.id })).toBeNull();
    expect(await resolveReferrer(ctx.db, { refCode: "not a code", familyId: fam.id, subscriberUserId: rel.id })).toBeNull();
    const s = await follow(ctx.db, { familyId: fam.id, userId: arch.id, refCode: code });
    expect(s.referrerUserId).toBeNull();
  });

  it("the referral cookie is first-touch, 60 days, valid codes only", () => {
    const set = (url: string, cookie?: string) => {
      const req = new NextRequest(url, { headers: cookie ? { cookie } : {} });
      return proxy(req).cookies.get(REF_COOKIE);
    };
    const c = set("https://app.example.org/f/x?ref=abcdefgh");
    expect(c?.value).toBe("abcdefgh");
    expect(c?.maxAge).toBe(60 * 86400);
    expect(c?.httpOnly).toBe(true);
    expect(set("https://app.example.org/f/x?ref=hjkmnpqr", `${REF_COOKIE}=abcdefgh`)).toBeUndefined(); // first touch wins
    expect(set("https://app.example.org/f/x?ref=BAD!")).toBeUndefined();
  });
});

describe("subscriptions and access", () => {
  it("webhooks set the state idempotently; deletion removes read access; subscribers never see private records", async () => {
    const s = await referredSubscription({ subId: "sub_state" });
    const subObj = (status: string) => ({ id: "sub_state", status, customer: "cus_1", metadata: {}, items: { data: [{ current_period_end: 1900000000, price: { unit_amount: 1200, currency: "usd", recurring: { interval: "year" } } }] } });
    await handleEvent(ctx.db, ev("customer.subscription.created", subObj("active")));
    await handleEvent(ctx.db, ev("customer.subscription.created", subObj("active")));
    let [row] = await ctx.db.select().from(subscriptions).where(eq(subscriptions.id, s.row.id));
    expect(row).toMatchObject({ status: "active", amountCents: 1200, interval: "year", currency: "usd" });
    expect(monthlyCents(row.amountCents, row.interval)).toBe(100);
    const viewer = { id: s.rel.id, isAdmin: false };
    await addRecord(ctx.db, { familyId: s.fam.id, userId: s.arch.id, body: Buffer.from("%PDF-1"), sniffed: { mime: "application/pdf", ext: "pdf", kind: "document" }, caption: "Shared", isPrivate: false });
    await addRecord(ctx.db, { familyId: s.fam.id, userId: s.arch.id, body: Buffer.from("%PDF-1"), sniffed: { mime: "application/pdf", ext: "pdf", kind: "document" }, caption: "Secret", isPrivate: true });
    expect((await familyForReader(ctx.db, s.fam.id, viewer))?.access).toBe("subscriber");
    expect((await listRecords(ctx.db, s.fam.id, { includePrivate: false })).map(r => r.caption)).toEqual(["Shared"]);
    await handleEvent(ctx.db, invoice("in_f", "sub_state", 1200).type === "invoice.paid" ? ev("invoice.payment_failed", { id: "in_f", subscription: "sub_state", currency: "usd", created: 0 }) : ev("x", {}));
    [row] = await ctx.db.select().from(subscriptions).where(eq(subscriptions.id, s.row.id));
    expect(row.status).toBe("past_due");
    expect(await familyForReader(ctx.db, s.fam.id, viewer)).not.toBeNull(); // grace while Stripe retries
    await handleEvent(ctx.db, ev("customer.subscription.deleted", subObj("canceled")));
    [row] = await ctx.db.select().from(subscriptions).where(eq(subscriptions.id, s.row.id));
    expect(row.status).toBe("canceled");
    expect(await familyForReader(ctx.db, s.fam.id, viewer)).toBeNull();
  });
});

describe("digests", () => {
  it("weekly by default, once per period, only public changes by others, honours 'off', signed unsubscribe", async () => {
    const arch = await user("dig-a@example.org", "Pat");
    const rel = await user("dig-r@example.org", "Sam");
    const fam = await createFamily(ctx.db, { name: "The Calders", userId: arch.id, src: null });
    const t0 = new Date("2026-10-12T12:00:00Z"); // a Monday
    const s = await follow(ctx.db, { familyId: fam.id, userId: rel.id, refCode: null });
    await ctx.db.update(subscriptions).set({ createdAt: t0 }).where(eq(subscriptions.id, s.id));
    expect(s.digestFreq).toBe("weekly");
    await logActivity(ctx.db, { familyId: fam.id, kind: "record_added", summary: "A new photo: Grandma Rose, 1952", actorUserId: arch.id, at: new Date("2026-10-14T12:00:00Z") });
    await logActivity(ctx.db, { familyId: fam.id, kind: "record_added", summary: "SECRET item", actorUserId: arch.id, isPrivate: true, at: new Date("2026-10-14T13:00:00Z") });
    await logActivity(ctx.db, { familyId: fam.id, kind: "record_added", summary: "Sam's own upload", actorUserId: rel.id, at: new Date("2026-10-14T14:00:00Z") });
    expect(await runDigests(ctx.db, new Date("2026-10-16T12:00:00Z"))).toBe(0); // same week they subscribed
    const nextWeek = new Date("2026-10-19T12:00:00Z");
    expect(await runDigests(ctx.db, nextWeek)).toBe(1);
    expect(await runDigests(ctx.db, nextWeek)).toBe(0); // once per period
    const d = sent.find(m => m.kind === "digest")!;
    expect(d.subject).toBe("What's new on the The Calders family page");
    expect(d.text).toContain("Grandma Rose, 1952");
    expect(d.text).not.toContain("SECRET");
    expect(d.text).not.toContain("Sam's own upload");
    expect(d.headers?.["List-Unsubscribe-Post"]).toBe("List-Unsubscribe=One-Click");
    // nothing new the following week → no email
    expect(await runDigests(ctx.db, new Date("2026-10-26T12:00:00Z"))).toBe(0);
    // unsubscribe
    const tok = unsubscribeToken(s.id);
    expect(readUnsubscribeToken(tok)).toBe(s.id);
    expect(readUnsubscribeToken(tok.slice(0, -3) + "abc")).toBeNull();
    await ctx.db.update(subscriptions).set({ digestFreq: "off" }).where(eq(subscriptions.id, s.id));
    await logActivity(ctx.db, { familyId: fam.id, kind: "member_joined", summary: "Lee joined", actorUserId: arch.id, at: new Date("2026-10-27T12:00:00Z") });
    expect(await runDigests(ctx.db, new Date("2026-11-03T12:00:00Z"))).toBe(0);
  });

  it("period keys", () => {
    expect(periodKey("weekly", new Date("2026-10-19T00:00:00Z"))).toBe("2026-W43");
    expect(periodKey("weekly", new Date("2026-10-18T23:59:00Z"))).toBe("2026-W42");
    expect(periodKey("weekly", new Date("2027-01-01T00:00:00Z"))).toBe("2026-W53");
    expect(periodKey("monthly", new Date("2026-10-31T23:00:00Z"))).toBe("2026-10");
  });
});
