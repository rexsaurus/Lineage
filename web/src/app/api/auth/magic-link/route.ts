import { NextResponse, type NextRequest } from "next/server";
import { getDb } from "@/db";
import { normalizeEmail } from "@/lib/crypto";
import { createMagicLink, safeRedirect } from "@/lib/magic";
import { sendMagicLinkEmail } from "@/lib/emails";
import { upsertUser } from "@/lib/users";
import { normalizeSrc, SRC_COOKIE } from "@/lib/src";

// POST /api/auth/magic-link {email, next?} — the JSON twin of the /login form. Always answers the same way, so it
// can't be used to find out who has an account.
const hits = new Map<string, number[]>();

export async function POST(req: NextRequest) {
  const ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim() || "local";
  const now = Date.now();
  const recent = (hits.get(ip) || []).filter(t => now - t < 15 * 60_000);
  if (recent.length >= 10) return NextResponse.json({ ok: false, message: "Please wait a few minutes and try again." }, { status: 429 });
  hits.set(ip, [...recent, now]);
  const b = (await req.json().catch(() => ({}))) as { email?: string; next?: string };
  const email = normalizeEmail(b.email);
  if (!email) return NextResponse.json({ ok: false, message: "Please check your email address." }, { status: 400 });
  const db = await getDb();
  await upsertUser(db, { email, src: normalizeSrc(req.cookies.get(SRC_COOKIE)?.value) });
  await sendMagicLinkEmail(db, email, await createMagicLink(db, email, safeRedirect(b.next)));
  return NextResponse.json({ ok: true, message: "Check your email for a sign-in link." });
}
