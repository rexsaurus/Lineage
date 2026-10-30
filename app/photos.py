"""The photo registry: one entry per photograph, for the photo viewer and every grid that shows pictures.

A photograph can reach the project several times: a row in photos/photo_index.csv, an image in Sources, a chosen
portrait, a copy under work/lineage-assets/, its unretouched original (`_orig/`) and its digital restoration. Here they
collapse into one entry with two renderings at most (restored and original). Grids show one tile per entry; the viewer
carries the flip between the two.

Facts come only from the project, in this order, and nothing is invented:
  data/photo_details.csv    photo (a path or a photo id), title, description, date, place, institution, reference,
                            url, kind (portrait, group, document, place)  -- stated by the owner
  data/image_sources.csv    path, url, title, creator, date, rights        -- where a downloaded image came from
  data/image_catalog.csv    key, path, sha256, width, height, chapters, captions, source_url  (image_manager.py)
  the catalogue rows        captions, dates, places, subjects
  data/photo_backfill.json  written by plugins/lineage/scripts/photo_backfill.py: the full-size file found for a
                            low-resolution one, or "not_located"
A file name or path is never a title: a caption that is one is dropped, and the title falls back to who and when.
"""
import csv
import json
import re
from pathlib import Path

import familypedia as fp

LOW_RES = 1200          # longest edge, in pixels, below which a scan counts as low resolution
_CACHE = {}
IMG = re.compile(r"\.(jpe?g|png|gif|webp|tiff?)$", re.I)
DOC = re.compile(r"clipping|newspaper|directory|deed|record|register|census|certificate|yearbook|catalog|patent|court|"
                 r"letter|page|card|form|ledger|roll|report|notice|obituary|article|advert|index|diagram|map\b|scan|"
                 r"transcript|minutes|program|journal|argus|beacon|docket|licen[cs]e|births|schedule|staff box|"
                 r"\bp\. ?\d|nominal|embarkation|application|file\b|issue\b|edition", re.I)
GROUP = re.compile(r"battalion|company|regiment|class of|\bclass\b|family|friends|group|team|ranks|crew|party|reunion|"
                   r"brothers|sisters|and his|and her|with his|with her|students|staff\b|members", re.I)
PLACE = re.compile(r"cabin|house|farm|street|church|school|homestead|cemetery|mill|town|view of|bridge|station|"
                   r"campus|building|harbou?r|lake|river|island|hall\b|shop\b|store\b|camp\b", re.I)


def _csv(p):
    return list(csv.DictReader(open(p, encoding="utf-8"))) if p.is_file() else []


