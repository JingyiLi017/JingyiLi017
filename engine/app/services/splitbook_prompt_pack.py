from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

PROMPT_VERSION = "extract.v1"
SCENE_SCHEMA_VERSION = "scenerecord.v1"
CANDIDATE_SCHEMA_VERSION = "candidates.v1"

_SYSTEM_PROMPT_A = """你是候选信息枚举器。只输出JSON，不要markdown，不要解释，不要注释。
禁止编造：候选内容必须来自输入文本scene_text。
目标：尽可能召回候选信息，包括但不限于：
- 序列/途径/魔药配方/材料/晋升仪式
- 世界观规则/限制/代价/警告/污染/组织信仰
- 道具/遗物/封印物/能力效果
- 关键事件（发生了什么）
- 伏笔种子（异常、信息缺口、明确提醒未来风险）
- 回收线索（解释、兑现、触发、揭示真相）
每条候选必须给出evidence：从scene_text中原样复制的短句1-3句。
不需要判断重要性：importance不输出；confidence不输出。
输出必须严格符合candidate_schema_hint，不允许多余字段。"""

_SYSTEM_PROMPT_B = """你是结构化裁决器。只输出JSON，不要markdown，不要解释，不要注释。
禁止编造事实：所有事实内容必须来自输入文本scene_text或candidate_json的evidence句子。
允许对“重要性importance”和“置信度confidence”做判断，但必须基于evidence。
重要性importance规则（必须执行）：
- 3：影响主线/卷级结构/长期设定/关键伏笔或关键回收/晋升大节点/关键规则或代价
- 2：章纲关键事件、重要道具/能力/配方、后文会复用的重要信息
- 1：背景信息或局部说明
- 0：噪音、修辞、无信息增量（不应进入结构账本）

evidence要求：每个events/world_facts/artifacts/foreshadow_candidates/payoff_candidates/conflict必须包含至少1条evidence句子，且必须原样来自scene_text。
若无法确定：对应字段填空字符串或空数组，并降低confidence。
输出必须严格符合schema_hint，不允许多余字段。"""

_SYSTEM_PROMPT_C = """你是JSON修复器。只输出JSON，不要markdown，不要解释，不要注释。
输入包含：schema_hint与broken_json。
你的任务：在不新增任何事实的前提下修复broken_json，使其严格满足schema_hint：
- 只能修正格式、缺失字段、字段类型、非法枚举值、数组/对象结构
- 不允许新增scene_text中不存在的证据句子
- evidence只能从broken_json已有的evidence里选择或复用
输出必须仅包含修复后的JSON对象。"""

_CANDIDATE_SCHEMA_HINT_OBJ = {
    "candidates": [
        {
            "kind": "potion_recipe|sequence|ritual|rule|warning|pollution|artifact|organization|ability|event|foreshadow_seed|payoff_hint|other",
            "content": "string",
            "evidence": ["string"],
            "entity_tags": ["string"],
        }
    ]
}

