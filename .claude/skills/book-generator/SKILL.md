---
name: book-generator
description: The BookAssembler orchestrator — runs every book skill in order to turn recorded interviews into a print-ready PDF (transcription, timeline, story units, chapter map, shaping, chapter assembly, images, records, reader glossary, about-the-recordings page, front matter, contents, index, build and preflight), stops at the three approval gates, and versions inputs in git and outputs as manifest-pinned snapshots. Knows which stages are done and what's next. Use this whenever the user asks to generate, build, rebuild, compile or finish the book, asks "where are we", "what's next" or "run the pipeline", wants a version or a copy to send someone, or changes something that should flow through to the PDF — even if they just say "make the book".
---

# Book Generator

One entry point that drives the other skills in sequence. At each stage, read and follow
that stage's own SKILL.md. This skill decides **what runs next, when to stop for the
author, and how the pieces become one versioned book**.

All commands run **from the project folder** (made by `make -C "$BOOKASSEMBLER" new
PROJECT=~/books/<name>`), with the repo's venv (`$BOOKASSEMBLER/.venv`, from `make install`).

## Always start with status
```bash
python .claude/skills/book-generator/scripts/pipeline.py status
```
Prints each stage done (✓) or not (·) and the next action. Resume from the first
incomplete stage; don't redo finished stages unless their inputs changed (see Reruns).

## Stages
| # | Stage | Skill | Produces |
|---|---|---|---|
| 1 | Transcribe & label | interview-transcriber | `transcript/clean/S*.md`, `master.md`, `sessions.csv`, glossary — **GATE 1** |
| 2 | Timeline | timeline-organizer | `facts/timeline.csv` |
| 3 | Separate stories | content-separator | `content/boundaries.csv`, `content/units/U*.md` |
| 4 | Chapter map | chapter-index-builder | `data/chapters.csv` — **GATE 2** |
| 5 | Shape units | content-separator + memoir-style-guide (+ family-history-chapters, records-archives for the family part) | units at `shaped` |
| 6 | Assemble chapters | chapter-generator | `chapters/NN-*.typ` |
| 7 | Images (if any) | photo-processor | plates, `photo_index.csv` |
| 8 | Records appendix | records-archives | `chapters/91-where-the-records-are.typ` |
| 9 | Reader glossary | this skill | `data/reader_glossary.csv` → `chapters/92-glossary.typ` |
| 10 | Timeline appendix | timeline-organizer | `chapters/90-timeline.typ` |
| 10b | Introduction | foreword-generator | `book/front/introduction.typ` |
| 11 | Front/back matter, main file, draft, index | this skill + book-layout + chapter-index-builder | `output/book-draft.pdf`, `data/back_index.csv` |
| 12 | Final | book-layout | `output/book-final.pdf` — **GATE 3** |

## The three gates — stop and wait for the author
1. **Speaker confirmation** (after stage 1): which speaker label is the subject and which
   the interviewer, confirmed from sample turns, plus `book.yaml` basics (name, birth year).
2. **Chapter-map approval** (after stage 4): send the outline; don't shape or assemble until
   every row's `status` is past `proposed`. Shaping against the wrong structure wastes the
   most work.
3. **Final sign-off** (stage 12): only when the author says it's final. The final build fails
   on any unapproved `#bridge`; that's intended. Before it, send the draft PDF with every
   `#bridge`, `// REVIEW:` and open question.

Between gates, run straight through. Collect questions and deliver them at the next gate
in one batch.

## Versioning
Every PDF that leaves the project can be traced to the exact text that produced it.
```bash
python .claude/skills/book-generator/scripts/version.py init      # once: git, .gitignore, originals checksums
python .claude/skills/book-generator/scripts/version.py snapshot "chapter map approved"
python .claude/skills/book-generator/scripts/version.py snapshot "review copy for the family" --major --note "mailed Oct 6"
python .claude/skills/book-generator/scripts/version.py list
python .claude/skills/book-generator/scripts/version.py diff v1.0 v1.3
python .claude/skills/book-generator/scripts/version.py show v1.0 -- content/units/U014-the-flood.md
```
- **Inputs in git with tags**: book.yaml, transcripts, facts, units, data, chapters, book/,
  `photos/photo_index.csv`. Commit at the end of every stage with a plain message.
