# {{title}}: how to use it

{{domain}}.

## 1. What you need
Python 3.10+ with `pyyaml`, and the builder for your output (`{{builder}}`). Claude Code does
the writing, using the skills in `.claude/skills/`.

## 2. Start a project
```bash
make new PROJECT=~/work/my-project
cd ~/work/my-project
export PIPELINE_HOME=<this folder>
```
A project has: `{{source_dir}}/` (the {{source_noun}}s), `ledger/`, `units/`, `map.csv`,
`excluded.csv`, `gates.yaml`, `build/` and `output/`.

## 3. Ingest the {{source_noun}}s
Put each {{source_noun}} in `{{source_dir}}/` as plain text, one addressable line per line.
`python $PIPELINE_HOME/scripts/pl.py ingest` checksums them. From then on they never change;
`pl.py check` fails if a byte does.

Citations look like `{{citation_example}}` (format `{{citation}}`); a range is `a-b`.

## 4. Cut {{unit_plural}}
A {{unit_noun}} is: {{unit_definition}}

One file per {{unit_noun}} in `units/` (format in `.claude/skills/{{name}}-units/SKILL.md`).
Every non-blank source line must be in a {{unit_noun}}'s `spans` or in `excluded.csv` with a
reason: `pl.py coverage` proves nothing was dropped.

## 5. Evidence tiers
{{tiers_table}}

## 6. Writing, and bridges
Each paragraph cites its lines. Anything the sources don't support goes in
`[[bridge ID: text]]`: highlighted in drafts, approved by adding the ID to
`bridges_approved`, and **the final build fails while one is unapproved**.

## 7. Gates
{{gates_table}}

`pl.py status` shows where you are; `pl.py questions` writes every open question to
`questions.md`, grouped by gate; `pl.py gate <ID> --by <name>` records the decision.

## 8. Build
`make draft PROJECT=…` assembles `build/{{name}}.{{ext}}` from `map.csv` (GENERATED header —
never edit it) and runs the builder into `output/`. `make final PROJECT=…` does the same and
refuses on any failed check, open bridge or open gate.

## 9. Versions
`pl.py snapshot "label" [--major]` commits the inputs, tags `vN.M`, and copies `output/` to
`output/versions/<tag>/` with a `MANIFEST.json` naming the input commit and every source's
checksum. Take a major version before anything is sent to anyone.

## 10. The fixture
`fixture/` is a complete small project. `make fixture` must always pass; if you change a rule,
change the fixture with it.
