---
name: foreword-generator
description: Writes the introduction of a Lineage book — the author's first-person opening pages telling the reader who the subject is, what the book covers (generations, years, places), why the author made it, and honestly how it was assembled from the recorded interviews and records. Gathers the verifiable numbers automatically, asks the author for the personal parts, drafts it, and places it in the front matter; also covers an optional afterword. Use this whenever the user mentions a foreword, preface, introduction, afterword, author's note, "about this book", how the book was made, or why it was written — even if they just say "it needs something at the start explaining what this is".
---

# Introduction (and Afterword)

A few pages at the front answer the reader's first questions: who is this, what will I find
here, why does this book exist, and can I trust it.

**Naming:** a *foreword* is written by someone other than the author; the author's own
opening is an *introduction* (or preface). Default title: **Introduction**
(`book.yaml` → `front.introduction_title`). If someone else writes an opening piece, theirs
is the Foreword and comes first.

## Voice
**The author speaking, first person**: "My grandmother, Ruth Calder, was born in…", "In June
2026 I sat down with her…". **The introduction and an optional afterword are the only
places the author appears**; the chapters stay third person with no author in them. Warm,
plain, specific. No grand claims, no character summed up in adjectives; two or three
concrete details do that.

## 1. Gather facts
```bash
python .claude/skills/foreword-generator/scripts/foreword_facts.py
```
Writes `data/foreword_facts.md`: sessions with dates and lengths, total recording time,
years and places covered, family figures, chapters with summaries, word count, number of
quotations, images (and how many are illustrations), records. Run after chapters are
assembled and `index_tools.py wordcount` has run. **Every number in the introduction comes
from this file.**

## 2. Ask the author for what only they know
Write `data/foreword_questions.md` and send it at the next gate:
1. How did the recordings happen (who suggested it, where, who else was there)?
2. Why did you want to make this book, and why now?
3. Who is it for?
4. Anything about the subject the reader should know before starting, in a sentence or two?
5. Anyone to thank?
6. Should the introduction say that AI tools helped transcribe and draft it?

Use the answers as close to the author's own words as possible. Unanswered → leave it out
(a `#bridge[...]` placeholder may hold the spot); never invent a motive.

## 3. Structure
About 600–1,200 words, three to five short sections without headings:
1. **Who the subject is**: name, birth, the arc of the life from the chapter summaries.
2. **What the book covers**: the family who came before (named relatives, how many
   generations back) and the subject's own life (stages, years, places); the back matter
   (timeline, glossary, where the records are, index).
3. **Why it exists**, from the author's answers.
4. **How it was made**, specific and honest:
   - the recordings: sessions, dates, hours;
   - everything about the subject comes from those recordings, and every quotation is in
     their own words; family-history chapters also draw on public records, cited in each
     chapter's THE RECORDS;
   - the process: transcribed, stories gathered and put in order, written as narrative;
   - the limits: memory is memory; dates are as remembered; where tellings or records
     disagree the book says so; stories from before the subject's time are marked as told
     or as lore;
   - illustrations, if any, are renderings, not photographs (photo-processor);
   - AI assistance if the author agrees ("Transcription and first drafts were done with the
     help of AI tools; every passage was checked against the recordings.");
   - where the recordings are kept (see Where the Records Are).
5. **A closing line**, to the intended reader or a short exact quote from the subject.

Cite like the chapters: `// src:` for the tape, `// src: foreword_facts` for numbers,
`// src: author` for the author's answers.

## 4. Write and place it
`book/front/introduction.typ`:
```
#import "/book/template.typ": *
#front-section("Introduction", follows-plain: false)

My grandmother, Ruth Calder, …
// src: foreword_facts

#align(right)[— Sam Calder \ #text(style: "italic")[Millbrook, Ohio, 2026]]
```
book-generator includes it after the contents with roman folios. Check the draft: it starts
on a recto and runs 2–5 pages.

An **afterword**, if the author wants one, is the same first-person voice: a hand-written
file (e.g. `chapters/89-afterword.typ`, `#show: chapter.with("Afterword")`) listed last in
`data/chapters.csv` with no units and no number, so assembly leaves it alone. The facts
rules still apply to anything it says about the subject.

## 5. Keep it current
Re-run `foreword_facts.py` whenever chapters, sessions or images change and fix any number
or chapter reference that moved.

## Report
The draft, any `#bridge` placeholders, and which questions still need answers.
