"""Compatibility shims for pyannote.audio. Import this BEFORE whisperx/pyannote.

    sys.path.insert(0, <this directory>); import hf_compat

Two upstream breakages, patched narrowly here rather than by pinning versions
backwards (an older huggingface_hub or torch breaks faster-whisper/whisperx):

1. huggingface_hub >= 1.0 removed the `use_auth_token` keyword in favour of
   `token`, but pyannote.audio 3.4 (and whisperx's DiarizationPipeline) still
   pass `use_auth_token`. We rename the keyword on the hub download functions.

2. PyTorch >= 2.6 changed torch.load to default to weights_only=True, which
   refuses pyannote's checkpoints because they pickle omegaconf containers
   (and a few plain Python types). We allowlist exactly those classes, and only
   if the safe load still fails with a weights_only error do we retry the same
   file with weights_only=False. These are model files downloaded from the
   pyannote repos you accepted the licence for, not arbitrary pickles.
"""
import collections
import typing

import torch
import torch.serialization as _S
import huggingface_hub as _hub


def _wrap(fn):
    def inner(*a, **kw):
        if "use_auth_token" in kw:
            tok = kw.pop("use_auth_token")
            kw.setdefault("token", tok)
        return fn(*a, **kw)
    inner.__name__ = getattr(fn, "__name__", "wrapped")
    inner.__doc__ = getattr(fn, "__doc__", None)
    return inner


for _name in ("hf_hub_download", "snapshot_download", "model_info"):
    if hasattr(_hub, _name):
        setattr(_hub, _name, _wrap(getattr(_hub, _name)))


def allowlist():
    """Classes legitimately pickled inside pyannote/whisperx VAD checkpoints."""
    allow = [collections.defaultdict, dict, list, int, float, str, bool, typing.Any]
    try:
        from omegaconf.listconfig import ListConfig
        from omegaconf.dictconfig import DictConfig
        from omegaconf.base import ContainerMetadata, Metadata
        allow += [ListConfig, DictConfig, ContainerMetadata, Metadata]
        from omegaconf.nodes import AnyNode, ValueNode
        from omegaconf.base import Container, Node
        allow += [AnyNode, ValueNode, Container, Node]
    except Exception:
        pass
    return allow


if hasattr(_S, "add_safe_globals"):
    _S.add_safe_globals(allowlist())

_orig_load = torch.load


def _load(*a, **kw):
    try:
        return _orig_load(*a, **kw)
    except Exception as e:
        if "weights_only" not in str(e) and "WeightsUnpickler" not in str(e):
            raise
        # The failed attempt consumed the stream; rewind or torch falls back
        # to _legacy_load and dies on "persistent IDs in protocol 0".
        if a and hasattr(a[0], "seek"):
            a[0].seek(0)
        kw["weights_only"] = False
        return _orig_load(*a, **kw)


if not getattr(torch.load, "_bookassembler_patched", False):
    _load._bookassembler_patched = True
    torch.load = _load
