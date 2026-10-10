# How to use Lineage

Lineage is a cooperative family documentation and research platform. A family collects its
material: recordings, photographs, documents, letters, scans, links. Lineage turns it into a
researched, sourced, browsable record: the people, places, events, vessels, organizations and
objects in it, a genealogy built from evidence, a timeline, and an encyclopedia of all of it
(the **Familypedia**), with every fact linked to the source that supports it. Stories, a
printed book and narration are exports of that record, made at the end.

This guide follows the work in the order a family usually does it:

| Part | What happens |
|---|---|
| [1. Set up a lineage](#1-set-up-a-lineage) | install the tools, start a project, open the dashboard |
| [2. Invite contributors](#2-invite-contributors) | the people who add material, and the review of what they add |
| [3. Add sources](#3-add-sources) | intake of every file; transcription of recordings; photographs catalogued |
| [4. Research records](#4-research-records) | the family's own papers and public records, catalogued by type and snapshotted |
| [5. Build the record](#5-build-the-record-timeline-genealogy-familypedia) | the timeline, the genealogy and the Familypedia |
| [6. Make stories and a book](#6-make-stories-and-a-book) | story units, the chapter map, writing, building, printing, narration |
| [7. Troubleshooting](#7-troubleshooting) · [8. Honest limits](#8-honest-limits) | |

It uses the sample project throughout: an invented family, the Calders. **Ruth Calder** (born
1938 in Duluth, Minnesota) is interviewed by her grandson **Sam**, and she talks about her
grandfather **Anders Calder**, who came from Norway. Everything about them is made up, so you
can open every file and see exactly what each stage produces.

Four things hold everywhere in Lineage, and the rest of this guide is how they are kept:
- **Nothing is invented.** A fact enters the record only from a source, and it carries a
  citation back to that source: a timestamp in a recording, a record's catalogue number, a URL.
- **Evidence has tiers.** Every fact is *witnessed* (the speaker saw it), *told* (someone
  named told them), *lore* (the family's story, source unclear) or *documented* (a record
  shows it). The tier travels with the fact into every view and every export.
- **Contradictions are kept.** When two tellings disagree, or the family and a record
  disagree, both stay, side by side, and the disagreement is shown. Nothing picks a winner
  silently.
- **A person decides.** Machines propose: tags, genealogy links, chapter maps, connecting
  sentences. People accept them. The places where a person must decide are named, and the
  tools stop there.

---

## 1. Set up a lineage

### 1.1 What you need

**The material.** Whatever the family has. Recordings in any common format (m4a, mp3, wav,
aac, flac, aiff, ogg, opus, wma, mp4 or mov; phone voice memos are fine), photographs and
scans, PDFs, letters, Word documents, notes, links. Originals are only ever read, never
changed.

**A Claude subscription and Claude Code.** The model work (understanding sources, the
timeline, the genealogy rebuild, story units, shaping, captions, the introduction) is done by
[Claude Code](https://claude.com/claude-code) following the rules in `.claude/skills/`. You
talk to it in plain English ("where are we?", "build the timeline", "shape the units for
chapter 3") and it runs the scripts and writes the files. Text is sent to Anthropic while it
works; audio is not (see [PRIVACY.md](../PRIVACY.md)).

**A Mac or Linux computer.** Windows is not tested. Apple Silicon works, but speech
recognition runs on the CPU there, because the engine has no Metal backend. An NVIDIA GPU
on Linux makes it much faster.

**Software:**

| Tool | Why | Install |
|---|---|---|
| Python 3.10+ | everything, including the dashboard | usually present; on Debian/Ubuntu also `apt install python3-venv` |
| ffmpeg | reads recordings | `brew install ffmpeg` / `apt install ffmpeg` |
| poppler (`pdfinfo`, `pdffonts`, `pdftotext`) | text from PDFs at intake; page counts and the print preflight | `brew install poppler` / `apt install poppler-utils` |
| tesseract (optional) | OCR of scans and image-only PDFs at intake | `brew install tesseract` / `apt install tesseract-ocr` |
| WhisperX, pyannote, PyTorch | speech recognition and speaker labels for recordings | `make install-transcribe` (pinned versions) |
| [Typst](https://github.com/typst/typst#installation) | rendering stories as pages, and the printed book | `brew install typst`, or see Typst's install page |

**Fonts.** EB Garamond is bundled in `fonts/` under the SIL Open Font License, and every
build points Typst at it. You don't need to install anything. The one exception is the map
tool (section 6.6), which uses EB Garamond only if it's installed system-wide.

**Disk and network.** The first transcription downloads about 5 GB of models. Each hour of
audio needs about 110 MB more for a working copy. The first book build downloads one small
Typst package (`droplet`, for the drop caps). After that, everything except the model work
and the research runs offline.

**A Hugging Face token** (only if you have recordings). [Hugging Face](https://huggingface.co)
is where the speech models are published. The speaker-labelling model (pyannote) is *gated*:
it's free, but its authors ask you to accept their licence and share contact details before
you download it. The token is how the download proves you've done that. **The model runs on
your computer. The token is only used to download it, and no audio is ever sent.** To set it
up once:

1. Create a free account and a **Read** token at <https://huggingface.co/settings/tokens>.
2. While logged in as that same account, open both of these pages and accept the
   conditions on each:
   - <https://huggingface.co/pyannote/speaker-diarization-3.1>
   - <https://huggingface.co/pyannote/segmentation-3.0>

   The first model depends on the second, and accepting only the first is the usual mistake.
3. Put it in your shell, never in a file in the project:
   ```sh
   export HF_TOKEN=hf_xxxxxxxxxxxxxxxx
   ```

Without a token you can still transcribe. The speakers just stay unlabelled until you run
the diarization step later.

### 1.2 Install the tools

```sh
git clone https://github.com/rexsaurus/Lineage.git ~/Lineage
cd ~/Lineage
make install              # Python venv in .venv with the build tools; checks for typst
make install-transcribe   # adds WhisperX + pyannote to the same venv (a large download)
make sample               # optional: proves the build works (see the README)
```

### 1.3 Start a lineage

A family's lineage lives in its **own folder**, outside the repo, so your family's material
never mixes with the public code:

```sh
make new PROJECT="$HOME/lineages/calder"
```

Use `$HOME` rather than `~`. In zsh, the default shell on macOS, `PROJECT=~/lineages/calder`
is not expanded, and make would create a folder literally named `~` inside the repo.

`make new` creates:

```
calder/
  book.yaml            names, the subject's birth year, print settings (fill this in now)
  lineage.lock         the Lineage release this project runs (section 1.5)
  Makefile             make dashboard, make lineage-version, make update-lineage
  CLAUDE.md            standing rules Claude Code reads at the start of every session
  local-overrides/     the few things specific to this family (section 1.5)
  .gitignore           keeps audio, photos, raw web caches and PDFs out of git
  .claude/skills  ->   a link to the skills in your Lineage checkout
  audio/               recordings (never modified)
  transcript/          raw JSON, verbatim and clean transcripts, sessions.csv, corrections.json
  facts/               timeline.csv, glossary.md, gaps.md (questions for you), records/
  content/units/       one file per story
  data/                archives.csv, chapters.csv, reader_glossary.csv, indexes
  chapters/            generated chapter files
  book/front/          title, copyright, dedication, contents, introduction
  photos/source/       original images (never modified)
  photos/print/        print-ready copies
  output/              PDFs and spreadsheets
```

The dashboard adds its own files as you use it: `sources/` (files added through the Sources
tab), `lineage.json` (settings), `data/sources.json` (the source index), `data/genealogy/`,
`data/familypedia/`, `data/requests.json`, and `.lineage/` (logs, rendered pages,
thumbnails). `app/README.md` lists everything it reads and writes.

### 1.4 Fill in `book.yaml`

`book.yaml` is the project's identity file, and every skill reads it first. (It keeps its
name from when the book was the only output; the dashboard's **Family details** page holds
the family-level identity: title, family name, summary, crest.) Here is the sample's:

```yaml
title: "The Lake Was Always There"
subtitle: "A Life of Ruth Calder"
narrator:                       # the main speaker on the recordings
  name: "Ruth Calder"
  label: "Grandma"              # speaker label used in the transcripts
  birth_year: 1938              # anchors every "when I was twelve"
  birthplace: "Duluth, Minnesota"
interviewer:                    # the family member who recorded the interviews
  name: "Sam Calder"
  label: "Sam"
other_speakers: []
family_figures:                 # relatives who get their own family-history section
  - "Anders Calder"
proper_nouns:                   # KEEP SHORT: surnames and odd place names only
  - "Calder"
  - "Duluth"
transcription_locked: true      # set once timestamps are cited (section 3.2)
print:
  trim: "7x10"                  # 6x9 | 7x10 | 8x10 | 8.5x11
  color: "bw"                   # bw | color
  printer: "kdp"                # kdp | ingramspark | lulu | blurb
  in_chapter_contents: false
narration:
  mode: "third_person"
  subject_name: "Ruth"          # how stories refer to the subject after first mention
front:
  introduction_title: "Introduction"
```

The field that matters most is **`birth_year`**. People date their lives by age: "when I
was twelve", "the year I started school", "after I turned sixteen". Every one of those
becomes a year by adding it to the birth year. Get it from a document if you can. If it's
off by one, every derived date in the timeline, the Familypedia and the book is off by one.

Two more to get right early:
- **`label`** values are the names that will appear on transcript paragraphs (`**Grandma**`,
  `**Sam**`). They must match what you put in the speaker map in section 3.2.
- **`proper_nouns`** are a *few* names the speech engine will otherwise mangle. Keep the list
  short (section 3.2 explains why).

### 1.5 `lineage.lock` and updates

A project **uses** Lineage; it doesn't contain it. It keeps only its own material (sources,
transcripts, stories, people, records, photos, settings). Everything else (skills, style
rules, templates, scripts, the dashboard) stays in Lineage and reaches the project as a
release. `lineage.lock` pins the release the project runs:

```sh
make lineage-version          # what this project runs
make update-lineage           # what a newer release would change, and which of your files it touches
make update-lineage APPLY=1   # install and pin it
make update-lineage TO=v0.4.0 APPLY=1   # a particular release instead of the newest
```

Releases install read-only under `~/.lineage/releases/<tag>`. An update never touches your
material. When a release changes something that would alter stories already generated (the
book template, fonts or skills), those stories are marked stale and listed, never rewritten.

Improvements found while working on one family's record go into Lineage and come back down
as a release, so every project gets them. Things only one family would want go in that
project's `local-overrides/`.

### 1.6 The dashboard

```sh
make dashboard                     # in a project: the dashboard of the pinned release
~/Lineage/app/lineage ~/lineages/calder   # or from a checkout, on any project folder
```

It runs on your own computer at `http://127.0.0.1:8777` and binds to `127.0.0.1` only.
`python3 server.py --demo` (in `app/`) shows invented sample content with a banner; it is
never the default.

There is no wizard. Every tab works whenever you open it and says plainly what it still
needs:

| Tab | What it's for |
|---|---|
| **Home** | story of the day, a featured relative, **Needs you** (one-click actions ordered by what they unblock), **Request more** (question lists built from open questions, gaps and unconfirmed links), counts, and an activity feed |
| **Sources** | every file the family has added, and its intake (section 3.1) |
| **Familypedia** | an article for every subject the material names (section 5.3) |
| **Genealogy** | the tree, derived from the sources with evidence on every link (section 5.2) |
| **Stories** | the written stories, rendered as pages, with narration (sections 6 and 6.10) |
| **Timeline** | every dated event, with tiers, conflicts and gaps (section 5.1) |

Behind the **settings gear**: **Family details** (title, family name, summary, crest),
**Connectors** (Google Drive, GitHub, Anthropic, OpenAI, ElevenLabs, agent CLIs),
**Contributors** (section 2) and **Project settings** (repo, Drive folder, narration voice,
writing style, story templates, trim and printer, the terminal command). A dot on the gear
means something needs attention.

The **Terminal** button in the header (or Ctrl+`) opens a drawer over any tab with a real
terminal running Claude Code in the project: the Genealogist, quick prompts, the pipeline
actions and the approvals list. Buttons that need real work done ("Generate", pipeline
actions) hand it to the Genealogist there.

### 1.7 Every session: set up the shell, then open Claude Code

```sh
export LINEAGE="$HOME/Lineage"     # put this line in your shell profile
source "$LINEAGE/.venv/bin/activate"     # so `python` is the Lineage venv
cd "$HOME/lineages/calder"
claude
```

Claude Code picks up the skills from `.claude/skills/` and the rules from `CLAUDE.md`. Start
each session by asking **"where are we?"**. It runs the status check and resumes at the
first unfinished stage. You can run the same check yourself:

```sh
make -C "$LINEAGE" status PROJECT="$PWD"
```

The output lists the pipeline's stages, each marked ✓ or ·, followed by a `NEXT:` line.

Everything in this guide can be done more than one way: in the dashboard, by asking Claude
("transcribe the recordings", "build the timeline", "rebuild the genealogy"), or by running
the commands shown here yourself. The commands assume you are in the project folder with the
venv active.

---

## 2. Invite contributors

A lineage is cooperative: many people add to one shared record. The family is the *subject*;
contributors are the people who add material about it, from wherever they are.

**Settings → Contributors** holds:
- **people and roles**: `contributor` (adds material), `reader`, `editor`;
- **invite links**, one per person, with an expiry, revocable;
- **requests outstanding**: what you've asked each person for (Home's **Request more**
  builds these lists from open questions, gaps and unconfirmed links, and saves them as
  asked or answered in `data/requests.json`);
- **the shared folder** contributors can drop files into (with the Google Drive connector);
- **the review queue**: material a contributor added waits here until someone accepts it.
  Home's **Needs you** says when something is waiting.

Members and invites are kept in `.lineage/family.json` in the project.

**What is not there yet.** The dashboard runs on your own computer, so **an invite link only
works on that machine** until the project is hosted, and the page says so. The management
side (people, roles, invites, requests, the review queue) is built; the **contributor-facing
view** behind an invite link waits for hosting (see `app/ROADMAP.md`). Until then, the
practical route is the shared Drive folder, email, or the post: you add what arrives through
the Sources tab and record who it came from.

---

## 3. Add sources

### 3.1 The Sources tab: intake

Drop files onto the **Sources** tab, or put them in the project and they are indexed where
they are. Every file runs the same visible stages, and each stage's result is kept in
`data/sources.json`:

| Stage | What happens |
|---|---|
| **Saved** (ingest) | the file is copied into `sources/` and given a SHA-256 hash. A file already in the project is recognised by its hash and not added twice. The original is never modified or renamed. |
| **Reading** (extract) | text comes out: a PDF's text layer, OCR for scans and image-only PDFs (needs tesseract), Word and text files directly. With an Anthropic key, an image also gets a short description and a transcription of any writing on it. It **never names a person from how they look**; a person is named only when writing on the item names them. |
| **Understanding** | a summary, the people, places and organizations named, a date range and the kind of item (letter, photo, certificate, record, transcript, recording, notes). With an Anthropic key this is a model pass; without one, a simpler heuristic. Everything here is marked as derived. |
| **Indexed** | the source joins the full-text search (`data/search_index.json`). |
| **Drive** (optional) | a copy goes to the project's Drive folder when the Google Drive connector is enabled and a folder is set. |

A stage that fails never loses the file; it shows the failure and can be re-run. Your edits
in the edit drawer (name, summary, people, dates, notes) are kept apart from the derived
values and always win, including across a **re-ingest**. Sources can be renamed, trashed
and restored (and then deleted permanently), and most actions work in bulk.

Tagging a source to the people and subjects it concerns happens in the Familypedia (section
5.3). A gallery and lightbox for photographs, and annotation and people tagging on the image
itself, are not built yet (`app/ROADMAP.md`, #5).

### 3.2 Recordings: transcription

A recording becomes useful when it becomes a timestamped, speaker-labelled transcript: then
every fact taken from it can point at the second it was said. A recording added through the
Sources tab shows **waiting for transcription** until its session's transcript exists;
re-ingest it afterwards and the transcript text becomes its searchable content.

Transcription runs on files in `audio/`. Copy the recordings there by any means. Then:

```sh
$LINEAGE/scripts/transcribe.sh --dry-run   # list sessions and the plan; do nothing
$LINEAGE/scripts/transcribe.sh --smoke     # the shortest session only: check it all works
$LINEAGE/scripts/transcribe.sh             # everything, shortest first
```

For each recording, this:
1. gives it a session ID (`S1`, `S2`, … in recording-date order) in `transcript/sessions.csv`.
   IDs never change once assigned, so adding a recording later never renumbers anything.
   If a file has no embedded date, fill in the `recorded` column by hand; it won't be
   overwritten.
2. makes a 16 kHz mono working copy in `transcript/work/`;
3. runs WhisperX (large-v3, with word timestamps) into `transcript/raw/S1.json`;
4. if `HF_TOKEN` is set, adds speaker labels (diarization).

It is safe to stop and restart. A session that already has its JSON is skipped, and output
is only moved into place when a session finishes, so a crash never leaves a half-written
file that looks done. A log is kept in `transcript/work/transcribe.log`.

Other useful forms: `transcribe.sh S3` (one session), `transcribe.sh --no-diarize` (speech
only, label speakers later). Environment overrides include `MODEL`, `LANGUAGE` (default
`en`), `DEVICE`, and `MIN_SPEAKERS`/`MAX_SPEAKERS`. By default it expects two speakers plus
any `other_speakers`.

#### Keep the initial prompt short

The speech engine accepts an "initial prompt" of vocabulary to listen for, and
`transcribe.sh` builds it from `proper_nouns`. **A long prompt gets echoed back into the
transcript as fake speech**: during a pause, the model "hears" your list of names read
aloud in the middle of a real answer. The script warns above 120 characters. Keep it to a
few surnames and unusual place names, and fix every other misspelling afterwards (below).

After every run, search the output for your prompt text. If an echo slips through, cut it at
render time in `transcript/corrections.json`:
- `drop_segments.patterns` drops a whole raw segment that is nothing but echo;
- `drop_word_runs.runs` removes an echoed phrase word by word from inside a real segment;
- `scrub_inline.patterns` strips an echo embedded inside a real paragraph.

#### Long recordings: chunked diarization

Speaker labelling gets disproportionately slower as files get longer. Measured on a CPU, it
took about 32 seconds of compute per audio-minute on 6–10 minute files but about 119 seconds
per audio-minute on a 34-minute file. A two-hour interview in one piece would take something
like 14 hours. So any session longer than 20 minutes is automatically labelled in
overlapping 10-minute windows, which are then stitched together. You can also run it
directly:

```sh
python $LINEAGE/scripts/diarize.py                    # every session without speakers
python $LINEAGE/scripts/diarize.py S1 S3
python $LINEAGE/scripts/diarize_chunked.py S5         # force chunking
python $LINEAGE/scripts/diarize_chunked.py S5 --chunk 600 --overlap 60
```

Each window logs a line like `stitched 2/2 by overlap`. Anything less than all speakers
matched deserves a listen at that seam.

#### Never re-run speech recognition once timestamps are cited

Two runs over the same audio never produce the same segment boundaries. Every citation in
the record (`[S2 00:14:07]`) would silently point at the wrong words. So:

- `transcript/raw/*.json` is **never edited**.
- Every fix (a misheard name, a speaker label, a prompt echo) goes in
  **`transcript/corrections.json`** and is applied when the Markdown is rendered. Start from
  the template: `cp $LINEAGE/scripts/corrections.example.json transcript/corrections.json`.
- Once anything cites a timestamp (the timeline, story units, the Familypedia's passages),
  set **`transcription_locked: true`** in `book.yaml`. After that, `transcribe.sh --force` and
  `diarize.py --force` refuse to run. New recordings can still be added; they just become new
  sessions.

#### GATE 1: confirm the speakers

Diarization labels voices `SPEAKER_00`, `SPEAKER_01`, … and the numbers mean nothing. Listen
to a minute of each session and decide which cluster is the subject. The interviewer
usually asks short questions, and the subject tells long stories. Then write the map into
`transcript/corrections.json`, using the labels from `book.yaml`:

```json
{
  "speaker_map": { "SPEAKER_00": "Grandma", "SPEAKER_01": "Sam" },
  "spelling": [ { "find": "\\b[Cc]aulder\\b", "replace": "Calder" } ],
  "drop_segments": { "patterns": [] },
  "scrub_inline": { "patterns": [] }
}
```

Then render:

```sh
python $LINEAGE/scripts/render_transcripts.py
```

This writes three layers:
- `transcript/verbatim/S1.md`: every word, with low-confidence words marked `[?word?]`;
- `transcript/clean/S1.md`: fillers (um, uh) and stutters removed, everything else kept. This
  is **the layer everything quotes and cites**;
- `transcript/master.md`: all clean sessions in order.

A clean paragraph looks like this:

```
**Grandma** [S1 00:00:29] When I was little, maybe seven or eight, I'd walk my dad's lunch down to the ore dock. A tin pail. ...
```

The render prints a line per session ending in `unmapped none` when every voice has a name.
If Claude is running this stage, it stops here and shows you three sample turns per speaker
to confirm. **Nothing is written until you say the mapping is right.**

One limitation: `render_transcripts.py` applies a single `speaker_map` to every session.
Cluster numbers can come out swapped from one session to the next. If that happens, you can
render that session by hand with the skill's converter, but this skips the spelling and echo
fixes, and a later full re-render will overwrite it:

```sh
python .claude/skills/interview-transcriber/scripts/whisperx_to_md.py transcript/raw/S3.json \
  --session S3 --map SPEAKER_01=Grandma --map SPEAKER_00=Sam \
  --verbatim transcript/verbatim/S3.md --clean transcript/clean/S3.md
```

Also confirm the basics in `book.yaml` (names, birth year) at this gate. Claude keeps a
spelling list in `facts/glossary.md`. Each spelling you approve goes into
`corrections.json` → `spelling`, and you re-render.

### 3.3 Photographs: catalogue with evidence

People will treat a photograph's label as fact for generations. So every label says what it
rests on, every guess looks like a guess, and nothing that isn't a photograph can pass for
one. The photo-processor skill holds the full rules.

A family photos document (Word, PDF, an exported Google Doc, a zip or a folder of scans) is
split into catalogued images:

```sh
python .claude/skills/photo-processor/scripts/extract_photos.py "Family photos.docx"   # or a PDF, zip or folder
```

Images get permanent IDs (`P001`, …). Originals are copied to `photos/source/` and never
edited, and any nearby text is saved as `original_caption`, which is often the best evidence
there is. Export a Google Doc as .docx first. Everything about each image goes in
`photos/photo_index.csv` (which the Familypedia reads), and each identification records its
**basis**, strongest first:

1. **inscription**: writing on the photo or its back, a printed lab date;
2. **document**: a caption in the family's photo document, an archive catalogue, the owner's word;
3. **transcript**: the subject describes this scene (cite `[S2 00:31:05]`);
4. **visual estimate**: clothing, cars, print format. Never better than medium confidence.

**Never name a person from facial resemblance.** A wrong name in the record is worse than
none. Without an inscription, document, transcript or the owner's word, describe instead
("unidentified woman, about 30"). Dates are exact only if inscribed; otherwise they're a
range or "about 1925". Only you or the owner can mark an image `confirmed`.

Generated images are marked as generated everywhere: rows in `photos/photo_index.csv` whose
subject starts "Illustration" show as illustrations in the Familypedia, and section 6.6 sets
the rules for using one in a book.

---

## 4. Research records

The family's version is half the record. The other half is what the archives hold: census
returns, military rosters and pension files, ship registers and crew lists, digitized
newspapers, museum and library catalogues, period books. Lineage catalogues both, snapshots
what it finds, and sets the records beside the family's version. The records-archives skill
does this work; ask Claude to "research Anders Calder" or "index the family's papers".

### 4.1 The family's own papers

`data/archives.csv` is an index of what the family holds and what it has lost: Bibles,
letters, discharge papers, albums, the recordings themselves, heirlooms. Each row is typed
(`photographs · letters · documents · bible · military · legal · recordings · heirlooms ·
institutional · other`), says who holds it in general terms, and has a status (`confirmed ·
mentioned · unknown · lost · destroyed · institutional`). **Lost and destroyed items get rows
too**: "the letters burned in 1962" saves a future relative years. Street addresses and phone
numbers live only in the private column, and a living holder is printed only with
`print_permission: yes`.

```sh
python .claude/skills/records-archives/scripts/archives_tools.py check   # flags addresses/phones in public columns
python .claude/skills/records-archives/scripts/archives_tools.py asks    # follow-up list, one call per relative
```

### 4.2 Public records

Research beyond the family's own material is welcome anywhere in the record. **Check the
records first**, because archives often hold the person.

- **Free and public sources first**: national and state archives, the Internet Archive and
  HathiTrust for period books, Chronicling America for newspapers, free census indexes,
  museum catalogues. Note any paywalled source as such, and give the free route if there is
  one.
- **Fetch politely.** Automated fetching respects robots.txt and site terms, waits at least
  2 seconds between requests to a site, and uses no logins or CAPTCHA tricks. **Never put
  anyone's name, email or credentials in a request**; the User-Agent names the project only
  (`research.user_agent` in `book.yaml`). `fetch_records.py` does this for a short list of
  record URLs and logs each one in the chapter's dossier:

  ```sh
  python $LINEAGE/scripts/fetch_records.py anders-calder https://example.org/roster/page-214
  ```
- **What only a person can reach.** A page behind a login, a bot check, or a robots.txt that
  bars automated crawlers goes on `research/MANUAL-LOOKUPS.md` (the template is in
  `$LINEAGE/templates/research/`): what to find, where, the search terms, why it matters.
  You do those lookups yourself, in your own browser and your own accounts, one record at a
  time; if you choose, a browser assistant can do them inside your own logged-in session at
  your direction. Never CAPTCHA solving, bot-check workarounds, anyone else's credentials, or
  bulk downloading. Results go in `research/manual-lookups-results.csv`, transcribed exactly.
  Letters and forms to archives are logged in `research/REQUESTS.md` with their replies.
- **A dossier per chapter.** Each chapter with research keeps `dossiers/<slug>/`: your
  requests for that chapter, a log of every search (blocked ones too), **every** source found
  or scraped (`SOURCES.csv`), the evidence and whether it confirms or contradicts the family,
  and lessons learned. `dossier.py new <slug>` makes one; `dossier.py records <slug>` writes
  the chapter's THE RECORDS from it; `dossier.py check <slug> <chapter>` proves nothing is
  missing (the chapter-dossier skill).
- **Fact sheets before prose.** For an episode worth building out (a voyage, a regiment, a
  mill town), the research goes first into `facts/records/<person>/context_<topic>.md`, one
  fact per bullet with URL, page and a confidence note. Anything written later is written
  from the sheets, never from memory.
- **Catalogue every source by type.** Each research folder keeps a `sources.csv` (`id,
  title, url, holder, type, date_retrieved`, or a `sources.json`). The Familypedia reads
  these and shows each record on the articles it concerns, with archive, number, link and
  retrieval date.
- **Snapshot what you use.** Raw downloads go in `facts/records/_raw/`, which is gitignored
  because catalogues often forbid reproduction. This is what lets the record outlive the
  links. Then export the shareable text into the project:

  ```sh
  python $LINEAGE/scripts/export_sources.py --dry-run
  python $LINEAGE/scripts/export_sources.py --restricted '^museum/'
  ```

  This copies text files to `facts/records/sources/` and writes `MANIFEST.csv` listing
  *every* raw file with its size and SHA-256 hash, plus whether it was exported and why not.
  Restricted paths are never copied. Rules can live in `facts/records/export.yaml`; see the
  script's header.

Low-confidence OCR from a record goes into the fact sheets flagged as such, and never into
anything written without being checked.

A dashboard screen for pasting record links and scanning them into the typed catalogue, with
a by-archive view, is not built yet (`app/ROADMAP.md`, #7). Today the research runs through
Claude Code and the files above.

### 4.3 Routes

Journeys (a crossing, a voyage, a regiment's march) are kept as sourced CSVs, one row per
recorded point:

```csv
seq,date,place,lat,lon,kind,aboard,source,label,gap_before
1,,Bergen,60.39,5.32,port,subject,<record ID or URL>,Bergen,
2,,New York,40.70,-74.01,port,subject,<record ID or URL>,New York,yes
3,,Duluth,46.78,-92.10,port,subject,<record ID or URL>,Duluth,
```

Only `seq`, `lat` and `lon` are required, but every point should carry a `source`. A file
named `*track*.csv` or `*route*.csv` under `facts/` gives the Familypedia its ports, positions
and map coordinates. A new `leg`, `gap_before`, or a row without coordinates is an
**unrecorded leg**, and it is shown as unrecorded rather than drawn. Section 6.6 turns the
same file into a printed map.

### 4.4 When records contradict the family

**Keep both, and say so.** Never silently correct the family's story, and never silently
repeat it. The timeline keeps both tellings (section 5.1), the genealogy rebuild keeps
contradictions for review (section 5.2), and the Familypedia shows the family's tiers and
"what the records show" as separate sections of the same article. Log the conflict in
`facts/gaps.md`, where it becomes a question for whoever can answer it. When the
disagreement reaches a written story, section 6.5 says how to tell both.

Say honest gaps out loud ("Which route the boat took that winter, no surviving record
says") and never fill them. Don't give an ancestor a famous battle or ship their unit or
crew did not have.

Include **a note on the name** whenever a record could be confused with a similar one, such
as two ships or two men with the same name: say which is which, and why, and keep the
reasoning in `facts/records/<person>/`. The worked example
([EXAMPLE-CHAPTER.md](EXAMPLE-CHAPTER.md)) ends with exactly such a note about two
whaleships called _Hannibal_.

---

## 5. Build the record: timeline, genealogy, Familypedia

### 5.1 The timeline

People don't tell their lives in order. `facts/timeline.csv` puts every event on one line,
and each date shows how it was worked out. Ask Claude to "build the timeline" (the
timeline-organizer skill), then check its work:

```sh
python .claude/skills/timeline-organizer/scripts/timeline_tools.py sort
python .claude/skills/timeline-organizer/scripts/timeline_tools.py check   # fix whatever it reports
python .claude/skills/timeline-organizer/scripts/timeline_tools.py md      # facts/timeline.md, by decade
```

#### Resolving relative dates

Each row records the arithmetic in `date_basis`, and how it will be said in `date_display`.
From the sample:

| event | quote | date_basis | date_display | confidence |
|---|---|---|---|---|
| E003 Ruth walks her father's lunch to the ore dock | "maybe seven or eight" | `'maybe seven or eight' + birth year 1938` | about 1945 | medium |
| E004 The big snow; school closed for a week | "around 1950, I think" | `'around 1950, I think'` | around 1950 | medium |
| E005 Ruth begins nursing school | "nursing school in 1956" | stated | 1956 | high |

The rules:
- **Never invent precision.** There's no month or day unless she said it or a document
  gives it.
- **Hedges carry over.** "Around 1950, I think" stays "around 1950". Nothing downstream may
  state a date more precisely than `date_display`.
- "Right after the war" is resolved by saying which war and why, labelled as historical
  context.
- A bare "yeah" to a leading question ("Was that 1952?" "Yeah.") gets low confidence.

#### Conflicts are kept, not settled

When two tellings disagree, or the family's story and a document disagree, **both stay**.
The `conflicts` column says what disagrees with what, confidence drops to low, and a
question for you goes into `facts/gaps.md`. Nobody picks a winner silently.

#### The Timeline tab

The dashboard draws the same file as a vertical spine with decade bands and a year rail.
Each card shows the date and its precision, the tier, the people, the place, the citations
and links to stories. Conflicts get their own cards; **gaps** get cards with "Add to
questions"; events with no date wait in an undated drawer. Filter, search, star, and export
as SVG, PNG or a printable appendix. (The printed book also takes an appendix, "A Timeline",
built by `make draft` from the high- and medium-confidence rows.)

### 5.2 The genealogy

The **Genealogy** tab derives the family tree from the sources. **Every link carries its
quoted evidence: no evidence, no link.**

- **Rebuild** asks Claude to read the material and propose the tree; each proposed link is
  checked against the passage it quotes. The proposal is saved in
  `data/genealogy/proposed.json` and shown as a **review of what changed** since the approved
  tree. Contradictions are kept for you, never resolved silently. Nothing changes until you
  apply it (`derived.json`; earlier versions in `history.json`).
- **Your edits** (merge two people, split one, add a link or a note) are kept in
  `data/genealogy/mine.json` and survive every rebuild.
- **Views**: a pan-and-zoom tree with descendant, ancestor and hourglass layouts, nodes for
  unknown parents, and line styles by evidence tier; and a Cast view of everyone.
- **GEDCOM** in and out. An imported GEDCOM arrives **unconfirmed**: it is someone else's
  claim until the material supports it.
- **Exports**: SVG, PNG and a printable chart. **Living people are left out of exports.**

### 5.3 The Familypedia

The Familypedia is the record's encyclopedia: an article for every subject the material
names, of nine types:

**person · place · event · vessel/vehicle · organization/unit · object · publication ·
occupation/trade · theme**

Each article has a lead from the material, a typed infobox, **tier sections** (witnessed ·
told · lore · what the records show), the passages that mention it, its sources with
thumbnails, typed records with archive, number, link and retrieval date, photographs and
marked illustrations, stories, related articles, backlinks, open questions, and a separate
"Beyond the family" section for public background. Browse by type, A–Z, most material or
needs more; search the full text with type filters; follow `[[links]]` across types.

**Where articles come from.** Only the project's files; everything is optional, and a
project with less material simply has fewer articles. The main inputs:

| Input | Gives |
|---|---|
| `content/units/*.md` front matter `people`, `places`, `subjects` (`"vessel: Hannibal"`) | subjects, and the passages that mention them (section 6.2) |
| `facts/timeline.csv` | events, their people and places, tiers, conflicts |
| `facts/people/*.md` (`# Name`, `Also called:`, `Relationship to …:`, `Dates:`) | person profiles and other names |
| `knowledge/graph.json` (or `nodes.csv` + `edges.csv`) | typed subjects, records and relations (`crew_on`, `master_of`, `served_in`, `held_by`, …) |
| `data/archives.csv`, `facts/records/**/sources.csv` | the records catalogue and research sources (section 4) |
| `facts/**/*track*.csv`, `*route*.csv` | ports, positions and map coordinates (section 4.3) |
| `photos/photo_index.csv` | photographs, with illustrations marked (section 3.3) |
| `facts/gaps.md`, `facts/records/**/context_*.md` | open questions; public background for "Beyond the family" |

`app/README.md` has the full table, including where map coastlines come from. **No map tiles
are ever fetched**: the map is drawn from the records' own coordinates, with unrecorded legs
shown as unrecorded.

**Tagging.** Any source, record, photograph or event can be tagged to any article, one at a
time or in bulk from the Records and Photographs views. Lineage **suggests** tags only from
names written in the item, shows the words that name them, and tags nothing until you
accept: no faces, no resemblance. Tags, your notes, infobox values, "same as" merges and
subjects you create are saved under `data/familypedia/`, and they are yours: rebuilding from
the material never overwrites them.

---

## 6. Make stories and a book

Everything above is the record. This part turns it into **stories** (written pieces, which
the dashboard renders as pages and can narrate) and a **printed book**. It is an export: the
record is complete without it, and the book can be rebuilt from the record at any time.

The book pipeline adds two more points where a person decides, after GATE 1 (section 3.2):

| Gate | When | What you decide |
|---|---|---|
| **GATE 1** | after transcription | which voice on the tape is the subject and which is you; the basics in `book.yaml` |
| **GATE 2** | after the chapter map is proposed | how the book is organized, before any prose is written |
| **GATE 3** | at the end | that the book is finished: every bridge approved, every flag dealt with |

The dashboard calls the written pieces **stories**; the printed book still has chapters,
and the files keep their names (`chapters/`, `data/chapters.csv`).

### 6.1 How it fits together

```
transcripts + records ─► story units ─► chapter map ─► chapters ─► book PDF
                          content/units/  data/chapters.csv  chapters/   output/
                                              ▲                          ▲
                                           GATE 2                     GATE 3
```

Story units are worth cutting even if you never print a book: their `people`, `places` and
`subjects` front matter is how the Familypedia knows which passages of which recording
concern which article.

### 6.2 Story units

A **story unit** is one story, memory or explanation that stands on its own: typically one
to five minutes of tape, stored as one file in `content/units/`. Each unit holds the exact
clean transcript excerpt (`## Source`), its metadata (people, places, subjects, timeline
events, part, era or relative), and later the finished prose (`## Shaped`) plus notes for
you.

**Why units instead of chapters?** Chapter boundaries move. A life stage splits in two, or
an uncle turns out to deserve his own chapter. Because chapters are *generated* from units,
moving a story is a one-line metadata change and a rebuild, not a rewrite. All editing
happens in units, and generated chapter files are never edited by hand.

Signs that a new unit is starting: a question that changes the subject, a jump in time or
place, "and another time…", "that reminds me…". A story told in pieces across sessions is
**one** unit with several spans. A story told twice is one unit: the fuller telling gets
shaped, and the differences go in its notes.

#### `content/boundaries.csv`

You (or Claude) list the cut points. For the sample it would be:

```csv
session,start,id,title,part,section,tier,people,places,events,flags
S1,00:00:02,U001,The boots,family,Others in the Family,told,Anders Calder,"Norway;Duluth, Minnesota",E001;E002,
S1,00:00:29,U002,The ore dock,life,The Ore Dock,,,"Duluth, Minnesota",E003,
S1,00:00:48,U003,The big snow,life,The Ore Dock,,Pete,"Duluth, Minnesota",E004,
S2,00:00:03,U004,The shoes,life,Walt and the Cabin,,,"Minneapolis, Minnesota",E005,
S2,00:00:17,U005,The dance,life,Walt and the Cabin,,Walt,"Minneapolis, Minnesota",E006,
S2,00:00:36,U006,The cabin,life,Walt and the Cabin,,Walt,"Pike Lake, Minnesota",E007,
```

- `start` is the timestamp of the unit's first paragraph, as printed in
  `transcript/clean/`. A unit runs until the next cut in that session.
- `id` `X` excludes a span (warm-up, a phone ringing, logistics, a prompt echo). Put the
  reason in `title`; the span goes to `content/excluded.md`.
- The same id in two sessions makes one unit with two spans.
- Lists are `;`-separated. Quote any cell that contains a comma.
- `part: family` units take a relative's name as `section` and a `tier` (section 6.5).

Then generate the unit files and check coverage:

```sh
python $LINEAGE/scripts/make_units.py --check    # coverage only
python $LINEAGE/scripts/make_units.py            # write content/units/U###-*.md
```

#### The coverage check

Because each cut runs to the next one, every paragraph lands in exactly one unit or in the
excluded list. That makes loss checkable instead of a hope:

```
paragraphs: 14 in 2 session(s)
  in units:   14  (6 units)
  excluded:   0  (0 spans)
  UNCOVERED:  0
```

The script exits with an error if anything is uncovered. Two more checks:

```sh
python .claude/skills/content-separator/scripts/units.py coverage   # every subject paragraph accounted for
python .claude/skills/content-separator/scripts/units.py check      # missing fields, uncited or Q&A-style Shaped text
```

Re-running `make_units.py` after you change boundaries is safe for the fields it knows:
`chapter`, `order`, `lead_in`, `break_before`, `status`, `## Shaped` and `## Notes` carry
over. Frontmatter it doesn't know about is rewritten away, though. That includes
`lead_in_approved`, `kind`, and any `date_display` you added by hand. An apparatus unit
(section 6.5) has no spans, so it shows up as "not in boundaries.csv". Leave it in place and
don't use `--prune` while you have one. New units start with `break_before: false`; set it to
`true` where you want a ❧ break between stories.

### 6.3 The chapter map

Claude proposes the map (the chapter-index-builder skill) from the timeline and the units,
not from the order things were said. It writes the map to `data/chapters.csv`.

**Two parts:**
- **The family part** ("Those Who Came Before"), first by default: **one chapter per named
  relative, titled with just the name**, oldest generation first. Relatives with only a
  story or two share a chapter called **"Others in the Family"**, each under their own
  heading.
- **The life part**: the subject's own life, **chronological**, one stage or place per
  chapter. A theme that spans decades can be its own chapter, placed where it peaks.

**Chapters are at least ten pages** by default (`chapters.min_pages` in `book.yaml`, measured
by building; `make chapter` tells you when one is short). A chapter gets there with real
material: the subject's full stories in their own words, the records, built-out sourced
context. Never with padding. Where the material is thin, **chapters are combined** (a relative
with one story joins "Others in the Family"; two thin stages of life become one) rather than
printed thin. Every chapter ends with **THE RECORDS**, listing every source found and used.

**Sizing.** Aim for roughly 1,000–2,500 words of the subject's speech per life chapter.
Under about 600, merge with a neighbour; over about 3,000, split at a natural turn. A
relative's chapter can be a single page.

**Columns per chapter** (`data/chapters.csv`):

| column | what goes in it | sample |
|---|---|---|
| `chapter`, `file`, `title`, `part` | order, file name, title, part name | `2`, `chapters/02-the-ore-dock.typ`, `The Ore Dock`, `Her Life` |
| `setting`, `dates` | the place-and-years line under the title | `Duluth, Minnesota`, `1938–1950` |
| `summary_line` | a short line in the old-book manner, never a list | `On Tin Pails and Tunnels` |
| `epigraph`, `epigraph_source` | the chapter's one epigraph: public-domain, verified (section 6.4) | |
| `columns` | `2` (two justified columns) by default; `1` for a chapter in one measure | `2` |
| `summary` | 2–4 neutral sentences, for you and the introduction | |
| `status` | `proposed` → `approved` → `drafted` → `reviewed` → `final` | `approved` |

Titles are plain stage or place names, or a phrase the subject said.

#### GATE 2: approve the map

Claude shows you a simple outline (number, title, setting, years, one line each). **Nothing
is shaped or assembled until every row's `status` is past `proposed`.** Shaping against the
wrong structure is the most expensive mistake in the pipeline, so take your time here.
Move stories around, merge, rename.

After approval, each unit gets a `chapter` and an `order`, and the chapter number is written
back into the timeline. To see what lands where, and what landed nowhere:

```sh
python .claude/skills/chapter-generator/scripts/assemble.py --list
```

A unit that fits nowhere goes on your list. It is never silently dropped.

### 6.4 Writing

The stories are a **biography written about the subject in the third person, past tense**,
by the family member who recorded it (you, the *author*). They should read like a real book,
not an interview. The master rulebook is `.claude/skills/memoir-style-guide/SKILL.md`, and
every other writing skill defers to it. Here are the rules that matter most.

#### The rules

**Voice**
- Third person, past tense: "Ruth left Duluth in 1956." The subject never narrates.
- **The author never appears in a chapter.** Your voice belongs in the introduction and an
  optional afterword only. No "my grandmother", no "I asked her".
- **No interview format anywhere.** No questions, no "when asked", no "she recalled in an
  interview", no speaker labels. A question's content is folded into the answer as a plain
  statement, and both timestamps are cited. (If `#asked` ever appears in a chapter, the
  template refuses to compile.)
- Tone: warm, plain, lightly wry about the world, never at the subject's expense.

**Facts: narration may restate, order and connect. It may not add.**
- No feelings, thoughts or motives she didn't state. No weather, sensory detail or dialogue
  she didn't give. No "she must have…".
- **Hedges carry over.** "I think it was '72" becomes "around 1972", never "in 1972".
- **A bare "yeah" to a leading question is a weak fact.** Hedge it or flag it; don't state it.
- Interpretation ("it was the end of her childhood") goes in a **bridge** for you to approve.
- Unclear names, dates or relationships become questions in `facts/gaps.md`, never guesses.
- **Sensitive material** (living people, legal trouble, health, violence, trauma) is written
  accurately and flagged with `// REVIEW:`. **It is never cut or softened by the writer.**
  You and the family decide what prints.

**Quotation: how her voice survives**
- About one or two direct quotes per page. **A chapter with no quotes has lost the subject.**
- Quotes are **exact** from `transcript/clean/`. Only fillers and false starts are removed,
  with "…" for an internal cut. Her grammar and dialect stay.
- Quote the verdicts, the humor and the punchlines, and paraphrase the logistics.
- Short quotes run inline. Passages of 40+ words go in `#verbatim[...]`, at most a few per
  chapter.
- **Never invent or tidy a quote.** If the wording isn't on tape, it's paraphrase.

**Sourcing: every paragraph ends with a comment that never prints**

```typst
// src: [S1 00:00:29]-[S1 00:00:47]        what the paragraph rests on
// src: transition                          pure connective text; no new facts allowed
// src: context                             a paragraph about the world, with...
// context: <the claim> — <source, page or URL>   ...one line per borrowed fact
// src: record R014                         a document from data/archives.csv
// REVIEW: <a doubt or sensitive item for the author>
// NOTE: <a research caveat>
```

**Context about the world** (what Duluth was like then, what a nurse earned) is welcome, but:
it describes the world, never the subject. It stays local to the chapter's place and years.
Every fact is sourced on a `// context:` line (a real source, never "general knowledge") and
listed in the chapter's THE RECORDS, and it takes up no more than about a quarter of a chapter. Juxtaposition is allowed and causation is
not: "That spring the mill cut its hours" is fine, but "so she left" is not unless she said
so. For a real example, see section 7 of [EXAMPLE-CHAPTER.md](EXAMPLE-CHAPTER.md):

```typst
// context: Elmo P. Hohman, The American Whaleman (1928), p. 15 (green hand's lay 1/200),
// p. 240 (about 20¢ a day vs about 90¢ for unskilled labor ashore)
```

**Epigraphs**: each chapter opens with one (two allowed in a family-history chapter; none if
you ask), from a writer of the chapter's place and time, public-domain literature only, never quoted from memory, and checked with
`verify_quotes.py` against a saved copy of the text listed in `facts/sources/works.csv`.

#### Before and after: one story, three ways

This is the sample's unit U002. Here is the clean transcript:

```
**Grandma** [S1 00:00:29] When I was little, maybe seven or eight, I'd walk my dad's lunch
down to the ore dock. A tin pail. And the dock was so tall you had to tip your head all the
way back. The trains ran right out on top of it.

**Sam** [S1 00:00:44] Were you scared of it?

**Grandma** [S1 00:00:45] No. Well, yeah. A little.
```

**WRONG: smoothed.** This version reads nicely and is full of things she never said:

> On warm summer mornings, seven-year-old Ruth proudly carried her father's lunch down to
> the ore dock. The towering structure terrified her: "you had to tip your head back to see
> the top." She loved those walks with all her heart.

- "warm summer mornings": the weather and season are invented.
- "seven-year-old": she said "maybe seven or eight". The hedge has been firmed up.
- "proudly", "loved those walks with all her heart": feelings she never stated.
- "terrified her": her answer was "No. Well, yeah. A little.", given to a leading question.
  A weak, wavering yes has been turned into a strong fact.
- The quote has been tidied. The checker catches it (this is its output on a test file
  holding the paragraph):

  ```
  QUOTE NOT FOUND chapters/99-wrong.typ:4: "you had to tip your head back to see the top."
      not in transcript: "you had to tip your head back to see the top"
  ```

**WRONG: interview format.** This version is accurate and still wrong:

> When Sam asked whether the dock scared her, Ruth recalled: "No. Well, yeah. A little."

- The interviewer has walked into the chapter, and "when … asked" is interview format. The
  reader should never see the tape recorder. (Written as `Q:`/`A:` lines it's worse.)

**RIGHT.** This is the sample's shaped text, exactly as it is in
`content/units/U002-the-ore-dock.md`:

```typst
When she was seven or eight, as best she remembered, Ruth walked her father's lunch down to
the ore dock#idx("Duluth, Minnesota!ore dock") in a tin pail. The dock was so tall "you had to tip your head all the way back,"
and the trains ran right out on top of it. Whether it frightened her, she never quite
settled: "No. Well, yeah. A little."
// src: [S1 00:00:29]-[S1 00:00:47]
```

- The hedge survives ("as best she remembered").
- Logistics are paraphrased (the pail, the trains), and the vivid line is quoted exactly.
- The question is gone, but its content survives: "Whether it frightened her" folds Sam's
  question into the narrative, and her wavering answer is quoted rather than resolved.
- `#idx(...)` marks an index entry at first mention. It is invisible in print.
- `// src:` cites the span, including the question's timestamp.

Two more patterns from the sample:
- **Folding a question.** Sam asked "And that's where you met Grandpa?" and she answered "At
  a dance. A church dance, in 1959." The book says: "She met Walt at a church dance in 1959."
  (U005)
- **Keeping a hedge.** "We built the cabin on Pike Lake ourselves, starting in, oh, 1964 or
  so" becomes "Starting in 1964 or so, Ruth and Walt built a cabin on Pike Lake with their
  own hands." (U006)

#### Bridges

A **bridge** is any sentence the writer added that isn't plain fact: an interpretation, or a
connecting line that might color the story. In the sample, unit U005 has this lead-in:

```yaml
lead_in: "Three years later, the thing she remembered best about Minneapolis had nothing to do with nursing."
```

Nothing on the tape says that, so it's assembled as `#bridge[...]`. In drafts it prints
highlighted, like this: ⟦BRIDGE: …⟧. **The final build refuses to compile while any bridge
remains**, and **an unapproved bridge is never narrated**. To decide on one:
- **Approve a lead-in:** add `lead_in_approved: true` to that unit's frontmatter. It then
  prints as plain text.
- **Approve a bridge inside Shaped text:** replace `#bridge[...]` with the sentence itself.
- **Reject it:** delete it.

`make status` shows how many bridges are pending, and the Stories tab can filter to the
stories that still have them.

#### Writing the units and checking quotes

Ask Claude to "shape the units for chapter 2" (content-separator plus the style guide). It
writes each unit's `## Shaped` section, usually with:

```sh
python $LINEAGE/scripts/shape.py U002 drafts/U002.md        # writes ## Shaped, status: shaped
python $LINEAGE/scripts/shape.py U002 --status approved     # only you set approved
```

Then check every quotation in the chapters against what the subject actually said:

```sh
python $LINEAGE/scripts/verify_quotes.py --transcript chapters/[0-8]*.typ
```

This matches every double-quoted passage of three or more words against the subject's
paragraphs in `transcript/clean/`. Case and punctuation are ignored, and nothing else is. A
quote found only in the interviewer's words is reported as "check attribution". A quotation
from a letter or another relative is exempted by putting
`// quote-source: <where it's from>` in the same paragraph. `make draft` runs this check and
warns, and `make final` stops on any failure.

Before a unit or chapter is done, Claude runs the style guide's checklist. Read it yourself
at least once (section 9 of the style guide). The scripts catch speaker labels, `#asked`,
missing citations and misquotes. They do **not** catch "when asked" phrasing, invented
feelings or firmed-up hedges. Those need a reader.

### 6.5 Family-history chapters

Stories about people nobody alive has met are the most fragile part of any record. Usually
they're secondhand, sometimes contradictory, and once printed they become "what happened".
The family-history-chapters skill adds rules on top of the style guide. Read
[EXAMPLE-CHAPTER.md](EXAMPLE-CHAPTER.md) alongside this section: it's a real ancestor's
chapter, annotated rule by rule. The research behind such a chapter is section 4.

#### Tiers and the chain of telling

Every fact sits in exactly one tier:
- **witnessed**: the subject saw it herself;
- **told**: someone named told her ("as her father told it");
- **lore**: the family's story, source unclear ("that's what they always said").

A fact a record supports is **documented**, and its record is cited. The chain stays visible
in the prose: "According to Ruth's father, Anders crossed at sixteen", not "Anders crossed
at sixteen". Lore keeps its hedges.

The chapter's **first paragraph says what kind of material this is and who it passed
through**, and the opening section makes a promise: **"Where the records and the family
part company, this chapter says so."** The sample's chapter 1 does both in one paragraph
(`content/units/U001-the-boots.md`).

#### Line of descent

A box at the foot of the opening page runs from the earliest known ancestor down to the
living family, with marriages included. It's built only from documents and links you've
confirmed, and unconfirmed links are marked. From the sample:

```typst
#descent(
  ([Anders Calder (link from Norway unconfirmed)], none),
  ([Ruth's father], none),
  ([Ruth Calder (b. 1938)], [Walt]),
  ([their children and grandchildren], none),
)
```

#### A small family tree

When you'd like a picture of the family around an ancestor rather than a single line, the
chapter can carry a three-generation tree at the foot of its first page instead of (or beside)
the line of descent: parents, the ancestor and spouse, their children, and the line continued
under the right child. Same rules: documents and confirmed names only.

```typst
#family-tree(title: "The Family of Anders Calder",
  couple: ([Anders Calder (c.1875–?)], none),
  children: ([Ruth's father], [a sister (name not recorded)]), line: 0, descent: [and so to Ruth])
```

#### Anyone who served

For an ancestor who served in a war, the official service record comes first and is the
spine, and the chapter is built out around it in time order: the town they grew up in and the
country then; how the war drew their countrymen in, and those soldiers' reputation; how a
young soldier enlisted, was examined, trained and shipped; what their unit met when they got
there (its battles, weapons, generals); being sent home; and what veterans came home to.
First-hand accounts from soldiers in or near the unit (diaries, letters, memoirs, unit
histories) are quoted briefly and exactly, and saved so the quote check can verify them. A
sensitive entry in a record (a punishment, a court case) stays out of the prose until you
decide. Details: family-history-chapters skill, §6a.

#### THE RECORDS

Every family-history chapter, and any chapter with `// context:` lines, ends with a
small-type **THE RECORDS** block after the closing paragraph. It lists where each documented
claim came from: catalogue numbers, record titles, database IDs, newspaper titles and dates,
books with years and pages, and links. It is drawn from the catalogue built in section 4.

```typst
#records(
  [*Census.* <census year, place, page and line>: Anders Calder, <age>, <occupation>.
   <where the free index is>. #link("https://…")],
  [*A note on the name.* <which of two similar records is meant, and why>.],
)
```

The angle-bracket parts are yours to fill in. The sample hasn't consulted any records yet,
and its `#records` block says exactly that. Include **a note on the name** whenever a
record could be confused with a similar one (section 4.4).

THE RECORDS and the photographs page (section 6.6) go in a final **apparatus unit** for the
chapter (`kind: apparatus`, same `section`, highest `order`, no spans), so they survive
reassembly. The sample keeps it inside U001 instead, which works for a one-unit chapter.

#### When documents contradict the family

**Print both, and say so.** Tell the life once, in order, with the record as the spine.
Where the family's version differs, tell it at that point, attributed ("The family
remembered his war differently…"). Let the record confirm what it can. Dates in narration
follow the record, with the family's date given as theirs. Log the conflict in
`facts/gaps.md` and mark it `// REVIEW:`. Section 4 of [EXAMPLE-CHAPTER.md](EXAMPLE-CHAPTER.md)
shows this done well: the family's "surgeon, drafted" set beside the records' "soldier,
enlisted", and the bounty money that turned out to be real.

#### Where the Records Are

`make draft` turns the printable rows of `data/archives.csv` (section 4.1) into the
back-matter appendix "Where the Records Are". Only rows with `print_permission: yes` print,
and private details never do.

### 6.6 Photos and illustrations in stories

Images are catalogued in section 3.3. Putting them on a page adds these rules.

#### Print copies

```sh
python .claude/skills/photo-processor/scripts/prepare_print.py --color bw
python .claude/skills/photo-processor/scripts/prepare_print.py --only P007 --crop P007=40,30,1880,1400
```

Allowed: rotating, cropping away the scanner bed or album page, converting to grayscale.
**Not allowed on a real photograph without the owner's say: colorizing, upscaling, face
restoration, or removing people or objects.** These fabricate detail. Flag the damage and let
the owner decide whether to get a better scan or a professional restorer.

**Resolution: 300 ppi at the printed size; 200 ppi is a hard floor.** Below that, print it
smaller or get a better scan. Never upscale to hide it. Note that `make final`'s preflight
measures resolution only for images placed with `#photo(...)`. For `#plate(...)` images,
check `max_print_width_in` in the photo index yourself.

#### Placing and captioning

Use few images, and only where they belong: a portrait near where a key person is
introduced, and one or two pictures at the exact moments they show. Nothing decorative, and
no more than one per page. Each image is anchored **after** the paragraph it belongs to, in
the unit's Shaped text:

```typst
#plate("/photos/print/P014.jpg", caption: "Anders Calder", id: "P014")
```

About 3.9 in wide for portraits and 4.4 in for landscapes. `#plate-pair` sets two side by
side, and `span: false` keeps a plate in one column of a two-column chapter.

Caption conventions:

| Situation | Caption |
|---|---|
| a portrait | the name exactly as you give it: `Anders Calder` |
| a scene | a short title in the text's own words: `The cabin on Pike Lake` |
| date and place confirmed | `Ruth and Walt at Pike Lake, 1966`. Add a date or place **only** if confirmed. |
| identification uncertain | `Probably Pete, about 1950` or `Believed to be the Duluth ore dock`, or no caption until you ask |
| an illustration | short like any other: `The tunnel to the street`. It is marked as an illustration in the photo index, the chapter note and the copyright page (below) |
| a map | `Positions from the logbook; lines between them are approximate.` |

If you supply a caption, it's used word for word, and any mismatch with the text gets a
`// REVIEW:`. Images with no matching story go on a candidates list, not into a random
chapter.

#### Illustrations (AI-generated or an artist's): strict rules

Often no photograph of an ancestor exists. A rendering is allowed **only if all four hold**:

- **(a)** **It is recorded as an illustration**: `kind: illustration` in
  `photos/photo_index.csv`, with what it was based on. Its caption stays short; yours is used
  word for word.
- **(b)** **The book says so in print**: the copyright page carries "The illustrations in this
  book are artist's renderings, not photographs." (written automatically whenever a placed
  image is an illustration; change the words with `front.illustrations_note` in `book.yaml`),
  and a note in the chapter says what likeness or source they were based on.
- **(c)** **It depicts a scene described in the material**, never an invented event, and
  matches its details: season, place, clothing.
- **(d)** **The distinction survives outside the book**: pages shared as images say the
  illustrations are renderings, and the dashboard never shows one as a person's picture.

Also: nothing that poses as an archival document, no caricature, nothing graphic. A real
photograph may serve as the likeness reference (say so under (b)), but the photograph itself
is never altered. To make illustrations in a consistent period style, with a relative's
likeness locked from their real photographs, see "Generating illustrations" below.

#### Maps: drawn from data, never generated

A route CSV (section 4.3) becomes a printed map:

```sh
python $LINEAGE/scripts/make_route_map.py facts/records/anders/crossing_track.csv \
    --out photos/print/P050.png --title "The crossing" --subject "Anders" \
    --caption "Positions from the records; lines between them are approximate."
```

The `--subject` flag names whose journey it is in the legend. Without it, the legend uses
the book's subject. The map is black and white and **evidence-coded**. Filled dots are places
recorded with the subject aboard. Open dots are places recorded without them. A dashed line
marks the subject's track, approximate between recorded points. **Legs no record covers are
not drawn and are labelled "not recorded"**. In the example, `gap_before=yes` on New York
leaves the Atlantic crossing blank and labels it that way. The output is a 300 dpi PNG.
Coastlines come from Natural Earth (public domain) and are downloaded once. For the map
lettering to be EB Garamond, copy `$LINEAGE/fonts/*.otf` into your system font folder
(`~/Library/Fonts` on a Mac, `~/.local/share/fonts` on Linux). `make_route_map.py --help`
lists the label and extent options.

#### The photographs page and permissions

At the end of each family-history chapter, after THE RECORDS, the **photographs page**
(`#photo-addendum`) lists real photographs held by archives: catalogue number, date,
description, link, and a note on what permission printing them would need. **Thumbnails
print in drafts, and in the final book only once the holder has given permission**
(`show-images: true`).

```typst
#photo-addendum(note: [Held by <the archive>; reproduction needs its written permission.],
  (none, [<catalogue number> · <date>], [<what the photograph shows>], "https://…"),
)
```

The first item in each row is a thumbnail path, or `none` until permission arrives.

Family photographs need permission too: ask whoever holds the original before it prints, and
record it in the index (`print_permission`).

#### Generating illustrations

Plan every illustration in `photos/images-plan.yaml` (example in
`$LINEAGE/templates/images/`): a period **style preset** (how photographs of that time looked),
the scene's citation, the prompt, and optionally a **likeness** set: real photographs of a
relative in `photos/reference/<name>/`, used as references so the person looks like themselves
across a set. Then:

```sh
python $LINEAGE/scripts/generate_images.py --dry-run     # read every prompt first
python $LINEAGE/scripts/generate_images.py               # photos/generated/<id>.png + grayscale print copy
```

The key comes from `OPENAI_API_KEY` for the one command or from `~/.openai_api_key` (chmod 600,
outside every repo), and is never written into the project. Index each result as
`kind: illustration` before placing it.

#### An illustrated story

For one scene the subject told in vivid detail, the chapter can carry an eight-panel sequence
over two facing pages, each panel captioned with the subject's exact words:

```typst
#story-page(title: "The Night of the Storm",
  story-panel("/photos/generated/print/IMG-03-1.jpg", 1)[“The wind took the barn roof clean off.”],
  …)
// src: panel 1 [S2 00:14:05]; …
#story-page(note: [Illustrations after Ruth's account; artist's renderings, not photographs.], …)
```

### 6.7 Assembling and building

#### Generate the chapters

Once units are shaped, ask Claude to "assemble the chapters", or run:

```sh
python .claude/skills/chapter-generator/scripts/assemble.py        # all chapters
python .claude/skills/chapter-generator/scripts/assemble.py 2 3    # just these
```

Each chapter opens with its title, the setting · dates line, the summary line and any
epigraph. The units follow in order, with ❧ between them, a drop cap on the first paragraph,
and `==` headings where one chapter holds several relatives. Claude then does a **seam
pass**. It reads each chapter start to finish and fixes jumps and repeated setup **in the
units**, never in `chapters/*.typ`. Those files carry a GENERATED header and are overwritten
on every build.

The Stories tab shows the same stories oldest first in era bands, with **Read** (real book
pages rendered through the Typst template) on each row, story states (draft · in the book ·
kept aside), and marks on stories that are stale because a source changed. "Generate" there
hands the work to the Genealogist in the terminal drawer.

#### Build a draft

```sh
make -C "$LINEAGE" draft PROJECT="$PWD"
```

In order, this runs:
1. **sync**: refreshes `book/template.typ` from the repo (the design lives in one file,
   `$LINEAGE/book/template.typ`);
2. **assemble**: regenerates every chapter from its units;
3. **quote check**: `verify_quotes.py --transcript`, which warns here and blocks in final;
4. **appendices**: "A Timeline" from `facts/timeline.csv` and "Where the Records Are" from
   `data/archives.csv`;
5. **front, glossary, sources**: the title and copyright pages from `book.yaml`, the reader's
   glossary from `data/reader_glossary.csv`, and "About the Recordings" from
   `transcript/sessions.csv`;
6. **main**: generates `book/main.typ` from `data/chapters.csv`;
7. **compile**: writes `output/book-draft.pdf`, padded to an even page count;
8. **back index**: reads the resolved index page numbers into `data/back_index.csv`.

Drafts show bridges highlighted, editor notes in red and image IDs. Afterwards, actually look
at the title page, the contents, a part page, two chapter openers, a spread with a plate, and
the index. Fix anything wrong at its source (a unit, `chapters.csv`, `book.yaml`), never in a
generated file.

To look at one chapter without building the whole book, run `build_book.py chapter
chapters/NN-x.typ` (→ `output/preview-NN-x.pdf`); add `--final --pages` for one image per page
in `output/pages/` to share outside the PDF.

#### Front matter

In print order: title, copyright, dedication, contents, then the introduction.

- **Title and copyright** are generated from `book.yaml` on every build. Don't edit them.
- **Dedication**: write `book/front/dedication.typ` yourself. `make new` copies in a stock
  line ("For the grandchildren."), so replace it. The sample's reads "For everyone who sat at
  that kitchen table."
- **Introduction**: this is *your* first-person voice, and one of only two places you appear
  (the other is an optional afterword). Ask Claude to "write the introduction" (the
  foreword-generator skill). It gathers verifiable numbers with
  `python .claude/skills/foreword-generator/scripts/foreword_facts.py` and asks you what only
  you know: how the recordings happened, why you made the book, who it's for, whether to say
  AI helped. Then it drafts `book/front/introduction.typ`. Every number in it comes from
  `data/foreword_facts.md`, and every motive comes from your answers. Nothing is invented.
- A **foreword** by someone else goes in `book/front/foreword.typ` and prints first. An
  **afterword** is a hand-written chapter file (for example `chapters/89-afterword.typ`)
  listed last in `data/chapters.csv`. Acknowledgments go in
  `chapters/94-acknowledgments.typ`, which is included in the back matter if it exists.

#### The index

Index terms are marked **in the text as it's written**, at first mention per paragraph, and
they're invisible in print:

```typst
Her grandfather Anders#idx("Calder, Anders") worked the ore boats.#idx("ore boats")
#idx("Duluth, Minnesota!ore dock")            // a sub-entry
#idx-see("Grandpa Walt", "Calder, Walt")      // a cross-reference
```

People are entered as "Surname, Given", and places as "Town, State". Page numbers are
computed during typesetting, so they stay right when pages move. After a build, review
`data/back_index.csv` for duplicate spellings and entries with too many page references.
For a spreadsheet of chapters and index:

```sh
python .claude/skills/chapter-index-builder/scripts/index_tools.py wordcount
python .claude/skills/chapter-index-builder/scripts/index_tools.py xlsx      # output/chapters.xlsx
```

#### Versions

Every PDF that leaves the project should be traceable to the exact text that produced it:

```sh
python .claude/skills/book-generator/scripts/version.py init      # once: git repo, originals' checksums
python .claude/skills/book-generator/scripts/version.py snapshot "chapter map approved"
python .claude/skills/book-generator/scripts/version.py snapshot "review copy for Ruth" --major --note "mailed Nov 3"
python .claude/skills/book-generator/scripts/version.py list
```

Take a snapshot at every gate, and **always a major version before anything is sent to
anyone**. "Page 41, line 3" only means something against the exact copy they received. If
you put the project on GitHub, keep the repository private, because transcripts are in it.

#### GATE 3: final build and preflight

```sh
make -C "$LINEAGE" final PROJECT="$PWD"
```

This builds the draft, re-checks every quotation (and **stops** on a mismatch), and compiles
`output/book-final.pdf` in final mode. Final mode **refuses to compile while any unapproved
bridge remains**, so the sample stops here on purpose:

```
error: panicked with: Unapproved #bridge left in manuscript: [Three years later, the thing she remembered best about Minneapolis had nothing to do with nursing.]
```

Then it runs the preflight for the trim, printer and color set in `book.yaml`: page size,
even page count, the printer's minimum page count, embedded fonts, image resolution, and no
leftover draft markers. A clean result ends with `No blocking problems found.`

Before you call it final: every bridge decided, every `// REVIEW:` read
(`grep -rn "REVIEW" content chapters`), every question in `facts/gaps.md` answered or
consciously left open. Then you, the author, sign off.

#### Where work stops, and the full first pass

By default work stops for you at three gates (speakers, the chapter map, the final build);
between them it runs straight through and saves its questions for the next gate. You choose
where it stops: add gates in `book.yaml` (`workflow.gates`) or in your project's CLAUDE.md
("one chapter at a time"), and the stricter rule wins.

When you'd rather see the whole book at once, ask for **a full first pass**. Claude runs the
**book swarm** ([BOOK-SWARM.md](BOOK-SWARM.md)): for every chapter, two researchers, a writer,
three editors (fidelity, your taste, layout), two independent judges with revisions, and a
100% sources pass; then front matter, an images plan, the index, the assembled draft and a
whole-book continuity review. It works on a branch of your project, and nothing is final until
you've read it.

### 6.8 Reviewing with the subject across a distance

The best check on the record is the person it's about. If they live far away, or don't use a
computer, here's a round trip that works by mail and phone, and that brings back a new source
as well as corrections. The repo has no dedicated tool for this. What follows is a small
Typst file you add yourself, plus the normal pipeline.

#### 1. Put your questions in the text

Where you need the subject's answer, add a draft-only note to the unit's Shaped text, right
where the question arises:

```typst
"Nobody believes that," she said. #note[Question for Ruth: which Pike Lake was it? Minnesota has several.]
```

`#note[...]` prints in drafts only and never in the final book. Good questions come from
`facts/gaps.md`, low-confidence timeline rows, bare-"yeah" facts, and `// REVIEW:` items you
want her view on. (Home's **Request more** builds question lists from the same places.)
Questions about other living people need more care.

#### 2. Make a large-type review edition

Save this as `book/review.typ` in the project. It sets 14-point body type on US Letter paper
(so it prints at home), numbers the lines on every page, leaves a wide margin for writing,
and keeps the bridges and your questions visible. List your own chapter files at the end:

```typst
// Large-type review edition: 14 pt body, numbered lines, a wide margin for notes,
// and draft notes, bridges and questions printed. Not for the printer.
#import "/book/template.typ": *

#show: book.with(title: "The Lake Was Always There", trim: "8.5x11")
#set page(margin: (inside: 1in, outside: 2in, top: 1in, bottom: 1in))
#show par: set text(size: 14pt)
#show regex("⟦[^⟧]*⟧"): set text(size: 12pt)
#set par.line(numbering: "1", numbering-scope: "page", number-clearance: 1.2em)

#show: main-matter
#include "/chapters/01-others-in-the-family.typ"
#include "/chapters/02-the-ore-dock.typ"
#include "/chapters/03-walt-and-the-cabin.typ"
```

Build the draft first, so the chapters and template are current. Then:

```sh
make -C "$LINEAGE" draft PROJECT="$PWD"
typst compile --root . --font-path "$LINEAGE/fonts" book/review.typ output/review.pdf
```

Line numbers restart on each page, so a note can say "page 4, line 12". Two-column
chapters stay two columns. Typst line numbering needs Typst 0.12 or newer.

#### 3. Print it, send it, call

- Print single-sided, so the backs are free for notes. Send it with a pen, a short cover
  letter explaining the red questions and the yellow highlights, and a stamped return
  envelope if you want the marked copy back.
- Snapshot first: `version.py snapshot "review copy for Ruth" --major --note "mailed …"`.
- When it has arrived and been read, **record a call** and go through the notes page by
  page. Tell her you're recording, and get her agreement on the tape. Recording a call
  without consent is illegal in many places. A phone or video call recorded on your end is
  fine. Speaker labelling works best when each of you is clearly audible.

#### 4. Feed the corrections back in as a new source

The call is a new recording, and it goes through intake and transcription like any other.
**Never edit the old transcripts.**

```sh
cp ~/Downloads/review-call.m4a audio/
$LINEAGE/scripts/transcribe.sh         # only the new session is processed (say S3)
```

Earlier sessions are skipped. `transcription_locked: true` stops nothing here, because this
session has never been transcribed. Confirm its speakers (GATE 1 again, for S3 only), render,
and then:

- **A new fact or a correction from her**: change the unit's Shaped text and cite the new
  session, e.g. `// src: [S1 00:00:36]-[S1 00:00:49]; [S3 00:12:40]`. Note the change under
  `## Notes`, and update the timeline row's source. If the correction contradicts what she
  said before, the timeline keeps both (section 5.1) and you decide what the text says.
- **A new story**: add boundary rows for S3 and it becomes a new unit, or a second span of
  an existing one.
- **A misheard word in an old transcript** (she says "it's Calder, not Caulder"): add a
  `spelling` rule to `corrections.json` and re-render. The raw transcript stays as it was.
- **The page-by-page talk itself**: add boundary rows marking those spans `X`, with a reason
  like "review call: corrections, used as citations", so the coverage check passes.
- Remove the `#note[...]` questions she answered, and re-run `make draft`.

### 6.9 Printing

**Trim size** (`print.trim`): 7×10 in is the default and suits a book with photographs. 6×9
works for a mostly text book. 8×10 and 8.5×11 are also supported. A **black-and-white**
interior (`print.color: bw`) costs several times less on print-on-demand than color, and red
details print as gray. Trim and printer can also be set in **Settings → Project settings**.

**Minimum page counts**, as the preflight checks them:

| Printer (`print.printer`) | Minimum pages |
|---|---|
| `kdp` (Amazon KDP paperback) | 24 (hardcover: 75) |
| `ingramspark` | 18 |
| `lulu` | 32 |
| `blurb` | 20 |

The build always pads to an even page count. Front and back matter add up quickly. The
sample, from two minutes of tape, is 30 pages, which is enough for KDP, IngramSpark and
Blurb, but not for Lulu.

**What Lineage doesn't do:**
- **The cover.** Each printer has a cover calculator that sizes the spine from your final
  page count and paper. Make the cover once the page count is final.
- **PDF/X conversion.** IngramSpark prefers PDF/X-1a or X-3. If it rejects the file, convert
  with Ghostscript or Acrobat.
- **Full bleed.** Bleed is only needed for images running off the page edge, and the template
  doesn't do it.

**Proofs.** Order a printed proof before anything else, and read it on paper. Pages that
looked fine on screen show their problems in print: a photo too dark, a widow, a caption
that crowds its image. Snapshot each proof as a major version so your notes match the copy.
Allow a week or two per proof round for printing and shipping, and usually plan on two
rounds. If the book is for a particular birthday or reunion, order the first proof at least
a month before.

### 6.10 Narration

The **Stories** tab can narrate any story with ElevenLabs (add the key under **Settings →
Connectors**). Each row has **Listen** beside **Read**, and **Narrate** / **Re-narrate**;
each story can have its own voice (the default is set in **Project settings**). **Narrate
all** shows the character count before it spends anything. Audio is marked stale when its
story changes, plays in a pinned player, and can be downloaded.

The narration script is extracted from the story itself, and **an unapproved bridge is never
narrated**: decide the bridges first (section 6.4).

Narration is written but has **not been tested end to end** with a real key; treat the
first run as a trial. The story's text goes to ElevenLabs to be read aloud.

---

## 7. Troubleshooting

**`UnpicklingError` / `WeightsUnpickler` / "weights_only" when WhisperX starts.** PyTorch
2.6 and later refuse the speech-detection checkpoints WhisperX loads. Use
`$LINEAGE/scripts/wx.py` in place of the `whisperx` command, as `transcribe.sh` does.
It applies the narrow fix in `scripts/hf_compat.py`.

**`TypeError: ... unexpected keyword argument 'use_auth_token'`.** huggingface_hub 1.0
removed that keyword, and pyannote 3.4 still passes it. `hf_compat.py` renames it. Run
diarization through `diarize.py`, `diarize_chunked.py` or `transcribe.sh`, which all import
the shim. **Don't fix either error by pinning older torch or huggingface_hub**, because that
breaks WhisperX. The tested versions are in `requirements-transcribe.txt`.

**pip can't find `torch==2.8.0`.** Your Python is probably newer than the pinned PyTorch
supports. The stack was last run on Python 3.13. Rebuild the venv with an older Python:
`rm -rf "$LINEAGE/.venv" && python3.13 -m venv "$LINEAGE/.venv"`, then
`make install install-transcribe`.

**401, 403 or `GatedRepoError` when diarization starts.** The token is wrong, or the licence
wasn't accepted on **both** pyannote pages (`speaker-diarization-3.1` *and*
`segmentation-3.0`) while logged in as the account that owns the token. See section 1.1. Your
transcription is safe. Fix the token and run `python $LINEAGE/scripts/diarize.py`.

**Diarization runs for hours.** One long session was labelled in one piece. Make sure you're
running through `diarize.py`, which chunks anything over 20 minutes by default, rather than
`transcribe.sh --one-pass`, which doesn't chunk. Or force chunking with
`python $LINEAGE/scripts/diarize_chunked.py S4`.

**Names in the transcript as fake speech.** This is the initial prompt being echoed. Shorten
`proper_nouns`, then cut the echoes with `drop_segments`/`scrub_inline` in
`corrections.json`, and re-render. Don't re-transcribe a cited session.

**A scan or image-only PDF shows no text in Sources.** OCR needs tesseract (`brew install
tesseract` / `apt install tesseract-ocr`). Install it and re-ingest the source, or paste the
text in the edit drawer.

**`Lineage vX.Y.Z is not installed` from `make dashboard`.** The release pinned in
`lineage.lock` isn't under `~/.lineage/releases/` on this machine. Run the command it prints:
`make update-lineage TO=vX.Y.Z APPLY=1`.

**`unknown font family` warnings, or the book comes out in the wrong typeface.** You compiled
without the bundled fonts. Always pass `--font-path "$LINEAGE/fonts"` to `typst
compile`, or build through `make draft`, which does it for you. Check that
`$LINEAGE/fonts/` contains the EB Garamond `.otf` files.

**`failed to download package @preview/droplet`.** The first build needs internet access once
to fetch the drop-cap package. After that it's cached.

**The final build stops on `Unapproved #bridge left in manuscript`.** This is working as
intended. The message names the chapter and line. Approve the bridge (`lead_in_approved:
true` on the unit, or replace `#bridge[...]` with the sentence in the Shaped text) or delete
it, then build again. `make status` shows how many remain.

**The final build stops on `QUOTE NOT FOUND`.** A quotation doesn't match the transcript word
for word. Fix the quote to match `transcript/clean/` or turn it into paraphrase. If it's
someone else's words, add `// quote-source: <where>` to the paragraph.

**Odd page count in the preflight.** `build_book.py compile` pads to an even count by
recompiling with a blank last page. If you compiled `book/main.typ` by hand, rebuild through
`make draft` or `make final`.

**`typst not found`.** Install Typst (`brew install typst`, or see
<https://github.com/typst/typst#installation>) and check that `typst --version` works in the
same terminal you run make from.

**`pdfinfo` or `pdffonts` not found, or the preflight crashes.** Install poppler (`brew install
poppler` / `apt install poppler-utils`). `make install` calls it optional, but the preflight
in `make final` needs it.

**`whisperx does not import`.** Run `make install-transcribe`. The transcription stack goes
into the same venv as everything else.

**A folder named `~` appeared inside the repo.** `PROJECT=~/…` wasn't expanded by your shell
(zsh). Delete that folder and use `PROJECT="$HOME/…"`.

**A chapter edit vanished.** You edited a GENERATED file in `chapters/`. Make the change in
the unit or in `data/chapters.csv` and rebuild.

---

## 8. Honest limits

### What needs a human

The tools will not, and should not, decide these for you:
- **Speaker confirmation** (GATE 1): which voice is the subject.
- **Accepting tag suggestions** in the Familypedia, and **applying a genealogy rebuild**
  after reading what it changed.
- **Reviewing contributors' uploads** before they join the record.
- **Identifying people in photographs**, and permission to print them.
- **Every question in `facts/gaps.md`**, and every contradiction: the platform shows both
  sides, and only a person can weigh them.
- For a book: **approving the chapter map** (GATE 2), **approving or rejecting every
  bridge** (meaning every interpretation), **every `// REVIEW:` item**, and **final sign-off**
  (GATE 3).
- **Sensitive material**: what to print or share about living people, illness, legal
  trouble, family conflict. The writer is told to flag it and never cut or soften it on its
  own, so the decision is yours and the family's.

The scripts check what can be checked mechanically: quotes against the transcript, coverage,
citations, missing fields, bridges, evidence on genealogy links, page counts. They can't
tell whether a sentence quietly invented a feeling. Read what it writes.

### What isn't built yet

The dashboard's `app/ROADMAP.md` is the current list. Among the things this guide does
*not* describe as working: the contributor-facing page behind an invite link (waits for
hosting); a photo gallery and lightbox with annotation and people tagging on the image; a
screen for pasting and scanning public-record links into the catalogue; the impact pass and
"update everything this affects" after new material arrives (Home's **Needs you** already
surfaces stale stories); and stories with hyperlinked people, places and citations and images
editable in place. Google Drive sign-in and sync, crest generation and ElevenLabs narration
are written but not tested end to end.

### How long it really takes

**Machine time** is the easy part to estimate. Speech recognition with large-v3 on a laptop
CPU runs at roughly real time or slower, so an hour of tape takes an hour or more. A CUDA GPU
is much faster. Chunked speaker labelling costs about half a minute of compute per minute of
audio on a CPU. You can leave both running overnight.

**Your time** is the larger part, and it doesn't shrink much with better tools:
- listening to confirm speakers and checking a few random stretches against the audio;
- reviewing tags, genealogy rebuilds and contributors' uploads;
- research into records, which can take longer than everything else combined;
- photographs: finding them, getting them scanned, asking who's in them;
- for a book: reading and approving the chapter map, reading every chapter against the tape,
  deciding every bridge and `// REVIEW:` item, the review round trip by mail (weeks), and one
  or two printer proofs (a week or two each).

A short book from a few hours of tape is a project of weeks of evenings, not a weekend. The
record itself is never finished: it grows as the family adds to it.

### How many pages your recordings will make

**This is a rough estimate.** Your mileage will vary with how much your subject talks, how
much research you add, and how many photographs you have.

- A recorded hour holds about **7,000–8,000 words of the subject's speech**.
- A finished narrative uses **well under half** of those words. Talk repeats itself and
  wanders, and the narrative paraphrases logistics and quotes only the best lines.
- A 7×10 page holds about 330 words of narrative, so the narrative alone comes to roughly ten
  text pages per hour.
- The rest of the book comes from chapter openers that start on right-hand pages, researched
  context and THE RECORDS, photographs and maps, part pages, and the front and back matter
  (contents, introduction, timeline, glossary, records, index).

**Taken together:** plan on roughly **10 pages of narrative per recorded hour**. Add the
openers, photographs, context and back matter on top of that. Chapters with a lot of research
grow well beyond it: in the worked example, about 25 minutes of tape plus public records
became a 10-page two-column chapter. No measured figure exists yet for a whole book. For your
own number, build a draft after the first few chapters and scale up from that.

### Where your material goes

**Originals stay on your computer**, unless you turn on the Google Drive connector, which
copies sources to your own Drive folder. Speech recognition and speaker labelling run
locally. The Hugging Face token only downloads the model. The dashboard binds to `127.0.0.1`
only.

**Text goes to cloud models.** Claude Code does the model work, so transcript passages,
extracted text, notes and drafts are sent to Anthropic while you work. With an Anthropic key
set in Connectors, the Sources tab's understanding pass sends a source's extracted text (and
a small image, for its description) to Anthropic too. Narration sends a story's text to
ElevenLabs. If a recording or document contains something that must not leave your machine,
keep it out of the project, or cut it from the transcript (exclude the span in
`boundaries.csv`, or leave that session out of the writing stages) before you start.
Research requests go to the sites concerned, and never with your personal details. See
[PRIVACY.md](../PRIVACY.md).

**The record is yours, in plain files.** Everything Lineage builds is CSV, JSON, Markdown
and Typst in the project folder, with raw snapshots of the records it used. Keep the project
in a private git repository and it outlives the links, the apps and the people in it.
