import { and, eq } from "drizzle-orm";
import type { Db } from "@/db";
import { families, familyMembers, invites, users } from "@/db/schema";
import { randomToken } from "./crypto";
import { logActivity } from "./activity";

// Invites (spec §3.4): a token link by email or copied/shared by text. Each token joins one person, once.
export const INVITE_TTL_DAYS = 30;

export async function createInvite(db: Db, a: { familyId: string; invitedBy: string; email: string | null; name: string | null; src: string | null }) {
  const [inv] = await db
    .insert(invites)
    .values({ familyId: a.familyId, invitedBy: a.invitedBy, email: a.email, name: a.name, token: randomToken(24), eventSource: a.src })
    .returning();
  return inv;
}

export async function inviteByToken(db: Db, token: string) {
  if (!/^[A-Za-z0-9_-]{16,64}$/.test(token)) return null;
  const [row] = await db
    .select({ invite: invites, familyName: families.name, inviterName: users.name, inviterEmail: users.email })
    .from(invites)
    .innerJoin(families, eq(invites.familyId, families.id))
    .leftJoin(users, eq(invites.invitedBy, users.id))
    .where(eq(invites.token, token))
    .limit(1);
  if (!row) return null;
  const expired = Date.now() - row.invite.createdAt.getTime() > INVITE_TTL_DAYS * 86400_000;
  return { ...row, usable: row.invite.status === "sent" && !expired };
}

/** Accepts once: the first person to use the token joins as a member; later uses are refused. */
export async function acceptInvite(db: Db, token: string, userId: string): Promise<{ ok: true; familyId: string } | { ok: false; reason: string }> {
  const found = await inviteByToken(db, token);
  if (!found) return { ok: false, reason: "This invitation link isn't valid." };
  if (!found.usable) {
    // the same person opening their own accepted link again just goes to the family
    const [m] = await db.select().from(familyMembers).where(and(eq(familyMembers.familyId, found.invite.familyId), eq(familyMembers.userId, userId))).limit(1);
    if (m) return { ok: true, familyId: found.invite.familyId };
    return { ok: false, reason: "This invitation has already been used or has expired. Ask for a new one." };
  }
  const claimed = await db
    .update(invites)
    .set({ status: "accepted", acceptedAt: new Date() })
    .where(and(eq(invites.id, found.invite.id), eq(invites.status, "sent")))
    .returning({ id: invites.id });
  if (!claimed.length) return { ok: false, reason: "This invitation has already been used. Ask for a new one." };
  await db.insert(familyMembers).values({ familyId: found.invite.familyId, userId, role: "member" }).onConflictDoNothing();
  const [u] = await db.select({ name: users.name }).from(users).where(eq(users.id, userId)).limit(1);
  const first = (u?.name || "").trim().split(/\s+/)[0];
  await logActivity(db, { familyId: found.invite.familyId, kind: "member_joined", summary: first ? `${first} joined the family page` : "A relative joined the family page", actorUserId: userId });
  return { ok: true, familyId: found.invite.familyId };
}
