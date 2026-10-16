import { NextResponse, type NextRequest } from "next/server";
import { getDb } from "@/db";
import { completeWelcome } from "@/lib/start";
import { makeSessionToken, SESSION_COOKIE, sessionCookieOptions } from "@/lib/session";
import { getUser, touchLogin } from "@/lib/users";
import { familiesOf } from "@/lib/families";
import { createMagicLink } from "@/lib/magic";
import { sendMagicLinkEmail } from "@/lib/emails";

// GET /welcome?session_id=… — Stripe's success URL (spec §3.1). A route handler, because it sets the session cookie.
export async function GET(req: NextRequest) {
  const id = req.nextUrl.searchParams.get("session_id") || "";
  const db = await getDb();
  const r = await completeWelcome(db, id);
  const to = (p: string) => NextResponse.redirect(new URL(p, req.nextUrl.origin), 303);
  if (r.status === "unpaid") return to("/welcome/pending");
  if (r.status !== "paid") return to("/login?error=session");
  if (!r.signIn) return to("/login?paid=1"); // the one-time sign-in for this payment was already used
  const user = await getUser(db, r.userId);
  if (!user) return to("/login?error=session");
  await touchLogin(db, user.id);
  await sendMagicLinkEmail(db, user.email, await createMagicLink(db, user.email, "/family/new"));
  const fams = await familiesOf(db, user.id);
  const res = to(fams.length ? `/family/${fams[0].id}` : "/family/new");
  res.cookies.set(SESSION_COOKIE, makeSessionToken(user.id), sessionCookieOptions());
  return res;
}
