#!/usr/bin/env python3
"""News posts for a published family site, their Atom feed, and the weekly-digest subscription. Used by
updates_page.py (which writes everything on each republish) and seo_build.py; run directly to check posts:

    python posts.py --project DIR                 # parse and render every post, run the privacy check, write nothing

A post is posts/<slug>.md in the project (settings.publish.posts_dir) with a front matter block:

    ---
    title: The 1927 photograph
    date: 2026-10-16
    summary: One line for the list, the feed, the digest and the share card.
    image: photos/print/kingsley-1927.jpg      # optional hero: a project path (via data/r2_manifest.csv) or a URL
    author: Rex St. John                       # optional
    slug: the-1927-photograph                  # optional: the page's address (default: the file name without a leading YYYY-MM-DD-)
    draft: true                                # optional: not published
    ---
    Markdown body. ![Caption](photos/x.jpg "Caption shown under it") ...

Project paths (no scheme, not starting with "/") in images and links resolve through data/r2_manifest.csv to the
R2 URL; a path missing from the manifest stops the build (run r2_sync.py). Site links (/stories/..., /family/...)
pass through. A paragraph made only of images becomes a gallery: a grid of thumbnails, each linking to the full
picture, captioned from the image's title. Pages go to /updates/<slug>/; the feed to /updates/feed.xml; the list
the digest reads to /updates/posts.json.
"""
import argparse
import csv
import datetime as dt
import html
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _publish  # noqa: E402

E = html.escape
PUBLISH_DIR = Path(__file__).resolve().parent.parent / "publish"     # plugins/lineage/publish: api/ and subscribe.js
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)
FONTS = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;1,400&display=swap">'

# the updates page's look (EB Garamond, rubric red, dark mode), shared by the list and every post
CSS = """  :root { --ink:#1d1a17; --paper:#f8f5ee; --rubric:#b3261e; --muted:#6b645b; --rule:#d9d2c4; }
  @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --ink:#ece6da; --paper:#171512; --rubric:#e0574d; --muted:#a59d90; --rule:#39342d; } }
  :root[data-theme="dark"] { --ink:#ece6da; --paper:#171512; --rubric:#e0574d; --muted:#a59d90; --rule:#39342d; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--paper); color:var(--ink); font:19px/1.6 "EB Garamond", Georgia, serif; overflow-wrap:break-word; }
  .wrap { max-width:760px; margin:0 auto; padding:48px 16px 64px; }
  a { color:var(--rubric); }
  img { max-width:100%; height:auto; }
  .kicker { letter-spacing:.22em; text-transform:uppercase; font-size:13px; color:var(--muted); }
  h1 { font-weight:400; color:var(--rubric); font-size:clamp(34px,5vw,48px); line-height:1.1; margin:8px 0 6px; }
  section { border-top:1px solid var(--rule); padding-top:22px; margin-top:28px; }
  h2 { font-weight:500; font-size:24px; margin:0; }
  .date { color:var(--muted); margin:2px 0 10px; font-style:italic; }
  li { margin:0 0 10px; }
  .posts { list-style:none; padding:0; margin:12px 0 0; }
  .posts li { display:flex; gap:16px; align-items:flex-start; border-top:1px solid var(--rule); padding:16px 0; margin:0; }
  .posts li img { width:120px; height:90px; object-fit:cover; border-radius:4px; flex:none; }
  .posts h3 { font-weight:500; font-size:22px; margin:0; line-height:1.25; }
  .posts p { margin:4px 0 0; }
  .posts .date { margin:2px 0 0; }
  @media (max-width:480px) { .posts li img { width:84px; height:66px; } }
  .post .hero { margin:18px 0 8px; }
  .post .hero img, .post figure img { display:block; border-radius:4px; }
  .post figure { margin:22px 0; }
  .post figcaption { color:var(--muted); font-size:16px; margin-top:6px; }
  .post .gallery { display:grid; grid-template-columns:repeat(auto-fill, minmax(150px, 1fr)); gap:12px; margin:22px 0; }
  .post .gallery figure { margin:0; }
  .post .gallery img { width:100%; aspect-ratio:4/3; object-fit:cover; }
  .post .tbl { overflow-x:auto; } .post table { border-collapse:collapse; font-size:17px; }
  .post th, .post td { border-bottom:1px solid var(--rule); padding:4px 10px 4px 0; text-align:left; vertical-align:top; }
  .post pre { overflow-x:auto; font-size:15px; } .post blockquote { margin:16px 0; padding-left:16px; border-left:3px solid var(--rule); color:var(--muted); }
  .back { margin-top:40px; }
"""


