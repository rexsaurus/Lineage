import { NextResponse, type NextRequest } from "next/server";
import { getDb } from "@/db";
import { isAdminRequest } from "@/lib/admin-auth";
import { kpiByEventCsv, kpisByEvent } from "@/lib/kpi";

// GET /api/admin/kpi-by-event.csv — date,event_source,families,archivists,records,paid
export async function GET(req: NextRequest) {
  if (!(await isAdminRequest(req, true))) return new NextResponse("Not found", { status: 404 });
  return new NextResponse(kpiByEventCsv(await kpisByEvent(await getDb())), {
    headers: { "Content-Type": "text/csv; charset=utf-8", "Cache-Control": "no-store" },
  });
}
