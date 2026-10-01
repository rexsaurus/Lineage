---
name: family-history-chapters
description: Writes the family-history chapters of a BookAssembler biography — one chapter per named relative or ancestor the subject talks about, keeping every fact in one tier (witnessed by the subject, told to the subject by someone named, or family lore), naming the chain of telling, setting documents beside the family's version and saying plainly where they disagree, with a line-of-descent box, optional epigraphs, research from census, military, newspaper, ship and museum records, and a sourced THE RECORDS section. Use this whenever the user mentions ancestors, grandparents, great-grandparents, family origins, where the family came from, genealogy, a line of descent, the family tree, or the "those who came before" part — even if they only ask "what did Grandma say about her grandfather".
---

# Family History Chapters

Stories about people nobody alive has met are the most fragile part of the book: usually
secondhand, sometimes contradictory, and once printed they become "what happened". The job
is to preserve them vividly **and** honestly: told in the third person, with the subject's
own words quoted, the chain of telling kept visible, and the record set beside the lore.

All memoir-style-guide rules apply. This skill adds the family-history rules. A finished
ancestor chapter is annotated in `docs/EXAMPLE-CHAPTER.md`: copy its density and order.
Examples here are invented (subject Ruth Calder, ancestor Tobias Calder).

**Pipeline fit:** family material is written as story units (content-separator) with
`part: family`, `section: <relative's name>` and `tier`; chapter-generator assembles them.
Read first: `book.yaml` (`family_figures`), `transcript/master.md`, ancestor rows in
`facts/timeline.csv`, `facts/glossary.md`, `facts/records/`, `photos/photo_index.csv`.

