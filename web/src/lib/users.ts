import { eq, sql } from "drizzle-orm";
import type { Db } from "@/db";
import { users } from "@/db/schema";
import { adminEmails } from "@/env";

export type User = typeof users.$inferSelect;

/** Find or create a user by email. The event source is kept from the first touch only. */
export async function upsertUser(db: Db, a: { email: string; name?: string | null; src: string; role?: string }): Promise<User> {
  const role = adminEmails().includes(a.email) ? "admin" : a.role || "archivist";
  const [row] = await db
    .insert(users)
    .values({ email: a.email, name: a.name || null, eventSource: a.src, role })
    .onConflictDoUpdate({
      target: users.email,
      set: { name: sql`coalesce(${users.name}, excluded.name)` },
    })
    .returning();
  return row;
}

export async function getUser(db: Db, id: string | null): Promise<User | null> {
  if (!id || !/^[0-9a-f-]{36}$/i.test(id)) return null;
  const [u] = await db.select().from(users).where(eq(users.id, id)).limit(1);
  return u || null;
}

export async function getUserByEmail(db: Db, email: string): Promise<User | null> {
  const [u] = await db.select().from(users).where(eq(users.email, email)).limit(1);
  return u || null;
}

export async function touchLogin(db: Db, id: string) {
  await db.update(users).set({ lastLoginAt: new Date() }).where(eq(users.id, id));
}

export function isAdmin(u: Pick<User, "email"> | null): boolean {
  return !!u && adminEmails().includes(u.email);
}
