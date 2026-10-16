import { and, eq, gt, isNull } from "drizzle-orm";
import type { Db } from "@/db";
import { magicLinks } from "@/db/schema";
import { randomToken, sha256 } from "./crypto";

// Magic links (spec §3.2): 15-minute expiry, single use. Only the token's hash is stored.
export const MAGIC_TTL_MS = 15 * 60 * 1000;

/** A safe in-app path to return to after sign-in (no open redirects). */
export function safeRedirect(v: unknown): string | null {
  return typeof v === "string" && /^\/(?!\/)[A-Za-z0-9/_\-?=&.%]*$/.test(v) ? v : null;
}

export async function createMagicLink(db: Db, email: string, redirectTo?: string | null, now = Date.now()): Promise<string> {
  const token = randomToken();
  await db.insert(magicLinks).values({
    tokenHash: sha256(token),
    email,
    redirectTo: safeRedirect(redirectTo),
    expiresAt: new Date(now + MAGIC_TTL_MS),
  });
  return token;
}

/** Marks the link used and returns its email and redirect, or null if unknown, expired or already used. */
export async function consumeMagicLink(db: Db, token: string, now = Date.now()): Promise<{ email: string; redirectTo: string | null } | null> {
  if (!token || token.length > 100) return null;
  const [row] = await db
    .update(magicLinks)
    .set({ usedAt: new Date(now) })
    .where(and(eq(magicLinks.tokenHash, sha256(token)), isNull(magicLinks.usedAt), gt(magicLinks.expiresAt, new Date(now))))
    .returning();
  return row ? { email: row.email, redirectTo: row.redirectTo } : null;
}
