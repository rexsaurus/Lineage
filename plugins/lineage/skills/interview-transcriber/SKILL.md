---
name: interview-transcriber
description: Turns interview recordings (or existing transcripts) in a lineage into the timestamped, speaker-labelled transcript every other skill builds on — inventories and checksums the audio, transcribes with WhisperX, diarizes long sessions in chunks, maps speakers with the author's confirmation, renders verbatim and clean layers with spelling fixes applied from corrections.json, labels each session with date, place and topic outline, and keeps a proper-noun glossary. Use this whenever audio, video or transcript files are added, the user asks to transcribe, label speakers, fix a misheard name, split or merge sessions, or asks "what did Grandma say about X" and no transcript exists yet. Always the first step of the pipeline.
---

# Interview Transcriber

The transcript is the single source of truth for the whole book. Every chapter, date,
caption and index entry traces back to a line in it, so accuracy and **stable timestamps**
matter more than speed or polish.

## Project conventions (shared by all Lineage skills)
- The repo lives anywhere; `$LINEAGE` points to it and `make install` creates
  `$LINEAGE/.venv` (use its `python`). A book is a separate project folder made by
  `make -C "$LINEAGE" new PROJECT=~/books/<name>`; **run everything from the project
  folder**. Skill scripts: `python .claude/skills/<skill>/scripts/<x>.py`; repo tools:
  `$LINEAGE/scripts/<tool>`.
- `book.yaml` at the project root holds names, labels, birth year and print settings. If
  missing, copy `assets/book.yaml` from this skill and ask the author to fill in the
  subject's name and label, the interviewer's, the birth year, and names ASR will mangle.
- Sessions are `S1`, `S2`, … in recording order. Every citation uses `[S2 00:14:07]`.
- Layout:
  ```
  audio/                    originals: never modified, never deleted (checksums recorded)
  transcript/work/          16 kHz mono WAV copies
  transcript/raw/*.json     WhisperX output: never edited
  transcript/verbatim/S1.md every word, every um
  transcript/clean/S1.md    light clean-up (below)
  transcript/master.md      all clean sessions, with session headers
  transcript/sessions.csv   session,file,recorded,duration (+ place, speakers, words, flags)
  transcript/corrections.json  speaker map, spelling fixes, prompt-echo cuts
  facts/glossary.md         proper nouns + spelling status
  facts/gaps.md             questions for the author
  ```

## Never re-run ASR once timestamps are cited
Re-running transcription or diarization on a session **shifts every timestamp** that units,
chapters and captions cite. Once anything cites a session, it is never re-transcribed.
Spelling fixes, speaker-label fixes and echo cuts go in `transcript/corrections.json` and are
applied at render time. When the author sets `transcription_locked: true` in `book.yaml`,
stage 1 is closed: if a step seems to need a re-run, stop and ask.

## Workflow

### 1. Inventory
List everything in `audio/` (m4a, mp3, wav, mp4, mov, aac, flac) and any existing
transcripts (txt, docx, srt, vtt, service exports). Get duration (`ffprobe`) and any
embedded creation date; assign session IDs chronologically; ask if the order is ambiguous.
Record checksums of the originals (book-generator `version.py init`).
An imported transcript still gets a session (`source: imported transcript`); without
timestamps cite paragraphs as `[S3 ¶42]`.

### 2. Normalize (copies only)
```bash
ffmpeg -i "audio/<file>" -ac 1 -ar 16000 transcript/work/S1.wav
```

### 3. Transcribe
```bash
export HF_TOKEN=hf_xxxxxxxx      # your Hugging Face token; never commit it
$LINEAGE/scripts/transcribe.sh          # WhisperX large-v3 → transcript/raw/
```
- **Keep the initial prompt short: a few surnames, no sentence-like lists.** Long prompts
  get echoed into the transcript as fake speech during silences. After every run, grep the
  output for the prompt text; add echoes to `drop_segments` in corrections.json.
