---
name: chapter-dossier
description: The per-chapter research dossier of a Lineage book — the author's instructions and structural requests for that chapter, every search run (blocked and empty ones too), 100% of the sources found or scraped, the evidence and how it bears on the family's version, and the lessons learned — plus the 100% sources check and the generated THE RECORDS list. Use it whenever you research, draft, edit, score or rebuild a chapter, add or cite a source, run a search for a chapter, hand off a lookup a person must do, or record something the author said about a chapter — even if they only say "for that chapter, also look at…" or "add that to the chapter notes".
---

# Chapter dossiers

Every chapter that involves research has a folder `dossiers/<slug>/`, listed in
`dossiers/README.md`. It is the memory of that chapter's research: read it **before** you
work on the chapter, update it **as** you work, and never leave a search or a source unlogged.
A dossier is project material (it stays in the project's git), never platform.

```bash
python $LINEAGE/scripts/dossier.py new <slug> --title "Tobias Calder" --chapter chapters/04-tobias-calder.typ
```

| File | What goes in it | Rule |
|---|---|---|
| `DOSSIER.md` | The author's instructions and structural requests for this chapter (dated, in their words where possible); scope (units, spans, years, places); status; decisions made and pending | Add every new request the moment it's made, dated. Never delete one; mark it superseded if the author changes their mind. The author's requests here override the defaults for this chapter. |
| `RESEARCH-LOG.md` | One line per search or fetch: date · stage · query or URL · site · result (found / nothing / blocked and why) | Log failures and blocks too ("bot check, not bypassed"; "robots.txt disallows"), so nobody repeats them blindly. |
| `SOURCES.csv` | **100% of sources** found, consulted or scraped: `id,title,author_or_publisher,date,url,local_path,retrieved,used_for,cited_in_chapter,status,group` | `title` is the work's real title, never the fact it supports (that goes in `used_for`). `cited_in_chapter=yes` only when the chapter's text relies on it. Every cited source appears in the chapter's THE RECORDS; found-but-unused ones stay here as `consulted`. |
| `EVIDENCE.md` | The findings that matter: source ids, confidence, and whether each **confirms, adds to or contradicts** the family's version | Contradictions get a `// REVIEW:` in the chapter and a line in `facts/gaps.md`. Sensitive entries are marked SENSITIVE for the author to decide. |
| `LEARNINGS.md` | What worked and what didn't: best sources, dead ends, search terms that hit, access limits, layout tricks, style lessons from the author's feedback | A lesson any project could use is a platform change: propose it for Lineage. |

## Procedure
1. **Start:** read `DOSSIER.md`, `LEARNINGS.md` and `EVIDENCE.md`; skim `RESEARCH-LOG.md` so you
   don't redo searches.
2. **Research:** log each search (`dossier.py log <slug> <stage> <query> <site> <result>`) and add
   each new source (`dossier.py source <slug> --title … --url …`, next id `S###`).
   `$LINEAGE/scripts/fetch_records.py <slug> URL…` fetches politely and logs for you. Raw copies go
   under `facts/records/_raw/<slug>/`; shareable text through `export_sources.py`; facts into
   fact sheets in `facts/records/<person-or-slug>/`; the decisive ones into `EVIDENCE.md`.
   Anything a script can't reach goes on `research/MANUAL-LOOKUPS.md` (records-archives).
3. **Write and edit:** cite with `// src:` (tape) and `// context: … — URL` (sources). After the
   closing paragraph, THE RECORDS lists **every** cited source:
   ```bash
   python $LINEAGE/scripts/dossier.py records <slug> --out /tmp/records.typ   # paste after the closing paragraph
   python $LINEAGE/scripts/dossier.py check <slug> chapters/04-tobias-calder.typ   # must print OK
   ```
   `check` fails when a URL in the chapter isn't in `SOURCES.csv`, or a cited source isn't in
   THE RECORDS. Generating the list keeps it from drifting as the prose changes.
4. **Finish:** update the status in `DOSSIER.md`; add lessons to `LEARNINGS.md`.

## Frozen chapters
When the author freezes a chapter ("covered well, don't touch it again"), write FROZEN with
the date in `DOSSIER.md`. Its text is never edited again by anyone; its dossier may still gain
sources and notes.
