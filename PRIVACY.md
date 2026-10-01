# Privacy

BookAssembler handles some of the most personal material a family has. Here is exactly
where it goes.

## What stays on your computer
- **Audio.** Speech recognition (WhisperX) and speaker labelling (pyannote) run locally.
  Your recordings are never uploaded by BookAssembler.
- **Originals.** `audio/` and `photos/source/` are never modified; their checksums are
  recorded so any change is noticed.
- **The project folder.** Transcripts, story units, chapters and PDFs live in your project
  folder. Nothing is published unless you publish it.

## What goes to a cloud service
- **Transcript text goes to a cloud language model.** The writing is done with Claude
  (Claude Code), so transcript passages, notes and drafts are sent to Anthropic while you
  work. If your recordings contain things that must not leave your machine, remove them from
  the transcript before you start writing, or don't use the writing stages for them.
- **Model downloads.** The first transcription run downloads the speech and diarization models
  from Hugging Face. The diarization model is gated: you accept its licence once, with a free
  account and an access token. The token is only used to download the model; no audio is sent.
- **Research.** If you ask Claude to look up public records (rosters, newspapers, museum
  catalogues), those requests go to the websites concerned. The skills tell Claude never to
  put your name, email or other personal details in those requests.

## Living people
- The book is about real people, many of them alive. The style guide makes the writer flag
  anything about living people, legal trouble or trauma with `// REVIEW:`. The writer never
  cuts or softens it on its own: you decide what prints.
- Before you share a draft, read the `// REVIEW:` list (`grep -rn "REVIEW" content chapters`).

## Git and GitHub
- `make new` writes a `.gitignore` that keeps audio, photos, raw web caches and outputs out
  of git. If you put your project on GitHub, keep the repository **private**: transcripts are
  in it.
- Never commit tokens. `HF_TOKEN` belongs in your shell environment, not in a file in the
  project.
