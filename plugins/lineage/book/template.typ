// Lineage print template (Typst).
//
// Every chapter file starts with:
//   #import "/book/template.typ": *
//   #show: chapter.with("Title", setting: "Place", dates: "1934–1952", columns: 1)
// and the rest of the file is the chapter.
//
// Compile from the project root (or let `make draft` do it):
//   typst compile --root . book/main.typ output/book-draft.pdf
//   typst compile --root . --input draft=false book/main.typ output/book-final.pdf
//
// The final build (draft=false) fails while any unapproved #bridge[...] remains.

#import "@preview/droplet:0.3.1": dropcap

#let draft = sys.inputs.at("draft", default: "true") == "true"

// ---- Page geometry by trim size --------------------------------------------------
#let trims = (
  "6x9":    (w: 6in,   h: 9in),
  "7x10":   (w: 7in,   h: 10in),
  "8x10":   (w: 8in,   h: 10in),
  "8.5x11": (w: 8.5in, h: 11in),
)

// EB Garamond is bundled in $LINEAGE/fonts (SIL OFL); builds pass --font-path.
#let body-font = ("EB Garamond", "Libertinus Serif")
#let display-font = body-font
#let rubric = rgb("#b3261e")   // red for the initial and ornaments; prints gray in B&W

#let spaced-caps(body, size: 8.5pt, tracking: 0.18em) = text(
  size: size, tracking: tracking, font: body-font, hyphenate: false, upper(body))

// ---- Chapter-start and blank-verso detection (no folio / running head there) -----
#let is-chapter-start(p) = query(<chapter-start>).any(m => m.location().page() == p)
// A page is a blank verso if the next page opens a chapter and the last content
// before that opener ended on the previous page.
#let is-blank-verso(p) = {
  let starts = query(<chapter-start>).filter(m => m.location().page() == p + 1)
  if starts.len() == 0 { return false }
  let ends = query(<chapter-end>).map(m => m.location().page()).filter(q => q < p + 1)
  ends.len() > 0 and calc.max(..ends) == p - 1
}
#let quiet-page(p) = is-chapter-start(p) or is-blank-verso(p)

#let running-title = state("running-title", "")

#let running-head(book-title) = context {
  let p = here().page()
  if quiet-page(p) or query(<main-start>).len() == 0 { return }
  if p < query(<main-start>).first().location().page() { return }
  let chap = running-title.get()
  if calc.odd(p) { align(right, spaced-caps(chap, size: 7.5pt)) }
  else { align(left, spaced-caps(book-title, size: 7.5pt)) }
}

#let folio(style) = context {
  let p = here().page()
  if is-blank-verso(p) { return }
  if query(<chapter-start>).any(m => m.location().page() == p and type(m.value) == dictionary and m.value.kind == "part") { return }
  align(center, text(size: 9pt, counter(page).display(style)))
}

// ---- Main setup --------------------------------------------------------------------
#let book(title: "", subtitle: "", author: "", trim: "7x10", body) = {
  let t = trims.at(trim)
  set document(title: title, author: author)
  set page(
    width: t.w, height: t.h,
    margin: (inside: 0.875in, outside: 0.625in, top: 0.85in, bottom: 0.85in),
    header: running-head(title),
    header-ascent: 40%,
    footer: folio("i"),
    fill: white,
  )
  set columns(gutter: 0.24in)
  set text(font: body-font, size: 11pt, lang: "en", hyphenate: true, number-type: "old-style")
  set par(justify: true, leading: 0.62em, spacing: 0.62em, first-line-indent: 1.2em)
  show heading: set text(font: body-font, weight: "regular")
  show heading.where(level: 1): it => spaced-caps(it.body, size: 15pt, tracking: 0.22em)
  show heading.where(level: 2): it => {
    v(1.1em)
    align(center, text(size: 12pt, style: "italic", it.body))
    v(0.5em)
  }
  show figure.caption: it => it.body
  set figure(numbering: none, gap: 0.6em)
  set footnote.entry(separator: line(length: 25%, stroke: 0.4pt))
  show footnote.entry: set text(size: 8.5pt)
  body
}