class PostError(SystemExit):
    pass


# ------------------------------------------------------------------------------------------------ parsing
def front(text):
    """(front matter dict, body). Simple `key: value` lines between --- fences; quotes stripped."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        k, _, v = line.partition(":")
        v = re.sub(r"\s+#.*$", "", v.strip()) if not v.strip().startswith(("'", '"')) else v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
            v = v[1:-1]
        meta[k.strip().lower()] = v
    return meta, text[m.end():]


def load_manifest(root):
    m = Path(root) / "data" / "r2_manifest.csv"
    out = {}
    if m.exists():
        for r in csv.DictReader(open(m, encoding="utf-8")):
            if r.get("url"):
                out[r["path"]] = (r["url"], r.get("thumb_url") or r["url"])
    return out


class Resolver:
    """Project paths -> R2 URLs. Unknown project paths are collected as errors."""

    def __init__(self, root, manifest, where):
        self.root, self.manifest, self.where, self.errors = Path(root), manifest, where, []

    def __call__(self, ref, thumb=False):
        ref = html.unescape(ref or "").strip()
        if not ref or ref.startswith(("/", "#", "?")) or SCHEME.match(ref):
            return ref                                               # site-relative, anchor, or absolute URL
        path, _, frag = ref.partition("#")
        clean = unquote(path).lstrip("./")
        cands = [clean]
        try:                                                         # also relative to posts/ ("../photos/x.jpg")
            cands.append(str((self.where / unquote(path)).resolve().relative_to(self.root.resolve())))
        except ValueError:
            pass
        for c in cands:
            if c in self.manifest:
                url, th = self.manifest[c]
                return (th if thumb else url) + (f"#{frag}" if frag else "")
        self.errors.append(ref)
        return ref


def _attrs(tag):
    return {k: html.unescape(v) for k, v in re.findall(r'([a-zA-Z_:][-\w:]*)="([^"]*)"', tag)}


def _figure(a, url, thumb=None, link=None):
    alt = E(a.get("alt", ""))
    extra = "".join(f' {k}="{E(v)}"' for k, v in a.items() if k not in ("src", "alt", "title"))
    img = f'<img src="{E(thumb or url)}" alt="{alt}" loading="lazy"{extra}>'
    if link:
        img = f'<a href="{E(link)}">{img}</a>'
    cap = f"<figcaption>{E(a['title'])}</figcaption>" if a.get("title") else ""
    return f"<figure>{img}{cap}</figure>"


def body_html(md_text, resolve):
    import markdown
    exts = ["tables", "attr_list", "sane_lists"]
    try:
        out = markdown.markdown(md_text, extensions=exts, output_format="html")
    except Exception:
        out = markdown.markdown(md_text, output_format="html")
    img_re = r"<img\b[^>]*?/?>"

    def para(m):
        inner = m.group(1)
        imgs = re.findall(img_re, inner)
        if not imgs or re.sub(img_re, "", inner).strip():
            return m.group(0)
        if len(imgs) == 1:
            a = _attrs(imgs[0])
            return _figure(a, resolve(a.get("src", "")))
        figs = []
        for t in imgs:
            a = _attrs(t)
            full = resolve(a.get("src", ""))
            figs.append(_figure(a, full, thumb=resolve(a.get("src", ""), thumb=True), link=full))
        return '<div class="gallery">' + "".join(figs) + "</div>"

    out = re.sub(r"<p>((?:\s|<br\s*/?>)*(?:<img\b[^>]*?/?>(?:\s|<br\s*/?>)*)+)</p>", para, out)

    def attr(m):                                                     # everything not yet resolved
        return f'{m.group(1)}="{E(resolve(m.group(2)))}"'
    out = re.sub(r'\b(src|href)="([^"]*)"', attr, out)
    out = re.sub(r"<table>", '<div class="tbl"><table>', out).replace("</table>", "</table></div>")
    return out


def nice(d):
    try:
        return dt.date.fromisoformat(d).strftime("%-d %B %Y")
    except Exception:
        return d


def load_posts(root, cfg):
    """Every published post, newest first: dicts with slug, title, date, summary, author, image, thumb, html."""
    root = Path(root)
    pdir = root / (cfg.get("posts_dir") or "posts")
    if not pdir.is_dir():
        return []
    manifest = load_manifest(root)
    posts, errors = [], []
    for f in sorted(pdir.glob("*.md")):
        meta, body = front(f.read_text(encoding="utf-8"))
        if str(meta.get("draft", "")).lower() in ("true", "yes", "1"):
            continue
        slug = _publish.slug(meta.get("slug") or re.sub(r"^\d{4}-\d{2}-\d{2}-", "", f.stem))
        if not meta.get("title") or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", meta.get("date", "")):
            errors.append(f"{f.name}: needs a title and a date (YYYY-MM-DD) in its front matter")
            continue
        res = Resolver(root, manifest, pdir)
        img = meta.get("image", "")
        p = {"slug": slug, "file": f.name, "title": meta["title"], "date": meta["date"], "summary": meta.get("summary", ""),
             "author": meta.get("author", ""), "image": res(img) if img else "", "thumb": res(img, thumb=True) if img else "",
             "html": body_html(body, res)}
        errors += [f"{f.name}: {e} is not in data/r2_manifest.csv (run r2_sync.py, or use a URL)" for e in dict.fromkeys(res.errors)]
        posts.append(p)
    if errors:
        raise PostError("posts: " + "\n  ".join([""] + errors))
    slugs = [p["slug"] for p in posts]
    if len(set(slugs)) != len(slugs):
        raise PostError("posts: two posts have the same slug")
    return sorted(posts, key=lambda p: (p["date"], p["slug"]), reverse=True)


# ------------------------------------------------------------------------------------------------ rendering
def abs_url(site, u):
    return f"{site}{u}" if u.startswith("/") and site else u


def subscribe_block():
    """The Subscribe form (filled in and opened by /updates/subscribe.js once the site's functions are configured)."""
    return ('<div data-lineage-subscribe><noscript><p>Follow the <a href="/updates/feed.xml">RSS feed</a> for new posts and changes.</p>'
            '</noscript></div>\n<script src="/updates/subscribe.js" defer></script>')


def feed_link(cfg):
    t = cfg["title"] or "Updates"
    return f'<link rel="alternate" type="application/atom+xml" title="{E(t)}: updates" href="/updates/feed.xml">'


def post_page(cfg, p):
    site, book = cfg["site_url"], cfg["title"] or "The book"
    url = f"{site}/updates/{p['slug']}/"
    img = abs_url(site, p["image"] or cfg.get("image") or "")
    desc = p["summary"] or f"{p['title']}: an update from {book}."
    head = (f'<link rel="canonical" href="{E(url)}">' if site else "") + (
        f'\n<meta property="og:site_name" content="{E(book)}"><meta property="og:type" content="article">'
        f'<meta property="og:title" content="{E(p["title"])}"><meta property="og:description" content="{E(desc)}">'
        + (f'<meta property="og:url" content="{E(url)}">' if site else "")
        + (f'<meta property="og:image" content="{E(img)}">' if img else "")
        + f'<meta property="article:published_time" content="{E(p["date"])}">'
        f'\n<meta name="twitter:card" content="{"summary_large_image" if img else "summary"}">'
        f'<meta name="twitter:title" content="{E(p["title"])}"><meta name="twitter:description" content="{E(desc)}">'
        + (f'<meta name="twitter:image" content="{E(img)}">' if img else ""))
    ld = {"@context": "https://schema.org", "@type": "BlogPosting", "headline": p["title"], "datePublished": p["date"],
          "description": desc, "isPartOf": {"@type": "Blog", "name": f"{book}: updates"}}
    if site:
        ld["url"] = url
    if img:
        ld["image"] = img
    if p["author"]:
        ld["author"] = {"@type": "Person", "name": p["author"]}
    hero = f'<figure class="hero"><img src="{E(p["image"])}" alt=""></figure>' if p["image"] else ""
    by = f" · {E(p['author'])}" if p["author"] else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(p['title'])} · {E(book)}</title>
