# Lineage — turn recorded interviews with a relative into a printed book.
#
#   make install                     build tools (Python venv, checks for typst)
#   make install-transcribe          + speech recognition and diarization (large download)
#   make sample                      build the sample book and the worked example chapter
#   make new PROJECT=~/books/grandma start a new book project
#   make status PROJECT=...          where the project stands, and what to do next
#   make draft PROJECT=...           assemble chapters, check quotes against the transcript
#                                    (warning only), build output/book-draft.pdf + back index
#   make final PROJECT=...           final build: stops on any misquote or unapproved #bridge,
#                                    then runs preflight
#   make screenshots                 rebuild the invented demo lineage and capture the dashboard
#                                    into docs/images/ (needs: pip install playwright, and Chrome)
#   make demo                        the dashboard on the demo lineage (a scratch copy)
#   make clean                       remove generated files from the examples
#
# Everything runs inside the project folder; nothing here edits your recordings.

SHELL   := /bin/bash
BA      := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
VENV    := $(BA)/.venv
PY      := $(VENV)/bin/python
SKILLS  := $(BA)/plugins/lineage/skills
SAMPLE  := $(BA)/examples/sample-project
EXAMPLE := $(BA)/examples/erasthus-burnham
export LINEAGE := $(BA)
# zsh passes PROJECT=~/x through unexpanded; expand a leading ~ here.
override PROJECT := $(patsubst ~/%,$(HOME)/%,$(PROJECT))

.PHONY: install install-transcribe sample new status draft final clean check-project screenshots demo

install:
	@command -v python3 >/dev/null || { echo "python3 is required"; exit 1; }
	@test -x $(PY) || python3 -m venv $(VENV)
	@$(PY) -m pip install -q --upgrade pip
	@$(PY) -m pip install -q -r $(BA)/requirements.txt
	@command -v typst >/dev/null || { echo "typst not found. Install it: brew install typst  (or see https://github.com/typst/typst#installation)"; exit 1; }
	@command -v pdfinfo >/dev/null || echo "note: pdfinfo not found (poppler). Optional; used by preflight. brew install poppler / apt install poppler-utils"
	@echo "Lineage installed. Try: make sample"

install-transcribe: install
	@command -v ffmpeg >/dev/null || { echo "ffmpeg is required for transcription: brew install ffmpeg / apt install ffmpeg"; exit 1; }
	@$(PY) -m pip install -r $(BA)/requirements-transcribe.txt
	@echo "Transcription tools installed. You also need a Hugging Face token: see docs/HOWTO.md section 1."

# ---- the sample ----------------------------------------------------------------------
sample:
	@test -x $(PY) || { echo "run 'make install' first"; exit 1; }
	@ln -sfn ../../.claude $(SAMPLE)/.claude
	@$(MAKE) --no-print-directory draft PROJECT=$(SAMPLE)
	@mkdir -p $(EXAMPLE)/book && cp $(BA)/book/template.typ $(EXAMPLE)/book/template.typ
	@cd $(EXAMPLE) && typst compile --root . --font-path $(BA)/fonts book/main.typ erasthus-burnham.pdf
	@echo "example chapter: $(EXAMPLE)/erasthus-burnham.pdf"

# ---- a real project ------------------------------------------------------------------
new:
	@test -n "$(PROJECT)" || { echo "usage: make new PROJECT=path/to/new-book"; exit 1; }
	@bash $(BA)/plugins/lineage/scripts/new_project.sh "$(PROJECT)"

check-project:
	@test -n "$(PROJECT)" || { echo "set PROJECT=path/to/your-book"; exit 1; }
	@test -f "$(PROJECT)/book.yaml" || { echo "$(PROJECT) has no book.yaml"; exit 1; }
	@test -x $(PY) || { echo "run 'make install' first"; exit 1; }

status: check-project
	@cd "$(PROJECT)" && $(PY) $(SKILLS)/book-generator/scripts/pipeline.py status

draft: check-project
	@cd "$(PROJECT)" && \
	  $(PY) $(SKILLS)/book-generator/scripts/build_book.py sync && \
	  $(PY) $(SKILLS)/chapter-generator/scripts/assemble.py && \
	  { ! ls transcript/clean/*.md >/dev/null 2>&1 || ! ls chapters/[0-8]*.typ >/dev/null 2>&1 || \
	    $(PY) $(BA)/scripts/verify_quotes.py --transcript chapters/[0-8]*.typ || \
	    echo "WARNING: some quotations don't match the transcript (the final build will stop on this)"; } && \
	  { test ! -f facts/timeline.csv || $(PY) $(SKILLS)/timeline-organizer/scripts/timeline_tools.py appendix; } && \
	  { test ! -f data/archives.csv || $(PY) $(SKILLS)/records-archives/scripts/archives_tools.py appendix; } && \
	  $(PY) $(SKILLS)/book-generator/scripts/build_book.py front && \
	  $(PY) $(SKILLS)/book-generator/scripts/build_book.py glossary && \
	  $(PY) $(SKILLS)/book-generator/scripts/build_book.py sources && \
	  $(PY) $(SKILLS)/book-generator/scripts/build_book.py main && \
	  $(PY) $(SKILLS)/book-generator/scripts/build_book.py compile && \
	  $(PY) $(SKILLS)/chapter-index-builder/scripts/index_tools.py backindex
	@echo "draft: $(PROJECT)/output/book-draft.pdf"

final: draft
	@cd "$(PROJECT)" && { ! ls transcript/clean/*.md >/dev/null 2>&1 || \
	    $(PY) $(BA)/scripts/verify_quotes.py --transcript chapters/[0-8]*.typ; } && \
	  $(PY) $(SKILLS)/book-generator/scripts/build_book.py compile --final && \
	  $(PY) $(SKILLS)/book-layout/scripts/preflight.py output/book-final.pdf \
	    --trim $$($(PY) -c "import yaml;print(yaml.safe_load(open('book.yaml'))['print']['trim'])") \
	    --printer $$($(PY) -c "import yaml;print(yaml.safe_load(open('book.yaml'))['print'].get('printer','kdp'))") \
	    --color $$($(PY) -c "import yaml;print(yaml.safe_load(open('book.yaml'))['print'].get('color','bw'))")

screenshots: sample
	@$(PY) -c "import playwright" 2>/dev/null || $(PY) -m pip install -q playwright
	@$(PY) $(BA)/plugins/lineage/scripts/screenshots.py

demo: sample
	@$(PY) $(BA)/plugins/lineage/scripts/demo_lineage.py
	@rm -rf /tmp/lineage-demo && cp -R $(BA)/examples/demo-lineage /tmp/lineage-demo
	@echo "demo lineage copied to /tmp/lineage-demo (the fixture stays clean)"
	@$(BA)/app/lineage /tmp/lineage-demo

clean:
	@rm -rf $(SAMPLE)/output $(SAMPLE)/chapters $(SAMPLE)/book/main.typ $(SAMPLE)/book/template.typ \
	  $(SAMPLE)/book/front/title.typ $(SAMPLE)/book/front/copyright.typ $(SAMPLE)/book/front/contents.typ \
	  $(SAMPLE)/.claude $(EXAMPLE)/book/template.typ $(EXAMPLE)/erasthus-burnham.pdf
	@echo "cleaned examples"
