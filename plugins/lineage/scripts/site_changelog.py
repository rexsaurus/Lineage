#!/usr/bin/env python3
"""A site changelog that keeps itself: every build of a published site appends what changed since the last one.

    python site_changelog.py --project DIR [--dry-run]          # a family site: DIR/data/site_changelog.json
    python site_changelog.py --project DIR --render SITE        # ...and write SITE/changelog/index.html
    python site_changelog.py --platform [--dry-run]             # the Lineage website: site/changelog.json

You rarely run it by hand: site/build_instance.py, seo_build.py and site/build_site.py (`make site`) call
capture() before they render, so no build or deploy can skip it. Running it twice with nothing changed adds
nothing (idempotent). --dry-run prints the entry that would be added and writes nothing.

The file (JSON, one per site):

    {"format": 1, "site": "...",
     "state":   {what the last entry saw: commit, Lineage version, fingerprints of published content},
     "entries": [{"id": "2026-10-16.1", "date": "2026-10-16", "at": "<ISO time>", "version": "1.9",
                  "lineage": "v0.9.1-6-gb88d39f", "commits": {"from": sha, "to": sha, "count": n},
                  "changes": ["plain-English line", ...], "noise": n, "backfill": false}, ...]}

Entries are appended oldest first; pages show them newest first. What becomes a line:

  family site  - the book: each new "## Version X.Y — date" section of CHANGELOG.md, bullet by bullet;
               - stories (data/chapters.csv) added, removed or rewritten;
               - Familypedia articles (data/wiki/*.md, data/familypedia/) new or changed, by title, only when the
                 article is itself published: `private: true` articles never appear, nor living people's unless
                 settings.publish.include_living;
               - timeline events (facts/timeline.csv) added or changed, except events drawn from private
                 passages (spans of `private: true` units) or about living people (same rule);
               - sources indexed (data/sources.json): counted by kind, never named;
               - the Lineage core: lineage.lock version changes, and the core commits the site was built with;
               - the project's git commits since the last entry, summarised by area (file counts). Commit
                 messages are free text and may name anyone, so they are listed only when
                 settings.publish.changelog_commit_messages is true.
  Lineage site - every commit message since the last entry (they are public in the repo), new releases from
                 docs/blog/releases.csv, new blog posts, and the docs pages that changed. A message that
                 names a real family or holds a local path is withheld (build_site.py's checks).

Never invented: every line comes from git, a file's contents or a hash difference. Pure noise (lockfiles,
caches, generated manifests, build output, this file itself) is counted in "noise", never listed.

On first run the file is created with a backfill from history (the book's CHANGELOG.md versions; for the
Lineage site, docs/blog/releases.csv and the git tags) and the current state as the baseline.
"""
import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _publish  # noqa: E402

FORMAT = 1
E = html.escape

NOISE = re.compile(
    r"(^|/)(__pycache__|\.venv|venv|node_modules|\.cache|\.pytest_cache|\.mypy_cache)(/|$)|(^|/)\.DS_Store$|\.pyc$"
    r"|(^|/)(package-lock\.json|yarn\.lock|poetry\.lock|Pipfile\.lock|uv\.lock|pnpm-lock\.yaml|Cargo\.lock)$"
    r"|^output/|^site/public/|^work/cache/"
    r"|^data/(site_changelog\.json|r2_manifest\.csv|image_focus\.json|search_index\.json|stale_stories\.json|story_states\.json)$"
    r"|^site/changelog\.json$")

