# This is a BookAssembler project

A book written from recorded interviews with a relative. The tools and rules live in the
BookAssembler repo ($BOOKASSEMBLER); the skills are linked into `.claude/skills/`.

Run repo tools with the BookAssembler Python: `source $BOOKASSEMBLER/.venv/bin/activate` at the
start of a session (or call `$BOOKASSEMBLER/.venv/bin/python <script>`).

Before any writing, read `.claude/skills/memoir-style-guide/SKILL.md`. Start every session with
`make status PROJECT=.` (from $BOOKASSEMBLER) or
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
