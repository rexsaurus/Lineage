# Work spec: digitizing a family's papers (template)

Fill in the bracketed parts. Get the family's written agreement before anyone works in their home, and
each museum's written permission before anyone scans its collection. Nothing is posted until the
project's owner approves it.

## Purpose
[Name] is writing a family history. The family's own papers — photographs, slides, letters, documents and
books, much of it in [the attic / storage] — have never been scanned, and related material in [museum /
library] needs good scans. This job turns all of it into a clean, catalogued digital archive.

## Where
1. **The family home, [town]** (address given privately on hire). By appointment.
2. **[Library] special collections** — [subject]. Book a reading-room appointment; follow their rules.
3. **[Museum / historical society]** — [collection, catalogue numbers]. Only with written permission.
   Many museums do not allow outside scanning; if they prefer to scan for a fee, that replaces this part.

## What to scan
- **Photographs**: loose prints, framed photos (scan through glass only if the frame can't safely be
  opened — ask), **albums** (whole pages *and* single photos; never pry glued photos loose).
- **Backs of photographs** whenever there is writing, a stamp or a date.
- **Slides and negatives** on a film-capable scanner (or send them to a lab — see below).
- **Documents and letters**: certificates, military papers, diplomas, deeds, school records, clippings,
  programmes, letters and **envelopes** (postmarks date things).
- **Books**: family Bibles (record pages), inscribed books, yearbooks, scrapbooks; for ordinary published
  books, only the title page, inscriptions and pages with family content.
- **Objects**: medals, badges, uniforms — photograph, don't scan.
- If unsure whether something matters: scan it and note it.

## Technical standard
| Item | Resolution | Format |
|---|---|---|
| Photographs, prints | 600 dpi (1200 dpi if smaller than 3×5 in) | TIFF master (24-bit colour, even for b&w) + JPEG |
| Slides / negatives | 2400–4000 dpi | TIFF master + JPEG |
| Documents, letters | 400 dpi, colour | TIFF or high-quality PDF + JPEG |
| Album pages, large items | 400 dpi flatbed, or an evenly lit overhead photo | JPEG/TIFF |
| Bound books | overhead scanner or copy stand, 400 dpi equivalent | PDF per book |

No retouching, cropping into the image, filters or "auto-enhance": restoration is done later, and the
raw scan is kept as the original (see the `photo-processor` skill). Keep originals in their order.

Slides and negatives are usually cheaper at a local film lab than by the hour; the items leave the
house, so the family must agree.

## Naming and catalogue
- One folder per box, album or place: `HOUSE-Attic-Box01/`, `HOUSE-Album-Wedding/`, `LIBRARY/`, `MUSEUM/`.
- Files `<folder>_<0001>.tif`; the back of an item `<folder>_<0001>-back.tif`.
- A spreadsheet row per item: file name; what it is; date (as written / estimated); people (as written,
  and as the family identifies them); place; where found; condition; notes. Write down what the family
  says about an item — it is part of the record. These rows feed `data/archives.csv`.
- Photograph each box or album cover before starting it.

## Handling and conduct
- Clean, dry hands or nitrile gloves; no tape, clips or sticky notes on originals.
- Remove nothing from the house, open no sealed letters without permission, discard nothing.
- Fragile, mouldy or brittle items: photograph, don't force; flag them.
- Everything seen is private: signed confidentiality and photo-release agreement before starting.

## Delivery
Daily upload to a shared folder (or a drive handed over weekly) with the spreadsheet kept current, and a
short end-of-day note: what was scanned, what is left, anything notable.

## Pay and terms
[Rate]/hour, plus mileage; independent contractor; weekly invoices. Start with a paid trial (one box and
one album) reviewed before continuing. Careful, patient, comfortable working in a private home; own
transport. Library, archives, history or photography students are a good fit.

Where to find someone: university student-employment boards that accept off-campus household jobs
(many career-services platforms do not), history and public-history departments, library-science job
lists, local photo and film labs, and local classifieds.
