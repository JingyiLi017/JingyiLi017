from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class JSONGuardError(ValueError):
    message: str
    snippet: str = ""

    def __str__(self) -> str:
        return self.message


def extract_json_candidate(text: str) -> str:
    if not text or not text.strip():
        raise JSONGuardError("empty text")

    data = text.strip()
    data = re.sub(r"^```(?:json)?\s*", "", data, flags=re.IGNORECASE)
    data = re.sub(r"\s*```$", "", data)

    candidates: list[str] = []
    obj_start, obj_end = data.find("{"), data.rfind("}")
    arr_start, arr_end = data.find("["), data.rfind("]")
    if obj_start >= 0 and obj_end > obj_start:
        candidates.append(data[obj_start : obj_end + 1].strip())
    if arr_start >= 0 and arr_end > arr_start:
        candidates.append(data[arr_start : arr_end + 1].strip())

    if not candidates:
        raise JSONGuardError("no json boundaries found", snippet=data[:400])
    return max(candidates, key=len)


def sanitize_json_like(raw: str) -> str:
    text_value = (raw or "").replace("\ufeff", "").strip()
    text_value = (
        text_value.replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
    )
    text_value = "".join(ch for ch in text_value if ch in ("\n", "\t") or ord(ch) >= 32)
    text_value = re.sub(r",\s*([}\]])", r"\1", text_value)
    return text_value


def json_guard_parse(text: str) -> dict[str, Any] | list[Any]:
    candidate = sanitize_json_like(extract_json_candidate(text))
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        snippet = candidate[max(0, exc.pos - 120) : exc.pos + 120]
        raise JSONGuardError(f"json decode error: {exc.msg} at pos {exc.pos}", snippet=snippet) from exc

