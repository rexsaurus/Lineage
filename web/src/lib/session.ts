import { signPayload, verifyPayload } from "./crypto";
import { env, sessionSecret } from "@/env";

// The signed-in user: a signed, HttpOnly cookie holding the user id and an expiry. No passwords (spec §3, §11).
export const SESSION_COOKIE = "lineage_session";
export const SESSION_DAYS = 30;

type Session = { uid: string; exp: number };

export function makeSessionToken(userId: string, now = Date.now()): string {
  return signPayload(sessionSecret(), { uid: userId, exp: now + SESSION_DAYS * 86400_000 } satisfies Session);
}

export function readSessionToken(token: string | undefined | null, now = Date.now()): string | null {
  const s = verifyPayload<Session>(sessionSecret(), token);
  if (!s || typeof s.uid !== "string" || typeof s.exp !== "number" || s.exp < now) return null;
  return s.uid;
}

/** Secure whenever the app is served over https (always, in production). */
export function sessionCookieOptions() {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    path: "/",
    maxAge: SESSION_DAYS * 86400,
    secure: env().APP_URL.startsWith("https://"),
  };
}
