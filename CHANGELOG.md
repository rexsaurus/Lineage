# Changelog

Each release is a git tag (`vX.Y.Z`). Projects record the version they run in `lineage.lock`.
Every entry says whether it changes anything that would alter already-generated stories
(templates, the book template, style guides, skills); when it does, a project updating to it
marks those stories stale rather than regenerating them.

## 0.7.0 — 2026-10-08

**Alters generated stories: no.** New tools, template helpers and a publishing path; the book
template's existing functions render as before (`records` gains an internal flag only).

From a working family book's assembly and publication, in generic form (no names, places or
material from that project):

- **Whole-book index without marks.** `#show: auto-index.with((heading: (spellings…), …))` in the
  book's master file marks every occurrence of the listed names as the book is set, longest name
  first, so chapter files stay untouched; `make-index` merges these with any hand-placed `#idx`.
  Names inside a `#records` list are skipped (`records` now sets an `in-records` state).
- **Exhibits.** `#exhibit(title:, note:, (path, [caption]), …)` reproduces a document's scanned pages
  after a chapter, two to a row, numbered and captioned (a court file, a service record, a deed).
- **Readable editions of records.** `templates/records/readable-edition.typ`: cover, plain-English
  summary and timeline, every original page beside its full transcription (typed text and
  handwriting distinguished), editor's notes.
- **Image manager** (`plugins/lineage/scripts/image_manager.py`, skill `image-manager`): one catalogue
  of every image (`data/image_catalog.csv`: SHA-256, size, chapters, captions, origin, prompt hash,
  source URL, Drive id); `check --id/--prompt/--url/--file` before generating or fetching anything;
  `missing` (broken references, stand-ins, PLATE-TODO anchors), `unused`, and `drive-sync` (uploads new
  or changed images, record PDFs and the book to Google Drive with the `drive.file` scope; ids written
  back). `generate_images.py` now runs the guard before every generation and records each prompt in
  `data/image_prompts.json`.
- **Research tools.** `archive_fts.py`: full-text search of the Internet Archive with the matching
  passages (yearbooks, gazettes, town reports, newspapers). `patent_index_scan.py`: every patent
  granted to a named person, from the Patent Office's annual indexes 1872–1969, with extracts and
  sources; confirm numbers on Google Patents' patent pages.
- **Publish a real family's dashboard** (`site/build_instance.py`): the same read-only static
  snapshot as the public demo, for any project, with its book PDF. Refuses without
  `--allow-real-names`; always fails on local paths, emails, keys and localhost links; scrubs home
  and temp paths from published files; writes a `vercel.json`. `--hide sources,settings` removes those
  areas (tabs, addresses, data and files) from a public snapshot. See docs/DEPLOY.md.

Fixed:
- The dashboard's home page crashed when a person's article stored its infobox as a list of
  `[field, value]` pairs (projects imported from older layouts); infobox reads now accept both forms.

## 0.6.0 — 2026-10-05

**Alters generated stories: yes**, for projects that use Lineage's skills: the book template,
the writing rules and several skills changed (two columns by default, an epigraph per chapter,
THE RECORDS on every chapter, a page minimum). Projects that carry their own copies of the
skills are not affected (`lineage update` knows the difference). `lineage update` marks
generated stories stale; it never regenerates them.

The innovations of a working family book's full first pass, brought up in generic form (no
names, places or material from that project). Where the working book's rules and Lineage's
disagreed, the working book's rules became Lineage's defaults:

