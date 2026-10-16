import Stripe from "stripe";
import { and, eq } from "drizzle-orm";
import type { Db } from "@/db";
import { payments } from "@/db/schema";
import { env } from "@/env";

// Payments (spec §6). Stripe Checkout in test mode; the webhook is the source of truth. A "fake" driver stands in for
// Stripe in development and tests: no network, no keys, nothing charged.
export type CheckoutSession = {
  id: string;
  url: string | null;
  paid: boolean;
  clientReferenceId: string | null;
  userId: string | null;
  src: string | null;
  amountCents: number | null;
  currency: string | null;
  customerId: string | null;
  paymentIntentId: string | null;
  livemode: boolean;
};

export interface Payments {
  createCheckout(a: { userId: string; email: string; src: string; successUrl: string; cancelUrl: string }): Promise<{ id: string; url: string }>;
  retrieveCheckout(id: string): Promise<CheckoutSession | null>;
  /** verifies the signature; throws on a bad one */
  parseWebhook(rawBody: string, signature: string | null): Stripe.Event;
}

function fromStripe(s: Stripe.Checkout.Session): CheckoutSession {
  return {
    id: s.id,
    url: s.url,
    paid: s.payment_status === "paid",
    clientReferenceId: s.client_reference_id,
    userId: (s.metadata?.user_id as string) || null,
    src: (s.metadata?.src as string) || null,
    amountCents: s.amount_total,
    currency: s.currency,
    customerId: typeof s.customer === "string" ? s.customer : s.customer?.id || null,
    paymentIntentId: typeof s.payment_intent === "string" ? s.payment_intent : s.payment_intent?.id || null,
    livemode: s.livemode,
  };
}

export class StripePayments implements Payments {
  private stripe: Stripe;
  constructor(secretKey: string, private priceId: string, private webhookSecret: string, client?: Stripe) {
    if (secretKey.startsWith("sk_live_") && !env().ALLOW_LIVE_STRIPE) throw new Error("live Stripe key refused (ALLOW_LIVE_STRIPE is not set)");
    this.stripe = client || new Stripe(secretKey);
  }
  async createCheckout(a: { userId: string; email: string; src: string; successUrl: string; cancelUrl: string }) {
    const s = await this.stripe.checkout.sessions.create({
      mode: "payment",
      line_items: [{ price: this.priceId, quantity: 1 }],
      customer_email: a.email,
      client_reference_id: a.userId,
      metadata: { user_id: a.userId, src: a.src },
      payment_intent_data: { metadata: { user_id: a.userId, src: a.src } },
      allow_promotion_codes: true,
      success_url: a.successUrl,
      cancel_url: a.cancelUrl,
    });
    return { id: s.id, url: s.url! };
  }
  async retrieveCheckout(id: string) {
    if (!/^cs_[A-Za-z0-9_]+$/.test(id)) return null;
    try {
      return fromStripe(await this.stripe.checkout.sessions.retrieve(id));
    } catch {
      return null;
    }
  }
  parseWebhook(rawBody: string, signature: string | null) {
    if (!signature) throw new Error("missing signature");
    return this.stripe.webhooks.constructEvent(rawBody, signature, this.webhookSecret);
  }
}

// ---- fake driver: sessions live in memory; /dev/fake-checkout "pays" them and runs the same webhook handler
type FakeState = Map<string, CheckoutSession>;
const g = globalThis as unknown as { __fakeCheckout?: FakeState };
export const fakeSessions: FakeState = (g.__fakeCheckout ??= new Map());

export class FakePayments implements Payments {
  async createCheckout(a: { userId: string; email: string; src: string; successUrl: string; cancelUrl: string }) {
    const id = `cs_test_fake_${Math.random().toString(36).slice(2, 12)}`;
    fakeSessions.set(id, {
      id, url: null, paid: false, clientReferenceId: a.userId, userId: a.userId, src: a.src,
      amountCents: null, currency: null, customerId: null, paymentIntentId: `pi_fake_${id.slice(-10)}`, livemode: false,
    });
    const u = new URL("/dev/fake-checkout", env().APP_URL);
    u.searchParams.set("session", id);
    u.searchParams.set("success", a.successUrl);
    u.searchParams.set("cancel", a.cancelUrl);
    return { id, url: u.pathname + u.search };
  }
  async retrieveCheckout(id: string) {
    return fakeSessions.get(id) || null;
  }
  parseWebhook(): Stripe.Event {
    throw new Error("the fake driver has no webhook; /dev/fake-checkout calls the handler directly");
  }
}

