# Changelog

Each release is a git tag (`vX.Y.Z`). Projects record the version they run in `lineage.lock`.
Every entry says whether it changes anything that would alter already-generated stories
(templates, the book template, style guides, skills); when it does, a project updating to it
marks those stories stale rather than regenerating them.

## Unreleased (on `development`)

**Alters generated stories: yes**, for projects that use Lineage's skills: the writing rules
below changed. Projects that carry their own copies of the skills are not affected
(`lineage update` knows the difference).

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
