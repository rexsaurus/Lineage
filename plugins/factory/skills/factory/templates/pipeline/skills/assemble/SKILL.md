---
name: {{name}}-assemble
description: Generate the {{output_noun}} from {{unit_plural}} and map.csv, then build it with {{builder}}. Use when ordering {{unit_plural}}, assembling, building a draft or a final {{output_noun}}.
---

# {{title}}: assemble and build the {{output_noun}}

Follow `{{name}}-policy`.

- `map.csv` (`section,unit`) is the order of the {{output_noun}}. Moving a {{unit_noun}} is a
  one-line change; nothing is rewritten.
- `python $PIPELINE_HOME/scripts/pl.py build` assembles `build/{{name}}.{{ext}}` (GENERATED
  header, bridges highlighted) and runs the builder (`{{builder}}`) into `output/`.
- `pl.py build --final` refuses while any check fails, any bridge is unapproved, or any gate
  is open. Unapproved bridges never reach a final {{output_noun}}.
- Never edit `build/` or `output/`. If something reads wrong, fix the {{unit_noun}}.