AREAS = [  # family project: path prefix -> what readers would call it
    (r"^(chapters|pilot)/", "chapter files"),
    (r"^data/(wiki|familypedia)/", "Familypedia files"),
    (r"^facts/timeline", "timeline files"),
    (r"^(facts|dossiers|knowledge)/", "research and records files"),
    (r"^sources/|^data/sources\.json$", "source files"),
    (r"^photos/", "photo files"),
    (r"^content/", "story-unit files"),
    (r"^transcript/", "transcript files"),
    (r"^(site|assets)/", "site page files"),
    (r"^(book|scripts|Makefile|book\.yaml|lineage\.json)", "build and layout files"),
    (r"^lineage\.lock$", "Lineage lock file"),
    (r"^(CHANGELOG\.md|VERSION)$", "edition notes files"),
    (r"^data/", "data files"),
]


# ------------------------------------------------------------------------------------------------ helpers
def git(cwd, *args):
    try:
        r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def head(cwd):
    return git(cwd, "rev-parse", "HEAD")


def has_commit(cwd, sha):
    return bool(sha) and git(cwd, "cat-file", "-e", sha + "^{commit}") is not None


def commits(cwd, a, b):
    """[(sha, subject)] in a..b, oldest first, no merges. a may be None (then nothing)."""
    if not a or not b or a == b or not has_commit(cwd, a):
        return []
    out = git(cwd, "log", "--no-merges", "--reverse", "--format=%H%x09%s", f"{a}..{b}") or ""
    return [tuple(l.split("\t", 1)) for l in out.splitlines() if "\t" in l]


def changed_files(cwd, a, b):
    if not a or not b or a == b or not has_commit(cwd, a):
        return []
    out = git(cwd, "diff", "--name-only", a, b) or ""
    return [l for l in out.splitlines() if l]


def commit_files(cwd, c):
    return [l for l in (git(cwd, "show", "--name-only", "--format=", c) or "").splitlines() if l]


def sha(text):
    return hashlib.sha256(text.encode("utf-8", "ignore") if isinstance(text, str) else text).hexdigest()[:16]


def fsha(p):
    try:
        return sha(Path(p).read_bytes())
    except OSError:
        return ""


def nice(d):
    try:
        return dt.date.fromisoformat(d).strftime("%-d %B %Y")
    except Exception:
        return d


def iso_from_words(s):
    """'15 October 2026' -> '2026-10-15' (or s unchanged)."""
    for fmt in ("%d %B %Y", "%B %d, %Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return s.strip()


def plural(n, word):
    return f"{n} {word}" if n != 1 else f"1 {word[:-1] if word.endswith('s') else word}"


def load(path):
    p = Path(path)
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict) and "entries" in d:
                return d
        except ValueError:
            pass
    return None


