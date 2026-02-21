from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def split_chunks(text_value: str, chunk_size: int, overlap: int) -> list[str]:
    content = text_value.strip()
    if not content:
        return []
    step = max(1, chunk_size - overlap)
    out: list[str] = []
    index = 0
    while index < len(content):
        chunk = content[index : index + chunk_size].strip()
        if chunk:
            out.append(chunk)
        index += step
    return out


async def run_ingest_job(
    session: AsyncSession,
    payload: dict,
    on_progress,
    on_log,
) -> dict:
    book_id = payload["book_id"]
    file_path = payload["path"]
    encoding = payload.get("encoding", "utf-8")
    chunk_size = int(payload.get("chunk_size", 900))
    overlap = int(payload.get("overlap", 120))

    await on_progress(5, "preflight", "检查文件")
    target = Path(file_path)
    if not target.exists():
        raise RuntimeError("FILE_NOT_FOUND")

    await on_progress(15, "read", "读取文本")
    raw = target.read_text(encoding=encoding)
    cleaned = raw.replace("\r\n", "\n").replace("\r", "\n")
    if cleaned.startswith("\ufeff"):
        cleaned = cleaned[1:]
    if not cleaned.strip():
        raise RuntimeError("EMPTY_CONTENT_AFTER_CLEAN")

    await on_progress(30, "structure", "拆分章节")
    await on_log("INFO", "structure", "使用最小策略，当前版本按单章处理")

    source_result = await session.execute(
        text(
            """
            INSERT INTO source(book_id, type, title, uri, meta)
            VALUES (:book_id, 'import_txt', :title, :uri, '{}'::jsonb)
            RETURNING source_id
            """
        ),
        {"book_id": book_id, "title": target.name, "uri": str(target)},
    )
    source_id = source_result.scalar_one()

    chapter_result = await session.execute(
        text(
            """
            INSERT INTO chapter(book_id, "order", title, text)
            VALUES (:book_id, 1, '正文', NULL)
            RETURNING chapter_id
            """
        ),
        {"book_id": book_id},
    )
    chapter_id = chapter_result.scalar_one()

    chunks = split_chunks(cleaned, chunk_size, overlap)
    await on_progress(45, "chunk", f"切块完成 {len(chunks)} 段")
    if not chunks:
        raise RuntimeError("NO_CHUNKS_CREATED")

    await on_progress(60, "write_db", "写入块数据")
    for idx, chunk in enumerate(chunks):
        await session.execute(
            text(
                """
                INSERT INTO chunk(book_id, source_id, chapter_id, index_in_chapter, text, fts)
                VALUES (:book_id, :source_id, :chapter_id, :idx, :text, to_tsvector('simple', :text))
                """
            ),
            {"book_id": book_id, "source_id": str(source_id), "chapter_id": str(chapter_id), "idx": idx, "text": chunk},
        )
        if idx % 200 == 0 and idx > 0:
            await on_log("INFO", "write_db", f"已写入 {idx}/{len(chunks)}")
    await session.commit()

    await on_progress(100, "done", "导入完成")
    return {
      "book_id": book_id,
      "chapters_created": 1,
      "chunks_created": len(chunks),
      "embedding_created": 0
    }
