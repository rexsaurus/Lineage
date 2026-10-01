# Lineage

**Turn recorded interviews with a relative into a real printed book — without the AI making things up.**

[![Build the sample book](https://github.com/rexsaurus/Lineage/actions/workflows/sample.yml/badge.svg)](https://github.com/rexsaurus/Lineage/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-black.svg)](LICENSE)

---

This project came out of my own attempt to document my family's oral history. It started
with a three-and-a-half hour interview with my dad. Then I fed that into AI — and spent
the next while discovering every way that goes wrong.

So I generalized the process and released it as a **Factory Skill** for Claude. Two
skills, really, working together: one that writes the pipeline, and one that runs it. It
covers the whole distance:

| | |
|---|---|
| **Transcribe** | Speech to word-level timestamps on your own machine, with speaker labels, so every sentence in the book can point back at the tape |
| **Research** | Family lore checked against archives, census rolls, regimental records and ship registers — and where they disagree, the book prints both |
| **Illustrate** | Photographs catalogued with the evidence behind every name; AI illustrations allowed, but marked as illustrations so nobody mistakes one for a photograph |
| **Write** | Third-person biography under strict rules: nothing invented, quotes exact, every paragraph cited |
| **Assemble** | Chapters generated from story units, then typeset with front matter, index and a print-ready PDF |

---

## Your book project uses Lineage; it doesn't contain it

A book project (made with `make new`) keeps only its own material: recordings, transcripts,
stories, people, records, photos. Everything else (skills, style, templates, scripts, the
dashboard) stays in Lineage and reaches the project as a release. The project pins the release
it runs in `lineage.lock`:

```bash
make lineage-version          # what this project runs
make update-lineage           # what a newer release would change, and which of your files it touches
make update-lineage APPLY=1   # install and pin it; stories it would alter are marked stale, never rewritten
make dashboard                # the dashboard, on this project
```

Improvements found while working on a book go into Lineage and come back down as a release,
so every project gets them. Things only one family would want go in that project's
`local-overrides/`.

## What it produces

Here is one chapter, start to finish. It came from about twenty minutes of my dad talking
about an ancestor he'd only ever heard stories about, plus a research pass that found the
man's actual letters sitting in a museum forty minutes from where he was born.

### The opening: say what kind of story this is

<img src="docs/images/chapter-p1.png" width="420" align="right" alt="Chapter opening page">

Every family-history chapter starts by telling the reader what they're holding. This one
opens: *"This chapter is family lore."* It names the chain the story travelled down —
old man to grandson to my dad — and promises that **where the records and the family part
company, this chapter says so.**

The **Line of Descent** box runs from the earliest confirmed ancestor to the living
generation, so a reader who picks the book up in fifty years knows exactly who everyone is.

Epigraphs are public domain and cited. The place-and-years line under the title comes from
the timeline, never from a guess.

<br clear="all">

---

### Evidence-coded maps

<img src="docs/images/chapter-p3.png" width="420" align="right" alt="Page with the voyage map">

The map of the whaling voyage distinguishes **recorded positions** (filled dots) from
**the ship's track between them** (dashed). One leg of the Atlantic is labelled
*"Route to the Pacific not recorded"* — because the sources don't say, and inventing a line
there would be inventing history.

Underneath it, in THE RECORDS: the shipping-news columns and logbook entries every dot
came from.

<br clear="all">

---

### Family lore, kept as lore

<img src="docs/images/chapter-p5.png" width="420" align="right" alt="Page with the Hong Kong bridge story">

Seven bandits, seven stab wounds, thrown off a bridge in Hong Kong in 1853. Nobody can
prove it. So the page says *"as the family told it"* and keeps my dad's own verdict in his
own words: **"If he hadn't made it through this, none of us would exist."**

Around the story sits what *is* documented: that the average whaleship lost two-thirds of
her crew, that three men in ten deserted. The desertion stops looking like a scandal and
starts looking like a Tuesday.

<br clear="all">

---

### Where the records win

<img src="docs/images/chapter-p7.png" width="420" align="right" alt="Page on the Petersburg siege">

The family remembered him as a drafted surgeon. The regimental rolls say private, Company
A, 1st Connecticut Heavy Artillery — and they put him at the Crater at a quarter to five
in the morning, among the guns that fired 3,833 rounds before breakfast.

The book prints both versions and explains the gap, rather than silently correcting the
family or silently repeating it: *"It is the way of family stories to improve a little with
each telling, and this one had fifty years and two tellers to do it in."*

<br clear="all">

---

### THE RECORDS

<img src="docs/images/chapter-p9.png" width="420" align="right" alt="The records section">

Every documented claim in the chapter ends up here: museum catalogue numbers, the crew
list that spells his name wrong, regimental histories, the grave, the newspaper columns.

Including the entry I'm proudest of — **a note on the name**, warning the next relative
that there were two American whaleships called *Hannibal*, and the surviving logbook
belongs to the other one.

<br clear="all">

---

### The photographs page

<img src="docs/images/chapter-p10.png" width="420" align="right" alt="The photographs page">

The real photographs, with catalogue numbers and links, and a plain statement that **the
illustrations in the chapter are artist's renderings** made from his Civil War tintype.

A reader in 2075 should never have to wonder which pictures are real. This page is the
rule, not a nicety.

<br clear="all">

---

## Try it in 60 seconds

No recordings, no models, no Claude account needed for the sample.

```bash
git clone https://github.com/rexsaurus/Lineage.git
cd Lineage
make install
make sample
```

You get two PDFs:

- **`examples/sample-project/output/book-draft.pdf`** — a complete 30-page book about an
  invented grandmother, built from two one-minute invented interviews: family-history
  chapter, two life chapters, timeline, glossary, records appendix, index. The yellow
  highlight in chapter 3 is a *bridge* — a sentence the machine wanted to add, held back
  for the author to approve.
- **`examples/erasthus-burnham/erasthus-burnham.pdf`** — the chapter above, annotated rule
  by rule in [docs/EXAMPLE-CHAPTER.md](docs/EXAMPLE-CHAPTER.md).

---

## How it works

```
recordings ─► transcripts ─► timeline ─► story units ─► chapter map ─► chapters ─► book
   audio/      transcript/    facts/      content/        data/        chapters/   output/
            ▲                                         ▲                              ▲
         GATE 1                                    GATE 2                         GATE 3
   confirm the speakers                   approve the chapter map              final sign-off
```

**Story units are the trick.** The transcript is cut into one file per story — not per
chapter — each carrying its source excerpt, its metadata and its written version. Chapters
are *generated* from units. Moving a story to a different chapter is a one-line change and
a rebuild, not a rewrite. A coverage check proves no part of your relative's speech got
quietly dropped.

**Bridges are the other trick.** Anything the model wants to add that the tape didn't give
it must be written as `#bridge[...]`. Those print highlighted in the draft, and **the final
build refuses to compile while one is unapproved.** It is maybe forty lines of code and it
is the reason you can trust the output.

---

## The Factory Skill

Lineage is one instance of a general pattern, and the repo ships the generator too.
Point it at a different kind of source material and it writes you a new pipeline.

Only five things change:

1. **What's the source**, and what does a citation look like?
2. **What's a unit** — the smallest piece that stands alone and can move without a rewrite?
3. **What are the evidence tiers** — witnessed / told / lore, documented / asserted / disputed?
4. **What's the output**, and what builds it?
5. **Where are the gates** — where does a human decide?

Everything else is constant, because the constants are what make the output trustworthy:
immutable sources, citations on every claim, generated outputs nobody hand-edits,
quarantined inventions, coverage checks, versioning that pins every PDF to the exact text
that produced it.

```
/plugin marketplace add rexsaurus/Lineage
/plugin install lineage@lineage   # the book pipeline
/plugin install factory@lineage         # the generator
```

---

## What you need for a real book

- The recordings, in any common audio or video format.
- A Mac or Linux machine with ffmpeg, Typst and Python. Transcription runs locally on CPU,
  faster on an NVIDIA GPU.
- A free Hugging Face token — only to download the speaker-labelling model, which then runs
  on your machine.
- A Claude subscription for Claude Code, which does the writing.
- Patience at three points. The gates are the product, not an inconvenience.

```bash
make install-transcribe                      # speech recognition + diarization
make new PROJECT="$HOME/books/grandma"       # start a book, outside this repo
```

---

## Honest limits

- Three and a half hours of tape makes roughly a 100–140 page book. More tape, more book.
- The machine cannot check a fact that isn't on the tape or in a document you give it.
- Your audio stays on your computer. The **transcript text goes to a cloud model** while
  Claude writes. See [PRIVACY.md](PRIVACY.md).
- Research chapters like the one above need a human who cares. The tools find the records;
  deciding what they mean is yours.
- Make your own book's repo private. Mine is.

---

## Read next

- **[docs/HOWTO.md](docs/HOWTO.md)** — recordings to printed book, step by step.
- **[docs/EXAMPLE-CHAPTER.md](docs/EXAMPLE-CHAPTER.md)** — the chapter above, annotated.
- **[docs/FACTORY.md](docs/FACTORY.md)** — the pattern, and how to aim it at something else.
- **[scripts/README.md](plugins/lineage/scripts/README.md)** — every tool, and the upstream breakage it works around.

---

## License

Code, templates, skills and docs are MIT. The license does not cover your recordings,
transcripts, photographs, or the books you make — those belong to you and your family. The
example chapter in `examples/erasthus-burnham/` is published for reading and learning only.
EB Garamond is under the SIL Open Font License.

*Built for my dad. The letters are still in that museum, in his great-great-grandfather's
very good handwriting, waiting for the family to come and read them.*
