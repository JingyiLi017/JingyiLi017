from __future__ import annotations

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from .ollama_client import OllamaClient


def snippet(value: str, max_len: int = 180) -> str:
    line = " ".join((value or "").split())
    return line[:max_len] + ("..." if len(line) > max_len else "")


async def search_chunks(session: AsyncSession, query: str, book_id: str, top_k: int) -> list[dict]:
    return await hybrid_search(session, query, book_id, top_k, False, 0.7, 0.3)


async def embed_query(query: str) -> list[float] | None:
    try:
        client = OllamaClient(settings.ollama_host)
        vecs = await client.embeddings(
            model=settings.embedding_model,
            texts=[query],
            timeout_s=30,
            retries=1,
            meta={"job_type": "SEARCH", "stage": "EMBED_QUERY"},
        )
        return vecs[0] if vecs else None
    except Exception:
        return None


async def hybrid_search(
    session: AsyncSession,
    query: str,
    book_id: str,
    top_k: int,
    hybrid: bool,
    vector_weight: float,
    keyword_weight: float,
) -> list[dict]:
    fts_query = "plainto_tsquery('simple', :query)"
    if hybrid:
        qvec = await embed_query(query)
        if qvec:
            result = await session.execute(
                text(
                    f"""
                    SELECT
                      c.chunk_id,
                      c.chapter_id,
                      ch."order" AS chapter_order,
                      c.text,
                      (1 - (e.embedding <=> CAST(:qvec AS vector))) AS vec_score,
                      ts_rank(c.fts, {fts_query}) AS fts_score,
                      (
                        :vector_weight * (1 - (e.embedding <=> CAST(:qvec AS vector))) +
                        :keyword_weight * ts_rank(c.fts, {fts_query})
                      ) AS final_score
                    FROM chunk c
                    LEFT JOIN chunk_embedding e ON e.chunk_id = c.chunk_id
                    LEFT JOIN chapter ch ON ch.chapter_id = c.chapter_id
                    WHERE c.book_id = :book_id
                    ORDER BY final_score DESC NULLS LAST
                    LIMIT :top_k
                    """
                ),
                {
                    "book_id": book_id,
                    "query": query,
                    "top_k": top_k,
                    "vector_weight": vector_weight,
                    "keyword_weight": keyword_weight,
                    "qvec": "[" + ",".join(str(x) for x in qvec) + "]",
                },
            )
            rows = result.mappings().all()
            return [
                {
                    "chunk_id": row["chunk_id"],
                    "chapter_id": row["chapter_id"],
                    "chapter_order": row["chapter_order"],
                    "score": float(row["final_score"] or 0),
                    "snippet": snippet(row["text"]),
                }
                for row in rows
            ]

    # fallback: keyword only
    result = await session.execute(
        text(
            f"""
            SELECT
              c.chunk_id,
              c.chapter_id,
              ch."order" AS chapter_order,
              c.text,
              ts_rank(c.fts, {fts_query}) AS final_score
            FROM chunk c
            LEFT JOIN chapter ch ON ch.chapter_id = c.chapter_id
            WHERE c.book_id = :book_id
              AND (c.fts @@ {fts_query} OR c.text ILIKE :contains)
            ORDER BY final_score DESC, c.created_at DESC
            LIMIT :top_k
            """
        ),
        {"book_id": book_id, "query": query, "contains": f"%{query}%", "top_k": top_k},
    )
    rows = result.mappings().all()
    return [
        {
            "chunk_id": row["chunk_id"],
            "chapter_id": row["chapter_id"],
            "chapter_order": row["chapter_order"],
            "score": float(row["final_score"] or 0),
            "snippet": snippet(row["text"]),
        }
        for row in rows
    ]
