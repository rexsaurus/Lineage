import { NextResponse, type NextRequest } from "next/server";
import type Stripe from "stripe";
import { env } from "@/env";
import { getDb } from "@/db";
import { fakeSessions, handleStripeEvent } from "@/lib/payments";

// POST /dev/fake-checkout/pay — development and tests only (PAYMENTS_DRIVER=fake). Marks the fake session paid, runs
// the same handler the real webhook runs, and returns to the success URL with a full-page redirect, as Stripe does.
export async function POST(req: NextRequest) {
  if (env().PAYMENTS_DRIVER !== "fake") return new NextResponse("Not found", { status: 404 });
  const form = await req.formData();
  const s = fakeSessions.get(String(form.get("session") || ""));
  if (!s) return new NextResponse("Not found", { status: 404 });
  s.paid = true;
  const event = {
    type: "checkout.session.completed",
    data: { object: { id: s.id, url: null, payment_status: "paid", client_reference_id: s.clientReferenceId, metadata: { user_id: s.userId, src: s.src },
      amount_total: null, currency: null, customer: null, payment_intent: s.paymentIntentId, livemode: false } },
  } as unknown as Stripe.Event;
  await handleStripeEvent(await getDb(), event);
  const success = new URL(String(form.get("success") || "/").replace("{CHECKOUT_SESSION_ID}", s.id));
  return NextResponse.redirect(new URL(success.pathname + success.search, req.nextUrl.origin), 303);
}
