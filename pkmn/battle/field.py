"""Per-side field state: entry hazards and screens. Weather lives on
the engine itself (it's whole-field)."""
from __future__ import annotations

from dataclasses import dataclass

WEATHERS = ("rain", "sun", "sandstorm", "hail")


@dataclass
class SideState:
    spikes: int = 0            # 0-3 layers
    toxic_spikes: int = 0      # 0-2 layers
    stealth_rock: bool = False
    reflect: int = 0           # turns remaining
    light_screen: int = 0
    safeguard: int = 0
    mist: int = 0
    lucky_chant: int = 0
    tailwind: int = 0
    healing_wish: bool = False

    def clear_hazards(self) -> list[str]:
        cleared = []
        if self.spikes:
            cleared.append("spikes")
        if self.toxic_spikes:
            cleared.append("toxic-spikes")
        if self.stealth_rock:
            cleared.append("stealth-rock")
        self.spikes = self.toxic_spikes = 0
        self.stealth_rock = False
        return cleared
