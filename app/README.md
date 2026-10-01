# Lineage dashboard

A local dashboard for the Lineage pipeline: turn recorded interviews with a relative into a
book (and a podcast) without the machine making things up. It runs on your own computer and
binds to `127.0.0.1` only.

```bash
./lineage                         # http://127.0.0.1:8777, project ~/lineage-books/my-book
./lineage ~/books/grandma         # point it at a project folder
python3 server.py --command bash  # use a different terminal command
```

Python 3.10+, standard library only. The page loads xterm.js and fonts from a CDN.

## Layout of the code

```
server.py           ENGINE (sources, pages, approvals, stage jobs: /api/engine/*, /api/run/*)
                    AUTHOR-ONLY SURFACE (terminal, keys, repo, Drive, CLIs)
                    HTTP (routing, session token, static files)
static/index.html   the dashboard
static/logo.svg     the mark
~/.lineage/         keys (config.json) and the Google token, chmod 600, this machine only
<project>/lineage.json        settings and stage status
<project>/.lineage/terminal.log   terminal scrollback (capped at 1 MB)
```

The engine endpoints use plain vocabulary ("sources", "page", "approvals") so a simpler,
non-technical front end can sit on the same server later. Everything technical is grouped
under the author-only surface, marked as such in both files.

## The tabs

No wizard: every tab works whenever you open it and says plainly what it still needs.

| Tab | What it's for |
|---|---|
| **Settings** | The lineage's identity (family name, title, subtitle, summary, subject, covers, crest), the book's trim and printer, narrator and writing style, story templates with rendered previews, photo formats, repo and Drive folder, the terminal command, resolved paths |
| **Sources** | The sources table: kind, size, duration, status, transcript drawer with audio jump, open/file/Drive links, drag-and-drop upload |
| **Familypedia** | An encyclopedia of the family built from the project's own material: people, places and events, wiki links laid over the text, backlinks, search, A–Z, random article, stubs under "Needs more", citation chips that open the transcript line, notes marked as yours |
| **Transcribe History** | The working surface: the embedded terminal ("Chat with the Genealogist") with a composer and quick prompts, the pipeline actions, the story map, everything awaiting approval |
| **Read About It** | The stories, oldest first in era bands, each rendered as real book pages through the Typst template; state per story (draft · in the book · kept aside) and its place in the book |
| **Listen To It** | Voice (live from ElevenLabs), episode length, episodes with their scripts and players |
| **Connectors** | Google Drive, GitHub, Anthropic, OpenAI, ElevenLabs, agent CLIs on this machine; honest "not wired up" cards |
| **Family** | Members, roles (contributor, reader, editor), expiring and revocable invite links, the review queue |

The UI calls the written pieces **stories**; the printed book still has chapters, and the files
keep their names (`chapters/`, `data/chapters.csv`). The mapping lives in one place, the `L`
labels object at the top of the page's script.

## The terminal: security model

Transcribe History embeds a real terminal (a PTY running `claude`, or whatever you choose). It is a
shell on your machine, so:
- the server binds to `127.0.0.1` only, and there is no option to change that;
- every `/api/*` call needs a session token minted at server start and injected into the page;
  other websites can't read it;
- requests whose `Host` header isn't `127.0.0.1` or `localhost` are refused (DNS rebinding);
- project files are only served from inside the project folder.

Output streams to the browser over Server-Sent Events; keystrokes go up with POST. No
websockets, no extra dependencies.

## What is real and what is a prototype

**Real:**
- the server and security model;
- the PTY terminal (start, restart, Ctrl-C, resize, exit codes, scrollback saved per project);
- settings shared by every tab, and the lineage identity (covers filled from the timeline,
  summary drafted from the project's own counts, crest, stale marks);
- repo verification and `git init`;
- file upload (originals never overwritten);
- the Sources table and transcript drawer;
- "page" drafts from a source's exact words;
- the approvals list;
- the Familypedia, built from units, timeline and transcripts, with notes and leads you edit
  saved as yours and never overwritten;
- the stories index with states and per-story rendering to book pages;
- family members and invite links, validated server-side;
- live key checks for Anthropic, OpenAI, ElevenLabs and GitHub;
- the live ElevenLabs voice list with previews;
- agent CLI and `gh` detection, and push.

**Written but not tested end to end** (no Google credentials on the test machine): Google
Drive device-flow and browser sign-in, folder verification, and two-way sync.

**Prototype:**
- The pipeline stages (records, genealogy, story map, writing, podcast) return demonstration
  content on a timed job. Each is one function in `server.py` (`demo_records`,
  `demo_genealogy`, `demo_chapters`, and the branches in `engine_run`); that is where the
  Lineage skills get wired in.
- Narration audio isn't rendered yet.
- "Beyond the family" in the Familypedia isn't wired up.
- The contributor-facing page behind an invite link arrives with hosting.
- Grok and ChatGPT cards are placeholders and say so.

See `ROADMAP.md` for what is queued.
