import { and, asc, count, desc, eq, inArray, lte } from "drizzle-orm";
import type { Db } from "@/db";
import { families, familyMembers, records, subscriptions, users } from "@/db/schema";
import { randomUUID } from "node:crypto";
import { store } from "./storage";
import type { Sniffed } from "./files";
import { logActivity } from "./activity";

export type Family = typeof families.$inferSelect;
export type RecordRow = typeof records.$inferSelect;

export async function createFamily(db: Db, a: { name: string; userId: string; src: string | null; isDemo?: boolean }): Promise<Family> {
  const [f] = await db.insert(families).values({ name: a.name, createdBy: a.userId, eventSource: a.src, isDemo: !!a.isDemo }).returning();
  await db.insert(familyMembers).values({ familyId: f.id, userId: a.userId, role: "archivist" }).onConflictDoNothing();
  return f;
}

export async function getFamily(db: Db, id: string): Promise<Family | null> {
  if (!/^[0-9a-f-]{36}$/i.test(id)) return null;
  const [f] = await db.select().from(families).where(eq(families.id, id)).limit(1);
  return f || null;
}

export async function memberRole(db: Db, familyId: string, userId: string | null): Promise<string | null> {
  if (!userId) return null;
  const [m] = await db
    .select({ role: familyMembers.role })
    .from(familyMembers)
    .where(and(eq(familyMembers.familyId, familyId), eq(familyMembers.userId, userId)))
    .limit(1);
  return m?.role || null;
}

/** Members only (admins may see any family). Anyone else gets null, and the page answers 404. */
export async function familyForViewer(db: Db, familyId: string, viewer: { id: string; isAdmin: boolean } | null): Promise<Family | null> {
  const f = await getFamily(db, familyId);
  if (!f || !viewer) return null;
  if (viewer.isAdmin) return f;
  return (await memberRole(db, f.id, viewer.id)) ? f : null;
}

export type Access = "admin" | "archivist" | "member" | "subscriber";

/** Who may READ a family: members, admins, and relatives with a live subscription or follow (read-only, and never
 * the private records). Returns the access level, or null (→ 404). Editing (upload, invite) uses familyForViewer. */
export async function familyForReader(db: Db, familyId: string, viewer: { id: string; isAdmin: boolean } | null): Promise<{ family: Family; access: Access } | null> {
  const f = await getFamily(db, familyId);
  if (!f || !viewer) return null;
  if (viewer.isAdmin) return { family: f, access: "admin" };
  const role = await memberRole(db, f.id, viewer.id);
  if (role) return { family: f, access: role === "archivist" ? "archivist" : "member" };
  const [s] = await db
    .select({ status: subscriptions.status })
    .from(subscriptions)
    .where(and(eq(subscriptions.familyId, f.id), eq(subscriptions.userId, viewer.id), inArray(subscriptions.status, READ_STATUSES)))
    .limit(1);
  return s ? { family: f, access: "subscriber" } : null;
}

/** Subscription states that keep read access (past_due keeps it while Stripe retries the card). */
export const READ_STATUSES = ["active", "past_due"];

export async function familiesOf(db: Db, userId: string): Promise<Family[]> {
  return db
    .select({ f: families })
    .from(familyMembers)
    .innerJoin(families, eq(familyMembers.familyId, families.id))
    .where(eq(familyMembers.userId, userId))
    .orderBy(asc(families.createdAt))
    .then(r => r.map(x => x.f));
}

export async function listRecords(db: Db, familyId: string, opts: { includePrivate?: boolean } = { includePrivate: true }): Promise<RecordRow[]> {
  const where = opts.includePrivate ? eq(records.familyId, familyId) : and(eq(records.familyId, familyId), eq(records.isPrivate, false));
  return db.select().from(records).where(where).orderBy(desc(records.createdAt));
}

export async function getRecord(db: Db, id: string): Promise<RecordRow | null> {
  if (!/^[0-9a-f-]{36}$/i.test(id)) return null;
  const [r] = await db.select().from(records).where(eq(records.id, id)).limit(1);
  return r || null;
}

export function newBlobKey(familyId: string, ext: string) {
  return `${familyId}/${randomUUID()}.${ext}`;
}

export async function addRecord(db: Db, a: { familyId: string; userId: string; body: Buffer; sniffed: Sniffed; caption: string | null; blobKey?: string; isPrivate?: boolean }) {
  const key = a.blobKey || newBlobKey(a.familyId, a.sniffed.ext);
  await store().put(key, a.body, a.sniffed.mime);
  const [r] = await db
    .insert(records)
    .values({ familyId: a.familyId, uploadedBy: a.userId, blobKey: key, mimeType: a.sniffed.mime, sizeBytes: a.body.length, caption: a.caption, kind: a.sniffed.kind, isPrivate: !!a.isPrivate })
    .returning();
  const what = a.sniffed.kind === "photo" ? "A new photo" : "A new document";
  await logActivity(db, { familyId: a.familyId, kind: "record_added", summary: a.caption ? `${what}: ${a.caption}` : what, actorUserId: a.userId, recordId: r.id, isPrivate: !!a.isPrivate });
  return r;
}

/** Change a caption (logged for the digest). */
export async function setCaption(db: Db, recordId: string, caption: string | null, actorUserId: string) {
  const [r] = await db.update(records).set({ caption }).where(eq(records.id, recordId)).returning();
  if (r) await logActivity(db, { familyId: r.familyId, kind: "caption_changed", summary: caption ? `Caption added: ${caption}` : "A caption was removed", actorUserId, recordId: r.id, isPrivate: r.isPrivate });
  return r;
}

/** "You're family #N in Lineage": this family's position among real (non-demo) families, from the database. */
export async function familyNumber(db: Db, f: Family): Promise<number | null> {
  if (f.isDemo) return null;
  const [r] = await db.select({ n: count() }).from(families).where(and(eq(families.isDemo, false), lte(families.createdAt, f.createdAt)));
  return r?.n ?? null;
}

/** Admin delete (spec §12): the family, its records and their files. */
export async function deleteFamily(db: Db, familyId: string) {
  const recs = await db.select({ key: records.blobKey }).from(records).where(eq(records.familyId, familyId));
  for (const r of recs) await store().delete(r.key).catch(() => {});
  await db.delete(families).where(eq(families.id, familyId));
}

export async function membersOf(db: Db, familyId: string) {
  return db
    .select({ id: users.id, email: users.email, name: users.name, role: familyMembers.role })
    .from(familyMembers)
    .innerJoin(users, eq(familyMembers.userId, users.id))
    .where(eq(familyMembers.familyId, familyId));
}
