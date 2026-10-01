#!/usr/bin/env python3
"""Draw an evidence-coded, black-and-white route map from a track CSV.

    python $LINEAGE/scripts/make_route_map.py facts/records/voyage_track.csv \\
        --out photos/print/P050.png --title "The voyage, 1851-1854" \\
        --caption "Positions from the logbook; lines between them are approximate."

Run from the book project folder (or --project DIR). Output is a 300 dpi PNG
sized for a book plate (--width inches, default 6.4).

The map shows what the records show and nothing more:
  * filled dot   a place recorded with the subject aboard   (aboard=subject)
  * open dot     a place recorded without the subject        (aboard=ship / other)
  * dashed line  the subject's track, approximate between recorded places
  * no line      an unrecorded leg (gap_before=yes on the row after the gap),
                 labelled "not recorded" at its midpoint
A legend explains the three marks.

Track CSV columns (only seq, lat, lon are required):
  seq        order along the route (number)
  date       free text, for your own reference
  place      place name, used as the label if `label` is blank and --auto-labels
  lat, lon   decimal degrees (west and south negative)
  kind       port | position | area | waypoint | text
               port/position  a dot (filled or open, see aboard)
               area           no dot; italic label (a sea or region)
               waypoint       no dot, no label; bends the line round a coast
               text           free label only (e.g. "PACIFIC OCEAN"); not on the track
  aboard     subject | ship (anything other than "subject" draws an open dot,
             and keeps the point off the subject's track)
  source     citation for the point (not drawn; keep every point sourced)
  note       free text (not drawn)
  label      text to print; "\\n" for a line break; blank for none
  label_dx, label_dy   label offset from the point, in degrees (default 1.5, 0)
  label_ha   left | right | center (default: left, or right when label_dx < 0)
  gap_before yes/true/1: the leg from the previous track point is unrecorded
  gap_label  text for that gap (default "not recorded"; "-" for none)
  gap_dx, gap_dy  offset of the gap label from the leg's midpoint, in degrees

Extent comes from the points (padded) unless --extent W,E,S,N is given. When
the route crosses the 180th meridian, longitudes are drawn 0-360 so the
Pacific stays in one piece (an --extent with values over 180 forces that).

Land: Natural Earth 1:50m (public domain), downloaded once to
facts/records/_raw/geo/ne_50m_land.geojson (or --land PATH).
Fonts: EB Garamond if installed in a usual font folder, else matplotlib's serif.
"""
import argparse
import csv
import json
import math
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _project as P  # noqa: E402

LAND_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
            "master/geojson/ne_50m_land.geojson")
USER_AGENT = "Lineage (open-source family-history tools)"
INK, PAPER, LANDC = "#1a1a1a", "white", "#d9d9d9"
FONT_DIRS = ["~/Library/Fonts", "/Library/Fonts", "/usr/share/fonts",
             "/usr/local/share/fonts", "~/.local/share/fonts", "~/.fonts",
             "C:/Windows/Fonts"]
YES = {"yes", "y", "true", "1", "x"}


def setup_fonts(plt):
    from matplotlib import font_manager as fm
    found = False
    for d in FONT_DIRS:
        root = Path(d).expanduser()
        if not root.is_dir():
            continue
        try:
            for f in list(root.rglob("EBGaramond*.otf")) + list(root.rglob("EBGaramond*.ttf")):
                try:
                    fm.fontManager.addfont(str(f))
                    found = True
                except Exception:
                    pass
        except Exception:
            pass
    plt.rcParams["font.family"] = ["EB Garamond", "serif"] if found else ["serif"]


