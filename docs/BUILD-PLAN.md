# Lineage platform: staged build plan (for Cursor)

**Read this first, Cursor.** This file is a complete handoff. You do not have the conversation that produced it; everything
you need is here or in the linked docs. Work **one stage at a time**. A stage is done only when every item in its
**Quality gate** passes and the gate's report is committed. Do not start the next stage early.

Companion docs: [BLOCK-DIAGRAM.md](BLOCK-DIAGRAM.md) (the picture), [PLATFORM-ARCHITECTURE.md](PLATFORM-ARCHITECTURE.md)
(why), [VERCEL-MIGRATION.md](VERCEL-MIGRATION.md) (which Vercel products, with sources).

---

## 0. What we are building

A hosted platform where many families each run a **lineage**: a researched family history (people, records, a
Familypedia, a timeline, a book) that keeps growing. An **Archivist** (one family member) runs it from a dashboard. A
**core research agent** works continuously in the cloud: it reads replies from archives, finds new records, drafts
requests and thank-yous, writes articles and chapters, and publishes updates. A **Skill Gallery** supplies everything the
agent can do (Chapter writer, Book writer, Clip generator, Newsletter writer, and more). Families buy **Lineage Credits**
that runs consume. Subscribers get an **email digest** of what changed.

The first tenant is _The Book of Daniel_ (live at daniel.rexstjohn.com and lineage.rexstjohn.com), today run by hand from
a laptop. The platform must reproduce it, then host more families.

### Objectives (non-negotiable)
1. **Always available in the cloud.** No laptop. Nothing runs continuously; everything is triggered or scheduled.
2. **A repeatable, scheduled graph** that triggers when data is added and rebuilds only what changed.
3. **Outbound email digest** to subscribers.
4. **Many lineages** hosted in one Vercel deployment (managed by us for now).
5. **Data stored twice:** Vercel (Blob + Neon) and the family's Google Drive.
6. **A hosted core research agent** that spins up sub-agents (skills).
7. **A lineage display zone** per family (public site + signed-in family archive).
8. **An Archivist dashboard** to manage agents, skills, approvals, credits, models and sites.
9. **Lineage Credits** to pay for and schedule runs.
10. **Cheap models by default, switchable instantly** without a redeploy.

### Rules the product enforces (also rules for you)
- **Nothing outward without approval.** Sending email, ordering, paying, submitting forms and publishing require an
  approval event for that exact item. Payments and logins are never automated (they become human tasks).
- **Every sentence in an article or chapter has a citation** to a stored source with a hash. Uncited text never publishes.
- **Evidence tiers:** record · told-by-subject · told-by-family · context. **Contradictions are kept**, both sides cited.
- **Never state a date more precisely than its source.** Never invent a name, date or regiment.
- **Paragraphs ≤ 130 words** (per-lineage setting). **Every site update writes a changelog entry.**
- **Privacy:** living people private by default; per-lineage private people/topics; in-copyright material paraphrased,
  quotes under 15 words; private research copies never published.
- **Open sources only for research:** respect robots.txt, rate-limit (≥ 2 s per domain), no logins, no paywalls, **never
  bypass a bot check** (Cloudflare/WAF). Blocked sites become human tasks.
- **Negative results are findings:** every "searched, not found" is recorded with where.

---

## 1. Stack (decided)

