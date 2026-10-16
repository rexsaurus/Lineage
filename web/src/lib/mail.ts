import fs from "node:fs";
import path from "node:path";
import { env } from "@/env";
import type { Db } from "@/db";
import { emails } from "@/db/schema";

// Email (spec §7). Development and tests never send anything: the "console" driver writes each message to
// OUTBOX_DIR as JSON and logs only its kind. Production uses Resend's HTTP API (no SDK needed).
export type Mail = { to: string; subject: string; text: string; kind: string; dedupeKey?: string; headers?: Record<string, string> };

export interface Mailer {
  send(m: Mail): Promise<{ id: string | null }>;
}

class ConsoleMailer implements Mailer {
  constructor(private dir: string) {}
  async send(m: Mail) {
    fs.mkdirSync(this.dir, { recursive: true });
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    fs.writeFileSync(path.join(this.dir, `${id}.json`), JSON.stringify({ ...m, at: new Date().toISOString() }, null, 2));
    console.log(`[mail:console] ${m.kind} queued in ${this.dir}`);
    return { id };
  }
}

class ResendMailer implements Mailer {
  constructor(private key: string, private from: string, private replyTo?: string) {}
  async send(m: Mail) {
    const r = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: { Authorization: `Bearer ${this.key}`, "Content-Type": "application/json" },
      body: JSON.stringify({ from: this.from, to: [m.to], subject: m.subject, text: m.text, reply_to: this.replyTo, headers: m.headers }),
    });
    if (!r.ok) throw new Error(`email provider HTTP ${r.status}`);
    const j = (await r.json()) as { id?: string };
    return { id: j.id || null };
  }
}

let override: Mailer | null = null;
export function setMailer(m: Mailer | null) {
  override = m;
}
export function mailer(): Mailer {
  if (override) return override;
  const e = env();
  return e.MAIL_DRIVER === "resend" ? new ResendMailer(e.RESEND_API_KEY!, e.MAIL_FROM, e.MAIL_REPLY_TO) : new ConsoleMailer(e.OUTBOX_DIR);
}

/** Sends and logs the email. With a dedupeKey, a second call with the same key sends nothing and returns false. */
export async function sendLogged(db: Db, m: Mail): Promise<boolean> {
  if (m.dedupeKey) {
    const claimed = await db
      .insert(emails)
      .values({ toEmail: m.to, kind: m.kind, dedupeKey: m.dedupeKey })
      .onConflictDoNothing({ target: emails.dedupeKey })
      .returning({ id: emails.id });
    if (!claimed.length) return false;
    try {
      await mailer().send(m);
    } catch (err) {
      // release the claim so the cron can retry
      const { eq } = await import("drizzle-orm");
      await db.delete(emails).where(eq(emails.id, claimed[0].id));
      throw err;
    }
    return true;
  }
  const { id } = await mailer().send(m);
  await db.insert(emails).values({ toEmail: m.to, kind: m.kind, providerId: id });
  return true;
}
