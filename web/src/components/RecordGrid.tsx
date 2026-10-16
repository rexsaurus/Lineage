type R = { id: string; caption: string | null; kind: string | null; mimeType: string | null };

/** Records as large thumbnails. Images load through /api/records/[id]/file, which checks membership first. */
export function RecordGrid({ records, demo = false }: { records: R[]; demo?: boolean }) {
  return (
    <div className="records">
      {records.map(r => (
        <figure key={r.id} className="record" style={{ margin: 0 }}>
          {r.kind === "photo" && r.mimeType !== "image/heic" ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={`/api/records/${r.id}/file`} alt={r.caption || "Family photo"} loading="lazy" />
          ) : (
            <a className="doc" href={`/api/records/${r.id}/file`}>{r.mimeType === "application/pdf" ? "PDF" : "Photo"}</a>
          )}
          <p>{r.caption || (demo ? "Demo content" : "")}</p>
        </figure>
      ))}
    </div>
  );
}