| Layer | Choice |
|---|---|
| App | One **Next.js** project on **Vercel** (Fluid compute), multi-tenant by domain/subdomain; **Python on Vercel** for ported engine code |
| Agent | **eve** (Vercel's open-source agent framework) in a separate repo `lineage-agent`; durable loop on **Vercel Workflows** / **WorkflowAgent** (`@ai-sdk/workflow`), **AI SDK 7** |
| Orchestration | **Vercel Workflows** (steps, `sleep`, hooks, `needsApproval`) + **one hourly Vercel Cron** |
| Models | **Vercel AI Gateway** only. Code names a **role**, never a model. Role→model table in **Edge Config** |
| Default models | `bulk`: DeepSeek V4.1 Flash · `write`: Claude Sonnet · `judge`: Claude Haiku (second provider) · `vision`: a cheap vision model |
| Search | **DeepSeek Search/Fetch API** (`POST https://api.deepseek.com/v1/tools/search`, `/v1/tools/fetch`) |
| Heavy jobs | **Vercel Sandbox** (Typst builds, OCR, Poppler) with a snapshot; only when needed |
| Database | **Neon Postgres** (Vercel Marketplace), row-level security by `tenant_id` |
| Files | **Vercel Blob** (primary, prefix per tenant), mirrored to **Google Drive** |
| Google (Gmail, Drive) | **Vercel Connect** managed Google connector (`getToken()` from `@vercel/connect`) |
| Content | **GitHub**, one content repo per lineage; changes arrive as PRs |
| Email out | Archive mail from the archivist's Gmail (Connect); digests via **Resend** |
| Payments | **Stripe** (credit packs; Connect for archivist referral earnings later) |
| Tests | Vitest (TS), Pytest (Python), Playwright (UI) |

**Verify every Vercel/eve API name against current docs before using it**; several are new (2026). If an API differs from
this plan, follow the docs and note the difference in the stage report.

---

## 2. Repositories

```
lineage-agent/                    (NEW) the core agent + Skill Gallery content. Open source candidate.
  instructions.md                 core agent brief: goals, rules above, approval policy
  agent.ts                        role-based model routing (reads Edge Config), budgets
  tools/                          one file per tool (see Stage 5)
  skills/                         THE SKILL GALLERY (see §3)
  evals/                          shared harness + frozen set (see Stage 3)
  package.json, vitest.config.ts

lineage/                          (EXISTING, github.com/rexsaurus/Lineage) the platform app
  web/                            Next.js app: display zones, Archivist dashboard, APIs, workflows, cron
                                  (exists on branch feature/event-onboarding: admin earnings, referrals, Stripe)
  app/                            existing Python engine (server.py /api/engine/*): port to Vercel Python (Stage 11)
  plugins/lineage/                existing scripts and Markdown skills: source material for skills and build steps
  db/                             (NEW) Neon migrations
  docs/                           these plans

lineage-book-of-daniel/           (NEW, Stage 12) content-only repo for tenant #1
```

---

## 3. The Skill Gallery

Every capability the agent has is a **skill**: a versioned folder with a manifest, instructions, optional tools and
templates, and **its own evals**. The core agent never improvises a writer; it calls `run_skill(skill_id, input)`.
Archivists enable, pin and configure skills per lineage from the dashboard. A skill version cannot be published to the
gallery unless its evals pass.

### 3.1 Skill folder

```
skills/<skill-id>/
  skill.json          manifest (below)
  instructions.md     what the skill does, step by step, with the rules that apply
  templates/          optional output templates (Markdown, Typst, email)
  tools/              optional skill-specific tools (TS)
  evals/
    cases/*.json      golden inputs + expected outputs or rubric
    rubric.md         how a judge scores free text (1–5 per criterion)
    thresholds.json   pass marks (see each skill)
  CHANGELOG.md
```

### 3.2 `skill.json` (comments are explanation only; the real file is plain JSON)

```jsonc
{
  "id": "chapter-writer",
  "name": "Chapter writer",
  "version": "0.1.0",
  "category": "writer",                       // writer | research | media | ingest | ops | quality
  "description": "Writes a book chapter from a person's dossier, with a citation on every paragraph.",
  "input_schema": "./schemas/input.json",
  "output_schema": "./schemas/output.json",
  "model_role": "write",                      // bulk | write | judge | vision
  "tools": ["read_dossier", "read_records", "propose_pr"],
  "needs_approval": true,                     // output goes to the approval inbox
  "privacy": "private-ok",                    // public-only | private-ok (routes via US-only + ZDR)
  "credit_estimate": { "per_run": 60 },
  "evals": { "suite": "./evals", "min_pass": "./evals/thresholds.json" },
  "depends_on": ["fact-checker"]              // run on its output before approval
}
```

### 3.3 Gallery registry (Neon)

`skills(id, name, category, description)` · `skill_versions(skill_id, version, manifest jsonb, eval_report jsonb,
published_at, status: draft|published|retired)` · `tenant_skills(tenant_id, skill_id, pinned_version, enabled, config
jsonb, schedule, credit_cap_per_run)`.

### 3.4 Launch skills

| Skill | Category | Does | Key eval (threshold) |
|---|---|---|---|
| `reply-reader` | ingest | Reads an archive reply + attachments; lists asks (fees, forms, questions); writes a record note | asks found: recall ≥ 0.95 on cases |
| `page-reader` | ingest | Reads scans/handwriting (vision); transcribes; crops | character accuracy ≥ 98% on golden scans |
| `record-matcher` | research | Accepts/rejects a record for a person using the lineage's match criteria; lists criteria met | precision ≥ 0.95, recall ≥ 0.90 |
| `open-source-researcher` | research | Searches open archives (DeepSeek Search/Fetch + allowlisted sites); writes findings **and negatives** | no robots/bot-check violations (100%); negatives recorded (100%) |
| `fact-checker` | quality | For each claim, checks the cited evidence span supports it; flags weak or contradicted claims | agreement with gold labels ≥ 0.90 |
| `request-writer` | writer | Short, specific request to an archive with a fee offer, from the institution's verified address | rubric ≥ 4/5; no invented facts (100%) |
| `thankyou-writer` | writer | Specific thank-you naming what arrived | rubric ≥ 4/5 |
| `followup-writer` | writer | One polite nudge at +21 days | rubric ≥ 4/5 |
| `familypedia-article-writer` | writer | Writes/updates a person, place, ship or event article; footnote on every sentence | citation coverage 100%; ≤130-word paragraphs 100%; contradictions kept 100%; rubric ≥ 4/5 |
| `timeline-builder` | writer | Adds timeline events with `date_basis`, precision, conflicts | date-precision violations 0 |
| `chapter-writer` | writer | Writes or revises a chapter from the dossier, quotes exact, bridges marked for approval | citation coverage 100%; quote fidelity 100%; rubric ≥ 4/5 |
| `book-writer` | writer | Assembles chapters into an edition: order, front matter, records list, changelog, version | build compiles; every chapter's records present; changelog entry present |
| `newsletter-writer` | writer | Writes the subscriber digest from the week's updates (what's new, per person) | no uncited claims; no private material (100%); rubric ≥ 4/5 |
| `clip-generator` | media | Makes short shareable clips from interviews and photos: quote cards and audio/video snippets with captions and exact timestamps | quotes verbatim (100%); timestamps within ±0.5 s; no private people (100%) |
| `changelog-writer` | ops | Writes the changelog/updates entry for a publish | every change listed (100%) |
| `privacy-checker` | quality | Scans any output for living people, private units/topics, over-long copyrighted quotes | recall on seeded violations 100% |

