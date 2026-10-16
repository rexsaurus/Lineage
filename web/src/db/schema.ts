import { boolean, integer, pgTable, primaryKey, text, timestamp, uuid, uniqueIndex, index } from "drizzle-orm/pg-core";

// Spec §5. Emails are stored lower-cased in text columns with unique indexes (equivalent to citext for our use, and it
// works the same on Postgres and on PGlite without an extension).
const now = () => timestamp({ withTimezone: true }).defaultNow().notNull();

export const users = pgTable("users", {
  id: uuid().primaryKey().defaultRandom(),
  email: text().notNull().unique(),
  name: text(),
  role: text().notNull().default("archivist"), // 'archivist' | 'member' | 'admin'
  eventSource: text("event_source"), // slug from ?src at first touch
  createdAt: now(),
  lastLoginAt: timestamp("last_login_at", { withTimezone: true }),
});

export const families = pgTable("families", {
  id: uuid().primaryKey().defaultRandom(),
  name: text().notNull(),
  createdBy: uuid("created_by").references(() => users.id, { onDelete: "set null" }),
  eventSource: text("event_source"),
  isDemo: boolean("is_demo").notNull().default(false),
  createdAt: now(),
});

export const familyMembers = pgTable(
  "family_members",
  {
    familyId: uuid("family_id").notNull().references(() => families.id, { onDelete: "cascade" }),
    userId: uuid("user_id").notNull().references(() => users.id, { onDelete: "cascade" }),
    role: text().notNull(), // 'archivist' | 'member'
    joinedAt: now(),
  },
  t => [primaryKey({ columns: [t.familyId, t.userId] })],
);

export const records = pgTable(
  "records",
  {
    id: uuid().primaryKey().defaultRandom(),
    familyId: uuid("family_id").notNull().references(() => families.id, { onDelete: "cascade" }),
    uploadedBy: uuid("uploaded_by").references(() => users.id, { onDelete: "set null" }),
    blobKey: text("blob_key").notNull(),
    mimeType: text("mime_type"),
    sizeBytes: integer("size_bytes"),
    caption: text(),
    kind: text(), // 'photo' | 'document'
    createdAt: now(),
  },
  t => [index("records_family_idx").on(t.familyId)],
);

export const invites = pgTable("invites", {
  id: uuid().primaryKey().defaultRandom(),
  familyId: uuid("family_id").notNull().references(() => families.id, { onDelete: "cascade" }),
  invitedBy: uuid("invited_by").references(() => users.id, { onDelete: "set null" }),
  email: text(),
  name: text(),
  token: text().notNull().unique(),
  status: text().notNull().default("sent"), // 'sent' | 'accepted' | 'expired'
  eventSource: text("event_source"),
  createdAt: now(),
  acceptedAt: timestamp("accepted_at", { withTimezone: true }),
});

export const payments = pgTable("payments", {
  id: uuid().primaryKey().defaultRandom(),
  userId: uuid("user_id").references(() => users.id, { onDelete: "set null" }),
  stripeCheckoutSessionId: text("stripe_checkout_session_id").unique(),
  stripeCustomerId: text("stripe_customer_id"),
  stripePaymentIntentId: text("stripe_payment_intent_id"),
  amountCents: integer("amount_cents"),
  currency: text(),
  status: text().notNull(), // 'pending' | 'paid' | 'failed' | 'refunded' | 'reserved'
  priceId: text("price_id"),
  eventSource: text("event_source"),
  livemode: boolean(),
  signinUsedAt: timestamp("signin_used_at", { withTimezone: true }), // the one on-device sign-in after paying (§3.1)
  createdAt: now(),
  paidAt: timestamp("paid_at", { withTimezone: true }),
});

export const events = pgTable("events", {
  slug: text().primaryKey(),
  name: text(),
  venue: text(),
  startsAt: timestamp("starts_at", { withTimezone: true }),
  notes: text(),
});

export const magicLinks = pgTable("magic_links", {
  tokenHash: text("token_hash").primaryKey(),
  email: text().notNull(),
  redirectTo: text("redirect_to"),
  expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
  usedAt: timestamp("used_at", { withTimezone: true }),
});

// every email sent, with a dedupe key so a follow-up is never sent twice (§7)
export const emails = pgTable(
  "emails",
  {
    id: uuid().primaryKey().defaultRandom(),
    toEmail: text("to_email").notNull(),
    kind: text().notNull(), // 'magic-link' | 'invite' | 'followup' | 'nudge'
    dedupeKey: text("dedupe_key"),
    providerId: text("provider_id"),
    sentAt: now(),
  },
  t => [uniqueIndex("emails_dedupe_idx").on(t.dedupeKey)],
);

// admin toggles, e.g. the Payment Link fallback (§6)
export const settings = pgTable("settings", {
  key: text().primaryKey(),
  value: text().notNull(),
});
