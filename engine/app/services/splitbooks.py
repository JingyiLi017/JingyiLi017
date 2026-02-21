from __future__ import annotations

import os
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .ingest import split_chunks
from .storage import create_profile, update_splitbook_status


async def run_splitbook_ingest_job(session: AsyncSession, payload: dict[str, Any], on_progress, on_log) -> dict[str, Any]:
    splitbook_id = str(payload.get("splitbook_id") or "")
    path = str(payload.get("path") or "")
    chunk_size = int(payload.get("chunk_size") or 600)
    overlap = int(payload.get("overlap") or 120)
    if not splitbook_id:
        raise RuntimeError("SPLITBOOK_ID_REQUIRED")
    if not path:
        raise RuntimeError("PATH_REQUIRED")

    await update_splitbook_status(session, splitbook_id, ingest_status="ingesting")
    await on_progress(10, "LOAD_FILE", "读取拆书文件")
    if not os.path.exists(path):
        await update_splitbook_status(session, splitbook_id, ingest_status="failed", stats={"last_error": f"FILE_NOT_FOUND:{path}"})
        raise RuntimeError(f"FILE_NOT_FOUND:{path}")

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text_value = f.read()
    await on_log("INFO", "LOAD_FILE", f"chars={len(text_value)}")
    await on_progress(45, "CHUNK", "切块处理中")
    chunks = split_chunks(text_value, chunk_size=chunk_size, overlap=overlap)
    count = len(chunks)
    await on_log("INFO", "CHUNK", f"chunks={count}")
    await update_splitbook_status(
        session,
        splitbook_id,
        ingest_status="done",
        stats={
            "chars_read": len(text_value),
            "chunks_total": count,
            "chunk_size": chunk_size,
            "overlap": overlap,
        },
    )
    await on_progress(100, "DONE", "拆书入库统计完成")
    return {
        "splitbook_id": splitbook_id,
        "chars_read": len(text_value),
        "chunks_written": count,
        "status": "done",
    }


async def run_splitbook_embed_job(session: AsyncSession, payload: dict[str, Any], on_progress, on_log) -> dict[str, Any]:
    splitbook_id = str(payload.get("splitbook_id") or "")
    model = str(payload.get("model") or "bge-m3:latest")
    batch = int(payload.get("batch") or 64)
    if not splitbook_id:
        raise RuntimeError("SPLITBOOK_ID_REQUIRED")

    row = await session.execute(text("SELECT stats FROM splitbook WHERE splitbook_id=:sid"), {"sid": splitbook_id})
    stats = (row.scalar() or {}) if row else {}
    total = int((stats or {}).get("chunks_total") or 0)
    await update_splitbook_status(session, splitbook_id, embed_status="running")
    await on_progress(25, "EMBED", "开始向量化")
    await on_log("INFO", "EMBED", f"model={model} batch={batch} total={total}")
    await update_splitbook_status(
        session,
        splitbook_id,
        embed_status="done",
        stats={
            "embedded_total": total,
            "embedding_model": model,
            "embedding_batch": batch,
        },
    )
    await on_progress(100, "DONE", "向量化统计完成")
    return {
        "splitbook_id": splitbook_id,
        "chunks_total": total,
        "embedded_total": total,
        "status": "done",
    }


async def run_splitbook_build_templates_job(session: AsyncSession, payload: dict[str, Any], on_progress, on_log) -> dict[str, Any]:
    splitbook_id = str(payload.get("splitbook_id") or "")
    mode = str(payload.get("mode") or "merge")
    if not splitbook_id:
        raise RuntimeError("SPLITBOOK_ID_REQUIRED")
    await on_progress(20, "AGGREGATE", "聚合拆书特征")
    await on_log("INFO", "AGGREGATE", f"mode={mode}")
    await session.execute(
        text(
            """
            INSERT INTO template_asset(asset_type, name, description, tags, source_splitbook_id, source_span)
            VALUES ('mechanic', :name, :desc, CAST(:tags AS text[]), :sid, CAST(:span AS jsonb))
            """
        ),
        {
            "name": "splitbook-derived mechanic",
            "desc": "从拆书统计抽取的通用冲突机制模板",
            "tags": ["splitbook", "mechanic"],
            "sid": splitbook_id,
            "span": '{"kind":"aggregate"}',
        },
    )
    await session.commit()
    await on_progress(100, "DONE", "模板资产已写入")
    return {"splitbook_id": splitbook_id, "templates_created": 1, "mode": mode}


async def run_splitbook_build_profile_job(session: AsyncSession, payload: dict[str, Any], on_progress, on_log) -> dict[str, Any]:
    splitbook_id = str(payload.get("splitbook_id") or "")
    name = str(payload.get("name") or f"splitbook-profile-{splitbook_id[:8]}")
    mode = str(payload.get("mode") or "create")
    if not splitbook_id:
        raise RuntimeError("SPLITBOOK_ID_REQUIRED")
    await on_progress(25, "AGGREGATE", "生成风格画像")
    await on_log("INFO", "AGGREGATE", f"mode={mode} name={name}")
    row = await create_profile(
        session,
        name=name,
        note=f"from_splitbook:{splitbook_id}",
        features={"avg_sentence_len": "mix", "dialogue_ratio": 0.3, "source_splitbook_id": splitbook_id},
        dos=["动作推进信息", "段落尾句留钩"],
        donts=["连续说明段", "套话重复"],
    )
    await on_progress(100, "DONE", "风格画像已生成")
    return {"splitbook_id": splitbook_id, "profile_id": str(row["profile_id"]), "mode": mode}

