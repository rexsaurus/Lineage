"""Curated encyclopedia articles: <project>/data/wiki/<slug>.md (front matter + markdown with [^n] footnotes).

An article written this way replaces the article Lineage would otherwise derive from the material, so a person's page
reads like an encyclopedia entry: infobox, lead, sections, numbered references. The same renderer feeds the
Familypedia view and any static site built from the project (link targets are passed in by the caller).

    art = load(project_root, "Kingsley Perry")            # by the family-tree name, or None
    html = render(art, person_href, chapter_href, file_url)
"""
import html as _html
import re
from pathlib import Path

E = _html.escape


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def _front(text):
    """Tiny front-matter reader: key: value lines, and one level of indented key: value under `infobox:`."""
    meta, box = {}, []
    if not text.startswith("---"):
        return meta, box, text
    end = text.find("\n---", 3)
    head, body = text[3:end], text[end + 4:]
    cur = None
    for line in head.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^(\s*)([^:]+):\s*(.*)$", line)
        if not m:
            continue
        ind, k, v = len(m.group(1)), m.group(2).strip(), m.group(3).strip()
        v = re.sub(r"\s+#\s.*$", "", v)                       # trailing comment
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        if ind == 0:
            cur = k
            if k != "infobox":
                meta[k] = v
        elif cur == "infobox" and v:
            box.append((k, v))
    return meta, box, body.lstrip("\n")


def load(root, name):
    p = Path(root) / "data" / "wiki" / (slug(name) + ".md")
    if not p.exists():
        return None
    meta, box, body = _front(p.read_text(encoding="utf-8"))
    refs, out = {}, []
    for line in body.splitlines():
        m = re.match(r"^\[\^([^\]]+)\]:\s*(.*)$", line)
        if m:
            refs[m.group(1)] = m.group(2).strip()
        else:
            out.append(line)
    body = "\n".join(out)
    body = re.sub(r"^##\s+References\s*$", "", body, flags=re.M | re.I).rstrip()
    return {"slug": p.stem, "name": meta.get("name") or name, "short": meta.get("short") or name,
            "image": meta.get("image") or "", "image_caption": meta.get("image_caption") or "",
            "infobox": box, "body": body, "refs": refs, "path": str(p)}


def _inline(t, order, person_href, chapter_href):
    t = E(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])[_*](?![\s_*])(.+?)(?<![\s_*])[_*](?![\w*])", r"<i>\1</i>", t)
    def wl(m):
        target, label = m.group(1), m.group(2) or None
        if target.startswith("chapter:"):
            title = target[8:]
            h = chapter_href(title)
            return f'<a href="{E(h)}">{E(label or title)}</a>' if h else E(label or title)
        h = person_href(target)
        return f'<a href="{E(h)}">{E(label or target)}</a>' if h else E(label or target)
    t = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", wl, t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" rel="noopener">\1</a>', t)
    def fn(m):
        k = m.group(1)
        if k not in order:
            order.append(k)
        n = order.index(k) + 1
        return f'<sup class="wref"><a href="#ref-{n}" id="cite-{n}-{len(order)}">[{n}]</a></sup>'
    return re.sub(r"\[\^([^\]]+)\]", fn, t)


def _link_urls(t):
    t = E(t, quote=False)
    t = re.sub(r"(?<![\w*])_(?!\s)(.+?)(?<!\s)_(?!\w)", r"<i>\1</i>", t)
    return re.sub(r"(https?://[^\s<>()]+[^\s<>().,;])", r'<a href="\1" rel="noopener">\1</a>', t)


