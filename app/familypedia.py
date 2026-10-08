"""Familypedia: an article for every subject the project's material names.

Article types: person · place · event · vessel · organization · object · publication ·
occupation · theme. Every article is built only from the project's own files, with the same
evidence rules for every type; nothing here writes prose that the material doesn't support.

What it reads (all optional; a project with none of them simply has fewer articles):
  content/units/*.md            front matter people / places / subjects ("vessel: Name")
  facts/timeline.csv            events, their people and places
  facts/people/*.md             person profiles ("# Name", "Also called: ...")
  knowledge/graph.json          typed nodes and edges (or knowledge/nodes.csv + edges.csv)
  data/archives.csv             the records catalogue (records-archives skill)
  facts/records/**/sources.csv  research sources: title, url, holder, type, date_retrieved
  facts/records/**/sources.json {key: {url, retrieved}}: retrieval dates by URL
  facts/**/*track*.csv, *route*.csv   positions and ports (make_route_map.py columns)
  photos/photo_index.csv        photographs and illustrations (photo-processor skill)
  facts/gaps.md                 open questions
  facts/records/**/context_*.md public background, offered under "Beyond the family"
  data/sources.json             the dashboard's source index (summaries, people, places)
What it writes (all under data/familypedia/, all the author's own):
  <slug>.json      my edits to one article: lead, notes, infobox, aliases, type, coords, beyond
  subjects.json    subjects I created ("New subject…")
  tags.json        tags on sources, records, photographs and events, with state and evidence
  routes.json      which subject a track or route file belongs to, when the name is ambiguous
"""
import csv
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

HOST = None  # the server module; set by server.py (engine_stories, intake_load, effective, ...)

TYPES = ["person", "place", "event", "vessel", "organization", "object", "publication", "occupation", "theme"]
TYPE_LABELS = {"person": "People", "place": "Places", "event": "Events", "vessel": "Vessels and vehicles",
               "organization": "Organizations and units", "object": "Objects", "publication": "Publications",
               "occupation": "Occupations and trades", "theme": "Themes"}
TYPE_SINGULAR = {"person": "person", "place": "place", "event": "event", "vessel": "vessel or vehicle",
                 "organization": "organization or unit", "object": "object", "publication": "publication",
                 "occupation": "occupation or trade", "theme": "theme"}
# knowledge-graph node type -> (article type, kind shown under the title)
KG_TYPES = {"person": ("person", ""), "place": ("place", ""), "event": ("event", ""), "voyage": ("event", "voyage"),
            "vessel": ("vessel", ""), "vehicle": ("vessel", "vehicle"), "ship": ("vessel", "ship"),
            "organization": ("organization", ""), "unit": ("organization", "military unit"),
            "object": ("object", ""), "publication": ("publication", ""), "occupation": ("occupation", ""),
            "theme": ("theme", "")}
KG_RECORDS = {"record": "catalogue record", "letter": "letter", "photograph": "photograph", "document": "document"}
INFOBOX = {
    "person": ["Also called", "Relationship", "Dates", "Places", "Served in", "Aboard", "Occupation"],
    "place": ["Location", "Region", "What it was", "Years in the story", "Map", "Who lived or worked there"],
    "vessel": ["Type", "Tonnage", "Built", "Owner", "Master", "Registry", "Fate", "Voyage dates"],
    "organization": ["Full name", "What it was", "The family's connection", "Members in the family"],
    "object": ["What it is", "Dates", "Made or owned by", "Where it is now", "Survives"],
    "event": ["Date", "Precision", "Place", "People", "Kind"],
    "publication": ["What it is", "When it appears", "Who it touches"],
    "occupation": ["What it is", "When it appears", "Who it touches"],
    "theme": ["What it is", "When it appears", "Who it touches"],
}
TIERS = ("witnessed", "told", "lore", "documented")
TAG_STATES = ("suggested", "accepted", "rejected", "unsure")
RELATION_LABELS = {"crew_on": "aboard", "master_of": "master of", "voyage_of": "voyage of", "served_in": "served in",
                   "member_of": "member of", "enlisted_in": "enlisted in", "lived_at": "lived at", "worked_at": "worked at",
                   "occurred_at": "happened at", "event_of": "event of", "took_part_in": "took part in", "married": "married",
                   "part_of": "part of", "held_by": "held by", "documents": "documents", "depicts": "depicts",
                   "mentions": "mentions", "concerns": "concerns", "wrote": "wrote", "addressed_to": "addressed to",
                   "written_at": "written at", "called_at": "called at", "owned_by": "owned by", "made_by": "made by"}
_LOCK = threading.Lock()
_CACHE = {}