Later: `photo-restorer`, `map-maker`, `interview-transcriber`, `foreword-writer`, `social-post-writer`.

Source material for these skills already exists: `lineage/plugins/lineage/skills/*` (records-archives, chapter-dossier,
chapter-generator, family-history-chapters, book-generator, published-sources, timeline-organizer, foreword-generator,
memoir-style-guide, photo-processor, interview-transcriber). Port, don't rewrite from scratch.

---

## 4. Shared quality machinery (used by every gate)

- **Frozen set** (`lineage-agent/evals/frozen-set/`): golden cases built from the demo lineage
  (`lineage/examples/demo-lineage`) and consented public-domain _Book of Daniel_ records (Hartford Courant clippings
  1914–1921, the 1851 _Hannibal_ crew list, Civil War rosters, the Falmouth Enterprise 1928–29 pages). Never put private
  material (living people, interview transcripts) in the frozen set.
- **Deterministic checks** (`lineage-agent/evals/checks/`): citation coverage, paragraph length, id uniqueness, schema
  validity, date precision, privacy scan, changelog presence, build compiles.
- **Judge scoring:** rubric scores from the `judge` role (a different provider from the writer). Report mean and min.
- **Cost and latency:** every eval run records credits and seconds per case; a gate fails if a skill exceeds its
  `credit_estimate` by more than 50% on average.
