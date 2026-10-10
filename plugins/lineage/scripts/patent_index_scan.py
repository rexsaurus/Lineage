#!/usr/bin/env python3
"""Find every US patent granted to an ancestor: stream the Patent Office's annual indexes of patentees
(1872-1969, scanned on the Internet Archive) and keep only the entries under the given names.

    python3 patent_index_scan.py --name "Calder, Tobias" --name "Calder, T. R." --out records/patents
    python3 patent_index_scan.py --name "Calder, Tobias" --years 1890-1930 --out records/patents

Writes one <volume>.extract.txt per index volume (the passages around each entry, with the source URL)
and MANIFEST.json. Then read the extracts: the annual reports of 1872-1912 give the subject but the
scans usually lose the number; the indexes from 1920 give "Subject. 1,234,567; Mon. dd." Confirm each
number on its own Google Patents page (https://patents.google.com/patent/US<number>A/en is allowed by
robots.txt; the search pages are not) and record the patents in a CSV with brother/person, year,
number, subject, assignee and source.

Known gaps on the Internet Archive: the volumes for about 1913-1919 are missing, and some downloads
fail; the run reports them. Each volume is about 12 MB; nothing is kept but the extracts.
Rate: one request per 2 seconds.
"""
import argparse, json, re, time, urllib.request
from pathlib import Path

UA = {"User-Agent": "Lineage family-history research (github.com/rexsaurus/Lineage)"}
SEARCH = ("https://archive.org/advancedsearch.php?q=(identifier%3Aannualreportofco*unit+OR+identifier%3Aindexofpatentsis*unit"
          "+OR+identifier%3Aofficialgazette19*unit)+AND+title%3A(patent*)&fl[]=identifier&fl[]=title&fl[]=year&rows=400&output=json")


def get(url, timeout=120):
    time.sleep(2)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def name_pattern(names):
    """'Calder, Tobias' also matches OCR noise like 'Ca1der , Tobias' and initial forms."""
    alts = []
    for n in names:
        last, _, first = n.partition(",")
        last = re.escape(last.strip()).replace("l", "[l1I]").replace("s", "[s5]")
        first = r"\s*".join(re.escape(w) for w in first.strip().split())
        alts.append(rf"{last}\s*[,.]\s*{first}")
    return re.compile("|".join(alts), re.I)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--name", action="append", required=True, help='"Surname, Given" (repeatable)')
    ap.add_argument("--assignee", action="append", default=[], help="a company name to keep as well")
    ap.add_argument("--years", default="1872-1969", help="e.g. 1890-1930")
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    y0, y1 = (int(x) for x in a.years.split("-"))
    pat = name_pattern(a.name)
    firm = re.compile("|".join(re.escape(x) for x in a.assignee), re.I) if a.assignee else None
    a.out.mkdir(parents=True, exist_ok=True)
    docs = json.loads(get(SEARCH))["response"]["docs"]
    ids = sorted(d["identifier"] for d in docs
                 if (m := re.search(r"(18[7-9]\d|19[0-6]\d)", d["identifier"])) and y0 <= int(m.group(1)) <= y1)
    print(len(ids), "volumes", flush=True)
    manifest = []
    for ident in ids:
        dest = a.out / f"{ident}.extract.txt"
        if dest.exists():
            continue
        try:
            files = json.loads(get(f"https://archive.org/metadata/{ident}/files"))["result"]
            txt = [f["name"] for f in files if f["name"].endswith("_djvu.txt")]
            if not txt:
                print(ident, "no text", flush=True); continue
            url = f"https://archive.org/download/{ident}/{txt[0]}"
            t = get(url, timeout=600).decode("utf-8", "ignore")
        except Exception as e:
            print(ident, "ERR", e, flush=True); continue
        t = re.sub(r"[ \t]+", " ", t)
        keep = [t[max(0, m.start() - 80): m.end() + 700] for m in pat.finditer(t)]
        if firm:
            keep += ["[ASSIGNEE] " + t[max(0, m.start() - 300): m.end() + 200] for m in firm.finditer(t)]
        dest.write_text(f"SOURCE {url}\nRETRIEVED {time.strftime('%Y-%m-%d')}\n\n" + "\n\n-----\n".join(keep))
        manifest.append((ident, url, len(keep)))
        print(ident, len(keep), flush=True)
    (a.out / "MANIFEST.json").write_text(json.dumps(manifest, indent=1))
    print("done", flush=True)


if __name__ == "__main__":
    main()
