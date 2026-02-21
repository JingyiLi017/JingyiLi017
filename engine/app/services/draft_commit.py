from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .tension import evaluate_tension_score_v1


def _norm(value: str) -> str:
    v = (value or "").strip().lower()
    v = re.sub(r"\s+", "", v)
    return v


def _split_text(text_value: str, chunk_size: int = 2200, overlap: int = 260) -> list[dict[str, Any]]:
    src = (text_value or "").strip()
    if not src:
        return []
    chunks: list[dict[str, Any]] = []
    i = 0
    n = len(src)
    while i < n:
        j = min(n, i + chunk_size)
        chunk = src[i:j]
        chunks.append({"idx": len(chunks) + 1, "start": i, "end": j, "text": chunk})
        if j >= n:
            break
        i = max(0, j - overlap)
    return chunks


def _split_sentences(text_value: str) -> list[str]:
    parts = re.split(r"[。！？!?;\n\r]+", (text_value or "").strip())
    return [p.strip() for p in parts if p and p.strip()]


def _extract_facts_from_sentences(sentences: list[str]) -> list[dict[str, Any]]:
    rules = [
        ("status", ["受伤", "重伤", "中毒", "虚弱", "失去", "死亡"]),
        ("gain", ["获得", "拿到", "得到", "发现"]),
        ("promise", ["发誓", "承诺", "约定"]),
        ("rule", ["必须", "否则", "期限", "天亮前", "倒计时"]),
        ("relation", ["背叛", "同盟", "盟友", "仇", "出卖"]),
        ("ability", ["突破", "升级", "觉醒"]),
    ]
    out: list[dict[str, Any]] = []
    for s in sentences:
        for fact_type, kws in rules:
            if any(k in s for k in kws):
                out.append(
                    {
                        "entity_type": "character",
                        "entity_name": "主角",
                        "fact_type": fact_type,
                        "fact": s[:80],
                        "evidence_span": s[:120],
                        "confidence": 0.72,
                    }
                )
                break
        if len(out) >= 20:
            break
    if not out and sentences:
        out.append(
            {
                "entity_type": "character",
                "entity_name": "主角",
                "fact_type": "status",
                "fact": sentences[0][:80],
                "evidence_span": sentences[0][:120],
                "confidence": 0.6,
            }
        )
    return out


