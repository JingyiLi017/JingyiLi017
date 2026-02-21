from __future__ import annotations

from typing import Any

EVAL_SCORE_KEYS = [
    "overall",
    "conflict_strength",
    "stakes",
    "cost",
    "pace",
    "reversal",
    "hook",
    "payoff",
]
SEVERITIES = {"low", "mid", "high"}
ALLOWED_PATCH_TYPES = {"insert_node", "change_summary"}
ALLOWED_MECHANICS = {
    "raise_stakes",
    "face_slap",
    "cost_hardening",
    "reversal",
    "timer",
    "betrayal",
    "upgrade",
    "rescue",
    "strengthen_obstacle",
    "sharpen_hook",
}
ALLOWED_MATERIAL_POINT_KINDS = {"fact", "emotion", "conflict", "mechanism", "style"}


def clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def ensure_keys(obj: dict[str, Any], keys: list[str], path: str) -> None:
    for key in keys:
        if key not in obj:
            raise ValueError(f"missing key at {path}: {key}")


def ensure_type(val: Any, expected_type: type, path: str) -> None:
    if not isinstance(val, expected_type):
        raise ValueError(f"type error at {path}: expected {expected_type.__name__}")


def short_err(exc: Exception, limit: int = 240) -> str:
    message = str(exc)
    return message if len(message) <= limit else f"{message[:limit]}..."


