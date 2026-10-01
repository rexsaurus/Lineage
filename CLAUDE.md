# Lineage

The public platform for a family's own documentation and research: the dashboard, skills,
scripts and templates that turn what a family collects into a researched, sourced record
(genealogy, timeline, Familypedia), with stories, a printed book and narration as exports.

## The arrangement with book projects (read first)
Book projects (each family's own, usually private, repo) are **consumers** of Lineage, not
forks of it.
- **Platform changes are made here and flow down.** Style guides, story templates, skills,
  the dashboard, scripts and the pipeline live only in this repo. A fix found while working in
  a book project is made here, released, and the project is updated to the release. Never let
  a project carry its own patched copy.
- **Content lives in the project.** Sources, transcripts, story units, stories, people,
  records, photos and the project's settings never come into this repo. This repo is public:
  before every push, check the diff for real names, places, addresses, Drive IDs, tokens or
  paths from someone's project.
- **One-off things stay in the project** in `local-overrides/` (a story template or caption
  convention nobody else would want), and the person is told each time.
- **When a request would cross the line**, say so first, then do it on the right side.

## Releases
- Every release is an annotated tag `vX.Y.Z` with an entry in `CHANGELOG.md`, and the version
  in `plugins/lineage/.claude-plugin/plugin.json` matches it.
- Every changelog entry starts with **Alters generated stories: yes/no**. It is yes when
  anything under `plugins/lineage/book/`, `plugins/lineage/fonts/` or `plugins/lineage/skills/`
  changed; `lineage update` then marks the project's generated stories stale and lists them.
  It never regenerates them.
- `bin/lineage version | update [--apply] | dashboard` is what projects use (through their
  `make lineage-version`, `make update-lineage [APPLY=1]`, `make dashboard`). Releases install
  read-only to `~/.lineage/releases/<tag>`; a project pins one in `lineage.lock`.
- Commits here are authored `Lineage contributors <noreply@lineage.invalid>`.

## Layout
- `plugins/lineage/` the plugin: `skills/`, `scripts/`, `book/` (Typst template), `fonts/`,
  `templates/project/` (what `make new` gives a project: CLAUDE.md, Makefile, gitignore).
- `app/` the dashboard (`app/README.md` lists what it reads and writes in a project).
- `bin/lineage` versions and updates; `examples/` the sample project and the example chapter.
