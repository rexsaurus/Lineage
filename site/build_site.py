#!/usr/bin/env python3
"""Build the public website for Lineage into site/public/: the landing page, the README tour with its
screenshots, the docs rendered to HTML, install instructions, the sample book PDF, and a
READ-ONLY static snapshot of the dashboard running on the invented demo lineage.

    make site                       (from the Lineage repo root; runs `make sample` first)
    python site/build_site.py [--no-browser] [--with-example-chapter]

How the demo is made: the committed fixture examples/demo-lineage is copied to a scratch folder,
the real dashboard (app/server.py) is started on it with an empty temporary HOME (so no keys,
accounts or paths of whoever builds it can leak), and every GET the page makes is fetched and
stored as a static file under site/public/demo/api/ (JSON, SVG, GEDCOM), with the project files it
shows under site/public/demo/files/. A small shim (site/public/demo/demo/shim.js) answers the page's fetch()
calls from those files; anything that would write, run a job or open the terminal is refused
with a note. If Playwright is installed (it is for `make screenshots`), a headless browser then
clicks through the static demo and any request the snapshot is missing is fetched and added,
so the snapshot covers what the UI actually asks for.

Needs: the Lineage venv (make install) plus `markdown` (pip install markdown) to render the
docs. Playwright is optional. Nothing here touches the fixture or any real lineage.

The worked example chapter (examples/erasthus-burnham, docs/EXAMPLE-CHAPTER.md and the
chapter-p*.png pages) is about a real family, so it is left out unless --with-example-chapter.
"""
import argparse
import hashlib
import html
import json
import os
import posixpath
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site" / "public"
APP = ROOT / "app"
FIXTURE = ROOT / "examples" / "demo-lineage"
SAMPLE_PDF = ROOT / "examples" / "sample-project" / "output" / "book-draft.pdf"
GITHUB = "https://github.com/rexsaurus/Lineage"
GH_REF = "main"
SCRATCH_NAME = "the-calders"
PUBLIC_PROJECT_PATH = "~/lineages/the-calders"        # what the demo shows instead of a real path

# repo markdown -> site page (directory with index.html)
DOCS = [
    ("docs/HOWTO.md", "docs/howto", "How to use Lineage"),
    ("docs/FACTORY.md", "docs/factory", "The Factory"),
    ("app/README.md", "docs/dashboard", "The dashboard"),
    ("PRIVACY.md", "docs/privacy", "Privacy"),
    ("CHANGELOG.md", "docs/changelog", "Changelog"),
]
EXAMPLE_CHAPTER = ("docs/EXAMPLE-CHAPTER.md", "docs/example-chapter", "The worked example chapter")
EXAMPLE_IMAGES = re.compile(r"chapter-p\d+\.png$")


def log(*a, **k):
    print(*a, flush=True, **k)


# =========================================================================================
# page shell
# =========================================================================================
NAV = [("", "Home"), ("tour", "Tour"), ("demo", "Live demo"), ("docs", "Docs"), ("install", "Install")]


def rel(from_page, to):
    """Relative URL from a page directory ('' is the root) to a site path ('' root, 'x/' dir, 'x.pdf' file)."""
    is_dir = to == "" or to.endswith("/") or "." not in posixpath.basename(to)
    target = to.rstrip("/")
    r = posixpath.relpath(target or ".", from_page or ".")
    if is_dir:
        return "./" if r == "." else r + "/"
    return r


def page(path, title, body, desc="", active=""):
    """path: the page's directory under site/ ('' for the root)."""
    nav = "".join(
        f'<a href="{rel(path, (p + "/") if p else "")}"{" aria-current=page" if active == p else ""}>{n}</a>'
        for p, n in NAV)
    css = rel(path, "assets/site.css")
    full_title = f"{title} · Lineage" if title != "Lineage" else "Lineage: a family's own research platform"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(full_title)}</title>
<meta name="description" content="{html.escape(desc or 'Lineage turns what a family has (recordings, letters, photographs, records) into a sourced, browsable family record, and a book.')}">
<link rel="icon" href="{rel(path, 'assets/logo.svg')}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=Public+Sans:wght@400;500;600&display=swap">
<link rel="stylesheet" href="{css}">
</head>
<body>
<header class="site-top"><div class="wrap">
  <a class="brand" href="{rel(path, '')}"><img src="{rel(path, 'assets/logo.svg')}" alt="" width="26" height="26"><span>Lineage</span></a>
  <nav class="site-nav" aria-label="Site">{nav}<a href="{GITHUB}" class="gh">GitHub</a></nav>
</div></header>
<main>
{body}
</main>
<footer class="site-foot"><div class="wrap">
  <p>Lineage is open source under the MIT license. <a href="{GITHUB}">github.com/rexsaurus/Lineage</a></p>
  <p class="muted">Every family in the screenshots and the demo is invented. Your recordings, transcripts and photographs stay yours: the license does not cover them.</p>
</div></footer>
</body>
</html>
"""


SITE_CSS = r"""
:root{--paper:#F7F3EC;--paper-2:#EFE8DC;--card:#FFFDF9;--ink:#1C1A17;--ink-2:#4A453E;--ink-3:#7C756A;--line:#E2D9CA;
  --accent:#C96F4A;--accent-ink:#A4522F;--code:#F1EBE0;--serif:'Fraunces',Georgia,serif;--sans:'Public Sans',system-ui,-apple-system,sans-serif;
  --mono:'SFMono-Regular',Menlo,Consolas,monospace}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--paper:#1C1A17;--paper-2:#24211D;--card:#24211D;--ink:#F3EDE2;--ink-2:#D6CEC0;
  --ink-3:#A39B8E;--line:#3A352E;--accent:#E08A63;--accent-ink:#F0A07B;--code:#2C2823}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.6 var(--sans)}
