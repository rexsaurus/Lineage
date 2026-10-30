# Lineage macros: the research loop

**This file is the whole research loop, in one place.** Any agent (Claude Code, another CLI agent, or a person) can run
it by reading this file and the project's `MACROS.local.md`, then following the steps. Nothing here is specific to one
family. Everything project-specific lives in the project's `MACROS.local.md`: paths, private names, frozen chapters,
blocked sites, outbound mode and schedule.

Entry points (all run the same text):
- **Claude Code:** `/sync` (a command that says "run `daily-update` from this file"), or "run the update-person macro
  for Jane Doe".
- **Terminal:** `scripts/research_sync.sh` (the mechanical steps), or `scripts/research_sync.sh --agent` (the whole loop,
  agent headless).
- **Schedule:** launchd or cron calls `research_sync.sh --agent` once a day. It has to run on the machine that holds the
  mail and Drive logins and the project files.

## 1. The graph

```
daily-update (once a day)
 ├─ scan-email ─────────────► new records, photos, leads, threads; marks people DIRTY
 ├─ pursue-leads ───────────► new sources (recursive: depth ≤ 3); marks people DIRTY
 ├─ update-person × each DIRTY person (and a few stale ones, rotating)
 │    ├─ hydrate sources · archive records · core records & events · conflicts
 │    ├─ revise content (chapter, Familypedia page, …) only where its data changed
 │    └─ marks directly related people DIRTY (one level only)
 ├─ handle-correspondence ──► thank-yous and asks (drafts unless outbound_mode = send)
 ├─ sync-storage ───────────► Drive, R2, git
 ├─ write-daily-report ─────► PRIVATE report: everything, including "needs owner" items
 ├─ publish-post ───────────► PUBLIC daily post (findings only) → Updates tab and /updates/
 └─ weekly-digest (on its day) ► PUBLIC weekly newsletter post; email only when enabled
add-source (any time) ──► attach to a person, mark DIRTY, run update-person
```

The rule that holds it together: **anything that changes a person only marks them dirty.** `update-person` is the only
place that does the expensive work, and content is revised only when the person's **data hash** differs from the hash
the content was built from. A change is never processed twice.

## 2. Rules for every macro

1. **No invented facts.** Every stored claim cites a source (a record, page, transcript or URL). If you can't cite it,
   don't store it.
2. **Conflicts are recorded, not resolved.** When sources disagree, store both, flag the conflict in the project's
   evidence file, and leave the decision to the owner.
3. **Scraping:** obey robots.txt, including any rule that names your agent. Make at most 1 request per 2 seconds per
   domain, send a descriptive User-Agent, and don't solve CAPTCHAs or get past logins or paywalls. Don't use a mirror
   to get around a block. The project's blocked sites are in `MACROS.local.md`.
4. **Never** pay, order, sign in, create accounts, accept terms, or enter personal data. Those become "needs owner"
   to-dos.
5. **Secrets:** read them from the environment or their own files only. Never print them, log them, or write them into
   reports, posts or these files.
6. **Frozen content** (listed in `MACROS.local.md`) is never edited. Write proposals next to it instead.
7. **Idempotent:** records are keyed by checksum, sources by URL, emails by message id, posts by date, the digest by ISO
   week. Re-running a day changes nothing twice.
8. **Every run leaves a trail:** what each macro did goes into that day's private report (step 4.7). Failures are
   reported, never hidden. One person failing never fails the run.
9. **Public output** (posts, digest, site) always passes the privacy filter (section 5). Private output (the report)
   can say anything, but it stays off the public site.

## 3. Project state (files, no database)

Paths are named in `MACROS.local.md`. The macros expect:

| What | Where (see `MACROS.local.md`) |
|---|---|
| person | the Familypedia page (`data/wiki/<person>.md`) and the dossier (`dossiers/<person>/`) |
| sources | `dossiers/<person>/SOURCES.csv`: id, title, author, date, url, local path, retrieved, used for, cited, status |
| research log | `dossiers/<person>/RESEARCH-LOG.md` (append-only, dated) |
| records | `facts/records/<person>/*.md` (transcriptions) and the files themselves (archive folder, checksummed) |
| correspondence | the archived mail folder and its `INDEX.csv` (one row per message) |
| requests | the request catalogue (institution, contact, sent, replies, status, next step due) and the sent log |
| content | chapters (`.typ` → per-chapter PDF), Familypedia pages, and other registered types |
| state | `data/people_state.json`: per person `dirty`, `dirty_reason`, `data_hash`, `last_hydrated`, `lock` |
| reports | `reports/daily-YYYY-MM-DD.md` (private) |
| posts | `posts/YYYY-MM-DD-daily-update.md` and `posts/YYYY-Www-weekly-digest.md` (public) |
| to-dos | inside the daily report, built from the request catalogue (due dates) and "needs owner" items |

