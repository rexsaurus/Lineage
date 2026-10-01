---
name: content-separator
description: Splits a lineage's interview transcripts into self-contained story units — one file per story or memory, with the exact clean source excerpt, metadata (people, places, dates, era, family figure, tier) and a shaped third-person narrative about the subject with their own words as exact quotations, following the style guide. Units are the raw material every story and chapter is generated from (so stories can move between chapters without rewriting), and their people, places and subjects tell the Familypedia which passages concern which article. Use this after transcription and the timeline, whenever the user asks to separate, extract, pull out, clean up or shape the stories, turn the transcript into narrative, find all the stories about someone or some place, or when a new session is added — even if they just say "get the stories out of the interviews".
---

# Content Separator

People tell stories out of order, in pieces, sometimes twice. This skill turns hours of
talk into a stack of **story units**: one file per story, with its source excerpt, its
metadata and a shaped narrative, tagged so it can drop into any chapter.

**Units, not chapters.** Chapter boundaries will move (a life stage splits in two, a
relative gets their own chapter). Because chapters are generated from units
(chapter-generator), a move is a metadata change and a reassembly, not a rewrite. All
editing happens in units.

Read first: `book.yaml`, `transcript/clean/*.md`, `facts/timeline.csv`,
`facts/glossary.md`, and the **memoir-style-guide** and **family-history-chapters** skills.

## Output
```
content/boundaries.csv   unit cut points (source of truth for separation)
content/units/U001-the-flood.md
content/excluded.md      transcript spans deliberately left out, with the reason
content/units.csv        summary table (generated)
```

## 1. Find the story boundaries
Read each session straight through. A unit is **one story, memory or explanation that
stands on its own**. Signals of a new one: a question that changes subject, a jump in time
or place, "and another time…", "that reminds me…". Typically 1–5 minutes of tape.
- Record each cut in `content/boundaries.csv` (the first subject paragraph of each unit,
  with id, working title, part, section/era, tier, people, places, events, flags; `X` for
  excluded spans with a reason), then generate unit skeletons with their exact Source
  excerpts: `$LINEAGE/scripts/make_units.py`. Cutting at boundaries makes coverage
  exact by construction.
- A story told in pieces (starts in S1, finished in S5) is **one** unit with several spans.
- A story told twice is one unit; list both tellings in `spans`, shape the fuller one, and
  note differences under `## Notes` (the timeline records any conflict).
- Non-content goes to `content/excluded.md` with a reason: warm-up, tech trouble, off-mic
  interruptions, wrap-up logistics, and ASR prompt echoes.

## 2. Unit file format
```markdown
---
id: U014
title: The flood                       # working title, not printed
part: life                             # family | life
section:                               # family part: the relative's name (their chapter)
era: mill-years                        # life part: the stage of life
kind: story                            # story | apparatus (THE RECORDS / photographs page; no spans)
spans: ["S5 00:12:10-00:15:40", "S1 00:22:10-00:22:55"]
date_display: spring 1937              # from the timeline, never more precise
timeline_events: [E004, E005]
people: ["Calder, Walter"]
places: ["Millbrook, Ohio"]
tier: witnessed                        # family part: witnessed | told | lore
chapter:                               # filled once the chapter map is approved
order:
lead_in:                               # optional connective text; a #bridge until approved
break_before: true                     # ❧ section break before this unit
flags: []                              # e.g. ["REVIEW: a living relative's illness"]
status: separated                      # separated → shaped → approved
---
## Source
**Grandma** [S5 00:12:10] (clean transcript excerpt, copied exactly, questions included)

## Shaped
(third-person narrative per the style guide, // src: after every paragraph)

## Notes
(differences between tellings, questions for the author)
```
IDs are permanent; new units take the next number. Slugs may change.

## 3. Shape
Turn `## Source` into `## Shaped` exactly per memoir-style-guide:
- **Third person, past tense, about the subject**; the author never appears.
- **No interview format.** Questions never appear; fold a question's content into the
  subject's answer as a standalone statement and cite both timestamps. A bare "yeah" to a
  leading question is flagged, not stated.
- **Quote the subject**: one or two exact quotes per page's worth, especially verdicts,
  humor and punchlines; 40+ words as `#verbatim[...]`; fillers and false starts removed,
  "…" for cuts, grammar and dialect kept. Never invent or tidy a quote.
- Put the story in order, joining pieces from several spans, as one finished piece of
  narrative with every detail given across all tellings.
- Nothing added: no feelings, motives, weather, sensory detail or dialogue. Plain
  transitions are fine (`// src: transition`); interpretation goes in `#bridge[...]`;
  context about the world only with `// context:` and a source (style guide §2a).
- Hedges carry over; never firm up a date.
- Family-part units keep the chain of telling and their tier (family-history-chapters).
- Mark index terms with `#idx(...)` at first mention in each paragraph.
- `// src:` after every paragraph.
- **Sensitive material** (living people's legal, health or family trouble, violence,
  trauma) gets a `flags` entry and `// REVIEW:`. Shape it faithfully; never cut or soften.

Set `status: shaped`. Only the author sets `approved`.

## 4. Check coverage
```bash
python .claude/skills/content-separator/scripts/units.py check
python .claude/skills/content-separator/scripts/units.py coverage
python .claude/skills/content-separator/scripts/units.py table
```
`check` catches missing fields, uncited paragraphs and interview format in Shaped text.
`coverage` lists every paragraph of the subject (speaker `book.yaml` → `narrator.label`)
that is in no unit and not excluded. The goal is zero: every minute of the subject talking
is either in the book's raw material or consciously set aside.

## 5. Report
Units by part/era/figure, shaped word count, excluded spans with reasons, flagged units,
retold stories, and questions for the author.
