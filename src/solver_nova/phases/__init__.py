"""Phase registration for Nova solver steps."""

from __future__ import annotations

from ..step_runner import register_step
from .boxline import step_box_line
from .branch import step_branch
from .propagate import step_propagate
from .subsets2 import step_subsets2_pairs

register_step("PROPAGATE", "propagate.basic", step_propagate)
register_step("HEURISTICS", "subsets2.pairs", step_subsets2_pairs)
register_step("HEURISTICS", "boxline.locked_candidates", step_box_line)
register_step("BRANCH", "branch.backtracking", step_branch)

__all__ = [
    "step_box_line",
    "step_branch",
    "step_propagate",
    "step_subsets2_pairs",
]
