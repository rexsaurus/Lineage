# The book swarm: a full first pass of the whole book

Most of the time Lineage works one stage at a time and stops at the author's gates
(book-generator skill). Sometimes the author wants to see the whole book at once: every
chapter researched, written, edited, judged and sourced, then assembled, so they can read it
end to end and say what to change. That is a **full first pass**, and the book swarm is the
recipe for it. It was worked out on a real family's book (a twelve-chapter biography built
from about four hours of interviews) and is written here without anything of theirs.

Run it **only when the author asks for it**, after the chapter map is approved (GATE 2). It
ends at a gate: the author reads the assembled book before anything is final.

## The shape

```
for each chapter (in parallel, each on its own track):
  research ─┬─ records and people   (primary records; for anyone who served, the service-record process)
            └─ place and period     (local history in its exact years, first-hand voices, epigraph candidates)
  → writer        (the chapter, to the page minimum, from the dossier and the fact sheets)
  → editor 1      fidelity: every sentence against the tape and the sources
  → editor 2      taste: as the author reads (chronology, tone, the dossier's requests)
  → editor 3      layout: build, look at every page, fix plates and stranded lines
  → two judges    independent, scored 1-10 on seven axes; revise and re-judge until the
                  average passes (default 8) and nobody hard-fails, at most two rounds
  → sources       100% of sources into the dossier; THE RECORDS regenerated and checked
then, once:
  front and back matter · images plan · index marks   (in parallel)
  → assembly (make draft) → whole-book continuity review (REVIEW.md for the author)
```

Two judges with different lenses matter: one is a fact-checker who reads the transcript and
the records, the other reads as the author (an engrossing, accurate book; every request in the
chapter's dossier honoured). A **hard fail** (under the page minimum, the build or quote check
failing, an invented fact, a bare-quote ending, an ignored request) blocks a pass whatever the
average.

## What every agent is told

- Read the project's `CLAUDE.md` and `local-overrides/` first; they win.
- Read the skills: memoir-style-guide (the master rulebook), family-history-chapters,
  records-archives, photo-processor, chapter-dossier; then the chapter's dossier.
- Nothing about the family that isn't on tape or in a cited record; quotes exact; bridges for
  anything interpretive; context sourced and never about anyone's thoughts; no "general
  knowledge" sources; doubts as `// REVIEW:`, never guesses; sensitive record entries out of
  the prose until the author decides; the transcription is locked.
- Research politely (robots.txt, 2 s per site, a project-only User-Agent, no logins, no bot
  checks, no harvesting); what can't be reached goes on `research/MANUAL-LOOKUPS.md`.
- Shared files (`book/template.typ`, `photos/photo_index.csv`, `data/chapters.csv`, other
  chapters) are not edited by chapter agents; frozen chapters are never edited.
- Images are planned, not generated: the main session runs `generate_images.py` afterwards,
  so the author can look at the plan first.
- No git commits inside the swarm; the main session reviews and commits.

## Running it

The template is `plugins/lineage/templates/swarm/book-swarm.js`, a script for Claude Code's
Workflow tool. Everything specific comes from its `args`:

```json
{
  "project": "/abs/path/to/the/book",
  "scratch": "/abs/path/outside/the/book/swarm",
  "min_pages": 10, "pass_score": 8, "max_rounds": 2,
  "author": "Sam",
  "chapters": [
    { "n": 1, "slug": "anders-calder", "title": "Anders Calder", "part": "Those Who Came Before",
      "kind": "ancestor", "file": "chapters/01-anders-calder.typ", "units": "U001",
      "note": "the passenger list is the spine" },
    { "n": 2, "slug": "the-ore-dock", "title": "The Ore Dock", "part": "Her Life",
      "kind": "life", "file": "chapters/02-the-ore-dock.typ", "units": "U002 U003" },
    { "n": 3, "slug": "walt-and-the-cabin", "title": "Walt and the Cabin", "part": "Her Life",
      "kind": "life", "file": "chapters/03-walt-and-the-cabin.typ", "frozen": true }
  ]
}
```

Ask Claude in the project: "run a full first pass with the Lineage book swarm", give it the
arguments (or let it build them from `data/chapters.csv`), and it runs the template.

**Before you start**
1. Make a git worktree or branch of the project (`git worktree add ../book-first-pass -b
   first-pass`) and point `project` at it, so the pass can be read, kept or dropped whole.
2. Make a dossier for each chapter (`dossier.py new <slug>`) and put the author's requests in
   `DOSSIER.md`. Mark finished chapters FROZEN and `"frozen": true` in the args.
3. Check `book.yaml`: `chapters.min_pages`, `research.user_agent`, `transcription_locked: true`.

**After it finishes**
1. Read the scratch `REVIEW.md` and each chapter's notes; answer what you can.
2. Look at the images plan, then `generate_images.py --dry-run`, then generate.
3. `make draft`, and give the author the PDF with every `#bridge`, `// REVIEW:` and question.
4. Commit on the first-pass branch; the author decides what merges.

## Costs and limits

A twelve-chapter pass is a few hundred agent runs and several hours. Two chapters with deep
research (service records, war diaries, many first-hand accounts) can be built in a separate,
smaller run with the same stages. The judges' scores are a gate, not a guarantee: the author's
reading is the real test, and every lesson from it goes into the dossiers, the project's rules,
or (if any project would benefit) into Lineage itself.
