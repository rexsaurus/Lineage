import type { NextRequest } from "next/server";
import { env } from "@/env";
import { safeEqual } from "./crypto";

/** Vercel Cron sends "Authorization: Bearer $CRON_SECRET". */
export function isCron(req: NextRequest): boolean {
  const secret = env().CRON_SECRET;
  const auth = req.headers.get("authorization") || "";
  return !!secret && auth.startsWith("Bearer ") && safeEqual(auth.slice(7), secret);
}
