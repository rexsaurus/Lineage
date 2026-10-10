# scripts/

Command-line tools that sit beside the skills in `.claude/skills/`. The skills
call them; you can also run them by hand.

**Every script runs from a book project folder**, not from this checkout:

```sh
export LINEAGE=~/Lineage          # where this repo lives
cd ~/books/ruth                               # a book project (has book.yaml)
$LINEAGE/.venv/bin/python $LINEAGE/scripts/render_transcripts.py
```

Each Python script also takes `--project DIR` (default: the current
directory). No script ever works out the project from its own location.
`make install` builds `$LINEAGE/.venv` with the build dependencies
(pyyaml, pillow, matplotlib, openpyxl). The transcription stack is optional:
`pip install -r $LINEAGE/requirements-transcribe.txt` into that venv,
plus `ffmpeg` on your PATH.

The pipeline, in order:

```
audio/ ──transcribe.sh──► transcript/raw/<S>.json ──diarize.py──► (speakers added)
       ──render_transcripts.py──► transcript/verbatim, clean, master.md
       ──make_units.py──► content/units/U###-*.md ──shape.py──► ## Shaped
chapters ──verify_quotes.py──► exit 0 or a list of problems
facts/records/_raw ──export_sources.py──► facts/records/sources + MANIFEST.csv
track CSV ──make_route_map.py──► 300 dpi map plate
record URLs ──fetch_records.py──► facts/records/_raw/<slug>/ + the chapter dossier
dossiers/<slug>/SOURCES.csv ──dossier.py records / check──► THE RECORDS, 100% checked
photos/images-plan.yaml ──generate_images.py──► photos/generated/<id>.png + print copy
```

