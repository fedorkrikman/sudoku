"""Placeholder registrations for yet-to-be-ported Nova techniques."""

from __future__ import annotations

from ..step_runner import register_step
from .als import step_als
from .color_chains import step_color_chains
from .fish import step_fish
from .subsets34 import step_subsets34
from .uniques import step_uniques
from .wings import step_wings

register_step("HEURISTICS", "subsets34.triples_quads", step_subsets34)
register_step("HEURISTICS", "fish.advanced", step_fish)
register_step("HEURISTICS", "wings.patterns", step_wings)
register_step("HEURISTICS", "uniques.rectangles", step_uniques)
register_step("HEURISTICS", "color.chains", step_color_chains)
register_step("HEURISTICS", "als.family", step_als)

__all__ = [
    "step_als",
    "step_color_chains",
    "step_fish",
    "step_subsets34",
    "step_uniques",
    "step_wings",
]
