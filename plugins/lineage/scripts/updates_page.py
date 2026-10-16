#!/usr/bin/env python3
"""The project's CHANGELOG.md as a published site's updates page.

    python updates_page.py --project DIR <site dir>      # writes <site dir>/updates/index.html
    python updates_page.py --project DIR                 # prints the page

Run on every republish. CHANGELOG.md sections are "## <version> — <date>" headings with "- " items; HTML comments
are dropped and _text_ is set in italics. Title and canonical URL come from settings.publish (title, site_url);
the "latest edition" link is the book PDF from data/r2_manifest.csv when it has a public URL.
"""
import argparse
import csv
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _project import add_project_arg, enter_project  # noqa: E402
import _publish  # noqa: E402


def esc(t):
    return re.sub(r"_(.+?)_", r"<em>\1</em>", html.escape(t))


def latest_edition_url(cfg):
    m = Path("data/r2_manifest.csv")
    if not m.exists():
        return ""
    want = f"{cfg['r2']['prefix']}/book/{cfg['slug']}.pdf"
    for r in csv.DictReader(open(m, encoding="utf-8")):
        if r.get("key") == want and r.get("url"):
            return r["url"]
    return ""


def render(cfg):
    md = re.sub(r"<!--.*?-->", "", Path("CHANGELOG.md").read_text(encoding="utf-8"), flags=re.S)
    sections, cur = [], None
    for line in md.splitlines():
        if line.startswith("## "):
            cur = {"head": line[3:].strip(), "items": []}
            sections.append(cur)
        elif line.startswith("- ") and cur:
            cur["items"].append(line[2:].strip())
    body = []
    for s in sections:
        title, _, when = s["head"].partition(" — ")
        body.append(f'<section><h2>{esc(title)}</h2><p class="date">{esc(when)}</p><ul>'
                    + "".join(f"<li>{esc(i)}</li>" for i in s["items"]) + "</ul></section>")
    book = cfg["title"] or "The book"
    site = cfg["site_url"]
    E = html.escape
    head_links = ""
    if site:
        head_links = (f'<link rel="canonical" href="{E(site)}/updates/">\n<meta property="og:title" content="Updates · {E(book)}">'
                      f'<meta property="og:url" content="{E(site)}/updates/"><meta name="twitter:card" content="summary">\n')
    ed = latest_edition_url(cfg)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Updates · {E(book)}</title>
{head_links}<meta name="description" content="Version history of {E(book)}: what changed in each published edition.">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;1,400&display=swap">
<style>
  :root {{ --ink:#1d1a17; --paper:#f8f5ee; --rubric:#b3261e; --muted:#6b645b; --rule:#d9d2c4; }}
  @media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --ink:#ece6da; --paper:#171512; --rubric:#e0574d; --muted:#a59d90; --rule:#39342d; }} }}
  :root[data-theme="dark"] {{ --ink:#ece6da; --paper:#171512; --rubric:#e0574d; --muted:#a59d90; --rule:#39342d; }}
  body {{ margin:0; background:var(--paper); color:var(--ink); font:19px/1.6 "EB Garamond", Georgia, serif; }}
  .wrap {{ max-width:760px; margin:0 auto; padding:48px 16px 64px; }}
  a {{ color:var(--rubric); }}
  .kicker {{ letter-spacing:.22em; text-transform:uppercase; font-size:13px; color:var(--muted); }}
  h1 {{ font-weight:400; color:var(--rubric); font-size:clamp(34px,5vw,48px); margin:8px 0 6px; }}
  section {{ border-top:1px solid var(--rule); padding-top:22px; margin-top:28px; }}
  h2 {{ font-weight:500; font-size:24px; margin:0; }}
  .date {{ color:var(--muted); margin:2px 0 10px; font-style:italic; }}
  li {{ margin:0 0 10px; }}
</style></head>
<body><div class="wrap">
<p class="kicker"><a href="/">{E(book)}</a></p>
<h1>Updates</h1>
<p>What changed in each edition of the book.{f' <a href="{E(ed)}">Read the latest edition</a>.' if ed else ''} Every change to the website itself is on the <a href="/changelog/">changelog</a>.</p>
{"".join(body)}
</div></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description="render CHANGELOG.md as <site>/updates/index.html")
    add_project_arg(ap)
    ap.add_argument("site", nargs="?", help="the built site folder (omit to print the page)")
    a = ap.parse_args()
    site = Path(a.site).expanduser().resolve() if a.site else None      # relative to where it was run
    root = enter_project(a.project)
    if not Path("CHANGELOG.md").exists():
        print("no CHANGELOG.md in the project: skipping the updates page", file=sys.stderr)
        return
    cfg = _publish.settings(root)
    page = render(cfg)
    if not site:
        sys.stdout.write(page)
        return
    out = site
    (out / "updates").mkdir(parents=True, exist_ok=True)
    (out / "updates" / "index.html").write_text(page, encoding="utf-8")
    print(f"updates page: {out / 'updates' / 'index.html'}")


if __name__ == "__main__":
    main()
