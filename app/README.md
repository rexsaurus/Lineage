# Lineage dashboard

A local dashboard for the Lineage pipeline: turn recorded interviews with a relative into a
book (and an audiobook) without the machine making things up. It runs on your own computer and
binds to `127.0.0.1` only.

```bash
./lineage                         # http://127.0.0.1:8777, project ~/lineage-books/my-book
./lineage ~/books/grandma         # point it at a project folder
python3 server.py --command bash  # use a different terminal command
python3 server.py --demo          # invented sample content, with a banner; never the default
```

Python 3.10+, standard library only. The page loads xterm.js and fonts from a CDN.

## Layout of the code

```
server.py             ENGINE (/api/engine/*: sources, stories, narration, timeline, Familypedia,
                      genealogy, home, requests), dashboard state, AUTHOR-ONLY SURFACE (terminal,
                      keys, repo, Drive, CLIs, contributors), HTTP (routing, session token, static)
static/index.html     the page shell
static/css/app.css    the styles
static/js/core.js     labels, routing, the settings gear, the dock (player + terminal), overlays
static/js/<tab>.js    one file per surface: home, sources, familypedia, genealogy, stories,
                      timeline, settings (the four settings pages), terminal (the drawer)
~/.lineage/           keys (config.json) and the Google token, chmod 600, this machine only
<project>/lineage.json            settings
<project>/data/genealogy/         derived.json (approved rebuild), mine.json (my edits),
                                  proposed.json (a rebuild awaiting review), history.json
<project>/data/requests.json      what you've asked for, with dates and status
<project>/.lineage/               terminal log, rendered pages, thumbnails, crest attempts
```

The engine endpoints use plain vocabulary so a simpler front end can sit on the same server
later. Everything technical is grouped under the author-only surface, marked as such in the code.

## The surfaces

No wizard: every tab works whenever you open it and says plainly what it still needs.

**Tabs (the working surfaces):**

| Tab | What it's for |
|---|---|
| **Home** | The landing page. Story of the day (seeded by the date; "Another" steps through), a featured relative (people with material but no story first), **Needs you** (one-click actions ordered by what they unblock), **Request more** (question lists built from open questions, gaps and unconfirmed links, saved as asked/answered), counts at a glance, and a plain activity feed. An empty project shows one card: what to add first. |
| **Sources** | Recordings, scans, letters. Intake runs visibly (Saved → Reading → Understanding → Indexed), with edit, rename, re-ingest, trash and restore, bulk actions. |
| **Familypedia** | An encyclopedia built only from the project's material: people, places, events (with date, precision, tier, the passages they rest on, before and after, conflicts), wiki links, backlinks, stubs, notes marked as yours. |
| **Genealogy** | The tree, derived from the sources. Every link carries its quoted evidence; no evidence, no link. Rebuild with a review of what changed (contradictions kept, never resolved silently); pan/zoom tree with descendant, ancestor and hourglass layouts, unknown-parent nodes and line styles by tier; Cast view; merge, split, add links and notes (kept across rebuilds); GEDCOM in and out (imports arrive unconfirmed); SVG, PNG and a printable chart. Living people are left out of exports. |
| **Stories** | Every story, oldest first in era bands. Read (real book pages through the Typst template) and Listen on the same row; Narrate / Re-narrate with ElevenLabs, a voice per story, stale-audio marks, Narrate all with a character count, a pinned player, audio download. Unapproved bridges are never narrated. "Generate" hands work to the Genealogist. |
| **Timeline** | A vertical spine with decade bands and a year rail; cards with date and precision, tier, people, place, citations and story links; stars; conflict cards; gap cards with "Add to questions"; an undated drawer; filters and search; SVG, PNG and a printable appendix. |

**Behind the gear** (`#/settings/<section>`, each with its own section list; Esc or Done
returns to the tab you came from; a dot on the gear means something needs attention):

| Page | What it holds |
|---|---|
| **Family details** | Lineage title, family name, subtitle, summary (with a draft button), subject, date range and places, and the crest: None (default) · Generate (four candidates per try, every attempt kept) · Upload (original kept; background removal and one-colour copies), a show toggle per surface, previews in context, provenance. |
| **Connectors** | Google Drive, GitHub, Anthropic, OpenAI, ElevenLabs, agent CLIs; honest "not wired up" cards. |
| **Contributors** | People who add material (the family is the subject; contributors are who adds to it): roles, invite links, requests outstanding, the shared folder, the review queue. |
| **Project settings** | Repo, Drive folder, narration voice, narrator and writing style, story templates, trim and printer, the terminal command, resolved paths. |

**The terminal** is a drawer, not a tab: the **Terminal** button in the header (or Ctrl+`)
opens it over any tab. It holds the Genealogist, quick prompts, the pipeline actions and the
approvals list. Old addresses (`#read`, `#listen`, `#transcribe`, `#family`, `#connectors`,
`#settings`) redirect to their new homes.

The UI calls the written pieces **stories**; the printed book still has chapters, and the files
keep their names (`chapters/`, `data/chapters.csv`). The mapping lives in one place, the `L`
labels object in `static/js/core.js`.

## The terminal: security model

The drawer embeds a real terminal (a PTY running `claude`, or whatever you choose). It is a
shell on your machine, so:
- the server binds to `127.0.0.1` only, and there is no option to change that;
- every `/api/*` call needs a session token minted at server start and injected into the page;
  other websites can't read it;
- requests whose `Host` header isn't `127.0.0.1` or `localhost` are refused (DNS rebinding);
- project files are only served from inside the project folder.

Output streams to the browser over Server-Sent Events; keystrokes go up with POST. No
websockets, no extra dependencies.

## What is real, and what isn't yet

**Real and tested:**
- the server, security model and PTY terminal;
- intake end to end (PDF, image, audio, text) with dedupe, trash and restore;
- the Familypedia, timeline and event pages, built from units, timeline and transcripts;
- the genealogy rebuild (Claude, evidence checked against the material, no evidence no link),
  review and apply, my edits, GEDCOM round trip;
- Home: story of the day, featured relative, Needs you, requests, counts, activity;
- stories with states, rendering to pages, and narration script extraction (bridges refused);
- settings, identity, stale marks, repo verification, live key checks, voice list.

**Written, not tested end to end on the build machine:** ElevenLabs narration (no key used in
tests), crest generation (OpenAI), Google Drive sign-in and sync.

**Not built yet:** see `ROADMAP.md` (annotation and people tagging on photos, the public records
catalogue, the impact pass and "update everything this affects", hyperlinked stories with images
editable in place, "Beyond the family", the contributor-facing page behind an invite link).
