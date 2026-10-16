import { cookies } from "next/headers";
import { notFound, redirect } from "next/navigation";
import { getDb } from "@/db";
import { getUser, isAdmin, touchLogin, type User } from "./users";
import { makeSessionToken, readSessionToken, SESSION_COOKIE, sessionCookieOptions } from "./session";
import { normalizeSrc, SRC_COOKIE } from "./src";

export type Viewer = User & { isAdmin: boolean };

/** The signed-in user, or null. */
export async function currentUser(): Promise<Viewer | null> {
  const jar = await cookies();
  const uid = readSessionToken(jar.get(SESSION_COOKIE)?.value);
  if (!uid) return null;
  const u = await getUser(await getDb(), uid);
  return u ? { ...u, isAdmin: isAdmin(u) } : null;
}

export async function requireUser(next: string): Promise<Viewer> {
  const u = await currentUser();
  if (!u) redirect(`/login?next=${encodeURIComponent(next)}`);
  return u;
}

/** Admin pages answer 404 to everyone else, so they aren't discoverable. */
export async function requireAdmin(): Promise<Viewer> {
  const u = await currentUser();
  if (!u?.isAdmin) notFound();
  return u;
}

/** Only in Server Actions and Route Handlers (cookies can't be set while rendering). */
export async function signIn(userId: string) {
  const jar = await cookies();
  jar.set(SESSION_COOKIE, makeSessionToken(userId), sessionCookieOptions());
  await touchLogin(await getDb(), userId);
}

export async function signOut() {
  (await cookies()).delete(SESSION_COOKIE);
}

export async function currentSrc(): Promise<string> {
  return normalizeSrc((await cookies()).get(SRC_COOKIE)?.value);
}