Conflicts resolved (the working book's rule is now the default):
- **C1 Illustrations.** Captions stay short (a name, or a scene title in the text's words; the
  author's caption word for word). An illustration is marked by `kind: illustration` in
  `photo_index.csv`, the chapter's note, and a copyright-page line ("The illustrations in this
  book are artist's renderings, not photographs."), which `build_book.py front` now writes
  whenever a placed image is an illustration (`book.yaml` → `front.illustrations_note`). The
  old rule that each caption must say "illustration" is retired.
- **C2 Epigraphs.** One per chapter by default (`chapters.epigraphs`); two allowed in a
  family-history chapter; none if the author asks. A writer of the chapter's place and time.
- **C3 THE RECORDS on every chapter**, listing 100% of the sources found and used (not only
  family-history chapters or chapters with context).
- **C4 No "general knowledge" sources.** Every context fact cites a real source.
- **C5 Two columns by default.** `chapter.with(columns: 2)` is the template default and
  `assemble.py` writes 2 when `data/chapters.csv` leaves `columns` blank; 1 stays available per
  chapter. Rows that already say 1 are unchanged.
- **C6 Archive thumbnails in drafts.** `#photo-addendum`'s `show-images` defaults to the draft
  flag: thumbnails print in drafts, and in the final book only once the holder's permission is
  recorded (`show-images: true`).
- **C7 Gates.** Work stops at the author's chosen gates (three by default, `workflow.gates`;
  the project's CLAUDE.md may be stricter and wins), and a full first pass of the whole book
  runs when the author asks for it (the book swarm, below).

New:
- **Chapter dossiers** (`chapter-dossier` skill, `scripts/dossier.py`, `templates/dossier/`):
  per chapter, the author's dated requests, a log of every search (blocked ones too), 100% of
  sources in `SOURCES.csv`, the evidence for and against the family's version, and lessons.
  `dossier.py records` generates THE RECORDS from it; `dossier.py check` fails when a URL in
  the chapter isn't logged or a cited source isn't listed.
- **Polite record fetching** (`scripts/fetch_records.py`): targeted lookups (at most 50 URLs a
  run), robots.txt obeyed, at least 2 s per site, a project-only User-Agent
  (`research.user_agent`; an email address is refused), no logins or bot-check workarounds;
  raw copies with sha256 metadata; logged in the dossier; anything blocked goes on the
  manual-lookups list.
- **Research access rules** (records-archives): automated fetching vs targeted lookups by a
  person in their own browser and accounts (or a browser assistant in the author's own
  session, at their direction); never CAPTCHA solving, bot-check tools, others' credentials or
  bulk harvesting. Hand-off templates: `templates/research/MANUAL-LOOKUPS.md`,
  `manual-lookups-results.csv`, and `REQUESTS.md` (archive requests and replies);
  `make new` copies them into `research/`.
- **The service-record method** (family-history-chapters §6a): for anyone who served, the
  official record first as the spine; then the hometown and country, how the war drew them in
  and their reputation, enlistment, training and shipping, the unit's battles, weapons and
  generals, being sent home, and what veterans came home to; first-hand accounts from soldiers
  in or near the unit, quoted exactly and verified.
- **Sensitive record entries** (memoir-style-guide §2): kept out of the prose until the author
  decides; then told plainly from the record, without moralising.
- **Page minimum and combining** (style guide §6, chapter-index-builder): chapters of at least
  `chapters.min_pages` (default 10) in the layout, reached with real material; sparse chapters
  are combined, never padded. `build_book.py chapter` (`make chapter`) prints a note when a
  chapter is short.
- **Template:** `#family-tree(...)`, a three-generation tree (parents → couple → children, the
  line of descent continued under one child) that stands in for or beside `#descent`;
  `#story-panel` and `#story-page`, an eight-panel illustrated story over two facing pages, each
  panel captioned with the subject's exact words.
- **Illustration generator** (`scripts/generate_images.py`, `templates/images/`): plans in
  `photos/images-plan.yaml` with period style presets, a one-line lock on every prompt, a
  required scene citation, and an optional likeness lock (real photographs as references
  through the edit endpoint); writes the original and a grayscale print copy; `--dry-run`
  prints every prompt. The key comes from `OPENAI_API_KEY` or `~/.openai_api_key` (chmod 600,
  outside every repo) and is never printed or written.
- **The book swarm** (`docs/BOOK-SWARM.md`, `templates/swarm/book-swarm.js`): a parameterized
  Workflow script for a full first pass: per chapter two researchers → writer → fidelity,
  taste and layout editors → two judges with revisions to a pass score → a 100% sources pass;
  then front matter, images plan, index, assembly and a whole-book continuity review.
- `book.yaml` template: `front.illustrations_note`, `chapters.min_pages`, `chapters.epigraphs`,
  `research.user_agent`, `workflow.gates`. Project `.gitignore`: `photos/generated/`,
  `photos/reference/`, `research/manual-lookups/`. Project CLAUDE.md: gates, dossiers, research.
- Docs: HOWTO (research access, dossiers, family tree, anyone who served, generating
  illustrations, the illustrated story, page minimum, gates and the full first pass), README,
  scripts/README, EXAMPLE-CHAPTER notes; the dashboard's standing rule on generated images.
- Typst gotchas documented: a `;` after an embedded call in markup is swallowed (write
  `\u{3B}`); a full-page float sized to the text block.

Also in this release (made on `development` after 0.5.0):

Dashboard:
- Sources: a gallery and a lightbox (arrow keys, summary, people and places linked, provenance,
  notes, subject tagging). Roadmap #5.
- Stories: what each story rests on, above its pages: every paragraph's citation chips, and every
  image's provenance with a toolbar (open, tag, copy reference). Roadmap #12.
- An illustration is never a person's picture (tree, featured relative, person articles);
  "illustration" is a kind of source.
- Wording: the dashboard speaks of the family's record; "the book" only where the export is meant.

Skills and scripts (generic improvements brought up from a working project):
- Writing rules: locked passages (`voice/verbatim.md`) go in `#verbatim` word for word; never
  silently correct the subject; public-domain status checked per edition for epigraphs; an
  author's introduction to a part is a `#bridge` until approved; when the subject told a story
  two ways, keep both, attributed; contents lines are short plain nouns; propose an album
  section when a chapter has more good photographs than text.
- Photo intake and archive workflow (`photos/inbox/` → `photos/archive/originals/…`); dating cues;
  relative dates chained to the event they hang on.
- `make chapter PROJECT=… CHAPTER=…` builds one story as a preview; `PAGES=1` exports each page
  as an image for sharing. build_book.py falls back to the `typst` Python package without the CLI.
- `transcript/corrections.json` → `drop_word_runs`: remove phrases the speech model echoed from
  its prompt, word by word.
- `lineage update`: skill changes don't mark stories stale in projects with their own skills.

## 0.5.0 — 2026-10-01

**Alters generated stories: no.** Eight skills' `description:` lines changed (what triggers
them, not what they tell the writer); `lineage update` now recognizes a description-only change
and doesn't mark stories stale for it.

Lineage is described as what it is: a cooperative family documentation and research platform
whose outputs include stories, a book and narration.
- README rewritten around the platform, with a tour of the real dashboard; docs/HOWTO.md
  restructured (set up a lineage, contributors, sources, records, genealogy and Familypedia,
  then stories and a book); docs/FACTORY.md, the plugin, marketplace and skill descriptions
  reframed.
- `examples/demo-lineage/`: an invented family (the Calders) with recordings, scanned records,
  a ship, a route, a genealogy, contributors and a narrated story, built by
  `scripts/demo_lineage.py`. `make demo` opens the dashboard on it.
- `make screenshots` (`scripts/screenshots.py`, Playwright) captures the dashboard against the
  demo lineage into `docs/images/`, with an empty HOME so no keys or accounts appear.
- Timeline and Familypedia tiers: a record citation (R001), manifest or ledger now counts as
  "what the records show" (the check was case-sensitive after lower-casing).

## 0.4.0 — 2026-10-01

**Alters generated stories: no.** Nothing under `plugins/lineage/book/`, `fonts/` or `skills/`.

Projects are consumers of Lineage:
- `bin/lineage version | update | dashboard`. `update` fetches the releases, prints the
  changelog between the pinned release and the target and the files of the project it would
  touch; with `--apply` it installs the release read-only under `~/.lineage/releases/<tag>`,
  pins it in `lineage.lock`, re-points `.claude/skills` when it links to a release, and marks
  stale (never regenerates) the stories a release would alter. Material is never touched.
- The project template gains a `Makefile` (`make dashboard`, `make lineage-version`,
  `make update-lineage [APPLY=1] [TO=vX.Y.Z]`), `lineage.lock`, `local-overrides/`, the
  dashboard's runtime files in `.gitignore`, and the arrangement at the top of its CLAUDE.md.
- `CLAUDE.md` for this repo: platform changes are made here and flow down; content stays in
  the project; one-off things go in the project's `local-overrides/`.
- Familypedia: empty Sources, Records and Photographs sections are hidden; a lone word that
  only names a stub person (a surname off a roster) is no longer linked automatically.

## 0.3.2 — 2026-10-01

**Alters generated stories: no.** Dashboard engine only (`app/familypedia.py`).

- A place on a route now links back to the ships and voyages whose route it is ("On the
  route of"), so a vessel, its ports and its voyage are reachable from each other.

## 0.3.1 — 2026-10-01

**Alters generated stories: no.** Dashboard engine only (`app/familypedia.py`).

Familypedia fixes found while building a real project's articles:
- After two articles are folded together ("same as"), the names of the folded one now find
  the surviving article, so its coordinates, routes, events and relations carry over.
- The person article's link into the genealogy tree reads the tree's people as a mapping
  (as the Genealogy tab writes it), not a list. Articles no longer fail on that.
- `Also called:` in a person profile keeps the names (and names in quotation marks) and drops
  commentary written on the same line.

## 0.3.0 — 2026-10-01

**Alters generated stories: no.** Nothing under `templates/`, `book/`, `plugins/lineage/book/`,
`plugins/lineage/templates/` or `plugins/lineage/skills/` changed since 0.2.0.

The dashboard (`app/`), new since 0.2.0:
- Home, a settings gear (Family details · Connectors · Contributors · Project settings) and a
  terminal drawer; Sources, Familypedia, Genealogy, Stories and Timeline tabs.
- Source intake end to end: SHA-256 dedupe, extraction and OCR, summaries, thumbnails, edits
  kept apart from derived values, trash and restore. No demo content unless `--demo`.
- Stories with states, rendering to book pages, narration; Timeline with tiers, conflicts and
  gaps; Genealogy rebuilt from the material with evidence, review, edits and GEDCOM.
- **Familypedia article types**: person · place · event · vessel · organization/unit · object ·
  publication · occupation · theme, with typed infoboxes, tier sections, passages, sources,
  typed records, photographs and marked illustrations, related articles, backlinks, open
  questions and "Beyond the family"; tagging of sources, records, photographs and events to
  any type (picker, suggestions with evidence, bulk); browse, search, `[[links]]`, and a map
  drawn from the records' own coordinates. Inputs and outputs: `app/README.md`.
- Example chapter: the Hannibal route and voyage details.

## 0.2.0

The project renamed to Lineage; a Claude Code plugin marketplace with two plugins (`lineage`,
`factory`).
