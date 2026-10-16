import { boolean, integer, pgTable, primaryKey, text, timestamp, uuid, uniqueIndex, index } from "drizzle-orm/pg-core";

// Spec §5. Emails are stored lower-cased in text columns with unique indexes (equivalent to citext for our use, and it
// works the same on Postgres and on PGlite without an extension).
const now = (name: string) => timestamp(name, { withTimezone: true }).defaultNow().notNull();

export const users = pgTable("users", {
  id: uuid().primaryKey().defaultRandom(),
  email: text().notNull().unique(),
  name: text(),
  role: text().notNull().default("archivist"), // 'archivist' | 'member' | 'admin'
  eventSource: text("event_source"), // slug from ?src at first touch
  createdAt: now("created_at"),
  lastLoginAt: timestamp("last_login_at", { withTimezone: true }),
  refCode: text("ref_code").unique(), // an archivist's referral code, made on first use
  stripeConnectAccountId: text("stripe_connect_account_id"),
  connectPayoutsEnabled: boolean("connect_payouts_enabled").notNull().default(false),
});

export const families = pgTable("families", {
  id: uuid().primaryKey().defaultRandom(),
  name: text().notNull(),
  createdBy: uuid("created_by").references(() => users.id, { onDelete: "set null" }),
  eventSource: text("event_source"),
  isDemo: boolean("is_demo").notNull().default(false),
  createdAt: now("created_at"),
});

export const familyMembers = pgTable(
  "family_members",
  {
    familyId: uuid("family_id").notNull().references(() => families.id, { onDelete: "cascade" }),
    userId: uuid("user_id").notNull().references(() => users.id, { onDelete: "cascade" }),
    role: text().notNull(), // 'archivist' | 'member'
    joinedAt: now("joined_at"),
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
    isPrivate: boolean("is_private").notNull().default(false), // members only: never shown to subscribers or in digests
    createdAt: now("created_at"),
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
  createdAt: now("created_at"),
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
  createdAt: now("created_at"),
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
    sentAt: now("sent_at"),
  },
  t => [uniqueIndex("emails_dedupe_idx").on(t.dedupeKey)],
);

// ---- family subscriptions, updates and referral earnings

// A relative who follows (free) or subscribes (paid) to a family's Lineage: read access + regular updates.
export const subscriptions = pgTable(
  "subscriptions",
  {
    id: uuid().primaryKey().defaultRandom(),
    familyId: uuid("family_id").notNull().references(() => families.id, { onDelete: "cascade" }),
    userId: uuid("user_id").notNull().references(() => users.id, { onDelete: "cascade" }),
    kind: text().notNull(), // 'follow' (free) | 'paid'
    status: text().notNull(), // 'active' | 'incomplete' | 'past_due' | 'canceled'
    stripeSubscriptionId: text("stripe_subscription_id").unique(),
    stripeCustomerId: text("stripe_customer_id"),
    stripeCheckoutSessionId: text("stripe_checkout_session_id").unique(),
    amountCents: integer("amount_cents"), // per interval, from Stripe (never set by the app)
    currency: text(),
    interval: text(), // 'month' | 'year' | 'week' | 'day'
    referrerUserId: uuid("referrer_user_id").references(() => users.id, { onDelete: "set null" }),
    refCode: text("ref_code"),
    digestFreq: text("digest_freq").notNull().default("weekly"), // 'weekly' | 'monthly' | 'off'
    lastDigestAt: timestamp("last_digest_at", { withTimezone: true }),
    currentPeriodEnd: timestamp("current_period_end", { withTimezone: true }),
    createdAt: now("created_at"),
    canceledAt: timestamp("canceled_at", { withTimezone: true }),
  },
  t => [uniqueIndex("subscriptions_family_user_idx").on(t.familyId, t.userId)],
);

// Every change to a family, written as it happens; the digests are built from it.
export const activity = pgTable(
  "activity",
  {
    id: uuid().primaryKey().defaultRandom(),
    familyId: uuid("family_id").notNull().references(() => families.id, { onDelete: "cascade" }),
    kind: text().notNull(), // 'record_added' | 'caption_changed' | 'member_joined' | 'family_renamed' | 'post_published'
    actorUserId: uuid("actor_user_id").references(() => users.id, { onDelete: "set null" }),
    recordId: uuid("record_id").references(() => records.id, { onDelete: "cascade" }),
    summary: text().notNull(),
    isPrivate: boolean("is_private").notNull().default(false),
    createdAt: now("created_at"),
  },
  t => [index("activity_family_time_idx").on(t.familyId, t.createdAt)],
);

// The referral ledger: one row per paid invoice of a referred subscription (plus clawback rows after a payout).
export const earnings = pgTable(
  "earnings",
  {
    id: uuid().primaryKey().defaultRandom(),
    referrerUserId: uuid("referrer_user_id").notNull().references(() => users.id, { onDelete: "cascade" }),
    subscriptionId: uuid("subscription_id").references(() => subscriptions.id, { onDelete: "set null" }),
    stripeInvoiceId: text("stripe_invoice_id"),
    stripeChargeId: text("stripe_charge_id"),
    stripePaymentIntentId: text("stripe_payment_intent_id"),
    kind: text().notNull().default("share"), // 'share' | 'clawback'
    invoiceNetCents: integer("invoice_net_cents").notNull(),
    shareBps: integer("share_bps"), // revenue share in basis points at the time (null: program not open)
    amountCents: integer("amount_cents").notNull(),
    currency: text().notNull(),
    status: text().notNull(), // 'pending' | 'available' | 'paid' | 'reversed'
    paidAt: timestamp("paid_at", { withTimezone: true }), // when the subscriber's invoice was paid; the hold counts from here
    availableAt: timestamp("available_at", { withTimezone: true }),
    payoutId: uuid("payout_id"),
    createdAt: now("created_at"),
    reversedAt: timestamp("reversed_at", { withTimezone: true }),
    note: text(),
  },
  t => [uniqueIndex("earnings_invoice_kind_idx").on(t.stripeInvoiceId, t.kind), index("earnings_referrer_idx").on(t.referrerUserId)],
);

export const payouts = pgTable("payouts", {
  id: uuid().primaryKey().defaultRandom(),
  userId: uuid("user_id").notNull().references(() => users.id, { onDelete: "cascade" }),
  amountCents: integer("amount_cents").notNull(),
  currency: text().notNull(),
  status: text().notNull(), // 'pending' | 'paid' | 'failed'
  stripeTransferId: text("stripe_transfer_id"),
  approvedBy: text("approved_by"),
  failure: text(),
  createdAt: now("created_at"),
  paidAt: timestamp("paid_at", { withTimezone: true }),
});

// admin toggles, e.g. the Payment Link fallback (§6)
export const settings = pgTable("settings", {
  key: text().primaryKey(),
  value: text().notNull(),
});
