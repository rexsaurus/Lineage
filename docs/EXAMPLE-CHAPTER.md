# The worked example: "Erasthus Burnham"

This is a real chapter, published with the family's permission, from the book BookAssembler
was built for: a biography of Daniel St. John written by his son from recorded interviews.
It is a **family-history chapter**, the hardest kind: an ancestor nobody alive met, known
through one grandson's stories, a museum's catalogue of his letters, and public records.

- Source: [`examples/erasthus-burnham/chapters/02-erasthus-burnham.typ`](../examples/erasthus-burnham/chapters/02-erasthus-burnham.typ)
- Build it: `make sample` → `examples/erasthus-burnham/erasthus-burnham.pdf` (10 pages)

The text is exactly as written for the book. Two things differ from the family's copy:
- **Six images are withheld.** Five are AI illustrations made from a museum photograph, and one
  is a photograph of unknown origin, so they print here as labelled gray boxes. The map is
  included; it was drawn from data (see below).
- **The museum's thumbnails are left out** of the photographs page. The museum restricts
  reproduction, so the page lists catalogue numbers and links only.

Read the source file alongside this page. Its `//` comments never print, but they carry
the chapter's whole audit trail.

---

## 1. The opener

```typst
#show: chapter.with("Erasthus Burnham", columns: 2,
  setting: "South Windsor, New London, Hong Kong and Holyoke",
  dates: "1834–1921",
  summary: [On Whales, Bandits, Bone Saws and Such],
  epigraphs: (
    ([Whenever I find myself growing grim about the mouth; …], "Herman Melville, Moby-Dick"),
    ([Bearing the bandages, water and sponge, \ Straight and swift to my wounded I go,],
     "Walt Whitman, The Wound-Dresser"),
  ))
```

| Rule | How it shows |
|---|---|
| Title is just the relative's name | "Erasthus Burnham": the name the family used, not the record's "Erastus" (the comment at the top says why) |
| Place-and-years line | `setting` · `dates` |
| A short summary line, not a list | "On Whales, Bandits, Bone Saws and Such" |
| Epigraphs: public domain only, cited, verified | Melville (1851) and Whitman (1865); the comment under them gives the Gutenberg sources, and `verify_quotes.py` checks the wording |
| Two columns for research-dense chapters | `columns: 2`. A narrative chapter would use 1 |
| Recto start, no running head, drop cap | done by the template; the drop cap is `#opening[…][…]` |

## 2. Saying what kind of material this is

```typst
#opening[This chapter is family lore.][It is the story of Daniel's
great-great-grandfather, Erasthus Burnham, as it came down the family: from the old man to
his grandson, William Burnham Krug, who spent years at his side, and from Krug to Daniel, …
Where the records and the family part company, this chapter says so.]
```

The first sentence names the tier (lore). The second traces the path the story travelled. The
last makes the promise every family chapter makes. Nothing that follows is allowed to break it.

## 3. The line of descent

`#descent(...)` floats a box to the foot of the opening page. It runs from the earliest
documented generation down to the living family, with marriages on each line. The comment
under it cites the source of every link and lists the gaps for the author:
`// REVIEW: Dad's mother's name is not on the tape…`. An unconfirmed link would be marked
in the box itself.

## 4. One timeline; the record is the spine

The chapter is strictly chronological: birth, the whaleship, Hong Kong, marriage, two
enlistments, the mills, death. An earlier draft told the family's version and the record's
version as two separate passes over the same years. The author called it "non sequential and
chunky". Now the documented life is the spine, and the family's version comes in where it
differs:

> The family remembered his war differently. In their telling he was a surgeon, drafted for
> his first term and paid for his second … The letters and the regiment's records describe a
> soldier, and there was no Union draft until 1863. The money, though, was real: it was the
> bounty that came with the second enlistment. It is the way of family stories to improve a
> little with each telling, and this one had fifty years and two tellers to do it in.

Both versions are printed and the disagreement is stated. The family story is neither
silently corrected nor silently repeated, and the record confirms what it can (the money).

## 5. Tiers, sentence by sentence

- **Documented:** "On June 21 a clerk at New London wrote him onto the crew list of the
  whaleship _Hannibal_ as 'Erastus W. Brunham'…" (`// src: … crew list AC061341`)
- **Told by the subject:** "Hong Kong, as Daniel explained, was a common stop for the whalers"
- **Lore, attributed:** "One day on patrol, as the family told it, seven bandits jumped him."
  The `// REVIEW:` beneath records that the museum confirms the police service but not the
  stabbing.

