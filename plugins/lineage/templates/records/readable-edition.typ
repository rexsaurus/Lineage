// A readable edition of a scanned record (a court file, a service record, a deed, a letter):
// a cover, a plain-English summary and timeline, then every page of the original beside its full
// transcription, and the editor's notes. Copy this file next to the scans, fill in the parts marked
// FILL IN, and build:
//     typst compile readable-edition.typ "<Record> (readable).pdf"
// Conventions: typed text in grey boxes (#typed), handwriting in italics with a red rule (#hand),
// the editor's words in [square brackets], [?] for an uncertain reading. Transcribe every page,
// including the backs and the duplicate copies; say which pages repeat which.
#set document(title: "FILL IN: the record's title")
#set page(paper: "us-letter", margin: (x: 0.85in, y: 0.8in),
  footer: context align(center, text(size: 8.5pt, fill: luma(40%))[FILL IN: short title · page #counter(page).display()]))
#set text(font: ("EB Garamond 12", "EB Garamond", "Libertinus Serif"), size: 11pt)
#set par(justify: true, leading: 0.6em)
#let rubric = rgb("#b3261e")
#show heading.where(level: 1): it => block(above: 1.2em, below: 0.7em, text(size: 16pt, fill: rubric, weight: "regular", it.body))
#show heading.where(level: 2): it => block(above: 0.4em, below: 0.8em, text(size: 14pt, weight: "regular", it.body))

// One original page: its image on the left, the transcription on the right.
//   img: path to the page image (rotate sideways scans upright first)
#let doc(no, title, img, body) = {
  pagebreak(weak: true)
  text(size: 8.5pt, fill: luma(40%), tracking: 0.08em)[ORIGINAL PAGE #no]
  v(-0.4em)
  heading(level: 2, title)
  grid(columns: (2.3in, 1fr), column-gutter: 0.3in,
    box(stroke: 0.4pt + luma(60%), image(img, width: 100%)),
    { set text(size: 10.5pt); body })
}
#let typed(body) = block(fill: luma(96%), inset: 9pt, radius: 2pt, width: 100%, {
  set text(font: ("Courier New", "DejaVu Sans Mono"), size: 9pt); set par(justify: false); body })
#let hand(body) = block(inset: (left: 9pt), stroke: (left: 1.5pt + rubric), { set text(style: "italic"); body })

// ---- cover
#align(center)[
  #v(1.2in)
  #text(size: 10pt, tracking: 0.15em)[FILL IN: COURT / ARCHIVE · JURISDICTION]
  #v(0.5em)
  #text(size: 26pt, fill: rubric)[FILL IN: Title]
  #v(0.4em)
  #text(size: 13pt, style: "italic")[FILL IN: subject · date]
  #v(1.8in)
  #block(width: 78%, text(size: 9.5pt)[A readable edition of the FILL IN-page file sent by FILL IN on FILL IN, in reply
  to a records request. Each original page is shown beside a full transcription. Typed text is set in grey boxes;
  handwriting is set in italics with a red rule. Words in square brackets are the editor's; [?] marks an uncertain
  reading.])
]

// ---- summary
#pagebreak()
= What the file says
FILL IN: what happened, in plain English, with dates, in two or three paragraphs.

#table(columns: (1.2in, 1fr), stroke: none, inset: (y: 4pt),
  table.hline(stroke: 0.4pt),
  [*date*], [event],
  table.hline(stroke: 0.4pt))

*People named.* FILL IN. *The law or the form.* FILL IN. *Contents of the file.* FILL IN (pages and what each is).

// ---- the pages (one #doc per original page)
#doc("1", "FILL IN: what this page is", "img/p-01.jpg")[
#typed[FILL IN: the typed text, line for line]
#hand[FILL IN: the handwriting]
]

// ---- notes
#pagebreak()
= Editor's notes
- *Spelling.* FILL IN.
- *Corrections in the originals.* FILL IN (overtyped dates, struck names).
- *Source.* FILL IN: the file name, who sent it, when. Transcribed FILL IN.