- **Gate report:** each stage commits `docs/gates/stage-N.md` with: what was built, test and eval results (numbers),
  anything that differs from this plan, open issues. **Rex reviews the report before the next stage starts.**

---

## 5. Stages

Each stage: **Goal · Build · Quality gate**. Estimates assume one developer with Cursor.

### Stage 1: Foundations (2–3 days)
**Goal:** accounts, repos and plumbing exist; nothing smart yet.
**Build**
- Create repo `lineage-agent` (eve scaffold) and branch `platform` in `lineage`.
- Vercel project for `lineage/web` (Pro team). Neon via Marketplace. Edge Config store. AI Gateway key with a small team
  budget, **US-only + Zero Data Retention on**. Vercel Connect: Google connector installed for the first archivist.
  `DEEPSEEK_API_KEY` in env. Resend and Stripe test keys in env.
- CI: lint, typecheck, unit tests on every PR in both repos.
**Quality gate**
- [ ] Smoke test function: reads one Gmail message via Connect, calls `bulk` via AI Gateway, runs one DeepSeek search,
      writes one Blob, reads one Neon row. All five green in CI (with test credentials).
- [ ] No secret in any repo (secret scanner in CI passes).

### Stage 2: Data model and storage (3–4 days)
**Goal:** the database, file storage and Drive mirror, with the first tenant's data imported.
**Build**
- Migrations in `lineage/db/`: `tenants`, `members`, `institutions`, `requests`, `messages`, `attachments` (sha256
  unique), `records`, `assets` + `asset_edges` (the dependency graph), `updates`, `subscriptions`, `tasks`, `approvals`,
  `runs`, `skills`/`skill_versions`/`tenant_skills`, `credit_accounts`, `credit_ledger`, `schedules`, `price_book`.
  Row-level security on `tenant_id` everywhere.
- Blob layout: `/<tenant>/sources/`, `/records/`, `/builds/`. **Drive mirror** step: copy new/changed files to the
  tenant's Drive folder via Connect; store Drive ids; nightly verify (hash both sides).
- Importer for _The Book of Daniel_: `REQUESTS-SENT.md`, `research_catalog.csv` (37 institutions), follow-up dates,
  archive files (from the existing R2 bucket and local archive folder), wiki, timeline, chapter list.
**Quality gate**
- [ ] Import parity: institution, request, record, wiki-article and timeline-event counts equal the source files.
- [ ] Mirror test: 20 files written → 20 in Blob and 20 in Drive, hashes equal; one deleted in Drive → nightly verify
      flags it.
- [ ] RLS test: a query as tenant A cannot read tenant B (automated).

### Stage 3: Model routing and the eval harness (3–4 days)
**Goal:** switch models instantly; measure quality before any skill exists.
**Build**
- `agent.ts` routing: role → ordered model list from Edge Config (global, overridable per tenant); fallback on error or
  rate limit; usage and cost captured per call into `runs`.
- Eval harness CLI: `lineage-agent eval <skill|all> --model-role-override bulk=<model>`; outputs a JSON report.
- Frozen set v1 (§4) and deterministic checks.
**Quality gate**
- [ ] Changing `bulk` in Edge Config changes the model used by the next call within 60 s, no redeploy (automated test).
- [ ] Fallback test: first model forced to fail → second model answers; logged.
- [ ] Harness runs end to end on a dummy skill; report committed with baseline numbers.

### Stage 4: Skill Gallery framework (3–4 days)
**Goal:** skills can be authored, evaluated, published, enabled per tenant and run.
**Build**
- `skill.json` schema + validator; `run_skill(skill_id, input)` tool that loads the tenant's pinned version, routes by
  `model_role`, enforces `tools`, `privacy`, `needs_approval`, records cost.
- Publish command: runs the skill's evals; refuses to publish below thresholds; writes `skill_versions.eval_report`.
- Dashboard page **Skills**: browse gallery, see eval scores and cost per run, enable/pin/configure per lineage.
**Quality gate**
- [ ] A sample skill below threshold cannot be published (test).
- [ ] Pinning v0.1.0 for tenant A and v0.2.0 for tenant B runs the right version for each (test).
- [ ] A skill that requests a tool not in its manifest is refused (test).

