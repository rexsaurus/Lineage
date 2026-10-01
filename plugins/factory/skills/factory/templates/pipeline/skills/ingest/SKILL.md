---
name: {{name}}-ingest
description: Bring {{source_noun}} files into a {{title}} project and lock them — checksums, naming, and what to do when a source is wrong. Use when adding, checking or replacing anything in sources/.
---

# {{title}}: ingest {{source_noun}}s

Follow `{{name}}-policy`. Run from the project folder.

1. Put each {{source_noun}} in `sources/` as a plain-text file, one line per addressable
   piece. The file's stem is its citation id (`{{citation_example}}` cites line 3 of the
   source whose stem is in the example). Choose short, stable stems.
2. `python $PIPELINE_HOME/scripts/pl.py ingest` — records SHA-256 for every new file. If a file
   already in the ledger has changed, it stops: never fix a source in place; add a corrected
   copy as a new file and say why in `excluded.csv` for the old lines.
3. Report: files added, line counts, anything that looked garbled.
4. Gate check: if a gate follows `ingest` in `pipeline.yaml`, stop and batch the questions.
