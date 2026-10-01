#!/usr/bin/env python3
"""Capture the real dashboard, against the invented demo lineage, into docs/images/.

    make screenshots        (from the Lineage repo root)

1. builds examples/demo-lineage (scripts/demo_lineage.py), copies it to a temporary folder
   (so the dashboard's runtime files never touch the fixture) and makes the thumbnails;
2. starts the dashboard on that copy with an empty temporary HOME, so no keys, accounts or
   paths of whoever runs it can appear in a picture;
3. drives a headless browser (Playwright, the installed Chrome) at 1440x900, 2x, light theme.
Needs: pip install playwright (in the Lineage venv) and Google Chrome, or
`playwright install chromium`.
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "examples" / "demo-lineage"
OUT = ROOT / "docs" / "images"
APP = ROOT / "app"

# name, hash route, what to do before the picture, full page?
SHOTS = [
    ("home", "#home", None, False),
    ("sources", "#sources", None, False),
    ("source-drawer", "#sources", "open_source", False),
    ("familypedia-person", "#familypedia/anders-calder", None, False),
    ("familypedia-vessel", "#familypedia/s-s-ottavia", None, False),
    ("familypedia-map", "#familypedia?view=map", None, False),
    ("genealogy", "#genealogy", None, False),
    ("timeline", "#timeline", None, False),
    ("stories", "#stories", "play_story", False),
    ("story", "#stories", "read_story", False),
    ("connectors", "#/settings/connectors", None, False),
    ("contributors", "#/settings/contributors", None, False),
]


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def prepare(tmp):
    subprocess.run([sys.executable, str(ROOT / "plugins/lineage/scripts/demo_lineage.py")], check=True)
    proj = Path("/tmp/the-calders")          # a tidy path for the header in the pictures
    shutil.rmtree(proj, ignore_errors=True)
    shutil.copytree(FIXTURE, proj)
    sys.path.insert(0, str(APP))
    import server  # noqa: E402
    p = server.Project(proj)
    data = json.loads((proj / "data" / "sources.json").read_text())
    for row in data.values():
        row["thumb"] = server._thumbnail(p, row, proj / row["path"])
    (proj / "data" / "sources.json").write_text(json.dumps(data, indent=1))
    return proj


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("pip install playwright  (in the Lineage venv), then run again")
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="lineage-shots-"))
    home = tmp / "home"
    home.mkdir()
    proj = prepare(tmp)
    port = free_port()
    env = dict(os.environ, HOME=str(home), LINEAGE_PORT=str(port))
    srv = subprocess.Popen([sys.executable, str(APP / "server.py"), "--port", str(port), "--project", str(proj),
                            "--command", "bash --norc --noprofile"], env=env, cwd=APP,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}/"
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(base, timeout=1)
                break
            except Exception:
                time.sleep(0.2)
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(channel="chrome")
            except Exception:
                browser = pw.chromium.launch()
            ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2, color_scheme="light")
            page = ctx.new_page()
            for name, route, action, full in SHOTS:
                page.goto("about:blank")
                page.goto(base + route)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(700)
                if action == "open_source":
                    page.evaluate("editSource('sources/1900-ottavia-passenger-list.png')")
                    page.wait_for_selector("#ed-subj .fp-tag, #ed-subj .empty", timeout=8000)
                    page.evaluate("document.querySelector('#ed-subj').closest('details').scrollIntoView({block:'start'})")
                    page.wait_for_timeout(500)
                elif action == "play_story":
                    page.locator("[data-listen='2']").first.click()
                    page.wait_for_timeout(800)
                elif action == "read_story":
                    page.locator("[data-read='2']").first.click()
                    page.wait_for_selector("#rd-pages img", timeout=60000)
                    page.wait_for_timeout(1200)
                page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)
                print(f"docs/images/{name}.png")
            browser.close()
    finally:
        srv.terminate()
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree("/tmp/the-calders", ignore_errors=True)


if __name__ == "__main__":
    main()
