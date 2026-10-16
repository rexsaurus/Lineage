import Link from "next/link";
import { cookies } from "next/headers";
import { asc, eq } from "drizzle-orm";
import { getDb } from "@/db";
import { families } from "@/db/schema";
import { listRecords } from "@/lib/families";
import { RecordGrid } from "@/components/RecordGrid";
import { isSlug } from "@/lib/src";

export const metadata = { title: "Demo family" };

// Spec §10: a read-only family page for Rex's phone. It shows the seeded demo family (npm run seed:demo) or, until Rex
// supplies material, clearly labelled placeholders. "Start your own" carries the event Rex picked in /admin.
export default async function Demo() {
  const db = await getDb();
  const [demo] = await db.select().from(families).where(eq(families.isDemo, true)).orderBy(asc(families.createdAt)).limit(1);
  const recs = demo ? await listRecords(db, demo.id) : [];
  const src = (await cookies()).get("lineage_demo_src")?.value;
  const start = isSlug(src) ? `/?src=${src}` : "/";
  return (
    <div className="page">
      <p className="badge">Demo content</p>
      <h1>{demo?.name || "A family page"}</h1>
      {recs.length ? (
        <RecordGrid records={recs} demo />
      ) : (
        <div className="records">
          {["The printed book", "A chapter page", "A relative's article", "Photographs"].map(t => (
            <figure key={t} className="record" style={{ margin: 0 }}>
              <div className="doc" style={{ fontSize: 18, padding: 12, textAlign: "center" }}>Demo content — Rex to add</div>
              <p>{t}</p>
            </figure>
          ))}
        </div>
      )}
      <Link className="btn" href={start}>Start your own</Link>
    </div>
  );
}