## 1. Find every figure
Scan the whole transcript for people from earlier generations, named or not ("my mother's
people", "the uncle who went to Oregon"). Start with `book.yaml` → `family_figures` and add
anyone with at least one real story. Work out each relationship **from what the subject
says**; if the tape doesn't settle it (grandfather or great-uncle?), it goes in
`facts/gaps.md`. Never guess a relationship.

## 2. Profile per figure
`facts/people/<slug>.md`:
```markdown
# Tobias Calder
Relationship to the subject: great-grandfather [S1 00:02:40]   (or: UNCONFIRMED — ask)
Also called: "the old man"
Dates: born about 1840 (derived: …) · died 1911 (record R007)
Chain of telling: Tobias → his grandson Walter (Ruth's father) → Ruth

## Witnessed by the subject
## Told to the subject (by whom)
- Ran a canal boat before the war — told by her father [S1 00:05:02]
## Family lore (source unclear)
- Supposedly won the boat in a card game [S1 00:06:30] — "that's what they always said"
## Documents
- 1870 census, Millbrook: "boatman", age 30 (R012, URL)
## Conflicts (family vs record)
## Photos
## Open questions
```

## 3. Chapter structure
- **One chapter per named relative, titled with just the name** ("Tobias Calder").
  Relatives with little material share a closing chapter, **"Others in the Family"**, each
  with a `== Name` heading. If a named figure has almost nothing, write the short honest
  version and tell the author rather than padding.
- Default placement: a part titled "Those Who Came Before", oldest generation first (the
  author may move it; record the decision in `data/chapters.csv`).
- Header as in the style guide §6: name, setting · dates, a short poetic summary line,
  optional epigraphs.

### Opening the chapter
The first paragraph (with the drop cap) **says plainly what kind of material this is**,
witnessed, told to the subject, or family lore, **and who it passed through on the way**:
"What the family knows of Tobias Calder came down by word of mouth, from the old man to his
grandson, and from him to Ruth." Then, in the opening section, the chapter states:
**"Where the records and the family part company, this chapter says so."**
Use a "great-great-" phrase once; after that, names.

### Line of descent
A **LINE OF DESCENT** box on the opening page, `#descent(...)`: the generations from the
earliest known ancestor down to the living family, **marriages included**, built only from
documented facts and names the author has confirmed, **unconfirmed links marked**:
```
#descent(
  ([Tobias Calder (c. 1840–1911)], [Hannah Pratt]),
  ([Walter Calder], [Edith Moss (link unconfirmed)]),
  ([Ruth Calder], none),
)
```
Put it in the first unit's Shaped text, right after the opening paragraph.

## 4. The three tiers and the chain of telling
- **Every fact sits in exactly one tier: witnessed / told by X / lore.** The unit's `tier`
  is the dominant one; mixed passages say the tier in the prose.
- Keep the chain visible: "According to Ruth's father, Tobias came west with nothing but a
  mule", not "Tobias came west with nothing but a mule." Quote the subject where the
  telling is the point ("That's what they always said," she'd add).
- Lore stays lore: keep the hedges ("I don't know if it's true").

## 5. Records beside the family's version
Research beyond the tape **is allowed** in these chapters: census, military rosters and
pension files, museum and library catalogues, newspapers, ship registers and crew lists,
period books. **Every documented claim is cited in THE RECORDS** (records-archives).
- **Check the records first.** Museums, archives and rosters often hold the person.
- **Tell the life once, in order, with the record as the spine.** Where the family's
  version differs, tell it at that point in the timeline, attributed ("The family
  remembered his war differently…"). Never tell the same years twice (a separate "what
  the records say" pass reads as chunky), and never silently merge the two.
- **Where documents and the family disagree, print BOTH and say so.** Never silently correct
  the family story, and never silently repeat it. Note the conflict in `facts/gaps.md` and
  `// REVIEW:`. Dates in narration follow the record where one exists, with the family's
  date given as theirs.
- The record may answer the family where it can ("The bounty, though, was real").
- **Honest gaps, said out loud:** "Which route the boat took that winter, no surviving
  record says." Don't fill gaps; don't give an ancestor a famous battle, ship or event their
  unit or crew did not have.
- **Disambiguate** anything a record could confuse (two vessels of the same name, two men
  of the same name): say which is which in the text if it matters and always in a "note on
  the name" entry in THE RECORDS.
- Verify notes pasted in by anyone before using them; record what was and wasn't confirmed
  in `facts/records/<person>/`.

## 6. Building out an episode from the record
When a record-backed episode (a voyage, a regiment, a mill town) deserves more than a line:
1. **Research into fact sheets first:** `facts/records/<person>/context_<topic>.md`, one fact
   per bullet with URL, page and a confidence note. Parallel research agents, one per topic,
   work well. Then write from the sheets, never from memory.
2. A built-out episode contains:
   - **the thing itself**, in numbers from the record (tonnage, crew size, regiment strength,
     "twenty-seven, married, paper-maker");
   - **daily life** in concrete, checkable specifics (quarters, food, work, pay, disease),
     with period writers quoted briefly and named in the text;
   - **the wider moment, dated against the ancestor's record**: what happened those same
     months. Juxtaposition, never causation; a coincidence is called a coincidence and
     flagged `// NOTE:`;
   - **the ancestor's own documents as the thread**: letters, rosters, newspaper sightings
     put them at a place and date. A letter's catalogue entry *names* things; what it *says*
     is unknown until read ("names", not "reports"; `// REVIEW:`);
   - **what became of it** (the ship's or regiment's end) in its place in the timeline.
3. Concrete numbers over adjectives; every added sentence has a `// context:` line.
4. Conflicting figures get safe wording ("more than five hundred") and a `// NOTE:`.
5. Keep the proportion: each paragraph still comes back to where the ancestor was.

## 7. Ending the chapter
Closing paragraph (style guide §6) → **THE RECORDS** (`#records`, records-archives) →
**the photographs page** (`#photo-addendum`, photo-processor) listing real photographs held
by archives. Put these in a final **apparatus unit** for the chapter (`kind: apparatus`,
same `section`, highest `order`, no spans) so they survive reassembly.

## 8. Illustrations of ancestors
Usually no photograph exists. AI or artist's illustrations are allowed only under the
photo-processor rules: captions marked ("as the family told it" / "illustration"), a note in
the chapter saying they are renderings and what likeness or source they were based on,
scenes from the material only, and the distinction kept in print.

## 9. Family tree (optional)
From confirmed relationships only, as an indented list or table in a back-matter file;
unconfirmed links shown "?" or left out. Show the author the draft first.

## 10. Report
Figures found and confirmed relationships; chapters proposed; words per figure; tier
breakdown; family-vs-record conflicts; records consulted; open questions batched for the
author. Update `data/chapters.csv` and add ancestor events to `facts/timeline.csv`.
