# Lineage "Try it" agent (free trial)

**Status:** plan, v0.1 (18 October 2026). Owner: Rex St. John.
**Scope:** this is the only thing being built now. It **supersedes** the wider platform plans
([PLATFORM-ARCHITECTURE.md](PLATFORM-ARCHITECTURE.md), [VERCEL-MIGRATION.md](VERCEL-MIGRATION.md),
[BUILD-PLAN.md](BUILD-PLAN.md)) until it ships. Those stay as the long-term direction.

**One sentence:** a visitor drops in some family files and a few facts, the agent reads everything, does one general
pass of the public record, and returns a summary of what it found and what's still missing, with a button to **buy
credits to fill it in**.

Lives at **lineage.rexstjohn.com/try** (linked as "Try it" from the home page and Quickstart). Replaces `/testdrive/`,
whose search code becomes one of the agent's tools.

---

## 1. The visitor's experience

```
┌──────────────────────────┐   ┌──────────────────────────┐   ┌──────────────────────────┐
│ 1. TELL US               │   │ 2. WE LOOK               │   │ 3. HERE'S WHAT WE FOUND  │
│                          │──►│                          │──►│                          │
│ • family name(s)         │   │ live progress:           │   │ • your family at a glance│
│ • a few people: name,    │   │  reading your files…     │   │ • what your files say    │
│   rough dates, places    │   │  found 6 people…         │   │ • what the record shows  │
│ • a family story (opt.)  │   │  searching newspapers…   │   │ • a first timeline       │
│ • drag & drop files      │   │  checking 1900 census…   │   │ • where the rest is      │
│ • email                  │   │                          │   │ • what's still missing   │
│ • "deceased relatives    │   │ (2–4 minutes)            │   │                          │
│   only" consent          │   │                          │   │ [ Buy credits to fill    │
└──────────────────────────┘   └──────────────────────────┘   │   this in ]              │
                                                              │ [ Email me this report ] │
                                                              └──────────────────────────┘
```

- The report has a private link and is emailed. Uploads are deleted after 30 days unless the visitor buys credits.
- "Buy credits" carries the trial over: the paid agent starts from this trial's people, files and findings.

## 2. What the trial does (and doesn't)

| Does | Doesn't (that's what credits buy) |
|---|---|
| Reads up to **10 files** (PDF, JPG/PNG/HEIC, DOCX, TXT; ≤ 25 MB each) | Audio/video transcription |
| Extracts people, dates, places, events and family claims, citing the file each came from | Writing articles or chapters |
| Picks up to **5 people** and runs one general search pass on each | Deep, repeated research rounds |
| Searches **open** sources only: Library of Congress newspapers, Internet Archive, Wikidata, plus DeepSeek web search | Drafting or sending archive requests |
| Says which finds are likely matches and why; lists searches that found nothing | Ordering records, paid databases |
| Names the archives that probably hold the rest | Familypedia, timeline site, book, digest |
| Estimates the work left, in credits | |

## 3. Architecture (blocky)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  lineage.rexstjohn.com/try          (Next.js page, rewrite to try app)   │
│  form + drag & drop  ──► files go straight to Vercel Blob (private)      │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    ▼  POST /api/trial  (BotID + rate limit)
┌──────────────────────────────────────────────────────────────────────────┐
│                     TRIAL WORKFLOW  (Vercel Workflows)                   │
│                                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ 1 READ   │─►│ 2 UNDER- │─►│ 3 PLAN   │─►│ 4 SEARCH │─►│ 5 MATCH  │    │
│  │ files    │  │ STAND    │  │ ≤5 people│  │ parallel │  │ likely / │    │
│  │ text+OCR │  │ people,  │  │ ≤4 quest-│  │ per      │  │ possible │    │
│  │          │  │ events   │  │ ions each│  │ person   │  │ / none   │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│                                                   │                      │
│                                                   ▼                      │
│                     ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│                     │ 8 CLEAN  │◄─│ 7 DELIVER│◄─│ 6 REPORT │             │
│                     │ UP (30d) │  │ page +   │  │ summary +│             │
│                     │          │  │ email    │  │ estimate │             │
│                     └──────────┘  └──────────┘  └──────────┘             │
└──────┬─────────────────────┬─────────────────────┬───────────────────────┘
       ▼                     ▼                     ▼
