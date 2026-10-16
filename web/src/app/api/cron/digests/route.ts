import { NextResponse, type NextRequest } from "next/server";
import { getDb } from "@/db";
import { isCron } from "@/lib/cron-auth";
import { runDigests } from "@/lib/digest";
import { releaseAvailable } from "@/lib/ledger";

// Daily (web/vercel.json): send due digests (each at most once per subscriber per week or month) and move referral
// earnings past their hold period to "available".
export async function GET(req: NextRequest) {
  if (!isCron(req)) return new NextResponse("Not found", { status: 404 });
  const db = await getDb();
  const released = await releaseAvailable(db);
  const sent = await runDigests(db);
  return NextResponse.json({ sent, released });
}
