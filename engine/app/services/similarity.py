from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from .ollama_client import OllamaClient


def segment_text(text_value: str, seg_chars: int = 600, overlap: int = 120, max_segments: int = 40) -> list[str]:
    content = (text_value or "").strip()
    out: list[str] = []
    idx = 0
    while idx < len(content) and len(out) < max_segments:
        seg = content[idx : idx + seg_chars]
        if seg.strip():
            out.append(seg)
        idx += max(1, seg_chars - overlap)
    return out


def ngrams(text_value: str, n: int) -> set[str]:
    s = (text_value or "").replace("\n", " ")
    if len(s) < n:
        return set()
    return {s[i : i + n] for i in range(len(s) - n + 1)}


def ngram_overlap_ratio(a: str, b: str, n: int = 5) -> float:
    a_set = ngrams(a, n)
    if not a_set:
        return 0.0
    b_set = ngrams(b, n)
    if not b_set:
        return 0.0
    return len(a_set.intersection(b_set)) / max(1, len(a_set))


def make_snippet(value: str, max_len: int = 140) -> str:
    compact = " ".join((value or "").split())
    return compact[:max_len] + ("..." if len(compact) > max_len else "")


def risk_level(max_vec: float, max_ng: float, vec_high: float, vec_mid: float, ng_high: float, ng_mid: float) -> str:
    if max_vec >= vec_high or max_ng >= ng_high:
        return "high"
    if max_vec >= vec_mid or max_ng >= ng_mid:
        return "mid"
    return "low"


def _normalize_sim_report(
    *,
    report: dict[str, Any],
    sim_threshold: float | None,
    scope: list[str] | None,
) -> dict[str, Any]:
    result = dict((report or {}).get("result") or {})
    value = sim_threshold if isinstance(sim_threshold, (int, float)) else result.get("sim_threshold", 0.86)
    try:
        threshold = float(value)
    except Exception:
        threshold = 0.86
    threshold = max(0.0, min(1.0, threshold))
    result["sim_threshold"] = threshold
    result["scope"] = list(scope or result.get("scope") or ["material_card"])
    result["hits"] = list(result.get("hits") or [])
    summary = dict(result.get("summary") or {})
    if result["hits"]:
        scores = [float((h or {}).get("score") or 0.0) for h in result["hits"]]
        summary["max_score"] = max(scores) if scores else 0.0
        summary["high"] = sum(1 for s in scores if s >= 0.90)
        summary["mid"] = sum(1 for s in scores if 0.86 <= s < 0.90)
        summary["low"] = sum(1 for s in scores if 0.82 <= s < 0.86)
    else:
        summary.setdefault("max_score", 0.0)
        summary.setdefault("high", 0)
        summary.setdefault("mid", 0)
        summary.setdefault("low", 0)
    result["summary"] = summary
    return {
        "schema_name": "SIM_GUARD_REPORT_V1",
        "schema_ver": 1,
        "generated_at": report.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "result": result,
        "warnings": list(report.get("warnings") or []),
    }


async def embed_texts_ollama(texts: list[str], model: str) -> list[list[float]]:
    client = OllamaClient(settings.ollama_host)
    return await client.embeddings(
        model=model,
        texts=texts,
        timeout_s=45,
        retries=1,
        meta={"job_type": "GUARD", "stage": "EMBED_SEGMENTS"},
    )


async def vector_search_topk_import(session: AsyncSession, book_id: str, qvec: list[float], top_k: int = 3) -> list[dict[str, Any]]:
    vec_sql = "[" + ",".join(str(v) for v in qvec) + "]"
    result = await session.execute(
        text(
            """
            SELECT
              c.chunk_id,
              s.source_id,
              s.title AS source_title,
              (1 - (e.embedding <=> CAST(:qvec AS vector))) AS score,
              c.text AS raw_text
            FROM chunk_embedding e
            JOIN chunk c ON c.chunk_id = e.chunk_id
            JOIN source s ON s.source_id = c.source_id
            WHERE c.book_id = :book_id
              AND s.type = 'import_txt'
            ORDER BY e.embedding <=> CAST(:qvec AS vector)
            LIMIT :top_k
            """
        ),
        {"qvec": vec_sql, "book_id": book_id, "top_k": top_k},
    )
    return [dict(r) for r in result.mappings().all()]


