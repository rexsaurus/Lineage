#!/usr/bin/env python3
"""Add speaker labels to WhisperX JSON that has already been transcribed.

    export HF_TOKEN=hf_xxxxxxxx
    python $LINEAGE/scripts/diarize.py            # every session without speakers
    python $LINEAGE/scripts/diarize.py S1 S3      # named sessions
    python $LINEAGE/scripts/diarize.py --chunked always S2

Run from the book project folder (or pass --project DIR). Reads
transcript/raw/<S>.json and transcript/work/<S>.wav (both made by
transcribe.sh) and writes the speaker labels into the same JSON.

Why a separate pass: diarization is the step most likely to fail (gated
models, token problems, version breakage). Keeping it apart from ASR means a
failure here never forces a re-transcription -- and re-running ASR moves every
timestamp the book cites. This pass only ADDS `speaker` keys: it checks that
every segment start/end is unchanged before it writes, and writes atomically.

Long sessions: pyannote's clustering cost grows superlinearly with length, so
by default any session longer than --chunk-over minutes (20) is diarized in
overlapping windows and stitched (see diarize_chunked.py).

Hugging Face access (one-time):
  1. Create a READ token at https://huggingface.co/settings/tokens
  2. While logged in, open and accept the user conditions on BOTH
       https://huggingface.co/pyannote/speaker-diarization-3.1
       https://huggingface.co/pyannote/segmentation-3.0
     These are gated repos: the models are free, but each asks you to accept
     its licence terms (and share contact details) before download.
  3. export HF_TOKEN=hf_xxxxxxxx
  A 401/403 or "GatedRepoError" when the pipeline loads means the token is
  wrong or one of the two licences has not been accepted with that account.

When book.yaml has transcription_locked: true, sessions that already have
speakers are never touched and --force is refused; only a session that has
never been diarized (e.g. a newly added recording) can still be labelled.
Speaker count defaults to 2 + len(other_speakers) from book.yaml
(override with --min-speakers/--max-speakers or MIN_SPEAKERS/MAX_SPEAKERS).
"""
import argparse
import json
import os
import sys
import time
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _project as P  # noqa: E402

RAW, WORK = Path("transcript/raw"), Path("transcript/work")
SR = 16000

LICENCE_HELP = """\
Could not load the pyannote diarization models from Hugging Face.
  * Is HF_TOKEN a valid READ token?  (https://huggingface.co/settings/tokens)
  * Have you accepted the user conditions on BOTH gated repos, logged in as
    the account that owns the token?
        https://huggingface.co/pyannote/speaker-diarization-3.1
        https://huggingface.co/pyannote/segmentation-3.0
  A 403 almost always means one of those licences was not accepted."""


def need_token():
    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("HF_TOKEN is not set. Diarization uses gated pyannote models.\n"
                 "  1. accept the licences on huggingface.co/pyannote/speaker-diarization-3.1\n"
                 "     and huggingface.co/pyannote/segmentation-3.0\n"
                 "  2. export HF_TOKEN=hf_xxxxxxxx   (a read token)\n"
                 "  3. re-run this script")
    return token


def load_pipeline(token, device):
    import hf_compat  # noqa: F401  (must precede whisperx/pyannote)
    from whisperx.diarize import DiarizationPipeline
    try:
        return DiarizationPipeline(use_auth_token=token, device=device)
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        if any(k in msg for k in ("401", "403", "Gated", "gated", "Unauthorized",
                                   "NoneType", "authenticat")):
            sys.exit(f"{msg}\n\n{LICENCE_HELP}")
        raise


def timing(result):
    return [(s.get("start"), s.get("end")) for s in result.get("segments", [])]


