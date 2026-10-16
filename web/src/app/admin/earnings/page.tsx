import Link from "next/link";
import { desc, eq, sql } from "drizzle-orm";
import { getDb } from "@/db";
import { earnings, payouts, users } from "@/db/schema";
import { minPayoutCents, refundHoldDays, revShareBps } from "@/env";
import { requireAdmin } from "@/lib/auth";
import { referralCounts, subscriptionKpis } from "@/lib/kpi";
import { releaseAvailable } from "@/lib/ledger";
import { money } from "@/lib/money";
import { adminPayoutAction } from "../../sub-actions";

export const metadata = { title: "Subscriptions and referrals" };
export const dynamic = "force-dynamic";

export default async function AdminEarnings({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  await requireAdmin();
  const sp = await searchParams;
  const db = await getDb();
  await releaseAvailable(db);
  const [k, refs, ledger, pays] = await Promise.all([
    subscriptionKpis(db),
    referralCounts(db),
    db.select({ e: earnings, email: users.email }).from(earnings).innerJoin(users, eq(earnings.referrerUserId, users.id)).orderBy(desc(earnings.createdAt)).limit(200),
    db.select({ p: payouts, email: users.email }).from(payouts).innerJoin(users, eq(payouts.userId, users.id)).orderBy(desc(payouts.createdAt)).limit(50),
  ]);
  const due = (await db.execute(sql`
    select e.referrer_user_id as uid, u.email, e.currency, sum(e.amount_cents) as amount, bool_or(u.connect_payouts_enabled) as ready
    from earnings e join users u on u.id = e.referrer_user_id
    where e.status = 'available' and e.payout_id is null group by 1, 2, 3 order by 2`)) as unknown as { rows: { uid: string; email: string; currency: string; amount: string; ready: boolean }[] };
  const bps = revShareBps();
  const hold = refundHoldDays();
  return (
    <div className="page wide">
      <p><Link href="/admin">← Admin</Link></p>
      <h1>Subscriptions and referrals</h1>
      {sp.paid ? <p className="okmsg">Payout sent.</p> : null}
      {sp.error ? <p className="error" role="alert">{sp.error}</p> : null}
      <p className="small muted">
        Revenue share: <b>{bps === null ? "not set (program not open)" : `${bps / 100}%`}</b> · hold: <b>{hold === null ? "not set (earnings stay pending)" : `${hold} days`}</b> · minimum payout: <b>{minPayoutCents() ? `${minPayoutCents()} (smallest unit)` : "none"}</b>
      </p>

      <h2>Counts</h2>
      <div className="scroll"><table className="data"><tbody>
        <tr><th>Paid subscribers</th><td>{k.paid_subscribers}</td></tr>
        <tr><th>Free followers</th><td>{k.followers}</td></tr>
        <tr><th>Monthly recurring revenue</th><td>{k.mrr_cents.length ? k.mrr_cents.map(m => money(m.cents, m.currency)).join(" + ") : "0"}</td></tr>
      </tbody></table></div>
      <p className="small"><a href="/api/admin/earnings.csv">Ledger CSV</a></p>

      <h2>Referrals by archivist</h2>
      <div className="scroll"><table className="data">
        <thead><tr><th>Archivist</th><th>Referred</th><th>Active</th><th>Paying</th></tr></thead>
        <tbody>{refs.map(r => <tr key={r.user_id}><td>{r.email}</td><td>{r.referred}</td><td>{r.active}</td><td>{r.paid_active}</td></tr>)}</tbody>
      </table></div>

      <h2>Ready to pay</h2>
      {due.rows.length ? (
        <div className="scroll"><table className="data">
          <thead><tr><th>Archivist</th><th>Available</th><th>Stripe</th><th></th></tr></thead>
          <tbody>{due.rows.map(d => (
            <tr key={d.uid + d.currency}>
              <td>{d.email}</td><td>{money(Number(d.amount), d.currency)}</td><td>{d.ready ? "set up" : "not set up"}</td>
              <td>
                <form action={adminPayoutAction}>
                  <input type="hidden" name="userId" value={d.uid} />
                  <input type="hidden" name="currency" value={d.currency} />
                  <button className="btn" style={{ minHeight: 48 }} type="submit" disabled={!d.ready || Number(d.amount) <= 0}>Approve payout</button>
                </form>
              </td>
            </tr>
          ))}</tbody>
        </table></div>
      ) : <p>Nothing available.</p>}

      <h2>Ledger</h2>
      <div className="scroll"><table className="data">
        <thead><tr><th>Date</th><th>Archivist</th><th>Kind</th><th>Invoice net</th><th>Share</th><th>Amount</th><th>Status</th><th>Available</th></tr></thead>
        <tbody>{ledger.map(({ e, email }) => (
          <tr key={e.id}>
            <td>{e.createdAt.toISOString().slice(0, 10)}</td><td>{email}</td><td>{e.kind}</td><td>{money(e.invoiceNetCents, e.currency)}</td>
            <td>{e.shareBps === null ? "—" : `${e.shareBps / 100}%`}</td><td>{money(e.amountCents, e.currency)}</td><td>{e.status}</td>
            <td>{e.availableAt ? e.availableAt.toISOString().slice(0, 10) : "—"}</td>
          </tr>
        ))}</tbody>
      </table></div>

      <h2>Payouts</h2>
      <div className="scroll"><table className="data">
        <thead><tr><th>Date</th><th>Archivist</th><th>Amount</th><th>Status</th><th>Approved by</th></tr></thead>
        <tbody>{pays.map(({ p, email }) => (
          <tr key={p.id}><td>{p.createdAt.toISOString().slice(0, 10)}</td><td>{email}</td><td>{money(p.amountCents, p.currency)}</td><td>{p.status}{p.failure ? ` (${p.failure})` : ""}</td><td>{p.approvedBy}</td></tr>
        ))}</tbody>
      </table></div>
    </div>
  );
}
