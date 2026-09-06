"""Owner model for Atlas scene-graph queries.

This package owns the agent-facing scene semantics that
``mncs/scene_graph.mncs`` implements in MNCS: node identity, bounding
geometry, confidence bands, and frame deltas over structures observed by the
MNCS visual observer (``mncs.core.vision.v1`` in the language workspace).
Perception is not re-implemented here; this model answers what an agent may
ask about an already-observed scene.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SceneNode:
    node_id: int
    kind: int  # 0 rectangle, 1 line, 2 blob
    left: int
    top: int
    width: int
    height: int
    confidence: int  # 0..100


@dataclass(frozen=True)
class SceneDelta:
    appeared: int
    disappeared: int
    moved: int
    changed: int
    unchanged: int
    has_focus: bool = False
    focus_id: int = 0
    focus_old_left: int = 0
    focus_old_top: int = 0
    focus_new_left: int = 0
    focus_new_top: int = 0


def rect_area(width: int, height: int) -> int:
    return width * height


def node_matches(node_id: int, want: int) -> bool:
    return node_id == want


def rects_overlap(a_left: int, a_top: int, a_width: int, a_height: int,
                  b_left: int, b_top: int, b_width: int, b_height: int) -> bool:
    if a_width <= 0 or a_height <= 0 or b_width <= 0 or b_height <= 0:
        return False
    return (
        a_left < b_left + b_width
        and b_left < a_left + a_width
        and a_top < b_top + b_height
        and b_top < a_top + a_height
    )


def viewport_contains(v_left: int, v_top: int, v_width: int, v_height: int,
                      n_left: int, n_top: int, n_width: int, n_height: int) -> bool:
    if n_width <= 0 or n_height <= 0:
        return False
    return (
        v_left <= n_left
        and n_left + n_width <= v_left + v_width
        and v_top <= n_top
        and n_top + n_height <= v_top + v_height
    )


def confidence_band(confidence: int) -> int:
    if confidence >= 80:
        return 2
    if confidence >= 50:
        return 1
    return 0


def focus_moved(old_left: int, old_top: int, new_left: int, new_top: int) -> bool:
    return (old_left, old_top) != (new_left, new_top)


def delta_is_move(delta: SceneDelta) -> bool:
    return (
        delta.moved == 1
        and delta.appeared == 0
        and delta.disappeared == 0
        and delta.changed == 0
        and delta.unchanged == 0
    )


def delta_is_quiet(delta: SceneDelta) -> bool:
    return (
        delta.appeared == 0
        and delta.disappeared == 0
        and delta.moved == 0
        and delta.changed == 0
        and delta.unchanged >= 1
    )
