---
name: photo-processor
description: Handles every image in a lineage and its book — extracts photos from a photos document (Word, PDF, exported Google Doc, zip or folder of scans), catalogues each with ID, date, holder and the evidence and confidence behind every identification, makes print-ready copies without altering the image, places a few images exactly where they belong, writes captions, keeps AI-generated or artist's illustrations unmistakably labelled as renderings, draws maps from sourced data, and lists archive-held photographs on a chapter's photographs page. Use this whenever photos, scans, albums, illustrations or maps are added or mentioned, or the user asks to caption, date, identify, place, move, generate or index images, asks where a photo went or which are unused, or wants the photo spreadsheet — even if they just say "I added some pictures".
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

**Intake.** New images arrive in `photos/inbox/` (prefix `01-`, `02-` to fix their order);
extract from there. Afterwards move the originals to `photos/archive/originals/<date>-<set>/`,
download duplicates ("photo (1).jpg") to `photos/archive/duplicates/`, and a set that a newer
one replaces to `photos/archive/superseded/`. When the author supplies the same set more than
once, use the **newest** files. `photos/inbox/` and `photos/archive/` stay out of git.

## 2. Catalogue every image
Set `kind`: **photograph**, **illustration** (AI-generated or artist's rendering),
**map**, or **placeholder** (a stand-in box until the real photograph is found; never in a final
build). Then fill the row. Every identification carries its **basis**, strongest first:
1. **inscription**: writing on the photo or its back, a printed lab date
2. **document**: a caption in the photos document, an archive catalogue, the author/owner
3. **transcript**: the subject describes this scene (cite `[S2 00:31:05]`)
4. **visual estimate**: clothing, hairstyles, cars (model years), print format (deckled
   edges ≈ 1940s–50s, square rounded-corner prints ≈ 1960s–70s, dated lab stamps on
   borders), signage, landscape

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
- **(a) It is recorded as an illustration**: `kind: illustration` in `photo_index.csv`, with
  `rendering_basis` (the scene's citation, the style, any likeness reference). Its caption
  stays short like any other (§5); the author's caption is used word for word.
- **(b) The book says so in print**: the copyright page carries the line "The illustrations
  in this book are artist's renderings, not photographs." (build_book.py writes it whenever a
  placed image is an illustration; `book.yaml` → `front.illustrations_note`), and the chapter
  says what likeness or source they were based on (in the photographs page note, a closing
  line, or a `#story-page` note).
- **(c) It depicts a scene described in the material**, never an invented event, and
  matches its details (season, place, animal, clothing). Flag mismatches.
- **(d) The distinction survives outside the book too**: pages shared as images say in the
  post that the illustrations are renderings; the dashboard never shows an illustration as a
  person's picture.

Also: no image that poses as an archival document (fake contact sheets, fake stamps or
labels); no caricature of any people; nothing graphic; no rank, insignia or uniform detail
the record doesn't support. Real photographs may be used as likeness references for a
rendering (say so per (b)) but are never altered themselves.

### Generating them
Keep a project style file (`photos/IMAGE-STYLE.md`: the look per period, the likeness rules,
a one-line lock appended to every prompt; example in `$LINEAGE/templates/images/`) so a set
looks like one book, and plan every image in `photos/images-plan.yaml` (id, size, period
style preset, optional likeness set, the scene's citation, the prompt):
```bash
python $LINEAGE/scripts/generate_images.py --dry-run     # read every full prompt first
python $LINEAGE/scripts/generate_images.py IMG-03-1      # photos/generated/IMG-03-1.png + print/IMG-03-1.jpg (grayscale)
```
- **Period style presets** describe the photographs of the time (a 1910s silver-gelatin
  print, a 1940s snapshot), never the people.
- **Likeness lock:** with `likeness:` set, the generator runs in edit mode with the family's
  real photographs (`photos/reference/<name>/`) as references, so a relative looks like
  themselves across a set; without a reference, keep figures small, turned away or in shadow.
- The originals in `photos/generated/` are never edited; the print copy is grayscale for a
  B&W book. Index each one (§2, `kind: illustration`) before placing it.
- The OpenAI key comes from `OPENAI_API_KEY` for the one command, or from a file outside
  every repo (`~/.openai_api_key`, chmod 600). Never in the project, never printed, never
  committed.

## 5. Placing and captioning
- **Few, and only where they belong**: a portrait near where a key person is introduced;
  one or two images at the exact moments they show. When in doubt, fewer. Nothing
  decorative. No more than one per page in running text.
- Anchor each image **after** the paragraph it belongs to, never mid-paragraph:
  ```
  #plate("/photos/print/P014.jpg", caption: "Tobias Calder, about 1890", id: "P014")
  #plate("/photos/print/P021.jpg", caption: "The water came up to the porch", id: "P021")
  // photo: P021 — illustration (photo_index.csv), after [S1 00:31:05]
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
- **An illustrated story** (family-history-chapters §8): eight panels over two facing pages,
  `#story-page(title: …, story-panel(path, 1)[“the subject's words”], …)`, each caption the
  subject's exact words, cited; the second page's `note:` says they are renderings.
- If a chapter has more good photos than text, propose an **album** section at its end (a
  grid of two: `#grid(columns: 2, gutter: 0.8em, photo(...), photo(...))`) rather than
  crowding the running text.
- Images with no matching story go on a candidates list, not into random chapters; the
  author may want them as an album chapter in the back matter, or cut.
- Record each placement as `chapter`, `placement_anchor` ("ch 03, after ¶ citing [S1 00:22:10]").

## 6. The photographs page (`#photo-addendum`)
At the end of each family-history chapter (after THE RECORDS), list the **real photographs
held by an archive**: catalogue number, date, title, description and record link, plus a
note on what permission is needed to print them. **Thumbnails print in drafts** (so the
family sees what exists) **and in the final book only once the holder has given permission**:
the template's default is `show-images: draft`; pass `show-images: true` after permission is
recorded (`print_permission: yes`).
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
  CSV first, then the call. A replaced image keeps a new ID; the old one becomes a candidate
  and its file goes to `photos/archive/superseded/`. An image removed from a chapter becomes
  a candidate too.
- People named in confirmed captions get `#idx` entries next to the call.
