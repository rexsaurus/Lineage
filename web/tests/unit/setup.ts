// Every unit test runs offline: in-memory PGlite, a capturing mailer, an in-memory blob store, fake payments.
import { beforeEach } from "vitest";
import { createPgliteDb, setDb, type Db } from "@/db";
import { resetEnv } from "@/env";
import { setMailer, type Mail } from "@/lib/mail";
import { setStore, type BlobStore } from "@/lib/storage";
import { setPayments } from "@/lib/payments";

export const sent: Mail[] = [];
export const blobs = new Map<string, Buffer>();
export const ctx: { db: Db } = { db: undefined as unknown as Db };

const memStore: BlobStore = {
  async put(k, b) { blobs.set(k, b); },
  async get(k) { return blobs.get(k) || null; },
  async delete(k) { blobs.delete(k); },
  async signedGetUrl(k) { return `/mem/${k}`; },
  async signedPutUrl() { return null; },
};

export const BASE_ENV = {
  NODE_ENV: "test",
  APP_URL: "http://localhost:3000",
  PRICE_TBD: "true",
  PAYMENTS_DRIVER: "fake",
  MAIL_DRIVER: "console",
  STORAGE_DRIVER: "local",
  ADMIN_EMAILS: "rex@example.org",
};

export function useEnv(over: Record<string, string | undefined> = {}) {
  for (const k of Object.keys(process.env)) if (/^(PRICE_|PAYMENTS_|STRIPE_|MAIL_|STORAGE_|ADMIN_|KPI_|CRON_|SESSION_|ALLOW_|DATABASE_URL)/.test(k)) delete process.env[k];
  Object.assign(process.env, BASE_ENV, over);
  resetEnv();
}

beforeEach(async () => {
  useEnv();
  sent.length = 0;
  blobs.clear();
  setMailer({ async send(m) { sent.push(m); return { id: `m${sent.length}` }; } });
  setStore(memStore);
  setPayments(null);
  ctx.db = await createPgliteDb("memory://");
  setDb(ctx.db);
});