Contents: [transcribe.sh](#transcribesh) · [sessions.py](#sessionspy) ·
[wx.py](#wxpy) · [hf_compat.py](#hf_compatpy) · [diarize.py](#diarizepy) ·
[diarize_chunked.py](#diarize_chunkedpy) ·
[render_transcripts.py](#render_transcriptspy) ·
[corrections.example.json](#correctionsexamplejson) ·
[make_units.py](#make_unitspy) · [shape.py](#shapepy) ·
[verify_quotes.py](#verify_quotespy) · [export_sources.py](#export_sourcespy) ·
[make_route_map.py](#make_route_mappy) · [fetch_records.py](#fetch_recordspy) ·
[dossier.py](#dossierpy) · [generate_images.py](#generate_imagespy) · [_project.py](#_projectpy) ·
[Left out on purpose](#left-out-on-purpose)

---

## transcribe.sh

Turns the recordings in `audio/` into word-timestamped WhisperX JSON.

```sh
$LINEAGE/scripts/transcribe.sh --dry-run     # show sessions and plan
$LINEAGE/scripts/transcribe.sh --smoke       # shortest session only
$LINEAGE/scripts/transcribe.sh               # everything, shortest first
$LINEAGE/scripts/transcribe.sh S3            # one session
$LINEAGE/scripts/transcribe.sh audio/tape2.m4a
```

Flags: `--no-diarize` (ASR only), `--one-pass` (legacy: whisperx diarizes in
the same run), `--force` (redo sessions that already have JSON), `--project DIR`.
Env: `MODEL` (large-v3), `LANGUAGE` (en), `BATCH_SIZE`, `THREADS`, `DEVICE`,
`COMPUTE_TYPE`, `MIN_SPEAKERS`/`MAX_SPEAKERS`, `HF_TOKEN`.

Per session it: assigns a session ID with `sessions.py`; normalizes the
original to `transcript/work/<S>.wav` (16 kHz mono; `audio/` is only read);
runs WhisperX large-v3 with word alignment through `wx.py`, staging output in a
temp dir and moving it to `transcript/raw/<S>.json` only on success; then,
if `HF_TOKEN` is set, runs `diarize.py`. Without a token it stops after ASR
and tells you the one command to run later. Preflight checks (ffmpeg,
whisperx importable, book.yaml readable, disk space) run before any model is
loaded. A log is appended to `transcript/work/transcribe.log`.

- **Inputs:** `audio/*`, `book.yaml` (`proper_nouns`, `other_speakers`,
  `transcription_locked`)
- **Outputs:** `transcript/sessions.csv`, `transcript/work/<S>.wav`,
  `transcript/raw/<S>.json`

**Works around:**
- *Whisper echoing a long `initial_prompt` as speech.* The prompt is built
  from `proper_nouns` and the script warns above 120 characters. A long list
  of names was observed coming back as fake "speech" (the list read out in
  the middle of a real answer). Keep it to a few surnames; fix any echo that
  slips through with `drop_segments`/`drop_word_runs`/`scrub_inline` at render time.
- *Re-running ASR shifts timestamps.* Two runs of the same audio do not
  produce the same segment boundaries, so every `[S2 00:14:07]` citation
  downstream would break. Hence: idempotent (existing JSON is skipped),
  staged writes (a crash never leaves a half file that looks done), ASR and
  diarization split (a diarization failure never costs a re-transcription),
  and `transcription_locked: true` in book.yaml makes `--force` refuse.
- *CTranslate2 has no Metal/MPS backend.* faster-whisper runs on CPU or CUDA
  only, so Apple Silicon is detected as CPU/int8 rather than failing on `mps`.
- *macOS ships bash 3.2* (no `mapfile`, no associative arrays): written for it.

## sessions.py

Keeps `transcript/sessions.csv` (`session,file,recorded,duration`) in step
with `audio/`. Run it alone to see the list; `transcribe.sh` calls it.

```sh
python $LINEAGE/scripts/sessions.py [--dry-run]
```

IDs are assigned once and never change: new files get the next free number
(ordered by the recording date embedded in the file, then by name), a row
whose file disappeared is kept and warned about, never renumbered. `recorded`
comes from the file's metadata when present; fill it in by hand otherwise -
a hand-entered value is never overwritten.

**Works around:** hard-coded session lists. Everything downstream reads
sessions from this file, so adding a recording later never renumbers the
citations already in the book.

## wx.py

A drop-in replacement for the `whisperx` command:
`python $LINEAGE/scripts/wx.py <whisperx args>`. Imports `hf_compat` and
then hands over to WhisperX's own CLI.

**Works around:** PyTorch >= 2.6 made `torch.load(weights_only=True)` the
default, and that refuses the pyannote VAD/segmentation checkpoints WhisperX
loads, because they pickle omegaconf containers. The stock `whisperx` command
then dies with an `UnpicklingError`/`WeightsUnpickler` error before
transcribing anything.

## hf_compat.py

Import-only shim (`import hf_compat` before whisperx/pyannote). Used by
`wx.py`, `diarize.py` and `diarize_chunked.py`.

**Works around:**
1. *huggingface_hub >= 1.0 removed the `use_auth_token` keyword* (replaced by
   `token`), but pyannote.audio 3.4 and WhisperX's `DiarizationPipeline` still
   pass `use_auth_token`, which now raises `TypeError`. The shim renames the
   keyword on `hf_hub_download`, `snapshot_download` and `model_info`.
2. *PyTorch >= 2.6 `weights_only=True`* rejects pyannote checkpoints that
   pickle omegaconf `ListConfig`/`DictConfig`/metadata objects. The shim
   allowlists exactly those classes with `torch.serialization.add_safe_globals`;
   only if a load still fails with a weights_only error does it rewind the
   stream and retry that file with `weights_only=False` (without the rewind,
   torch falls back to its legacy loader and fails with "persistent IDs in
   protocol 0").

Pinning older torch or huggingface_hub instead breaks faster-whisper/WhisperX,
which is why this is a shim and not a version pin. Tested versions are in
`requirements-transcribe.txt`.

## diarize.py

Adds speaker labels (`SPEAKER_00`, `SPEAKER_01`, ...) to JSON that ASR has
already produced.

```sh
export HF_TOKEN=hf_xxxxxxxx
python $LINEAGE/scripts/diarize.py               # every session without speakers
python $LINEAGE/scripts/diarize.py S1 S3
python $LINEAGE/scripts/diarize.py --chunked never S4
```

Options: `--chunked auto|always|never` (auto chunks sessions longer than
`--chunk-over` minutes, default 20), `--chunk`/`--overlap` seconds,
`--min-speakers`/`--max-speakers` (default 2 + `other_speakers`),
`--device cpu|cuda`, `--force`.

It only *adds* `speaker` keys: it compares every segment's start/end before
and after and refuses to write if anything moved, and writes atomically. With
`transcription_locked: true`, `--force` is refused, so labelled sessions are
never re-labelled; a never-diarized session can still be done.

**Hugging Face access (one time).** The diarization models are free but
*gated*: create a read token at <https://huggingface.co/settings/tokens>,
then, logged in as the same account, accept the user conditions on **both**
<https://huggingface.co/pyannote/speaker-diarization-3.1> and
<https://huggingface.co/pyannote/segmentation-3.0>. Export it as
`HF_TOKEN=hf_xxxxxxxx` (never commit it). A 401/403 or `GatedRepoError`
when the pipeline loads means the token is wrong or one of the two licences
was not accepted; the pipeline depends on the segmentation model, so
accepting only the first is the usual mistake.

After diarizing, listen to a minute of each session and record which cluster
is the narrator in `transcript/corrections.json` → `speaker_map`. Cluster
numbers are arbitrary and can differ between sessions.

**Works around:** diarization being the fragile step (gated downloads,
upstream API breakage). Separating it from ASR means fixing it never requires
re-transcribing - which would move every timestamp.

## diarize_chunked.py

Same as `diarize.py --chunked always`, with its own CLI:

```sh
python $LINEAGE/scripts/diarize_chunked.py S5 --chunk 600 --overlap 60
```

Diarizes overlapping windows (10 min, 60 s overlap by default) and stitches
labels across windows by how much each new window's speakers coincide in time
with the running labels inside the overlap. Each window logs
`stitched 2/2 by overlap`; anything less deserves a listen at that seam.

**Works around:** pyannote's clustering cost growing superlinearly with audio
length. Measured on CPU with speaker-diarization-3.1: about **32 s of compute
per audio-minute on 6-10 minute files, but about 119 s per audio-minute on a
34-minute file**; extrapolated, a 2-hour interview would take ~14 hours in one
piece. Fixed windows keep the per-minute cost flat.

## render_transcripts.py

Raw JSON → readable, citable Markdown.

```sh
python $LINEAGE/scripts/render_transcripts.py [S1 S2 ...]
```

- **Inputs:** `transcript/raw/<S>.json`, `transcript/sessions.csv`,
  `transcript/corrections.json`, `book.yaml` (names and labels)
- **Outputs:** `transcript/verbatim/<S>.md` (every word; low-confidence words
  as `[?word?]`), `transcript/clean/<S>.md` (fillers and stutters removed -
  the layer the book cites), `transcript/master.md` (all clean sessions)

Each file starts with frontmatter (session, file, recorded, speakers, duration,
word counts, number of echo segments removed) and a `## Topics` list of
timestamps. Paragraphs look like `**Ruth** [S1 00:04:28] ...`. The paragraph
builder is the interview-transcriber skill's `whisperx_to_md.py`, loaded from
`./.claude/skills/` in the project, else `$LINEAGE/.claude/skills/`.

**Works around:** *editing raw output moves timestamps and can't be redone.*
All corrections (speaker names, spelling, prompt-echo removal) live in
`corrections.json` and are applied at render time, so `transcript/raw/` stays
exactly as WhisperX wrote it and a re-render is reproducible.

## corrections.example.json

The format of `transcript/corrections.json`, with invented entries. Copy it
into the project and edit. Keys:

- `speaker_map` - `{"SPEAKER_00": "<narrator.label>", ...}`, confirmed by ear
- `spelling` - `[{find, replace}]` regexes applied to paragraph text
- `drop_segments.patterns` - regexes; a raw segment matching one is dropped
  whole (a prompt echo). Confirm first by re-transcribing that stretch
  without a prompt.
- `drop_word_runs.runs` - phrases (or word lists) removed word by word from
  each segment's word array, case and edge punctuation ignored: an echo inside
  an otherwise real segment, before paragraphs are built
- `scrub_inline.patterns` - `[{find, replace}]` for an echo embedded inside a
  real paragraph (text may contain `[?word?]` markers)

Keys starting with `_` are comments.

## make_units.py

Cuts the clean transcripts into story units from cut points you list.

```sh
python $LINEAGE/scripts/make_units.py           # write units, print coverage
python $LINEAGE/scripts/make_units.py --check   # coverage only
python $LINEAGE/scripts/make_units.py --prune   # move stale unit files aside
```

`content/boundaries.csv`:

```csv
session,start,id,title,part,section,tier,people,places,events,flags
S1,00:00:05,U001,The farm at Tannacreek,life,childhood,,Ruth Calder;Agnes Calder,"Tannacreek, Ontario",E003,
S1,00:06:40,X,false start while the recorder is adjusted,,,,,,,
S1,00:07:12,U002,Leaving for the city,life,young-adult,,,"Toronto, Ontario",E010;E011,REVIEW: living person
S2,00:00:03,U002,Leaving for the city,life,young-adult,,,,,
```

`start` is the timestamp of the unit's first paragraph; a unit runs to the
next cut in that session, so **coverage is exact by construction**. The same
id in two sessions gives one unit with two spans. `id` = `X` excludes the span
(reason in `title`) into `content/excluded.md`. `people`, `places`, `events`,
`flags` are `;`-separated (quote cells that contain commas). `part: family`
writes `section:` and `tier:`; any other part writes `era:` from `section`.
Rows whose `session` starts with `#` are comments.

- **Outputs:** `content/units/U###-slug.md` (frontmatter `id, title, part,
  era|section(+tier), spans, timeline_events, people, places, chapter, order,
  lead_in, break_before, flags, status` and sections `## Source`,
  `## Shaped`, `## Notes`), `content/excluded.md`, a coverage report (exit 1
  if any paragraph is uncovered)

Re-running is safe: existing units keep `chapter`, `order`, `lead_in`,
`break_before`, `status`, `## Shaped` and `## Notes`; only the
boundary-driven fields and `## Source` are regenerated, and a unit whose
source changed under shaped text is reported.

**Works around:** silent loss of material. Picking excerpts by hand drops
paragraphs no one notices; cutting at boundaries makes every paragraph land in
exactly one unit or in the excluded list with a reason.

## shape.py

Writes a unit's `## Shaped` text and sets its status.

```sh
python $LINEAGE/scripts/shape.py U002 drafts/U002.md
python $LINEAGE/scripts/shape.py U002 - --lead-in "That spring," --break-before < text.md
python $LINEAGE/scripts/shape.py U002 --status approved
python $LINEAGE/scripts/shape.py --json batch.json   # {"U002": "text" | {"text":..., "lead_in":...}}
```

Replaces only what is between `## Shaped` and `## Notes`; frontmatter edits
touch only the frontmatter. Status becomes `shaped` when text is given.
Importable as `from shape import set_shaped`.

**Works around:** hand-editing frontmatter and section boundaries across
dozens of files, where one slip deletes `## Notes` or the source excerpt.

## verify_quotes.py

Checks quotations. Exit 1 on any problem.

```sh
python $LINEAGE/scripts/verify_quotes.py chapters/*.typ               # published works
python $LINEAGE/scripts/verify_quotes.py --transcript chapters/*.typ  # the subject's words
python $LINEAGE/scripts/verify_quotes.py --all chapters/*.typ
```

**Works mode** checks epigraphs (`epigraphs: (([text], "Author, Work"), ...)`
in `chapter.with(...)`, or `epigraph:` + `epigraph-source:`) and
`#voice[text][Author, Work]` / `#voice([text], "Author, Work")` passages
against public-domain texts listed in `facts/sources/works.csv`
(`work,author,file`, files under `facts/sources/`). A work with no row is an
error ("NO PUBLIC-DOMAIN SOURCE") - in copyright works must be cleared by hand.
Ellipses split a passage into pieces; curly quotes, line breaks, Typst
escapes and dash spellings are normalized. A passage whose words match but
punctuation doesn't is reported separately.

**Transcript mode** checks every double-quoted passage of 3+ words in the
prose (outside epigraphs, voices, comments and code) against what the
narrator says in `transcript/clean/*.md`. Words must match exactly; case,
punctuation and quote style are ignored. Ellipses and `[bracketed
insertions]` split a quote into pieces. A quote found only in another
speaker's words is printed as "check attribution". Quotes from documents or
other people are exempted with `// quote-source: <where>` in the same
paragraph. If the paragraph's `// src: [S2 ...]` cites a different session
than where the words were found, that is noted.

**Works around:** language models and tired editors "improving" quotations -
smoothing grammar, merging two sentences, misremembering a poem. The rule is
*never invent or tidy a quote*; this makes it checkable instead of a hope.

## export_sources.py

Copies the shareable text from the local research cache into the project.

```sh
python $LINEAGE/scripts/export_sources.py [--dry-run]
python $LINEAGE/scripts/export_sources.py --restricted '^museum/' \
    --extract '^ships/data/=VOY0042|\bSea Lark\b' --big-mb 5
```

`facts/records/_raw/` (keep it out of git) → `facts/records/sources/` plus
`MANIFEST.csv` (`raw_path, bytes, sha256, exported, note` for *every* raw
file). Text files are copied; binaries are listed only; restricted paths are
never copied; files over the size limit are either reduced to matching lines
by an extract rule or listed as too large. Rules come from
`facts/records/export.yaml` (documented in the script header) and/or flags.

**Works around:** two opposite failures - committing material whose
reproduction is restricted (archive catalogue pages, copyrighted articles,
grave-listing sites), and losing track of what was consulted. The manifest's
hashes let anyone confirm a re-downloaded file is the one you used.

## make_route_map.py

Draws a black-and-white map of a journey that shows only what the records
show.

```sh
python $LINEAGE/scripts/make_route_map.py facts/records/voyage_track.csv \
    --out photos/print/P050.png --title "The voyage" --caption "Positions from the logbook."
```

Track CSV: `seq,date,place,lat,lon,kind,aboard,source,note,label,label_dx,label_dy,label_ha,gap_before,gap_label,gap_dx,gap_dy`
(only `seq,lat,lon` required). `kind` is `port|position` (a dot),
`area` (italic label, no dot), `waypoint` (bends the line, nothing drawn),
or `text` (a free label such as an ocean name). `aboard=subject` gives a
filled dot on the subject's dashed track; anything else an open dot off it.
`gap_before=yes` leaves the leg before that row undrawn and labels it "not
recorded" (`gap_label`, offset by `gap_dx/gap_dy`). Labels are placed by
`label_dx/label_dy` (degrees) and `label_ha`; `\n` breaks a line.

Extent is automatic (or `--extent W,E,S,N`); routes crossing the 180th
meridian are drawn 0-360. Land is Natural Earth 1:50m (public domain),
downloaded once to `facts/records/_raw/geo/` with the User-Agent
`Lineage (open-source family-history tools)`. EB Garamond is
used if installed (`~/Library/Fonts`, `/usr/share/fonts`,
`~/.local/share/fonts`, ...), else the default serif. `--legend-loc` moves
the key off your labels. Output: PNG at 300 dpi.

**Works around:** maps that imply more than is known. A smooth line from port
to port suggests a recorded route; this draws approximate lines only between
recorded points, marks which points had the subject aboard, and leaves
unrecorded legs visibly blank.

## fetch_records.py

Targeted lookups of a few record pages (at most 50 a run), politely: robots.txt obeyed for
the project's User-Agent (`book.yaml` → `research.user_agent`, never an email address), at
least 2 seconds between requests to a site, no logins, cookies or bot-check workarounds. Each
page is saved under `facts/records/_raw/<slug>/` with a `.meta.json` (URL, retrieval time,
status, sha256); with a dossier, each URL gets a `SOURCES.csv` row and a `RESEARCH-LOG.md`
line. A page it may not or cannot fetch is logged as blocked and added to
`research/MANUAL-LOOKUPS.md` for a person.

```sh
python $LINEAGE/scripts/fetch_records.py anders-calder URL [URL ...] [--group "His crossing"]
python $LINEAGE/scripts/fetch_records.py anders-calder --list urls.txt --dry-run   # robots verdicts only
```

## dossier.py

The chapter dossier (chapter-dossier skill): `new` makes `dossiers/<slug>/` from
`templates/dossier/`; `source` and `log` add a source or a search; `records` writes the
chapter's THE RECORDS from `SOURCES.csv` (cited sources by group, then "Further sources
consulted", then what couldn't be reached); `check` exits 1 unless every URL in the chapter is
in `SOURCES.csv` and every cited source is in THE RECORDS.

## generate_images.py

Generates the illustrations planned in `photos/images-plan.yaml` with OpenAI's image model:
period style presets, a one-line lock on every prompt, and an optional likeness lock (the
family's real photographs as references, through the edit endpoint). Every image must cite the
scene it shows. Writes `photos/generated/<id>.png` and a grayscale `print/<id>.jpg`; `--dry-run`
prints the prompts. The key comes from `OPENAI_API_KEY` or `~/.openai_api_key` (chmod 600,
outside every repo) and is never printed or written. Example plan and style file:
`templates/images/`.

## _project.py

Shared helpers (project folder, `book.yaml`, `sessions.csv`, timestamps).
Imported by the other scripts; not run directly.

## Left out on purpose

- **A Google Drive audio fetcher.** An earlier, private version of this pipeline pulled recordings
  from specific shared Drive files; that is tied to one person's account and
  file IDs, so it is not included. Copy the recordings into `audio/` by any
  means - they are only ever read.
- Backup, museum- or person-specific record scrapers (`fetch_records.py` is the generic,
  polite core), and project-specific verification scripts.

## New in 0.7.0

| Script | What it does |
|---|---|
| `image_manager.py` | catalogue every image; `check` before generating or fetching; `missing`, `unused`; `drive-sync` |
| `archive_fts.py` | Internet Archive full-text search with passages |
| `patent_index_scan.py` | every patent under a name, from the 1872–1969 annual indexes |
