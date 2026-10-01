#!/usr/bin/env python3
"""Build examples/demo-lineage: an INVENTED family's lineage, full enough to show every part of
the dashboard (sources, Familypedia, genealogy, timeline, stories, contributors) in the
README's screenshots without exposing anyone's real family.

    python scripts/demo_lineage.py          (from the Lineage repo root; `make screenshots` runs it)

Everything here is made up: the Calders, their recordings, their records, the ship and the ore
dock company. Record links use example.org. The recordings are spoken by the computer from the
invented transcripts; the scene pictures are generated illustrations and are marked as such.
It reuses the sample project (examples/sample-project) for the transcripts, story units and
stories, so `make sample` must have run first. Re-running rebuilds everything except the
illustrations in sources/, which are made once and committed.
"""
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]           # the Lineage repo
SAMPLE = ROOT / "examples" / "sample-project"
OUT = ROOT / "examples" / "demo-lineage"
PLUGIN = ROOT / "plugins" / "lineage"
STAMP = "2026-09-20T10:00:00-05:00"


def w(rel, text):
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")


def wj(rel, data):
    w(rel, json.dumps(data, indent=1, ensure_ascii=False))


def wcsv(rel, header, rows):
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as f:
        cw = csv.writer(f)
        cw.writerow(header)
        cw.writerows(rows)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------------------- material
def copy_sample():
    for rel in ("transcript", "content", "facts/glossary.md", "data/reader_glossary.csv", "book/front", "photos/print"):
        src, dst = SAMPLE / rel, OUT / rel
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    if not (SAMPLE / "chapters").is_dir():
        sys.exit("run `make sample` first: the demo reuses the sample's generated stories")
    shutil.copytree(SAMPLE / "chapters", OUT / "chapters", dirs_exist_ok=True)
    shutil.copy2(PLUGIN / "book" / "template.typ", OUT / "book" / "template.typ")
    shutil.copy2(SAMPLE / "book.yaml", OUT / "book.yaml")
    shutil.copy2(SAMPLE / "data" / "chapters.csv", OUT / "data" / "chapters.csv")


def recordings():
    """The two invented sessions, spoken by the computer (macOS `say`) so the player and the
    waveforms are real. Two voices: Grandma and Sam."""
    voices = {"Grandma": "Samantha", "Sam": "Daniel"}
    for sid in ("S1", "S2"):
        out = OUT / "audio" / f"sample-session-{sid[1]}.m4a"
        if out.exists():
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT / ".build"
        tmp.mkdir(exist_ok=True)
        parts = []
        for i, line in enumerate((OUT / "transcript" / "clean" / f"{sid}.md").read_text().splitlines()):
            if line.startswith("**"):
                spk, text = line[2:].split("**", 1)
                text = text.split("]", 1)[1].strip()
                aiff = tmp / f"{sid}-{i:03d}.aiff"
                subprocess.run(["say", "-v", voices.get(spk, "Samantha"), "-o", str(aiff), text], check=True)
                parts.append(aiff)
        lst = tmp / f"{sid}.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in parts))
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-c:a", "aac", "-b:a", "64k", str(out)], check=True)
    shutil.rmtree(OUT / ".build", ignore_errors=True)


DOC_TYP = r"""
#set page(width: 6.5in, height: auto, margin: 0.45in, fill: rgb("#efe6d2"))
#set text(font: ("EB Garamond", "Libertinus Serif"), size: 10.5pt, fill: rgb("#2b2418"))
"""


