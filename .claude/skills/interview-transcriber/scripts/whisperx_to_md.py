#!/usr/bin/env python3
"""Convert WhisperX JSON (with diarization) into verbatim + clean Markdown transcripts.

Usage:
  whisperx_to_md.py raw.json --session S1 --map SPEAKER_00=Grandma --map SPEAKER_01=Sam \
      --verbatim out/verbatim/S1.md --clean out/clean/S1.md
"""
import argparse, json, re
from pathlib import Path

FILLERS = re.compile(r"\b(?:um+|uh+|er+|erm+|hmm+|mm+)\b[,.]?\s*", re.I)
STUTTER = re.compile(r"\b(\w+)(?:\s+\1\b)+", re.I)
# Repeats that are usually deliberate grammar or emphasis, not stumbles.
KEEP_REPEATS = {"had", "that", "very", "no", "so", "really", "far", "long", "never", "back"}
PAUSE_BREAK = 2.0
LOW_SCORE = 0.5


def ts(sec):
    sec = int(sec or 0)
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def seg_words(seg):
    """Return list of (text, start, score) with low-confidence words marked."""
    out = []
    for w in seg.get("words") or []:
        word = w.get("word", "").strip()
        if not word:
            continue
        score = w.get("score")
        if score is not None and score < LOW_SCORE:
            word = f"[?{word}?]"
        out.append(word)
    if not out:
        out = [seg.get("text", "").strip()]
    return " ".join(out)


def clean_text(t):
    t = FILLERS.sub("", t)
    t = STUTTER.sub(lambda m: m.group(0) if m.group(1).lower() in KEEP_REPEATS else m.group(1), t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    t = re.sub(r"\s+([,.?!])", r"\1", t)
    if t:
        t = t[0].upper() + t[1:]
    return t


def build(segments, session, mapping):
    paras = []  # (speaker, start, text)
    last_end, last_spk = None, None
    for seg in segments:
        spk = mapping.get(seg.get("speaker"), seg.get("speaker") or "UNKNOWN")
        start, end = seg.get("start", 0), seg.get("end", 0)
        text = seg_words(seg)
        if last_end is not None and start - last_end > 30:
            paras.append((None, last_end, f"[inaudible {ts(last_end)}]"))
        new_para = (spk != last_spk) or (last_end is None) or (start - last_end > PAUSE_BREAK)
        if new_para:
            paras.append([spk, start, text])
        else:
            paras[-1][2] += " " + text
        last_end, last_spk = end, spk
    return paras


def render(paras, session, clean):
    lines = []
    for spk, start, text in paras:
        body = clean_text(text) if clean else text.strip()
        if not body:
            continue
        if spk is None:
            lines.append(body)
        else:
            lines.append(f"**{spk}** [{session} {ts(start)}] {body}")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json")
    ap.add_argument("--session", required=True)
    ap.add_argument("--map", action="append", default=[], help="SPEAKER_00=Grandma (labels from book.yaml)")
    ap.add_argument("--verbatim", required=True)
    ap.add_argument("--clean", required=True)
    a = ap.parse_args()
    mapping = dict(m.split("=", 1) for m in a.map)
    data = json.loads(Path(a.json).read_text())
    paras = build(data.get("segments", []), a.session, mapping)
    for path, clean in ((a.verbatim, False), (a.clean, True)):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(render(paras, a.session, clean))
    unmapped = {s for s, _, _ in paras if s and s.startswith("SPEAKER_")}
    words = {}
    for s, _, t in paras:
        if s:
            words[s] = words.get(s, 0) + len(t.split())
    flags = sum(t.count("[?") + t.count("[inaudible") for _, _, t in paras)
    print(json.dumps({"session": a.session, "words": words, "flags": flags,
                      "unmapped_speakers": sorted(unmapped)}, indent=2))


if __name__ == "__main__":
    main()
