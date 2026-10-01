# How to make a book from recorded interviews

This guide goes from a folder of recordings to a printed book, in the order you'll do the
work. It uses the sample project throughout: an invented grandmother, **Ruth Calder** (born
1938 in Duluth, Minnesota), interviewed by her grandson **Sam**. Everything about her is
made up, so you can open every file and see exactly what each stage produces.

The tools do the mechanical work, and Claude Code does the drafting under strict rules.
Three decisions are always yours, and the pipeline stops for each of them:

| Gate | When | What you decide |
|---|---|---|
| **GATE 1** | after transcription | which voice on the tape is the subject and which is you; the basics in `book.yaml` |
| **GATE 2** | after the chapter map is proposed | how the book is organized, before any prose is written |
| **GATE 3** | at the end | that the book is finished: every bridge approved, every flag dealt with |

Contents:
[1. What you need](#1-what-you-need) ·
[2. Setup](#2-setup) ·
[3. Transcription](#3-transcription) ·
[4. The timeline](#4-the-timeline) ·
[5. Story units](#5-story-units) ·
[6. The chapter map](#6-the-chapter-map) ·
[7. Writing](#7-writing) ·
[8. Family-history chapters](#8-family-history-chapters) ·
[9. Photos and illustrations](#9-photos-and-illustrations) ·
[10. Assembling and building](#10-assembling-and-building) ·
[11. Reviewing with the subject across a distance](#11-reviewing-with-the-subject-across-a-distance) ·
[12. Printing](#12-printing) ·
[13. Troubleshooting](#13-troubleshooting) ·
[14. Honest limits](#14-honest-limits)

---

## 1. What you need

**The recordings.** Any common format works: m4a, mp3, wav, aac, flac, aiff, ogg, opus,
wma, mp4 or mov. Phone voice memos are fine. They are only ever read, never changed.

**A Claude subscription and Claude Code.** The writing (timeline, story units, shaping,
chapters, captions, introduction) is done by [Claude Code](https://claude.com/claude-code)
following the rules in `.claude/skills/`. You talk to it in plain English ("where are
we?", "shape the units for chapter 3") and it runs the scripts and writes the files.
Transcript text is sent to Anthropic while it works; the audio is not (see
[PRIVACY.md](../PRIVACY.md)).

**A Mac or Linux computer.** Windows is not tested. Apple Silicon works, but speech
recognition runs on the CPU there, because the engine has no Metal backend. An NVIDIA GPU
on Linux makes it much faster.

**Software:**

| Tool | Why | Install |
|---|---|---|
| Python 3.10+ | everything | usually present; on Debian/Ubuntu also `apt install python3-venv` |
| [Typst](https://github.com/typst/typst#installation) | typesets the book | `brew install typst`, or see Typst's install page |
| ffmpeg | reads your recordings | `brew install ffmpeg` / `apt install ffmpeg` |
| poppler (`pdfinfo`, `pdffonts`, `pdftotext`) | page counts and the print preflight | `brew install poppler` / `apt install poppler-utils` |
| WhisperX, pyannote, PyTorch | speech recognition and speaker labels | `make install-transcribe` (pinned versions) |

**Fonts.** EB Garamond is bundled in `fonts/` under the SIL Open Font License, and every
build points Typst at it. You don't need to install anything. The one exception is the map
tool (section 9), which uses EB Garamond only if it's installed system-wide.

**Disk and network.** The first transcription downloads about 5 GB of models. Each hour of
audio needs about 110 MB more for a working copy. The first book build downloads one small
Typst package (`droplet`, for the drop caps). After that, everything except the writing
runs offline.

**A Hugging Face token.** [Hugging Face](https://huggingface.co) is where the speech models
are published. The speaker-labelling model (pyannote) is *gated*: it's free, but its authors
ask you to accept their licence and share contact details before you download it. The token
is how the download proves you've done that. **The model runs on your computer. The token
is only used to download it, and no audio is ever sent.** To set it up once:

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

---

## 2. Setup

### Install the tools

```sh
git clone https://github.com/rexsaurus/BookAssembler.git ~/BookAssembler
cd ~/BookAssembler
make install              # Python venv in .venv with the build tools; checks for typst
make install-transcribe   # adds WhisperX + pyannote to the same venv (a large download)
make sample               # optional: proves the build works (see the README)
```

### Start a project

A book lives in its **own folder**, outside the repo, so your family's material never mixes
with the public code:

```sh
make new PROJECT="$HOME/books/ruth"
```

Use `$HOME` rather than `~`. In zsh, the default shell on macOS, `PROJECT=~/books/ruth` is
not expanded, and make would create a folder literally named `~` inside the repo.

`make new` creates:

```
ruth/
  book.yaml            names, birth year, print settings (fill this in now)
  CLAUDE.md            standing rules Claude Code reads at the start of every session
  .gitignore           keeps audio, photos, raw web caches and PDFs out of git
  .claude/skills  ->   a link to the skills in your BookAssembler checkout
  audio/               your recordings (never modified)
  transcript/          raw JSON, verbatim and clean transcripts, sessions.csv, corrections.json
  facts/               timeline.csv, glossary.md, gaps.md (questions for you), records/
  content/units/       one file per story
  data/                chapters.csv, archives.csv, reader_glossary.csv, indexes
  chapters/            generated chapter files
  book/front/          title, copyright, dedication, contents, introduction
  photos/source/       original images (never modified)
  photos/print/        print-ready copies
  output/              PDFs and spreadsheets
```

### Fill in `book.yaml`

Every skill reads this file first. Here is the sample's:

```yaml
title: "The Lake Was Always There"
subtitle: "A Life of Ruth Calder"
narrator:                       # the subject of the book
  name: "Ruth Calder"
  label: "Grandma"              # speaker label used in the transcripts
  birth_year: 1938              # anchors every "when I was twelve"
  birthplace: "Duluth, Minnesota"
interviewer:                    # the family member who recorded and writes the book
  name: "Sam Calder"
  label: "Sam"
other_speakers: []
family_figures:                 # relatives who get a family-history chapter
  - "Anders Calder"
proper_nouns:                   # KEEP SHORT: surnames and odd place names only
  - "Calder"
  - "Duluth"
transcription_locked: true      # set once timestamps are cited (section 3)
print:
  trim: "7x10"                  # 6x9 | 7x10 | 8x10 | 8.5x11
  color: "bw"                   # bw | color
  printer: "kdp"                # kdp | ingramspark | lulu | blurb
  in_chapter_contents: false
narration:
  mode: "third_person"
  subject_name: "Ruth"          # how chapters refer to the subject after first mention
front:
  introduction_title: "Introduction"
```

The field that matters most is **`birth_year`**. People date their lives by age: "when I
was twelve", "the year I started school", "after I turned sixteen". Every one of those
becomes a year by adding it to the birth year. Get it from a document if you can. If it's
off by one, every derived date in the book is off by one.

Two more to get right early:
- **`label`** values are the names that will appear on transcript paragraphs (`**Grandma**`,
  `**Sam**`). They must match what you put in the speaker map in section 3.
- **`proper_nouns`** are a *few* names the speech engine will otherwise mangle. Keep the list
  short (section 3 explains why).

### Every session: set up the shell, then open Claude Code

```sh
export BOOKASSEMBLER="$HOME/BookAssembler"     # put this line in your shell profile
source "$BOOKASSEMBLER/.venv/bin/activate"     # so `python` is the BookAssembler venv
cd "$HOME/books/ruth"
claude
```

Claude Code picks up the skills from `.claude/skills/` and the rules from `CLAUDE.md`. Start
each session by asking **"where are we?"**. It runs the status check and resumes at the
first unfinished stage. You can run the same check yourself:

```sh
make -C "$BOOKASSEMBLER" status PROJECT="$PWD"
```

The output lists stages 1 to 12, each marked ✓ or ·, followed by a `NEXT:` line.

Everything in this guide can be done either way. You can ask Claude ("transcribe the
recordings", "build the timeline", "propose a chapter map"), or you can run the commands
shown here yourself. The commands below assume you are in the project folder with the venv
active.

---

## 3. Transcription

Copy the recordings into `audio/` by any means. Then:

```sh
$BOOKASSEMBLER/scripts/transcribe.sh --dry-run   # list sessions and the plan; do nothing
$BOOKASSEMBLER/scripts/transcribe.sh --smoke     # the shortest session only: check it all works
$BOOKASSEMBLER/scripts/transcribe.sh             # everything, shortest first
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

### Keep the initial prompt short

The speech engine accepts an "initial prompt" of vocabulary to listen for, and
`transcribe.sh` builds it from `proper_nouns`. **A long prompt gets echoed back into the
transcript as fake speech**: during a pause, the model "hears" your list of names read
aloud in the middle of a real answer. The script warns above 120 characters. Keep it to a
few surnames and unusual place names, and fix every other misspelling afterwards (below).

After every run, search the output for your prompt text. If an echo slips through, cut it at
render time in `transcript/corrections.json`:
- `drop_segments.patterns` drops a whole raw segment that is nothing but echo;
- `scrub_inline.patterns` strips an echo embedded inside a real paragraph.

### Long recordings: chunked diarization

Speaker labelling gets disproportionately slower as files get longer. Measured on a CPU, it
took about 32 seconds of compute per audio-minute on 6–10 minute files but about 119 seconds
per audio-minute on a 34-minute file. A two-hour interview in one piece would take something
like 14 hours. So any session longer than 20 minutes is automatically labelled in
overlapping 10-minute windows, which are then stitched together. You can also run it
directly:

```sh
python $BOOKASSEMBLER/scripts/diarize.py                    # every session without speakers
python $BOOKASSEMBLER/scripts/diarize.py S1 S3
python $BOOKASSEMBLER/scripts/diarize_chunked.py S5         # force chunking
python $BOOKASSEMBLER/scripts/diarize_chunked.py S5 --chunk 600 --overlap 60
```

Each window logs a line like `stitched 2/2 by overlap`. Anything less than all speakers
matched deserves a listen at that seam.

### Never re-run speech recognition once timestamps are cited

Two runs over the same audio never produce the same segment boundaries. Every citation in
the book (`[S2 00:14:07]`) would silently point at the wrong words. So:

- `transcript/raw/*.json` is **never edited**.
- Every fix (a misheard name, a speaker label, a prompt echo) goes in
  **`transcript/corrections.json`** and is applied when the Markdown is rendered. Start from
  the template: `cp $BOOKASSEMBLER/scripts/corrections.example.json transcript/corrections.json`.
- Once you start cutting story units (section 5), set **`transcription_locked: true`** in
  `book.yaml`. After that, `transcribe.sh --force` and `diarize.py --force` refuse to run. New
  recordings can still be added; they just become new sessions.

### GATE 1: confirm the speakers

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
python $BOOKASSEMBLER/scripts/render_transcripts.py
```

This writes three layers:
- `transcript/verbatim/S1.md`: every word, with low-confidence words marked `[?word?]`;
- `transcript/clean/S1.md`: fillers (um, uh) and stutters removed, everything else kept. This
  is **the layer the book quotes and cites**;
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

---

## 4. The timeline

People don't tell their lives in order. `facts/timeline.csv` puts every event on one line,
and each date shows how it was worked out. Ask Claude to "build the timeline" (the
timeline-organizer skill), then check its work:

```sh
python .claude/skills/timeline-organizer/scripts/timeline_tools.py sort
python .claude/skills/timeline-organizer/scripts/timeline_tools.py check   # fix whatever it reports
python .claude/skills/timeline-organizer/scripts/timeline_tools.py md      # facts/timeline.md, by decade
```

### Resolving relative dates

Each row records the arithmetic in `date_basis`, and how the book will say it in
`date_display`. From the sample:

| event | quote | date_basis | date_display | confidence |
|---|---|---|---|---|
| E003 Ruth walks her father's lunch to the ore dock | "maybe seven or eight" | `'maybe seven or eight' + birth year 1938` | about 1945 | medium |
| E004 The big snow; school closed for a week | "around 1950, I think" | `'around 1950, I think'` | around 1950 | medium |
| E005 Ruth begins nursing school | "nursing school in 1956" | stated | 1956 | high |

The rules:
- **Never invent precision.** There's no month or day unless she said it or a document
  gives it.
- **Hedges carry over.** "Around 1950, I think" stays "around 1950". The prose may never
  state a date more precisely than `date_display`.
- "Right after the war" is resolved by saying which war and why, labelled as historical
  context.
- A bare "yeah" to a leading question ("Was that 1952?" "Yeah.") gets low confidence.

### Conflicts are kept, not settled

When two tellings disagree, or the family's story and a document disagree, **both stay**.
The `conflicts` column says what disagrees with what, confidence drops to low, and a
question for you goes into `facts/gaps.md`. Nobody picks a winner silently. In
family-history chapters the book prints both versions (section 8).

The timeline also produces a printed appendix, "A Timeline", built by `make draft` from the
high- and medium-confidence rows.

---

## 5. Story units

A **story unit** is one story, memory or explanation that stands on its own: typically one
to five minutes of tape, stored as one file in `content/units/`. Each unit holds the exact
clean transcript excerpt (`## Source`), its metadata (people, places, timeline events, part,
era or relative), and later the finished prose (`## Shaped`) plus notes for you.

**Why units instead of chapters?** Chapter boundaries move. A life stage splits in two, or
an uncle turns out to deserve his own chapter. Because chapters are *generated* from units,
moving a story is a one-line metadata change and a rebuild, not a rewrite. All editing
happens in units, and generated chapter files are never edited by hand.

Signs that a new unit is starting: a question that changes the subject, a jump in time or
place, "and another time…", "that reminds me…". A story told in pieces across sessions is
**one** unit with several spans. A story told twice is one unit: the fuller telling gets
shaped, and the differences go in its notes.

### `content/boundaries.csv`

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
- `part: family` units take a relative's name as `section` and a `tier` (section 8).

Then generate the unit files and check coverage:

```sh
python $BOOKASSEMBLER/scripts/make_units.py --check    # coverage only
python $BOOKASSEMBLER/scripts/make_units.py            # write content/units/U###-*.md
```

### The coverage check

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
(section 8) has no spans, so it shows up as "not in boundaries.csv". Leave it in place and
don't use `--prune` while you have one. New units start with `break_before: false`; set it to
`true` where you want a ❧ break between stories.

---

## 6. The chapter map

Claude proposes the map (the chapter-index-builder skill) from the timeline and the units,
not from the order things were said. It writes the map to `data/chapters.csv`.

**Two parts:**
- **The family part** ("Those Who Came Before"), first by default: **one chapter per named
  relative, titled with just the name**, oldest generation first. Relatives with only a
  story or two share a chapter called **"Others in the Family"**, each under their own
  heading.
- **The life part**: the subject's own life, **chronological**, one stage or place per
  chapter. A theme that spans decades can be its own chapter, placed where it peaks.

**Sizing.** Aim for roughly 1,000–2,500 words of the subject's speech per life chapter.
Under about 600, merge with a neighbour; over about 3,000, split at a natural turn. A
relative's chapter can be a single page.

**Columns per chapter** (`data/chapters.csv`):

| column | what goes in it | sample |
|---|---|---|
| `chapter`, `file`, `title`, `part` | order, file name, title, part name | `2`, `chapters/02-the-ore-dock.typ`, `The Ore Dock`, `Her Life` |
| `setting`, `dates` | the place-and-years line under the title | `Duluth, Minnesota`, `1938–1950` |
| `summary_line` | a short line in the old-book manner, never a list | `On Tin Pails and Tunnels` |
| `epigraph`, `epigraph_source` | optional, public-domain, verified (section 7) | |
| `columns` | `1` for narrative chapters, `2` for research-dense ones | `1` |
| `summary` | 2–4 neutral sentences, for you and the introduction | |
| `status` | `proposed` → `approved` → `drafted` → `reviewed` → `final` | `approved` |

Titles are plain stage or place names, or a phrase the subject said.

### GATE 2: approve the map

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

---

## 7. Writing

The book is a **biography written about the subject in the third person, past tense**, by
the family member who recorded it (you, the *author*). It should read like a real book, not
an interview. The master rulebook is `.claude/skills/memoir-style-guide/SKILL.md`, and every
other writing skill defers to it. Here are the rules that matter most.

### The rules

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
Every fact is sourced on a `// context:` line and listed in the chapter's THE RECORDS, and it
takes up no more than about a quarter of a chapter. Juxtaposition is allowed and causation is
not: "That spring the mill cut its hours" is fine, but "so she left" is not unless she said
so. For a real example, see section 7 of [EXAMPLE-CHAPTER.md](EXAMPLE-CHAPTER.md):

```typst
// context: Elmo P. Hohman, The American Whaleman (1928), p. 15 (green hand's lay 1/200),
// p. 240 (about 20¢ a day vs about 90¢ for unskilled labor ashore)
```

**Epigraphs** are optional: at most one per chapter (two for a family-history chapter),
from public-domain literature only, never quoted from memory, and checked with
`verify_quotes.py` against a saved copy of the text listed in `facts/sources/works.csv`.

### Before and after: one story, three ways

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

### Bridges

A **bridge** is any sentence the writer added that isn't plain fact: an interpretation, or a
connecting line that might color the story. In the sample, unit U005 has this lead-in:

```yaml
lead_in: "Three years later, the thing she remembered best about Minneapolis had nothing to do with nursing."
```

Nothing on the tape says that, so it's assembled as `#bridge[...]`. In drafts it prints
highlighted, like this: ⟦BRIDGE: …⟧. **The final build refuses to compile while any bridge
remains.** To decide on one:
- **Approve a lead-in:** add `lead_in_approved: true` to that unit's frontmatter. It then
  prints as plain text.
- **Approve a bridge inside Shaped text:** replace `#bridge[...]` with the sentence itself.
- **Reject it:** delete it.

`make status` shows how many bridges are pending.

### Writing the units and checking quotes

Ask Claude to "shape the units for chapter 2" (content-separator plus the style guide). It
writes each unit's `## Shaped` section, usually with:

```sh
python $BOOKASSEMBLER/scripts/shape.py U002 drafts/U002.md        # writes ## Shaped, status: shaped
python $BOOKASSEMBLER/scripts/shape.py U002 --status approved     # only you set approved
```

Then check every quotation in the chapters against what the subject actually said:

```sh
python $BOOKASSEMBLER/scripts/verify_quotes.py --transcript chapters/[0-8]*.typ
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

---

## 8. Family-history chapters

Stories about people nobody alive has met are the most fragile part of the book. Usually
they're secondhand, sometimes contradictory, and once printed they become "what happened".
The family-history-chapters skill adds rules on top of the style guide. Read
[EXAMPLE-CHAPTER.md](EXAMPLE-CHAPTER.md) alongside this section: it's a real ancestor's
chapter, annotated rule by rule.

### Tiers and the chain of telling

Every fact sits in exactly one tier:
- **witnessed**: the subject saw it herself;
- **told**: someone named told her ("as her father told it");
- **lore**: the family's story, source unclear ("that's what they always said").

The chain stays visible in the prose: "According to Ruth's father, Anders crossed at
sixteen", not "Anders crossed at sixteen". Lore keeps its hedges.

The chapter's **first paragraph says what kind of material this is and who it passed
through**, and the opening section makes a promise: **"Where the records and the family
part company, this chapter says so."** The sample's chapter 1 does both in one paragraph
(`content/units/U001-the-boots.md`).

### Line of descent

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

### Researching an ancestor

Research beyond the tape is allowed in these chapters: census returns, military rosters and
pension files, ship registers and crew lists, digitized newspapers, museum and library
catalogues, period books. **Check the records first**, because archives often hold the
person.

- **Free and public sources first**: national and state archives, the Internet Archive and
  HathiTrust for period books, Chronicling America for newspapers, free census indexes,
  museum catalogues. Note any paywalled source as such, and give the free route if there is
  one.
- **Fetch politely.** Respect robots.txt and site terms, make at most one request every
  couple of seconds per site, and use no logins or CAPTCHA tricks. **Never put anyone's
  name, email or credentials in a request.**
- **Fact sheets before prose.** For an episode worth building out (a voyage, a regiment, a
  mill town), the research goes first into `facts/records/<person>/context_<topic>.md`, one
  fact per bullet with URL, page and a confidence note. The chapter is then written from the
  sheets, never from memory.
- **Cache what you use.** Raw downloads go in `facts/records/_raw/`, which is gitignored
  because catalogues often forbid reproduction. Then export the shareable text into the
  project:

  ```sh
  python $BOOKASSEMBLER/scripts/export_sources.py --dry-run
  python $BOOKASSEMBLER/scripts/export_sources.py --restricted '^museum/'
  ```

  This copies text files to `facts/records/sources/` and writes `MANIFEST.csv` listing
  *every* raw file with its size and SHA-256 hash, plus whether it was exported and why not.
  Restricted paths are never copied. Rules can live in `facts/records/export.yaml`; see the
  script's header.

### THE RECORDS and the note on the name

Every family-history chapter, and any chapter with `// context:` lines, ends with a
small-type **THE RECORDS** block after the closing paragraph. It lists where each documented
claim came from: catalogue numbers, record titles, database IDs, newspaper titles and dates,
books with years and pages, and links.

```typst
#records(
  [*Census.* <census year, place, page and line>: Anders Calder, <age>, <occupation>.
   <where the free index is>. #link("https://…")],
  [*A note on the name.* <which of two similar records is meant, and why>.],
)
```

The angle-bracket parts are yours to fill in. The sample hasn't consulted any records yet,
and its `#records` block says exactly that. Include **a note on the name** whenever a
record could be confused with a similar one, such as two ships or two men with the same
name. Say which is which and why. The worked example ends with exactly such a note about
two whaleships called _Hannibal_.

THE RECORDS and the photographs page (section 9) go in a final **apparatus unit** for the
chapter (`kind: apparatus`, same `section`, highest `order`, no spans), so they survive
reassembly. The sample keeps it inside U001 instead, which works for a one-unit chapter.

### When documents contradict the family

**Print both, and say so.** Never silently correct the family's story, and never silently
repeat it. Tell the life once, in order, with the record as the spine. Where the family's
version differs, tell it at that point, attributed ("The family remembered his war
differently…"). Let the record confirm what it can. Dates in narration follow the record,
with the family's date given as theirs. Log the conflict in `facts/gaps.md` and mark it
`// REVIEW:`. Section 4 of [EXAMPLE-CHAPTER.md](EXAMPLE-CHAPTER.md) shows this done well:
the family's "surgeon, drafted" set beside the records' "soldier, enlisted", and the bounty
money that turned out to be real.

Say honest gaps out loud ("Which route the boat took that winter, no surviving record
says") and never fill them. Don't give an ancestor a famous battle or ship their unit or
crew did not have.

### The family's own papers

Separately, the records-archives skill keeps `data/archives.csv`, an index of what the family
holds: Bibles, letters, discharge papers, albums, the recordings themselves. Lost and
destroyed items get rows too. Street addresses and phone numbers live only in the private
column, and a living holder is printed only with `print_permission: yes`. `make draft` turns
the printable rows into the back-matter appendix "Where the Records Are".

```sh
python .claude/skills/records-archives/scripts/archives_tools.py check   # flags addresses/phones in public columns
python .claude/skills/records-archives/scripts/archives_tools.py asks    # follow-up list, one call per relative
```

---

## 9. Photos and illustrations

Readers will treat a caption as fact for generations. So every label says what it rests on,
every guess looks like a guess, and nothing that isn't a photograph can pass for one. The
photo-processor skill holds the full rules.

### Extract and catalogue

```sh
python .claude/skills/photo-processor/scripts/extract_photos.py "Family photos.docx"   # or a PDF, zip or folder
```

Images get permanent IDs (`P001`, …). Originals are copied to `photos/source/` and never
edited, and any nearby text is saved as `original_caption`, which is often the best evidence
there is. Export a Google Doc as .docx first. Everything about each image goes in
`photos/photo_index.csv`, and each identification records its **basis**, strongest first:

1. **inscription**: writing on the photo or its back, a printed lab date;
2. **document**: a caption in the family's photo document, an archive catalogue, the owner's word;
3. **transcript**: the subject describes this scene (cite `[S2 00:31:05]`);
4. **visual estimate**: clothing, cars, print format. Never better than medium confidence.

**Never name a person from facial resemblance.** A wrong name in print is worse than none.
Without an inscription, document, transcript or the owner's word, describe instead
("unidentified woman, about 30"). Dates are exact only if inscribed; otherwise they're a
range or "about 1925". Only you or the owner can mark an image `confirmed`.

### Print copies

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

### Placing and captioning

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
| an illustration | `The tunnel to the street, as the family told it (illustration)` |
| a map | `Positions from the logbook; lines between them are approximate.` |

If you supply a caption, it's used word for word, and any mismatch with the text gets a
`// REVIEW:`. Images with no matching story go on a candidates list, not into a random
chapter.

### Illustrations (AI-generated or an artist's): strict rules

Often no photograph of an ancestor exists. A rendering is allowed **only if all four hold**:

- **(a)** **The caption itself marks it**, with "as the family told it" or an explicit
  "illustration", so a reader in fifty years cannot mistake it for a photograph.
- **(b)** **A note in the chapter** says the illustrations are renderings and what likeness or
  source each was based on. This can go in the photographs page note or a closing line.
- **(c)** **It depicts a scene described in the material**, never an invented event, and
  matches its details: season, place, clothing.
- **(d)** **The distinction survives in the printed book**, not just in drafts or the index.

Also: nothing that poses as an archival document, no caricature, nothing graphic. A real
photograph may serve as the likeness reference (say so under (b)), but the photograph itself
is never altered. The worked example admits that some of its illustration captions break
rule (a); see section 10 of [EXAMPLE-CHAPTER.md](EXAMPLE-CHAPTER.md).

### Maps: drawn from data, never generated

Keep a route as a sourced CSV, one row per recorded point, and draw it:

```csv
seq,date,place,lat,lon,kind,aboard,source,label,gap_before
1,,Bergen,60.39,5.32,port,subject,<record ID or URL>,Bergen,
2,,New York,40.70,-74.01,port,subject,<record ID or URL>,New York,yes
3,,Duluth,46.78,-92.10,port,subject,<record ID or URL>,Duluth,
```

```sh
python $BOOKASSEMBLER/scripts/make_route_map.py facts/records/anders/crossing_track.csv \
    --out photos/print/P050.png --title "The crossing" --subject "Anders" \
    --caption "Positions from the records; lines between them are approximate."
```

Only `seq`, `lat` and `lon` are required, but every point should carry a `source`. The
`--subject` flag names whose journey it is in the legend. Without it, the legend uses the
book's subject. The map is black and white and **evidence-coded**. Filled dots are places recorded with the subject
aboard. Open dots are places recorded without them. A dashed line marks the subject's track,
approximate between recorded points. **Legs no record covers are not drawn and are labelled
"not recorded"**. In the example, `gap_before=yes` on New York leaves the Atlantic crossing
blank and labels it that way. The output is a 300 dpi PNG. Coastlines come from Natural
Earth (public domain) and are downloaded once. For the map lettering to be EB Garamond, copy
`$BOOKASSEMBLER/fonts/*.otf` into your system font folder (`~/Library/Fonts` on a Mac,
`~/.local/share/fonts` on Linux). `make_route_map.py --help` lists the label and extent
options.

### The photographs page and permissions

At the end of each family-history chapter, after THE RECORDS, the **photographs page**
(`#photo-addendum`) lists real photographs held by archives: catalogue number, date,
description, link, and a note on what permission printing them would need. **Thumbnails
print only once the holder has given permission** (`show-images: true`).

```typst
#photo-addendum(note: [Held by <the archive>; reproduction needs its written permission.],
  (none, [<catalogue number> · <date>], [<what the photograph shows>], "https://…"),
)
```

The first item in each row is a thumbnail path, or `none` until permission arrives.

Family photographs need permission too: ask whoever holds the original before it prints, and
record it in the index (`print_permission`).

---

## 10. Assembling and building

### Generate the chapters

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

### Build a draft

```sh
make -C "$BOOKASSEMBLER" draft PROJECT="$PWD"
```

In order, this runs:
1. **sync**: refreshes `book/template.typ` from the repo (the design lives in one file,
   `$BOOKASSEMBLER/book/template.typ`);
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

### Front matter

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

### The index

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

### Versions

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

### GATE 3: final build and preflight

```sh
make -C "$BOOKASSEMBLER" final PROJECT="$PWD"
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

---

## 11. Reviewing with the subject across a distance

The best check on the book is the person it's about. If they live far away, or don't use a
computer, here's a round trip that works by mail and phone. The repo has no dedicated tool
for this. What follows is a small Typst file you add yourself, plus the normal pipeline.

### 1. Put your questions in the text

Where you need the subject's answer, add a draft-only note to the unit's Shaped text, right
where the question arises:

```typst
"Nobody believes that," she said. #note[Question for Ruth: which Pike Lake was it? Minnesota has several.]
```

`#note[...]` prints in drafts only and never in the final book. Good questions come from
`facts/gaps.md`, low-confidence timeline rows, bare-"yeah" facts, and `// REVIEW:` items you
want her view on. Questions about other living people need more care.

### 2. Make a large-type review edition

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
make -C "$BOOKASSEMBLER" draft PROJECT="$PWD"
typst compile --root . --font-path "$BOOKASSEMBLER/fonts" book/review.typ output/review.pdf
```

Line numbers restart on each page, so a note can say "page 4, line 12". Two-column
chapters stay two columns. Typst line numbering needs Typst 0.12 or newer.

### 3. Print it, send it, call

- Print single-sided, so the backs are free for notes. Send it with a pen, a short cover
  letter explaining the red questions and the yellow highlights, and a stamped return
  envelope if you want the marked copy back.
- Snapshot first: `version.py snapshot "review copy for Ruth" --major --note "mailed …"`.
- When it has arrived and been read, **record a call** and go through the notes page by
  page. Tell her you're recording, and get her agreement on the tape. Recording a call
  without consent is illegal in many places. A phone or video call recorded on your end is
  fine. Speaker labelling works best when each of you is clearly audible.

### 4. Feed the corrections back in as a new source

The call is a new recording, and it goes through the pipeline like any other. **Never edit
the old transcripts.**

```sh
cp ~/Downloads/review-call.m4a audio/
$BOOKASSEMBLER/scripts/transcribe.sh         # only the new session is processed (say S3)
```

Earlier sessions are skipped. `transcription_locked: true` stops nothing here, because this
session has never been transcribed. Confirm its speakers (GATE 1 again, for S3 only), render,
and then:

- **A new fact or a correction from her**: change the unit's Shaped text and cite the new
  session, e.g. `// src: [S1 00:00:36]-[S1 00:00:49]; [S3 00:12:40]`. Note the change under
  `## Notes`, and update the timeline row's source. If the correction contradicts what she
  said before, the timeline keeps both (section 4) and you decide what the text says.
- **A new story**: add boundary rows for S3 and it becomes a new unit, or a second span of
  an existing one.
- **A misheard word in an old transcript** (she says "it's Calder, not Caulder"): add a
  `spelling` rule to `corrections.json` and re-render. The raw transcript stays as it was.
- **The page-by-page talk itself**: add boundary rows marking those spans `X`, with a reason
  like "review call: corrections, used as citations", so the coverage check passes.
- Remove the `#note[...]` questions she answered, and re-run `make draft`.

---

## 12. Printing

**Trim size** (`print.trim`): 7×10 in is the default and suits a book with photographs. 6×9
works for a mostly text book. 8×10 and 8.5×11 are also supported. A **black-and-white**
interior (`print.color: bw`) costs several times less on print-on-demand than color, and red
details print as gray.

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

**What BookAssembler doesn't do:**
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

---

## 13. Troubleshooting

**`UnpicklingError` / `WeightsUnpickler` / "weights_only" when WhisperX starts.** PyTorch
2.6 and later refuse the speech-detection checkpoints WhisperX loads. Use
`$BOOKASSEMBLER/scripts/wx.py` in place of the `whisperx` command, as `transcribe.sh` does.
It applies the narrow fix in `scripts/hf_compat.py`.

**`TypeError: ... unexpected keyword argument 'use_auth_token'`.** huggingface_hub 1.0
removed that keyword, and pyannote 3.4 still passes it. `hf_compat.py` renames it. Run
diarization through `diarize.py`, `diarize_chunked.py` or `transcribe.sh`, which all import
the shim. **Don't fix either error by pinning older torch or huggingface_hub**, because that
breaks WhisperX. The tested versions are in `requirements-transcribe.txt`.

**pip can't find `torch==2.8.0`.** Your Python is probably newer than the pinned PyTorch
supports. The stack was last run on Python 3.13. Rebuild the venv with an older Python:
`rm -rf "$BOOKASSEMBLER/.venv" && python3.13 -m venv "$BOOKASSEMBLER/.venv"`, then
`make install install-transcribe`.

**401, 403 or `GatedRepoError` when diarization starts.** The token is wrong, or the licence
wasn't accepted on **both** pyannote pages (`speaker-diarization-3.1` *and*
`segmentation-3.0`) while logged in as the account that owns the token. See section 1. Your
transcription is safe. Fix the token and run `python $BOOKASSEMBLER/scripts/diarize.py`.

**Diarization runs for hours.** One long session was labelled in one piece. Make sure you're
running through `diarize.py`, which chunks anything over 20 minutes by default, rather than
`transcribe.sh --one-pass`, which doesn't chunk. Or force chunking with
`python $BOOKASSEMBLER/scripts/diarize_chunked.py S4`.

**Names in the transcript as fake speech.** This is the initial prompt being echoed. Shorten
`proper_nouns`, then cut the echoes with `drop_segments`/`scrub_inline` in
`corrections.json`, and re-render. Don't re-transcribe a cited session.

**`unknown font family` warnings, or the book comes out in the wrong typeface.** You compiled
without the bundled fonts. Always pass `--font-path "$BOOKASSEMBLER/fonts"` to `typst
compile`, or build through `make draft`, which does it for you. Check that
`$BOOKASSEMBLER/fonts/` contains the EB Garamond `.otf` files.

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

## 14. Honest limits

### How long it really takes

**Machine time** is the easy part to estimate. Speech recognition with large-v3 on a laptop
CPU runs at roughly real time or slower, so an hour of tape takes an hour or more. A CUDA GPU
is much faster. Chunked speaker labelling costs about half a minute of compute per minute of
audio on a CPU. You can leave both running overnight.

**Your time** is the larger part, and it doesn't shrink much with better tools:
- listening to confirm speakers and checking a few random stretches against the audio;
- reading and approving the chapter map;
- reading every chapter against the tape, deciding every bridge and `// REVIEW:` item;
- research for each family-history chapter, which can take longer than everything else
  combined;
- photographs: finding them, getting them scanned, asking who's in them;
- the review round trip by mail (weeks), and one or two printer proofs (a week or two each).

A short book from a few hours of tape is a project of weeks of evenings, not a weekend.

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

### What needs a human

The tools will not, and should not, decide these for you:
- **Speaker confirmation** (GATE 1): which voice is the subject.
- **Approving the chapter map** (GATE 2).
- **Approving or rejecting every bridge**, meaning every interpretation in the book.
- **Every `// REVIEW:` item**, and the questions in `facts/gaps.md`.
- **Sensitive material**: what to print about living people, illness, legal trouble,
  family conflict. The writer is told to flag it and never cut or soften it on its own, so
  the decision is yours and the family's.
- **Identifying people in photographs**, and permission to print them.
- **Final sign-off** (GATE 3).

The scripts check what can be checked mechanically: quotes against the transcript, coverage,
citations, missing fields, bridges, page counts. They can't tell whether a sentence quietly
invented a feeling. Read the book.

### Where your material goes

**The audio stays on your computer.** Speech recognition and speaker labelling run locally.
The Hugging Face token only downloads the model.

**The transcript text goes to a cloud model.** Claude Code does the writing, so transcript
passages, notes and drafts are sent to Anthropic while you work. If a recording contains
something that must not leave your machine, cut it from the transcript (exclude the span in
`boundaries.csv`, or leave that session out of the writing stages) before you start. Research
requests go to the sites concerned, and never with your personal details. See
[PRIVACY.md](../PRIVACY.md).
