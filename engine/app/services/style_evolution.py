from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha1
from statistics import mean
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .storage import create_skill_run, get_profile, set_book_settings, update_profile


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _clip01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _bucket_sentence_len(avg_len: float) -> str:
    if avg_len <= 18.0:
        return "short"
    if avg_len >= 34.0:
        return "long"
    return "mix"


def _pace_hint(short_sentence_ratio: float) -> str:
    if short_sentence_ratio >= 0.58:
        return "rapid"
    if short_sentence_ratio <= 0.25:
        return "steady"
    return "balanced"


def _merge_guidance(existing: list[str], generated: list[str], limit: int = 24) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for line in [*(existing or []), *(generated or [])]:
        txt = str(line or "").strip()
        if not txt:
            continue
        key = re.sub(r"\s+", " ", txt)
        if key in seen:
            continue
        seen.add(key)
        merged.append(txt)
        if len(merged) >= limit:
            break
    return merged


def _extract_text_metrics(text_value: str) -> dict[str, float]:
    txt = str(text_value or "").strip()
    if not txt:
        return {
            "char_len": 0.0,
            "sentence_avg_len": 0.0,
            "short_sentence_ratio": 0.0,
            "dialogue_ratio": 0.0,
            "question_ratio": 0.0,
            "exclamation_ratio": 0.0,
            "first_person_ratio": 0.0,
            "paragraph_avg_sentences": 0.0,
        }
    sentences = [seg.strip() for seg in re.split(r"[。！？!?]", txt) if seg.strip()]
    sentence_lens = [len(seg) for seg in sentences]
    sent_count = len(sentence_lens)
    avg_len = (sum(sentence_lens) / sent_count) if sent_count else 0.0
    short_ratio = (sum(1 for value in sentence_lens if value <= 12) / sent_count) if sent_count else 0.0
    dialog_marks = len(re.findall(r"[“”\"「」『』]", txt))
    question_marks = txt.count("？") + txt.count("?")
    exclamation_marks = txt.count("！") + txt.count("!")
    paragraphs = [p for p in txt.splitlines() if p.strip()]
    return {
        "char_len": float(len(txt)),
        "sentence_avg_len": float(avg_len),
        "short_sentence_ratio": float(short_ratio),
        "dialogue_ratio": float(dialog_marks / max(1, len(txt))),
        "question_ratio": float(question_marks / max(1, sent_count)),
        "exclamation_ratio": float(exclamation_marks / max(1, sent_count)),
        "first_person_ratio": float(txt.count("我") / max(1, len(txt))),
        "paragraph_avg_sentences": float(sent_count / max(1, len(paragraphs))),
    }


def _aggregate_metrics(items: list[dict[str, float]]) -> dict[str, float]:
    if not items:
        return _extract_text_metrics("")
    total_chars = sum(max(1.0, _to_float(item.get("char_len"), 1.0)) for item in items)
    weighted = {}
    for key in (
        "sentence_avg_len",
        "short_sentence_ratio",
        "dialogue_ratio",
        "question_ratio",
        "exclamation_ratio",
        "first_person_ratio",
        "paragraph_avg_sentences",
    ):
        weighted[key] = sum(_to_float(item.get(key)) * max(1.0, _to_float(item.get("char_len"), 1.0)) for item in items) / total_chars
    weighted["char_len"] = float(total_chars)
    return weighted


