import { NextResponse, type NextRequest } from "next/server";
import type Stripe from "stripe";
import { env } from "@/env";
import { getDb } from "@/db";
import { fakeConnect } from "@/lib/connect";
import { handleEvent } from "@/lib/webhooks";

// POST /dev/fake-connect/done — development and tests only: marks the fake account able to receive payouts, sends the
// same account.updated event Stripe would, and returns like Stripe's onboarding does.
export async function POST(req: NextRequest) {
  if (env().CONNECT_DRIVER !== "fake") return new NextResponse("Not found", { status: 404 });
  const form = await req.formData();
  const id = String(form.get("account") || "");
  const acct = fakeConnect.accounts.get(id);
  if (!acct) return new NextResponse("Not found", { status: 404 });
  acct.payoutsEnabled = true;
  acct.detailsSubmitted = true;
  await handleEvent(await getDb(), { type: "account.updated", data: { object: { id, payouts_enabled: true } } } as unknown as Stripe.Event);
  const ret = new URL(String(form.get("return") || "/earnings"), req.nextUrl.origin);
  return NextResponse.redirect(new URL(ret.pathname + ret.search, req.nextUrl.origin), 303);
}
