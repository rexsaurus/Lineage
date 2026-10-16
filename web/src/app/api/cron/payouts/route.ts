import { NextResponse, type NextRequest } from "next/server";
import { getDb } from "@/db";
import { env } from "@/env";
import { isCron } from "@/lib/cron-auth";
import { payOutEveryone } from "@/lib/ledger";

// Monthly (web/vercel.json), and only when PAYOUT_CRON_ENABLED=true; otherwise payouts are approved one by one in
// /admin/earnings.
export async function GET(req: NextRequest) {
  if (!isCron(req)) return new NextResponse("Not found", { status: 404 });
  if (!env().PAYOUT_CRON_ENABLED) return NextResponse.json({ skipped: "PAYOUT_CRON_ENABLED is not true" });
  return NextResponse.json({ paid: await payOutEveryone(await getDb()) });
}