### Stage 5: Core agent and ingest skills, in shadow mode (1–2 weeks)
**Goal:** the agent ingests real archive replies as well as the hand-run process does, without sending or publishing.
**Build**
- Core agent (`instructions.md`) with tools: `gmail_search`, `gmail_get_message` (attachments streamed to Blob, sha256),
  `blob_put/get`, `ledger_upsert`, `deepseek_search`, `deepseek_fetch` (allowlist; never on bot-checked sites),
  `sandbox_run`, `propose_pr`, `human_task`, `run_skill`.
- Skills: `reply-reader`, `page-reader`, `record-matcher`, `fact-checker`, `open-source-researcher`, `privacy-checker`.
- Shadow mode on tenant #1 for 7 days: the agent writes PRs to a shadow branch only.
**Quality gate**
- [ ] Each skill meets its threshold in §3.4 on the frozen set.
- [ ] Shadow parity: for every real reply in the 7 days, the agent's record note matches the hand-made one on people,
      dates, asks and attachments (≥ 95% of fields); every miss explained in the report.
- [ ] Zero outward actions taken (audit log check).

### Stage 6: Workflows, triggers, approvals and timers (1 week)
**Goal:** the loop runs by itself and waits for the archivist where it must.
**Build**
- Workflows: `ingest.reply`, `ingest.upload`, `research.lead`, `request.new`, `request.followup`, `request.thankyou`,
  `bounce.recover`, `build.publish`, `ops.daily`.
- Triggers: Gmail via Connect events (beta) with the **hourly cron** as fallback; Blob upload; dashboard "run".
  The hourly cron selects tenants with due work only.
- Approvals: every outward tool `needsApproval: true`; approval inbox in the dashboard (approve/decline/edit). Merging a
  content PR = approval for content.
- Timers: `sleep('21d')` → `followup-writer` draft → approval → send → `sleep('21d')` → mark **dormant**.
- Human tasks: one-line unblock action + full parameters; a call-sheet view.
**Quality gate**
- [ ] E2E: a test reply → record PR + thank-you draft appear in the inbox within 5 minutes.
- [ ] E2E: approving the draft sends it from the archivist's Gmail in the original thread and starts the 21-day timer.
- [ ] Timer test with time travel: no reply → nudge drafted at day 21 → dormant at day 42.
- [ ] Idempotency: the same email delivered twice produces one record and one draft.

### Stage 7: Lineage Credits (4–5 days)
**Goal:** runs are paid for and capped.
**Build**
- Stripe Checkout credit packs → webhook → `credit_ledger` purchase.
- Reserve → meter (AI Gateway usage, search calls, Sandbox seconds) → settle at `price_book` with markup → release.
- Schedules with `credit_cap_per_run` and `monthly_cap`; refusal creates a "top up" task.
- Per-tenant AI Gateway key/budget as the hard cap.
- Dashboard **Credits & schedules** page.
**Quality gate**
- [ ] Ledger invariants (property tests): balance never negative; settle is idempotent; reserve released on failure.
- [ ] A run with insufficient balance does not start and creates a task.
- [ ] Metered cost on 20 real runs within ±10% of AI Gateway's own reported cost.

### Stage 8: Writer skills (1–2 weeks)
**Goal:** articles, chapters, timeline events and correspondence written to the rules.
**Build**
- Skills: `familypedia-article-writer`, `timeline-builder`, `chapter-writer`, `book-writer`, `request-writer`,
  `thankyou-writer`, `followup-writer`, `changelog-writer`. Each runs `fact-checker` and `privacy-checker` on its output
  before it reaches approval.
**Quality gate**
- [ ] Thresholds in §3.4 met on the frozen set.
- [ ] Human review: Rex scores a sample of 10 outputs per writer skill; mean ≥ 4/5; any 1–2 blocks the gate.
- [ ] No output with an uncited sentence reaches the approval inbox (audit).

