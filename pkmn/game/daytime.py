"""Day/night cycle.

Phases come from the hour of day — the real system clock by default, the
way the Gen 2/4/5 handhelds read their console clock — and each phase
carries a subtle RGBA tint that the overworld and the battle backdrop blend
over the scene. The active source is configurable per Game (the manifest
``daynight`` setting or the ``--time`` flag): ``"auto"`` follows the clock,
``"off"`` disables tinting (always day), and a phase name pins one phase.
"""
from __future__ import annotations

from datetime import datetime

PHASES = ("morning", "day", "evening", "night")

# Phase for hour h is the last (start, name) with start <= h (h in 0..23);
# hours before the first boundary wrap to the final phase (night).
_BOUNDS = [(0, "night"), (5, "morning"), (10, "day"),
           (18, "evening"), (21, "night")]

# Subtle RGBA overlays (low alpha keeps it gentle); midday is untinted.
TINTS = {
    "morning": (255, 206, 148, 28),
    "day":     (0, 0, 0, 0),
    "evening": (255, 138, 64, 60),
    "night":   (24, 28, 96, 115),
}
LABELS = {"morning": "Morning", "day": "Day",
          "evening": "Evening", "night": "Night"}


def phase_for_hour(hour: int) -> str:
    name = _BOUNDS[-1][1]
    for start, label in _BOUNDS:
        if hour >= start:
            name = label
    return name


def current_phase(hour: int | None = None) -> str:
    if hour is None:
        hour = datetime.now().hour
    return phase_for_hour(hour % 24)


def tint(phase: str):
    return TINTS.get(phase, (0, 0, 0, 0))


def is_night(phase: str) -> bool:
    return phase == "night"
