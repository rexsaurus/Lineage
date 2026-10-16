# Lineage web: in-person event onboarding (v1)

A stranger at a genealogy meeting scans a QR code, becomes a Founding Archivist, names their family, and adds a first
photo, on their own phone, in under two minutes. Built from the event-onboarding spec (v1). This app lives in `web/`
and is separate from the static Lineage site (`site/`, `api/`), which the repo-root `.vercelignore` keeps out of this
app and vice versa: nothing here changes how lineage.rexstjohn.com is built or deployed.

**Status: local and test mode only.** Nothing is deployed, no accounts were created, no email is sent, no price is set.

**Also built: family subscriptions, regular updates and archivist referral earnings** (see "Subscriptions, updates and
referral earnings" below). A relative follows (free) or subscribes (paid) to a family's page from the archivist's link;
they get read access and email digests; the archivist earns a share of what referred subscribers pay, paid out through
Stripe Connect. All test mode, all decisions (price, share, hold, minimum) left to Rex.

## Run it

```bash
cd web
npm install
npx playwright install chromium webkit   # once, for the browser tests
npm run dev                               # http://localhost:3000
```

With no settings at all it runs fully offline:

| Concern | Default (local) | Production |
|---|---|---|
| Database | PGlite (embedded Postgres) in `.data/pglite`, migrated on first use | Postgres via `DATABASE_URL` (Neon / Vercel Postgres); `npm run db:migrate` |
| Payments | `PAYMENTS_DRIVER=fake`: a "Test checkout" page, no network, nothing charged | Stripe Checkout, **test keys** first |
| Price | `PRICE_TBD=true`: no price anywhere; "Reserve my spot", no payment | `PRICE_TBD=false` + `PRICE_DISPLAY` once Rex decides |
| Email | `MAIL_DRIVER=console`: each email written to `.data/outbox/*.json`, nothing sent | Resend |
| Files | `.data/blobs`, served only through signed, expiring URLs | Cloudflare R2 (private bucket) |

To try it as an admin, put `ADMIN_EMAILS=you@example.org` in `.env.local`, sign in at `/login`, and open the sign-in link
from the newest file in `.data/outbox/`.

## Tests

```bash
npm test                                         # Vitest: 38 unit tests, in-memory PGlite, no network
npm run build                                    # needed before the browser tests
npx playwright test                              # 10 tests: iPhone 13 (WebKit) + Pixel 7 (Chromium), prices set, fake Stripe + Connect
npx playwright test -c playwright.tbd.config.ts  # 2 tests: the default no-price reservation flow
npm run typecheck
```

The browser run sets test-only values in `playwright.config.ts` (a fake $10 subscription invoice, a 20% share, no
hold) purely to exercise the referral path; they are not defaults and not decisions.

The browser tests run the whole journey on a production build: scan with `?src=` → email → test checkout → name the
family → photo → family page (about 2 s automated), the follow-up email, inviting a cousin who joins on another phone
and uploads a PDF, an invite that can't be reused, a signed-out visitor and a signed-in stranger both kept out (page and
file), the admin's per-event counts and both CSV exports, upload limits, noindex, and the large-type checks (body ≥18px,
buttons ≥48px (designed at 56px), no sideways scrolling, every input labelled).

Not automated: Lighthouse scores, VoiceOver, real-phone timing, HEIC from a real iPhone camera, Stripe's hosted pages.
Those are in the manual script (spec §14) for Monday.

## Map

