---
name: timeline-organizer
description: Converts a Lineage book's interview transcripts (and any cited records) into one sequential, sourced timeline of the subject's life and the family's past — resolving "when I was twelve" and "right after the war" into dates with the arithmetic shown, keeping hedged dates hedged, flagging conflicts between tellings or between the family and the records, and producing a timeline CSV, a decade-by-decade summary, a spreadsheet and the printed timeline appendix. Use this whenever the user asks for a timeline, chronology, dates, "what order did this happen", "how old was she when", wants to check a date or reconcile two stories, or when chapters need ordering or images dating — even if they don't say "timeline".
---

# Timeline Organizer

People don't tell their lives in order. The timeline puts every event on one line, with
each date showing how it was worked out, so chapters (which are strictly chronological),
captions and family-history chapters all agree.

## Files
```
facts/timeline.csv          source of truth
facts/timeline.md           decade-by-decade readable version (generated)
output/timeline.xlsx        spreadsheet (generated)
chapters/90-timeline.typ    printed appendix (generated)
```
Read `book.yaml` (birth year, family figures), `transcript/master.md`, `facts/glossary.md`,
`facts/records/` and `photos/photo_index.csv` if they exist.

## Columns
| Column | Meaning |
|---|---|
| event_id | E001… stable forever; never renumber |
| date_start / date_end | `YYYY`, `YYYY-MM` or `YYYY-MM-DD`; end only for spans |
| date_display | how the book says it: "1953", "about 1925", "early 1960s", "summer 1958" |
| precision | exact · year · approx · decade · derived · unknown |
| date_basis | **show the arithmetic**: "age 12 at [S1 00:10:02] + born 1931 → about 1943" |
| event | one short factual sentence, neutral third person |
| people / place | glossary spellings; `;`-separated |
| generation | ancestors · grandparents · parents · subject · children |
| source | every mention `[S1 00:10:02]; [S3 00:05:40]`, and/or record IDs (R012) |
| quote | ≤15 words of the subject's phrasing that pins the date |
| confidence | high · medium · low |
| conflicts | other events or tellings (or records) that disagree, and how |
| chapter | filled by chapter-index-builder |

## Workflow
1. **Extract.** Every discrete happening is a row: births, deaths, marriages, moves, jobs,
   schooling, service, illnesses, disasters, firsts, and stories about people before the
   subject was born (`generation: ancestors/grandparents`). Told twice → one row, both sources.
2. **Anchor.** Birth year, years said outright, events with fixed public dates (a named war,
   a famous flood). List anchors in `facts/timeline.md`.
3. **Resolve relative dates** against anchors and show the working:
   - "when I was twelve" → birth year + 12 (±1) → `derived`, display "about 1943"
   - "right after the war" → say which war and why; display "late 1940s"
   - public-history anchors are labelled `historical context` in the basis
   - **Never invent precision**: no month or day unless said or documented. **Hedges carry
     over** ("around 1972" stays around). A bare "yeah" to a leading question → low confidence.
4. **Conflicts.** Two tellings disagree, or the family and a record disagree → keep both in
   `conflicts`, confidence low, question in `facts/gaps.md`. Don't pick a winner silently;
   the book will print both (family-history-chapters).
5. **Sort, check, generate.**
   ```bash
   python .claude/skills/timeline-organizer/scripts/timeline_tools.py sort
   python .claude/skills/timeline-organizer/scripts/timeline_tools.py check   # fix everything it reports
   python .claude/skills/timeline-organizer/scripts/timeline_tools.py md
   python .claude/skills/timeline-organizer/scripts/csv_to_xlsx.py output/timeline.xlsx "Timeline=facts/timeline.csv"
   ```
6. **Report**: events by generation, date range, undated events, conflicts, questions.

## Printed appendix
```bash
python .claude/skills/timeline-organizer/scripts/timeline_tools.py appendix
```
Writes `chapters/90-timeline.typ` (show-rule chapter "A Timeline", one column) with high-
and medium-confidence dated events; book-generator puts it first in the back matter.

## Downstream
- chapter-index-builder orders chapters by these dates; chapter-generator orders units
  strictly by them.
- photo-processor checks image dates against it.
- family-history-chapters takes ancestor rows as its skeleton.
- Style rule: prose never states a date more precisely than `date_display`.
