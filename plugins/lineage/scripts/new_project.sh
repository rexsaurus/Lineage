#!/usr/bin/env bash
# Create a new Lineage project folder.
#   new_project.sh path/to/new-book
# Works from a repo checkout (make new) or from the installed plugin:
#   bash "$LINEAGE/scripts/new_project.sh" ~/books/grandma
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # the plugin root
PROJECT="${1:?usage: new_project.sh path/to/new-book}"
if [[ -e "$PROJECT/book.yaml" ]]; then echo "$PROJECT already has a book.yaml; not overwriting" >&2; exit 1; fi
mkdir -p "$PROJECT"/{audio,transcript,facts/records,content/units,data,chapters,book/front,photos/source,photos/print,output,.claude}
cp "$ROOT/skills/interview-transcriber/assets/book.yaml" "$PROJECT/book.yaml"
cp "$ROOT/templates/project/CLAUDE.md" "$PROJECT/CLAUDE.md"
cp "$ROOT/templates/project/gitignore" "$PROJECT/.gitignore"
cp "$ROOT/templates/project/Makefile" "$PROJECT/Makefile"
mkdir -p "$PROJECT/local-overrides"
printf '# local-overrides\n\nThings genuinely specific to this project (a one-off story template, a caption convention\nnobody else would want). Everything else is platform and belongs in the Lineage repo.\n' > "$PROJECT/local-overrides/README.md"
VERSION="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['version'])" "$ROOT/.claude-plugin/plugin.json")"
COMMIT="$(git -C "$ROOT" rev-list -n1 "v$VERSION" 2>/dev/null || true)"
printf '{\n  "lineage": "%s",\n  "tag": "v%s",\n  "commit": "%s",\n  "source": "git@github.com:rexsaurus/Lineage.git",\n  "stale_on_update": []\n}\n' "$VERSION" "$VERSION" "$COMMIT" > "$PROJECT/lineage.lock"
ln -sfn "$ROOT/skills" "$PROJECT/.claude/skills"
cp "$ROOT"/book/front/*.typ "$PROJECT/book/front/"
echo "New project at $PROJECT. Next: fill in book.yaml, put recordings in audio/, open Claude Code there."
echo "Tools: export LINEAGE=$ROOT"
