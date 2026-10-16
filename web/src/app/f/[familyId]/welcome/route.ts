import { NextResponse, type NextRequest } from "next/server";
import { getDb } from "@/db";
import { completeSubscriptionCheckout } from "@/lib/subscriptions";
import { makeSessionToken, SESSION_COOKIE, sessionCookieOptions } from "@/lib/session";
import { getUser, touchLogin } from "@/lib/users";
import { createMagicLink } from "@/lib/magic";
import { sendMagicLinkEmail } from "@/lib/emails";

// GET /f/[familyId]/welcome?session_id=… — Stripe's success URL for a family subscription.
export async function GET(req: NextRequest, { params }: { params: Promise<{ familyId: string }> }) {
  const { familyId } = await params;
  const db = await getDb();
  const r = await completeSubscriptionCheckout(db, req.nextUrl.searchParams.get("session_id") || "");
  const to = (p: string) => NextResponse.redirect(new URL(p, req.nextUrl.origin), 303);
  if (!r.ok || r.familyId !== familyId) return to(`/f/${familyId}`);
  const user = await getUser(db, r.userId);
  if (!user) return to(`/f/${familyId}`);
  const dest = `/family/${familyId}?subscribed=1`;
  await sendMagicLinkEmail(db, user.email, await createMagicLink(db, user.email, dest));
  if (!r.signIn) return to("/login?paid=1");
  await touchLogin(db, user.id);
  const res = to(dest);
  res.cookies.set(SESSION_COOKIE, makeSessionToken(user.id), sessionCookieOptions());
  return res;
}
