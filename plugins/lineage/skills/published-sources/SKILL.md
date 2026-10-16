---
name: published-sources
description: Clears the rights on a published book, periodical or memoir before anything is copied, then ingests it into a lineage as a secondary source — a passage index with page numbers, a quotations file graded by rights, timeline rows, a records-catalogue entry and Familypedia updates. Use whenever the user wants to add a book, county history, yearbook, magazine run or someone else's memoir to the project, asks "can we download this", "is this public domain", "scan this book", or shares an archive.org, HathiTrust, Google Books or Goodreads link.
---

# Published sources

A published book is a **secondary source**: evidence of what was believed and printed at the time,
not proof. Old county and family histories were often compiled from the same oral accounts the
family already has; mark what merely repeats tradition. Where a book disagrees with a primary record,
keep both and say which is which.

## 0. Rights first — before downloading anything
Decide the status and write it down (with links and the date checked) before any copy is made.

| Published in the US | Status |
|---|---|
| before 1930 (as of 2026; the line moves forward each 1 January) | public domain |
| 1930–1963 | public domain **only if not renewed** in its 28th year — check both sources below |
| 1964–1977 | renewal was automatic: in copyright |
| 1978 on | in copyright (life + 70, or 95 years for corporate works) |

Renewal checks for 1930–1963 (record both searches):
- US Copyright Office public records (publicrecords.copyright.gov): search the author's name; a renewal
  appears as an `RE…` registration naming the title.
- Stanford Copyright Renewal Database (books 1923–1963), or the Catalog of Copyright Entries renewal
  volumes for the 28th year (HathiTrust / Gutenberg scans).
- Also look at the copyright page of any scan.

If a renewal is found, or the answer is unclear: **stop, download nothing, and report**. The fallback
is an excerpt-only ingest from pages the user supplies (rights: "fair-use excerpt only").

Non-US books follow their own country's terms; say so rather than guessing.

## 1. Acquire (public domain or open items only)
Order of preference: Internet Archive (an edition with a good OCR text layer), HathiTrust full view,
Google Books full view, Project Gutenberg. Prefer a first or near-first edition and record which one —
page numbers differ between editions and the citations depend on them. Use the `archive-open-book`
skill for Internet Archive items; it refuses lending-library and access-restricted items.

**Lending-library copies** (Internet Archive "Borrow", library e-loans) are for reading only. Never
capture, screenshot page-by-page, or otherwise copy a borrowed book, even when the user owns the loan.
Work from the pages that mention the family: the user searches inside the loan and supplies those pages
(or the project buys a print copy and scans it privately).

"Open on archive.org" does not mean public domain. Check rights before publishing anything from it.

## 2. Catalogue
Add a row to `facts/records/<person>/sources.csv` (it appears in the Familypedia records catalogue):

    id,title,url,holder,type,date_retrieved,local_raw_path,rights_notes
    R01,"<full citation as it will print>. Subjects: <the people it is about>.",<catalogue or lending page>,<holder>,book,<date>,<path or empty>,"<rights status and basis>"

- `type` is `book`; put the people it covers in the title (Library of Congress subject lines are ideal)
  so the record attaches to their Familypedia pages.
- For an in-copyright book leave `local_raw_path` **empty**: a private research copy stays outside git
  and outside the datastore, and is never published or uploaded to image hosting.

## 3. Read and index
Write `facts/records/<person>/<short-title>_notes_<date>.md`:
1. Chapter by chapter, with page ranges.
2. Dated events table: date | event | page (feeds the timeline).
3. People around the subject, as the book presents them.
4. Where it agrees with, contradicts or adds to the record — one bullet per point, both sources named.
Page numbers are the printed numbers of the edition used; note the PDF offset if there is one.

## 4. Quotations
Keep `facts/records/<person>/<topic>_quotes.md`, every entry with source, page (or line in the cached
text) and rights:
- **Public domain**: quote where the period wording carries something a paraphrase would lose.
- **In copyright**: paraphrase by default; any quotation under 15 words; a handful per book at most.
  Flag any passage worth quoting at length for the user's decision instead of quoting it.
- Recommend the few quotations worth using in the chapter; note which are already used.

## 5. Ingest
- **Timeline** (`facts/timeline.csv`): one row per dated event, `source` = "Author, Short title (year),
  p. N", the page also in `date_basis`, `conflicts` when another source disagrees.
- **Familypedia** (`data/wiki/<slug>.md`): new facts with footnotes citing author, short title and page.
  An organization, place or event can have its own curated article (see HOWTO, Familypedia).
- **Chapter**: paraphrased, with `// src:` comments carrying the pages; mark the story stale rather than
  regenerating it unless the user asks.
- **Open questions**: mark what the book answers; add what it raises.

## 6. Report
Title, author, year, edition and archive; the citation as it will print; rights status and basis; the
pages that mention the family; what it confirms, adds and contradicts; which articles, events and
chapters changed; proposed quotations with pages.
