#!/usr/bin/env python3
"""The timeline rebuilds from its inputs: a new dated fact, a star, or a photograph dated to an event shows
up on the next request, and `updatedAt` moves with it. Runs on a scratch copy of examples/demo-lineage.

    .venv/bin/python app/tests/check_timeline.py        (or: make test-timeline)
"""
import csv, json, shutil, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))
import server  # noqa: E402


def main():
    with tempfile.TemporaryDirectory() as tmp:
        proj = Path(tmp) / "demo"
        shutil.copytree(ROOT / "examples" / "demo-lineage", proj)
        p = server.Project(str(proj))
        before = server.engine_timeline(p)
        assert before["updatedAt"], "updatedAt missing"
        n = len(before["events"])

        # a new dated fact (what a scan, a claim or the Genealogist writes: a row in facts/timeline.csv)
        time.sleep(0.02)
        tl = proj / "facts" / "timeline.csv"
        rows = list(csv.DictReader(open(tl, encoding="utf-8")))
        with open(tl, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writerow({**{k: "" for k in rows[0]}, "event_id": "E999", "date_start": "1931", "date_display": "1931",
                        "precision": "year", "date_basis": "Check: a new record (R999)", "event": "A freshly added check event",
                        "people": rows[0]["people"].split(";")[0], "source": "R999", "confidence": "high"})
        after = server.engine_timeline(p)
        assert after["updatedAt"] > before["updatedAt"], ("updatedAt did not move", before["updatedAt"], after["updatedAt"])
        assert len(after["events"]) == n + 1, "the new event is not on the timeline"
        ev = next((e for e in after["events"] if e["id"] == "E999"), None)
        assert ev and ev["year"] == 1931 and ev["tier"] == "documented", ev

        # a photograph dated to that event (the Sources page writes it into data/sources.json)
        time.sleep(0.02)
        src = proj / "data" / "sources.json"
        data = json.loads(src.read_text())
        img = next((r for r in data.values() if r.get("kind") == "image" and r.get("thumb") and not r.get("trashed")), None)
        if not img:                                   # the demo has no photographs: add one, as an upload would
            img = data["check-photo"] = {"id": "check-photo", "kind": "image", "original_name": "check.jpg",
                                          "path": "sources/check.jpg", "thumb": ".thumbs/check.jpg", "stages": {}}
        if img:
            img.setdefault("mine", {})["events"] = ["E999"]
            src.write_text(json.dumps(data, indent=1))
            dated = server.engine_timeline(p)
            assert dated["updatedAt"] > after["updatedAt"], "updatedAt did not move when a photo was dated"
            assert next(e for e in dated["events"] if e["id"] == "E999")["photo"] == img["thumb"], "photo not attached"
            after = dated

        # a star
        time.sleep(0.02)
        (proj / "data" / "timeline_stars.json").write_text(json.dumps(["E999"]))
        starred = server.engine_timeline(p)
        assert starred["updatedAt"] > after["updatedAt"], "updatedAt did not move when an event was starred"
        assert next(e for e in starred["events"] if e["id"] == "E999")["starred"]
        print(f"timeline rebuilds: ok ({n} → {len(starred['events'])} events; updatedAt {before['updatedAt']} → {starred['updatedAt']}"
              f"{'; photo dating checked' if img else '; no image in the demo, photo dating skipped'})")


if __name__ == "__main__":
    main()
