---
name: family-history-chapters
description: Writes the family-history stories and chapters of a lineage — one chapter per named relative or ancestor the subject talks about, keeping every fact in one tier (witnessed by the subject, told to the subject by someone named, or family lore), naming the chain of telling, setting documents beside the family's version and saying plainly where they disagree, with a line-of-descent box or a small family tree, an epigraph, research from census, military service files, first-hand accounts, newspaper, ship and museum records, and a sourced THE RECORDS section. Use this whenever the user mentions ancestors, grandparents, great-grandparents, family origins, where the family came from, genealogy, a line of descent, the family tree, or the "those who came before" part — even if they only ask "what did Grandma say about her grandfather".
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
  version and tell the author rather than padding. A relative's chapter that can't reach the
  page minimum (style guide §6) with real material is **combined**: folded into "Others in
  the Family" or into the neighbouring generation's chapter, at its place in time.
- Default placement: a part titled "Those Who Came Before", oldest generation first (the
  author may move it; record the decision in `data/chapters.csv`).
- Header as in the style guide §6: name, setting · dates, a short poetic summary line,
  one epigraph (two allowed in a family-history chapter).

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

**Or a small family tree** when the author asks for one ("a little tree, three
generations"): `#family-tree(...)` at the foot of the same page, the ancestor's parents →
the ancestor and spouse (a note line for the spouse's parents if known) → their children in
birth order, with the line of descent continued under the right child ("and so to Ruth").
It stands in for `#descent` or sits beside it. Same rules: documented facts and confirmed
names only, unconfirmed links marked, approximate years as "c." (from census ages), and
every name cited in a `// descent:` comment.
```
#family-tree(title: "The Family of Tobias Calder",
  parents: ([Josiah Calder], [Mary Calder]),
  couple: ([Tobias Calder (c.1840–1911)], [Hannah Pratt (1844–1920)]),
  children: ([Walter (b. 1868)], [Mary (b. c.1870)]), line: 0, descent: [and so to Ruth])
```

## 4. The three tiers and the chain of telling
- **Every fact sits in exactly one tier: witnessed / told by X / lore.** The unit's `tier`
  is the dominant one; mixed passages say the tier in the prose.
- Keep the chain visible: "According to Ruth's father, Tobias came west with nothing but a
  mule", not "Tobias came west with nothing but a mule." Quote the subject where the
  telling is the point ("That's what they always said," she'd add).
- Lore stays lore: keep the hedges ("I don't know if it's true").
- **Two tellings by the subject:** don't resolve them in the prose. If they told it both
  ways, the book holds both, each attributed to its session.
- The author may add a short italic introduction to the part or a chapter, marked
  `#bridge[...]` until they approve it.

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

## 6a. Ancestors who served: research comprehensively
For anyone in the chapter who served in a war, the service record is the spine:
1. **Pull the official service record first** (a national archive's personnel file,
   attestation or enlistment record, pension file, regimental roster). Use it as the
   spine; tell the family's version where it differs, attributed and kind, with
   `// REVIEW:` ("The family remembered four years in the trenches; the file shows four
   months in France").
2. Research, with numbers, short period quotations and sources, and use generously in time
   order:
   - **the town they grew up in** and what it and the country were like then;
   - **how the war drew their countrymen in**, and those soldiers' **reputation**;
   - **how a young soldier enlisted, was examined, trained and shipped** (the ship, the
     route) and sent up to the line;
   - **what happened to their unit when they got there**: how it went into battle, the
     reality of its battles: weapons, artillery, gas, and the **leadership and generals** of
     that time and place;
   - **the process of being sent home** and the journey back;
   - **what veterans came home to**: the economy, politics, prices, jobs, pensions, illness,
     the public mood.
3. **First-hand accounts:** seek out letters, diaries, memoirs, unit histories and letters
   home printed in local papers by soldiers **in or near their units and battles**. Quote
   short exact passages from public-domain or archival sources, cite each, save the texts
   (`facts/sources/`, listed in `works.csv`) so `verify_quotes.py` can check them. Set the
   unit's days from its war diary beside a private's diary and say plainly that the diary
   doesn't name the ancestor; that keeps them in the scene without inventing their presence.
4. **Sensitive record entries** (a field punishment, a court-martial, a venereal-disease
   admission) stay out of the prose until the author decides (style guide §2).
5. Anything that needs a login or a written request goes on the manual-lookups list
   (records-archives); log every search in the chapter's dossier (chapter-dossier).

## 7. Ending the chapter
Closing paragraph (style guide §6) → **THE RECORDS** (`#records`, records-archives) →
**the photographs page** (`#photo-addendum`, photo-processor) listing real photographs held
by archives. Put these in a final **apparatus unit** for the chapter (`kind: apparatus`,
same `section`, highest `order`, no spans) so they survive reassembly.

## 8. Illustrations of ancestors
Usually no photograph exists. AI or artist's illustrations are allowed only under the
photo-processor rules: recorded as illustrations in `photo_index.csv`, a note in the chapter
saying they are renderings and what likeness or source they were based on, the book's
front-matter line, scenes from the material only. Real photographs of the family may serve
as **likeness references** (generate_images.py), and the chapter says so.

**The illustrated story.** When the subject told one scene in vivid detail (a fight, a
storm, a departure), the author may want it drawn as a two-page sequence of eight panels
(`#story-page` with `#story-panel`, book-layout), each captioned with **the subject's own
words, verbatim**, in order, each cited `// src:`. The panels follow the telling exactly;
the page's note line says they are renderings after the subject's account. Nothing graphic;
faces of named people only from reference photographs. Check in the assembled book that the
two pages face each other.

## 9. Family tree (optional)
In a chapter: the three-generation `#family-tree` (§3). For the whole family: from confirmed
relationships only, as an indented list or table in a back-matter file (or the dashboard's
Genealogy export); unconfirmed links shown "?" or left out. Show the author the draft first.

## 10. Report
Figures found and confirmed relationships; chapters proposed; words per figure; tier
breakdown; family-vs-record conflicts; records consulted; open questions batched for the
author. Update `data/chapters.csv` and add ancestor events to `facts/timeline.csv`.