```
src/proxy.ts                 ?src=<slug> → lineage_src cookie (30 days)
src/env.ts                   every setting, validated with zod (below)
src/db/schema.ts, drizzle/   spec §5 tables + emails (send log, dedupe) + settings; 0001 seeds the §9 event slugs
src/lib/                     start (signup/checkout/welcome), payments (Stripe + fake, webhook handler), magic (links),
                             session, families, invites, files (type sniffing, 25 MB, EXIF/GPS stripping), storage
                             (local/R2, signed URLs), mail + emails (all wording), followup (first-record email + cron
                             nudge), kpi, qr, settings, auth, admin-auth
src/app/                     / · /start · /welcome · /login · /family/new · /family/[id] · /upload · /invite ·
                             /invite/[token] · /demo · /admin · /admin/qr · /admin/qr/[slug]/cards · /privacy · /terms
src/app/api/                 auth/magic-link · auth/callback · upload (+ sign, complete) · records/[id]/file · files ·
                             stripe/webhook · admin/kpi.csv · admin/kpi-by-event.csv · admin/qr/[slug] · cron/followups
scripts/                     migrate.ts · seed-demo.ts · append-kpi.ts
tests/unit, tests/e2e, tests/e2e-tbd
```

## Settings (src/env.ts)

| Variable | Required | Notes |
|---|---|---|
| `APP_URL` | prod | e.g. `https://app.lineage.rexstjohn.com`; links in emails, Stripe return URLs, QR codes. Cookies are `Secure` when https. |
| `SESSION_SECRET` | prod | 32+ random chars (`openssl rand -base64 48`); signs sessions and file URLs |
| `DATABASE_URL` | prod | Postgres. Unset → PGlite in `PGLITE_DIR` |
| `PRICE_TBD` | — | default `true`: no price, no payment, reservations only |
| `PRICE_DISPLAY` | when `PRICE_TBD=false` | the text after "Founding Archivist —"; never defaulted |
| `PAYMENTS_DRIVER` | — | `fake` (default) or `stripe` |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID_FOUNDING` | with stripe | `sk_live_…` is refused unless `ALLOW_LIVE_STRIPE=true` (checked at startup and again at runtime) |
| `STRIPE_PUBLISHABLE_KEY` | — | not needed by Checkout redirects; kept for later |
| `STRIPE_PAYMENT_LINK_URL` | — | the fallback the admin can switch on (§6) |
| `MAIL_DRIVER`, `RESEND_API_KEY`, `MAIL_FROM`, `MAIL_REPLY_TO` | with resend | `MAIL_FROM` must be on a domain verified in Resend |
| `STORAGE_DRIVER`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` | with r2 | a **private** bucket, separate from the public book-image bucket |
| `ADMIN_EMAILS` | prod | comma-separated; see /admin; excluded from every count |
| `KPI_EXPORT_TOKEN` | for append-kpi | 24+ chars |
| `CRON_SECRET` | prod | 16+ chars; Vercel Cron sends it |
| `SUB_PRICE_TBD` | — | default `true`: relatives can only **follow** free; no price shown, no payment |
| `SUB_PRICE_DISPLAY` | when `SUB_PRICE_TBD=false` | the text after "Subscribe —"; never defaulted |
| `STRIPE_PRICE_ID_FAMILY_SUB` | paid subs with Stripe | a recurring Price; the interval comes from Stripe |
| `REV_SHARE_PCT` | — | e.g. `20` or `12.5`. **No default**: unset = "earnings program not yet open"; ledger rows are kept at 0 |
| `REFUND_HOLD_DAYS` | — | days before an earning can be paid out. **No default**: unset = earnings stay pending |
| `MIN_PAYOUT_CENTS` | — | smallest payout, in the currency's smallest unit; unset = no minimum |
| `PAYOUT_CRON_ENABLED` | — | default `false`: payouts only by admin approval; `true` also pays everyone due on the 1st |
| `CONNECT_DRIVER` | — | `fake` (default) or `stripe` (Connect Express, test keys) |
| `FAKE_SUB_AMOUNT_CENTS`, `FAKE_SUB_CURRENCY` | — | fake driver only: what a fake subscription invoice charges; ignored with real Stripe |

`.env.example` lists them all. Empty values count as unset.

## Subscriptions, updates and referral earnings

