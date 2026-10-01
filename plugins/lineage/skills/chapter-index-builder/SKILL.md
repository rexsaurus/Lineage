---
name: chapter-index-builder
description: Plans and maintains a Lineage book's chapter map and all its finding aids — proposes the chapter layout from the timeline and transcript (family-history chapters per relative, chronological life chapters), keeps the chapter spreadsheet (titles, setting and dates, summary lines, columns, events, people, places, sources, word and image counts, status), checks transcript coverage, writes chapter summaries, builds the per-chapter index, and sets the conventions for #idx marks that generate the back-of-book index with real page numbers. Use this whenever the user asks about chapters, chapter order, the outline, table of contents, splitting or merging chapters, summaries, what's in a chapter, the index or index terms, or the chapter spreadsheet — even if they just say "how should the book be organized".
---

# Chapter Map & Index Builder

Owns the book's skeleton (which stories go in which chapter, in what order) and its finding
aids (summaries, chapter indexes, the back index).

## Files
```
data/chapters.csv        source of truth for the chapter map
data/chapter_index.csv   per-chapter names/places/events (from #idx marks)
data/back_index.csv      resolved page numbers from the last build
output/chapters.xlsx     tabs: Chapters · Key Events · Chapter Index · Back Index
```
Reads: `book.yaml`, `transcript/master.md` (topic outlines), `facts/timeline.csv`,
`facts/glossary.md`, `content/units/`, `photos/photo_index.csv`, `chapters/*.typ`.

## 1. Propose the chapter map
Work from the timeline and the units, not from the order things were said.
- **Family history first**, as a part ("Those Who Came Before"), unless the author prefers
  it at the back: **one chapter per named relative, titled with just the name**; relatives
  with little material share **"Others in the Family"** (family-history-chapters).
- **Life chapters: chronological** through the subject's life, one stage or place each.
  A theme spanning decades can be its own chapter, placed where it peaks.
- **Size to the material.** Aim for roughly 1,000–2,500 words of the subject's speech per
  life chapter; under ~600 merge with a neighbour, over ~3,000 split at a natural turn.
  A relative's chapter can be a page.
- **Titles:** plain stage or place names, or a phrase the subject said.
- **Columns:** `1` for narrative chapters, `2` for research-dense ones (records, lists of
  ships and regiments).

Write the proposal into `data/chapters.csv` with `status: proposed` and show the author a
simple outline (number, title, setting, years, one line each, main sources). **This is
GATE 2: nothing is shaped or assembled until the author approves the map.**

### chapters.csv columns
| column | content |
|---|---|
| chapter / number | order / printed number (family part numbered first) |
| file | `chapters/03-the-mill-years.typ` |
| title, part | chapter title; part name |
| setting, dates | place-and-years line for the opener ("Millbrook, Ohio", "1934–1952") |
| date_range | from the timeline (fallback for `dates`) |
| summary_line | short poetic line for the opener ("On Looms, Floods and Such"), never a list |
| summary | 2–4 neutral sentences for the spreadsheet and introduction |
| epigraph, epigraph_source | optional, verified (style guide §2b) |
| columns | 1 or 2 |
| contents | optional "in this chapter" line |
| key_events | timeline IDs `E004; E007` |
| people / places | glossary spellings, `;`-separated |
| sources | transcript spans used |
| photos | image IDs placed |
| word_count / photo_count | filled by `index_tools.py wordcount` |
| status | proposed · approved · drafted · reviewed · final |

After approval, write each event's chapter number back to `facts/timeline.csv`; every event
gets a home or a recorded decision to leave it out.

**Coverage check:** every minute of the subject talking falls in some unit or in
`content/excluded.md` (`units.py coverage`, content-separator). List gaps for the author.

## 2. Summaries
For each drafted chapter, 2–4 sentences, neutral, third person, past tense, naming key
people, places and years. They describe; they don't interpret or praise.

## 3. Marking index terms
Index terms are marked **in the text as it is written**, with `#idx(...)` right after the
word (invisible in print). The index is generated with real page numbers at build time.
```
Her great-grandfather Tobias#idx("Calder, Tobias") ran a canal boat.#idx("canals")
```
- **People:** "Surname, Given (Nickname)". Women under the name the family uses, with a
  cross-reference: `#idx-see("Pratt, Hannah", "Calder, Hannah (Pratt)")`. Family names
  ("Grandpa Walt") get a see-reference once.
- **Places:** "Town, State"; sub-entries with `!`: `"Millbrook, Ohio!Elm Street house"`.
- **Organizations and events:** "U.S. Army", "Flood of 1937".
- **Topics** sparingly: only what a relative would look up.
- First mention per paragraph, not every mention. Names in confirmed captions get `#idx`
  beside the plate. Spellings from `facts/glossary.md` (add missing ones).

## 4. Per-chapter index
```bash
python .claude/skills/chapter-index-builder/scripts/index_tools.py terms
```
Builds `data/chapter_index.csv`: per chapter, every indexed term, its count and citations.
Feeds the optional `contents` line when `print.in_chapter_contents: true`.

## 5. Back-of-book index
`#make-index()` at the end of `book/main.typ` computes page numbers during typesetting, so
it stays correct whenever pages shift. After a build:
```bash
python .claude/skills/chapter-index-builder/scripts/index_tools.py backindex
```
Review `data/back_index.csv` for duplicate spellings, entries with more than ~15 page refs
(split into sub-entries), orphan see-references, trivial single mentions.

## 6. Spreadsheet and report
```bash
python .claude/skills/chapter-index-builder/scripts/index_tools.py wordcount
python .claude/skills/chapter-index-builder/scripts/index_tools.py xlsx
```
Report: chapter count, words per chapter, chapters by status, coverage gaps, unplaced
timeline events, index problems.
