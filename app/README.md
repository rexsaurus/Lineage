# Lineage dashboard

The dashboard for a Lineage project: the family's sources, the Familypedia, the genealogy, the
timeline and the stories, in one place, with every fact traceable to its source and nothing
made up by the machine. Stories render as book pages and can be narrated; the printed book is
built from the same record. It runs on your own computer and binds to `127.0.0.1` only.

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
familypedia.py        the Familypedia engine: nine article types, infoboxes, tiers, records,
                      tagging, links, search and the map (server.py routes to it)
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
| **Familypedia** | An article for every subject the material names: person · place · event · vessel/vehicle · organization/unit · object · publication · occupation/trade · theme. Each has a lead from the material, a typed infobox, tier sections (witnessed · told · lore · what the records show), the passages that mention it, sources with thumbnails, typed records with archive, number, link and retrieval date, photographs and marked illustrations, stories, related articles, backlinks, open questions and a separate “Beyond the family”. Browse by type, A–Z, most material and needs more; full-text search with type filters; `[[links]]` across types; a map drawn from the records' own coordinates; Records and Photographs views with bulk tagging. |
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
- the Familypedia (all nine types), timeline and event pages, built from units, timeline,
  transcripts, the knowledge graph, records, photo index and routes; tagging of sources,
  records, photographs and events to any article, with suggestions that need acceptance;
  the evidence-coded map (tested on a 1,344-article project: index 0.5 s, cached reads 10 ms);
- the genealogy rebuild (Claude, evidence checked against the material, no evidence no link),
  review and apply, my edits, GEDCOM round trip;
- Home: story of the day, featured relative, Needs you, requests, counts, activity;
- stories with states, rendering to pages, narration script extraction (bridges refused), and what each
  story rests on: citation chips per paragraph and each image's provenance, with a toolbar;
- the Sources gallery and lightbox; illustrations are marked and never used as a person's picture;
- settings, identity, stale marks, repo verification, live key checks, voice list.

**Written, not tested end to end on the build machine:** ElevenLabs narration (no key used in
tests), crest generation (OpenAI), Google Drive sign-in and sync.

**Not built yet:** see `ROADMAP.md` (annotation and people tagging on photos, the public records
catalogue, the impact pass and "update everything this affects", hyperlinked stories with images
editable in place, "Beyond the family", the contributor-facing page behind an invite link).

## Familypedia: what it reads and writes

Articles come only from the project's files. Everything is optional; a project with none of
these simply has fewer articles.

| Input | Gives |
|---|---|
| `content/units/*.md` front matter `people`, `places`, `subjects` (`"vessel: Hannibal"`) | subjects, and which units mention them |
| `facts/timeline.csv` | events, their people and places, tiers, conflicts |
| `facts/people/*.md` (`# Name`, `Also called:`, `Relationship to …:`, `Dates:`) | person profiles and other names |
| `knowledge/graph.json` (or `nodes.csv` + `edges.csv`) | typed subjects (`person, place, event, voyage, vessel, organization, unit, object, publication, occupation, theme`), records (`record, letter, photograph, document`) and relations (`crew_on`, `master_of`, `voyage_of`, `served_in`, `held_by`, `part_of`, `mentions`, …) |
| `data/archives.csv` | the records catalogue (records-archives skill) |
| `facts/records/**/sources.csv` (`id, title, url, holder, type, date_retrieved`) and `**/sources.json` | research sources and retrieval dates by URL |
| `facts/**/*track*.csv`, `*route*.csv` (make_route_map.py columns) | ports and positions; coordinates for the map. A new `leg`, `gap_before`, or a row without coordinates is an unrecorded leg |
| `photos/photo_index.csv` | photographs; rows whose subject starts "Illustration" are marked as generated |
| `facts/gaps.md`, `facts/records/**/context_*.md` | open questions; public background offered under "Beyond the family" |
| `facts/records/_raw/geo/*.geojson` (or `facts/records/sources/geo/`) | coastlines for the map. No map tiles are ever fetched |

What it writes, all under `data/familypedia/` and all the author's own:
`<slug>.json` (lead, notes, infobox values, other names, type, coordinates, "same as" merges,
background), `subjects.json` (subjects created with "New subject…"), `tags.json` (tags on
`source:`, `record:`, `photo:` and `event:` targets, each with state and evidence), and
`routes.json` (which article a route belongs to when its file name matches more than one).
Suggested tags come only from names written in the item, with the words that name them; no
faces, no resemblance, nothing tagged until accepted.
