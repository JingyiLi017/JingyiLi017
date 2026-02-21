from __future__ import annotations

import time


def new_node_id(prefix: str) -> str:
    return f"X_{prefix}_{int(time.time() * 1000)}"

