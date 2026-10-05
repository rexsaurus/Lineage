#!/usr/bin/env python3
"""Chapter dossiers: the research memory of one chapter (chapter-dossier skill).

    python $LINEAGE/scripts/dossier.py new <slug> --title "Tobias Calder" [--chapter chapters/04-tobias-calder.typ]
    python $LINEAGE/scripts/dossier.py source <slug> --title "..." --url URL [--author ...] [--date ...]
                     [--local facts/records/_raw/...] [--used-for "..."] [--cited yes|no]
                     [--status found|consulted|blocked|generated] [--group "His service"]
    python $LINEAGE/scripts/dossier.py log <slug> "<stage>" "<query or URL>" "<site>" "<result>"
    python $LINEAGE/scripts/dossier.py check <slug> [chapter.typ]     # the 100% sources check
    python $LINEAGE/scripts/dossier.py records <slug> [--out FILE]   # a #records(...) block

Run from the project folder (or --project DIR). A dossier is dossiers/<slug>/:

    DOSSIER.md       the author's instructions for this chapter (dated, never deleted),
                     scope, status, decisions made and pending
    RESEARCH-LOG.md  one line per search or fetch, including blocked and empty ones
    SOURCES.csv      100% of sources found, consulted or scraped (columns below)
    EVIDENCE.md      findings: source ids, confidence, confirms / adds to / contradicts
    LEARNINGS.md     what worked and what didn't for this chapter's research

SOURCES.csv columns:
    id,title,author_or_publisher,date,url,local_path,retrieved,used_for,cited_in_chapter,status,group
`title` is the work's real title (the fact it supports goes in used_for); cited_in_chapter is
yes only when the chapter's text relies on it; `group` is the heading it prints under in
THE RECORDS (optional).

check: every URL in the chapter file (in // context: and // src: comments and in #link calls)
must be a row of SOURCES.csv, and every row with cited_in_chapter=yes must appear in the
chapter's THE RECORDS. Exit 1 on any gap.

records: writes THE RECORDS from SOURCES.csv, every cited row under its group, then
"Further sources consulted" (found or consulted, not cited) grouped by site. Generating it
keeps the list from drifting as the prose changes; paste it after the closing paragraph
(or into the chapter's apparatus unit).
"""
import argparse
import csv
import datetime
import re
import sys
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _project as P  # noqa: E402

COLS = ["id", "title", "author_or_publisher", "date", "url", "local_path", "retrieved",
        "used_for", "cited_in_chapter", "status", "group"]
TEMPLATES = Path(__file__).resolve().parent.parent / "templates" / "dossier"
URL = re.compile(r"https?://[^\s\"'<>\[\]()]+(?:\([^\s\"'<>()]*\)[^\s\"'<>\[\]()]*)*")


def ddir(slug):
    return Path("dossiers") / slug


def today():
    return datetime.date.today().isoformat()


def read_sources(slug):
    f = ddir(slug) / "SOURCES.csv"
    if not f.exists():
        return []
    with open(f, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_sources(slug, rows):
    f = ddir(slug) / "SOURCES.csv"
    with open(f, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in COLS})


def norm_url(u):
    u = u.strip().rstrip(".,;:")
    while u.count("(") < u.count(")") and u.endswith(")"):   # "(see https://x/y)" -> drop the closer
        u = u[:-1]
    return u.rstrip("/").replace("http://", "https://", 1)


def add_source(slug, **kw):
    """Append a source unless its URL is already logged; return its id."""
    rows = read_sources(slug)
    url = kw.get("url", "")
    for r in rows:
        if url and norm_url(r.get("url", "")) == norm_url(url):
            return r["id"]
    n = max([int(r["id"][1:]) for r in rows if re.fullmatch(r"S\d+", r.get("id", ""))] or [0]) + 1
    row = {k: kw.get(k, "") or "" for k in COLS}
    row["id"] = f"S{n:03d}"
    row["retrieved"] = row["retrieved"] or today()
    row["status"] = row["status"] or "found"
    row["cited_in_chapter"] = row["cited_in_chapter"] or "no"
    rows.append(row)
    write_sources(slug, rows)
    return row["id"]