a{color:var(--accent-ink)}
img{max-width:100%;height:auto}
.wrap{max-width:1120px;margin:0 auto;padding:0 16px}
.site-top{border-bottom:1px solid var(--line);background:var(--paper);position:sticky;top:0;z-index:5}
.site-top .wrap{display:flex;align-items:center;gap:18px;min-height:58px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:9px;text-decoration:none;color:var(--ink);font:600 21px var(--serif)}
.site-nav{display:flex;gap:4px;flex-wrap:wrap;margin-left:auto}
.site-nav a{color:var(--ink-2);text-decoration:none;padding:6px 10px;border-radius:8px;font-size:15px}
.site-nav a:hover,.site-nav a[aria-current]{background:var(--paper-2);color:var(--ink)}
.site-nav a.gh{border:1px solid var(--line)}
main{min-height:60vh}
.hero{padding:56px 0 28px}
.hero h1{font:600 clamp(32px,5vw,52px)/1.1 var(--serif);margin:0 0 16px;letter-spacing:-.01em;max-width:860px}
.hero .lede{font-size:clamp(17px,2vw,20px);color:var(--ink-2);max-width:760px;margin:0 0 24px}
.cta{display:flex;gap:10px;flex-wrap:wrap}
.btn{display:inline-block;padding:11px 18px;border-radius:10px;background:var(--accent);color:#fff;text-decoration:none;font-weight:600}
.btn.ghost{background:transparent;color:var(--ink);border:1px solid var(--line)}
.shot{border:1px solid var(--line);border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.08);display:block}
figure{margin:28px 0}
figcaption{color:var(--ink-3);font-size:14px;margin-top:8px}
section.band{padding:36px 0;border-top:1px solid var(--line)}
section.band h2{font:600 30px/1.2 var(--serif);margin:0 0 14px}
.grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(230px,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px}
.card h3{font:600 19px var(--serif);margin:0 0 6px}
.card p{margin:0;color:var(--ink-2);font-size:15px}
.muted{color:var(--ink-3)}
pre{background:var(--code);border:1px solid var(--line);border-radius:10px;padding:14px;overflow-x:auto;font:13.5px/1.5 var(--mono)}
code{font-family:var(--mono);font-size:.92em;background:var(--code);padding:1px 4px;border-radius:4px}
pre code{background:none;padding:0}
.doc{max-width:860px;padding:36px 16px 60px;margin:0 auto}
.doc h1{font:600 clamp(30px,4vw,42px)/1.15 var(--serif)}
.doc h2{font:600 27px/1.25 var(--serif);margin-top:44px;padding-top:12px;border-top:1px solid var(--line)}
.doc h3{font:600 21px/1.3 var(--serif);margin-top:30px}
.doc h4{font-size:17px;margin-top:24px}
.doc table{border-collapse:collapse;width:100%;display:block;overflow-x:auto;font-size:15px}
.doc th,.doc td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
.doc th{background:var(--paper-2)}
.doc img{border:1px solid var(--line);border-radius:10px}
.doc blockquote{margin:16px 0;padding:4px 16px;border-left:3px solid var(--accent);color:var(--ink-2)}
.doc hr{border:0;border-top:1px solid var(--line);margin:36px 0}
.doc .toc{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 18px;font-size:15px}
.doclist{list-style:none;padding:0}
.doclist li{padding:14px 0;border-bottom:1px solid var(--line)}
.doclist a{font:600 20px var(--serif)}
.note{background:var(--paper-2);border:1px solid var(--line);border-radius:10px;padding:12px 16px;font-size:15px}
.site-foot{border-top:1px solid var(--line);padding:22px 0 30px;margin-top:40px;font-size:14px}
.site-foot p{margin:4px 0}
.demo-frame{display:block;width:100%;border:0}
.doc p,.doc li,.doc td{overflow-wrap:break-word}.doc a{overflow-wrap:anywhere}
@media (max-width:640px){.hero{padding:32px 0 16px}.site-top .wrap{gap:6px;padding-top:6px;padding-bottom:6px}.site-nav{margin-left:0}
  .site-nav a{padding:5px 7px;font-size:14px}.doc{padding-top:22px}}
@media (max-width:480px){.site-nav a.gh{display:none}}
"""


# =========================================================================================
# markdown -> html, with links rewritten for the site
# =========================================================================================
def md_to_html(text):
    import markdown

    # Python-Markdown doesn't see fenced code indented under a list item; lift those blocks out
    def lift(m):
        ind = m.group(1)
        body = "\n".join(l[len(ind):] if l.startswith(ind) else l for l in m.group(3).split("\n"))
        return f"\n```{m.group(2)}\n{body}\n```\n"
    text = re.sub(r"^( +)```(\w*)\n(.*?)\n\1```[ \t]*$", lift, text, flags=re.M | re.S)
    return markdown.markdown(text, extensions=["tables", "fenced_code", "toc", "sane_lists"],
                             extension_configs={"toc": {"permalink": False}})


def rewrite_links(htm, src_repo_path, page_dir, page_map, image_dir="images"):
    """Point links at site pages where we publish the target, images at site/images, and
    everything else in the repo at GitHub."""
    base = posixpath.dirname(src_repo_path)

    def fix(m):
        attr, url = m.group(1), html.unescape(m.group(2))
        if re.match(r"^(https?:|mailto:|#|data:)", url) or not url:
            return m.group(0)
        path, _, frag = url.partition("#")
        target = posixpath.normpath(posixpath.join(base, path))
        if target in page_map:
            out = rel(page_dir, page_map[target] + "/") + (("#" + frag) if frag else "")
        elif target.startswith("docs/images/"):
            out = rel(page_dir, f"{image_dir}/{posixpath.basename(target)}")
        else:
            kind = "tree" if (ROOT / target).is_dir() else "blob"
            out = f"{GITHUB}/{kind}/{GH_REF}/{urllib.parse.quote(target)}" + (("#" + frag) if frag else "")
        return f'{attr}="{html.escape(out, quote=True)}"'

    return re.sub(r'\b(href|src)="([^"]*)"', fix, htm)


def md_section(text, start, stop):
    """The markdown from the heading line `start` up to (not including) the heading `stop`."""
    i = text.index(start)
    j = text.index(stop, i) if stop else len(text)
    return text[i:j]


def drop_subsection(text, heading):
    """Remove a ### subsection (up to the next ##/### heading or ---)."""
    i = text.find(heading)
    if i < 0:
        return text
    m = re.compile(r"^(---|##\s|###\s)", re.M).search(text, i + len(heading))
    return text[:i] + (text[m.start():] if m else "")