# ------------------------------------------------------------------------------- helpers
def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:90]


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_csv(p):
    try:
        with open(p, encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def _read_json(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(p, data):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    tmp.replace(p)


def _fp(project):
    return project.root / "data" / "familypedia"


def _split_list(v):
    v = (v or "").strip()
    if v.startswith("["):
        return [x.strip() for x in re.findall(r'"([^"]+)"', v)]
    return [x.strip() for x in re.split(r";\s*", v) if x.strip()]


def _years(text):
    return [int(y) for y in re.findall(r"\b(1[5-9]\d\d|20\d\d)\b", text or "")]


def _parse_metadata(s):
    """'Key | Value | Key | Value' (museum catalogue exports) -> dict."""
    parts = [p.strip() for p in (s or "").split("|")]
    out = {}
    for i in range(0, len(parts) - 1, 2):
        if parts[i] and parts[i] not in out:
            out[parts[i]] = parts[i + 1]
    return out


def _host_name(url):
    m = re.match(r"https?://(?:www\.)?([^/]+)", url or "")
    return m.group(1) if m else ""


# ------------------------------------------------------------------------------- inputs
def _inputs(project):
    r = project.root
    files = []
    for g in ("content/units/*.md", "facts/timeline.csv", "facts/people/*.md", "knowledge/graph.json",
              "knowledge/nodes.csv", "knowledge/edges.csv", "data/archives.csv", "facts/records/**/sources.csv",
              "facts/records/**/sources.json", "facts/**/*track*.csv", "facts/**/*route*.csv", "photos/photo_index.csv",
              "facts/gaps.md", "facts/records/**/context_*.md", "transcript/clean/*.md", "chapters/*.typ", "chapters/*.md",
              "data/chapters.csv", "data/sources.json", "data/familypedia/*.json", "data/genealogy/*.json",
              "data/stale_stories.json"):
        for p in r.glob(g):
            if "_raw" in p.parts:
                continue
            try:
                files.append((str(p), p.stat().st_mtime_ns))
            except OSError:
                pass
    return tuple(sorted(files))


def _kg(project):
    r = project.root / "knowledge"
    g = _read_json(r / "graph.json", None)
    if g and g.get("nodes"):
        return g["nodes"], g.get("edges") or g.get("links") or []
    nodes = _read_csv(r / "nodes.csv")
    edges = []
    for e in _read_csv(r / "edges.csv"):
        attrs = _read_json_str(e.pop("attrs", "") or "{}")
        edges.append({**e, **attrs})
    return nodes, edges


def _read_json_str(s):
    try:
        return json.loads(s)
    except Exception:
        return {}


def _units(project):
    out = []
    for p in sorted(project.root.glob("content/units/*.md")):
        text = p.read_text(encoding="utf-8", errors="ignore")
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
        if not m:
            continue
        fm = {}
        for line in m.group(1).splitlines():
            k, _, v = line.partition(":")
            if k and not k.startswith(" "):
                fm[k.strip()] = v.strip()
        body = m.group(2)
        shaped = body.split("## Shaped", 1)[1].split("## Notes", 1)[0] if "## Shaped" in body else ""
        out.append({"id": fm.get("id", p.stem), "file": p.relative_to(project.root).as_posix(),
                    "title": fm.get("title", "").strip('"'), "chapter": str(fm.get("chapter", "") or ""),
                    "part": fm.get("part", ""), "tier": fm.get("tier", ""), "section": fm.get("section", "").strip('"'),
                    "people": _split_list(fm.get("people")), "places": _split_list(fm.get("places")),
                    "subjects": _split_list(fm.get("subjects")), "events": _split_list(fm.get("timeline_events")),
                    "spans": _split_list(fm.get("spans")), "text": body, "shaped": shaped})
    return out


def _profiles(project):
    out = []
    for p in sorted(project.root.glob("facts/people/*.md")):
        text = p.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"^#\s+(.+)$", text, re.M)
        if not m:
            continue
        also = re.search(r"^Also called:\s*(.+)$", text, re.M | re.I)
        rel = re.search(r"^Relationship to [^:]*:\s*(.+)$", text, re.M | re.I)
        dates = re.search(r"^Dates:\s*(.+)$", text, re.M | re.I)
        out.append({"title": m.group(1).strip(), "file": p.relative_to(project.root).as_posix(),
                    "aliases": _profile_aliases(also.group(1)) if also else [],
                    "relationship": rel.group(1).strip() if rel else "", "dates": dates.group(1).strip() if dates else ""})
    return out


def _profile_aliases(line):
    """'Also called:' holds names and sometimes a note about them. Keep the short name-like parts
    and any name in quotation marks; drop the commentary."""
    out = []
    for part in re.split(r"[;,]", line):
        part = part.strip().strip('"“”').strip()
        if part and len(part) <= 40 and not re.search(r"[\[\]—:]|\b(says|said|spelling|unverified|leave)\b", part, re.I):
            out.append(part)
    out += re.findall(r'[“"]([^”"]{2,40})[”"]', line)
    return list(dict.fromkeys(out))


def _retrieved_by_url(project):
    out = {}
    for p in project.root.glob("facts/records/**/sources.csv"):
        if "_raw" in p.parts:
            continue
        for r in _read_csv(p):
            if r.get("url"):
                out[r["url"]] = r.get("date_retrieved") or r.get("retrieved") or ""
    for p in project.root.glob("facts/records/**/sources.json"):
        if "_raw" in p.parts:
            continue
        d = _read_json(p, {})
        items = d.items() if isinstance(d, dict) else enumerate(d if isinstance(d, list) else [])
        for _, v in items:
            if isinstance(v, dict) and v.get("url") and v.get("retrieved"):
                out.setdefault(v["url"], v["retrieved"])
    return out


def _tracks(project):
    """Track and route CSVs: rows with a place and/or coordinates, in order."""
    out = []
    seen = set()
    for g in ("facts/**/*track*.csv", "facts/**/*route*.csv"):
        for p in sorted(project.root.glob(g)):
            if "_raw" in p.parts or p in seen:
                continue
            seen.add(p)
            rows = _read_csv(p)
            if not rows or not ({"place", "lat"} & set(rows[0].keys())):
                continue
            out.append({"file": p.relative_to(project.root).as_posix(), "rows": rows,
                        "has_coords": any((r.get("lat") or "").strip() for r in rows)})
    return out


def _photos(project):
    rows = _read_csv(project.root / "photos" / "photo_index.csv")
    return [r for r in rows if (r.get("status") or "").lower() not in ("superseded", "duplicate", "rejected")]


def _context_lines(project):
    out = []
    for p in project.root.glob("facts/records/**/context_*.md"):
        if "_raw" in p.parts:
            continue
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip().startswith(("-", "*", "|")) and len(line) > 30:
                out.append({"file": p.relative_to(project.root).as_posix(), "text": line.strip(" -*|")})
    return out


# ------------------------------------------------------------------------------- the index
class Subject(dict):
    pass


def _build(project):
    root = project.root
    fp = _fp(project)
    edits = {p.stem: _read_json(p, {}) for p in fp.glob("*.json")
             if p.stem not in ("subjects", "tags", "routes")} if fp.is_dir() else {}
    mine = _read_json(fp / "subjects.json", {})
    tags = _read_json(fp / "tags.json", {})
    routes_cfg = _read_json(fp / "routes.json", {})
    subs = {}       # slug -> subject
    by_norm = {}    # (type, norm title) -> slug

    def add(title, typ, kind="", origin=""):
        title = re.sub(r"\s+", " ", (title or "").strip().rstrip("."))
        if not title or typ not in TYPES:
            return None
        key = (typ, norm(title))
        if key in by_norm:
            s = subs[by_norm[key]]
        else:
            slug = slugify(title)
            if slug in subs and subs[slug]["type"] != typ:
                slug = f"{slug}-{typ}"
            n = 2
            base = slug
            while slug in subs and subs[slug]["type"] != typ:
                slug = f"{base}-{n}"
                n += 1
            s = subs.get(slug)
            if not s:
                s = Subject(slug=slug, title=title, type=typ, kind=kind, aliases=set(), units=set(), events=set(),
                            kg=set(), origins=set(), profile=None, mention_paras=[], stories=set(), records=[],
                            photos=[], sources=[], tagged=[], coords=None, routes=[])
                subs[slug] = s
            by_norm[key] = slug
        if kind and not s["kind"]:
            s["kind"] = kind
        if origin:
            s["origins"].add(origin)
        return s

    units = _units(project)
    for u in units:
        for n in u["people"]:
            add(n, "person", origin="story units")["units"].add(u["id"])
        for n in u["places"]:
            add(n, "place", origin="story units")["units"].add(u["id"])
        for item in u["subjects"]:
            t, _, n = item.partition(":")
            if n and t.strip() in TYPES:
                add(n, t.strip(), origin="story units")["units"].add(u["id"])
    timeline = HOST._timeline_rows(project)
    for e in timeline:
        ev = add(e.get("event", ""), "event", origin="timeline")
        if ev:
            ev["events"].add(e["event_id"])
        for n in _split_list(e.get("people")):
            add(n, "person", origin="timeline")["events"].add(e["event_id"])
        if e.get("place"):
            add(e["place"], "place", origin="timeline")["events"].add(e["event_id"])
    for pr in _profiles(project):
        s = add(pr["title"], "person", origin="people profiles")
        s["profile"] = pr
        s["aliases"].update(a for a in pr["aliases"] if a)
    nodes, edges = _kg(project)
    kg_nodes = {n["id"]: n for n in nodes}
    kg_subject = {}  # kg id -> slug
    for n in nodes:
        t = (n.get("type") or "").lower()
        if t in KG_TYPES:
            typ, kind = KG_TYPES[t]
            s = add(n.get("label") or n["id"], typ, kind, origin="knowledge graph")
            s["kg"].add(n["id"])
            kg_subject[n["id"]] = s["slug"]
    for slug, m in mine.items():
        s = add(m.get("title", ""), m.get("type", "theme"), m.get("kind", ""), origin="created by me")
        if s:
            s["aliases"].update(m.get("aliases") or [])
            s["mine"] = True
    tracks = _tracks(project)
    for tr in tracks:
        for r in tr["rows"]:
            if (r.get("place") or "").strip() and (r.get("kind") or "port") not in ("text", "waypoint", "area"):
                add(_clean_place(r["place"]), "place", origin="routes and tracks")

    # my edits: type changes, aliases, merges ("same as")
    for slug, e in edits.items():
        s = subs.get(slug)
        if not s:
            continue
        if e.get("type") in TYPES:
            s["type"] = e["type"]
        if e.get("kind"):
            s["kind"] = e["kind"]
        s["aliases"].update(a for a in (e.get("aliases") or []) if a)
    merged = {}
    for slug, s in list(subs.items()):
        e = edits.get(slug) or {}
        for other in (e.get("same_as") or []):
            o = subs.get(other)
            if o and other != slug and other not in merged:
                _merge(s, o)
                merged[other] = slug
    for other in merged:
        subs.pop(other, None)
    for kid, slug in list(kg_subject.items()):
        kg_subject[kid] = merged.get(slug, slug)
    for key, slug in list(by_norm.items()):     # names of a folded article now find the one it was folded into
        if slug in merged:
            by_norm[key] = merged[slug]

    # mention keys: title, title before a comma, aliases; first names only when unique among people
    keys = {}
    for s in subs.values():
        for k in _keys(s):
            keys.setdefault(k, set()).add(s["slug"])
    first = {}
    for s in subs.values():
        if s["type"] == "person":
            f = s["title"].split()[0] if s["title"].split() else ""
            if len(f) > 3:
                first.setdefault(f, []).append(s["slug"])
    rx = _key_regex(keys)

    # transcripts
    paras = []
    for p in sorted(root.glob("transcript/clean/*.md")):
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            pm = HOST.PARA.match(line)
            if pm:
                paras.append({"speaker": pm["spk"], "session": pm["sid"], "t": pm["ts"],
                              "cite": f"[{pm['sid']} {pm['ts']}]", "text": pm["text"]})
    whole = "\n".join(p["text"] for p in paras)
    for f, slugs in first.items():
        if len(slugs) == 1 and f not in keys and not any(k in whole for k in _keys(subs[slugs[0]])):
            keys[f] = {slugs[0]}
    rx = _key_regex(keys)
    for i, para in enumerate(paras):
        for slug in _hits(rx, keys, para["text"]):
            subs[slug]["mention_paras"].append(i)
    for u in units:
        for slug in _hits(rx, keys, u["shaped"] or u["text"]):
            subs[slug]["units"].add(u["id"])

    # stories
    stories = HOST.engine_stories(project)
    story_text = {}
    for st in stories:
        f = root / st["file"]
        if f.is_file():
            story_text[st["id"]] = f.read_text(encoding="utf-8", errors="ignore")
            for slug in _hits(rx, keys, story_text[st["id"]]):
                subs[slug]["stories"].add(st["id"])
    unit_by_id = {u["id"]: u for u in units}
    story_ids = {st["id"] for st in stories}
    for s in subs.values():
        for uid in s["units"]:
            ch = unit_by_id.get(uid, {}).get("chapter")
            if ch and ch in story_ids:
                s["stories"].add(ch)

    # records
    retrieved = _retrieved_by_url(project)
    records = []
    adj = {}
    for e in edges:
        adj.setdefault(e["source"], []).append((e.get("rel", ""), e["target"], e, "out"))
        adj.setdefault(e["target"], []).append((e.get("rel", ""), e["source"], e, "in"))

    def archive_of(nid, depth=0):
        for rel, other, _, d in adj.get(nid, []):
            if rel == "held_by" and d == "out":
                return (kg_nodes.get(other) or {}).get("label", "")
        if depth < 2:
            for rel, other, _, d in adj.get(nid, []):
                if rel == "part_of" and d == "out":
                    a = archive_of(other, depth + 1)
                    if a:
                        return a
        return ""

    for n in nodes:
        t = (n.get("type") or "").lower()
        url = n.get("url") or ""
        if t in KG_RECORDS:
            meta = _parse_metadata(n.get("metadata"))
            linked = sorted({kg_subject[o] for _, o, _, _ in adj.get(n["id"], []) if o in kg_subject})
            records.append({"id": n["id"], "type": KG_RECORDS[t], "title": n.get("label") or n["id"],
                            "archive": n.get("holder") or archive_of(n["id"]) or _host_name(url),
                            "number": meta.get("Object ID number") or _catalogue_number(n.get("label")),
                            "url": url, "retrieved": n.get("retrieved") or retrieved.get(url, ""),
                            "date": n.get("date") or meta.get("Date", ""), "description": n.get("description") or meta.get("Description", ""),
                            "subjects": linked, "origin": "knowledge graph"})
        elif t in KG_TYPES and url:
            slug = kg_subject.get(n["id"])
            records.append({"id": n["id"] + "#entry", "type": "database entry", "title": n.get("label") or n["id"],
                            "archive": n.get("holder") or _host_name(url),
                            "number": n.get("whaling_id") or _catalogue_number(n.get("label")), "url": url,
                            "retrieved": n.get("retrieved") or retrieved.get(url, ""), "date": n.get("date", ""),
                            "description": n.get("description", ""), "subjects": [slug] if slug else [],
                            "origin": "knowledge graph"})
    for r in _read_csv(root / "data" / "archives.csv"):
        text = " ".join(r.get(k, "") for k in ("item", "description", "holder", "date_range"))
        urls = re.findall(r"https?://\S+", r.get("mentioned_in", ""))
        records.append({"id": r.get("record_id") or r.get("item"), "type": r.get("type") or "record",
                        "title": r.get("item", ""), "archive": r.get("holder") or r.get("location_general", ""),
                        "number": r.get("record_id", ""), "url": urls[0] if urls else "",
                        "retrieved": retrieved.get(urls[0], "") if urls else "", "date": r.get("date_range", ""),
                        "description": r.get("description", ""), "status": r.get("status", ""),
                        "cite": " ".join(re.findall(r"\[S\d+ \d\d:\d\d:\d\d\]", r.get("mentioned_in", ""))),
                        "subjects": sorted(_hits(rx, keys, text)), "origin": "records catalogue"})
    seen_urls = {r["url"] for r in records if r["url"]}
    for p in sorted(root.glob("facts/records/**/sources.csv")):
        if "_raw" in p.parts:
            continue
        for r in _read_csv(p):
            if not r.get("url") or r["url"] in seen_urls:
                continue
            seen_urls.add(r["url"])
            records.append({"id": f"{p.parent.name}:{r.get('id') or slugify(r.get('title'))}", "type": r.get("type") or "source",
                            "title": r.get("title", ""), "archive": r.get("holder") or _host_name(r["url"]),
                            "number": r.get("id", ""), "url": r["url"], "retrieved": r.get("date_retrieved", ""),
                            "date": "", "description": "", "rights": r.get("rights_notes", ""),
                            "subjects": sorted(_hits(rx, keys, r.get("title", ""))), "origin": p.relative_to(root).as_posix()})
    rec_by_id = {r["id"]: r for r in records}
    for target, tl in tags.items():
        if target.startswith("record:"):
            rec = rec_by_id.get(target[7:])
            if rec:
                for t in tl:
                    if t.get("state") == "accepted" and t["subject"] in subs and t["subject"] not in rec["subjects"]:
                        rec["subjects"].append(t["subject"])
    for r in records:
        for slug in r["subjects"]:
            if slug in subs:
                subs[slug]["records"].append(r["id"])

    # photographs and illustrations
    photos = []
    for r in _photos(project):
        text = " ".join(r.get(k, "") for k in ("subject", "people", "location", "comment", "original_caption"))
        illus = bool(re.match(r"\s*illustration", r.get("subject", ""), re.I)) or "generated" in (r.get("comment", "") + r.get("source_file", "")).lower()
        thumb = (r.get("print_file") or "").lstrip("/")
        if thumb and not (root / thumb).is_file():
            thumb = ""
        ph = {"id": r.get("id"), "caption": r.get("subject", ""), "people": r.get("people", ""),
              "people_basis": r.get("people_basis", ""), "date": r.get("date", ""), "date_basis": r.get("date_basis", ""),
              "location": r.get("location", ""), "location_basis": r.get("location_basis", ""),
              "thumb": thumb, "illustration": illus, "chapter": r.get("chapter", ""),
              "provenance": ("Generated illustration, not a photograph" + (f" ({r.get('people_basis')})" if r.get("people_basis") else ""))
              if illus else (r.get("source_file") or ""), "subjects": sorted(_hits(rx, keys, text)), "origin": "photo index"}
        photos.append(ph)
    for row in HOST.intake_load(project).values():
        if row.get("trashed") or row.get("kind") != "image":
            continue
        eff = HOST.effective(row)
        text = " ".join([eff.get("summary") or "", " ".join(eff.get("people") or []), " ".join(eff.get("places") or [])])
        photos.append({"id": "src:" + row["id"], "caption": eff.get("accepted_name") or row["original_name"],
                       "thumb": row.get("thumb") or "", "illustration": HOST.is_illustration(row), "provenance": "source: " + row["path"],
                       "date": eff.get("date_range") or "", "subjects": sorted(_hits(rx, keys, text)), "origin": "sources"})
    ph_by_id = {p["id"]: p for p in photos}
    for target, tl in tags.items():
        if target.startswith("photo:"):
            ph = ph_by_id.get(target[6:])
            if ph:
                for t in tl:
                    if t.get("state") == "accepted" and t["subject"] in subs and t["subject"] not in ph["subjects"]:
                        ph["subjects"].append(t["subject"])
    for ph in photos:
        for slug in ph["subjects"]:
            if slug in subs:
                subs[slug]["photos"].append(ph["id"])

    # sources (the dashboard's source index, plus recordings by the sessions that mention a subject)
    sessions = HOST.session_map(project)
    session_file = {sid: f for f, sid in sessions.items()}
    src_rows = {r["id"]: r for r in HOST.intake_load(project).values() if not r.get("trashed")}
    for rid, row in src_rows.items():
        eff = HOST.effective(row)
        names = " ; ".join((eff.get("people") or []) + (eff.get("places") or []) + (eff.get("organizations") or []))
        for slug in _hits(rx, keys, names + " " + (eff.get("summary") or "")):
            subs[slug]["sources"].append({"id": rid, "why": "named in its summary or details"})
    for target, tl in tags.items():
        if target.startswith("source:"):
            for t in tl:
                if t.get("state") == "accepted" and t["subject"] in subs:
                    subs[t["subject"]]["sources"].append({"id": target[7:], "why": "tagged by me"})
        if target.startswith("event:"):
            for t in tl:
                if t.get("state") == "accepted" and t["subject"] in subs:
                    subs[t["subject"]]["events"].add(target[6:])
    for s in subs.values():
        for i in s["mention_paras"]:
            sid = paras[i]["session"]
            if sid in session_file and not any(x["id"] == "session:" + sid for x in s["sources"]):
                s["sources"].append({"id": "session:" + sid, "why": "mentioned in the recording"})

    # timeline events: subjects named in the event text count too
    for e in timeline:
        for slug in _hits(rx, keys, " ".join([e.get("event", ""), e.get("place", ""), e.get("people", "")])):
            subs[slug]["events"].add(e["event_id"])

    # coordinates and routes
    for tr in tracks:
        tr["subjects"] = _route_subjects(tr, subs, routes_cfg)
        for slug in tr["subjects"]:
            subs[slug]["routes"].append(tr["file"])
        for r in tr["rows"]:
            pl = _clean_place(r.get("place", ""))
            s = subs.get(by_norm.get(("place", norm(pl)), ""))
            if s and tr["subjects"]:
                s["routes"].append(tr["file"])
            if s and (r.get("lat") or "").strip() and (r.get("lon") or "").strip() and not s["coords"]:
                try:
                    s["coords"] = {"lat": float(r["lat"]), "lon": float(r["lon"]), "basis": "recorded",
                                   "source": f"{tr['file']} (row {r.get('seq') or tr['rows'].index(r) + 1}): {r.get('source', '')}"}
                except ValueError:
                    pass
    for n in nodes:
        s = subs.get(kg_subject.get(n["id"], ""))
        if s and n.get("lat") and n.get("lon") and not s["coords"]:
            try:
                s["coords"] = {"lat": float(n["lat"]), "lon": float(n["lon"]), "basis": n.get("coord_basis", "recorded"),
                               "source": n.get("url") or "knowledge graph"}
            except ValueError:
                pass
    for slug, e in edits.items():
        s = subs.get(merged.get(slug, slug))
        if s and isinstance(e.get("coords"), dict) and e["coords"].get("lat") not in (None, ""):
            try:
                s["coords"] = {"lat": float(e["coords"]["lat"]), "lon": float(e["coords"]["lon"]),
                               "basis": e["coords"].get("basis", "approximate"), "source": e["coords"].get("source", "stated by me"), "by": "me"}
            except (TypeError, ValueError):
                pass

    # score and stubs
    for s in subs.values():
        s["degree"] = sum(1 for k in s["kg"] for _, o, _, _ in adj.get(k, []) if o in kg_subject or o in kg_nodes)
        s["score"] = (min(s["degree"], 30) // 3 + 3 * len(s["units"]) + 2 * len(s["events"]) + len(s["mention_paras"]) + len(s["records"])
                      + len(s["photos"]) + 3 * len(s["stories"]) + len(s["sources"]))
        s["stub"] = s["score"] < 3 and not (edits.get(s["slug"]) or {}).get("lead")
    return {"subs": subs, "by_norm": by_norm, "keys": keys, "rx": rx, "paras": paras, "units": unit_by_id,
            "timeline": {e["event_id"]: e for e in timeline}, "stories": {st["id"]: st for st in stories},
            "records": rec_by_id, "photos": ph_by_id, "kg_nodes": kg_nodes, "kg_subject": kg_subject, "adj": adj,
            "edits": edits, "merged": merged, "tags": tags, "tracks": tracks, "src_rows": src_rows,
            "session_file": session_file, "story_text": story_text}


def _merge(into, other):
    into["aliases"].add(other["title"])
    into["aliases"].update(other["aliases"])
    for k in ("units", "events", "kg", "origins", "stories"):
        into[k].update(other[k])
    into["kind"] = into["kind"] or other["kind"]
    into["profile"] = into["profile"] or other["profile"]


def _clean_place(s):
    return re.sub(r"\s*\((?:near|off)[^)]*\)\s*$", "", (s or "").strip().strip('"'))


def _catalogue_number(label):
    m = re.search(r"\b(\d{4}\.\d{1,3}\.\d{1,4}(?:\.\d+)?|A[SVDMC]\d{4,})\b", label or "")
    return m.group(1) if m else ""


def _keys(s):
    out = set()
    for k in [s["title"], s["title"].split(",")[0], *s["aliases"]]:
        k = (k or "").strip()
        k = re.sub(r"\s*\([^)]*\)\s*$", "", k)
        if len(k) > 3 and not (s["type"] == "event" and len(k) > 60):
            out.add(k)
    return out


def _key_regex(keys):
    if not keys:
        return None
    alts = sorted(keys, key=len, reverse=True)
    return re.compile(r"(?<![\w])(" + "|".join(re.escape(k) for k in alts) + r")(?![\w])")


def _hits(rx, keys, text):
    if not rx or not text:
        return set()
    out = set()
    for m in rx.finditer(text):
        out.update(keys.get(m.group(1), ()))
    return out


def _route_subjects(tr, subs, cfg):
    """A route belongs to the subject routes.json names; else to the one vessel or event its path names."""
    if tr["file"] in cfg:
        v = cfg[tr["file"]]
        return [x for x in (v if isinstance(v, list) else [v]) if x in subs]
    path = norm(tr["file"].replace("/", " ").replace("_", " "))
    words = set(path.split())
    cands = [s["slug"] for s in subs.values() if s["type"] in ("vessel",)
             and norm(re.sub(r"^(ship|bark|brig|schooner|sloop|steamship|uss)\s+", "", s["title"], flags=re.I)).split()[:1]
             and norm(re.sub(r"^(ship|bark|brig|schooner|sloop|steamship|uss)\s+", "", s["title"], flags=re.I)).split()[0] in words]
    return cands if len(cands) == 1 else []


def index(project):
    sig = _inputs(project)
    with _LOCK:
        c = _CACHE.get(str(project.root))
        if c and c[0] == sig:
            return c[1]
    built = _build(project)
    with _LOCK:
        _CACHE[str(project.root)] = (sig, built)
    return built


def invalidate(project):
    with _LOCK:
        _CACHE.pop(str(project.root), None)


# ------------------------------------------------------------------------------- list views
def summaries(project):
    """Every article, with the counts the browse views sort and filter by. Compatible with the
    older person/place/event list: slug, title, type, stub, units, events, mentions."""
    ix = index(project)
    out = []
    for s in ix["subs"].values():
        out.append({"slug": s["slug"], "title": s["title"], "type": s["type"], "kind": s["kind"],
                    "aliases": sorted(s["aliases"]), "stub": s["stub"], "score": s["score"],
                    "units": sorted(s["units"]), "events": sorted(s["events"]), "mentions": len(s["mention_paras"]),
                    "records": len(s["records"]), "photos": len(s["photos"]), "stories": len(s["stories"]),
                    "sources": len(s["sources"]), "has_coords": bool(s["coords"]), "origins": sorted(s["origins"])})
    return sorted(out, key=lambda a: (TYPES.index(a["type"]), a["title"].lower()))


def link_table(project):
    """Names the project knows -> article, longest first, for [[links]] and automatic links."""
    ix = index(project)
    rows = []
    for k, slugs in ix["keys"].items():
        if len(slugs) == 1:
            s = ix["subs"][next(iter(slugs))]
            rows.append([k, s["slug"], s["type"], s["stub"]])
        else:
            for slug in sorted(slugs):
                s = ix["subs"][slug]
                rows.append([k, slug, s["type"], s["stub"]])
    for s in ix["subs"].values():
        rows.append([s["title"], s["slug"], s["type"], s["stub"]])
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: -len(r[0])):
        if (r[0].lower(), r[1]) not in seen:
            seen.add((r[0].lower(), r[1]))
            out.append(r)
    return out


