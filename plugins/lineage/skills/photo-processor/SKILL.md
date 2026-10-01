---
name: photo-processor
description: Handles every image in a Lineage book — extracts photos from a photos document (Word, PDF, exported Google Doc, zip or folder of scans), catalogues each with ID, date, holder and the evidence and confidence behind every identification, makes print-ready copies without altering the image, places a few images exactly where they belong, writes captions, keeps AI-generated or artist's illustrations unmistakably labelled as renderings, draws maps from sourced data, and lists archive-held photographs on a chapter's photographs page. Use this whenever photos, scans, albums, illustrations or maps are added or mentioned, or the user asks to caption, date, identify, place, move, generate or index images, asks where a photo went or which are unused, or wants the photo spreadsheet — even if they just say "I added some pictures".
---

# Photos, Illustrations and Maps

Readers will treat a caption as fact for generations, so every label says what it rests
on, every guess looks like a guess, and nothing that isn't a photograph can pass for one.

## Files
```
photos/source/P001.jpg      originals as extracted — never edited (checksummed)
photos/print/P001.jpg       print copies (grayscale or sRGB, 300 ppi tag)
photos/photo_index.csv      source of truth, one row per image
output/photo_index.xlsx     spreadsheet view
```
Images stay out of git (`photos/source/`, `photos/print/` are ignored); only
`photo_index.csv` is tracked. Never `git add -A photos`.

## 1. Extract
```bash
python .claude/skills/photo-processor/scripts/extract_photos.py "<document or folder>"
```
Google Doc: export as .docx first. The script keeps document order, assigns `P001…`, copies
originals to `photos/source/`, and records nearby text as `original_caption` (often the best
evidence; check whether it belongs to the photo above or below). Re-running appends; IDs are
never reused or renumbered, because chapters cite them. Scans of a photo's **back** are
linked to the front (`needs_attention: back: P017`) and read.

