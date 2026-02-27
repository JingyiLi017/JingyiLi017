from __future__ import annotations

import json
from typing import Any

STRICT_JSON_SYSTEM_PROMPT = """You are a strict JSON generator.

Rules:
1) Output ONLY valid JSON. No markdown, no code fences, no comments, no extra text.
2) Use double quotes for all JSON strings.
3) Do not output trailing commas.
4) Ensure the JSON can be parsed by standard json.loads.
5) Do not include any keys not requested.
6) If information is missing, use null or an empty array, but keep the required keys.

Remember: Output ONLY JSON."""


def _dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def build_eval_user_prompt(*, targets: dict[str, Any], outline_nodes: list[dict[str, Any]]) -> str:
    required_schema = {
        "schema_name": "EVAL_TENSION_SCORE",
        "schema_ver": 1,
        "result": {
            "scores": {
                "overall": 0.0,
                "conflict_strength": 0.0,
                "stakes": 0.0,
                "cost": 0.0,
                "pace": 0.0,
                "reversal": 0.0,
                "hook": 0.0,
                "payoff": 0.0,
            },
            "tension_curve": [0.0, 0.0, 0.0, 0.0, 0.0],
            "issues": [{"code": "STRING", "severity": "low", "where": None, "detail": "STRING"}],
        },
        "warnings": [],
    }
    return f"""Task: Evaluate the tension quality of this chapter outline.

Scoring dimensions (0.00 to 1.00):
- conflict_strength: active opposition, clashes, friction
- stakes: what can be gained/lost, consequences
- cost: irreversible price paid, meaningful sacrifice
- pace: progression speed, scene-to-scene momentum
- reversal: surprises, information asymmetry, turning points
- hook: curiosity and forward pull
- payoff: closure and reward for setup
overall: weighted overall quality

Target scores (for guidance, not strict):
{_dump(targets)}

Chapter outline (nodes in order):
{_dump(outline_nodes)}

Rules:
- Use ONLY the information in the outline.
- Identify 0~6 major issues maximum.
- If an issue relates to a node, set "where" to that node_id; else null.
- Make "detail" concise.
- Output JSON strictly following this required schema (same keys, same nesting):
{_dump(required_schema)}
"""


def build_plan_user_prompt(
    *,
    targets: dict[str, Any],
    style: dict[str, Any],
    eval_scores: dict[str, Any] | None,
    actions_override: list[str],
    outline_nodes: list[dict[str, Any]],
    max_insert: int,
    max_change: int,
    max_patch: int,
    reference_blocks: list[str] | None = None,
) -> str:
    required_schema = {
        "schema_name": "TENSION_CONTROL_PLAN",
        "schema_ver": 1,
        "result": {
            "gap": {
                "conflict_strength": 0.0,
                "stakes": 0.0,
                "cost": 0.0,
                "pace": 0.0,
                "reversal": 0.0,
                "hook": 0.0,
                "payoff": 0.0,
            },
            "selected_actions": [{"mechanic": "timer", "anchor": "NODE_ID"}],
            "limits": {"max_insert_nodes": max_insert, "max_change_summary": max_change, "max_total_patches": max_patch},
            "patches": [],
            "fill_nodes": [],
        },
        "warnings": [],
    }
    refs = [str(x).strip() for x in (reference_blocks or []) if str(x).strip()]
    refs_compact = [x[:1600] for x in refs[:8]]
    refs_section = _dump(refs_compact) if refs_compact else "[]"
    return f"""Task: Generate a minimal patch plan to improve the chapter outline to match the targets.

Inputs:
Targets:
{_dump(targets)}

Style preferences:
{_dump(style)}

Current evaluation (if available, else null):
{_dump(eval_scores)}

Actions override (MUST prioritize if present):
{_dump(actions_override)}

Outline nodes in order:
{_dump(outline_nodes)}

Optional structure references (anti-copy mode, mechanics only):
{refs_section}

Mechanics you can use (choose only what is needed):
- raise_stakes
- face_slap
- cost_hardening
- reversal
- timer
- betrayal
- upgrade
- rescue

Patch types allowed:
1) insert_node: insert a new micro node after an existing node
2) change_summary: rewrite an existing node summary (keep node_id)

Constraints:
- max_insert_nodes = {max_insert}
- max_change_summary = {max_change}
- max_total_patches = {max_patch}
- Use at most 2 mechanics per chapter.
- If actions_override is not empty, ensure those mechanics appear in selected_actions and patches unless impossible due to constraints.
- References are for structure learning only: DO NOT copy wording, paragraphs, or original narrative order from references.
- Do NOT fill in the node.summary content for inserted nodes; leave summary as "" and add them into fill_nodes for later filling.
- Output JSON strictly following this required schema (same keys, same nesting):
{_dump(required_schema)}
"""


def build_fill_user_prompt(*, max_words: int, outline_nodes: list[dict[str, Any]], fill_nodes: list[dict[str, Any]]) -> str:
    return f"""Task: Fill concise summaries for inserted micro nodes.

Rules:
- Output ONLY JSON: {{"fills":[{{"node_id":"...","summary":"..."}}...]}}
- Keep each summary <= {max_words} words/chars roughly.
- Use the same tone as the outline.
- Do not invent new main plot lines; only strengthen tension.

Outline context (original nodes):
{_dump(outline_nodes)}

Nodes to fill:
{_dump(fill_nodes)}
"""


def build_material_extract_user_prompt(
    *,
    material: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> str:
    required_schema = {
        "schema_name": "MATERIAL_EXTRACT_POINTS",
        "schema_ver": 1,
        "result": {
            "card_id": "UUID",
            "extracted_points": [
                {
                    "kind": "fact",
                    "point": "STRING",
                    "rewrite_hint": "STRING",
                }
            ],
            "risk_flags": [
                {
                    "code": "COPY_RISK",
                    "severity": "low",
                    "detail": "STRING",
                }
            ],
        },
        "warnings": [],
    }
    return f"""Task: Extract reusable points from a material card for novel writing WITHOUT copying.

Material:
{_dump(material)}

Context (optional):
{_dump(context or {})}

Rules:
- Do NOT quote or copy original sentences.
- Extract only high-level reusable points: facts, emotions, conflict mechanisms, style cues.
- Point must be abstract; do NOT contain unique named entities unless essential.
- Each "point" must be concise.
- Each "rewrite_hint" must be concise.
- Output 3 to 7 points.
- If the material has distinctive phrases that are risky to copy, add a COPY_RISK flag with severity mid/high.
- Output JSON strictly following this required schema (same keys, same nesting):
{_dump(required_schema)}
"""
