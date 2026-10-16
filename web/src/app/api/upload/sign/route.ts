import { NextResponse, type NextRequest } from "next/server";
import { getDb } from "@/db";
import { currentUser } from "@/lib/auth";
import { familyForViewer, newBlobKey } from "@/lib/families";
import { MAX_UPLOAD_BYTES } from "@/lib/files";
import { store } from "@/lib/storage";
import { signPayload } from "@/lib/crypto";
import { sessionSecret } from "@/env";

const EXT: Record<string, string> = { "image/jpeg": "jpg", "image/png": "png", "image/heic": "heic", "image/webp": "webp", "application/pdf": "pdf" };

// POST /api/upload/sign {familyId, type, size} → {url, key}: a 10-minute URL to PUT one large file straight to storage.
// 501 when the storage driver can't (local), and the browser falls back to /api/upload.
export async function POST(req: NextRequest) {
  const b = (await req.json().catch(() => ({}))) as { familyId?: string; type?: string; size?: number };
  const u = await currentUser();
  if (!u) return NextResponse.json({ ok: false, message: "Please sign in again." }, { status: 401 });
  const f = await familyForViewer(await getDb(), String(b.familyId || ""), u);
  if (!f) return NextResponse.json({ ok: false, message: "Family page not found." }, { status: 404 });
  if (!b.size || b.size > MAX_UPLOAD_BYTES) return NextResponse.json({ ok: false, message: "That file is over 25 MB." }, { status: 413 });
  const ext = EXT[String(b.type)];
  if (!ext) return NextResponse.json({ ok: false, message: "Please choose a photo or a PDF." }, { status: 400 });
  const key = newBlobKey(f.id, ext);
  const url = await store().signedPutUrl(key, String(b.type), 600);
  if (!url) return NextResponse.json({ ok: false }, { status: 501 });
  // the key is signed so /complete can only finish uploads this endpoint started, for this user and family
  return NextResponse.json({ ok: true, url, key: signPayload(sessionSecret(), { key, uid: u.id, fid: f.id, exp: Date.now() + 600_000 }) });
}
