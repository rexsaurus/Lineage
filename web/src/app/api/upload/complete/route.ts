import { NextResponse, type NextRequest } from "next/server";
import { getDb } from "@/db";
import { currentUser } from "@/lib/auth";
import { verifyPayload } from "@/lib/crypto";
import { sessionSecret } from "@/env";
import { store } from "@/lib/storage";
import { acceptUpload } from "@/lib/upload";

// POST /api/upload/complete {familyId, key, caption}: after a direct PUT, check the stored file like any other upload
// (type, size, metadata stripped and re-stored) and record it.
export async function POST(req: NextRequest) {
  const b = (await req.json().catch(() => ({}))) as { familyId?: string; key?: string; caption?: string; private?: boolean };
  const u = await currentUser();
  const k = verifyPayload<{ key: string; uid: string; fid: string; exp: number }>(sessionSecret(), b.key);
  if (!u || !k || k.uid !== u.id || k.fid !== b.familyId || k.exp < Date.now()) return NextResponse.json({ ok: false, message: "Please try the upload again." }, { status: 400 });
  const bytes = await store().get(k.key);
  if (!bytes) return NextResponse.json({ ok: false, message: "The upload didn't arrive. Please try again." }, { status: 400 });
  const r = await acceptUpload(await getDb(), { viewer: u, familyId: k.fid, bytes, caption: b.caption, blobKey: k.key, isPrivate: b.private === true });
  if (!r.ok) {
    await store().delete(k.key).catch(() => {});
    return NextResponse.json({ ok: false, message: r.message }, { status: r.status });
  }
  return NextResponse.json(r);
}