┌──────────────┐   ┌───────────────────┐   ┌───────────────────┐
│ AI GATEWAY   │   │ SEARCH TOOLS      │   │ STORAGE           │
│ bulk: cheap  │   │ LOC newspapers    │   │ Blob: uploads,    │
│ vision: cheap│   │ Internet Archive  │   │       report      │
│ (env switch) │   │ Wikidata          │   │ KV/Neon: trials,  │
│ budget cap   │   │ DeepSeek Search   │   │       leads       │
└──────────────┘   └───────────────────┘   └───────────────────┘
                                    │
                                    ▼
                 ┌──────────────────────────────────────┐
                 │ "Buy credits to fill this in"        │
                 │ Stripe Checkout ──► paid agent later │
                 └──────────────────────────────────────┘
```

## 4. The steps

| Step | What it does | Model / tool | Caps |
|---|---|---|---|
| **1 Read** | PDF text layer (pdf-parse); scans and photos → vision model transcribes and describes (who, when, where, any writing on the back); DOCX → text | `vision` role (cheap) | 10 files, 25 MB each, 30 pages per PDF |
| **2 Understand** | Builds the family: people (names, variants, dates, places, relationships), events, family claims; each item cites its file (and page) | `bulk` role (DeepSeek V4.1 Flash) | one pass |
| **3 Plan** | Picks up to 5 people with enough detail to search; up to 4 questions each (birth, marriage, death, census, military, immigration, obituary) | `bulk` | 20 questions max |
| **4 Search** | Per person, in parallel: LOC Chronicling America (≤ 1963), Internet Archive (books, directories, yearbooks), Wikidata (notable relatives), DeepSeek Search with `site:`/`before:` filters; Fetch only on allowed pages | tools from `api/testdrive.js` + DeepSeek | ≤ 40 searches, ≤ 15 fetches per trial |
| **5 Match** | For each candidate: likely / possible / no match, with the details that matched; every empty search recorded | `bulk` | — |
| **6 Report** | Writes the summary (§5), the "still missing" list and the credit estimate | `write` role (cheap by default) | ≤ 2,500 words |
| **7 Deliver** | Saves report to Blob; private link; email via Resend; lead stored | — | — |
| **8 Clean up** | `sleep('30d')` then delete uploads unless converted | Workflows | — |

Live progress: each step writes a short status line the page polls (or streams).

## 5. The report

```
YOUR FAMILY AT A GLANCE          people, relationships, places (from your files)
WHAT YOUR FILES SAY              key facts, each with the file it came from
WHAT THE PUBLIC RECORD SHOWS     per person: likely matches (with link + why), possible matches
A FIRST TIMELINE                 dated events, file or record cited
WHERE YOUR FILES AND THE RECORD DISAGREE
WHERE THE REST PROBABLY IS       archives, libraries, societies likely to hold more (named, no requests drafted)
WHAT WE SEARCHED                 including searches that found nothing
WHAT'S STILL MISSING             open questions, each with an estimate
  e.g. "~14 records to chase · 6 archive requests to write · 5 family articles · 1 chapter ≈ 900 credits"
[ Buy credits to fill this in ]
```

Rules carried from the hand-run research: every fact cites a file or a link; contradictions shown, not resolved; dates
never more precise than the source; "possible" matches labelled as such; living people never searched.

## 6. Cost, limits and abuse

- **Cost per trial (estimate):** DeepSeek Flash + a cheap vision model + ~40 searches ≈ **$0.05–0.30**. AI Gateway project
  budget is the hard daily cap (e.g. $10/day = at least ~30 trials/day); trials beyond it queue for tomorrow with a
  polite message.
- **Abuse:** Vercel BotID on the form; 1 trial per email per 30 days and a per-IP rate limit; file type/size checks;
  uploads scanned for type before reading.
- **Privacy:** consent checkbox ("my relatives in these files have died"); no searches on people born after 1925 or not
  known to have died (as `/testdrive/` already enforces: ≤ 1949, deceased only); uploads in private Blob; model calls
  with US-only + Zero Data Retention; deletion after 30 days; nothing published.

## 7. Models (switch at the drop of a hat)

Code calls roles only: `bulk`, `vision`, `write`. Each role is an env var or Edge Config key holding an AI Gateway
model id, e.g. `TRIAL_MODEL_BULK=deepseek/deepseek-v4.1-flash`. Changing it takes effect on the next trial with no
redeploy (Edge Config) or one redeploy (env). The eval set (§9) runs before any switch.

## 8. Code and hosting

New Vercel project **`lineage-try`** (Next.js App Router + Workflows), in the Lineage repo at `try/`, served at
`lineage.rexstjohn.com/try` by a rewrite in the main project's `vercel.json`. Keeping it separate means the static site
is untouched and the trial can deploy on its own.

```
try/
  app/try/page.tsx                 form + drag & drop + progress + report view
  app/api/trial/route.ts           start a trial (BotID, limits, consent) → start workflow
  app/api/trial/[id]/route.ts      status + report
  app/api/upload/route.ts          Blob client-upload tokens (type/size limits)
  workflows/trial.ts               'use workflow': read → understand → plan → search → match → report → deliver → cleanup
  lib/steps/read.ts                pdf-parse, mammoth, vision
  lib/steps/understand.ts          people/events/claims schema (zod)
  lib/steps/plan.ts
  lib/steps/search/{loc,ia,wikidata,deepseek}.ts   (loc/ia/wikidata ported from api/testdrive.js)
  lib/steps/match.ts
  lib/steps/report.ts              report template
  lib/models.ts                    role → model (env / Edge Config), via AI Gateway
  lib/limits.ts                    caps, rate limits, budget checks
  lib/store.ts                     trials + leads (Upstash KV or Neon)
  evals/                           §9
