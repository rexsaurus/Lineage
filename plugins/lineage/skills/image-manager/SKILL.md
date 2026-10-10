---
name: image-manager
description: Keeps every image in a Lineage book project catalogued, linked and backed up, and stops work from being repeated. Use it BEFORE generating any illustration (gpt-image-1) or downloading/scanning any image from an archive, museum, newspaper or the family's files, to check whether it already exists; AFTER adding, generating, placing, moving or replacing any image, to re-catalogue and sync to Google Drive; and whenever the author asks where an image is, which images are missing or unused, whether everything is on Drive, or to "sync", "catalogue", "index" or "back up" the pictures.
---

# Image Manager

One catalogue, one guard, one sync. The catalogue is `data/image_catalog.csv` (and `.json`), built by
`image_manager.py` (Lineage's plugins/lineage/scripts/) from the files on disk, the chapter files and the provenance records.
The identity of an image is the SHA-256 of its bytes; the identity of a generated image is also its
id (`IMG-<chapter>-<n>`) and the hash of its normalised prompt.

## The rule: check before you make or fetch

Never generate, download, scan or re-crop an image without running the guard first:

```
python3 $LINEAGE/plugins/lineage/scripts/image_manager.py check --id IMG-regina-1
python3 $LINEAGE/plugins/lineage/scripts/image_manager.py check --prompt "<the full prompt you are about to send>"
python3 $LINEAGE/plugins/lineage/scripts/image_manager.py check --url "<the archive/museum/newspaper URL>"
python3 $LINEAGE/plugins/lineage/scripts/image_manager.py check --file ~/BookDrop/<file>      # same bytes already filed?
```

Exit 0 + `EXISTS …` means it is already here: use the existing file (the line gives its path,
chapters and Drive id). Exit 1 means nothing matches and you may create or fetch it.
Lineage's `generate_images.py` runs this guard itself before every generation, and records each prompt.

## Provenance: write it down when the image arrives

| Kind | Where the file goes | Where its provenance goes |
|---|---|---|
| Generated illustration | `images/IMG-<chapter>-<n>.png` + grayscale `images/print/…jpg` | `data/image_prompts.json` (prompt, size, model, reference photos, date). `generate_images.py` writes it. |
| The family's photographs and supplied images | `photos/source/P###.jpg` + `photos/print/P###.jpg` (photo-processor skill) | `photos/photo_index.csv` |
| Sourced images (archives, museums, newspapers, Wikimedia) | `records/<chapter>/plates/<slug>.jpg` | `data/image_sources.csv`: path, url, title, creator, date, rights, retrieved |
| Records (prison cards, census crops, deeds) | `records/<chapter>/plates/` | `data/image_sources.csv` and the chapter's `SOURCES.csv` |

Captions that are illustrations end "(illustration)". A generated image is never presented as a
photograph, and never shows a named real person's face as if it were a photograph.

## After any change

```
python3 $LINEAGE/plugins/lineage/scripts/image_manager.py catalog       # rescan: hashes, sizes, chapters, captions, origin
python3 $LINEAGE/plugins/lineage/scripts/image_manager.py missing       # broken references, 5 KB stand-ins, PLATE-TODO anchors
python3 $LINEAGE/plugins/lineage/scripts/image_manager.py unused        # catalogued but not placed in any chapter
python3 $LINEAGE/plugins/lineage/scripts/image_manager.py drive-sync   # upload new/changed files
```

`drive-sync` uploads into Drive › *(the folder in `book.yaml` → `drive.parent_id`)* › Lineage › Images ›
`<kind>/` (generated, photo, plate, artwork, record, museum), plus record PDFs (`records/**.pdf` →
Records/) and the book (`output/*.pdf` → Book/). It skips anything whose Drive MD5 already matches,
records each file's Drive id in the catalogue, and uploads the catalogue itself. It needs
`google-api-python-client`, `google-auth-oauthlib` and an OAuth user token with the `drive.file`
scope at `book.yaml` → `drive.token`. Do not upload images through a chat connector's file-create
tool: that routes the file's bytes through the conversation and fails for anything but tiny files.

## Placing an image in a chapter

Use `#plate("/<path>", caption: "…", width: …)` from `pilot/moser.typ`, with a `// photo:` line
under it naming the id and origin. Planned but not yet made plates are marked
`// PLATE-TODO: IMG-…` with the plan in `images-plan.yaml`; when the image
exists, replace the TODO with the `#plate` and keep the plan line as the `// photo:` note. Then
`catalog` again, so the chapter column is right.

## Stand-ins

A checkout may hold small stand-in files where the real plates live elsewhere (a private archive, another
machine). `missing` reports anything under 20 KB in photos/print as a stand-in. Replace them by copying
the real files, never by regenerating.

## What lives where

- `data/image_catalog.csv` — one row per file: key, path, kind, sha256, bytes, size, chapters,
  captions, origin, prompt hash, source URL, Drive id and MD5, note.
- `data/image_prompts.json` — every generated image's prompt.
- `data/image_sources.csv` — every downloaded or scanned image's source.
- `photos/photo_index.csv` — the family's photographs (photo-processor skill owns it).
