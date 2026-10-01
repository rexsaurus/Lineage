---
name: {{name}}-units
description: Cut {{source_noun}}s into {{unit_plural}} — the smallest pieces that stand alone and can be moved without rewriting — and prove nothing was lost with the coverage check. Use when creating, splitting, merging or writing {{unit_plural}}.
---

# {{title}}: {{unit_plural}}

Follow `{{name}}-policy`.

**A {{unit_noun}} is:** {{unit_definition}}

Units sit between the sources and the {{output_noun}}, so the {{output_noun}} can be reordered
without rewriting anything and every sentence can be traced to its lines.

## File format: `units/U001-short-slug.md`
```markdown
---
id: U001
title: Short title
spans: ["{{span_example}}"]          # the source lines this unit covers
tier: {{first_tier}}                    # one of: {{tier_ids}}
bridges_approved: []                  # bridge IDs a human has approved
questions: []                         # open questions for the next gate
---
## Source
(the cited lines, copied for the reader's convenience)

## Text
One paragraph per point, each with a citation {{citation_example}}.
```

## Steps
1. Read the sources in order. Cut where a reader could start fresh.
2. Every non-blank source line belongs to exactly one {{unit_noun}} or to `excluded.csv`
   (`span,reason`). `python $PIPELINE_HOME/scripts/pl.py coverage` must report 0 uncovered.
3. Write `## Text` by the policy: restate, order, connect; cite every paragraph; bridges for
   anything added; questions into `questions:`.
4. `pl.py check` must pass before the next gate.