// Switch from front matter (roman) to main matter (arabic, restarting at 1).
// Use as a show rule where chapter one begins:  #show: main-matter
#let main-matter(body) = {
  [#metadata(none) <chapter-end>]
  pagebreak(to: "odd", weak: true)
  set page(footer: folio("1"))
  [#metadata("main") <main-start>]
  counter(page).update(1)
  body
}

// A front-matter page with no folio or running head (title, copyright, dedication).
#let plain-page(body) = page(header: none, footer: none, [#body#metadata(none)<chapter-end>])

// A front-matter section that opens on a recto (contents, foreword, introduction).
#let front-section(title, follows-plain: true) = {
  if not follows-plain [#metadata(none) <chapter-end>]
  pagebreak(to: "odd", weak: true)
  [#metadata((kind: "front", title: title)) <chapter-start>]
  running-title.update(title)
  v(0.8in)
  align(center, spaced-caps(title, size: 14pt, tracking: 0.22em))
  v(0.4in)
}

// ---- Chapters ---------------------------------------------------------------------
// Use as a show rule at the top of a chapter file; the rest of the file is its body.
//   #show: chapter.with("Tobias Calder", setting: "Millbrook, Ohio and the Pacific",
//     dates: "1840–1911", summary: [On Ships, Farms and Such],
//     epigraphs: (([Call me Ishmael.], "Herman Melville, Moby-Dick"),), columns: 2)
// Openers always start on a recto, carry no running head, and span both columns.
// columns: 1 for narrative chapters, 2 for research-dense ones (a per-chapter choice).
#let chapter(title, number: none, setting: none, dates: none, summary: none,
             epigraphs: (), contents: none, columns: 1, body) = {
  // The chapter-end marker goes at the END of the body, inside this page run: a marker
  // emitted after the run would land on the next (blank) page and spoil blank-verso detection.
  pagebreak(to: "odd", weak: true)
  set page(columns: columns)
  set text(size: if columns == 2 { 10.5pt } else { 11pt })
  set par(leading: if columns == 2 { 0.52em } else { 0.62em },
          spacing: if columns == 2 { 0.52em } else { 0.62em },
          first-line-indent: if columns == 2 { 1em } else { 1.2em })
  running-title.update(title)
  place(top + center, float: true, scope: "parent", clearance: 1.8em, {
    [#metadata((kind: "chapter", title: title, number: number)) <chapter-start>]
    v(0.45in)
    if number != none { spaced-caps("Chapter " + str(number), size: 8pt); v(0.5em) }
    heading(level: 1, title)
    v(0.7em)
    line(length: 0.9in, stroke: 0.4pt)
    if setting != none or dates != none {
      v(0.7em)
      spaced-caps((setting, dates).filter(x => x != none).join("  ·  "), size: 8pt, tracking: 0.16em)
    }
    if summary != none {
      v(0.5em)
      block(width: 72%, {
        set par(justify: false, first-line-indent: 0pt, leading: 0.5em)
        align(center, text(size: 10.5pt, style: "italic", summary))
      })
    }
    for (i, (ep, src)) in epigraphs.enumerate() {
      v(if i == 0 { 0.9em } else { 0.7em })
      block(width: 62%, {
        set par(justify: false, first-line-indent: 0pt, leading: 0.5em)
        align(center, text(size: 10pt, style: "italic", ep))
        v(0.4em); align(center, spaced-caps(src, size: 7.5pt, tracking: 0.16em))
      })
    }
    if contents != none {
      v(0.6em)
      block(width: 80%, align(center, text(size: 8.5pt, tracking: 0.03em, contents)))
    }
    v(0.25in)
  })
  body
  [#metadata(none) <chapter-end>]
}

// A part title page (no folio). The next chapter breaks to a recto itself.
#let part(title) = {
  [#metadata(none) <chapter-end>]
  pagebreak(to: "odd", weak: true)
  [#metadata((kind: "part", title: title)) <chapter-start>]
  v(3in)
  align(center, spaced-caps(title, size: 16pt, tracking: 0.25em))
  [#metadata(none) <chapter-end>]
}

// The opening paragraph: a red three-line initial, then the first words in small caps.
//   #opening[The summer of 1951][was the summer ...]
#let opening(lead, rest) = dropcap(
  height: 3, gap: 3pt, hanging-indent: 0pt, justify: true,
  font: body-font, fill: rubric, weight: "regular",
)[#smallcaps(lead) #rest]

#let sectionbreak = block(width: 100%, above: 1.1em, below: 1.1em,
  align(center, text(size: 9pt, fill: rubric, "❧")))

// A paragraph that starts flush left (after a break or a plate).
#let flush(body) = par(first-line-indent: 0pt, body)

// ---- Voice -------------------------------------------------------------------------
// A long or locked quotation from the subject (40+ words): an indented block.
#let verbatim(body) = block(inset: (left: 1.2em, right: 0.8em), above: 0.9em, below: 0.9em,
  par(first-line-indent: 0pt, body))

// A short passage from a writer of the time and place, at the head of a section.
#let voice(body, source) = block(width: 100%, breakable: false, inset: (x: 0.9em), above: 0.4em, below: 1em, {
  set par(justify: false, first-line-indent: 0pt, leading: 0.48em)
  align(center, text(size: 9.5pt, style: "italic", body))
  v(0.35em)
  align(center, spaced-caps(source, size: 7pt, tracking: 0.14em))
})

// Interview format is never used. Kept so a stray question fails loudly.
#let asked(body) = panic("#asked is not allowed: fold the question into the subject's answer")

// Connective or interpretive text awaiting the author's approval.
// Highlighted in draft; the final build stops on it.
#let bridge(body) = if draft {
  highlight(fill: rgb("#ffe8a3"), [⟦BRIDGE: #body⟧])
} else {
  panic("Unapproved #bridge left in manuscript: " + repr(body))
}

// Editor notes that print only in draft.
#let note(body) = if draft { text(fill: rgb("#b03030"), size: 8pt)[ ⟦#body⟧ ] }

// ---- Images ------------------------------------------------------------------------
// A plate floated to the top or bottom of a page, framed, captioned in spaced caps.
// span: true crosses both columns of a two-column chapter. Captions of illustrations
// must say so ("as the family told it", "illustration"); see the photo-processor skill.
#let plate(path, caption: none, width: 3.9in, span: true, id: none) = place(auto, float: true,
  scope: if span { "parent" } else { "column" }, clearance: 1.4em,
  align(center, block({
    box(stroke: 0.4pt + black, inset: 0pt, image(path, width: width))
    if caption != none { v(0.45em); spaced-caps(caption, size: 8pt, tracking: 0.22em) }
    if draft and id != none { text(size: 7pt, fill: rgb("#b03030"))[ ⟦#id⟧] }
  })))

// Two plates side by side, each with its own caption.
#let plate-pair(a, b, caption-a: none, caption-b: none, width: 2.55in) = place(auto,
  float: true, scope: "parent", clearance: 1.4em,
  align(center, grid(columns: 2, column-gutter: 0.3in,
    ..((a, caption-a), (b, caption-b)).map(((path, cap)) => align(center, block({
      box(stroke: 0.4pt + black, image(path, width: width))
      if cap != none { v(0.45em); spaced-caps(cap, size: 8pt, tracking: 0.22em) }
    }))))))

// An inline photograph with a caption in normal type (single-column chapters).
#let photo(path, id: none, caption: none, date: none, place: none, comment: none,
           width: 100%, placement: auto) = {
  let meta = (place, date).filter(x => x != none and x != "")
  figure(
    image(path, width: width),
    placement: placement,
    caption: block(width: width, {
      set align(left)
      set par(first-line-indent: 0pt, justify: false, leading: 0.5em)
      set text(size: 8.5pt)
      if caption != none { caption }
      if meta.len() > 0 { [ #text(fill: luma(70), smallcaps(meta.join(", ")))] }
      if comment != none { linebreak(); text(style: "italic", comment) }
      if draft and id != none { text(fill: rgb("#b03030"))[ ⟦#id⟧] }
    }),
  )
}

// ---- Family-history devices ----------------------------------------------------------
// The line of descent, floated to the foot of the opening page, across both columns.
// gens: ((person, spouse), ...), each a content value or none. Mark unconfirmed links
// in the content itself, e.g. [Tobias Calder (link unproven)].
#let descent(title: "The Line of Descent", ..gens) = place(bottom + center, float: true,
  scope: "parent", clearance: 1.2em, block(width: 100%, inset: (top: 0.6em), {
    line(length: 100%, stroke: 0.3pt)
    v(0.4em)
    align(center, spaced-caps(title, size: 7.5pt, tracking: 0.2em))
    v(0.35em)
    let items = gens.pos()
    let rows = ()
    for (i, g) in items.enumerate() {
      let (person, spouse) = g
      rows.push(box(text(size: 8.5pt, {
        person
        if spouse != none { text(fill: luma(35%))[ #h(0.3em)=#h(0.3em) ]; spouse }
      })))
      if i < items.len() - 1 {
        rows.push(box(height: 7pt, align(center + horizon, text(size: 6.5pt, fill: luma(45%), sym.arrow.b))))
      }
    }
    align(center, stack(dir: ttb, spacing: 1.5pt, ..rows.map(r => align(center, r))))
  }))

// "The Records": where every documented claim in the chapter came from, with links.
// Small type, after the closing paragraph.
#let records(title: "The Records", ..items) = block(width: 100%, above: 1.4em, breakable: true, {
  align(center, spaced-caps(title, size: 7.5pt, tracking: 0.2em))
  v(0.3em)
  set par(justify: false, first-line-indent: 0pt, leading: 0.42em, spacing: 0.5em)
  set text(size: 8pt)
  show link: it => underline(offset: 1.5pt, stroke: 0.3pt, it)
  for it in items.pos() { block(above: 0.55em, below: 0pt, par(hanging-indent: 1em, it)) }
})

// An index of real photographs held by an archive, with links. Thumbnails print only
// when show-images is true, i.e. once the holder has given permission to reproduce them.
// items: ((thumb-path or none, [catalogue line], [description], url), ...)
#let photo-addendum(title: "The Photographs", note: none, show-images: false, ..items) = {
  block(width: 100%, above: 1.6em, below: 0.9em, breakable: false, {
    align(center, text(size: 9pt, fill: rubric, "❧"))
    v(0.3em)
    align(center, spaced-caps(title, size: 9pt, tracking: 0.2em))
    if note != none {
      v(0.35em)
      set par(justify: false, first-line-indent: 0pt)
      align(center, text(size: 7.5pt, style: "italic", note))
    }
  })
  set par(justify: false, first-line-indent: 0pt, leading: 0.42em, spacing: 0.4em)
  show link: it => underline(offset: 1.5pt, stroke: 0.3pt, it)
  for (thumb, head, desc, url) in items.pos() {
    let pic = show-images and thumb != none
    block(breakable: false, below: 0.9em, grid(
      columns: if pic { (1.05in, 1fr) } else { (1fr,) }, column-gutter: 0.12in,
      ..(if pic { (box(stroke: 0.3pt, image(thumb, width: 1.05in)),) } else { () }),
      [#spaced-caps(head, size: 7pt, tracking: 0.12em) \
       #text(size: 8.5pt, desc) \
       #text(size: 7.5pt, link(url)[Catalogue record])]))
  }
}

// ---- Index -------------------------------------------------------------------------
// Mark terms as you write: #idx("Calder, Tobias") or a sub-entry
// #idx("Calder, Tobias!at sea"). Cross-reference: #idx-see("Toby", "Calder, Tobias")
#let idx(..terms) = for t in terms.pos() { [#metadata(t)<idx>] }
#let idx-see(from, to) = [#metadata((see: from, to: to))<idx-see>]

#let make-index(title: "Index") = {
  pagebreak(to: "odd", weak: true)
  [#metadata((kind: "chapter", title: title, number: none)) <chapter-start>]
  running-title.update(title)
  v(0.8in)
  align(center, heading(level: 1, title))
  v(0.5in)
  context {
    let entries = (:)
    for m in query(<idx>) {
      let pg = counter(page).at(m.location()).first()
      let pgs = entries.at(m.value, default: ())
      if pg not in pgs { pgs.push(pg) }
      entries.insert(m.value, pgs)
    }
    let sees = (:)
    for m in query(<idx-see>) { sees.insert(m.value.see, m.value.to) }
    let keys = (entries.keys() + sees.keys()).dedup()
    let sort-key(k) = lower(k.replace("!", "\u{1}"))
    keys = keys.sorted(key: sort-key)
    [#metadata((entries: entries, see: sees)) <idx-resolved>]
    set par(first-line-indent: 0pt, justify: false, hanging-indent: 1.2em, spacing: 0.35em)
    set text(size: 9pt)
    columns(2, gutter: 1.5em, {
      let last-main = none
      let last-letter = none
      for k in keys {
        let parts = k.split("!")
        let main = parts.first()
        let letter = upper(main.first())
        if letter != last-letter {
          v(0.6em); text(weight: "bold", letter); v(0.2em)
          last-letter = letter
        }
        if k in sees {
          [#k, _see_ #sees.at(k)]; parbreak()
          continue
        }
        let pages = entries.at(k).sorted().map(str).join(", ")
        if parts.len() == 1 {
          [#main, #pages]; parbreak()
          last-main = main
        } else {
          if main != last-main { [#main]; parbreak(); last-main = main }
          [#h(1em)#parts.at(1), #pages]; parbreak()
        }
      }
    })
  }
}

// ---- Table of contents ---------------------------------------------------------------
#let book-contents() = context {
  let items = query(<chapter-start>).filter(m => type(m.value) == dictionary and (
    m.value.kind in ("part", "chapter") or (m.value.kind == "front" and m.value.title != "Contents")))
  set par(first-line-indent: 0pt, justify: false, spacing: 0.55em)
  for m in items {
    let e = m.value
    if e.kind == "part" {
      v(1em)
      spaced-caps(e.title, size: 8.5pt, tracking: 0.15em)
      v(0.2em)
    } else {
      let n = counter(page).at(m.location()).first()
      let pg = if e.kind == "front" { numbering("i", n) } else { str(n) }
      let num = if e.at("number", default: none) != none { str(e.number) } else { "" }
      link(m.location(), grid(columns: (1.8em, 1fr, auto), column-gutter: 0.3em,
        text(fill: luma(90), num),
        [#e.title #box(width: 1fr, repeat[#h(0.35em).])],
        pg))
    }
  }
}