def save(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def new_entry(data, version, lineage, frm, to, n_commits, changes, noise, now=None, backfill=False, date=None):
    now = now or dt.datetime.now().astimezone()
    day = date or now.date().isoformat()
    same = sum(1 for e in data["entries"] if e.get("date") == day)
    return {"id": f"{day}.{same + 1}", "date": day, "at": now.isoformat(timespec="seconds"), "version": version,
            "lineage": lineage, "commits": {"from": frm, "to": to, "count": n_commits},
            "changes": changes, "noise": noise, "backfill": backfill}


def lineage_build():
    """The Lineage checkout these tools run from: (describe, commit)."""
    home = _publish.lineage_home()
    return (git(home, "describe", "--tags", "--always") or ""), (head(home) or "")


# ------------------------------------------------------------------------------------------------ family site
def _front(text):
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    meta = {}
    for line in (m.group(1).splitlines() if m else []):
        k, _, v = line.partition(":")
        if k and not k.startswith(" "):
            meta[k.strip()] = v.strip().strip("\"'")
    return meta


PRIVATE_FM = re.compile(r"^---\n(?:.*\n)*?private:\s*(?:true|yes)\s*\n(?:.*\n)*?---", re.I)


def _secs(ts):
    h, m, s = (int(x) for x in ts.split(":"))
    return h * 3600 + m * 60 + s


def private_spans(root):
    out = {}
    for p in root.glob("content/units/*.md"):
        t = p.read_text(encoding="utf-8", errors="ignore")
        if PRIVATE_FM.match(t):
            for sid, a, b in re.findall(r"(S\d+) (\d\d:\d\d:\d\d)-(\d\d:\d\d:\d\d)", t.split("\n---", 1)[0]):
                out.setdefault(sid, []).append((_secs(a), _secs(b)))
    return out


def living_people(root):
    names = set()
    ft = root / "data" / "family_tree.csv"
    for r in (csv.DictReader(open(ft, encoding="utf-8")) if ft.exists() else []):
        if (r.get("living") or "").strip().lower() == "yes" and r.get("name"):
            names.add(r["name"].strip())

    def walk(x):
        if isinstance(x, dict):
            if x.get("living") is True and x.get("name"):
                names.add(str(x["name"]).strip())
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    for g in (root / "data" / "genealogy").glob("*.json"):
        try:
            walk(json.loads(g.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return names


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def instance_content(root, include_living):
    """Fingerprints of what the published site shows, published items only: {kind: {key: [label, hash]}}."""
    living = set() if include_living else living_people(root)
    living_slugs = {slugify(n) for n in living}
    c = {"stories": {}, "articles": {}, "events": {}, "sources": {}, "book": {}}
    # stories
    cp, cj = root / "data" / "chapters.csv", root / "data" / "chapters.json"
    rows = []
    if cp.exists():
        rows = [(r.get("file", ""), r.get("title", "")) for r in csv.DictReader(open(cp, encoding="utf-8"))]
    elif cj.exists():
        rows = [(f"chapters/{int(x['n']):02d}-{slugify(x['title'])}.md", x["title"]) for x in json.loads(cj.read_text())]
    for f, t in rows:
        if t and f and (root / f).is_file():
            c["stories"][f] = [t, fsha(root / f)]
    # Familypedia: curated articles, subject articles, and the author's edits to derived articles
    tree_names = {slugify(n): n for n in _tree_names(root)}
    for p in sorted((root / "data" / "wiki").glob("*.md")):
        t = p.read_text(encoding="utf-8", errors="ignore")
        if PRIVATE_FM.match(t):
            continue
        name = _front(t).get("name") or tree_names.get(p.stem) or p.stem.replace("-", " ").title()
        if name in living or p.stem in living_slugs:
            continue
        c["articles"]["wiki/" + p.stem] = [name, sha(t)]
    sj = root / "data" / "familypedia" / "subjects.json"
    try:
        subjects = json.loads(sj.read_text(encoding="utf-8")) if sj.exists() else {}
    except ValueError:
        subjects = {}
    for k, v in (subjects.items() if isinstance(subjects, dict) else []):
        if isinstance(v, dict) and v.get("title") and not v.get("private"):
            c["articles"]["subject/" + k] = [v["title"], sha(json.dumps(v, sort_keys=True))]
    for p in sorted((root / "data" / "familypedia").glob("*.json")):
        if p.stem in ("subjects", "routes") or p.stem in living_slugs:
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("private"):
            continue
        name = (subjects.get(p.stem) or {}).get("title") if isinstance(subjects, dict) else None
        name = name or (d.get("title") if isinstance(d, dict) else None) or tree_names.get(p.stem)
        if name and name not in living:
            c["articles"]["edit/" + p.stem] = [name, sha(json.dumps(d, sort_keys=True))]
    # timeline (not from private passages, not about living people)
    tl = root / "facts" / "timeline.csv"
    spans = private_spans(root)
    for r in (csv.DictReader(open(tl, encoding="utf-8")) if tl.exists() else []):
        stamps = re.findall(r"(S\d+) (\d\d:\d\d:\d\d)", (r.get("source") or "") + " " + (r.get("date_basis") or ""))
        if any(any(a <= _secs(ts) <= b for a, b in spans.get(s, ())) for s, ts in stamps):
            continue
        people = {x.strip() for x in (r.get("people") or "").split(";") if x.strip()}
        if people & living:
            continue
        label = f"{r.get('date_display') or r.get('date_start') or ''}: {(r.get('event') or '').strip()}".strip(": ")
        if r.get("event_id"):
            c["events"][r["event_id"]] = [label, sha(json.dumps(r, sort_keys=True))]
    # sources: counted by kind, never named
    sp = root / "data" / "sources.json"
    try:
        src = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    except ValueError:
        src = {}
    for k, v in (src.items() if isinstance(src, dict) else []):
        if isinstance(v, dict) and not v.get("trashed"):
            c["sources"][k] = [v.get("kind") or "file", ""]
    # the book's editions (CHANGELOG.md is already public on /updates/)
    for ver, date, items in book_versions(root):
        c["book"][ver] = [date, sha("\n".join(items))]
    return c


def _tree_names(root):
    ft = root / "data" / "family_tree.csv"
    return [r["name"].strip() for r in (csv.DictReader(open(ft, encoding="utf-8")) if ft.exists() else []) if r.get("name")]


def book_versions(root):
    """[(version, iso date, [bullets])] from CHANGELOG.md "## Version X — date" sections, oldest first."""
    p = root / "CHANGELOG.md"
    if not p.exists():
        return []
    md = re.sub(r"<!--.*?-->", "", p.read_text(encoding="utf-8"), flags=re.S)
    out, cur = [], None
    for line in md.splitlines():
        if line.startswith("## "):
            title, _, when = line[3:].strip().partition(" — ")
            ver = re.sub(r"^version\s+", "", title.strip(), flags=re.I)
            cur = [ver, iso_from_words(when), []]
            out.append(cur)
        elif line.startswith("- ") and cur:
            cur[2].append(line[2:].strip())
        elif cur and cur[2] and line.startswith("  ") and line.strip():
            cur[2][-1] += " " + line.strip()
    return [tuple(x) for x in reversed(out)]


def content_lines(old, new, cap_events=25):
    lines = []
    o, n = old.get("book", {}), new.get("book", {})
    root_versions = new.get("_book_items", {})
    for ver in n:
        if ver not in o:
            date = n[ver][0]
            items = root_versions.get(ver) or []
            if items:
                lines += [f"Book Version {ver} ({nice(date)}): {i}" for i in items]
            else:
                lines.append(f"Book Version {ver} published ({nice(date)}).")
        elif o[ver][1] != n[ver][1]:
            lines.append(f"Book Version {ver}: the edition notes were revised.")
    for kind, new_w, chg_w, gone_w in (("stories", "New story", "Story revised", "stories"),
                                        ("articles", "New Familypedia article", "Familypedia article updated",
                                         "Familypedia articles")):
        o, n = old.get(kind, {}), new.get(kind, {})
        seen = set()
        for k, (label, h) in n.items():
            if k not in o:
                if (kind, label) not in seen:
                    lines.append(f"{new_w}: {label}"); seen.add((kind, label))
            elif o[k][1] != h and (kind, label) not in seen:
                lines.append(f"{chg_w}: {label}"); seen.add((kind, label))
        # removals are counted, never named: an article taken down may have been made private on purpose
        gone = {label for k, (label, _) in o.items() if k not in n and not any(v[0] == label for v in n.values())}
        if gone:
            lines.append(f"{plural(len(gone), gone_w)} taken off the site.")
    o, n = old.get("events", {}), new.get("events", {})
    added = [n[k][0] for k in n if k not in o]
    changed = [n[k][0] for k in n if k in o and o[k][1] != n[k][1]]
    gone = [o[k][0] for k in o if k not in n]
    for label, xs in (("New timeline event", added), ("Timeline event corrected", changed)):
        lines += [f"{label}: {x[:160]}" for x in xs[:cap_events]]
        if len(xs) > cap_events:
            lines.append(f"…and {len(xs) - cap_events} more ({label.lower()}s).")
    if gone:
        lines.append(f"{plural(len(gone), 'timeline events')} removed.")
    o, n = old.get("sources", {}), new.get("sources", {})
    kinds = {}
    for k in n:
        if k not in o:
            kinds[n[k][0]] = kinds.get(n[k][0], 0) + 1
    if kinds:
        total = sum(kinds.values())
        lines.append(f"{plural(total, 'new sources')} indexed ("
                     + ", ".join(f"{v} {k}" for k, v in sorted(kinds.items(), key=lambda x: -x[1])) + ").")
    return lines


def area_summary(files):
    counts, noise = {}, 0
    for f in files:
        if NOISE.search(f):
            noise += 1
            continue
        label = next((lab for rx, lab in AREAS if re.search(rx, f)), "other files")
        counts[label] = counts.get(label, 0) + 1
    return counts, noise


def read_lock(root):
    p = root / "lineage.lock"
    try:
        d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except ValueError:
        d = {}
    return {"lineage": d.get("lineage") or "", "commit": d.get("commit") or ""}


def instance_path(root):
    return Path(root) / "data" / "site_changelog.json"


def capture_instance(root, dry_run=False, now=None):
    """Append an entry for everything that changed since the last one. Returns (entry or None, data)."""
    root = Path(root).resolve()
    cfg = _publish.settings(root)
    path = instance_path(root)
    data = load(path)
    content = instance_content(root, bool(cfg["include_living"]))
    items = {v: i for v, _, i in book_versions(root)}
    describe, lcommit = lineage_build()
    cur = {"commit": head(root) or "", "lock": read_lock(root), "lineage": {"describe": describe, "commit": lcommit},
           "version": _publish.version(root), "content": content}
    first = data is None
    if first:
        data = {"format": FORMAT, "site": cfg["site_url"] or cfg["title"] or root.name, "state": {}, "entries": []}
        for ver, date, bullets in book_versions(root):
            data["entries"].append(new_entry(data, ver, "", None, None, 0, bullets or [f"Version {ver} published."], 0,
                                             now=now, backfill=True, date=date))
        data["entries"].append(new_entry(data, cur["version"], describe, None, cur["commit"] or None, 0,
                                         ["Site changelog started: from here on every build of the site adds an entry "
                                          "listing what changed."], 0, now=now))
        data["state"] = cur
        if not dry_run:
            save(path, data)
        return data["entries"][-1], data

    st = data.get("state") or {}
    lines = content_lines(st.get("content") or {}, dict(content, _book_items=items))
    # the Lineage core
    ol, nl = st.get("lock") or {}, cur["lock"]
    if nl.get("lineage") and ol.get("lineage") != nl.get("lineage"):
        lines.append(f"Lineage core updated to {nl['lineage']}" + (f" (was {ol['lineage']})." if ol.get("lineage") else "."))
    ob, nb = (st.get("lineage") or {}).get("commit"), lcommit
    if nb and ob and ob != nb:
        home = _publish.lineage_home()
        cc = commits(home, ob, nb)
        if cc:
            lines.append(f"Built with Lineage {describe}: {plural(len(cc), 'core changes')} since the last build.")
            lines += [f"Lineage: {s}" for _, s in cc[:15]]
            if len(cc) > 15:
                lines.append(f"…and {len(cc) - 15} more Lineage changes (see the Lineage site changelog).")
        else:
            lines.append(f"Built with a different Lineage checkout: {describe}.")
    # the project's own commits
    frm, to = st.get("commit") or None, cur["commit"] or None
    cc = commits(root, frm, to)
    counts, noise = area_summary(changed_files(root, frm, to))
    meaningful = sum(counts.values())
    if cc and meaningful:
        lines.append(f"{plural(len(cc), 'commits')} to the project: "
                     + ", ".join(plural(v, k) for k, v in sorted(counts.items(), key=lambda x: -x[1])) + " changed.")
        if cfg.get("changelog_commit_messages"):
            lines += [f"Commit: {s}" for _, s in cc]
    elif frm and to and frm != to and not has_commit(root, frm):
        lines.append("The project's history was rewritten since the last entry; commits before it are not listed.")
    if cur["version"] and cur["version"] != st.get("version") and not any(l.startswith(f"Book Version {cur['version']}") for l in lines):
        lines.append(f"The book is now Version {cur['version']}" + (f" (was {st['version']})." if st.get("version") else "."))
    if not lines:
        return None, data              # nothing a reader would notice: no entry; noise is counted next time
    entry = new_entry(data, cur["version"], describe, frm, to, len(cc), lines, noise, now=now)
    data["entries"].append(entry)
    data["state"] = cur
    if not dry_run:
        save(path, data)
    return entry, data


# ------------------------------------------------------------------------------------------------ Lineage site
def platform_path(repo):
    return Path(repo) / "site" / "changelog.json"


def platform_content(repo, doc_titles):
    c = {"blog": {}, "docs": {}, "releases": {}}
    for f in sorted((repo / "docs" / "blog").glob("*.md")):
        t = f.read_text(encoding="utf-8", errors="ignore")
        c["blog"][f.name] = [_front(t).get("title") or f.stem, sha(t)]
    for src, title in doc_titles.items():
        if (repo / src).exists():
            c["docs"][src] = [title, fsha(repo / src)]
    rc = repo / "docs" / "blog" / "releases.csv"
    for r in (csv.DictReader(open(rc, encoding="utf-8")) if rc.exists() else []):
        c["releases"][r["version"]] = [r.get("date", ""), r.get("highlights", "")]
    return c


def _clean(subjects, withhold):
    keep, held = [], 0
    for s in subjects:
        if any(rx.search(s) for rx in withhold):
            held += 1
        else:
            keep.append(s)
    return keep, held


def capture_platform(repo=None, dry_run=False, withhold=(), doc_titles=None, now=None):
    """The Lineage website's changelog (site/changelog.json). withhold: regexes; a commit message matching one
    is not listed (build_site.py passes its real-names and leaks checks). Returns (entry or None, data)."""
    repo = Path(repo or _publish.lineage_home()).resolve()
    path = platform_path(repo)
    data = load(path)
    first = data is None
    doc_titles = doc_titles or {}
    describe = git(repo, "describe", "--tags", "--always") or ""
    cur = {"commit": head(repo) or "", "describe": describe, "content": platform_content(repo, doc_titles)}
    if data is None:
        data = {"format": FORMAT, "site": "Lineage", "state": {}, "entries": []}
        rels = sorted(cur["content"]["releases"].items(),
                      key=lambda kv: (kv[1][0], [int(x) if x.isdigit() else 0 for x in kv[0].split(".")]))
        prev = None
        for ver, (date, hl) in rels:
            tag = git(repo, "rev-list", "-n", "1", f"v{ver}")
            cc = commits(repo, prev, tag) if prev else []
            subs, held = _clean([s for _, s in cc], withhold)
            lines = [f"Release {ver}: {hl}"] + subs + ([f"{plural(held, 'changes')} not listed (they name a real family)."] if held else [])
            data["entries"].append(new_entry(data, f"v{ver}", f"v{ver}", prev, tag, len(cc), lines, 0,
                                             now=now, backfill=True, date=date))
            prev = tag or prev
        # baseline: the last release; the capture below lists everything after it
        data["state"] = {"commit": prev or cur["commit"], "describe": "", "content": cur["content"]}
    st = data.get("state") or {}
    frm, to = st.get("commit") or None, cur["commit"] or None
    cc = commits(repo, frm, to)
    files = changed_files(repo, frm, to)
    noise = sum(1 for f in files if NOISE.search(f))
    # a commit that only touched noise (this file, build output, lockfiles) is not listed
    subs, held = _clean([s for c, s in cc if not all(NOISE.search(f) for f in commit_files(repo, c))], withhold)
    lines = list(subs)
    if held:
        lines.append(f"{plural(held, 'changes')} not listed here (the message names a real family or a local path).")
    oc, nc = st.get("content") or {}, cur["content"]
    for ver, (date, hl) in nc["releases"].items():
        if ver not in oc.get("releases", {}):
            lines.insert(0, f"Release {ver} ({nice(date)}): {hl}")
    for k, (title, h) in nc["blog"].items():
        if k not in oc.get("blog", {}):
            lines.append(f"New blog post: {title}")
        elif oc["blog"][k][1] != h:
            lines.append(f"Blog post revised: {title}")
    docs = [title for k, (title, h) in nc["docs"].items() if k in oc.get("docs", {}) and oc["docs"][k][1] != h]
    docs += [title for k, (title, _) in nc["docs"].items() if k not in oc.get("docs", {})]
    if docs:
        lines.append("Docs updated: " + ", ".join(docs) + ".")
    if not lines:
        if first and not dry_run:
            save(path, data)                      # the backfill alone
        return None, data
    entry = new_entry(data, describe, describe, frm, to, len(cc), lines, noise, now=now)
    data["entries"].append(entry)
    data["state"] = cur
    if not dry_run:
        save(path, data)
    return entry, data


# ------------------------------------------------------------------------------------------------ rendering
NAMED = ("New story: ", "Story revised: ", "New Familypedia article: ", "Familypedia article updated: ",
         "New timeline event: ", "Timeline event corrected: ")


def still_published(data):
    """For a family site: a test that drops old lines naming a story, article or event that is no longer published
    (made private, a living person, or deleted since), so the page never keeps showing it. Book notes stay."""
    c = (data.get("state") or {}).get("content") or {}
    labels = {v[0] for kind in ("stories", "articles") for v in (c.get(kind) or {}).values()}
    labels |= {v[0][:160] for v in (c.get("events") or {}).values()}

    def keep(line):
        for p in NAMED:
            if line.startswith(p):
                return line[len(p):] in labels
        return True
    return keep if c.get("stories") is not None and "events" in c else (lambda line: True)


def entries_html(data, compare_url=None, h="h2"):
    """The entries, newest first, as HTML sections (the caller wraps them in its own page)."""
    out = []
    keep = still_published(data)
    for e in reversed(data.get("entries") or []):
        meta = []
        if e.get("version"):
            meta.append(("version " if not str(e["version"]).startswith("v") else "") + E(str(e["version"])))
        if not e.get("backfill"):
            meta.append(f"build {E(e['id'])}")
        c = e.get("commits") or {}
        if c.get("count"):
            rng = f"{(c.get('from') or '')[:7]}…{(c.get('to') or '')[:7]}"
            link = f'<a href="{E(compare_url)}/{E(c["from"])}...{E(c["to"])}">{rng}</a>' if compare_url and c.get("from") else rng
            meta.append(f"{plural(c['count'], 'commits')} ({link})")
        if e.get("noise"):
            meta.append(f"{plural(e['noise'], 'housekeeping files')} not listed")
        if e.get("backfill"):
            meta.append("from the release history")
        out.append(f'<section class="clog-entry"><{h} id="{E(e["id"])}">{E(nice(e["date"]))}</{h}>'
                   f'<p class="clog-meta">{" · ".join(meta)}</p><ul>'
                   + "".join(f"<li>{E(x)}</li>" for x in e.get("changes") or [] if keep(x)) + "</ul></section>")
    return "\n".join(out) or "<p>No changes recorded yet.</p>"


CLOG_CSS = (".clog-entry{border-top:1px solid var(--line,#ddd);padding-top:14px;margin-top:22px}"
            ".clog-entry h2,.clog-entry h3{margin:0}.clog-meta{color:var(--ink2,var(--ink-3,#777));font-size:14px;margin:2px 0 8px}"
            ".clog-entry li{margin:0 0 6px;overflow-wrap:anywhere}")


def standalone_page(data, title, home_url="/", home_label="Home", canonical=""):
    """A self-contained /changelog/ page (for a dashboard snapshot with no page shell of its own)."""
    can = f'<link rel="canonical" href="{E(canonical)}">' if canonical else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Changelog · {E(title)}</title>{can}
<meta name="description" content="Every change to {E(title)}, newest first, recorded each time the site is built.">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;1,400&display=swap">
<style>
  :root {{ --ink:#1d1a17; --paper:#f8f5ee; --rubric:#b3261e; --ink2:#6b645b; --line:#d9d2c4; }}
  @media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --ink:#ece6da; --paper:#171512; --rubric:#e0574d; --ink2:#a59d90; --line:#39342d; }} }}
  :root[data-theme="dark"] {{ --ink:#ece6da; --paper:#171512; --rubric:#e0574d; --ink2:#a59d90; --line:#39342d; }}
  body {{ margin:0; background:var(--paper); color:var(--ink); font:19px/1.6 "EB Garamond", Georgia, serif; }}
  .wrap {{ max-width:760px; margin:0 auto; padding:48px 16px 64px; }}
  a {{ color:var(--rubric); }}
  .kicker {{ letter-spacing:.22em; text-transform:uppercase; font-size:13px; color:var(--ink2); }}
  h1 {{ font-weight:400; color:var(--rubric); font-size:clamp(34px,5vw,48px); margin:8px 0 6px; }}
  {CLOG_CSS}
</style></head>
<body><div class="wrap">
<p class="kicker"><a href="{E(home_url)}">{E(home_label)}</a></p>
<h1>Changelog</h1>
<p>Every change to the site, newest first. An entry is added automatically each time the site is rebuilt.</p>
{entries_html(data)}
</div></body></html>
"""


def write_page(site, text):
    p = Path(site) / "changelog" / "index.html"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


# ------------------------------------------------------------------------------------------------ CLI
def _platform_checks():
    """build_site.py's real-names and leaks patterns, from this checkout."""
    try:
        sys.path.insert(0, str(_publish.lineage_home() / "site"))
        import build_site as bs  # noqa: E402
        return (bs.REAL_NAMES, bs.LEAKS), {s: t for s, _, t in bs.DOCS}
    except Exception:
        return (), {}


def main():
    ap = argparse.ArgumentParser(description="append what changed to a published site's changelog")
    ap.add_argument("--project", help="a family project folder (writes data/site_changelog.json)")
    ap.add_argument("--platform", action="store_true", help="the Lineage website (writes site/changelog.json)")
    ap.add_argument("--dry-run", action="store_true", help="print the entry that would be added; write nothing")
    ap.add_argument("--render", metavar="SITE", help="also write SITE/changelog/index.html")
    a = ap.parse_args()
    if bool(a.project) == bool(a.platform):
        ap.error("give --project DIR or --platform")
    if a.platform:
        withhold, titles = _platform_checks()
        entry, data = capture_platform(dry_run=a.dry_run, withhold=withhold, doc_titles=titles)
        title, where = "Lineage", platform_path(_publish.lineage_home())
    else:
        root = Path(a.project).expanduser().resolve()
        entry, data = capture_instance(root, dry_run=a.dry_run)
        title, where = _publish.settings(root)["title"] or root.name, instance_path(root)
    if entry:
        print(("would add" if a.dry_run else "added") + f" changelog entry {entry['id']} ({len(entry['changes'])} lines) to {where}")
        for x in entry["changes"]:
            print("  - " + x)
    else:
        print(f"changelog: nothing new since the last entry ({where})")
    if a.render and not a.dry_run:
        print("changelog page:", write_page(Path(a.render).expanduser().resolve(), standalone_page(data, title)))


if __name__ == "__main__":
    main()
