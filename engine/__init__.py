"""Orphic SightDiff: local browser capture and visual comparison."""

from .capture import capture
from .compare import compare
from .store import accept, approve, baseline, ignore_add, ignore_list, ignore_remove

__all__ = ["capture", "baseline", "compare", "ignore_add", "ignore_list",
           "ignore_remove", "approve", "accept"]