def log(slug, stage, query, site, result):
    f = ddir(slug) / "RESEARCH-LOG.md"
    if not f.exists():
        f.write_text(f"# Research log\n\ndate · stage · query/URL · site · result\n\n")
    with open(f, "a", encoding="utf-8") as fh:
        fh.write(f"{today()} · {stage} · {query} · {site} · {result}\n")


def cmd_new(a):
    d = ddir(a.slug)
    if d.exists() and any(d.iterdir()):
        sys.exit(f"{d} already exists")
    d.mkdir(parents=True, exist_ok=True)
    for t in sorted(TEMPLATES.glob("*")):
        text = t.read_text().replace("{{TITLE}}", a.title or a.slug).replace("{{SLUG}}", a.slug)
        text = text.replace("{{CHAPTER}}", a.chapter or "").replace("{{DATE}}", today())
        (d / t.name).write_text(text)
    readme = Path("dossiers/README.md")
    if not readme.exists():
        readme.write_text("# Chapter dossiers\n\nOne folder per chapter; see the chapter-dossier skill.\n\n")
    with open(readme, "a", encoding="utf-8") as fh:
        fh.write(f"- `{a.slug}` — {a.title or a.slug}{' (' + a.chapter + ')' if a.chapter else ''}\n")
    print(f"dossier: {d}/ ({', '.join(sorted(p.name for p in d.iterdir()))})")


def cmd_source(a):
    sid = add_source(a.slug, title=a.title, author_or_publisher=a.author, date=a.date, url=a.url,
                     local_path=a.local, used_for=a.used_for, cited_in_chapter=a.cited,
                     status=a.status, group=a.group)
    print(sid)


def chapter_of(slug):
    f = ddir(slug) / "DOSSIER.md"
    if f.exists():
        m = re.search(r"^File:\s*(\S+)", f.read_text(), re.M)
        if m and Path(m.group(1)).exists():
            return m.group(1)
    return None


def records_text(src):
    """The text of the chapter's #records(...) call(s), or ''."""
    out, i = [], 0
    while True:
        j = src.find("#records(", i)
        if j < 0:
            return "\n".join(out)
        depth, k = 0, j + len("#records")
        while k < len(src):
            if src[k] == "(":
                depth += 1
            elif src[k] == ")":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        out.append(src[j:k + 1])
        i = k + 1


def cmd_check(a):
    chap = a.chapter or chapter_of(a.slug)
    if not chap:
        sys.exit("which chapter? give the file, or put 'File: chapters/NN-x.typ' in DOSSIER.md")
    src = Path(chap).read_text(encoding="utf-8")
    rows = read_sources(a.slug)
    logged = {norm_url(r["url"]) for r in rows if r.get("url")}
    in_chapter = OrderedDict((norm_url(u), u) for u in URL.findall(src))
    missing = [u for k, u in in_chapter.items() if k not in logged]
    rec = {norm_url(u) for u in URL.findall(records_text(src))}
    cited = [r for r in rows if r.get("cited_in_chapter", "").lower().startswith("y")]
    unlisted = [r for r in cited if r.get("url") and norm_url(r["url"]) not in rec]
    print(f"{chap}: {len(in_chapter)} URL(s) in the chapter, {len(rows)} source(s) in the dossier, "
          f"{len(cited)} cited, THE RECORDS {'present' if rec else 'MISSING'}")
    for u in missing:
        print(f"  not in SOURCES.csv: {u}")
    for r in unlisted:
        print(f"  cited but not in THE RECORDS: {r['id']} {r['title'][:70]}")
    no_url = [r for r in cited if not r.get("url")]
    for r in no_url:
        print(f"  cited with no URL (check THE RECORDS by hand): {r['id']} {r['title'][:70]}")
    bad = bool(missing or unlisted or (not rec and cited))
    print("OK: 100% of sources logged and listed" if not bad else "FAIL: sources incomplete")
    sys.exit(1 if bad else 0)


