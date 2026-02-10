"""Deterministic id generation helpers."""

from __future__ import annotations

from eco_sim.sim.state import GameState


def next_id(state: GameState, prefix: str) -> str:
    count = state.id_counters.get(prefix, 0) + 1
    state.id_counters[prefix] = count
    return f"{prefix}{count:03d}"