<meta name="description" content="{E(desc)}">
{head}
{feed_link(cfg)}
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")}</script>
{FONTS}
<style>
{CSS}</style></head>
<body><div class="wrap post">
<p class="kicker"><a href="/">{E(book)}</a> · <a href="/updates/">Updates</a></p>
<h1>{E(p['title'])}</h1>
<p class="date">{E(nice(p['date']))}{by}</p>
{hero}
{p['html']}
{subscribe_block()}
<p class="back"><a href="/updates/">← All updates</a> · <a href="/">{E(book)}</a></p>
</div></body></html>
"""


def posts_list_html(posts):
    if not posts:
        return ""
    items = []
    for p in posts:
        th = f'<a href="/updates/{E(p["slug"])}/" tabindex="-1" aria-hidden="true"><img src="{E(p["thumb"])}" alt="" loading="lazy"></a>' if p["thumb"] else ""
        items.append(f'<li>{th}<div><h3><a href="/updates/{E(p["slug"])}/">{E(p["title"])}</a></h3>'
                     f'<p class="date">{E(nice(p["date"]))}</p>' + (f"<p>{E(p['summary'])}</p>" if p["summary"] else "") + "</div></li>")
    return '<section class="posts-sec"><h2>Posts</h2><ul class="posts">' + "".join(items) + "</ul></section>"


def _iso(d):
    return f"{d}T12:00:00Z" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d or "") else None


def _absolutize(site, h):
    return re.sub(r'\b(src|href)="(/[^"/][^"]*|/)"', lambda m: f'{m.group(1)}="{site}{m.group(2)}"', h) if site else h


def feed_xml(cfg, posts, editions):
    """Atom: posts and the book's editions (editions: dicts with id, title, date (ISO), items)."""
    site, book = cfg["site_url"], cfg["title"] or "The book"
    entries = []
    for p in posts:
        u = f"{site}/updates/{p['slug']}/"
        hero = f'<p><img src="{E(abs_url(site, p["image"]))}" alt=""></p>' if p["image"] else ""
        entries.append((_iso(p["date"]), f"""  <entry>
    <title>{E(p['title'])}</title>
    <link rel="alternate" type="text/html" href="{E(u)}"/>
    <id>{E(u)}</id>
    <published>{_iso(p['date'])}</published><updated>{_iso(p['date'])}</updated>
    {f"<author><name>{E(p['author'])}</name></author>" if p['author'] else ""}
    <summary>{E(p['summary'])}</summary>
    <content type="html">{E(hero + _absolutize(site, p['html']))}</content>
  </entry>
"""))
    for ed in editions:
        u = f"{site}/updates/#{ed['id']}"
        when = _iso(ed["date"]) or None
        if not when:
            continue
        body = "<ul>" + "".join(f"<li>{E(i)}</li>" for i in ed["items"]) + "</ul>"
        entries.append((when, f"""  <entry>
    <title>{E(book)}: {E(ed['title'])}</title>
    <link rel="alternate" type="text/html" href="{E(u)}"/>
    <id>{E(u)}</id>
    <published>{when}</published><updated>{when}</updated>
    <content type="html">{E(body)}</content>
  </entry>
"""))
    entries.sort(key=lambda e: e[0], reverse=True)
    updated = entries[0][0] if entries else dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    author = f"<author><name>{E(cfg['author'] or book)}</name></author>"
    return f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>{E(book)}: updates</title>
  <subtitle>New posts and each new edition of {E(book)}.</subtitle>
  <link rel="self" type="application/atom+xml" href="{E(site)}/updates/feed.xml"/>
  <link rel="alternate" type="text/html" href="{E(site)}/updates/"/>
  <id>{E(site)}/updates/</id>
  <updated>{updated}</updated>
  {author}
{"".join(e[1] for e in entries)}</feed>
"""


def posts_json(posts):
    return {"format": 1, "posts": [{"slug": p["slug"], "title": p["title"], "date": p["date"], "summary": p["summary"],
                                    "url": f"/updates/{p['slug']}/", "image": p["thumb"] or ""} for p in posts]}


# ------------------------------------------------------------------------------------------------ subscriptions
def install_functions(site, cfg):
    """Copy the subscription functions into <site>/api/ and the form script to <site>/updates/subscribe.js, write
    api/_lineage-config.json, and merge the weekly digest cron into <site>/vercel.json (never replacing it)."""
    site = Path(site)
    api = site / "api"
    api.mkdir(parents=True, exist_ok=True)
    written = []
    for f in sorted((PUBLISH_DIR / "api").glob("*.js")):
        shutil.copy(f, api / f.name)
        written.append(api / f.name)
    (site / "updates").mkdir(parents=True, exist_ok=True)
    shutil.copy(PUBLISH_DIR / "subscribe.js", site / "updates" / "subscribe.js")
    written.append(site / "updates" / "subscribe.js")

    vj = site / "vercel.json"
    conf = {}
    if vj.exists():
        try:
            conf = json.loads(vj.read_text(encoding="utf-8"))
        except ValueError:
            raise PostError(f"{vj} is not valid JSON: not touching it")
    slash = conf.get("trailingSlash") is True
    d = cfg.get("digest") or {}
    (api / "_lineage-config.json").write_text(json.dumps({
        "site_url": cfg["site_url"], "title": cfg["title"] or "The family book", "slug": cfg["slug"],
        "sender_line": d.get("sender_line", ""), "postal_address": d.get("postal_address", ""), "trailing_slash": slash,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    written.append(api / "_lineage-config.json")
    path = "/api/digest/" if slash else "/api/digest"
    crons = [c for c in conf.get("crons") or [] if c.get("path", "").rstrip("/") != "/api/digest"]
    if d.get("enabled", True) not in (False, "false", "no", 0):   # settings.publish.digest.enabled: false = no emails
        crons.append({"path": path, "schedule": d.get("schedule") or "0 15 * * 1"})
    conf["crons"] = crons
    hdrs = conf.setdefault("headers", [])
    if not any(h.get("source") == "/api/(.*)" for h in hdrs):
        hdrs.append({"source": "/api/(.*)", "headers": [{"key": "X-Robots-Tag", "value": "noindex"},
                                                        {"key": "Cache-Control", "value": "no-store"}]})
    if not any(h.get("source") == "/updates/feed.xml" for h in hdrs):
        hdrs.append({"source": "/updates/feed.xml", "headers": [{"key": "Content-Type", "value": "application/atom+xml; charset=utf-8"}]})
    vj.write_text(json.dumps(conf, indent=2) + "\n", encoding="utf-8")
    return written


def changelog_json(data):
    """The site changelog as /changelog.json: the same entries and lines /changelog/ shows, nothing else."""
    import site_changelog
    keep = site_changelog.still_published(data or {})
    out = []
    for e in (data or {}).get("entries") or []:
        lines = [x for x in e.get("changes") or [] if keep(x)]
        out.append({"id": e.get("id"), "date": e.get("date"), "at": e.get("at"), "version": e.get("version"), "changes": lines})
    return {"format": 1, "entries": list(reversed(out))}


# ------------------------------------------------------------------------------------------------ privacy
def leaks_pattern():
    """build_site.py's LEAKS check (local paths, localhost links, keys, real email addresses) from this checkout."""
    try:
        sys.path.insert(0, str(_publish.lineage_home() / "site"))
        import build_site as bs  # noqa: E402
        return bs.LEAKS
    except Exception as e:
        raise PostError(f"cannot load the leak check from site/build_site.py ({e}): refusing to publish")