def search(project, q, types=None):
    ix = index(project)
    terms = [t for t in norm(q).split() if t]
    if not terms:
        return []
    hits = []
    for s in ix["subs"].values():
        if types and s["type"] not in types:
            continue
        e = ix["edits"].get(s["slug"]) or {}
        head = norm(" ".join([s["title"], *s["aliases"], s["kind"], s["type"]]))
        body_parts = [e.get("lead", ""), e.get("notes", "")]
        body_parts += [ix["units"][u]["title"] for u in s["units"] if u in ix["units"]]
        body_parts += [ix["timeline"][x].get("event", "") for x in s["events"] if x in ix["timeline"]]
        body_parts += [ix["records"][r]["title"] for r in s["records"][:40] if r in ix["records"]]
        body_parts += [ix["paras"][i]["text"] for i in s["mention_paras"][:30]]
        for kid in s["kg"]:
            n = ix["kg_nodes"].get(kid) or {}
            body_parts += [str(v) for k, v in n.items() if k not in ("id", "type")]
        body = norm(" ".join(body_parts))
        if all(t in head or t in body for t in terms):
            rank = sum(3 for t in terms if t in head) + min(s["score"], 50) / 50
            snippet = ""
            raw = " ".join(body_parts)
            pos = raw.lower().find(terms[0])
            if pos >= 0:
                snippet = raw[max(0, pos - 60): pos + 120]
            hits.append({"slug": s["slug"], "title": s["title"], "type": s["type"], "stub": s["stub"],
                         "snippet": snippet, "rank": rank})
    return sorted(hits, key=lambda h: -h["rank"])[:100]


