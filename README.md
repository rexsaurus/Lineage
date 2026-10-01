# BookAssembler

[![Build the sample book](https://github.com/rexsaurus/BookAssembler/actions/workflows/sample.yml/badge.svg)](https://github.com/rexsaurus/BookAssembler/actions/workflows/sample.yml)

You sat down with a parent or grandparent and recorded them. Now you have hours of audio
and want a real book: chapters in order, their own words quoted exactly, the family's old
stories set beside the records, a few photographs, an index, and something you can order
in print and hand to the grandchildren.

Getting there by hand takes months, and the usual shortcuts go wrong in two ways. Either
the book invents things (feelings, weather, tidied-up quotes nobody said), or it sands the
person down into someone bland. BookAssembler is a set of tools, Typst templates and
[Claude Code](https://claude.com/claude-code) skills that carry you from recordings to a
print-ready PDF. Every sentence it writes traces back to a timestamp on the tape, and you
make the decisions only you can make.

## Try it in 60 seconds

You need Python 3.10 or newer and [Typst](https://github.com/typst/typst#installation)
(`brew install typst` on a Mac). The sample builds without any recordings, models or
Claude account.

```sh
git clone https://github.com/rexsaurus/BookAssembler.git
cd BookAssembler
make install
make sample
```

Then open the two PDFs it builds:

- `examples/sample-project/output/book-draft.pdf`: a complete 30-page book about an
  invented grandmother, Ruth Calder. It is built from two one-minute invented interviews
  and has a family-history chapter, two life chapters, a timeline, a glossary, the records
  appendix and an index. The yellow highlight in chapter 3 is a **bridge**: a sentence
  waiting for the author's approval.
- `examples/erasthus-burnham/erasthus-burnham.pdf`: a 10-page real family-history chapter,
  published with the family's permission. It is annotated in
  [docs/EXAMPLE-CHAPTER.md](docs/EXAMPLE-CHAPTER.md).

`make status PROJECT="$PWD/examples/sample-project"` shows where a book stands and what
comes next.

## How a book gets made

```
recordings ─► transcripts ─► timeline ─► story units ─► chapter map ─► shaped units ─► chapters ─► book
   audio/      transcript/    facts/      content/       data/          content/        chapters/   output/
            ▲                                         ▲                                              ▲
         GATE 1                                    GATE 2                                         GATE 3
     confirm speakers                        approve the chapter map                         final sign-off
```

1. **Transcripts.** WhisperX turns each recording into a word-timestamped transcript on
   your own computer, and pyannote works out who is speaking. Every later citation looks
   like `[S2 00:14:07]`, so once anything cites a session, it is never re-transcribed.
2. **Timeline.** "When I was twelve" becomes "about 1950", with the arithmetic written
   down. When two tellings conflict, both are kept.
3. **Story units.** The transcript is cut into one file per story, and a coverage check
   proves no paragraph of the subject's speech was lost.
4. **Chapter map.** Family history first, one chapter per relative, then the life in
   order. You approve it before any writing happens.
5. **Shaping.** Claude writes each unit as third-person biography under strict rules:
   nothing added, quotes exact and checked by script, every paragraph cited, and any
   interpretation held back as a bridge for you to approve.
6. **Chapters and book.** Units are assembled into chapters. Typst sets the book with
   front matter, back matter and a generated index, and a preflight checks it against
   your printer's requirements (KDP, IngramSpark, Lulu or Blurb).

The three gates are where the tools stop and wait for you: which voice is the subject,
how the book is organized, and whether it's finished. The final build refuses to compile
while any unapproved bridge remains.

## What you need for a real book

- The recordings (any common audio or video format).
- A Mac or Linux computer with ffmpeg, Typst and Python. The transcription models run
  locally on CPU, or on an NVIDIA GPU if you have one.
- A free Hugging Face account and token, used only to download the speaker-labelling model.
- A Claude subscription for Claude Code, which does the writing with the skills in
  `.claude/skills/`.
- Time. Read [Honest limits](docs/HOWTO.md#14-honest-limits) before you start.

```sh
make install-transcribe                        # speech recognition + diarization (large download)
make new PROJECT="$HOME/books/grandma"         # a new book project, outside this repo
```

## Read next

[docs/HOWTO.md](docs/HOWTO.md) walks through the whole process, from recordings to a
printed book:

1. [What you need](docs/HOWTO.md#1-what-you-need)
2. [Setup](docs/HOWTO.md#2-setup)
3. [Transcription](docs/HOWTO.md#3-transcription)
4. [The timeline](docs/HOWTO.md#4-the-timeline)
5. [Story units](docs/HOWTO.md#5-story-units)
6. [The chapter map](docs/HOWTO.md#6-the-chapter-map)
7. [Writing](docs/HOWTO.md#7-writing) covers voice, quotation and sourcing, with a before-and-after example
8. [Family-history chapters](docs/HOWTO.md#8-family-history-chapters)
9. [Photos and illustrations](docs/HOWTO.md#9-photos-and-illustrations)
10. [Assembling and building](docs/HOWTO.md#10-assembling-and-building)
11. [Reviewing with the subject across a distance](docs/HOWTO.md#11-reviewing-with-the-subject-across-a-distance)
12. [Printing](docs/HOWTO.md#12-printing)
13. [Troubleshooting](docs/HOWTO.md#13-troubleshooting)
14. [Honest limits](docs/HOWTO.md#14-honest-limits)

Also:

- [docs/EXAMPLE-CHAPTER.md](docs/EXAMPLE-CHAPTER.md): a finished family-history chapter,
  annotated rule by rule.
- [scripts/README.md](scripts/README.md): every command-line tool, its flags, and the
  upstream breakage it works around.
- [PRIVACY.md](PRIVACY.md): what stays on your computer (the audio) and what goes to a cloud
  model (the transcript text, while Claude writes).
- [CONTRIBUTING.md](CONTRIBUTING.md): how to help, and why real family material never goes
  into issues or fixtures.

## License

The code, templates, skills and documentation are [MIT licensed](LICENSE). The license does
**not** cover your recordings, transcripts, photographs or the books you make with
BookAssembler. Those belong to you and your family. The worked example chapter in
`examples/erasthus-burnham/` is published for reading and learning only. EB Garamond in
`fonts/` is under the SIL Open Font License.
