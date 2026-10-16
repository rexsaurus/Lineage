import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/db";
import { requireUser } from "@/lib/auth";
import { familyForViewer, familyNumber, listRecords } from "@/lib/families";
import { RecordGrid } from "@/components/RecordGrid";

export const metadata = { title: "Family page" };

export default async function FamilyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const u = await requireUser(`/family/${id}`);
  const db = await getDb();
  const f = await familyForViewer(db, id, u);
  if (!f) notFound();
  const recs = await listRecords(db, f.id);
  const n = recs.length ? await familyNumber(db, f) : null;
  return (
    <div className="page">
      <h1>{f.name}</h1>
      {n ? <p className="okmsg">You&apos;re family #{n} in Lineage.</p> : null}
      {recs.length ? (
        <RecordGrid records={recs} />
      ) : (
        <p>Your page is ready. Add its first photo or document.</p>
      )}
      <Link className="btn" href={`/family/${f.id}/upload`}>{recs.length ? "Add another" : "Add a photo or document"}</Link>
      <Link className="btn secondary" href={`/family/${f.id}/invite`}>Invite a relative</Link>
      <p className="small muted" style={{ marginTop: 24 }}>
        Coming next: Lineage reads your records and starts your family&apos;s history. We&apos;ll email you when it&apos;s ready.
      </p>
    </div>
  );
}