# ------------------------------------------------------------------------------- one article
def article(project, slug):
    ix = index(project)
    slug = ix["merged"].get(slug, slug)
    s = ix["subs"].get(slug)
    if not s:
        raise KeyError("no such article")
    e = ix["edits"].get(slug) or {}
    subs = ix["subs"]
    events = sorted((ix["timeline"][x] for x in s["events"] if x in ix["timeline"]),
                    key=lambda r: ((r.get("date_start") or "9999"), r["event_id"]))
    units = [ix["units"][u] for u in sorted(s["units"]) if u in ix["units"]]
    records = [ix["records"][r] for r in dict.fromkeys(s["records"]) if r in ix["records"]]
    photos = [ix["photos"][p] for p in dict.fromkeys(s["photos"]) if p in ix["photos"]]
    related = _related(ix, s)
    infobox = _infobox(ix, s, events, units, records, related, e)

    # tiers: what was witnessed, told, family lore, and what the records show
    tiers = {t: [] for t in TIERS}
    for ev in events:
        tiers[HOST._tier_of(ev)].append({"text": ev.get("event", "").rstrip("."), "date": ev.get("date_display", ""),
                                         "cite": ev.get("source", ""), "confidence": ev.get("confidence", ""),
                                         "id": ev["event_id"], "kind": "event"})
    for u in units:
        t = (u.get("tier") or "").lower()
        if t in TIERS and t != "documented":
            tiers[t].append({"text": u["title"], "date": "", "cite": " ".join(f"[{x.split('-')[0]}]" for x in u["spans"][:1]),
                             "id": u["id"], "kind": "unit"})
    for r in records[:60]:
        if r["type"] in ("database entry",) and not r["description"]:
            continue
        tiers["documented"].append({"text": r["title"] if r["origin"] != "knowledge graph" or not r["description"] else r["description"], "date": r.get("date", ""), "cite": r["url"],
                                    "record": r["id"], "kind": "record", "archive": r["archive"]})
    for kid in s["kg"]:
        for rel, other, edge, d in ix["adj"].get(kid, []):
            n = ix["kg_nodes"].get(other) or {}
            if (n.get("type") == "event") and n.get("description"):
                tiers["documented"].append({"text": n["description"], "date": n.get("date", ""), "cite": n.get("cite", "") or n.get("url", ""),
                                            "kind": "record event", "slug": ix["kg_subject"].get(other)})

    passages = []
    for i in s["mention_paras"][:120]:
        p = ix["paras"][i]
        f = ix["session_file"].get(p["session"])
        passages.append({**p, "source": f"audio/{f}" if f else None})
    sources = []
    seen = set()
    for x in s["sources"]:
        if x["id"] in seen:
            continue
        seen.add(x["id"])
        if x["id"].startswith("session:"):
            sid = x["id"][8:]
            f = ix["session_file"].get(sid)
            n = sum(1 for i in s["mention_paras"] if ix["paras"][i]["session"] == sid)
            sources.append({"id": f"audio/{f}", "name": f, "session": sid, "kind": "audio", "thumb": None,
                            "why": f"mentioned {n} time{'s' if n != 1 else ''} in the recording"})
        else:
            row = ix["src_rows"].get(x["id"])
            if row:
                eff = HOST.effective(row)
                sources.append({"id": row["path"], "rid": row["id"], "name": eff.get("accepted_name") or row["original_name"],
                                "kind": row["kind"], "thumb": row.get("thumb"), "why": x["why"]})
    stories = [{"id": sid, "title": ix["stories"][sid]["title"], "state": ix["stories"][sid].get("state")}
               for sid in sorted(s["stories"], key=lambda z: (len(z), z)) if sid in ix["stories"]]

    backlinks = {}
    for grp in related:
        for it in grp["items"]:
            if it.get("slug") and it["slug"] != slug:
                backlinks[it["slug"]] = it
    for oslug, oe in ix["edits"].items():
        if oslug != slug and oslug in subs:
            text = (oe.get("lead") or "") + " " + (oe.get("notes") or "")
            for m in re.finditer(r"\[\[([^\]|]+)", text):
                if norm(m.group(1)) in {norm(k) for k in _keys(s)} | {norm(s["title"])}:
                    o = subs[oslug]
                    backlinks[oslug] = {"slug": oslug, "title": o["title"], "type": o["type"]}
    backlinks = sorted(backlinks.values(), key=lambda b: (TYPES.index(b["type"]), b["title"]))

    open_q = _open_questions(project, ix, s, events, infobox)
    beyond = {"items": e.get("beyond") or [], "suggestions": _beyond_suggestions(project, s)}
    lead = e.get("lead") or _derived_lead(s, infobox, events, units, records, photos, stories, related)
    out = {"slug": slug, "title": s["title"], "type": s["type"], "type_label": TYPE_SINGULAR[s["type"]], "kind": s["kind"],
           "aliases": sorted(s["aliases"]), "stub": s["stub"], "score": s["score"], "origins": sorted(s["origins"]),
           "lead": lead, "lead_by": "me" if e.get("lead") else "derived", "notes": e.get("notes", ""),
           "infobox": infobox, "tiers": tiers, "passages": passages, "mentions": passages,
           "sources": sources, "records": records, "photos": photos, "stories": stories,
           "units": [{"id": u["id"], "title": u["title"], "chapter": u["chapter"]} for u in units],
           "events": [{"id": ev["event_id"], "title": ev.get("event", "").rstrip("."), "date": ev.get("date_display", "")} for ev in events],
           "related": related, "backlinks": backlinks, "open_questions": open_q, "beyond": beyond,
           "coords": s["coords"], "routes": sorted(set(s["routes"])),
           "genealogy": _genealogy_id(project, s) if s["type"] == "person" else None,
           "history": e.get("history", [])[-12:]}
    if s["type"] == "event":
        out.update(_event_extra(project, s))
    return out


