from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

PRIO = {
    "cost_hardening": 1,
    "timer": 2,
    "reversal": 3,
    "raise_stakes": 4,
    "face_slap": 5,
    "betrayal": 5,
    "upgrade": 6,
    "rescue": 6,
}

ORDER = ["raise_stakes", "face_slap", "betrayal", "cost_hardening", "reversal", "timer", "upgrade", "rescue"]


def merge_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by: dict[int, set[str]] = {}
    for a in actions:
        try:
            ch = int(a.get("chapter_no") or 0)
        except Exception:
            continue
        if ch <= 0:
            continue
        action = str(a.get("action") or "").strip()
        if not action:
            continue
        by.setdefault(ch, set()).add(action)

    merged: list[dict[str, Any]] = []
    for ch, acts in by.items():
        picked = sorted(list(acts), key=lambda x: PRIO.get(x, 99))[:2]
        merged.append({"chapter_no": ch, "actions": picked})
    merged.sort(key=lambda x: int(x["chapter_no"]))
    return merged


def _cluster_key(sample: dict[str, Any]) -> str:
    context = sample.get("context") or {}
    arc_shape = str(context.get("arc_shape") or "unknown")
    phase = str(context.get("phase") or "unknown")
    genre = str(context.get("genre") or "unknown")
    mechs = sorted(sample.get("applied_mechanics") or [])
    mech_key = "+".join(str(m) for m in mechs if m)
    return f"{arc_shape}|{phase}|{genre}|{mech_key}"


def _mean(xs: list[float]) -> float:
    if not xs:
        return 0.0
    return sum(xs) / len(xs)


