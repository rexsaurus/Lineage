import { NextResponse, type NextRequest } from "next/server";
import { getDb } from "@/db";
import { env } from "@/env";
import { safeEqual } from "@/lib/crypto";
import { runNudges } from "@/lib/followup";

// Vercel Cron (web/vercel.json) calls this with "Authorization: Bearer $CRON_SECRET".
export async function GET(req: NextRequest) {
  const secret = env().CRON_SECRET;
  const auth = req.headers.get("authorization") || "";
  if (!secret || !auth.startsWith("Bearer ") || !safeEqual(auth.slice(7), secret)) return new NextResponse("Not found", { status: 404 });
  const sent = await runNudges(await getDb());
  return NextResponse.json({ sent });
}
