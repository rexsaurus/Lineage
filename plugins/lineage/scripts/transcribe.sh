#!/usr/bin/env bash
#
# Lineage -- transcription (ASR first, speakers second).
#
# Run from the book project folder (or pass --project DIR):
#
#   $LINEAGE/scripts/transcribe.sh                 # every session, shortest first
#   $LINEAGE/scripts/transcribe.sh --smoke         # shortest session only
#   $LINEAGE/scripts/transcribe.sh --dry-run       # show the plan, do nothing
#   $LINEAGE/scripts/transcribe.sh S3              # one session
#   $LINEAGE/scripts/transcribe.sh audio/tape2.m4a # one file (must be in audio/)
#
# Flags:
#   --no-diarize   ASR only; run diarize.py later
#   --one-pass     legacy path: let the whisperx CLI diarize in the same run
#                  (needs HF_TOKEN up front; no chunking for long sessions)
#   --force        re-transcribe sessions that already have raw JSON
#                  (refused when book.yaml has transcription_locked: true)
#   --project DIR  book project folder (default: current directory)
#
# What it does, per session:
#   1. sessions.py assigns S1..Sn to the files in audio/ (stable; recorded in
#      transcript/sessions.csv; existing IDs never change)
#   2. ffmpeg -> transcript/work/<S>.wav (16 kHz mono; audio/ is only read)
#   3. WhisperX large-v3 + word alignment, via wx.py, with a SHORT
#      initial prompt built from book.yaml proper_nouns -> transcript/raw/<S>.json
#   4. diarize.py adds speaker labels to the JSON (if HF_TOKEN is set;
#      otherwise it tells you how to run it later -- ASR is never repeated)
#
# Idempotent: a session whose transcript/raw/<S>.json exists is skipped.
# Output is staged in a temp dir and moved into place only on success, so a
# crash three hours in never leaves a half-written file that looks complete.
#
# Env overrides: MODEL (large-v3), LANGUAGE (en), BATCH_SIZE (4), THREADS,
#                DEVICE, COMPUTE_TYPE, MIN_SPEAKERS, MAX_SPEAKERS, HF_TOKEN

set -euo pipefail

SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SMOKE=0; DRY_RUN=0; FORCE=0; DIARIZE=1; ONE_PASS=0; PROJECT="."
TARGETS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --smoke)      SMOKE=1 ;;
        --dry-run)    DRY_RUN=1 ;;
        --force)      FORCE=1 ;;
        --no-diarize) DIARIZE=0 ;;
        --one-pass)   ONE_PASS=1 ;;
        --project)    shift; PROJECT="${1:?--project needs a folder}" ;;
        --project=*)  PROJECT="${1#--project=}" ;;
        -h|--help)    sed -n '2,37p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        -*)           echo "unknown flag: $1" >&2; exit 2 ;;
        *)            TARGETS+=("$1") ;;
    esac
    shift
done

cd "$PROJECT" || { echo "no such project folder: $PROJECT" >&2; exit 2; }
PROJECT_DIR="$(pwd)"

# Python: the Lineage venv (make install), else the checkout's own venv, else PATH.
PYTHON=""
for cand in "${LINEAGE:-}/.venv/bin/python" "$SCRIPTS/../.venv/bin/python"; do
    if [[ -x "$cand" ]]; then PYTHON="$cand"; break; fi
done
[[ -n "$PYTHON" ]] || PYTHON="$(command -v python3 || true)"

MODEL="${MODEL:-large-v3}"
LANGUAGE="${LANGUAGE:-en}"
BATCH_SIZE="${BATCH_SIZE:-4}"
THREADS="${THREADS:-$(sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null || echo 4)}"
WORK_DIR="transcript/work"
RAW_DIR="transcript/raw"

mkdir -p "$WORK_DIR" "$RAW_DIR"
LOG_FILE="$WORK_DIR/transcribe.log"
exec > >(tee -a "$LOG_FILE") 2>&1

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
die() { log "FATAL: $*"; exit 1; }

log "=============================================================="
log "transcribe.sh in $PROJECT_DIR (pid $$)"

# ----------------------------------------------------------------------------
# Preflight. Fail loudly and early, not 40 minutes into a model download.
# ----------------------------------------------------------------------------
[[ -n "$PYTHON" && -x "$PYTHON" ]] || die "python3 not found (run 'make install' in Lineage)"
command -v ffmpeg  >/dev/null || die "ffmpeg not found on PATH (macOS: brew install ffmpeg)"
command -v ffprobe >/dev/null || die "ffprobe not found on PATH (comes with ffmpeg)"
[[ -d audio ]] || die "audio/ does not exist here -- is $PROJECT_DIR a book project?"
[[ -f book.yaml ]] || log "WARNING: no book.yaml; using defaults (no initial prompt, 2 speakers)"

