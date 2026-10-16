import { and, eq, isNull } from "drizzle-orm";
import { randomBytes } from "node:crypto";
import type { Db } from "@/db";
import { familyMembers, users } from "@/db/schema";
import { env } from "@/env";

// Archivist referral codes and attribution. A relative who arrives through /f/<familyId>?ref=<code> keeps the code in a
// first-touch cookie for 60 days; it is recorded on their subscription. A code counts only for a family its owner is
// the archivist of, and never for the subscriber themself (no self-referral).
export const REF_COOKIE = "lineage_ref";
export const REF_MAX_AGE = 60 * 24 * 60 * 60;
const ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"; // no 0/o, 1/l/i
const CODE = /^[a-hj-km-np-z2-9]{8}$/;

export function isRefCode(v: unknown): v is string {
  return typeof v === "string" && CODE.test(v);
}

function newCode() {
  const b = randomBytes(8);
  return Array.from(b, x => ALPHABET[x % ALPHABET.length]).join("");
}

/** The user's referral code, created on first use. */
export async function ensureRefCode(db: Db, userId: string): Promise<string> {
  for (let i = 0; i < 5; i++) {
    const [u] = await db.select({ code: users.refCode }).from(users).where(eq(users.id, userId)).limit(1);
    if (u?.code) return u.code;
    try {
      await db.update(users).set({ refCode: newCode() }).where(and(eq(users.id, userId), isNull(users.refCode)));
    } catch {
      // a rare code collision: try again
    }
  }
  throw new Error("could not create a referral code");
}

export function referralUrl(familyId: string, code: string) {
  return new URL(`/f/${familyId}?ref=${code}`, env().APP_URL).toString();
}

/** The referrer to credit for a new subscription, or null: unknown code, self-referral, or not this family's archivist. */
export async function resolveReferrer(db: Db, a: { refCode: string | null | undefined; familyId: string; subscriberUserId: string }): Promise<string | null> {
  if (!isRefCode(a.refCode)) return null;
  const [u] = await db.select({ id: users.id }).from(users).where(eq(users.refCode, a.refCode)).limit(1);
  if (!u || u.id === a.subscriberUserId) return null;
  const [m] = await db
    .select({ role: familyMembers.role })
    .from(familyMembers)
    .where(and(eq(familyMembers.familyId, a.familyId), eq(familyMembers.userId, u.id)))
    .limit(1);
  return m?.role === "archivist" ? u.id : null;
}
