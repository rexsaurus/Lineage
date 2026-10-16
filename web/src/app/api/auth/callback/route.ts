import { NextResponse, type NextRequest } from "next/server";
import { getDb } from "@/db";
import { consumeMagicLink } from "@/lib/magic";
import { getUserByEmail, touchLogin, upsertUser } from "@/lib/users";
import { familiesOf } from "@/lib/families";
import { makeSessionToken, SESSION_COOKIE, sessionCookieOptions } from "@/lib/session";

// GET /api/auth/callback?token=… — the link in the sign-in email (spec §3.2).
export async function GET(req: NextRequest) {
  const db = await getDb();
  const link = await consumeMagicLink(db, req.nextUrl.searchParams.get("token") || "");
  const to = (p: string) => NextResponse.redirect(new URL(p, req.nextUrl.origin), 303);
  if (!link) return to("/login?error=link");
  const user = (await getUserByEmail(db, link.email)) || (await upsertUser(db, { email: link.email, src: "direct" }));
  await touchLogin(db, user.id);
  let dest = link.redirectTo;
  if (!dest || dest === "/family/new") {
    const fams = await familiesOf(db, user.id);
    dest = fams.length ? `/family/${fams[0].id}` : "/family/new";
  }
  const res = to(dest);
  res.cookies.set(SESSION_COOKIE, makeSessionToken(user.id), sessionCookieOptions());
  return res;
}