def documents():
    """Scans of invented records, typeset to look like their kind. Rendered with Typst."""
    docs = {
        "1900-ottavia-passenger-list.png": DOC_TYP + r"""
#align(center)[#text(size: 15pt, tracking: 0.12em)[LIST OR MANIFEST OF ALIEN PASSENGERS] \
#text(size: 9pt)[S.S. OTTAVIA · sailing from LIVERPOOL · arriving at the Port of QUEBEC · May 21st, 1900]]
#v(6pt)
#table(columns: (auto, 1.6fr, auto, auto, 1fr, 1fr), stroke: 0.4pt + rgb("#7a6a4f"), inset: 4pt,
  [*No.*], [*Name in full*], [*Age*], [*Sex*], [*Last residence*], [*Final destination*],
  [14], [Lindgren, Karl], [24], [M], [Bergen], [Winnipeg],
  [15], [Calder, Anders], [17], [M], [Aalesund], [Duluth, Minn.],
  [16], [Hauge, Marit], [31], [F], [Bergen], [St. Paul, Minn.],
  [17], [Hauge, Ole], [8], [M], [Bergen], [St. Paul, Minn.],
  [18], [Brekke, Johan], [19], [M], [Stavanger], [Duluth, Minn.])
#v(4pt) #text(size: 8pt, style: "italic")[DEMO RECORD. Invented for the Lineage demo lineage; no such list exists.]
""",
        "1938-ore-dock-payroll-ledger.png": DOC_TYP + r"""
#align(center)[#text(size: 14pt, tracking: 0.1em)[DULUTH ORE DOCK COMPANY] \ #text(size: 9pt)[Dock No. 6 · Payroll, fortnight ending October 15, 1938]]
#v(6pt)
#table(columns: (1.4fr, 1fr, auto, auto, auto), stroke: 0.4pt + rgb("#7a6a4f"), inset: 4pt,
  [*Name*], [*Position*], [*Hours*], [*Rate*], [*Paid*],
  [Calder, A.], [Dock foreman], [96], [.68], [65.28],
  [Calder, H.], [Chute tender], [104], [.52], [54.08],
  [Nyberg, T.], [Chute tender], [88], [.52], [45.76],
  [Ostrom, C.], [Car spotter], [100], [.48], [48.00])
#v(4pt) #text(size: 8pt, style: "italic")[DEMO RECORD. Invented for the Lineage demo lineage.]
""",
        "1950-courier-the-big-snow.png": r"""
#set page(width: 4.6in, height: auto, margin: 0.35in, fill: rgb("#ece4d0"))
#set text(font: ("EB Garamond", "Libertinus Serif"), size: 9.5pt, fill: rgb("#1f1a12"))
#align(center)[#text(size: 8pt, tracking: 0.2em)[THE DULUTH LAKESIDE COURIER · NOVEMBER 9, 1950]
#line(length: 100%, stroke: 0.6pt)
#text(size: 19pt, weight: "bold")[CITY BURIED; SCHOOLS SHUT FOR WEEK]
#line(length: 100%, stroke: 0.4pt)]
#columns(2, gutter: 10pt)[
Snow that began falling on Tuesday had by last evening reached the eaves of houses on the hillside, and the Board of Education announced that every school in the city will remain closed through the week.

Crews from the ore docks were loaned to the city to open the avenues. Men walked to work along the tops of drifts, and boys were seen sliding from second-storey windows.
]
#v(4pt) #text(size: 7.5pt, style: "italic")[DEMO RECORD. An invented newspaper, for the Lineage demo lineage.]
""",
        "1944-letter-henrik-to-ruth.pdf": r"""
#set page(width: 6in, height: 7.6in, margin: 0.6in, fill: rgb("#f3ecdc"))
#set text(font: ("EB Garamond", "Libertinus Serif"), size: 11.5pt, style: "italic", fill: rgb("#23304a"))
#align(right)[Somewhere in France \ Sept. 3, 1944]
#v(10pt)
Dear Ruthie,

Your mother says you have learned to walk the lunch pail down to the dock all by yourself, and that Grandpa Anders lets you ring the bell. I am very proud. Here we build bridges where the old ones were blown up, which is not so different from the dock, only wetter.

Tell Pete he is the man of the house until I come home, but he is not to boss you.

#v(8pt)
Your loving Papa
#v(16pt) #text(size: 8pt, style: "normal", fill: rgb("#5a4a30"))[DEMO RECORD. An invented letter, for the Lineage demo lineage.]
""",
    }
    for name, src in docs.items():
        out = OUT / "sources" / name
        out.parent.mkdir(parents=True, exist_ok=True)
        typ = OUT / f".{Path(name).stem}.typ"
        typ.write_text(src)
        fmt = ["--format", "png", "--ppi", "150"] if name.endswith(".png") else []
        subprocess.run(["typst", "compile", "--font-path", str(PLUGIN / "fonts"), *fmt, str(typ), str(out)],
                       check=True, capture_output=True)
        typ.unlink()
    w("sources/1944-letter-henrik-to-ruth-transcription.txt",
      "Transcription of the letter of Sept. 3, 1944 (Henrik Calder to his daughter Ruth). Typed by June Calder Moe.\n\n"
      "Somewhere in France, Sept. 3, 1944. Dear Ruthie, Your mother says you have learned to walk the lunch pail down to "
      "the dock all by yourself, and that Grandpa Anders lets you ring the bell. I am very proud. Here we build bridges "
      "where the old ones were blown up, which is not so different from the dock, only wetter. Tell Pete he is the man of "
      "the house until I come home, but he is not to boss you. Your loving Papa.\n\nDEMO RECORD. Invented.")


# The scene illustrations (made once with an image model, committed): (file, caption, people, place, date)
ILLUSTRATIONS = [
    ("ore-dock-1946-illustration.jpg", "Illustration: an ore boat loading at a Duluth ore dock in winter", "", "Duluth, Minnesota", "about 1946"),
    ("pike-lake-cabin-illustration.jpg", "Illustration: a half-built log cabin by a lake, about 1965", "Walt; Ruth Calder", "Pike Lake, Minnesota", "about 1965"),
    ("big-snow-1950-illustration.jpg", "Illustration: a hillside street buried in snow, 1950", "", "Duluth, Minnesota", "November 1950"),
    ("quebec-arrival-1900-illustration.jpg", "Illustration: an emigrant steamer at the Quebec quay, 1900", "Anders Calder", "Quebec, Canada", "May 1900"),
]


