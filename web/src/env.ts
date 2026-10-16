import { z } from "zod";

// Every setting the app reads, validated once. Defaults are safe for local development: no price (PRICE_TBD=true),
// fake payments, email written to .data/outbox, files stored in .data/blobs, the database in .data/pglite.
const bool = (d: boolean) =>
  z.enum(["true", "false", "1", "0"]).optional().transform(v => (v === undefined ? d : v === "true" || v === "1"));

const schema = z
  .object({
    NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
    APP_URL: z.string().url().default("http://localhost:3000"),
    SESSION_SECRET: z.string().min(32).optional(),

    // database: DATABASE_URL (Postgres) in production; PGlite (embedded Postgres) when unset
    DATABASE_URL: z.string().optional(),
    PGLITE_DIR: z.string().default(".data/pglite"),

    // offer and payments
    PRICE_TBD: bool(true),
    PRICE_DISPLAY: z.string().max(40).optional(),
    PAYMENTS_DRIVER: z.enum(["stripe", "fake"]).default("fake"),
    STRIPE_SECRET_KEY: z.string().optional(),
    STRIPE_PUBLISHABLE_KEY: z.string().optional(),
    STRIPE_WEBHOOK_SECRET: z.string().optional(),
    STRIPE_PRICE_ID_FOUNDING: z.string().optional(),
    STRIPE_PAYMENT_LINK_URL: z.string().url().optional(),
    ALLOW_LIVE_STRIPE: bool(false),

    // family subscriptions (relatives following a family's Lineage)
    SUB_PRICE_TBD: bool(true), // true: a free "follow" only, no price shown, no payment
    SUB_PRICE_DISPLAY: z.string().max(60).optional(),
    STRIPE_PRICE_ID_FAMILY_SUB: z.string().optional(),

    // referral earnings — no defaults: unset means the program isn't open / not decided
    REV_SHARE_PCT: z
      .string()
      .regex(/^\d{1,2}(\.\d{1,2})?$|^100$/, "a percentage like 20 or 12.5")
      .optional(),
    REFUND_HOLD_DAYS: z.string().regex(/^\d{1,3}$/).optional(),
    MIN_PAYOUT_CENTS: z.string().regex(/^\d{1,9}$/).optional(),
    PAYOUT_CRON_ENABLED: bool(false),
    CONNECT_DRIVER: z.enum(["stripe", "fake"]).default("fake"),

    // fake driver only (local runs and tests): what a fake subscription invoice charges. Never used with real Stripe.
    FAKE_SUB_AMOUNT_CENTS: z.string().regex(/^\d{1,9}$/).optional(),
    FAKE_SUB_CURRENCY: z.string().regex(/^[a-z]{3}$/).default("usd"),

    // email
    MAIL_DRIVER: z.enum(["console", "resend"]).default("console"),
    RESEND_API_KEY: z.string().optional(),
    MAIL_FROM: z.string().default("Rex at Lineage <rex@example.org>"),
    MAIL_REPLY_TO: z.string().optional(),
    OUTBOX_DIR: z.string().default(".data/outbox"),

    // file storage
    STORAGE_DRIVER: z.enum(["local", "r2"]).default("local"),
    LOCAL_BLOB_DIR: z.string().default(".data/blobs"),
    R2_ACCOUNT_ID: z.string().optional(),
    R2_ACCESS_KEY_ID: z.string().optional(),
    R2_SECRET_ACCESS_KEY: z.string().optional(),
    R2_BUCKET: z.string().optional(),

    // admin
    ADMIN_EMAILS: z.string().default(""),
    KPI_EXPORT_TOKEN: z.string().min(24).optional(),
    CRON_SECRET: z.string().min(16).optional(),
  })
  .superRefine((e, ctx) => {
    const need = (k: keyof typeof e, why: string) => {
      if (!e[k]) ctx.addIssue({ code: "custom", path: [k], message: `${k} is required ${why}` });
    };
    if (e.NODE_ENV === "production") need("SESSION_SECRET", "in production");
    if (!e.PRICE_TBD) need("PRICE_DISPLAY", "when PRICE_TBD=false");
    if (e.PAYMENTS_DRIVER === "stripe") {
      need("STRIPE_SECRET_KEY", "for PAYMENTS_DRIVER=stripe");
      need("STRIPE_WEBHOOK_SECRET", "for PAYMENTS_DRIVER=stripe");
      need("STRIPE_PRICE_ID_FOUNDING", "for PAYMENTS_DRIVER=stripe");
      if (e.STRIPE_SECRET_KEY?.startsWith("sk_live_") && !e.ALLOW_LIVE_STRIPE)
        ctx.addIssue({ code: "custom", path: ["STRIPE_SECRET_KEY"], message: "live Stripe key refused: set ALLOW_LIVE_STRIPE=true only after Rex confirms price and entity" });
    }
    if (!e.SUB_PRICE_TBD) {
      need("SUB_PRICE_DISPLAY", "when SUB_PRICE_TBD=false");
      if (e.PAYMENTS_DRIVER === "stripe") need("STRIPE_PRICE_ID_FAMILY_SUB", "for paid subscriptions with Stripe");
    }
    if (e.CONNECT_DRIVER === "stripe") need("STRIPE_SECRET_KEY", "for CONNECT_DRIVER=stripe");
    if (e.MAIL_DRIVER === "resend") need("RESEND_API_KEY", "for MAIL_DRIVER=resend");
    if (e.STORAGE_DRIVER === "r2") {
      need("R2_ACCOUNT_ID", "for STORAGE_DRIVER=r2");
      need("R2_ACCESS_KEY_ID", "for STORAGE_DRIVER=r2");
      need("R2_SECRET_ACCESS_KEY", "for STORAGE_DRIVER=r2");
      need("R2_BUCKET", "for STORAGE_DRIVER=r2");
    }
    if (e.STRIPE_PAYMENT_LINK_URL && !/^https:\/\/([a-z0-9-]+\.)*stripe\.com\//.test(e.STRIPE_PAYMENT_LINK_URL))
      ctx.addIssue({ code: "custom", path: ["STRIPE_PAYMENT_LINK_URL"], message: "must be a https://…stripe.com/ Payment Link" });
  });

export type Env = z.infer<typeof schema>;

let cached: Env | null = null;
export function env(): Env {
  if (!cached) cached = parseEnv(process.env);
  return cached;
}
export function parseEnv(src: Record<string, string | undefined>): Env {
  // an empty value (as copied from .env.example) means "not set"
  const clean = Object.fromEntries(Object.entries(src).map(([k, v]) => [k, v === "" ? undefined : v]));
  const r = schema.safeParse(clean);
  if (!r.success) throw new Error("Invalid environment:\n" + r.error.issues.map(i => `  ${i.path.join(".")}: ${i.message}`).join("\n"));
  return r.data;
}
/** for tests */
export function resetEnv() {
  cached = null;
}

export function sessionSecret(): string {
  // dev/test fall back to a fixed, clearly non-production secret; production must set SESSION_SECRET (enforced above)
  return env().SESSION_SECRET || "dev-only-session-secret-do-not-use-in-production";
}
export function adminEmails(): string[] {
  return env().ADMIN_EMAILS.split(",").map(s => s.trim().toLowerCase()).filter(Boolean);
}
export function priceDisplay(): string | null {
  const e = env();
  return e.PRICE_TBD ? null : e.PRICE_DISPLAY || null;
}
export function subPriceDisplay(): string | null {
  const e = env();
  return e.SUB_PRICE_TBD ? null : e.SUB_PRICE_DISPLAY || null;
}
/** The revenue share in basis points (20% → 2000), or null while the earnings program isn't open. */
export function revShareBps(): number | null {
  const p = env().REV_SHARE_PCT;
  return p ? Math.round(parseFloat(p) * 100) : null;
}
/** Days a referral earning waits before it can be paid out, or null if not decided (earnings then stay pending). */
export function refundHoldDays(): number | null {
  const d = env().REFUND_HOLD_DAYS;
  return d === undefined ? null : parseInt(d, 10);
}
export function minPayoutCents(): number {
  return parseInt(env().MIN_PAYOUT_CENTS || "0", 10);
}