def fnum(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def read_track(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        for n, r in enumerate(csv.DictReader(fh), start=2):
            r = {k.strip(): (v or "").strip() for k, v in r.items() if k}
            if not r.get("lat") or not r.get("lon"):
                print(f"{path}:{n}: no lat/lon, skipped", file=sys.stderr)
                continue
            r["lat"], r["lon"] = float(r["lat"]), float(r["lon"])
            r["kind"] = (r.get("kind") or "position").lower()
            r["seqn"] = fnum(r.get("seq"), n)
            rows.append(r)
    if not rows:
        sys.exit(f"{path}: no usable rows")
    return sorted(rows, key=lambda r: r["seqn"])


def choose_wrap(lons, extent):
    """True if longitudes should run 0-360."""
    if extent:
        return extent[0] > 180 or extent[1] > 180 or extent[0] > extent[1]
    def span(xs):
        return max(xs) - min(xs) if xs else 0
    return span([x % 360 for x in lons]) < span(lons)


def main():
    ap = argparse.ArgumentParser(description="Evidence-coded B&W route map from a track CSV.")
    P.add_project_arg(ap)
    ap.add_argument("track", help="track CSV (see --help for columns)")
    ap.add_argument("--out", default="photos/print/route-map.png")
    ap.add_argument("--title")
    ap.add_argument("--caption")
    ap.add_argument("--extent", help="W,E,S,N in degrees (e.g. 102,342,-8,76 or -80,-60,30,45)")
    ap.add_argument("--pad", type=float, default=0.12, help="auto-extent padding fraction (0.12)")
    ap.add_argument("--width", type=float, default=6.4, help="figure width in inches (6.4)")
    ap.add_argument("--subject", help="name in the legend (default: book.yaml subject)")
    ap.add_argument("--vessel", default="the ship", help='legend wording for open dots ("the ship")')
    ap.add_argument("--auto-labels", action="store_true", help="label dots with `place` when `label` is blank")
    ap.add_argument("--land", default="facts/records/_raw/geo/ne_50m_land.geojson")
    ap.add_argument("--no-grid", action="store_true")
    ap.add_argument("--legend-loc", default="lower left")
    a = ap.parse_args()
    P.enter_project(a.project)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Polygon
    setup_fonts(plt)

    book = P.load_book()
    subject = a.subject or (book.get("narration") or {}).get("subject_name") \
        or (book.get("narrator") or {}).get("name") or "the subject"
    rows = read_track(a.track)

    extent = [float(v) for v in a.extent.split(",")] if a.extent else None
    if extent and len(extent) != 4:
        sys.exit("--extent wants W,E,S,N")
    wrap = choose_wrap([r["lon"] for r in rows], extent)
    def x(lon):
        return lon % 360 if wrap else lon
    for r in rows:
        r["x"] = x(r["lon"])
    if extent:
        W, E, S, N = extent
        if wrap:
            W, E = W % 360, E % 360 or 360
    else:
        xs = [r["x"] for r in rows]
        ys = [r["lat"] for r in rows]
        dx = max(max(xs) - min(xs), 2.0)
        dy = max(max(ys) - min(ys), 2.0)
        W, E = min(xs) - dx * a.pad, max(xs) + dx * a.pad
        S, N = max(min(ys) - dy * a.pad * 1.6, -89), min(max(ys) + dy * a.pad, 89)

    land = Path(a.land)
    if not land.exists():
        print(f"downloading Natural Earth land -> {land}", file=sys.stderr)
        land.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(LAND_URL, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=120) as resp:
            land.write_bytes(resp.read())

    mid = math.radians((S + N) / 2)
    aspect = 1 / max(math.cos(mid), 0.2)
    h = a.width * (N - S) * aspect / (E - W)
    h = min(max(h, 1.6), 9.0)
    extra = (0.3 if a.title else 0) + (0.35 if a.caption else 0)
    fig, ax = plt.subplots(figsize=(a.width, h + extra), dpi=300)
    fig.patch.set_facecolor(PAPER)
    ax.set_facecolor(PAPER)

    for feat in json.loads(land.read_text())["features"]:
        g = feat["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            ring = poly[0]
            lo = min(c[0] for c in ring)
            hi = max(c[0] for c in ring)
            la0 = min(c[1] for c in ring)
            la1 = max(c[1] for c in ring)
            if la1 < S or la0 > N:
                continue
            for shift in (-360, 0, 360):          # the axes clip what is off-map
                if hi + shift < W or lo + shift > E:
                    continue
                ax.add_patch(Polygon([(c[0] + shift, c[1]) for c in ring], closed=True,
                                     facecolor=LANDC, edgecolor=INK, linewidth=0.3, zorder=1))

    if not a.no_grid:
        span = max(E - W, N - S)
        step = 30 if span > 120 else 20 if span > 60 else 10 if span > 25 else 5 if span > 10 else 1
        g = math.ceil(W / step) * step
        while g <= E:
            ax.axvline(g, color=INK, lw=0.15, alpha=0.35, zorder=0)
            g += step
        g = math.ceil(S / step) * step
        while g <= N:
            ax.axhline(g, color=INK, lw=0.15 if g else 0.3, alpha=0.35 if g else 0.6, zorder=0)
            g += step
        if S < 0 < N:
            ax.text(W + (E - W) * 0.01, 0.4, "Equator", fontsize=5, style="italic",
                    color=INK, alpha=0.8, zorder=2)

    # the subject's track, broken at unrecorded legs
    track = [r for r in rows if r["kind"] != "text" and r.get("aboard", "").lower() == "subject"]
    legs, cur, gaps = [], [], []
    for r in track:
        if cur and (r.get("gap_before", "").lower() in YES):
            legs.append(cur)
            gaps.append((cur[-1], r))
            cur = []
        cur.append(r)
    if cur:
        legs.append(cur)
    dash = (0, (3, 1.6))
    for leg in legs:
        if len(leg) > 1:
            ax.plot([r["x"] for r in leg], [r["lat"] for r in leg], color=INK, lw=0.9,
                    ls=dash, zorder=3, solid_capstyle="round")
    for prev, nxt in gaps:
        text = nxt.get("gap_label") or "not recorded"
        if text == "-":
            continue
        mx = (prev["x"] + nxt["x"]) / 2 + fnum(nxt.get("gap_dx"))
        my = (prev["lat"] + nxt["lat"]) / 2 + fnum(nxt.get("gap_dy"))
        ax.text(mx, my, text.replace("\\n", "\n"), fontsize=5.4, ha="center", va="center",
                style="italic", color=INK, zorder=6)

    box = dict(boxstyle="square,pad=0.15", fc=PAPER, ec="none", alpha=0.85)
    for r in rows:
        k = r["kind"]
        if k in ("port", "position"):
            filled = r.get("aboard", "").lower() == "subject"
            ax.plot(r["x"], r["lat"], marker="o", ms=3.2, mfc=INK if filled else PAPER,
                    mec=INK, mew=0.7, zorder=5)
        label = r.get("label") or (r.get("place") if a.auto_labels and k in ("port", "position") else "")
        if not label or k == "waypoint":
            continue
        dxl = fnum(r.get("label_dx"), 0.0 if k in ("text", "area") else 1.5)
        dyl = fnum(r.get("label_dy"), 0.0)
        ha = r.get("label_ha") or ("center" if k in ("text", "area") else "right" if dxl < 0 else "left")
        if k == "text":
            ax.text(r["x"] + dxl, r["lat"] + dyl, label.replace("\\n", "\n"), fontsize=7,
                    ha=ha, va="center", color=INK, alpha=0.75, linespacing=1.1, zorder=2)
        else:
            ax.text(r["x"] + dxl, r["lat"] + dyl, label.replace("\\n", "\n"), fontsize=5.6,
                    ha=ha, va="center", color=INK, zorder=6, bbox=box, linespacing=1.05,
                    style="italic" if k == "area" else "normal")

    handles = [
        Line2D([], [], color=INK, lw=0.9, ls=dash, label="track, approximate between recorded places"),
        Line2D([], [], ls="", marker="o", ms=3.2, mfc=INK, mec=INK, label=f"recorded, {subject} aboard"),
    ]
    if any(r["kind"] in ("port", "position") and r.get("aboard", "").lower() != "subject" for r in rows):
        handles.append(Line2D([], [], ls="", marker="o", ms=3.2, mfc=PAPER, mec=INK, mew=0.7,
                              label=f"recorded, {a.vessel} without {subject}"))
    leg = ax.legend(handles=handles, loc=a.legend_loc, fontsize=5, frameon=True, fancybox=False,
                    edgecolor=INK, framealpha=0.9, handlelength=2.4, borderpad=0.5)
    leg.get_frame().set_linewidth(0.4)
    leg.set_zorder(7)

    ax.set_xlim(W, E)
    ax.set_ylim(S, N)
    ax.set_aspect(aspect)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_linewidth(0.8)
        s.set_color(INK)
    if a.title:
        ax.set_title(a.title, fontsize=9, color=INK, pad=5)
    if a.caption:
        fig.text(0.5, 0.01, a.caption, ha="center", va="bottom", fontsize=6, style="italic",
                 color=INK, wrap=True)
    fig.tight_layout(pad=0.15, rect=(0, 0.05 if a.caption else 0, 1, 1))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, facecolor=PAPER, bbox_inches="tight", pad_inches=0.04)
    print(out)


if __name__ == "__main__":
    main()