# ------------------------------------------------------------------------------- the record
def facts():
    wcsv("facts/timeline.csv",
         ["event_id", "date_start", "date_end", "date_display", "precision", "date_basis", "event", "people", "place",
          "generation", "source", "quote", "confidence", "conflicts", "chapter"],
         [["E001", "1883", "", "about 1883", "approx", "Manifest age 17 in May 1900 (record R001); family account says sixteen at the crossing.",
           "Anders Calder born near Aalesund, Norway", "Anders Calder", "Aalesund, Norway", "ancestors", "R001; [S1 00:00:05]", "", "medium",
           "Age at the crossing: the family says sixteen [S1 00:00:05], the manifest says 17 (R001). Both kept.", "1"],
          ["E002", "1900-05-21", "", "May 21, 1900", "day", "Passenger manifest, S.S. Ottavia (R001)", "Anders Calder crosses from Liverpool to Quebec on the S.S. Ottavia",
           "Anders Calder", "Quebec, Canada", "ancestors", "R001; [S1 00:00:05]", "came over on a ship when he was sixteen", "high", "", "1"],
          ["E003", "1900", "", "about 1900", "approx", "Family account; follows E002", "Anders works on the ore boats at Duluth (family account)",
           "Anders Calder", "Duluth, Minnesota", "ancestors", "[S1 00:00:21]", "He ended up on the ore boats", "low", "", "1"],
          ["E004", "1910", "", "1910", "year", "Federal census, Duluth (R002)", "Henrik Calder born in Duluth", "Henrik Calder; Anders Calder",
           "Duluth, Minnesota", "parents", "R002", "", "high", "", ""],
          ["E005", "1938", "", "1938", "year", "book.yaml birth year", "Ruth Calder born in Duluth", "Ruth Calder; Henrik Calder", "Duluth, Minnesota",
           "subject", "[S1 00:00:29]", "", "high", "", "2"],
          ["E006", "1938-10-15", "", "October 1938", "day", "Payroll ledger, Dock No. 6 (R003)", "Anders and Henrik on the payroll of the Duluth Ore Dock Company",
           "Anders Calder; Henrik Calder", "Duluth, Minnesota", "parents", "R003", "", "high", "", "2"],
          ["E007", "1944-09-03", "", "September 3, 1944", "day", "Letter (source 1944-letter-henrik-to-ruth.pdf)", "Henrik writes to Ruth from France with the Arrowhead Engineer Battalion",
           "Henrik Calder; Ruth Calder; Pete", "France", "parents", "R004", "Here we build bridges", "high", "", "2"],
          ["E008", "1945", "1946", "about 1945", "approx", "'maybe seven or eight' + birth year 1938", "Ruth walks her father's lunch to the ore dock",
           "Ruth Calder; Henrik Calder", "Duluth, Minnesota", "subject", "[S1 00:00:29]", "maybe seven or eight", "medium",
           "The 1944 letter already has her carrying the pail at six (R004).", "2"],
          ["E009", "1950-11-07", "1950-11-14", "November 1950", "approx", "'around 1950, I think'; the Courier dates it Nov 1950 (R005)",
           "The big snow; school closed for a week", "Ruth Calder; Pete", "Duluth, Minnesota", "subject", "[S1 00:00:48]; R005", "around 1950, I think", "high", "", "2"],
          ["E010", "1951", "", "1951", "year", "Family account", "Anders Calder dies in Duluth", "Anders Calder", "Duluth, Minnesota", "ancestors",
           "[S1 00:00:21]", "", "low", "", "1"],
          ["E011", "1956", "1959", "1956–1959", "year", "'1956. Three years.'", "Ruth trains as a nurse in Minneapolis", "Ruth Calder",
           "Minneapolis, Minnesota", "subject", "[S2 00:00:03]", "I went down to Minneapolis for nursing school in 1956", "high", "", "3"],
          ["E012", "1959", "", "1959", "year", "'A church dance, in 1959'", "Ruth meets Walt at a church dance", "Ruth Calder; Walt",
           "Minneapolis, Minnesota", "subject", "[S2 00:00:19]", "A church dance, in 1959", "high", "", "3"],
          ["E013", "1964", "1968", "1964–1968", "approx", "'1964 or so. It took four summers.'", "Ruth and Walt build the cabin on Pike Lake",
           "Ruth Calder; Walt", "Pike Lake, Minnesota", "subject", "[S2 00:00:36]", "It took four summers", "medium", "", "3"]])
    w("facts/people/anders-calder.md", """# Anders Calder
Relationship to the subject: grandfather [S1 00:00:05]
Also called: "Grandpa Anders"
Dates: born about 1883 (manifest age 17 in 1900, R001) · died 1951 (family account)
Places: Aalesund, Norway; Liverpool; Quebec; Duluth, Minnesota

## Told
- Crossed from Norway "on a ship when he was sixteen", with one pair of boots [S1 00:00:05]
- Worked on the ore boats, then the ore dock [S1 00:00:21]

## What the records show
- S.S. Ottavia, Liverpool to Quebec, arriving May 21, 1900: "Calder, Anders", 17, of Aalesund, bound for Duluth (R001)
- Dock foreman, Duluth Ore Dock Company, October 1938 (R003)
""")
    w("facts/people/henrik-calder.md", """# Henrik Calder
Relationship to the subject: father [S1 00:00:29]
Also called: "Papa"
Dates: born 1910, Duluth (R002)
Places: Duluth, Minnesota; France

## What the records show
- Chute tender, Duluth Ore Dock Company, October 1938 (R003)
- Wrote to Ruth from France, September 1944, with the Arrowhead Engineer Battalion (R004)
""")
    w("facts/people/ruth-calder.md", """# Ruth Calder
Relationship to the subject: the subject
Also called: "Grandma", "Ruthie"
Dates: born 1938, Duluth
Places: Duluth, Minnesota; Minneapolis, Minnesota; Pike Lake, Minnesota
""")
    gaps = (SAMPLE / "facts" / "gaps.md").read_text()
    w("facts/gaps.md", gaps.rstrip() + """

## Walt's surname
- Ruth only ever says "Walt" [S2 00:00:19]. His surname is not in the material. Ask June.

## Anders's age at the crossing
- The family says sixteen [S1 00:00:05]; the manifest says 17 (R001). Both are kept.
""")
    w("facts/records/calder/sources.csv", "")
    wcsv("facts/records/calder/sources.csv", ["id", "title", "url", "holder", "type", "date_retrieved", "rights_notes"],
         [["S01", "Passenger manifest, S.S. Ottavia, Liverpool to Quebec, May 1900", "https://example.org/demo/ottavia-1900", "Demo immigration archive", "passenger list", "2026-09-18", "demo record"],
          ["S02", "Federal census 1910, Duluth, ward 4, sheet 12", "https://example.org/demo/census-1910-duluth", "Demo census index", "census", "2026-09-18", "demo record"],
          ["S03", "Payroll ledger, Dock No. 6, October 1938", "https://example.org/demo/ore-dock-payroll-1938", "Demo county historical society", "ledger", "2026-09-19", "demo record"],
          ["S04", "Duluth Lakeside Courier, Nov 9, 1950, p. 1", "https://example.org/demo/courier-1950-11-09", "Demo newspaper archive", "newspaper", "2026-09-19", "demo record"]])
    wcsv("facts/records/calder/ottavia_1900_track.csv", ["seq", "date", "place", "lat", "lon", "kind", "aboard", "leg", "source", "note"],
         [[1, "1900-05-04", "Aalesund, Norway", "62.47", "6.15", "port", "subject", "1", "family account [S1 00:00:05]", ""],
          [2, "1900-05-07", "Bergen, Norway", "60.39", "5.32", "port", "subject", "1", "family account", "coastal steamer, not recorded"],
          [3, "1900-05-09", "Hull, England", "53.74", "-0.33", "port", "subject", "2", "demo emigrant agent's ledger", "North Sea crossing not recorded"],
          [4, "1900-05-10", "Liverpool, England", "53.41", "-2.99", "port", "subject", "2", "manifest R001 (port of departure)", ""],
          [5, "1900-05-21", "Quebec, Canada", "46.81", "-71.21", "port", "subject", "2", "manifest R001 (arrival)", ""],
          [6, "1900-06", "Duluth, Minnesota", "46.78", "-92.10", "port", "subject", "3", "family account [S1 00:00:21]", "route from Quebec not recorded"]])
    wj("data/familypedia/routes.json", {"facts/records/calder/ottavia_1900_track.csv": ["s-s-ottavia", "anders-calder"]})