def _genealogy_id(project, s):
    names = {norm(s["title"]), *(norm(a) for a in s["aliases"])}
    for f in ("mine", "derived"):
        people = _read_json(project.root / "data" / "genealogy" / f"{f}.json", {}).get("people") or {}
        for pid, p in (people.items() if isinstance(people, dict) else ((x.get("id"), x) for x in people)):
            if isinstance(p, dict) and ({norm(p.get("name"))} | {norm(a) for a in p.get("aliases") or []}) & names:
                return p.get("id") or pid
    return None


def _event_extra(project, s):
    tl = HOST.engine_timeline(project)
    me = next((ev for ev in tl["events"] + tl["undated"] if norm(ev["title"]) == norm(s["title"])), None)
    if not me:
        return {}
    others = [ev for ev in tl["events"] if ev["id"] != me["id"] and set(ev["people"]) & set(me["people"])]
    before = [ev for ev in others if (ev["year"] or 0) < (me["year"] or 0) or (ev["year"] == me["year"] and ev["id"] < me["id"])]
    after = [ev for ev in others if ev not in before]
    passages = [x for x in (HOST._transcript_line(project, c) for c in me["cites"]) if x]
    return {"event": me, "event_passages": passages, "conflicts": [me["conflict"]] if me["conflict"] else [],
            "before": [{"title": ev["title"], "date": ev["date"], "slug": ev["slug"]} for ev in before[-3:]],
            "after": [{"title": ev["title"], "date": ev["date"], "slug": ev["slug"]} for ev in after[:3]]}


def _related(ix, s):
    """Typed relations from the knowledge graph (one hop, and through voyages for vessels), then
    the subjects that share story units or timeline events with this one."""
    subs, adj, kgs, kgn = ix["subs"], ix["adj"], ix["kg_subject"], ix["kg_nodes"]
    groups = {}

    def put(group, slug, note=""):
        if slug and slug in subs and slug != s["slug"]:
            o = subs[slug]
            g = groups.setdefault(group, {})
            if slug not in g:
                g[slug] = {"slug": slug, "title": o["title"], "type": o["type"], "note": note, "stub": o["stub"]}

    for kid in s["kg"]:
        for rel, other, edge, d in adj.get(kid, []):
            if other not in kgs:
                continue
            o = subs.get(kgs[other])
            if not o:
                continue
            label = RELATION_LABELS.get(rel, rel.replace("_", " "))
            note = ", ".join(f"{k} {v}" for k, v in edge.items() if k in ("rank", "age", "date", "residence") and v)
            if s["type"] == "vessel" and rel == "voyage_of":
                put("Voyages", o["slug"])
                for rel2, other2, edge2, d2 in adj.get(other, []):
                    o2 = subs.get(kgs.get(other2, ""))
                    if not o2:
                        continue
                    if rel2 == "master_of":
                        put("Masters", o2["slug"], o["title"])
                    elif rel2 == "crew_on":
                        put("People aboard", o2["slug"], ", ".join(x for x in [o["title"], edge2.get("rank", "")] if x))
                    elif o2["type"] == "place":
                        put("Ports and places", o2["slug"], o["title"])
            elif o["type"] == "place":
                put("Places", o["slug"], label)
            elif o["type"] == "person":
                put({"crew_on": "People aboard", "master_of": "Masters", "served_in": "Members", "member_of": "Members"}
                    .get(rel, "People") if d == "in" else "People", o["slug"], note or label)
            else:
                put(TYPE_LABELS[o["type"]], o["slug"], label)
    for f in s["routes"]:
        tr = next((t for t in ix["tracks"] if t["file"] == f), None)
        if tr and s["slug"] in (tr.get("subjects") or []):
            for r in tr["rows"]:
                pl = ix["by_norm"].get(("place", norm(_clean_place(r.get("place", "")))))
                put("Ports and places", pl, r.get("date", ""))
    if s["type"] == "place":
        for f in dict.fromkeys(s["routes"]):          # a port links back to the ships and voyages whose route it is on
            tr = next((t for t in ix["tracks"] if t["file"] == f), None)
            if tr:
                when = next((r.get("date", "") for r in tr["rows"] if norm(_clean_place(r.get("place", ""))) in {norm(s["title"]), *(norm(a) for a in s["aliases"])}), "")
                for slug in tr.get("subjects") or []:
                    put("On the route of", slug, when)
        for x in s["events"]:
            ev = ix["timeline"].get(x)
            if ev:
                for n in _split_list(ev.get("people")):
                    put("People who were there", ix["by_norm"].get(("person", norm(n))), ev.get("date_display", ""))
                put("Events here", ix["by_norm"].get(("event", norm(ev.get("event", "").rstrip(".")))), ev.get("date_display", ""))
    co = {}
    for u in s["units"]:
        for o in subs.values():
            if o is not s and u in o["units"]:
                co[o["slug"]] = co.get(o["slug"], 0) + 1
    for x in s["events"]:
        for o in subs.values():
            if o is not s and x in o["events"]:
                co[o["slug"]] = co.get(o["slug"], 0) + 1
    for slug, n in sorted(co.items(), key=lambda kv: -kv[1])[:16]:
        if not any(slug in g for g in groups.values()):
            put("Appears alongside", slug, f"{n} shared stor{'y' if n == 1 else 'ies'} or event{'s' if n != 1 else ''}")
    order = ["On the route of", "Voyages", "Masters", "Ports and places", "People aboard", "Members", "People", "People who were there",
             "Events here", "Places"] + list(TYPE_LABELS.values()) + ["Appears alongside"]
    out = []
    for name in sorted(groups, key=lambda g: order.index(g) if g in order else 99):
        items = list(groups[name].values())
        out.append({"group": name, "count": len(items), "items": items[:60]})
    return out


