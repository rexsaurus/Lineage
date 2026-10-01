---
name: {{name}}-pipeline
description: Orchestrate the {{title}} pipeline — status, what to run next, gates with batched questions, and versioned snapshots that pin each {{output_noun}} to its exact inputs. Use at the start of every session and whenever asked where things stand.
---

# {{title}}: the pipeline

Start every session with `python $PIPELINE_HOME/scripts/pl.py status` from the project folder and
resume at the first incomplete stage. Read `{{name}}-policy` before any writing.

| Stage | Skill | Done when |
|---|---|---|
| ingest | `{{name}}-ingest` | every source in the ledger |
| units | `{{name}}-units` | coverage 0 uncovered, `pl.py check` passes |
| assemble / build | `{{name}}-assemble` | draft {{output_noun}} in `output/` |
| final | `{{name}}-assemble` | all gates approved, 0 open bridges |

## Gates
{{gates_table}}

Between gates, run straight through without asking. At a gate: `pl.py questions` writes every
open question (unit questions and unapproved bridges) to `questions.md`, grouped by gate. Send
that one batch, stop, and wait for a person to run `pl.py gate <ID>`.

## Versions
`pl.py snapshot "label"` commits the inputs, tags `vN.M`, copies `output/` to
`output/versions/<tag>/` and writes `MANIFEST.json` with the input commit, every source's
SHA-256, and the gate decisions. Take a **major** version (`--major`) before anything is sent
to anyone.
