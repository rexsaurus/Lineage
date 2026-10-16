import type { NextRequest } from "next/server";
import { getDb } from "@/db";
import { env } from "@/env";
import { safeEqual } from "./crypto";
import { readSessionToken, SESSION_COOKIE } from "./session";
import { getUser, isAdmin } from "./users";

/** Admin API access: an admin's session cookie, or (for scripts) Authorization: Bearer KPI_EXPORT_TOKEN. */
export async function isAdminRequest(req: NextRequest, allowToken = false): Promise<boolean> {
  const token = env().KPI_EXPORT_TOKEN;
  const auth = req.headers.get("authorization") || "";
  if (allowToken && token && auth.startsWith("Bearer ") && safeEqual(auth.slice(7), token)) return true;
  const uid = readSessionToken(req.cookies.get(SESSION_COOKIE)?.value);
  return isAdmin(await getUser(await getDb(), uid));
}
