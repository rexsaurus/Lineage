#!/usr/bin/env python3
"""Full-text search of the Internet Archive's scanned books, yearbooks, gazettes and newspapers,
with the matching passages: the fastest way to find a person in print before 1970.

    python3 archive_fts.py '"Calder, Tobias"'
    python3 archive_fts.py '"Tobias Calder" Harrow' --rows 50 --json > hits.json
    python3 archive_fts.py '"Calder"' --only-title yearbook

Phrase-quote names. Each hit prints the item id, year, title and the highlighted passages
({{{like this}}}). Fetch a hit's full text with:
    curl -L https://archive.org/download/<id>/<id>_djvu.txt   (see archive.org/metadata/<id>/files)
Items lent through the Open Library (most books after 1927) return snippets only; quote them briefly.
Rate: one request per run; be polite (no loops faster than one request per 2 seconds).
"""
import argparse, json, sys, urllib.parse, urllib.request

UA = {"User-Agent": "Lineage family-history research (github.com/rexsaurus/Lineage)"}
URL = "https://archive.org/services/search/beta/page_production/?user_query={q}&hits_per_page={n}&service_backend=fts"


def search(q, rows=40):
    with urllib.request.urlopen(urllib.request.Request(URL.format(q=urllib.parse.quote(q), n=rows), headers=UA), timeout=90) as r:
        d = json.loads(r.read())
    hits = (d.get("response", {}).get("body") or {}).get("hits", {}).get("hits") or []
    out = []
    for h in hits:
        f = h.get("fields", {})
        out.append({"id": f.get("identifier"), "year": str(f.get("date", ""))[:4], "title": f.get("title", ""),
                    "passages": h.get("highlight", {}).get("text", [])})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("query")
    ap.add_argument("--rows", type=int, default=40)
    ap.add_argument("--only-title", help="keep hits whose title contains this (case-insensitive)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    hits = search(a.query, a.rows)
    if a.only_title:
        hits = [h for h in hits if a.only_title.lower() in str(h["title"]).lower()]
    if a.json:
        json.dump(hits, sys.stdout, indent=1); return
    for h in hits:
        print(f"{h['id']} | {h['year']} | {str(h['title'])[:70]}")
        for p in h["passages"][:3]:
            print("    …" + " ".join(p.split())[:400] + "…")


if __name__ == "__main__":
    main()
