import type Stripe from "stripe";
import type { Db } from "@/db";
import { env } from "@/env";
import { handleStripeEvent, type CheckoutSession } from "./payments";
import { applyStripeSubscription, linkCheckoutSubscription, onAccountUpdated, onChargeRefunded, onDispute, onInvoiceFailed, onInvoicePaid, type AnyInvoice } from "./subscriptions";

// Every Stripe event, in one place. Each handler is idempotent: replaying an event changes nothing.
export async function handleEvent(db: Db, event: Stripe.Event): Promise<string> {
  const o = event.data.object as unknown;
  switch (event.type) {
    case "checkout.session.completed": {
      const s = o as Stripe.Checkout.Session;
      if (s.mode === "subscription") return linkCheckoutSubscription(db, s);
      return handleStripeEvent(db, event);
    }
    case "customer.subscription.created":
    case "customer.subscription.updated":
      return applyStripeSubscription(db, o as Stripe.Subscription);
    case "customer.subscription.deleted":
      return applyStripeSubscription(db, o as Stripe.Subscription, true);
    case "invoice.paid":
      return onInvoicePaid(db, o as AnyInvoice);
    case "invoice.payment_failed":
      return onInvoiceFailed(db, o as AnyInvoice);
    case "charge.refunded": {
      const a = await handleStripeEvent(db, event); // a one-time Founding Archivist payment, if it was one
      const b = await onChargeRefunded(db, o as Stripe.Charge); // a subscription invoice's referral earning, if any
      return `${a}; ledger rows: ${b ?? 0}`;
    }
    case "charge.dispute.created":
      return `ledger rows: ${(await onDispute(db, o as Stripe.Dispute)) ?? 0}`;
    case "account.updated":
      return onAccountUpdated(db, o as Stripe.Account);
    default:
      return handleStripeEvent(db, event);
  }
}

/** The fake driver's stand-in for Stripe sending the events of a completed subscription checkout. */
export function fakeSubscriptionEvents(s: CheckoutSession): Stripe.Event[] {
  const e = env();
  const subId = `sub_fake_${s.id.slice(-10)}`;
  const amount = parseInt(e.FAKE_SUB_AMOUNT_CENTS || "0", 10);
  const now = Math.floor(Date.now() / 1000);
  const ev = (type: string, object: object) => ({ id: `evt_fake_${type}_${s.id.slice(-10)}`, type, data: { object } }) as unknown as Stripe.Event;
  return [
    ev("checkout.session.completed", { id: s.id, mode: "subscription", subscription: subId, metadata: s.metadata, client_reference_id: s.userId }),
    ev("customer.subscription.created", {
      id: subId, status: "active", customer: s.customerId, metadata: s.metadata,
      items: { data: [{ current_period_end: now + 30 * 86400, price: { unit_amount: amount, currency: e.FAKE_SUB_CURRENCY, recurring: { interval: "month" } } }] },
    }),
    ev("invoice.paid", {
      id: `in_fake_${s.id.slice(-10)}`, subscription: subId, amount_paid: amount, tax: 0, currency: e.FAKE_SUB_CURRENCY,
      charge: `ch_fake_${s.id.slice(-10)}`, payment_intent: `pi_fake_${s.id.slice(-10)}`, created: now, status_transitions: { paid_at: now },
    }),
  ];
}
