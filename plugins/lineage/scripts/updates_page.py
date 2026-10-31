#!/usr/bin/env python3
"""The project's CHANGELOG.md as a published site's updates page.

    python updates_page.py --project DIR <site dir>      # writes <site dir>/updates/index.html
    python updates_page.py --project DIR                 # prints the page

Run on every republish. CHANGELOG.md sections are "## <version> — <date>" headings with "- " items; HTML comments
are dropped and _text_ is set in italics. Title and canonical URL come from settings.publish (title, site_url);
the "latest edition" link is the book PDF from data/r2_manifest.csv when it has a public URL.

With a site folder it also publishes (see posts.py):
  - the project's news posts (posts/*.md) at /updates/<slug>/, listed newest first above the edition notes;
  - /updates/feed.xml (Atom: posts and editions) and /updates/posts.json (what the weekly digest reads);
  - the Subscribe form (/updates/subscribe.js) and the site's subscription functions in api/ (subscribe, google,
    confirm, unsubscribe, digest) with a weekly cron merged into the site's vercel.json. They stay closed (503)
    until the Vercel project has every variable listed in docs/HOWTO.md; --no-subscribe leaves them out.
Every file written is run through the instance build's leak check (local paths, localhost, keys, emails); a hit
stops the build.
"""
import argparse
import csv
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _project import add_project_arg, enter_project  # noqa: E402
import _publish  # noqa: E402
import site_changelog  # noqa: E402
import posts as P  # noqa: E402


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


def editions():
    """CHANGELOG.md's sections: [{id, title, when, date (ISO or ''), items}], newest first as written."""
    if not Path("CHANGELOG.md").exists():
        return []
    md = re.sub(r"<!--.*?-->", "", Path("CHANGELOG.md").read_text(encoding="utf-8"), flags=re.S)
    sections, cur = [], None
    for line in md.splitlines():
        if line.startswith("## "):
            cur = {"head": line[3:].strip(), "items": []}
            sections.append(cur)
        elif line.startswith("- ") and cur:
            cur["items"].append(line[2:].strip())
    out = []
    for s in sections:
        title, _, when = s["head"].partition(" — ")
        iso = site_changelog.iso_from_words(when) if when else ""
        out.append({"id": _publish.slug(title) or "edition", "title": title.strip(), "when": when.strip(),
                     "date": iso if re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso or "") else "", "items": s["items"]})
    return out


def render(cfg, posts=(), subscribe=True):
    body = []
    for s in editions():
        body.append(f'<section id="{esc(s["id"])}"><h2>{esc(s["title"])}</h2><p class="date">{esc(s["when"])}</p><ul>'
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
{head_links}<meta name="description" content="News and version history of {E(book)}: posts, and what changed in each published edition.">
{P.feed_link(cfg)}
{P.FONTS}
<style>
{P.CSS}</style></head>
<body><div class="wrap">
<p class="kicker"><a href="/">{E(book)}</a></p>
<h1>Updates</h1>
<p>{'News about the book, and w' if posts else 'W'}hat changed in each edition of it.{f' <a href="{E(ed)}">Read the latest edition</a>.' if ed else ''} Every change to the website itself is on the <a href="/changelog/">changelog</a>.</p>
{P.posts_list_html(posts)}
{P.subscribe_block() if subscribe else ''}
{'<p class="kicker" style="margin-top:36px">Edition notes</p>' if posts and body else ''}
{"".join(body)}
</div></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description="render CHANGELOG.md and posts/*.md as <site>/updates/")
    add_project_arg(ap)
    ap.add_argument("site", nargs="?", help="the built site folder (omit to print the page)")
    ap.add_argument("--no-subscribe", action="store_true", help="leave out the Subscribe form and the api/ functions")
    a = ap.parse_args()
    site = Path(a.site).expanduser().resolve() if a.site else None      # relative to where it was run
    root = enter_project(a.project)
    cfg = _publish.settings(root)
    posts = P.load_posts(root, cfg)
    if not Path("CHANGELOG.md").exists():
        if not posts:
            print("no CHANGELOG.md and no posts in the project: skipping the updates page", file=sys.stderr)
            return
    page = render(cfg, posts, subscribe=not a.no_subscribe)
    if not site:
        sys.stdout.write(page)
        return
    out = site
    up = out / "updates"
    up.mkdir(parents=True, exist_ok=True)
    written = [up / "index.html"]
    (up / "index.html").write_text(page, encoding="utf-8")
    for p in posts:
        f = up / p["slug"] / "index.html"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(P.post_page(cfg, p), encoding="utf-8")
        written.append(f)
    eds = editions()
    if cfg["site_url"]:
        (up / "feed.xml").write_text(P.feed_xml(cfg, posts, eds), encoding="utf-8")
        written.append(up / "feed.xml")
    else:
        print("settings.publish.site_url is not set: no feed (Atom needs absolute links)", file=sys.stderr)
    (up / "posts.json").write_text(json.dumps(P.posts_json(posts), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    written.append(up / "posts.json")
    if not a.no_subscribe:
        written += P.install_functions(out, cfg)
    P.apply_home_subscribe(out, cfg)
    n = P.leak_check(written, out)
    print(f"updates page: {up / 'index.html'} ({len(posts)} posts, {len(eds)} editions"
          f"{', feed' if cfg['site_url'] else ''}{'' if a.no_subscribe else ', subscribe functions'}; leak check passed on {n} files)")


if __name__ == "__main__":
    main()