def render(art, person_href, chapter_href, file_url=None, show_image=True):
    """HTML for one article: infobox, lead, contents, sections, references."""
    order, blocks, toc = [], [], []
    para, lst = [], []

    def flush():
        if para:
            blocks.append("<p>" + _inline(" ".join(para), order, person_href, chapter_href) + "</p>")
            para.clear()
        if lst:
            blocks.append("<ul>" + "".join(f"<li>{_inline(x, order, person_href, chapter_href)}</li>" for x in lst) + "</ul>")
            lst.clear()
    for line in art["body"].splitlines():
        s = line.rstrip()
        if not s.strip():
            flush(); continue
        m = re.match(r"^(#{2,4})\s+(.*)$", s)
        if m:
            flush()
            lvl, title = len(m.group(1)), m.group(2).strip()
            sid = slug(title)
            if lvl == 2:
                toc.append((sid, title))
            blocks.append(f'<h{lvl} id="{sid}">{E(title)}</h{lvl}>')
            continue
        if s.lstrip().startswith(("- ", "* ")):
            if para:
                flush()
            lst.append(s.lstrip()[2:]); continue
        if s.startswith(">"):
            flush(); blocks.append("<blockquote>" + _inline(s.lstrip("> "), order, person_href, chapter_href) + "</blockquote>"); continue
        if lst:
            flush()
        para.append(s.strip())
    flush()
    # the lead is everything before the first section heading
    first_h = next((i for i, b in enumerate(blocks) if b.startswith("<h2")), len(blocks))
    lead, rest = blocks[:first_h], blocks[first_h:]
    rows = "".join(f'<tr><th>{E(k)}</th><td>{_inline(v, order, person_href, chapter_href)}</td></tr>' for k, v in art["infobox"])
    img = ""
    if show_image and art["image"] and file_url:
        u = file_url(art["image"])
        if u:
            img = f'<tr><td colspan="2" class="wimg"><img src="{E(u)}" alt="{E(art["name"])}" loading="lazy"><div class="wcap">{E(art["image_caption"])}</div></td></tr>'
    infobox = f'<table class="winfobox"><caption>{E(art["name"])}</caption>{img}{rows}</table>' if (rows or img) else ""
    contents = ""
    if len(toc) >= 3:
        contents = '<nav class="wtoc"><b>Contents</b><ol>' + "".join(f'<li><a href="#{sid}">{E(t)}</a></li>' for sid, t in toc) + "</ol></nav>"
    refs = ""
    if order:
        refs = '<h2 id="references">References</h2><ol class="wrefs">' + "".join(
            f'<li id="ref-{i + 1}">{_link_urls(art["refs"].get(k, "(citation missing)"))}</li>' for i, k in enumerate(order)) + "</ol>"
    return f'<div class="wiki">{infobox}{"".join(lead)}{contents}{"".join(rest)}{refs}</div>'


CSS = """.wiki{line-height:1.6}.wiki h2{font-size:1.35em;border-bottom:1px solid var(--line,#ddd);padding-bottom:.15em;margin:1.4em 0 .5em}
.wiki h3{font-size:1.1em;margin:1.1em 0 .4em}.wiki p{margin:.55em 0}
.winfobox{float:right;width:300px;max-width:100%;margin:0 0 14px 18px;border:1px solid var(--line,#ccc);background:var(--card,#F8F6F1);font-size:.86em;border-collapse:collapse}
.winfobox caption{font-weight:700;font-size:1.12em;padding:8px 6px 4px;text-align:center}
.winfobox th{text-align:left;vertical-align:top;padding:4px 8px;width:36%;font-weight:600}.winfobox td{vertical-align:top;padding:4px 8px}
.winfobox .wimg{text-align:center;padding:6px}.winfobox .wimg img{max-width:100%;height:auto;border-radius:3px}.wcap{font-size:.92em;color:var(--ink-3,#666);margin-top:4px}
.wtoc{display:inline-block;border:1px solid var(--line,#ccc);background:var(--card,#F8F6F1);padding:8px 16px;margin:10px 0;font-size:.9em}.wtoc ol{margin:.3em 0 0;padding-left:1.2em}
sup.wref{font-size:.72em;line-height:0}sup.wref a{text-decoration:none}
.wrefs{font-size:.86em}.wrefs li{margin:.3em 0;overflow-wrap:anywhere}
.wiki blockquote{margin:.8em 0;padding:.2em 1em;border-left:3px solid var(--line,#ccc);font-style:italic}
@media (max-width:640px){.winfobox{float:none;width:100%;margin:0 0 14px}}"""
