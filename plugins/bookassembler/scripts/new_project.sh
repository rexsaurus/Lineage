#!/usr/bin/env bash
# Create a new BookAssembler project folder.
#   new_project.sh path/to/new-book
# Works from a repo checkout (make new) or from the installed plugin:
#   bash "$BOOKASSEMBLER/scripts/new_project.sh" ~/books/grandma
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # the plugin root
PROJECT="${1:?usage: new_project.sh path/to/new-book}"
if [[ -e "$PROJECT/book.yaml" ]]; then echo "$PROJECT already has a book.yaml; not overwriting" >&2; exit 1; fi
mkdir -p "$PROJECT"/{audio,transcript,facts/records,content/units,data,chapters,book/front,photos/source,photos/print,output,.claude}
cp "$ROOT/skills/interview-transcriber/assets/book.yaml" "$PROJECT/book.yaml"
cp "$ROOT/templates/project/CLAUDE.md" "$PROJECT/CLAUDE.md"
cp "$ROOT/templates/project/gitignore" "$PROJECT/.gitignore"
ln -sfn "$ROOT/skills" "$PROJECT/.claude/skills"
cp "$ROOT"/book/front/*.typ "$PROJECT/book/front/"
echo "New project at $PROJECT. Next: fill in book.yaml, put recordings in audio/, open Claude Code there."
echo "Tools: export BOOKASSEMBLER=$ROOT"
