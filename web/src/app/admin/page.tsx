import Link from "next/link";
import { cookies } from "next/headers";
import { desc } from "drizzle-orm";
import { getDb } from "@/db";
import { events, families, users } from "@/db/schema";
import { env } from "@/env";
import { requireAdmin } from "@/lib/auth";
import { computeKpis, kpisByEvent } from "@/lib/kpi";
import { getSetting, PAYMENT_LINK_FALLBACK } from "@/lib/settings";
import { adminDeleteFamily, adminSetDemoSrc, adminToggleFallback } from "../actions";

export const metadata = { title: "Admin" };

export default async function Admin({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  await requireAdmin();
  const sp = await searchParams;
  const db = await getDb();
  const [k, byEvent, recent, fams, evs, fallback] = await Promise.all([
    computeKpis(db),
    kpisByEvent(db),
    db.select({ email: users.email, src: users.eventSource, at: users.createdAt, role: users.role }).from(users).orderBy(desc(users.createdAt)).limit(25),
    db.select({ id: families.id, name: families.name, src: families.eventSource, demo: families.isDemo, at: families.createdAt }).from(families).orderBy(desc(families.createdAt)).limit(50),
    db.select().from(events).orderBy(events.slug),
    getSetting(db, PAYMENT_LINK_FALLBACK),
  ]);
  const demoSrc = (await cookies()).get("lineage_demo_src")?.value || "";
  const e = env();
  return (
    <div className="page wide">
      <h1>Admin</h1>
      {sp.deleted ? <p className="okmsg">Deleted.</p> : null}
      {sp.error === "confirm" ? <p className="error">Type DELETE to confirm.</p> : null}
      <p className="small muted">
        Mode: payments <b>{e.PAYMENTS_DRIVER}</b>{e.PRICE_TBD ? ", price not set (reservations only)" : ""} · email <b>{e.MAIL_DRIVER}</b> · storage <b>{e.STORAGE_DRIVER}</b> · database <b>{e.DATABASE_URL ? "Postgres" : "PGlite"}</b>
      </p>

      <h2>Counts</h2>
      <div className="scroll"><table className="data"><tbody>
        <tr><th>Families indexed</th><td>{k.families_indexed}</td></tr>
        <tr><th>Archivists added</th><td>{k.archivists_added}</td></tr>
        <tr><th>Records uploaded</th><td>{k.records_uploaded}</td></tr>
        <tr><th>Invites sent / accepted</th><td>{k.invites_sent} / {k.invites_accepted}</td></tr>
        <tr><th>Paid sign-ups</th><td>{k.paid_signups}</td></tr>
      </tbody></table></div>
      <p className="small">Demo families and admin accounts are not counted. <a href="/api/admin/kpi.csv">kpi.csv</a> · <a href="/api/admin/kpi-by-event.csv">kpi-by-event.csv</a> · <Link href="/admin/qr">QR codes</Link></p>

      <h2>By event</h2>
      <div className="scroll"><table className="data">
        <thead><tr><th>Event</th><th>Families</th><th>Archivists</th><th>Records</th><th>Invites</th><th>Accepted</th><th>Paid</th></tr></thead>
        <tbody>{byEvent.map(r => (
          <tr key={r.event_source}><td>{r.event_source}</td><td>{r.families_indexed}</td><td>{r.archivists_added}</td><td>{r.records_uploaded}</td><td>{r.invites_sent}</td><td>{r.invites_accepted}</td><td>{r.paid_signups}</td></tr>
        ))}</tbody>
      </table></div>

      <h2>Recent sign-ups</h2>
      <div className="scroll"><table className="data">
        <thead><tr><th>Email</th><th>Event</th><th>Role</th><th>When</th></tr></thead>
        <tbody>{recent.map(r => (<tr key={r.email}><td>{r.email}</td><td>{r.src}</td><td>{r.role}</td><td>{r.at.toISOString().slice(0, 16).replace("T", " ")}</td></tr>))}</tbody>
      </table></div>

      <h2>Demo phone</h2>
      <form action={adminSetDemoSrc}>
        <label htmlFor="slug">Event for the demo&apos;s &ldquo;Start your own&rdquo; button (this device)</label>
        <select id="slug" name="slug" defaultValue={demoSrc}>
          <option value="">None</option>
          {evs.map(ev => <option key={ev.slug} value={ev.slug}>{ev.slug}{ev.name ? ` — ${ev.name}` : ""}</option>)}
        </select>
        <button className="btn secondary" style={{ marginTop: 12 }} type="submit">Save</button>
      </form>

      <h2>Payment Link fallback</h2>
      <p className="small">If Checkout is down at an event, send people to the Stripe Payment Link instead. {e.STRIPE_PAYMENT_LINK_URL ? "" : "(STRIPE_PAYMENT_LINK_URL is not set.)"}</p>
      <form action={adminToggleFallback}>
        <label><input type="checkbox" name="on" defaultChecked={fallback === "on"} disabled={!e.STRIPE_PAYMENT_LINK_URL} /> Use the Payment Link</label>
        <button className="btn secondary" type="submit" disabled={!e.STRIPE_PAYMENT_LINK_URL}>Save</button>
      </form>

      <h2>Families</h2>
      <div className="scroll"><table className="data">
        <thead><tr><th>Name</th><th>Event</th><th>Created</th><th>Delete</th></tr></thead>
        <tbody>{fams.map(f => (
          <tr key={f.id}>
            <td><Link href={`/family/${f.id}`}>{f.name}</Link>{f.demo ? " (demo)" : ""}</td><td>{f.src}</td><td>{f.at.toISOString().slice(0, 10)}</td>
            <td>
              <form action={adminDeleteFamily} style={{ display: "flex", gap: 8 }}>
                <input type="hidden" name="familyId" value={f.id} />
                <input name="confirm" placeholder="DELETE" aria-label={`Type DELETE to delete ${f.name}`} style={{ minHeight: 44 }} />
                <button className="btn secondary" style={{ width: "auto", minHeight: 44 }} type="submit">Delete</button>
              </form>
            </td>
          </tr>
        ))}</tbody>
      </table></div>
      <form action="/logout" method="post" style={{ marginTop: 32 }}><button className="btn secondary" type="submit">Sign out</button></form>
    </div>
  );
}

export const dynamic = "force-dynamic";
