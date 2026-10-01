#!/usr/bin/env python3
"""Keep transcript/sessions.csv in step with audio/.

  python $BOOKASSEMBLER/scripts/sessions.py            # sync and show the session list
  python $BOOKASSEMBLER/scripts/sessions.py --dry-run  # show what would be assigned

Every recording in audio/ gets a session ID (S1, S2, ...). IDs are assigned
once and never change: an existing row keeps its ID even if more files are
added later, and a row whose file has gone missing is kept (and warned about)
rather than renumbered, because every citation in the book ("[S2 00:14:07]")
depends on these IDs. New files are numbered in order of their embedded
recording date (ffprobe creation_time) where present, then by file name.

Columns: session,file,recorded,duration
  recorded  YYYY-MM-DD from the file's metadata, or blank -- fill it in by hand;
            a hand-entered value is never overwritten.
  duration  HH:MM:SS

Used by transcribe.sh (with --tsv) to build its work queue.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _project as P  # noqa: E402


def sync(dry_run=False):
    rows = P.read_sessions() if P.SESSIONS_CSV.exists() else []
    known = {r["file"]: r for r in rows}
    if not Path("audio").is_dir():
        sys.exit("audio/ does not exist -- put the original recordings there first")
    new = []
    for f in P.audio_files():
        rel = f.as_posix()
        if rel in known:
            r = known[rel]
            if not r.get("duration") or not r.get("recorded"):
                dur, created = P.probe(f)
                r["duration"] = r.get("duration") or (P.hms(dur) if dur else "")
                r["recorded"] = r.get("recorded") or created
            continue
        dur, created = P.probe(f)
        new.append(dict(file=rel, recorded=created, duration=P.hms(dur) if dur else ""))
    # dated files first in date order, undated after, each by file name (already sorted)
    new.sort(key=lambda r: (r["recorded"] == "", r["recorded"]))
    used = [P.session_key(r["session"])[1] for r in rows]
    nxt = max(used, default=0) + 1
    for r in new:
        r["session"] = f"S{nxt}"
        nxt += 1
        rows.append(r)
    for r in rows:
        if not Path(r["file"]).exists():
            print(f"warning: {r['session']}: {r['file']} is missing from audio/ "
                  "(row kept; IDs are never reused)", file=sys.stderr)
    if rows and not dry_run:
        P.write_sessions(rows)  # also records durations/dates filled in above
    return sorted(rows, key=lambda r: P.session_key(r["session"])), new


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    P.add_project_arg(ap)
    ap.add_argument("--dry-run", action="store_true", help="do not write sessions.csv")
    ap.add_argument("--tsv", action="store_true",
                    help="print 'session<TAB>file<TAB>seconds' for the selected sessions, "
                         "shortest first (for transcribe.sh)")
    ap.add_argument("targets", nargs="*",
                    help="session IDs (S3) or audio files (audio/x.m4a); default: all")
    a = ap.parse_args()
    P.enter_project(a.project)
    rows, new = sync(a.dry_run)

    sel = rows
    if a.targets:
        by_id = {r["session"]: r for r in rows}
        by_file = {Path(r["file"]).resolve(): r for r in rows}
        sel = []
        for t in a.targets:
            r = by_id.get(t) or by_file.get(Path(t).resolve())
            if not r:
                sys.exit(f"{t}: not a session ID or a file in audio/ "
                         "(recordings must be copied into audio/ first)")
            sel.append(r)
    sel = [r for r in sel if Path(r["file"]).exists()]

    if a.tsv:
        def seconds(r):
            return P.secs(r["duration"]) if r.get("duration") else 0
        for r in sorted(sel, key=seconds):
            print(f"{r['session']}\t{r['file']}\t{seconds(r)}")
        return
    for r in rows:
        mark = "  (new)" if r in new else ""
        print(f"{r['session']:>4}  {r['duration'] or '--:--:--'}  "
              f"{r['recorded'] or '(date unknown)':<14}  {r['file']}{mark}")
    if a.dry_run and new:
        print(f"--dry-run: {len(new)} new session(s) not written")


if __name__ == "__main__":
    main()
