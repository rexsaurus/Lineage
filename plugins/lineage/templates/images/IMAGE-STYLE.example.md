# Image style (photos/IMAGE-STYLE.md)

The project's master prompt for generated illustrations, so a set looks like one book. Copy
this to `photos/IMAGE-STYLE.md` and fill it in with the author. The style presets and the lock
also go in `photos/images-plan.yaml`, which `generate_images.py` reads.

## The look, per period
- **<period or place>**: the photographic process of the time (tintype, silver-gelatin snapshot,
  newspaper halftone), its grain and border, black and white for a B&W book; "Photorealistic,
  NOT illustration, NOT CGI".

## People
- Faces of named relatives come only from **reference photographs** (`photos/reference/<name>/`)
  through the generator's edit mode, and the chapter says so. Without a reference, keep figures
  small, turned away or in shadow; never invent a named person's face as if it were a portrait.
- What each recurring person wears and looks like **in the material** (the subject's own
  descriptions, cited), and their age in each scene.

## Scenes
- Only scenes the material describes, with its details (season, place, animals, clothing).
- Nothing graphic; no rank, unit insignia or uniform details the record does not support.
- No image that poses as a document (fake stamps, contact sheets, labels).

## The lock (appended to every prompt)
"No text, no caption, no watermark."

## The illustrated story (optional)
For one scene the subject told in detail, a sequence of 8 panels (two pages of four,
`#story-page`), each captioned with the subject's exact words and cited. Plan the panels in
`photos/images-plan.yaml` (ids IMG-<chapter>-story-1 … 8) with the same style and likeness.