def _build_guidance(
    *,
    metrics: dict[str, float],
    repair_stats: dict[str, Any],
    report_stats: dict[str, Any],
) -> tuple[list[str], list[str]]:
    dos: list[str] = []
    donts: list[str] = []
    dialog_ratio = _to_float(metrics.get("dialogue_ratio"))
    avg_len = _to_float(metrics.get("sentence_avg_len"))
    short_ratio = _to_float(metrics.get("short_sentence_ratio"))
    question_ratio = _to_float(metrics.get("question_ratio"))
    reversal_gain = _to_float(repair_stats.get("mean_reversal_delta"))
    cost_gain = _to_float(repair_stats.get("mean_cost_delta"))
    warn_ratio = _to_float(report_stats.get("warn_ratio"))
    fail_ratio = _to_float(report_stats.get("fail_ratio"))

    if dialog_ratio < 0.06:
        dos.append("关键冲突场景增加双向对白，避免纯叙述推进。")
    if avg_len > 32:
        dos.append("动作与冲突段优先短句，提升推进速度。")
    if question_ratio < 0.08:
        dos.append("章末保留一个明确问题钩子，驱动下一章目标。")
    if reversal_gain >= 0.06:
        dos.append("保留中段偏转机制：每章至少一次预期反差。")
    if cost_gain >= 0.06:
        dos.append("强化代价显性化：关键收益要同步给出压力与损耗。")
    if warn_ratio >= 0.3:
        dos.append("生成前先检索最近体检问题，优先修复重复告警。")

    if short_ratio > 0.72:
        donts.append("避免连续短句堆叠超过四句，防止节奏单一。")
    if dialog_ratio > 0.22:
        donts.append("避免对白过密导致信息重复，保留叙述层证据。")
    if fail_ratio >= 0.25:
        donts.append("禁止跳过时间锚点与设定约束，先过体检再发布。")
    if avg_len < 11:
        donts.append("避免全章碎句化，关键情绪段保留完整长句。")
    return dos, donts


async def _resolve_profile_id(session: AsyncSession, book_id: str, profile_id: str | None) -> str:
    if profile_id:
        return profile_id
    row = await session.execute(
        text(
            """
            SELECT b.profile_id::text AS profile_id
            FROM book b
            WHERE b.book_id=CAST(:book_id AS uuid)
            LIMIT 1
            """
        ),
        {"book_id": book_id},
    )
    hit = row.mappings().first()
    pid = str(hit.get("profile_id") or "") if hit else ""
    if pid:
        return pid
    link = await session.execute(
        text(
            """
            SELECT profile_id::text AS profile_id
            FROM book_profile_link
            WHERE book_id=CAST(:book_id AS uuid)
            ORDER BY CASE WHEN role='main' THEN 0 ELSE 1 END, created_at DESC
            LIMIT 1
            """
        ),
        {"book_id": book_id},
    )
    link_hit = link.mappings().first()
    pid2 = str(link_hit.get("profile_id") or "") if link_hit else ""
    if not pid2:
        raise RuntimeError("PROFILE_NOT_FOUND")
    return pid2


async def _load_text_samples(session: AsyncSession, *, book_id: str, sample_limit: int) -> tuple[list[dict[str, Any]], list[str]]:
    selected_res = await session.execute(
        text(
            """
            SELECT
              cd.draft_id::text AS sample_id,
              'selected_draft'::text AS source_type,
              cd.text AS content,
              cs.selected_at AS ts
            FROM chapter_selected cs
            JOIN chapter_draft cd ON cd.draft_id=cs.selected_draft_id
            JOIN chapter c ON c.chapter_id=cs.chapter_id
            WHERE c.book_id=CAST(:book_id AS uuid)
            ORDER BY cs.selected_at DESC
            LIMIT :limit
            """
        ),
        {"book_id": book_id, "limit": max(6, min(int(sample_limit), 200))},
    )
    selected_rows = [dict(r) for r in selected_res.mappings().all()]
    text_ver_res = await session.execute(
        text(
            """
            SELECT
              tv.text_ver_id::text AS sample_id,
              'text_version'::text AS source_type,
              tv.content AS content,
              tv.created_at AS ts
            FROM chapter_text_version tv
            JOIN chapter c ON c.chapter_id=tv.chapter_id
            WHERE c.book_id=CAST(:book_id AS uuid)
            ORDER BY tv.created_at DESC
            LIMIT :limit
            """
        ),
        {"book_id": book_id, "limit": max(6, min(int(sample_limit), 200))},
    )
    text_rows = [dict(r) for r in text_ver_res.mappings().all()]
    merged_rows = sorted([*selected_rows, *text_rows], key=lambda row: str(row.get("ts") or ""), reverse=True)
    picked: list[dict[str, Any]] = []
    seen_text_fp: set[str] = set()
    source_text_ver_ids: list[str] = []
    for row in merged_rows:
        content = str(row.get("content") or "").strip()
        if len(content) < 80:
            continue
        fp = sha1(content.encode("utf-8", errors="ignore")).hexdigest()
        if fp in seen_text_fp:
            continue
        seen_text_fp.add(fp)
        picked.append(
            {
                "sample_id": str(row.get("sample_id") or ""),
                "source_type": str(row.get("source_type") or "unknown"),
                "content": content,
            }
        )
        if str(row.get("source_type") or "") == "text_version":
            source_text_ver_ids.append(str(row.get("sample_id") or ""))
        if len(picked) >= sample_limit:
            break
    return picked, source_text_ver_ids