def records_catalogue():
    wcsv("data/archives.csv",
         ["record_id", "item", "type", "description", "date_range", "holder", "holder_relation", "location_general",
          "location_detail_private", "condition", "status", "mentioned_in", "chapter", "official_copy_hint", "print_permission", "follow_up"],
         [["R001", "Passenger manifest, S.S. Ottavia, May 1900", "documents", "Anders Calder, 17, of Aalesund, bound for Duluth", "1900",
           "Demo immigration archive", "", "online", "", "image", "institutional", "https://example.org/demo/ottavia-1900 [S1 00:00:05]", "1", "", "yes", ""],
          ["R002", "Federal census 1910, Duluth", "documents", "Calder household: Anders, his wife Signe, son Henrik (born 1910)", "1910",
           "Demo census index", "", "online", "", "transcribed", "institutional", "https://example.org/demo/census-1910-duluth", "", "", "yes", ""],
          ["R003", "Payroll ledger, Duluth Ore Dock Company, Dock No. 6", "documents", "A. Calder, dock foreman; H. Calder, chute tender, October 1938", "1938",
           "Demo county historical society", "", "Duluth, Minnesota", "", "good", "institutional", "https://example.org/demo/ore-dock-payroll-1938", "2", "", "yes", ""],
          ["R004", "Letters from Henrik in France, 1944", "letters", "Eleven letters to the family; one to Ruth transcribed", "1944",
           "June Calder Moe", "Ruth's sister", "Minnesota", "her desk drawer", "good", "confirmed", "[S1 00:00:29]", "2", "", "ask", "Scan the other ten"],
          ["R005", "Duluth Lakeside Courier, Nov 9, 1950", "documents", "Front page: schools shut for the big snow", "1950",
           "Demo newspaper archive", "", "online", "", "microfilm", "institutional", "https://example.org/demo/courier-1950-11-09 [S1 00:00:48]", "2", "", "yes", ""],
          ["R006", "Anders's sea chest", "heirlooms", "Painted pine chest, his initials on the lid", "about 1900",
           "Peter Lind", "Ruth's nephew", "Minnesota", "", "worn", "confirmed", "family account", "", "", "ask", "Photograph the lid"],
          ["R007", "Family Bible", "bible", "Births and marriages from 1883", "1883–1962", "June Calder Moe", "Ruth's sister", "Minnesota", "", "fragile",
           "confirmed", "family account", "", "", "ask", "Photograph the family register pages"]])


