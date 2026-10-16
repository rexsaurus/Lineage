import { NextResponse, type NextRequest } from "next/server";
import { LocalStore, verifyLocalSig } from "@/lib/storage";
import { sniff } from "@/lib/files";
import { env } from "@/env";

// GET /api/files?k=&e=&s= — serves a file from the LOCAL store when the signature from signedGetUrl is valid and not
// expired. (With R2, signed URLs point at R2 directly and this route is unused.)
export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams;
  const key = q.get("k") || "";
  const exp = Number(q.get("e") || 0);
  const sig = q.get("s") || "";
  if (env().STORAGE_DRIVER !== "local" || !verifyLocalSig(key, exp, sig)) return new NextResponse("Not found", { status: 404 });
  let body: Buffer | null = null;
  try {
    body = await new LocalStore(env().LOCAL_BLOB_DIR).get(key);
  } catch {
    body = null;
  }
  if (!body) return new NextResponse("Not found", { status: 404 });
  return new NextResponse(new Uint8Array(body), {
    headers: { "Content-Type": sniff(body)?.mime || "application/octet-stream", "Cache-Control": "private, max-age=300", "Content-Disposition": "inline" },
  });
}
