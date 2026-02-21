from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any

ALLOWED_INSERT_NODE_TYPES = {
    "micro_obstacle",
    "micro_cost",
    "micro_turning_point",
    "micro_timer",
    "micro_info_gap",
    "micro_stake_raise",
    "micro_rescue",
    "micro_betrayal",
    "micro_revelation",
    "micro_chase",
    "micro_gamble",
    "micro_upgrade",
    "hook",
    "goal",
    "obstacle",
    "escalation",
    "turning_point",
    "cost",
    "gain",
    "cliffhanger",
}


def _sha1_short(value: str) -> str:
    return hashlib.sha1((value or "").encode("utf-8")).hexdigest()[:6]


def clamp_conflict(conflict: dict[str, Any]) -> dict[str, Any]:
    out = dict(conflict or {})
    keys = [
        "goal_clarity",
        "opposition_strength",
        "stake_level",
        "cost_level",
        "time_pressure",
        "info_gap",
        "reversal_power",
    ]
    for key in keys:
        if key in out and out[key] is not None:
            value = float(out[key])
            if value < 0:
                value = 0.0
            if value > 1:
                value = 1.0
            out[key] = value
    return out


def find_node_index(nodes: list[dict[str, Any]], node_id: str) -> int:
    for idx, node in enumerate(nodes):
        if node.get("node_id") == node_id:
            return idx
    return -1


def _next_micro_node_id(nodes: list[dict[str, Any]]) -> str:
    max_id = 0
    for node in nodes:
        node_id = str(node.get("node_id", ""))
        if node_id.startswith("X"):
            suffix = node_id[1:]
            if suffix.isdigit():
                max_id = max(max_id, int(suffix))
    return f"X{max_id + 1}"


def _build_node_index(nodes: list[dict[str, Any]]) -> dict[str, int]:
    return {str(node.get("node_id")): i for i, node in enumerate(nodes) if isinstance(node, dict) and node.get("node_id")}


def _ensure_unique_node_id(node_id: str, existing: set[str], patch_id: str) -> tuple[str, str | None]:
    if node_id not in existing:
        return node_id, None
    suffix = _sha1_short(patch_id or node_id)
    candidate = f"{node_id}__{suffix}"
    idx = 0
    while candidate in existing:
        idx += 1
        candidate = f"{node_id}__{suffix}_{idx}"
    return candidate, candidate