_SCENE_RECORD_SCHEMA_HINT_OBJ = {
    "scene_key": "string",
    "chapter_no": 0,
    "scene_no": 0,
    "events": [
        {
            "beat": "string",
            "what": "string",
            "cause": "string",
            "result": "string",
            "tension_score": 0,
            "importance": 0,
            "confidence": 0.0,
            "evidence": ["string"],
        }
    ],
    "world_facts": [
        {
            "fact_type": "pathway|sequence|potion_recipe|ritual|rule|warning|pollution|organization|artifact|ability|other",
            "subject": "string",
            "predicate": "string",
            "object": "string",
            "constraints": "string",
            "cost_or_risk": "string",
            "importance": 0,
            "confidence": 0.0,
            "evidence": ["string"],
            "entity_tags": ["string"],
        }
    ],
    "artifacts": [
        {
            "name": "string",
            "type": "string",
            "effect": "string",
            "risk_or_cost": "string",
            "owner_or_source": "string",
            "importance": 0,
            "confidence": 0.0,
            "evidence": ["string"],
        }
    ],
    "conflict": {
        "type": "man_vs_man|man_vs_self|man_vs_world|man_vs_system|man_vs_unknown|none",
        "side_a_goal": "string",
        "side_b_goal": "string",
        "stakes": "string",
        "escalation": "string",
        "turning_point": "string",
        "outcome": "string",
        "tension_score": 0,
        "confidence": 0.0,
        "evidence": ["string"],
    },
    "foreshadow_candidates": [
        {
            "seed": "string",
            "why": "string",
            "promise": "string",
            "importance": 0,
            "confidence": 0.0,
            "entity_tags": ["string"],
            "evidence": ["string"],
        }
    ],
    "payoff_candidates": [
        {
            "payoff": "string",
            "trigger": "string",
            "effect": "string",
            "resolves": "string",
            "importance": 0,
            "confidence": 0.0,
            "entity_tags": ["string"],
            "evidence": ["string"],
        }
    ],
}


def system_prompt_a() -> str:
    return _SYSTEM_PROMPT_A


def system_prompt_b() -> str:
    return _SYSTEM_PROMPT_B


def system_prompt_c() -> str:
    return _SYSTEM_PROMPT_C


def candidate_schema_hint() -> str:
    return json.dumps(_CANDIDATE_SCHEMA_HINT_OBJ, ensure_ascii=False)


def scene_record_schema_hint() -> str:
    return json.dumps(_SCENE_RECORD_SCHEMA_HINT_OBJ, ensure_ascii=False)


def build_user_prompt_a(*, scene_key: str, chapter_no: int, scene_no: int, scene_excerpt: str) -> str:
    return (
        "任务=extract_candidates\n"
        f"scene_key={scene_key} chapter_no={chapter_no} scene_no={scene_no}\n\n"
        "输出要求：仅输出一个JSON对象，严格满足candidate_schema_hint；不允许输出多余字段。\n"
        f"candidate_schema_hint={candidate_schema_hint()}\n\n"
        "scene_text:\n"
        f"{scene_excerpt}"
    )


def build_user_prompt_b(*, scene_key: str, chapter_no: int, scene_no: int, candidate_json: str, scene_excerpt: str) -> str:
    return (
        "任务=judge_and_structurize\n"
        f"scene_key={scene_key} chapter_no={chapter_no} scene_no={scene_no}\n\n"
        "输出要求：仅输出一个JSON对象，严格满足schema_hint；不允许输出多余字段。\n"
        f"schema_hint={scene_record_schema_hint()}\n\n"
        f"候选结果（可参考可修正）candidate_json={candidate_json}\n\n"
        "scene_text:\n"
        f"{scene_excerpt}"
    )


def build_user_prompt_c(*, schema_hint: str, broken_json: str) -> str:
    return (
        "任务=fix_json\n"
        f"schema_hint={schema_hint}\n"
        f"broken_json={broken_json}"
    )


@lru_cache(maxsize=1)
def load_candidate_schema() -> dict[str, Any]:
    p = (Path(__file__).resolve().parents[1] / "contracts" / "splitbook" / "candidates.v1.json").resolve()
    return json.loads(p.read_text(encoding="utf-8-sig"))


@lru_cache(maxsize=1)
def load_scene_record_schema() -> dict[str, Any]:
    p = (Path(__file__).resolve().parents[1] / "contracts" / "splitbook" / "scenerecord.v1.json").resolve()
    return json.loads(p.read_text(encoding="utf-8-sig"))


@lru_cache(maxsize=1)
def load_postgres_schema_sql() -> str:
    p = (Path(__file__).resolve().parents[1] / "contracts" / "splitbook" / "postgres" / "high_precision_schema.sql").resolve()
    return p.read_text(encoding="utf-8-sig")
