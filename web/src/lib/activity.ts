import { and, asc, eq, gt, lte } from "drizzle-orm";
import type { Db } from "@/db";
import { activity } from "@/db/schema";

// The change log every digest is built from. Written on every record/family change; private items are flagged here
// and never leave the family.
export type ActivityKind = "record_added" | "caption_changed" | "member_joined" | "family_renamed" | "post_published";

export async function logActivity(
  db: Db,
  a: { familyId: string; kind: ActivityKind; summary: string; actorUserId?: string | null; recordId?: string | null; isPrivate?: boolean; at?: Date },
) {
  await db.insert(activity).values({
    familyId: a.familyId,
    kind: a.kind,
    summary: a.summary.slice(0, 300),
    actorUserId: a.actorUserId || null,
    recordId: a.recordId || null,
    isPrivate: !!a.isPrivate,
    ...(a.at ? { createdAt: a.at } : {}),
  });
}

/** Public (non-private) changes to a family in (since, until]. */
export async function publicActivity(db: Db, familyId: string, since: Date, until: Date) {
  return db
    .select()
    .from(activity)
    .where(and(eq(activity.familyId, familyId), eq(activity.isPrivate, false), gt(activity.createdAt, since), lte(activity.createdAt, until)))
    .orderBy(asc(activity.createdAt));
}