- Version breakage between PyTorch, huggingface_hub and pyannote is patched in
  `$LINEAGE/scripts/hf_compat.py` (and the `wx.py` wrapper); import it rather than
  pinning old versions.

### 4. Diarize
Diarization is applied to the existing ASR JSON, separately, so labelling speakers never
requires re-transcribing:
```bash
$LINEAGE/scripts/diarize.py S1 S2                 # short sessions
$LINEAGE/scripts/diarize_chunked.py S5            # anything over ~20 minutes
```
Diarization time grows faster than audio length (a two-hour file can take many hours in one
pass). The chunked tool diarizes 10-minute windows with overlap and stitches speaker
identity across seams; spot-check the seams. A 403 means the token hasn't accepted the
`pyannote/speaker-diarization-3.1` and `pyannote/segmentation-3.0` terms on Hugging Face.

### 5. Map speakers — GATE 1
Decide which `SPEAKER_0x` is which by content (the interviewer asks short questions; the
subject tells long stories), then **show the author three short sample turns per speaker
and get confirmation** before writing labels. Labels come from `book.yaml`
(`narrator.label`, e.g. "Grandma"; `interviewer.label`, e.g. "Sam"). Record the mapping per
session in `speaker_map` in corrections.json; it can flip between sessions.

### 6. Render Markdown
```bash
$LINEAGE/scripts/render_transcripts.py      # all sessions, corrections applied
# or one file directly:
python .claude/skills/interview-transcriber/scripts/whisperx_to_md.py transcript/raw/S1.json \
  --session S1 --map SPEAKER_00=Grandma --map SPEAKER_01=Sam \
  --verbatim transcript/verbatim/S1.md --clean transcript/clean/S1.md
```
**Verbatim**: every word as recognized. **Clean**: only filler sounds (um, uh, er, hmm) and
immediate stutters removed; grammar, dialect, fragments and trailing-off stay. Clean is not
prose; prose is the style guide's job. Both mark `[?word?]` (score < 0.5),
`[inaudible 00:14:07]`, `[crosstalk]`. A paragraph starts at each speaker change or pause
over 2 s, with its timestamp:
```
**Grandma** [S1 00:14:07] We lived out past the grain elevator then. My dad had the ...
**Sam** [S1 00:15:30] Was that the house on Elm?
```
`corrections.json` holds `speaker_map`, `spelling` (`{find, replace}` regexes the author
approved), `drop_segments` (prompt echoes and other artifacts) and optional `scrub_inline`.
Fix words there, never by hand-editing one layer.

### 7. Label each session
Header and topic outline at the top of each `clean/S*.md`:
```markdown
---
session: S1
file: audio/interview-part1.m4a
recorded: 2026-06-14        # or "unknown — ask"
place: ""
speakers: {Grandma: SPEAKER_00, Sam: SPEAKER_01}
duration: 00:47:12
---
## Topics
- 00:00:00 Warm-up
- 00:02:40 Her grandfather and the canal
```
Topics are short neutral labels. Mirror into `transcript/sessions.csv`.

### 8. Glossary
Every person, place, organization and unusual term → `facts/glossary.md`
(`| Term | Heard as | First at | Status |`). Unverified items go to the author; approved
spellings go into corrections.json and the glossary status is updated.

### 9. Master and verify
Concatenate clean sessions into `transcript/master.md` with `# Session S1 — <date>` headers.
Before reporting done: listen to five random 30-second windows and compare; confirm total
transcript duration ≈ audio duration; confirm no `SPEAKER_0x` survived unmapped.

Report: sessions, minutes, words per speaker, `[?]`/`[inaudible]` counts, glossary items
needing confirmation.

## Corrections and new sessions
- Fixing a word: add it to corrections.json and re-render. Never regenerate from audio.
- A new recording becomes the next session; only that session goes through ASR.
- Re-transcribing an already-cited session: only on the author's explicit instruction; keep
  the old files as `S1.v1.*` and tell downstream skills every citation for it needs
  re-checking.
