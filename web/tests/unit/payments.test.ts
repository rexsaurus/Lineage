import { describe, expect, it } from "vitest";
import Stripe from "stripe";
import { eq } from "drizzle-orm";
import { payments, users, families } from "@/db/schema";
import { StripePayments, handleStripeEvent, setPayments, fakeSessions } from "@/lib/payments";
import { startSignup, completeWelcome } from "@/lib/start";
import { createFamily } from "@/lib/families";
import { ctx, useEnv } from "./setup";

const SECRET = "whsec_test_secret";
const stripe = new Stripe("sk_test_dummy");

function signed(event: object) {
  const payload = JSON.stringify(event);
  return { payload, header: stripe.webhooks.generateTestHeaderString({ payload, secret: SECRET }) };
}
const completed = (id: string, userId: string, src = "test-event") => ({
  id: "evt_1", object: "event", type: "checkout.session.completed",
  data: { object: { id, object: "checkout.session", payment_status: "paid", client_reference_id: userId, metadata: { user_id: userId, src },
    amount_total: 4900, currency: "usd", customer: "cus_1", payment_intent: "pi_1", livemode: false, url: null } },
});

describe("Stripe webhook", () => {
  it("valid signature marks paid; replay is a no-op; bad signature is rejected", async () => {
    const p = new StripePayments("sk_test_dummy", "price_x", SECRET);
    const [u] = await ctx.db.insert(users).values({ email: "a@example.org", eventSource: "test-event" }).returning();
    const { payload, header } = signed(completed("cs_test_1", u.id));
    const ev = p.parseWebhook(payload, header);
    expect(await handleStripeEvent(ctx.db, ev)).toBe("paid");
    expect(await handleStripeEvent(ctx.db, ev)).toBe("paid"); // replay
    const rows = await ctx.db.select().from(payments);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ status: "paid", userId: u.id, eventSource: "test-event", amountCents: 4900, stripePaymentIntentId: "pi_1" });
    expect(() => p.parseWebhook(payload, header.replace(/v1=\w+/, "v1=deadbeef"))).toThrow();
    expect(() => p.parseWebhook(payload, null)).toThrow();
    expect(() => p.parseWebhook(payload.replace("4900", "1"), header)).toThrow(); // body tampered
  });

  it("charge.refunded marks the payment refunded", async () => {
    const [u] = await ctx.db.insert(users).values({ email: "b@example.org" }).returning();
    await handleStripeEvent(ctx.db, completed("cs_test_2", u.id) as unknown as Stripe.Event);
    await handleStripeEvent(ctx.db, { type: "charge.refunded", data: { object: { payment_intent: "pi_1", refunded: true } } } as unknown as Stripe.Event);
    const [row] = await ctx.db.select().from(payments).where(eq(payments.stripeCheckoutSessionId, "cs_test_2"));
    expect(row.status).toBe("refunded");
    // a late replay of "completed" doesn't undo the refund
    await handleStripeEvent(ctx.db, completed("cs_test_2", u.id) as unknown as Stripe.Event);
    const [again] = await ctx.db.select().from(payments).where(eq(payments.stripeCheckoutSessionId, "cs_test_2"));
    expect(again.status).toBe("refunded");
  });

  it("creates the Checkout session with the price, metadata and client_reference_id", async () => {
    let params: Stripe.Checkout.SessionCreateParams | undefined;
    const client = { checkout: { sessions: { create: async (p: Stripe.Checkout.SessionCreateParams) => { params = p; return { id: "cs_test_x", url: "https://checkout.stripe.com/c/pay/cs_test_x" }; } } } } as unknown as Stripe;
    useEnv({ PRICE_TBD: "false", PRICE_DISPLAY: "TEST", PAYMENTS_DRIVER: "stripe", STRIPE_SECRET_KEY: "sk_test_x", STRIPE_WEBHOOK_SECRET: SECRET, STRIPE_PRICE_ID_FOUNDING: "price_founding" });
    setPayments(new StripePayments("sk_test_x", "price_founding", SECRET, client));
    const r = await startSignup(ctx.db, { email: "c@example.org", src: "scchgs-writing-2026-10-20" });
    expect(r.kind).toBe("checkout");
    expect(params).toMatchObject({
      mode: "payment",
      line_items: [{ price: "price_founding", quantity: 1 }],
      customer_email: "c@example.org",
      client_reference_id: r.user.id,
      metadata: { user_id: r.user.id, src: "scchgs-writing-2026-10-20" },
      allow_promotion_codes: true,
    });
    expect(params!.success_url).toContain("/welcome?session_id={CHECKOUT_SESSION_ID}");
    const [pending] = await ctx.db.select().from(payments);
    expect(pending).toMatchObject({ status: "pending", stripeCheckoutSessionId: "cs_test_x", eventSource: "scchgs-writing-2026-10-20" });
  });

  it("refuses a live key at runtime too", () => {
    expect(() => new StripePayments("sk_live_x", "price", SECRET)).toThrow(/live Stripe key refused/);
  });
});

