import { NextResponse, type NextRequest } from "next/server";
import { eq } from "drizzle-orm";
import { getDb } from "@/db";
import { users } from "@/db/schema";
import { getUser } from "@/lib/users";
import { readSessionToken, SESSION_COOKIE } from "@/lib/session";
import { connectProvider } from "@/lib/connect";

// GET /earnings/connected — the return URL from Stripe's onboarding. Re-reads the account (the account.updated webhook
// does the same) and goes back to the dashboard.
export async function GET(req: NextRequest) {
  const db = await getDb();
  const u = await getUser(db, readSessionToken(req.cookies.get(SESSION_COOKIE)?.value));
  if (u?.stripeConnectAccountId) {
    const a = await connectProvider().getAccount(u.stripeConnectAccountId);
    if (a) await db.update(users).set({ connectPayoutsEnabled: a.payoutsEnabled }).where(eq(users.id, u.id));
  }
  return NextResponse.redirect(new URL("/earnings?connected=1", req.nextUrl.origin), 303);
}
