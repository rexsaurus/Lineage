import { NextResponse, type NextRequest } from "next/server";
import { isSlug, SRC_COOKIE, SRC_MAX_AGE } from "@/lib/src";

// Attribution (spec §3.1): any page opened with ?src=<slug> stores the slug in a first-party cookie for 30 days.
export function proxy(req: NextRequest) {
  const res = NextResponse.next();
  const src = req.nextUrl.searchParams.get("src")?.toLowerCase();
  if (isSlug(src)) {
    res.cookies.set(SRC_COOKIE, src, { maxAge: SRC_MAX_AGE, sameSite: "lax", path: "/", secure: req.nextUrl.protocol === "https:" });
  }
  return res;
}

export const config = {
  matcher: ["/((?!_next/|api/|favicon|robots.txt).*)"],
};
