from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..defaults import DEFAULT_LLM_MODEL, DEFAULT_TENSION_STYLE, DEFAULT_TENSION_TARGETS, merge_defaults
from .book_tension import insert_chapter_tension_metric
from .mechanics import ACTION_MECHANIC_MAP, MECHANICS
from .ollama_client import OllamaClient
from .patch_apply import apply_patches, apply_patches_to_outline
from .prompt_templates import (
    STRICT_JSON_SYSTEM_PROMPT,
    build_eval_user_prompt,
    build_fill_user_prompt,
    build_plan_user_prompt,
)
from .schema_validate import (
    short_err,
    validate_eval_output,
    validate_fill_output,
    validate_plan_output,
)
from .storage import create_repair_effect_sample


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


DEFAULT_NODE_CONFLICT = {
    "hook": {"opposition_strength": 0.3, "stake_level": 0.4, "cost_level": 0.0, "reversal_power": 0.2},
    "goal": {"opposition_strength": 0.2, "stake_level": 0.5, "cost_level": 0.0, "reversal_power": 0.0},
    "obstacle": {"opposition_strength": 0.6, "stake_level": 0.6, "cost_level": 0.2, "reversal_power": 0.1},
    "escalation": {"opposition_strength": 0.7, "stake_level": 0.7, "cost_level": 0.4, "reversal_power": 0.2},
    "turning_point": {"opposition_strength": 0.8, "stake_level": 0.7, "cost_level": 0.5, "reversal_power": 0.7},
    "cost": {"opposition_strength": 0.5, "stake_level": 0.7, "cost_level": 0.9, "reversal_power": 0.1},
    "gain": {"opposition_strength": 0.4, "stake_level": 0.8, "cost_level": 0.1, "reversal_power": 0.2},
    "cliffhanger": {"opposition_strength": 0.5, "stake_level": 0.7, "cost_level": 0.0, "reversal_power": 0.5},
}

MECH_COST: dict[str, tuple[int, int]] = {
    "cost_hardening": (1, 0),
    "timer": (1, 0),
    "raise_stakes": (1, 1),
    "face_slap": (2, 0),
    "rescue": (2, 0),
    "betrayal": (2, 0),
    "upgrade": (2, 1),
    "reversal": (1, 1),
    "strengthen_obstacle": (0, 1),
}

REQ_BY_MECHANIC: dict[str, list[str]] = {
    "timer": ["写清期限+失败后果", "期限必须具体", "后果绑定人物利益"],
    "cost_hardening": ["代价必须不可逆或长期负担", "代价影响下一章"],
    "raise_stakes": ["赌注从小风险提升到大后果", "写清提赌注因果"],
    "reversal": ["包含误导点+真相点", "解释为何此前看错"],
    "face_slap": ["公开场景+评判标准", "反击方式明确且有后果"],
    "upgrade": ["升级收益明确", "升级限制明确"],
    "rescue": ["救场不能凭空出现", "救场后新增限制或债务"],
    "betrayal": ["背叛动机明确", "背刺后即时损失"],
    "sharpen_hook": ["开头包含目标+风险+异常点"],
}


def evaluate_tension_score_v1(text_value: str, nodes: list[dict[str, Any]]) -> dict[str, Any]:
    length = len(text_value or "")
    exclamation = (text_value or "").count("！")
    question = (text_value or "").count("？")
    fight_words = sum((text_value or "").count(w) for w in ["冲突", "代价", "危机", "追杀", "打脸", "反转"])

    conflict_strength = _clamp(0.25 + fight_words * 0.03)
    stakes = _clamp(0.2 + question * 0.02)
    cost = _clamp(0.15 + (text_value or "").count("代价") * 0.08)
    pace = _clamp(0.2 + exclamation * 0.02 + min(length, 4000) / 40000)
    reversal = _clamp(0.2 + (text_value or "").count("反转") * 0.08)
    hook = _clamp(0.25 + (text_value[:160] if text_value else "").count("？") * 0.08)
    payoff = _clamp((conflict_strength + stakes + cost + reversal) / 4)
    overall = _clamp((conflict_strength + stakes + cost + pace + reversal + hook + payoff) / 7)

    curve = [
        round(_clamp(hook * 0.8), 2),
        round(_clamp(conflict_strength * 0.7), 2),
        round(_clamp(stakes * 0.9), 2),
        round(_clamp(max(conflict_strength, reversal)), 2),
        round(_clamp(payoff * 0.9), 2),
    ]

    node_map = {n.get("type"): n.get("node_id") for n in nodes if isinstance(n, dict)}
    issues: list[dict[str, Any]] = []
    if conflict_strength < 0.45:
        issues.append({"type": "weak_obstacle", "severity": "high", "where": {"node_id": node_map.get("obstacle", "N3")}, "detail": "阻碍强度偏弱"})
    if stakes < 0.45:
        issues.append({"type": "low_stakes", "severity": "mid", "where": {"node_id": node_map.get("escalation", "N4")}, "detail": "赌注不足"})
    if cost < 0.4:
        issues.append({"type": "no_cost", "severity": "mid", "where": {"node_id": node_map.get("cost", "N6")}, "detail": "代价不明确"})
    if max(curve) - min(curve) < 0.18:
        issues.append({"type": "flat_curve", "severity": "high", "where": {"node_id": node_map.get("escalation", "N4")}, "detail": "张力曲线过平"})
    if reversal < 0.4:
        issues.append({"type": "fake_reversal", "severity": "mid", "where": {"node_id": node_map.get("turning_point", "N5")}, "detail": "反转力度不足"})
    if hook < 0.45:
        issues.append({"type": "weak_hook", "severity": "mid", "where": {"node_id": node_map.get("hook", "N1")}, "detail": "开头钩子不够强"})

    return {
        "schema_name": "EVAL_TENSION_SCORE",
        "schema_ver": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": {
            "scores": {
                "overall": round(overall, 2),
                "conflict_strength": round(conflict_strength, 2),
                "stakes": round(stakes, 2),
                "cost": round(cost, 2),
                "pace": round(pace, 2),
                "reversal": round(reversal, 2),
                "hook": round(hook, 2),
                "payoff": round(payoff, 2),
            },
            "tension_curve": curve,
            "issues": issues[:8],
        },
        "warnings": [],
    }


def _build_default_outline(chapter_no: int, chapter_title: str) -> dict[str, Any]:
    node_types = ["hook", "goal", "obstacle", "escalation", "turning_point", "cost", "gain", "cliffhanger"]
    nodes = []
    for i, node_type in enumerate(node_types, start=1):
        conf = {"goal_clarity": 0.5, "time_pressure": 0.4, "info_gap": 0.4}
        conf.update(DEFAULT_NODE_CONFLICT.get(node_type, {}))
        nodes.append(
            {
                "node_id": f"N{i}",
                "type": node_type,
                "summary": "",
                "beats": [],
                "characters": [],
                "world_facts": [],
                "plot_hooks": [],
                "conflict": conf,
                "constraints": {},
                "_meta": {"needs_review": False},
            }
        )
    return {
        "schema_name": "OUTLINE_DETAIL",
        "schema_ver": 1,
        "chapter_no": chapter_no,
        "chapter_title": chapter_title,
        "template_ref": {},
        "nodes": nodes,
        "global_constraints": {"must_have_cost": True, "must_end_with_hook": True},
    }


async def _load_outline_detail(session: AsyncSession, chapter_id: str) -> tuple[dict[str, Any], dict[str, Any], int]:
    chapter_data = await session.execute(
        text('SELECT book_id, "order", arc_id, title FROM chapter WHERE chapter_id=:chapter_id'),
        {"chapter_id": chapter_id},
    )
    chapter_row = chapter_data.mappings().first()
    if not chapter_row:
        raise RuntimeError("CHAPTER_NOT_FOUND")

    latest = await session.execute(
        text(
            """
            SELECT version, content
            FROM outline
            WHERE chapter_id=:chapter_id AND scope='chapter'
            ORDER BY version DESC
            LIMIT 1
            """
        ),
        {"chapter_id": chapter_id},
    )
    row_outline = latest.mappings().first()
    if row_outline:
        outline = row_outline["content"] or {}
        version = int(row_outline["version"])
    else:
        outline = _build_default_outline(int(chapter_row["order"]), chapter_row["title"] or f"Chapter {chapter_row['order']}")
        version = 0
    return outline, dict(chapter_row), version


