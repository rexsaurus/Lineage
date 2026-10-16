import { and, eq, inArray, ne } from "drizzle-orm";
import type { Db } from "@/db";
import { families, subscriptions, users } from "@/db/schema";
import { env, sessionSecret } from "@/env";
import { signPayload, verifyPayload } from "./crypto";
import { publicActivity } from "./activity";
import { sendLogged } from "./mail";
import { READ_STATUSES } from "./families";

// Regular updates for subscribers (spec: weekly by default; weekly, monthly or off per subscriber). A daily cron calls
// runDigests; each subscription gets at most one digest per period (emails.dedupe_key = digest:<sub>:<period>), and
// only when something public changed. Private records never appear. Each email has a signed one-click unsubscribe.

/** "2026-W43" (ISO week) or "2026-10". */
export function periodKey(freq: "weekly" | "monthly", d: Date): string {
  if (freq === "monthly") return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
  const t = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  const day = t.getUTCDay() || 7;
  t.setUTCDate(t.getUTCDate() + 4 - day);
  const year = t.getUTCFullYear();
  const week = Math.ceil(((t.getTime() - Date.UTC(year, 0, 1)) / 86400_000 + 1) / 7);
  return `${year}-W${String(week).padStart(2, "0")}`;
}

/** The start of the period a digest covers: the previous digest, or when they subscribed. */
function since(s: { lastDigestAt: Date | null; createdAt: Date }) {
  return s.lastDigestAt || s.createdAt;
}

export function unsubscribeToken(subscriptionId: string) {
  return signPayload(sessionSecret(), { sub: subscriptionId, p: "unsub" });
}
export function readUnsubscribeToken(token: string): string | null {
  const v = verifyPayload<{ sub: string; p: string }>(sessionSecret(), token);
  return v && v.p === "unsub" && /^[0-9a-f-]{36}$/i.test(v.sub) ? v.sub : null;
}

export async function setDigestFreq(db: Db, subscriptionId: string, freq: "weekly" | "monthly" | "off") {
  await db.update(subscriptions).set({ digestFreq: freq }).where(eq(subscriptions.id, subscriptionId));
}

export function digestText(a: { name: string | null; familyName: string; familyId: string; items: { summary: string; createdAt: Date }[]; unsubscribeUrl: string; prefsUrl: string }) {
  const first = (a.name || "").trim().split(/\s+/)[0] || "there";
  const lines = a.items.slice(0, 30).map(i => `• ${i.summary} (${i.createdAt.toISOString().slice(0, 10)})`);
  const more = a.items.length > 30 ? `\n…and ${a.items.length - 30} more.` : "";
  const url = new URL(`/family/${a.familyId}`, env().APP_URL).toString();
  return `Hi ${first},\n\nHere's what's new on the ${a.familyName} family page:\n\n${lines.join("\n")}${more}\n\nSee it all: ${url}\n\n— Lineage\n\nChange how often you hear from us: ${a.prefsUrl}\nUnsubscribe from these updates: ${a.unsubscribeUrl}`;
}

/** Sends every due digest. Returns how many went out. Safe to run any number of times a day. */
export async function runDigests(db: Db, now = new Date()): Promise<number> {
  const subs = await db
    .select({ s: subscriptions, email: users.email, name: users.name, familyName: families.name, isDemo: families.isDemo })
    .from(subscriptions)
    .innerJoin(users, eq(subscriptions.userId, users.id))
    .innerJoin(families, eq(subscriptions.familyId, families.id))
    .where(and(inArray(subscriptions.status, READ_STATUSES), ne(subscriptions.digestFreq, "off")));
  let sent = 0;
  for (const r of subs) {
    if (r.isDemo) continue;
    const freq = r.s.digestFreq === "monthly" ? "monthly" : "weekly";
    // nothing in the period they subscribed in: the first digest goes out in the next period
    if (periodKey(freq, since(r.s)) === periodKey(freq, now) && !r.s.lastDigestAt) continue;
    if (r.s.lastDigestAt && periodKey(freq, r.s.lastDigestAt) === periodKey(freq, now)) continue;
    const items = (await publicActivity(db, r.s.familyId, since(r.s), now)).filter(i => i.actorUserId !== r.s.userId);
    if (!items.length) continue;
    const base = env().APP_URL;
    const ok = await sendLogged(db, {
      to: r.email,
      kind: "digest",
      dedupeKey: `digest:${r.s.id}:${periodKey(freq, now)}`,
      subject: `What's new on the ${r.familyName} family page`,
      text: digestText({
        name: r.name, familyName: r.familyName, familyId: r.s.familyId, items,
        unsubscribeUrl: new URL(`/u/${unsubscribeToken(r.s.id)}`, base).toString(),
        prefsUrl: new URL(`/family/${r.s.familyId}/updates`, base).toString(),
      }),
      headers: {
        "List-Unsubscribe": `<${new URL(`/api/unsubscribe/${unsubscribeToken(r.s.id)}`, base).toString()}>`,
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
      },
    });
    if (ok) {
      await db.update(subscriptions).set({ lastDigestAt: now }).where(eq(subscriptions.id, r.s.id));
      sent++;
    }
  }
  return sent;
}
