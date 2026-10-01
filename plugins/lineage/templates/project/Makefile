# This project USES Lineage; it doesn't contain it. The release it runs is pinned in lineage.lock
# and installed read-only under ~/.lineage/releases/<tag>.
#
#   make dashboard              the dashboard of the pinned release, on this project
#   make lineage-version        which Lineage this project runs
#   make update-lineage         show what the newest release would change (changelog, and
#                               which of your files it would touch). Changes nothing.
#   make update-lineage APPLY=1 install it and pin it. Your material is never touched; stories
#                               a release would alter are marked stale and listed, not rewritten.
#   TO=v0.4.0                   pick a release instead of the newest
LOCK_TAG    := $(shell python3 -c "import json;print(json.load(open('lineage.lock'))['tag'])" 2>/dev/null)
LINEAGE_BIN := $(HOME)/.lineage/releases/$(LOCK_TAG)/bin/lineage
UPDATE_ARGS := $(if $(TO),--to $(TO)) $(if $(APPLY),--apply)

.PHONY: dashboard lineage-version update-lineage
dashboard:
	@test -x "$(LINEAGE_BIN)" || { echo "Lineage $(LOCK_TAG) is not installed: make update-lineage TO=$(LOCK_TAG) APPLY=1"; exit 1; }
	@$(LINEAGE_BIN) dashboard --project .
lineage-version:
	@$(LINEAGE_BIN) version --project .
update-lineage:
	@$(LINEAGE_BIN) update --project . $(UPDATE_ARGS)
