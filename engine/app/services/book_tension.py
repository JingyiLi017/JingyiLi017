from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

DEFAULT_ARC_TARGET_POINTS: dict[str, list[float]] = {
    "ramp": [0.42, 0.52, 0.60, 0.70, 0.74],
    "late_peak": [0.40, 0.48, 0.56, 0.70, 0.80],
    "early_peak": [0.48, 0.70, 0.58, 0.55, 0.62],
    "plateau": [0.55, 0.56, 0.56, 0.58, 0.60],
    "sawtooth": [0.50, 0.62, 0.52, 0.66, 0.56],
}


@dataclass
class ChapterMetric:
    chapter_no: int
    chapter_id: str
    arc_id: str | None
    arc_index: int | None
    title: str
    scores: dict[str, float]
    tension_curve: list[float]
    issues_count: int
    mechanics_used: list[str]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def moving_average(xs: list[float], w: int = 5) -> list[float]:
    if not xs:
        return []
    out: list[float] = []
    s = 0.0
    q: list[float] = []
    for x in xs:
        q.append(float(x))
        s += float(x)
        if len(q) > w:
            s -= q.pop(0)
        out.append(s / len(q))
    return out


def density_per_10(chapters: list[int], last_chapter_no: int) -> float:
    if last_chapter_no <= 0:
        return 0.0
    windows = max(1, (last_chapter_no + 9) // 10)
    return len(chapters) / windows


def detect_peaks_valleys(items: list[ChapterMetric]) -> tuple[list[int], list[int]]:
    peaks: list[int] = []
    valleys: list[int] = []
    for it in items:
        ov = float(it.scores.get("overall", 0.0))
        cmax = max(it.tension_curve) if it.tension_curve else 0.0
        if ov >= 0.72 or cmax >= 0.78:
            peaks.append(it.chapter_no)
        if ov <= 0.45:
            valleys.append(it.chapter_no)
    return peaks, valleys


def std(xs: list[float]) -> float:
    if not xs:
        return 0.0
    m = sum(xs) / len(xs)
    v = sum((x - m) * (x - m) for x in xs) / len(xs)
    return math.sqrt(v)


def fatigue_by_overall(items: list[ChapterMetric], low: float = 0.45, min_len: int = 5) -> list[tuple[int, int, str]]:
    zones: list[tuple[int, int, str]] = []
    start: int | None = None
    for it in items:
        ov = float(it.scores.get("overall", 0.0))
        if ov < low:
            if start is None:
                start = it.chapter_no
        else:
            if start is not None:
                end = it.chapter_no - 1
                if end - start + 1 >= min_len:
                    zones.append((start, end, "overall<0.45 for 5+ chapters"))
                start = None
    if start is not None and items:
        end = items[-1].chapter_no
        if end - start + 1 >= min_len:
            zones.append((start, end, "overall<0.45 for 5+ chapters"))
    return zones


def fatigue_by_flat_curve(items: list[ChapterMetric], flat_std: float = 0.07, min_len: int = 4) -> list[tuple[int, int, str]]:
    zones: list[tuple[int, int, str]] = []
    start: int | None = None
    for it in items:
        cstd = std(it.tension_curve or [])
        if cstd <= flat_std:
            if start is None:
                start = it.chapter_no
        else:
            if start is not None:
                end = it.chapter_no - 1
                if end - start + 1 >= min_len:
                    zones.append((start, end, "tension_curve too flat"))
                start = None
    if start is not None and items:
        end = items[-1].chapter_no
        if end - start + 1 >= min_len:
            zones.append((start, end, "tension_curve too flat"))
    return zones


def merge_ranges(ranges: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    if not ranges:
        return []
    ranges = sorted(ranges, key=lambda x: (x[0], x[1]))
    out = [ranges[0]]
    for s, e, reason in ranges[1:]:
        ps, pe, pr = out[-1]
        if s <= pe + 1:
            out[-1] = (ps, max(pe, e), pr + "; " + reason)
        else:
            out.append((s, e, reason))
    return out


def avg_scores(items: list[ChapterMetric]) -> dict[str, float]:
    keys = ["overall", "conflict_strength", "stakes", "cost", "pace", "reversal", "hook", "payoff"]
    acc = {k: 0.0 for k in keys}
    n = max(1, len(items))
    for it in items:
        for k in keys:
            acc[k] += float(it.scores.get(k, 0.0))
    return {k: round(acc[k] / n, 4) for k in keys}


def mechanics_mix(items: list[ChapterMetric]) -> dict[str, int]:
    c: Counter[str] = Counter()
    for it in items:
        for m in it.mechanics_used or []:
            c[m] += 1
    return dict(c)


def infer_issues_top(avg: dict[str, float]) -> list[str]:
    out: list[str] = []
    if avg.get("cost", 0.0) < 0.45:
        out.append("no_cost")
    if avg.get("reversal", 0.0) < 0.45:
        out.append("low_reversal")
    if avg.get("pace", 0.0) < 0.5:
        out.append("slow_pace")
    if avg.get("stakes", 0.0) < 0.5:
        out.append("low_stakes")
    return out[:3]


def curve_shape(overalls: list[float]) -> str:
    if len(overalls) < 8:
        return "unknown"
    n = len(overalls)
    idxs = [0, n // 4, n // 2, (3 * n) // 4, n - 1]
    s = [overalls[i] for i in idxs]
    if s[-1] - s[0] >= 0.12:
        return "ramp"
    if max(s) - min(s) <= 0.08:
        return "flat"
    if s[1] > s[3] and s[1] == max(s):
        return "early_peak"
    if s[3] > s[1] and s[3] == max(s):
        return "late_peak"
    return "sawtooth"


def sample_5_points(xs: list[float]) -> list[float]:
    if not xs:
        return [0.0, 0.0, 0.0, 0.0, 0.0]
    n = len(xs)
    idxs = [0, n // 4, n // 2, (3 * n) // 4, n - 1]
    return [float(xs[i]) for i in idxs]


def deviation(actual5: list[float], target5: list[float]) -> dict[str, Any]:
    dev = [float(a) - float(t) for a, t in zip(actual5, target5)]
    neg = [d for d in dev if d < 0]
    pos = [d for d in dev if d > 0]
    return {
        "dev": [round(d, 4) for d in dev],
        "abs_mean": round(sum(abs(d) for d in dev) / max(1, len(dev)), 4),
        "neg_mean": round(sum(neg) / max(1, len(neg)), 4) if neg else 0.0,
        "pos_mean": round(sum(pos) / max(1, len(pos)), 4) if pos else 0.0,
    }


def classify_arc_deviation(dev: list[float]) -> str:
    if len(dev) < 5:
        return "minor"
    if dev[2] <= -0.10 and dev[1] > -0.05 and dev[3] > -0.05:
        return "mid_slump"
    if dev[0] >= 0.08 and dev[3] <= -0.08:
        return "early_peak_leak"
    if all(d <= -0.06 for d in dev[2:]):
        return "no_ramp"
    if dev[4] <= -0.10:
        return "weak_ending"
    return "minor"


def peak_spacing(peaks: list[int]) -> dict[str, Any]:
    if len(peaks) < 2:
        return {"avg_gap": None, "max_gap": None, "gaps": [], "outliers": []}
    gaps = [peaks[i] - peaks[i - 1] for i in range(1, len(peaks))]
    outliers: list[dict[str, int]] = []
    for i, gap in enumerate(gaps, start=1):
        if gap >= 12:
            outliers.append({"from": peaks[i - 1], "to": peaks[i], "gap": gap})
    return {"avg_gap": round(sum(gaps) / len(gaps), 3), "max_gap": max(gaps), "gaps": gaps, "outliers": outliers}


def post_peak_drop(overall_by_no: dict[int, float], peaks: list[int], k: int = 4) -> list[dict[str, Any]]:
    drops: list[dict[str, Any]] = []
    for peak in peaks:
        seq = [overall_by_no.get(peak + i) for i in range(0, k + 1)]
        if any(v is None for v in seq):
            continue
        base = float(seq[0] or 0.0)
        if base < 0.72:
            continue
        down = True
        for i in range(0, k):
            if float(seq[i] or 0.0) < float(seq[i + 1] or 0.0) - 0.01:
                down = False
                break
        tail_avg = sum(float(v or 0.0) for v in seq[1:]) / k
        if down and tail_avg < 0.52:
            drops.append({"peak": peak, "from": peak + 1, "to": peak + k, "tail_avg": round(tail_avg, 3)})
    return drops


def late_book_fade(overalls: list[float]) -> dict[str, Any] | None:
    if len(overalls) < 30:
        return None
    n = len(overalls)
    cut = int(n * 0.7)
    early = overalls[:cut]
    late = overalls[cut:]
    early_avg = sum(early) / max(1, len(early))
    late_avg = sum(late) / max(1, len(late))
    if late_avg < early_avg - 0.07:
        return {
            "early_avg": round(early_avg, 3),
            "late_avg": round(late_avg, 3),
            "delta": round(late_avg - early_avg, 3),
            "cut_index": cut,
        }
    return None


def sawtooth_rate(overalls: list[float]) -> dict[str, Any]:
    if len(overalls) < 10:
        return {"rate": 0.0, "flag": False}
    deltas = [overalls[i] - overalls[i - 1] for i in range(1, len(overalls))]
    signs = [1 if d > 0.01 else (-1 if d < -0.01 else 0) for d in deltas]
    flips = 0
    valid = 0
    for i in range(1, len(signs)):
        if signs[i] == 0 or signs[i - 1] == 0:
            continue
        valid += 1
        if signs[i] != signs[i - 1]:
            flips += 1
    rate = flips / max(1, valid)
    return {"rate": round(rate, 3), "flag": rate >= 0.60}


def _actions_for_peak_gap(mid: int) -> list[tuple[int, str]]:
    return [(mid, "timer"), (mid + 1, "raise_stakes"), (mid + 2, "face_slap")]


def _actions_for_post_peak_drop(start: int) -> list[tuple[int, str]]:
    return [(start, "timer"), (start + 1, "cost_hardening"), (start + 2, "reversal")]


def _actions_for_arc_deviation(dev_type: str, chapter_from: int, chapter_to: int) -> list[tuple[int, str]]:
    mid = (chapter_from + chapter_to) // 2
    if dev_type == "mid_slump":
        return [(mid, "raise_stakes"), (mid + 1, "face_slap"), (mid + 2, "cost_hardening")]
    if dev_type == "early_peak_leak":
        return [(chapter_from + 1, "cost_hardening"), (chapter_from + 2, "timer"), (chapter_from + 3, "reversal")]
    if dev_type == "no_ramp":
        return [(mid, "timer"), (mid + 1, "raise_stakes"), (mid + 2, "cost_hardening")]
    if dev_type == "weak_ending":
        return [(chapter_to - 2, "reversal"), (chapter_to - 1, "timer"), (chapter_to, "face_slap")]
    return []


def suggest_actions_for_zone(items_by_no: dict[int, ChapterMetric], start: int, end: int) -> list[tuple[int, str]]:
    actions: list[tuple[int, str]] = []
    for ch_no in range(start, end + 1):
        it = items_by_no.get(ch_no)
        if not it:
            continue
        if (ch_no - start) % 2 != 0:
            continue
        avg_cost = float(it.scores.get("cost", 0.0))
        avg_pace = float(it.scores.get("pace", 0.0))
        avg_rev = float(it.scores.get("reversal", 0.0))
        avg_stk = float(it.scores.get("stakes", 0.0))

        if avg_cost < 0.5:
            actions.append((ch_no, "cost_hardening"))
        elif avg_pace < 0.55:
            actions.append((ch_no, "timer"))
        elif avg_rev < 0.5:
            actions.append((ch_no, "reversal"))
        elif avg_stk < 0.55:
            actions.append((ch_no, "raise_stakes"))
        else:
            actions.append((ch_no, "face_slap"))
    return actions[:6]


def arc_key(it: ChapterMetric, vol_size: int = 40) -> str:
    if it.arc_id:
        return it.arc_id
    k = (it.chapter_no - 1) // vol_size + 1
    return f"vol-{k}"


async def insert_chapter_tension_metric(
    session: AsyncSession,
    *,
    book_id: str,
    chapter_id: str,
    chapter_no: int,
    chapter_version_id: str | None,
    eval_skill_run_id: str,
    scores: dict[str, float],
    tension_curve: list[float],
    issues_count: int,
    mechanics_used: list[str],
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO chapter_tension_metrics(
              book_id, chapter_id, chapter_no, chapter_version_id, eval_skill_run_id,
              scores, tension_curve, issues_count, mechanics_used
            )
            VALUES (
              :book_id, :chapter_id, :chapter_no, :chapter_version_id, :eval_skill_run_id,
              CAST(:scores AS jsonb), CAST(:tension_curve AS real[]), :issues_count, CAST(:mechanics_used AS text[])
            )
            ON CONFLICT (book_id, chapter_id, eval_skill_run_id) DO NOTHING
            """
        ),
        {
            "book_id": book_id,
            "chapter_id": chapter_id,
            "chapter_no": chapter_no,
            "chapter_version_id": chapter_version_id,
            "eval_skill_run_id": eval_skill_run_id,
            "scores": json.dumps(scores),
            "tension_curve": tension_curve,
            "issues_count": issues_count,
            "mechanics_used": mechanics_used,
        },
    )


async def fetch_latest_metrics_rows(session: AsyncSession, book_id: str) -> list[dict[str, Any]]:
    res = await session.execute(
        text(
            """
            WITH latest AS (
              SELECT DISTINCT ON (book_id, chapter_id)
                book_id, chapter_id, chapter_no, chapter_version_id, eval_skill_run_id,
                scores, tension_curve, issues_count, mechanics_used, created_at
              FROM chapter_tension_metrics
              WHERE book_id = :book_id
              ORDER BY book_id, chapter_id, created_at DESC
            )
            SELECT
              l.chapter_id, l.chapter_no, l.chapter_version_id, l.eval_skill_run_id,
              l.scores, l.tension_curve, l.issues_count, l.mechanics_used,
              c.arc_id, c.arc_index, c.title
            FROM latest l
            JOIN chapter c ON c.chapter_id = l.chapter_id
            ORDER BY l.chapter_no ASC
            """
        ),
        {"book_id": book_id},
    )
    return [dict(r) for r in res.mappings().all()]


async def fetch_arc_targets(session: AsyncSession, book_id: str) -> dict[str, dict[str, Any]]:
    try:
        res = await session.execute(
            text(
                """
                SELECT arc_id, target_shape, target_points, weights
                FROM arc_target
                WHERE book_id=:book_id
                """
            ),
            {"book_id": book_id},
        )
    except Exception:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in res.mappings().all():
        out[str(row["arc_id"])] = {
            "target_shape": str(row["target_shape"]),
            "target_points": [float(x) for x in (row["target_points"] or [])],
            "weights": dict(row["weights"] or {}),
        }
    return out


def row_to_metric(row: dict[str, Any]) -> ChapterMetric:
    return ChapterMetric(
        chapter_no=int(row.get("chapter_no") or 0),
        chapter_id=str(row.get("chapter_id")),
        arc_id=row.get("arc_id"),
        arc_index=row.get("arc_index"),
        title=str(row.get("title") or ""),
        scores=dict(row.get("scores") or {}),
        tension_curve=[float(x) for x in (row.get("tension_curve") or [])],
        issues_count=int(row.get("issues_count") or 0),
        mechanics_used=list(row.get("mechanics_used") or []),
    )


async def get_chapters_total(session: AsyncSession, book_id: str) -> int:
    res = await session.execute(text("SELECT COUNT(*) FROM chapter WHERE book_id=:book_id"), {"book_id": book_id})
    return int(res.scalar() or 0)


def build_book_tension_analysis(
    book_id: str,
    metrics: list[ChapterMetric],
    chapters_total: int,
    arc_targets: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not metrics:
        return {
            "schema_name": "BOOK_TENSION_ANALYSIS",
            "schema_ver": 1,
            "generated_at": now_iso(),
            "result": {
                "coverage": {"chapters_total": chapters_total, "chapters_with_metrics": 0, "last_chapter_no": 0},
                "book_trends": {"overall_ma": [], "conflict_ma": [], "pace_ma": [], "fatigue_zones": []},
                "peaks": {"chapters": [], "density_per_10": 0.0},
                "valleys": {"chapters": [], "density_per_10": 0.0},
                "arc_summary": [],
                "diagnosis": [],
                "advanced": {
                    "peak_spacing": {"avg_gap": None, "max_gap": None, "gaps": [], "outliers": []},
                    "post_peak_drop": [],
                    "late_book_fade": None,
                    "sawtooth": {"rate": 0.0, "flag": False},
                },
                "arc_targets": [],
            },
            "warnings": ["NO_METRICS"],
        }

    last_ch = metrics[-1].chapter_no
    items_by_no = {m.chapter_no: m for m in metrics}

    overall = [float(m.scores.get("overall", 0.0)) for m in metrics]
    cost_series = [float(m.scores.get("cost", 0.0)) for m in metrics]
    reversal_series = [float(m.scores.get("reversal", 0.0)) for m in metrics]
    conflict = [float(m.scores.get("conflict_strength", 0.0)) for m in metrics]
    pace = [float(m.scores.get("pace", 0.0)) for m in metrics]
    overall_by_no = {m.chapter_no: float(m.scores.get("overall", 0.0)) for m in metrics}

    overall_ma = moving_average(overall, 5)
    conflict_ma = moving_average(conflict, 5)
    pace_ma = moving_average(pace, 5)

    peaks, valleys = detect_peaks_valleys(metrics)

    zones = merge_ranges(fatigue_by_overall(metrics) + fatigue_by_flat_curve(metrics))
    fatigue_list = [{"from": a, "to": b, "reason": r} for a, b, r in zones]

    arcs: dict[str, list[ChapterMetric]] = defaultdict(list)
    for m in metrics:
        arcs[arc_key(m)].append(m)

    arc_summary: list[dict[str, Any]] = []
    for ak, arr in arcs.items():
        ov = [float(x.scores.get("overall", 0.0)) for x in arr]
        avg = avg_scores(arr)
        arc_summary.append(
            {
                "arc_id": ak,
                "chapter_from": arr[0].chapter_no,
                "chapter_to": arr[-1].chapter_no,
                "avg_scores": avg,
                "curve_shape": curve_shape(ov),
                "issues_top": infer_issues_top(avg),
                "mechanics_mix": mechanics_mix(arr),
            }
        )
    arc_summary.sort(key=lambda x: x["chapter_from"])

    diagnosis: list[dict[str, Any]] = []
    for a, b, reason in zones:
        actions = suggest_actions_for_zone(items_by_no, a, b)
        diagnosis.append(
            {
                "severity": "high" if (b - a + 1) >= 7 else "mid",
                "where": {"chapter_from": a, "chapter_to": b},
                "type": "fatigue_zone",
                "detail": f"{reason}；建议补代价/时压/反转以恢复张力",
                "suggest_actions": [{"chapter_no": n, "action": act} for n, act in actions],
            }
        )

    advanced_peak_spacing = peak_spacing(peaks)
    advanced_post_drop = post_peak_drop(overall_by_no, peaks)
    advanced_late_fade = late_book_fade(overall)
    advanced_sawtooth = sawtooth_rate(overall)

    for outlier in advanced_peak_spacing.get("outliers", []):
        mid = (int(outlier["from"]) + int(outlier["to"])) // 2
        diagnosis.append(
            {
                "severity": "mid",
                "where": {"chapter_from": int(outlier["from"]), "chapter_to": int(outlier["to"])},
                "type": "peak_gap",
                "detail": f"爆点空窗过长（gap={outlier['gap']}）",
                "suggest_actions": [{"chapter_no": n, "action": a} for n, a in _actions_for_peak_gap(mid)],
            }
        )

    for drop in advanced_post_drop:
        diagnosis.append(
            {
                "severity": "mid",
                "where": {"chapter_from": int(drop["from"]), "chapter_to": int(drop["to"])},
                "type": "post_peak_drop",
                "detail": f"高潮后连续回落（peak={drop['peak']} tail_avg={drop['tail_avg']})",
                "suggest_actions": [{"chapter_no": n, "action": a} for n, a in _actions_for_post_peak_drop(int(drop["from"]))],
            }
        )

    if advanced_late_fade:
        n = len(metrics)
        start_no = metrics[int(n * 0.7)].chapter_no
        end_no = metrics[-1].chapter_no
        diagnosis.append(
            {
                "severity": "high",
                "where": {"chapter_from": start_no, "chapter_to": end_no},
                "type": "late_book_fade",
                "detail": f"后30%张力下滑（delta={advanced_late_fade['delta']}）",
                "suggest_actions": [
                    {"chapter_no": start_no, "action": "timer"},
                    {"chapter_no": min(start_no + 2, end_no), "action": "cost_hardening"},
                    {"chapter_no": min(start_no + 4, end_no), "action": "face_slap"},
                ],
            }
        )

    if advanced_sawtooth.get("flag"):
        diagnosis.append(
            {
                "severity": "mid",
                "where": {"chapter_from": metrics[0].chapter_no, "chapter_to": metrics[-1].chapter_no},
                "type": "sawtooth",
                "detail": f"章节振荡偏高（rate={advanced_sawtooth['rate']}）",
                "suggest_actions": [
                    {"chapter_no": metrics[0].chapter_no + 1, "action": "timer"},
                    {"chapter_no": metrics[0].chapter_no + 2, "action": "raise_stakes"},
                ],
            }
        )

    arc_target_rows: list[dict[str, Any]] = []
    target_map = arc_targets or {}
    for arc in arc_summary:
        arc_id = str(arc["arc_id"])
        arr = arcs.get(arc_id, [])
        arc_overall = [float(x.scores.get("overall", 0.0)) for x in arr]
        arc_cost = [float(x.scores.get("cost", 0.0)) for x in arr]
        arc_reversal = [float(x.scores.get("reversal", 0.0)) for x in arr]

        target_shape = "ramp"
        target_points = DEFAULT_ARC_TARGET_POINTS[target_shape]
        weights = {"overall": 0.6, "cost": 0.2, "reversal": 0.2}

        existing = target_map.get(arc_id)
        if existing:
            target_shape = str(existing.get("target_shape") or target_shape)
            target_points = [float(x) for x in (existing.get("target_points") or target_points)]
            if len(target_points) != 5:
                target_points = DEFAULT_ARC_TARGET_POINTS.get(target_shape, DEFAULT_ARC_TARGET_POINTS["ramp"])
            weights = dict(existing.get("weights") or weights)

        actual_overall = sample_5_points(arc_overall)
        actual_cost = sample_5_points(arc_cost)
        actual_reversal = sample_5_points(arc_reversal)

        actual_points = []
        for i in range(5):
            combined = (
                float(weights.get("overall", 0.6)) * actual_overall[i]
                + float(weights.get("cost", 0.2)) * actual_cost[i]
                + float(weights.get("reversal", 0.2)) * actual_reversal[i]
            )
            actual_points.append(round(combined, 4))

        dev = deviation(actual_points, target_points)
        dev_type = classify_arc_deviation(dev["dev"])
        suggest_actions = _actions_for_arc_deviation(dev_type, int(arc["chapter_from"]), int(arc["chapter_to"]))
        if suggest_actions:
            diagnosis.append(
                {
                    "severity": "mid" if dev_type != "weak_ending" else "high",
                    "where": {"chapter_from": int(arc["chapter_from"]), "chapter_to": int(arc["chapter_to"])},
                    "type": "arc_target_deviation",
                    "detail": f"{arc_id} 偏差类型: {dev_type}",
                    "suggest_actions": [{"chapter_no": n, "action": a} for n, a in suggest_actions],
                }
            )

        arc_target_rows.append(
            {
                "arc_id": arc_id,
                "target_shape": target_shape,
                "target_points": [round(float(x), 4) for x in target_points],
                "actual_points": actual_points,
                "deviation": dev,
                "deviation_type": dev_type,
                "suggest_actions": [{"chapter_no": n, "action": a} for n, a in suggest_actions],
            }
        )

    diagnosis = sorted(
        diagnosis,
        key=lambda d: (
            0 if d.get("severity") == "high" else 1,
            int(((d.get("where") or {}).get("chapter_from") or 0)),
        ),
    )

    return {
        "schema_name": "BOOK_TENSION_ANALYSIS",
        "schema_ver": 1,
        "generated_at": now_iso(),
        "result": {
            "coverage": {
                "chapters_total": chapters_total,
                "chapters_with_metrics": len(metrics),
                "last_chapter_no": last_ch,
            },
            "book_trends": {
                "overall_ma": [round(x, 4) for x in overall_ma],
                "conflict_ma": [round(x, 4) for x in conflict_ma],
                "cost_ma": [round(x, 4) for x in moving_average(cost_series, 5)],
                "reversal_ma": [round(x, 4) for x in moving_average(reversal_series, 5)],
                "pace_ma": [round(x, 4) for x in pace_ma],
                "fatigue_zones": fatigue_list,
            },
            "peaks": {
                "chapters": peaks,
                "density_per_10": round(density_per_10(peaks, last_ch), 3),
            },
            "valleys": {
                "chapters": valleys,
                "density_per_10": round(density_per_10(valleys, last_ch), 3),
            },
            "arc_summary": arc_summary,
            "diagnosis": diagnosis,
            "advanced": {
                "peak_spacing": advanced_peak_spacing,
                "post_peak_drop": advanced_post_drop,
                "late_book_fade": advanced_late_fade,
                "sawtooth": advanced_sawtooth,
            },
            "arc_targets": arc_target_rows,
        },
        "warnings": [],
    }


async def run_book_tension_analyze_job(session: AsyncSession, payload: dict[str, Any], on_progress, on_log) -> dict[str, Any]:
    book_id = str(payload["book_id"])

    await on_progress(10, "LOAD_METRICS", "加载章节张力指标")
    rows = await fetch_latest_metrics_rows(session, book_id)
    metrics = [row_to_metric(r) for r in rows]
    chapters_total = await get_chapters_total(session, book_id)
    arc_targets = await fetch_arc_targets(session, book_id)

    await on_progress(55, "ANALYZE", "计算趋势与诊断")
    report = build_book_tension_analysis(book_id, metrics, chapters_total, arc_targets=arc_targets)

    await on_progress(92, "SAVE_SKILL_RUN", "保存分析报告")
    saved = await session.execute(
        text(
            """
            INSERT INTO skill_run(book_id, skill_name, schema_ver, output)
            VALUES (:book_id, 'BOOK_TENSION_ANALYSIS_V1', 1, CAST(:output AS jsonb))
            RETURNING skill_run_id
            """
        ),
        {"book_id": book_id, "output": json.dumps(report)},
    )
    skill_run_id = str(saved.scalar_one())
    await session.commit()

    await on_log("INFO", "DONE", "book tension analysis 完成")
    await on_progress(100, "DONE", "完成")
    return {"skill_run_id": skill_run_id}


async def get_latest_book_tension_report(session: AsyncSession, book_id: str) -> dict[str, Any]:
    res = await session.execute(
        text(
            """
            SELECT skill_run_id, output, created_at
            FROM skill_run
            WHERE book_id=:book_id
              AND skill_name='BOOK_TENSION_ANALYSIS_V1'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"book_id": book_id},
    )
    row = res.mappings().first()
    if not row:
        raise RuntimeError("REPORT_NOT_FOUND")
    return dict(row)