def knowledge():
    nodes, edges = [], []

    def n(nid, typ, label, **kw):
        nodes.append({"id": nid, "type": typ, "label": label, **kw})

    def e(a, rel, b, **kw):
        edges.append({"source": a, "rel": rel, "target": b, **kw})

    n("person:anders-calder", "person", "Anders Calder")
    n("person:henrik-calder", "person", "Henrik Calder")
    n("person:ruth-calder", "person", "Ruth Calder")
    n("person:signe-calder", "person", "Signe Calder", basis="1910 census")
    n("person:karl-lindgren", "person", "Karl Lindgren", basis="passenger manifest")
    n("person:johan-brekke", "person", "Johan Brekke", basis="passenger manifest")
    n("person:captain-r-mcallister", "person", "R. McAllister", basis="demo shipping register")
    n("vessel:s-s-ottavia", "vessel", "S.S. Ottavia", rig="steamship", tonnage="4,800", built="Glasgow, 1891", owner="Demo Atlantic Line",
      registry="Liverpool", fate="broken up, 1926", url="https://example.org/demo/ships/ottavia", retrieved="2026-09-18")
    n("voyage:ottavia-1900", "voyage", "Ottavia, Liverpool to Quebec, May 1900", url="https://example.org/demo/ottavia-1900")
    n("organization:duluth-ore-dock-company", "organization", "Duluth Ore Dock Company", description="loaded iron ore from rail cars into lake freighters")
    n("unit:arrowhead-engineer-battalion", "unit", "Arrowhead Engineer Battalion", description="combat engineers (bridges)")
    n("object:anders-sea-chest", "object", "Anders's sea chest", description="painted pine chest, his initials on the lid", date="about 1900")
    n("publication:duluth-lakeside-courier", "publication", "Duluth Lakeside Courier", description="daily newspaper")
    n("place:liverpool-england", "place", "Liverpool, England")
    n("place:quebec-canada", "place", "Quebec, Canada")
    for rid, lab, url in (("record:r001", "Passenger manifest, S.S. Ottavia, May 1900", "https://example.org/demo/ottavia-1900"),
                          ("record:r003", "Payroll ledger, Dock No. 6, October 1938", "https://example.org/demo/ore-dock-payroll-1938"),
                          ("record:r005", "Duluth Lakeside Courier, Nov 9, 1950", "https://example.org/demo/courier-1950-11-09")):
        n(rid, "record", lab, url=url, retrieved="2026-09-18")
    n("letter:henrik-1944-09-03", "letter", "Henrik to Ruth, Sept. 3, 1944", date="1944-09-03", description="from France: building bridges; Ruth carries the lunch pail")
    e("voyage:ottavia-1900", "voyage_of", "vessel:s-s-ottavia")
    e("person:captain-r-mcallister", "master_of", "voyage:ottavia-1900")
    for p, rank in (("person:anders-calder", "steerage"), ("person:karl-lindgren", "steerage"), ("person:johan-brekke", "steerage")):
        e(p, "crew_on" if False else "crew_on", "voyage:ottavia-1900", rank=rank)
    e("voyage:ottavia-1900", "called_at", "place:liverpool-england")
    e("voyage:ottavia-1900", "called_at", "place:quebec-canada")
    e("record:r001", "documents", "voyage:ottavia-1900")
    e("record:r001", "mentions", "person:anders-calder")
    e("person:anders-calder", "worked_at", "organization:duluth-ore-dock-company")
    e("person:henrik-calder", "worked_at", "organization:duluth-ore-dock-company")
    e("record:r003", "mentions", "person:anders-calder")
    e("record:r003", "mentions", "person:henrik-calder")
    e("record:r003", "concerns", "organization:duluth-ore-dock-company")
    e("person:henrik-calder", "served_in", "unit:arrowhead-engineer-battalion")
    e("letter:henrik-1944-09-03", "wrote" if False else "mentions", "person:henrik-calder")
    e("letter:henrik-1944-09-03", "addressed_to", "person:ruth-calder")
    e("letter:henrik-1944-09-03", "concerns", "unit:arrowhead-engineer-battalion")
    e("object:anders-sea-chest", "owned_by", "person:anders-calder")
    e("record:r005", "concerns", "publication:duluth-lakeside-courier")
    wj("knowledge/graph.json", {"nodes": nodes, "edges": edges})


