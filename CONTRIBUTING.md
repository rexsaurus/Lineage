# Contributing

Thanks for helping. BookAssembler is a small set of tools, Typst templates and Claude Code
skills; most contributions are one of these:

- **Bug fixes in the scripts.** Run `make sample` before and after; CI builds the sample
  project on every push, so a template or script that breaks it fails the check.
- **Transcription fixes.** Upstream libraries (WhisperX, pyannote, PyTorch,
  huggingface_hub) break often. If you work around a new breakage, document the upstream
  issue and the version numbers in `scripts/README.md` ("Works around:").
- **Skills.** The SKILL.md files are the rules the writing follows. Keep each rule in one
  place (the memoir-style-guide is the master for voice, quotation and sourcing), and say
  *why* a rule exists. That is what lets someone apply it to a case it didn't foresee.
- **Templates.** `book/template.typ` is the single source of truth; projects receive a copy
  at build time.

## Ground rules
- **No real family content in issues, pull requests or fixtures.** Use the invented sample
  project, or invent your own. Never attach someone's transcript to an issue.
- No tokens, keys, Drive IDs or personal paths in commits. Before you open a PR, run:
  `grep -rnE "hf_[A-Za-z0-9]{6,}|/Users/|/home/[a-z]" --exclude-dir=.venv .`
- Keep dependencies few. Say what a new one is and why in the PR.
- Python 3.10+, standard library where possible; shell scripts with `set -euo pipefail`.

## Development
```bash
make install          # build tools
make sample           # must still produce both PDFs
.venv/bin/python -m py_compile scripts/*.py .claude/skills/*/scripts/*.py
```