def aggregate_samples(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        groups[_cluster_key(sample)].append(sample)

    out: list[dict[str, Any]] = []
    for key, arr in groups.items():
        d_overall = [float((a.get("delta") or {}).get("overall", 0.0)) for a in arr]
        d_cost = [float((a.get("delta") or {}).get("cost", 0.0)) for a in arr]
        d_reversal = [float((a.get("delta") or {}).get("reversal", 0.0)) for a in arr]
        books = {str(a.get("book_id")) for a in arr}
        arcs = {str(a.get("arc_id") or "none") for a in arr}
        mechs = sorted(list({m for a in arr for m in (a.get("applied_mechanics") or []) if m}))
        arc_shape, phase, genre, _ = key.split("|", 3)
        out.append(
            {
                "key": key,
                "n": len(arr),
                "books": len(books),
                "arcs": len(arcs),
                "mean_overall": _mean(d_overall),
                "mean_cost": _mean(d_cost),
                "mean_reversal": _mean(d_reversal),
                "mechs": mechs,
                "arc_shape": arc_shape,
                "phase": phase,
                "genre": genre,
            }
        )
    return out


def should_promote(group: dict[str, Any], min_samples: int, min_mean_overall: float) -> bool:
    if int(group.get("n", 0)) < min_samples:
        return False
    if int(group.get("books", 0)) < 2 and int(group.get("arcs", 0)) < 2:
        return False
    if float(group.get("mean_overall", 0.0)) < min_mean_overall:
        return False
    mechs = list(group.get("mechs") or [])
    if not mechs or len(mechs) > 3:
        return False
    return True


def build_recipe(mechs: list[str], arc_shape: str, phase: str) -> dict[str, Any]:
    ordered = sorted(mechs, key=lambda m: ORDER.index(m) if m in ORDER else 99)
    if any(m in ordered for m in ("reversal", "face_slap", "betrayal")):
        anchor = "turning_point"
    elif "timer" in ordered:
        anchor = "goal"
    else:
        anchor = "turning_point"
    insert_plan = [{"relative_to": anchor, "mechanic": mech, "offset": idx} for idx, mech in enumerate(ordered)]
    return {
        "schema_name": "TEMPLATE_RECIPE",
        "schema_ver": 1,
        "target_shape": f"{arc_shape}_{phase}_fix",
        "insert_plan": insert_plan,
        "limits": {"max_insert_nodes": 4},
        "notes": "auto-evolved",
    }


def _unique_key(base_template_id: str | None, group: dict[str, Any]) -> str:
    mech_key = "+".join(group.get("mechs") or [])
    raw = f"{base_template_id or 'none'}|{group.get('arc_shape')}|{group.get('phase')}|{group.get('genre')}|{mech_key}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


async def run_template_evolve_job(
    session: AsyncSession,
    payload: dict[str, Any],
    on_progress,
    on_log,
) -> dict[str, Any]:
    min_samples = int(payload.get("min_samples") or 8)
    min_mean_overall = float(payload.get("min_mean_overall") or 0.05)
    scope = payload.get("scope") or {}
    base_template_id = payload.get("base_template_id")

    await on_progress(10, "LOAD_SAMPLES", "读取修复效果样本")
    sql = """
      SELECT sample_id, book_id, arc_id, chapter_no, applied_mechanics, delta, context, created_at
      FROM repair_effect_sample
      WHERE
        (COALESCE((delta->>'overall')::float, 0.0) >= 0.06
         OR COALESCE((delta->>'cost')::float, 0.0) >= 0.12
         OR COALESCE((delta->>'reversal')::float, 0.0) >= 0.12)
    """
    params: dict[str, Any] = {}
    if scope.get("arc_shape"):
        sql += " AND context->>'arc_shape' = :arc_shape"
        params["arc_shape"] = str(scope["arc_shape"])
    res = await session.execute(text(sql), params)
    samples = [dict(r) for r in res.mappings().all()]

    await on_progress(40, "AGGREGATE", "聚合有效模式")
    groups = aggregate_samples(samples)
    promoted = [g for g in groups if should_promote(g, min_samples, min_mean_overall)]

    await on_progress(70, "GENERATE_VARIANTS", "生成模板变体")
    created: list[dict[str, Any]] = []
    skipped = 0
    for group in promoted:
        recipe = build_recipe(group["mechs"], str(group["arc_shape"]), str(group["phase"]))
        ukey = _unique_key(str(base_template_id) if base_template_id else None, group)
        name = f"Fix-{group['arc_shape']}-{group['phase']}-v1"
        scope_json = {"arc_shape": group["arc_shape"], "phase": group["phase"], "genre": group["genre"]}
        stats = {
            "n": group["n"],
            "books": group["books"],
            "arcs": group["arcs"],
            "mean_overall": round(float(group["mean_overall"]), 4),
            "mean_cost": round(float(group["mean_cost"]), 4),
            "mean_reversal": round(float(group["mean_reversal"]), 4),
            "mechs": group["mechs"],
        }
        try:
            ins = await session.execute(
                text(
                    """
                    INSERT INTO template_variant(base_template_id, unique_key, name, scope, recipe, enabled, weight, stats)
                    VALUES (:base_template_id, :unique_key, :name, :scope::jsonb, :recipe::jsonb, false, 0.1, :stats::jsonb)
                    RETURNING variant_id, base_template_id, unique_key, name, scope, recipe, enabled, weight, stats, created_at
                    """
                ),
                {
                    "base_template_id": str(base_template_id) if base_template_id else None,
                    "unique_key": ukey,
                    "name": name,
                    "scope": json.dumps(scope_json),
                    "recipe": json.dumps(recipe),
                    "stats": json.dumps(stats),
                },
            )
            created.append(dict(ins.mappings().one()))
        except Exception:
            skipped += 1

    await on_progress(92, "SAVE_OUTPUT", "保存结果")
    output = {
        "schema_name": "TEMPLATE_EVOLUTION_RESULT",
        "schema_ver": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": {
            "samples": len(samples),
            "groups": len(groups),
            "promoted_groups": len(promoted),
            "variants_created": len(created),
            "variants_skipped": skipped,
            "variants": created,
        },
        "warnings": [],
    }

    out_book_id = payload.get("book_id")
    if not out_book_id and samples:
        out_book_id = str(samples[0].get("book_id"))
    if not out_book_id:
        row = await session.execute(text("SELECT book_id FROM book ORDER BY created_at DESC LIMIT 1"))
        out_book_id = row.scalar()
    if not out_book_id:
        await on_log("WARN", "SAVE_OUTPUT", "无可用book_id，跳过skill_run保存")
        await on_progress(100, "DONE", "完成")
        return {"skill_run_id": None, "variants_created": len(created), "variants_skipped": skipped}

    sr = await session.execute(
        text(
            """
            INSERT INTO skill_run(book_id, skill_name, schema_ver, output)
            VALUES (:book_id, 'TEMPLATE_EVOLVE_V1', 1, :output::jsonb)
            RETURNING skill_run_id
            """
        ),
        {"book_id": str(out_book_id), "output": json.dumps(output)},
    )
    skill_run_id = str(sr.scalar_one())
    await session.commit()
    await on_log("INFO", "DONE", f"template evolve 完成，created={len(created)}, skipped={skipped}")
    await on_progress(100, "DONE", "完成")
    return {"skill_run_id": skill_run_id, "variants_created": len(created), "variants_skipped": skipped}