def genealogy():
    def p(pid, name, dates, living=False, aliases=()):
        return pid, {"id": pid, "name": name, "aliases": list(aliases), "dates": dates, "living": living, "evidence": []}

    people = dict([p("anders-calder", "Anders Calder", "about 1883–1951", aliases=["Grandpa Anders"]),
                   p("signe-calder", "Signe Calder", "in the 1910 census"),
                   p("henrik-calder", "Henrik Calder", "born 1910"),
                   p("ruth-calder", "Ruth Calder", "born 1938", living=True, aliases=["Grandma"]),
                   p("pete", "Pete", "", living=None),
                   p("june-calder-moe", "June Calder Moe", "", living=True),
                   p("walt", "Walt", "", living=None),
                   p("sam-calder", "Sam Calder", "", living=True)])

    def link(a, rel, b, tier, cite, quote):
        lid = f"{min(a, b)}-{rel}-{max(a, b)}" if rel in ("spouse", "sibling") else f"{a}-{rel}-{b}"
        return {"id": lid, "a": a, "rel": rel, "b": b, "tier": tier, "evidence": [{"cite": cite, "quote": quote}]}

    links = [link("anders-calder", "parent", "henrik-calder", "documented", "R002", "Calder household: Anders, his wife Signe, son Henrik"),
             link("signe-calder", "parent", "henrik-calder", "documented", "R002", "Calder household: Anders, his wife Signe, son Henrik"),
             link("anders-calder", "spouse", "signe-calder", "documented", "R002", "Anders, his wife Signe"),
             link("henrik-calder", "parent", "ruth-calder", "told", "[S1 00:00:29]", "my father's lunch"),
             link("ruth-calder", "sibling", "pete", "told", "[S1 00:00:48]", "Pete"),
             link("ruth-calder", "sibling", "june-calder-moe", "told", "R004", "June Calder Moe, Ruth's sister"),
             link("ruth-calder", "spouse", "walt", "told", "[S2 00:00:19]", "Walt couldn't dance at all")]
    wj("data/genealogy/derived.json", {"people": people, "links": links, "conflicts": [], "applied": STAMP,
                                       "note": "demo: every link cites a passage or a record"})
    wj("data/genealogy/history.json", [{"at": STAMP, "by": "me", "event": "applied a rebuild", "detail": {"links": len(links), "conflicts": 0}}])


