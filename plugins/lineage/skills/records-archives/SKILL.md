---
name: records-archives
description: Keeps a lineage's documentary trail — indexes the family's own records and keepsakes (letters, Bibles, albums, deeds, discharge papers, recordings, heirlooms — what exists, who holds it, what's lost), caches public records found in research (census, rosters, catalogues, newspapers, ship registers) with URLs and checksums, exports their text to git with a manifest, writes each chapter's THE RECORDS section with catalogue numbers, citations and "note on the name" disambiguations, and builds the privacy-safe "Where the Records Are" appendix. Use this whenever the user mentions family papers, documents, archives, heirlooms, genealogy research, a census or military record, citing a source, who has the photos, or asks where something is kept or who to ask — even if it's just "Aunt May has a box of old letters".
---

# Records & Archives

Two jobs: (A) the family's own papers and keepsakes, so the next person to go looking
doesn't start from zero; (B) the public records behind every documented or context claim
in the book, so any reader can check them.

## Files
```
data/archives.csv                       index of records (family and public), source of truth
data/archive_asks.md                    follow-up list grouped by holder (generated)
output/archives.xlsx                    spreadsheet view (generated)
facts/records/<person>/                 structured facts from research: CSV/markdown with URLs,
                                        retrieval dates, context_<topic>.md fact sheets, notes
facts/records/_raw/                     raw downloads (pages, PDFs, images) — NOT in git
facts/records/sources/                  shareable text exports + MANIFEST.csv — in git
chapters/91-where-the-records-are.typ   printed appendix (generated, print-safe)
dossiers/<slug>/                        per-chapter research memory (chapter-dossier skill)
research/MANUAL-LOOKUPS.md              lookups only a person can do (template in $LINEAGE/templates/research/)
research/manual-lookups-results.csv     what they found, one row per lookup
research/REQUESTS.md                    letters and forms sent to archives, and the replies
```

## A. The family's records

### Scan
Search the transcript and manuscript for anything that is or was a record: "she still
has…", "it's in a box at…", "the Bible has all the names", "burned in the fire", "the
county has it", "there's a tape of…". Also: the photo originals and who holds them; the
interview recordings for this book (holder: the author; where the backups are); institutions
mentioned (a church's baptism register, a courthouse). **Lost and destroyed items get rows
too**: "the letters burned in 1962" saves a future relative years.

### Columns (`data/archives.csv`)
| column | content |
|---|---|
| record_id | R001… stable forever |
| item | "Family Bible", "Muster roll, Co. B, 1862" |
| type | photographs · letters · documents · bible · military · legal · recordings · heirlooms · institutional · other |
| description | what it is, as described or catalogued, neutral |
| date_range | as stated or derived |
| holder | person or institution as named, or blank |
| holder_relation | relation to the subject/author if known |
| location_general | city/state or institution — **never** a street address |
| location_detail_private | address, box location, contacts — never printed |
| condition | as described |
| status | confirmed · mentioned · unknown · lost · destroyed · institutional |
| mentioned_in | transcript citations `[S2 00:12:40]` and/or the record's URL |
| chapter | where the book uses it |
| official_copy_hint | where a copy *might* exist, phrased as a possibility |
| print_permission | yes · no · ask (default ask) |
| follow_up | the specific ask |

### Rules
- **Only what was said, confirmed or found.** Don't assume a record exists because it
  usually would. Official-copy hints are the one place general knowledge is allowed.
- **Privacy.** Living people's addresses, phones and emails only in
  `location_detail_private`. A living holder is printed only with `print_permission: yes`.
- **Custody is sensitive.** "Your uncle took the papers" is recorded neutrally; the
  grievance stays out of the index.
- When the author confirms an item, set `confirmed` and note the date.

## B. Research records

### Gathering
- **Prefer public-domain and freely accessible sources, and say where they live**: national
  and state archives, official rosters and regimental histories, period books on the
  Internet Archive or HathiTrust, digitized newspapers (e.g. Chronicling America), free
  census indexes, museum and library catalogues, maritime and ship-register databases, park
  service pages. Note paywalled sources as such and give the free route if there is one.
- **Automated fetching** (scripts and agents on their own) is polite: it respects robots.txt
  and site terms, waits **at least 2 seconds between requests to the same site**, and sends a
  User-Agent naming the project only (`book.yaml` → `research.user_agent`). **Never put
  anyone's personal email or credentials in a request.** `$LINEAGE/scripts/fetch_records.py
  <slug> URL…` does all of this, saves raw copies with checksums and logs the chapter dossier.
- **Targeted lookups by a person.** What automation may not or cannot reach (a login, a bot
  check, a robots.txt that bars automated crawlers) goes on `research/MANUAL-LOOKUPS.md`: what
  to find, where, the search terms, why it matters. The author (or someone they ask) does those
  lookups in **their own browser and their own accounts**, one record at a time at a human
  pace, within each site's terms; if the author chooses, a browser assistant can do the same
  inside the author's own logged-in session, at the author's direction. **Never**: CAPTCHA
  solving, tools built to defeat bot checks, credentials beyond the author's own session, or
  bulk harvesting of a database. Results go to `research/manual-lookups-results.csv`
  (transcribed exactly, every candidate listed, two agreeing facts before an identity
  match), and every lookup is logged in the chapter dossier.
- **Archive requests** (an email, a web form, a records request) go out only with the
  author's go-ahead, from the author's own address; log each in `research/REQUESTS.md` with
  the date and status, and the replies under it.
- **Cache what you use:** structured facts (one row or bullet per fact, with URL, page and
  retrieval date) in `facts/records/<person>/`; raw snapshots in `facts/records/_raw/`
  (gitignored; catalogues often forbid reproduction).
- **Export to git:** after any new caching run `$LINEAGE/scripts/export_sources.py`.
  It copies shareable text (txt, csv, json, md…) from `_raw/` to `facts/records/sources/`
  and writes `MANIFEST.csv` (every raw file, size, sha256, exported or why not), so anything
  not in git can be re-downloaded. Binaries stay local; whole-database dumps are cut to the
  relevant rows; content whose holder forbids reproduction (museum pages, third-party
  memorial sites, copyrighted articles) is linked, never exported.
- Low-confidence OCR goes into fact sheets flagged as such and never into prose unverified.
- **When sources disagree** (a museum's date vs the official roster), follow the more
  authoritative record in the text, keep a `// REVIEW:`, and log it in `facts/gaps.md`.

### THE RECORDS (every chapter, 100% of its sources)
**Every chapter** ends with a small-type `#records(...)` block after the closing paragraph,
**listing every original source found and used for it**: catalogue numbers, record titles,
database entries with IDs, newspaper titles and dates, book citations with years and pages,
URLs (and, in the dossier, the local cached path). Nothing used or downloaded is left off:
sources consulted but not cited go in a closing "Further sources consulted" entry, and the
chapter's dossier `SOURCES.csv` holds them all. Generate the block from the dossier
(`$LINEAGE/scripts/dossier.py records <slug>`) and check it (`dossier.py check <slug> <file>`).
```
#records(
  [*Census.* U.S. Census 1870, Millbrook, Hamlin Co., Ohio, p. 12, line 31: Tobias
   Calder, 30, boatman. Free index at FamilySearch. #link("https://…")],
  [*Roster.* _Official Roster of the Soldiers of the State of Ohio_, vol. 4, p. 214. Internet Archive. #link("https://…")],
  [*A note on the name.* Two barques named _Mariah Dent_ sailed in the 1850s: the
   Salem vessel (database ID V1234, 1849–1861) and a Liverpool ship. The crew list puts
   Tobias on the Salem ship; nothing in this chapter refers to the other.],
)
```
- **Include a "note on the name/identity" entry whenever a record might be confused with
  a similar one** (two ships of the same name, two men with the same name): which is which,
  and why. Record the reasoning in `facts/records/<person>/`.
- One entry per source (or a group heading with its sources); clickable links. Typst
  gotcha: in markup a `;` straight after an embedded call (`#link(...)[x];`) is swallowed as
  a statement end, so write `\u{3B}` there (dossier.py does).
- In units, THE RECORDS lives in the chapter's apparatus unit (`kind: apparatus`).

## Generate
```bash
python .claude/skills/records-archives/scripts/archives_tools.py check     # fix everything reported
python .claude/skills/records-archives/scripts/archives_tools.py asks
python .claude/skills/records-archives/scripts/archives_tools.py appendix
python .claude/skills/records-archives/scripts/csv_to_xlsx.py output/archives.xlsx "Records=data/archives.csv"
```
`check` flags addresses, phones or emails outside the private column and rows with neither
a transcript citation nor a URL. `appendix` writes `chapters/91-where-the-records-are.typ`
from rows with `print_permission: yes`, grouped by type, omitting private details;
book-generator includes it in the back matter.

## Report
Items by type and status, lost items, research sources cached and exported, chapters missing
THE RECORDS, disambiguation notes added, and the follow-up list grouped by holder so the
author can make one call per relative.


## More tools (0.7.0)

- `archive_fts.py '"Surname, Given"'`: full-text search of the Internet Archive with passages: town
  reports, school yearbooks, gazettes, newspapers. The quickest first look for anyone in print before 1970.
- `patent_index_scan.py --name "Surname, Given" --out records/patents`: every US patent under that name
  in the annual indexes 1872–1969; confirm numbers on Google Patents' patent pages.
- When a record arrives as scans (a court file, a prison card), make a readable edition from
  `templates/records/readable-edition.typ` and keep the transcription in the chapter's records folder.
