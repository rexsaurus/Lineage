import { and, asc, count, desc, eq, lte } from "drizzle-orm";
import type { Db } from "@/db";
import { families, familyMembers, records, users } from "@/db/schema";
import { randomUUID } from "node:crypto";
import { store } from "./storage";
import type { Sniffed } from "./files";

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

export async function familiesOf(db: Db, userId: string): Promise<Family[]> {
  return db
    .select({ f: families })
    .from(familyMembers)
    .innerJoin(families, eq(familyMembers.familyId, families.id))
    .where(eq(familyMembers.userId, userId))
    .orderBy(asc(families.createdAt))
    .then(r => r.map(x => x.f));
}

export async function listRecords(db: Db, familyId: string): Promise<RecordRow[]> {
  return db.select().from(records).where(eq(records.familyId, familyId)).orderBy(desc(records.createdAt));
}

export async function getRecord(db: Db, id: string): Promise<RecordRow | null> {
  if (!/^[0-9a-f-]{36}$/i.test(id)) return null;
  const [r] = await db.select().from(records).where(eq(records.id, id)).limit(1);
  return r || null;
}

export function newBlobKey(familyId: string, ext: string) {
  return `${familyId}/${randomUUID()}.${ext}`;
}

export async function addRecord(db: Db, a: { familyId: string; userId: string; body: Buffer; sniffed: Sniffed; caption: string | null; blobKey?: string }) {
  const key = a.blobKey || newBlobKey(a.familyId, a.sniffed.ext);
  await store().put(key, a.body, a.sniffed.mime);
  const [r] = await db
    .insert(records)
    .values({ familyId: a.familyId, uploadedBy: a.userId, blobKey: key, mimeType: a.sniffed.mime, sizeBytes: a.body.length, caption: a.caption, kind: a.sniffed.kind })
    .returning();
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