def project_state():
    wj("lineage.json", {
        "title": "The Calders of the Lake", "subject": "Ruth Calder",
        "stages": {"setup": "done", "sources": "done", "research": "done", "genealogy": "done", "chapters": "done",
                   "style": "done", "generate": "done", "podcast": "todo"},
        "settings": {"family_name": "Calder", "subtitle": "A family record from Aalesund to Pike Lake", "subject_short": "Ruth",
                     "summary": "The Calders came from the coast of Norway to the ore docks of Duluth in 1900. "
                                "This is their record: Ruth Calder's recordings, Henrik's letters from France, the "
                                "manifest of the ship Anders crossed on, the ore dock's payroll, and the cabin on Pike Lake.",
                     "narrative_style": "biographer", "chapter_template": "ancestor", "photo_style": "silver",
                     "quote_density": "standard", "ornament": "❧", "bridges_in_drafts": True, "opener": "dropcap",
                     "trim": "7x10", "printer": "kdp", "drive_folder": "", "sync_sources": False, "sync_outputs": False,
                     "terminal_command": "", "terminal_cwd": "", "voice_id": "", "voice_name": ""},
        "artifacts": {}})
    wj(".lineage/family.json", {
        "members": [
            {"id": "m1", "name": "Sam Calder", "email": "sam@example.org", "role": "editor", "relation": "grandson; recorded the interviews", "added": STAMP},
            {"id": "m2", "name": "June Calder Moe", "email": "june@example.org", "role": "contributor", "relation": "Ruth's sister; holds the letters and the Bible", "added": STAMP},
            {"id": "m3", "name": "Peter Lind", "email": "peter@example.org", "role": "contributor", "relation": "Ruth's nephew; has the sea chest", "added": STAMP},
            {"id": "m4", "name": "Linnea Calder", "email": "linnea@example.org", "role": "reader", "relation": "Sam's mother", "added": STAMP}],
        "invites": [{"member": "m3", "token": "demo-invite-token", "created": 1790000000, "expires": 2000000000}]})
    wj("data/story_states.json", {"1": "in the book", "2": "in the book", "3": "draft"})
    wj("data/timeline_stars.json", ["E002", "E007", "E009"])
    wj("data/questions.json", [{"text": "What was Walt's surname?", "source": "facts/gaps.md", "at": STAMP},
                               {"text": "Where did Anders live between 1900 and 1910?", "source": "timeline gap", "at": STAMP}])
    wj("data/requests.json", [{"id": "a1b2c3d4", "kind": "person", "about": "henrik-calder", "to": "m2", "to_name": "June Calder Moe",
                               "to_email": "june@example.org", "title": "Henrik's letters from France",
                               "questions": ["Could you scan the other ten letters from 1944?", "Do any of them mention Pete?"],
                               "made": STAMP, "status": "asked"}])
    wj("data/familypedia/anders-calder.json", {
        "lead": "Anders Calder crossed from Norway to Quebec on the S.S. Ottavia in May 1900, bound for Duluth, where he "
                "worked the ore boats and then the ore dock until he was foreman. The family says he was sixteen; the "
                "manifest says seventeen. Both are kept.",
        "history": [{"at": STAMP, "by": "me", "fields": ["lead"]}]})
    wj("data/familypedia/tags.json", {"event:E009": [{"subject": "duluth-lakeside-courier", "state": "accepted", "evidence": "", "by": "me", "at": STAMP}]})


def sources_index():
    """data/sources.json as the intake leaves it, so the Sources tab shows ingested, summarized, tagged rows."""
    rows = {}
    spec = [
        ("audio/sample-session-1.m4a", "recording", "Sam Calder", "Ruth talks about where the Calders came from, the ore dock, and the big snow.",
         ["Ruth Calder", "Anders Calder", "Henrik Calder", "Pete"], ["Duluth, Minnesota", "Norway"], "1900–1950"),
        ("audio/sample-session-2.m4a", "recording", "Sam Calder", "Nursing school in Minneapolis, meeting Walt at a church dance, building the cabin on Pike Lake.",
         ["Ruth Calder", "Walt"], ["Minneapolis, Minnesota", "Pike Lake, Minnesota"], "1956–1968"),
        ("sources/1900-ottavia-passenger-list.png", "record", "Sam Calder", "Passenger manifest page, S.S. Ottavia, Liverpool to Quebec, May 21, 1900. Line 15: Calder, Anders, 17, of Aalesund, for Duluth.",
         ["Anders Calder", "Karl Lindgren", "Johan Brekke"], ["Liverpool, England", "Quebec, Canada", "Duluth, Minnesota"], "1900"),
        ("sources/1938-ore-dock-payroll-ledger.png", "record", "Peter Lind", "Payroll ledger of the Duluth Ore Dock Company, Dock No. 6, October 1938: A. Calder, dock foreman; H. Calder, chute tender.",
         ["Anders Calder", "Henrik Calder"], ["Duluth, Minnesota"], "1938"),
        ("sources/1950-courier-the-big-snow.png", "record", "Sam Calder", "Front page of the Duluth Lakeside Courier, Nov 9, 1950: the city buried, schools shut for the week.",
         [], ["Duluth, Minnesota"], "1950"),
        ("sources/1944-letter-henrik-to-ruth.pdf", "letter", "June Calder Moe", "Henrik writes to Ruth from France, Sept. 3, 1944: building bridges; she carries the lunch pail to the dock.",
         ["Henrik Calder", "Ruth Calder", "Pete", "Anders Calder"], ["France", "Duluth, Minnesota"], "1944"),
        ("sources/1944-letter-henrik-to-ruth-transcription.txt", "transcript", "June Calder Moe", "June's typed transcription of Henrik's letter of Sept. 3, 1944.",
         ["Henrik Calder", "Ruth Calder"], ["France"], "1944"),
    ] + [(f"sources/{f}", "photo", "Sam Calder", cap.replace("Illustration: ", "Generated illustration: "),
          [], [place], date) for f, cap, ppl, place, date in ILLUSTRATIONS]   # nobody is pictured by an illustration
    for i, (rel, kind, who, summary, people, places, dr) in enumerate(spec):
        p = OUT / rel
        if not p.exists():
            continue
        h = sha(p)
        k = {".m4a": "audio", ".png": "image", ".jpg": "image", ".pdf": "pdf", ".txt": "text"}[p.suffix]
        rows[h[:12]] = {
            "id": h[:12], "path": rel, "original_name": p.name, "sha256": h, "bytes": p.stat().st_size,
            "mime": {"audio": "audio/mp4", "image": "image/png" if p.suffix == ".png" else "image/jpeg", "pdf": "application/pdf", "text": "text/plain"}[k],
            "kind": k, "date_added": f"2026-09-{12 + i:02d}T09:{10 + i:02d}:00-05:00", "added_by": who,
            "derived": {"summary": summary, "people": people, "places": places, "organizations": [], "date_range": dr, "doc_kind": kind,
                        "confidence": {"summary": "high", "people": "high", "places": "high", "date_range": "medium", "doc_kind": "high"},
                        "method": "demo fixture (written by hand)", "suggested_name": p.name, "suggested_name_basis": "date from the content"},
            "mine": {}, "fields": {"provenance": "demo fixture"}, "notes": "",
            "stages": {s: {"state": "done", "detail": ""} for s in ("ingest", "extract", "understand", "index")} | {"drive": {"state": "skipped", "detail": "not connected"}},
            "history": [{"at": f"2026-09-{12 + i:02d}T09:{10 + i:02d}:00-05:00", "by": who, "event": "added"}]}
    wj("data/sources.json", rows)
    wcsv("transcript/sessions.csv", ["session", "file", "recorded", "duration", "speakers", "topic"],
         [["S1", "audio/sample-session-1.m4a", "2024-06-02", "00:01:04", "Grandma; Sam", "Where the Calders came from; the ore dock; the big snow"],
          ["S2", "audio/sample-session-2.m4a", "2024-06-09", "00:01:02", "Grandma; Sam", "Nursing school; Walt; the cabin on Pike Lake"]])