`data_hash` = a SHA-256 of the person's page, their sources CSV, the transcriptions of their records, and the
correspondence rows that name them. Each content item records the hash it was built from in a comment
(`// built-from: <hash>`) or a sidecar file.

## 4. The macros

### 4.1 `daily-update` (the top level)
**Inputs:** `date` (default today); `dry_run` (default false); `outbound_mode` (from `MACROS.local.md`; default
`draft`); `max_people` (default 8); `max_minutes` (default 120).

1. Take the daily lock (`reports/.lock`). If it's already held, stop.
2. Run `scan-email`. If mail can't be read (for example an expired login), skip to step 8 and report it as a "needs
   owner" item.
3. Run `pursue-leads` on that day's new leads.
4. Run `update-person` for every dirty person, then for up to 2 stale people (oldest `last_hydrated` first, more than
   14 days old), within `max_people` and `max_minutes`.
5. Run `handle-correspondence`.
6. Run `sync-storage`.
7. Collect the to-dos: requests past their follow-up date (21 days after sending, or the institution's own stated
   date); orders in transit with their expected dates; decisions waiting on the owner; "needs owner" items.
8. Run `write-daily-report`, then `publish-post`.
9. If a weekly digest is due (its weekday, or the first run after a missed one), run `weekly-digest`.
10. Release the lock. Print the report's path and a one-line summary.

### 4.2 `scan-email`
Read-only. Only reads mail to or from research correspondents: the addresses in the request catalogue, sources and
logs. Never reads anything else in the inbox, and never anything the project marks private (legal or court matters,
personal finance).

1. Export new messages since the last scan to the archived mail folder (original message plus an `INDEX.csv` row). Skip
   drafts.
2. Extract the attachments (never overwriting) and list each one by kind: image, PDF or other.
3. For each new inbound message:
   - classify it: data shared, acknowledgement, question, fee or quote, or noise;
   - link it to the people it concerns;
   - pull out any recommended sources as leads.
4. Mark the people it concerns dirty, with the reason `email:<message id>`.

**Output:** new messages, new files, new leads, and the threads that need a reply.

### 4.3 `update-person` (the per-person macro)
**Inputs:** `person`; `force` (default false); `reason` (`new_source` | `email` | `daily` | `manual`).

0. If the person isn't dirty, was updated less than 24 hours ago, and `force` is false, stop and report "fresh". Take
   the person's lock.
1. **Identity.** Complete the name variants: short and long forms, nicknames, maiden name, misspellings,
   transliterations, and spellings for their nationality. Also complete the historical place names (county or parish
   changes). Note the evidence for any variant you add.
2. **Sources.**
   - Re-check the existing sources and mark each one alive, changed or gone.
   - Search for new ones using variants × places × dates (digitized newspapers, archive catalogues, open indexes,
     Wikipedia and Wikidata).
   - Rank each hit confirmed, probable or unrelated, using dates, places and relatives. Store confirmed and probable
     hits with their confidence. Log unrelated hits in the research log so they're never re-checked.
   - Blocked sites (rule 3) become leads for a person to follow up.
3. **Records.** Save each new record (PDF, image or scan) to the archive folder with its checksum. Transcribe it or
   read it with OCR into `facts/records/<person>/`. Extract names, dates and places, and link the record to every
   relative it mentions.
4. **Email.** Attach the threads that name the person (`scan-email` already archived them). Run any files that were
   shared through steps 2–3.
5. **Core records and events.** Check birth, marriage, divorce, children's births and death, and mark each one as held,
   requested or missing. Update the person's events with date, place and source. If sources disagree, flag the
   conflict (rule 2).
6. **Revise content.** Compute `data_hash`. For each content item whose built-from hash differs:
   - **Chapter:** make targeted edits only. Add the new fact in the chapter's voice, with its source comment and an
     entry in the chapter's records section and a plate if there's an image, then rebuild that chapter's PDF alone.
     **Never regenerate a chapter from scratch** unless the owner asks for it. Frozen chapters get a proposal instead.
   - **Familypedia page:** add the fact with a footnote citing the source.
   - **Other registered types:** keep the old output until the new one succeeds. A failure keeps the old output and
     goes into the report.
7. **Wrap up.** Store `data_hash` and `last_hydrated`, clear `dirty`, and release the lock. Mark relatives dirty only
   if a shared fact changed (a spouse, a parent, a shared event), and go one level only.

**Output:** person, status (`updated` | `fresh` | `partial` | `failed`), sources added, records added, emails, variants
added, events changed, conflicts, content revised, failures, relatives marked, suggested outreach, and new leads.

### 4.4 `handle-correspondence`
For each inbound message that shared data, write a warm, specific thank-you that names what was shared. Add one short,
specific ask where it helps: the next document, a scan, a pointer.

The tier decides the behaviour:

| Message | `outbound_mode = draft` (default) | `outbound_mode = send` |
|---|---|---|
| thank-you or ask to someone who sent data | draft | send, once per thread per day |
| follow-up past its due date to an existing contact | draft | draft |
| first contact with a new archive | draft | draft |
| anything with money, orders, forms, terms, or the owner's address or phone | never; becomes a "needs owner" item | never |