def _vals(*xs):
    return [x for x in xs if x not in (None, "", [])]


def _infobox(ix, s, events, units, records, related, e):
    """One row per field of the type's schema. Each row says whether it is mine or derived, and where it came from."""
    kgn = [ix["kg_nodes"][k] for k in s["kg"] if k in ix["kg_nodes"]]
    attrs = {}
    for n in kgn:
        for k, v in n.items():
            if k not in ("id", "type", "label") and v not in (None, ""):
                attrs.setdefault(k.lower(), v)
        attrs.update({k.lower(): v for k, v in _parse_metadata(n.get("metadata")).items() if v})
    rel = {g["group"]: g["items"] for g in related}
    years = sorted({y for ev in events for y in _years(ev.get("date_start") or ev.get("date_display"))})
    span = (f"{years[0]}–{years[-1]}" if len(years) > 1 else str(years[0])) if years else ""
    links = lambda items: [{"text": i["title"], "slug": i["slug"], "note": i.get("note", "")} for i in items]
    t = s["type"]
    rows = {}

    def put(label, value, basis="", many=False):
        if value in (None, "", []):
            return
        rows[label] = {"label": label, "values": value if many else [{"text": str(value)}], "by": "derived", "basis": basis}

    if t == "person":
        put("Also called", ", ".join(sorted(s["aliases"])), "profile and my aliases")
        if s["profile"]:
            put("Relationship", s["profile"]["relationship"], s["profile"]["file"])
            put("Dates", s["profile"]["dates"], s["profile"]["file"])
        if "Dates" not in rows:
            put("Dates", span, "timeline")
        put("Places", links(rel.get("Places", [])) or [{"text": p} for p in sorted({ev.get("place") for ev in events if ev.get("place")})], "timeline and records", many=True)
        put("Served in", links([i for i in rel.get(TYPE_LABELS["organization"], [])]), "records", many=True)
        aboard = [i for g, items in rel.items() for i in items if i["type"] == "event" and "aboard" in (i.get("note") or "")]
        put("Aboard", links(aboard), "crew lists", many=True)
        put("Occupation", links(rel.get(TYPE_LABELS["occupation"], [])), "", many=True)
    elif t == "place":
        c = s["coords"]
        put("Location", f"{c['lat']:.2f}, {c['lon']:.2f} ({c['basis']})" if c else "", (c or {}).get("source", ""))
        parts = [p.strip() for p in s["title"].split(",")]
        put("Region", parts[-1] if len(parts) > 1 else attrs.get("region", ""), "from the name" if len(parts) > 1 else "records")
        kinds = sorted({(r.get("kind") or "").strip() for tr in ix["tracks"] for r in tr["rows"]
                        if norm(_clean_place(r.get("place", ""))) == norm(s["title"]) and (r.get("kind") or "").strip()})
        put("What it was", attrs.get("kind") or attrs.get("what", "") or (", ".join(kinds) + " (in the voyage records)" if kinds else ""), "records")
        put("Years in the story", span, "timeline")
        put("Map", "on the map" if c else "", "")
        put("Who lived or worked there", links(rel.get("People who were there", []) + rel.get("People", [])), "timeline and records", many=True)
    elif t == "vessel":
        label = s["title"]
        vt = re.match(r"^(ship|bark|barque|brig|schooner|sloop|steamship|steamer|uss|whaleship)\b", label, re.I)
        put("Type", attrs.get("rig") or attrs.get("vessel_type") or (vt.group(1).lower() if vt else "") or s["kind"], "records")
        put("Tonnage", attrs.get("tonnage", ""), attrs.get("url", "records"))
        put("Built", attrs.get("built", ""), attrs.get("url", "records"))
        put("Owner", attrs.get("owner") or attrs.get("agent", ""), attrs.get("url", "records"))
        put("Master", links(rel.get("Masters", [])), "crew lists", many=True)
        reg = re.search(r"\bof ([A-Z][\w .]+?)(?: \(|$)", label)
        put("Registry", attrs.get("registry") or attrs.get("port") or (reg.group(1) if reg else ""), "records" if attrs.get("registry") else "from the name")
        put("Fate", attrs.get("fate") or attrs.get("end", ""), attrs.get("url", "records"))
        vy = [i for i in rel.get("Voyages", [])]
        put("Voyage dates", [{"text": i["title"], "slug": i["slug"]} for i in vy], "voyage records", many=True)
    elif t == "organization":
        put("Full name", attrs.get("full_name") or s["title"], "records")
        put("What it was", attrs.get("what") or s["kind"] or attrs.get("description", ""), "records")
        put("The family's connection", span, "timeline")
        fam = [i for i in rel.get("Members", []) + rel.get("People", []) if _is_family(ix, i["slug"])]
        put("Members in the family", links(fam), "records", many=True)
    elif t == "object":
        put("What it is", attrs.get("description") or attrs.get("collection") or s["kind"], attrs.get("url", "records"))
        yr = " to ".join(_vals(attrs.get("year range from"), attrs.get("year range to")))
        put("Dates", yr or attrs.get("date", "") or span, "records")
        put("Made or owned by", links(rel.get("People", [])), "records", many=True)
        held = [r for r in records if r.get("archive")]
        put("Where it is now", [{"text": held[0]["archive"], "record": held[0]["id"]}] if held else "", "records index", many=True)
        status = next((r.get("status") for r in records if r.get("status")), "")
        put("Survives", {"lost": "no (lost)", "destroyed": "no (destroyed)", "institutional": "yes (held by an institution)",
                         "confirmed": "yes"}.get(status, "unknown") if (status or held) else "", "records catalogue")
    elif t == "event":
        ev = events[0] if len(events) == 1 else next((x for x in events if norm(x.get("event", "").rstrip(".")) == norm(s["title"])), None)
        if ev:
            put("Date", ev.get("date_display", ""), ev.get("source", ""))
            put("Precision", ev.get("precision", ""), ev.get("date_basis", ""))
            pl = ev.get("place")
            if pl:
                put("Place", [{"text": pl, "slug": ix["by_norm"].get(("place", norm(pl)))}], "timeline", many=True)
            put("People", [{"text": n, "slug": ix["by_norm"].get(("person", norm(n)))} for n in _split_list(ev.get("people"))], "timeline", many=True)
            put("Kind", HOST._event_type(ev.get("event", "")), "derived from the wording")
        else:
            put("Date", attrs.get("date", ""), attrs.get("cite", "records"))
            put("Kind", s["kind"] or "", "")
            put("People", links(rel.get("People aboard", []) + rel.get("People", []))[:30], "records", many=True)
    else:
        put("What it is", attrs.get("description") or s["kind"], "")
        put("When it appears", span, "timeline")
        people = [i for items in rel.values() for i in items if i["type"] == "person"]
        put("Who it touches", links(people[:20]), "", many=True)
    box = e.get("infobox") or {}
    if not isinstance(box, dict):            # older projects store [label, value] pairs
        box = {r[0]: r[1] for r in box if isinstance(r, (list, tuple)) and len(r) >= 2}
    for label, v in box.items():
        if v not in (None, ""):
            rows[label] = {"label": label, "values": [{"text": str(v)}], "by": "me", "basis": "stated by me"}
    schema = INFOBOX[t]
    return [rows.get(f) or {"label": f, "values": [], "by": "derived", "basis": "not in the material"} for f in schema] + \
           [r for k, r in rows.items() if k not in schema]


