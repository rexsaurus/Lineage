import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/db";
import { requireUser } from "@/lib/auth";
import { familyForViewer, listRecords } from "@/lib/families";
import { UploadForm } from "@/components/UploadForm";

export const metadata = { title: "Add a record" };

export default async function Upload({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const u = await requireUser(`/family/${id}/upload`);
  const db = await getDb();
  const f = await familyForViewer(db, id, u);
  if (!f) notFound();
  const first = (await listRecords(db, f.id)).length === 0;
  return (
    <div className="page">
      {first ? <p className="steps">Step 3 of 4</p> : null}
      <h1>{first ? "Add your first record" : "Add a record"}</h1>
      <p>A photo of an old picture, letter or certificate is perfect.</p>
      <UploadForm familyId={f.id} />
      <p style={{ marginTop: 24 }}><Link href={`/family/${f.id}`}>Back to the {f.name} page</Link></p>
    </div>
  );
}
