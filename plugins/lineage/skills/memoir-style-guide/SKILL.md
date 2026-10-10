---
name: memoir-style-guide
description: The voice, point-of-view, quotation, fact-sourcing and chapter-shape rules for the stories and printed book a Lineage record exports — a third-person, past-tense narrative about the subject, written by the family member who recorded the interviews, built only from the recordings and sourced research, with the subject's own words woven in as exact quotations. Use this whenever drafting, shaping, rewriting, editing, tightening, proofreading or reviewing any story unit, chapter or passage; turning transcript into prose; writing captions, transitions, context or epigraphs; handling quotes, dialect, dates or names; or when a passage feels flat, invented, or doesn't sound like the subject. This is the master rulebook; other writing skills defer to it.
---

# Biography Style Guide

The book is a **biography of the subject, written about them in the third person** by the
family member who recorded the interviews (the *author*). It reads like a real book, not
an interview: continuous narrative, scenes told start to finish, no questions and no sign
of a tape recorder. Every fact about the subject comes from the recordings (or a cited
document); the subject's own voice lives in the quotations.

Two ways this goes wrong, and every rule below guards against one of them:
1. **Invention.** A biographer's instinct is to fill gaps: the weather, what they felt,
   what they must have thought. Readers will take every sentence as family fact.
2. **Blandness.** Third person can sand a person down to "a hardworking woman of few
   words." Their phrasing, humor and opinions have to survive, mostly through quotation.

Read first: `book.yaml` (`narrator.name`, `narrator.label`, `narration.subject_name`,
`interviewer`), `facts/glossary.md`, `facts/timeline.csv`, and `voice/verbatim.md` if it
exists (passages the author has locked; anything in it goes in `#verbatim[...]` word for
word). A finished, annotated chapter is
in `docs/EXAMPLE-CHAPTER.md`; copy its shape.

Examples below use an invented subject, **Ruth Calder** (speaker label "Grandma"),
interviewed by her grandson **Sam**.

## 1. Voice and point of view
- **Third person, past tense**, written *about* the subject: "Ruth left Millbrook in 1952."
  Never first-person "as told to", never the subject narrating.
- Name the subject per `book.yaml` → `narration.subject_name` (default: first name). Full
  name once at the start of the book, then the short form; vary with the pronoun. Avoid
  "our subject", "the young woman" and similar.