**Routes.** `/f/[familyId]?ref=<code>` (follow or subscribe; shows only the family name and who shared it) ·
`/f/[familyId]/welcome` (Stripe success) · `/family/[id]/updates` (weekly / monthly / never; stop following) · `/u/[token]`
and `POST /api/unsubscribe/[token]` (signed one-click unsubscribe, RFC 8058 header) · `/earnings` (archivist: link + QR per
family, referred / active / paying counts, pending / available / paid, "Get paid", payout history) · `/earnings/connected`
(Connect return) · `/admin/earnings` (paid subscribers, followers, MRR, referrals by archivist, ready-to-pay with
"Approve payout", ledger, payouts) · `/api/admin/earnings.csv` · `/api/cron/digests` (daily) · `/api/cron/payouts`
(monthly, only with `PAYOUT_CRON_ENABLED`) · `/terms/referrals`, `/terms/subscribers` (DRAFT) · `/dev/fake-connect` (fake only).

**Tables.** `subscriptions` (kind follow|paid, status, Stripe ids, amount/interval from Stripe, referrer + code, digest
frequency), `activity` (every record/caption/member/family change, with a private flag), `earnings` (the ledger),
`payouts`; `users` gains `ref_code` and Connect fields; `records` gains `is_private`.

**Access.** Members (archivist, invited relatives) edit; followers and subscribers (status active, or past_due while
Stripe retries) only read, and never see records marked "Only for family members". Cancelled → no access.

**Attribution.** The archivist's code (8 characters, made on first use) rides on their link; the proxy keeps it in an
HttpOnly `lineage_ref` cookie for 60 days, first touch wins. It is credited only if its owner is the archivist of that
family and is not the subscriber (self-referral blocked). It is stored on the subscription row and in the Stripe
subscription metadata.

**Ledger rules** (`src/lib/ledger.ts`). One row per paid invoice (idempotent on the invoice id): net = amount paid − tax;
earning = floor(net × share) — rounding always down. Pending until `REFUND_HOLD_DAYS` after the payment date, then
available. Refund before payout: the earning is recomputed on what's left (full refund → reversed). Refund or chargeback
after payout: a negative clawback row comes off the next payout. Payouts claim every available row atomically, transfer
through Connect with an idempotency key (the payout id), and release the rows if the transfer fails.

**Stripe events handled** (`src/lib/webhooks.ts`): `checkout.session.completed` (payment and subscription modes),
`customer.subscription.created|updated|deleted`, `invoice.paid`, `invoice.payment_failed`, `charge.refunded`,
`charge.dispute.created`, `account.updated`. All idempotent; invoice fields are read for both older and newer Stripe API
shapes.

**Digests** (`src/lib/digest.ts`). Daily cron; each subscription gets at most one email per ISO week or month
(`emails.dedupe_key = digest:<subscription>:<period>`), only when something public changed, never their own changes,
nothing in the period they joined (the first digest covers it the next period). Every digest carries a signed unsubscribe
link and `List-Unsubscribe` headers.

### Stripe Connect setup (test mode) — for Rex; nothing here has been done
1. Stripe Dashboard (test mode) → **Connect** → get started → platform profile: Lineage is a platform paying its users
   (archivists) for referrals; choose **Express** accounts.
2. Branding (name, icon, colour) for the onboarding pages; set the **redirect** domain to the app's `APP_URL`.
3. Make sure the platform balance can fund transfers (in test mode, use the test card `4000 0000 0000 0077` to add
   available balance).
4. Add `account.updated` to the webhook endpoint, and enable "Listen to events on Connected accounts".
5. `CONNECT_DRIVER=stripe`. Test: sign in as an archivist → /earnings → Get paid → Stripe's test onboarding → back on
   /earnings it shows "Payouts are set up" → as admin, approve a payout in /admin/earnings.
6. For paid subscriptions: create a recurring Price → `STRIPE_PRICE_ID_FAMILY_SUB`; `SUB_PRICE_TBD=false`,
   `SUB_PRICE_DISPLAY`; add the subscription and invoice events listed above to the webhook endpoint.
7. Live mode only after Rex decides the numbers and the legal entity; Stripe may require the platform's own tax and
   identity details, and will collect each archivist's.