## 6. The subject's voice

Daniel is the subject of the book, and this chapter keeps his voice even though it's about
someone else. A few of his quotes:
- "So the main thing it took," Daniel said, "was a good iron stomach."
- "If he hadn't made it through this," Daniel said, "none of us would exist."
- Daniel's verdict was brief: "Erastus was happy to do it."

Each one is exact from the clean transcript and cited with `// src: [S5 hh:mm:ss]`. They are
the lines nobody else would phrase that way, which is why they are quoted, not paraphrased.

## 7. Historical context that describes the world, never the subject

The whaling and Civil War passages are built out from period sources. Every sentence of
context has a `// context:` line with its source:

```typst
A green hand's share, or lay, was about one two-hundredth of the catch, which worked out to
around twenty cents a day, when a laborer ashore made ninety; …
// context: Elmo P. Hohman, The American Whaleman (1928), p. 15 (green hand's lay 1/200),
// p. 240 (about 20¢ a day vs about 90¢ for unskilled labor ashore)
```

The method behind it: build a sourced fact sheet first, then write from it. Specific numbers
beat adjectives. Period writers are quoted briefly and named. Coincidences in time are stated
plainly and never turned into causes:

> On January 5, 1864, the last day before the draft, Erasthus enlisted again …
> `// NOTE: that the Jan 5 date and the draft deadline are connected is inference; the text states the coincidence only.`

## 8. Honest gaps

> Which cape the _Hannibal_ took, no surviving record says.

When the record is silent, the chapter says so; it doesn't fill the gap. The same rule
shapes the map (section 10).

## 9. `// REVIEW:` notes and conflicts

The chapter carries a dozen `// REVIEW:` notes for the author. Some examples:
- the museum gives one discharge date and the 1889 state roster another, so the text follows
  the roster and the note records the conflict;
- an inference ("that he deserted") the family calls a mutiny;
- a detail Daniel gave that the medical record contradicts, left out and noted.

None of these notes print, and none of them is settled by the writer.

## 10. Images

- **The map** (`P043.png`) is evidence-coded. Filled dots mark places recorded with him aboard;
  open dots mark the ship without him; a dashed line is approximate between recorded points.
  The passage to the Pacific and the voyage home are labelled "not recorded". It was drawn by
  `scripts/make_route_map.py` from a track file in which every row cites its source. An
  AI-generated map was tried first and rejected as inaccurate.
- **Illustrations.** The family's copy has five AI renderings of scenes from the text, made
  with his real Civil War tintype as the likeness reference. The photographs page says so.
  One caption marks its image ("The surgeon's tent, as the family told it"). The others,
  like "Erasthus Burnham, 1864", **do not**. That was written before the rule that every illustration's own caption
  must say what it is (photo-processor skill), and it is the fix this chapter still needs.
- **The photographs page** (`#photo-addendum`) lists nine real photographs at the museum, with
  catalogue numbers, dates, descriptions and links. It says that printing them needs the
  museum's permission, so thumbnails stay off until it's granted.

## 11. The Records

`#records(...)` closes the chapter in small type. It covers every kind of source the chapter
used:
- the museum's person record and letter collections, by catalogue number;
- the Civil War rosters and regimental histories, with years, and where to read them free;
- the National Park Service soldier entries, linked;
- the grave;
- the whaling database entries;
- the Honolulu newspaper issues that sighted the ship;
- the books behind the context.

It ends with a **note on the name**:

> _A note on the name._ There were at least two American whaleships called _Hannibal_: his,
> of New London (441 tons, built 1821, voyages 1843–1861), and an older, smaller ship of Sag
> Harbor … A surviving Sag Harbor logbook of 1845–1849 belongs to the other ship, not to his.

## 12. The closing

The chapter does not end on a quote. The last section says what he left behind (the letters,
the uniform that didn't survive) and where those things are now. That turns the chapter into
something a grandchild can act on.

---

### What to copy into your own family chapters
1. Name the tier and the path in the first two sentences.
2. A line of descent with every link sourced.
3. One chronological timeline; the family's version told where it differs.
4. Research written up as a sourced fact sheet before any context is written.
5. `// src:` on every paragraph, `// context:` on every borrowed fact, `// REVIEW:` on every doubt.
6. Gaps said out loud; maps that show what isn't known.
7. The Records, with a note on any name that could be confused.
