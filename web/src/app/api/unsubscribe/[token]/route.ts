import { NextResponse, type NextRequest } from "next/server";
import { getDb } from "@/db";
import { readUnsubscribeToken, setDigestFreq } from "@/lib/digest";

// POST /api/unsubscribe/[token] — RFC 8058 one-click unsubscribe (List-Unsubscribe-Post), sent by mail apps.
export async function POST(_req: NextRequest, { params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const id = readUnsubscribeToken(decodeURIComponent(token));
  if (!id) return new NextResponse("Not found", { status: 404 });
  await setDigestFreq(await getDb(), id, "off");
  return new NextResponse("Unsubscribed", { status: 200 });
}