### Known limits (subscriptions)
- Cancelling a paid subscription is manual (reply to an update email); the Stripe Customer Portal is a later step.
- In paid mode, an invited family member who wants email updates is offered the paid subscription; whether members get
  updates free is one of Rex's decisions (below).
- A first-time account can be signed in on the device right after paying (an existing account never is; it gets the
  emailed link). Someone paying with an email address that has never been used would hold that new account's session.
- MRR is reported per currency, from the amounts Stripe reports on each subscription.
- Earnings are per currency; one payout per archivist per currency.

## Dependencies (what and why)

Runtime: `next`, `react`, `react-dom` (the app); `drizzle-orm` + `pg` (Postgres) and `@electric-sql/pglite` (embedded
Postgres for local runs and tests, so nothing external is needed); `zod` (settings validation); `stripe` (Checkout,
webhook signature verification); `qrcode` (the §9 QR codes); `@aws-sdk/client-s3` + `@aws-sdk/s3-request-presigner`
(private R2 storage and signed URLs — the spec allows Blob or S3/R2; R2 matches the bucket Rex already uses).
Dev: `typescript` (5.x: Next 16 type-checks with it), `tailwindcss` + `@tailwindcss/postcss` + `postcss`, `drizzle-kit`
(migrations), `vitest`, `@playwright/test`, `tsx` (scripts), and `@types/*`.
Not added: Auth.js (magic links are ~60 lines with signed tokens), the Resend SDK (one `fetch`), an image library (photos
are resized and re-encoded in the browser; JPEG/PNG metadata is stripped on the server without decoding).

## Known limits (v1)

- **Uploads on Vercel:** a function accepts about 4.5 MB. Photos are resized in the browser to ≤2400px JPEG first, so
  they fit. Larger files (big PDFs) go straight to R2 with a signed URL (`/api/upload/sign` → PUT → `/api/upload/complete`),
  so 25 MB works with R2; with local storage they go through the server.
