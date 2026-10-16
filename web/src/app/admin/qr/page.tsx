import Link from "next/link";
import { getDb } from "@/db";
import { events } from "@/db/schema";
import { requireAdmin } from "@/lib/auth";
import { eventUrl, qrSvg } from "@/lib/qr";
import { adminSaveEvent } from "../../actions";

export const metadata = { title: "QR codes" };
export const dynamic = "force-dynamic";

export default async function QrAdmin({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  await requireAdmin();
  const sp = await searchParams;
  const evs = await (await getDb()).select().from(events).orderBy(events.slug);
  const svgs = await Promise.all(evs.map(e => qrSvg(eventUrl(e.slug))));
  return (
    <div className="page wide">
      <p><Link href="/admin">← Admin</Link></p>
      <h1>QR codes</h1>
      {sp.saved ? <p className="okmsg">Saved {sp.saved}.</p> : null}
      {sp.error ? <p className="error">The slug may use only a–z, 0–9 and dashes (up to 64).</p> : null}
      <form action={adminSaveEvent} className="card">
        <h2 style={{ marginTop: 0 }}>Add or update an event</h2>
        <label htmlFor="slug">Slug</label>
        <input id="slug" name="slug" required pattern="[a-z0-9-]{1,64}" placeholder="scchgs-writing-2026-10-20" />
        <label htmlFor="name">Name</label>
        <input id="name" name="name" maxLength={120} />
        <label htmlFor="venue">Venue</label>
        <input id="venue" name="venue" maxLength={120} />
        <label htmlFor="startsAt">Date</label>
        <input id="startsAt" name="startsAt" type="date" />
        <button className="btn" style={{ marginTop: 16 }} type="submit">Save event</button>
      </form>
      {evs.map((e, i) => (
        <section key={e.slug} className="card">
          <h2 style={{ marginTop: 0 }}>{e.name || e.slug}</h2>
          <p className="small">{e.slug}{e.venue ? ` · ${e.venue}` : ""}{e.startsAt ? ` · ${e.startsAt.toISOString().slice(0, 10)}` : ""}</p>
          <div style={{ width: 180 }} dangerouslySetInnerHTML={{ __html: svgs[i] }} />
          <p className="small">{eventUrl(e.slug)}</p>
          <p>
            <a href={`/api/admin/qr/${e.slug}`} download={`lineage-${e.slug}.png`}>Download PNG (1024px)</a> ·{" "}
            <Link href={`/admin/qr/${e.slug}/cards`}>Printable cards</Link>
          </p>
        </section>
      ))}
    </div>
  );
}