async def _load_outline_detail_with_override(
    session: AsyncSession,
    chapter_id: str,
    outline_id: str | None,
) -> tuple[dict[str, Any], dict[str, Any], int]:
    outline_detail, chapter_row, latest_version = await _load_outline_detail(session, chapter_id)
    if outline_id:
        specific = await session.execute(
            text(
                """
                SELECT version, content
                FROM outline
                WHERE outline_id=:outline_id AND chapter_id=:chapter_id AND scope='chapter'
                LIMIT 1
                """
            ),
            {"outline_id": outline_id, "chapter_id": chapter_id},
        )
        row = specific.mappings().first()
        if row:
            outline_detail = row["content"] or outline_detail
            latest_version = int(row["version"])
    return outline_detail, chapter_row, latest_version


def should_inject(chapter_no: int, density: float) -> bool:
    if density <= 0:
        return False
    interval = max(2, int(round(1.0 / density)))
    return (chapter_no % interval) == 0


def choose_anchor(nodes: list[dict[str, Any]], preferred_types: list[str]) -> str:
    for node in nodes:
        if node.get("type") in preferred_types and not node.get("_meta", {}).get("overloaded"):
            return str(node.get("node_id"))
    for node in nodes:
        if node.get("node_id"):
            return str(node["node_id"])
    return "N1"


def already_mechanics(outline: dict[str, Any]) -> set[str]:
    used: set[str] = set()
    for node in outline.get("nodes", []):
        if not isinstance(node, dict):
            continue
        meta = node.get("_meta") or {}
        mech = meta.get("mechanic")
        if mech:
            used.add(str(mech))
        for p in (meta.get("patches_applied") or []):
            if isinstance(p, dict):
                m = p.get("mechanic") or ((p.get("_meta") or {}).get("mechanic") if isinstance(p.get("_meta"), dict) else None)
                if m:
                    used.add(str(m))
    return used


def _count_patch_cost(patches: list[dict[str, Any]]) -> tuple[int, int]:
    insert_count = 0
    change_count = 0
    for p in patches:
        pt = p.get("patch_type")
        if pt == "insert_node":
            insert_count += 1
        else:
            change_count += 1
    return insert_count, change_count


def _patch_id() -> str:
    return f"patch_{uuid4().hex[:12]}"


def _requirements_for_fill(mechanic: str, node_type: str) -> list[str]:
    req = [
        "2-6行结构概述",
        "不要长对白",
        "不引用拆书原句",
    ]
    req.extend(REQ_BY_MECHANIC.get(mechanic, []))
    if node_type == "change_summary":
        req.append("保持主线不变")
    return req


def plan_recipe(
    outline: dict[str, Any],
    scores: dict[str, Any],
    targets: dict[str, Any],
    style: dict[str, Any],
    forced_actions: list[str] | None = None,
    variant_actions: list[str] | None = None,
    hard_limits: dict[str, int] | None = None,
) -> dict[str, Any]:
    nodes = outline.get("nodes", [])
    chapter_no = int(outline.get("chapter_no", 1) or 1)
    gap = {k: max(0.0, float(targets.get(k, 0.0)) - float(scores.get(k, 0.0))) for k in targets}

    limits = hard_limits or {
        "max_insert_nodes": 4,
        "max_change_summary": 2,
        "max_total_patches": 8,
    }
    remaining_insert = limits["max_insert_nodes"]
    remaining_change = limits["max_change_summary"]

    selected_actions: list[dict[str, Any]] = []
    patches: list[dict[str, Any]] = []
    already_used = already_mechanics(outline)

    def try_add(mech_name: str, anchor: str | None = None, *, force: bool = False) -> bool:
        nonlocal remaining_insert, remaining_change
        mechanic = MECHANICS.get(mech_name)
        if mechanic is None:
            return False
        if (not force) and mech_name in already_used:
            return False

        ctx = {"outline_detail": outline, "selected_node_id": anchor, "strength": 0.7}
        generated = mechanic.apply(ctx)
        ins, chg = _count_patch_cost(generated)
        if remaining_insert < ins or remaining_change < chg:
            return False

        for p in generated:
            p["patch_id"] = _patch_id()
            p.setdefault("_meta", {})["mechanic"] = mech_name
        patches.extend(generated)
        remaining_insert -= ins
        remaining_change -= chg
        already_used.add(mech_name)
        selected_actions.append({"mechanic": mech_name, "anchor": anchor, "patches": len(generated)})
        return True

    if forced_actions:
        anchor_rules = {
            "cost_hardening": ["cost", "turning_point"],
            "timer": ["goal", "hook"],
            "raise_stakes": ["obstacle", "goal", "escalation"],
            "reversal": ["turning_point", "cliffhanger"],
            "face_slap": ["turning_point", "gain"],
            "upgrade": ["gain", "turning_point"],
            "rescue": ["escalation", "turning_point"],
            "betrayal": ["cliffhanger", "turning_point"],
            "strengthen_obstacle": ["obstacle", "escalation"],
        }
        for action in forced_actions:
            mech = ACTION_MECHANIC_MAP.get(action, action)
            prefs = anchor_rules.get(mech, ["turning_point", "gain", "goal"])
            try_add(mech, choose_anchor(nodes, prefs), force=True)
    else:
        if variant_actions:
            for action in variant_actions:
                mech = ACTION_MECHANIC_MAP.get(action, action)
                prefs = {
                    "timer": ["goal", "hook"],
                    "cost_hardening": ["cost", "turning_point"],
                    "reversal": ["turning_point", "cliffhanger"],
                    "raise_stakes": ["obstacle", "goal", "escalation"],
                    "face_slap": ["turning_point", "gain"],
                    "betrayal": ["cliffhanger", "turning_point"],
                    "upgrade": ["gain", "turning_point"],
                    "rescue": ["escalation", "turning_point"],
                    "strengthen_obstacle": ["obstacle", "escalation"],
                }.get(mech, ["turning_point", "gain", "goal"])
                try_add(mech, choose_anchor(nodes, prefs), force=False)

        if gap.get("cost", 0.0) >= 0.10:
            try_add("cost_hardening", choose_anchor(nodes, ["cost", "turning_point"]))
        if gap.get("pace", 0.0) >= 0.08:
            try_add("timer", choose_anchor(nodes, ["goal", "hook"]))
        if gap.get("stakes", 0.0) >= 0.08:
            try_add("raise_stakes", choose_anchor(nodes, ["obstacle", "goal", "escalation"]))
        if gap.get("reversal", 0.0) >= 0.10:
            try_add("reversal", choose_anchor(nodes, ["turning_point", "cliffhanger"]))

        if gap.get("conflict_strength", 0.0) >= 0.12:
            if not try_add("raise_stakes", choose_anchor(nodes, ["escalation", "obstacle"])):
                try_add("rescue", choose_anchor(nodes, ["escalation", "turning_point"]))

        if should_inject(chapter_no, float(style.get("face_slap_density", 0.0))):
            try_add("face_slap", choose_anchor(nodes, ["turning_point", "gain"]))
        if should_inject(chapter_no, float(style.get("upgrade_density", 0.0))):
            try_add("upgrade", choose_anchor(nodes, ["gain", "turning_point"]))

    if (not forced_actions) and gap.get("hook", 0.0) >= 0.10 and remaining_change > 0:
        hook_id = choose_anchor(nodes, ["hook"])
        patches.append(
            {
                "patch_id": _patch_id(),
                "patch_type": "change_summary",
                "where": {"node_id": hook_id},
                "change": {"before": "", "after": ""},
                "impact_estimate": {"hook": 0.1},
                "_meta": {"mechanic": "sharpen_hook"},
            }
        )
        selected_actions.append({"mechanic": "sharpen_hook", "anchor": hook_id, "patches": 1})
        remaining_change -= 1

    patches = patches[: limits["max_total_patches"]]

    fill_nodes: list[dict[str, Any]] = []
    for p in patches:
        if p.get("patch_type") == "insert_node":
            node = ((p.get("insert") or {}).get("node") or {})
            node_id = node.get("node_id")
            node_type = node.get("type")
            if node_id and node_type:
                mechanic = str((node.get("_meta") or {}).get("mechanic") or (p.get("_meta") or {}).get("mechanic") or "")
                fill_nodes.append(
                    {
                        "node_id": node_id,
                        "type": node_type,
                        "mechanic": mechanic,
                        "max_words": int(((node.get("constraints") or {}).get("max_words") or 120)),
                        "requirements": _requirements_for_fill(mechanic, str(node_type)),
                    }
                )
        else:
            node_id = (p.get("where") or {}).get("node_id")
            if node_id:
                mechanic = str((p.get("_meta") or {}).get("mechanic") or "sharpen_hook")
                fill_nodes.append(
                    {
                        "node_id": node_id,
                        "type": "change_summary",
                        "mechanic": mechanic,
                        "max_words": 120,
                        "requirements": _requirements_for_fill(mechanic, "change_summary"),
                    }
                )

    return {
        "gap": {k: round(v, 3) for k, v in gap.items()},
        "selected_actions": selected_actions,
        "patches": patches,
        "fill_nodes": fill_nodes,
        "limits": limits,
    }