def _json(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else default
    except Exception:
        return default


def key(path):
    """A path as the registry knows it: no leading slash, no query, no work/lineage-assets/ copy prefix."""
    p = str(path or "").split("?")[0].lstrip("/")
    return p[len("work/lineage-assets/"):] if p.startswith("work/lineage-assets/") else p


def _inputs(project):
    r = project.root
    files = [r / "data" / n for n in ("photo_details.csv", "image_sources.csv", "image_catalog.csv",
                                      "image_restorations.json", "photo_backfill.json")]
    return (fp._inputs(project), tuple(f.stat().st_mtime if f.exists() else 0 for f in files))


def registry(project):
    sig = _inputs(project)
    c = _CACHE.get(str(project.root))
    if c and c[0] == sig:
        return c[1]
    built = _build(project)
    _CACHE[str(project.root)] = (sig, built)
    return built


def _meta(project, files):
    """path -> (width, height, dhash) for the files the catalogue doesn't size; cached in .lineage/photo_meta.json."""
    cf = project.root / ".lineage" / "photo_meta.json"
    cache, out, dirty = _json(cf, {}), {}, False
    try:
        from PIL import Image
    except Exception:
        Image = None
    for rel in files:
        f = project.root / rel
        try:
            st = f.stat()
        except OSError:
            continue
        stamp = f"{st.st_mtime:.0f}:{st.st_size}"
        hit = cache.get(rel)
        if hit and hit[0] == stamp:
            out[rel] = tuple(hit[1:])
            continue
        if Image is None:
            continue
        try:
            with Image.open(f) as im:
                w, h = im.size
                im.draft("L", (64, 64))
                g = im.convert("L").resize((9, 8))
                px = list(g.getdata())
            bits = 0
            for r_ in range(8):
                for c_ in range(8):
                    bits = (bits << 1) | (px[r_ * 9 + c_] > px[r_ * 9 + c_ + 1])
        except Exception:
            continue
        out[rel] = (w, h, bits)
        cache[rel] = [stamp, w, h, bits]
        dirty = True
    if dirty:
        try:
            cf.parent.mkdir(parents=True, exist_ok=True)
            cf.write_text(json.dumps(cache), encoding="utf-8")
        except OSError:
            pass
    return out


def _clean(caption):
    """A caption fit to show, or '' when it is a file name, a path or bookkeeping."""
    c = re.sub(r"\s+", " ", str(caption or "")).strip()
    c = re.sub(r"^the unretouched original\.?\s*\((.*)\)\s*$", r"\1", c, flags=re.I)
    c = re.sub(r"\s*\((digitally restored|restored|the same|crop)\)\s*$", "", c, flags=re.I)
    c = re.sub(r";?\s*digitally restored\b", "", c, flags=re.I).replace("()", "").strip()
    c = re.sub(r"\s*\[(in the book|inferred)\]\s*$", "", c, flags=re.I)
    if not c or re.match(r"source file\b", c, re.I) or IMG.search(c.split()[-1] if c.split() else c) \
            or ("/" in c and " " not in c) or re.fullmatch(r"[\w.-]+", c) and not re.search(r"[a-z]{3,} [a-z]", c):
        return ""
    return c


def _short(text, n=90):
    """A title from a long caption: the first clause, cut at a word."""
    if len(text) <= n:
        return text
    m = re.match(r"(.{25,%d}?)[:;.](\s|$)" % n, text)
    if m:
        return m.group(1).strip()
    return text[:n].rsplit(" ", 1)[0].rstrip(",;: ") + "…"


def _build(project):
    root = project.root
    cat = fp.catalogue(project, "photos")
    ix = fp.index(project)
    details = {}
    for r in _csv(root / "data" / "photo_details.csv"):
        k = (r.get("photo") or "").strip()
        if k:
            details[key(k)] = {a: (b or "").strip() for a, b in r.items()}
    sources = {key(r.get("path")): r for r in _csv(root / "data" / "image_sources.csv") if r.get("path")}
    icat = {}
    for r in _csv(root / "data" / "image_catalog.csv"):
        if r.get("path"):
            icat[key(r["path"])] = r
    restorations = {key(k): key(v.get("orig")) for k, v in _json(root / "data" / "image_restorations.json", {}).items()
                    if isinstance(v, dict) and v.get("orig")}
    backfill = {key(k): v for k, v in _json(root / "data" / "photo_backfill.json", {}).items()}

    # 1. every catalogue row, with the file it shows
    rows = []
    for it in cat:
        th = (it.get("thumb") or "").lstrip("/")
        prov = it.get("provenance") or ""
        src = prov[len("source: "):] if prov.startswith("source: ") else ""
        main = src or th
        if not main or not IMG.search(main.split("?")[0]):
            continue
        real = next((c for c in (main, "work/lineage-assets/" + key(main), key(main)) if (root / c).is_file()), None)
        if not real:
            continue
        rows.append({"it": it, "path": real, "alias": {th, main, real, key(real)} - {""}})

    # 2. group: same file, restoration and its original, same bytes, near-identical picture
    parent = {}
    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    real_of = {}
    for r in rows:
        k = key(r["path"])
        real_of.setdefault(k, r["path"])
        find(k)
    for rest, orig in restorations.items():
        for k in (rest, orig):
            if k not in real_of:
                f = next((c for c in (k, "work/lineage-assets/" + k) if (root / c).is_file()), None)
                if f:
                    real_of[k] = f
        if rest in real_of and orig in real_of:
            union(rest, orig)
    for k in list(real_of):
        m = re.match(r"(.*)/_orig/([^/]+)$", k)
        if m:
            stem, ext = m.group(2).rsplit(".", 1) if "." in m.group(2) else (m.group(2), "")
            for twin in (f"{m.group(1)}/{m.group(2)}", f"{m.group(1)}/{stem}-restored.{ext}"):
                if twin in real_of:
                    union(twin, k)
                    restorations.setdefault(twin, k)
    by_sha = {}
    for k in real_of:
        sha = (icat.get(k) or {}).get("sha256")
        if sha:
            if sha in by_sha:
                union(by_sha[sha], k)
            else:
                by_sha[sha] = k
    sizes = {}
    need = []
    for k, f in real_of.items():
        r = icat.get(k)
        if r and (r.get("width") or "").isdigit() and (r.get("height") or "").isdigit():
            sizes[k] = (int(r["width"]), int(r["height"]), None)
        need.append(f)
    meta = _meta(project, need)
    for k, f in real_of.items():
        m = meta.get(f)
        if m:
            sizes[k] = (sizes.get(k, m)[0], sizes.get(k, m)[1], m[2])
    hashed = [(k, s) for k, s in sizes.items() if s[2] is not None]
    for i, (a, sa) in enumerate(hashed):
        for b, sb in hashed[i + 1:]:
            if find(a) == find(b) or bin(sa[2] ^ sb[2]).count("1") > 3:
                continue
            if abs(sa[0] / max(sa[1], 1) - sb[0] / max(sb[1], 1)) <= 0.02 * (sa[0] / max(sa[1], 1)):
                union(a, b)

    groups = {}
    for k in real_of:
        groups.setdefault(find(k), []).append(k)
    rows_by_group = {}
    for r in rows:
        rows_by_group.setdefault(find(key(r["path"])), []).append(r)

    # where each file is used: chapters (story files that name it), timeline entries
    story_uses = {}
    try:
        for st in fp.HOST.engine_stories(project):
            f = root / st["file"] if st.get("file") else None
            if f and f.is_file():
                for m in re.finditer(r"[\"(]/?([\w./ ()-]+?\.(?:jpe?g|png|webp|gif))[\")]", f.read_text(encoding="utf-8", errors="ignore"), re.I):
                    story_uses.setdefault(key(m.group(1)), {})[st["id"]] = st["title"]
    except Exception:
        pass
    timeline_uses = {}
    try:
        for e in (fp.HOST.engine_timeline(project).get("events") or []):
            if e.get("photo"):
                timeline_uses.setdefault(key(e["photo"]), []).append(e)
    except Exception:
        pass
    article_photo = {}
    for s in ix["subs"].values():
        for pid in s.get("photos") or []:
            article_photo.setdefault(pid, {})[s["slug"]] = s["title"]

    out = []
    for g, members in groups.items():
        grows = rows_by_group.get(g, [])
        if not grows:
            continue
        restored = next((k for k in members if k in restorations), None) or next((k for k in members if "-restored" in k), None)
        original = restorations.get(restored) if restored else None
        if restored and original not in members:
            original = next((k for k in members if "/_orig/" in k), None)
        if restored and not original:
            restored = None
        def area(k):
            s = sizes.get(k)
            return s[0] * s[1] if s else 0
        if restored:
            image = restored
        else:
            plain = [k for k in members if "/_orig/" not in k] or members
            image = max(plain, key=area)
        scan = original or image
        its = [r["it"] for r in grows]
        illus = all(it.get("illustration") for it in its)
        det = next((details[k] for k in members if k in details), None) or \
            next((details[it["id"]] for it in its if it.get("id") in details), None) or {}
        srcrow = next((sources[k] for k in members if k in sources), {})
        crow = next((icat[k] for k in (image, scan) if k in icat), None) or next((icat[k] for k in members if k in icat), {})
        # title and description
        caps = []
        for c in [det.get("title"), srcrow.get("title")] + [c for k in members for c in ((icat.get(k) or {}).get("captions") or "").split(" | ")] \
                + [it.get("caption") for it in its]:
            c = _clean(c)
            if c and c not in caps:
                caps.append(c)
        people = {}
        places = {}
        other = {}
        for it in its:
            for s in it.get("subjects") or []:
                (people if s["type"] == "person" else places if s["type"] == "place" else other)[s["slug"]] = s["title"]
        def _d(v):
            return re.sub(r"\s*\((scene|about)\)\s*$", "", v or "").strip()
        date = det.get("date") or next((_d(it.get("date")) for it in its if it.get("date") and it.get("origin") == "photo index"), "")
        place = det.get("place") or next((re.sub(r"\s*\(scene\)\s*$", "", it.get("location") or "") for it in its if it.get("location")), "") \
            or (next(iter(places.values())) if places else "")
        if not illus:
            caps = [re.sub(r"^(illustration|photograph):\s*", "", c, flags=re.I) for c in caps]
            caps = [c[0].upper() + c[1:] for c in caps if c]
        title = det.get("title") or (_short(caps[0]) if caps else "")
        credit = re.search(r"\s*\(([^()]*(?:Digest|Press|Library|Museum|Archives?|Society|Times|Journal|Courier|JSTOR|Company|University|College)[^()]*)\)\s*$", title)
        if credit:
            title = title[:credit.start()].strip()
        if not date:
            m = re.search(r"\b((?:about |c\. ?)?(?:\d{1,2} )?(?:January|February|March|April|May|June|July|August|September|October|November|December)? ?(?:1[6-9]|20)\d{2}s?)\b", title)
            date = m.group(1).strip() if m else ""
        date = date or next((_d(it.get("date")) for it in its if it.get("date")), "") or srcrow.get("date") or ""
        if not title:
            who = ", ".join(list(people.values())[:2])
            title = (who or ("Photograph of " + place if place else "Untitled photograph")) + (f", {date}" if date and who else "")
        desc = det.get("description") or next((c for c in caps if len(c) > len(title) + 15), "")
        if desc.startswith(title.rstrip("…")):
            desc = desc if len(desc) > len(title) + 15 else ""
        # source: who holds it, its reference, its page
        inst = det.get("institution") or srcrow.get("creator") or (credit.group(1) if credit else "")
        ref = det.get("reference") or ""
        url = det.get("url") or srcrow.get("url") or crow.get("source_url") or ""
        if not inst and srcrow.get("title"):
            m = re.search(r"\(([^()]+)\)\s*$", srcrow["title"])
            inst = m.group(1) if m else ""
        if not ref:
            m = re.search(r"(?<![\w.])(A\d{4}\.\d+(?:\s*\([a-z]\))?|\d{3,4}\.\d{1,3}\.\d{1,3}(?:\.\d+)?(?:\s*\([a-z]\))?)(?![\w.])",
                          " ".join(caps) + " " + scan.rsplit("/", 1)[-1].rsplit(".", 1)[0])
            ref = m.group(1) if m else ""
        # kind
        text = " ".join(caps)
        kind = (det.get("kind") or "").lower() or ("illustration" if illus else "portrait" if re.search(r"\bportrait\b", text, re.I) and len(people) <= 2
                                                  else "document" if DOC.search(text + " " + scan.rsplit("/", 1)[-1])
                                                  else "group" if GROUP.search(text) or len(people) >= 3
                                                  else "place" if not people and (places or PLACE.search(text))
                                                  else "place" if PLACE.search(text) and not re.search(r"\bportrait\b", text, re.I)
                                                  and len(people) <= 1 and not re.search(r"\bin uniform\b", text, re.I) else "portrait")
        w, h = (sizes.get(scan) or (0, 0, None))[:2]
        low = bool(w and max(w, h) < LOW_RES) and not illus
        bf = backfill.get(scan) or {}
        state = "ok" if not low else (bf.get("state") or "searching")
        if low and bf.get("state") == "ok" and bf.get("full") and (root / bf["full"]).is_file():
            full = bf["full"]
            if original:
                original = full
            else:
                image = full
            w, h = bf.get("width") or w, bf.get("height") or h
            low, state = False, "ok"
        # appears in
        appears = []
        for slug, t in sorted({sl: t for it in its for sl, t in article_photo.get(it.get("id"), {}).items()}.items(), key=lambda x: x[1]):
            appears.append({"kind": "article", "title": t, "href": "#familypedia/" + slug})
        seen_st = {}
        for k in members:
            seen_st.update(story_uses.get(k, {}))
        for sid, t in seen_st.items():
            appears.append({"kind": "chapter", "title": t, "href": "#stories?read=" + sid})
        for k in members:
            for e in timeline_uses.get(k, []):
                yr = (e.get("date") or e.get("sort") or "")[:4]
                appears.append({"kind": "timeline", "title": "Timeline" + (f" · {yr}" if yr else ""), "href": "#timeline"})
        aliases = set()
        for k in members:
            aliases |= {k, real_of[k], "work/lineage-assets/" + k}
        for r in grows:
            aliases |= r["alias"]
        if bf.get("full"):
            aliases.add(bf["full"])
        pid = next((it["id"] for it in its if it.get("id") and not str(it["id"]).startswith(("src:", "portrait:"))), its[0].get("id"))
        out.append({
            "id": pid, "dedupKey": f"{(sizes.get(scan) or (0, 0, 0))[2] or 0:016x}:{key(scan)}",
            "title": title, "description": desc, "date": date, "place": place,
            "source": {"institution": inst, "reference": ref, "url": url} if (inst or ref or url) else None,
            "kind": kind, "illustration": illus, "restored": bool(restored), "image": real_of.get(image, image),
            "original": real_of.get(original, original) if original else None, "restorationOf": pid if restored else None,
            "width": w, "height": h, "isLowRes": low, "backfillState": state,
            "portrait": any(it.get("portrait") for it in its),
            "tags": {"people": [{"slug": s, "title": t} for s, t in people.items()],
                     "places": [{"slug": s, "title": t} for s, t in places.items()],
                     "other": [{"slug": s, "title": t} for s, t in other.items()]},
            "appears": appears, "ids": sorted({it.get("id") for it in its if it.get("id")}),
            "paths": sorted(a for a in aliases if a),
        })
    out.sort(key=lambda p: (p["illustration"], (p["date"] or "9999")[:4] if re.match(r"\d{4}", p["date"] or "") else "9999", p["title"]))
    return {"photos": out, "low_res": sum(1 for p in out if p["isLowRes"]),
            "counts": {k: sum(1 for p in out if p["kind"] == k) for k in ("portrait", "group", "document", "place", "illustration")}}


def lookup(project):
    """path or photo id -> the registry entry, for grids that dedupe their pictures."""
    reg = registry(project)
    m = {}
    for p in reg["photos"]:
        for a in p["paths"] + p["ids"]:
            m.setdefault(key(a), p)
            m.setdefault(a, p)
    return m