def esc(s):
    s = re.sub(r"([\\#*_$@<>\[\]`~])", r"\\\1", s or "")
    return s.replace("//", "/​/").replace(";", "\\u{3B}")


def link(r, label=None):
    label = esc(label or r["title"])
    return f'#link("{r["url"]}")[{label}]' if r.get("url") else label


def cmd_records(a):
    rows = read_sources(a.slug)
    cited = [r for r in rows if r.get("cited_in_chapter", "").lower().startswith("y")]
    groups = OrderedDict()
    for r in cited:
        groups.setdefault(r.get("group") or "Sources", []).append(r)
    items = []
    for g, rs in groups.items():
        parts = []
        for r in rs:
            who = esc(r.get("author_or_publisher", ""))
            date = esc(r.get("date", ""))
            meta = ", ".join(x for x in (who, date) if x)
            parts.append(link(r) + (f" ({meta})" if meta else ""))
        items.append(f"  [*{esc(g)}.* " + "\\u{3B} ".join(parts) + ".],")
    further = [r for r in rows if r not in cited and r.get("status", "") in ("found", "consulted")]
    if further:
        by_site = OrderedDict()
        for r in further:
            by_site.setdefault(urlparse(r.get("url", "")).netloc.replace("www.", "") or "other", []).append(r)
        parts = [f"_{esc(site)}_ ({len(rs)}): " + "\\u{3B} ".join(link(r, r["title"][:60]) for r in rs)
                 for site, rs in by_site.items()]
        items.append(f"  [*Further sources consulted* ({len(further)}, not cited above; full details in "
                     f"dossiers/{esc(a.slug)}/SOURCES.csv). " + ". ".join(parts) + ".],")
    blocked = [r for r in rows if r.get("status") == "blocked"]
    if blocked:
        items.append(f"  [*Not reached* ({len(blocked)}: a login, a bot check or the site's rules). "
                     + "\\u{3B} ".join(link(r, r["title"][:60]) for r in blocked) + ".],")
    text = "// GENERATED by dossier.py records from dossiers/%s/SOURCES.csv\n#records(\n%s\n)\n" % (a.slug, "\n".join(items))
    if a.out:
        Path(a.out).write_text(text)
        print(f"wrote {a.out}: {len(cited)} cited, {len(further)} further, {len(blocked)} not reached")
    else:
        sys.stdout.write(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    P.add_project_arg(ap)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new"); n.add_argument("slug"); n.add_argument("--title"); n.add_argument("--chapter")
    s = sub.add_parser("source"); s.add_argument("slug")
    for k in ("title", "url"):
        s.add_argument("--" + k, required=True)
    for k in ("author", "date", "local", "used-for", "group"):
        s.add_argument("--" + k, default="")
    s.add_argument("--cited", default="no", choices=["yes", "no"])
    s.add_argument("--status", default="found", choices=["found", "consulted", "blocked", "generated"])
    lg = sub.add_parser("log"); lg.add_argument("slug")
    for k in ("stage", "query", "site", "result"):
        lg.add_argument(k)
    c = sub.add_parser("check"); c.add_argument("slug"); c.add_argument("chapter", nargs="?")
    r = sub.add_parser("records"); r.add_argument("slug"); r.add_argument("--out")
    a = ap.parse_args()
    P.enter_project(a.project)
    if a.cmd != "new" and not ddir(a.slug).exists():
        sys.exit(f"no dossier {ddir(a.slug)}: dossier.py new {a.slug} --title ...")
    {"new": cmd_new, "source": cmd_source, "check": cmd_check, "records": cmd_records,
     "log": lambda a: log(a.slug, a.stage, a.query, a.site, a.result)}[a.cmd](a)


if __name__ == "__main__":
    main()
