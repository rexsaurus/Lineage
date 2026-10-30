# Changelog

Each release is a git tag (`vX.Y.Z`). Projects record the version they run in `lineage.lock`.
Every entry says whether it changes anything that would alter already-generated stories
(templates, the book template, style guides, skills); when it does, a project updating to it
marks those stories stale rather than regenerating them.

## Unreleased

**Alters generated stories: no.** Dashboard and snapshot only.

- **A first name inside someone else's name no longer tags a relative**: "John" in "John Carmack" or "Alex St. John",
  "William" in "William H. Bristol". A one-word person's name counts only standing alone, or followed by initials and
  that person's own surname ("Erasthus W. Burnham"). Places keep matching inside longer names ("the Arctic Circle").
- **The timeline reads the material, not only `facts/timeline.csv`**: a dated photograph that shares a year and a person with
  an event illustrates it; other dated photographs gather into one entry per year, and dated records into one entry
  per year and archive (a box of letters is one line). Spans of more than 15 years date nothing. `updatedAt` now also
  moves with photo details, the image catalogue and restorations.
- **Chart PDFs split across Letter pages** (Genealogy and Timeline Download → PDF): portrait for a tall chart, landscape for
  a wide one, filling the width inside half-inch margins and running onto as many pages as the chart needs.
- **Genealogy, full width.** The tree takes the whole page; the side panel is gone. Clicking anyone opens a card
  under the tree: portrait, name, dates, each relationship inline with its evidence tier (documented, told, family
  lore, unconfirmed, my edit), and *Centre the tree here*, their sources, *In a story* and *Open Familypedia article*.
  The evidence quotes and my edits (tiers, remove, name and dates, add a relationship, merge, split, note) fold open
  under the card. The card closes with ×. Clicking a person in the tree now opens the card rather than jumping to the
  article.
- **Unplaced** replaces the "Not in this view" card: people no evidenced link reaches, each with the reason (no
  evidenced link yet, or linked only outside this tree).
- **Genealogy toolbar:** Tree / Cast are a pair of icon buttons; the layout select is **Tree shape** (Hourglass,
  Ancestors only, Descendants only, Everyone); GEDCOM, SVG and PNG are one **Download** menu (PDF, PNG image, SVG
  vector, GEDCOM · for other software) beside **Print**. Zoom stays inside the tree frame, top right.
- **PDF downloads, with no library:** the chart is drawn to a canvas and written as a one-page PDF holding a JPEG
  (`app/static/js/exports.js`, shared by Genealogy and Timeline; the PNG export moved there too). Works in the
  published static snapshot. Very large charts are drawn at a lower scale rather than failing.
- **Timeline, simpler:** Highlights, Conflicts, Undated, SVG, PNG and Printable appendix are gone from the page (the
  data stays in the API); a **Download** menu (PDF, PNG image, SVG vector) takes their place. Home's "conflicting
  sources" link still opens the timeline filtered to conflicts, with a Show all button.
- **Timeline `updatedAt`:** `GET /api/engine/timeline` reports the newest input it read (events, stars, sources with
  photographs dated to events, stories, Familypedia inputs), shown as "Material last changed …". The timeline itself
  is never cached; `make test-timeline` (`app/tests/check_timeline.py`) adds a dated fact, a dated photograph and a
  star to a scratch copy of the demo and checks each appears and moves `updatedAt`.