def apply_patch_to_outline_detail(outline: dict[str, Any], patch: dict[str, Any]) -> tuple[dict[str, Any], bool, str]:
    out = deepcopy(outline)
    nodes = out.get("nodes", [])
    where = patch.get("where", {}) or {}
    patch_type = patch.get("patch_type")
    if patch_type in {
        "strengthen_obstacle",
        "raise_stakes",
        "add_cost",
        "add_timer",
        "add_info_gap",
        "upgrade_face_slap",
        "sharpen_hook",
        "inject_upgrade",
    }:
        patch_type = "change_summary"
    change = patch.get("change", {}) or {}
    impact = patch.get("impact_estimate", {}) or {}

    if patch_type == "insert_node":
        after_node_id = where.get("after_node_id")
        if not after_node_id:
            return out, False, "missing where.after_node_id"
        idx = find_node_index(nodes, after_node_id)
        if idx < 0:
            return out, False, f"after_node_id not found: {after_node_id}"
        insert_block = patch.get("insert", {}) or {}
        new_node = insert_block.get("node")
        if not isinstance(new_node, dict):
            return out, False, "missing insert.node"
        node_type = str(new_node.get("type") or "")
        if node_type not in ALLOWED_INSERT_NODE_TYPES:
            return out, False, f"invalid insert node type: {node_type}"
        summary = str(new_node.get("summary") or "")
        if len(summary) > 300:
            return out, False, "summary too long (>300)"
        if summary.count('"') > 6 or summary.count("“") > 6 or summary.count("”") > 6:
            return out, False, "summary likely contains excessive quoted text"

        # Micro node hard guards
        if node_type.startswith("micro_"):
            meta = new_node.get("_meta", {}) or {}
            if not isinstance(meta, dict) or not meta.get("mechanic"):
                return out, False, "micro node missing _meta.mechanic"
            constraints = new_node.get("constraints", {}) or {}
            max_words = constraints.get("max_words")
            if max_words is None or int(max_words) > 120:
                return out, False, "micro node constraints.max_words must exist and <=120"
            conflict = new_node.get("conflict", {}) or {}
            if not isinstance(conflict, dict):
                return out, False, "micro node conflict must be object"
            non_zero_dims = 0
            for value in conflict.values():
                try:
                    if float(value) > 0:
                        non_zero_dims += 1
                except Exception:
                    continue
            if non_zero_dims < 2:
                return out, False, "micro node conflict must contain at least 2 non-zero dimensions"
        if not new_node.get("node_id"):
            new_node["node_id"] = _next_micro_node_id(nodes)
        new_node["conflict"] = clamp_conflict(new_node.get("conflict", {}) or {})
        meta = new_node.get("_meta", {}) or {}
        meta.setdefault("patches_applied", []).append({"patch_type": patch_type, "where": where, "impact_estimate": impact})
        new_node["_meta"] = meta
        nodes = nodes[: idx + 1] + [new_node] + nodes[idx + 1 :]
        out["nodes"] = nodes
        return out, True, "inserted"

    if patch_type != "change_summary":
        return out, False, f"unsupported patch_type: {patch.get('patch_type')}"

    node_id = where.get("node_id")
    if not node_id:
        return out, False, "missing where.node_id"

    idx = find_node_index(nodes, node_id)
    if idx < 0:
        return out, False, f"node_id not found: {node_id}"

    node = nodes[idx]
    if "after" in change and isinstance(change["after"], str):
        node["summary"] = change["after"]

    node["conflict"] = clamp_conflict(node.get("conflict", {}) or {})

    meta = node.get("_meta", {}) or {}
    meta.setdefault("patches_applied", []).append(
        {
            "patch_type": patch_type,
            "where": where,
            "impact_estimate": impact,
        }
    )
    node["_meta"] = meta
    nodes[idx] = node
    out["nodes"] = nodes
    return out, True, "applied"