```

Accounts/keys: AI Gateway (US-only + ZDR, daily budget), `DEEPSEEK_API_KEY` (Search/Fetch), Blob store, Upstash KV
(already planned for `/join/`) or Neon, Resend (already used for the digest), Stripe (Payment Link or Checkout for credit
packs; price TBD by Rex).

## 9. Quality checks (before launch, and before any model switch)

**Benchmark families** (in `try/evals/`):
1. **Book of Daniel sample:** 6 files we already hold whose content is public-domain or Rex's own (e.g. the 1921 Hartford
   Courant obituary of Erastus W. Burnham, a family photo with writing, a 1940s letter, a typed family summary) and a
   brief written from what was known *before* the research. Gold answers: what the hand-run research actually found.
2. **Demo lineage** (`examples/demo-lineage`): invented family, safe to share.
3. **Adversarial:** a living person in the files, a blurry photo, an unrelated PDF, a file in another language.

| Check | Pass mark |
|---|---|
| People extracted from files (recall vs gold) | ≥ 90% |
| Facts cite the right file | 100% |
| "Likely" matches that are wrong | ≤ 5% |
| Public-record finds vs gold that a general pass should reach | ≥ 50% (the rest is what credits are for) |
| Living people searched | 0 |
| Searches that hit a bot-checked or login site | 0 |
| Run time | ≤ 4 min (p90) |
| Cost per trial | ≤ $0.30 (p90) |
| Report rubric (judge model + Rex on 5 samples): clear, honest, useful, makes the "buy" case without overselling | ≥ 4/5 |

## 10. Build stages (each ends with a check)

| Stage | Build | Check |
|---|---|---|
| **1 Skeleton** (2 days) | `try/` project, page with form + drag & drop to Blob, `/api/trial` starts a workflow that echoes the inputs | upload 10 files; workflow runs; status shows |
| **2 Read + Understand** (3 days) | steps 1–2; people/events/claims JSON with file citations | benchmark: people recall ≥ 90%, citations 100% |
| **3 Search + Match** (3 days) | steps 3–5; testdrive tools ported; DeepSeek Search; caps | benchmark: wrong "likely" ≤ 5%; no living/bot-checked searches |
| **4 Report + Deliver** (2 days) | steps 6–7; report page; email; lead store; credit estimate; "Buy credits" (Stripe test mode) | rubric ≥ 4/5 on 5 samples; email arrives |
| **5 Limits + launch** (2 days) | BotID, rate limits, budget cap, 30-day cleanup, consent; rewrite at `/try`; home + Quickstart link "Try it"; `/testdrive/` redirects; changelog entry | run 20 trials: p90 ≤ 4 min, ≤ $0.30; cleanup verified with time travel |

**Then** the paid agent (deeper rounds, archive requests, articles, chapters) grows from this same workflow: more
rounds, more skills, credits instead of a free cap.

## 11. Decisions for Rex

1. Credit pack prices and what "1 credit" buys.
2. Free-trial daily budget (suggest $10/day to start).
3. Which Book of Daniel files may go in the benchmark (public-domain clippings and your own documents only).
4. Keep `/testdrive/` as a lighter "search a surname" page, or redirect it to `/try/`.
