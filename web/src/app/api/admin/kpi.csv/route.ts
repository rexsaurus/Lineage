import { NextResponse, type NextRequest } from "next/server";
import { getDb } from "@/db";
import { isAdminRequest } from "@/lib/admin-auth";
import { computeKpis, kpiCsv } from "@/lib/kpi";

// GET /api/admin/kpi.csv — "date,families,archivists" plus today's row, counted from the database (spec §8).
export async function GET(req: NextRequest) {
  if (!(await isAdminRequest(req, true))) return new NextResponse("Not found", { status: 404 });
  return new NextResponse(kpiCsv(await computeKpis(await getDb())), {
    headers: { "Content-Type": "text/csv; charset=utf-8", "Cache-Control": "no-store" },
  });
}