def _extract_timeline_from_sentences(sentences: list[str]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for i, s in enumerate(sentences[:10], start=1):
        events.append(
            {
                "event_no": i,
                "time_hint": "当章",
                "location": None,
                "actors": ["主角"],
                "event": s[:120],
                "consequence": None,
            }
        )
    return events


def _extract_growth_from_sentences(sentences: list[str]) -> list[dict[str, Any]]:
    text_join = " ".join(sentences[:12])
    pressure = "高压推进"
    if "追杀" in text_join or "围堵" in text_join:
        pressure = "被追杀/围堵"
    cost = "未知代价"
    if "失去" in text_join:
        cost = "失去关键资源/关系"
    gain = "推进主线线索"
    if "获得" in text_join or "发现" in text_join:
        gain = "获得关键线索"
    return [
        {
            "character_name": "主角",
            "pressure": pressure,
            "cost": cost,
            "gain": gain,
            "change": "从被动应对转为主动布局",
            "trigger_event_no": 1,
            "confidence": 0.7,
        }
    ]


def _extract_materials_from_sentences(sentences: list[str]) -> list[dict[str, Any]]:
    if not sentences:
        return []
    samples = sentences[: min(3, len(sentences))]
    return [
        {
            "title": f"章内素材#{i}",
            "tag": "chapter_extract",
            "content": s[:200],
            "importance": 3,
        }
        for i, s in enumerate(samples, start=1)
    ]


def _fact_key(f: dict[str, Any]) -> tuple[str, str, str, str]:
    return (_norm(str(f.get("entity_type") or "")), _norm(str(f.get("entity_name") or "")), _norm(str(f.get("fact_type") or "")), _norm(str(f.get("fact") or "")))


def _merge_facts(chunks_facts: list[list[dict[str, Any]]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    best: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for fact_list in chunks_facts:
        for f in fact_list:
            k = _fact_key(f)
            if not all(k):
                continue
            if k not in best:
                best[k] = dict(f)
                continue
            old = float(best[k].get("confidence") or 0.0)
            cur = float(f.get("confidence") or 0.0)
            if cur > old:
                best[k] = dict(f)
            elif cur == old and len(str(f.get("evidence_span") or "")) < len(str(best[k].get("evidence_span") or "")):
                best[k] = dict(f)

    by_slot: dict[tuple[str, str, str], set[str]] = {}
    for f in best.values():
        slot = (_norm(str(f.get("entity_type") or "")), _norm(str(f.get("entity_name") or "")), _norm(str(f.get("fact_type") or "")))
        by_slot.setdefault(slot, set()).add(_norm(str(f.get("fact") or "")))
    flags: list[dict[str, Any]] = []
    for slot, variants in by_slot.items():
        if len(variants) >= 2:
            flags.append({"code": "FACT_CONFLICT", "severity": "mid", "detail": f"{slot} has {len(variants)} variants"})
    return list(best.values()), flags


def _event_key(e: dict[str, Any]) -> tuple[str, str, tuple[str, ...]]:
    actors = tuple(sorted([_norm(str(x)) for x in (e.get("actors") or [])]))
    return (_norm(str(e.get("event") or "")), _norm(str(e.get("location") or "")), actors)


def _merge_timeline(chunks_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # chunks_events: [{"chunk_idx":1,"events":[...]}]
    best: dict[tuple[str, str, tuple[str, ...]], dict[str, Any]] = {}
    order: dict[tuple[str, str, tuple[str, ...]], tuple[int, int]] = {}
    for ce in chunks_events:
        cidx = int(ce["chunk_idx"])
        for i, e in enumerate(ce["events"]):
            k = _event_key(e)
            if not k[0]:
                continue
            if k not in best:
                best[k] = dict(e)
                order[k] = (cidx, i)
            else:
                if len(_norm(str(e.get("event") or ""))) > len(_norm(str(best[k].get("event") or ""))):
                    best[k] = dict(e)
    keys = sorted(best.keys(), key=lambda k: order.get(k, (10**9, 10**9)))
    out: list[dict[str, Any]] = []
    for idx, k in enumerate(keys, start=1):
        e = best[k]
        out.append(
            {
                "event_no": idx,
                "time_hint": e.get("time_hint"),
                "location": e.get("location"),
                "actors": e.get("actors") or [],
                "event": str(e.get("event") or "")[:120],
                "consequence": e.get("consequence"),
            }
        )
    return out


def _pick_better_text(a: Any, b: Any, limit: int = 120) -> str:
    sa, sb = str(a or "").strip(), str(b or "").strip()
    chosen = sb if len(_norm(sb)) > len(_norm(sa)) else sa
    return chosen[:limit]


def _merge_growth(chunks_growth: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for gl in chunks_growth:
        for g in gl:
            name = _norm(str(g.get("character_name") or ""))
            if not name:
                continue
            if name not in merged:
                merged[name] = dict(g)
                continue
            cur = merged[name]
            for k in ["pressure", "cost", "gain", "change"]:
                cur[k] = _pick_better_text(cur.get(k), g.get(k))
            a = cur.get("trigger_event_no")
            b = g.get("trigger_event_no")
            if a is None:
                cur["trigger_event_no"] = b
            elif b is not None and int(b) < int(a):
                cur["trigger_event_no"] = b
            cur["confidence"] = max(float(cur.get("confidence") or 0.0), float(g.get("confidence") or 0.0))
    return list(merged.values())


async def run_commit_draft_job(session: AsyncSession, payload: dict, on_progress, on_log) -> dict:
    chapter_id = str(payload.get("chapter_id") or "")
    if not chapter_id:
        raise RuntimeError("CHAPTER_NOT_FOUND")
    writeback = dict(payload.get("writeback") or {})
    commit_txn_id = str(payload.get("commit_txn_id") or uuid4())

    row_ch = await session.execute(
        text('SELECT chapter_id, book_id, "order", title FROM chapter WHERE chapter_id=:chapter_id'),
        {"chapter_id": chapter_id},
    )
    ch = row_ch.mappings().first()
    if not ch:
        raise RuntimeError("CHAPTER_NOT_FOUND")
    book_id = str(ch["book_id"])
    chapter_no = int(ch["order"])
    chapter_title = str(ch.get("title") or "")

    stage_result: dict[str, dict[str, Any]] = {}
    profile_id_used = str(payload.get("profile_id_used") or "").strip() or None
    profile_version_used_raw = payload.get("profile_version_used")
    profile_version_used = int(profile_version_used_raw) if profile_version_used_raw is not None else None
    injected_bundle_id = str(payload.get("injected_bundle_id") or "").strip() or None
    injected_counts = payload.get("injected_counts") if isinstance(payload.get("injected_counts"), dict) else {}

    await on_progress(8, "SAVE_TEXT_VERSION", "saving chapter text version")
    text_content = str(payload.get("text_content") or "").strip()
    text_ver_id = payload.get("text_ver_id")
    if text_ver_id and not text_content:
        row_text = await session.execute(
            text("SELECT content FROM chapter_text_version WHERE text_ver_id=:text_ver_id"),
            {"text_ver_id": str(text_ver_id)},
        )
        r = row_text.mappings().first()
        if not r:
            raise RuntimeError("TEXT_VER_NOT_FOUND")
        text_content = str(r["content"] or "")
    if not text_content:
        raise RuntimeError("TEXT_CONTENT_REQUIRED")

    resolved_outline_version = int(payload.get("outline_version") or 1)
    insert_text = await session.execute(
        text(
            """
            INSERT INTO chapter_text_version(
              chapter_id, outline_version, profile_id_used, profile_version_used, meta, source, content, note
            )
            VALUES (
              :chapter_id, :outline_version, CAST(:profile_id_used AS uuid), :profile_version_used, CAST(:meta AS jsonb), 'draft', :content, :note
            )
            RETURNING text_ver_id, created_at, profile_id_used, profile_version_used
            """
        ),
        {
            "chapter_id": chapter_id,
            "outline_version": resolved_outline_version,
            "profile_id_used": profile_id_used,
            "profile_version_used": profile_version_used,
            "meta": json.dumps(
                {
                    "injected_bundle_id": injected_bundle_id,
                    "injected_counts": injected_counts,
                },
                ensure_ascii=False,
            ),
            "content": text_content,
            "note": f"commit_txn:{commit_txn_id}",
        },
    )
    created_text = dict(insert_text.mappings().one())
    saved_text_ver_id = str(created_text["text_ver_id"])
    await session.commit()
    stage_result["SAVE_TEXT_VERSION"] = {"ok": True, "rows": 1, "text_ver_id": saved_text_ver_id}
    await on_log("INFO", "SAVE_TEXT_VERSION", f"text_ver_id={saved_text_ver_id}")

    chunks = _split_text(text_content, chunk_size=2200, overlap=260)
    if not chunks:
        chunks = [{"idx": 1, "start": 0, "end": min(len(text_content), 200), "text": text_content[:200]}]

    chunk_facts: list[list[dict[str, Any]]] = []
    chunk_events: list[dict[str, Any]] = []
    chunk_growth: list[list[dict[str, Any]]] = []
    chunk_materials: list[list[dict[str, Any]]] = []
    for c in chunks:
        sents = _split_sentences(c["text"])
        if not sents and c["text"].strip():
            sents = [c["text"].strip()[:200]]
        if writeback.get("extract_facts", True):
            chunk_facts.append(_extract_facts_from_sentences(sents))
        if writeback.get("extract_timeline", True):
            chunk_events.append({"chunk_idx": c["idx"], "events": _extract_timeline_from_sentences(sents)})
        if writeback.get("extract_growth", True):
            chunk_growth.append(_extract_growth_from_sentences(sents))
        if writeback.get("extract_new_materials", True):
            chunk_materials.append(_extract_materials_from_sentences(sents))

    facts, fact_flags = _merge_facts(chunk_facts) if writeback.get("extract_facts", True) else ([], [])
    timeline = _merge_timeline(chunk_events) if writeback.get("extract_timeline", True) else []
    growth = _merge_growth(chunk_growth) if writeback.get("extract_growth", True) else []
    # material de-dup by title+content
    mat_map: dict[tuple[str, str], dict[str, Any]] = {}
    for ml in chunk_materials:
        for m in ml:
            k = (_norm(str(m.get("title") or "")), _norm(str(m.get("content") or "")))
            if k not in mat_map:
                mat_map[k] = m
    materials = list(mat_map.values())

    await on_progress(24, "EXTRACT_FACTS", "upsert chapter facts")
    if facts:
        for f in facts:
            await session.execute(
                text(
                    """
                    INSERT INTO chapter_fact(
                      book_id, chapter_id, commit_txn_id, entity_type, entity_name, fact_type,
                      fact, evidence_span, confidence
                    )
                    VALUES (
                      :book_id, :chapter_id, CAST(:commit_txn_id AS uuid), :entity_type, :entity_name, :fact_type,
                      :fact, :evidence_span, :confidence
                    )
                    ON CONFLICT (commit_txn_id, entity_type, entity_name, fact_type, fact)
                    DO UPDATE SET
                      evidence_span=EXCLUDED.evidence_span,
                      confidence=GREATEST(chapter_fact.confidence, EXCLUDED.confidence)
                    """
                ),
                {"book_id": book_id, "chapter_id": chapter_id, "commit_txn_id": commit_txn_id, **f},
            )
        await session.commit()
    stage_result["EXTRACT_FACTS"] = {"ok": True, "facts": len(facts), "flags": len(fact_flags), "risk_flags": fact_flags[:8]}
    await on_log("INFO", "EXTRACT_FACTS", f"facts={len(facts)} flags={len(fact_flags)}")

    await on_progress(38, "EXTRACT_TIMELINE", "upsert timeline events")
    if timeline:
        for e in timeline:
            await session.execute(
                text(
                    """
                    INSERT INTO chapter_timeline_event(
                      book_id, chapter_id, commit_txn_id, event_no, time_hint, location, actors, event, consequence
                    )
                    VALUES (
                      :book_id, :chapter_id, CAST(:commit_txn_id AS uuid), :event_no, :time_hint, :location, CAST(:actors AS text[]), :event, :consequence
                    )
                    ON CONFLICT (commit_txn_id, event_no)
                    DO UPDATE SET
                      time_hint=EXCLUDED.time_hint,
                      location=EXCLUDED.location,
                      actors=EXCLUDED.actors,
                      event=EXCLUDED.event,
                      consequence=EXCLUDED.consequence
                    """
                ),
                {"book_id": book_id, "chapter_id": chapter_id, "commit_txn_id": commit_txn_id, **e},
            )
        await session.commit()
    stage_result["EXTRACT_TIMELINE"] = {"ok": True, "events": len(timeline)}
    await on_log("INFO", "EXTRACT_TIMELINE", f"events={len(timeline)}")

    await on_progress(52, "EXTRACT_GROWTH", "upsert character growth")
    if growth:
        for g in growth:
            await session.execute(
                text(
                    """
                    INSERT INTO character_growth_log(
                      book_id, chapter_id, commit_txn_id, character_name, pressure, cost, gain, change, trigger_event_no, confidence
                    )
                    VALUES (
                      :book_id, :chapter_id, CAST(:commit_txn_id AS uuid), :character_name, :pressure, :cost, :gain, :change, :trigger_event_no, :confidence
                    )
                    ON CONFLICT (commit_txn_id, character_name)
                    DO UPDATE SET
                      pressure=EXCLUDED.pressure,
                      cost=EXCLUDED.cost,
                      gain=EXCLUDED.gain,
                      change=EXCLUDED.change,
                      trigger_event_no=EXCLUDED.trigger_event_no,
                      confidence=GREATEST(character_growth_log.confidence, EXCLUDED.confidence)
                    """
                ),
                {"book_id": book_id, "chapter_id": chapter_id, "commit_txn_id": commit_txn_id, **g},
            )
        await session.commit()
    stage_result["EXTRACT_GROWTH"] = {"ok": True, "rows": len(growth)}
    await on_log("INFO", "EXTRACT_GROWTH", f"rows={len(growth)}")

    await on_progress(66, "EXTRACT_NEW_MATERIALS", "insert extracted materials")
    if materials:
        for m in materials:
            await session.execute(
                text(
                    """
                    INSERT INTO material_card(book_id, source_type, title, content, tag, importance)
                    SELECT :book_id, 'chapter', :title, :content, :tag, :importance
                    WHERE NOT EXISTS (
                      SELECT 1 FROM material_card
                      WHERE book_id=:book_id AND source_type='chapter' AND title=:title AND content=:content
                    )
                    """
                ),
                {"book_id": book_id, **m},
            )
        await session.commit()
    stage_result["EXTRACT_NEW_MATERIALS"] = {"ok": True, "cards": len(materials)}
    await on_log("INFO", "EXTRACT_NEW_MATERIALS", f"cards={len(materials)}")

    await on_progress(82, "RUN_EVAL", "running chapter eval")
    eval_run_id = None
    eval_result = None
    if writeback.get("run_eval", True):
        row_outline = await session.execute(
            text(
                """
                SELECT content
                FROM outline
                WHERE chapter_id=:chapter_id AND scope='chapter'
                ORDER BY version DESC
                LIMIT 1
                """
            ),
            {"chapter_id": chapter_id},
        )
        outline_row = row_outline.mappings().first()
        outline_nodes = []
        if outline_row and isinstance(outline_row.get("content"), dict):
            outline_nodes = list((outline_row["content"] or {}).get("nodes") or [])
        eval_result = evaluate_tension_score_v1(text_content, outline_nodes)
        eval_run_id = str(uuid4())
        await session.execute(
            text(
                """
                INSERT INTO skill_run(skill_run_id, book_id, skill_name, schema_ver, output)
                VALUES (:skill_run_id, :book_id, 'EVAL_TENSION_SCORE_V1', 1, CAST(:output AS jsonb))
                """
            ),
            {"skill_run_id": eval_run_id, "book_id": book_id, "output": json.dumps(eval_result, ensure_ascii=False)},
        )
        await session.execute(
            text(
                """
                INSERT INTO chapter_tension_metrics(
                  book_id, chapter_id, chapter_no, chapter_version_id, eval_skill_run_id,
                  scores, tension_curve, issues_count, mechanics_used
                )
                VALUES (
                  :book_id, :chapter_id, :chapter_no, NULL, :eval_skill_run_id,
                  CAST(:scores AS jsonb), CAST(:curve AS real[]), :issues_count, CAST(:mechanics_used AS text[])
                )
                """
            ),
            {
                "book_id": book_id,
                "chapter_id": chapter_id,
                "chapter_no": chapter_no,
                "eval_skill_run_id": eval_run_id,
                "scores": json.dumps((eval_result.get("result") or {}).get("scores") or {}),
                "curve": (eval_result.get("result") or {}).get("tension_curve") or [0.4, 0.4, 0.4, 0.4, 0.4],
                "issues_count": len(((eval_result.get("result") or {}).get("issues") or [])),
                "mechanics_used": [],
            },
        )
        await session.commit()
    stage_result["RUN_EVAL"] = {"ok": True, "eval_run_id": eval_run_id}
    await on_log("INFO", "RUN_EVAL", f"eval_run_id={eval_run_id}")

    await on_progress(94, "WRITE_REPORT", "writing commit report")
    summary = {
        "new_facts": len(facts),
        "timeline_events": len(timeline),
        "growth_entries": len(growth),
        "new_materials": len(materials),
        "eval_overall": ((eval_result or {}).get("result") or {}).get("scores", {}).get("overall") if eval_result else None,
    }
    report_payload = {
        "chapter_id": chapter_id,
        "chapter_title": chapter_title,
        "commit_txn_id": commit_txn_id,
        "text_ver_id": saved_text_ver_id,
        "profile_id_used": profile_id_used,
        "profile_version_used": profile_version_used,
        "injected_bundle_id": injected_bundle_id,
        "injected_counts": injected_counts,
        "stages": stage_result,
        "summary": summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    rep = await session.execute(
        text(
            """
            INSERT INTO report(
              book_id, chapter_id, profile_id_used, profile_version_used, report_type, payload, html
            )
            VALUES (
              :book_id, :chapter_id, CAST(:profile_id_used AS uuid), :profile_version_used, 'draft_commit', CAST(:payload AS jsonb), :html
            )
            RETURNING report_id
            """
        ),
        {
            "book_id": book_id,
            "chapter_id": chapter_id,
            "profile_id_used": profile_id_used,
            "profile_version_used": profile_version_used,
            "payload": json.dumps(report_payload, ensure_ascii=False),
            "html": "",
        },
    )
    report_id = str(rep.scalar_one())
    await session.commit()
    stage_result["WRITE_REPORT"] = {"ok": True, "report_id": report_id}
    await on_log("INFO", "WRITE_REPORT", f"report_id={report_id}")

    await on_progress(100, "DONE", "commit completed")
    return {
        "commit_txn_id": commit_txn_id,
        "text_ver_id": saved_text_ver_id,
        "profile_id_used": profile_id_used,
        "profile_version_used": profile_version_used,
        "outline_version": resolved_outline_version,
        "stages": stage_result,
        "summary": summary,
    }