def write_atomic(path, data):
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def run(sessions, mode="auto", chunk_over=20.0, chunk=600.0, overlap=60.0,
        min_speakers=None, max_speakers=None, device="cpu", force=False):
    warnings.filterwarnings("ignore")
    book = P.load_book()
    if force and P.transcription_locked(book):
        sys.exit("book.yaml has transcription_locked: true -- refusing --force. "
                 "Re-labelling speakers changes every attribution downstream; unlock "
                 "it deliberately if you really mean to.")
    lo, hi = P.speaker_bounds(book)
    min_speakers = min_speakers or lo
    max_speakers = max_speakers or hi
    sessions = sessions or [r["session"] for r in P.read_sessions()]
    if not sessions:
        sys.exit("no sessions found (transcript/sessions.csv or transcript/raw/*.json)")

    token = need_token()
    import whisperx
    pipe = None
    failed = 0
    for sid in sessions:
        jf, wav = RAW / f"{sid}.json", WORK / f"{sid}.wav"
        if not jf.exists():
            print(f"== {sid}: no {jf}, skipping (run transcribe.sh first)")
            continue
        if not wav.exists():
            print(f"== {sid}: no {wav}, skipping (transcribe.sh makes it)")
            failed += 1
            continue
        result = json.loads(jf.read_text(encoding="utf-8"))
        if any(s.get("speaker") for s in result.get("segments", [])) and not force:
            print(f"== {sid}: already diarized, skipping (--force to redo)")
            continue
        for s in result.get("segments", []):          # --force: start clean
            s.pop("speaker", None)
            for w in s.get("words") or []:
                w.pop("speaker", None)
        before = timing(result)

        if pipe is None:
            pipe = load_pipeline(token, device)
        audio = whisperx.load_audio(str(wav))
        dur = len(audio) / SR
        chunked = mode == "always" or (mode == "auto" and dur > chunk_over * 60)
        print(f"== {sid}: {dur / 60:.1f} min, {'chunked' if chunked else 'whole file'}, "
              f"speakers {min_speakers}-{max_speakers}", flush=True)
        t0 = time.time()
        if chunked:
            from diarize_chunked import diarize_in_chunks
            dsegs = diarize_in_chunks(pipe, audio, chunk, overlap, min_speakers, max_speakers)
        else:
            dsegs = pipe(audio, min_speakers=min_speakers, max_speakers=max_speakers)
        merged = whisperx.assign_word_speakers(dsegs, result)
        if timing(merged) != before:
            print(f"== {sid}: REFUSING TO WRITE -- segment timings changed during "
                  "speaker assignment; raw JSON left untouched")
            failed += 1
            continue
        write_atomic(jf, merged)
        spk = {}
        for s in merged.get("segments", []):
            if s.get("speaker"):
                spk[s["speaker"]] = spk.get(s["speaker"], 0) + len(s.get("text", "").split())
        print(f"== {sid}: done in {time.time() - t0:.0f}s  words/speaker: {spk}", flush=True)
    print("\nNext: listen to a minute of each session, decide which SPEAKER_xx is "
          "the narrator, and record it in transcript/corrections.json speaker_map.")
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser(description="Diarize already-transcribed sessions.")
    P.add_project_arg(ap)
    ap.add_argument("sessions", nargs="*", help="session IDs (default: all)")
    ap.add_argument("--chunked", choices=["auto", "always", "never"], default="auto")
    ap.add_argument("--chunk-over", type=float, default=20.0,
                    help="auto mode: chunk sessions longer than this many minutes (20)")
    ap.add_argument("--chunk", type=float, default=600.0, help="window seconds (600)")
    ap.add_argument("--overlap", type=float, default=60.0, help="window overlap seconds (60)")
    ap.add_argument("--min-speakers", type=int)
    ap.add_argument("--max-speakers", type=int)
    ap.add_argument("--device", default=os.environ.get("DIARIZE_DEVICE", "cpu"),
                    help="cpu (default) or cuda")
    ap.add_argument("--force", action="store_true", help="re-diarize sessions that have speakers")
    a = ap.parse_args()
    P.enter_project(a.project)
    sys.exit(run(a.sessions, a.chunked, a.chunk_over, a.chunk, a.overlap,
                 a.min_speakers, a.max_speakers, a.device, a.force))


if __name__ == "__main__":
    main()
