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

## The terminal: security model

The Chat tab embeds a real terminal (a PTY running `claude`, or whatever you choose). It is a
shell on your machine, so:
- the server binds to `127.0.0.1` only, and there is no option to change that;
- every `/api/*` call needs a session token minted at server start and injected into the page;
  other websites can't read it;
- requests whose `Host` header isn't `127.0.0.1` or `localhost` are refused (DNS rebinding);
- project files are only served from inside the project folder.

Output streams to the browser over Server-Sent Events; keystrokes go up with POST. No
websockets, no extra dependencies.

## What is real and what is a prototype

**Real:** the server and security model; the PTY terminal (start, restart, Ctrl-C, resize,
scrollback saved per project); settings shared by every tab; repo verification and `git init`;
file upload (originals never overwritten); the Sources table (kind, size, duration via ffprobe,
transcription and citation status, transcript drawer with audio jump); "page" drafts built from
a source's exact words; the approvals list (bridges, REVIEW notes, proposed stages); live key
checks for Anthropic, OpenAI, ElevenLabs and GitHub; the live ElevenLabs voice list with
previews; agent CLI detection; `gh` detection and push.

**Written but not tested end to end** (no Google credentials on the test machine): Google
Drive device-flow and browser sign-in, folder verification, and two-way sync.

**Prototype:** the five pipeline stages (records, genealogy, chapter map, chapters, podcast)
return realistic demonstration content on a timed job. Each is one function in `server.py`
(`demo_records`, `demo_genealogy`, `demo_chapters`, and the stage branches in `engine_run`);
that is where the Lineage skills get wired in. Grok and ChatGPT cards are placeholders and say so.

See `ROADMAP.md` for what is queued.
