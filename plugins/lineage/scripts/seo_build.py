#!/usr/bin/env python3
"""Search-engine pages for a published family site. The Lineage dashboard is a one-page app behind #hash routes,
which search engines do not index, so every story and every family member also gets a plain, fast HTML page with
its own title, description, canonical URL, Open Graph / Twitter card and schema.org JSON-LD:

    /stories/                 the stories, in book order          (schema.org Book + Chapter list)
    /stories/<slug>/          one story: summary, opening, lead picture, people in it, links to read it
    /family/                  the family, by line                  (schema.org ItemList of Person)
    /family/<slug>/           one person: relation, dates, parents/spouse/children, portrait, stories
    /sitemap.xml, /robots.txt

    python seo_build.py --project DIR <site dir>       # after the site is assembled (site/build_instance.py)

Settings (lineage.json -> settings.publish): site_url (required: without it this step is skipped), title,
subtitle, author, image (absolute URL of the default share image), app_path (where the dashboard is published,
default "/lineage/"), include_living (default false: people marked living get no page), hidden_aliases (aliases
never printed, e.g. household nicknames).

Data: data/chapters.csv; the family from data/family_tree.csv (name, father, mother, spouse, dates, living,
how_sure, evidence) and data/family_members.csv (name, relation, line, aliases) when present, else the dashboard's
genealogy; data/r2_manifest.csv for picture and PDF URLs; facts/people/*.md for prose; curated articles in
data/wiki/<slug>.md rendered with Lineage's app/wiki.py exactly as the Familypedia renders them. The Lineage app
is imported from this checkout (app/ beside plugins/), never from a fixed path.
"""
import argparse
import csv
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _project import add_project_arg, enter_project  # noqa: E402
import _publish  # noqa: E402

sys.path.insert(0, str(_publish.lineage_home() / "app"))
import server, familypedia, wiki  # noqa: E402,E401

E = html.escape
STAMP = re.compile(r"\s*\[(?:S\d+ \d{1,2}:\d{2}:\d{2}|\?[^\]]*\?|inaudible[^\]]*)\]")
CFG = {}
R2 = {}
ROOT = Path(".")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def clean(t):
    return re.sub(r"\s+", " ", STAMP.sub("", t or "")).strip()


def short(t, n=158):
    t = clean(t)
    return t if len(t) <= n else t[:n - 1].rsplit(" ", 1)[0] + "…"


def load_r2():
    m = ROOT / "data" / "r2_manifest.csv"
    out, keys = {}, {}
    for r in (csv.DictReader(open(m, encoding="utf-8")) if m.exists() else []):
        if r.get("url"):
            out[r["path"]] = (r["url"], r.get("thumb_url") or r["url"])
            keys[r.get("key", "")] = r["url"]
    return out, keys


def img_url(rel, thumb=False):
    if not rel:
        return None
    hit = R2.get(rel.lstrip("/"))
    return (hit[1] if thumb else hit[0]) if hit else None


CSS = """:root{--paper:#FBF8F2;--ink:#1C1A17;--ink2:#4A453E;--line:#E4DCCD;--accent:#A4512F}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#1A1815;--ink:#F1ECE2;--ink2:#C9C1B3;--line:#3A352E;--accent:#E0946F}}
:root[data-theme="dark"]{--paper:#1A1815;--ink:#F1ECE2;--ink2:#C9C1B3;--line:#3A352E;--accent:#E0946F}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:18px/1.6 "EB Garamond",Georgia,serif}
main{max-width:760px;margin:0 auto;padding:28px 16px 64px}a{color:var(--accent)}
nav.crumbs{font:14px/1.4 system-ui,sans-serif;color:var(--ink2);margin-bottom:18px}nav.crumbs a{color:var(--ink2)}
h1{font-size:40px;line-height:1.1;margin:.2em 0 .2em}h2{font-size:24px;margin:1.6em 0 .4em}
.kicker{font:13px/1.4 system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--ink2)}
.lede{font-size:21px;color:var(--ink2)}figure{margin:22px 0}figure img{max-width:100%;height:auto;border-radius:6px;display:block}
figcaption{font-size:15px;color:var(--ink2);margin-top:6px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}.chip{display:inline-flex;align-items:center;gap:8px;padding:3px 12px 3px 3px;border:1px solid var(--line);border-radius:999px;text-decoration:none;color:var(--ink);font:15px/1.3 system-ui,sans-serif}
.chip.noimg{padding-left:12px}.chip img{width:30px;height:30px;border-radius:50%;object-fit:cover}
ul.list{list-style:none;padding:0}ul.list li{padding:10px 0;border-bottom:1px solid var(--line)}
.cta{display:inline-block;margin:6px 10px 6px 0;padding:9px 16px;border-radius:8px;background:var(--ink);color:var(--paper);text-decoration:none;font:15px system-ui,sans-serif}
.cta.ghost{background:none;color:var(--ink);border:1px solid var(--line)}
.encyc h2{font-size:26px}
footer{clear:both;margin-top:48px;font:14px/1.5 system-ui,sans-serif;color:var(--ink2)}"""


