---
name: {{name}}-policy
description: The rules every {{title}} skill defers to — citations, evidence tiers, what may be added, bridges, and who decides. Use before writing, checking or changing any {{unit_noun}}, any {{output_noun}}, or anything that cites a {{source_noun}}.
---

# {{title}}: policy

**Domain:** {{domain}}. This skill is the master. Every other {{name}} skill defers to it; where they
seem to disagree, this one wins.

## 1. Sources are evidence, and they never change
- A {{source_noun}} goes into `sources/` once and is never edited, renamed or deleted.
  `pl.py ingest` records its SHA-256 in `ledger/sources.json`; `pl.py check` fails if a byte
  changes. A correction is a **new** source file, not an edit.
- Sources are read line by line. Line numbers are the addresses everything else cites.

## 2. Every claim cites back
- Citation format: `{{citation}}` — for example `{{citation_example}}`. A range is `a-b`.
- Every paragraph of a {{unit_noun}} carries at least one citation, and every citation points
  inside that {{unit_noun}}'s own `spans`. `pl.py check` enforces both.
- Quote exactly or not at all. Restate, order and connect; never add facts, motives,
  feelings or detail the source does not contain.

## 3. Evidence tiers
Every {{unit_noun}} declares exactly one tier, and says it in the text where it matters:

{{tiers_table}}

Never upgrade a tier silently. When two sources disagree, keep both and say so.

## 4. Anything the model adds is a bridge
Connective or interpretive text that no source supports goes in `[[bridge ID: text]]`.
Drafts show it highlighted as ⟦BRIDGE ID: …⟧. A human approves it by adding the ID to the
{{unit_noun}}'s `bridges_approved`. **The final build fails while any bridge is unapproved.**

## 5. Outputs are generated
The {{output_noun}} in `build/` and `output/` is generated from `units/` and `map.csv` and
carries a GENERATED header. Never edit it; `pl.py check` detects hand edits. Change the units.

## 6. Humans decide at the gates
{{gates_table}}

Stop at a gate. Collect every open question into one batch (`pl.py questions`) rather than
asking one at a time, then wait for a person to run `pl.py gate <ID>`.

## 7. Domain rules
{{domain_rules}}