def _is_family(ix, slug):
    s = ix["subs"].get(slug)
    return bool(s and (s["units"] or s["mention_paras"] or s["profile"] or
                       any(ix["timeline"].get(x, {}).get("generation") for x in s["events"])))


def _derived_lead(s, infobox, events, units, records, photos, stories, related):
    """Plain sentences assembled from the infobox and the counts. No adjectives, nothing inferred."""
    facts = []
    for row in infobox:
        if row["values"] and row["label"] not in ("Map", "Also called", "Who lived or worked there", "People aboard",
                                                    "Members in the family", "Made or owned by", "Who it touches", "Voyage dates", "People", "Places", "Served in", "Aboard"):
            facts.append(f"{row['label'].lower()}: " + "; ".join(v["text"] for v in row["values"][:3]))
    counts = []
    for n, word in ((len(stories), "stor"), (len(units), "story unit"), (len(events), "timeline event"),
                    (len(records), "record"), (len(photos), "image")):
        if n:
            counts.append(f"{n} {word + ('y' if n == 1 else 'ies') if word == 'stor' else word + ('s' if n != 1 else '')}")
    if s["mention_paras"]:
        counts.append(f"{len(s['mention_paras'])} passage{'s' if len(s['mention_paras']) != 1 else ''} of the recordings")
    lead = f"{s['title']} ({TYPE_SINGULAR[s['type']]}{', ' + s['kind'] if s['kind'] else ''})."
    if facts:
        lead += " " + "; ".join(facts)[:420] + "."
    if counts:
        lead += " The material has " + ", ".join(counts) + "."
    else:
        lead += " The material names it once and says no more yet."
    return lead


def _open_questions(project, ix, s, events, infobox):
    out = []
    keys = _keys(s)
    gaps = project.root / "facts" / "gaps.md"
    if gaps.exists():
        for line in gaps.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip().startswith(("-", "|", "*")) and any(k in line for k in keys):
                out.append({"text": re.sub(r"[*`|]+", " ", line).strip(" -"), "from": "facts/gaps.md"})
    for ev in events:
        if (ev.get("confidence") or "").lower() == "low":
            out.append({"text": f"{ev.get('event', '').rstrip('.')}: low confidence ({ev.get('date_basis', '')[:140]})", "from": ev["event_id"]})
        if (ev.get("conflicts") or "").strip():
            out.append({"text": f"The sources disagree: {ev['conflicts']}", "from": ev["event_id"]})
    missing = [r["label"] for r in infobox if not r["values"] and r["label"] not in ("Map",)]
    if missing and s["type"] not in ("person", "event"):
        out.append({"text": "Not in the material yet: " + ", ".join(m.lower() for m in missing[:6]) + ".", "from": "infobox"})
    if s["stub"]:
        out.append({"text": f"Only a passing mention so far. Ask about {s['title']} in the next recording, or tag a source to it.",
                    "from": "stub"})
    return out[:20]


def _beyond_suggestions(project, s):
    keys = _keys(s)
    out = []
    for c in _context_lines(project):
        if any(k in c["text"] for k in keys):
            urls = re.findall(r"https?://[^\s)\]>]+", c["text"])
            out.append({"text": c["text"][:400], "url": urls[0] if urls else "", "file": c["file"]})
    return out[:12]


# ------------------------------------------------------------------------------- edits, subjects, tags
def save_edit(project, slug, patch):
    fp = _fp(project)
    p = fp / f"{slug}.json"
    cur = _read_json(p, {})
    fields = []
    for k in ("lead", "notes", "infobox", "aliases", "type", "kind", "coords", "beyond", "same_as"):
        if k in patch:
            if k == "type" and patch[k] not in TYPES:
                raise ValueError(f"type must be one of {', '.join(TYPES)}")
            cur[k] = patch[k]
            fields.append(k)
    cur.setdefault("history", []).append({"at": _now(), "by": "me", "fields": fields})
    _write_json(p, cur)
    invalidate(project)
    return cur


def new_subject(project, title, typ, aliases=None, kind=""):
    title = re.sub(r"\s+", " ", (title or "").strip())
    if not title:
        raise ValueError("a subject needs a name")
    if typ not in TYPES:
        raise ValueError(f"type must be one of {', '.join(TYPES)}")
    ix = index(project)
    existing = ix["by_norm"].get((typ, norm(title)))
    if existing:
        return {"slug": existing, "created": False}
    p = _fp(project) / "subjects.json"
    cur = _read_json(p, {})
    slug = slugify(title)
    if slug in ix["subs"]:
        slug = f"{slug}-{typ}"
    cur[slug] = {"title": title, "type": typ, "kind": kind, "aliases": aliases or [], "created": _now(), "by": "me"}
    _write_json(p, cur)
    invalidate(project)
    return {"slug": slug, "created": True}


def _target_text(project, ix, target):
    kind, _, tid = target.partition(":")
    if kind == "source":
        row = ix["src_rows"].get(tid)
        if not row:
            return ""
        eff = HOST.effective(row)
        parts = [eff.get("summary") or "", " ; ".join(eff.get("people") or []), " ; ".join(eff.get("places") or []),
                 " ; ".join(eff.get("organizations") or []), " ".join(str(v) for v in (row.get("fields") or {}).values()), row.get("notes") or ""]
        ex = project.root / (row.get("extracted") or "")
        if row.get("extracted") and ex.is_file():
            parts.append(ex.read_text(encoding="utf-8", errors="ignore")[:40000])
        if (row.get("mine") or {}).get("text"):
            parts.append(row["mine"]["text"][:40000])
        return "\n".join(parts)
    if kind == "record":
        r = ix["records"].get(tid)
        return " ".join([r["title"], r["description"], r.get("archive", "")]) if r else ""
    if kind == "photo":
        p = ix["photos"].get(tid)
        return " ".join([p.get("caption", ""), p.get("people", ""), p.get("location", "")]) if p else ""
    if kind == "event":
        e = ix["timeline"].get(tid)
        return " ".join([e.get("event", ""), e.get("people", ""), e.get("place", ""), e.get("quote", "")]) if e else ""
    return ""


def suggest(project, target):
    """Subjects whose names appear in the item, each with the passage that names it. Never from faces
    or from guesses: a suggestion exists only where the name is written in the item."""
    ix = index(project)
    text = _target_text(project, ix, target)
    have = {t["subject"] for t in ix["tags"].get(target, [])}
    if target.startswith("event:") and target[6:] in ix["timeline"]:   # an event doesn't suggest itself
        have.add(ix["by_norm"].get(("event", norm(ix["timeline"][target[6:]].get("event", "").rstrip("."))), ""))
    out = {}
    if ix["rx"] and text:
        for m in ix["rx"].finditer(text):
            for slug in ix["keys"].get(m.group(1), ()):
                if slug in have or slug in out:
                    continue
                a, b = max(0, m.start() - 70), min(len(text), m.end() + 70)
                s = ix["subs"][slug]
                out[slug] = {"subject": slug, "title": s["title"], "type": s["type"], "state": "suggested", "by": "derived",
                             "evidence": f"names “{m.group(1)}”: …{text[a:b].strip()}…"}
    return list(out.values())[:40]


def tags_for(project, target):
    ix = index(project)
    tl = []
    for t in ix["tags"].get(target, []):
        s = ix["subs"].get(ix["merged"].get(t["subject"], t["subject"]))
        tl.append({**t, "title": s["title"] if s else t["subject"], "type": s["type"] if s else "", "missing": not s})
    return {"target": target, "tags": tl, "suggestions": suggest(project, target)}


def set_tags(project, targets, subject, state="accepted", evidence="", by="me"):
    if state not in TAG_STATES:
        raise ValueError(f"state must be one of {', '.join(TAG_STATES)}")
    p = _fp(project) / "tags.json"
    with _LOCK:
        cur = _read_json(p, {})
        for target in targets:
            lst = cur.setdefault(target, [])
            t = next((x for x in lst if x["subject"] == subject), None)
            if t:
                t.update(state=state, at=_now(), by=by)
                if evidence:
                    t["evidence"] = evidence
            else:
                lst.append({"subject": subject, "state": state, "evidence": evidence, "by": by, "at": _now()})
        _write_json(p, cur)
    invalidate(project)
    return {"ok": True, "targets": len(targets)}


def picker(project, q="", limit=12):
    """Subjects grouped by type for the tagger, best matches first."""
    ix = index(project)
    qn = norm(q)
    groups = {t: [] for t in TYPES}
    for s in ix["subs"].values():
        hay = norm(" ".join([s["title"], *s["aliases"]]))
        if qn and qn not in hay:
            continue
        groups[s["type"]].append(s)
    out = []
    for t in TYPES:
        items = sorted(groups[t], key=lambda s: (not norm(s["title"]).startswith(qn), -s["score"], s["title"].lower()))
        if items:
            out.append({"type": t, "label": TYPE_LABELS[t], "count": len(items),
                        "items": [{"slug": s["slug"], "title": s["title"], "kind": s["kind"], "stub": s["stub"]} for s in items[:limit]]})
    return out


