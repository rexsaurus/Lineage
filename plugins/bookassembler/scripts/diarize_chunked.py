#!/usr/bin/env python3
"""Chunked speaker diarization with cross-chunk speaker stitching.

    python $BOOKASSEMBLER/scripts/diarize_chunked.py S2 S5 [--chunk 600] [--overlap 60]

Same as `diarize.py --chunked always` (diarize.py switches to this
automatically for sessions over 20 minutes). Run from the book project folder.

Why it exists -- measured on CPU with pyannote/speaker-diarization-3.1:
pyannote's clustering cost grows superlinearly with audio length. A 6-10
minute file cost ~32 s of compute per audio-minute; a 34-minute file cost
~119 s per audio-minute; extrapolated, a 2-hour interview would have taken
~14 hours in one piece. Cutting the audio into fixed windows keeps the
per-minute cost flat, so a 2-hour session costs roughly 12 x a 10-minute one.

The price of chunking is that SPEAKER_00 in one window has no relation to
SPEAKER_00 in the next. So windows overlap (60 s by default), and each new
window's labels are mapped onto the running labels by how much their speech
actually coincides in time inside the overlap. Each window's log line reports
how many of its speakers were matched that way ("stitched 2/2 by overlap");
anything less than all of them deserves a listen at that seam.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _project as P  # noqa: E402

SR = 16000


def _overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def stitch(prev_df, cur_df, win_start, win_end):
    """Map cur_df speaker labels onto prev_df's labels using the speech they
    share inside [win_start, win_end]. Returns (mapping, matched, n_speakers)."""
    canon = sorted(prev_df["speaker"].unique())
    cur = sorted(cur_df["speaker"].unique())
    prev_w = prev_df[(prev_df["end"] > win_start) & (prev_df["start"] < win_end)]
    cur_w = cur_df[(cur_df["end"] > win_start) & (cur_df["start"] < win_end)]
    score = {}
    for c in cur:
        cs = cur_w[cur_w["speaker"] == c][["start", "end"]].to_numpy()
        for k in canon:
            ks = prev_w[prev_w["speaker"] == k][["start", "end"]].to_numpy()
            tot = 0.0
            for r0, r1 in cs:
                for q0, q1 in ks:
                    tot += _overlap(max(r0, win_start), min(r1, win_end),
                                    max(q0, win_start), min(q1, win_end))
            score[(c, k)] = tot
    mapping, used = {}, set()
    for c, k in sorted(score, key=lambda p: -score[p]):
        if c in mapping or k in used or score[(c, k)] <= 0:
            continue
        mapping[c] = k
        used.add(k)
    # an unmatched window speaker takes a free existing label, else a new one
    free = [k for k in canon if k not in used]
    n = 0
    for c in cur:
        if c in mapping:
            continue
        if free:
            mapping[c] = free.pop(0)
        else:
            while f"SPEAKER_{n:02d}" in used or f"SPEAKER_{n:02d}" in canon:
                n += 1
            mapping[c] = f"SPEAKER_{n:02d}"
        used.add(mapping[c])
    matched = sum(1 for c in cur if score.get((c, mapping[c]), 0) > 0)
    return mapping, matched, len(cur)


def diarize_in_chunks(pipe, audio, chunk=600.0, overlap=60.0,
                      min_speakers=2, max_speakers=2, log=print):
    """Diarize a 16 kHz mono array in overlapping windows; return one
    pyannote-style DataFrame (start, end, speaker) with stitched labels."""
    import time
    import numpy as np
    import pandas as pd

    if overlap >= chunk:
        raise ValueError("--overlap must be shorter than --chunk")
    dur = len(audio) / SR
    step = chunk - overlap
    starts = [0.0] if dur <= chunk else [float(s) for s in np.arange(0, dur - overlap, step)]
    log(f"   {dur / 60:.1f} min -> {len(starts)} window(s) of {chunk / 60:.0f} min "
        f"(overlap {overlap:.0f}s)")
    merged = None
    for i, st in enumerate(starts):
        en = min(st + chunk, dur)
        c0 = time.time()
        df = pipe(audio[int(st * SR):int(en * SR)],
                  min_speakers=min_speakers, max_speakers=max_speakers).copy()
        if "segment" in df.columns:
            df = df.drop(columns=["segment"])
        df["start"] += st
        df["end"] += st
        if merged is None:
            merged, note = df, "anchor"
        else:
            prev_end = float(merged["end"].max())
            mp, matched, n = stitch(merged, df, st, min(prev_end, en))
            df["speaker"] = df["speaker"].map(mp)
            note = f"stitched {matched}/{n} by overlap"
            # cut both sides at the middle of the overlap so the seam isn't doubled
            seam = st + overlap / 2
            merged = merged[merged["start"] < seam].copy()
            merged.loc[merged["end"] > seam, "end"] = seam
            df = df[df["end"] > seam].copy()
            df.loc[df["start"] < seam, "start"] = seam
            merged = pd.concat([merged, df], ignore_index=True)
        log(f"   [{i + 1}/{len(starts)}] {st / 60:5.1f}-{en / 60:5.1f} min  "
            f"{time.time() - c0:5.0f}s  {note}")
    return merged.sort_values("start").reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser(description="Chunked diarization (diarize.py --chunked always).")
    P.add_project_arg(ap)
    ap.add_argument("sessions", nargs="*")
    ap.add_argument("--chunk", type=float, default=600.0)
    ap.add_argument("--overlap", type=float, default=60.0)
    ap.add_argument("--min-speakers", type=int)
    ap.add_argument("--max-speakers", type=int)
    ap.add_argument("--device", default=os.environ.get("DIARIZE_DEVICE", "cpu"))
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    P.enter_project(a.project)
    import diarize
    sys.exit(diarize.run(a.sessions, "always", 0, a.chunk, a.overlap,
                         a.min_speakers, a.max_speakers, a.device, a.force))


if __name__ == "__main__":
    main()
