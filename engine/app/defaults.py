from __future__ import annotations

from typing import Any

DEFAULT_LLM_MODEL = "qwen2.5:7b"

DEFAULT_TENSION_TARGETS: dict[str, float] = {
    "conflict_strength": 0.72,
    "stakes": 0.65,
    "cost": 0.60,
    "pace": 0.62,
    "reversal": 0.55,
    "hook": 0.60,
    "payoff": 0.62,
}

DEFAULT_TENSION_STYLE: dict[str, float] = {
    "face_slap_density": 0.18,
    "upgrade_density": 0.14,
}


def merge_defaults(base: dict[str, float], values: dict[str, Any] | None) -> dict[str, float]:
    out = dict(base)
    if not values:
        return out
    for key, val in values.items():
        if key in out:
            try:
                out[key] = float(val)
            except Exception:
                continue
    return out