async def _load_repair_stats(session: AsyncSession, *, book_id: str, limit: int = 240) -> dict[str, Any]:
    res = await session.execute(
        text(
            """
            SELECT applied_mechanics, delta
            FROM repair_effect_sample
            WHERE book_id=CAST(:book_id AS uuid)
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"book_id": book_id, "limit": max(20, min(limit, 1000))},
    )
    rows = [dict(r) for r in res.mappings().all()]
    if not rows:
        return {
            "sample_count": 0,
            "mean_overall_delta": 0.0,
            "mean_cost_delta": 0.0,
            "mean_reversal_delta": 0.0,
            "top_mechanics": [],
        }
    overall_deltas: list[float] = []
    cost_deltas: list[float] = []
    reversal_deltas: list[float] = []
    mechanic_counter: Counter[str] = Counter()
    for row in rows:
        delta = row.get("delta") if isinstance(row.get("delta"), dict) else {}
        overall_deltas.append(_to_float((delta or {}).get("overall")))
        cost_deltas.append(_to_float((delta or {}).get("cost")))
        reversal_deltas.append(_to_float((delta or {}).get("reversal")))
        mechanics = row.get("applied_mechanics") if isinstance(row.get("applied_mechanics"), list) else []
        for mechanic in mechanics:
            name = str(mechanic or "").strip()
            if name:
                mechanic_counter[name] += 1
    top_mechanics = [{"name": name, "count": int(count)} for name, count in mechanic_counter.most_common(6)]
    return {
        "sample_count": len(rows),
        "mean_overall_delta": round(mean(overall_deltas), 4),
        "mean_cost_delta": round(mean(cost_deltas), 4),
        "mean_reversal_delta": round(mean(reversal_deltas), 4),
        "top_mechanics": top_mechanics,
    }


async def _load_report_stats(session: AsyncSession, *, book_id: str, limit: int = 120) -> dict[str, Any]:
    res = await session.execute(
        text(
            """
            SELECT report_type, payload
            FROM report
            WHERE book_id=CAST(:book_id AS uuid)
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"book_id": book_id, "limit": max(20, min(limit, 1000))},
    )
    rows = [dict(r) for r in res.mappings().all()]
    if not rows:
        return {"sample_count": 0, "warn_ratio": 0.0, "fail_ratio": 0.0, "top_issue_tags": []}
    warn_count = 0
    fail_count = 0
    issue_counter: Counter[str] = Counter()
    for row in rows:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        overall = str(summary.get("overall") or "").strip().upper()
        if overall == "WARN":
            warn_count += 1
        elif overall == "FAIL":
            fail_count += 1
        issues = payload.get("issues") if isinstance(payload.get("issues"), list) else []
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            tag = str(issue.get("type") or issue.get("kind") or issue.get("code") or "").strip().lower()
            if tag:
                issue_counter[tag] += 1
    n = max(1, len(rows))
    return {
        "sample_count": len(rows),
        "warn_ratio": round(warn_count / n, 4),
        "fail_ratio": round(fail_count / n, 4),
        "top_issue_tags": [{"tag": name, "count": int(count)} for name, count in issue_counter.most_common(8)],
    }


def _smooth(old_value: float | None, new_value: float, alpha: float) -> float:
    if old_value is None:
        return new_value
    return old_value * (1.0 - alpha) + new_value * alpha


