#!/usr/bin/env python3
"""Render transcript/raw/*.json into labelled verbatim + clean Markdown.

    python $BOOKASSEMBLER/scripts/render_transcripts.py           # every session
    python $BOOKASSEMBLER/scripts/render_transcripts.py S2 S3     # some sessions

Run from the book project folder (or --project DIR).

Inputs
  transcript/raw/<S>.json        WhisperX output -- read only, never edited
  transcript/sessions.csv        session list + file/recorded/duration
  transcript/corrections.json    speaker_map, spelling, drop_segments,
                                 scrub_inline (see corrections.example.json)
  book.yaml                      narrator/interviewer names and labels
Outputs
  transcript/verbatim/<S>.md     every word, low-confidence words as [?word?]
  transcript/clean/<S>.md        fillers/stutters removed; the citable text
  transcript/master.md           all clean sessions in order

Corrections are applied here, at render time, rather than by editing the raw
JSON, so a re-render is reproducible and no timestamp that the book cites
ever shifts. Order of application:
  1. drop_segments: a raw segment whose text matches any pattern is dropped
     whole (Whisper echoing the initial prompt as if it were speech).
  2. paragraphs are built from the word arrays (whisperx_to_md.py).
  3. scrub_inline then spelling are applied to each paragraph's text (an echo
     embedded inside a real paragraph; approved spelling fixes).

The paragraph builder is the interview-transcriber skill's whisperx_to_md.py,
loaded from ./.claude/skills/ (the project's symlink) or, failing that, from
$BOOKASSEMBLER/.claude/skills/.
"""
import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _project as P  # noqa: E402

SKILL_REL = Path(".claude/skills/interview-transcriber/scripts/whisperx_to_md.py")
CORRECTIONS = Path("transcript/corrections.json")


def load_whisperx_to_md():
    cands = [Path.cwd() / SKILL_REL]
    if os.environ.get("BOOKASSEMBLER"):
        cands.append(Path(os.environ["BOOKASSEMBLER"]).expanduser() / SKILL_REL)
    cands.append(HERE.parent / SKILL_REL)  # a repo checkout (.claude/skills)
    cands.append(HERE.parent / "skills" / SKILL_REL.relative_to(".claude/skills"))  # the plugin itself
    for c in cands:
        if c.exists():
            spec = importlib.util.spec_from_file_location("whisperx_to_md", c)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    sys.exit("whisperx_to_md.py not found. Looked in:\n  " + "\n  ".join(map(str, cands))
             + "\nLink the skills into the project (ln -s $BOOKASSEMBLER/.claude .claude) "
               "or set BOOKASSEMBLER.")


def load_corrections():
    if not CORRECTIONS.exists():
        print(f"note: no {CORRECTIONS}; rendering with raw speaker IDs and no fixes "
              f"(copy $BOOKASSEMBLER/scripts/corrections.example.json to start one)",
              file=sys.stderr)
        return {}
    return json.loads(CORRECTIONS.read_text(encoding="utf-8"))


class Fixer:
    def __init__(self, corr):
        def rules(items):
            return [(re.compile(r["find"]), r["replace"]) for r in items or []]
        self.spell = rules(corr.get("spelling"))
        self.scrub = rules((corr.get("scrub_inline") or {}).get("patterns"))
        self.drop = [re.compile(p) for p in (corr.get("drop_segments") or {}).get("patterns", [])]
        # speaker_map is either one map for every session {"SPEAKER_00": "Grandma", ...}
        # or per session {"S1": {"SPEAKER_00": "Grandma", ...}, "S2": {...}}: diarization
        # clusters are numbered per file, so SPEAKER_00 can be a different person in each.
        raw = {k: v for k, v in (corr.get("speaker_map") or {}).items() if not k.startswith("_")}
        self.per_session = {k: v for k, v in raw.items() if isinstance(v, dict)}
        self.default_map = {k: v for k, v in raw.items() if not isinstance(v, dict)}
        self.smap = self.default_map

    def for_session(self, sid):
        self.smap = self.per_session.get(sid, self.default_map)
        return self.smap

    def text(self, t):
        for pat, rep in self.scrub:
            t = pat.sub(rep, t)
        for pat, rep in self.spell:
            t = pat.sub(rep, t)
        return re.sub(r"\s{2,}", " ", t).strip()


def topics(paras, narrator, gap=240, min_words=8):
    """Neutral navigation markers: the first long narrator paragraph after each gap."""
    marks, last = [], -10 ** 9
    for spk, start, text in paras:
        if spk != narrator or start - last < gap or len(text.split()) < min_words:
            continue
        marks.append((start, text))
        last = start
    return marks


def yaml_str(s):
    return json.dumps(str(s), ensure_ascii=False)