# =========================================================================================
# the static pages
# =========================================================================================
def build_pages(with_example):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    docs = DOCS + ([EXAMPLE_CHAPTER] if with_example else [])
    page_map = {src: dst for src, dst, _ in docs}
    page_map.update({"README.md": "", "examples/demo-lineage": "demo"})

    # assets
    (SITE / "assets").mkdir(parents=True, exist_ok=True)
    (SITE / "assets" / "site.css").write_text(SITE_CSS.strip() + "\n")
    shutil.copy(APP / "static" / "logo.svg", SITE / "assets" / "logo.svg")
    (SITE / "images").mkdir(exist_ok=True)
    for img in sorted((ROOT / "docs" / "images").glob("*.png")):
        if EXAMPLE_IMAGES.search(img.name) and not with_example:
            continue
        shutil.copy(img, SITE / "images" / img.name)
    (SITE / "sample").mkdir(exist_ok=True)
    shutil.copy(SAMPLE_PDF, SITE / "sample" / "lineage-sample-book.pdf")

    # --- landing
    def readme_md(start, stop, page_dir):
        return rewrite_links(md_to_html(md_section(readme, start, stop)), "README.md", page_dir, page_map)

    differ = readme_md("### What makes it different", "## A tour of the dashboard", "")
    differ = differ.replace("<h3", "<h2").replace("</h3>", "</h2>")
    landing = f"""
<div class="wrap">
  <section class="hero">
    <h1>A family's own research platform.</h1>
    <p class="lede">Collect what the family has, check it against the records, and keep it as a sourced,
    browsable record that outlives everyone in it. Recorded interviews, letters, scans and public records
    become a living family encyclopedia, and, at the end, a sourced book.</p>
    <div class="cta"><a class="btn" href="demo/">Open the live demo</a><a class="btn ghost" href="tour/">Take the tour</a>
      <a class="btn ghost" href="install/">Install</a><a class="btn ghost" href="{GITHUB}">GitHub</a></div>
  </section>
  <figure><a href="demo/"><img class="shot" src="images/home.png" width="1440" height="900"
    alt="The Lineage dashboard's Home tab for an invented family, the Calders"></a>
    <figcaption>Home, for an invented family (the Calders): the story of the day, a relative to fill in, and what needs a person's decision.
    <a href="demo/">Click through it yourself</a>.</figcaption></figure>
</div>
<section class="band"><div class="wrap">
  <h2>Family history lives in a dozen places at once</h2>
  <p class="lede muted" style="max-width:760px">A grandmother's memory, an aunt's shoebox of letters, a cousin's photographs, a museum
  catalogue, a ship's manifest nobody has looked at in a century. Lineage brings it into one record and keeps it honest.</p>
  <div class="grid">
    <div class="card"><h3>Everyone contributes</h3><p>Recordings, photographs, documents, letters, scans, links. Each one is ingested,
      summarized, tagged to the people and subjects in it, and indexed. Nothing is renamed or altered on disk.</p></div>
    <div class="card"><h3>Records beside the family's version</h3><p>Archives, censuses, rosters, ship registers and newspapers are
      searched, catalogued and snapshotted. Where a record and the family disagree, Lineage keeps both and says so.</p></div>
    <div class="card"><h3>A living record</h3><p>A genealogy built from evidence, a timeline, and a Familypedia with an article for every
      person, place, event, vessel and object. Every fact clicks back to the passage or record behind it.</p></div>
    <div class="card"><h3>Stories and a book, at the end</h3><p>Stories, a printed book and narration are exports of the record. They
      inherit its sourcing; anything a writer adds is held as a <em>bridge</em> until a person approves it.</p></div>
  </div>
</div></section>
<section class="band"><div class="wrap doc" style="max-width:none;padding:0">
  {differ}
</div></section>
<section class="band"><div class="wrap">
  <h2>See it on an invented family</h2>
  <div class="grid">
    <a class="card" href="demo/#familypedia/anders-calder" style="text-decoration:none;color:inherit"><img class="shot" src="images/familypedia-person.png" alt="A Familypedia article" loading="lazy">
      <h3 style="margin-top:12px">Familypedia</h3><p>The family says Anders crossed at sixteen; the manifest says seventeen. The article keeps both.</p></a>
    <a class="card" href="demo/#genealogy" style="text-decoration:none;color:inherit"><img class="shot" src="images/genealogy.png" alt="The genealogy tree" loading="lazy">
      <h3 style="margin-top:12px">Genealogy</h3><p>Every link points at the words or the record that establish it. No evidence, no line.</p></a>
    <a class="card" href="demo/#timeline" style="text-decoration:none;color:inherit"><img class="shot" src="images/timeline.png" alt="The timeline" loading="lazy">
      <h3 style="margin-top:12px">Timeline</h3><p>Every dated event, coloured by evidence tier, with a flag wherever the sources disagree.</p></a>
  </div>
  <p style="margin-top:20px"><a class="btn" href="demo/">Open the read-only demo</a> <a class="btn ghost" href="tour/">The full tour</a></p>
</div></section>
<section class="band"><div class="wrap">
  <h2>The book falls out of the record</h2>
  <p style="max-width:760px">Story units are cut from the transcripts, arranged on a chapter map, written under strict style rules
  (quotes exact, every paragraph cited), set in Typst with front matter, a timeline, a records appendix and an index, and checked for print.</p>
  <p><a class="btn ghost" href="sample/lineage-sample-book.pdf">Read the sample book (PDF, 30 pages)</a></p>
  <p class="muted">The sample book is about an invented grandmother, built by <code>make sample</code> from invented recordings.</p>
</div></section>
<section class="band"><div class="wrap">
  <h2>Try it in 60 seconds</h2>
  <pre><code>git clone {GITHUB}.git
cd Lineage
make install         # Python tools; needs typst (brew install typst)
make demo            # the dashboard, on a scratch copy of the demo lineage</code></pre>
  <p><a href="install/">Everything you need for a real lineage</a> · <a href="docs/howto/">The how-to guide</a></p>
</div></section>
"""
    write(SITE / "index.html", page("", "Lineage", landing, active=""))

    # --- tour
    tour_md = md_section(readme, "## A tour of the dashboard", "## Try it in 60 seconds")
    tour_md += md_section(readme, "## The book, and the narration", "## What you need for a real lineage")
    if not with_example:
        tour_md = drop_subsection(tour_md, "### One chapter, start to finish")
        tour_md = tour_md.replace(
            "and this chapter as `examples/erasthus-burnham/erasthus-burnham.pdf`.",
            "and a worked example chapter (see the README on GitHub).")
    tour_md = tour_md.replace("[the demo lineage](examples/demo-lineage/)", "[the demo lineage](examples/demo-lineage)")
    tour_html = rewrite_links(md_to_html(tour_md), "README.md", "tour", page_map)
    tour_html = tour_html.replace("<img ", '<img loading="lazy" ')
    tour = f"""<article class="doc">
<p class="note">Every picture here is the real dashboard on an invented family. <a href="../demo/">Open the same dashboard, read-only</a>, and click around.</p>
{tour_html}
<p><a class="btn" href="../demo/">Open the live demo</a> <a class="btn ghost" href="../install/">Install</a></p>
</article>"""
    write(SITE / "tour" / "index.html", page("tour", "Tour", tour, "A tour of the Lineage dashboard, with real screenshots.", "tour"))

    # --- install
    inst_md = md_section(readme, "## Try it in 60 seconds", "## The book, and the narration")
    inst_md += md_section(readme, "## What you need for a real lineage", "## Read next")
    inst_md += "\n## As Claude Code plugins\n\n```\n/plugin marketplace add rexsaurus/Lineage\n" \
               "/plugin install lineage@lineage     # the family record platform\n" \
               "/plugin install factory@lineage     # the generator\n```\n\n" \
               "The full setup, step by step, is in [the how-to guide](docs/HOWTO.md#1-set-up-a-lineage).\n"
    inst_md = inst_md.replace("`make demo` opens the dashboard on the Calders at http://127.0.0.1:8777.",
                              "`make demo` opens the dashboard on the Calders on your own machine.")
    inst = f'<article class="doc"><h1>Install</h1>{rewrite_links(md_to_html(inst_md), "README.md", "install", page_map)}</article>'
    write(SITE / "install" / "index.html", page("install", "Install", inst, "Install Lineage and run the demo locally.", "install"))

    # --- docs
    items = []
    for src, dst, title in docs:
        text = (ROOT / src).read_text(encoding="utf-8")
        body = rewrite_links(md_to_html(text), src, dst, page_map)
        body = body.replace("<img ", '<img loading="lazy" ')
        art = f'<article class="doc"><p class="muted"><a href="{rel(dst, "docs/")}">Docs</a> · <a href="{GITHUB}/blob/{GH_REF}/{src}">view on GitHub</a></p>{body}</article>'
        write(SITE / dst / "index.html", page(dst, title, art, f"Lineage: {title}.", "docs"))
        first = re.sub(r"[#*`\[\]]", "", next((l for l in text.splitlines()[1:] if l.strip() and not l.startswith(("#", "|", "[", "!", "<"))), ""))
        items.append(f'<li><a href="{rel("docs", dst + "/")}">{html.escape(title)}</a><br><span class="muted">{html.escape(first[:220])}</span></li>')
    readme_link = f'<li><a href="{GITHUB}#readme">The README</a><br><span class="muted">On GitHub.</span></li>'
    docs_index = f'<article class="doc"><h1>Docs</h1><ul class="doclist">{"".join(items)}{readme_link}</ul></article>'
    write(SITE / "docs" / "index.html", page("docs", "Docs", docs_index, "Lineage documentation.", "docs"))

    # --- 404
    nf = '<article class="doc"><h1>Not here</h1><p>That page doesn\'t exist. <a href="/">Back to Lineage</a>.</p></article>'
    write(SITE / "404.html", page("", "Not found", nf).replace('href="./"', 'href="/"').replace('="assets/', '="/assets/')
          .replace('="tour/', '="/tour/').replace('="demo/', '="/demo/').replace('="docs/', '="/docs/').replace('="install/', '="/install/'))


