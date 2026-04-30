"""Compatibility exports for candidate move policy."""

from g6explanation.context_engine.candidate_moves.assembly import build_candidates
from g6explanation.context_engine.candidate_moves.findability import time_situation
from g6explanation.context_engine.candidate_moves.selection import choose_key_candidate

__all__ = [
    "build_candidates",
    "choose_key_candidate",
    "time_situation",
]
