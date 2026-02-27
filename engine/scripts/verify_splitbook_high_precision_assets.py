from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.services.splitbook_prompt_pack import (
    build_user_prompt_a,
    build_user_prompt_b,
    build_user_prompt_c,
    candidate_schema_hint,
    load_candidate_schema,
    load_postgres_schema_sql,
    load_scene_record_schema,
    scene_record_schema_hint,
    system_prompt_a,
    system_prompt_b,
    system_prompt_c,
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _to_asyncpg_url(url: str) -> str:
    raw = str(url or "").strip()
    if raw.startswith("postgresql+asyncpg://"):
        return "postgresql://" + raw[len("postgresql+asyncpg://") :]
    return raw


def _strip_extension_statements(sql_text: str) -> str:
    lines = []
    for line in sql_text.splitlines():
        if re.match(r"^\s*CREATE\s+EXTENSION\s+IF\s+NOT\s+EXISTS\s+", line, flags=re.IGNORECASE):
            continue
        lines.append(line)
    return "\n".join(lines)


async def _verify_schema_sql() -> dict[str, object]:
    sql_text = _strip_extension_statements(load_postgres_schema_sql())
    _assert("CREATE TABLE IF NOT EXISTS scene_record" in sql_text, "schema SQL missing scene_record")
    _assert("CREATE TABLE IF NOT EXISTS job" in sql_text, "schema SQL missing job")

    pg_url = _to_asyncpg_url(settings.database_url)
    _assert(pg_url.startswith("postgresql://"), "invalid database url for asyncpg")

    schema_name = f"verify_hp_{int(time.time())}"
    conn = await asyncpg.connect(pg_url)
    try:
        await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
        await conn.execute(f'SET search_path TO "{schema_name}"')
        await conn.execute(sql_text)

        required = [
            "book",
            "chapter",
            "scene",
            "chunk",
            "entity",
            "entity_mention",
            "scene_record",
            "fact",
            "event",
            "conflict",
            "foreshadow_seed",
            "payoff_candidate",
            "foreshadow_pair",
            "job",
        ]
        found: dict[str, bool] = {}
        for table_name in required:
            obj = await conn.fetchval("SELECT to_regclass($1)", f"{schema_name}.{table_name}")
            found[table_name] = bool(obj)
            _assert(found[table_name], f"table missing after apply SQL: {table_name}")

        return {"schema_name": schema_name, "tables": found}
    finally:
        try:
            await conn.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')
        finally:
            await conn.close()


def _verify_prompt_and_schema_assets() -> dict[str, object]:
    c_schema = load_candidate_schema()
    s_schema = load_scene_record_schema()

    _assert(isinstance(c_schema, dict) and c_schema.get("title") == "CandidatesV1", "candidate schema invalid")
    _assert(isinstance(s_schema, dict) and s_schema.get("title") == "SceneRecordV1", "scene schema invalid")

    prompt_a = build_user_prompt_a(scene_key="s1", chapter_no=1, scene_no=1, scene_excerpt="scene")
    prompt_b = build_user_prompt_b(
        scene_key="s1",
        chapter_no=1,
        scene_no=1,
        candidate_json='{"candidates":[]}',
        scene_excerpt="scene",
    )
    prompt_c = build_user_prompt_c(schema_hint='{"type":"object"}', broken_json='{"a":1}')

    _assert("任务=extract_candidates" in prompt_a, "prompt A invalid")
    _assert("任务=judge_and_structurize" in prompt_b, "prompt B invalid")
    _assert("任务=fix_json" in prompt_c, "prompt C invalid")
    _assert("candidates" in candidate_schema_hint(), "candidate schema hint invalid")
    _assert("scene_key" in scene_record_schema_hint(), "scene schema hint invalid")

    _assert("只输出JSON" in system_prompt_a(), "system prompt A invalid")
    _assert("重要性importance规则" in system_prompt_b(), "system prompt B invalid")
    _assert("JSON修复器" in system_prompt_c(), "system prompt C invalid")

    return {
        "candidate_schema_id": c_schema.get("$id"),
        "scene_schema_id": s_schema.get("$id"),
        "prompt_a_len": len(prompt_a),
        "prompt_b_len": len(prompt_b),
        "prompt_c_len": len(prompt_c),
    }


async def main() -> None:
    asset_info = _verify_prompt_and_schema_assets()
    sql_info = await _verify_schema_sql()
    print(json.dumps({"ok": True, "assets": asset_info, "sql": sql_info}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