def write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


# =========================================================================================
# the read-only demo
# =========================================================================================
def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def canon(url):
    """The key a request is stored under: path + sorted query pairs, minus the session token.
    Must match canon() in shim.js."""
    u = urllib.parse.urlsplit(url)
    pairs = sorted((k, v) for k, v in urllib.parse.parse_qsl(u.query, keep_blank_values=True) if k not in ("token", "v"))
    return json.dumps([u.path, [list(p) for p in pairs]], ensure_ascii=False, separators=(",", ":"))


class Demo:
    def __init__(self, tmp):
        self.tmp = tmp
        self.home = tmp / "home"
        self.home.mkdir()
        self.proj = Path(tempfile.gettempdir()) / f"lineage-site-{os.getpid()}" / SCRATCH_NAME
        self.out = SITE / "demo"
        self.manifest = {}            # canon key -> {"f": file, "t": content type}
        self.files = set()            # project-relative files the snapshot shows
        self.scrub = []
        self.srv = None

    # ---- the scratch project and the server
    def prepare(self):
        shutil.rmtree(self.proj.parent, ignore_errors=True)
        self.proj.parent.mkdir(parents=True)
        shutil.copytree(FIXTURE, self.proj)
        sys.path.insert(0, str(APP))
        import server  # noqa: E402
        p = server.Project(self.proj)
        sj = self.proj / "data" / "sources.json"
        data = json.loads(sj.read_text())
        for row in data.values():
            row["thumb"] = server._thumbnail(p, row, self.proj / row["path"])
        sj.write_text(json.dumps(data, indent=1))
        if not (self.proj / "output" / "book-draft.pdf").exists() and SAMPLE_PDF.exists():
            # the sample book is the same invented family; the dashboard links to the draft
            (self.proj / "output").mkdir(exist_ok=True)
            shutil.copy(SAMPLE_PDF, self.proj / "output" / "book-draft.pdf")
        real = self.proj.resolve()
        for s in {str(real), str(self.proj)}:
            self.scrub += [("file://" + s, ""), (s, PUBLIC_PROJECT_PATH)]
        for s in {str(self.home.resolve()), str(self.home)}:
            self.scrub.append((s, "~"))
        self.scrub.append((str(self.tmp.resolve()), "/tmp"))
        self.scrub.append((str(ROOT), "<lineage>"))
        self.scrub.sort(key=lambda x: -len(x[0]))

    def start(self):
        port = free_port()
        env = dict(os.environ, HOME=str(self.home), LINEAGE_PORT=str(port))
        env.pop("ANTHROPIC_API_KEY", None)
        self.srv = subprocess.Popen([sys.executable, str(APP / "server.py"), "--port", str(port), "--project", str(self.proj),
                                     "--command", "true"], env=env, cwd=APP,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.base = f"http://127.0.0.1:{port}"
        for _ in range(100):
            try:
                page_ = urllib.request.urlopen(self.base + "/", timeout=1).read().decode()
                self.token = re.search(r'const TOKEN = "([^"]+)"', page_).group(1)
                return
            except Exception:
                time.sleep(0.15)
        raise SystemExit("the dashboard did not start")

    def stop(self):
        if self.srv:
            self.srv.terminate()
            self.srv.wait(timeout=10)
        shutil.rmtree(self.proj.parent, ignore_errors=True)

    def req(self, path, method="GET", body=None):
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(self.base + path, data=data, method=method,
                                   headers={"X-Lineage-Token": self.token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(r, timeout=120) as resp:
                return resp.status, resp.headers.get("Content-Type", ""), resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get("Content-Type", ""), e.read()

    def get_json(self, path):
        code, _, b = self.req(path)
        return json.loads(b) if code == 200 else None

    # ---- storing a response
    def clean(self, text):
        for a, b in self.scrub:
            text = text.replace(a, b)
        text = re.sub(r"/(?:Users|home)/[^/\"\s]+", "~", text)              # e.g. where an agent CLI is installed
        text = re.sub(r"http://127\.0\.0\.1:\d+", "http://127.0.0.1:8777", text)   # invite links: the default port
        return text

    def collect_files(self, obj):
        if isinstance(obj, dict):
            for v in obj.values():
                self.collect_files(v)
        elif isinstance(obj, list):
            for v in obj:
                self.collect_files(v)
        elif isinstance(obj, str) and 0 < len(obj) < 400 and not obj.startswith(("/", "http", "file:")) and "\n" not in obj:
            cand = obj.split("#")[0]
            try:
                p = (self.proj / cand)
                if p.is_file() and self.proj.resolve() in p.resolve().parents:
                    self.files.add(cand)
            except (OSError, ValueError):
                pass

    def store(self, path, code, ctype, body, override=None):
        key = canon(path)
        if key in self.manifest:
            return
        if code != 200 and override is None:
            log(f"  skip {path}: HTTP {code}")
            return
        ext = ".json" if "json" in ctype else ".svg" if "svg" in ctype else ".txt"
        name = hashlib.sha1(key.encode()).hexdigest()[:16] + ext
        if override is not None:
            text = json.dumps(override, ensure_ascii=False)
        else:
            text = body.decode("utf-8")
        if ext == ".json":
            obj = json.loads(text)
            self.collect_files(obj)
            text = self.clean(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
        else:
            text = self.clean(text)
        write(self.out / "api" / name, text)
        self.manifest[key] = {"f": name, "t": ctype.split(";")[0] or "application/json"}

    def fetch(self, path):
        if canon(path) in self.manifest:
            return
        code, ctype, body = self.req(path)
        self.store(path, code, ctype, body)

    # ---- the crawl
    def crawl(self):
        q = urllib.parse.quote
        for p in ["/api/bootstrap", "/api/settings", "/api/identity", "/api/crest", "/api/voices", "/api/connectors",
                  "/api/family", "/api/engine/sources", "/api/engine/approvals", "/api/engine/status",
                  "/api/engine/stories", "/api/engine/familypedia", "/api/engine/familypedia/meta",
                  "/api/engine/familypedia/map", "/api/engine/familypedia/picker?q=", "/api/engine/timeline",
                  "/api/engine/timeline.svg", "/api/engine/genealogy", "/api/engine/genealogy/review",
                  "/api/engine/genealogy.ged", "/api/engine/attention", "/api/engine/requests", "/api/engine/trash",
                  "/api/engine/episodes", "/api/engine/familypedia/catalogue?what=records",
                  "/api/engine/familypedia/catalogue?what=photos"]:
            self.fetch(p)
        # Home rotates its story and relative; find each cycle and keep every combination
        def period(param, field):
            seen = []
            for i in range(24):
                h = self.get_json(f"/api/engine/home?story={i if param == 'story' else 0}&relative={i if param == 'relative' else 0}") or {}
                v = json.dumps(h.get(field), sort_keys=True)
                if i and v == seen[0]:
                    return i
                seen.append(v)
            return 1
        ns, nr = period("story", "story"), period("relative", "relative")
        for i in range(ns):
            for j in range(nr):
                self.fetch(f"/api/engine/home?story={i}&relative={j}")
        self.meta = {"home_story": ns, "home_relative": nr}

        fp = self.get_json("/api/engine/familypedia") or {}
        for a in fp.get("articles", []):
            self.fetch("/api/engine/article?slug=" + q(a["slug"], safe=""))
            self.fetch("/api/engine/familypedia/map?focus=" + q(a["slug"], safe=""))
            self.fetch("/api/engine/tags?target=" + q("article:" + a["slug"], safe=""))
        for what, pre in (("records", "record:"), ("photos", "photo:")):
            cat = self.get_json(f"/api/engine/familypedia/catalogue?what={what}") or {}
            for it in cat.get("items", []):
                self.fetch("/api/engine/tags?target=" + q(pre + str(it["id"]), safe=""))
        src = self.get_json("/api/engine/sources") or {}
        for s in src.get("sources", []):
            self.files.add(s["id"])
            if s.get("thumb"):
                self.files.add(s["thumb"])
            self.fetch("/api/engine/source?id=" + q(s["id"], safe=""))
            if s.get("rid"):
                self.fetch("/api/engine/source/meta?rid=" + q(s["rid"], safe=""))
                self.fetch("/api/engine/tags?target=" + q("source:" + s["rid"], safe=""))
        st = self.get_json("/api/engine/stories") or {}
        for s in st.get("stories", []):
            sid = q(str(s["id"]), safe="")
            self.fetch("/api/engine/story/apparatus?id=" + sid)
            self.fetch("/api/engine/familypedia/story?id=" + sid)
            self.fetch("/api/engine/story/script?id=" + sid)
            self.render_story(str(s["id"]))
        self.files.add("output/book-draft.pdf")          # Home and Stories link to the draft book directly
        tl = self.get_json("/api/engine/timeline") or {}
        self.collect_files(tl)

    def render_story(self, sid):
        """Rendering a story is a POST + a job; the snapshot keeps the finished result under a fixed job id."""
        code, _, b = self.req("/api/engine/story/render", "POST", {"id": sid})
        job = json.loads(b).get("job") if code == 200 else None
        res = None
        for _ in range(600):
            if not job:
                break
            j = self.get_json("/api/job/" + job) or {}
            if j.get("state") == "done":
                res = j
                break
            if j.get("state") in ("error", "unknown"):
                log(f"  story {sid}: render failed: {j.get('step')}")
                break
            time.sleep(0.3)
        if res:
            res.pop("id", None)                         # the server's random job id
            self.store(f"/api/job/demo-render-{sid}", 200, "application/json", None, override=res)

    def copy_files(self):
        dest = self.out / "files"
        for rel_ in sorted(self.files):
            src = self.proj / rel_
            if src.is_file():
                # dot-folders (.thumbs, .lineage) are published without the dot: static hosts may skip them
                d = dest / "/".join(("_" + s[1:]) if s.startswith(".") else s for s in rel_.split("/"))
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src, d)

    # ---- the page itself
    def write_app(self):
        st = APP / "static"
        for sub in ("css", "js", "previews"):
            shutil.copytree(st / sub, self.out / sub, dirs_exist_ok=True)
        shutil.copy(st / "logo.svg", self.out / "logo.svg")
        # absolute paths in the app's JS become relative to demo/
        for js in (self.out / "js").glob("*.js"):
            t = js.read_text(encoding="utf-8")
            t = t.replace('"/previews/', '"previews/').replace('"/logo.svg"', '"logo.svg"')
            # a placeholder in app/static/js/sources.js uses a real family's name; the demo uses the Calders'
            t = t.replace("The farm after Homer died", "The farm after Anders died")
            if js.name == "core.js":
                for old, new in [
                    ("const fileUrl = rel => '/api/file?path='+encodeURIComponent(rel)+'&token='+encodeURIComponent(TOKEN);",
                     "const fileUrl = rel => demoFileUrl(rel);"),
                    ("const tokUrl = p => p+(p.includes('?')?'&':'?')+'token='+encodeURIComponent(TOKEN);",
                     "const tokUrl = p => demoTokUrl(p);"),
                ]:
                    if old not in t:
                        raise SystemExit(f"core.js changed; update build_site.py: {old[:40]}…")
                    t = t.replace(old, new)
            js.write_text(t, encoding="utf-8")
        idx = (st / "index.html").read_text(encoding="utf-8")
        idx = re.sub(r'\s*<link rel="stylesheet" href="https://cdn\.jsdelivr\.net[^>]*>', "", idx)
        idx = re.sub(r'\s*<script src="https://cdn\.jsdelivr\.net[^>]*></script>', "", idx)
        idx = idx.replace('"/logo.svg"', '"logo.svg"').replace('"/css/', '"css/').replace('"/js/', '"js/')
        idx = idx.replace('const TOKEN = "__LINEAGE_TOKEN__";', 'const TOKEN = "read-only-demo";')
        idx = idx.replace('<title>Lineage</title>',
                          '<title>The Calders · Lineage live demo (read-only)</title>\n'
                          '<meta name="description" content="A read-only snapshot of the Lineage dashboard on an invented family, the Calders.">\n'
                          '<script>if(!location.pathname.endsWith("/")&&!location.pathname.endsWith(".html"))location.replace(location.pathname+"/"+location.search+location.hash);</script>')
        idx = idx.replace('<link rel="stylesheet" href="css/app.css">',
                          '<link rel="stylesheet" href="css/app.css">\n<link rel="stylesheet" href="demo/demo.css">')
        idx = idx.replace('<script src="js/core.js"></script>', '<script src="demo/shim.js"></script>\n<script src="js/core.js"></script>')
        idx = idx.replace("<script>boot();</script>", '<script src="demo/after.js"></script>\n<script>boot();</script>')
        for need in ("demo/shim.js", "demo/after.js", "demo/demo.css"):
            if need not in idx:
                raise SystemExit("app/static/index.html changed; update build_site.py")
        write(self.out / "index.html", idx)
        write(self.out / "demo" / "shim.js", SHIM_JS.replace("__META__", json.dumps(self.meta)))
        write(self.out / "demo" / "after.js", AFTER_JS)
        write(self.out / "demo" / "demo.css", DEMO_CSS)

    def write_manifest(self):
        write(self.out / "api" / "manifest.json", json.dumps(self.manifest, ensure_ascii=False, sort_keys=True, indent=0))

    # ---- a browser pass over the static snapshot: whatever the UI asks for and we lack, add
    def browser_pass(self, rounds=3):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            log("  (playwright not installed: skipping the browser pass; the API crawl alone is used)")
            return None
        fp = self.get_json("/api/engine/familypedia") or {}
        st = self.get_json("/api/engine/stories") or {}
        src = self.get_json("/api/engine/sources") or {}
        routes = ["#home", "#sources", "#sources?view=gallery", "#sources?view=table", "#familypedia",
                  "#familypedia?view=map", "#familypedia?view=records", "#familypedia?view=photos",
                  "#genealogy", "#timeline", "#stories", "#/settings/family", "#/settings/connectors",
                  "#/settings/contributors", "#/settings/project"]
        routes += ["#familypedia/" + urllib.parse.quote(a["slug"]) for a in fp.get("articles", [])]
        routes += ["#familypedia?view=map&focus=" + urllib.parse.quote(a["slug"]) for a in fp.get("articles", []) if a.get("has_coords")]
        actions = [("#stories", f"document.querySelector(\"[data-read='{s['id']}']\")?.click()") for s in st.get("stories", [])]
        actions += [("#sources", f"editSource({json.dumps(s['id'])})") for s in src.get("sources", []) if s.get("rid")]
        actions += [("#sources", f"openTranscript({json.dumps(s['id'])})") for s in src.get("sources", []) if s.get("transcribed")]
        report = {}
        with serve(SITE) as base, sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(channel="chrome")
            except Exception:
                browser = pw.chromium.launch()
            for rnd in range(rounds):
                ctx = browser.new_context(viewport={"width": 1440, "height": 900})
                page_ = ctx.new_page()
                misses, outside, errors = set(), set(), []
                page_.on("request", lambda r: outside.add(r.url) if not r.url.startswith((base, "data:", "blob:", "https://fonts.googleapis.com/", "https://fonts.gstatic.com/")) else None)
                page_.on("pageerror", lambda e: errors.append(str(e)))
                page_.on("response", lambda r: r.status >= 400 and r.url.startswith(base) and misses.add("FILE " + r.url[len(base):]))
                for route in routes + [a[0] for a in actions]:
                    page_.goto(f"{base}/demo/{route}")
                    page_.wait_for_load_state("networkidle")
                    page_.wait_for_timeout(250)
                for route, js in actions:
                    page_.goto(f"{base}/demo/{route}")
                    page_.wait_for_load_state("networkidle")
                    try:
                        page_.evaluate(js)
                    except Exception as e:
                        errors.append(f"{js}: {e}")
                    page_.wait_for_timeout(600)
                    page_.wait_for_load_state("networkidle")
                for u in page_.evaluate("window.__demoMisses||[]"):
                    misses.add(u)
                ctx.close()
                added = 0
                for m in sorted(misses):
                    if m.startswith("FILE "):
                        continue
                    before = len(self.manifest)
                    self.fetch(m)
                    added += len(self.manifest) - before
                if added:
                    self.copy_files()
                    self.write_manifest()
                report = {"misses": sorted(misses), "outside": sorted(outside), "errors": errors[:20], "added": added}
                log(f"  browser pass {rnd + 1}: {len(misses)} missing, {added} added, {len(outside)} requests leaving the site, {len(errors)} page errors")
                if not added:
                    break
            browser.close()
        return report


class serve:
    """A throwaway static server for site/ on a free port."""
    def __init__(self, root):
        self.root = root

    def __enter__(self):
        port = free_port()
        handler = partial(QuietHandler, directory=str(self.root))
        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{port}"

    def __exit__(self, *a):
        self.httpd.shutdown()


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


SHIM_JS = r"""/* Lineage read-only demo: answers the dashboard's API calls from a static snapshot.
   Generated by site/build_site.py. Nothing here talks to a server: writes, jobs and the
   terminal are refused with a note. Run the real thing with `make demo`. */
(function(){
  const META = __META__;
  const realFetch = window.fetch.bind(window);
  let manifest = null;
  const loadManifest = () => manifest || (manifest = realFetch('api/manifest.json').then(r=>r.json()));
  window.__demoMisses = [];
  const READONLY = 'This is a read-only demo: nothing is saved. Run it yourself with "make demo".';
  function canon(u){
    const url = new URL(u, location.origin);
    const pairs = [...url.searchParams.entries()].filter(([k])=>k!=='token' && k!=='v')
      .sort((a,b)=> a[0]<b[0]?-1:a[0]>b[0]?1:(a[1]<b[1]?-1:a[1]>b[1]?1:0));
    return JSON.stringify([url.pathname, pairs]);
  }
  let lastNote = 0;
  function note(msg){
    const now = Date.now(); if(now-lastNote<1500) return; lastNote = now;
    if(typeof alertNote==='function') alertNote(msg);
  }
  window.demoNote = note;
  const json = (obj, status=200) => new Response(JSON.stringify(obj), {status, headers:{'Content-Type':'application/json'}});
  window.fetch = async function(input, opts={}){
    const url = typeof input==='string' ? input : input.url;
    if(!url.startsWith('/api/')) return realFetch(input, opts);
    const method = (opts.method||'GET').toUpperCase();
    let u = new URL(url, location.origin);
    if(method!=='GET'){
      if(u.pathname==='/api/engine/story/render'){
        try{ const id = JSON.parse(opts.body).id; return json({job:'demo-render-'+id}); }catch(e){}
      }
      note(READONLY);
      return json({error:READONLY, readonly:true}, 200);
    }
    if(u.pathname==='/api/engine/home'){
      const s=+(u.searchParams.get('story')||0), r=+(u.searchParams.get('relative')||0);
      u.searchParams.set('story', String(s % META.home_story)); u.searchParams.set('relative', String(r % META.home_relative));
    }
    const m = await loadManifest();
    const hit = m[canon(u.pathname+u.search)];
    if(hit) return realFetch('api/'+hit.f);
    window.__demoMisses.push(u.pathname+u.search);
    if(u.pathname==='/api/engine/familypedia/search'){
      // the full search reads every passage on the server; here, names and other names only
      const q=(u.searchParams.get('q')||'').toLowerCase(), types=u.searchParams.get('types');
      const fp=m[canon('/api/engine/familypedia')]; const all=fp ? (await (await realFetch('api/'+fp.f)).json()).articles : [];
      const hits=all.filter(a=>(!types||a.type===types) && [a.title,...(a.aliases||[])].some(n=>n.toLowerCase().includes(q)))
        .map(a=>({slug:a.slug, title:a.title, type:a.type, stub:a.stub, snippet:''}));
      note('In this demo, search matches names only. The full search runs on your own machine.');
      return json({hits});
    }
    if(/search|picker/.test(u.pathname)){ note('Search runs on your own machine in the full version ("make demo").'); return json({hits:[], items:[], results:[]}); }
    if(u.pathname.startsWith('/api/job/')) return json({state:'error', step:READONLY});
    note('Not in this read-only snapshot. Run it yourself with "make demo".');
    return json({error:'Not in the read-only demo snapshot.'}, 404);
  };
  window.demoFileUrl = rel => 'files/' + String(rel).split('/').map(s=>encodeURIComponent(s.startsWith('.')?'_'+s.slice(1):s)).join('/') + '?demo=1';
  window.demoTokUrl = p => p.startsWith('/api/') ? '#' : p;
  window.EventSource = function(){ return {addEventListener(){}, close(){}}; };
})();
"""

AFTER_JS = r"""/* Lineage read-only demo: switch off the parts that need the local server. */
(function(){
  const msg = 'The terminal runs Claude Code on your own machine. Run it yourself with "make demo".';
  window.openDock = function(open){ if(open) demoNote(msg); };
  window.sendToTerminal = function(){ demoNote(msg); };
  window.runJob = async function(stage, onStep, onDone, onError){ demoNote('Pipeline steps run on your own machine ("make demo").'); onError && onError('read-only demo'); };
  document.addEventListener('DOMContentLoaded', ()=>{
    const bar = document.createElement('div');
    bar.className = 'demo-bar';
    bar.innerHTML = '<span><b>Read-only demo</b> of an invented family, the Calders. Nothing you change is saved.</span>'
      + '<span>Run it yourself: <code>make demo</code> · <a href="../">About Lineage</a> · <a href="../install/">Install</a></span>';
    document.body.prepend(bar);
  });
})();
"""

DEMO_CSS = """/* Lineage read-only demo */
#termbtn,#tdrawer{display:none !important}
.demo-bar{display:flex;flex-wrap:wrap;gap:4px 18px;justify-content:center;align-items:center;background:#1C1A17;color:#F7F3EC;
  font:13px/1.4 'Public Sans',system-ui,sans-serif;padding:7px 14px;text-align:center}
.demo-bar a{color:#F0B08F}
.demo-bar code{background:rgba(255,255,255,.12);padding:1px 5px;border-radius:4px;color:#fff}
@media (max-width:760px){
  .top{height:auto;flex-wrap:wrap;gap:0 12px;padding:8px 12px}
  .top .proj{display:none}
  .tabs{order:3;width:100%;height:42px}
  .tabs a{padding:0 9px}
  .top h1{font-size:18px}
  .page table{display:block;overflow-x:auto;max-width:100%}
  .page pre,.page svg{max-width:100%}
}
"""


# =========================================================================================
# checks
# =========================================================================================
REAL_NAMES = re.compile(r"\bSt\.?\s?John\b|\bBurnham\b|\bKrug\b|\bHomer\b|\bPigeon\b|\bDaniel\b|\bRex\b", re.I)
# local paths, keys, real email addresses (example.org/.com are the invented ones), and anything
# that would make the page call a local server (a mention of 127.0.0.1 in the docs is fine)
LEAKS = re.compile(r"/Users/|/home/[a-z]|/private/|/var/folders|__LINEAGE_TOKEN__|"
                   r"[A-Za-z0-9._%+-]+@(?!example\.(?:org|com)\b)[A-Za-z][A-Za-z0-9-]*\.[A-Za-z]{2,}|"
                   r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{10,}|hf_(?!x+\b)[A-Za-z0-9]{10,}|"
                   r"(?:src|href|action)=[\"']?(?:https?:)?//(?:127\.0\.0\.1|localhost)|"
                   r"(?:fetch|EventSource|WebSocket)\(\s*[\"'`](?:https?|wss?)://(?:127\.0\.0\.1|localhost)")


def check_text():
    findings = {"names": [], "leaks": []}
    for f in sorted(SITE.rglob("*")):
        if not f.is_file() or f.suffix.lower() in (".png", ".jpg", ".jpeg", ".mp3", ".m4a", ".wav", ".woff2"):
            continue
        if f.suffix.lower() == ".pdf":
            try:
                text = subprocess.run(["pdftotext", str(f), "-"], capture_output=True, text=True).stdout
            except FileNotFoundError:
                continue
        else:
            text = f.read_text(encoding="utf-8", errors="replace")
        r = str(f.relative_to(SITE))
        for m in REAL_NAMES.finditer(text):
            findings["names"].append(f"{r}: …{text[max(0, m.start() - 40):m.end() + 40]!r}…")
        for m in LEAKS.finditer(text):
            findings["leaks"].append(f"{r}: …{text[max(0, m.start() - 50):m.end() + 30]!r}…")
    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--no-browser", action="store_true", help="skip the Playwright pass over the static demo")
    ap.add_argument("--with-example-chapter", action="store_true",
                    help="also publish the worked example chapter (a real family): off by default")
    a = ap.parse_args()
    if not SAMPLE_PDF.exists():
        raise SystemExit("no sample book: run `make sample` first (make site does)")
    try:
        import markdown  # noqa: F401
    except ImportError:
        raise SystemExit("pip install markdown  (in the Lineage venv) to render the docs")

    keep = set()
    if SITE.exists():
        for p in SITE.iterdir():
            if p.name not in keep:
                shutil.rmtree(p) if p.is_dir() else p.unlink()
    SITE.mkdir(parents=True, exist_ok=True)

    log("pages…")
    build_pages(a.with_example_chapter)

    log("demo: snapshotting the dashboard on the demo lineage…")
    tmp = Path(tempfile.mkdtemp(prefix="lineage-site-"))
    demo = Demo(tmp)
    report = None
    try:
        demo.prepare()
        demo.start()
        demo.crawl()
        demo.write_app()
        demo.copy_files()
        demo.write_manifest()
        log(f"  {len(demo.manifest)} API responses, {len(demo.files)} files")
        if not a.no_browser:
            report = demo.browser_pass()
    finally:
        demo.stop()
        shutil.rmtree(tmp, ignore_errors=True)

    found = check_text()
    size = sum(f.stat().st_size for f in SITE.rglob("*") if f.is_file())
    n = sum(1 for f in SITE.rglob("*") if f.is_file())
    log(f"site/public/: {n} files, {size / 1048576:.1f} MB")
    if report:
        if report["misses"]:
            log("  still missing from the snapshot (answered with a note):", *report["misses"][:30], sep="\n    ")
        if report["outside"]:
            log("  requests leaving the site:", *report["outside"][:30], sep="\n    ")
    for kind in ("names", "leaks"):
        if found[kind]:
            log(f"CHECK {kind}: {len(found[kind])}", *found[kind][:40], sep="\n  ")
    if found["leaks"] or found["names"]:
        raise SystemExit("check failed: see above")
    log("checks: no real-family names, local paths, localhost URLs, emails or keys in site/public/")


if __name__ == "__main__":
    main()