async def run_similarity_guard_job(session: AsyncSession, payload: dict[str, Any], on_progress, on_log) -> dict[str, Any]:
    chapter_id = str(payload["chapter_id"])
    chapter_version_id = str(payload["chapter_version_id"])
    model = payload.get("embedding_model", settings.embedding_model)
    vec_high = float(payload.get("vec_high", 0.86))
    vec_mid = float(payload.get("vec_mid", 0.80))
    ng_high = float(payload.get("ngram_high", 0.20))
    ng_mid = float(payload.get("ngram_mid", 0.12))

    await on_progress(5, "LOAD_TEXT", "读取章节文本")
    chapter_row = await session.execute(
        text("SELECT book_id FROM chapter WHERE chapter_id=:chapter_id"),
        {"chapter_id": chapter_id},
    )
    chapter_book_id = chapter_row.scalar()
    if not chapter_book_id:
        raise RuntimeError("CHAPTER_NOT_FOUND")
    reference_book_id = str(payload.get("book_id") or chapter_book_id)

    version_row = await session.execute(
        text("SELECT text FROM chapter_version WHERE chapter_version_id=:cid"),
        {"cid": chapter_version_id},
    )
    text_row = version_row.first()
    if not text_row:
        raise RuntimeError("CHAPTER_VERSION_NOT_FOUND")
    chapter_text = text_row[0] or ""
    if not chapter_text.strip():
        raise RuntimeError("EMPTY_CHAPTER_TEXT")

    segs = segment_text(chapter_text, seg_chars=600, overlap=120, max_segments=40)
    if not segs:
        raise RuntimeError("EMPTY_SEGMENTS")

    await on_progress(20, "EMBED_SEGMENTS", "分段向量化")
    max_vec = 0.0
    max_ng = 0.0
    all_hits: list[tuple[float, float, float, dict[str, Any]]] = []
    warnings: list[str] = []

    batch_size = 8
    processed = 0
    for i in range(0, len(segs), batch_size):
        batch = segs[i : i + batch_size]
        try:
            vectors = await embed_texts_ollama(batch, model=model)
        except Exception:
            warnings.append("embedding_unavailable")
            break

        await on_progress(35 + int(50 * ((i + len(batch)) / max(1, len(segs)))), "VECTOR_SEARCH", "检索拆书来源")
        for seg_text, vec in zip(batch, vectors):
            hits = await vector_search_topk_import(session, reference_book_id, vec, top_k=3)
            for hit in hits:
                vec_score = float(hit.get("score") or 0.0)
                ng_score = ngram_overlap_ratio(seg_text, str(hit.get("raw_text") or ""), n=5)
                max_vec = max(max_vec, vec_score)
                max_ng = max(max_ng, ng_score)
                combo = vec_score * 0.7 + ng_score * 0.3
                all_hits.append((combo, vec_score, ng_score, hit))
        processed += len(batch)
        await on_log("INFO", "VECTOR_SEARCH", f"segments_done={processed}/{len(segs)}")

    all_hits.sort(key=lambda x: x[0], reverse=True)
    top_hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, vec_score, _ng_score, hit in all_hits:
        chunk_id = str(hit.get("chunk_id"))
        if not chunk_id or chunk_id in seen:
            continue
        seen.add(chunk_id)
        top_hits.append(
            {
                "chunk_id": chunk_id,
                "score": round(vec_score, 4),
                "snippet": make_snippet(str(hit.get("raw_text") or ""), 140),
            }
        )
        if len(top_hits) >= 5:
            break

    await on_progress(88, "RISK_DECISION", "判定风险等级")
    level = risk_level(max_vec, max_ng, vec_high, vec_mid, ng_high, ng_mid)
    suggest = {
        "rewrite_mode": "reduce_similarity" if level in ("mid", "high") else "de_ai_smell",
        "strength": 0.75 if level == "high" else (0.55 if level == "mid" else 0.35),
    }

    output = {
        "schema_name": "SIMILARITY_GUARD",
        "schema_ver": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": {
            "risk_level": level,
            "max_vec_score": round(max_vec, 4),
            "max_ngram_overlap": round(max_ng, 4),
            "top_hits": top_hits,
            "suggest": suggest,
        },
        "warnings": warnings,
    }
    output = _normalize_sim_report(report=output, sim_threshold=vec_mid, scope=["splitbook_chunk"])

    await on_progress(95, "SAVE_SKILL_RUN", "写入结果")
    saved = await session.execute(
        text(
            """
            INSERT INTO skill_run(book_id, skill_name, schema_ver, output)
            VALUES (:book_id, 'SIMILARITY_GUARD_V1', 1, CAST(:output AS jsonb))
            RETURNING skill_run_id
            """
        ),
        {"book_id": str(chapter_book_id), "output": json.dumps(output)},
    )
    skill_run_id = str(saved.scalar_one())
    await session.commit()
    await on_log("INFO", "DONE", "similarity guard 完成")
    await on_progress(100, "DONE", "完成")
    return {"skill_run_id": skill_run_id, "risk_level": level, "max_vec_score": round(max_vec, 4), "report": output}


