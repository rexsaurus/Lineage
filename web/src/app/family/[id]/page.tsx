import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/db";
import { requireUser } from "@/lib/auth";
import { familyForReader, familyNumber, listRecords } from "@/lib/families";
import { ensureRefCode, referralUrl } from "@/lib/refs";
import { RecordGrid } from "@/components/RecordGrid";

export const metadata = { title: "Family page" };

export default async function FamilyPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const { id } = await params;
  const sp = await searchParams;
  const u = await requireUser(`/family/${id}`);
  const db = await getDb();
  const r = await familyForReader(db, id, u);
  if (!r) notFound();
  const { family: f, access } = r;
  const canEdit = access !== "subscriber";
  // subscribers never see private records
  const recs = await listRecords(db, f.id, { includePrivate: canEdit });
  const n = recs.length && canEdit ? await familyNumber(db, f) : null;
  const shareLink = access === "archivist" ? referralUrl(f.id, await ensureRefCode(db, u.id)) : null;
  return (
    <div className="page">
      <h1>{f.name}</h1>
      {sp.following ? <p className="okmsg" role="status">You&apos;re following this family. We&apos;ll email you when there&apos;s something new.</p> : null}
      {sp.subscribed ? <p className="okmsg" role="status">Thank you for subscribing. We&apos;ll email you when there&apos;s something new.</p> : null}
      {n ? <p className="okmsg">You&apos;re family #{n} in Lineage.</p> : null}
      {recs.length ? <RecordGrid records={recs} /> : <p>{canEdit ? "Your page is ready. Add its first photo or document." : "Nothing has been shared here yet."}</p>}
      {canEdit ? (
        <>
          <Link className="btn" href={`/family/${f.id}/upload`}>{recs.length ? "Add another" : "Add a photo or document"}</Link>
          <Link className="btn secondary" href={`/family/${f.id}/invite`}>Invite a relative</Link>
        </>
      ) : null}
      {shareLink ? (
        <section className="card" aria-labelledby="share-h">
          <h2 id="share-h" style={{ marginTop: 0 }}>Share with relatives</h2>
          <p>Relatives who follow through your link get updates when you add to this page.</p>
          <label htmlFor="ref-link">Your link</label>
          <input id="ref-link" readOnly value={shareLink} />
          <Link className="btn secondary" style={{ marginTop: 12 }} href="/earnings">Your link, QR code and earnings</Link>
        </section>
      ) : null}
      <p style={{ marginTop: 20 }}><Link href={`/family/${f.id}/updates`}>Email updates</Link></p>
      {canEdit ? (
        <p className="small muted" style={{ marginTop: 24 }}>Coming next: Lineage reads your records and starts your family&apos;s history. We&apos;ll email you when it&apos;s ready.</p>
      ) : null}
    </div>
  );
}