let override: Payments | null = null;
export function setPayments(p: Payments | null) {
  override = p;
}
export function paymentsProvider(): Payments {
  if (override) return override;
  const e = env();
  if (e.PAYMENTS_DRIVER === "stripe") return new StripePayments(e.STRIPE_SECRET_KEY!, e.STRIPE_PRICE_ID_FOUNDING!, e.STRIPE_WEBHOOK_SECRET!);
  return new FakePayments();
}

// ---- recording payments (shared by the webhook, /welcome and the fake checkout); every write is idempotent

export async function recordPending(db: Db, a: { userId: string; sessionId: string; src: string }) {
  await db
    .insert(payments)
    .values({ userId: a.userId, stripeCheckoutSessionId: a.sessionId, status: "pending", eventSource: a.src, priceId: env().STRIPE_PRICE_ID_FOUNDING || null })
    .onConflictDoNothing({ target: payments.stripeCheckoutSessionId });
}

export async function recordReserved(db: Db, a: { userId: string; src: string }) {
  const existing = await db.select({ id: payments.id }).from(payments).where(and(eq(payments.userId, a.userId), eq(payments.status, "reserved"))).limit(1);
  if (!existing.length) await db.insert(payments).values({ userId: a.userId, status: "reserved", eventSource: a.src });
}

/** Marks a checkout session paid. Safe to call any number of times. Returns the payment row. */
export async function markPaid(db: Db, s: CheckoutSession) {
  const userId = s.userId || s.clientReferenceId;
  const values = {
    userId: userId && /^[0-9a-f-]{36}$/i.test(userId) ? userId : null,
    stripeCheckoutSessionId: s.id,
    stripeCustomerId: s.customerId,
    stripePaymentIntentId: s.paymentIntentId,
    amountCents: s.amountCents,
    currency: s.currency,
    status: "paid",
    eventSource: s.src,
    livemode: s.livemode,
    paidAt: new Date(),
  };
  const [row] = await db
    .insert(payments)
    .values(values)
    .onConflictDoUpdate({
      target: payments.stripeCheckoutSessionId,
      // only a pending row moves to paid; a row already paid (a replayed event) or refunded is left alone
      set: {
        stripeCustomerId: values.stripeCustomerId,
        stripePaymentIntentId: values.stripePaymentIntentId,
        amountCents: values.amountCents,
        currency: values.currency,
        livemode: values.livemode,
        status: "paid",
        paidAt: values.paidAt,
      },
      setWhere: eq(payments.status, "pending"),
    })
    .returning();
  if (row) return row;
  const [cur] = await db.select().from(payments).where(eq(payments.stripeCheckoutSessionId, s.id)).limit(1);
  return cur;
}

/** The webhook (spec §6): checkout.session.completed, checkout.session.async_payment_failed, charge.refunded. */
export async function handleStripeEvent(db: Db, event: Stripe.Event): Promise<string> {
  switch (event.type) {
    case "checkout.session.completed":
    case "checkout.session.async_payment_succeeded": {
      const s = fromStripe(event.data.object as Stripe.Checkout.Session);
      if (!s.paid) return "ignored: not paid yet";
      await markPaid(db, s);
      return "paid";
    }
    case "checkout.session.async_payment_failed": {
      const s = event.data.object as Stripe.Checkout.Session;
      await db.update(payments).set({ status: "failed" }).where(and(eq(payments.stripeCheckoutSessionId, s.id), eq(payments.status, "pending")));
      return "failed";
    }
    case "charge.refunded": {
      const c = event.data.object as Stripe.Charge;
      const pi = typeof c.payment_intent === "string" ? c.payment_intent : c.payment_intent?.id;
      if (!pi || !c.refunded) return "ignored: partial refund";
      await db.update(payments).set({ status: "refunded" }).where(eq(payments.stripePaymentIntentId, pi));
      return "refunded";
    }
    default:
      return "ignored";
  }
}
