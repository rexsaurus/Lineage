# Changelog

Each release is a git tag (`vX.Y.Z`). Projects record the version they run in `lineage.lock`.
Every entry says whether it changes anything that would alter already-generated stories
(templates, the book template, style guides, skills); when it does, a project updating to it
marks those stories stale rather than regenerating them.

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
