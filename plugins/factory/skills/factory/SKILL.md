---
name: factory
description: Generate a complete, trustworthy source-to-output pipeline for a new domain (skills, runtime, fixture, HOWTO) from five answers — sources and citations, units, evidence tiers, output and builder, human gates. Use when someone wants "a Lineage for X", a pipeline that turns raw material (transcripts, logs, papers, records) into a document where every claim cites back, or asks to scaffold a citation-checked writing workflow.
---

# The factory

Lineage turns interview recordings into a book. Underneath it is a pattern that has
nothing to do with books: **raw sources → small cited units → generated output, with humans
deciding at named gates.** This skill asks five questions, writes a spec, and runs
`scripts/scaffold.py`, which builds the whole pipeline the same way every time.

Read `docs/FACTORY.md` in the repo for why each invariant exists.

## Step 1 — ask the five questions (in one message)

Ask them together, with an example answer for each, and wait. Don't scaffold on guesses.

1. **What is the source, and what does a citation look like?**
   What raw material comes in (recordings, chat exports, papers, case files)? How does a sentence
   point back at it? The generic runtime cites lines of plain-text sources: `[call-1:12]`, `[chat-0412:118-121]`.
2. **What is a unit** — the smallest piece that stands alone and can be moved without rewriting
   anything? (A story; a decision; a timeline event; a finding.)
3. **What are the evidence tiers?** Two to four levels of how well a claim is supported
   (witnessed / told / lore; logged / stated / reconstructed; documented / asserted / disputed).
4. **What is the output, and what builds it?** Markdown, HTML or Typst; builder `none`, `typst`,
   `pandoc`, or a shell command with `{in}` and `{out}`.
5. **Where are the gates** — the points where a human decides? Each gate sits after a stage
   (`ingest`, `units`, `assemble`, `build`) and has one question. There must be a final sign-off
   after `build`.

Also ask for 2–5 domain rules (what this domain must never do) and, if possible, a small real
example to turn into the fixture.

## Step 2 — write the spec

Write `<name>.yaml` in the shape of `examples/toy-minutes.yaml` (a full example with a fixture).
Keys: `name, title, domain, source{noun,dir,citation}, unit{noun,plural,definition},
tiers[{id,meaning}], output{noun,format,builder,title}, gates[{id,name,after,question}], rules[],
fixture{sources,units,map}` (fixture optional — a generic one is generated if absent).

## Step 3 — scaffold

```bash
python <this skill>/scripts/scaffold.py <name>.yaml --out <dir>
cd <dir> && make fixture
```
`make fixture` must pass before you hand anything over. The spec is the record of the
decisions: same spec, same pipeline.

## What is always generated (do not ask, do not remove)

These do not vary by domain; they are what make the output trustworthy.

| Invariant | Where it lives |
|---|---|
| Sources immutable and checksummed; every claim cites back into its own unit's spans | `pl.py ingest`, `pl.py check` |
| Units between source and output, with a coverage check (every source line is in a unit or excluded with a reason) | `units/`, `excluded.csv`, `pl.py coverage` |
| One policy skill the others defer to | `.claude/skills/<name>-policy/` |
| Outputs generated, never hand-edited (GENERATED header, hand edits detected) | `pl.py assemble`, `build/.generated.json` |
| Anything the model adds is a `[[bridge ID: …]]`; the final build fails while one is unapproved | `pl.py build --final` |
| Named gates with batched questions | `pipeline.yaml` gates, `pl.py questions`, `pl.py gate` |
| Versioning that pins each output to its exact inputs | `pl.py snapshot` → `MANIFEST.json` |
| An orchestrator with a status command | `.claude/skills/<name>-pipeline/`, `pl.py status` |
| A fixture project and a HOWTO | `fixture/`, `docs/HOWTO.md` |

## Step 4 — make it the domain's own

After scaffolding, edit only the domain parts:
- `<name>-policy` §7: the domain rules, in the voice of someone who has been burned by them.
- Replace the generic fixture with a small realistic one (two sources, three units, one bridge).
- If the domain needs more than the runtime gives (audio transcription, timestamp citations,
  page layout), add scripts beside `pl.py`; keep the invariants intact and keep `make fixture`
  passing.

## Worked example 1 — Lineage

| | |
|---|---|
| 1. Source / citation | Interview recordings, transcribed locally; citation `[S1 00:04:28]` (session + timestamp) |
| 2. Unit | A story unit: one story as the subject told it, movable between chapters without rewriting |
| 3. Tiers | witnessed / told by a named person / family lore — plus documented (in THE RECORDS) |
| 4. Output / builder | A 7×10 printed book, Typst |
| 5. Gates | speakers confirmed (after transcription) · chapter map approved (after units) · final sign-off |

`examples/lineage.yaml` scaffolds the same skeleton with line citations. The real
Lineage (plugins/lineage) extends it with transcription, timestamp citations,
family-history research and book layout. That is step 4 done thoroughly.

## Worked example 2 — an incident review (not a book)

| | |
|---|---|
| 1. Source / citation | Incident-channel chat exports, alert history, deploy logs; `[chat-0412:118]` |
| 2. Unit | A timeline event: one thing that happened at one time, with when and who |
| 3. Tiers | logged (a system recorded it) / stated (a person said it then) / reconstructed (inferred later) |
| 4. Output / builder | An HTML review page, no builder |
| 5. Gates | logs complete · timeline agreed by the people involved · blameless sign-off before publishing |

Rules: blameless language; UTC with the source's own timestamp; a cause is a bridge until someone
with evidence approves it. Spec: `examples/incident-review.yaml`.

## Report
The spec path, the generated tree, the `make fixture` output, and the domain rules you still
need from the user.