def apply_patches_to_outline(outline: dict[str, Any], patches: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    new_outline = deepcopy(outline)
    nodes = new_outline.get("nodes")
    if nodes is None and isinstance(new_outline.get("content"), dict):
        nodes = new_outline["content"].get("nodes")
    if nodes is None:
        raise ValueError("outline has no nodes")
    if not isinstance(nodes, list):
        raise ValueError("nodes must be list")

    # Ensure writes go to the actual stored path.
    if "content" in new_outline and isinstance(new_outline["content"], dict) and isinstance(new_outline["content"].get("nodes"), list):
        target_nodes = new_outline["content"]["nodes"]
    else:
        target_nodes = new_outline["nodes"]

    applied_log: dict[str, Any] = {
        "applied": [],
        "skipped": [],
        "renamed_nodes": [],
        "summary_changed": [],
    }
    existing_ids = {str(n.get("node_id")) for n in target_nodes if isinstance(n, dict) and n.get("node_id")}
    node_idx = _build_node_index(target_nodes)

    for patch in patches:
        patch_id = str(patch.get("patch_id") or "")
        patch_type = str(patch.get("patch_type") or "")
        if patch_type == "insert_node":
            where = patch.get("where") or {}
            after_id = str(where.get("after_node_id") or "")
            if not after_id or after_id not in node_idx:
                applied_log["skipped"].append(
                    {
                        "patch_id": patch_id,
                        "reason": "AFTER_NODE_NOT_FOUND",
                        "after_node_id": after_id or None,
                    }
                )
                continue
            insert_node = ((patch.get("insert") or {}).get("node") or {})
            if not isinstance(insert_node, dict):
                applied_log["skipped"].append({"patch_id": patch_id, "reason": "INVALID_INSERT_NODE"})
                continue
            old_id = str(insert_node.get("node_id") or "")
            if not old_id:
                applied_log["skipped"].append({"patch_id": patch_id, "reason": "MISSING_NODE_ID"})
                continue
            node_type = str(insert_node.get("type") or "")
            if node_type not in ALLOWED_INSERT_NODE_TYPES:
                applied_log["skipped"].append({"patch_id": patch_id, "reason": "INVALID_NODE_TYPE", "type": node_type})
                continue
            summary = str(insert_node.get("summary") or "")
            if len(summary) > 300:
                applied_log["skipped"].append({"patch_id": patch_id, "reason": "SUMMARY_TOO_LONG"})
                continue

            unique_id, renamed = _ensure_unique_node_id(old_id, existing_ids, patch_id)
            if renamed:
                insert_node["node_id"] = unique_id
                applied_log["renamed_nodes"].append({"patch_id": patch_id, "from": old_id, "to": unique_id})
            existing_ids.add(str(insert_node["node_id"]))
            insert_node["conflict"] = clamp_conflict(insert_node.get("conflict", {}) or {})
            meta = insert_node.get("_meta", {}) or {}
            meta.setdefault("patches_applied", []).append(
                {"patch_id": patch_id, "patch_type": "insert_node", "where": {"after_node_id": after_id}}
            )
            insert_node["_meta"] = meta

            pos = int(node_idx[after_id]) + 1
            target_nodes.insert(pos, insert_node)
            node_idx = _build_node_index(target_nodes)
            applied_log["applied"].append(
                {
                    "patch_id": patch_id,
                    "patch_type": "insert_node",
                    "inserted_node_id": str(insert_node["node_id"]),
                    "after_node_id": after_id,
                }
            )
            continue

        if patch_type == "change_summary":
            where = patch.get("where") or {}
            node_id = str(where.get("node_id") or "")
            if not node_id or node_id not in node_idx:
                applied_log["skipped"].append({"patch_id": patch_id, "reason": "NODE_NOT_FOUND", "node_id": node_id or None})
                continue
            change = patch.get("change") or {}
            new_summary = change.get("summary", change.get("after"))
            if not isinstance(new_summary, str) or not new_summary.strip():
                applied_log["skipped"].append({"patch_id": patch_id, "reason": "INVALID_SUMMARY", "node_id": node_id})
                continue
            i = node_idx[node_id]
            before = str((target_nodes[i] or {}).get("summary") or "")
            target_nodes[i]["summary"] = new_summary.strip()
            meta = target_nodes[i].get("_meta", {}) or {}
            meta.setdefault("patches_applied", []).append(
                {"patch_id": patch_id, "patch_type": "change_summary", "where": {"node_id": node_id}}
            )
            target_nodes[i]["_meta"] = meta
            applied_log["summary_changed"].append(
                {
                    "patch_id": patch_id,
                    "node_id": node_id,
                    "before": before,
                    "after": new_summary.strip(),
                }
            )
            applied_log["applied"].append({"patch_id": patch_id, "patch_type": "change_summary", "node_id": node_id})
            continue

        applied_log["skipped"].append({"patch_id": patch_id, "reason": "UNSUPPORTED_PATCH_TYPE", "patch_type": patch_type})

    applied_count = len(applied_log["applied"])
    failed_count = len(applied_log["skipped"])
    meta = new_outline.get("_meta", {}) or {}
    meta["patch_apply"] = {
        "applied": applied_count,
        "failed": failed_count,
        "errors": applied_log["skipped"][:20],
        "applied_log": applied_log,
    }
    new_outline["_meta"] = meta
    return new_outline, applied_log


def apply_patches(outline_detail: dict[str, Any], patches: list[dict[str, Any]]) -> dict[str, Any]:
    patched, _ = apply_patches_to_outline(outline_detail, patches)
    return patched
