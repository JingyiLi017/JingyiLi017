from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .patch_utils import new_node_id

PatchList = list[dict[str, Any]]


@dataclass
class Mechanic:
    name: str
    supported_node_types: list[str]
    apply: Callable[[dict[str, Any]], PatchList]


def find_first_node(nodes: list[dict[str, Any]], types: list[str]) -> str | None:
    for node in nodes:
        if node.get("type") in types and node.get("node_id"):
            return str(node["node_id"])
    return None


def find_last_node(nodes: list[dict[str, Any]], types: list[str]) -> str | None:
    for node in reversed(nodes):
        if node.get("type") in types and node.get("node_id"):
            return str(node["node_id"])
    return None


def find_node(nodes: list[dict[str, Any]], node_id: str) -> dict[str, Any] | None:
    for node in nodes:
        if node.get("node_id") == node_id:
            return node
    return None


def _micro_node(
    node_type: str,
    summary: str,
    conflict: dict[str, float],
    mechanic: str,
    prefix: str,
) -> dict[str, Any]:
    node = {
        "node_id": new_node_id(prefix),
        "type": node_type,
        "summary": summary,
        "beats": [],
        "characters": [],
        "world_facts": [],
        "plot_hooks": [],
        "conflict": conflict,
        "constraints": {"max_words": 120},
        "_meta": {"needs_review": False, "mechanic": mechanic},
    }
    return node


def insert_node_patch(after: str, node: dict[str, Any], impact: dict[str, float] | None = None) -> dict[str, Any]:
    return {
        "patch_type": "insert_node",
        "where": {"after_node_id": after},
        "insert": {"node": node},
        "impact_estimate": impact or {},
    }


def change_summary_patch(node_id: str, before: str, after: str, impact: dict[str, float] | None = None) -> dict[str, Any]:
    return {
        "patch_type": "change_summary",
        "where": {"node_id": node_id},
        "change": {"before": before[:120], "after": after},
        "impact_estimate": impact or {},
    }


def _ensure_anchor(outline_detail: dict[str, Any], selected_node_id: str | None, preferred_types: list[str]) -> str:
    nodes = outline_detail.get("nodes", [])
    if selected_node_id and find_node(nodes, selected_node_id):
        return selected_node_id
    return find_first_node(nodes, preferred_types) or (str(nodes[0].get("node_id")) if nodes else "N1")


def apply_face_slap(ctx: dict[str, Any]) -> PatchList:
    outline = ctx["outline_detail"]
    nodes = outline.get("nodes", [])
    anchor = _ensure_anchor(outline, ctx.get("selected_node_id"), ["turning_point", "gain"])
    pre = _micro_node(
        "micro_obstacle",
        "打脸前置：对手当众羞辱或误判主角，建立公开评判标准。",
        {"stake_level": 0.7, "opposition_strength": 0.65},
        "face_slap",
        "face_pre",
    )
    hit = _micro_node(
        "micro_turning_point",
        "公开反击：主角用规则或证据完成逆转，并让对手承受后果。",
        {"reversal_power": 0.82, "stake_level": 0.8},
        "face_slap",
        "face_hit",
    )
    _ = nodes
    return [
        insert_node_patch(anchor, pre, {"conflict_strength": 0.08}),
        insert_node_patch(pre["node_id"], hit, {"reversal": 0.1}),
    ]


def apply_upgrade(ctx: dict[str, Any]) -> PatchList:
    outline = ctx["outline_detail"]
    nodes = outline.get("nodes", [])
    anchor = _ensure_anchor(outline, ctx.get("selected_node_id"), ["gain", "turning_point"])
    node = find_node(nodes, anchor) or {}
    up = _micro_node(
        "micro_upgrade",
        "升级触发：主角获得阶段性突破，但能力边界被重新定义。",
        {"stake_level": 0.6, "goal_clarity": 0.6},
        "upgrade",
        "up",
    )
    cost = _micro_node(
        "micro_cost",
        "升级代价：突破伴随资源或身体负担，影响后续选择。",
        {"cost_level": 0.82, "stake_level": 0.7},
        "upgrade",
        "upg",
    )
    return [
        insert_node_patch(anchor, up, {"payoff": 0.06}),
        insert_node_patch(up["node_id"], cost, {"cost": 0.12}),
        change_summary_patch(anchor, node.get("summary") or "", "明确升级收益与新限制，保证下一章仍有压力。", {"payoff": 0.08}),
    ]