- **HEIC:** iPhones usually hand Safari a JPEG; if a HEIC arrives and the browser can't decode it, it is stored as
  received (HEIC metadata isn't stripped server-side). A server-side stripper or converter would need an image library.
- **Orientation:** the server strips the whole EXIF block from JPEGs; photos resized in the browser are already upright,
  but a raw JPEG that bypassed resizing could display rotated.
- **Cron:** `vercel.json` runs the no-upload nudge every 15 minutes, which needs a Vercel Pro plan; on Hobby, change it
  to daily (`0 17 * * *`).
- Rate limiting on `/api/auth/magic-link` is per server instance (best effort).
- Lighthouse ≥95 and VoiceOver are to be checked by hand.

## Deploy checklist (spec §13) — for Rex; nothing here has been done

1. **Domain.** `lineage.rexstjohn.com` already serves the Lineage docs and live demo. Use a new name for this app, e.g.
   `app.lineage.rexstjohn.com` or `join.rexstjohn.com`, and set `APP_URL` to it.
2. **Vercel project:** new project from `rexsaurus/Lineage`, **Root Directory `web`**, framework Next.js. (The existing
   `lineage` project, rooted at the repo, is untouched.)
3. **Postgres:** Vercel Marketplace → Neon (or Vercel Postgres) → connect; `DATABASE_URL` appears. Run
   `DATABASE_URL=… npm run db:migrate` once (and after each new migration).
4. **R2:** create a private bucket (e.g. `lineage-family-records`) and an API token limited to it; set the four `R2_*`
   variables and `STORAGE_DRIVER=r2`. Add a CORS rule allowing `PUT` from `APP_URL` (for large direct uploads).
5. **Resend:** add and verify the sending domain (SPF/DKIM records go into DreamHost DNS); set `RESEND_API_KEY`,
   `MAIL_FROM`, `MAIL_REPLY_TO`, `MAIL_DRIVER=resend`.
6. **Stripe (test mode):** create Product "Lineage Founding Archivist" with one one-time Price → `STRIPE_PRICE_ID_FOUNDING`;
   `sk_test_…` → `STRIPE_SECRET_KEY`; add webhook endpoint `https://<app>/api/stripe/webhook` for
   `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`,
   `charge.refunded` → its signing secret → `STRIPE_WEBHOOK_SECRET`; `PAYMENTS_DRIVER=stripe`.
   Local webhook testing: `stripe listen --forward-to localhost:3000/api/stripe/webhook`.
7. `SESSION_SECRET`, `ADMIN_EMAILS`, `KPI_EXPORT_TOKEN`, `CRON_SECRET`, `APP_URL` in Production (and Preview).
8. **DNS:** add the domain in Vercel; add the CNAME it shows (`<name> → cname.vercel-dns.com`) in DreamHost (Manage
   Websites → rexstjohn.com → DNS → Add Record); wait for TLS.
9. Deploy, then on a phone over cellular: open `/admin/qr`, check the slugs, and run the manual script (spec §14).
10. **Live mode only after** Rex confirms the price and legal entity: live price + keys, `ALLOW_LIVE_STRIPE=true`,
    `PRICE_TBD=false`, `PRICE_DISPLAY`; buy one seat with Rex's own card, refund it, confirm `/admin` shows it refunded.

KPI log: `KPI_EXPORT_TOKEN=… npm run kpi:append -- ../../second-brain-fundraising/kpi-log.csv --url https://<app>/api/admin/kpi.csv`
Demo phone: `npm run seed:demo -- <folder of images Rex picks> --name "…"` (against the production `DATABASE_URL` and R2).

## Open questions for Rex (spec §16) — the app ships with safe defaults until each is answered

- [ ] **Price** of the Founding Archivist seat, what it includes, refund promise. Until then `PRICE_TBD=true`.
- [ ] **Legal entity for Stripe** (company or sole proprietor, legal name, EIN/SSN, bank account, statement descriptor). Live mode is blocked until set.
- [ ] **Repo:** keep this in `rexsaurus/Lineage` under `web/` (as built), or move it to a separate `lineage-web` repo?
- [ ] **"Indexed"** = a non-demo family with ≥1 archivist and ≥1 uploaded record (as built). Confirm.
- [ ] **Sender address/domain** for sign-in and follow-up emails.
- [ ] **What a Founding Archivist gets next** (pre-scan, Familypedia draft, book?), so the landing copy promises only what's real. The family page currently says only "Coming next: Lineage reads your records and starts your family's history."
- [ ] **Demo content:** which files from the St. John book may be shown on `/demo` (placeholders labelled "Demo content" until then).
- [ ] **Storage limits** per family and the data-retention/deletion promise for `/privacy` (currently: delete on request).
- [ ] **Event slugs** (§9): confirm names, venues and dates in `/admin/qr`; the seven slugs are pre-created.
- [ ] **App domain** (deploy step 1) and whether the cron runs every 15 minutes (Pro) or daily (Hobby).

Subscriptions and referrals (each ships "off" or "not yet open" until decided):
- [ ] **Subscription price and interval** (monthly / yearly?), and currency. Until then `SUB_PRICE_TBD=true`: free follow only.
- [ ] **Paid to view, or paid only for updates?** As built: a paid subscription gives read access and updates; while the price isn't set, following is free and gives both.
- [ ] **Do invited family members get updates free?** As built they edit for free; in paid mode, updates are offered as the paid subscription.
- [ ] **Revenue share %** (`REV_SHARE_PCT`) and whether it's on the amount after tax only (as built) or also after Stripe's fees.
- [ ] **Hold period** before an earning can be paid (`REFUND_HOLD_DAYS`); until set, earnings stay pending.
- [ ] **Minimum payout** (`MIN_PAYOUT_CENTS`) and payout schedule (admin approval only, as built, or the monthly cron too).
- [ ] **Does the share last for the subscriber's lifetime** (as built and as the draft terms say) or for a limited time?
- [ ] **Tax and legal entity** for the platform (Stripe Connect requires it), whether Lineage must issue tax forms to archivists, and a lawyer's review of the DRAFT referral terms, subscriber terms and privacy page.
