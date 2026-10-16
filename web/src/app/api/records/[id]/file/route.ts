import { NextResponse, type NextRequest } from "next/server";
import { getDb } from "@/db";
import { currentUser } from "@/lib/auth";
import { familyForReader, getFamily, getRecord } from "@/lib/families";
import { store } from "@/lib/storage";

// GET /api/records/[id]/file → 302 to a 5-minute signed URL. Members and admins: any record of their family.
// Subscribers: non-private records only. Demo records: anyone (the demo is public, read-only). Everyone else: 404.
export async function GET(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const db = await getDb();
  const r = await getRecord(db, id);
  const nf = () => new NextResponse("Not found", { status: 404, headers: { "Cache-Control": "no-store" } });
  if (!r) return nf();
  const fam = await getFamily(db, r.familyId);
  if (!fam) return nf();
  if (!fam.isDemo) {
    const access = await familyForReader(db, fam.id, await currentUser());
    if (!access) return nf();
    if (access.access === "subscriber" && r.isPrivate) return nf();
  }
  const url = await store().signedGetUrl(r.blobKey, 300);
  const res = NextResponse.redirect(new URL(url, req.nextUrl.origin), 302);
  res.headers.set("Cache-Control", "private, no-store");
  return res;
}
