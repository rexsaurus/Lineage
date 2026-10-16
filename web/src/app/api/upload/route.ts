import { NextResponse, type NextRequest } from "next/server";
import { getDb } from "@/db";
import { currentUser } from "@/lib/auth";
import { MAX_UPLOAD_BYTES } from "@/lib/files";
import { acceptUpload } from "@/lib/upload";

// POST /api/upload (multipart: familyId, caption, file). Files up to ~4 MB on Vercel (its request limit); larger files
// use /api/upload/sign + /api/upload/complete when storage is R2.
export async function POST(req: NextRequest) {
  const len = Number(req.headers.get("content-length") || 0);
  if (len > MAX_UPLOAD_BYTES + 64 * 1024) return NextResponse.json({ ok: false, message: "That file is over 25 MB. Please choose a smaller photo or document." }, { status: 413 });
  let form: FormData;
  try {
    form = await req.formData();
  } catch {
    return NextResponse.json({ ok: false, message: "The upload didn't arrive. Please try again." }, { status: 400 });
  }
  const file = form.get("file");
  if (!(file instanceof Blob)) return NextResponse.json({ ok: false, message: "Please choose a file." }, { status: 400 });
  if (file.size > MAX_UPLOAD_BYTES) return NextResponse.json({ ok: false, message: "That file is over 25 MB. Please choose a smaller photo or document." }, { status: 413 });
  const r = await acceptUpload(await getDb(), {
    viewer: await currentUser(),
    familyId: String(form.get("familyId") || ""),
    bytes: Buffer.from(await file.arrayBuffer()),
    caption: form.get("caption"),
    isPrivate: form.get("private") === "1",
  });
  return r.ok ? NextResponse.json(r) : NextResponse.json({ ok: false, message: r.message }, { status: r.status });
}
