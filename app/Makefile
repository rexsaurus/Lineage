# Lineage dashboard
#   make run        start the dashboard (http://127.0.0.1:8777)
#   make previews   render the story-template thumbnails and photo-format swatches
#                   into static/previews/ (committed, so the dashboard needs no build step)
ROOT := $(abspath ..)
PY   ?= $(ROOT)/.venv/bin/python
FONTS := $(ROOT)/plugins/lineage/fonts

.PHONY: run previews
run:
	./lineage

previews:
	@mkdir -p static/previews
	@for t in ancestor life-stage theme album; do \
	  typst compile --root $(ROOT) --font-path $(FONTS) --format png --ppi 60 --pages 1 previews/$$t.typ static/previews/tpl-$$t.png || exit 1; \
	  echo "tpl-$$t"; done
	@$(PY) previews/swatches.py
