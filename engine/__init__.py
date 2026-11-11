"""Orphic Eyes: local browser capture and visual comparison."""

from .capture import capture
from .compare import compare
from .store import accept, approve, baseline, ignore_add, ignore_list, ignore_remove
from .url_capture import capture as capture_url, capture_pair
from .loop import loop_step, orphic_loop_step

__all__ = ["capture", "baseline", "compare", "ignore_add", "ignore_list",
           "ignore_remove", "approve", "accept", "capture_url", "capture_pair", "loop_step", "orphic_loop_step"]