def photo_index():
    rows = [[f"P{i + 1:03d}", f"sources/{f}", cap, ppl, "named in the recording" if ppl else "", date, "scene in the story, not a photo date", "low",
             place, "transcript", "", "illustration", "", "", f"sources/{f}", "4", "Generated illustration: never presented as a photograph", "placed"]
            for i, (f, cap, ppl, place, date) in enumerate(ILLUSTRATIONS)]
    rows += [["P005", "sources/1900-ottavia-passenger-list.png", "Passenger manifest, S.S. Ottavia, May 1900 (scan)", "Anders Calder", "line 15 of the record", "1900", "the record", "high",
              "Quebec, Canada", "the record", "Demo immigration archive", "record", "1", "", "sources/1900-ottavia-passenger-list.png", "5", "", "placed"]]
    wcsv("photos/photo_index.csv", ["id", "source_file", "subject", "people", "people_basis", "date", "date_basis", "date_confidence", "location",
                                    "location_basis", "holder", "kind", "chapter", "placement_anchor", "print_file", "max_print_width_in", "needs_attention", "status"], rows)


def narration():
    """One story narrated (by the computer's voice) so the player shows."""
    sys.path.insert(0, str(ROOT / "app"))
    import server  # noqa: E402
    proj = server.Project.__new__(server.Project)
    proj.root = OUT
    for st in server.engine_stories(proj):
        if st["id"] != "2":
            continue
        mp3, meta = server._audio_paths(proj, st)
        _, text = server.story_script(proj, st["id"])
        if not mp3.exists():
            mp3.parent.mkdir(parents=True, exist_ok=True)
            aiff = mp3.with_suffix(".aiff")
            subprocess.run(["say", "-v", "Samantha", "-o", str(aiff), text[:2400]], check=True)
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(aiff), "-b:a", "64k", str(mp3)], check=True)
            aiff.unlink()
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp3)],
                                   capture_output=True, text=True).stdout.strip() or 0)
        meta.write_text(json.dumps({"text_sha": server._sha256_bytes(text.encode()), "voice_name": "computer voice (demo)",
                                    "made": STAMP, "duration": round(dur, 1)}, indent=1))


def main():
    if not SAMPLE.is_dir():
        sys.exit("examples/sample-project is missing")
    OUT.mkdir(parents=True, exist_ok=True)
    w("README.md", """# The demo lineage

An **invented** family, the Calders, built to show the whole dashboard in the README's
screenshots without exposing anyone's real family. Nothing here is real: the people, the
recordings (spoken by the computer from invented transcripts), the records (every link is on
example.org), the ship, the ore dock company and the battalion. The scene pictures in
`sources/` are generated illustrations and are marked as such everywhere they appear.

Rebuild with `python scripts/demo_lineage.py`; `make screenshots` does that and then captures
the dashboard into `docs/images/`.
""")
    copy_sample()
    recordings()
    documents()
    facts()
    records_catalogue()
    knowledge()
    genealogy()
    project_state()
    sources_index()
    photo_index()
    narration()
    missing = [f for f, *_ in ILLUSTRATIONS if not (OUT / "sources" / f).exists()]
    if missing:
        print("note: illustrations not made yet (made once with an image model): " + ", ".join(missing))
    print(f"demo lineage: {OUT}")


if __name__ == "__main__":
    main()