def render_session(W, row, fx, narrator, interviewer):
    sid = row["session"]
    data = json.loads(Path(f"transcript/raw/{sid}.json").read_text(encoding="utf-8"))
    segs, dropped = [], []
    for s in data.get("segments", []):
        t = s.get("text", "")
        if any(p.search(t) for p in fx.drop):
            dropped.append((s.get("start", 0), t.strip()))
        else:
            segs.append(s)
    fx.for_session(sid)
    paras = [[spk, st, fx.text(t)] for spk, st, t in W.build(segs, sid, fx.smap)]
    # a paragraph that was nothing but a scrubbed echo leaves only punctuation
    paras = [p for p in paras if re.search(r"\w", p[2])]

    words = {}
    for spk, _, t in paras:
        if spk:
            words[spk] = words.get(spk, 0) + len(t.split())
    flags = sum(t.count("[?") + t.count("[inaudible") for _, _, t in paras)
    unmapped = sorted({s for s, _, _ in paras if s and (s.startswith("SPEAKER_") or s == "UNKNOWN")})
    dur = row.get("duration") or P.hms(segs[-1].get("end", 0) if segs else 0)
    inv = {v: k for k, v in fx.smap.items()}
    spk_line = ", ".join(f"{lab}: {inv[lab]}" for lab in (narrator, interviewer) if lab in inv)
    spk_line = "{" + spk_line + "}" if spk_line else "{}   # speaker_map not set -- confirm by ear"

    hdr = ["---",
           f"session: {sid}",
           f"file: {yaml_str(row.get('file', ''))}",
           f"recorded: {row.get('recorded', '')}",
           'place: ""',
           f"speakers: {spk_line}",
           f"duration: {dur}",
           "words: {" + ", ".join(f"{k}: {v}" for k, v in sorted(words.items())) + "}",
           f"prompt_echo_segments_removed: {len(dropped)}",
           "---", "", "## Topics"]
    for st, txt in topics(paras, narrator):
        hdr.append(f"- {W.ts(st)} " + " ".join(W.clean_text(txt).split()[:11]).rstrip(".,"))
    hdr.append("")
    head = "\n".join(hdr) + "\n"
    for layer, clean in (("verbatim", False), ("clean", True)):
        p = Path(f"transcript/{layer}/{sid}.md")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(head + W.render(paras, sid, clean), encoding="utf-8")

    summary = "  ".join(f"{k} {v:>6}w" for k, v in sorted(words.items()))
    print(f"{sid}: {summary}  flags {flags:>4}  echo-cut {len(dropped)}  "
          f"unmapped {unmapped or 'none'}")
    for st, t in dropped:
        print(f"     cut [{sid} {W.ts(st)}] {t[:78]}")
    return unmapped


def main():
    ap = argparse.ArgumentParser(description="Render raw WhisperX JSON to Markdown transcripts.")
    P.add_project_arg(ap)
    ap.add_argument("sessions", nargs="*", help="session IDs (default: all)")
    a = ap.parse_args()
    P.enter_project(a.project)

    W = load_whisperx_to_md()
    book = P.load_book()
    narrator, interviewer = P.labels(book)
    fx = Fixer(load_corrections())
    rows = P.read_sessions()
    if a.sessions:
        rows = [r for r in rows if r["session"] in a.sessions]
    if not rows:
        sys.exit("no sessions (transcript/sessions.csv or transcript/raw/*.json)")

    any_unmapped = False
    for row in rows:
        if not Path(f"transcript/raw/{row['session']}.json").exists():
            print(f"{row['session']}: no transcript/raw/{row['session']}.json yet, skipped")
            continue
        any_unmapped |= bool(render_session(W, row, fx, narrator, interviewer))

    # master.md always covers every rendered session, in session order
    name = (book.get("narrator") or {}).get("name") or narrator
    parts = [f"# Interviews with {name}", "",
             "Source of truth for the whole book. Clean layer, all sessions in session order.",
             "Citations elsewhere use the form `[S2 00:14:07]`.", ""]
    for row in P.read_sessions():
        p = Path(f"transcript/clean/{row['session']}.md")
        if p.exists():
            when = row.get("recorded") or "date unknown"
            parts.append(f"\n# Session {row['session']} -- {when} ({row.get('duration') or '?'})\n")
            parts.append(p.read_text(encoding="utf-8"))
    Path("transcript/master.md").write_text("\n".join(parts), encoding="utf-8")
    print(f"\nmaster.md: {len(Path('transcript/master.md').read_text().split())} words")
    if any_unmapped:
        print("NOTE: some speakers are unmapped -- confirm by ear and add them to "
              "speaker_map in transcript/corrections.json")


if __name__ == "__main__":
    main()