- Relatives get their names, with the relationship on first mention per chapter ("her
  uncle Tobias"). Nicknames the subject used go in quotation marks.
- **The author appears only in the introduction and an optional afterword**, never in the
  chapters. No "my grandmother", no "I asked her", no interviewer's name inside a chapter.
- **No interview format anywhere.** No questions, no "when asked…", no "she recalled in an
  interview", no speaker labels, no Q&A. A question's content is folded into the subject's
  answer as a standalone statement: Q "Was that the house on Elm?" / A "Yes, the Elm Street
  house" → "The family was living in the house on Elm Street by then." Cite the question's
  timestamp too. (The template's `#asked` panics on purpose if one slips in.)
- At most "she liked to say" or "as she told it" where the act of telling matters.
- **A bare "yeah" to a leading question is a weak fact.** Don't state it as fact; hedge it
  ("she agreed it was probably 1952") or put it in `facts/gaps.md`, and flag it
  `// REVIEW: confirmed only by "yeah" to a leading question`.
- **Default tone:** warm, plain, lightly wry. A dry aside about the world or the situation
  is welcome ("The mill's safety record may not survive scrutiny"); a joke at the subject's
  expense, or one that invents what they thought, is not.

## 2. Facts: what the narrator may write

| Allowed without approval | Not allowed |
|---|---|
| Restating what the subject said, as narration | Feelings, thoughts or motives they didn't state |
| Putting a story in order from pieces across sessions | Sensory detail, weather, dialogue they didn't give |
| Connective narration: "Two years later…", "By then the family had moved to town." | Facts not on the tape or in a cited document |
| Sourced context about the world (§2a) | Speculation as fact ("she must have…", "surely…") |
| Folding a question into a statement the subject confirmed (§1) | Firming up a bare "yeah" (§1) |
| Judgments the subject made, attributed: "She never forgave the board for that." | The narrator's own judgments of people |

Narration may **restate, order and connect**. It may not **add**.

- **Interpretation** the author might want ("It was, in a way, the end of her childhood")
  goes in `#bridge[...]` for the author to approve. The drafter never decides it. Bridges
  are highlighted in drafts, and **the final build fails while any unapproved bridge
  remains**.
- **Hedges carry over.** "I think it was '72" → "around 1972" or "in 1972, as best she
  remembered". Never firm up an uncertain date or number, and never state a date more
  precisely than `facts/timeline.csv` → `date_display`.
- **Sensitive material** (living people, legal trouble, health, violence, trauma): write it
  accurately, add `// REVIEW:` saying what it is, and **never cut or soften it**. The author
  and family decide what prints; the drafter does not.
- **Sensitive record entries** (a punishment in a service file, a court case, an asylum or
  prison record, a cause of death) are different: they did not come from the subject. They
  stay **out of the prose until the author decides**, flagged `// REVIEW:` and marked
  SENSITIVE in the chapter's dossier. Once the author decides to include one, tell it plainly
  from the record, with what it meant at the time (sourced), at its place in the timeline,
  without moralising; record the decision in `DOSSIER.md`.
- Unclear names, dates or relationships go in `facts/gaps.md` as questions for the author,
  never into the text as guesses.

### 2a. Context about the world
Context turns a list of facts into a life lived somewhere: what the place was like then,
what was changing, what things cost, what a reader in fifty years won't know.
- It describes **the world, never the subject.** No motives, feelings, reactions or
  presence they didn't state ("Like many young women, she felt…", "The news must have…").
  **Juxtaposition, not causation:** "That spring the mill cut its hours" is fine; "so she
  left" is not, unless she said so.
- **Never silently correct the subject.** Where a record or context disagrees with what they
  said, don't fix it in the narration: print both where it matters, attributed, and add a
  `// REVIEW:` and a line in `facts/gaps.md`.
- **Local to the chapter's place and years.** No national headlines or another place's
  history unless it bears directly on what the subject was doing.
- **Every fact is sourced** from a reliable source (government, university, museum,
  encyclopedia, major newspaper, period book), never written from memory. Mark it on the
  paragraph: `// context: <claim> — <source/URL>`. **"General knowledge" is never a source**,
  not even for the obvious: there is always a real source to cite (an encyclopedia entry
  will do for the end of the Second World War).
- **Every context source is listed in that chapter's THE RECORDS** (`#records[...]` after
  the closing paragraph; see records-archives). A fact that can't be verified is cut.
- Keep the proportion: context supports the story and the subject stays the spine (as a
  rough guide, no more than a quarter of a chapter's words). Thread it in by date ("That
  October, while she was at the mill, …").
- A claim made in passing ("around the Cape") can assert something no record says. Reread
  every added sentence against its source before the build.

### 2b. Epigraphs
- **Each chapter opens with one epigraph** by default (`book.yaml` → `chapters.epigraphs`),
  printed on the opener via the chapter's `epigraphs:`; a family-history chapter may carry
  two, and the author may ask for none. No other quotations from such writers at section
  heads. Choose a writer **of the chapter's place and time**; a project can keep its own
  place → writer table in `local-overrides/epigraphs.md`.
- **Public-domain literature only**, chosen for the chapter's place or era, cited as
  "Author, Work". Never from memory: save the source text in the project and verify the
  exact wording with `$LINEAGE/scripts/verify_quotes.py <chapter file>`. Note the text
  you used: `// epigraph: <work> — <URL of the text>`.
- **Public-domain status is per edition**, not per author: a poet's early editions can be
  free while later revisions or collections are not. Check the publication date of the
  edition you quote against the public-domain cutoff where the book is printed, and record
  the edition and year in the `// epigraph:` note.
- Copyrighted writers only with written permission, recorded in `data/archives.csv`.
- The epigraph is juxtaposition: the narrator never says the subject felt what the line
  says. Avoid lines that imply the subject's death or doom.

## 3. Quotation: how the subject's voice survives
- **One or two direct quotes per page** as a rough guide; more where they're most vivid.
  **A chapter with no quotes has lost the subject.**
- Quotes are **exact** from `transcript/clean/`: only fillers (um, uh) and false starts
  removed, "…" for an internal cut. **Grammar and dialect are preserved.**
- **Short quotes run inline:** She called it "the worst job on God's earth."
- **40+ words**, or a passage the author has locked word for word, go in an indented block:
  `#verbatim[...]`. A few per chapter at most, for the stories that only work in their words.
- **Quote the verdicts, humor and punchlines**: the lines nobody else would phrase that
  way. Example: "So the main thing it took was a good iron stomach." Paraphrase logistics;
  quote verdicts.
- **People the subject quotes** are attributed through the subject: Her father's answer,
  as she told it, was "You'll do it or you'll walk."
- **Never invent or tidy a quote.** If the wording isn't on tape, it's paraphrase.

## 4. Traceability
Every paragraph ends with a Typst comment citing its sources (comments never print):
```
Ruth had no telephone until she was fourteen. To call anyone, she walked to the
Petersons' farm down the road.
// src: [S2 00:31:05]-[S2 00:31:40]
```
- Pure transitions: `// src: transition` (no new facts allowed in them).
- Context paragraphs: `// src: context` plus one `// context: … — source` per fact.
- Documents: `// src: record R014` or the record's URL (also listed in THE RECORDS).
- Doubts for the author: `// REVIEW: …`; research caveats: `// NOTE: …`.

## 5. Grammar and mechanics
*Chicago Manual of Style* base.
- Narration is standard English; dialect and the subject's grammar live only inside quotes.
- Spell out one through one hundred and round numbers; numerals for years, addresses,
  exact measures and prices ("$1.25 an hour").
- "June 14, 1958"; "the 1950s" in narration ("the fifties" only inside quotes).
- City and state on first mention per chapter; spellings from `facts/glossary.md`.
- Curly quotes, unspaced em dashes (type `---`), serial comma. Italics for ship names and
  titles, and for emphasis only where the subject stressed a word on tape. No bold.

## 6. Chapter shape
1. **Header:** title; a **setting · dates** line ("Millbrook, Ohio · 1934–1952"); a short,
   poetic **summary line** in the old-book manner, never a list or a sentence of facts
   ("On Looms, Floods and Such"). Set in `data/chapters.csv` (`setting`, `dates`,
   `summary_line`).
2. **Epigraph** (one, §2b).
3. **Opening: the place and the people at that time.** One to three paragraphs on where
   and when the chapter happens and who matters in it, then the first concrete moment the
   subject described. The first paragraph carries the drop cap: `#opening[lead words][rest]`.
   Never open on invented scene-setting about the subject or on a thesis ("The flood would
   change everything").
4. **Strict chronology.** Forward in time, one thing after another: no flash-forward
   openings, no cutting back and forth. Each section opens with when and where the subject
   was ("In the winter of 1949, Ruth was boarding with the Hales…"). A story told *to* the
   subject goes where they heard it. Sections are separated by `#sectionbreak` (❧).
5. **The last scene**, told start to finish.
6. **Closing paragraph** after a `#sectionbreak`: what followed and what remains, in sourced
   facts only. No moral, no feelings they didn't state, never a bare quote as the ending.
7. Then **THE RECORDS** (`#records`) on **every chapter**: a complete list of **every
   original source found and used** for it (title, author or publisher, date, link), and
   in the chapter's dossier every source consulted or scraped, so nothing used or downloaded
   goes unlisted (chapter-dossier, records-archives). Family-history chapters also get the
   photographs page (`#photo-addendum`).

- **Length: at least `chapters.min_pages` pages (default 10) in the book's layout**, measured
  by building the chapter (`make chapter`). Reach it with real material: the subject's full
  stories in their own words, the records, and built-out sourced context. **Never padding,
  repetition or invention.** Where a chapter can't reach it honestly, **combine sparse
  chapters** (a short relative's chapter into "Others in the Family" or a neighbour, two
  thin life stages into one) rather than print thin ones; propose the merge to the author.
- Paragraphs 60–150 words, varied; a short one for a punchline is fine.
- Titles: plain stage or place names, or a phrase the subject said; relatives' chapters
  are just the name.
- **Images: few, and only where they belong**: a portrait near where a key person is
  introduced, one or two at the exact moments they show. When in doubt, fewer. Captions,
  evidence and illustration rules: photo-processor.

## 7. Captions and back matter
Same third-person, past-tense, neutral voice: "Tobias Calder with his canal boat, about
1890." No invented quotes; dates and places only if confirmed.

## 8. Manuscript markup
Prose lives in story units (content-separator) and is assembled into `chapters/NN-slug.typ`
(chapter-generator). Markup: blank lines between paragraphs, `_italic_`, `#opening[..][..]`,
`#verbatim[...]`, `#bridge[...]`, `#sectionbreak`, `#idx(...)`, `#plate(...)`,
`#footnote[...]` (reader explanations only).

## 9. Before calling a unit or chapter done
1. No interview traces: no questions, speaker labels or "when asked"; no author in a chapter.
2. Every paragraph has `// src:`; spot-check three against the transcript.
3. Nothing the subject didn't say: scan for feelings, motives, weather, dialogue, "must have".
4. Every quote matches `transcript/clean/` word for word (bar removed fillers).
5. One or two quotes per page; does it still sound like them?
6. Every `// context:` has a real source (never "general knowledge") that is listed in THE
   RECORDS, and no context sentence claims anything about the subject. If the chapter has a
   dossier, `dossier.py check <slug> <file>` prints OK.
7. Strictly chronological; ends on a closing paragraph.
8. The epigraph passes `verify_quotes.py`.
9. The chapter builds to at least the page minimum without padding.
10. List every `#bridge`, `// REVIEW:` and bare-"yeah" fact for the author.

## Example
Transcript:
> **Sam** [S1 00:22:05] What was your dad like?
> **Grandma** [S1 00:22:10] Um, so, my dad, he, he wasn't a, you know, he wasn't a talker. We'd be out there all day and he'd maybe say ten words. And one of them was "Git." (laughs) Git meaning get over here, get that, get going, it meant everything.

Wrong (invented, bland):
> Ruth's father was a stern, silent man. Working beside him through long hot days, she learned the value of quiet diligence.

Wrong (interview format):
> Asked what her father was like, Ruth said he "wasn't a talker."

Right:
> Her father was not a talker. They could work side by side all day, Ruth said, and he might say ten words, one of which was "Git." As she explained it, "Git meaning get over here, get that, get going. It meant everything."
> // src: [S1 00:22:05]-[S1 00:22:10]

Family-history chapters (ancestors, tiers, records beside lore) add the rules in the
family-history-chapters skill.