Never reply to automated or marketing mail. Log every draft and every message sent in the sent log.

### 4.5 `pursue-leads`
Run each open lead (a recommended archive, collection, book, site or person) through the source search and
ingestion. Attach what you find to people and mark them dirty. Add any new leads with `depth + 1`.

Limits: depth ≤ 3; at most 10 leads a run; deduplicate by URL and checksum; obey rule 3. Whatever can't be done
online goes into the catalogue's additional-research list as a to-do.

### 4.6 `sync-storage`
- Register new photos in the photo index, with provenance, credit, date and who is shown.
- Upload new images to R2.
- Mirror every new archive file to Drive (`Records/...`), keyed by checksum and never uploaded twice.
- Push the project to git.
- Report anything that failed to upload. An expired login is a "needs owner" item.

### 4.7 `write-daily-report` (private)
Write `reports/daily-YYYY-MM-DD.md`. Facts only; every item links to its record, page or message id. Sections:
1. **Summary counts:** people updated, sources, records, messages in and out, photos, content revised, and minutes.
2. **Open to-dos (read first):**
   - follow-ups due;
   - orders and their expected dates;
   - decisions;
   - **needs owner:** fees, calls, forms, logins, drafts to approve, and posts the filter refused.
3. **Mail in and out**, and the drafts awaiting approval.
4. **Updates by person**, with links.
5. **New leads and sources**, with confidence.
6. **Conflicts** waiting for a decision.
7. **Failures and partial runs.**
8. **Storage:** Drive, R2 and git.

### 4.8 `publish-post` (public)
1. Write `posts/YYYY-MM-DD-daily-update.md` with front matter: title "Daily update, D Month YYYY: …",
   `slug: daily-YYYY-MM-DD`, date, summary, image (a project path that's on R2) and author.
2. **Findings only:**
   - what was found;
   - what changed in the book, linking `/family/<person>/` pages;
   - leads followed;
   - what is still being looked for, per person.
3. Run the privacy filter (section 5). If it refuses the post, fix it. If it can't be fixed, set `draft: true` and add
   a "needs owner" to-do. **Never weaken the filter to make a post pass.**
4. Publish: add the release-notes entry, rebuild only the changed chapters (and the book edition when the owner bumps
   it), then republish the site.

The post appears in the dashboard's **Updates** tab and at `/updates/<slug>/`. It is **not** emailed.

### 4.9 `weekly-digest` (public; the only thing emailed)
**Inputs:** `week` (`YYYY-Www`, default last week); `dry_run`; `send` (default off, from `MACROS.local.md`).

1. Read that week's daily posts and the data behind them.
2. Write one newsletter in warm prose to the family, with these sections:
   - **Opening:** match the tone to the real counts. Never inflate a quiet week.
   - **Highlights:** 3–5 finds, each with why it matters.
   - **New photos:** captions and who is shown, following the rules for living people.
   - **New sources:** where each came from and who it concerns.
   - **People updated:** what changed for each, and which chapters and pages changed.
   - **Still to track down:** outstanding records and data by person, with the age of each open question.
3. **Never include:** "needs owner" items, fees, correspondence, or anything legal or private.
4. Save it as `posts/YYYY-Www-weekly-digest.md`, run the privacy filter, add a release-notes entry, and publish.
5. **Sending:**
   - while the digest is disabled (`settings.publish.digest.enabled: false`), it is only published and previewed for
     the owner;
   - once enabled, the site's digest function emails confirmed subscribers once per ISO week, with an unsubscribe
     link, and logs week, recipient count and time;
   - a quiet week is skipped by default and logged.

### 4.10 `add-source`
**Inputs:** `person`; `url | file`.

Attach it, mark the person dirty with `reason: new_source`, and run `update-person`.

## 5. The privacy filter (all public output)

Enforced in code by `plugins/lineage/scripts/posts.py`; the site build refuses a post that fails. A public post must
not contain:
- **Private terms:**
  - `settings.publish.private_terms`, and the file `settings.publish.private_terms_file`;
  - the project generates that file from every correspondent's name, plus its own manual list of protected people and
    topics.
- **Correspondence:**
  - email header lines, quoted replies, mail or draft ids;
  - sections about letters, emails or drafts;
  - who wrote to whom, or what was asked.
- **Contact details:** phone numbers, plus email addresses, local paths and keys (the leak check).
- **Living people:** private details about them (PRIVACY.md); legal or court matters; fees and orders.

## 6. Owner settings (in `MACROS.local.md`)

- `outbound_mode` (`draft` | `send`).
- The weekly digest: on or off, its weekday, and whether quiet weeks are skipped.
- The daily run time.
- Limits: `max_people`, lead depth, minutes.
- The staleness threshold (default 14 days).
- Blocked sites and private-topic rules.
- Frozen content.
- Paths that differ from section 3.