## 2. Catalogue every image
Set `kind`: **photograph**, **illustration** (AI-generated or artist's rendering),
**map**, or **placeholder** (a stand-in box until the real photograph is found; never in a final
build). Then fill the row. Every identification carries its **basis**, strongest first:
1. **inscription**: writing on the photo or its back, a printed lab date
2. **document**: a caption in the photos document, an archive catalogue, the author/owner
3. **transcript**: the subject describes this scene (cite `[S2 00:31:05]`)
4. **visual estimate**: clothing, cars, print format, signage, landscape

| Column | Rule |
|---|---|
| holder / catalogue_ref | who holds the original (family member, archive + catalogue number) |
| subject | one plain sentence of what's shown |
| people + people_basis + people_confidence | names **only** from inscription, document, transcript or the owner. Otherwise describe ("unidentified woman, about 30"). **Never name a person from facial resemblance**: a wrong name in print is worse than none. |
| date + date_basis + date_confidence | exact only if inscribed; else a range or "about 1925"; visual estimate = low/medium |
| location + location_basis | same rules; "Ohio (per transcript)" beats a precise guess |
| rendering_basis | illustrations: the scene in the material + the likeness/source used; maps: script + data CSV |
| caption / comment | see §5 |
| print_permission | for archive-held images: yes · no · ask |
| status | extracted → inferred → **confirmed** (only the author or owner confirms) |

Batch questions ("who is this?", "is this the Elm Street house?") for the next gate.

## 3. Print copies
```bash
python .claude/skills/photo-processor/scripts/prepare_print.py --color bw   # or color, per book.yaml
python .claude/skills/photo-processor/scripts/prepare_print.py --only P007 --crop P007=40,30,1880,1400
```
- Allowed: orientation, cropping away the scanner bed or album page, grayscale conversion,
  and cropping text baked into a generated image off the **print copy** (original kept).
- **Not allowed on real photographs without the owner's instruction: colorizing, upscaling,
  face restoration, removing people or objects.** These fabricate detail. Flag damage and
  let the owner decide (a better scan, a professional restorer).
- **Resolution: 300 ppi at printed size; 200 ppi is a hard floor.** `max_print_width_in`
  (at 300 ppi) tells layout how wide it can print; below 200 ppi, print smaller or get a
  better scan. Never upscale to hide it.

## 4. Illustrations (AI-generated or artist's) — strict
Allowed **only if all of these hold**:
- **(a) The caption itself marks it**, e.g. "as the family told it" or an explicit
  "illustration" line, so a reader in fifty years cannot mistake it for a photograph.
- **(b) A note in the chapter** (in the photographs page note or a closing line) states that
  the illustrations are renderings and what likeness or source each was based on.
- **(c) It depicts a scene described in the material**, never an invented event, and
  matches its details (season, place, animal, clothing). Flag mismatches.
- **(d) The distinction survives in the printed book**, not just in drafts or the index.

Also: no image that poses as an archival document (fake contact sheets, fake stamps or
labels); no caricature of any people; nothing graphic. Real photographs may be used as
likeness references for a rendering (say so per (b)) but are never altered themselves.
Keep a project style file (`photos/IMAGE-STYLE.md`: a style prefix, a likeness lock, a
one-line lock appended to every prompt) so a set looks consistent. API keys go in an
environment variable for the one command; never write them to disk.

## 5. Placing and captioning
- **Few, and only where they belong**: a portrait near where a key person is introduced;
  one or two images at the exact moments they show. When in doubt, fewer. Nothing
  decorative. No more than one per page in running text.
- Anchor each image **after** the paragraph it belongs to, never mid-paragraph:
  ```
  #plate("/photos/print/P014.jpg", caption: "Tobias Calder, about 1890", id: "P014")
  #plate("/photos/print/P021.jpg", caption: "The flood, as the family told it (illustration)", id: "P021")
  ```
  `width:` about 3.9in for portraits, 4.4in for landscapes; `span: false` keeps it in one
  column of a two-column chapter; `#plate-pair` for two side by side; `#photo(...)` for an
  inline photo with date, place and comment in single-column chapters.
- **Captions:** short — a person's name for a portrait (exactly as the author gives it), or
  a scene title in the text's own words. No date or place unless confirmed. Low-confidence
  identifications print with "probably" / "believed to be", or not at all (ask). When the
  author supplies a caption, use it word for word and note any mismatch with the text in a
  `// REVIEW:`.
- An author may place an image on a given page; floats land on or after their anchor's
  page, so move the call to a paragraph on (or just before) that page and re-render.
- Images with no matching story go on a candidates list, not into random chapters.
- Record each placement as `chapter`, `placement_anchor` ("ch 03, after ¶ citing [S1 00:22:10]").

## 6. The photographs page (`#photo-addendum`)
At the end of each family-history chapter (after THE RECORDS), list the **real photographs
held by an archive**: catalogue number, date, title, description and record link, plus a
note on what permission is needed to print them. Thumbnails print only once the holder has
given permission (`show-images: true`).
```
#photo-addendum(note: [Held by the Millbrook Historical Society; reproduction needs the
  Society's written permission. The illustrations in this chapter are renderings based on
  the 1862 tintype below.],
  (none, [1987.04.013 · about 1862], [Tintype of Tobias Calder in uniform.], "https://…"),
)
```

## 7. Maps — drawn from data, never generated
- Keep the route or places as a sourced CSV (`facts/records/<person>/<route>_track.csv`:
  date, place, lat, lon, kind, source, note) and draw it with
  `$LINEAGE/scripts/make_route_map.py` (black and white, public-domain coastlines).
- **Evidence-coded:** distinguish recorded positions (filled marks) from approximations
  (dashed, labelled "approximate"); **legs no record covers are not drawn and are labelled
  "not recorded"**; the caption or THE RECORDS **cites the sources of the positions**.
- Index the map with `kind: map` and its script + CSV in `rendering_basis`.

## 8. Spreadsheet and report
```bash
python .claude/skills/photo-processor/scripts/csv_to_xlsx.py output/photo_index.xlsx "Photos=photos/photo_index.csv"
```
Report: images processed by kind, placed vs. candidates, confirmed vs. inferred,
low-resolution or damaged ones, illustrations and whether each meets rules (a)–(d), and the
batched questions.

## Consistency
- When a chapter moves, update `chapter` and anchors. When a caption is corrected, fix the
  CSV first, then the call. A replaced image keeps a new ID; the old one becomes a candidate.
- People named in confirmed captions get `#idx` entries next to the call.
