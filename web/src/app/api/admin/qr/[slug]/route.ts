import { NextResponse, type NextRequest } from "next/server";
import { isAdminRequest } from "@/lib/admin-auth";
import { isSlug } from "@/lib/src";
import { eventUrl, qrPng } from "@/lib/qr";

// GET /api/admin/qr/[slug] → a 1024px PNG for the phone lock screen or printing.
export async function GET(req: NextRequest, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  if (!(await isAdminRequest(req)) || !isSlug(slug)) return new NextResponse("Not found", { status: 404 });
  const png = await qrPng(eventUrl(slug));
  return new NextResponse(new Uint8Array(png), {
    headers: { "Content-Type": "image/png", "Content-Disposition": `inline; filename="lineage-${slug}.png"`, "Cache-Control": "private, no-store" },
  });
}