async def _vector_search_topk_material(session: AsyncSession, book_id: str, qvec: list[float], top_k: int = 5) -> list[dict[str, Any]]:
    vec_sql = "[" + ",".join(str(v) for v in qvec) + "]"
    result = await session.execute(
        text(
            """
            SELECT
              c.card_id::text AS source_id,
              'material_card'::text AS source_type,
              c.title AS source_title,
              c.content AS raw_text,
              (1 - (e.embedding <=> CAST(:qvec AS vector))) AS score
            FROM material_card c
            JOIN material_embedding e ON e.card_id = c.card_id
            WHERE (:book_id = '' OR c.book_id = CAST(:book_id AS uuid))
            ORDER BY e.embedding <=> CAST(:qvec AS vector)
            LIMIT :top_k
            """
        ),
        {"qvec": vec_sql, "book_id": book_id, "top_k": top_k},
    )
    return [dict(r) for r in result.mappings().all()]


async def _vector_search_topk_splitbook(session: AsyncSession, book_id: str, qvec: list[float], top_k: int = 5) -> list[dict[str, Any]]:
    vec_sql = "[" + ",".join(str(v) for v in qvec) + "]"
    result = await session.execute(
        text(
            """
            SELECT
              c.chunk_id::text AS source_id,
              'splitbook_chunk'::text AS source_type,
              s.title AS source_title,
              c.text AS raw_text,
              (1 - (e.embedding <=> CAST(:qvec AS vector))) AS score
            FROM chunk_embedding e
            JOIN chunk c ON c.chunk_id = e.chunk_id
            LEFT JOIN source s ON s.source_id = c.source_id
            WHERE c.book_id = CAST(:book_id AS uuid)
            ORDER BY e.embedding <=> CAST(:qvec AS vector)
            LIMIT :top_k
            """
        ),
        {"qvec": vec_sql, "book_id": book_id, "top_k": top_k},
    )
    return [dict(r) for r in result.mappings().all()]