### Stage 9: Publishing, display zones and the digest (1–2 weeks)
**Goal:** approved changes publish to each family's site; subscribers get a weekly email.
**Build**
- Asset graph: new data marks downstream assets stale; **debounced rebuild** (≤ hourly per tenant; heavy builds
  nightly) in Sandbox (Typst, fonts) from a snapshot.
- Display zones: multi-tenant routing by domain; static/ISR pages for Familypedia, chapters, timeline, `/updates`,
  `/changelog/`; signed-in family archive.
- `newsletter-writer` + Resend weekly digest per tenant (reuse `plugins/lineage/publish/api/{subscribe,confirm,digest,unsubscribe}.js`).
**Quality gate**
- [ ] **Byte-identical build:** the platform builds _The Book of Daniel_ PDF and site identical to the current hand-run
      build (or every difference listed and accepted by Rex).
- [ ] Ten new records in one hour → one rebuild, not ten.
- [ ] Digest preview for tenant #1 approved by Rex; double opt-in and unsubscribe work (Playwright).

### Stage 10: Clip generator (4–5 days)
**Goal:** shareable media from interviews and photos.
**Build**
- `clip-generator` skill: quote cards (image), short audio/video snippets with captions; exact timestamps from the
  transcript; output to Blob; needs approval before any public use.
**Quality gate**
- [ ] Quotes verbatim against the transcript (100%); timestamps within ±0.5 s on golden cases.
- [ ] No clip of a private person (seeded test cases, 100%).

### Stage 11: Archivist dashboard (1 week)
**Goal:** one place to run everything.
**Build**
- Port `lineage/app/server.py` `/api/engine/*` to Vercel Python on Neon/Blob; reuse `app/static` UI.
- Merge `web/src/app/admin/*` (earnings, KPI, QR, referrals) from `feature/event-onboarding`.
- Pages: **Agents & runs** (live runs, cost, logs), **Approvals**, **Skills**, **Credits & schedules**, **Models**
  (edit Edge Config roles; run evals on a candidate model before switching), **Sites**, **Call sheet**.
**Quality gate**
- [ ] Playwright: approve a draft, pause a schedule, switch `bulk` model (evals run first), top up credits.
- [ ] Every number on the dashboard traceable to a Neon query (no hard-coded values).

### Stage 12: Tenant #1 cutover (1 week)
**Goal:** _The Book of Daniel_ runs only on the platform.
**Build**
- Create `lineage-book-of-daniel` (content only) with `lineage.json` (pins agent + spec versions, models, budget).
- Retire: laptop sessions, local scheduled prompts, local Gmail/Drive tokens, worktree + clone push path.
**Quality gate**
- [ ] 14 days with no laptop involvement; every archive reply ingested; every approval honoured.
- [ ] Monthly cost report for tenant #1 within the estimate ($5–30 underlying).

### Stage 13: Multi-tenant hardening and tenant #2 (1–2 weeks)
**Goal:** prove the platform hosts more than one family.
**Build**
- Onboarding: form → tenant row → Connect Google install → content repo from template → Drive folder → domain.
- Tenant #2: the demo lineage; then one real family.
**Quality gate**
- [ ] Isolation suite: data, files, Drive, budgets and skills pinned per tenant cannot cross (automated).
- [ ] Onboarding a new family takes ≤ 30 minutes of human time.
- [ ] Upgrading tenant #2's skill versions does not change tenant #1.

---

## 6. Conventions for Cursor

- TypeScript strict; Zod schemas for every tool input/output; Vitest for units; Playwright for UI.
- Python only for the ported engine; `uv` + `pyproject.toml`; Pytest.
- Never hard-code a model id in code. Use roles.
- Never commit secrets, family data or private research files. Test data comes from the frozen set or the demo lineage.
- Every PR: tests + updated `CHANGELOG.md`; stages end with `docs/gates/stage-N.md`.
- When this plan and current Vercel/eve docs disagree, follow the docs and record the difference in the gate report.
- Ask Rex (via the gate report) rather than guessing on: prices and markup, digest frequency, auto-send policy for
  thank-yous, which Book of Daniel records may enter the frozen set.