async def _load_variant_actions(
    session: AsyncSession,
    *,
    book_id: str,
    chapter_no: int,
    arc_id: str | None,
) -> list[str]:
    # phase by chapter percentile (pre/mid/late)
    total_res = await session.execute(text("SELECT COUNT(*) FROM chapter WHERE book_id=:book_id"), {"book_id": book_id})
    total = int(total_res.scalar() or 0)
    phase = "mid"
    if total > 0:
        p = chapter_no / max(1, total)
        if p < 0.33:
            phase = "pre"
        elif p > 0.66:
            phase = "late"

    try:
        res = await session.execute(
            text(
                """
                SELECT recipe, scope
                FROM template_variant
                WHERE enabled=true
                ORDER BY weight DESC, created_at DESC
                LIMIT 20
                """
            )
        )
        rows = res.mappings().all()
    except Exception:
        return []
    for row in rows:
        scope = row.get("scope") or {}
        if scope.get("phase") and scope.get("phase") != phase:
            continue
        if scope.get("arc_id") and arc_id and scope.get("arc_id") != arc_id:
            continue
        recipe = row.get("recipe") or {}
        mechs = [str(x.get("mechanic")) for x in (recipe.get("insert_plan") or []) if x.get("mechanic")]
        if mechs:
            return mechs[:3]
    return []


def normalize_outline_style(text_value: str, max_lines: int = 6, max_chars: int = 220) -> str:
    t = (text_value or "").strip()
    t = re.sub(r"「[^」]{40,}」", "「…」", t)
    t = re.sub(r"“[^”]{40,}”", "“…”", t)
    if len(t) > max_chars:
        t = t[:max_chars].rstrip() + "…"

    parts = re.split(r"[。\n；;]+", t)
    parts = [p.strip() for p in parts if p.strip()]
    parts = parts[:max_lines]

    lines: list[str] = []
    for p in parts:
        if len(p) > 35:
            p = p[:35].rstrip() + "…"
        lines.append(p)
    return "\n".join(lines)


def suspicious_long_run(text_value: str, limit: int = 18) -> bool:
    longest = 0
    cur = 0
    for ch in text_value:
        if ch.isspace():
            cur = 0
        else:
            cur += 1
            longest = max(longest, cur)
    return longest >= limit


def _facts_summary_stub() -> dict[str, Any]:
    return {"characters": [], "world_rules": [], "open_plot_hooks": []}


def _generate_summary_for_node(fill_node: dict[str, Any], chapter_goal: str) -> str:
    mechanic = str(fill_node.get("mechanic") or "")
    node_type = str(fill_node.get("type") or "")

    if mechanic == "timer":
        return "设置明确期限与阶段目标\n失败将导致关键资源丧失\n角色必须立刻改变行动节奏"
    if mechanic == "cost_hardening" or node_type == "micro_cost":
        return "补入不可逆代价\n本章获益伴随长期负担\n该负担直接压到下一章"
    if mechanic == "raise_stakes":
        return "将赌注提升到身份与关系层\n失败后果从可承受变不可承受\n推动角色做高风险决策"
    if mechanic == "reversal":
        return "先确认误导信息成立\n再揭示隐藏条件触发反转\n反转后立即产生新后果"
    if mechanic == "face_slap":
        return "公开场景建立评判标准\n对手先行羞辱形成压迫\n主角用规则反击并留下后果"
    if mechanic == "upgrade":
        return "给出升级来源与即时收益\n明确新能力边界\n同步写入限制与代价"
    if mechanic == "rescue":
        return "外援或反制介入逆转局面\n救场需付出额外债务\n新增限制延续到后续"
    if mechanic == "betrayal":
        return "盟友立场突变造成即时损失\n揭示背叛动机与利益链\n结尾保留追击悬念"
    if mechanic == "sharpen_hook":
        return "开头直接给出章节目标\n同步抛出异常点与风险\n收束到本章必须立即行动"

    return f"围绕章节目标补强结构\n明确阻碍与代价\n结尾保留推进钩子：{chapter_goal[:20]}"


def fill_summaries(fill_request: dict[str, Any]) -> dict[str, Any]:
    summaries: dict[str, str] = {}
    chapter_goal = str(fill_request.get("chapter_goal") or "推进主线")
    for item in fill_request.get("fill_nodes", []):
        node_id = str(item.get("node_id") or "")
        if not node_id:
            continue
        summaries[node_id] = _generate_summary_for_node(item, chapter_goal)

    return {
        "schema_name": "FILL_BEAT_SUMMARY",
        "schema_ver": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": {"summaries": summaries},
        "warnings": [],
    }


def fill_in_batches(fill_request: dict[str, Any], batch_size: int = 8) -> dict[str, str]:
    fill_nodes = fill_request.get("fill_nodes", []) or []
    merged: dict[str, str] = {}
    for i in range(0, len(fill_nodes), batch_size):
        req = dict(fill_request)
        current_batch = fill_nodes[i : i + batch_size]
        req["fill_nodes"] = current_batch
        output = fill_summaries(req)
        summary_map = (((output.get("result") or {}).get("summaries")) or {})
        fills_obj = {"fills": [{"node_id": str(k), "summary": str(v)} for k, v in summary_map.items()]}
        expected = {str(item.get("node_id")) for item in current_batch if item.get("node_id")}
        validated, _ = validate_fill_output(fills_obj, expected_node_ids=expected)
        for item in validated["fills"]:
            merged[item["node_id"]] = item["summary"]
    return merged