def catalogue(project, what):
    """The records or the photographs, each with its subjects, for browsing and bulk tagging."""
    ix = index(project)
    name = lambda slug: {"slug": slug, "title": ix["subs"][slug]["title"], "type": ix["subs"][slug]["type"]} if slug in ix["subs"] else None
    if what == "records":
        rows = sorted(ix["records"].values(), key=lambda r: (r["type"], r.get("date") or "", r["title"]))
        return [{**r, "subjects": [x for x in map(name, r["subjects"]) if x]} for r in rows]
    rows = sorted(ix["photos"].values(), key=lambda p: (p.get("id") or ""))
    return [{**p, "subjects": [x for x in map(name, p["subjects"]) if x]} for p in rows]


def story_subjects(project, story_id):
    ix = index(project)
    out = [s for s in ix["subs"].values() if story_id in s["stories"]]
    return sorted(({"slug": s["slug"], "title": s["title"], "type": s["type"]} for s in out),
                  key=lambda x: (TYPES.index(x["type"]), x["title"]))


def event_subjects(project):
    """event id -> the articles it touches (beyond its people and place), for the Timeline."""
    ix = index(project)
    out = {}
    for s in ix["subs"].values():
        for x in s["events"]:
            out.setdefault(x, []).append({"slug": s["slug"], "title": s["title"], "type": s["type"]})
    return out


# ------------------------------------------------------------------------------- the map
def _land(project):
    for g in ("facts/records/_raw/geo/*.geojson", "facts/records/sources/geo/*.geojson", "data/geo/*.geojson"):
        for p in sorted(project.root.glob(g)):
            d = _read_json(p, None)
            if d and d.get("features"):
                return d, p.relative_to(project.root).as_posix()
    return None, None


def map_data(project, focus=None):
    """Places with coordinates and the routes, drawn with the voyage map's evidence coding:
    recorded positions solid, approximations dashed, unrecorded legs labelled as not recorded."""
    ix = index(project)
    subs = ix["subs"]
    focus_s = subs.get(ix["merged"].get(focus, focus)) if focus else None
    places = []
    for s in subs.values():
        if s["type"] == "place" and s["coords"]:
            places.append({"slug": s["slug"], "title": s["title"], **s["coords"], "score": s["score"]})
    tracks = []
    for tr in ix["tracks"]:
        if not tr["has_coords"]:
            continue
        if focus_s and focus_s["slug"] not in (tr.get("subjects") or []) and focus_s["type"] != "place":
            continue
        pts = []
        prev_leg = None
        for i, r in enumerate(tr["rows"]):
            lat, lon = (r.get("lat") or "").strip(), (r.get("lon") or "").strip()
            leg = (r.get("leg") or "").strip()
            gap = str(r.get("gap_before") or "").lower() in ("yes", "true", "1") or (prev_leg is not None and leg and leg != prev_leg)
            if leg:
                prev_leg = leg
            if not lat or not lon:
                pts.append({"gap": True})
                continue
            try:
                pts.append({"lat": float(lat), "lon": float(lon), "place": r.get("place", ""), "date": r.get("date", ""),
                            "kind": (r.get("kind") or "position").lower(), "aboard": (r.get("aboard") or "subject"),
                            "gap_before": gap, "source": r.get("source", ""), "note": r.get("note", ""),
                            "slug": ix["by_norm"].get(("place", norm(_clean_place(r.get("place", "")))))})
            except ValueError:
                pts.append({"gap": True})
        tracks.append({"file": tr["file"], "subjects": [{"slug": x, "title": subs[x]["title"]} for x in tr.get("subjects") or [] if x in subs],
                       "points": pts})
    if focus_s and focus_s["type"] == "place":
        places = [p for p in places if p["slug"] == focus_s["slug"]] or places
    missing = sorted(s["title"] for s in subs.values() if s["type"] == "place" and not s["coords"])
    unattached = [t["file"] for t in ix["tracks"] if not t.get("subjects")]
    svg, land_file = _map_svg(project, places, tracks)
    return {"svg": svg, "places": places, "tracks": [{"file": t["file"], "subjects": t["subjects"],
                                                       "points": sum(1 for p in t["points"] if not p.get("gap"))} for t in tracks],
            "not_on_map": missing, "unattached_routes": unattached, "land": land_file}


def _map_svg(project, places, tracks):
    pts = [(p["lon"], p["lat"]) for p in places] + [(q["lon"], q["lat"]) for t in tracks for q in t["points"] if not q.get("gap")]
    if not pts:
        return "", None
    lons = [x for x, _ in pts]
    shift = (max(lons) - min(lons)) > 180  # crosses the antimeridian: work in 0..360
    X = (lambda lon: lon % 360) if shift else (lambda lon: lon)
    xs = [X(x) for x, _ in pts]
    ys = [y for _, y in pts]
    pad_x = max(4, (max(xs) - min(xs)) * 0.08)
    pad_y = max(3, (max(ys) - min(ys)) * 0.1)
    w0, e0, s0, n0 = min(xs) - pad_x, max(xs) + pad_x, max(-85, min(ys) - pad_y), min(85, max(ys) + pad_y)
    W = 1000
    H = max(260, min(700, int(W * (n0 - s0) / max(e0 - w0, 1) * 1.15)))
    px = lambda lon: (X(lon) - w0) / (e0 - w0) * W
    py = lambda lat: (n0 - lat) / (n0 - s0) * H
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" class="fp-map" role="img" aria-label="Map of the places and routes in the records">',
           f'<rect width="{W}" height="{H}" class="sea"/>']
    land, land_file = _land(project)
    if land:
        paths = []
        for f in land["features"]:
            g = f.get("geometry") or {}
            polys = g.get("coordinates") or []
            polys = [polys] if g.get("type") == "Polygon" else polys
            for poly in polys:
                for ring in poly[:1]:
                    seg, last = [], None
                    for lon, lat in ring:
                        x = X(lon)
                        if x < w0 - 25 or x > e0 + 25 or lat < s0 - 25 or lat > n0 + 25:
                            continue
                        sx, sy = (x - w0) / (e0 - w0) * W, (n0 - lat) / (n0 - s0) * H
                        if last and abs(sx - last[0]) > W / 2:      # wrapped round the globe: start afresh
                            if len(seg) > 2:
                                paths.append("M" + "L".join(seg) + "Z")
                            seg, last = [], None
                        if last and abs(sx - last[0]) < 1.2 and abs(sy - last[1]) < 1.2:
                            continue
                        seg.append(f"{sx:.1f},{sy:.1f}")
                        last = (sx, sy)
                    if len(seg) > 2:
                        paths.append("M" + "L".join(seg) + "Z")
        out.append(f'<path class="land" d="{"".join(paths)}"/>')
    for t in tracks:
        # Between two recorded positions the line is dashed (the track between them is approximate).
        # A leg with no record (a row without coordinates, gap_before, or a new leg) gets no line, only a label.
        last, gap = None, False
        for q in t["points"]:
            if q.get("gap"):
                gap = True
                continue
            if last:
                x1, y1, x2, y2 = px(last["lon"]), py(last["lat"]), px(q["lon"]), py(q["lat"])
                if gap or q["gap_before"]:
                    out.append(f'<text class="gap" x="{(x1 + x2) / 2:.1f}" y="{(y1 + y2) / 2 - 4:.1f}" text-anchor="middle">not recorded</text>')
                else:
                    out.append(f'<line class="leg" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')
            last, gap = q, False
        for q in t["points"]:
            if q.get("gap") or q["kind"] in ("waypoint", "text", "area"):
                continue
            cls = "rec" if q["aboard"].lower() not in ("ship", "other", "no") else "open"
            title = f'{q["place"]} {q["date"]} · {q["source"]}'.replace('"', "'").replace("<", "")
            dot = f'<circle class="{cls}" cx="{px(q["lon"]):.1f}" cy="{py(q["lat"]):.1f}" r="4"><title>{title}</title></circle>'
            out.append(f'<a href="#familypedia/{q["slug"]}">{dot}</a>' if q.get("slug") else dot)
    for p in places:
        cls = "place" if p["basis"] == "recorded" else "place approx"
        x, y = px(p["lon"]), py(p["lat"])
        title = f'{p["title"]} · {p["basis"]} · {p.get("source", "")}'.replace('"', "'").replace("<", "")
        out.append(f'<a href="#familypedia/{p["slug"]}"><circle class="{cls}" cx="{x:.1f}" cy="{y:.1f}" r="5"><title>{title}</title></circle>'
                   f'<text class="lbl" x="{x + 7:.1f}" y="{y + 4:.1f}">{p["title"].split(",")[0].replace("<", "")}</text></a>')
    out.append("</svg>")
    return "".join(out), land_file
