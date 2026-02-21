from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _short(value: str, length: int = 32) -> str:
    normalized = " ".join((value or "").split())
    return normalized[:length] if len(normalized) > length else normalized


def build_structure_beats_prompt(chapter_no: int, chunks: list[dict[str, Any]]) -> str:
    # v1 先生成统一 prompt 文本，后续接真实 LLM 可直接复用。
    preview = "\n".join([f"- {c['chunk_id']}: {_short(c['text'], 60)}" for c in chunks[:8]])
    return (
        "你是结构节拍抽取器，只输出结构，不输出原句。\n"
        f"chapter_no={chapter_no}\n"
        "请按 hook/goal/obstacle/escalation/turning_point/cost/gain/cliffhanger 输出。\n"
        f"chunks:\n{preview}"
    )


def _rule_extract_beats(chapter_no: int, chunks: list[dict[str, Any]]) -> dict[str, Any]:
    if not chunks:
        return {"chapter_no": chapter_no, "beats": [], "mechanics": [], "confidence": 0.0}
    first = chunks[0]
    middle = chunks[len(chunks) // 2]
    last = chunks[-1]
    beats = [
        {"type": "hook", "summary": f"开局钩子: {_short(first['text'])}", "evidence": [str(first["chunk_id"])]},
        {"type": "goal", "summary": "本章目标建立", "evidence": [str(first["chunk_id"])]},
        {"type": "obstacle", "summary": f"阻碍出现: {_short(middle['text'])}", "evidence": [str(middle["chunk_id"])]},
        {"type": "turning_point", "summary": "关键转折发生", "evidence": [str(middle["chunk_id"])]},
        {"type": "cost", "summary": "主角承受代价", "evidence": [str(last["chunk_id"])]},
        {"type": "gain", "summary": "获得推进或收益", "evidence": [str(last["chunk_id"])]},
        {"type": "cliffhanger", "summary": f"悬念收尾: {_short(last['text'])}", "evidence": [str(last["chunk_id"])]},
    ]
    mechanics = [{"name": "upgrade", "strength": 0.65}, {"name": "reversal", "strength": 0.5}]
    return {"chapter_no": chapter_no, "beats": beats, "mechanics": mechanics, "confidence": 0.72}


def extract_sequence(beats_items: list[dict[str, Any]]) -> list[tuple[str, ...]]:
    sequences: list[tuple[str, ...]] = []
    for item in beats_items:
        seq = tuple(b.get("type", "") for b in item.get("beats", []) if b.get("type"))
        if seq:
            sequences.append(seq)
    return sequences


def most_common_sequence(sequences: list[tuple[str, ...]]) -> tuple[str, ...]:
    if not sequences:
        return ("hook", "goal", "obstacle", "turning_point", "cost", "gain", "cliffhanger")
    counter = Counter(sequences)
    return counter.most_common(1)[0][0]


def aggregate_mechanics(beats_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scores: dict[str, list[float]] = defaultdict(list)
    for item in beats_items:
        for mech in item.get("mechanics", []):
            name = mech.get("name")
            if name:
                scores[name].append(float(mech.get("strength", 0)))
    result: list[dict[str, Any]] = []
    for name, vals in scores.items():
        result.append({"name": name, "strength": sum(vals) / len(vals)})
    return result


def build_template_graph(level: str, sequence: tuple[str, ...], mechanics: list[dict[str, Any]]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for idx, beat_type in enumerate(sequence):
        node_id = f"N{idx + 1}"
        nodes.append({"id": node_id, "type": beat_type, "constraints": {}})
        if idx > 0:
            edges.append({"from": f"N{idx}", "to": node_id})
    return {
        "schema_name": "STRUCTURE_TEMPLATE_GRAPH",
        "schema_ver": 1,
        "level": level,
        "nodes": nodes,
        "edges": edges,
        "mechanics": mechanics,
    }


async def _fetch_chapters_in_range(session: AsyncSession, book_id: str, chapter_range: list[int] | None) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"book_id": book_id}
    sql = """
      SELECT chapter_id, "order" AS chapter_no
      FROM chapter
      WHERE book_id=:book_id
    """
    if chapter_range and len(chapter_range) == 2:
        sql += ' AND "order" BETWEEN :start_no AND :end_no'
        params["start_no"] = int(chapter_range[0])
        params["end_no"] = int(chapter_range[1])
    sql += ' ORDER BY "order" ASC'
    result = await session.execute(text(sql), params)
    return [dict(r) for r in result.mappings().all()]


async def _fetch_chunks_by_chapter(session: AsyncSession, chapter_id: str) -> list[dict[str, Any]]:
    result = await session.execute(
        text(
            """
            SELECT chunk_id, text, index_in_chapter
            FROM chunk
            WHERE chapter_id=:chapter_id
            ORDER BY index_in_chapter ASC
            """
        ),
        {"chapter_id": chapter_id},
    )
    return [dict(r) for r in result.mappings().all()]


async def run_extract_structure_beats_job(session: AsyncSession, payload: dict[str, Any], on_progress, on_log) -> dict[str, Any]:
    book_id = str(payload["book_id"])
    scope = payload.get("scope", {}) or {}
    chapter_range = scope.get("chapter_range")
    llm_model = payload.get("llm_model", "qwen2.5:7b")

    await on_progress(5, "LOAD_SCOPE", "加载章节范围")
    chapters = await _fetch_chapters_in_range(session, book_id, chapter_range)
    if not chapters:
        raise RuntimeError("NO_CHAPTERS_IN_SCOPE")

    all_results: list[dict[str, Any]] = []
    await on_progress(10, "BATCH_LLM", "开始逐章抽取结构节拍")
    total = len(chapters)

    for idx, chapter in enumerate(chapters, start=1):
        chunks = await _fetch_chunks_by_chapter(session, str(chapter["chapter_id"]))
        _ = build_structure_beats_prompt(int(chapter["chapter_no"]), chunks)
        try:
            # v1: 规则抽取，占位 LLM 结果，接口保持一致
            data = _rule_extract_beats(int(chapter["chapter_no"]), chunks)
            all_results.append(data)
        except Exception as exc:
            await on_log("WARN", "BATCH_LLM", f"chapter={chapter['chapter_no']} failed: {exc}")
        progress = 10 + int(70 * (idx / total))
        await on_progress(progress, "BATCH_LLM", f"章节 {idx}/{total} 抽取完成（model={llm_model}）")

    await on_progress(84, "MERGE_BY_CHAPTER", "按章节合并结果")
    merged = sorted(all_results, key=lambda x: int(x.get("chapter_no", 0)))
    output = {
        "schema_name": "EXTRACT_STRUCTURE_BEATS",
        "schema_ver": int(payload.get("schema_ver", 1)),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": merged,
        "warnings": [],
    }

    await on_progress(95, "SAVE_SKILL_RUN", "写入 skill_run")
    sr = await session.execute(
        text(
            """
            INSERT INTO skill_run(book_id, skill_name, schema_ver, output)
            VALUES (:book_id, 'EXTRACT_STRUCTURE_BEATS_V1', :schema_ver, CAST(:output AS jsonb))
            RETURNING skill_run_id
            """
        ),
        {"book_id": book_id, "schema_ver": int(payload.get("schema_ver", 1)), "output": json.dumps(output)},
    )
    skill_run_id = str(sr.scalar_one())
    await session.commit()
    await on_progress(100, "DONE", "结构节拍抽取完成")
    return {"skill_run_id": skill_run_id, "count": len(merged)}


async def run_generate_structure_template_job(session: AsyncSession, payload: dict[str, Any], on_progress, on_log) -> dict[str, Any]:
    book_id = str(payload["book_id"])
    skill_run_id = str(payload["skill_run_id"])
    level = payload.get("level", "chapter")
    name = payload.get("name", "标准爽点章节结构")
    tags = payload.get("tags", [])

    await on_progress(10, "LOAD_SKILL_RUN", "读取 beats skill_run")
    sr = await session.execute(
        text(
            """
            SELECT output FROM skill_run
            WHERE skill_run_id=:skill_run_id AND book_id=:book_id
            """
        ),
        {"skill_run_id": skill_run_id, "book_id": book_id},
    )
    row = sr.mappings().first()
    if not row:
        raise RuntimeError("SKILL_RUN_NOT_FOUND")
    beats_data = (row["output"] or {}).get("items", [])
    if not beats_data:
        raise RuntimeError("EMPTY_BEATS_DATA")

    await on_progress(35, "AGGREGATE_SEQUENCE", "统计主结构序列")
    sequences = extract_sequence(beats_data)
    main_seq = most_common_sequence(sequences)

    await on_progress(55, "AGGREGATE_MECHANICS", "统计机制强度")
    mechanics = aggregate_mechanics(beats_data)

    await on_progress(70, "BUILD_GRAPH", "构建模板图谱")
    graph = build_template_graph(level, main_seq, mechanics)

    await on_progress(85, "SAVE_TEMPLATE", "写入模板")
    prof = await session.execute(text("SELECT profile_id FROM book WHERE book_id=:book_id"), {"book_id": book_id})
    profile_id = prof.scalar()
    if profile_id is None:
        created = await session.execute(
            text("INSERT INTO profile(name, note) VALUES ('Default Profile','Auto created by template job') RETURNING profile_id")
        )
        profile_id = created.scalar_one()
        await session.execute(text("UPDATE book SET profile_id=:pid WHERE book_id=:book_id"), {"pid": str(profile_id), "book_id": book_id})

    tpl = await session.execute(
        text(
            """
            INSERT INTO structure_template(profile_id, name, level, tags, schema_ver, graph, meta)
            VALUES (:profile_id, :name, :level, :tags::text[], 1, :graph::jsonb, :meta::jsonb)
            RETURNING template_id
            """
        ),
        {
            "profile_id": str(profile_id),
            "name": name,
            "level": level,
            "tags": tags,
            "graph": json.dumps(graph),
            "meta": json.dumps({"from_skill_run": skill_run_id, "source_book_id": book_id}),
        },
    )
    template_id = str(tpl.scalar_one())

    evidence_chunks: list[str] = []
    for item in beats_data:
        for beat in item.get("beats", []):
            for cid in beat.get("evidence", []):
                if cid and cid not in evidence_chunks:
                    evidence_chunks.append(cid)
    await session.execute(
        text(
            """
            INSERT INTO structure_template_source(template_id, source_book_id, source_chunk_ids, note)
            VALUES (:template_id, :source_book_id, :source_chunk_ids::uuid[], :note)
            """
        ),
        {
            "template_id": template_id,
            "source_book_id": book_id,
            "source_chunk_ids": evidence_chunks,
            "note": "generated from EXTRACT_STRUCTURE_BEATS_V1",
        },
    )
    await session.commit()
    await on_log("INFO", "DONE", "模板生成完成并已入库")
    await on_progress(100, "DONE", "模板生成完成")
    return {"template_id": template_id, "main_sequence": list(main_seq), "mechanics": mechanics}