def validate_eval_output(obj: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []

    ensure_type(obj, dict, "$")
    ensure_keys(obj, ["schema_name", "schema_ver", "result"], "$")
    if "warnings" not in obj or not isinstance(obj.get("warnings"), list):
        obj["warnings"] = []
    if obj["schema_name"] != "EVAL_TENSION_SCORE" or int(obj["schema_ver"]) != 1:
        raise ValueError("schema mismatch: expected EVAL_TENSION_SCORE v1")

    result = obj["result"]
    ensure_type(result, dict, "$.result")
    ensure_keys(result, ["scores", "tension_curve", "issues"], "$.result")

    scores = result["scores"]
    ensure_type(scores, dict, "$.result.scores")
    ensure_keys(scores, EVAL_SCORE_KEYS, "$.result.scores")
    for key in EVAL_SCORE_KEYS:
        try:
            value = float(scores[key])
        except Exception as exc:
            raise ValueError(f"score not numeric: {key}") from exc
        clamped = clamp01(value)
        if clamped != value:
            warnings.append(f"score_clamped:{key}:{value}->{clamped}")
        scores[key] = round(clamped, 4)

    curve = result["tension_curve"]
    ensure_type(curve, list, "$.result.tension_curve")
    if len(curve) != 5:
        raise ValueError(f"tension_curve length must be 5, got {len(curve)}")
    fixed_curve: list[float] = []
    for idx, item in enumerate(curve):
        try:
            value = float(item)
        except Exception as exc:
            raise ValueError(f"tension_curve not numeric at index {idx}") from exc
        clamped = clamp01(value)
        if clamped != value:
            warnings.append(f"curve_clamped:{idx}:{value}->{clamped}")
        fixed_curve.append(round(clamped, 4))
    result["tension_curve"] = fixed_curve

    issues = result["issues"]
    ensure_type(issues, list, "$.result.issues")
    if len(issues) > 6:
        warnings.append(f"issues_truncated:{len(issues)}->6")
        issues = issues[:6]
        result["issues"] = issues

    for idx, item in enumerate(issues):
        ensure_type(item, dict, f"$.result.issues[{idx}]")
        ensure_keys(item, ["code", "severity", "where", "detail"], f"$.result.issues[{idx}]")
        if item["severity"] not in SEVERITIES:
            warnings.append(f"issue_severity_fixed:{idx}")
            item["severity"] = "mid"
        if not (item["where"] is None or isinstance(item["where"], str)):
            warnings.append(f"issue_where_fixed:{idx}")
            item["where"] = None
        if not isinstance(item["detail"], str):
            item["detail"] = str(item["detail"])[:120]

    obj["warnings"].extend(warnings)
    return obj, warnings


def validate_plan_output(
    obj: dict[str, Any],
    *,
    max_insert: int = 4,
    max_change: int = 2,
    max_patches: int = 8,
    actions_override: list[str] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    actions_override = actions_override or []

    ensure_type(obj, dict, "$")
    ensure_keys(obj, ["schema_name", "schema_ver", "result"], "$")
    if "warnings" not in obj or not isinstance(obj.get("warnings"), list):
        obj["warnings"] = []
    if obj["schema_name"] != "TENSION_CONTROL_PLAN" or int(obj["schema_ver"]) != 1:
        raise ValueError("schema mismatch: expected TENSION_CONTROL_PLAN v1")

    result = obj["result"]
    ensure_type(result, dict, "$.result")
    ensure_keys(result, ["gap", "selected_actions", "limits", "patches", "fill_nodes"], "$.result")

    result["limits"] = {
        "max_insert_nodes": int(max_insert),
        "max_change_summary": int(max_change),
        "max_total_patches": int(max_patches),
    }

    patches = result["patches"]
    ensure_type(patches, list, "$.result.patches")
    if len(patches) > max_patches:
        warnings.append(f"patches_truncated:{len(patches)}->{max_patches}")
        patches = patches[:max_patches]
        result["patches"] = patches

    insert_count = 0
    change_count = 0
    inserted_empty: list[str] = []
    seen_patch_ids: set[str] = set()
    for idx, patch in enumerate(patches):
        ensure_type(patch, dict, f"$.result.patches[{idx}]")
        ensure_keys(patch, ["patch_id", "patch_type"], f"$.result.patches[{idx}]")
        patch_id = patch["patch_id"]
        if not isinstance(patch_id, str) or not patch_id:
            raise ValueError(f"invalid patch_id at patches[{idx}]")
        if patch_id in seen_patch_ids:
            warnings.append(f"dup_patch_id:{patch_id}")
        seen_patch_ids.add(patch_id)

        patch_type = patch["patch_type"]
        if patch_type not in ALLOWED_PATCH_TYPES:
            raise ValueError(f"invalid patch_type {patch_type} at patches[{idx}]")

        if patch_type == "insert_node":
            insert_count += 1
            if insert_count > max_insert:
                patch["_drop"] = True
                warnings.append(f"insert_nodes_truncated>{max_insert}")
                continue
            ensure_keys(patch, ["where", "insert"], f"$.result.patches[{idx}]")
            ensure_type(patch["where"], dict, f"$.result.patches[{idx}].where")
            ensure_keys(patch["where"], ["after_node_id"], f"$.result.patches[{idx}].where")
            if not isinstance(patch["where"]["after_node_id"], str) or not patch["where"]["after_node_id"]:
                raise ValueError(f"missing after_node_id at patches[{idx}]")

            ensure_type(patch["insert"], dict, f"$.result.patches[{idx}].insert")
            ensure_keys(patch["insert"], ["node"], f"$.result.patches[{idx}].insert")
            node = patch["insert"]["node"]
            ensure_type(node, dict, f"$.result.patches[{idx}].insert.node")
            ensure_keys(node, ["node_id", "type", "summary", "_meta"], f"$.result.patches[{idx}].insert.node")
            ensure_type(node["_meta"], dict, f"$.result.patches[{idx}].insert.node._meta")
            ensure_keys(node["_meta"], ["mechanic"], f"$.result.patches[{idx}].insert.node._meta")
            mechanic = str(node["_meta"]["mechanic"])
            if mechanic not in ALLOWED_MECHANICS:
                warnings.append(f"unknown_mechanic:{mechanic}")
            if isinstance(node.get("summary"), str) and node.get("summary", "").strip() == "":
                inserted_empty.append(str(node["node_id"]))

        if patch_type == "change_summary":
            change_count += 1
            if change_count > max_change:
                patch["_drop"] = True
                warnings.append(f"change_summary_truncated>{max_change}")
                continue
            ensure_keys(patch, ["where", "change"], f"$.result.patches[{idx}]")
            ensure_type(patch["where"], dict, f"$.result.patches[{idx}].where")
            ensure_keys(patch["where"], ["node_id"], f"$.result.patches[{idx}].where")
            ensure_type(patch["change"], dict, f"$.result.patches[{idx}].change")
            if "after" not in patch["change"] and "summary" not in patch["change"]:
                raise ValueError(f"change must contain after|summary at patches[{idx}]")

    result["patches"] = [p for p in result["patches"] if not p.get("_drop")]

    fill_nodes = result["fill_nodes"]
    ensure_type(fill_nodes, list, "$.result.fill_nodes")
    fill_node_ids = {str(item.get("node_id")) for item in fill_nodes if isinstance(item, dict) and item.get("node_id")}
    for node_id in inserted_empty:
        if node_id not in fill_node_ids:
            warnings.append(f"fill_nodes_missing:{node_id}")
            result["fill_nodes"].append({"node_id": node_id, "mechanic": "unknown", "max_words": 120})

    selected_actions = result["selected_actions"]
    ensure_type(selected_actions, list, "$.result.selected_actions")
    selected_mechanics = {str(item.get("mechanic")) for item in selected_actions if isinstance(item, dict) and item.get("mechanic")}
    for action in actions_override:
        if action not in selected_mechanics:
            warnings.append(f"override_not_satisfied:{action}")

    obj["warnings"].extend(warnings)
    return obj, warnings


def validate_fill_output(obj: dict[str, Any], *, expected_node_ids: set[str]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    ensure_type(obj, dict, "$")
    ensure_keys(obj, ["fills"], "$")
    fills = obj["fills"]
    ensure_type(fills, list, "$.fills")

    seen: set[str] = set()
    output: list[dict[str, str]] = []
    for idx, item in enumerate(fills):
        ensure_type(item, dict, f"$.fills[{idx}]")
        ensure_keys(item, ["node_id", "summary"], f"$.fills[{idx}]")
        node_id = item["node_id"]
        summary = item["summary"]
        if not isinstance(node_id, str) or not node_id:
            raise ValueError(f"invalid node_id at fills[{idx}]")
        if node_id in seen:
            warnings.append(f"dup_fill_node:{node_id}")
            continue
        seen.add(node_id)
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError(f"empty summary for node {node_id}")
        if node_id not in expected_node_ids:
            warnings.append(f"unexpected_fill_node:{node_id}")
            continue
        output.append({"node_id": node_id, "summary": summary.strip()})

    missing = expected_node_ids - {x["node_id"] for x in output}
    if missing:
        raise ValueError(f"missing fills for nodes: {sorted(list(missing))[:10]}")

    obj["fills"] = output
    return obj, warnings


def validate_material_extract_output(obj: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    ensure_type(obj, dict, "$")
    ensure_keys(obj, ["schema_name", "schema_ver", "result"], "$")
    if "warnings" not in obj or not isinstance(obj.get("warnings"), list):
        obj["warnings"] = []
    if obj["schema_name"] != "MATERIAL_EXTRACT_POINTS" or int(obj["schema_ver"]) != 1:
        raise ValueError("schema mismatch: expected MATERIAL_EXTRACT_POINTS v1")

    result = obj["result"]
    ensure_type(result, dict, "$.result")
    ensure_keys(result, ["card_id", "extracted_points", "risk_flags"], "$.result")
    if not isinstance(result["card_id"], str) or not result["card_id"]:
        raise ValueError("card_id must be non-empty string")

    points = result["extracted_points"]
    ensure_type(points, list, "$.result.extracted_points")
    if len(points) < 3:
        raise ValueError("extracted_points must be >= 3")
    if len(points) > 7:
        warnings.append(f"extracted_points_truncated:{len(points)}->7")
        points = points[:7]
        result["extracted_points"] = points

    cleaned_points: list[dict[str, str]] = []
    for idx, item in enumerate(points):
        ensure_type(item, dict, f"$.result.extracted_points[{idx}]")
        ensure_keys(item, ["kind", "point", "rewrite_hint"], f"$.result.extracted_points[{idx}]")
        kind = str(item.get("kind") or "mechanism")
        if kind not in ALLOWED_MATERIAL_POINT_KINDS:
            warnings.append(f"point_kind_fixed:{idx}:{kind}->mechanism")
            kind = "mechanism"
        point = str(item.get("point") or "").strip()
        hint = str(item.get("rewrite_hint") or "").strip()
        if not point:
            raise ValueError(f"empty point at index {idx}")
        if not hint:
            raise ValueError(f"empty rewrite_hint at index {idx}")
        if len(point) > 80:
            warnings.append(f"point_truncated:{idx}")
            point = point[:80]
        if len(hint) > 60:
            warnings.append(f"rewrite_hint_truncated:{idx}")
            hint = hint[:60]
        cleaned_points.append({"kind": kind, "point": point, "rewrite_hint": hint})
    result["extracted_points"] = cleaned_points

    risk_flags = result["risk_flags"]
    ensure_type(risk_flags, list, "$.result.risk_flags")
    fixed_flags: list[dict[str, str]] = []
    for idx, item in enumerate(risk_flags):
        if not isinstance(item, dict):
            warnings.append(f"risk_flag_invalid:{idx}")
            continue
        code = str(item.get("code") or "COPY_RISK")
        severity = str(item.get("severity") or "low")
        detail = str(item.get("detail") or "").strip()
        if severity not in SEVERITIES:
            warnings.append(f"risk_severity_fixed:{idx}")
            severity = "mid"
        if len(detail) > 120:
            detail = detail[:120]
        fixed_flags.append({"code": code, "severity": severity, "detail": detail})
    result["risk_flags"] = fixed_flags

    obj["warnings"].extend(warnings)
    return obj, warnings