- **Outputs snapshotted**: each snapshot tags the inputs (`v0.3`) and copies PDFs and
  spreadsheets to `output/versions/v0.3-<label>/` with a `MANIFEST.json` **pinning the exact
  input commit** (plus output checksums and page/word/bridge counts); `CHANGES.md` gets a line.
- Snapshot at every gate (minor version) and **always a major version (`--major`) before
  anything is sent to anyone**: a family review copy, a proof order, the final print.
  Feedback ("page 41, line 3") only makes sense against the exact version received.
- **Originals are never modified; checksums are recorded.** `audio/` and `photos/source/`
  are never edited; `init` records their SHA-256 and `snapshot` stops if one changed. With
  `transcription_locked: true` in book.yaml, `transcript/raw/` is protected the same way.
- `output/`, `audio/`, `photos/source/`, `photos/print/` stay out of git (large); back up
  `output/versions/` and the originals somewhere safe after each major version.
- Never rewrite history or move a tag that has been sent to someone. Never commit secrets
  (`.env`, tokens, `HF_TOKEN`).

## Stage 9: reader glossary
For readers decades from now, separate from the internal spelling list `facts/glossary.md`:
terms in the book a future reader might not know: places, things, organizations, period
terms, family nicknames. One or two plain sentences each; if unsure, leave it out.
`data/reader_glossary.csv`: term, definition, first_chapter.

## Stage 11: assemble the book
```bash
python .claude/skills/book-generator/scripts/build_book.py sync   # refresh book/template.typ from $BOOKASSEMBLER/book
python .claude/skills/book-generator/scripts/build_book.py all    # front, glossary, about-the-recordings, main.typ, draft PDF
python .claude/skills/chapter-index-builder/scripts/index_tools.py backindex
python .claude/skills/chapter-index-builder/scripts/index_tools.py xlsx
python .claude/skills/book-layout/scripts/preflight.py output/book-draft.pdf --trim <trim> --printer <printer> --color <color>
```
(`make -C "$BOOKASSEMBLER" draft PROJECT="$PWD"` / `final` wrap the build.) `build_book.py`
generates the title and copyright pages from `book.yaml`; a placeholder dedication until the
author writes `book/front/dedication.typ`; **About the Recordings** from
`transcript/sessions.csv`; and `book/main.typ` from `data/chapters.csv`: front matter with
roman folios, parts and chapters with arabic folios from 1, then the back matter (timeline,
glossary, where the records are, about the recordings, acknowledgments) and the index,
padded to an even page count. Never hand-edit `book/main.typ` or GENERATED chapter files.

After building, look at: title page, contents, a part page, two chapter openers, a spread
with a plate, the index. Fix anything wrong at its source.

## Reruns
| Change | Rerun from |
|---|---|
| spelling fix | add to `transcript/corrections.json`, re-render (interview-transcriber), grep units → 6 → 11 |
| new recording | 1 for the new session only → 2 → 3 for it → 5 → 6 → 11 |
| chapter moved, split or merged | `chapters.csv` + unit `chapter`/`order` → 6 → 11 |
| unit edited or bridge approved | 6 → 11 |
| images added | 7 → 11 |
| `book.yaml` title or names | 11 |
| chapters, sessions or images changed | re-run foreword facts, fix the introduction → 11 |

**Never re-run ASR on a session whose timestamps are cited**; it shifts every timestamp.

## Report at each gate
Snapshot first and give the version number. Then: pipeline status, what changed since last
report, page count, words per chapter, pending bridges and REVIEW flags, and the batched
questions.
