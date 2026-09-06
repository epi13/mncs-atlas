"""Scalar glue between the scene owner model and the MNCS ABI."""

from __future__ import annotations

from .model import SceneDelta


def bool_bit(value: bool) -> int:
    return 1 if value else 0


def move_args(delta: SceneDelta) -> list[int]:
    return [delta.appeared, delta.disappeared, delta.moved, delta.changed, delta.unchanged]


def focus_args(old_left: int, old_top: int, new_left: int, new_top: int) -> list[int]:
    return [old_left, old_top, new_left, new_top]