def apply_filled_summaries_to_patches(patches: list[dict[str, Any]], summaries: dict[str, str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for patch in patches:
        p = dict(patch)
        if p.get("patch_type") == "insert_node":
            node = ((p.get("insert") or {}).get("node") or {})
            node_id = str(node.get("node_id") or "")
            if node_id and node_id in summaries:
                summary = normalize_outline_style(summaries[node_id])
                node["summary"] = summary
                if suspicious_long_run(summary):
                    meta = node.get("_meta", {}) or {}
                    meta["needs_review"] = True
                    node["_meta"] = meta
                p["insert"] = {"node": node}
        else:
            node_id = str(((p.get("where") or {}).get("node_id")) or "")
            if node_id and node_id in summaries:
                after = normalize_outline_style(summaries[node_id])
                change = p.get("change", {}) or {}
                change["after"] = after
                p["change"] = change
        out.append(p)
    return out


async def _build_fill_request(outline: dict[str, Any], fill_nodes: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = outline.get("nodes", [])
    context_nodes = []
    for n in nodes[:4]:
        context_nodes.append({"node_id": n.get("node_id"), "type": n.get("type"), "summary": n.get("summary")})
    chapter_goal = "推进主线并制造下一章悬念"
    return {
        "schema_name": "FILL_BEAT_SUMMARY_REQUEST",
        "schema_ver": 1,
        "chapter_no": outline.get("chapter_no", 1),
        "chapter_title": outline.get("chapter_title", ""),
        "chapter_goal": chapter_goal,
        "facts_summary": _facts_summary_stub(),
        "outline_nodes_context": context_nodes,
        "fill_nodes": fill_nodes,
    }


def _outline_nodes_min(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        out.append(
            {
                "node_id": str(node.get("node_id") or ""),
                "type": str(node.get("type") or ""),
                "summary": str(node.get("summary") or ""),
            }
        )
    return out


async def _try_llm_eval(
    *,
    llm_model: str,
    targets: dict[str, Any],
    nodes: list[dict[str, Any]],
    on_log,
) -> dict[str, Any] | None:
    prompt = build_eval_user_prompt(targets=targets, outline_nodes=_outline_nodes_min(nodes))
    schema_hint = (
        '{"schema_name":"EVAL_TENSION_SCORE","schema_ver":1,'
        '"result":{"scores":{"overall":0.0,"conflict_strength":0.0,"stakes":0.0,"cost":0.0,'
        '"pace":0.0,"reversal":0.0,"hook":0.0,"payoff":0.0},"tension_curve":[0,0,0,0,0],"issues":[]},'
        '"warnings":[]}'
    )
    client = OllamaClient(settings.ollama_host)
    try:
        raw = await client.chat_json(
            model=llm_model,
            user=prompt,
            system=STRICT_JSON_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=900,
            timeout_s=120,
            retries=1,
            schema_hint=schema_hint,
            meta={"stage": "LLM_SCORE"},
        )
        if not isinstance(raw, dict):
            raise ValueError("eval output must be object")
        validated, warnings = validate_eval_output(raw)
        if warnings:
            await on_log("WARN", "LLM_SCORE", f"llm eval soft-fix: {', '.join(warnings[:4])}")
        return validated
    except Exception as exc:
        await on_log("WARN", "LLM_SCORE", f"llm eval fallback to rule: {short_err(exc)}")
        return None


async def _try_llm_fill(
    *,
    llm_model: str,
    fill_request: dict[str, Any],
    batch_size: int,
    on_log,
) -> dict[str, str] | None:
    fill_nodes = list(fill_request.get("fill_nodes") or [])
    if not fill_nodes:
        return {}
    client = OllamaClient(settings.ollama_host)
    merged: dict[str, str] = {}
    for i in range(0, len(fill_nodes), batch_size):
        current_batch = fill_nodes[i : i + batch_size]
        prompt = build_fill_user_prompt(
            max_words=120,
            outline_nodes=list(fill_request.get("outline_nodes_context") or []),
            fill_nodes=current_batch,
        )
        schema_hint = '{"fills":[{"node_id":"NODE_ID","summary":"TEXT"}]}'
        try:
            raw = await client.chat_json(
                model=llm_model,
                user=prompt,
                system=STRICT_JSON_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=600,
                timeout_s=90,
                retries=1,
                schema_hint=schema_hint,
                meta={"stage": "LLM_FILL", "batch_index": i // max(1, batch_size)},
            )
            if not isinstance(raw, dict):
                raise ValueError("fill output must be object")
            expected = {str(x.get("node_id")) for x in current_batch if x.get("node_id")}
            checked, warnings = validate_fill_output(raw, expected_node_ids=expected)
            if warnings:
                await on_log("WARN", "LLM_FILL", f"llm fill soft-fix: {', '.join(warnings[:4])}")
            for item in checked["fills"]:
                merged[str(item["node_id"])] = str(item["summary"])
        except Exception as exc:
            await on_log("WARN", "LLM_FILL", f"llm fill batch failed: {short_err(exc)}")
            return None
    return merged


async def _try_llm_plan(
    *,
    llm_model: str,
    targets: dict[str, Any],
    style: dict[str, Any],
    scores: dict[str, Any] | None,
    actions_override: list[str],
    outline_nodes: list[dict[str, Any]],
    limits: dict[str, int],
    reference_blocks: list[str] | None,
    on_log,
) -> dict[str, Any] | None:
    prompt = build_plan_user_prompt(
        targets=targets,
        style=style,
        eval_scores=scores,
        actions_override=actions_override,
        outline_nodes=outline_nodes,
        max_insert=int(limits.get("max_insert_nodes", 4)),
        max_change=int(limits.get("max_change_summary", 2)),
        max_patch=int(limits.get("max_total_patches", 8)),
        reference_blocks=reference_blocks,
    )
    schema_hint = (
        '{"schema_name":"TENSION_CONTROL_PLAN","schema_ver":1,'
        '"result":{"gap":{},"selected_actions":[],"limits":{"max_insert_nodes":4,"max_change_summary":2,'
        '"max_total_patches":8},"patches":[],"fill_nodes":[]},"warnings":[]}'
    )
    client = OllamaClient(settings.ollama_host)
    try:
        raw = await client.chat_json(
            model=llm_model,
            user=prompt,
            system=STRICT_JSON_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=1400,
            timeout_s=150,
            retries=1,
            schema_hint=schema_hint,
            meta={"stage": "LLM_PATCH"},
        )
        if not isinstance(raw, dict):
            raise ValueError("plan output must be object")
        validated, warnings = validate_plan_output(
            raw,
            max_insert=int(limits.get("max_insert_nodes", 4)),
            max_change=int(limits.get("max_change_summary", 2)),
            max_patches=int(limits.get("max_total_patches", 8)),
            actions_override=[str(x) for x in actions_override],
        )
        if warnings:
            await on_log("WARN", "VALIDATE_PATCH", f"llm plan soft-fix: {', '.join(warnings[:4])}")
        return validated
    except Exception as exc:
        await on_log("WARN", "LLM_PATCH", f"llm plan fallback to rule: {short_err(exc)}")
        return None


async def run_eval_tension_job(session: AsyncSession, payload: dict[str, Any], on_progress, on_log) -> dict[str, Any]:
    book_id = str(payload["book_id"])
    chapter_id = str(payload["chapter_id"])
    chapter_version_id = str(payload["chapter_version_id"])
    input_mode = payload.get("input_mode", "draft")
    llm_model = str(payload.get("llm_model") or DEFAULT_LLM_MODEL)
    targets = merge_defaults(DEFAULT_TENSION_TARGETS, payload.get("targets") or {})

    await on_progress(5, "GATHER_CONTEXT", "加载章节上下文")
    outline_detail, chapter_row, _ = await _load_outline_detail(session, chapter_id)
    nodes = outline_detail.get("nodes", []) if isinstance(outline_detail, dict) else []

    await on_progress(30, "LOAD_INPUT", "读取输入内容")
    if input_mode == "draft":
        src = await session.execute(
            text("SELECT text FROM chapter_version WHERE chapter_version_id=:cid"),
            {"cid": chapter_version_id},
        )
        row = src.first()
        source_text = row[0] if row else ""
    else:
        source_text = " ".join([(n.get("summary") or "")[:160] for n in nodes if isinstance(n, dict)])

    await on_progress(50, "LLM_SCORE", "阶段1: 打分与问题定位")
    score_data = await _try_llm_eval(
        llm_model=llm_model,
        targets=targets,
        nodes=nodes,
        on_log=on_log,
    )
    if score_data is None:
        raise RuntimeError("EVAL_AI_REQUIRED:LLM_SCORE_UNAVAILABLE")

    await on_progress(100, "DONE", "完成")
    saved = await session.execute(
        text(
            """
            INSERT INTO skill_run(book_id, skill_name, schema_ver, output)
            VALUES (:book_id, 'EVAL_CONFLICT_TENSION_V1', 1, CAST(:output AS jsonb))
            RETURNING skill_run_id
            """
        ),
        {"book_id": book_id, "output": json.dumps(score_data)},
    )
    skill_run_id = str(saved.scalar_one())

    mechanics_used: list[str] = []
    for node in nodes:
        meta = (node.get("_meta") or {}) if isinstance(node, dict) else {}
        for p in (meta.get("patches_applied") or []):
            if isinstance(p, dict):
                mech = p.get("mechanic")
                if mech:
                    mechanics_used.append(str(mech))
        mech_self = meta.get("mechanic")
        if mech_self:
            mechanics_used.append(str(mech_self))
    mechanics_used = sorted(set(mechanics_used))

    result_block = score_data.get("result") or {}
    await insert_chapter_tension_metric(
        session,
        book_id=book_id,
        chapter_id=chapter_id,
        chapter_no=int(chapter_row["order"]),
        chapter_version_id=chapter_version_id if chapter_version_id != "00000000-0000-0000-0000-000000000000" else None,
        eval_skill_run_id=skill_run_id,
        scores=dict(result_block.get("scores") or {}),
        tension_curve=[float(x) for x in (result_block.get("tension_curve") or [])],
        issues_count=len(result_block.get("issues") or []),
        mechanics_used=mechanics_used,
    )
    await session.commit()
    await on_log("INFO", "DONE", "tension eval 完成")
    return {"skill_run_id": skill_run_id, "scores": (score_data.get("result") or {}).get("scores", {})}


async def run_tension_control_plan_job(session: AsyncSession, payload: dict[str, Any], on_progress, on_log) -> dict[str, Any]:
    book_id = str(payload["book_id"])
    chapter_id = str(payload["chapter_id"])
    outline_id = str(payload["outline_id"]) if payload.get("outline_id") else None
    targets = merge_defaults(DEFAULT_TENSION_TARGETS, payload.get("targets", {}) or {})
    style = merge_defaults(DEFAULT_TENSION_STYLE, payload.get("style", {}) or {})
    actions_override = payload.get("actions_override") or []
    material_refs = [str(x).strip() for x in (payload.get("material_refs") or []) if str(x).strip()][:20]
    llm_model = str(payload.get("llm_model") or DEFAULT_LLM_MODEL)

    await on_progress(8, "GATHER_CONTEXT", "加载细纲与当前分数")
    outline_detail, chapter_row, _ = await _load_outline_detail_with_override(session, chapter_id, outline_id)
    nodes = outline_detail.get("nodes", []) if isinstance(outline_detail, dict) else []
    text_for_eval = " ".join([(n.get("summary") or "")[:160] for n in nodes if isinstance(n, dict)])

    await on_progress(24, "LLM_SCORE", "评估当前张力")
    score_data = await _try_llm_eval(
        llm_model=llm_model,
        targets=targets,
        nodes=nodes,
        on_log=on_log,
    )
    if score_data is None:
        raise RuntimeError("CONTROL_PLAN_AI_REQUIRED:LLM_SCORE_UNAVAILABLE")
    scores = (score_data.get("result") or {}).get("scores", {})

    await on_progress(40, "PLAN_RECIPE", "生成机制配方")
    variant_actions = await _load_variant_actions(
        session,
        book_id=book_id,
        chapter_no=int(outline_detail.get("chapter_no") or 1),
        arc_id=chapter_row.get("arc_id"),
    )
    plan = plan_recipe(
        outline_detail,
        scores,
        targets,
        style,
        forced_actions=list(actions_override),
        variant_actions=variant_actions,
    )
    llm_result = await _try_llm_plan(
        llm_model=llm_model,
        targets=targets,
        style=style,
        scores=scores,
        actions_override=[str(x) for x in actions_override],
        outline_nodes=_outline_nodes_min(nodes),
        limits={
            "max_insert_nodes": int(plan["limits"].get("max_insert_nodes", 4)),
            "max_change_summary": int(plan["limits"].get("max_change_summary", 2)),
            "max_total_patches": int(plan["limits"].get("max_total_patches", 8)),
        },
        reference_blocks=material_refs,
        on_log=on_log,
    )
    if llm_result is None:
        raise RuntimeError("CONTROL_PLAN_AI_REQUIRED:LLM_PLAN_UNAVAILABLE")

    await on_progress(58, "FILL_SUMMARIES", "批量填充补丁摘要")
    llm_patches = (((llm_result.get("result") or {}).get("patches")) or [])
    if not llm_patches:
        raise RuntimeError("CONTROL_PLAN_AI_REQUIRED:LLM_PLAN_EMPTY_PATCHES")
    fill_nodes = (((llm_result.get("result") or {}).get("fill_nodes")) or [])
    fill_req = await _build_fill_request(outline_detail, fill_nodes)
    llm_fills = await _try_llm_fill(llm_model=llm_model, fill_request=fill_req, batch_size=4, on_log=on_log)
    if llm_fills is None:
        raise RuntimeError("CONTROL_PLAN_AI_REQUIRED:LLM_FILL_UNAVAILABLE")
    final_patches = apply_filled_summaries_to_patches(llm_patches, llm_fills)
    llm_result["result"]["patches"] = final_patches[:12]
    validated_result: dict[str, Any] = llm_result

    await on_progress(92, "SAVE_SKILL_RUN", "写入控制计划")
    saved = await session.execute(
        text(
            """
            INSERT INTO skill_run(book_id, skill_name, schema_ver, output)
            VALUES (:book_id, 'TENSION_CONTROL_PLAN_V1', 1, CAST(:output AS jsonb))
            RETURNING skill_run_id
            """
        ),
        {"book_id": book_id, "output": json.dumps(validated_result)},
    )
    skill_run_id = str(saved.scalar_one())
    await session.commit()

    actual_patches = (((validated_result.get("result") or {}).get("patches")) or [])
    await on_log("INFO", "DONE", f"tension control plan 完成 patches={len(actual_patches)} refs={len(material_refs)}")
    await on_progress(100, "DONE", "完成")
    return {"skill_run_id": skill_run_id, "gap": plan["gap"], "actions": len(plan["selected_actions"]), "patches": len(actual_patches)}


async def get_skill_run_output(session: AsyncSession, skill_run_id: str) -> dict[str, Any]:
    sr = await session.execute(
        text("SELECT skill_run_id, skill_name, schema_ver, output, created_at FROM skill_run WHERE skill_run_id=:id"),
        {"id": skill_run_id},
    )
    row = sr.mappings().first()
    if not row:
        raise RuntimeError("SKILL_RUN_NOT_FOUND")
    return dict(row)


async def get_latest_skill_run(
    session: AsyncSession,
    chapter_id: str,
    skill_name: str,
) -> dict[str, Any]:
    res = await session.execute(
        text(
            """
            SELECT sr.skill_run_id, sr.skill_name, sr.schema_ver, sr.output, sr.created_at
            FROM skill_run sr
            JOIN chapter c ON c.book_id = sr.book_id
            WHERE c.chapter_id=:chapter_id
              AND sr.skill_name=:skill_name
            ORDER BY sr.created_at DESC
            LIMIT 1
            """
        ),
        {"chapter_id": chapter_id, "skill_name": skill_name},
    )
    row = res.mappings().first()
    if not row:
        raise RuntimeError("SKILL_RUN_NOT_FOUND")
    return dict(row)


async def get_outline_detail(session: AsyncSession, chapter_id: str, version: int | None) -> dict[str, Any]:
    if version is None:
        outline, _, current_version = await _load_outline_detail(session, chapter_id)
        return {"version": current_version, "content": outline}

    result = await session.execute(
        text(
            """
            SELECT version, content
            FROM outline
            WHERE chapter_id=:chapter_id AND scope='chapter' AND version=:version
            LIMIT 1
            """
        ),
        {"chapter_id": chapter_id, "version": version},
    )
    row = result.mappings().first()
    if not row:
        raise RuntimeError("OUTLINE_NOT_FOUND")
    return {"version": int(row["version"]), "content": row["content"] or {}}


def _extract_mechanic_from_node(node: dict[str, Any]) -> str | None:
    meta = (node.get("_meta") or {}) if isinstance(node, dict) else {}
    mech = meta.get("mechanic")
    if mech:
        return str(mech)
    for p in (meta.get("patches_applied") or []):
        if isinstance(p, dict):
            m = p.get("mechanic") or ((p.get("_meta") or {}).get("mechanic") if isinstance(p.get("_meta"), dict) else None)
            if m:
                return str(m)
    return None


async def get_outline_detail_diff(session: AsyncSession, chapter_id: str, from_version: int, to_version: int) -> dict[str, Any]:
    fr = await get_outline_detail(session, chapter_id, from_version)
    to = await get_outline_detail(session, chapter_id, to_version)
    from_nodes = list((fr.get("content") or {}).get("nodes") or [])
    to_nodes = list((to.get("content") or {}).get("nodes") or [])

    from_map = {str(n.get("node_id")): n for n in from_nodes if isinstance(n, dict) and n.get("node_id")}
    to_map = {str(n.get("node_id")): n for n in to_nodes if isinstance(n, dict) and n.get("node_id")}
    from_idx = {str(n.get("node_id")): i for i, n in enumerate(from_nodes) if isinstance(n, dict) and n.get("node_id")}
    to_idx = {str(n.get("node_id")): i for i, n in enumerate(to_nodes) if isinstance(n, dict) and n.get("node_id")}

    inserted_nodes: list[dict[str, Any]] = []
    removed_nodes: list[dict[str, Any]] = []
    moved_nodes: list[dict[str, Any]] = []
    summary_changed: list[dict[str, Any]] = []
    mechanics_count: dict[str, int] = {}

    for node_id, node in to_map.items():
        if node_id not in from_map:
            idx = to_idx[node_id]
            after_node_id = to_nodes[idx - 1].get("node_id") if idx > 0 and isinstance(to_nodes[idx - 1], dict) else None
            mechanic = _extract_mechanic_from_node(node)
            if mechanic:
                mechanics_count[mechanic] = mechanics_count.get(mechanic, 0) + 1
            inserted_nodes.append(
                {
                    "node_id": node_id,
                    "type": node.get("type"),
                    "after_node_id": after_node_id,
                    "mechanic": mechanic,
                }
            )
        else:
            old = from_map[node_id]
            old_summary = str(old.get("summary") or "")
            new_summary = str(node.get("summary") or "")
            if old_summary != new_summary:
                mechanic = _extract_mechanic_from_node(node) or _extract_mechanic_from_node(old)
                if mechanic:
                    mechanics_count[mechanic] = mechanics_count.get(mechanic, 0) + 1
                summary_changed.append(
                    {
                        "node_id": node_id,
                        "before": old_summary,
                        "after": new_summary,
                        "mechanic": mechanic,
                    }
                )
            if node_id in from_idx and node_id in to_idx:
                if abs(int(from_idx[node_id]) - int(to_idx[node_id])) > 1:
                    moved_nodes.append(
                        {
                            "node_id": node_id,
                            "from_index": int(from_idx[node_id]),
                            "to_index": int(to_idx[node_id]),
                        }
                    )

    for node_id, node in from_map.items():
        if node_id not in to_map:
            removed_nodes.append({"node_id": node_id, "type": node.get("type"), "mechanic": _extract_mechanic_from_node(node)})

    # Optional merge from applied_log (more precise insert anchor + summary provenance).
    used_applied_log = False
    applied_log = (((to.get("content") or {}).get("_meta") or {}).get("applied_log")) or None
    if isinstance(applied_log, dict):
        used_applied_log = True
        to_by_id = {str(n.get("node_id")): n for n in to_nodes if isinstance(n, dict) and n.get("node_id")}
        from_by_id = {str(n.get("node_id")): n for n in from_nodes if isinstance(n, dict) and n.get("node_id")}

        def _insert_if_missing(items: list[dict[str, Any]], candidate: dict[str, Any]) -> None:
            node_id = str(candidate.get("node_id") or "")
            if not node_id:
                return
            if not any(str(x.get("node_id") or "") == node_id for x in items):
                items.append(candidate)

        for entry in (applied_log.get("applied") or []):
            if str(entry.get("patch_type")) == "insert_node":
                nid = str(entry.get("inserted_node_id") or "")
                if not nid:
                    continue
                node = to_by_id.get(nid) or {}
                _insert_if_missing(
                    inserted_nodes,
                    {
                        "node_id": nid,
                        "type": node.get("type"),
                        "after_node_id": entry.get("after_node_id"),
                        "mechanic": _extract_mechanic_from_node(node),
                    },
                )
        for entry in (applied_log.get("summary_changed") or []):
            nid = str(entry.get("node_id") or "")
            if not nid:
                continue
            if any(str(x.get("node_id") or "") == nid for x in summary_changed):
                continue
            node = to_by_id.get(nid) or from_by_id.get(nid) or {}
            summary_changed.append(
                {
                    "node_id": nid,
                    "before": str(entry.get("before") or ""),
                    "after": str(entry.get("after") or ""),
                    "mechanic": _extract_mechanic_from_node(node),
                }
            )

        mechanics_count = {}
        for item in inserted_nodes:
            m = item.get("mechanic")
            if m:
                mechanics_count[str(m)] = mechanics_count.get(str(m), 0) + 1
        for item in summary_changed:
            m = item.get("mechanic")
            if m:
                mechanics_count[str(m)] = mechanics_count.get(str(m), 0) + 1

    return {
        "from_version": from_version,
        "to_version": to_version,
        "changes": {
            "inserted_nodes": inserted_nodes,
            "removed_nodes": removed_nodes,
            "moved_nodes": moved_nodes,
            "summary_changed": summary_changed,
        },
        "stats": {
            "insert_count": len(inserted_nodes),
            "remove_count": len(removed_nodes),
            "move_count": len(moved_nodes),
            "change_summary_count": len(summary_changed),
            "mechanics": mechanics_count,
        },
        "meta": {"used_applied_log": used_applied_log},
    }


async def compare_eval_runs(session: AsyncSession, chapter_id: str, before_run_id: str, after_run_id: str) -> dict[str, Any]:
    _ = chapter_id
    before = await _load_eval_output(session, before_run_id)
    after = await _load_eval_output(session, after_run_id)
    bs = _extract_scores_from_eval_output(before)
    af = _extract_scores_from_eval_output(after)
    delta = _compute_delta(bs, af)
    return {
        "before": {"scores": bs, "curve": ((before.get("result") or {}).get("tension_curve") or [])},
        "after": {"scores": af, "curve": ((after.get("result") or {}).get("tension_curve") or [])},
        "delta": delta,
    }


async def list_outline_versions(session: AsyncSession, chapter_id: str) -> list[dict[str, Any]]:
    result = await session.execute(
        text(
            """
            SELECT outline_id, version, title, created_at
            FROM outline
            WHERE chapter_id=:chapter_id AND scope='chapter'
            ORDER BY version DESC
            """
        ),
        {"chapter_id": chapter_id},
    )
    return [dict(r) for r in result.mappings().all()]


async def delete_outline_detail(session: AsyncSession, chapter_id: str, version: int | None) -> dict[str, Any]:
    chapter_row = await session.execute(
        text("SELECT chapter_id::text AS chapter_id FROM chapter WHERE chapter_id=CAST(:chapter_id AS uuid) LIMIT 1"),
        {"chapter_id": chapter_id},
    )
    if not chapter_row.mappings().first():
        raise RuntimeError("CHAPTER_NOT_FOUND")

    if version is None:
        target = await session.execute(
            text(
                """
                SELECT outline_id::text AS outline_id, version
                FROM outline
                WHERE chapter_id=CAST(:chapter_id AS uuid) AND scope='chapter'
                ORDER BY version DESC
                LIMIT 1
                """
            ),
            {"chapter_id": chapter_id},
        )
    else:
        target = await session.execute(
            text(
                """
                SELECT outline_id::text AS outline_id, version
                FROM outline
                WHERE chapter_id=CAST(:chapter_id AS uuid) AND scope='chapter' AND version=:version
                LIMIT 1
                """
            ),
            {"chapter_id": chapter_id, "version": int(version)},
        )
    target_row = target.mappings().first()
    if not target_row:
        raise RuntimeError("OUTLINE_NOT_FOUND")

    await session.execute(
        text("DELETE FROM outline WHERE outline_id=CAST(:outline_id AS uuid)"),
        {"outline_id": str(target_row["outline_id"])},
    )

    remain = await session.execute(
        text(
            """
            SELECT COUNT(*)::int AS total, COALESCE(MAX(version), 0)::int AS latest_version
            FROM outline
            WHERE chapter_id=CAST(:chapter_id AS uuid) AND scope='chapter'
            """
        ),
        {"chapter_id": chapter_id},
    )
    remain_row = remain.mappings().first() or {}
    await session.commit()
    return {
        "chapter_id": chapter_id,
        "deleted_version": int(target_row["version"]),
        "remaining_total": int(remain_row.get("total") or 0),
        "remaining_latest_version": int(remain_row.get("latest_version") or 0),
    }


async def save_outline_detail(session: AsyncSession, chapter_id: str, outline: dict[str, Any], note: str | None = None) -> dict[str, Any]:
    _, chapter_row, current_version = await _load_outline_detail(session, chapter_id)
    next_version = current_version + 1
    title = (outline.get("chapter_title") or f"Chapter {chapter_row['order']} Detail")
    if note:
        title = f"{title} | {note}"

    inserted = await session.execute(
        text(
            """
            INSERT INTO outline(book_id, chapter_id, scope, title, version, content)
            VALUES (:book_id, :chapter_id, 'chapter', :title, :version, CAST(:content AS jsonb))
            RETURNING outline_id, version, created_at
            """
        ),
        {
            "book_id": str(chapter_row["book_id"]),
            "chapter_id": chapter_id,
            "title": title,
            "version": next_version,
            "content": json.dumps(outline),
        },
    )
    row = inserted.mappings().one()
    await session.commit()
    return dict(row)


async def apply_tension_patches(
    session: AsyncSession,
    chapter_id: str,
    skill_run_id: str,
    apply_target: str,
    selected_patch_ids: list[str] | None = None,
) -> dict[str, Any]:
    if apply_target != "outline_detail":
        raise RuntimeError("UNSUPPORTED_APPLY_TARGET")

    sr = await session.execute(
        text(
            """
            SELECT output FROM skill_run
            WHERE skill_run_id=:skill_run_id
            """
        ),
        {"skill_run_id": skill_run_id},
    )
    row = sr.mappings().first()
    if not row:
        raise RuntimeError("SKILL_RUN_NOT_FOUND")
    output = row["output"] or {}
    patches = (((output.get("patches") or {}).get("result") or {}).get("patches")) or (((output.get("result") or {}).get("patches")) or [])

    if selected_patch_ids:
        selected = set(selected_patch_ids)
        patches = [p for p in patches if str(p.get("patch_id") or "") in selected]

    outline_detail, chapter_row, current_version = await _load_outline_detail(session, chapter_id)
    patched_outline, applied_log = apply_patches_to_outline(outline_detail, patches)
    patch_meta = (patched_outline.get("_meta") or {}).get("patch_apply", {})
    applied_count = int(patch_meta.get("applied", 0))
    failed_count = int(patch_meta.get("failed", 0))

    patched_meta = patched_outline.get("_meta", {}) or {}
    patched_meta["applied_plan_run_id"] = str(skill_run_id)
    patched_meta["applied_patch_ids"] = [str(p.get("patch_id") or "") for p in patches if p.get("patch_id")]
    patched_meta["derived_from_version"] = int(current_version)
    patched_meta["applied_log"] = applied_log
    patched_outline["_meta"] = patched_meta

    await session.execute(
        text(
            """
            INSERT INTO outline(book_id, chapter_id, scope, title, version, content)
            VALUES (:book_id, :chapter_id, 'chapter', :title, :version, CAST(:content AS jsonb))
            """
        ),
        {
            "book_id": str(chapter_row["book_id"]),
            "chapter_id": chapter_id,
            "title": (
                f"Chapter {chapter_row['order']} Detail | "
                f"apply patches plan_run={skill_run_id} patches={len(patches)}"
            ),
            "version": current_version + 1,
            "content": json.dumps(patched_outline),
        },
    )
    await session.commit()
    return {
        "ok": True,
        "applied_patches": applied_count,
        "failed_patches": failed_count,
        "outline_version": current_version + 1,
        "applied_log": applied_log,
    }


def _extract_patches_from_plan_output(output: dict[str, Any]) -> list[dict[str, Any]]:
    return (
        (((output.get("patches") or {}).get("result") or {}).get("patches"))
        or (((output.get("result") or {}).get("patches")) or [])
        or []
    )


def _extract_scores_from_eval_output(output: dict[str, Any]) -> dict[str, float]:
    return dict((((output.get("result") or {}).get("scores")) or {}))


def _compute_delta(before_scores: dict[str, float], after_scores: dict[str, float]) -> dict[str, float]:
    keys = ["overall", "conflict_strength", "stakes", "cost", "pace", "reversal", "hook", "payoff"]
    out: dict[str, float] = {}
    for k in keys:
        out[k] = round(float(after_scores.get(k, 0.0)) - float(before_scores.get(k, 0.0)), 4)
    return out


def _mechanics_from_patches(plan_output: dict[str, Any], selected_patch_ids: list[str]) -> list[str]:
    selected = set(selected_patch_ids or [])
    patches = _extract_patches_from_plan_output(plan_output)
    values: list[str] = []
    for p in patches:
        if selected and str(p.get("patch_id") or "") not in selected:
            continue
        mech = None
        if p.get("patch_type") == "insert_node":
            mech = (((p.get("insert") or {}).get("node") or {}).get("_meta") or {}).get("mechanic")
        if not mech:
            mech = (p.get("_meta") or {}).get("mechanic")
        if mech:
            values.append(str(mech))
    seen: set[str] = set()
    out: list[str] = []
    for m in values:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


async def _create_repair_txn(
    session: AsyncSession,
    *,
    repair_txn_id: str,
    book_id: str,
    chapter_id: str,
    plan_skill_run_id: str,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO repair_txn(repair_txn_id, book_id, chapter_id, plan_skill_run_id)
            VALUES (:repair_txn_id, :book_id, :chapter_id, :plan_skill_run_id)
            ON CONFLICT (repair_txn_id) DO NOTHING
            """
        ),
        {
            "repair_txn_id": repair_txn_id,
            "book_id": book_id,
            "chapter_id": chapter_id,
            "plan_skill_run_id": plan_skill_run_id,
        },
    )


async def _update_repair_txn(
    session: AsyncSession,
    *,
    repair_txn_id: str,
    before_eval_run_id: str | None = None,
    after_eval_run_id: str | None = None,
    applied_outline_version: int | None = None,
) -> None:
    sets: list[str] = []
    params: dict[str, Any] = {"repair_txn_id": repair_txn_id}
    if before_eval_run_id is not None:
        sets.append("before_eval_run_id=:before_eval_run_id")
        params["before_eval_run_id"] = before_eval_run_id
    if after_eval_run_id is not None:
        sets.append("after_eval_run_id=:after_eval_run_id")
        params["after_eval_run_id"] = after_eval_run_id
    if applied_outline_version is not None:
        sets.append("applied_outline_version=:applied_outline_version")
        params["applied_outline_version"] = applied_outline_version
    if not sets:
        return
    await session.execute(
        text(f"UPDATE repair_txn SET {', '.join(sets)} WHERE repair_txn_id=:repair_txn_id"),
        params,
    )


async def _find_recent_eval_run_id(session: AsyncSession, chapter_id: str, within_minutes: int = 15) -> str | None:
    try:
        res = await session.execute(
            text(
                """
                SELECT eval_skill_run_id
                FROM chapter_tension_metrics
                WHERE chapter_id=:chapter_id
                  AND created_at > now() - make_interval(mins => :mins)
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"chapter_id": chapter_id, "mins": int(within_minutes)},
        )
    except Exception:
        await session.rollback()
        return None
    value = res.scalar()
    return str(value) if value else None


async def _eval_outline_and_save(
    session: AsyncSession,
    *,
    book_id: str,
    chapter_id: str,
    chapter_no: int,
    outline_detail: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    nodes = outline_detail.get("nodes", []) if isinstance(outline_detail, dict) else []
    text_for_eval = " ".join([(n.get("summary") or "")[:160] for n in nodes if isinstance(n, dict)])
    score_data = evaluate_tension_score_v1(text_for_eval, nodes)
    saved = await session.execute(
        text(
            """
            INSERT INTO skill_run(book_id, skill_name, schema_ver, output)
            VALUES (:book_id, 'EVAL_CONFLICT_TENSION_V1', 1, CAST(:output AS jsonb))
            RETURNING skill_run_id
            """
        ),
        {"book_id": book_id, "output": json.dumps(score_data)},
    )
    skill_run_id = str(saved.scalar_one())
    result_block = score_data.get("result") or {}
    await insert_chapter_tension_metric(
        session,
        book_id=book_id,
        chapter_id=chapter_id,
        chapter_no=chapter_no,
        chapter_version_id=None,
        eval_skill_run_id=skill_run_id,
        scores=dict(result_block.get("scores") or {}),
        tension_curve=[float(x) for x in (result_block.get("tension_curve") or [])],
        issues_count=len(result_block.get("issues") or []),
        mechanics_used=sorted(list(already_mechanics(outline_detail))),
    )
    return skill_run_id, score_data


async def _load_eval_output(session: AsyncSession, eval_run_id: str) -> dict[str, Any]:
    res = await session.execute(
        text("SELECT output FROM skill_run WHERE skill_run_id=:id LIMIT 1"),
        {"id": eval_run_id},
    )
    row = res.mappings().first()
    if not row:
        raise RuntimeError("EVAL_SKILL_RUN_NOT_FOUND")
    return dict(row["output"] or {})


async def _infer_arc_shape(session: AsyncSession, book_id: str, arc_id: str | None) -> str:
    if not arc_id:
        return "unknown"
    res = await session.execute(
        text(
            """
            SELECT output
            FROM skill_run
            WHERE book_id=:book_id AND skill_name='BOOK_TENSION_ANALYSIS_V1'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"book_id": book_id},
    )
    row = res.mappings().first()
    if not row:
        return "unknown"
    output = dict(row["output"] or {})
    for item in (((output.get("result") or {}).get("arc_targets")) or []):
        if str(item.get("arc_id") or "") == str(arc_id):
            return str(item.get("deviation_type") or "unknown")
    return "unknown"


async def _infer_phase(session: AsyncSession, book_id: str, chapter_no: int, arc_id: str | None) -> str:
    if arc_id:
        res = await session.execute(
            text('SELECT "order" FROM chapter WHERE book_id=:book_id AND arc_id=:arc_id ORDER BY "order" ASC'),
            {"book_id": book_id, "arc_id": arc_id},
        )
    else:
        res = await session.execute(
            text('SELECT "order" FROM chapter WHERE book_id=:book_id ORDER BY "order" ASC'),
            {"book_id": book_id},
        )
    orders = [int(r[0]) for r in res.all()]
    if not orders:
        return "mid"
    start = orders[0]
    end = orders[-1]
    if end <= start:
        return "mid"
    p = (chapter_no - start) / max(1, end - start)
    if p < 0.33:
        return "pre"
    if p > 0.66:
        return "late"
    return "mid"


async def run_apply_and_measure_job(session: AsyncSession, payload: dict[str, Any], on_progress, on_log) -> dict[str, Any]:
    chapter_id = str(payload["chapter_id"])
    book_id = str(payload["book_id"])
    plan_skill_run_id = str(payload["plan_skill_run_id"])
    selected_patch_ids = [str(x) for x in (payload.get("selected_patch_ids") or [])]
    auto_eval = bool(payload.get("auto_eval", True))
    repair_txn_id = str(payload.get("repair_txn_id") or uuid4())

    await on_progress(8, "ENSURE_BEFORE_EVAL", "创建修复事务")
    outline_current, chapter_row, current_version = await _load_outline_detail(session, chapter_id)
    await _create_repair_txn(
        session,
        repair_txn_id=repair_txn_id,
        book_id=book_id,
        chapter_id=chapter_id,
        plan_skill_run_id=plan_skill_run_id,
    )
    await session.commit()

    before_eval_id = await _find_recent_eval_run_id(session, chapter_id, within_minutes=15)
    before_eval_output: dict[str, Any] | None = None
    if not before_eval_id and auto_eval:
        await on_log("INFO", "ENSURE_BEFORE_EVAL", "未找到最近评估，自动执行 before eval")
        before_eval_id, before_eval_output = await _eval_outline_and_save(
            session,
            book_id=book_id,
            chapter_id=chapter_id,
            chapter_no=int(chapter_row["order"]),
            outline_detail=outline_current,
        )
        await session.commit()
    if before_eval_id:
        await _update_repair_txn(session, repair_txn_id=repair_txn_id, before_eval_run_id=before_eval_id)
        await session.commit()
    else:
        await on_log("WARN", "ENSURE_BEFORE_EVAL", "无 before eval 基线，将跳过 sample 写入")

    await on_progress(35, "APPLY_PATCHES", "应用补丁并生成新版本")
    sr = await session.execute(
        text("SELECT output FROM skill_run WHERE skill_run_id=:id LIMIT 1"),
        {"id": plan_skill_run_id},
    )
    sr_row = sr.mappings().first()
    if not sr_row:
        raise RuntimeError("PLAN_SKILL_RUN_NOT_FOUND")
    plan_output = dict(sr_row["output"] or {})
    patches = _extract_patches_from_plan_output(plan_output)
    if selected_patch_ids:
        selected = set(selected_patch_ids)
        patches = [p for p in patches if str(p.get("patch_id") or "") in selected]

    patched_outline, applied_log = apply_patches_to_outline(outline_current, patches)
    patch_meta = (patched_outline.get("_meta") or {}).get("patch_apply", {})
    applied_count = int(patch_meta.get("applied", 0))
    failed_count = int(patch_meta.get("failed", 0))
    await on_log("INFO", "APPLY_PATCHES", f"apply patches ok applied={applied_count} skipped={failed_count}")
    patch_ids = [str(p.get("patch_id") or "") for p in patches if p.get("patch_id")]
    patched_meta = patched_outline.get("_meta", {}) or {}
    patched_meta["derived_from_version"] = int(current_version)
    patched_meta["applied_plan_run_id"] = plan_skill_run_id
    patched_meta["applied_patch_ids"] = patch_ids
    patched_meta["applied_log"] = applied_log
    patched_outline["_meta"] = patched_meta

    new_version = current_version + 1
    await session.execute(
        text(
            """
            INSERT INTO outline(book_id, chapter_id, scope, title, version, content)
            VALUES (:book_id, :chapter_id, 'chapter', :title, :version, CAST(:content AS jsonb))
            """
        ),
        {
            "book_id": str(chapter_row["book_id"]),
            "chapter_id": chapter_id,
            "title": (
                f"Chapter {chapter_row['order']} Detail | "
                f"apply_and_measure:{repair_txn_id} patches={len(patch_ids)} plan_run={plan_skill_run_id}"
            ),
            "version": new_version,
            "content": json.dumps(patched_outline),
        },
    )
    await _update_repair_txn(session, repair_txn_id=repair_txn_id, applied_outline_version=new_version)
    await session.commit()

    await on_progress(60, "RUN_AFTER_EVAL", "执行 after eval")
    after_eval_id: str | None = None
    after_eval_output: dict[str, Any] | None = None
    if auto_eval:
        after_eval_id, after_eval_output = await _eval_outline_and_save(
            session,
            book_id=book_id,
            chapter_id=chapter_id,
            chapter_no=int(chapter_row["order"]),
            outline_detail=patched_outline,
        )
        await _update_repair_txn(session, repair_txn_id=repair_txn_id, after_eval_run_id=after_eval_id)
        await session.commit()

    await on_progress(82, "COMPUTE_DELTA", "计算前后评估差值")
    delta: dict[str, float] | None = None
    sample_written = False
    warnings: list[str] = []
    if before_eval_id and after_eval_id:
        if before_eval_output is None:
            before_eval_output = await _load_eval_output(session, before_eval_id)
        if after_eval_output is None:
            after_eval_output = await _load_eval_output(session, after_eval_id)
        before_scores = _extract_scores_from_eval_output(before_eval_output)
        after_scores = _extract_scores_from_eval_output(after_eval_output)
        delta = _compute_delta(before_scores, after_scores)
        mechanics = _mechanics_from_patches(plan_output, selected_patch_ids)
        arc_shape = await _infer_arc_shape(session, book_id, chapter_row.get("arc_id"))
        phase = await _infer_phase(session, book_id, int(chapter_row["order"]), chapter_row.get("arc_id"))
        context = {
            "arc_shape": arc_shape,
            "phase": phase,
            "arc_id": chapter_row.get("arc_id"),
            "chapter_no": int(chapter_row["order"]),
        }
        await on_progress(92, "SAVE_SAMPLE", "写入修复效果样本")
        await create_repair_effect_sample(
            session,
            book_id=book_id,
            arc_id=chapter_row.get("arc_id"),
            chapter_no=int(chapter_row["order"]),
            before_eval_run_id=before_eval_id,
            after_eval_run_id=after_eval_id,
            applied_mechanics=mechanics,
            delta=delta,
            context=context,
        )
        sample_written = True
    else:
        warnings.append("SKIP_SAMPLE_NO_BASELINE_OR_AFTER_EVAL")
        if auto_eval and not after_eval_id:
            warnings.append("AFTER_EVAL_FAILED_OR_SKIPPED")

    await on_progress(100, "DONE", "完成")
    await on_log("INFO", "DONE", f"apply_and_measure 完成，v{new_version}")
    return {
        "repair_txn_id": repair_txn_id,
        "new_outline_version": new_version,
        "applied_patches": applied_count,
        "failed_patches": failed_count,
        "applied_log": applied_log,
        "before_eval_run_id": before_eval_id,
        "after_eval_run_id": after_eval_id,
        "delta": delta,
        "sample_written": sample_written,
        "warnings": warnings,
    }

