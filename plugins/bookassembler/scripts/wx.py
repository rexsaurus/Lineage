#!/usr/bin/env python3
"""WhisperX command-line wrapper that survives PyTorch >= 2.6.

    python $BOOKASSEMBLER/scripts/wx.py <same arguments as the `whisperx` CLI>

torch.load now defaults to weights_only=True, which refuses the pyannote
VAD/segmentation checkpoints WhisperX loads, because they pickle omegaconf
containers. The plain `whisperx` command therefore dies before transcribing a
word. This wrapper applies the narrow fix in hf_compat.py (allowlist those
classes; retry the known model file with weights_only=False only if the safe
load still fails) and then hands over to WhisperX's own CLI unchanged.
transcribe.sh always calls WhisperX through this wrapper.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hf_compat  # noqa: E402,F401  (must precede whisperx)

from whisperx.__main__ import cli  # noqa: E402

if __name__ == "__main__":
    cli()