def leak_check(paths, base=None):
    """Raise on any leak in these files; returns the number of files checked."""
    pat, hits, n = leaks_pattern(), [], 0
    for p in paths:
        p = Path(p)
        if not p.is_file():
            continue
        n += 1
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in pat.finditer(text):
            name = p.relative_to(base) if base else p
            hits.append(f"{name}: …{text[max(0, m.start() - 50):m.end() + 30]!r}…")
    if hits:
        raise PostError("privacy check failed (local paths, emails, keys or localhost links):\n  " + "\n  ".join(hits[:40]))
    return n


def main():
    from _project import add_project_arg, enter_project
    ap = argparse.ArgumentParser(description="check a project's posts (parse, resolve images, privacy check); writes nothing")
    add_project_arg(ap)
    a = ap.parse_args()
    root = enter_project(a.project)
    cfg = _publish.settings(root)
    posts = load_posts(root, cfg)
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        files = []
        for p in posts:
            f = Path(t) / f"{p['slug']}.html"
            f.write_text(post_page(cfg, p), encoding="utf-8")
            files.append(f)
        leak_check(files, Path(t))
    for p in posts:
        print(f"{p['date']}  /updates/{p['slug']}/  {p['title']}")
    print(f"{len(posts)} posts OK")


if __name__ == "__main__":
    main()
