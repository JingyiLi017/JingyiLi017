from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from collections.abc import AsyncIterator


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue[tuple[str, dict]]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, key: str) -> asyncio.Queue[tuple[str, dict]]:
        queue: asyncio.Queue[tuple[str, dict]] = asyncio.Queue(maxsize=2000)
        async with self._lock:
            self._subs[key].add(queue)
        return queue

    async def unsubscribe(self, key: str, queue: asyncio.Queue[tuple[str, dict]]) -> None:
        async with self._lock:
            self._subs[key].discard(queue)
            if not self._subs[key]:
                self._subs.pop(key, None)

    async def publish(self, key: str, event_type: str, payload: dict) -> None:
        async with self._lock:
            targets = list(self._subs.get(key, set()))
            targets += list(self._subs.get("all", set()))
        for queue in targets:
            try:
                queue.put_nowait((event_type, payload))
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                    queue.put_nowait((event_type, payload))
                except Exception:
                    pass


def format_sse(event_type: str, payload: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def stream_sse(queue: asyncio.Queue[tuple[str, dict]]) -> AsyncIterator[str]:
    while True:
        event_type, payload = await queue.get()
        yield format_sse(event_type, payload)


event_bus = EventBus()

