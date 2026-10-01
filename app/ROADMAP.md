# Dashboard roadmap

Specs received, in the order they will be built. Each lands as its own commit.

| # | Spec | Status |
|---|---|---|
| 1 | Five-tab dashboard: Settings, Chat (terminal), Style, Sources, Connectors | done |
| 2 | Eight tabs: Settings · Sources · Familypedia · Transcribe History · Read About It · Listen To It · Connectors · Family; no wizard anywhere | done |
| 3 | "Stories" vocabulary in the UI (one labels module), story states: draft · in the book · kept aside | done |
| 4 | Source intake (done: ingest + dedupe, extract, understand with Claude or a labelled basic fallback, index + search, Drive copy, thumbnails, edit drawer with my-edits-win, re-ingest, trash/restore/delete permanently, bulk actions; OCR needs tesseract): ingest + SHA-256 dedupe, text extraction/OCR, understand (summary, suggested name, entities), index, optional Drive copy; row actions (edit, re-scan, trash/restore, transcribe) | done |
| 5 | Source annotation, thumbnails (+ gallery, lightbox), people tagging with evidence; never identify by resemblance | queued |
| 6 | Familypedia (first version done: articles, wiki links, backlinks, search, A–Z, random, stubs, notes; still to do: cast grid, clickable tree, GEDCOM, merge/split, Beyond the family): articles (person, place, event, object, organization, theme), cast, person pages, clickable tree, GEDCOM, stubs, "Beyond the family" kept separate | queued |
| 7 | Public records: paste links and scan, typed catalogue, by-archive view, citations into THE RECORDS | queued |
| 8 | Single-story demo and per-row Generate + Preview: rendered pages, citations panel, real photos first, marked illustrations, queue | queued |
| 9 | Stories index: chronological, era bands, inline narration (ElevenLabs), mini player, "play all from here" | queued |
| 10 | Propagation: impact pass after intake, "update everything this affects" with a review diff, contradictions never auto-resolved, history with revert | queued |
| 11 | Family: members, roles, invites (local until hosted), review queue, server-side permissions | management side done; contributor view waits for hosting |
| 12 | Stories hyperlinked (people/places/citation chips, no unlinked facts), images editable in place with provenance | queued |
| 13 | Settings: the lineage's identity (family name, title, subtitle, summary with a draft button, subject, covers, crest; stale marks) | done |
| 14 | No demo content by default (`--demo` with a banner); pipeline buttons hand real work to the Genealogist | done |
| 15 | Stories tab: merge Read About It and Listen To It; narration on every row; pinned mini player | next |
