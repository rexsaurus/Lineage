import type { Db } from "@/db";
import { checkUpload } from "./files";
import { addRecord, familyForViewer } from "./families";
import { cleanText } from "./crypto";
import { followupAfterFirstRecord } from "./followup";
import type { Viewer } from "./auth";

export type UploadResult = { ok: true; recordId: string } | { ok: false; status: number; message: string };

/** Shared by /api/upload (through the server) and /api/upload/complete (direct to storage). */
export async function acceptUpload(db: Db, a: { viewer: Viewer | null; familyId: string; bytes: Buffer; caption: unknown; blobKey?: string; isPrivate?: boolean }): Promise<UploadResult> {
  if (!a.viewer) return { ok: false, status: 401, message: "Please sign in again." };
  const f = await familyForViewer(db, a.familyId, a.viewer);
  if (!f) return { ok: false, status: 404, message: "Family page not found." };
  const c = checkUpload(a.bytes);
  if (!c.ok) return { ok: false, status: 400, message: c.message };
  const r = await addRecord(db, { familyId: f.id, userId: a.viewer.id, body: c.body, sniffed: c.sniffed, caption: cleanText(a.caption, 200) || null, blobKey: a.blobKey, isPrivate: !!a.isPrivate });
  try {
    await followupAfterFirstRecord(db, f.id, { email: a.viewer.email, name: a.viewer.name });
  } catch {
    console.error("follow-up email failed; the cron will retry it as a nudge"); // never block the upload
  }
  return { ok: true, recordId: r.id };
}