- **Subscribe on Home** (published site only, using the existing `/updates/subscribe.js`): a band after Story of the
  day ("New stories, when there are new stories", with the project's family name), the form again at the foot of
  Home, and a quiet **Subscribe** link in the header that jumps to the band. Nothing shows where the script is absent
  (the local app).
- **One photo viewer, everywhere** (`app/static/js/photoviewer.js`): any photograph on the site — homepage gallery,
  All photographs, Familypedia articles and their profile photos, updates, story images, timeline entries — opens the
  same modal: the full-resolution image, a Restored | Original scan flip, badge, description, date, place, source
  (institution and catalogue reference), people and places (three, then "+ N more"), and every article, chapter and
  timeline entry it appears in. Previous/next with a counter, Open full size, a real Download, ←/→/Esc, focus trapped
  and returned. No file path or file name is ever shown, and nothing links to an image file.
- **The photo registry** (`app/photos.py`, `GET /api/engine/photos`, captured in the snapshot): one entry per
  photograph. A row in the photo index, an image in Sources, a chosen portrait, a lineage-assets copy, the
  unretouched original and its restoration collapse into one (`dedupKey`, `restorationOf`), so a photograph never
  appears twice in a grid. Facts come from the project only; an optional `data/photo_details.csv` (photo, title,
  description, date, place, institution, reference, url, kind) states them by hand.
- **Low-resolution backfill** (`plugins/lineage/scripts/photo_backfill.py`): for every scan under 1200 px it looks for
  the full-size file among the project's own files (mail attachments, archive downloads) and, where the source is the
  Internet Archive or the Library of Congress, re-fetches the largest image (robots.txt, 2 s per host). Restorations,
  print files and generated or stylised renderings never count. What can't be found is `not_located` and shows a red
  Low resolution badge and a line in the viewer. Never upscaled.
- **All photographs** (Familypedia · Photographs): cards with the badge on the image (Original, Restored, Low
  resolution), a serif title, date · institution, two people/place pills and "+N" for the full grouped list; filters
  for Portraits, Groups, Documents, Places, Restored and Low resolution; Select for bulk tagging. Illustrations are
  not photographs and are left out.
- **Familypedia** opens on People; tabs are People · Places · Photographs · Sources · Everything (then Events, Map).
- **Re-running the daily loop adds to today's post** (`macros/lineage-macros.md` §4.7–4.8): one post per day; a second
  run folds only the new findings into that day's post (title, summary and an `updated:` time cover the whole day),
  keeps every published sentence, and appends a `Run N` block to the private report. Nothing new: no republish.
- **Subscribe and Weekly Update in the Updates tab:** the tab opens with a Weekly Update button (newest `weekly-` post)
  and a Subscribe button that jumps to the weekly-digest form at the foot of the list. The form is the site's own
  `/updates/subscribe.js`, so it appears only on a published site with subscriptions configured.
- **The research loop as macros** (`macros/lineage-macros.md`): one readable file with the whole daily loop (scan mail,
  update each changed person, revise chapters and Familypedia pages by targeted edits, pursue leads, store, write a
  private report, publish a findings-only daily post, weekly digest), its rules and its privacy filter. Projects add a
  `MACROS.local.md` with their paths and settings; any agent runs it by reading the two.
- **Updates tab.** The dashboard's tab bar gains **Updates**: the project's posts (`posts/<slug>.md`, the same files the
  published site turns into `/updates/` pages), newest first, each opening in place at `#updates/<slug>`. Served by
  `GET /api/engine/updates` through `posts.py` (same parsing, image resolution and privacy rules) and captured into the
  published snapshot, so a family site shows its news inside the Lineage view. Research reports written as posts
  (the daily update) appear here.
- **Privacy filter for posts** (so for the weekly digest too, which only carries published posts). Every post is
  refused, with the reason, if it contains a term the project lists as private (`settings.publish.private_terms`, and/or
  `settings.publish.private_terms_file`, one per line — people to protect, case numbers, topics; whole words, any case),
  any sign of correspondence (e-mail header lines, quoted replies, mail or draft ids, a section about letters, e-mails
  or drafts), or a phone number. Posts report what was found, never who wrote to whom. Fix the post or mark it
  `draft: true`.
- **Digest off switch.** `settings.publish.digest.enabled: false` publishes posts, the feed and the subscribe form
  but leaves the weekly digest cron out of `vercel.json`, so no email goes to subscribers until it is turned back on.
- **Header on narrow screens.** The tabs move to their own scrolling row under the title (they were squeezed to nothing
  beside the Terminal and Settings buttons); on wide screens tab labels never shrink, the project path gives way first.

## 0.9.1 — 2026-10-13

**Alters generated stories: no** (the paragraph tool changes them only when run with `--fix`).

- **Private units.** A story unit whose front matter says `private: true` is skipped by the Familypedia, the timeline
  and every engine view, and the publishing step deletes it from the snapshot copy, so it is never published even as a
  raw file. For passages the family wants kept out.
- **Paragraph length** (`split_paragraphs.py`, style guide): prose paragraphs over 130 words are reported, and with
  `--fix` split at sentence ends outside quotations, words unchanged; wrapped lines never begin with Typst list or
  heading markup.

## 0.9.0 — 2026-10-12

**Alters generated stories: no.** New publishing scripts; templates, the book template, the style guides
and the skills are unchanged.

From a working family site, in generic form (no names, places, URLs or bucket names from that project).
Settings live in the project's `lineage.json` under `settings.publish`; every key is optional and a step
whose settings are missing is skipped with a message. Documented in HOWTO 6.11, "Publishing a family site".

- **chapter_pdfs.py**: every Typst story in `data/chapters.csv` as its own compressed PDF (Ghostscript
  /ebook, 150 dpi) in `chapters_dir`, through the project's `chapter_entry` wrapper or a generated one
  around Lineage's book template. Optional filter by file name.
- **book_edition.py**: `VERSION` (optional `--bump`), the whole book through Lineage's normal build or the
  project's `book_entry`, and a compressed edition `output/<slug>-v<VERSION>.pdf`.
- **r2_sync.py**: pictures and PDFs to Cloudflare R2 under `<prefix>/originals|restorations|illustrations|
  thumbnails|chapters|book/`, with illustrations recognised from the project's data, not from paths;
  writes `data/r2_manifest.csv` for `site/build_instance.py --assets`. `--dry-run` needs no credentials.
- **face_focus.py**: `data/image_focus.json`, face positions so cropped pictures centre on the face.
- **restore_photos.py**: classical photo restoration (and halftone descreening), originals kept in
  `_orig/`, logged in `data/image_restorations.json`.
- **seo_build.py**: static `/stories/`, `/stories/<slug>/`, `/family/`, `/family/<slug>/`, `sitemap.xml`
  and `robots.txt`, with schema.org data; curated articles rendered through `app/wiki.py`; people marked
  living left out unless `include_living` is set.
- **updates_page.py**: the project's `CHANGELOG.md` as `<site>/updates/index.html`.
- **image_manager.py drive-sync**: a folder holding a `.no-drive` file, and everything below it, is never
  uploaded.
- Makefile: `chapter-pdfs`, `edition`, `r2-sync`, `face-focus`, `seo`, `updates` (each with `PROJECT=`).

## 0.8.0 — 2026-10-12

**Alters generated stories: no.** New skills, a template and Familypedia behaviour; templates, the book
template and the style guides are unchanged.

From a working family book's research, in generic form (no names, places or material from that project):

- **Published sources** (skill `published-sources`). Rights before any download: US public domain
  before 1930; 1930–63 only if not renewed (check the Copyright Office public records for an `RE…`
  renewal and the Stanford renewal database or the Catalog of Copyright Entries); stop and report when a
  renewal is found. Borrowed (lending-library) copies are read, never captured. Ingest as a secondary
  source: reading notes with printed page numbers, a dated-events table, a quotations file graded by
  rights (public domain quoted freely; in copyright paraphrased, quotations under 15 words), timeline rows
  citing the page, a `book` row in `facts/records/<person>/sources.csv` with no file path for in-copyright
  books (the private copy stays outside git and the datastore).
- **archive-open-book** (skill and `plugins/lineage/scripts/archive_open_book.js`). Saves an open Internet
  Archive item as a PDF (Text PDF preferred; page-image fallback with Playwright for open items without a
  PDF) and exits 2 for lending-library, print-disabled, access-restricted or dark items.
- **Familypedia: curated articles for any subject.** `data/wiki/<slug>.md` now renders for organizations,
  places, events and other subjects (named by title), not only people; `[[Name]]` links in articles open
  the matching subject before falling back to the genealogy view; hand-added subjects live in
  `data/familypedia/subjects.json`. Documented in HOWTO 5.3.
- **Digitization work spec** (`templates/digitization/SCANNING-WORK-SPEC.md`): what to scan in a family
  home and at a museum, resolutions and formats, naming, a catalogue that feeds `data/archives.csv`,
  handling and confidentiality, and where to find someone to hire.
- **CSV files are written with LF line endings** (`dossier.py`, `image_manager.py`, `export_sources.py`,
  `_project.py`, `demo_lineage.py`): Python's default CRLF made every rewrite of a CSV show as a change to
  every line.

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
