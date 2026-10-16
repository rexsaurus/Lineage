import Link from "next/link";
import { and, desc, eq, sql } from "drizzle-orm";
import { getDb } from "@/db";
import { families, familyMembers, payouts, subscriptions } from "@/db/schema";
import { refundHoldDays, revShareBps } from "@/env";
import { requireUser } from "@/lib/auth";
import { ensureRefCode, referralUrl } from "@/lib/refs";
import { balances, releaseAvailable } from "@/lib/ledger";
import { qrSvg } from "@/lib/qr";
import { money } from "@/lib/money";
import { connectOnboardAction } from "../sub-actions";
import { SubmitButton } from "@/components/SubmitButton";

export const metadata = { title: "Your link and earnings" };
export const dynamic = "force-dynamic";

// The archivist's dashboard: their referral link and QR for each family they keep, who followed or subscribed through
// it, and their earnings (pending / available / paid) and payouts. Numbers come only from the ledger.
export default async function Earnings({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const u = await requireUser("/earnings");
  const sp = await searchParams;
  const db = await getDb();
  await releaseAvailable(db);
  const code = await ensureRefCode(db, u.id);
  const fams = await db
    .select({ id: families.id, name: families.name })
    .from(familyMembers)
    .innerJoin(families, eq(familyMembers.familyId, families.id))
    .where(and(eq(familyMembers.userId, u.id), eq(familyMembers.role, "archivist"), eq(families.isDemo, false)));
  const links = await Promise.all(fams.map(async f => ({ ...f, url: referralUrl(f.id, code), svg: await qrSvg(referralUrl(f.id, code)) })));
  const [counts] = await db
    .select({
      referred: sql<number>`count(*)`,
      active: sql<number>`count(*) filter (where ${subscriptions.status} in ('active','past_due'))`,
      paid: sql<number>`count(*) filter (where ${subscriptions.status} in ('active','past_due') and ${subscriptions.kind} = 'paid')`,
    })
    .from(subscriptions)
    .where(eq(subscriptions.referrerUserId, u.id));
  const bal = await balances(db, u.id);
  const history = await db.select().from(payouts).where(eq(payouts.userId, u.id)).orderBy(desc(payouts.createdAt)).limit(24);
  const open = revShareBps() !== null;
  const hold = refundHoldDays();

  return (
    <div className="page">
      <h1>Your link and earnings</h1>
      {!open ? (
        <p className="card"><strong>The earnings program is not yet open.</strong> Your link already works: relatives who follow through it are counted, and you&apos;ll see earnings here once the program opens. <Link href="/terms/referrals">How it will work</Link></p>
      ) : (
        <p>When a relative subscribes through your link, you earn a share of what they pay. <Link href="/terms/referrals">Referral terms</Link></p>
      )}

      {links.length ? links.map(l => (
        <section key={l.id} className="card">
          <h2 style={{ marginTop: 0 }}>{l.name}</h2>
          <label htmlFor={`link-${l.id}`}>Your link for this family</label>
          <input id={`link-${l.id}`} readOnly value={l.url} />
          <div style={{ width: 180, marginTop: 12 }} role="img" aria-label={`QR code for your ${l.name} link`} dangerouslySetInnerHTML={{ __html: l.svg }} />
        </section>
      )) : <p>Start a family page first, then share its link with relatives.</p>}

      <h2>Relatives you brought in</h2>
      <div className="scroll"><table className="data"><tbody>
        <tr><th>Followed or subscribed</th><td>{Number(counts?.referred || 0)}</td></tr>
        <tr><th>Still active</th><td>{Number(counts?.active || 0)}</td></tr>
        <tr><th>Paying subscribers</th><td>{Number(counts?.paid || 0)}</td></tr>
      </tbody></table></div>

      <h2>Earnings</h2>
      {bal.length ? (
        <div className="scroll"><table className="data">
          <thead><tr><th>Currency</th><th>Pending</th><th>Available</th><th>Paid</th></tr></thead>
          <tbody>{bal.map(b => (
            <tr key={b.currency}><td>{b.currency.toUpperCase()}</td><td>{money(b.pending, b.currency)}</td><td>{money(b.available, b.currency)}</td><td>{money(b.paid, b.currency)}</td></tr>
          ))}</tbody>
        </table></div>
      ) : <p>No earnings yet.</p>}
      <p className="small muted">
        {hold === null ? "Earnings stay pending until the refund hold period is set." : `Earnings become available ${hold} day${hold === 1 ? "" : "s"} after each payment, in case of refunds.`} Payouts are approved by Rex and sent through Stripe.
      </p>

      <h2>Getting paid</h2>
      {sp.connected ? <p className="okmsg" role="status">Thanks — your payout details are saved with Stripe.</p> : null}
      {u.connectPayoutsEnabled ? (
        <p className="okmsg">Payouts are set up with Stripe.</p>
      ) : (
        <form action={connectOnboardAction}>
          <p>Stripe pays you. It will ask for your bank details, and may ask for identity and tax information.</p>
          <SubmitButton>{u.stripeConnectAccountId ? "Finish setting up payouts" : "Get paid"}</SubmitButton>
        </form>
      )}

      <h2>Payouts</h2>
      {history.length ? (
        <div className="scroll"><table className="data">
          <thead><tr><th>Date</th><th>Amount</th><th>Status</th></tr></thead>
          <tbody>{history.map(p => (
            <tr key={p.id}><td>{(p.paidAt || p.createdAt).toISOString().slice(0, 10)}</td><td>{money(p.amountCents, p.currency)}</td><td>{p.status}</td></tr>
          ))}</tbody>
        </table></div>
      ) : <p>No payouts yet.</p>}
    </div>
  );
}