def page(path, title, desc, body, image=None, jsonld=None, kind="article", crumbs=()):
    SITE, BOOK, SUB, AUTHOR, APP = CFG["site_url"], CFG["book"], CFG["subtitle"], CFG["author"], CFG["app_path"]
    url = SITE + path
    img = image or CFG.get("image") or ""
    ld = "".join(f'<script type="application/ld+json">{json.dumps(j, ensure_ascii=False)}</script>' for j in (jsonld or []))
    crumb_html = " › ".join([f'<a href="/">{E(BOOK)}</a>'] + [f'<a href="{E(h)}">{E(t)}</a>' for t, h in crumbs])
    bc = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement":
          [{"@type": "ListItem", "position": i + 1, "name": t, "item": SITE + h}
           for i, (t, h) in enumerate([(BOOK, "/")] + list(crumbs) + [(title, path)])]}
    og_img = f'<meta property="og:image" content="{E(img)}">' if img else ""
    tw_img = f'<meta name="twitter:image" content="{E(img)}">' if img else ""
    by = f"<p>{E(BOOK)}{': ' + E(SUB) if SUB else ''}.{' Compiled from interviews and research by ' + E(AUTHOR) + '.' if AUTHOR else ''}</p>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)} · {E(BOOK)}</title>
<meta name="description" content="{E(desc)}">
<link rel="canonical" href="{E(url)}">
<meta name="robots" content="index,follow,max-image-preview:large">
{f'<meta name="author" content="{E(AUTHOR)}">' if AUTHOR else ''}
<meta property="og:site_name" content="{E(BOOK)}"><meta property="og:type" content="{kind}">
<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{E(url)}">{og_img}
<meta name="twitter:card" content="{'summary_large_image' if img else 'summary'}"><meta name="twitter:title" content="{E(title)}">
<meta name="twitter:description" content="{E(desc)}">{tw_img}
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,600;1,400&display=swap">
<style>{CSS}{wiki.CSS}</style>{ld}<script type="application/ld+json">{json.dumps(bc, ensure_ascii=False)}</script></head>
<body><main><nav class="crumbs">{crumb_html}</nav>{body}
<footer><p><a href="/">{E(BOOK)}</a> · <a href="/stories/">The stories</a> · <a href="/family/">The family</a> · <a href="{E(APP)}">Explore in Lineage</a> · <a href="/updates/">Updates</a></p>
{by}</footer></main></body></html>
"""


def write(out, path, text):
    p = out / path.strip("/") / "index.html" if path.endswith("/") else out / path.strip("/")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def chip(href, name, pic=None):
    im = f'<img src="{E(pic)}" alt="" loading="lazy" width="30" height="30">' if pic else ""
    return f'<a class="chip{"" if pic else " noimg"}" href="{E(href)}">{im}<span>{E(name)}</span></a>'


def tidy(x):
    """Prose without citation keys, URLs or markdown."""
    x = re.sub(r"\[(?:[A-Z]{1,5}\d*(?:[ -][^\]]{0,40})?|S\d+ [0-9:]+|[a-z0-9.-]+\.[a-z]{2,}(?:/[^\]]*)?)\](?:,\s*)?", "", x)
    x = re.sub(r"\((?:[A-Z][A-Za-z ]+ \d{4}(?:; [^)]*)?)\)", "", x)
    x = re.sub(r"https?://\S+", "", x)
    x = re.sub(r"[*_`#>]", "", x)
    return clean(re.sub(r"\s+([,.;:])", r"\1", x)).strip(" ;,")


def profile_text(name, aliases):
    """(prose, record) from facts/people/<slug>.md: prose paragraphs, and the top-level bullets of its
    "## The record" / "## The public record" section."""
    d = ROOT / "facts" / "people"
    if not d.is_dir():
        return [], []
    for c in [slug(name)] + [slug(a) for a in aliases]:
        for p in sorted(d.glob("*.md")):
            if not (p.stem == c or c.startswith(p.stem) or p.stem.startswith(c)):
                continue
            text = p.read_text(encoding="utf-8")
            paras = [x.strip() for x in text.split("\n\n")]
            prose = [tidy(x) for x in paras if x and not x.startswith(("#", "|", "-", "Dates:", "<!--", "Source keys", "Timeline keys",
                     "Relationship", "Also called", "Places", "Note:")) and len(x.split()) > 12 and "\n- " not in x]
            rec = []
            m = re.search(r"^## The (?:public )?record[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
            if m:
                for b in re.split(r"\n- ", "\n" + m.group(1)):
                    b = tidy(re.sub(r"\n\s+- .*", "", b, flags=re.S).replace("\n", " "))
                    if len(b.split()) >= 5:
                        rec.append(b)
            return [x for x in prose if x][:3], rec[:14]
    return [], []


def family(P, gl):
    """[{name, parents, spouse, dates, living, how_sure, evidence}], {name: {relation, line, aliases}}."""
    members = {}
    mp = ROOT / "data" / "family_members.csv"
    if mp.exists():
        members = {r["name"]: r for r in csv.DictReader(open(mp, encoding="utf-8")) if r.get("name")}
    tp = ROOT / "data" / "family_tree.csv"
    if tp.exists():
        tree = []
        for r in csv.DictReader(open(tp, encoding="utf-8")):
            if r.get("name"):
                tree.append({"name": r["name"], "parents": [x for x in (r.get("father"), r.get("mother")) if x],
                             "spouse": r.get("spouse") or "", "dates": r.get("dates") or "",
                             "living": (r.get("living") or "").lower() == "yes", "how_sure": r.get("how_sure") or "",
                             "evidence": r.get("evidence") or ""})
        return tree, members
    byid = {p["id"]: p for p in gl["people"] if p.get("name")}
    tree = {pid: {"name": p["name"], "parents": [], "spouse": "", "dates": p.get("dates") or "", "living": bool(p.get("living")),
                  "how_sure": "", "evidence": "; ".join(e.get("cite", "") for e in p.get("evidence") or [] if e.get("cite"))}
            for pid, p in byid.items()}
    for l in gl["links"]:
        a, b = byid.get(l.get("a")), byid.get(l.get("b"))
        if not (a and b):
            continue
        if l.get("rel") == "parent":
            tree[l["b"]]["parents"].append(a["name"])
        elif l.get("rel") == "spouse":
            tree[l["a"]]["spouse"] = tree[l["a"]]["spouse"] or b["name"]
            tree[l["b"]]["spouse"] = tree[l["b"]]["spouse"] or a["name"]
    for pid, p in byid.items():
        members.setdefault(p["name"], {"aliases": "; ".join(p.get("aliases") or [])})
    return list(tree.values()), members


def main():
    global CFG, R2, ROOT
    ap = argparse.ArgumentParser(description="static SEO pages, sitemap and robots.txt for a published site")
    add_project_arg(ap)
    ap.add_argument("site", nargs="?", help="the built site folder (default: output/site/public in the project)")
    a = ap.parse_args()
    site = Path(a.site).expanduser().resolve() if a.site else None
    root = enter_project(a.project)
    ROOT = root
    cfg = _publish.settings(root)
    if not cfg["site_url"]:
        print("settings.publish.site_url is not set in lineage.json: skipping the SEO pages")
        return
    CFG = dict(cfg, book=cfg["title"] or "The family book", app_path=("/" + cfg["app_path"].strip("/") + "/") if (cfg["app_path"] or "").strip("/") else "/")
    SITE, BOOK, SUB, AUTHOR, APP = CFG["site_url"], CFG["book"], CFG["subtitle"], CFG["author"], CFG["app_path"]
    include_living = bool(cfg["include_living"])
    hidden = {x.lower() for x in cfg["hidden_aliases"] or []}
    R2, by_key = load_r2()
    book_pdf = by_key.get(f"{cfg['r2']['prefix']}/book/{cfg['slug']}.pdf")
    out = site or root / "output" / "site" / "public"
    out.mkdir(parents=True, exist_ok=True)

    P = server.Project(root)
    stories = [s for s in server.engine_stories(P) if s.get("exists")]
    cp = root / "data" / "chapters.csv"
    chapters = {r["file"]: r for r in csv.DictReader(open(cp, encoding="utf-8"))} if cp.exists() else {}
    gl = server.genealogy_graph(P)
    gpeople = {p["name"]: p for p in gl["people"] if p.get("name")}
    canon = familypedia._family_canon(P)
    tree, members = family(P, gl)
    tree = [r for r in tree if include_living or not r["living"]]
    pslug = {r["name"]: slug(r["name"]) for r in tree}
    urls = [("/", "1.0"), ("/stories/", "0.9"), ("/family/", "0.9"), (APP, "0.6"), ("/updates/", "0.5")]

    # ---------------------------------------------------------------- stories
    story_people, items = {}, []
    for n, s in enumerate(stories, 1):
        sl = slug(s["title"])
        ch = chapters.get(s.get("file"), {})
        opening = clean(server._opening(P, s, n=7))
        photo = server._lead_photo(P, s)
        pic, thumb = img_url(photo), img_url(photo, True)
        ppl = []
        try:
            subs = familypedia.story_subjects(P, s["id"])
        except Exception:
            subs = []
        for x in subs:
            if x.get("type") != "person":
                continue
            fam = familypedia.family_name_of(canon, x["title"]) or x["title"]
            if fam in pslug and fam not in ppl:
                ppl.append(fam)
                story_people.setdefault(fam, []).append((s["title"], sl))
        part = (ch.get("part") or "").split(":")[0]
        summary = clean(s.get("summary") or ch.get("summary") or "")
        desc = short(f"{s['title']} ({s.get('dates') or ''}): {summary}. {opening}" if summary else f"{s['title']}: {opening}")
        ch_pdf = by_key.get(f"{cfg['r2']['prefix']}/chapters/{Path(s.get('file') or '').stem}.pdf")
        ctas = f'<a class="cta" href="{E(APP)}#stories?read={E(s["id"])}">Read the whole story</a>'
        if ch_pdf:
            ctas += f'<a class="cta ghost" href="{E(ch_pdf)}">Download this story (PDF)</a>'
        if book_pdf:
            ctas += f'<a class="cta ghost" href="{E(book_pdf)}">Download the book (PDF)</a>'
        kick = " · ".join(x for x in [E(part), f"Chapter {n}", E(s.get("dates") or "")] if x)
        prev_ = f'<a href="/stories/{slug(stories[n - 2]["title"])}/">← {E(stories[n - 2]["title"])}</a>' if n > 1 else ""
        next_ = f'<a href="/stories/{slug(stories[n]["title"])}/">{E(stories[n]["title"])} →</a>' if n < len(stories) else ""
        body = (f'<p class="kicker">{kick}</p><h1>{E(s["title"])}</h1>'
                + (f'<p class="lede">{E(summary)}</p>' if summary else "")
                + (f'<figure><img src="{E(pic)}" alt="{E(s["title"])}" width="760"><figcaption>{E(s["title"])}, from {E(BOOK)}</figcaption></figure>' if pic else "")
                + (f"<h2>How the story opens</h2><p>{E(opening)}</p>" if opening else "")
                + f"<p>{ctas}</p>"
                + (('<h2>People in this story</h2><div class="chips">' + "".join(
                    chip(f"/family/{pslug[p]}/", p, img_url((gpeople.get(p) or {}).get("photo"), True)) for p in ppl) + "</div>") if ppl else "")
                + f"<p>{prev_}{' · ' if prev_ and next_ else ''}{next_}</p>")
        ld = {"@context": "https://schema.org", "@type": "Chapter", "name": s["title"], "position": n,
              "description": desc, "url": f"{SITE}/stories/{sl}/",
              "isPartOf": {"@type": "Book", "name": BOOK, "url": SITE + "/"},
              "about": [{"@type": "Person", "name": p, "url": f"{SITE}/family/{pslug[p]}/"} for p in ppl]}
        if AUTHOR:
            ld["author"] = {"@type": "Person", "name": AUTHOR}
        if pic:
            ld["image"] = pic
        write(out, f"/stories/{sl}/", page(f"/stories/{sl}/", s["title"], desc, body, pic, [ld], crumbs=[("The stories", "/stories/")]))
        urls.append((f"/stories/{sl}/", "0.8"))
        items.append((n, s, sl, part, summary, thumb))
    lst = "".join(f'<li>{chip(f"/stories/{sl}/", s["title"], th)} <span class="kicker">{E(part)}{" · " if part and s.get("dates") else ""}{E(s.get("dates") or "")}</span>'
                  f'{f"<br>{E(su)}" if su else ""}</li>' for n, s, sl, part, su, th in items)
    book_ld = {"@context": "https://schema.org", "@type": "Book", "name": BOOK, "url": SITE + "/", "inLanguage": "en",
               "hasPart": [{"@type": "Chapter", "name": s["title"], "position": n, "url": f"{SITE}/stories/{sl}/"} for n, s, sl, *_ in items]}
    if SUB:
        book_ld["alternativeHeadline"] = SUB
    if AUTHOR:
        book_ld["author"] = {"@type": "Person", "name": AUTHOR}
    subj = _publish.lineage_json(root).get("subject") or ""
    if subj in pslug:
        book_ld["about"] = {"@type": "Person", "name": subj, "url": f"{SITE}/family/{pslug[subj]}/"}
    summary_all = (_publish.lineage_json(root).get("settings") or {}).get("summary") or ""
    write(out, "/stories/", page("/stories/", "The stories",
                                 short(f"All {len(items)} stories of {BOOK}{': ' + SUB if SUB else ''}. {summary_all}"),
                                 f'<p class="kicker">{E(BOOK)}</p><h1>The stories</h1><p class="lede">{E(SUB) + ", in" if SUB else "In"} book order.</p><ul class="list">{lst}</ul>',
                                 jsonld=[book_ld], kind="website"))

    # ---------------------------------------------------------------- family
    kids = {}
    for r in tree:
        for p in r["parents"]:
            kids.setdefault(p, []).append(r["name"])
    stitles = {x["title"]: slug(x["title"]) for x in stories}
    lines = {}
    for r in tree:
        m = members.get(r["name"], {})
        g = gpeople.get(r["name"], {})
        sl = pslug[r["name"]]
        pic, thumb = img_url(g.get("photo")), img_url(g.get("photo"), True)
        rel = m.get("relation") or ""
        aliases = [x.strip() for x in (m.get("aliases") or "").split(";") if x.strip() and x.strip().lower() not in hidden
                   and len(x.split()) > 1 and x.strip() != r["name"]]
        lines.setdefault(m.get("line") or "", []).append((r["name"], sl, rel, r.get("dates"), thumb))
        bio, record = profile_text(r["name"], aliases)
        own = next((x for x in stories if x["title"] == r["name"] or familypedia.family_name_of(canon, x["title"]) == r["name"]), None)
        if not bio and own:
            bio = [clean(server._opening(P, own, n=5))]
        facts = []
        if g.get("article"):
            try:
                art = familypedia.article(P, g["article"])
                for tier in ("documented", "witnessed", "told", "lore"):
                    for it in art.get("tiers", {}).get(tier, []):
                        t = clean(it.get("text", ""))
                        if len(t.split()) >= 7 and t not in facts:
                            facts.append(t)
            except Exception:
                pass

        def link(x):
            return chip(f"/family/{pslug[x]}/", x, img_url((gpeople.get(x) or {}).get("photo"), True)) if x in pslug else f"<span>{E(x)}</span> "
        fam_links = []
        for label, names in [("Parents", r["parents"]), ("Spouse", [r.get("spouse")]), ("Children", kids.get(r["name"], []))]:
            names = [x for x in names if x and (x in pslug or x not in gpeople or not gpeople[x].get("living") or include_living)]
            if names:
                fam_links.append(f"<p><b>{label}:</b> " + "".join(link(x) for x in names) + "</p>")
        st = story_people.get(r["name"], [])
        dates = r.get("dates") or ""
        line = m.get("line") or ""
        first = bio[0] if bio else (record[0] if record else (facts[0] if facts else ""))
        desc = short(f"{r['name']}{', ' + dates if dates else ''}{': ' + rel if rel else ''} in {BOOK}. {first}")
        explore = f"{APP}#" + ("familypedia/" + g["article"] if g.get("article") else "genealogy?focus=" + (g.get("id") or sl))
        ctas = (f'<p><a class="cta" href="{E(explore)}">Explore in Lineage</a>'
                f'<a class="cta ghost" href="{E(APP)}#genealogy?focus={E(g.get("id") or sl)}">See the family tree</a></p>')
        kick = " · ".join(x for x in [E(line) + " line" if line else "", E(rel)] if x)
        evid = re.sub(r"\s*\((?:facts|work|data)/[^)]*\)|\S+\.md\b", "", clean(r.get("evidence") or "")).strip(" ;")
        body = ((f'<p class="kicker">{kick}</p>' if kick else "") + f'<h1>{E(r["name"])}</h1>'
                + (f'<p class="lede">{E(dates)}</p>' if dates else "")
                + (f"<p>Also known as {E(', '.join(aliases))}.</p>" if aliases else "")
                + (f'<figure><img src="{E(pic)}" alt="{E(r["name"])}" width="420"><figcaption>{E(r["name"])}{" (illustration)" if g.get("photo_illustration") else ""}</figcaption></figure>' if pic else "")
                + "".join(f"<p>{E(b)}</p>" for b in bio)
                + (("<h2>From the public record</h2><ul>" + "".join(f"<li>{E(x)}</li>" for x in record) + "</ul>") if record else "")
                + (("<h2>What the book records</h2><ul>" + "".join(f"<li>{E(x)}</li>" for x in facts[:8]) + "</ul>") if facts else "")
                + "<h2>Family</h2>" + ("".join(fam_links) or "<p>No parents, spouse or children recorded yet.</p>")
                + (('<h2>In the book</h2><div class="chips">' + "".join(chip(f"/stories/{s2}/", t) for t, s2 in st) + "</div>") if st else "")
                + ctas
                + (f'<p class="kicker">{"How sure: " + E(r["how_sure"]) if r.get("how_sure") else ""}{" · " if r.get("how_sure") and evid else ""}{E(evid)}</p>' if r.get("how_sure") or evid else ""))
        art = wiki.load(root, r["name"])
        if art:                                            # a curated article replaces the derived page, as in the Familypedia
            whtml = wiki.render(art, lambda nm: f"/family/{pslug[nm]}/" if nm in pslug else None,
                                lambda t: f"/stories/{stitles[t]}/" if t in stitles else None, file_url=lambda pth: img_url(pth))
            lead_txt = clean(re.sub(r"<[^>]+>", "", re.sub(r"<sup.*?</sup>", "", whtml.split('<table class="winfobox"')[0]
                                                           + (re.search(r"</table>(.*?)<(?:nav|h2)", whtml, re.S) or [None, ""])[1])))
            desc = short(lead_txt or desc)
            body = ((f'<p class="kicker">{kick}</p>' if kick else "") + f'<h1>{E(art["name"])}</h1>' + whtml
                    + '<h2 style="clear:both">Family</h2>' + ("".join(fam_links) or "<p>No parents, spouse or children recorded yet.</p>") + ctas)
            if art["image"] and img_url(art["image"]):
                pic = img_url(art["image"])
        ld = {"@context": "https://schema.org", "@type": "Person", "name": r["name"], "url": f"{SITE}/family/{sl}/", "description": desc}
        if aliases:
            ld["alternateName"] = aliases
        if pic:
            ld["image"] = pic
        for p in r["parents"]:
            if p in pslug:
                ld.setdefault("parent", []).append({"@type": "Person", "name": p, "url": f"{SITE}/family/{pslug[p]}/"})
        if r.get("spouse") in pslug:
            ld["spouse"] = {"@type": "Person", "name": r["spouse"], "url": f"{SITE}/family/{pslug[r['spouse']]}/"}
        if kids.get(r["name"]):
            ld["children"] = [{"@type": "Person", "name": c, "url": f"{SITE}/family/{pslug[c]}/"} for c in kids[r["name"]] if c in pslug]
        yrs = re.findall(r"\b(1[5-9]\d\d|20\d\d)\b", dates)
        if yrs and (dates[:4].isdigit() or dates.startswith(("born", "about")) or "–" in dates):
            ld["birthDate"] = yrs[0]
            if "–" in dates and len(yrs) > 1:
                ld["deathDate"] = yrs[1]
        write(out, f"/family/{sl}/", page(f"/family/{sl}/", r["name"], desc, body, pic, [ld], kind="profile", crumbs=[("The family", "/family/")]))
        urls.append((f"/family/{sl}/", "0.7"))
    secs = "".join((f"<h2>The {E(line)} line</h2>" if line else "") + '<ul class="list">' + "".join(
        f'<li>{chip(f"/family/{sl}/", n, th)} <span class="kicker">{E(rel)}{" · " if rel and d else ""}{E(d or "")}</span></li>'
        for n, sl, rel, d, th in ppl) + "</ul>" for line, ppl in lines.items())
    named = [x for x in lines if x]
    write(out, "/family/", page("/family/", "The family",
                                short(f"The family in {BOOK}" + (f" and its lines ({', '.join(named)})" if named else "")
                                      + f": {len(tree)} people, with parents, spouses, children and their stories."),
                                f'<p class="kicker">{E(BOOK)}</p><h1>The family</h1><p class="lede">Everyone in the family tree of {E(BOOK)}{", by line" if named else ""}.</p>{secs}',
                                jsonld=[{"@context": "https://schema.org", "@type": "ItemList", "name": f"The family in {BOOK}",
                                         "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": f"{SITE}/family/{pslug[r['name']]}/", "name": r["name"]}
                                                             for i, r in enumerate(tree)]}],
                                kind="website"))

    # ---------------------------------------------------------------- the dashboard page: tags + crawlable links
    li = out / APP.strip("/") / "index.html" if APP.strip("/") else None
    if li and li.exists():
        t = li.read_text(encoding="utf-8")
        if 'rel="canonical"' not in t:
            tags = (f'<link rel="canonical" href="{SITE}{APP}">\n<meta property="og:title" content="Lineage · {E(BOOK)}">'
                    f'<meta property="og:url" content="{SITE}{APP}">'
                    + (f'<meta property="og:image" content="{E(CFG["image"])}">' if CFG["image"] else "")
                    + '<meta name="twitter:card" content="summary_large_image">\n')
            t = t.replace("</head>", tags + "</head>", 1)
            nav = ("<noscript><nav><h1>" + E(BOOK) + '</h1><p><a href="/stories/">The stories</a> · <a href="/family/">The family</a></p><ul>'
                   + "".join(f'<li><a href="/stories/{sl}/">{E(s["title"])}</a></li>' for n, s, sl, *_ in items)
                   + "".join(f'<li><a href="/family/{pslug[r["name"]]}/">{E(r["name"])}</a></li>' for r in tree) + "</ul></nav></noscript>")
            t = t.replace("<body>", "<body>" + nav, 1) if "<body>" in t else re.sub(r"(<body[^>]*>)", r"\1" + nav.replace("\\", "\\\\"), t, count=1)
            li.write_text(t, encoding="utf-8")

    # ---------------------------------------------------------------- sitemap, robots
    today = date.today().isoformat()
    (out / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                     + "".join(f"  <url><loc>{E(SITE + u)}</loc><lastmod>{today}</lastmod><priority>{p}</priority></url>\n" for u, p in urls)
                                     + "</urlset>\n")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nDisallow: {APP}api/\n\nSitemap: {SITE}/sitemap.xml\n")
    print(f"SEO: {len(items)} story pages, {len(tree)} family pages, sitemap with {len(urls)} URLs -> {out}")


if __name__ == "__main__":
    main()