async def evolve_book_style(
    session: AsyncSession,
    *,
    book_id: str,
    profile_id: str | None = None,
    sample_limit: int = 24,
    min_sample_count: int = 6,
    alpha: float = 0.58,
    force: bool = False,
    sync_book_settings: bool = True,
    note: str | None = None,
) -> dict[str, Any]:
    row = await session.execute(
        text("SELECT book_id::text AS book_id, title FROM book WHERE book_id=CAST(:book_id AS uuid) LIMIT 1"),
        {"book_id": book_id},
    )
    book_hit = row.mappings().first()
    if not book_hit:
        raise RuntimeError("BOOK_NOT_FOUND")

    resolved_profile_id = await _resolve_profile_id(session, book_id, profile_id)
    profile = await get_profile(session, resolved_profile_id)
    if not profile:
        raise RuntimeError("PROFILE_NOT_FOUND")

    samples, source_text_ver_ids = await _load_text_samples(
        session,
        book_id=book_id,
        sample_limit=max(6, min(int(sample_limit), 120)),
    )
    sample_count = len(samples)
    if sample_count < max(3, int(min_sample_count)) and not force:
        return {
            "ok": True,
            "updated": False,
            "skipped": True,
            "reason": "INSUFFICIENT_SAMPLES",
            "book_id": book_id,
            "profile_id": resolved_profile_id,
            "sample_count": sample_count,
            "min_sample_count": int(min_sample_count),
        }

    metrics_rows = [_extract_text_metrics(str(item.get("content") or "")) for item in samples]
    metrics = _aggregate_metrics(metrics_rows)
    repair_stats = await _load_repair_stats(session, book_id=book_id)
    report_stats = await _load_report_stats(session, book_id=book_id)

    features_old = profile.get("features") if isinstance(profile.get("features"), dict) else {}
    old_dialogue = _to_float(features_old.get("dialogue_ratio"), default=0.0) if "dialogue_ratio" in features_old else None
    old_avg_len = _to_float(features_old.get("style_evolution", {}).get("sentence_avg_len")) if isinstance(features_old.get("style_evolution"), dict) else None
    new_dialogue = _clip01(_to_float(metrics.get("dialogue_ratio")))
    new_avg_len = max(0.0, _to_float(metrics.get("sentence_avg_len")))
    alpha_eff = max(0.1, min(float(alpha), 1.0))
    smooth_dialogue = round(_clip01(_smooth(old_dialogue, new_dialogue, alpha_eff)), 4)
    smooth_avg_len = round(max(0.0, _smooth(old_avg_len, new_avg_len, alpha_eff)), 2)

    old_bucket = str(features_old.get("avg_sentence_len") or "")
    new_bucket = _bucket_sentence_len(smooth_avg_len)
    old_evo = features_old.get("style_evolution") if isinstance(features_old.get("style_evolution"), dict) else {}
    next_iteration = int(old_evo.get("iteration") or 0) + 1

    if not force:
        delta_dialogue = abs(smooth_dialogue - _to_float(old_dialogue))
        delta_avg = abs(smooth_avg_len - _to_float(old_avg_len))
        if delta_dialogue < 0.006 and delta_avg < 0.6 and old_bucket == new_bucket and sample_count < (min_sample_count + 4):
            return {
                "ok": True,
                "updated": False,
                "skipped": True,
                "reason": "NO_SIGNIFICANT_DELTA",
                "book_id": book_id,
                "profile_id": resolved_profile_id,
                "sample_count": sample_count,
                "metrics": {
                    "dialogue_ratio": smooth_dialogue,
                    "sentence_avg_len": smooth_avg_len,
                    "bucket": new_bucket,
                },
            }

    dos_old = profile.get("dos") if isinstance(profile.get("dos"), list) else []
    donts_old = profile.get("donts") if isinstance(profile.get("donts"), list) else []
    dos_add, donts_add = _build_guidance(metrics=metrics, repair_stats=repair_stats, report_stats=report_stats)
    dos_new = _merge_guidance(dos_old, dos_add)
    donts_new = _merge_guidance(donts_old, donts_add)

    generated_at = datetime.now(timezone.utc).isoformat()
    features_new = dict(features_old)
    features_new.update(
        {
            "avg_sentence_len": new_bucket,
            "dialogue_ratio": smooth_dialogue,
            "pace_hint": _pace_hint(_to_float(metrics.get("short_sentence_ratio"))),
            "learn_sample_count": sample_count,
            "style_evolution": {
                "iteration": next_iteration,
                "last_run_at": generated_at,
                "sample_count": sample_count,
                "sample_window": int(sample_limit),
                "sentence_avg_len": smooth_avg_len,
                "short_sentence_ratio": round(_clip01(_to_float(metrics.get("short_sentence_ratio"))), 4),
                "dialogue_ratio": smooth_dialogue,
                "question_ratio": round(_clip01(_to_float(metrics.get("question_ratio"))), 4),
                "exclamation_ratio": round(_clip01(_to_float(metrics.get("exclamation_ratio"))), 4),
                "first_person_ratio": round(_clip01(_to_float(metrics.get("first_person_ratio"))), 4),
                "paragraph_avg_sentences": round(max(0.0, _to_float(metrics.get("paragraph_avg_sentences"))), 3),
                "repair_feedback": repair_stats,
                "report_feedback": report_stats,
            },
        }
    )

    updated = await update_profile(
        session,
        resolved_profile_id,
        features=features_new,
        dos=dos_new,
        donts=donts_new,
        create_version=True,
        version_action="evolve_auto",
        version_note=(note or "").strip() or f"auto evolve from {sample_count} samples",
        version_actor="style_evolution_agent",
        source_text_ver_ids=source_text_ver_ids,
    )
    if not updated:
        raise RuntimeError("PROFILE_UPDATE_FAILED")
    new_version = int(updated.get("active_version") or 1)

    settings_patch: dict[str, Any] = {}
    if sync_book_settings:
        settings_patch = {
            "draft": {
                "style_profile": {
                    "profile_id": resolved_profile_id,
                    "profile_version": new_version,
                    "name": str(updated.get("name") or ""),
                    "updated_at": generated_at,
                    "features": {
                        "avg_sentence_len": features_new.get("avg_sentence_len"),
                        "dialogue_ratio": features_new.get("dialogue_ratio"),
                        "pace_hint": features_new.get("pace_hint"),
                        "question_ratio": (features_new.get("style_evolution") or {}).get("question_ratio"),
                    },
                },
                "style_evolution": {
                    "enabled": True,
                    "last_run_at": generated_at,
                    "last_profile_version": new_version,
                    "sample_count": sample_count,
                    "iteration": next_iteration,
                },
            }
        }
        await set_book_settings(session, book_id, settings_patch)

    output = {
        "schema_name": "STYLE_EVOLUTION_RESULT",
        "schema_ver": 1,
        "generated_at": generated_at,
        "book_id": book_id,
        "book_title": str(book_hit.get("title") or ""),
        "profile_id": resolved_profile_id,
        "result": {
            "updated": True,
            "sample_count": sample_count,
            "sample_limit": int(sample_limit),
            "profile_version_before": int(profile.get("active_version") or 1),
            "profile_version_after": new_version,
            "metrics": {
                "sentence_avg_len": smooth_avg_len,
                "avg_sentence_len_bucket": new_bucket,
                "dialogue_ratio": smooth_dialogue,
                "short_sentence_ratio": round(_clip01(_to_float(metrics.get("short_sentence_ratio"))), 4),
                "question_ratio": round(_clip01(_to_float(metrics.get("question_ratio"))), 4),
                "exclamation_ratio": round(_clip01(_to_float(metrics.get("exclamation_ratio"))), 4),
                "first_person_ratio": round(_clip01(_to_float(metrics.get("first_person_ratio"))), 4),
                "paragraph_avg_sentences": round(max(0.0, _to_float(metrics.get("paragraph_avg_sentences"))), 3),
            },
            "repair_feedback": repair_stats,
            "report_feedback": report_stats,
            "guidance_delta": {
                "dos_added": [item for item in dos_new if item not in dos_old],
                "donts_added": [item for item in donts_new if item not in donts_old],
            },
            "settings_synced": bool(sync_book_settings),
        },
    }

    skill_run = await create_skill_run(
        session,
        book_id=book_id,
        skill_name="STYLE_EVOLVE_V1",
        schema_ver=1,
        output=output,
    )
    return {
        "ok": True,
        "updated": True,
        "skipped": False,
        "book_id": book_id,
        "profile_id": resolved_profile_id,
        "profile_version": new_version,
        "skill_run_id": str(skill_run.get("skill_run_id")),
        "output": output,
        "settings_patch": settings_patch,
    }


async def get_latest_style_evolution(session: AsyncSession, *, book_id: str) -> dict[str, Any] | None:
    row = await session.execute(
        text(
            """
            SELECT skill_run_id::text AS skill_run_id, skill_name, schema_ver, output, created_at
            FROM skill_run
            WHERE book_id=CAST(:book_id AS uuid) AND skill_name='STYLE_EVOLVE_V1'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"book_id": book_id},
    )
    hit = row.mappings().first()
    return dict(hit) if hit else None
