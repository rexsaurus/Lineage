# This is a Lineage project

## Where things go (read first)
This project **uses** Lineage; it is not a copy of it.
- **Platform changes go to the Lineage repo**, never here: style guides, story templates,
  skills, the dashboard, scripts, the pipeline. They are released there as a tag and reach this
  project through `make update-lineage`. Never fix platform code only in this project.
- **This project holds only its own material**: sources, transcripts, story units, stories,
  people, records, photos and its settings (`book.yaml`, `lineage.json`, `lineage.lock`).
- **Genuinely one-off things** (a story template or caption convention nobody else would want)
  go in `local-overrides/`, and you say so each time you put something there.
- **When a request would cross the line**, say where it belongs first. If it is a platform
  change, make it in Lineage, release it, then `make update-lineage APPLY=1` here; don't patch
  the local copy.
- `make lineage-version` shows the pinned release; `make dashboard` opens the dashboard.

A family's lineage: its sources, records, genealogy, timeline and Familypedia, with stories and
a book as exports. The tools and rules live in the Lineage repo ($LINEAGE); the skills are
linked into `.claude/skills/`.

Run repo tools with the Lineage Python: `source $LINEAGE/.venv/bin/activate` at the
start of a session (or call `$LINEAGE/.venv/bin/python <script>`).

Before any writing, read `.claude/skills/memoir-style-guide/SKILL.md`. Start every session with
`make status PROJECT=.` (from $LINEAGE) or
`python .claude/skills/book-generator/scripts/pipeline.py status`, and resume at the first
incomplete stage (book-generator skill).

Standing rules (details in the skills):
- `book.yaml` is the source of truth for names, the subject's birth year, and print settings.
- Originals (`audio/`, `photos/source/`) are never modified. Raw transcripts are never edited;
  fixes go in `transcript/corrections.json`. Once timestamps are cited, never re-run
  speech recognition (`transcription_locked: true`).
- Chapters are generated from story units. Edit `content/units/`, then reassemble.
- Third person about the subject; no interview format; quotes exact; every paragraph cites
  its timestamps with `// src:`; interpretation goes in `#bridge[...]` for the author.
- Three gates where you stop and wait for the author: speaker confirmation, chapter-map
  approval, final sign-off.
- Never send the author's personal details (email, phone) to any outside service.