describe("start flow", () => {
  it("PRICE_TBD=true: reserved, no Stripe, src recorded", async () => {
    const never = () => { throw new Error("must not be called"); };
    setPayments({ createCheckout: never, createSubscriptionCheckout: never, retrieveCheckout: async () => null, parseWebhook: never });
    const r = await startSignup(ctx.db, { email: "d@example.org", src: "smcgs-2026-10-17" });
    expect(r.kind).toBe("reserved");
    const [pay] = await ctx.db.select().from(payments);
    expect(pay).toMatchObject({ status: "reserved", eventSource: "smcgs-2026-10-17", userId: r.user.id });
    expect(r.user.eventSource).toBe("smcgs-2026-10-17");
    const f = await createFamily(ctx.db, { name: "The Calders", userId: r.user.id, src: r.user.eventSource });
    const [fam] = await ctx.db.select().from(families).where(eq(families.id, f.id));
    expect(fam.eventSource).toBe("smcgs-2026-10-17");
  });

  it("first touch wins: a later visit from another event doesn't overwrite the user's source", async () => {
    await startSignup(ctx.db, { email: "e@example.org", src: "first-event" });
    const again = await startSignup(ctx.db, { email: "e@example.org", src: "second-event" });
    expect(again.user.eventSource).toBe("first-event");
  });

  it("payment link fallback carries client_reference_id and prefilled email", async () => {
    useEnv({ PRICE_TBD: "false", PRICE_DISPLAY: "TEST", STRIPE_PAYMENT_LINK_URL: "https://buy.stripe.com/test_abc" });
    const { setSetting, PAYMENT_LINK_FALLBACK } = await import("@/lib/settings");
    await setSetting(ctx.db, PAYMENT_LINK_FALLBACK, "on");
    const r = await startSignup(ctx.db, { email: "f@example.org", src: "x" });
    expect(r.kind).toBe("payment-link");
    if (r.kind === "payment-link") {
      const u = new URL(r.url);
      expect(u.searchParams.get("client_reference_id")).toBe(r.user.id);
      expect(u.searchParams.get("prefilled_email")).toBe("f@example.org");
    }
  });

  it("/welcome signs in once per paid session (fake driver), never for an unpaid one", async () => {
    useEnv({ PRICE_TBD: "false", PRICE_DISPLAY: "TEST" });
    const r = await startSignup(ctx.db, { email: "g@example.org", src: "x" });
    const id = new URL(r.kind === "checkout" ? r.url : "", "http://x").searchParams.get("session")!;
    expect(await completeWelcome(ctx.db, id)).toEqual({ status: "unpaid" });
    fakeSessions.get(id)!.paid = true;
    expect(await completeWelcome(ctx.db, id)).toMatchObject({ status: "paid", signIn: true });
    expect(await completeWelcome(ctx.db, id)).toMatchObject({ status: "paid", signIn: false });
    expect(await completeWelcome(ctx.db, "cs_unknown")).toEqual({ status: "unknown" });
  });
});
