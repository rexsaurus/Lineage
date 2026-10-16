import { sql } from "drizzle-orm";
import type { Db } from "@/db";
import { adminEmails } from "@/env";

// KPIs (spec §8). Every number is counted from the database. Demo families and admin users are excluded everywhere.
//   families_indexed = non-demo families with ≥1 archivist member and ≥1 record
//   archivists_added = distinct non-admin users who are an archivist of a non-demo family

export type Kpis = {
  families_indexed: number;
  archivists_added: number;
  records_uploaded: number;
  invites_sent: number;
  invites_accepted: number;
  paid_signups: number;
};
export type EventRow = Kpis & { event_source: string };

function adminList() {
  const a = adminEmails();
  // a value that can never be an email keeps the IN () list valid when there are no admins
  return sql.join((a.length ? a : ["\u0000none"]).map(e => sql`${e}`), sql`, `);
}

const n = (v: unknown) => Number(v ?? 0);

async function rows<T>(db: Db, q: ReturnType<typeof sql>): Promise<T[]> {
  const r = (await db.execute(q)) as unknown as { rows: T[] };
  return r.rows;
}

export async function computeKpis(db: Db): Promise<Kpis> {
  const all = await kpisByEvent(db);
  const sum = (k: keyof Kpis) => all.reduce((s, r) => s + r[k], 0);
  // archivists can span events, so count them distinctly rather than summing per event
  const [a] = await rows<{ c: number }>(
    db,
    sql`select count(distinct u.id) as c from users u
        join family_members m on m.user_id = u.id and m.role = 'archivist'
        join families f on f.id = m.family_id and f.is_demo = false
        where u.email not in (${adminList()})`,
  );
  return {
    families_indexed: sum("families_indexed"),
    archivists_added: n(a?.c),
    records_uploaded: sum("records_uploaded"),
    invites_sent: sum("invites_sent"),
    invites_accepted: sum("invites_accepted"),
    paid_signups: sum("paid_signups"),
  };
}

export async function kpisByEvent(db: Db): Promise<EventRow[]> {
  const admins = adminList();
  const fam = await rows<{ src: string; families: number; records: number }>(
    db,
    sql`select src, count(*) filter (where has_archivist and nrec > 0) as families, coalesce(sum(nrec), 0) as records
        from (
          select coalesce(f.event_source, 'direct') as src,
            exists (select 1 from family_members m join users u on u.id = m.user_id
                    where m.family_id = f.id and m.role = 'archivist' and u.email not in (${admins})) as has_archivist,
            (select count(*) from records r where r.family_id = f.id) as nrec
          from families f
          left join users cu on cu.id = f.created_by
          where f.is_demo = false and (cu.email is null or cu.email not in (${admins}))
        ) t
        group by src`,
  );
  const arch = await rows<{ src: string; c: number }>(
    db,
    sql`select coalesce(f.event_source, 'direct') as src, count(distinct u.id) as c from users u
        join family_members m on m.user_id = u.id and m.role = 'archivist'
        join families f on f.id = m.family_id and f.is_demo = false
        where u.email not in (${admins}) group by 1`,
  );
  const inv = await rows<{ src: string; sent: number; accepted: number }>(
    db,
    sql`select coalesce(i.event_source, 'direct') as src, count(*) as sent, count(*) filter (where i.status = 'accepted') as accepted
        from invites i join families f on f.id = i.family_id and f.is_demo = false
        left join users iu on iu.id = i.invited_by
        where iu.email is null or iu.email not in (${admins}) group by 1`,
  );
  const paid = await rows<{ src: string; c: number }>(
    db,
    sql`select coalesce(p.event_source, 'direct') as src, count(distinct p.user_id) as c from payments p
        left join users u on u.id = p.user_id
        where p.status = 'paid' and (u.email is null or u.email not in (${admins})) group by 1`,
  );
  const out = new Map<string, EventRow>();
  const row = (src: string) => {
    let r = out.get(src);
    if (!r) out.set(src, (r = { event_source: src, families_indexed: 0, archivists_added: 0, records_uploaded: 0, invites_sent: 0, invites_accepted: 0, paid_signups: 0 }));
    return r;
  };
  for (const f of fam) Object.assign(row(f.src), { families_indexed: n(f.families), records_uploaded: n(f.records) });
  for (const a of arch) row(a.src).archivists_added = n(a.c);
  for (const i of inv) Object.assign(row(i.src), { invites_sent: n(i.sent), invites_accepted: n(i.accepted) });
  for (const p of paid) row(p.src).paid_signups = n(p.c);
  return [...out.values()].sort((a, b) => a.event_source.localeCompare(b.event_source));
}

export const today = (d = new Date()) => d.toISOString().slice(0, 10);

/** The exact format of second-brain-fundraising/kpi-log.csv */
export function kpiCsv(k: Kpis, date = today()) {
  return `date,families,archivists\n${date},${k.families_indexed},${k.archivists_added}\n`;
}

export function kpiByEventCsv(rowsIn: EventRow[], date = today()) {
  const lines = rowsIn.map(r => [date, r.event_source, r.families_indexed, r.archivists_added, r.records_uploaded, r.paid_signups].join(","));
  return ["date,event_source,families,archivists,records,paid", ...lines].join("\n") + "\n";
}
