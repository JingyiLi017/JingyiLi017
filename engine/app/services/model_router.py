from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings


MODEL_ROUTER_SCHEMA_VERSION = "model_router_v1"


TASK_PROFILE_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "stable_json": {
        "label": "抽取/校验",
        "required_tags": {"json", "stable"},
        "json_guard_required": True,
    },
    "reasoning": {
        "label": "配对裁决",
        "required_tags": {"reasoning"},
        "json_guard_required": False,
    },
    "expressive": {
        "label": "正文创作",
        "required_tags": {"prose", "expressive"},
        "json_guard_required": False,
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(raw: Any, default: float = 0.0) -> float:
    try:
        return float(raw)
    except Exception:
        return default


def _safe_bool(raw: Any, default: bool = False) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return default
    txt = str(raw).strip().lower()
    if txt in {"1", "true", "yes", "on"}:
        return True
    if txt in {"0", "false", "no", "off"}:
        return False
    return default


def _safe_json_list(raw: Any) -> list[Any]:
    return raw if isinstance(raw, list) else []


def _normalize_task_profile(task_type: str, payload: dict[str, Any]) -> str:
    preferred = str(payload.get("task_profile") or payload.get("profile") or "").strip().lower()
    if preferred in TASK_PROFILE_REQUIREMENTS:
        return preferred
    txt = str(task_type or "").strip().lower()
    if any(key in txt for key in ["extract", "parse", "json", "fact", "validate", "audit", "consistency", "校验", "事实"]):
        return "stable_json"
    if any(key in txt for key in ["judge", "rerank", "pair", "arbiter", "reason", "裁决", "评估"]):
        return "reasoning"
    if any(key in txt for key in ["write", "draft", "rewrite", "chapter", "正文", "创作"]):
        return "expressive"
    return "stable_json"


def _default_catalog() -> list[dict[str, Any]]:
    return [
        {
            "provider": "local",
            "model": settings.splitbook_extract_model,
            "tags": ["json", "stable", "reasoning"],
            "cost": 0.12,
            "quality": 0.72,
            "reliability": 0.82,
        },
        {
            "provider": "local",
            "model": "qwen2.5:7b-instruct",
            "tags": ["json", "stable", "cheap"],
            "cost": 0.08,
            "quality": 0.62,
            "reliability": 0.78,
        },
        {
            "provider": "local",
            "model": "qwen2.5:14b-instruct",
            "tags": ["prose", "expressive", "reasoning"],
            "cost": 0.24,
            "quality": 0.8,
            "reliability": 0.8,
        },
        {
            "provider": "cloud",
            "model": "gpt-4.1-mini",
            "tags": ["json", "stable", "reasoning", "cloud"],
            "cost": 0.62,
            "quality": 0.88,
            "reliability": 0.91,
        },
        {
            "provider": "cloud",
            "model": "gpt-4.1",
            "tags": ["reasoning", "judge", "cloud"],
            "cost": 0.92,
            "quality": 0.94,
            "reliability": 0.92,
        },
        {
            "provider": "cloud",
            "model": "claude-3-7-sonnet",
            "tags": ["prose", "expressive", "reasoning", "cloud"],
            "cost": 0.9,
            "quality": 0.95,
            "reliability": 0.9,
        },
    ]


def _normalize_catalog(raw_catalog: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in raw_catalog:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip().lower()
        model = str(item.get("model") or "").strip()
        if not provider or not model:
            continue
        tags = {str(x).strip().lower() for x in _safe_json_list(item.get("tags")) if str(x).strip()}
        out.append(
            {
                "provider": provider,
                "model": model,
                "tags": tags,
                "cost": max(0.0, min(1.0, _safe_float(item.get("cost"), 0.5))),
                "quality": max(0.0, min(1.0, _safe_float(item.get("quality"), 0.7))),
                "reliability": max(0.0, min(1.0, _safe_float(item.get("reliability"), 0.8))),
            }
        )
    return out


def _score_candidate(
    *,
    candidate: dict[str, Any],
    required_tags: set[str],
    cost_mode: str,
    privacy_mode: str,
    provider_health: dict[str, bool],
) -> tuple[float, list[str]]:
    provider = str(candidate.get("provider") or "").strip().lower()
    tags = set(candidate.get("tags") or set())
    if provider in provider_health and not provider_health.get(provider, True):
        return (-999.0, [f"provider:{provider}:unhealthy"])
    reasons: list[str] = []
    matched = len(required_tags & tags)
    score = matched * 2.4
    if matched:
        reasons.append(f"tag_match={matched}/{len(required_tags)}")
    quality = _safe_float(candidate.get("quality"), 0.7)
    reliability = _safe_float(candidate.get("reliability"), 0.8)
    cost = _safe_float(candidate.get("cost"), 0.5)
    score += quality * 2.0
    score += reliability * 2.4
    if cost_mode == "low":
        score += (1.0 - cost) * 1.8
        reasons.append("cost_mode=low")
    elif cost_mode == "quality":
        score += quality * 1.8
        score -= cost * 0.8
        reasons.append("cost_mode=quality")
    else:
        score += quality * 0.9
        score += (1.0 - cost) * 0.7
        reasons.append("cost_mode=balanced")
    if privacy_mode == "strict":
        if provider == "local":
            score += 2.2
            reasons.append("privacy_boost=local")
        else:
            score -= 2.6
            reasons.append("privacy_penalty=cloud")
    return (round(score, 6), reasons)


async def ensure_model_router_tables(session: AsyncSession) -> None:
    ddl = [
        """
        CREATE TABLE IF NOT EXISTS model_route_decision (
          route_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          book_id UUID NULL REFERENCES book(book_id) ON DELETE SET NULL,
          task_type TEXT NOT NULL DEFAULT '',
          task_profile TEXT NOT NULL DEFAULT 'stable_json',
          selected_provider TEXT NOT NULL DEFAULT '',
          selected_model TEXT NOT NULL DEFAULT '',
          fallback_chain JSONB NOT NULL DEFAULT '[]'::jsonb,
          route_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
          input_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
          schema_version TEXT NOT NULL DEFAULT 'model_router_v1',
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_model_route_decision_book_time ON model_route_decision(book_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_model_route_decision_task ON model_route_decision(task_type, task_profile, created_at DESC)",
    ]
    for sql in ddl:
        await session.execute(text(sql))
    await session.commit()


async def route_story_model(session: AsyncSession, book_id: str | None, payload: dict[str, Any]) -> dict[str, Any]:
    await ensure_model_router_tables(session)
    task_type = str(payload.get("task_type") or payload.get("operation") or "write_chapter").strip().lower()
    task_profile = _normalize_task_profile(task_type, payload)
    profile_cfg = TASK_PROFILE_REQUIREMENTS.get(task_profile) or TASK_PROFILE_REQUIREMENTS["stable_json"]
    required_tags = set(profile_cfg.get("required_tags") or set())
    cost_mode = str(payload.get("cost_mode") or "balanced").strip().lower()
    if cost_mode not in {"low", "balanced", "quality"}:
        cost_mode = "balanced"
    privacy_mode = str(payload.get("privacy_mode") or "normal").strip().lower()
    if privacy_mode not in {"normal", "strict"}:
        privacy_mode = "normal"
    provider_health_raw = payload.get("provider_health") if isinstance(payload.get("provider_health"), dict) else {}
    provider_health: dict[str, bool] = {
        str(k).strip().lower(): _safe_bool(v, True)
        for k, v in provider_health_raw.items()
        if str(k).strip()
    }
    catalog = _normalize_catalog(_safe_json_list(payload.get("catalog")))
    if not catalog:
        catalog = _normalize_catalog(_default_catalog())
    scored: list[dict[str, Any]] = []
    for cand in catalog:
        score, reasons = _score_candidate(
            candidate=cand,
            required_tags=required_tags,
            cost_mode=cost_mode,
            privacy_mode=privacy_mode,
            provider_health=provider_health,
        )
        if score < -100:
            continue
        scored.append(
            {
                "provider": str(cand.get("provider") or ""),
                "model": str(cand.get("model") or ""),
                "tags": sorted(list(cand.get("tags") or set())),
                "score": score,
                "quality": _safe_float(cand.get("quality"), 0.0),
                "reliability": _safe_float(cand.get("reliability"), 0.0),
                "cost": _safe_float(cand.get("cost"), 1.0),
                "reasons": reasons,
            }
        )
    scored.sort(key=lambda x: (_safe_float(x.get("score"), -999.0), _safe_float(x.get("reliability"), 0.0)), reverse=True)
    if not scored:
        scored = [
            {
                "provider": "local",
                "model": settings.splitbook_extract_model,
                "tags": ["json", "stable"],
                "score": 0.0,
                "quality": 0.0,
                "reliability": 0.0,
                "cost": 0.0,
                "reasons": ["fallback_default_only"],
            }
        ]
    selected = scored[0]
    fallback_chain = scored[1:4]
    fallback_mode = "none"
    if selected.get("provider") == "local" and any(x.get("provider") == "cloud" for x in fallback_chain):
        fallback_mode = "local_to_cloud"
    elif selected.get("provider") == "cloud" and any(x.get("provider") == "local" for x in fallback_chain):
        fallback_mode = "cloud_to_local"
    decision_payload = {
        "task_type": task_type,
        "task_profile": task_profile,
        "task_label": str(profile_cfg.get("label") or ""),
        "selection": selected,
        "fallback_chain": fallback_chain,
        "policy": {
            "cost_mode": cost_mode,
            "privacy_mode": privacy_mode,
            "json_guard_required": bool(profile_cfg.get("json_guard_required")),
            "failure_downgrade": fallback_mode,
        },
        "schema_version": MODEL_ROUTER_SCHEMA_VERSION,
        "generated_at": _now_iso(),
    }
    row = (
        await session.execute(
            text(
                """
                INSERT INTO model_route_decision(
                  book_id, task_type, task_profile, selected_provider, selected_model,
                  fallback_chain, route_payload, input_payload, schema_version
                )
                VALUES (
                  CAST(:book_id AS uuid), :task_type, :task_profile, :selected_provider, :selected_model,
                  CAST(:fallback_chain AS jsonb), CAST(:route_payload AS jsonb), CAST(:input_payload AS jsonb), :schema_version
                )
                RETURNING route_id::text AS route_id, created_at
                """
            ),
            {
                "book_id": book_id,
                "task_type": task_type,
                "task_profile": task_profile,
                "selected_provider": str(selected.get("provider") or ""),
                "selected_model": str(selected.get("model") or ""),
                "fallback_chain": json.dumps(fallback_chain, ensure_ascii=False),
                "route_payload": json.dumps(decision_payload, ensure_ascii=False),
                "input_payload": json.dumps(payload or {}, ensure_ascii=False),
                "schema_version": MODEL_ROUTER_SCHEMA_VERSION,
            },
        )
    ).mappings().first()
    await session.commit()
    return {
        "ok": True,
        "book_id": book_id,
        "route_id": str((row or {}).get("route_id") or ""),
        "created_at": str((row or {}).get("created_at") or ""),
        **decision_payload,
    }
