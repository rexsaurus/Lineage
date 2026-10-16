import { NextResponse, type NextRequest } from "next/server";
import { getDb } from "@/db";
import { paymentsProvider } from "@/lib/payments";
import { handleEvent } from "@/lib/webhooks";

// POST /api/stripe/webhook (spec §6): verify the signature, then record. Replays are no-ops; a bad signature is 400.
export async function POST(req: NextRequest) {
  const raw = await req.text();
  let event;
  try {
    event = paymentsProvider().parseWebhook(raw, req.headers.get("stripe-signature"));
  } catch {
    return NextResponse.json({ error: "bad signature" }, { status: 400 });
  }
  const result = await handleEvent(await getDb(), event);
  return NextResponse.json({ received: true, result });
}
