import { NextResponse, type NextRequest } from "next/server";
import type Stripe from "stripe";
import { env } from "@/env";
import { getDb } from "@/db";
import { fakeSessions } from "@/lib/payments";
import { fakeSubscriptionEvents, handleEvent } from "@/lib/webhooks";

// POST /dev/fake-checkout/pay — development and tests only (PAYMENTS_DRIVER=fake). Marks the fake session paid, runs
// the same events through the same handler the real webhook uses, and returns to the success URL with a full-page
// redirect, as Stripe does.
export async function POST(req: NextRequest) {
  if (env().PAYMENTS_DRIVER !== "fake") return new NextResponse("Not found", { status: 404 });
  const form = await req.formData();
  const s = fakeSessions.get(String(form.get("session") || ""));
  if (!s) return new NextResponse("Not found", { status: 404 });
  s.paid = true;
  const db = await getDb();
  if (s.mode === "subscription") {
    for (const ev of fakeSubscriptionEvents(s)) await handleEvent(db, ev);
  } else {
    const event = {
      type: "checkout.session.completed",
      data: { object: { id: s.id, mode: "payment", url: null, payment_status: "paid", client_reference_id: s.clientReferenceId, metadata: { user_id: s.userId, src: s.src },
        amount_total: null, currency: null, customer: null, payment_intent: s.paymentIntentId, livemode: false } },
    } as unknown as Stripe.Event;
    await handleEvent(db, event);
  }
  const success = new URL(String(form.get("success") || "/").replace("{CHECKOUT_SESSION_ID}", s.id), req.nextUrl.origin);
  return NextResponse.redirect(new URL(success.pathname + success.search, req.nextUrl.origin), 303);
}
