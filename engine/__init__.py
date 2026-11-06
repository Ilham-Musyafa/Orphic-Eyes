"""Orphic SightDiff: local browser capture and visual comparison."""

from .capture import capture
from .compare import compare
from .store import baseline

__all__ = ["capture", "baseline", "compare"]