async def run_similarity_guard_text_job(session: AsyncSession, payload: dict[str, Any], on_progress, on_log) -> dict[str, Any]:
    chapter_id = str(payload["chapter_id"])
    row_ch = await session.execute(text("SELECT book_id FROM chapter WHERE chapter_id=:chapter_id"), {"chapter_id": chapter_id})
    ch_book_id = row_ch.scalar()
    if not ch_book_id:
        raise RuntimeError("CHAPTER_NOT_FOUND")
    book_id = str(ch_book_id)

    text_ver_id = payload.get("text_ver_id")
    text_value = ""
    if text_ver_id:
        row_text = await session.execute(
            text("SELECT content FROM chapter_text_version WHERE text_ver_id=:text_ver_id AND chapter_id=:chapter_id"),
            {"text_ver_id": str(text_ver_id), "chapter_id": chapter_id},
        )
        r = row_text.mappings().first()
        if not r:
            raise RuntimeError("TEXT_VER_NOT_FOUND")
        text_value = str(r["content"] or "")
    else:
        row_text = await session.execute(
            text(
                """
                SELECT content, text_ver_id
                FROM chapter_text_version
                WHERE chapter_id=:chapter_id
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"chapter_id": chapter_id},
        )
        r = row_text.mappings().first()
        if not r:
            raise RuntimeError("TEXT_VER_NOT_FOUND")
        text_value = str(r["content"] or "")
        text_ver_id = str(r["text_ver_id"])

    if not text_value.strip():
        raise RuntimeError("EMPTY_CHAPTER_TEXT")

    model = str(payload.get("embedding_model") or settings.embedding_model)
    top_k = max(1, min(int(payload.get("top_k", 5)), 20))
    sim_threshold = float(payload.get("sim_threshold", 0.86))
    scope = [str(x) for x in (payload.get("scope") or ["material_card", "splitbook_chunk"])]

    await on_progress(8, "LOAD_TEXT", "加载文本")
    segments = segment_text(text_value, seg_chars=320, overlap=80, max_segments=60)
    if not segments:
        raise RuntimeError("EMPTY_SEGMENTS")

    await on_progress(20, "EMBED_SEGMENTS", "分段向量化")
    vectors = await embed_texts_ollama(segments, model=model)
    hits: list[dict[str, Any]] = []
    for idx, (seg, vec) in enumerate(zip(segments, vectors), start=1):
        chunk_hits: list[dict[str, Any]] = []
        if "material_card" in scope:
            chunk_hits.extend(await _vector_search_topk_material(session, book_id, vec, top_k=top_k))
        if "splitbook_chunk" in scope:
            chunk_hits.extend(await _vector_search_topk_splitbook(session, book_id, vec, top_k=top_k))
        chunk_hits.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
        for rank, h in enumerate(chunk_hits[:2], start=1):
            score = float(h.get("score") or 0.0)
            if score < 0.82:
                continue
            risk = "high" if score >= 0.90 else ("mid" if score >= 0.86 else "low")
            excerpt = make_snippet(seg, 180)
            source_excerpt = make_snippet(str(h.get("raw_text") or ""), 180)
            hits.append(
                {
                    "rank": rank,
                    "risk": risk,
                    "score": round(score, 4),
                    "source_type": str(h.get("source_type") or ""),
                    "source_id": str(h.get("source_id") or ""),
                    "source_title": str(h.get("source_title") or ""),
                    "chapter_span": {"start_char": (idx - 1) * 240, "end_char": (idx - 1) * 240 + len(seg), "excerpt": excerpt},
                    "source_excerpt": source_excerpt,
                    "rewrite_actions": [
                        "改写句式与节奏",
                        "替换标志性措辞",
                        "改变叙事顺序",
                    ],
                }
            )
        await on_log("INFO", "VECTOR_SEARCH", f"segment={idx}/{len(segments)} hits={len(chunk_hits)}")

    # de-dup by source + excerpt and keep top-N
    uniq: dict[tuple[str, str], dict[str, Any]] = {}
    for h in hits:
        k = (h["source_id"], h["chapter_span"]["excerpt"])
        if k not in uniq or float(h["score"]) > float(uniq[k]["score"]):
            uniq[k] = h
    final_hits = sorted(uniq.values(), key=lambda x: float(x["score"]), reverse=True)[:20]
    report = _normalize_sim_report(
        report={
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "result": {
                "sim_threshold": sim_threshold,
                "scope": scope,
                "text_hash": f"len:{len(text_value)}",
                "hits": final_hits,
            },
            "warnings": [],
        },
        sim_threshold=sim_threshold,
        scope=scope,
    )
    if "sim_threshold" not in ((report.get("result") or {})):
        report.setdefault("warnings", []).append("SIM_THRESHOLD_DEFAULTED")

    await on_progress(92, "SAVE_SKILL_RUN", "保存结果")
    saved = await session.execute(
        text(
            """
            INSERT INTO skill_run(book_id, skill_name, schema_ver, output)
            VALUES (:book_id, 'SIM_GUARD_REPORT_V1', 1, CAST(:output AS jsonb))
            RETURNING skill_run_id
            """
        ),
        {"book_id": book_id, "output": json.dumps(report, ensure_ascii=False)},
    )
    skill_run_id = str(saved.scalar_one())
    await session.commit()

    await on_progress(100, "DONE", "完成")
    return {
        "skill_run_id": skill_run_id,
        "text_ver_id": str(text_ver_id),
        "report": report,
    }