def apply_reversal(ctx: dict[str, Any]) -> PatchList:
    outline = ctx["outline_detail"]
    nodes = outline.get("nodes", [])
    anchor = _ensure_anchor(outline, ctx.get("selected_node_id"), ["turning_point", "cliffhanger"])
    node = find_node(nodes, anchor) or {}
    gap = _micro_node(
        "micro_info_gap",
        "信息差铺垫：提前埋下误导线索，为后续反转提供依据。",
        {"info_gap": 0.86, "reversal_power": 0.7},
        "reversal",
        "rev",
    )
    early_anchor = find_first_node(nodes, ["hook", "goal"]) or anchor
    return [
        insert_node_patch(early_anchor, gap, {"reversal": 0.08}),
        change_summary_patch(anchor, node.get("summary") or "", "转折依据信息差完成，不依赖新设定突降。", {"reversal": 0.1}),
    ]


def apply_timer(ctx: dict[str, Any]) -> PatchList:
    outline = ctx["outline_detail"]
    anchor = _ensure_anchor(outline, ctx.get("selected_node_id"), ["goal", "hook"])
    timer = _micro_node(
        "micro_timer",
        "倒计时启动：明确期限与失败后果，逼迫角色立刻行动。",
        {"time_pressure": 0.88, "stake_level": 0.72},
        "timer",
        "timer",
    )
    return [insert_node_patch(anchor, timer, {"pace": 0.1})]


def apply_raise_stakes(ctx: dict[str, Any]) -> PatchList:
    outline = ctx["outline_detail"]
    nodes = outline.get("nodes", [])
    anchor = _ensure_anchor(outline, ctx.get("selected_node_id"), ["obstacle", "goal", "escalation"])
    node = find_node(nodes, anchor) or {}
    stake = _micro_node(
        "micro_stake_raise",
        "抬高赌注：把风险从可承受损失提升到身份/关系/生存层面。",
        {"stake_level": 0.9, "opposition_strength": 0.6},
        "raise_stakes",
        "stake",
    )
    return [
        insert_node_patch(anchor, stake, {"stakes": 0.12}),
        change_summary_patch(anchor, node.get("summary") or "", "将赌注升级为不可承受损失，强制角色冒险。", {"stakes": 0.1}),
    ]


def apply_cost_hardening(ctx: dict[str, Any]) -> PatchList:
    outline = ctx["outline_detail"]
    nodes = outline.get("nodes", [])
    anchor = _ensure_anchor(outline, ctx.get("selected_node_id"), ["cost", "turning_point"])
    micro = _micro_node(
        "micro_cost",
        "硬化代价：引入不可逆损失或长期负担，直接改变后续决策。",
        {"cost_level": 0.9, "stake_level": 0.72},
        "cost_hardening",
        "cost",
    )
    _ = nodes
    return [insert_node_patch(anchor, micro, {"cost": 0.15})]


def apply_rescue(ctx: dict[str, Any]) -> PatchList:
    outline = ctx["outline_detail"]
    anchor = _ensure_anchor(outline, ctx.get("selected_node_id"), ["escalation", "turning_point"])
    rescue = _micro_node(
        "micro_rescue",
        "救场介入：外援或反制出现，但附带新的限制与债务。",
        {"opposition_strength": 0.65, "stake_level": 0.75},
        "rescue",
        "rescue",
    )
    cost = _micro_node(
        "micro_cost",
        "救场后果：本次脱困以长期代价换取，埋下新风险。",
        {"cost_level": 0.75, "stake_level": 0.65},
        "rescue",
        "rescue_cost",
    )
    return [
        insert_node_patch(anchor, rescue, {"conflict_strength": 0.08}),
        insert_node_patch(rescue["node_id"], cost, {"cost": 0.06}),
    ]


