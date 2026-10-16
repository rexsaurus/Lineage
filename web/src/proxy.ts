import { NextResponse, type NextRequest } from "next/server";
import { isSlug, SRC_COOKIE, SRC_MAX_AGE } from "@/lib/src";
import { isRefCode, REF_COOKIE, REF_MAX_AGE } from "@/lib/refs";

// Attribution, set before any page renders:
//  - ?src=<event slug> from a QR code at a meeting → lineage_src, 30 days (the latest event wins)
//  - ?ref=<archivist code> from a referral link → lineage_ref, 60 days, FIRST touch wins (never overwritten)
export function proxy(req: NextRequest) {
  const res = NextResponse.next();
  const secure = req.nextUrl.protocol === "https:";
  const src = req.nextUrl.searchParams.get("src")?.toLowerCase();
  if (isSlug(src)) res.cookies.set(SRC_COOKIE, src, { maxAge: SRC_MAX_AGE, sameSite: "lax", path: "/", secure });
  const ref = req.nextUrl.searchParams.get("ref")?.toLowerCase();
  if (isRefCode(ref) && !isRefCode(req.cookies.get(REF_COOKIE)?.value)) {
    res.cookies.set(REF_COOKIE, ref, { maxAge: REF_MAX_AGE, sameSite: "lax", path: "/", secure, httpOnly: true });
  }
  return res;
}

export const config = {
  matcher: ["/((?!_next/|api/|favicon|robots.txt).*)"],
};
