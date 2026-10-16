import { and, eq, lt, sql } from "drizzle-orm";
import type { Db } from "@/db";
import { events, families, familyMembers, users } from "@/db/schema";
import { sendFollowupEmail, sendNudgeEmail } from "./emails";
import { adminEmails } from "@/env";

// Spec §7: the follow-up goes right after a family's first record; anyone who signed up but hasn't uploaded gets one
// nudge an hour later (Vercel Cron → /api/cron/followups). Each is sent at most once (emails.dedupe_key).

async function eventName(db: Db, slug: string | null) {
  if (!slug || slug === "direct") return null;
  const [e] = await db.select({ name: events.name }).from(events).where(eq(events.slug, slug)).limit(1);
  return e?.name || null;
}

/** Called after an upload. Sends only for the family's first record, and only once. */
export async function followupAfterFirstRecord(db: Db, familyId: string, user: { email: string; name: string | null }): Promise<boolean> {
  const [f] = await db
    .select({ id: families.id, name: families.name, src: families.eventSource, isDemo: families.isDemo, n: sql<number>`(select count(*) from records r where r.family_id = "families"."id")` })
    .from(families)
    .where(eq(families.id, familyId))
    .limit(1);
  if (!f || f.isDemo || Number(f.n) !== 1) return false;
  return sendFollowupEmail(db, { to: user.email, name: user.name, eventName: await eventName(db, f.src), familyName: f.name, familyId: f.id });
}

/** The cron: archivists who signed up more than an hour ago and have no records yet. Returns how many were sent. */
export async function runNudges(db: Db, now = new Date()): Promise<number> {
  const cutoff = new Date(now.getTime() - 60 * 60 * 1000);
  const admins = adminEmails();
  const candidates = await db
    .select({ id: users.id, email: users.email, name: users.name })
    .from(users)
    .where(and(eq(users.role, "archivist"), lt(users.createdAt, cutoff)))
    .limit(200);
  let sent = 0;
  for (const u of candidates) {
    if (admins.includes(u.email)) continue;
    const fams = await db
      .select({ id: families.id, n: sql<number>`(select count(*) from records r where r.family_id = "families"."id")` })
      .from(familyMembers)
      .innerJoin(families, eq(familyMembers.familyId, families.id))
      .where(and(eq(familyMembers.userId, u.id), eq(families.isDemo, false)));
    if (fams.some(f => Number(f.n) > 0)) continue;
    if (await sendNudgeEmail(db, { to: u.email, name: u.name, userId: u.id, familyId: fams[0]?.id || null })) sent++;
  }
  return sent;
}