def apply_betrayal(ctx: dict[str, Any]) -> PatchList:
    outline = ctx["outline_detail"]
    anchor = _ensure_anchor(outline, ctx.get("selected_node_id"), ["cliffhanger", "turning_point"])
    betray = _micro_node(
        "micro_betrayal",
        "背刺触发：盟友立场转向，导致主角即时受损。",
        {"stake_level": 0.82, "cost_level": 0.65},
        "betrayal",
        "betray",
    )
    reveal = _micro_node(
        "micro_revelation",
        "动机揭示：给出利益/恐惧/立场原因，确保背叛具备因果。",
        {"info_gap": 0.7, "reversal_power": 0.62},
        "betrayal",
        "betray",
    )
    return [
        insert_node_patch(anchor, betray, {"conflict_strength": 0.1}),
        insert_node_patch(betray["node_id"], reveal, {"reversal": 0.07}),
    ]


def apply_strengthen_obstacle(ctx: dict[str, Any]) -> PatchList:
    outline = ctx["outline_detail"]
    nodes = outline.get("nodes", [])
    anchor = _ensure_anchor(outline, ctx.get("selected_node_id"), ["obstacle", "escalation"])
    node = find_node(nodes, anchor) or {}
    return [
        change_summary_patch(
            anchor,
            node.get("summary") or "",
            "阻碍升级为不可接受损失风险，迫使主角改变策略并承担代价。",
            {"conflict_strength": 0.12, "pace": 0.04},
        )
    ]


MECHANICS: dict[str, Mechanic] = {
    "face_slap": Mechanic("face_slap", ["turning_point", "gain"], apply_face_slap),
    "upgrade": Mechanic("upgrade", ["gain"], apply_upgrade),
    "reversal": Mechanic("reversal", ["turning_point", "hook", "cliffhanger"], apply_reversal),
    "timer": Mechanic("timer", ["goal", "obstacle"], apply_timer),
    "raise_stakes": Mechanic("raise_stakes", ["goal", "obstacle", "escalation"], apply_raise_stakes),
    "cost_hardening": Mechanic("cost_hardening", ["cost", "turning_point"], apply_cost_hardening),
    "rescue": Mechanic("rescue", ["escalation", "turning_point"], apply_rescue),
    "betrayal": Mechanic("betrayal", ["turning_point", "cliffhanger"], apply_betrayal),
    "strengthen_obstacle": Mechanic("strengthen_obstacle", ["obstacle", "escalation"], apply_strengthen_obstacle),
}


ACTION_MECHANIC_MAP: dict[str, str] = {
    "inject_face_slap": "face_slap",
    "inject_upgrade": "upgrade",
    "add_timer": "timer",
    "add_info_gap": "reversal",
    "add_micro_cost": "cost_hardening",
    "add_micro_obstacle": "strengthen_obstacle",
    "upgrade_obstacle": "strengthen_obstacle",
    "strengthen_obstacle": "strengthen_obstacle",
    "raise_stakes": "raise_stakes",
}


def mechanics_preview(
    outline_detail: dict[str, Any],
    mechanic_name: str,
    selected_node_id: str | None = None,
    strength: float = 0.7,
) -> dict[str, Any]:
    mechanic = MECHANICS.get(mechanic_name)
    if not mechanic:
        raise ValueError("MECHANIC_NOT_FOUND")
    ctx = {"outline_detail": outline_detail, "selected_node_id": selected_node_id, "strength": strength}
    patches = mechanic.apply(ctx)
    return {"patches": patches, "notes": ["将插入 1-3 个 micro 节点或改写 summary", "不改变主线", "不改事实账本"]}