# book.yaml -> prompt, lock, speaker counts (one python call, tab-separated)
IFS=$'\t' read -r PROMPT LOCKED MIN_SPK MAX_SPK < <("$PYTHON" - "$SCRIPTS" <<'PY'
import sys; sys.path.insert(0, sys.argv[1])
import _project as P
b = P.load_book()
nouns = [str(x).strip() for x in (b.get("proper_nouns") or []) if str(x).strip()]
lo, hi = P.speaker_bounds(b)
print(", ".join(nouns).replace("\t", " ") or "-", int(P.transcription_locked(b)), lo, hi, sep="\t")
PY
) || die "could not read book.yaml (is pyyaml installed? run 'make install')"
[[ "$PROMPT" == "-" ]] && PROMPT=""

if [[ ${#PROMPT} -gt 120 ]]; then
    log "WARNING: initial prompt is ${#PROMPT} characters. Whisper tends to echo a long"
    log "         initial_prompt back as fake speech. Keep proper_nouns to a few surnames."
fi
log "initial prompt: ${PROMPT:-(none)}"

if [[ $FORCE -eq 1 && "$LOCKED" == "1" ]]; then
    die "--force refused: book.yaml has transcription_locked: true. Re-transcribing moves
      every timestamp the book cites. Unlock it deliberately if you must."
fi

if [[ $DRY_RUN -eq 0 ]]; then
    "$PYTHON" -c "import whisperx" >/dev/null 2>&1 || die "whisperx does not import in $PYTHON.
      Install the optional transcription stack:
        $PYTHON -m pip install -r \"\$LINEAGE/requirements-transcribe.txt\""
fi

HAVE_TOKEN=0; [[ -n "${HF_TOKEN:-}" ]] && HAVE_TOKEN=1
if [[ $ONE_PASS -eq 1 && $HAVE_TOKEN -eq 0 ]]; then
    die "--one-pass needs HF_TOKEN (gated pyannote models). See diarize.py --help,
      or drop --one-pass to transcribe now and diarize later."
fi

# Device: WhisperX transcribes via faster-whisper/CTranslate2, which supports
# CPU and CUDA only -- no Metal/MPS -- so Apple Silicon runs on CPU.
if [[ $DRY_RUN -eq 0 && ( -z "${DEVICE:-}" || -z "${COMPUTE_TYPE:-}" ) ]]; then
    read -r DETECTED_DEVICE DETECTED_COMPUTE < <("$PYTHON" - <<'PY'
import ctranslate2
if ctranslate2.get_cuda_device_count() > 0:
    s = ctranslate2.get_supported_compute_types("cuda")
    print("cuda", "float16" if "float16" in s else "float32")
else:
    s = ctranslate2.get_supported_compute_types("cpu")
    print("cpu", "int8" if "int8" in s else "float32")
PY
)
    DEVICE="${DEVICE:-$DETECTED_DEVICE}"
    COMPUTE_TYPE="${COMPUTE_TYPE:-$DETECTED_COMPUTE}"
fi
DEVICE="${DEVICE:-cpu}"; COMPUTE_TYPE="${COMPUTE_TYPE:-int8}"
log "model=$MODEL language=$LANGUAGE device=$DEVICE compute_type=$COMPUTE_TYPE batch=$BATCH_SIZE threads=$THREADS speakers=$MIN_SPK-$MAX_SPK"
[[ "$DEVICE" == "cpu" ]] && log "NOTE: CPU run. large-v3 is slow here -- budget roughly real time or slower."

AVAIL_GB="$(df -Pk . 2>/dev/null | awk 'NR==2 {print int($4/1048576)}' || echo 99)"
if [[ "${AVAIL_GB:-99}" -lt 15 ]]; then
    log "WARNING: only ${AVAIL_GB}GB free. Models need ~5GB on first run, plus ~110MB per audio-hour of WAV."
fi

# ----------------------------------------------------------------------------
# Sessions: assign IDs, build the queue (shortest first so failures surface fast).
# ----------------------------------------------------------------------------
SYNC_ARGS=(--tsv); [[ $DRY_RUN -eq 1 ]] && SYNC_ARGS+=(--dry-run)
QUEUE_TSV="$("$PYTHON" "$SCRIPTS/sessions.py" "${SYNC_ARGS[@]}" ${TARGETS[@]+"${TARGETS[@]}"})" \
    || die "session sync failed (see message above)"
QUEUE=()
# while-read rather than mapfile: macOS ships bash 3.2, which has no mapfile.
while IFS= read -r line; do
    [[ -n "$line" ]] && QUEUE+=("$line")
done <<<"$QUEUE_TSV"
[[ ${#QUEUE[@]} -gt 0 ]] || die "no audio files in audio/ -- nothing to transcribe"
[[ $SMOKE -eq 1 ]] && { QUEUE=("${QUEUE[0]}"); log "--smoke: shortest session only"; }

log "${#QUEUE[@]} session(s) queued:"
for q in "${QUEUE[@]}"; do
    IFS=$'\t' read -r sid file sec <<<"$q"
    state="todo"; [[ -s "$RAW_DIR/$sid.json" ]] && state="done"
    [[ $FORCE -eq 1 && "$state" == "done" ]] && state="redo (--force)"
    log "  $(printf '%-4s %6.1f min  %-15s' "$sid" "$(awk -v s="$sec" 'BEGIN{print s/60}')" "$state") $file"
done
if [[ $DRY_RUN -eq 1 ]]; then
    log "--dry-run: stopping before any work"
    exit 0
fi

# ----------------------------------------------------------------------------
# ASR loop.
# ----------------------------------------------------------------------------
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/lineage-transcribe.XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT
processed=0; skipped=0; failed=0

for q in "${QUEUE[@]}"; do
    IFS=$'\t' read -r sid src sec <<<"$q"
    wav="$WORK_DIR/$sid.wav"
    out="$RAW_DIR/$sid.json"
    log "--------------------------------------------------------------"
    if [[ -s "$out" && $FORCE -eq 0 ]]; then
        log "SKIP $sid -- $out exists"
        skipped=$((skipped + 1)); continue
    fi
    log "START $sid  <- $src"

    # 1. normalize (atomic; audio/ is never written)
    if [[ -s "$wav" ]]; then
        log "  reusing $wav"
    else
        tmp_wav="$TMP_ROOT/$sid.wav"
        if ! ffmpeg -nostdin -hide_banner -loglevel error -y \
                -i "$src" -vn -ac 1 -ar 16000 -acodec pcm_s16le "$tmp_wav"; then
            log "  ERROR: ffmpeg failed on $src"; failed=$((failed + 1)); continue
        fi
        mv "$tmp_wav" "$wav"
    fi

    # 2. WhisperX into a staging dir
    stage="$TMP_ROOT/stage_$sid"; rm -rf "$stage"; mkdir -p "$stage"
    WX_ARGS=("$wav" --model "$MODEL" --language "$LANGUAGE" --device "$DEVICE"
             --compute_type "$COMPUTE_TYPE" --batch_size "$BATCH_SIZE" --threads "$THREADS"
             --output_format json --output_dir "$stage" --print_progress True)
    [[ -n "$PROMPT" ]] && WX_ARGS+=(--initial_prompt "$PROMPT")
    if [[ $ONE_PASS -eq 1 ]]; then
        WX_ARGS+=(--diarize --min_speakers "$MIN_SPK" --max_speakers "$MAX_SPK" --hf_token "$HF_TOKEN")
    fi
    t0=$SECONDS
    if ! "$PYTHON" "$SCRIPTS/wx.py" "${WX_ARGS[@]}" 2>&1 | sed "s/^/   [$sid] /"; then
        log "  ERROR: whisperx failed on $sid -- previous outputs untouched"
        failed=$((failed + 1)); continue
    fi
    staged="$stage/$sid.json"
    [[ -s "$staged" ]] || { log "  ERROR: expected $staged, not found"; failed=$((failed + 1)); continue; }
    mv "$staged" "$out"
    rm -rf "$stage"
    el=$((SECONDS - t0)); [[ $el -gt 0 ]] || el=1
    log "DONE $sid -> $out in ${el}s ($(awk -v s="$sec" -v e="$el" 'BEGIN{printf "%.2f", s/e}')x real time)"
    processed=$((processed + 1))
done

log "=============================================================="
log "ASR finished: $processed transcribed, $skipped skipped, $failed failed"

# ----------------------------------------------------------------------------
# Diarization (separate pass, so a failure here never costs a re-transcription).
# ----------------------------------------------------------------------------
if [[ $ONE_PASS -eq 0 && $DIARIZE -eq 1 ]]; then
    if [[ $HAVE_TOKEN -eq 1 ]]; then
        log "diarizing (sessions that already have speakers are skipped)"
        DIA_IDS=()
        for q in "${QUEUE[@]}"; do IFS=$'\t' read -r sid _ _ <<<"$q"; DIA_IDS+=("$sid"); done
        if ! "$PYTHON" "$SCRIPTS/diarize.py" "${DIA_IDS[@]}"; then
            log "diarization failed -- the ASR output is safe; fix the cause and run diarize.py"
            failed=$((failed + 1))
        fi
    else
        log "HF_TOKEN not set: speakers not labelled yet. When ready:"
        log "  export HF_TOKEN=hf_xxxxxxxx   # after accepting the pyannote licences (see diarize.py --help)"
        log "  $PYTHON $SCRIPTS/diarize.py"
    fi
fi

log "next: confirm speakers by ear, fill transcript/corrections.json, then run render_transcripts.py"
[[ $failed -eq 0 ]] || exit 1
