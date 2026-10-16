import { NextResponse, type NextRequest } from "next/server";
import { asc, eq } from "drizzle-orm";
import { getDb } from "@/db";
import { earnings, users } from "@/db/schema";
import { isAdminRequest } from "@/lib/admin-auth";

// GET /api/admin/earnings.csv — the whole referral ledger.
export async function GET(req: NextRequest) {
  if (!(await isAdminRequest(req, true))) return new NextResponse("Not found", { status: 404 });
  const rows = await (await getDb())
    .select({ e: earnings, email: users.email })
    .from(earnings)
    .innerJoin(users, eq(earnings.referrerUserId, users.id))
    .orderBy(asc(earnings.createdAt));
  const cols = ["created_at", "referrer_email", "kind", "stripe_invoice_id", "invoice_net_cents", "share_bps", "amount_cents", "currency", "status", "available_at", "payout_id", "note"];
  const cell = (v: unknown) => {
    const s = v === null || v === undefined ? "" : v instanceof Date ? v.toISOString() : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = rows.map(({ e, email }) =>
    [e.createdAt, email, e.kind, e.stripeInvoiceId, e.invoiceNetCents, e.shareBps, e.amountCents, e.currency, e.status, e.availableAt, e.payoutId, e.note].map(cell).join(","),
  );
  return new NextResponse([cols.join(","), ...lines].join("\n") + "\n", {
    headers: { "Content-Type": "text/csv; charset=utf-8", "Cache-Control": "no-store", "Content-Disposition": 'attachment; filename="lineage-ledger.csv"' },
  });
}
