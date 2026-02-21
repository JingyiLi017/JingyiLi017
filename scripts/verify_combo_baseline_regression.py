import argparse
import json
import statistics
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class ChapterRun:
    chapter_id: str
    chapter_no: int
    batch_id: str
    status: str
    exp_score: float | None
    baseline_score: float | None
    combo_baseline_score: float | None
    delta: float | None
    combo_delta: float | None
    exp_text_ver_id: str | None
    combo_baseline_text_ver_id: str | None


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def _mean(vals: list[float]) -> float | None:
    if not vals:
        return None
    return float(sum(vals) / len(vals))


def _p50(vals: list[float]) -> float | None:
    if not vals:
        return None
    return float(statistics.median(vals))


def _create_book(client: httpx.Client, base: str, title_prefix: str) -> str:
    ts = int(time.time())
    r = client.post(
        f"{base}/v1/books",
        json={
            "title": f"{title_prefix}-{ts}-{uuid.uuid4().hex[:6]}",
            "author": "combo-regression",
            "language": "zh-CN",
            "notes": "auto regression for combo baseline",
        },
        timeout=30.0,
    )
    r.raise_for_status()
    return str(r.json()["book_id"])


def _create_chapters(client: httpx.Client, base: str, book_id: str, chapter_count: int) -> list[dict]:
    out: list[dict] = []
    for i in range(1, chapter_count + 1):
        r = client.post(
            f"{base}/v1/books/{book_id}/chapters",
            json={"chapter_no": i, "title": f"Regression Chapter {i}"},
            timeout=30.0,
        )
        r.raise_for_status()
        item = r.json()
        out.append({"chapter_no": i, "chapter_id": str(item["chapter_id"])})
    return out


def _ensure_volumes(client: httpx.Client, base: str, book_id: str, chapters_per_volume: int = 50) -> None:
    r = client.post(
        f"{base}/v1/books/{book_id}/volumes/auto_create",
        json={"chapters_per_volume": chapters_per_volume},
        timeout=30.0,
    )
    r.raise_for_status()


def _run_ab_for_chapter(client: httpx.Client, base: str, chapter_id: str, note: str) -> dict:
    r = client.post(
        f"{base}/v1/chapters/{chapter_id}/ab_batch/run",
        json={
            "note": note,
            "profiles": "all",
            "include_baseline": True,
            "baseline_profile": "main",
            "include_combo_baseline": True,
            "combo_baseline_profile": "main",
            "do_eval": True,
            "do_simguard": True,
            "orchestrator_enabled": True,
            "orchestrator_max_tasks": 3,
            "orchestrator_max_weight": 4,
        },
        timeout=120.0,
    )
    r.raise_for_status()
    batch_id = str(r.json()["batch_id"])
    g = client.get(f"{base}/v1/ab_batch/{batch_id}", timeout=60.0)
    g.raise_for_status()
    out = g.json()
    out["_batch_id"] = batch_id
    return out


def _extract_metrics(chapter_id: str, chapter_no: int, batch: dict) -> ChapterRun:
    items = batch.get("items") or []
    by_variant = {str(x.get("variant") or ""): x for x in items if isinstance(x, dict)}
    exp = by_variant.get("exp") or {}
    base = by_variant.get("baseline") or {}
    combo_base = by_variant.get("combo_baseline") or {}
    delta_row = (batch.get("delta_ranking") or [None])[0] or {}
    combo_delta_row = (batch.get("combo_delta_ranking") or [None])[0] or {}

    return ChapterRun(
        chapter_id=chapter_id,
        chapter_no=chapter_no,
        batch_id=str(batch.get("_batch_id") or batch.get("batch_id") or ""),
        status=str(batch.get("status") or ""),
        exp_score=_safe_float(exp.get("score")),
        baseline_score=_safe_float(base.get("score")),
        combo_baseline_score=_safe_float(combo_base.get("score")),
        delta=_safe_float(delta_row.get("delta")),
        combo_delta=_safe_float(combo_delta_row.get("delta")),
        exp_text_ver_id=str(exp.get("text_ver_id")) if exp.get("text_ver_id") else None,
        combo_baseline_text_ver_id=str(combo_base.get("text_ver_id")) if combo_base.get("text_ver_id") else None,
    )


def _health(client: httpx.Client, base: str) -> dict:
    r = client.get(f"{base}/v1/health", timeout=15.0)
    r.raise_for_status()
    return r.json()


def main() -> None:
    p = argparse.ArgumentParser(description="Run combo baseline regression across multiple chapters.")
    p.add_argument("--base", default="http://127.0.0.1:17777", help="API base URL")
    p.add_argument("--chapter-count", type=int, default=3, help="How many chapters to generate and test")
    p.add_argument("--title-prefix", default="ComboRegression", help="Auto-created book title prefix")
    args = p.parse_args()

    chapter_count = max(1, min(int(args.chapter_count), 20))
    base = str(args.base).rstrip("/")

    with httpx.Client() as client:
        health = _health(client, base)
        book_id = _create_book(client, base, args.title_prefix)
        chapters = _create_chapters(client, base, book_id, chapter_count)
        _ensure_volumes(client, base, book_id, chapters_per_volume=50)

        rows: list[ChapterRun] = []
        for c in chapters:
            chapter_id = str(c["chapter_id"])
            chapter_no = int(c["chapter_no"])
            batch = _run_ab_for_chapter(client, base, chapter_id, f"combo regression chapter {chapter_no}")
            rows.append(_extract_metrics(chapter_id, chapter_no, batch))

        deltas = [x.delta for x in rows if x.delta is not None]
        combo_deltas = [x.combo_delta for x in rows if x.combo_delta is not None]
        done_count = sum(1 for x in rows if x.status == "done")
        combo_available = sum(1 for x in rows if x.combo_delta is not None)

        report = {
            "ok": True,
            "base": base,
            "book_id": book_id,
            "health_status": health.get("status"),
            "chapter_count": chapter_count,
            "done_count": done_count,
            "combo_delta_available_count": combo_available,
            "summary": {
                "delta": {
                    "count": len(deltas),
                    "mean": _mean(deltas),
                    "p50": _p50(deltas),
                    "positive_ratio": (sum(1 for x in deltas if x > 0) / len(deltas)) if deltas else None,
                },
                "combo_delta": {
                    "count": len(combo_deltas),
                    "mean": _mean(combo_deltas),
                    "p50": _p50(combo_deltas),
                    "positive_ratio": (sum(1 for x in combo_deltas if x > 0) / len(combo_deltas)) if combo_deltas else None,
                },
            },
            "chapters": [
                {
                    "chapter_no": x.chapter_no,
                    "chapter_id": x.chapter_id,
                    "batch_id": x.batch_id,
                    "status": x.status,
                    "exp_score": x.exp_score,
                    "baseline_score": x.baseline_score,
                    "combo_baseline_score": x.combo_baseline_score,
                    "delta": x.delta,
                    "combo_delta": x.combo_delta,
                    "exp_text_ver_id": x.exp_text_ver_id,
                    "combo_baseline_text_ver_id": x.combo_baseline_text_ver_id,
                }
                for x in rows
            ],
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
