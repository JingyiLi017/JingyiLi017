from __future__ import annotations

import json
import hashlib
import math
import random
import re
import difflib
import csv
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
from uuid import UUID
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import text
from starlette.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .defaults import DEFAULT_LLM_MODEL, merge_defaults, DEFAULT_TENSION_TARGETS, DEFAULT_TENSION_STYLE
from .db import get_db
from .schemas import (
    BookProfileBindRequest,
    ArcTargetItem,
    ArcTargetListResponse,
    ArcTargetUpsertRequest,
    BookCreateRequest,
    ChapterRevisionReportRequest,
    MaterialCardCreateRequest,
    MaterialCardItem,
    MaterialCardListResponse,
    MaterialKnnRequest,
    MaterialImportFromChunksRequest,
    RefInboxFromMaterialRequest,
    RefInboxStatusRequest,
    DraftCommitRequest,
    RefInboxFromTemplateRequest,
    TemplateEvolveRequest,
    RepairEffectSampleCreateRequest,
    TemplateVariantItem,
    TemplateVariantListResponse,
    BookTensionRepairPlanRequest,
    BookListResponse,
    BookItem,
    ChapterCreateRequest,
    ChapterItem,
    JobCreateRequest,
    JobResponse,
    LedgerApplyRequest,
    LedgerApplyResponse,
    ProfileCreateRequest,
    ProfileFromSplitbookRequest,
    ProfileCloneRequest,
    ProfileDiffRequest,
    ProfileItem,
    ProfileListResponse,
    ProfileLearnFromTextsRequest,
    MasterOutlineAutoGenerateRequest,
    StyleEvolutionRequest,
    ProfileSetActiveVersionRequest,
    ProfileUpdateRequest,
    BookProfileLinkRequest,
    SplitbookAllowGuardRequest,
    SplitbookCreateRequest,
    SearchResponse,
    SkillRunCreateRequest,
    SkillRunCreateResponse,
    StructureBeatsExtractRequest,
    SubmitJobResponse,
    TensionApplyRequest,
    TensionControlPlanRequest,
    TensionEvalRequest,
    MechanicsPreviewRequest,
    OutlineDetailSaveRequest,
    OutlinePatchApplyRequest,
    SimilarityGuardRequest,
    SimilarityGuardTextRequest,
    GenerateTemplateFromBeatsRequest,
    TemplateCreateRequest,
    TemplateItem,
    TemplateListResponse,
    TemplateRecommendRequest,
    TemplateUseRequest,
    TemplateUseResponse,
)
from .services.event_bus import event_bus, stream_sse
from .services.book_tension import get_latest_book_tension_report
from .services.jobs import job_runner
from .services.job_examples import JOB_EXAMPLES
from .services.draft_commit import run_commit_draft_job
from .services.ledger import apply_from_skill_run
from .services.search import hybrid_search
from .services.tension import apply_tension_patches
from .services.tension import compare_eval_runs, get_outline_detail_diff
from .services.tension import delete_outline_detail as delete_outline_detail_service
from .services.tension import get_outline_detail as get_outline_detail_service
from .services.tension import get_latest_skill_run as get_latest_skill_run_service
from .services.tension import get_skill_run_output
from .services.tension import list_outline_versions as list_outline_versions_service
from .services.tension import save_outline_detail as save_outline_detail_service
from .services.tension import evaluate_tension_score_v1
from .services.mechanics import mechanics_preview
from .services.reporting import create_chapter_revision_report
from .services.similarity import run_similarity_guard_text_job
from .services.splitbooks import (
    build_splitbook_chapter_pack,
    build_splitbook_outline,
    build_splitbook_template_library,
    get_splitbook_ledger_view,
    get_splitbook_pair_view,
    get_splitbook_qa_report,
    get_splitbook_scene_view,
    splitbook_anti_copy_check,
    splitbook_chapter_health_report,
    writeback_splitbook_chapter,
)
from .services.storage import (
    add_template_source,
    create_book,
    create_chapter,
    create_repair_effect_sample,
    create_job,
    create_profile,
    delete_book,
    delete_chapter,
    clone_profile,
    bind_book_profile,
    list_book_profiles,
    get_profile,
    delete_profile,
    create_skill_run,
    create_template,
    delete_structure_template,
    create_splitbook,
    delete_splitbook,
    fetch_system_info,
    get_book_settings,
    get_chapter_settings,
    get_effective_settings,
    get_default_scoped_settings_template,
    get_global_settings_scoped,
    list_settings_presets,
    create_settings_preset,
    update_settings_preset,
    delete_settings_preset,
    apply_settings_preset,
    list_settings_audit,
    rollback_settings_audit,
    diff_settings,
    get_settings,
    get_template_variant,
    get_splitbook,
    health_checks,
    get_job,
    list_jobs,
    delete_jobs,
    delete_job_by_id,
    delete_jobs_by_splitbook,
    delete_dangling_splitbook_jobs,
    list_books,
    list_arc_targets,
    list_chapters,
    list_template_variants,
    list_splitbooks,
    list_profiles,
    list_profile_versions,
    get_profile_version,
    set_profile_active_version,
    diff_profile_versions,
    add_book_profile_link,
    list_templates,
    list_material_cards,
    create_material_card,
    get_material_card,
    delete_material_card,
    upsert_material_embedding,
    search_material_knn,
    import_material_cards_from_chunks,
    create_ref_inbox_item,
    list_ref_inbox_items,
    set_ref_inbox_status,
    list_template_assets,
    get_template_asset,
    delete_template_asset,
    unified_search,
    log_template_usage,
    recommend_templates,
    run_init_sql,
    upsert_arc_target,
    set_template_variant_enabled,
    update_splitbook_allow_guard,
    update_profile,
    update_splitbook_status,
    set_book_settings,
    set_chapter_settings,
    set_global_settings_scoped,
    update_settings,
)
from .services.ollama_client import OllamaClient
from .services.json_guard import JSONGuardError, json_guard_parse
from .services.prompt_templates import STRICT_JSON_SYSTEM_PROMPT, build_material_extract_user_prompt
from .services.schema_validate import validate_material_extract_output
from sqlalchemy.exc import IntegrityError
from .services.template_evolution import merge_actions
from .services.style_evolution import evolve_book_style, get_latest_style_evolution
from .services.story_engine import (
    build_writing_memory_pack,
    build_chapter_engine_pack,
    build_chapter_repair_plan,
    create_story_bible_proposal,
    get_story_engine_quality_metrics,
    run_story_engine_regression,
    get_writing_session_state,
    get_story_bible_snapshot,
    get_story_engine_dashboard,
    list_story_bible_proposals,
    review_story_bible_proposal,
    run_chapter_engine_audit,
    upsert_writing_session_state,
    validate_and_writeback_memory,
)
from .services.model_router import route_story_model
from .observability import configure_logging, set_request_id, reset_request_id, get_logger

app = FastAPI(title="WriterBook Engine", version="0.2.0")
configure_logging()
logger = get_logger("api")

ERROR_ZH_MAP: dict[str, str] = {
    "INVALID_DIFF_BODY": "差异请求体格式无效",
    "PRESET_NAME_REQUIRED": "缺少预设名称",
    "PRESET_NOT_FOUND": "未找到预设",
    "INVALID_SCOPE": "作用域参数无效",
    "INVALID_MODE": "模式参数无效",
    "BOOK_NOT_FOUND": "未找到书籍",
    "CHAPTER_NOT_FOUND": "未找到章节",
    "PROFILE_NOT_FOUND": "未找到画像",
    "SPLITBOOK_NOT_FOUND": "未找到拆书档案",
    "SPLITBOOK_JOB_RUNNING": "该拆书已有任务运行中",
    "SPLITBOOK_EMBED_ALREADY_DONE": "该拆书已完成向量化，无需重复执行",
    "JOB_NOT_FOUND": "未找到任务",
    "FILE_NOT_FOUND": "文件不存在",
    "DUPLICATE_CHAPTER_NO": "章节号重复",
    "BOOK_ID_REQUIRED": "缺少书籍 ID",
    "CHAPTER_ID_REQUIRED": "缺少章节 ID",
    "INVALID_SETTINGS_JSON": "设置 JSON 格式错误",
    "REPORT_HTML_EMPTY": "报告内容为空",
    "EVAL_RESULT_NOT_FOUND": "评估结果不存在",
    "CONTROL_PLAN_NOT_FOUND": "控制计划不存在",
    "ONECLICK_NO_DRAFT_VERSION": "未找到可用草稿版本",
    "SMARTRUN_NO_DRAFT_VERSION": "智能运行未找到可用草稿版本",
    "OUTLINE_NOT_FOUND": "未找到章纲版本",
    "MASTER_OUTLINE_AI_UNAVAILABLE": "总纲生成失败：AI 服务不可用",
    "VOLUME_PLAN_AI_REQUIRED": "卷纲生成失败：必须启用 AI 生成",
    "VOLUME_PLAN_AI_UNAVAILABLE": "卷纲生成失败：AI 服务不可用",
    "EVAL_AI_REQUIRED": "张力评估失败：AI 服务不可用",
    "CONTROL_PLAN_AI_REQUIRED": "控制计划失败：AI 服务不可用",
    "ASSET_SNAPSHOT_NOT_FOUND": "未找到资产快照",
    "ASSET_SNAPSHOT_ROLLBACK_FAILED": "资产快照回滚失败",
    "ASSET_SNAPSHOT_CAPTURE_FAILED": "资产快照创建失败",
    "DRAFT_DELETE_LAST_FORBIDDEN": "当前章节仅剩一个版本，不能删除",
    "DRAFT_DELETE_NO_REPLACEMENT": "删除失败：没有可切换的替代版本",
    "VOLUME_PLAN_DELETE_LAST_FORBIDDEN": "当前分卷仅剩一个方案版本，不能删除",
    "VOLUME_PLAN_DELETE_NO_REPLACEMENT": "删除失败：没有可切换的替代分卷方案",
    "CHAPTER_IMPORT_TEXT_EMPTY": "导入失败：章节正文不能为空",
    "JOB_DELETE_RUNNING_FORBIDDEN": "运行中任务不允许删除，请先中止任务",
    "JOB_RESUME_FORBIDDEN_DONE": "已完成任务不能继续",
    "JOB_RESUME_FORBIDDEN_CANCELED": "已中止任务不能继续",
    "JOB_RESUME_RUNNING_ACTIVE": "任务仍在活跃运行，请稍后再试或使用强制继续",
    "AGENT_ORCHESTRATE_PHASE_INVALID": "总控阶段参数无效",
    "AGENT_ORCHESTRATE_CONFIRM_REQUIRED": "该计划需要人工确认后才能执行",
    "REQUEST_VALIDATION_ERROR": "请求参数校验失败",
    "INTERNAL_SERVER_ERROR": "服务内部异常",
}


def _normalize_error_code(raw: str) -> str:
    text_value = str(raw or "").strip().replace("Error:", "").strip()
    if not text_value:
        return ""
    token = str(text_value.split(":")[0] or "").strip().upper()
    if not token:
        return ""
    if not re.fullmatch(r"[A-Z0-9_.-]+", token or ""):
        return ""
    if "_" not in token and "." not in token and len(token) < 4:
        return ""
    return token


def _translate_error_code_zh(code: str) -> str:
    key = str(code or "").strip().upper()
    if not key:
        return ""
    if key in ERROR_ZH_MAP:
        return ERROR_ZH_MAP[key]
    if key.endswith("_NOT_FOUND"):
        return "请求资源不存在"
    if key.endswith("_REQUIRED"):
        return "缺少必填参数"
    if key.endswith("_INVALID"):
        return "输入参数无效"
    if key.endswith("_TIMEOUT"):
        return "请求处理超时"
    if key.endswith("_LOAD_FAILED"):
        return "加载失败"
    if key.endswith("_SAVE_FAILED"):
        return "保存失败"
    if key.endswith("_CREATE_FAILED"):
        return "创建失败"
    if key.endswith("_UPDATE_FAILED"):
        return "更新失败"
    if key.endswith("_DELETE_FAILED"):
        return "删除失败"
    if key.endswith("_START_FAILED"):
        return "启动失败"
    if key.endswith("_RUN_FAILED"):
        return "运行失败"
    if key.endswith("_APPLY_FAILED"):
        return "应用失败"
    if key.endswith("_EXPORT_FAILED"):
        return "导出失败"
    if key.endswith("_FETCH_FAILED"):
        return "读取失败"
    if key.endswith("_COMPARE_FAILED"):
        return "对比失败"
    if key.endswith("_DIFF_FAILED"):
        return "差异计算失败"
    if key.endswith("_FAILED"):
        return "操作执行失败"
    if key.endswith("_ERROR"):
        return "操作异常"
    return ""


def _build_error_payload(detail: object, rid: str) -> dict:
    if isinstance(detail, str):
        raw = detail.strip()
        code = _normalize_error_code(raw)
        zh = _translate_error_code_zh(code) if code else ""
        payload = {
            "detail": raw,
            "detail_zh": zh or ("请求失败" if raw else "请求失败"),
            "request_id": rid,
        }
        if code:
            payload["detail_code"] = code
        return payload
    if isinstance(detail, dict):
        payload = {"detail": detail, "detail_zh": "请求失败", "request_id": rid}
        code = _normalize_error_code(str(detail.get("code") or detail.get("detail") or ""))
        zh = _translate_error_code_zh(code)
        if code:
            payload["detail_code"] = code
            if zh:
                payload["detail_zh"] = zh
        return payload
    if isinstance(detail, list):
        return {"detail": detail, "detail_code": "REQUEST_VALIDATION_ERROR", "detail_zh": "请求参数校验失败", "request_id": rid}
    return {"detail": str(detail), "detail_zh": "请求失败", "request_id": rid}


def _build_material_ref_block(card: dict, extract_json: dict) -> str:
    points = ((extract_json.get("result") or {}).get("extracted_points") or [])[:7]
    lines: list[str] = []
    lines.append("[MaterialRef]")
    lines.append(f"- card_id: {card.get('card_id')}")
    lines.append(f"- title: {card.get('title') or ''}")
    lines.append(f"- tag: {card.get('tag') or ''}")
    lines.append('- usage_rule: "仅用 extracted_points 生成新内容；不得复述原句；不得沿用原叙事顺序；必须改写为本书语气；最多用1-2个点"')
    lines.append("- extracted_points:")
    for i, point in enumerate(points, start=1):
        kind = str(point.get("kind") or "mechanism")
        text_value = str(point.get("point") or "")
        hint = str(point.get("rewrite_hint") or "")
        lines.append(f"  {i}) {kind}: {text_value}（{hint}）")
    lines.append("- forbidden:")
    lines.append('  - "禁止使用素材原句与标志性措辞"')
    lines.append('  - "禁止复述具体叙事顺序"')
    lines.append("[/MaterialRef]")
    return "\n".join(lines)


def _build_template_ref_block(asset: dict, note: str | None = None) -> str:
    lines: list[str] = []
    lines.append("[TemplateRef]")
    lines.append(f"- asset_id: {asset.get('asset_id')}")
    lines.append(f"- type: {asset.get('asset_type')}")
    lines.append(f"- name: {asset.get('name') or ''}")
    lines.append('- usage_rule: "仅借结构/机制，不借具体事件/措辞/人名地名；必须换动机、换场景、换因果链；最多使用1个模板"')
    lines.append(f"- template_description: {asset.get('description') or ''}")
    if note:
        lines.append(f"- note: {note}")
    lines.append("- mapping_questions:")
    lines.append("  1) 本章谁执行该机制？对手是谁？")
    lines.append("  2) 触发点是什么？代价是什么？")
    lines.append("  3) 反转/升级落点是什么？结尾钩子是什么？")
    lines.append("  4) 如何体现本书世界观规则与角色缺陷？")
    lines.append("[/TemplateRef]")
    return "\n".join(lines)


def request_id(request: Request) -> str:
    state_id = getattr(request.state, "request_id", None)
    return state_id or request.headers.get("x-request-id") or f"req_{int(datetime.now(timezone.utc).timestamp() * 1000)}"


def _attach_trigger_meta(
    payload: dict,
    *,
    trigger_source: str | None = None,
    trigger_entry: str | None = None,
    trigger_mode: str | None = None,
) -> None:
    source = str(trigger_source or "").strip()
    if source:
        payload["trigger_source"] = source[:240]
    entry = str(trigger_entry or "").strip()
    if entry:
        payload["trigger_entry"] = entry[:180]
    mode = str(trigger_mode or "").strip().lower()
    if mode in {"manual", "recommended", "one_click", "auto"}:
        payload["trigger_mode"] = mode


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("x-request-id") or str(uuid4())
    token = set_request_id(rid)
    request.state.request_id = rid
    try:
        response: Response = await call_next(request)
    finally:
        reset_request_id(token)
    response.headers["X-Request-Id"] = rid
    logger.info(
        "http.request",
        extra={
            "request_id": rid,
            "meta": {
                "method": request.method,
                "path": request.url.path,
            },
        },
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    rid = request_id(request)
    payload = _build_error_payload(exc.detail, rid)
    return JSONResponse(status_code=exc.status_code, content=payload, headers=exc.headers or None)


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    rid = request_id(request)
    payload = {
        "detail": exc.errors(),
        "detail_code": "REQUEST_VALIDATION_ERROR",
        "detail_zh": "请求参数校验失败",
        "request_id": rid,
    }
    return JSONResponse(status_code=422, content=payload)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    rid = request_id(request)
    logger.exception(
        "http.unhandled_exception",
        extra={
            "request_id": rid,
            "meta": {
                "method": request.method,
                "path": request.url.path,
                "error": str(exc),
            },
        },
    )
    payload = {
        "detail": "INTERNAL_SERVER_ERROR",
        "detail_code": "INTERNAL_SERVER_ERROR",
        "detail_zh": "服务内部异常，请查看日志后重试",
        "request_id": rid,
    }
    return JSONResponse(status_code=500, content=payload)


@app.on_event("startup")
async def startup() -> None:
    await job_runner.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    await job_runner.shutdown()


@app.get("/v1/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    data = await health_checks(db)
    ollama_ok = False
    models: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            res = await client.get(f"{settings.ollama_host}/api/tags")
            if res.status_code == 200:
                ollama_ok = True
                payload = res.json()
                for m in payload.get("models", []) or []:
                    name = m.get("name")
                    if name:
                        models.append(str(name))
    except Exception:
        ollama_ok = False
    data["checks"]["ollama"] = {"ok": ollama_ok, "models": models}
    if not ollama_ok and data["status"] == "ok":
        data["status"] = "degraded"
    return data


@app.get("/v1/system/info")
async def system_info(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    info = await fetch_system_info(db)
    return {
        "engine_version": app.version,
        "time": info["time"],
        "db": {"connected": True, "schema_version": info["schema_version"], "tables": info["tables"]},
        "pgvector": {"extension_enabled": info["pgvector_enabled"]},
        "request_id": request_id(request),
    }


@app.post("/v1/system/db/init")
async def db_init(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    await run_init_sql(db)
    return {"ok": True, "schema_version": "2026.02.18_01", "request_id": request_id(request)}


@app.post("/v1/system/init")
async def system_init_route(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    await run_init_sql(db)
    return {
        "ok": True,
        "created_tables": "auto",
        "created_indexes": "auto",
        "extensions": ["vector", "pgcrypto"],
        "warnings": [],
        "request_id": request_id(request),
    }


@app.post("/v1/system/db/verify")
async def db_verify(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    info = await fetch_system_info(db)
    missing = [name for name, ok in info["tables"].items() if not ok]
    problems: list[dict] = []
    if not info["pgvector_enabled"]:
        problems.append({"code": "PGVECTOR_EXTENSION_MISSING", "message": "vector extension missing"})
    if missing:
        problems.append({"code": "TABLES_MISSING", "message": f"missing: {', '.join(missing)}"})
    return {
        "ok": len(problems) == 0,
        "problems": problems,
        "suggested_fix": None if not problems else "POST /v1/system/db/init",
        "request_id": request_id(request),
    }


@app.post("/v1/system/rebuild_fts")
async def rebuild_fts_route(db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(text("UPDATE chunk SET fts = to_tsvector('simple', text)"))
    await db.execute(text("REINDEX INDEX idx_chunk_fts"))
    await db.commit()
    return {"ok": True}


@app.post("/v1/system/cleanup_jobs")
async def cleanup_jobs_route(db: AsyncSession = Depends(get_db)) -> dict:
    done = await db.execute(text("DELETE FROM jobs WHERE status='succeeded' AND created_at < now() - interval '30 days'"))
    failed = await db.execute(text("DELETE FROM jobs WHERE status='failed' AND created_at < now() - interval '7 days'"))
    await db.commit()
    dangling = await delete_dangling_splitbook_jobs(db, limit=50000, include_active=False)
    return {
        "ok": True,
        "deleted_succeeded": int(done.rowcount or 0),
        "deleted_failed": int(failed.rowcount or 0),
        "deleted_dangling_splitbook_jobs": int(dangling),
    }


@app.post("/v1/system/rebuild_embeddings")
async def rebuild_embeddings_route(db: AsyncSession = Depends(get_db)) -> dict:
    deleted = await db.execute(text("DELETE FROM chunk_embedding"))
    await db.commit()
    return {"ok": True, "deleted_rows": int(deleted.rowcount or 0), "note": "re-embedding should be triggered via ingest or embed job"}


@app.get("/v1/settings")
async def get_settings_route(db: AsyncSession = Depends(get_db)) -> dict:
    return await get_settings(db)


@app.post("/v1/settings")
async def post_settings_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    return await update_settings(db, body)


@app.get("/v1/settings/global")
async def get_settings_global_route(db: AsyncSession = Depends(get_db)) -> dict:
    return {"settings": await get_global_settings_scoped(db)}


@app.post("/v1/settings/global")
async def post_settings_global_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    return {"settings": await set_global_settings_scoped(db, body or {})}


@app.get("/v1/settings/default_template")
async def get_settings_default_template_route() -> dict:
    return {"settings": get_default_scoped_settings_template()}


@app.post("/v1/settings/diff")
async def settings_diff_route(body: dict) -> dict:
    a = body.get("a") if isinstance(body, dict) else {}
    b = body.get("b") if isinstance(body, dict) else {}
    if not isinstance(a, dict) or not isinstance(b, dict):
        raise HTTPException(status_code=400, detail="INVALID_DIFF_BODY")
    return {"changes": diff_settings(a, b)}


@app.get("/v1/settings/presets")
async def list_settings_presets_route(
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = await list_settings_presets(db, limit=limit)
    return {"items": rows}


@app.post("/v1/settings/presets")
async def create_settings_preset_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    name = str((body or {}).get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="PRESET_NAME_REQUIRED")
    description = str((body or {}).get("description") or "")
    settings_value = (body or {}).get("settings") or {}
    if not isinstance(settings_value, dict):
        raise HTTPException(status_code=400, detail="INVALID_PRESET_SETTINGS")
    try:
        return await create_settings_preset(db, name=name, description=description, settings_value=settings_value)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="PRESET_NAME_CONFLICT") from exc


@app.post("/v1/settings/presets/{preset_id}")
async def update_settings_preset_route(preset_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    row = await update_settings_preset(
        db,
        str(preset_id),
        name=(body or {}).get("name"),
        description=(body or {}).get("description"),
        settings_value=(body or {}).get("settings"),
    )
    if not row:
        raise HTTPException(status_code=404, detail="PRESET_NOT_FOUND")
    return row


@app.delete("/v1/settings/presets/{preset_id}")
async def delete_settings_preset_route(preset_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    ok = await delete_settings_preset(db, str(preset_id))
    if not ok:
        raise HTTPException(status_code=404, detail="PRESET_NOT_FOUND")
    return {"ok": True}


@app.post("/v1/settings/presets/{preset_id}/apply")
async def apply_settings_preset_route(preset_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    scope = str((body or {}).get("scope") or "").strip().lower()
    mode = str((body or {}).get("mode") or "merge").strip().lower()
    if scope not in {"global", "book", "chapter"}:
        raise HTTPException(status_code=400, detail="INVALID_SCOPE")
    if mode not in {"merge", "replace"}:
        raise HTTPException(status_code=400, detail="INVALID_MODE")
    try:
        out = await apply_settings_preset(
            db,
            preset_id=str(preset_id),
            scope=scope,
            book_id=(body or {}).get("book_id"),
            chapter_id=(body or {}).get("chapter_id"),
            mode=mode,
        )
        return out
    except RuntimeError as exc:
        code = str(exc)
        if code in {"PRESET_NOT_FOUND"}:
            raise HTTPException(status_code=404, detail=code) from exc
        if code in {"BOOK_ID_REQUIRED", "CHAPTER_ID_REQUIRED", "INVALID_SCOPE"}:
            raise HTTPException(status_code=400, detail=code) from exc
        raise


@app.get("/v1/settings/audit")
async def list_settings_audit_route(
    scope: str | None = Query(default=None),
    scope_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> dict:
    scope_norm = scope.strip().lower() if isinstance(scope, str) and scope.strip() else None
    if scope_norm and scope_norm not in {"global", "book", "chapter"}:
        raise HTTPException(status_code=400, detail="INVALID_SCOPE")
    rows = await list_settings_audit(db, scope=scope_norm, scope_id=scope_id, limit=limit)
    return {"items": rows}


@app.post("/v1/settings/audit/{audit_id}/rollback")
async def rollback_settings_audit_route(audit_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    note = str((body or {}).get("note") or "")
    try:
        return await rollback_settings_audit(db, audit_id=str(audit_id), note=note)
    except RuntimeError as exc:
        code = str(exc)
        if code in {"AUDIT_NOT_FOUND"}:
            raise HTTPException(status_code=404, detail=code) from exc
        if code in {"AUDIT_NOT_ROLLBACKABLE", "INVALID_AUDIT_BEFORE_SETTINGS", "ROLLBACK_NOOP"}:
            raise HTTPException(status_code=400, detail=code) from exc
        raise


@app.get("/v1/books/{book_id}/settings")
async def get_book_settings_route(book_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    value = await get_book_settings(db, str(book_id))
    return {"book_id": str(book_id), "settings": value or {}}


@app.post("/v1/books/{book_id}/settings")
async def post_book_settings_route(book_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        value = await set_book_settings(db, str(book_id), body or {})
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail="BOOK_NOT_FOUND") from exc
    return {"book_id": str(book_id), "settings": value}


@app.post("/v1/books/{book_id}/master_outline/auto_generate")
async def master_outline_auto_generate_route(
    book_id: UUID,
    body: MasterOutlineAutoGenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    row_book = await db.execute(
        text("SELECT book_id::text AS book_id, title FROM book WHERE book_id=CAST(:book_id AS uuid)"),
        {"book_id": str(book_id)},
    )
    book_row = row_book.mappings().first()
    if not book_row:
        raise HTTPException(status_code=404, detail="BOOK_NOT_FOUND")

    settings_value = await get_book_settings(db, str(book_id)) or {}
    brief_from_settings = settings_value.get("writing_brief") if isinstance(settings_value.get("writing_brief"), dict) else {}
    genre = _normalize_brief_typos(str(body.genre or brief_from_settings.get("genre") or "").strip())
    theme = _normalize_brief_typos(str(body.theme or brief_from_settings.get("theme") or "").strip())
    tone = _normalize_brief_typos(str(body.tone or brief_from_settings.get("tone") or "").strip())
    audience = _normalize_brief_typos(str(body.audience or brief_from_settings.get("audience") or "").strip())
    idea = _normalize_brief_typos(str(body.idea or brief_from_settings.get("idea") or "").strip())
    setting_text = _normalize_brief_typos(str(body.setting or brief_from_settings.get("setting") or "").strip())
    brief_structured = _build_master_outline_brief_payload(
        brief_from_settings,
        overrides={
            "genre": genre,
            "theme": theme,
            "tone": tone,
            "audience": audience,
            "idea": idea,
            "setting": setting_text,
        },
    )

    volume_items: list[dict[str, Any]] = [x.model_dump() for x in (body.volume_items or [])]
    if not volume_items:
        rows = await db.execute(
            text(
                """
                SELECT volume_no, title, note, start_chapter_no, end_chapter_no, planned_chapters
                FROM volume
                WHERE book_id=CAST(:book_id AS uuid)
                ORDER BY volume_no ASC
                """
            ),
            {"book_id": str(book_id)},
        )
        volume_items = [dict(r) for r in rows.mappings().all()]
    chapter_count_row = await db.execute(
        text("SELECT COUNT(*) AS n FROM chapter WHERE book_id=CAST(:book_id AS uuid)"),
        {"book_id": str(book_id)},
    )
    chapter_count = int((chapter_count_row.mappings().first() or {}).get("n") or 0)

    planned_from_vol = 0
    for vol in volume_items:
        p = int(vol.get("planned_chapters") or 0)
        if p > 0:
            planned_from_vol += p
            continue
        s = int(vol.get("start_chapter_no") or 0)
        e = int(vol.get("end_chapter_no") or 0)
        if s > 0 and e >= s:
            planned_from_vol += e - s + 1
    planned_hint = max(1, int(body.planned_chapters or 0), int(planned_from_vol or 0), int(chapter_count or 0))

    hints = _normalize_structure_hints(body.model_dump())
    splitbook_id = str(body.splitbook_id) if body.splitbook_id else ""
    material_guidance = _extract_material_guidance_from_refs([str(x) for x in (body.material_refs or [])][:30])
    material_rows = await db.execute(
        text(
            """
            SELECT title, content, tag, importance
            FROM material_card
            WHERE book_id=CAST(:book_id AS uuid)
            ORDER BY importance DESC, created_at DESC
            LIMIT 40
            """
        ),
        {"book_id": str(book_id)},
    )
    material_library_guidance: list[str] = []
    for row in material_rows.mappings().all():
        title = str(row.get("title") or "").strip()
        content = str(row.get("content") or "").strip()
        tag = str(row.get("tag") or "").strip()
        if not (title or content):
            continue
        line = f"{title}｜{content[:140]}{f'｜tag={tag}' if tag else ''}"
        if line not in material_library_guidance:
            material_library_guidance.append(line)
        if len(material_library_guidance) >= 20:
            break
    splitbook_outline_reference: dict[str, Any] = {}
    if splitbook_id:
        hints = await _merge_splitbook_hints(db, splitbook_id=splitbook_id, hints=hints)
        splitbook_outline_reference = await _build_splitbook_outline_reference(db, splitbook_id=splitbook_id)
    hint_count = int(hints.get("total_lines") or 0)
    safe_structure_hints = _outline_safe_structure_hints(hints)
    brief_protected_lines = _collect_brief_source_lines(genre, theme, tone, audience, idea, setting_text)
    extended_brief = brief_structured.get("extended") if isinstance(brief_structured.get("extended"), dict) else {}
    for value in extended_brief.values():
        for line in _collect_brief_source_lines(str(value or "")):
            if line not in brief_protected_lines:
                brief_protected_lines.append(line)
    prompt_reference_text, prompt_reference_source = _load_master_outline_prompt_reference()

    prompt_payload = {
        "book_title": str(book_row.get("title") or ""),
        "brief": {
            "genre": genre,
            "theme": theme,
            "tone": tone,
            "audience": audience,
            "idea": idea,
            "setting": setting_text,
        },
        "brief_structured": brief_structured,
        "planned_chapters_hint": planned_hint,
        "volumes": [
            {
                "name": str(v.get("title") or f"卷{v.get('volume_no') or ''}").strip(),
                "goal_hint": str(v.get("note") or "").strip(),
                "chapter_range": (
                    f"{int(v.get('start_chapter_no') or 0)}-{int(v.get('end_chapter_no') or 0)}"
                    if int(v.get("start_chapter_no") or 0) > 0 and int(v.get("end_chapter_no") or 0) >= int(v.get("start_chapter_no") or 0)
                    else ""
                ),
            }
            for v in volume_items[:20]
        ],
        "structure_hints": safe_structure_hints,
        "material_guidance": material_guidance,
        "material_library_guidance": material_library_guidance,
        "splitbook_outline_reference": splitbook_outline_reference,
        "requirements": {
            "anti_copy": "只可借鉴结构规律，禁止复述来源文本",
            "continuity": "后续必须支持总纲->卷纲->章纲一致",
            "language": "简体中文",
            "structure_hint_input_mode": "tag_only",
            "forbid_copy_from_brief": True,
            "outline_summary_min_chars": 120,
            "prioritize_material_guidance": True,
        },
    }
    user_prompt = (
        "请你作为网文策划编辑，生成全书级总纲 JSON。\n"
        "要求：\n"
        "1) 只输出 JSON，不要 Markdown。\n"
        "2) total outline 要可执行，可直接用于后续卷纲/章纲。\n"
        "3) 若给了结构提示，仅可抽象借鉴，禁止复述原文。\n"
        "4) phases 需要覆盖阶段推进与章节范围。\n\n"
        f"输入:\n{json.dumps(prompt_payload, ensure_ascii=False)}"
    )
    schema_hint = (
        '{"summary":"string","premise":"string","core_conflict":"string","theme":"string","audience":"string",'
        '"planned_chapters":120,"phases":[{"name":"第一阶段","goal":"string","chapter_range":"1-30"}],'
        '"constraints":{"anti_copy":"string","continuity":"string"}}'
    )
    system_prompt = (
        "你是小说策划编辑。只输出合法 JSON。\n"
        "生成依据必须优先使用创作简报；拆书资料只允许借鉴结构节奏，不允许复述。\n"
        "以下是总纲生成提示词参考（Markdown）：\n"
        f"{prompt_reference_text}"
    )
    generation_mode = "llm"
    generation_error = ""
    try:
        client = OllamaClient(settings.ollama_host)
        raw = await client.chat_json(
            model=str(body.llm_model or DEFAULT_LLM_MODEL),
            user=user_prompt,
            system=system_prompt,
            temperature=0.25,
            max_tokens=2200,
            timeout_s=180,
            retries=1,
            schema_hint=schema_hint,
            validate=_validate_master_outline_ai_json,
            meta={
                "route": "master_outline_auto_generate",
                "book_id": str(book_id),
                "splitbook_hint_count": hint_count,
            },
        )
    except Exception as exc:
        generation_error = str(exc)
        raise HTTPException(status_code=503, detail=f"MASTER_OUTLINE_AI_UNAVAILABLE:{generation_error[:180]}") from exc

    normalized = _normalize_master_outline_ai_json(
        raw if isinstance(raw, dict) else {},
        fallback_planned=planned_hint,
        hint_count=hint_count,
    )
    hint_lines = _collect_hint_lines(hints)
    anti_copy_source_lines = []
    for line in (hint_lines + brief_protected_lines):
        txt = str(line or "").strip()
        if txt and txt not in anti_copy_source_lines:
            anti_copy_source_lines.append(txt)
    normalized, anti_copy_rewritten_fields = _apply_master_outline_anti_copy_guard(
        normalized,
        source_hint_lines=anti_copy_source_lines,
        theme=theme,
        audience=audience,
        setting_text=setting_text,
        idea=idea,
    )
    normalized = _enrich_master_outline_summary(normalized)
    if not normalized.get("summary"):
        normalized["summary"] = _fallback_outline_texts(theme=theme, audience=audience, setting_text=setting_text, idea=idea)["summary"]
    basis: list[str] = ["writing_brief", "writing_brief_structured", "volume_items", "book_db_context", "prompt_md_template"]
    if chapter_count > 0:
        basis.append("chapter_items_db")
    if splitbook_id:
        basis.append("splitbook_selected")
    if splitbook_outline_reference:
        basis.append("splitbook_outline_structure")
    if isinstance(body.material_refs, list) and len(body.material_refs) > 0:
        basis.append("material_refs")
    if material_guidance:
        basis.append("material_guidance")
    if material_library_guidance:
        basis.append("material_library")
    if hint_count > 0:
        basis.append("splitbook_structure_hints" if splitbook_id else "manual_structure_hints")
    return {
        "ok": True,
        "book_id": str(book_id),
        "outline": normalized,
        "meta": {
            "provider": "ollama" if generation_mode == "llm" else "fallback",
            "model": str(body.llm_model or DEFAULT_LLM_MODEL),
            "structure_hints_applied": hint_count,
            "structure_hint_sources": [str(x) for x in (hints.get("sources") or []) if str(x).strip()][:8],
            "structure_hint_mode": "tag_only",
            "brief_protected_lines": len(brief_protected_lines),
            "material_guidance_count": len(material_guidance),
            "material_library_count": len(material_library_guidance),
            "prompt_template_source": prompt_reference_source,
            "splitbook_outline_reference": {
                "chapter_total": int(splitbook_outline_reference.get("chapter_total") or 0),
                "phase_count": len(splitbook_outline_reference.get("phase_skeleton") or []),
            },
            "db_context": {
                "book_title": str(book_row.get("title") or ""),
                "chapter_count": int(chapter_count),
                "volume_count": len(volume_items),
                "planned_chapters_hint": int(planned_hint),
            },
            "basis": basis,
            "generation_mode": generation_mode,
            "fallback_reason": generation_error[:200] if generation_mode != "llm" and generation_error else "",
            "anti_copy_guard_triggered": bool(anti_copy_rewritten_fields),
            "anti_copy_rewritten_fields": anti_copy_rewritten_fields,
            "ai_debug": {
                "route": "master_outline_auto_generate",
                "provider": "ollama" if generation_mode == "llm" else "fallback",
                "model": str(body.llm_model or DEFAULT_LLM_MODEL),
                "prompt_payload": prompt_payload,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "schema_hint": schema_hint,
                "basis": basis,
                "prompt_template_source": prompt_reference_source,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@app.get("/v1/chapters/{chapter_id}/settings")
async def get_chapter_settings_route(chapter_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    value = await get_chapter_settings(db, str(chapter_id))
    return {"chapter_id": str(chapter_id), "settings": value or {}}


@app.post("/v1/chapters/{chapter_id}/settings")
async def post_chapter_settings_route(chapter_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        value = await set_chapter_settings(db, str(chapter_id), body or {})
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail="CHAPTER_NOT_FOUND") from exc
    return {"chapter_id": str(chapter_id), "settings": value}


@app.get("/v1/chapters/{chapter_id}/settings/effective")
async def get_chapter_effective_settings_route(chapter_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    out = await get_effective_settings(db, str(chapter_id))
    if not out:
        raise HTTPException(status_code=404, detail="CHAPTER_NOT_FOUND")
    return {"chapter_id": str(chapter_id), **out}


@app.get("/v1/books/{book_id}/ai_debug")
async def get_book_ai_debug_route(
    book_id: UUID,
    chapter_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row_book = await db.execute(
        text("SELECT book_id::text AS book_id, title FROM book WHERE book_id=CAST(:book_id AS uuid) LIMIT 1"),
        {"book_id": str(book_id)},
    )
    book_hit = row_book.mappings().first()
    if not book_hit:
        raise HTTPException(status_code=404, detail="BOOK_NOT_FOUND")

    book_settings = await get_book_settings(db, str(book_id))
    book_settings_obj = book_settings if isinstance(book_settings, dict) else {}
    master_meta = (
        book_settings_obj.get("writing_master_outline_meta")
        if isinstance(book_settings_obj.get("writing_master_outline_meta"), dict)
        else {}
    )
    master_ai_debug = master_meta.get("ai_debug") if isinstance(master_meta.get("ai_debug"), dict) else {}

    chapter_id_text = str(chapter_id) if chapter_id else ""
    chapter_meta: dict[str, Any] = {}
    chapter_ai_debug: dict[str, Any] = {}
    chapter_title = ""
    chapter_no = 0
    volume_id_for_audit = ""
    volume_no_for_audit = 0
    volume_title_for_audit = ""
    if chapter_id_text:
        row_chapter = await db.execute(
            text(
                """
                SELECT chapter_id::text AS chapter_id, title, "order" AS chapter_no
                FROM chapter
                WHERE chapter_id=CAST(:chapter_id AS uuid) AND book_id=CAST(:book_id AS uuid)
                LIMIT 1
                """
            ),
            {"chapter_id": chapter_id_text, "book_id": str(book_id)},
        )
        chapter_hit = row_chapter.mappings().first()
        if not chapter_hit:
            raise HTTPException(status_code=404, detail="CHAPTER_NOT_FOUND")
        chapter_title = str(chapter_hit.get("title") or "")
        chapter_no = int(chapter_hit.get("chapter_no") or 0)
        chapter_settings = await get_chapter_settings(db, chapter_id_text)
        chapter_settings_obj = chapter_settings if isinstance(chapter_settings, dict) else {}
        chapter_meta = (
            chapter_settings_obj.get("writing_chapter_outline_meta")
            if isinstance(chapter_settings_obj.get("writing_chapter_outline_meta"), dict)
            else {}
        )
        chapter_ai_debug = chapter_meta.get("ai_debug") if isinstance(chapter_meta.get("ai_debug"), dict) else {}
        row_volume = await db.execute(
            text(
                """
                SELECT v.volume_id::text AS volume_id, v.volume_no, v.title
                FROM chapter c
                JOIN volume v
                  ON v.book_id=c.book_id
                 AND c."order" BETWEEN v.start_chapter_no AND v.end_chapter_no
                WHERE c.chapter_id=CAST(:chapter_id AS uuid)
                  AND c.book_id=CAST(:book_id AS uuid)
                ORDER BY v.volume_no DESC
                LIMIT 1
                """
            ),
            {"chapter_id": chapter_id_text, "book_id": str(book_id)},
        )
        volume_hit = row_volume.mappings().first()
        if volume_hit:
            volume_id_for_audit = str(volume_hit.get("volume_id") or "")
            volume_no_for_audit = int(volume_hit.get("volume_no") or 0)
            volume_title_for_audit = str(volume_hit.get("title") or "")
    else:
        row_volume = await db.execute(
            text(
                """
                SELECT v.volume_id::text AS volume_id, v.volume_no, v.title
                FROM volume_plan p
                JOIN volume v ON v.volume_id=p.volume_id
                WHERE p.book_id=CAST(:book_id AS uuid) AND p.status='active'
                ORDER BY p.version DESC, p.updated_at DESC
                LIMIT 1
                """
            ),
            {"book_id": str(book_id)},
        )
        volume_hit = row_volume.mappings().first()
        if volume_hit:
            volume_id_for_audit = str(volume_hit.get("volume_id") or "")
            volume_no_for_audit = int(volume_hit.get("volume_no") or 0)
            volume_title_for_audit = str(volume_hit.get("title") or "")

    volume_plan_active = await _load_active_volume_plan(db, book_id=str(book_id), volume_id=volume_id_for_audit) if volume_id_for_audit else None
    volume_plan_assumptions = (
        volume_plan_active.get("assumptions")
        if isinstance(volume_plan_active, dict) and isinstance(volume_plan_active.get("assumptions"), dict)
        else {}
    )
    volume_plan_ai_refine = (
        volume_plan_assumptions.get("ai_refine")
        if isinstance(volume_plan_assumptions.get("ai_refine"), dict)
        else {}
    )

    run_sql = """
        SELECT run_id::text AS run_id, workflow_id, status, started_at, ended_at, error, meta, chapter_id::text AS chapter_id
        FROM workflow_run
        WHERE workflow_id='draft_runner_v1' AND book_id=CAST(:book_id AS uuid)
    """
    run_params: dict[str, Any] = {"book_id": str(book_id)}
    if chapter_id_text:
        run_sql += " AND chapter_id=CAST(:chapter_id AS uuid)"
        run_params["chapter_id"] = chapter_id_text
    run_sql += " ORDER BY started_at DESC LIMIT 1"

    run_row = await db.execute(text(run_sql), run_params)
    run_hit = run_row.mappings().first()
    draft_generation: dict[str, Any] = {}
    if run_hit:
        run_id_text = str(run_hit.get("run_id") or "")
        steps_row = await db.execute(
            text(
                """
                SELECT node_id, status, input, output, metrics, error, started_at, ended_at
                FROM workflow_step
                WHERE run_id=CAST(:run_id AS uuid)
                ORDER BY started_at ASC, node_id ASC
                """
            ),
            {"run_id": run_id_text},
        )
        steps = [dict(x) for x in steps_row.mappings().all()]
        step_by_node = {str(s.get("node_id") or ""): s for s in steps}
        compose_step = step_by_node.get("compose_prompt") or {}
        llm_step = step_by_node.get("llm_generate") or {}
        compose_output = compose_step.get("output") if isinstance(compose_step.get("output"), dict) else {}
        llm_output_wrap = llm_step.get("output") if isinstance(llm_step.get("output"), dict) else {}
        llm_output = llm_output_wrap.get("llm_output") if isinstance(llm_output_wrap.get("llm_output"), dict) else {}
        draft_generation = {
            "run": {
                "run_id": run_id_text,
                "workflow_id": str(run_hit.get("workflow_id") or ""),
                "status": str(run_hit.get("status") or ""),
                "started_at": run_hit.get("started_at"),
                "ended_at": run_hit.get("ended_at"),
                "chapter_id": str(run_hit.get("chapter_id") or ""),
                "error": run_hit.get("error") if isinstance(run_hit.get("error"), dict) else {},
            },
            "compose_prompt": {
                "status": str(compose_step.get("status") or ""),
                "prompt": str(compose_output.get("prompt") or ""),
                "prompt_blocks": compose_output.get("prompt_blocks") if isinstance(compose_output.get("prompt_blocks"), dict) else {},
            },
            "llm_generate": {
                "status": str(llm_step.get("status") or ""),
                "input": llm_step.get("input") if isinstance(llm_step.get("input"), dict) else {},
                "model": str(llm_output.get("model") or ""),
                "stubbed": bool(llm_output.get("stubbed", False)),
                "latency_ms": int(llm_output.get("latency_ms") or 0),
                "tokens_in_est": int(llm_output.get("tokens_in_est") or 0),
                "tokens_out_est": int(llm_output.get("tokens_out_est") or 0),
                "chapter_text_preview": str(llm_output.get("chapter_text") or "")[:2000],
                "events_json": llm_output.get("events_json") if isinstance(llm_output.get("events_json"), dict) else {},
            },
        }

    step_12_ok = bool(master_ai_debug) and bool(str(master_ai_debug.get("user_prompt") or "").strip())
    step_13_ok = bool(volume_plan_ai_refine.get("enabled")) and int(volume_plan_ai_refine.get("sample_size") or 0) > 0
    step_14_ok = bool(chapter_ai_debug) and bool(str(chapter_ai_debug.get("user_prompt") or "").strip())
    llm_gen = draft_generation.get("llm_generate") if isinstance(draft_generation.get("llm_generate"), dict) else {}
    step_15_ok = (
        bool(draft_generation)
        and bool(str(llm_gen.get("model") or "").strip())
        and not bool(llm_gen.get("stubbed"))
        and str(draft_generation.get("run", {}).get("status") or "").lower() == "succeeded"
    )
    ai_compliance = {
        "overall_ok": bool(step_12_ok and step_13_ok and step_14_ok and step_15_ok),
        "stages": {
            "1.2": {
                "label": "总纲生成",
                "required_ai": True,
                "ok": bool(step_12_ok),
                "reason": "" if step_12_ok else "未找到总纲 AI 调用记录",
            },
            "1.3": {
                "label": "卷纲生成/应用",
                "required_ai": True,
                "ok": bool(step_13_ok),
                "reason": "" if step_13_ok else "卷纲 AI refine 未命中或无有效样本",
            },
            "1.4": {
                "label": "章纲生成",
                "required_ai": True,
                "ok": bool(step_14_ok),
                "reason": "" if step_14_ok else "未找到章纲 AI 调用记录",
            },
            "1.5": {
                "label": "章节生成",
                "required_ai": True,
                "ok": bool(step_15_ok),
                "reason": "" if step_15_ok else "未找到成功的非 Stub LLM 章节生成记录",
            },
        },
    }

    return {
        "ok": True,
        "book": {
            "book_id": str(book_id),
            "title": str(book_hit.get("title") or ""),
        },
        "chapter": {
            "chapter_id": chapter_id_text or None,
            "chapter_no": chapter_no if chapter_id_text else None,
            "title": chapter_title or None,
        },
        "master_outline": {
            "meta": master_meta,
            "ai_debug": master_ai_debug,
        },
        "chapter_outline": {
            "meta": chapter_meta,
            "ai_debug": chapter_ai_debug,
        },
        "volume_plan": {
            "volume_id": volume_id_for_audit or None,
            "volume_no": volume_no_for_audit or None,
            "title": volume_title_for_audit or None,
            "ai_refine": volume_plan_ai_refine,
        },
        "draft_generation": draft_generation,
        "ai_compliance": ai_compliance,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/v1/books", response_model=BookItem)
async def create_book_route(body: BookCreateRequest, db: AsyncSession = Depends(get_db)) -> BookItem:
    row = await create_book(db, body.title, body.author, body.language, body.notes)
    return BookItem(**row)


@app.get("/v1/books", response_model=BookListResponse)
async def list_books_route(
    query: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> BookListResponse:
    rows = await list_books(db, query=query, limit=limit)
    return BookListResponse(items=[BookItem(**row) for row in rows])


@app.delete("/v1/books/{book_id}")
async def delete_book_route(book_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    row = await delete_book(db, str(book_id))
    if not row:
        raise HTTPException(status_code=404, detail="BOOK_NOT_FOUND")
    return {"ok": True, "deleted": row}


@app.post("/v1/books/{book_id}/chapters", response_model=ChapterItem)
async def create_chapter_route(
    book_id: UUID,
    body: ChapterCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> ChapterItem:
    try:
        row = await create_chapter(
            db,
            book_id=str(book_id),
            chapter_no=body.chapter_no,
            title=body.title,
            arc_id=body.arc_id,
            arc_index=body.arc_index,
        )
        return ChapterItem(**row)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="DUPLICATE_CHAPTER_NO") from exc


@app.get("/v1/books/{book_id}/chapters")
async def list_chapters_route(
    book_id: UUID,
    query: str = Query(default=""),
    limit: int = Query(default=200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = await list_chapters(db, str(book_id), query=query, limit=limit)
    return {"chapters": [ChapterItem(**row).model_dump() for row in rows]}


@app.get("/v1/books/{book_id}/draft_confirmations")
async def book_draft_confirmations_route(
    book_id: UUID,
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = await db.execute(
        text(
            """
            SELECT
              c.chapter_id::text AS chapter_id,
              c."order" AS chapter_no,
              c.title AS chapter_title,
              c.active_draft_id::text AS active_draft_id,
              cs.selected_draft_id::text AS selected_draft_id,
              cs.selected_branch,
              cs.selected_by,
              cs.selected_reason,
              cs.selected_at,
              d.created_at AS selected_draft_created_at,
              d.run_id::text AS selected_run_id
            FROM chapter c
            LEFT JOIN chapter_selected cs ON cs.chapter_id=c.chapter_id
            LEFT JOIN chapter_draft d ON d.draft_id=cs.selected_draft_id
            WHERE c.book_id=CAST(:book_id AS uuid)
            ORDER BY c."order" ASC
            LIMIT :limit
            """
        ),
        {"book_id": str(book_id), "limit": int(limit)},
    )
    items = []
    confirmed = 0
    for r in rows.mappings().all():
        x = dict(r)
        selected_draft_id = str(x.get("selected_draft_id") or "").strip()
        x["confirm_status"] = "confirmed" if selected_draft_id else "pending"
        if selected_draft_id:
            confirmed += 1
        items.append(x)
    total = len(items)
    return {
        "ok": True,
        "book_id": str(book_id),
        "total": total,
        "confirmed": confirmed,
        "pending": max(0, total - confirmed),
        "items": items,
    }


@app.delete("/v1/chapters/{chapter_id}")
async def delete_chapter_route(chapter_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    row = await delete_chapter(db, str(chapter_id))
    if not row:
        raise HTTPException(status_code=404, detail="CHAPTER_NOT_FOUND")
    return {"ok": True, "deleted": row}


@app.get("/v1/books/{book_id}/volumes")
async def list_volumes_route(book_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    rows = await db.execute(
        text(
            """
            SELECT
              volume_id::text AS volume_id,
              volume_no,
              title,
              start_chapter_no,
              end_chapter_no,
              planned_chapters,
              note,
              created_at
            FROM volume
            WHERE book_id=CAST(:book_id AS uuid)
            ORDER BY volume_no ASC
            """
        ),
        {"book_id": str(book_id)},
    )
    return {"book_id": str(book_id), "items": [dict(r) for r in rows.mappings().all()]}


@app.post("/v1/books/{book_id}/volumes/auto_create")
async def volume_auto_create_route(book_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    chapters_per_volume = int((body or {}).get("chapters_per_volume") or 50)
    chapters_per_volume = max(10, min(chapters_per_volume, 200))
    rows = await db.execute(
        text('SELECT chapter_id::text AS chapter_id, "order" AS chapter_no FROM chapter WHERE book_id=CAST(:book_id AS uuid) ORDER BY "order" ASC'),
        {"book_id": str(book_id)},
    )
    chapters = [dict(r) for r in rows.mappings().all()]
    if not chapters:
        return {"ok": True, "book_id": str(book_id), "created": 0, "items": []}
    max_no = int(chapters[-1].get("chapter_no") or 0)
    if max_no <= 0:
        return {"ok": True, "book_id": str(book_id), "created": 0, "items": []}
    await db.execute(text("DELETE FROM volume WHERE book_id=CAST(:book_id AS uuid)"), {"book_id": str(book_id)})
    created = []
    vol_no = 1
    start = 1
    while start <= max_no:
        end = min(max_no, start + chapters_per_volume - 1)
        ins = await db.execute(
            text(
                """
                INSERT INTO volume(book_id, volume_no, title, start_chapter_no, end_chapter_no, planned_chapters, note)
                VALUES (CAST(:book_id AS uuid), :volume_no, :title, :start_no, :end_no, :planned, :note)
                RETURNING volume_id::text AS volume_id
                """
            ),
            {
                "book_id": str(book_id),
                "volume_no": vol_no,
                "title": f"Volume {vol_no}",
                "start_no": start,
                "end_no": end,
                "planned": end - start + 1,
                "note": "auto_created",
            },
        )
        volume_id = str(ins.scalar_one())
        created.append({"volume_id": volume_id, "volume_no": vol_no, "start_chapter_no": start, "end_chapter_no": end})
        vol_no += 1
        start = end + 1
    await db.commit()
    return {"ok": True, "book_id": str(book_id), "created": len(created), "items": created}


def _volume_window_ranges() -> dict[str, tuple[float, float]]:
    return {
        "vol_setup": (0.00, 0.18),
        "vol_build": (0.18, 0.65),
        "vol_spike": (0.65, 0.90),
        "vol_release": (0.90, 1.00),
    }


def _window_for_stage(stage: str) -> str:
    s = str(stage or "").strip().lower()
    if s == "pressure":
        return "vol_setup"
    if s == "cost":
        return "vol_build"
    if s == "breakthrough":
        return "vol_spike"
    if s in {"integration", "reflect"}:
        return "vol_release"
    return "vol_build"


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _compute_volume_progress(chapter_no: int | None, volume_row: dict | None) -> float:
    if not chapter_no or not volume_row:
        return 0.0
    start_no = int(volume_row.get("start_chapter_no") or chapter_no)
    end_no = int(volume_row.get("end_chapter_no") or chapter_no)
    if end_no <= start_no:
        return 1.0 if chapter_no >= end_no else 0.0
    return _clamp01((float(chapter_no) - float(start_no)) / float(max(1, end_no - start_no)))


async def _load_active_volume_plan(db: AsyncSession, *, book_id: str, volume_id: str) -> dict | None:
    row = await db.execute(
        text(
            """
            SELECT vol_plan_id::text AS vol_plan_id, book_id::text AS book_id, volume_id::text AS volume_id,
                   version, status, assumptions, note, created_at
            FROM volume_plan
            WHERE book_id=CAST(:book_id AS uuid)
              AND volume_id=CAST(:volume_id AS uuid)
              AND status='active'
            ORDER BY version DESC
            LIMIT 1
            """
        ),
        {"book_id": book_id, "volume_id": volume_id},
    )
    plan = row.mappings().first()
    if not plan:
        return None
    items_res = await db.execute(
        text(
            """
            SELECT item_id::text AS item_id, kind, ref_id::text AS ref_id, summary, target_window,
                   target_p_vol_min, target_p_vol_max, priority, must_happen, meta, created_at
            FROM volume_plan_item
            WHERE vol_plan_id=CAST(:vol_plan_id AS uuid)
            ORDER BY priority DESC, created_at ASC
            """
        ),
        {"vol_plan_id": str(plan["vol_plan_id"])},
    )
    out = dict(plan)
    out["items"] = [dict(r) for r in items_res.mappings().all()]
    return out


def _volume_goal_profile(volume_goal: str, chapter_count: int, target_pacing: str) -> dict:
    goal = str(volume_goal or "").strip().lower()
    pacing = str(target_pacing or "mid").strip().lower()
    payoff_count = 1
    if chapter_count >= 35:
        payoff_count = 2
    if chapter_count >= 70:
        payoff_count = 3
    if any(x in goal for x in ("终局", "揭秘", "收束", "真相", "决战")):
        payoff_count += 1

    seed_count = 1
    if chapter_count >= 50:
        seed_count = 2
    if any(x in goal for x in ("下一卷", "铺垫", "扩张", "新敌", "升级")):
        seed_count += 1
    if pacing == "fast":
        seed_count = max(1, seed_count - 1)
    return {
        "payoff_count": max(1, min(4, payoff_count)),
        "seed_count": max(1, min(3, seed_count)),
        "growth_count": 1,
    }


def _make_plan_item_summary(*, kind: str, title: str, window: str, payoff_type: str | None = None, intensity: int | None = None, volume_goal: str = "") -> str:
    k = str(kind or "").strip().lower()
    t = str(title or "").strip()
    w = str(window or "").strip()
    goal = str(volume_goal or "").strip()
    if k == "growth":
        return f"成长推进：{t or '关键节点'}；窗口={w}；要求：代价必须上镜、选择必须明确；目标：{goal or '推进角色弧线'}"
    if k == "foreshadow_payoff":
        return f"伏笔回收：{t or '核心伏笔'}；方式={payoff_type or 'reversal'}；强度={intensity or 2}；规则：重解释旧线索但不破坏逻辑"
    if k == "foreshadow_seed":
        return f"埋新伏笔：{t or '下一卷钩子'}；窗口={w}；要求：只埋问句不一次性解释"
    if k == "cliffhanger":
        return "卷末钩子：抛出新威胁或新条件，形成“下一卷必须看”的问题句"
    return f"{k}: {t or 'plan item'}"


def _structure_pattern_fingerprint(st_type: str, subtype: str, pattern: dict) -> str:
    norm = pattern if isinstance(pattern, dict) else {}
    payload = {
        "st_type": str(st_type or "").strip().lower(),
        "subtype": str(subtype or "").strip().lower(),
        "pattern": norm,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _combo_fingerprint(combo_type: str, target_window: str, steps: list[dict], constraints: dict | None = None) -> str:
    norm_steps = []
    for s in (steps or []):
        if not isinstance(s, dict):
            continue
        norm_steps.append(
            {
                "kind": str(s.get("kind") or "").strip().lower(),
                "stage": str(s.get("stage") or "").strip().lower(),
                "payoff_type": str(s.get("payoff_type") or "").strip().lower(),
                "style": str(s.get("style") or "").strip().lower(),
                "intensity": int(s.get("intensity") or 1),
            }
        )
    payload = {
        "combo_type": str(combo_type or "").strip().lower(),
        "target_window": str(target_window or "").strip().lower(),
        "steps": norm_steps,
        "constraints": constraints if isinstance(constraints, dict) else {},
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _structure_risk_score(pattern: dict, slots: list[str]) -> float:
    text_blob = json.dumps(pattern if isinstance(pattern, dict) else {}, ensure_ascii=False)
    slot_blob = " ".join([str(x) for x in (slots or [])])
    blob = f"{text_blob} {slot_blob}"
    risk = 0.05
    if re.search(r"[A-Z][a-z]{2,}", blob):
        risk += 0.18
    if re.search(r"\d{3,}", blob):
        risk += 0.12
    if re.search(r"[\u4e00-\u9fff]{2,}(宗|门|国|城|帝|王|阁|殿|府|家族)", blob):
        risk += 0.22
    if re.search(r"(专有|原文|照搬|实体名|人名|地名)", blob):
        risk += 0.22
    if len(blob) > 3000:
        risk += 0.08
    return round(max(0.0, min(1.0, risk)), 6)


def _goal_tags(volume_goal: str, volume_theme: str, target_pacing: str) -> list[str]:
    tags: list[str] = []
    pacing = str(target_pacing or "mid").strip().lower()
    if pacing == "fast":
        tags.extend(["fast_paced", "high_conflict"])
    elif pacing == "slow":
        tags.extend(["slow_burn", "introspection_heavy"])
    else:
        tags.extend(["mid_paced"])
    g = f"{volume_goal} {volume_theme}".lower()
    if any(x in g for x in ("回收", "揭秘", "真相", "收束")):
        tags.append("info_reveal")
    if any(x in g for x in ("代价", "牺牲", "抉择")):
        tags.append("character_growth")
    if any(x in g for x in ("钩子", "悬念", "危机", "追更")):
        tags.append("cliffhanger_end")
    return sorted(list(dict.fromkeys(tags)))


def _default_combo_patterns() -> dict[str, dict]:
    return {
        "setup_hook_combo": {
            "steps": [
                {"kind": "hook", "style": "abnormality", "intensity": 2},
                {"kind": "goal", "style": "explicit_goal", "intensity": 2},
                {"kind": "obstacle", "style": "first_block", "intensity": 2},
                {"kind": "cliffhanger", "style": "question_end", "intensity": 2},
            ],
            "constraints": {"max_items_per_chapter": 1, "hook_must_be_in_ch1": True},
        },
        "mid_spike_combo": {
            "steps": [
                {"kind": "growth", "stage": "pressure", "intensity": 2},
                {"kind": "cost", "style": "visible_cost", "intensity": 2},
                {"kind": "foreshadow_payoff", "payoff_type": "cost", "intensity": 2},
                {"kind": "new_lead", "style": "bigger_threat_hint", "intensity": 2},
            ],
            "constraints": {"payoff_must_not_close_main_mystery": True},
        },
        "reveal_combo": {
            "steps": [
                {"kind": "reveal", "style": "partial_reveal", "intensity": 2},
                {"kind": "foreshadow_payoff", "payoff_type": "misinterpretation", "intensity": 2},
                {"kind": "gap", "style": "missing_piece", "intensity": 2},
                {"kind": "hook", "style": "new_condition", "intensity": 2},
            ],
            "constraints": {"no_full_exposition_dump": True},
        },
        "vol_end_combo": {
            "steps": [
                {"kind": "growth", "stage": "breakthrough", "intensity": 3},
                {"kind": "foreshadow_payoff", "payoff_type": "reversal", "intensity": 3},
                {"kind": "foreshadow_seed", "style": "next_volume_seed", "intensity": 2},
                {"kind": "cliffhanger", "style": "question_end", "intensity": 3},
            ],
            "constraints": {"max_items_per_chapter": 2, "payoff_before_seed": True},
        },
    }


async def _pick_structure_templates_for_plan(
    db: AsyncSession,
    *,
    book_id: str,
    volume_no: int,
    volume_goal: str,
    volume_theme: str,
    target_pacing: str,
) -> dict:
    goal_tags = _goal_tags(volume_goal, volume_theme, target_pacing)
    rows = await db.execute(
        text(
            """
            SELECT
              template_id::text AS template_id,
              st_type, subtype, name, tags, pattern, slots,
              COALESCE(risk_score,0)::float AS risk_score,
              policy, fingerprint, source_meta, source_book_hash, rotation_group, last_used_volume_no,
              COALESCE(s.weight, 0)::float AS learned_weight
            FROM structure_template t
            LEFT JOIN asset_score_stat s
              ON s.item_type='structure_template' AND s.item_id=t.template_id AND s.book_id=CAST(:book_id AS uuid)
            WHERE (t.profile_id IS NULL OR t.profile_id IN (
              SELECT profile_id FROM book WHERE book_id=CAST(:book_id AS uuid)
            ))
              AND COALESCE(t.policy, 'normal') <> 'banned'
              AND COALESCE(t.risk_score, 0) < 0.35
              AND t.st_type IN ('volume_plan', 'payoff', 'cliff', 'beat_pack')
            ORDER BY t.created_at DESC
            LIMIT 300
            """
        ),
        {"book_id": book_id},
    )
    cands = [dict(r) for r in rows.mappings().all()]
    for c in cands:
        tags = c.get("tags") if isinstance(c.get("tags"), list) else []
        overlap = len(set([str(x) for x in tags]) & set(goal_tags))
        risk = float(c.get("risk_score") or 0.0)
        learned = float(c.get("learned_weight") or 0.0)
        rotation_penalty = 0.0
        lv = c.get("last_used_volume_no")
        if lv is not None:
            try:
                d = int(volume_no) - int(lv)
                if d <= 1:
                    rotation_penalty = 1.0
                elif d == 2:
                    rotation_penalty = 0.6
            except Exception:
                rotation_penalty = 0.0
        c["_score"] = overlap * 1.0 + learned * 1.5 - risk * 0.7 - rotation_penalty
        c["_rotation_penalty"] = rotation_penalty
    cands.sort(key=lambda x: (float(x.get("_score") or -1e9), -float(x.get("risk_score") or 0.0)), reverse=True)

    by_type: dict[str, list[dict]] = {}
    for c in cands:
        by_type.setdefault(str(c.get("st_type") or ""), []).append(c)

    selected: dict[str, dict] = {}
    used_fp: set[str] = set()
    used_source: set[str] = set()
    for tp in ("volume_plan", "payoff", "cliff", "beat_pack"):
        arr = by_type.get(tp) or []
        picked = None
        for c in arr:
            fp = str(c.get("fingerprint") or "")
            source_hash = str(c.get("source_book_hash") or "")
            if fp and fp in used_fp:
                continue
            if source_hash and source_hash in used_source:
                continue
            picked = c
            break
        if picked:
            selected[tp] = picked
            if str(picked.get("fingerprint") or ""):
                used_fp.add(str(picked.get("fingerprint")))
            if str(picked.get("source_book_hash") or ""):
                used_source.add(str(picked.get("source_book_hash")))
    return {"goal_tags": goal_tags, "selected": selected}


async def _pick_structure_combos_for_plan(
    db: AsyncSession,
    *,
    book_id: str,
    volume_no: int,
    goal_tags: list[str],
) -> dict:
    rows = await db.execute(
        text(
            """
            SELECT
              c.combo_id::text AS combo_id,
              c.combo_type,
              c.fingerprint,
              c.pattern,
              c.tags,
              COALESCE(c.risk_score,0)::float AS risk_score,
              c.policy,
              c.rotation_group,
              c.last_used_volume_no,
              COALESCE(s.weight, 0)::float AS learned_weight
            FROM structure_combo c
            LEFT JOIN asset_score_stat s
              ON s.item_type='structure_combo' AND s.item_id=c.combo_id AND s.book_id=CAST(:book_id AS uuid)
            WHERE (c.book_id IS NULL OR c.book_id=CAST(:book_id AS uuid))
              AND c.combo_type IN ('setup_hook_combo','mid_spike_combo','reveal_combo','vol_end_combo')
              AND COALESCE(c.policy,'normal') <> 'banned'
              AND COALESCE(c.risk_score,0) < 0.35
            ORDER BY c.created_at DESC
            LIMIT 300
            """
        ),
        {"book_id": book_id},
    )
    cands = [dict(r) for r in rows.mappings().all()]
    group_latest: dict[str, int] = {}
    for c in cands:
        g = str(c.get("rotation_group") or "").strip()
        lv = c.get("last_used_volume_no")
        if not g or lv is None:
            continue
        try:
            cur = int(lv)
            prev = group_latest.get(g)
            group_latest[g] = cur if prev is None else max(prev, cur)
        except Exception:
            continue

    goal_set = set([str(x) for x in (goal_tags or []) if str(x).strip()])
    for c in cands:
        tags = c.get("tags") if isinstance(c.get("tags"), list) else []
        overlap = len(set([str(x) for x in tags]) & goal_set)
        risk = float(c.get("risk_score") or 0.0)
        learned = float(c.get("learned_weight") or 0.0)
        pin_bonus = 0.5 if str(c.get("policy") or "").lower() == "pinned" else 0.0
        rotation_penalty = 0.0
        lv = c.get("last_used_volume_no")
        if lv is not None:
            try:
                d = int(volume_no) - int(lv)
                if d <= 1:
                    rotation_penalty = 1.2
                elif d == 2:
                    rotation_penalty = 0.7
                elif d == 3:
                    rotation_penalty = 0.25
            except Exception:
                rotation_penalty = 0.0
        group_penalty = 0.0
        g = str(c.get("rotation_group") or "").strip()
        if g and g in group_latest:
            d2 = int(volume_no) - int(group_latest[g])
            if d2 <= 1:
                group_penalty = 0.8
            elif d2 == 2:
                group_penalty = 0.35
        c["_score"] = overlap * 1.0 + learned * 1.5 + pin_bonus - risk * 0.7 - rotation_penalty - group_penalty
        c["_rotation_penalty"] = rotation_penalty
        c["_group_penalty"] = group_penalty
        c["_pin_bonus"] = pin_bonus
        c["_tag_overlap"] = overlap

    cands.sort(key=lambda x: float(x.get("_score") or -1e9), reverse=True)
    by_type: dict[str, list[dict]] = {}
    for c in cands:
        by_type.setdefault(str(c.get("combo_type") or ""), []).append(c)

    selected: dict[str, dict] = {}
    used_fp: set[str] = set()
    used_group: set[str] = set()
    for tp in ("setup_hook_combo", "mid_spike_combo", "reveal_combo", "vol_end_combo"):
        arr = by_type.get(tp) or []
        picked = None
        for c in arr:
            fp = str(c.get("fingerprint") or "")
            group = str(c.get("rotation_group") or "")
            if fp and fp in used_fp:
                continue
            if group and group in used_group:
                continue
            picked = c
            break
        if picked:
            selected[tp] = picked
            if str(picked.get("fingerprint") or ""):
                used_fp.add(str(picked.get("fingerprint")))
            if str(picked.get("rotation_group") or ""):
                used_group.add(str(picked.get("rotation_group")))
    return {"selected": selected}


def _extract_structure_hints_from_material_refs(material_refs: list[str] | None) -> dict[str, Any]:
    refs = [str(x) for x in (material_refs or []) if str(x).strip()]
    out: dict[str, Any] = {
        "sources": [],
        "conflicts": [],
        "foreshadows": [],
        "payoffs": [],
        "growths": [],
        "strategies": [],
    }
    if not refs:
        out["total_lines"] = 0
        return out
    source_set: set[str] = set()

    def _append_unique(bucket: list[str], line: str, limit: int = 8) -> None:
        txt = re.sub(r"^\s*[-*•]\s*", "", str(line or "")).strip()
        if not txt or txt.startswith("（待补充"):
            return
        if txt in bucket:
            return
        if len(bucket) >= limit:
            return
        bucket.append(txt)

    section_map = {
        "conflicts": "【冲突驱动（可复用结构）】",
        "foreshadows": "【伏笔铺设（仅结构，不取原句）】",
        "payoffs": "【回收节点（仅策略，不取原句）】",
        "growths": "【角色成长维度（成长/代价/压力/收获）】",
        "strategies": "【节奏与调参建议】",
    }
    for block in refs:
        if "[拆书结构引用]" not in block:
            continue
        m_source = re.search(r"source_splitbook_name=([^\n\r]+)", block, flags=re.IGNORECASE)
        if m_source:
            src = str(m_source.group(1) or "").strip()
            if src:
                source_set.add(src)
        for key, heading in section_map.items():
            m = re.search(rf"{re.escape(heading)}\s*([\s\S]*?)(?:\n【|$)", block, flags=re.MULTILINE)
            if not m:
                continue
            for line in str(m.group(1) or "").splitlines():
                _append_unique(out[key], line)
    out["sources"] = sorted(list(source_set))[:8]
    out["total_lines"] = sum(len(out[k]) for k in ("conflicts", "foreshadows", "payoffs", "growths", "strategies"))
    return out


def _extract_splitbook_ids_from_material_refs(material_refs: list[str] | None) -> list[str]:
    refs = [str(x) for x in (material_refs or []) if str(x).strip()]
    out: list[str] = []
    for block in refs:
        if "[拆书结构引用]" not in block:
            continue
        found = re.findall(r"source_splitbook_id=([0-9a-fA-F-]{16,64})", block, flags=re.IGNORECASE)
        for sid in found:
            s = str(sid or "").strip()
            if s and s not in out:
                out.append(s)
    return out[:8]


def _extract_material_guidance_from_refs(material_refs: list[str] | None) -> list[str]:
    refs = [str(x) for x in (material_refs or []) if str(x).strip()]
    out: list[str] = []
    for block in refs:
        txt = str(block or "").strip()
        if not txt:
            continue
        if txt.startswith("[拆书结构引用]"):
            continue
        lines = [re.sub(r"^\s*[-*•]\s*", "", ln).strip() for ln in txt.splitlines()]
        for ln in lines:
            if not ln:
                continue
            if ln.startswith("[") and "]" in ln:
                continue
            if len(ln) < 4:
                continue
            if ln not in out:
                out.append(ln[:220])
            if len(out) >= 20:
                return out
    return out


def _resolve_splitbook_id_from_body(body: dict | None) -> str:
    payload = body or {}
    splitbook_id = str(payload.get("splitbook_id") or "").strip()
    if splitbook_id:
        return splitbook_id
    refs = payload.get("material_refs") if isinstance(payload.get("material_refs"), list) else []
    ids = _extract_splitbook_ids_from_material_refs([str(x) for x in refs][:30])
    return ids[0] if ids else ""


def _normalize_structure_hints(body: dict | None) -> dict[str, Any]:
    payload = body or {}
    hints_raw = payload.get("structure_hints") if isinstance(payload.get("structure_hints"), dict) else {}
    material_refs = payload.get("material_refs") if isinstance(payload.get("material_refs"), list) else []
    from_refs = _extract_structure_hints_from_material_refs([str(x) for x in material_refs][:30])
    out: dict[str, Any] = {}
    for key in ("sources", "conflicts", "foreshadows", "payoffs", "growths", "strategies"):
        vals: list[str] = []
        src_a = hints_raw.get(key) if isinstance(hints_raw, dict) else []
        if isinstance(src_a, list):
            vals.extend([str(x).strip() for x in src_a if str(x).strip()])
        src_b = from_refs.get(key) if isinstance(from_refs.get(key), list) else []
        vals.extend([str(x).strip() for x in src_b if str(x).strip()])
        dedup: list[str] = []
        for v in vals:
            if v and v not in dedup:
                dedup.append(v)
        out[key] = dedup[:8]
    out["total_lines"] = sum(len(out[k]) for k in ("conflicts", "foreshadows", "payoffs", "growths", "strategies"))
    return out


def _normalize_brief_typos(text: str) -> str:
    s = str(text or "").strip()
    if not s:
        return ""
    typo_map = {
        "啥法果断": "杀伐果断",
        "沙伐果断": "杀伐果断",
        "杀阀果断": "杀伐果断",
        "节凑": "节奏",
        "设定集定": "设定",
    }
    for wrong, right in typo_map.items():
        s = s.replace(wrong, right)
    s = re.sub(r"[ \t\r\f\v]+", " ", s).strip()
    return s


def _collect_brief_source_lines(*texts: str) -> list[str]:
    out: list[str] = []
    for raw in texts:
        txt = _normalize_brief_typos(str(raw or ""))
        if not txt:
            continue
        if txt not in out:
            out.append(txt)
        parts = re.split(r"[，。；、/|：:,.!?！？\-\s]+", txt)
        for p in parts:
            seg = str(p or "").strip()
            if len(seg) < 4:
                continue
            if seg not in out:
                out.append(seg)
    return out[:120]


def _build_master_outline_brief_payload(
    base: dict[str, Any] | None,
    *,
    overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    src = base if isinstance(base, dict) else {}
    out: dict[str, Any] = {}
    known = ("genre", "theme", "tone", "audience", "idea", "setting")
    for key in known:
        override_value = str((overrides or {}).get(key) or "").strip()
        raw_value = override_value or str(src.get(key) or "").strip()
        norm = _normalize_brief_typos(raw_value)
        if norm:
            out[key] = norm[:500]
    extended: dict[str, str] = {}
    for key, value in src.items():
        k = str(key or "").strip()
        if not k or k in known or k == "updated_at":
            continue
        if isinstance(value, (dict, list)):
            txt = json.dumps(value, ensure_ascii=False)
        else:
            txt = str(value or "").strip()
        norm = _normalize_brief_typos(txt)
        if norm:
            extended[k[:80]] = norm[:500]
    if extended:
        out["extended"] = extended
    return out


def _load_master_outline_prompt_reference() -> tuple[str, str]:
    prompt_path = (Path(__file__).resolve().parents[2] / "docs" / "prompts" / "master_outline_prompt.md").resolve()
    fallback = (
        "# 总纲生成参考\n"
        "- 优先依据创作简报生成主线与阶段推进。\n"
        "- 拆书资料仅用于结构节奏，不得复述原文。\n"
        "- 输出必须支持卷纲与章纲继续生成。\n"
    )
    try:
        content = prompt_path.read_text(encoding="utf-8").strip()
        if content:
            return content[:5000], str(prompt_path)
    except Exception:
        pass
    return fallback, "builtin:master_outline_prompt"


def _slice_chapter_range(chapters: list[dict[str, Any]], start: int, end: int) -> str:
    if not chapters:
        return ""
    start = max(1, start)
    end = max(start, end)
    return f"{start}-{end}"


async def _build_splitbook_outline_reference(db: AsyncSession, *, splitbook_id: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not splitbook_id:
        return out
    sb = await get_splitbook(db, splitbook_id)
    if sb:
        out["splitbook_id"] = str(sb.get("splitbook_id") or splitbook_id)
        out["splitbook_name"] = str(sb.get("name") or "").strip()
    try:
        outline = await build_splitbook_outline(db, splitbook_id)
    except Exception:
        return out
    chapters = outline.get("chapters") if isinstance(outline, dict) else []
    if not isinstance(chapters, list) or not chapters:
        return out
    chapter_total = int(outline.get("chapter_total") or len(chapters) or 0)
    chapter_total = max(1, chapter_total)
    out["chapter_total"] = chapter_total

    phase_names = ["起势", "升级", "爆发", "回收"]
    phase_skeleton: list[dict[str, str]] = []
    for idx, name in enumerate(phase_names):
        start = int((chapter_total * idx) / len(phase_names)) + 1
        end = int((chapter_total * (idx + 1)) / len(phase_names))
        phase_skeleton.append(
            {
                "name": name,
                "chapter_range": _slice_chapter_range(chapters, start, end),
                "goal": ["建立主线目标与关键矛盾", "抬升冲突与代价压力", "多线爆发并兑现关键爽点", "收束阶段承诺并引出下阶段问题"][idx],
            }
        )
    out["phase_skeleton"] = phase_skeleton

    samples: list[dict[str, Any]] = []
    foreshadow_total = 0
    payoff_total = 0
    for ch in chapters[:24]:
        if not isinstance(ch, dict):
            continue
        summary = ch.get("summary") if isinstance(ch.get("summary"), dict) else {}
        foreshadow_count = int(summary.get("foreshadow_count") or 0)
        payoff_count = int(summary.get("payoff_count") or 0)
        foreshadow_total += foreshadow_count
        payoff_total += payoff_count
        samples.append(
            {
                "chapter_no": int(ch.get("chapter_no") or 0),
                "chapter_title": str(ch.get("chapter_title") or "")[:80],
                "conflict": str(summary.get("conflict") or "")[:120],
                "foreshadow_count": foreshadow_count,
                "payoff_count": payoff_count,
            }
        )
    out["chapter_pattern_samples"] = samples
    out["rhythm"] = {
        "foreshadow_total": foreshadow_total,
        "payoff_total": payoff_total,
        "foreshadow_payoff_ratio": round(foreshadow_total / max(1, payoff_total), 3),
    }
    return out


def _derive_outline_axes(*texts: str) -> list[str]:
    merged = " ".join([_normalize_brief_typos(str(x or "")) for x in texts]).lower()
    rules: list[tuple[list[str], str]] = [
        (["生存", "求生", "绝境"], "生存压力"),
        (["群像", "团队", "同伴"], "群像协同"),
        (["杀伐", "果断", "铁血"], "强决策推进"),
        (["升级", "进阶", "成长"], "阶段升级"),
        (["规则", "禁忌", "体系"], "规则对抗"),
        (["阴谋", "外神", "魔物", "敌对势力"], "高压对抗"),
        (["伏笔", "回收", "反转"], "伏笔回收"),
        (["代价", "牺牲", "痛点"], "代价驱动"),
    ]
    tags: list[str] = []
    for keys, label in rules:
        if any(k in merged for k in keys) and label not in tags:
            tags.append(label)
    if not tags:
        tags = ["目标推进", "冲突升级", "代价兑现"]
    return tags[:5]


def _normalize_copycheck_text(text: str) -> str:
    s = str(text or "").lower()
    s = re.sub(r"[\s\u3000]+", "", s)
    s = re.sub(r"[^\w\u4e00-\u9fff]", "", s)
    return s


def _char_ngrams(text: str, n: int = 3) -> set[str]:
    if not text or len(text) < n:
        return set()
    return {text[i : i + n] for i in range(0, len(text) - n + 1)}


def _is_copy_like_text(text: str, source_lines: list[str]) -> bool:
    target = _normalize_copycheck_text(text)
    if len(target) < 8:
        return False
    target_grams = _char_ngrams(target, 3)
    for line in source_lines:
        source = _normalize_copycheck_text(line)
        if len(source) < 8:
            continue
        if source in target:
            return True
        source_grams = _char_ngrams(source, 3)
        if not source_grams or not target_grams:
            continue
        overlap = len(target_grams & source_grams)
        ratio = overlap / max(1, len(source_grams))
        if overlap >= 5 and ratio >= 0.62:
            return True
    return False


def _collect_hint_lines(hints: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key in ("conflicts", "foreshadows", "payoffs", "growths", "strategies"):
        vals = hints.get(key) if isinstance(hints.get(key), list) else []
        for v in vals:
            t = str(v or "").strip()
            if t and t not in lines:
                lines.append(t)
    return lines[:80]


def _detect_tags(lines: list[str], mapping: list[tuple[str, list[str]]], default_tag: str) -> list[str]:
    tags: list[str] = []
    for line in lines:
        txt = str(line or "")
        for tag, words in mapping:
            if any(w in txt for w in words):
                if tag not in tags:
                    tags.append(tag)
                break
    if not tags:
        tags.append(default_tag)
    return tags[:4]


def _outline_safe_structure_hints(hints: dict[str, Any]) -> dict[str, Any]:
    conflicts = [str(x) for x in (hints.get("conflicts") or []) if str(x).strip()][:16]
    foreshadows = [str(x) for x in (hints.get("foreshadows") or []) if str(x).strip()][:16]
    payoffs = [str(x) for x in (hints.get("payoffs") or []) if str(x).strip()][:16]
    growths = [str(x) for x in (hints.get("growths") or []) if str(x).strip()][:16]
    strategies = [str(x) for x in (hints.get("strategies") or []) if str(x).strip()][:16]
    conflict_tags = _detect_tags(
        conflicts,
        [
            ("生存压力冲突", ["生存", "求生", "绝境", "危机"]),
            ("资源争夺冲突", ["资源", "争夺", "利益", "筹码"]),
            ("身份与立场冲突", ["身份", "阵营", "立场", "背叛", "隐瞒"]),
            ("规则对抗冲突", ["规则", "禁令", "秩序", "契约", "制度"]),
            ("战力压制冲突", ["压制", "逆袭", "越级", "战力", "碾压"]),
        ],
        "复合冲突",
    )
    foreshadow_tags = _detect_tags(
        foreshadows,
        [
            ("身份伏笔", ["身份", "血脉", "来历", "真实身份"]),
            ("规则伏笔", ["规则", "禁忌", "代价", "限制"]),
            ("关系伏笔", ["关系", "师徒", "盟友", "情感"]),
            ("事件伏笔", ["事件", "线索", "真相", "阴谋"]),
        ],
        "剧情伏笔",
    )
    payoff_tags = _detect_tags(
        payoffs,
        [
            ("反转回收", ["反转", "真相", "揭露"]),
            ("战斗回收", ["战斗", "对决", "镇压", "击败"]),
            ("关系回收", ["和解", "决裂", "联盟", "背叛"]),
            ("成长回收", ["成长", "突破", "觉醒", "代价"]),
        ],
        "阶段回收",
    )
    growth_tags = _detect_tags(
        growths,
        [
            ("代价驱动成长", ["代价", "牺牲", "痛点", "负担"]),
            ("压力驱动成长", ["压力", "逼迫", "危机", "困境"]),
            ("关系驱动成长", ["关系", "同伴", "亲人", "羁绊"]),
            ("目标驱动成长", ["目标", "使命", "信念", "选择"]),
        ],
        "冲突驱动成长",
    )
    strategy_tags = _detect_tags(
        strategies,
        [
            ("铺垫-爆发-余震", ["铺垫", "爆发", "余震"]),
            ("多线并进", ["多线", "并线", "线索并行"]),
            ("阶段升级", ["升级", "阶段", "递进"]),
            ("短回收高频", ["短回收", "高频", "节奏"]),
        ],
        "结构节奏优化",
    )
    return {
        "sources": [str(x) for x in (hints.get("sources") or []) if str(x).strip()][:8],
        "counts": {
            "conflicts": len(conflicts),
            "foreshadows": len(foreshadows),
            "payoffs": len(payoffs),
            "growths": len(growths),
            "strategies": len(strategies),
            "total_lines": int(hints.get("total_lines") or 0),
        },
        "tags": {
            "conflicts": conflict_tags,
            "foreshadows": foreshadow_tags,
            "payoffs": payoff_tags,
            "growths": growth_tags,
            "strategies": strategy_tags,
        },
        "policy": {
            "abstract_only": True,
            "quote_source_text": False,
            "forbidden": ["不得复述来源文本", "不得沿用来源句式", "不得复制原书金句"],
        },
    }


def _fallback_outline_texts(*, theme: str, audience: str, setting_text: str, idea: str) -> dict[str, str]:
    axes = _derive_outline_axes(theme, setting_text, idea)
    audience_txt = _normalize_brief_typos(str(audience or "").strip()) or "网文读者"
    theme_txt = " / ".join(axes[:2]) if axes else "成长与代价"
    axis_text = " / ".join(axes[:3]) if axes else "目标推进 / 冲突升级 / 代价兑现"
    return {
        "summary": f"以“{axis_text}”为全书结构主轴，分阶段抬升冲突强度并稳定安排爽点与回收。",
        "premise": "主角围绕长期目标持续推进，在外部高压对抗与内部价值选择中完成阶段突破与关系重排。",
        "core_conflict": "主角的阶段目标与世界规则/阵营利益持续冲突，每次破局都伴随可见代价并触发更高层对抗。",
        "theme": theme_txt,
        "audience": audience_txt,
    }


def _apply_master_outline_anti_copy_guard(
    outline: dict[str, Any],
    *,
    source_hint_lines: list[str],
    theme: str,
    audience: str,
    setting_text: str,
    idea: str,
) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(outline, dict):
        return outline, []
    safe = dict(outline)
    fallback = _fallback_outline_texts(theme=theme, audience=audience, setting_text=setting_text, idea=idea)
    rewritten_fields: list[str] = []
    for key in ("summary", "premise", "core_conflict", "theme"):
        text_value = str(safe.get(key) or "").strip()
        if not text_value or _is_copy_like_text(text_value, source_hint_lines):
            safe[key] = fallback[key]
            rewritten_fields.append(key)
    phases = safe.get("phases") if isinstance(safe.get("phases"), list) else []
    normalized_phases: list[dict[str, str]] = []
    for idx, ph in enumerate(phases):
        if not isinstance(ph, dict):
            continue
        name = str(ph.get("name") or "").strip() or f"第{idx + 1}阶段"
        goal = str(ph.get("goal") or "").strip()
        chapter_range = str(ph.get("chapter_range") or "").strip()
        if not goal or _is_copy_like_text(goal, source_hint_lines):
            goal = f"第{idx + 1}阶段围绕主线目标推进，升级冲突与代价，并完成阶段性回收。"
            rewritten_fields.append(f"phases[{idx}].goal")
        normalized_phases.append({"name": name[:80], "goal": goal[:220], "chapter_range": chapter_range[:40]})
    if normalized_phases:
        safe["phases"] = normalized_phases
    constraints = safe.get("constraints") if isinstance(safe.get("constraints"), dict) else {}
    constraints = {**constraints}
    constraints["anti_copy"] = "仅可借结构，不可复述来源文本"
    if rewritten_fields:
        constraints["anti_copy_guard"] = "triggered"
    safe["constraints"] = constraints
    return safe, sorted(set(rewritten_fields))


def _enrich_master_outline_summary(outline: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(outline, dict):
        return outline
    out = dict(outline)
    summary = str(out.get("summary") or "").strip()
    if len(summary) >= 80:
        return out
    premise = str(out.get("premise") or "").strip()
    core_conflict = str(out.get("core_conflict") or "").strip()
    phases = out.get("phases") if isinstance(out.get("phases"), list) else []
    phase_lines: list[str] = []
    for item in phases[:4]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        goal = str(item.get("goal") or "").strip()
        if not (name or goal):
            continue
        if goal:
            phase_lines.append(f"{name}:{goal}" if name else goal)
    phase_text = "；".join(phase_lines)
    merged = "。".join([x for x in [premise, f"核心冲突：{core_conflict}" if core_conflict else "", f"阶段推进：{phase_text}" if phase_text else ""] if x]).strip("。")
    if merged:
        out["summary"] = (merged + "。")[:1200]
    return out


def _validate_chapter_outline_ai_json(value: dict[str, Any] | list[Any]) -> None:
    if not isinstance(value, dict):
        raise ValueError("must be object")
    nodes = value.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("nodes must be array")


def _normalize_chapter_outline_ai_json(value: dict[str, Any], *, chapter_title: str) -> dict[str, Any]:
    node_types = ["setup", "conflict", "turn", "hook"]
    nodes_in = value.get("nodes") if isinstance(value.get("nodes"), list) else []
    nodes: list[dict[str, str]] = []
    seen: set[str] = set()
    for idx, raw in enumerate(nodes_in[:10]):
        if not isinstance(raw, dict):
            continue
        ntype = str(raw.get("type") or "").strip().lower()
        if ntype not in {"setup", "conflict", "turn", "hook", "payoff", "reveal"}:
            ntype = node_types[min(idx, len(node_types) - 1)]
        summary = str(raw.get("summary") or "").strip()
        if not summary:
            continue
        node_id = str(raw.get("node_id") or f"beat-{ntype}-{idx + 1}").strip()[:64]
        if node_id in seen:
            node_id = f"{node_id}-{idx + 1}"
        seen.add(node_id)
        nodes.append({"node_id": node_id, "type": ntype, "summary": summary[:320]})
    if len(nodes) < 4:
        defaults = [
            ("setup", "开场明确本章目标与阻力，承接总纲与卷纲推进。"),
            ("conflict", "本章核心冲突升级，形成可见压力与代价。"),
            ("turn", "关键决策触发局势转折，人物关系或目标发生变化。"),
            ("hook", "章末留出悬念与下一章驱动力，保持节奏连续。"),
        ]
        for idx, (ntype, summary) in enumerate(defaults):
            if len(nodes) >= 4:
                break
            nodes.append({"node_id": f"beat-{ntype}-{idx+1}", "type": ntype, "summary": summary})
    return {
        "chapter_title": str(value.get("chapter_title") or chapter_title or "").strip()[:120] or chapter_title or "章节",
        "nodes": nodes[:8],
    }


def _validate_master_outline_ai_json(value: dict[str, Any] | list[Any]) -> None:
    if not isinstance(value, dict):
        raise ValueError("must be object")
    required = ("summary", "premise", "core_conflict", "theme", "audience", "planned_chapters", "phases")
    for key in required:
        if key not in value:
            raise ValueError(f"missing field: {key}")
    if not isinstance(value.get("phases"), list):
        raise ValueError("phases must be array")


def _normalize_master_outline_ai_json(value: dict[str, Any], *, fallback_planned: int, hint_count: int) -> dict[str, Any]:
    planned_raw = value.get("planned_chapters")
    try:
        planned = int(planned_raw)
    except Exception:
        planned = int(fallback_planned)
    planned = max(1, min(9999, planned))

    phases_in = value.get("phases") if isinstance(value.get("phases"), list) else []
    phases: list[dict[str, str]] = []
    for item in phases_in[:20]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()[:80]
        goal = str(item.get("goal") or "").strip()[:220]
        chapter_range = str(item.get("chapter_range") or "").strip()[:40]
        if not name and not goal:
            continue
        phases.append({"name": name or "阶段", "goal": goal, "chapter_range": chapter_range})
    constraints_in = value.get("constraints") if isinstance(value.get("constraints"), dict) else {}
    constraints = {
        "anti_copy": str(constraints_in.get("anti_copy") or "仅可借结构，不可复述来源文本").strip()[:120],
        "continuity": str(constraints_in.get("continuity") or "生成章节需保持总纲→卷纲→章纲一致").strip()[:120],
    }
    return {
        "schema": "writing_master_outline_v1",
        "summary": str(value.get("summary") or "").strip()[:1200],
        "planned_chapters": planned,
        "premise": str(value.get("premise") or "").strip()[:1200],
        "core_conflict": str(value.get("core_conflict") or "").strip()[:1200],
        "theme": str(value.get("theme") or "").strip()[:300],
        "audience": str(value.get("audience") or "").strip()[:300],
        "phases": phases,
        "constraints": constraints,
        "splitbook_hints_count": max(0, int(hint_count or 0)),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


async def _merge_splitbook_hints(
    db: AsyncSession,
    *,
    splitbook_id: str,
    hints: dict[str, Any],
) -> dict[str, Any]:
    out = {
        "sources": [str(x) for x in (hints.get("sources") or []) if str(x).strip()][:8],
        "conflicts": [str(x) for x in (hints.get("conflicts") or []) if str(x).strip()][:8],
        "foreshadows": [str(x) for x in (hints.get("foreshadows") or []) if str(x).strip()][:8],
        "payoffs": [str(x) for x in (hints.get("payoffs") or []) if str(x).strip()][:8],
        "growths": [str(x) for x in (hints.get("growths") or []) if str(x).strip()][:8],
        "strategies": [str(x) for x in (hints.get("strategies") or []) if str(x).strip()][:8],
    }
    sb = await get_splitbook(db, splitbook_id)
    if not sb:
        out["total_lines"] = sum(len(out[k]) for k in ("conflicts", "foreshadows", "payoffs", "growths", "strategies"))
        return out
    sb_name = str(sb.get("name") or "").strip()
    if sb_name and sb_name not in out["sources"]:
        out["sources"].append(sb_name)
    try:
        outline = await build_splitbook_outline(db, splitbook_id)
        chapters = outline.get("chapters") if isinstance(outline, dict) else []
        if isinstance(chapters, list):
            for ch in chapters[:24]:
                if not isinstance(ch, dict):
                    continue
                summary = ch.get("summary") if isinstance(ch.get("summary"), dict) else {}
                c = str(summary.get("conflict") or "").strip()
                if c and c not in out["conflicts"] and len(out["conflicts"]) < 8:
                    out["conflicts"].append(c)
                beats = ch.get("beats") if isinstance(ch.get("beats"), dict) else {}
                for line in [str(x).strip() for x in (beats.get("foreshadow") or []) if str(x).strip()]:
                    if line not in out["foreshadows"] and len(out["foreshadows"]) < 8:
                        out["foreshadows"].append(line)
                for line in [str(x).strip() for x in (beats.get("payoff") or []) if str(x).strip()]:
                    if line not in out["payoffs"] and len(out["payoffs"]) < 8:
                        out["payoffs"].append(line)
    except Exception:
        pass
    try:
        ledger = await get_splitbook_ledger_view(db, splitbook_id, view="chapter", limit=200)
        rows = ledger.get("rows") if isinstance(ledger, dict) else []
        if isinstance(rows, list):
            for row in rows[:40]:
                if not isinstance(row, dict):
                    continue
                who = str(row.get("character_name") or row.get("name") or "").strip()
                stage = str(row.get("growth_stage") or row.get("latest_stage") or "").strip()
                pressure = str(row.get("pressure") or row.get("latest_pressure") or "").strip()
                cost = str(row.get("cost") or row.get("latest_cost") or "").strip()
                gain = str(row.get("gain") or row.get("latest_gain") or "").strip()
                if not who:
                    continue
                line = f"{who}: 阶段={stage or '待补充'}；压力={pressure or '待补充'}；代价={cost or '待补充'}；收获={gain or '待补充'}"
                if line not in out["growths"] and len(out["growths"]) < 8:
                    out["growths"].append(line)
    except Exception:
        pass
    if out["sources"]:
        strategy_line = f"优先复用拆书结构节奏（来源：{' / '.join(out['sources'][:3])}），禁止复述原文。"
        if strategy_line not in out["strategies"] and len(out["strategies"]) < 8:
            out["strategies"].append(strategy_line)
    out["total_lines"] = sum(len(out[k]) for k in ("conflicts", "foreshadows", "payoffs", "growths", "strategies"))
    return out


def _apply_structure_hints_to_volume_draft(draft: dict, hints: dict[str, Any]) -> dict:
    if not isinstance(draft, dict):
        return draft
    total_lines = int(hints.get("total_lines") or 0)
    if total_lines <= 0:
        return draft
    assumptions = draft.get("assumptions") if isinstance(draft.get("assumptions"), dict) else {}
    items = draft.get("items") if isinstance(draft.get("items"), list) else []
    assumptions = {**assumptions}
    assumptions["external_structure_hints"] = {
        "sources": [str(x) for x in (hints.get("sources") or []) if str(x).strip()][:8],
        "total_lines": total_lines,
        "counts": {
            "conflicts": len(hints.get("conflicts") or []),
            "foreshadows": len(hints.get("foreshadows") or []),
            "payoffs": len(hints.get("payoffs") or []),
            "growths": len(hints.get("growths") or []),
            "strategies": len(hints.get("strategies") or []),
        },
    }

    def _append_hint(kind: str, lines: list[str], window: str, priority: int, max_append: int = 2) -> None:
        if not lines:
            return
        added = 0
        for line in lines:
            txt = str(line or "").strip()
            if not txt:
                continue
            if any(txt in str(it.get("summary") or "") for it in items):
                continue
            items.append(
                {
                    "kind": kind,
                    "ref_id": "",
                    "summary": f"融合拆书结构：{txt}",
                    "target_window": window,
                    "target_p_vol_min": 0.2 if window == "vol_setup" else 0.55 if window == "vol_build" else 0.78,
                    "target_p_vol_max": 0.5 if window == "vol_setup" else 0.82 if window == "vol_build" else 0.98,
                    "priority": int(priority),
                    "must_happen": False,
                    "meta": {
                        "external_structure_hint": True,
                        "hint_kind": kind,
                        "source_splitbooks": assumptions["external_structure_hints"]["sources"],
                    },
                }
            )
            added += 1
            if added >= max_append:
                break

    _append_hint("conflict", list(hints.get("conflicts") or []), "vol_build", 4, 2)
    _append_hint("foreshadow_seed", list(hints.get("foreshadows") or []), "vol_setup", 3, 2)
    _append_hint("foreshadow_payoff", list(hints.get("payoffs") or []), "vol_spike", 4, 2)
    _append_hint("growth", list(hints.get("growths") or []), "vol_build", 4, 2)
    _append_hint("combo", list(hints.get("strategies") or []), "vol_release", 3, 1)
    return {"assumptions": assumptions, "items": items}


def _validate_volume_plan_refine_output(value: dict[str, Any] | list[Any]) -> None:
    if not isinstance(value, dict):
        raise ValueError("must be object")
    items = value.get("items")
    if not isinstance(items, list):
        raise ValueError("items must be array")


def _normalize_volume_plan_refine_output(value: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
    rows = value.get("items") if isinstance(value.get("items"), list) else []
    out: list[dict[str, Any]] = []
    for row in rows[: max(1, min(40, limit))]:
        if not isinstance(row, dict):
            continue
        try:
            index = int(row.get("index"))
        except Exception:
            continue
        summary = str(row.get("summary") or "").strip()
        if index < 0 or not summary:
            continue
        out.append({"index": index, "summary": summary[:320]})
    return out


async def _refine_volume_plan_with_ai(
    *,
    draft: dict[str, Any],
    volume_goal: str,
    volume_theme: str,
    target_pacing: str,
    structure_hints: dict[str, Any],
    splitbook_outline_reference: dict[str, Any],
    strict: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(draft, dict):
        if strict:
            raise RuntimeError("VOLUME_PLAN_AI_UNAVAILABLE:draft_invalid")
        return draft, {"applied": False, "reason": "draft_invalid"}
    items = draft.get("items") if isinstance(draft.get("items"), list) else []
    if not items:
        if strict:
            raise RuntimeError("VOLUME_PLAN_AI_UNAVAILABLE:items_empty")
        return draft, {"applied": False, "reason": "items_empty"}

    sample_items: list[dict[str, Any]] = []
    for idx, it in enumerate(items[:12]):
        if not isinstance(it, dict):
            continue
        sample_items.append(
            {
                "index": idx,
                "kind": str(it.get("kind") or ""),
                "target_window": str(it.get("target_window") or ""),
                "priority": int(it.get("priority") or 3),
                "must_happen": bool(it.get("must_happen", False)),
                "summary": str(it.get("summary") or "")[:220],
            }
        )
    if not sample_items:
        if strict:
            raise RuntimeError("VOLUME_PLAN_AI_UNAVAILABLE:sample_empty")
        return draft, {"applied": False, "reason": "sample_empty"}

    safe_hints = _outline_safe_structure_hints(structure_hints)
    prompt_payload = {
        "volume_goal": str(volume_goal or "").strip(),
        "volume_theme": str(volume_theme or "").strip(),
        "target_pacing": str(target_pacing or "mid").strip(),
        "plan_items": sample_items,
        "splitbook_outline_reference": splitbook_outline_reference if isinstance(splitbook_outline_reference, dict) else {},
        "structure_hints": safe_hints,
        "requirements": {
            "language": "简体中文",
            "rewrite_only_summary": True,
            "keep_kind_window_priority": True,
            "anti_copy": "仅可借结构节奏，禁止复述来源句子",
        },
    }
    user_prompt = (
        "请优化卷纲条目的 summary，使其更可执行、节奏更清晰。\n"
        "规则：\n"
        "1) 只可修改 summary；不得改变 index、kind、target_window、priority、must_happen。\n"
        "2) summary 必须体现目标-阻力-推进/回收，不要空话。\n"
        "3) 仅借鉴拆书结构，不可复述原文。\n"
        "4) 仅输出 JSON。\n\n"
        f"输入：{json.dumps(prompt_payload, ensure_ascii=False)}"
    )
    schema_hint = '{"items":[{"index":0,"summary":"string"}]}'
    try:
        client = OllamaClient(settings.ollama_host)
        raw = await client.chat_json(
            model=DEFAULT_LLM_MODEL,
            user=user_prompt,
            system="你是小说卷纲策划编辑。只输出合法 JSON。",
            temperature=0.25,
            max_tokens=1400,
            timeout_s=120,
            retries=1,
            schema_hint=schema_hint,
            validate=_validate_volume_plan_refine_output,
            meta={"route": "volume_plan_refine", "item_count": len(sample_items)},
        )
    except Exception as exc:
        if strict:
            raise RuntimeError(f"VOLUME_PLAN_AI_UNAVAILABLE:llm_failed:{str(exc)[:120]}") from exc
        return draft, {"applied": False, "reason": f"llm_failed:{str(exc)[:120]}"}

    rewrites = _normalize_volume_plan_refine_output(raw if isinstance(raw, dict) else {}, limit=len(sample_items))
    if not rewrites:
        return draft, {"applied": False, "reason": "rewrite_empty"}
    next_items = [dict(x) if isinstance(x, dict) else x for x in items]
    changed = 0
    for row in rewrites:
        idx = int(row.get("index") or -1)
        if idx < 0 or idx >= len(next_items):
            continue
        target = next_items[idx]
        if not isinstance(target, dict):
            continue
        summary = str(row.get("summary") or "").strip()
        if not summary:
            continue
        if summary != str(target.get("summary") or ""):
            target["summary"] = summary
            changed += 1
    out = dict(draft)
    out["items"] = next_items
    assumptions = out.get("assumptions") if isinstance(out.get("assumptions"), dict) else {}
    assumptions = dict(assumptions)
    assumptions["ai_refine"] = {
        "enabled": True,
        "changed_items": changed,
        "sample_size": len(sample_items),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    out["assumptions"] = assumptions
    return out, {"applied": changed > 0, "changed_items": changed, "sample_size": len(sample_items)}


async def _build_volume_plan_auto_draft(
    db: AsyncSession,
    *,
    book_id: str,
    volume_row: dict,
    volume_goal: str,
    volume_theme: str,
    target_pacing: str,
    reason: str,
) -> dict:
    volume_id = str(volume_row.get("volume_id") or "")
    start_no = int(volume_row.get("start_chapter_no") or 1)
    end_no = int(volume_row.get("end_chapter_no") or start_no)
    volume_no = int(volume_row.get("volume_no") or 1)
    chapter_count = max(1, end_no - start_no + 1)
    windows = _volume_window_ranges()
    mix = _volume_goal_profile(volume_goal, chapter_count, target_pacing)
    picked_templates = await _pick_structure_templates_for_plan(
        db,
        book_id=book_id,
        volume_no=volume_no,
        volume_goal=volume_goal,
        volume_theme=volume_theme,
        target_pacing=target_pacing,
    )
    selected_tpl = picked_templates.get("selected") if isinstance(picked_templates.get("selected"), dict) else {}
    payoff_tpl = selected_tpl.get("payoff") if isinstance(selected_tpl.get("payoff"), dict) else None
    cliff_tpl = selected_tpl.get("cliff") if isinstance(selected_tpl.get("cliff"), dict) else None
    vol_tpl = selected_tpl.get("volume_plan") if isinstance(selected_tpl.get("volume_plan"), dict) else None
    if vol_tpl and isinstance(vol_tpl.get("pattern"), dict):
        combo = vol_tpl["pattern"].get("combo") if isinstance(vol_tpl["pattern"].get("combo"), list) else []
        if combo:
            payoff_combo = sum(1 for x in combo if isinstance(x, dict) and str(x.get("kind") or "") == "foreshadow_payoff")
            seed_combo = sum(1 for x in combo if isinstance(x, dict) and str(x.get("kind") or "") == "foreshadow_seed")
            if payoff_combo > 0:
                mix["payoff_count"] = max(1, min(4, payoff_combo))
            if seed_combo > 0:
                mix["seed_count"] = max(1, min(3, seed_combo))

    combo_pick = await _pick_structure_combos_for_plan(
        db,
        book_id=book_id,
        volume_no=volume_no,
        goal_tags=(
            picked_templates.get("goal_tags")
            if isinstance(picked_templates.get("goal_tags"), list)
            else []
        ),
    )
    selected_combos = combo_pick.get("selected") if isinstance(combo_pick.get("selected"), dict) else {}

    default_shaping = {
        "max_total_boost": 0.35,
        "sigma_scale": 0.7,
        "A_by_kind": {
            "growth": {"conflict": 0.22, "tension": 0.18, "growth": 0.15},
            "foreshadow_payoff": {"reveal": 0.18, "tension": 0.12},
            "cliffhanger": {"tension": 0.20},
            "foreshadow_seed": {"tension": 0.06},
        },
        "learning": {
            "A_growth": 0.22,
            "A_payoff": 0.18,
            "wins_growth": 0,
            "loss_growth": 0,
            "wins_payoff": 0,
            "loss_payoff": 0,
        },
    }
    assumptions = {
        "start_chapter_no": start_no,
        "end_chapter_no": end_no,
        "windows": {k: [v[0], v[1]] for k, v in windows.items()},
        "shaping": default_shaping,
        "reason": reason,
        "volume_goal": volume_goal,
        "volume_theme": volume_theme,
        "target_pacing": target_pacing,
        "planner_mix": mix,
        "structure_goal_tags": picked_templates.get("goal_tags") if isinstance(picked_templates.get("goal_tags"), list) else [],
        "selected_structure_templates": {
            k: {
                "template_id": str(v.get("template_id") or ""),
                "subtype": str(v.get("subtype") or ""),
                "risk_score": float(v.get("risk_score") or 0.0),
                "fingerprint": str(v.get("fingerprint") or ""),
                "source_book_hash": str(v.get("source_book_hash") or ""),
            }
            for k, v in selected_tpl.items()
            if isinstance(v, dict)
        },
        "selected_combos": {
            k: {
                "combo_id": str(v.get("combo_id") or ""),
                "fingerprint": str(v.get("fingerprint") or ""),
                "rotation_group": str(v.get("rotation_group") or ""),
                "risk_score": float(v.get("risk_score") or 0.0),
                "score": float(v.get("_score") or 0.0),
                "rotation_penalty": float(v.get("_rotation_penalty") or 0.0),
                "group_penalty": float(v.get("_group_penalty") or 0.0),
                "pin_bonus": float(v.get("_pin_bonus") or 0.0),
                "tag_overlap": int(v.get("_tag_overlap") or 0),
            }
            for k, v in selected_combos.items()
            if isinstance(v, dict)
        },
    }

    plan_items: list[dict] = []
    gm_res = await db.execute(
        text(
            """
            SELECT milestone_id::text AS milestone_id, stage, priority, planned_scope,
                   planned_chapter_no, planned_volume_id::text AS planned_volume_id, status,
                   title, trigger, cost, choice_text, payoff_template_type
            FROM growth_milestone
            WHERE book_id=CAST(:book_id AS uuid)
              AND status IN ('planned','seeded','in_progress')
            ORDER BY
              CASE WHEN stage='breakthrough' THEN 0 ELSE 1 END,
              priority DESC,
              COALESCE(planned_chapter_no, 999999) ASC,
              milestone_no ASC
            LIMIT 120
            """
        ),
        {"book_id": book_id},
    )
    growth_candidates: list[dict] = []
    for r in gm_res.mappings().all():
        rr = dict(r)
        planned_volume_id = str(rr.get("planned_volume_id") or "")
        planned_ch_no = int(rr.get("planned_chapter_no") or 0)
        if planned_volume_id and planned_volume_id != volume_id:
            continue
        if not planned_volume_id and planned_ch_no and (planned_ch_no < start_no or planned_ch_no > end_no):
            continue
        growth_candidates.append(rr)
    for rr in growth_candidates[: int(mix["growth_count"])]:
        stage = str(rr.get("stage") or "")
        window = _window_for_stage(stage)
        if stage == "breakthrough":
            window = "vol_spike"
        w = windows.get(window) or (0.18, 0.65)
        summary = _make_plan_item_summary(
            kind="growth",
            title=str(rr.get("title") or ""),
            window=window,
            volume_goal=volume_goal,
        )
        plan_items.append(
            {
                "kind": "growth",
                "ref_id": str(rr.get("milestone_id") or ""),
                "summary": summary,
                "target_window": window,
                "target_p_vol_min": w[0],
                "target_p_vol_max": w[1],
                "priority": max(4, int(rr.get("priority") or 3)),
                "must_happen": True,
                "meta": {
                    "stage": stage,
                    "status": str(rr.get("status") or ""),
                    "trigger": str(rr.get("trigger") or ""),
                    "cost": str(rr.get("cost") or ""),
                    "choice_text": str(rr.get("choice_text") or ""),
                    "payoff_template_type": str(rr.get("payoff_template_type") or ""),
                },
            }
        )

    fs_res = await db.execute(
        text(
            """
            SELECT foreshadow_id::text AS foreshadow_id, status, priority, type, title
            FROM foreshadow
            WHERE book_id=CAST(:book_id AS uuid)
              AND (volume_id IS NULL OR volume_id=CAST(:volume_id AS uuid))
              AND status IN ('seeded','reinforced','payoff_planned')
            ORDER BY
              CASE WHEN status='payoff_planned' THEN 0 ELSE 1 END,
              priority DESC,
              updated_at ASC
            LIMIT 120
            """
        ),
        {"book_id": book_id, "volume_id": volume_id},
    )
    foreshadows = [dict(r) for r in fs_res.mappings().all()]
    payoff_candidates = [x for x in foreshadows if str(x.get("status") or "") in {"payoff_planned", "reinforced", "seeded"}]
    payoff_map = {
        "mystery": "reversal",
        "secret": "misinterpretation",
        "threat": "cost",
        "artifact": "cost",
        "relationship": "emotional",
        "promise": "emotional",
    }
    for rr in payoff_candidates[: int(mix["payoff_count"])]:
        window = "vol_spike"
        w = windows.get(window) or (0.65, 0.90)
        f_type = str(rr.get("type") or "").strip().lower()
        payoff_type = payoff_map.get(f_type, "reversal")
        if payoff_tpl:
            payoff_type = str(payoff_tpl.get("subtype") or payoff_type)
        intensity = 3 if w[1] >= 0.9 else 2
        summary = _make_plan_item_summary(
            kind="foreshadow_payoff",
            title=str(rr.get("title") or ""),
            window=window,
            payoff_type=payoff_type,
            intensity=intensity,
            volume_goal=volume_goal,
        )
        plan_items.append(
            {
                "kind": "foreshadow_payoff",
                "ref_id": str(rr.get("foreshadow_id") or ""),
                "summary": summary,
                "target_window": window,
                "target_p_vol_min": w[0],
                "target_p_vol_max": 0.92,
                "priority": max(4, int(rr.get("priority") or 3)),
                "must_happen": True,
                "meta": {
                    "status": str(rr.get("status") or ""),
                    "foreshadow_type": f_type,
                    "payoff_template_type": payoff_type,
                    "intensity": intensity,
                    "structure_template_id": str(payoff_tpl.get("template_id") or "") if payoff_tpl else "",
                },
            }
        )

    for idx in range(int(mix["seed_count"])):
        window = "vol_release"
        w = windows.get(window) or (0.90, 1.00)
        title = f"下一卷伏笔#{idx + 1}"
        summary = _make_plan_item_summary(kind="foreshadow_seed", title=title, window=window, volume_goal=volume_goal)
        plan_items.append(
            {
                "kind": "foreshadow_seed",
                "ref_id": "",
                "summary": summary,
                "target_window": window,
                "target_p_vol_min": max(w[0], 0.90 + idx * 0.03),
                "target_p_vol_max": min(0.99, 0.96 + idx * 0.02),
                "priority": 3,
                "must_happen": True,
                "meta": {
                    "auto_seed": True,
                    "seed_index": idx + 1,
                    "seed_prompt": f"围绕本卷目标“{volume_goal or volume_theme or '主线推进'}”埋一个下一卷问题句",
                },
            }
        )

    w_spike = windows["vol_spike"]
    plan_items.append(
        {
            "kind": "cliffhanger",
            "ref_id": "",
            "summary": _make_plan_item_summary(kind="cliffhanger", title="", window="vol_release", volume_goal=volume_goal),
            "target_window": "vol_release",
            "target_p_vol_min": 0.94,
            "target_p_vol_max": 1.00,
            "priority": 5,
            "must_happen": True,
            "meta": {
                "auto": True,
                "rule": "end_with_question_hook",
                "source_window": [w_spike[0], w_spike[1]],
                "cliff_style": str(cliff_tpl.get("subtype") or "") if cliff_tpl else "",
                "structure_template_id": str(cliff_tpl.get("template_id") or "") if cliff_tpl else "",
            },
        }
    )

    # combo-level plan items (setup/mid/reveal/end)
    combo_patterns = _default_combo_patterns()

    def _append_combo(combo_type: str, window: str, priority: int, must_happen: bool = True) -> None:
        cp_selected = selected_combos.get(combo_type) if isinstance(selected_combos.get(combo_type), dict) else None
        cp = (
            cp_selected.get("pattern")
            if cp_selected and isinstance(cp_selected.get("pattern"), dict)
            else combo_patterns.get(combo_type)
        )
        cp = cp if isinstance(cp, dict) else {}
        steps = cp.get("steps") if isinstance(cp.get("steps"), list) else []
        constraints = cp.get("constraints") if isinstance(cp.get("constraints"), dict) else {}
        w = windows.get(window) or (0.18, 0.65)
        fp = str(cp_selected.get("fingerprint") or "") if cp_selected else ""
        if not fp:
            fp = _combo_fingerprint(combo_type, window, steps, constraints)
        combo_id = str(cp_selected.get("combo_id") or "") if cp_selected else ""
        rotation_group = (
            str(cp_selected.get("rotation_group") or "")
            if cp_selected
            else f"{combo_type}:{window}"
        )
        plan_items.append(
            {
                "kind": "combo",
                "ref_id": combo_id,
                "summary": _make_plan_item_summary(kind="combo", title=combo_type, window=window, volume_goal=volume_goal),
                "target_window": window,
                "target_p_vol_min": float(w[0]),
                "target_p_vol_max": float(w[1]),
                "priority": int(priority),
                "must_happen": bool(must_happen),
                "meta": {
                    "combo_type": combo_type,
                    "combo_fingerprint": fp,
                    "combo_pattern": {"steps": steps, "constraints": constraints},
                    "combo_rotation_group": rotation_group,
                    "combo_selected_from_library": bool(cp_selected),
                    "combo_score": float(cp_selected.get("_score") or 0.0) if cp_selected else 0.0,
                    "combo_rotation_penalty": float(cp_selected.get("_rotation_penalty") or 0.0) if cp_selected else 0.0,
                    "combo_group_penalty": float(cp_selected.get("_group_penalty") or 0.0) if cp_selected else 0.0,
                },
            }
        )

    _append_combo("setup_hook_combo", "vol_setup", 4, True)
    _append_combo("mid_spike_combo", "vol_build", 4, True)
    _append_combo("reveal_combo", "vol_spike", 4, True)
    _append_combo("vol_end_combo", "vol_release", 5, True)

    return {"assumptions": assumptions, "items": plan_items}


async def _create_volume_plan_auto(
    db: AsyncSession,
    *,
    book_id: str,
    volume_row: dict,
    note: str,
    reason: str,
    volume_goal: str = "",
    volume_theme: str = "",
    target_pacing: str = "mid",
    draft_plan: dict | None = None,
) -> dict:
    volume_id = str(volume_row.get("volume_id") or "")
    if not volume_id:
        raise RuntimeError("VOLUME_NOT_FOUND")
    draft = draft_plan if isinstance(draft_plan, dict) else await _build_volume_plan_auto_draft(
        db,
        book_id=book_id,
        volume_row=volume_row,
        volume_goal=volume_goal,
        volume_theme=volume_theme,
        target_pacing=target_pacing,
        reason=reason,
    )
    assumptions = draft.get("assumptions") if isinstance(draft.get("assumptions"), dict) else {}
    plan_items = draft.get("items") if isinstance(draft.get("items"), list) else []
    prev_res = await db.execute(
        text(
            """
            SELECT vol_plan_id::text AS vol_plan_id, version
            FROM volume_plan
            WHERE volume_id=CAST(:volume_id AS uuid)
            ORDER BY version DESC
            LIMIT 1
            """
        ),
        {"volume_id": volume_id},
    )
    prev = prev_res.mappings().first()
    next_version = int(prev.get("version") or 0) + 1 if prev else 1
    await db.execute(
        text("UPDATE volume_plan SET status='archived' WHERE volume_id=CAST(:volume_id AS uuid) AND status='active'"),
        {"volume_id": volume_id},
    )
    ins = await db.execute(
        text(
            """
            INSERT INTO volume_plan(book_id, volume_id, version, status, assumptions, note)
            VALUES (
              CAST(:book_id AS uuid), CAST(:volume_id AS uuid), :version, 'active',
              CAST(:assumptions AS jsonb), :note
            )
            RETURNING vol_plan_id::text AS vol_plan_id
            """
        ),
        {
            "book_id": book_id,
            "volume_id": volume_id,
            "version": next_version,
            "assumptions": json.dumps(assumptions, ensure_ascii=False),
            "note": note or "auto_generated",
        },
    )
    vol_plan_id = str(ins.scalar_one())

    for it in plan_items:
        kind = str(it.get("kind") or "")
        it_ref_id = str(it.get("ref_id") or "")
        it_meta = it.get("meta") if isinstance(it.get("meta"), dict) else {}
        if kind == "combo":
            combo_fp = str(it_meta.get("combo_fingerprint") or "").strip()
            combo_type = str(it_meta.get("combo_type") or "vol_end_combo").strip().lower()
            combo_pattern = it_meta.get("combo_pattern") if isinstance(it_meta.get("combo_pattern"), dict) else {}
            combo_tags = assumptions.get("structure_goal_tags") if isinstance(assumptions.get("structure_goal_tags"), list) else []
            combo_tags = [str(x) for x in combo_tags if str(x).strip()]
            if str(it.get("target_window") or "").strip():
                combo_tags.append(str(it.get("target_window")))
            combo_tags = sorted(list(dict.fromkeys(combo_tags)))[:20]
            if not combo_fp:
                combo_steps = combo_pattern.get("steps") if isinstance(combo_pattern.get("steps"), list) else []
                combo_constraints = combo_pattern.get("constraints") if isinstance(combo_pattern.get("constraints"), dict) else {}
                combo_fp = _combo_fingerprint(combo_type, str(it.get("target_window") or ""), combo_steps, combo_constraints)
                it_meta["combo_fingerprint"] = combo_fp

            combo_row = await db.execute(
                text(
                    """
                    SELECT combo_id::text AS combo_id
                    FROM structure_combo
                    WHERE book_id=CAST(:book_id AS uuid) AND fingerprint=:fingerprint
                    LIMIT 1
                    """
                ),
                {"book_id": book_id, "fingerprint": combo_fp},
            )
            combo = combo_row.mappings().first()
            if combo and combo.get("combo_id"):
                it_ref_id = str(combo["combo_id"])
                await db.execute(
                    text(
                        """
                        UPDATE structure_combo
                        SET combo_type=:combo_type,
                            tags=:tags,
                            pattern=CAST(:pattern AS jsonb),
                            rotation_group=:rotation_group,
                            last_used_volume_no=:last_used_volume_no,
                            meta=COALESCE(meta, '{}'::jsonb) || CAST(:meta_patch AS jsonb)
                        WHERE combo_id=CAST(:combo_id AS uuid)
                        """
                    ),
                    {
                        "combo_id": it_ref_id,
                        "combo_type": combo_type,
                        "tags": combo_tags,
                        "pattern": json.dumps(combo_pattern if isinstance(combo_pattern, dict) else {}, ensure_ascii=False),
                        "rotation_group": str(it_meta.get("combo_rotation_group") or f"{combo_type}:{str(it.get('target_window') or '')}"),
                        "last_used_volume_no": int(volume_row.get("volume_no") or 0) or None,
                        "meta_patch": json.dumps(
                            {
                                "from_plan_version": next_version,
                                "target_window": str(it.get("target_window") or ""),
                            },
                            ensure_ascii=False,
                        ),
                    },
                )
            else:
                ins_combo = await db.execute(
                    text(
                        """
                        INSERT INTO structure_combo(
                          book_id, combo_type, fingerprint, pattern, tags, risk_score, policy,
                          rotation_group, last_used_volume_no, meta
                        )
                        VALUES(
                          CAST(:book_id AS uuid), :combo_type, :fingerprint, CAST(:pattern AS jsonb), :tags, :risk_score, 'normal',
                          :rotation_group, :last_used_volume_no, CAST(:meta AS jsonb)
                        )
                        RETURNING combo_id::text AS combo_id
                        """
                    ),
                    {
                        "book_id": book_id,
                        "combo_type": combo_type,
                        "fingerprint": combo_fp,
                        "pattern": json.dumps(combo_pattern if isinstance(combo_pattern, dict) else {}, ensure_ascii=False),
                        "tags": combo_tags,
                        "risk_score": 0.05,
                        "rotation_group": str(it_meta.get("combo_rotation_group") or f"{combo_type}:{str(it.get('target_window') or '')}"),
                        "last_used_volume_no": int(volume_row.get("volume_no") or 0) or None,
                        "meta": json.dumps(
                            {
                                "created_from": "volume_plan_auto",
                                "from_plan_version": next_version,
                                "target_window": str(it.get("target_window") or ""),
                            },
                            ensure_ascii=False,
                        ),
                    },
                )
                it_ref_id = str(ins_combo.scalar_one())
            it["ref_id"] = it_ref_id
            it["meta"] = it_meta

        await db.execute(
            text(
                """
                INSERT INTO volume_plan_item(
                  vol_plan_id, kind, ref_id, summary, target_window, target_p_vol_min, target_p_vol_max,
                  priority, must_happen, meta
                )
                VALUES (
                  CAST(:vol_plan_id AS uuid), :kind, CAST(NULLIF(:ref_id, '') AS uuid), :summary, :target_window,
                  :target_p_vol_min, :target_p_vol_max, :priority, :must_happen, CAST(:meta AS jsonb)
                )
                """
            ),
            {
                "vol_plan_id": vol_plan_id,
                "kind": kind,
                "ref_id": it_ref_id,
                "summary": str(it.get("summary") or ""),
                "target_window": str(it.get("target_window") or "vol_build"),
                "target_p_vol_min": float(it.get("target_p_vol_min") or 0.18),
                "target_p_vol_max": float(it.get("target_p_vol_max") or 0.65),
                "priority": int(it.get("priority") or 3),
                "must_happen": bool(it.get("must_happen", True)),
                "meta": json.dumps(it.get("meta") if isinstance(it.get("meta"), dict) else {}, ensure_ascii=False),
            },
        )

    selected_templates = assumptions.get("selected_structure_templates") if isinstance(assumptions.get("selected_structure_templates"), dict) else {}
    volume_no = int(volume_row.get("volume_no") or 0)
    for _, meta in selected_templates.items():
        if not isinstance(meta, dict):
            continue
        tid = str(meta.get("template_id") or "").strip()
        if not tid:
            continue
        await db.execute(
            text(
                """
                UPDATE structure_template
                SET last_used_volume_no=:volume_no
                WHERE template_id=CAST(:template_id AS uuid)
                """
            ),
            {"template_id": tid, "volume_no": volume_no if volume_no > 0 else None},
        )

    if prev and int(prev.get("version") or 0) > 0:
        await db.execute(
            text(
                """
                INSERT INTO volume_plan_audit(book_id, volume_id, from_version, to_version, reason, evidence)
                VALUES (
                  CAST(:book_id AS uuid), CAST(:volume_id AS uuid), :from_version, :to_version, :reason,
                  CAST(:evidence AS jsonb)
                )
                """
            ),
            {
                "book_id": book_id,
                "volume_id": volume_id,
                "from_version": int(prev.get("version") or 0),
                "to_version": int(next_version),
                "reason": reason,
                "evidence": json.dumps({"note": note, "plan_items": len(plan_items)}, ensure_ascii=False),
            },
        )

    await db.commit()
    plan = await _load_active_volume_plan(db, book_id=book_id, volume_id=volume_id)
    return {
        "ok": True,
        "book_id": book_id,
        "volume_id": volume_id,
        "version": int(next_version),
        "plan": plan,
    }


@app.get("/v1/books/{book_id}/volumes/{volume_id}/plan/versions")
async def volume_plan_versions_route(
    book_id: UUID,
    volume_id: UUID,
    limit: int = Query(default=30, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = await db.execute(
        text(
            """
            SELECT vol_plan_id::text AS vol_plan_id, version, status, assumptions, note, created_at
            FROM volume_plan
            WHERE book_id=CAST(:book_id AS uuid)
              AND volume_id=CAST(:volume_id AS uuid)
            ORDER BY version DESC
            LIMIT :limit
            """
        ),
        {"book_id": str(book_id), "volume_id": str(volume_id), "limit": int(limit)},
    )
    return {"book_id": str(book_id), "volume_id": str(volume_id), "items": [dict(r) for r in rows.mappings().all()]}


@app.delete("/v1/books/{book_id}/volumes/{volume_id}/plan/{version}")
async def volume_plan_delete_version_route(
    book_id: UUID,
    volume_id: UUID,
    version: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    row_target = await db.execute(
        text(
            """
            SELECT vol_plan_id::text AS vol_plan_id, version, status
            FROM volume_plan
            WHERE book_id=CAST(:book_id AS uuid)
              AND volume_id=CAST(:volume_id AS uuid)
              AND version=:version
            LIMIT 1
            """
        ),
        {"book_id": str(book_id), "volume_id": str(volume_id), "version": int(version)},
    )
    target = row_target.mappings().first()
    if not target:
        raise HTTPException(status_code=404, detail="VOLUME_PLAN_VERSION_NOT_FOUND")

    row_count = await db.execute(
        text(
            """
            SELECT COUNT(*)::int AS n
            FROM volume_plan
            WHERE book_id=CAST(:book_id AS uuid)
              AND volume_id=CAST(:volume_id AS uuid)
            """
        ),
        {"book_id": str(book_id), "volume_id": str(volume_id)},
    )
    total = int((row_count.mappings().first() or {}).get("n") or 0)
    if total <= 1:
        raise HTTPException(status_code=400, detail="VOLUME_PLAN_DELETE_LAST_FORBIDDEN")

    deleted_version = int(target.get("version") or version)
    deleted_status = str(target.get("status") or "")
    replacement_version: int | None = None

    if deleted_status == "active":
        row_replacement = await db.execute(
            text(
                """
                SELECT version
                FROM volume_plan
                WHERE book_id=CAST(:book_id AS uuid)
                  AND volume_id=CAST(:volume_id AS uuid)
                  AND version<>:version
                ORDER BY version DESC
                LIMIT 1
                """
            ),
            {"book_id": str(book_id), "volume_id": str(volume_id), "version": deleted_version},
        )
        replacement = row_replacement.mappings().first()
        replacement_version = int((replacement or {}).get("version") or 0) or None
        if replacement_version is None:
            raise HTTPException(status_code=400, detail="VOLUME_PLAN_DELETE_NO_REPLACEMENT")

    await db.execute(
        text(
            """
            DELETE FROM volume_plan
            WHERE book_id=CAST(:book_id AS uuid)
              AND volume_id=CAST(:volume_id AS uuid)
              AND version=:version
            """
        ),
        {"book_id": str(book_id), "volume_id": str(volume_id), "version": deleted_version},
    )

    if replacement_version is not None:
        await db.execute(
            text(
                """
                UPDATE volume_plan
                SET status='archived'
                WHERE book_id=CAST(:book_id AS uuid)
                  AND volume_id=CAST(:volume_id AS uuid)
                  AND status='active'
                """
            ),
            {"book_id": str(book_id), "volume_id": str(volume_id)},
        )
        await db.execute(
            text(
                """
                UPDATE volume_plan
                SET status='active'
                WHERE book_id=CAST(:book_id AS uuid)
                  AND volume_id=CAST(:volume_id AS uuid)
                  AND version=:version
                """
            ),
            {"book_id": str(book_id), "volume_id": str(volume_id), "version": replacement_version},
        )

    cleanup_audit = await db.execute(
        text(
            """
            DELETE FROM volume_plan_audit
            WHERE book_id=CAST(:book_id AS uuid)
              AND volume_id=CAST(:volume_id AS uuid)
              AND (from_version=:version OR to_version=:version)
            RETURNING audit_id
            """
        ),
        {"book_id": str(book_id), "volume_id": str(volume_id), "version": deleted_version},
    )
    audit_deleted = len(cleanup_audit.fetchall())

    await db.commit()
    return {
        "ok": True,
        "book_id": str(book_id),
        "volume_id": str(volume_id),
        "deleted_version": deleted_version,
        "deleted_status": deleted_status,
        "replacement_version": replacement_version,
        "audit_deleted": audit_deleted,
    }


@app.post("/v1/books/{book_id}/volumes/{volume_id}/plan/{version}/promote")
async def volume_plan_promote_route(
    book_id: UUID,
    volume_id: UUID,
    version: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> dict:
    note = str((body or {}).get("note") or "")
    row_cur = await db.execute(
        text(
            """
            SELECT version
            FROM volume_plan
            WHERE book_id=CAST(:book_id AS uuid)
              AND volume_id=CAST(:volume_id AS uuid)
              AND status='active'
            ORDER BY version DESC
            LIMIT 1
            """
        ),
        {"book_id": str(book_id), "volume_id": str(volume_id)},
    )
    cur = row_cur.scalar()
    row_tgt = await db.execute(
        text(
            """
            SELECT vol_plan_id::text AS vol_plan_id, version
            FROM volume_plan
            WHERE book_id=CAST(:book_id AS uuid)
              AND volume_id=CAST(:volume_id AS uuid)
              AND version=:version
            """
        ),
        {"book_id": str(book_id), "volume_id": str(volume_id), "version": int(version)},
    )
    tgt = row_tgt.mappings().first()
    if not tgt:
        raise HTTPException(status_code=404, detail="VOLUME_PLAN_VERSION_NOT_FOUND")
    if cur == int(version):
        return {"ok": True, "book_id": str(book_id), "volume_id": str(volume_id), "active_version": int(version), "noop": True}

    await db.execute(
        text("UPDATE volume_plan SET status='archived' WHERE book_id=CAST(:book_id AS uuid) AND volume_id=CAST(:volume_id AS uuid) AND status='active'"),
        {"book_id": str(book_id), "volume_id": str(volume_id)},
    )
    await db.execute(
        text("UPDATE volume_plan SET status='active' WHERE book_id=CAST(:book_id AS uuid) AND volume_id=CAST(:volume_id AS uuid) AND version=:version"),
        {"book_id": str(book_id), "volume_id": str(volume_id), "version": int(version)},
    )
    if cur is not None:
        await db.execute(
            text(
                """
                INSERT INTO volume_plan_audit(book_id, volume_id, from_version, to_version, reason, evidence)
                VALUES (
                  CAST(:book_id AS uuid), CAST(:volume_id AS uuid), :from_version, :to_version, :reason,
                  CAST(:evidence AS jsonb)
                )
                """
            ),
            {
                "book_id": str(book_id),
                "volume_id": str(volume_id),
                "from_version": int(cur),
                "to_version": int(version),
                "reason": "promote",
                "evidence": json.dumps({"note": note}, ensure_ascii=False),
            },
        )
    await db.commit()
    return {"ok": True, "book_id": str(book_id), "volume_id": str(volume_id), "active_version": int(version), "from_version": int(cur) if cur is not None else None}


@app.post("/v1/books/{book_id}/volumes/{volume_id}/plan/rollback_last")
async def volume_plan_rollback_last_route(book_id: UUID, volume_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.execute(
        text(
            """
            SELECT from_version, to_version, audit_id::text AS audit_id
            FROM volume_plan_audit
            WHERE book_id=CAST(:book_id AS uuid)
              AND volume_id=CAST(:volume_id AS uuid)
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"book_id": str(book_id), "volume_id": str(volume_id)},
    )
    a = row.mappings().first()
    if not a:
        raise HTTPException(status_code=404, detail="VOLUME_PLAN_AUDIT_NOT_FOUND")
    from_v = int(a.get("from_version") or 0)
    to_v = int(a.get("to_version") or 0)
    if from_v <= 0:
        raise HTTPException(status_code=400, detail="INVALID_ROLLBACK_TARGET")
    await db.execute(
        text("UPDATE volume_plan SET status='archived' WHERE book_id=CAST(:book_id AS uuid) AND volume_id=CAST(:volume_id AS uuid) AND status='active'"),
        {"book_id": str(book_id), "volume_id": str(volume_id)},
    )
    await db.execute(
        text("UPDATE volume_plan SET status='active' WHERE book_id=CAST(:book_id AS uuid) AND volume_id=CAST(:volume_id AS uuid) AND version=:version"),
        {"book_id": str(book_id), "volume_id": str(volume_id), "version": from_v},
    )
    await db.execute(
        text(
            """
            INSERT INTO volume_plan_audit(book_id, volume_id, from_version, to_version, reason, evidence)
            VALUES (
              CAST(:book_id AS uuid), CAST(:volume_id AS uuid), :from_version, :to_version, 'rollback',
              CAST(:evidence AS jsonb)
            )
            """
        ),
        {
            "book_id": str(book_id),
            "volume_id": str(volume_id),
            "from_version": to_v,
            "to_version": from_v,
            "evidence": json.dumps({"rollback_of_audit_id": str(a.get("audit_id") or "")}, ensure_ascii=False),
        },
    )
    await db.commit()
    return {"ok": True, "book_id": str(book_id), "volume_id": str(volume_id), "active_version": from_v, "rollback_from": to_v}


@app.post("/v1/books/{book_id}/volumes/{volume_id}/plan/learn_from_batches")
async def volume_plan_learn_from_batches_route(book_id: UUID, volume_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    lr = float((body or {}).get("lr") or 0.02)
    lr = max(0.001, min(0.08, lr))
    recent_limit = int((body or {}).get("recent_limit") or 30)
    recent_limit = max(1, min(200, recent_limit))

    row_plan = await db.execute(
        text(
            """
            SELECT vol_plan_id::text AS vol_plan_id, version, assumptions
            FROM volume_plan
            WHERE book_id=CAST(:book_id AS uuid)
              AND volume_id=CAST(:volume_id AS uuid)
              AND status='active'
            ORDER BY version DESC
            LIMIT 1
            """
        ),
        {"book_id": str(book_id), "volume_id": str(volume_id)},
    )
    plan = row_plan.mappings().first()
    if not plan:
        raise HTTPException(status_code=404, detail="VOLUME_PLAN_NOT_FOUND")
    assumptions = plan.get("assumptions") if isinstance(plan.get("assumptions"), dict) else {}
    shaping = assumptions.get("shaping") if isinstance(assumptions.get("shaping"), dict) else {}
    learning = shaping.get("learning") if isinstance(shaping.get("learning"), dict) else {}

    a_growth = float(learning.get("A_growth") or 0.22)
    a_payoff = float(learning.get("A_payoff") or 0.18)
    wins_growth = int(learning.get("wins_growth") or 0)
    loss_growth = int(learning.get("loss_growth") or 0)
    wins_payoff = int(learning.get("wins_payoff") or 0)
    loss_payoff = int(learning.get("loss_payoff") or 0)

    rows = await db.execute(
        text(
            """
            WITH exp AS (
              SELECT
                i.batch_id,
                i.profile_id,
                i.score AS exp_score,
                r.payload AS payload
              FROM ab_batch_item i
              JOIN ab_batch_run br ON br.batch_id=i.batch_id
              LEFT JOIN report r ON r.report_id=i.report_id
              WHERE br.book_id=CAST(:book_id AS uuid)
                AND br.volume_id=CAST(:volume_id AS uuid)
                AND i.variant='exp'
                AND i.status='done'
                AND i.score IS NOT NULL
              ORDER BY br.created_at DESC
              LIMIT :recent_limit
            )
            SELECT
              e.batch_id::text AS batch_id,
              e.profile_id::text AS profile_id,
              e.exp_score::double precision AS exp_score,
              b.score::double precision AS baseline_score,
              COALESCE(e.payload->'growth_task'->>'action', '') AS growth_action,
              jsonb_array_length(COALESCE(e.payload->'foreshadow_selection'->'payoff', '[]'::jsonb))::int AS payoff_count
            FROM exp e
            LEFT JOIN ab_batch_item b
              ON b.batch_id=e.batch_id
             AND b.profile_id=e.profile_id
             AND b.variant='baseline'
             AND b.status='done'
             AND b.score IS NOT NULL
            """
        ),
        {"book_id": str(book_id), "volume_id": str(volume_id), "recent_limit": recent_limit},
    )
    samples = [dict(r) for r in rows.mappings().all()]
    growth_samples = 0
    payoff_samples = 0
    for s in samples:
        exp_score = s.get("exp_score")
        baseline_score = s.get("baseline_score")
        if exp_score is None or baseline_score is None:
            continue
        delta = float(exp_score) - float(baseline_score)
        g_action = str(s.get("growth_action") or "").strip().lower()
        payoff_count = int(s.get("payoff_count") or 0)
        if g_action in {"achieve", "advance", "reflect"}:
            growth_samples += 1
            if delta > 0:
                wins_growth += 1
                a_growth = a_growth + lr
            elif delta < 0:
                loss_growth += 1
                a_growth = a_growth - lr
        if payoff_count > 0:
            payoff_samples += 1
            if delta > 0:
                wins_payoff += 1
                a_payoff = a_payoff + lr
            elif delta < 0:
                loss_payoff += 1
                a_payoff = a_payoff - lr

    a_growth = max(0.08, min(0.5, a_growth))
    a_payoff = max(0.05, min(0.5, a_payoff))

    shaping_out = {
        **(shaping if isinstance(shaping, dict) else {}),
        "A_by_kind": {
            **((shaping.get("A_by_kind") if isinstance(shaping.get("A_by_kind"), dict) else {})),
            "growth": {
                "conflict": round(a_growth, 6),
                "tension": round(max(0.05, a_growth * 0.8), 6),
                "growth": round(max(0.04, a_growth * 0.65), 6),
            },
            "foreshadow_payoff": {
                "reveal": round(a_payoff, 6),
                "tension": round(max(0.04, a_payoff * 0.65), 6),
            },
        },
        "learning": {
            "A_growth": round(a_growth, 6),
            "A_payoff": round(a_payoff, 6),
            "wins_growth": int(wins_growth),
            "loss_growth": int(loss_growth),
            "wins_payoff": int(wins_payoff),
            "loss_payoff": int(loss_payoff),
            "last_lr": round(lr, 6),
            "last_samples": int(len(samples)),
            "growth_samples": int(growth_samples),
            "payoff_samples": int(payoff_samples),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    assumptions_out = {**assumptions, "shaping": shaping_out}
    await db.execute(
        text(
            """
            UPDATE volume_plan
            SET assumptions=CAST(:assumptions AS jsonb)
            WHERE vol_plan_id=CAST(:vol_plan_id AS uuid)
            """
        ),
        {"vol_plan_id": str(plan["vol_plan_id"]), "assumptions": json.dumps(assumptions_out, ensure_ascii=False)},
    )
    await db.commit()
    return {
        "ok": True,
        "book_id": str(book_id),
        "volume_id": str(volume_id),
        "plan_version": int(plan.get("version") or 0),
        "learning": shaping_out.get("learning"),
    }


@app.get("/v1/books/{book_id}/volumes/{volume_id}/plan/active")
async def volume_plan_active_route(book_id: UUID, volume_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    plan = await _load_active_volume_plan(db, book_id=str(book_id), volume_id=str(volume_id))
    if not plan:
        return {"book_id": str(book_id), "volume_id": str(volume_id), "plan": None}
    return {"book_id": str(book_id), "volume_id": str(volume_id), "plan": plan}


@app.post("/v1/books/{book_id}/volumes/{volume_id}/plan/preview_auto")
async def volume_plan_preview_auto_route(book_id: UUID, volume_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.execute(
        text(
            """
            SELECT volume_id::text AS volume_id, book_id::text AS book_id, volume_no, title,
                   start_chapter_no, end_chapter_no, planned_chapters, note
            FROM volume
            WHERE volume_id=CAST(:volume_id AS uuid)
              AND book_id=CAST(:book_id AS uuid)
            """
        ),
        {"book_id": str(book_id), "volume_id": str(volume_id)},
    )
    vol = row.mappings().first()
    if not vol:
        raise HTTPException(status_code=404, detail="VOLUME_NOT_FOUND")
    volume_goal = str((body or {}).get("volume_goal") or (body or {}).get("goal") or "").strip()
    volume_theme = str((body or {}).get("volume_theme") or "").strip()
    target_pacing = str((body or {}).get("target_pacing") or "mid").strip().lower()
    structure_hints = _normalize_structure_hints(body or {})
    material_guidance = _extract_material_guidance_from_refs([str(x) for x in ((body or {}).get("material_refs") or [])][:30])
    splitbook_id = _resolve_splitbook_id_from_body(body or {})
    splitbook_outline_reference = await _build_splitbook_outline_reference(db, splitbook_id=splitbook_id) if splitbook_id else {}
    draft = await _build_volume_plan_auto_draft(
        db,
        book_id=str(book_id),
        volume_row=dict(vol),
        volume_goal=volume_goal,
        volume_theme=volume_theme,
        target_pacing=target_pacing,
        reason="preview_auto",
    )
    draft = _apply_structure_hints_to_volume_draft(draft, structure_hints)
    ai_meta = {"applied": False, "reason": "disabled"}
    if not bool((body or {}).get("use_ai_refine", True)):
        raise HTTPException(status_code=400, detail="VOLUME_PLAN_AI_REQUIRED")
    try:
        draft, ai_meta = await _refine_volume_plan_with_ai(
            draft=draft,
            volume_goal=volume_goal,
            volume_theme=volume_theme,
            target_pacing=target_pacing,
            structure_hints=structure_hints,
            splitbook_outline_reference=splitbook_outline_reference,
            strict=True,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "ok": True,
        "book_id": str(book_id),
        "volume_id": str(volume_id),
        "volume_goal": volume_goal,
        "volume_theme": volume_theme,
        "target_pacing": target_pacing,
        "splitbook_id": splitbook_id or None,
        "splitbook_outline_reference": {
            "chapter_total": int(splitbook_outline_reference.get("chapter_total") or 0),
            "phase_count": len(splitbook_outline_reference.get("phase_skeleton") or []),
        }
        if splitbook_outline_reference
        else {},
        "structure_hints_applied": int(structure_hints.get("total_lines") or 0),
        "structure_hint_sources": [str(x) for x in (structure_hints.get("sources") or []) if str(x).strip()][:8],
        "ai_refine": ai_meta,
        "plan": draft,
    }


@app.post("/v1/books/{book_id}/volumes/{volume_id}/plan/apply_auto")
async def volume_plan_apply_auto_route(book_id: UUID, volume_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.execute(
        text(
            """
            SELECT volume_id::text AS volume_id, book_id::text AS book_id, volume_no, title,
                   start_chapter_no, end_chapter_no, planned_chapters, note
            FROM volume
            WHERE volume_id=CAST(:volume_id AS uuid)
              AND book_id=CAST(:book_id AS uuid)
            """
        ),
        {"book_id": str(book_id), "volume_id": str(volume_id)},
    )
    vol = row.mappings().first()
    if not vol:
        raise HTTPException(status_code=404, detail="VOLUME_NOT_FOUND")
    volume_goal = str((body or {}).get("volume_goal") or (body or {}).get("goal") or "").strip()
    volume_theme = str((body or {}).get("volume_theme") or "").strip()
    target_pacing = str((body or {}).get("target_pacing") or "mid").strip().lower()
    structure_hints = _normalize_structure_hints(body or {})
    splitbook_id = _resolve_splitbook_id_from_body(body or {})
    splitbook_outline_reference = await _build_splitbook_outline_reference(db, splitbook_id=splitbook_id) if splitbook_id else {}
    reason = str((body or {}).get("reason") or "apply_auto")
    note = str((body or {}).get("note") or "auto_apply_volume_plan")
    preview_plan = (body or {}).get("plan")
    draft_plan = preview_plan if isinstance(preview_plan, dict) else await _build_volume_plan_auto_draft(
        db,
        book_id=str(book_id),
        volume_row=dict(vol),
        volume_goal=volume_goal,
        volume_theme=volume_theme,
        target_pacing=target_pacing,
        reason=reason,
    )
    draft_plan = _apply_structure_hints_to_volume_draft(draft_plan, structure_hints)
    ai_meta = {"applied": False, "reason": "disabled"}
    if not bool((body or {}).get("use_ai_refine", True)):
        raise HTTPException(status_code=400, detail="VOLUME_PLAN_AI_REQUIRED")
    try:
        draft_plan, ai_meta = await _refine_volume_plan_with_ai(
            draft=draft_plan,
            volume_goal=volume_goal,
            volume_theme=volume_theme,
            target_pacing=target_pacing,
            structure_hints=structure_hints,
            splitbook_outline_reference=splitbook_outline_reference,
            strict=True,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    out = await _create_volume_plan_auto(
        db,
        book_id=str(book_id),
        volume_row=dict(vol),
        note=note,
        reason=reason,
        volume_goal=volume_goal,
        volume_theme=volume_theme,
        target_pacing=target_pacing,
        draft_plan=draft_plan,
    )
    out["structure_hints_applied"] = int(structure_hints.get("total_lines") or 0)
    out["structure_hint_sources"] = [str(x) for x in (structure_hints.get("sources") or []) if str(x).strip()][:8]
    out["splitbook_id"] = splitbook_id or None
    out["splitbook_outline_reference"] = {
        "chapter_total": int(splitbook_outline_reference.get("chapter_total") or 0),
        "phase_count": len(splitbook_outline_reference.get("phase_skeleton") or []),
    } if splitbook_outline_reference else {}
    out["ai_refine"] = ai_meta
    return out


@app.post("/v1/books/{book_id}/volumes/{volume_id}/plan/items/{item_id}")
async def volume_plan_item_update_route(
    book_id: UUID,
    volume_id: UUID,
    item_id: UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await db.execute(
        text(
            """
            SELECT p.vol_plan_id::text AS vol_plan_id, p.version, p.status
            FROM volume_plan_item i
            JOIN volume_plan p ON p.vol_plan_id=i.vol_plan_id
            WHERE i.item_id=CAST(:item_id AS uuid)
              AND p.book_id=CAST(:book_id AS uuid)
              AND p.volume_id=CAST(:volume_id AS uuid)
              AND p.status='active'
            LIMIT 1
            """
        ),
        {"item_id": str(item_id), "book_id": str(book_id), "volume_id": str(volume_id)},
    )
    hit = row.mappings().first()
    if not hit:
        raise HTTPException(status_code=404, detail="VOLUME_PLAN_ITEM_NOT_FOUND")
    pmin = body.get("target_p_vol_min")
    pmax = body.get("target_p_vol_max")
    pmin_f = _clamp01(float(pmin)) if pmin is not None else None
    pmax_f = _clamp01(float(pmax)) if pmax is not None else None
    if pmin_f is not None and pmax_f is not None and pmax_f < pmin_f:
        pmin_f, pmax_f = pmax_f, pmin_f
    cur_row = await db.execute(
        text(
            """
            SELECT summary, target_window, target_p_vol_min, target_p_vol_max, priority, must_happen, meta
            FROM volume_plan_item
            WHERE item_id=CAST(:item_id AS uuid)
            """
        ),
        {"item_id": str(item_id)},
    )
    cur = cur_row.mappings().first()
    if not cur:
        raise HTTPException(status_code=404, detail="VOLUME_PLAN_ITEM_NOT_FOUND")
    meta_cur = cur.get("meta") if isinstance(cur.get("meta"), dict) else {}
    meta_patch = body.get("meta") if isinstance(body.get("meta"), dict) else {}
    meta_out = {**meta_cur, **meta_patch}
    await db.execute(
        text(
            """
            UPDATE volume_plan_item
            SET
              summary=:summary,
              target_window=:target_window,
              target_p_vol_min=:target_p_vol_min,
              target_p_vol_max=:target_p_vol_max,
              priority=:priority,
              must_happen=:must_happen,
              meta=CAST(:meta AS jsonb)
            WHERE item_id=CAST(:item_id AS uuid)
            """
        ),
        {
            "item_id": str(item_id),
            "summary": str(body.get("summary") if body.get("summary") is not None else (cur.get("summary") or "")),
            "target_window": str(body.get("target_window") if body.get("target_window") is not None else (cur.get("target_window") or "vol_build")),
            "target_p_vol_min": pmin_f if pmin_f is not None else float(cur.get("target_p_vol_min") or 0.18),
            "target_p_vol_max": pmax_f if pmax_f is not None else float(cur.get("target_p_vol_max") or 0.65),
            "priority": _clamp_int(int(body.get("priority") if body.get("priority") is not None else (cur.get("priority") or 3)), 1, 5),
            "must_happen": bool(body.get("must_happen") if body.get("must_happen") is not None else bool(cur.get("must_happen", True))),
            "meta": json.dumps(meta_out, ensure_ascii=False),
        },
    )
    await db.commit()
    plan = await _load_active_volume_plan(db, book_id=str(book_id), volume_id=str(volume_id))
    return {"ok": True, "book_id": str(book_id), "volume_id": str(volume_id), "plan": plan}


@app.post("/v1/books/{book_id}/volumes/{volume_id}/plan/items_batch_update")
async def volume_plan_item_batch_update_route(
    book_id: UUID,
    volume_id: UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> dict:
    items = (body or {}).get("items") if isinstance((body or {}).get("items"), list) else []
    if not items:
        raise HTTPException(status_code=400, detail="ITEMS_REQUIRED")
    updated = 0
    for raw in items[:200]:
        if not isinstance(raw, dict):
            continue
        item_id = str(raw.get("item_id") or "").strip()
        if not item_id:
            continue
        row = await db.execute(
            text(
                """
                SELECT p.vol_plan_id::text AS vol_plan_id, p.version, p.status
                FROM volume_plan_item i
                JOIN volume_plan p ON p.vol_plan_id=i.vol_plan_id
                WHERE i.item_id=CAST(:item_id AS uuid)
                  AND p.book_id=CAST(:book_id AS uuid)
                  AND p.volume_id=CAST(:volume_id AS uuid)
                  AND p.status='active'
                LIMIT 1
                """
            ),
            {"item_id": item_id, "book_id": str(book_id), "volume_id": str(volume_id)},
        )
        hit = row.mappings().first()
        if not hit:
            continue
        cur_row = await db.execute(
            text(
                """
                SELECT summary, target_window, target_p_vol_min, target_p_vol_max, priority, must_happen, meta
                FROM volume_plan_item
                WHERE item_id=CAST(:item_id AS uuid)
                """
            ),
            {"item_id": item_id},
        )
        cur = cur_row.mappings().first()
        if not cur:
            continue
        pmin = raw.get("target_p_vol_min")
        pmax = raw.get("target_p_vol_max")
        pmin_f = _clamp01(float(pmin)) if pmin is not None else float(cur.get("target_p_vol_min") or 0.18)
        pmax_f = _clamp01(float(pmax)) if pmax is not None else float(cur.get("target_p_vol_max") or 0.65)
        if pmax_f < pmin_f:
            pmin_f, pmax_f = pmax_f, pmin_f
        meta_cur = cur.get("meta") if isinstance(cur.get("meta"), dict) else {}
        meta_patch = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
        meta_out = {**meta_cur, **meta_patch}
        await db.execute(
            text(
                """
                UPDATE volume_plan_item
                SET
                  summary=:summary,
                  target_window=:target_window,
                  target_p_vol_min=:target_p_vol_min,
                  target_p_vol_max=:target_p_vol_max,
                  priority=:priority,
                  must_happen=:must_happen,
                  meta=CAST(:meta AS jsonb)
                WHERE item_id=CAST(:item_id AS uuid)
                """
            ),
            {
                "item_id": item_id,
                "summary": str(raw.get("summary") if raw.get("summary") is not None else (cur.get("summary") or "")),
                "target_window": str(raw.get("target_window") if raw.get("target_window") is not None else (cur.get("target_window") or "vol_build")),
                "target_p_vol_min": pmin_f,
                "target_p_vol_max": pmax_f,
                "priority": _clamp_int(int(raw.get("priority") if raw.get("priority") is not None else (cur.get("priority") or 3)), 1, 5),
                "must_happen": bool(raw.get("must_happen") if raw.get("must_happen") is not None else bool(cur.get("must_happen", True))),
                "meta": json.dumps(meta_out, ensure_ascii=False),
            },
        )
        updated += 1
    await db.commit()
    plan = await _load_active_volume_plan(db, book_id=str(book_id), volume_id=str(volume_id))
    return {"ok": True, "book_id": str(book_id), "volume_id": str(volume_id), "updated": int(updated), "plan": plan}


@app.post("/v1/books/{book_id}/volumes/{volume_id}/plan/auto_generate")
async def volume_plan_auto_generate_route(book_id: UUID, volume_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.execute(
        text(
            """
            SELECT volume_id::text AS volume_id, book_id::text AS book_id, volume_no, title,
                   start_chapter_no, end_chapter_no, planned_chapters, note
            FROM volume
            WHERE volume_id=CAST(:volume_id AS uuid)
              AND book_id=CAST(:book_id AS uuid)
            """
        ),
        {"book_id": str(book_id), "volume_id": str(volume_id)},
    )
    vol = row.mappings().first()
    if not vol:
        raise HTTPException(status_code=404, detail="VOLUME_NOT_FOUND")
    note = str((body or {}).get("note") or "auto_generate_volume_plan")
    reason = str((body or {}).get("reason") or "manual_generate")
    volume_goal = str((body or {}).get("volume_goal") or (body or {}).get("goal") or "").strip()
    volume_theme = str((body or {}).get("volume_theme") or "").strip()
    target_pacing = str((body or {}).get("target_pacing") or "mid").strip().lower()
    structure_hints = _normalize_structure_hints(body or {})
    splitbook_id = _resolve_splitbook_id_from_body(body or {})
    splitbook_outline_reference = await _build_splitbook_outline_reference(db, splitbook_id=splitbook_id) if splitbook_id else {}

    # Backward-compatible endpoint, but generation path is now AI-required.
    if not bool((body or {}).get("use_ai_refine", True)):
        raise HTTPException(status_code=400, detail="VOLUME_PLAN_AI_REQUIRED")

    draft_plan = await _build_volume_plan_auto_draft(
        db,
        book_id=str(book_id),
        volume_row=dict(vol),
        volume_goal=volume_goal,
        volume_theme=volume_theme,
        target_pacing=target_pacing,
        reason=reason,
    )
    draft_plan = _apply_structure_hints_to_volume_draft(draft_plan, structure_hints)
    try:
        draft_plan, ai_meta = await _refine_volume_plan_with_ai(
            draft=draft_plan,
            volume_goal=volume_goal,
            volume_theme=volume_theme,
            target_pacing=target_pacing,
            structure_hints=structure_hints,
            splitbook_outline_reference=splitbook_outline_reference,
            strict=True,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    out = await _create_volume_plan_auto(
        db,
        book_id=str(book_id),
        volume_row=dict(vol),
        note=note,
        reason=reason,
        volume_goal=volume_goal,
        volume_theme=volume_theme,
        target_pacing=target_pacing,
        draft_plan=draft_plan,
    )
    out["structure_hints_applied"] = int(structure_hints.get("total_lines") or 0)
    out["structure_hint_sources"] = [str(x) for x in (structure_hints.get("sources") or []) if str(x).strip()][:8]
    out["splitbook_id"] = splitbook_id or None
    out["splitbook_outline_reference"] = {
        "chapter_total": int(splitbook_outline_reference.get("chapter_total") or 0),
        "phase_count": len(splitbook_outline_reference.get("phase_skeleton") or []),
    } if splitbook_outline_reference else {}
    out["ai_refine"] = ai_meta
    return out


@app.post("/v1/plan/autobuild")
async def plan_autobuild_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    book_id = str((body or {}).get("book_id") or "").strip()
    if not book_id:
        raise HTTPException(status_code=400, detail="book_id required")
    volume_id = str((body or {}).get("volume_id") or "").strip()
    chapter_id = str((body or {}).get("chapter_id") or "").strip()
    chapter_no_raw = body.get("chapter_no")
    volume_row: dict | None = None
    if volume_id:
        row = await db.execute(
            text(
                """
                SELECT volume_id::text AS volume_id, book_id::text AS book_id, volume_no, title,
                       start_chapter_no, end_chapter_no, planned_chapters, note
                FROM volume
                WHERE volume_id=CAST(:volume_id AS uuid)
                  AND book_id=CAST(:book_id AS uuid)
                LIMIT 1
                """
            ),
            {"book_id": book_id, "volume_id": volume_id},
        )
        volume_row = dict(row.mappings().first() or {}) if row else None
    if not volume_row and chapter_id:
        row = await db.execute(
            text(
                """
                SELECT v.volume_id::text AS volume_id, v.book_id::text AS book_id, v.volume_no, v.title,
                       v.start_chapter_no, v.end_chapter_no, v.planned_chapters, v.note
                FROM chapter c
                JOIN volume v
                  ON v.book_id=c.book_id
                 AND c."order" BETWEEN v.start_chapter_no AND v.end_chapter_no
                WHERE c.chapter_id=CAST(:chapter_id AS uuid)
                  AND c.book_id=CAST(:book_id AS uuid)
                ORDER BY v.volume_no DESC
                LIMIT 1
                """
            ),
            {"book_id": book_id, "chapter_id": chapter_id},
        )
        volume_row = dict(row.mappings().first() or {}) if row else None
    if not volume_row and chapter_no_raw is not None:
        try:
            ch_no = int(chapter_no_raw)
        except Exception:
            ch_no = 0
        if ch_no > 0:
            row = await db.execute(
                text(
                    """
                    SELECT volume_id::text AS volume_id, book_id::text AS book_id, volume_no, title,
                           start_chapter_no, end_chapter_no, planned_chapters, note
                    FROM volume
                    WHERE book_id=CAST(:book_id AS uuid)
                      AND :chapter_no BETWEEN start_chapter_no AND end_chapter_no
                    ORDER BY volume_no DESC
                    LIMIT 1
                    """
                ),
                {"book_id": book_id, "chapter_no": ch_no},
            )
            volume_row = dict(row.mappings().first() or {}) if row else None
    if not volume_row:
        row = await db.execute(
            text(
                """
                SELECT volume_id::text AS volume_id, book_id::text AS book_id, volume_no, title,
                       start_chapter_no, end_chapter_no, planned_chapters, note
                FROM volume
                WHERE book_id=CAST(:book_id AS uuid)
                ORDER BY volume_no DESC
                LIMIT 1
                """
            ),
            {"book_id": book_id},
        )
        volume_row = dict(row.mappings().first() or {}) if row else None
    if not volume_row:
        raise HTTPException(status_code=404, detail="VOLUME_NOT_FOUND")

    note = str((body or {}).get("note") or "autobuild_volume_plan")
    reason = str((body or {}).get("reason") or "autobuild")
    volume_goal = str((body or {}).get("volume_goal") or (body or {}).get("goal") or "").strip()
    volume_theme = str((body or {}).get("volume_theme") or "").strip()
    target_pacing = str((body or {}).get("target_pacing") or "mid").strip().lower()
    res = await _create_volume_plan_auto(
        db,
        book_id=book_id,
        volume_row=volume_row,
        note=note,
        reason=reason,
        volume_goal=volume_goal,
        volume_theme=volume_theme,
        target_pacing=target_pacing,
    )
    return {"ok": True, "route": "autobuild", **res}


@app.get("/v1/plan/items/{item_id}/execution_trace")
async def plan_item_execution_trace_route(
    item_id: UUID,
    limit: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await db.execute(
        text(
            """
            SELECT
              i.item_id::text AS item_id,
              i.kind,
              i.summary,
              i.target_window,
              i.target_p_vol_min::double precision AS target_p_vol_min,
              i.target_p_vol_max::double precision AS target_p_vol_max,
              i.priority,
              i.must_happen,
              i.status,
              COALESCE(i.meta, '{}'::jsonb) AS meta,
              p.vol_plan_id::text AS vol_plan_id,
              p.version AS vol_plan_version,
              p.status AS vol_plan_status,
              p.book_id::text AS book_id,
              p.volume_id::text AS volume_id
            FROM volume_plan_item i
            JOIN volume_plan p ON p.vol_plan_id=i.vol_plan_id
            WHERE i.item_id=CAST(:item_id AS uuid)
            LIMIT 1
            """
        ),
        {"item_id": str(item_id)},
    )
    item = row.mappings().first()
    if not item:
        raise HTTPException(status_code=404, detail="PLAN_ITEM_NOT_FOUND")

    hits_res = await db.execute(
        text(
            """
            SELECT
              ct.trace_id::text AS trace_id,
              ct.run_id::text AS run_id,
              ct.chapter_id::text AS chapter_id,
              COALESCE(c."order", 0)::int AS chapter_no,
              ct.created_at,
              jt.task AS task
            FROM chapter_trace ct
            LEFT JOIN chapter c ON c.chapter_id=ct.chapter_id
            CROSS JOIN LATERAL jsonb_array_elements(COALESCE(ct.payload->'final_tasks', '[]'::jsonb)) AS jt(task)
            WHERE (jt.task#>>'{refs,plan_item_id}') = :item_id
            ORDER BY ct.created_at DESC
            LIMIT :limit
            """
        ),
        {"item_id": str(item_id), "limit": int(limit)},
    )
    hits_raw = hits_res.mappings().all()

    hits: list[dict] = []
    step_counts: dict[str, int] = {}
    for r in hits_raw:
        task = r.get("task") if isinstance(r.get("task"), dict) else {}
        combo = task.get("combo") if isinstance(task.get("combo"), dict) else {}
        meta = task.get("meta") if isinstance(task.get("meta"), dict) else {}
        combo_step = str(combo.get("step") or meta.get("combo_step") or "").strip().lower()
        if combo_step:
            step_counts[combo_step] = int(step_counts.get(combo_step, 0)) + 1
        hits.append(
            {
                "trace_id": str(r.get("trace_id") or ""),
                "run_id": str(r.get("run_id") or ""),
                "chapter_id": str(r.get("chapter_id") or ""),
                "chapter_no": int(r.get("chapter_no") or 0),
                "created_at": r.get("created_at"),
                "task": {
                    "task_id": str(task.get("task_id") or ""),
                    "type": str(task.get("type") or task.get("task_type") or ""),
                    "source": str(task.get("source") or ""),
                    "priority": int(task.get("priority") or 0),
                    "intensity": int(task.get("intensity") or 0),
                    "combo": {
                        "combo_type": str(combo.get("combo_type") or ""),
                        "step": combo_step,
                        "combo_fp": str(combo.get("combo_fp") or ""),
                    },
                },
            }
        )

    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    done_info = {
        "done_at": str(meta.get("done_at") or ""),
        "done_reason": str(meta.get("done_reason") or ""),
        "done_combo_type": str(meta.get("done_combo_type") or ""),
        "done_combo_step": str(meta.get("done_combo_step") or ""),
    }

    return {
        "ok": True,
        "item": {
            "item_id": str(item.get("item_id") or ""),
            "book_id": str(item.get("book_id") or ""),
            "volume_id": str(item.get("volume_id") or ""),
            "vol_plan_id": str(item.get("vol_plan_id") or ""),
            "vol_plan_version": int(item.get("vol_plan_version") or 0),
            "vol_plan_status": str(item.get("vol_plan_status") or ""),
            "kind": str(item.get("kind") or ""),
            "summary": str(item.get("summary") or ""),
            "target_window": str(item.get("target_window") or ""),
            "target_p_vol_min": float(item.get("target_p_vol_min") or 0.0),
            "target_p_vol_max": float(item.get("target_p_vol_max") or 1.0),
            "priority": int(item.get("priority") or 0),
            "must_happen": bool(item.get("must_happen")),
            "status": str(item.get("status") or ""),
            "done_info": done_info,
            "meta": meta,
        },
        "execution": {
            "hits_count": len(hits),
            "step_counts": step_counts,
            "hits": hits,
        },
    }


@app.get("/v1/ctx_tags/dictionary")
async def ctx_tags_dictionary_route(db: AsyncSession = Depends(get_db)) -> dict:
    rows = await db.execute(
        text(
            """
            SELECT tag, category, description, is_enabled
            FROM tag_dictionary
            ORDER BY category, tag
            """
        )
    )
    aliases = await db.execute(
        text(
            """
            SELECT from_tag, to_tag
            FROM tag_alias
            ORDER BY from_tag
            """
        )
    )
    return {
        "items": [
            {
                "tag": str(r[0]),
                "category": str(r[1]),
                "description": str(r[2] or ""),
                "is_enabled": bool(r[3]),
            }
            for r in rows.fetchall()
        ],
        "aliases": [
            {"from_tag": str(a[0]), "to_tag": str(a[1])}
            for a in aliases.fetchall()
        ],
    }


@app.post("/v1/ctx_tags/dictionary")
async def ctx_tags_dictionary_upsert_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    tag = str((body or {}).get("tag") or "").strip().lower()
    category = str((body or {}).get("category") or "custom").strip().lower()
    description = str((body or {}).get("description") or "")
    is_enabled = bool((body or {}).get("is_enabled", True))
    if not tag:
        raise HTTPException(status_code=400, detail="TAG_REQUIRED")
    await db.execute(
        text(
            """
            INSERT INTO tag_dictionary(tag, category, description, is_enabled)
            VALUES (:tag, :category, :description, :is_enabled)
            ON CONFLICT (tag)
            DO UPDATE SET
              category=EXCLUDED.category,
              description=EXCLUDED.description,
              is_enabled=EXCLUDED.is_enabled
            """
        ),
        {"tag": tag, "category": category, "description": description, "is_enabled": is_enabled},
    )
    alias = str((body or {}).get("alias_of") or "").strip().lower()
    if alias:
        await db.execute(
            text(
                """
                INSERT INTO tag_alias(from_tag, to_tag)
                VALUES (:from_tag, :to_tag)
                ON CONFLICT (from_tag)
                DO UPDATE SET to_tag=EXCLUDED.to_tag
                """
            ),
            {"from_tag": tag, "to_tag": alias},
        )
    await db.commit()
    return {"ok": True, "tag": tag, "category": category, "is_enabled": is_enabled}


@app.get("/v1/chapters/{chapter_id}/intent")
async def chapter_intent_get_route(chapter_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.execute(
        text("SELECT intent, intent_status FROM chapter WHERE chapter_id=:chapter_id"),
        {"chapter_id": str(chapter_id)},
    )
    r = row.mappings().first()
    if not r:
        raise HTTPException(status_code=404, detail="CHAPTER_NOT_FOUND")
    return {
        "chapter_id": str(chapter_id),
        "intent": _canonical_intent(r.get("intent") if isinstance(r.get("intent"), dict) else {}),
        "intent_status": str(r.get("intent_status") or "suggested"),
    }


@app.post("/v1/chapters/{chapter_id}/intent")
async def chapter_intent_set_route(chapter_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.execute(
        text("SELECT chapter_id FROM chapter WHERE chapter_id=:chapter_id"),
        {"chapter_id": str(chapter_id)},
    )
    if not row.first():
        raise HTTPException(status_code=404, detail="CHAPTER_NOT_FOUND")
    intent = _canonical_intent((body or {}).get("intent") if isinstance((body or {}).get("intent"), dict) else {})
    intent_status = str((body or {}).get("intent_status") or "confirmed").strip().lower()
    if intent_status not in {"suggested", "confirmed"}:
        intent_status = "confirmed"
    await db.execute(
        text(
            """
            UPDATE chapter
            SET intent=CAST(:intent AS jsonb), intent_status=:intent_status
            WHERE chapter_id=:chapter_id
            """
        ),
        {"chapter_id": str(chapter_id), "intent": json.dumps(intent, ensure_ascii=False), "intent_status": intent_status},
    )
    await db.commit()
    return {"ok": True, "chapter_id": str(chapter_id), "intent": intent, "intent_status": intent_status}


@app.post("/v1/chapters/{chapter_id}/intent/suggest")
async def chapter_intent_suggest_route(chapter_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    row_ch = await db.execute(
        text('SELECT chapter_id, "order" AS chapter_no FROM chapter WHERE chapter_id=:chapter_id'),
        {"chapter_id": str(chapter_id)},
    )
    ch = row_ch.mappings().first()
    if not ch:
        raise HTTPException(status_code=404, detail="CHAPTER_NOT_FOUND")
    effective_settings = await get_effective_settings(db, str(chapter_id))
    effective = (effective_settings or {}).get("effective") if isinstance((effective_settings or {}).get("effective"), dict) else {}
    intent, confidence, rationale = _suggest_intent_from_effective(
        effective,
        chapter_no=int(ch.get("chapter_no")) if ch.get("chapter_no") is not None else None,
    )
    auto_confirm = bool((body or {}).get("auto_confirm", False))
    intent_status = "confirmed" if auto_confirm and confidence >= 0.7 else "suggested"
    await db.execute(
        text(
            """
            UPDATE chapter
            SET intent=CAST(:intent AS jsonb), intent_status=:intent_status
            WHERE chapter_id=:chapter_id
            """
        ),
        {"chapter_id": str(chapter_id), "intent": json.dumps(intent, ensure_ascii=False), "intent_status": intent_status},
    )
    await db.commit()
    return {
        "chapter_id": str(chapter_id),
        "intent": intent,
        "intent_status": intent_status,
        "confidence": confidence,
        "rationale": rationale,
    }


@app.post("/v1/chapters/{chapter_id}/foreshadow/plan")
async def chapter_foreshadow_plan_route(chapter_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    row_ch = await db.execute(
        text('SELECT chapter_id::text AS chapter_id, book_id::text AS book_id, "order" AS chapter_no FROM chapter WHERE chapter_id=CAST(:chapter_id AS uuid)'),
        {"chapter_id": str(chapter_id)},
    )
    ch = row_ch.mappings().first()
    if not ch:
        raise HTTPException(status_code=404, detail="CHAPTER_NOT_FOUND")
    book_id = str(ch["book_id"])
    chapter_no = int(ch.get("chapter_no") or 0)
    vol = await _find_volume_for_chapter(db, book_id=book_id, chapter_no=chapter_no)
    volume_id = str(vol.get("volume_id")) if vol and vol.get("volume_id") else None

    created_ids: list[str] = []
    reinforced_ids: list[str] = []
    planned_ids: list[str] = []
    creates = (body or {}).get("create") if isinstance((body or {}).get("create"), list) else []
    reinforces = (body or {}).get("reinforce") if isinstance((body or {}).get("reinforce"), list) else []
    payoff_plan = (body or {}).get("payoff_plan") if isinstance((body or {}).get("payoff_plan"), list) else []

    for c in creates[:20]:
        title = str((c or {}).get("title") or "").strip()
        if not title:
            continue
        ftype = str((c or {}).get("type") or "mystery").strip().lower()
        scope = str((c or {}).get("scope") or "volume").strip().lower()
        priority = max(1, min(5, int((c or {}).get("priority") or 3)))
        question = str((c or {}).get("question") or "")
        expected_payoff = str((c or {}).get("expected_payoff") or "")
        tags_raw = (c or {}).get("tags") if isinstance((c or {}).get("tags"), list) else []
        tags = [str(x).strip().lower() for x in tags_raw if str(x).strip()][:12]
        ins = await db.execute(
            text(
                """
                INSERT INTO foreshadow(
                  book_id, volume_id, title, type, scope, priority, status,
                  created_chapter_id, question, expected_payoff, tags
                )
                VALUES (
                  CAST(:book_id AS uuid), CAST(:volume_id AS uuid), :title, :type, :scope, :priority, 'seeded',
                  CAST(:chapter_id AS uuid), :question, :expected_payoff, CAST(:tags AS text[])
                )
                RETURNING foreshadow_id::text AS foreshadow_id
                """
            ),
            {
                "book_id": book_id,
                "volume_id": volume_id,
                "title": title,
                "type": ftype,
                "scope": scope,
                "priority": priority,
                "chapter_id": str(chapter_id),
                "question": question,
                "expected_payoff": expected_payoff,
                "tags": tags,
            },
        )
        fid = str(ins.scalar_one())
        created_ids.append(fid)
        await db.execute(
            text(
                """
                INSERT INTO foreshadow_event(foreshadow_id, chapter_id, event_type, intensity, note)
                VALUES (CAST(:foreshadow_id AS uuid), CAST(:chapter_id AS uuid), 'seed', 1, :note)
                """
            ),
            {"foreshadow_id": fid, "chapter_id": str(chapter_id), "note": "planned seed"},
        )

    for r in reinforces[:20]:
        fid = str((r or {}).get("foreshadow_id") or "").strip()
        if not fid:
            continue
        intensity = max(1, min(3, int((r or {}).get("intensity") or 1)))
        note = str((r or {}).get("note") or "")
        await db.execute(
            text(
                """
                INSERT INTO foreshadow_event(foreshadow_id, chapter_id, event_type, intensity, note)
                VALUES (CAST(:foreshadow_id AS uuid), CAST(:chapter_id AS uuid), 'reinforce', :intensity, :note)
                """
            ),
            {"foreshadow_id": fid, "chapter_id": str(chapter_id), "intensity": intensity, "note": note},
        )
        await db.execute(
            text("UPDATE foreshadow SET status='reinforced', updated_at=now() WHERE foreshadow_id=CAST(:foreshadow_id AS uuid)"),
            {"foreshadow_id": fid},
        )
        reinforced_ids.append(fid)

    for p in payoff_plan[:20]:
        fid = str((p or {}).get("foreshadow_id") or "").strip()
        payoff_no = int((p or {}).get("planned_payoff_chapter_no") or 0)
        if not fid or payoff_no <= 0:
            continue
        row_cp = await db.execute(
            text('SELECT chapter_id::text AS chapter_id FROM chapter WHERE book_id=CAST(:book_id AS uuid) AND "order"=:chapter_no LIMIT 1'),
            {"book_id": book_id, "chapter_no": payoff_no},
        )
        cp = row_cp.mappings().first()
        cp_id = str(cp["chapter_id"]) if cp and cp.get("chapter_id") else None
        await db.execute(
            text(
                """
                UPDATE foreshadow
                SET planned_payoff_chapter_id=CAST(:cp_id AS uuid), status='payoff_planned', updated_at=now()
                WHERE foreshadow_id=CAST(:foreshadow_id AS uuid)
                """
            ),
            {"foreshadow_id": fid, "cp_id": cp_id},
        )
        planned_ids.append(fid)
    await db.commit()
    return {
        "ok": True,
        "chapter_id": str(chapter_id),
        "created": created_ids,
        "reinforced": reinforced_ids,
        "payoff_planned": planned_ids,
    }


@app.get("/v1/books/{book_id}/foreshadow/board")
async def foreshadow_board_route(
    book_id: UUID,
    chapter_no: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = await db.execute(
        text(
            """
            SELECT
              f.foreshadow_id::text AS foreshadow_id,
              f.title, f.type, f.scope, f.priority, f.status, f.tags,
              c."order" AS created_chapter_no,
              cp."order" AS planned_payoff_chapter_no,
              f.updated_at
            FROM foreshadow f
            LEFT JOIN chapter c ON c.chapter_id=f.created_chapter_id
            LEFT JOIN chapter cp ON cp.chapter_id=f.planned_payoff_chapter_id
            WHERE f.book_id=CAST(:book_id AS uuid)
            ORDER BY f.priority DESC, f.updated_at DESC
            """
        ),
        {"book_id": str(book_id)},
    )
    items = []
    open_items = []
    due_soon = []
    overdue = []
    closed = []
    now_no = int(chapter_no or 0)
    for r in rows.mappings().all():
        it = {
            "foreshadow_id": str(r.get("foreshadow_id") or ""),
            "title": str(r.get("title") or ""),
            "type": str(r.get("type") or ""),
            "scope": str(r.get("scope") or ""),
            "priority": int(r.get("priority") or 3),
            "status": str(r.get("status") or ""),
            "tags": [str(x) for x in (r.get("tags") or [])],
            "created_chapter_no": int(r.get("created_chapter_no") or 0),
            "planned_payoff_chapter_no": int(r.get("planned_payoff_chapter_no") or 0),
            "updated_at": r.get("updated_at"),
        }
        items.append(it)
        status = it["status"]
        is_open = status in {"seeded", "reinforced", "payoff_planned"}
        if status in {"paid_off", "closed", "dropped"}:
            closed.append(it)
            continue
        if is_open:
            open_items.append(it)
            pp = int(it.get("planned_payoff_chapter_no") or 0)
            if now_no > 0 and pp > 0 and pp - now_no <= 2 and pp >= now_no:
                due_soon.append(it)
            if now_no > 0 and pp > 0 and now_no > pp:
                overdue.append(it)
    return {
        "book_id": str(book_id),
        "items": items,
        "open": open_items,
        "due_soon": due_soon,
        "overdue": overdue,
        "closed": closed,
    }


@app.post("/v1/foreshadow/{foreshadow_id}/event")
async def foreshadow_event_route(foreshadow_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    event_type = str((body or {}).get("event_type") or "").strip().lower()
    if event_type not in {"seed", "reinforce", "hint", "payoff", "close", "retcon", "drop"}:
        raise HTTPException(status_code=400, detail="INVALID_EVENT_TYPE")
    chapter_id = str((body or {}).get("chapter_id") or "").strip()
    if not chapter_id:
        raise HTTPException(status_code=400, detail="CHAPTER_ID_REQUIRED")
    intensity = max(1, min(3, int((body or {}).get("intensity") or 1)))
    note = str((body or {}).get("note") or "")
    excerpt = str((body or {}).get("excerpt_safe") or "")
    if len(excerpt) > 25:
        excerpt = excerpt[:25]
    row_f = await db.execute(
        text("SELECT foreshadow_id::text AS foreshadow_id FROM foreshadow WHERE foreshadow_id=CAST(:foreshadow_id AS uuid)"),
        {"foreshadow_id": str(foreshadow_id)},
    )
    if not row_f.mappings().first():
        raise HTTPException(status_code=404, detail="FORESHADOW_NOT_FOUND")
    await db.execute(
        text(
            """
            INSERT INTO foreshadow_event(foreshadow_id, chapter_id, event_type, intensity, excerpt_safe, note)
            VALUES (CAST(:foreshadow_id AS uuid), CAST(:chapter_id AS uuid), :event_type, :intensity, :excerpt_safe, :note)
            """
        ),
        {
            "foreshadow_id": str(foreshadow_id),
            "chapter_id": chapter_id,
            "event_type": event_type,
            "intensity": intensity,
            "excerpt_safe": excerpt,
            "note": note,
        },
    )
    next_status = None
    if event_type == "seed":
        next_status = "seeded"
    elif event_type in {"reinforce", "hint"}:
        next_status = "reinforced"
    elif event_type in {"payoff", "close"}:
        next_status = "paid_off"
    elif event_type == "retcon":
        next_status = "retcon"
    elif event_type == "drop":
        next_status = "dropped"
    if next_status:
        await db.execute(
            text("UPDATE foreshadow SET status=:status, updated_at=now() WHERE foreshadow_id=CAST(:foreshadow_id AS uuid)"),
            {"foreshadow_id": str(foreshadow_id), "status": next_status},
        )
    await db.commit()
    return {"ok": True, "foreshadow_id": str(foreshadow_id), "event_type": event_type, "status": next_status}


@app.post("/v1/chapters/{chapter_id}/foreshadow/suggest_events")
async def chapter_foreshadow_suggest_events_route(chapter_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    text_ver_id = str((body or {}).get("text_ver_id") or "").strip()
    if not text_ver_id:
        row_latest = await db.execute(
            text(
                """
                SELECT text_ver_id::text AS text_ver_id
                FROM chapter_text_version
                WHERE chapter_id=CAST(:chapter_id AS uuid)
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"chapter_id": str(chapter_id)},
        )
        latest = row_latest.mappings().first()
        if not latest:
            raise HTTPException(status_code=404, detail="TEXT_VERSION_NOT_FOUND")
        text_ver_id = str(latest["text_ver_id"])
    row_tv = await db.execute(
        text(
            """
            SELECT text_ver_id::text AS text_ver_id, meta
            FROM chapter_text_version
            WHERE text_ver_id=CAST(:text_ver_id AS uuid)
              AND chapter_id=CAST(:chapter_id AS uuid)
            """
        ),
        {"text_ver_id": text_ver_id, "chapter_id": str(chapter_id)},
    )
    tv = row_tv.mappings().first()
    if not tv:
        raise HTTPException(status_code=404, detail="TEXT_VERSION_NOT_FOUND")
    meta = tv.get("meta") if isinstance(tv.get("meta"), dict) else {}
    fs = meta.get("foreshadow_selection") if isinstance(meta.get("foreshadow_selection"), dict) else {}
    seed = fs.get("seed") if isinstance(fs.get("seed"), list) else []
    reinforce = fs.get("reinforce") if isinstance(fs.get("reinforce"), list) else []
    payoff = fs.get("payoff") if isinstance(fs.get("payoff"), list) else []
    suggestions: list[dict] = []
    for it in seed:
        fid = str((it or {}).get("foreshadow_id") or "").strip()
        if fid:
            suggestions.append(
                {
                    "foreshadow_id": fid,
                    "event_type": "seed",
                    "intensity": 1,
                    "note": "suggested from draft foreshadow_selection.seed",
                    "source": "meta.seed",
                }
            )
    for it in reinforce:
        fid = str((it or {}).get("foreshadow_id") or "").strip()
        if fid:
            suggestions.append(
                {
                    "foreshadow_id": fid,
                    "event_type": "reinforce",
                    "intensity": 1,
                    "note": "suggested from draft foreshadow_selection.reinforce",
                    "source": "meta.reinforce",
                }
            )
    for it in payoff:
        fid = str((it or {}).get("foreshadow_id") or "").strip()
        if fid:
            suggestions.append(
                {
                    "foreshadow_id": fid,
                    "event_type": "payoff",
                    "intensity": 2,
                    "note": "suggested from draft foreshadow_selection.payoff",
                    "source": "meta.payoff",
                }
            )
    if not suggestions:
        used_ids = meta.get("used_foreshadow_ids") if isinstance(meta.get("used_foreshadow_ids"), list) else []
        for fid_raw in used_ids:
            fid = str(fid_raw or "").strip()
            if fid:
                suggestions.append(
                    {
                        "foreshadow_id": fid,
                        "event_type": "reinforce",
                        "intensity": 1,
                        "note": "fallback suggested from meta.used_foreshadow_ids",
                        "source": "meta.used_foreshadow_ids",
                    }
                )
    uniq: dict[str, dict] = {}
    for s in suggestions:
        key = f"{s['foreshadow_id']}:{s['event_type']}"
        uniq[key] = s
    out = list(uniq.values())
    if out:
        ids = [str(x["foreshadow_id"]) for x in out]
        row_titles = await db.execute(
            text(
                """
                SELECT foreshadow_id::text AS foreshadow_id, title, status
                FROM foreshadow
                WHERE foreshadow_id = ANY(CAST(:ids AS uuid[]))
                """
            ),
            {"ids": ids},
        )
        title_map = {str(r["foreshadow_id"]): {"title": str(r.get("title") or ""), "status": str(r.get("status") or "")} for r in row_titles.mappings().all()}
        for s in out:
            m = title_map.get(str(s["foreshadow_id"])) or {}
            s["title"] = m.get("title") or ""
            s["current_status"] = m.get("status") or ""
    return {"chapter_id": str(chapter_id), "text_ver_id": text_ver_id, "suggestions": out}


@app.post("/v1/chapters/{chapter_id}/foreshadow/confirm_events")
async def chapter_foreshadow_confirm_events_route(chapter_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    events = (body or {}).get("events")
    if not isinstance(events, list) or not events:
        raise HTTPException(status_code=400, detail="EVENTS_REQUIRED")
    text_ver_id = str((body or {}).get("text_ver_id") or "").strip()
    applied: list[dict] = []
    for e in events[:100]:
        if not isinstance(e, dict):
            continue
        fid = str(e.get("foreshadow_id") or "").strip()
        event_type = str(e.get("event_type") or "").strip().lower()
        if not fid or event_type not in {"seed", "reinforce", "hint", "payoff", "close", "retcon", "drop"}:
            continue
        intensity = max(1, min(3, int(e.get("intensity") or 1)))
        note = str(e.get("note") or "")
        if text_ver_id:
            note = (note + f" [confirmed_from_text_ver:{text_ver_id}]").strip()
        excerpt = str(e.get("excerpt_safe") or "")
        if len(excerpt) > 25:
            excerpt = excerpt[:25]
        row_f = await db.execute(
            text("SELECT foreshadow_id::text AS foreshadow_id FROM foreshadow WHERE foreshadow_id=CAST(:foreshadow_id AS uuid)"),
            {"foreshadow_id": fid},
        )
        if not row_f.mappings().first():
            continue
        await db.execute(
            text(
                """
                INSERT INTO foreshadow_event(foreshadow_id, chapter_id, event_type, intensity, excerpt_safe, note)
                VALUES (CAST(:foreshadow_id AS uuid), CAST(:chapter_id AS uuid), :event_type, :intensity, :excerpt_safe, :note)
                """
            ),
            {
                "foreshadow_id": fid,
                "chapter_id": str(chapter_id),
                "event_type": event_type,
                "intensity": intensity,
                "excerpt_safe": excerpt,
                "note": note,
            },
        )
        status_next = _foreshadow_status_by_event(event_type)
        if status_next:
            await db.execute(
                text("UPDATE foreshadow SET status=:status, updated_at=now() WHERE foreshadow_id=CAST(:foreshadow_id AS uuid)"),
                {"foreshadow_id": fid, "status": status_next},
            )
        applied.append({"foreshadow_id": fid, "event_type": event_type, "status": status_next})
    await db.commit()
    return {"ok": True, "chapter_id": str(chapter_id), "text_ver_id": text_ver_id or None, "applied": applied}


@app.post("/v1/books/{book_id}/growth/milestones")
async def growth_milestone_create_route(book_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    items = (body or {}).get("items")
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=400, detail="ITEMS_REQUIRED")
    inserted: list[dict] = []
    for it in items[:50]:
        if not isinstance(it, dict):
            continue
        title = str(it.get("title") or "").strip()
        if not title:
            continue
        character_name = str(it.get("character_name") or "主角").strip() or "主角"
        stage = str(it.get("stage") or "pressure").strip().lower()
        if stage not in {"setup", "pressure", "cost", "breakthrough", "integration", "reflect"}:
            stage = "pressure"
        milestone_no = max(1, int(it.get("milestone_no") or 1))
        priority = max(1, min(5, int(it.get("priority") or 3)))
        planned_scope = str(it.get("planned_scope") or "volume").strip().lower()
        if planned_scope not in {"chapter", "volume", "book"}:
            planned_scope = "volume"
        planned_chapter_no = int(it.get("planned_chapter_no") or 0) or None
        planned_volume_id = str(it.get("planned_volume_id") or "").strip() or None
        bind_foreshadow_ids = [str(x) for x in ((it.get("bind_foreshadow_ids") if isinstance(it.get("bind_foreshadow_ids"), list) else [])) if str(x).strip()]
        row = await db.execute(
            text(
                """
                INSERT INTO growth_milestone(
                  book_id, character_name, milestone_no, title, stage, priority, planned_scope, planned_chapter_no,
                  planned_volume_id, trigger, cost, choice_text, new_belief, bind_foreshadow_ids,
                  payoff_template_type, status, meta
                )
                VALUES (
                  CAST(:book_id AS uuid), :character_name, :milestone_no, :title, :stage, :priority, :planned_scope, :planned_chapter_no,
                  CAST(:planned_volume_id AS uuid), :trigger, :cost, :choice_text, :new_belief, CAST(:bind_foreshadow_ids AS uuid[]),
                  :payoff_template_type, :status, CAST(:meta AS jsonb)
                )
                ON CONFLICT (book_id, character_name, milestone_no) DO UPDATE SET
                  title=EXCLUDED.title,
                  stage=EXCLUDED.stage,
                  priority=EXCLUDED.priority,
                  planned_scope=EXCLUDED.planned_scope,
                  planned_chapter_no=EXCLUDED.planned_chapter_no,
                  planned_volume_id=EXCLUDED.planned_volume_id,
                  trigger=EXCLUDED.trigger,
                  cost=EXCLUDED.cost,
                  choice_text=EXCLUDED.choice_text,
                  new_belief=EXCLUDED.new_belief,
                  bind_foreshadow_ids=EXCLUDED.bind_foreshadow_ids,
                  payoff_template_type=EXCLUDED.payoff_template_type,
                  meta=EXCLUDED.meta,
                  updated_at=now()
                RETURNING milestone_id::text AS milestone_id, character_name, milestone_no, title, stage, status
                """
            ),
            {
                "book_id": str(book_id),
                "character_name": character_name,
                "milestone_no": milestone_no,
                "title": title,
                "stage": stage,
                "priority": priority,
                "planned_scope": planned_scope,
                "planned_chapter_no": planned_chapter_no,
                "planned_volume_id": planned_volume_id,
                "trigger": str(it.get("trigger") or ""),
                "cost": str(it.get("cost") or ""),
                "choice_text": str(it.get("choice_text") or ""),
                "new_belief": str(it.get("new_belief") or ""),
                "bind_foreshadow_ids": bind_foreshadow_ids,
                "payoff_template_type": str(it.get("payoff_template_type") or "") or None,
                "status": str(it.get("status") or "planned"),
                "meta": json.dumps(it.get("meta") if isinstance(it.get("meta"), dict) else {}, ensure_ascii=False),
            },
        )
        got = row.mappings().first()
        if got:
            inserted.append(dict(got))
    await db.commit()
    return {"book_id": str(book_id), "items": inserted}


@app.get("/v1/books/{book_id}/growth/board")
async def growth_board_route(book_id: UUID, chapter_id: UUID | None = None, db: AsyncSession = Depends(get_db)) -> dict:
    current_chapter_no = 0
    if chapter_id:
        ch = await db.execute(text('SELECT "order" AS chapter_no FROM chapter WHERE chapter_id=CAST(:chapter_id AS uuid)'), {"chapter_id": str(chapter_id)})
        rr = ch.mappings().first()
        current_chapter_no = int(rr.get("chapter_no") or 0) if rr else 0
    rows = await db.execute(
        text(
            """
            SELECT
              milestone_id::text AS milestone_id,
              character_name,
              milestone_no,
              title,
              stage,
              priority,
              planned_scope,
              planned_chapter_no,
              planned_volume_id::text AS planned_volume_id,
              trigger,
              cost,
              choice_text,
              new_belief,
              bind_foreshadow_ids,
              payoff_template_type,
              status,
              updated_at
            FROM growth_milestone
            WHERE book_id=CAST(:book_id AS uuid)
            ORDER BY character_name, milestone_no
            """
        ),
        {"book_id": str(book_id)},
    )
    items = [dict(r) for r in rows.mappings().all()]
    open_items = [x for x in items if str(x.get("status") or "") in {"planned", "seeded", "in_progress"}]
    achieved = [x for x in items if str(x.get("status") or "") in {"achieved", "reflected"}]
    due_soon = []
    overdue = []
    if current_chapter_no > 0:
        for it in open_items:
            planned = int(it.get("planned_chapter_no") or 0)
            if planned > 0 and planned - current_chapter_no <= 1 and planned >= current_chapter_no:
                due_soon.append(it)
            if planned > 0 and current_chapter_no > planned + 1:
                overdue.append(it)
    return {
        "book_id": str(book_id),
        "chapter_no": current_chapter_no,
        "items": items,
        "open": open_items,
        "due_soon": due_soon,
        "overdue": overdue,
        "achieved": achieved,
    }


@app.get("/v1/books/{book_id}/growth/curve")
async def growth_curve_route(book_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    book_id_s = str(book_id)
    ev_rows = await db.execute(
        text(
            """
            SELECT
              c."order" AS chapter_no,
              e.value AS event_item
            FROM chapter_events ce
            JOIN chapter c ON c.chapter_id=ce.chapter_id
            CROSS JOIN LATERAL jsonb_array_elements(COALESCE(ce.events->'growth_events', '[]'::jsonb)) e(value)
            WHERE ce.book_id=CAST(:book_id AS uuid)
            ORDER BY c."order" ASC
            """
        ),
        {"book_id": book_id_s},
    )
    events = [dict(r) for r in ev_rows.mappings().all()]
    milestone_ids = {
        str(((r.get("event_item") or {}).get("milestone_id") or "")).strip()
        for r in events
        if isinstance(r.get("event_item"), dict)
    }
    milestone_ids = {x for x in milestone_ids if x}
    milestone_map: dict[str, str] = {}
    if milestone_ids:
        ms_rows = await db.execute(
            text(
                """
                SELECT milestone_id::text AS milestone_id, character_name
                FROM growth_milestone
                WHERE milestone_id = ANY(:ids)
                """
            ),
            {"ids": list(milestone_ids)},
        )
        milestone_map = {str(r.get("milestone_id")): str(r.get("character_name") or "角色") for r in ms_rows.mappings().all()}

    by_character: dict[str, dict[int, float]] = {}
    by_character_actions: dict[str, dict[int, int]] = {}
    for row in events:
        chapter_no = int(row.get("chapter_no") or 0)
        item = row.get("event_item") if isinstance(row.get("event_item"), dict) else {}
        if chapter_no <= 0 or not item:
            continue
        milestone_id = str(item.get("milestone_id") or "").strip()
        character_name = milestone_map.get(milestone_id) or "角色"
        action = str(item.get("action") or "").strip().lower()
        delta = 0.0
        if action == "advance":
            delta += 1.0
        elif action == "achieve":
            delta += 2.2
        if bool(item.get("cost_shown")):
            delta += 0.5
        if bool(item.get("choice_explicit")):
            delta += 0.3
        if delta <= 0:
            continue
        by_character.setdefault(character_name, {})
        by_character_actions.setdefault(character_name, {})
        by_character[character_name][chapter_no] = float(by_character[character_name].get(chapter_no, 0.0)) + delta
        by_character_actions[character_name][chapter_no] = int(by_character_actions[character_name].get(chapter_no, 0)) + 1

    if not by_character:
        ms_rows = await db.execute(
            text(
                """
                SELECT character_name, milestone_no, planned_chapter_no, status
                FROM growth_milestone
                WHERE book_id=CAST(:book_id AS uuid)
                ORDER BY character_name, milestone_no
                """
            ),
            {"book_id": book_id_s},
        )
        for row in ms_rows.mappings().all():
            character_name = str(row.get("character_name") or "角色")
            chapter_no = int(row.get("planned_chapter_no") or 0)
            status = str(row.get("status") or "").lower()
            if chapter_no <= 0:
                chapter_no = int(row.get("milestone_no") or 1) * 3
            delta = 0.8
            if status in {"achieved", "reflected"}:
                delta = 2.0
            elif status in {"in_progress", "seeded"}:
                delta = 1.2
            by_character.setdefault(character_name, {})
            by_character_actions.setdefault(character_name, {})
            by_character[character_name][chapter_no] = float(by_character[character_name].get(chapter_no, 0.0)) + delta
            by_character_actions[character_name][chapter_no] = int(by_character_actions[character_name].get(chapter_no, 0)) + 1

    characters_out: list[dict] = []
    global_curve_raw: dict[int, float] = {}
    for character_name, chapters in by_character.items():
        chapter_nos = sorted(chapters.keys())
        cumulative = 0.0
        points: list[dict] = []
        for ch_no in chapter_nos:
            delta = round(float(chapters.get(ch_no) or 0.0), 4)
            cumulative = round(cumulative + delta, 4)
            points.append(
                {
                    "chapter_no": ch_no,
                    "delta": delta,
                    "cumulative": cumulative,
                    "action_count": int(by_character_actions.get(character_name, {}).get(ch_no, 0)),
                }
            )
            global_curve_raw[ch_no] = float(global_curve_raw.get(ch_no, 0.0)) + delta
        characters_out.append(
            {
                "character_name": character_name,
                "points": points,
                "summary": {
                    "event_points": len(points),
                    "max_cumulative": round(max((float(x.get("cumulative") or 0.0) for x in points), default=0.0), 4),
                    "last_cumulative": round(float(points[-1]["cumulative"]) if points else 0.0, 4),
                },
            }
        )
    characters_out.sort(key=lambda x: float(((x.get("summary") or {}).get("last_cumulative") or 0.0)), reverse=True)

    global_points: list[dict] = []
    global_cumulative = 0.0
    for ch_no in sorted(global_curve_raw.keys()):
        delta = round(float(global_curve_raw[ch_no]), 4)
        global_cumulative = round(global_cumulative + delta, 4)
        global_points.append({"chapter_no": ch_no, "delta": delta, "cumulative": global_cumulative})

    return {
        "book_id": book_id_s,
        "characters": characters_out,
        "global_curve": global_points,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/v1/growth/milestones/{milestone_id}/event")
async def growth_milestone_event_route(milestone_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    action = str((body or {}).get("action") or "").strip().lower()
    if action not in {"seed", "advance", "achieve", "reflect", "drop"}:
        raise HTTPException(status_code=400, detail="INVALID_ACTION")
    note = str((body or {}).get("note") or "")
    row = await db.execute(
        text("SELECT milestone_id::text AS milestone_id, status FROM growth_milestone WHERE milestone_id=CAST(:milestone_id AS uuid)"),
        {"milestone_id": str(milestone_id)},
    )
    got = row.mappings().first()
    if not got:
        raise HTTPException(status_code=404, detail="MILESTONE_NOT_FOUND")
    next_status = {
        "seed": "seeded",
        "advance": "in_progress",
        "achieve": "achieved",
        "reflect": "reflected",
        "drop": "dropped",
    }[action]
    await db.execute(
        text(
            """
            UPDATE growth_milestone
            SET status=:status,
                meta = COALESCE(meta, '{}'::jsonb) || jsonb_build_object('last_event', :action, 'last_note', :note, 'last_event_at', now()),
                updated_at=now()
            WHERE milestone_id=CAST(:milestone_id AS uuid)
            """
        ),
        {"milestone_id": str(milestone_id), "status": next_status, "action": action, "note": note},
    )
    await db.commit()
    return {"ok": True, "milestone_id": str(milestone_id), "action": action, "status": next_status}


@app.get("/v1/payoff_templates")
async def payoff_templates_list_route(
    ftype: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = await db.execute(
        text(
            """
            SELECT template_id::text AS template_id, type, applicable_foreshadow_type, structure_pattern, rewrite_instruction, intensity_level, risk_score, created_at
            FROM payoff_template
            WHERE (:ftype = '' OR type=:ftype)
            ORDER BY type, intensity_level, created_at DESC
            LIMIT 200
            """
        ),
        {"ftype": str(ftype or "").strip().lower()},
    )
    return {"items": [dict(r) for r in rows.mappings().all()]}


@app.get("/v1/payoff_templates/hits")
async def payoff_templates_hits_route(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = await db.execute(
        text(
            """
            WITH payoff_rows AS (
              SELECT
                COALESCE(
                  p.value->'payoff_template'->>'template_id',
                  ''
                ) AS template_id,
                COALESCE(
                  p.value->'payoff_template'->>'type',
                  p.value->>'type',
                  ''
                ) AS payoff_type
              FROM report r
              JOIN LATERAL jsonb_array_elements(
                COALESCE(r.payload->'foreshadow_selection'->'payoff', '[]'::jsonb)
              ) AS p(value) ON TRUE
              WHERE r.created_at > now() - make_interval(days => :days)
            )
            SELECT template_id, payoff_type AS type, COUNT(*)::int AS hits
            FROM payoff_rows
            GROUP BY template_id, payoff_type
            ORDER BY hits DESC, template_id
            LIMIT :limit
            """
        ),
        {"days": int(days), "limit": int(limit)},
    )
    items = []
    for r in rows.mappings().all():
        items.append(
            {
                "template_id": str(r.get("template_id") or ""),
                "type": str(r.get("type") or ""),
                "hits": int(r.get("hits") or 0),
            }
        )
    return {"items": items, "days": int(days)}


@app.get("/v1/payoff_templates/stats")
async def payoff_templates_stats_route(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = await db.execute(
        text(
            """
            WITH rep AS (
              SELECT
                r.payload,
                COALESCE(
                  NULLIF(r.payload->>'score', '')::double precision,
                  abi.score
                ) AS exp_score,
                COALESCE(r.payload->>'batch_id', '') AS batch_id_text,
                COALESCE(r.payload->>'profile_id_used', '') AS profile_id_text,
                COALESCE(r.payload->>'variant', '') AS variant
              FROM report r
              LEFT JOIN ab_batch_item abi ON abi.report_id = r.report_id
              WHERE r.created_at > now() - make_interval(days => :days)
                AND r.report_type = 'ab_batch_item'
            ),
            rep_exp AS (
              SELECT payload, exp_score, batch_id_text, profile_id_text
              FROM rep
              WHERE variant = 'exp'
            ),
            payoff_rows AS (
              SELECT
                COALESCE(
                  p.value->'payoff_template'->>'template_id',
                  ''
                ) AS template_id,
                COALESCE(
                  p.value->'payoff_template'->>'type',
                  p.value->>'type',
                  ''
                ) AS payoff_type,
                r.exp_score AS exp_score,
                (
                  SELECT b.score
                  FROM ab_batch_item b
                  WHERE b.batch_id = CAST(NULLIF(r.batch_id_text, '') AS uuid)
                    AND b.profile_id = CAST(NULLIF(r.profile_id_text, '') AS uuid)
                    AND b.variant = 'baseline'
                    AND b.status = 'done'
                  LIMIT 1
                ) AS baseline_score
              FROM rep_exp r
              JOIN LATERAL jsonb_array_elements(
                COALESCE(r.payload->'foreshadow_selection'->'payoff', '[]'::jsonb)
              ) AS p(value) ON TRUE
            )
            SELECT
              template_id,
              payoff_type AS type,
              COUNT(*)::int AS hits,
              AVG(exp_score)::double precision AS avg_score,
              AVG(
                CASE
                  WHEN baseline_score IS NOT NULL THEN (exp_score - baseline_score)
                  ELSE NULL
                END
              )::double precision AS avg_delta,
              COUNT(*) FILTER (WHERE baseline_score IS NOT NULL)::int AS delta_samples
            FROM payoff_rows
            WHERE template_id <> ''
            GROUP BY template_id, payoff_type
            ORDER BY hits DESC, avg_delta DESC NULLS LAST, template_id
            LIMIT :limit
            """
        ),
        {"days": int(days), "limit": int(limit)},
    )
    items = []
    for r in rows.mappings().all():
        hits = int(r.get("hits") or 0)
        avg_delta_raw = r.get("avg_delta")
        avg_delta = round(float(avg_delta_raw), 6) if avg_delta_raw is not None else None
        avg_score_raw = r.get("avg_score")
        avg_score = round(float(avg_score_raw), 6) if avg_score_raw is not None else None
        impact = round(float(max(0.0, avg_delta or 0.0) * max(0, hits)), 6)
        items.append(
            {
                "template_id": str(r.get("template_id") or ""),
                "type": str(r.get("type") or ""),
                "hits": hits,
                "avg_score": avg_score,
                "avg_delta": avg_delta,
                "delta_avg_by_template": avg_delta,
                "delta_samples": int(r.get("delta_samples") or 0),
                "impact": impact,
            }
        )
    return {"items": items, "days": int(days)}


@app.post("/v1/payoff_templates")
async def payoff_templates_upsert_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="INVALID_BODY")
    t_id = str(body.get("template_id") or "").strip()
    p_type = str(body.get("type") or "").strip().lower()
    if not p_type:
        raise HTTPException(status_code=400, detail="TYPE_REQUIRED")
    app_types = body.get("applicable_foreshadow_type")
    if not isinstance(app_types, list):
        app_types = []
    app_types = [str(x).strip().lower() for x in app_types if str(x).strip()][:20]
    pattern = str(body.get("structure_pattern") or "").strip()
    instruction = str(body.get("rewrite_instruction") or "").strip()
    if not pattern or not instruction:
        raise HTTPException(status_code=400, detail="PATTERN_AND_INSTRUCTION_REQUIRED")
    intensity = max(1, min(3, int(body.get("intensity_level") or 2)))
    risk_score = body.get("risk_score")
    meta = body.get("meta") if isinstance(body.get("meta"), dict) else {}

    if t_id:
        row = await db.execute(
            text(
                """
                UPDATE payoff_template
                SET type=:type,
                    applicable_foreshadow_type=CAST(:applicable_foreshadow_type AS text[]),
                    structure_pattern=:structure_pattern,
                    rewrite_instruction=:rewrite_instruction,
                    intensity_level=:intensity_level,
                    risk_score=:risk_score,
                    meta=CAST(:meta AS jsonb)
                WHERE template_id=CAST(:template_id AS uuid)
                RETURNING template_id::text AS template_id, type, applicable_foreshadow_type, structure_pattern, rewrite_instruction, intensity_level, risk_score, meta, created_at
                """
            ),
            {
                "template_id": t_id,
                "type": p_type,
                "applicable_foreshadow_type": app_types,
                "structure_pattern": pattern,
                "rewrite_instruction": instruction,
                "intensity_level": intensity,
                "risk_score": risk_score,
                "meta": json.dumps(meta, ensure_ascii=False),
            },
        )
        out = row.mappings().first()
        if not out:
            raise HTTPException(status_code=404, detail="PAYOFF_TEMPLATE_NOT_FOUND")
        await db.commit()
        return {"item": dict(out), "mode": "update"}

    row = await db.execute(
        text(
            """
            INSERT INTO payoff_template(type, applicable_foreshadow_type, structure_pattern, rewrite_instruction, intensity_level, risk_score, meta)
            VALUES (:type, CAST(:applicable_foreshadow_type AS text[]), :structure_pattern, :rewrite_instruction, :intensity_level, :risk_score, CAST(:meta AS jsonb))
            RETURNING template_id::text AS template_id, type, applicable_foreshadow_type, structure_pattern, rewrite_instruction, intensity_level, risk_score, meta, created_at
            """
        ),
        {
            "type": p_type,
            "applicable_foreshadow_type": app_types,
            "structure_pattern": pattern,
            "rewrite_instruction": instruction,
            "intensity_level": intensity,
            "risk_score": risk_score,
            "meta": json.dumps(meta, ensure_ascii=False),
        },
    )
    out = row.mappings().one()
    await db.commit()
    return {"item": dict(out), "mode": "create"}


@app.delete("/v1/payoff_templates/{template_id}")
async def payoff_templates_delete_route(template_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.execute(
        text("DELETE FROM payoff_template WHERE template_id=CAST(:template_id AS uuid) RETURNING template_id::text AS template_id"),
        {"template_id": str(template_id)},
    )
    out = row.mappings().first()
    if not out:
        raise HTTPException(status_code=404, detail="PAYOFF_TEMPLATE_NOT_FOUND")
    await db.commit()
    return {"ok": True, "template_id": str(out.get("template_id"))}


@app.post("/v1/profiles", response_model=ProfileItem)
async def create_profile_route(body: ProfileCreateRequest, db: AsyncSession = Depends(get_db)) -> ProfileItem:
    row = await create_profile(db, body.name, body.note, body.features, body.dos, body.donts)
    return ProfileItem(**row)


@app.get("/v1/profiles", response_model=ProfileListResponse)
async def list_profiles_route(db: AsyncSession = Depends(get_db)) -> ProfileListResponse:
    rows = await list_profiles(db)
    return ProfileListResponse(items=[ProfileItem(**row) for row in rows])


@app.get("/v1/profiles/{profile_id}", response_model=ProfileItem)
async def get_profile_route(profile_id: UUID, db: AsyncSession = Depends(get_db)) -> ProfileItem:
    row = await get_profile(db, str(profile_id))
    if not row:
        raise HTTPException(status_code=404, detail="PROFILE_NOT_FOUND")
    return ProfileItem(**row)


@app.delete("/v1/profiles/{profile_id}")
async def delete_profile_route(profile_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    row = await delete_profile(db, str(profile_id))
    if not row:
        raise HTTPException(status_code=404, detail="PROFILE_NOT_FOUND")
    return {"ok": True, "deleted": row}


@app.post("/v1/profiles/{profile_id}", response_model=ProfileItem)
async def update_profile_route(
    profile_id: UUID,
    body: ProfileUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> ProfileItem:
    row = await update_profile(
        db,
        str(profile_id),
        name=body.name,
        note=body.note,
        features=body.features,
        dos=body.dos,
        donts=body.donts,
    )
    if not row:
        raise HTTPException(status_code=404, detail="PROFILE_NOT_FOUND")
    return ProfileItem(**row)


@app.post("/v1/books/{book_id}/profile", response_model=BookItem)
async def bind_book_profile_route(
    book_id: UUID,
    body: BookProfileBindRequest,
    db: AsyncSession = Depends(get_db),
) -> BookItem:
    if body.profile_id:
        prof = await get_profile(db, str(body.profile_id))
        if not prof:
            raise HTTPException(status_code=404, detail="PROFILE_NOT_FOUND")
    row = await bind_book_profile(db, str(book_id), str(body.profile_id) if body.profile_id else None)
    if not row:
        raise HTTPException(status_code=404, detail="BOOK_NOT_FOUND")
    return BookItem(**row)


@app.post("/v1/books/{book_id}/profile_id", response_model=BookItem)
async def bind_book_profile_alias_route(
    book_id: UUID,
    body: BookProfileBindRequest,
    db: AsyncSession = Depends(get_db),
) -> BookItem:
    return await bind_book_profile_route(book_id, body, db)


@app.get("/v1/books/{book_id}/profiles")
async def list_book_profiles_route(book_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    out = await list_book_profiles(db, str(book_id))
    if not out:
        raise HTTPException(status_code=404, detail="BOOK_NOT_FOUND")
    return out


@app.post("/v1/books/{book_id}/profiles")
async def add_book_profile_route(
    book_id: UUID,
    body: BookProfileLinkRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    prof = await get_profile(db, str(body.profile_id))
    if not prof:
        raise HTTPException(status_code=404, detail="PROFILE_NOT_FOUND")
    try:
        return await add_book_profile_link(db, str(book_id), str(body.profile_id), body.role)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail="BOOK_NOT_FOUND") from exc


@app.get("/v1/profiles/{profile_id}/versions")
async def list_profile_versions_route(
    profile_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    out = await list_profile_versions(db, str(profile_id), limit=limit)
    if not out:
        raise HTTPException(status_code=404, detail="PROFILE_NOT_FOUND")
    return out


@app.get("/v1/profiles/{profile_id}/versions/{version}")
async def get_profile_version_route(profile_id: UUID, version: int, db: AsyncSession = Depends(get_db)) -> dict:
    row = await get_profile_version(db, str(profile_id), int(version))
    if not row:
        raise HTTPException(status_code=404, detail="PROFILE_VERSION_NOT_FOUND")
    return row


@app.post("/v1/profiles/{profile_id}/active_version", response_model=ProfileItem)
async def set_profile_active_version_route(
    profile_id: UUID,
    body: ProfileSetActiveVersionRequest,
    db: AsyncSession = Depends(get_db),
) -> ProfileItem:
    try:
        row = await set_profile_active_version(
            db,
            str(profile_id),
            int(body.version),
            note=body.note,
            actor="desktop_user",
        )
    except RuntimeError as exc:
        if str(exc) in {"PROFILE_VERSION_NOT_FOUND", "PROFILE_SNAPSHOT_INVALID"}:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise
    if not row:
        raise HTTPException(status_code=404, detail="PROFILE_NOT_FOUND")
    return ProfileItem(**row)


@app.post("/v1/profiles/{profile_id}/diff")
async def profile_diff_route(
    profile_id: UUID,
    body: ProfileDiffRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await diff_profile_versions(db, str(profile_id), int(body.from_version), int(body.to_version))
    except RuntimeError as exc:
        if str(exc) == "PROFILE_VERSION_NOT_FOUND":
            raise HTTPException(status_code=404, detail="PROFILE_VERSION_NOT_FOUND") from exc
        raise


@app.post("/v1/profiles/{profile_id}/clone", response_model=ProfileItem)
async def clone_profile_route(
    profile_id: UUID,
    body: ProfileCloneRequest,
    db: AsyncSession = Depends(get_db),
) -> ProfileItem:
    try:
        row = await clone_profile(
            db,
            str(profile_id),
            new_name=body.new_name,
            note=body.note,
            actor="desktop_user",
        )
    except RuntimeError as exc:
        if str(exc) == "PROFILE_NOT_FOUND":
            raise HTTPException(status_code=404, detail="PROFILE_NOT_FOUND") from exc
        raise
    return ProfileItem(**row)


@app.post("/v1/profiles/build/from_splitbook", response_model=ProfileItem)
async def profile_from_splitbook_route(
    body: ProfileFromSplitbookRequest,
    db: AsyncSession = Depends(get_db),
) -> ProfileItem:
    stats_res = await db.execute(
        text(
            """
            SELECT asset_type, COUNT(*)::int AS n
            FROM template_asset
            WHERE source_splitbook_id = :sid
            GROUP BY asset_type
            """
        ),
        {"sid": str(body.splitbook_id)},
    )
    rows = [dict(r) for r in stats_res.mappings().all()]
    total_assets = sum(int(r["n"]) for r in rows)
    features = {
        "avg_sentence_len": "mix",
        "dialogue_ratio": 0.3,
        "paragraph_rhythm": "mixed",
        "source_splitbook_id": str(body.splitbook_id),
        "template_asset_counts": {str(r["asset_type"]): int(r["n"]) for r in rows},
    }
    dos = ["动作推进信息", "段落结尾留钩子"]
    donts = ["连续大段说明", "套话重复"]

    if body.mode == "merge":
        existing = await db.execute(
            text("SELECT profile_id FROM profile WHERE name=:name ORDER BY updated_at DESC LIMIT 1"),
            {"name": body.name},
        )
        existing_id = existing.scalar()
        if existing_id:
            updated = await update_profile(
                db,
                str(existing_id),
                features=features,
                dos=dos,
                donts=donts,
                note=f"from_splitbook:{body.splitbook_id}; assets={total_assets}",
            )
            if not updated:
                raise HTTPException(status_code=500, detail="PROFILE_UPDATE_FAILED")
            return ProfileItem(**updated)

    created = await create_profile(
        db,
        body.name,
        note=f"from_splitbook:{body.splitbook_id}; assets={total_assets}",
        features=features,
        dos=dos,
        donts=donts,
    )
    return ProfileItem(**created)


@app.post("/v1/profiles/actions/learn_from_texts")
async def profile_learn_from_texts_route(
    body: ProfileLearnFromTextsRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    prof = await get_profile(db, str(body.profile_id))
    if not prof:
        raise HTTPException(status_code=404, detail="PROFILE_NOT_FOUND")

    text_rows: list[dict] = []
    if body.text_ver_ids:
        res = await db.execute(
            text(
                """
                SELECT text_ver_id, content
                FROM chapter_text_version
                WHERE text_ver_id = ANY(:ids)
                """
            ),
            {"ids": [str(x) for x in body.text_ver_ids]},
        )
        text_rows = [dict(r) for r in res.mappings().all()]
    elif body.book_id:
        res = await db.execute(
            text(
                """
                SELECT tv.text_ver_id, tv.content
                FROM chapter_text_version tv
                JOIN chapter c ON c.chapter_id = tv.chapter_id
                WHERE c.book_id = :book_id
                ORDER BY tv.created_at DESC
                LIMIT 8
                """
            ),
            {"book_id": str(body.book_id)},
        )
        text_rows = [dict(r) for r in res.mappings().all()]
    else:
        raise HTTPException(status_code=400, detail="BOOK_ID_OR_TEXT_VER_IDS_REQUIRED")

    if not text_rows:
        raise HTTPException(status_code=404, detail="NO_TEXTS_FOUND")

    total_chars = 0
    dialogue_chars = 0
    sentence_count = 0
    sentence_chars = 0
    for row in text_rows:
        content = str(row.get("content") or "")
        total_chars += len(content)
        dialogue_chars += content.count("“") + content.count("”") + content.count("\"")
        parts = [p.strip() for p in content.replace("？", "。").replace("！", "。").replace("!", "。").replace("?", "。").split("。")]
        parts = [p for p in parts if p]
        sentence_count += len(parts)
        sentence_chars += sum(len(p) for p in parts)

    dialogue_ratio = round((dialogue_chars / max(1, total_chars)), 4)
    avg_sentence_len_num = sentence_chars / max(1, sentence_count)
    if avg_sentence_len_num < 18:
        avg_sentence_len = "short"
    elif avg_sentence_len_num > 40:
        avg_sentence_len = "long"
    else:
        avg_sentence_len = "mix"

    current_features = prof.get("features") or {}
    learned_features = {
        **current_features,
        "avg_sentence_len": avg_sentence_len,
        "dialogue_ratio": dialogue_ratio,
        "learn_sample_count": len(text_rows),
    }
    if body.mode == "merge":
        old_ratio = float(current_features.get("dialogue_ratio") or dialogue_ratio)
        learned_features["dialogue_ratio"] = round((old_ratio + dialogue_ratio) / 2.0, 4)

    source_ids = [str(r.get("text_ver_id")) for r in text_rows if r.get("text_ver_id")]
    updated = await update_profile(
        db,
        str(body.profile_id),
        features=learned_features,
        create_version=True,
        version_action="learn",
        version_note=body.note or f"learn from {len(text_rows)} texts",
        version_actor="desktop_user",
        source_text_ver_ids=source_ids,
    )
    if not updated:
        raise HTTPException(status_code=500, detail="PROFILE_UPDATE_FAILED")

    return {
        "profile_id": str(body.profile_id),
        "updated": True,
        "new_version": int(updated.get("active_version") or 1),
        "diff": {
            "dialogue_ratio": {
                "old": current_features.get("dialogue_ratio"),
                "new": learned_features.get("dialogue_ratio"),
            },
            "avg_sentence_len": {
                "old": current_features.get("avg_sentence_len"),
                "new": learned_features.get("avg_sentence_len"),
            },
            "sample_count": len(text_rows),
        },
    }


@app.post("/v1/books/{book_id}/style/evolve")
async def evolve_book_style_route(
    book_id: UUID,
    body: StyleEvolutionRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await evolve_book_style(
            db,
            book_id=str(book_id),
            profile_id=str(body.profile_id) if body.profile_id else None,
            sample_limit=int(body.sample_limit),
            min_sample_count=int(body.min_sample_count),
            alpha=float(body.alpha),
            force=bool(body.force),
            sync_book_settings=bool(body.sync_book_settings),
            note=body.note,
        )
    except RuntimeError as exc:
        code = str(exc)
        if code in ("BOOK_NOT_FOUND", "PROFILE_NOT_FOUND"):
            raise HTTPException(status_code=404, detail=code) from exc
        if code in ("PROFILE_UPDATE_FAILED",):
            raise HTTPException(status_code=500, detail=code) from exc
        raise HTTPException(status_code=400, detail=code) from exc


@app.get("/v1/books/{book_id}/style/evolution/latest")
async def latest_book_style_evolution_route(book_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    item = await get_latest_style_evolution(db, book_id=str(book_id))
    return {"ok": True, "item": item}


async def reconcile_splitbook_state(db: AsyncSession, splitbook_id: str | None = None) -> dict:
    target_rows: list[dict] = []
    if splitbook_id:
        one = await get_splitbook(db, str(splitbook_id))
        if one:
            target_rows = [one]
    else:
        target_rows = await list_splitbooks(db, limit=500)

    updated = 0

    def _job_pct(job_row: dict) -> int:
        progress_obj = job_row.get("progress") if isinstance(job_row.get("progress"), dict) else {}
        pct_raw = progress_obj.get("pct")
        if isinstance(pct_raw, (int, float)):
            return int(max(0, min(100, round(float(pct_raw)))))
        pv = float(job_row.get("progress_value") or 0)
        return int(max(0, min(100, round(pv * 100))))

    def _job_age_seconds(job_row: dict) -> int:
        raw = str(job_row.get("updated_at") or "").strip()
        if not raw:
            return 10**9
        try:
            ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return 10**9
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - ts).total_seconds()))

    for row in target_rows:
        sid = str(row.get("splitbook_id") or "").strip()
        if not sid:
            continue
        current_ingest = str(row.get("ingest_status") or "").strip().lower()
        current_embed = str(row.get("embed_status") or "").strip().lower()
        stats = dict(row.get("stats") or {})

        count_res = await db.execute(
            text(
                """
                SELECT
                  (SELECT COUNT(*) FROM splitbook_chunk WHERE splitbook_id=CAST(:sid AS uuid)) AS chunks_total,
                  (SELECT COUNT(*) FROM splitbook_chunk_embedding e
                    JOIN splitbook_chunk c ON c.chunk_id=e.chunk_id
                   WHERE c.splitbook_id=CAST(:sid AS uuid)) AS embedded_total
                """
            ),
            {"sid": sid},
        )
        count_row = count_res.mappings().first() or {}
        chunks_total = int(count_row.get("chunks_total") or 0)
        embedded_total = int(count_row.get("embedded_total") or 0)
        derived_pct = int(round((embedded_total / chunks_total) * 100)) if chunks_total > 0 else 0

        job_rows = (
            await db.execute(
                text(
                    """
                    SELECT job_id::text AS job_id, capability_id, status, progress_value, progress, updated_at
                    FROM jobs
                    WHERE payload->>'splitbook_id' = :sid
                      AND capability_id IN ('splitbook.ingest.v1', 'splitbook.embed.v1')
                    ORDER BY updated_at DESC
                    """
                ),
                {"sid": sid},
            )
        ).mappings().all()

        latest_active: dict[str, dict] = {}
        latest_terminal: dict[str, dict] = {}
        for job in job_rows:
            cap = str(job.get("capability_id") or "").strip()
            status = str(job.get("status") or "").strip().lower()
            if not cap:
                continue
            if status in {"queued", "running"} and cap not in latest_active:
                latest_active[cap] = dict(job)
            if status in {"succeeded", "failed", "canceled", "cancelled"} and cap not in latest_terminal:
                latest_terminal[cap] = dict(job)

        active_ingest = latest_active.get("splitbook.ingest.v1")
        active_embed = latest_active.get("splitbook.embed.v1")
        terminal_ingest = latest_terminal.get("splitbook.ingest.v1")
        terminal_embed = latest_terminal.get("splitbook.embed.v1")

        next_ingest = current_ingest
        next_embed = current_embed

        if active_ingest:
            active_ingest_age = _job_age_seconds(active_ingest)
            active_ingest_status = str(active_ingest.get("status") or "").lower()
            ingest_done_conflict = current_ingest == "done"
            ingest_stale_conflict = active_ingest_status == "queued" and active_ingest_age >= 900
            if ingest_done_conflict or ingest_stale_conflict:
                next_ingest = "done"
            else:
                next_ingest = str(active_ingest.get("status") or "queued").lower()
        elif terminal_ingest:
            t = str(terminal_ingest.get("status") or "").lower()
            next_ingest = "done" if t == "succeeded" else t
        elif current_ingest in {"running", "queued", "ingesting"}:
            next_ingest = "pending"

        dirty_embed = False
        if active_embed:
            active_embed_age = _job_age_seconds(active_embed)
            active_embed_status = str(active_embed.get("status") or "").lower()
            active_embed_pct = _job_pct(active_embed)
            embed_done_conflict = current_embed == "done" or (chunks_total > 0 and embedded_total >= chunks_total)
            embed_stale_conflict = (
                (active_embed_status == "queued" and active_embed_age >= 1800)
                or (active_embed_status == "running" and active_embed_age >= 7200 and active_embed_pct >= 99)
            )
            if embed_done_conflict or embed_stale_conflict:
                next_embed = "done" if (chunks_total > 0 and embedded_total >= chunks_total) or current_embed == "done" else "pending"
                stats.pop("active_embed_job_id", None)
                stats.pop("active_embed_job_status", None)
                stats["embed_progress_pct"] = 100 if next_embed == "done" else derived_pct
                if next_embed == "done":
                    stats.pop("recover_hint", None)
                else:
                    stats["recover_hint"] = "manual_resume_required"
                    dirty_embed = True
            else:
                next_embed = str(active_embed.get("status") or "queued").lower()
                stats["active_embed_job_id"] = str(active_embed.get("job_id") or "")
                stats["active_embed_job_status"] = next_embed
                stats["embed_progress_pct"] = _job_pct(active_embed)
                stats.pop("recover_hint", None)
        elif terminal_embed:
            t = str(terminal_embed.get("status") or "").lower()
            next_embed = "done" if t == "succeeded" else t
            stats.pop("active_embed_job_id", None)
            stats.pop("active_embed_job_status", None)
            stats["embed_progress_pct"] = 100 if next_embed == "done" else derived_pct
            stats.pop("recover_hint", None)
        elif current_embed in {"running", "queued"}:
            if chunks_total > 0 and embedded_total >= chunks_total:
                next_embed = "done"
                stats.pop("recover_hint", None)
            else:
                next_embed = "pending"
                stats["recover_hint"] = "manual_resume_required"
                dirty_embed = True
            stats.pop("active_embed_job_id", None)
            stats.pop("active_embed_job_status", None)
            stats["embed_progress_pct"] = derived_pct
        else:
            stats.pop("active_embed_job_id", None)
            stats.pop("active_embed_job_status", None)
            if chunks_total > 0:
                stats["embed_progress_pct"] = derived_pct
            if next_embed != "pending":
                stats.pop("recover_hint", None)

        stats["chunks_total"] = chunks_total
        stats["embedded_total"] = embedded_total
        if dirty_embed and "recover_hint" not in stats:
            stats["recover_hint"] = "manual_resume_required"

        if next_ingest != current_ingest or next_embed != current_embed or stats != dict(row.get("stats") or {}):
            await update_splitbook_status(
                db,
                sid,
                ingest_status=next_ingest,
                embed_status=next_embed,
                stats=stats,
            )
            updated += 1

    return {"checked": len(target_rows), "updated": updated}


@app.get("/v1/splitbooks")
async def list_splitbooks_route(
    limit: int = Query(default=100, ge=1, le=500),
    sync: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if sync:
        await reconcile_splitbook_state(db)
    rows = await list_splitbooks(db, limit=limit)
    return {"items": rows}


@app.get("/v1/splitbooks/compare")
async def compare_splitbooks_route(
    splitbook_ids: str | None = Query(default=None),
    limit: int = Query(default=8, ge=2, le=20),
    db: AsyncSession = Depends(get_db),
) -> dict:
    raw_ids = [x.strip() for x in str(splitbook_ids or "").split(",") if x.strip()]
    selected: list[dict] = []
    if raw_ids:
        rows = await db.execute(
            text(
                """
                SELECT splitbook_id::text AS splitbook_id, name, author, ingest_status, embed_status, stats, created_at
                FROM splitbook
                WHERE splitbook_id = ANY(:ids)
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"ids": raw_ids, "limit": max(2, min(int(limit), 20))},
        )
        selected = [dict(r) for r in rows.mappings().all()]
    if not selected:
        rows = await db.execute(
            text(
                """
                SELECT splitbook_id::text AS splitbook_id, name, author, ingest_status, embed_status, stats, created_at
                FROM splitbook
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": max(2, min(int(limit), 20))},
        )
        selected = [dict(r) for r in rows.mappings().all()]
    if not selected:
        return {"items": [], "pairwise": [], "baseline_splitbook_id": None}

    def _cosine(a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(float(x) * float(y) for x, y in zip(a, b))
        na = math.sqrt(sum(float(x) * float(x) for x in a))
        nb = math.sqrt(sum(float(y) * float(y) for y in b))
        if na <= 0 or nb <= 0:
            return 0.0
        return dot / (na * nb)

    items_out: list[dict] = []
    for row in selected:
        sid = str(row.get("splitbook_id") or "")
        stats_obj = row.get("stats") if isinstance(row.get("stats"), dict) else {}
        counts_row = await db.execute(
            text(
                """
                SELECT
                  (SELECT COUNT(*) FROM splitbook_chunk WHERE splitbook_id=CAST(:sid AS uuid)) AS chunk_total,
                  (SELECT COUNT(*) FROM splitbook_fact WHERE splitbook_id=CAST(:sid AS uuid)) AS fact_total,
                  (SELECT COUNT(*) FROM splitbook_growth_ledger WHERE splitbook_id=CAST(:sid AS uuid)) AS growth_total,
                  (SELECT COUNT(DISTINCT character_name) FROM splitbook_growth_ledger WHERE splitbook_id=CAST(:sid AS uuid)) AS character_total
                """
            ),
            {"sid": sid},
        )
        counts = counts_row.mappings().first() or {}
        text_rows = await db.execute(
            text(
                """
                SELECT text
                FROM splitbook_chunk
                WHERE splitbook_id=CAST(:sid AS uuid)
                ORDER BY chunk_no
                LIMIT 120
                """
            ),
            {"sid": sid},
        )
        merged_text = "\n".join(str(r.get("text") or "") for r in text_rows.mappings().all())
        style_metrics = _simple_style_metrics(merged_text)
        merged_lower = str(merged_text or "")
        token_base = max(1, len(merged_lower))
        conflict_hits = sum(merged_lower.count(x) for x in ["冲突", "对抗", "危机", "威胁", "反击", "追杀"])
        payoff_hits = sum(merged_lower.count(x) for x in ["回收", "揭晓", "答案", "反转", "应验", "兑现"])
        pressure_hits = sum(merged_lower.count(x) for x in ["压力", "倒计时", "逼迫", "危急", "濒临"])
        conflict_density = round((conflict_hits / token_base) * 10000, 3)
        payoff_density = round((payoff_hits / token_base) * 10000, 3)
        pressure_density = round((pressure_hits / token_base) * 10000, 3)
        style_vector = [
            round(min(1.0, float(style_metrics.get("sentence_avg_len") or 0.0) / 40.0), 6),
            round(min(1.0, float(style_metrics.get("short_sentence_ratio") or 0.0)), 6),
            round(min(1.0, float(style_metrics.get("dialog_ratio") or 0.0)), 6),
            round(min(1.0, conflict_density / 12.0), 6),
            round(min(1.0, payoff_density / 10.0), 6),
            round(min(1.0, pressure_density / 10.0), 6),
        ]
        items_out.append(
            {
                "splitbook_id": sid,
                "name": str(row.get("name") or ""),
                "author": str(row.get("author") or ""),
                "ingest_status": str(row.get("ingest_status") or ""),
                "embed_status": str(row.get("embed_status") or ""),
                "counts": {
                    "chunks": int(counts.get("chunk_total") or stats_obj.get("chunks_total") or 0),
                    "facts": int(counts.get("fact_total") or stats_obj.get("fact_total") or 0),
                    "growth_rows": int(counts.get("growth_total") or stats_obj.get("growth_rows") or 0),
                    "characters": int(counts.get("character_total") or stats_obj.get("character_total") or 0),
                },
                "style_metrics": style_metrics,
                "structure_metrics": {
                    "conflict_density_per_10k_chars": conflict_density,
                    "payoff_density_per_10k_chars": payoff_density,
                    "pressure_density_per_10k_chars": pressure_density,
                },
                "style_vector": style_vector,
            }
        )

    baseline = items_out[0]
    baseline_vec = list(baseline.get("style_vector") or [])
    pairwise: list[dict] = []
    for item in items_out[1:]:
        vec = list(item.get("style_vector") or [])
        bm = baseline.get("style_metrics") if isinstance(baseline.get("style_metrics"), dict) else {}
        im = item.get("style_metrics") if isinstance(item.get("style_metrics"), dict) else {}
        bs = baseline.get("structure_metrics") if isinstance(baseline.get("structure_metrics"), dict) else {}
        is_ = item.get("structure_metrics") if isinstance(item.get("structure_metrics"), dict) else {}
        pairwise.append(
            {
                "baseline_splitbook_id": str(baseline.get("splitbook_id") or ""),
                "compare_splitbook_id": str(item.get("splitbook_id") or ""),
                "similarity": round(_cosine(baseline_vec, vec), 4),
                "deltas": {
                    "sentence_avg_len": round(float(im.get("sentence_avg_len") or 0.0) - float(bm.get("sentence_avg_len") or 0.0), 4),
                    "short_sentence_ratio": round(float(im.get("short_sentence_ratio") or 0.0) - float(bm.get("short_sentence_ratio") or 0.0), 4),
                    "dialog_ratio": round(float(im.get("dialog_ratio") or 0.0) - float(bm.get("dialog_ratio") or 0.0), 4),
                    "conflict_density_per_10k_chars": round(float(is_.get("conflict_density_per_10k_chars") or 0.0) - float(bs.get("conflict_density_per_10k_chars") or 0.0), 4),
                    "payoff_density_per_10k_chars": round(float(is_.get("payoff_density_per_10k_chars") or 0.0) - float(bs.get("payoff_density_per_10k_chars") or 0.0), 4),
                },
            }
        )

    return {
        "baseline_splitbook_id": str(baseline.get("splitbook_id") or ""),
        "items": items_out,
        "pairwise": pairwise,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/v1/splitbooks")
async def create_splitbook_route(body: SplitbookCreateRequest, db: AsyncSession = Depends(get_db)) -> dict:
    row = await create_splitbook(
        db,
        name=body.name,
        author=body.author,
        source_path=body.source_path,
        note=body.note,
    )
    return row


@app.delete("/v1/splitbooks/{splitbook_id}")
async def delete_splitbook_route(
    splitbook_id: UUID,
    purge_assets: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> dict:
    sid = str(splitbook_id)
    row = await get_splitbook(db, sid)
    if not row:
        raise HTTPException(status_code=404, detail="SPLITBOOK_NOT_FOUND")
    running = (
        await db.execute(
            text(
                """
                SELECT job_id::text AS job_id
                FROM jobs
                WHERE status IN ('queued', 'running')
                  AND payload->>'splitbook_id' = :sid
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"sid": sid},
        )
    ).mappings().first()
    if running:
        raise HTTPException(status_code=409, detail="SPLITBOOK_JOB_RUNNING")
    deleted = await delete_splitbook(db, sid, purge_assets=bool(purge_assets))
    if not deleted:
        raise HTTPException(status_code=404, detail="SPLITBOOK_NOT_FOUND")
    deleted_jobs = await delete_jobs_by_splitbook(db, sid, include_active=False)
    return {
        "ok": True,
        "deleted": deleted,
        "purge_assets": bool(purge_assets),
        "deleted_job_records": int(deleted_jobs),
    }


@app.post("/v1/splitbooks/{splitbook_id}/allow_guard")
async def set_splitbook_allow_guard_route(
    splitbook_id: UUID,
    body: SplitbookAllowGuardRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await update_splitbook_allow_guard(db, str(splitbook_id), body.allow_guard)
    if not row:
        raise HTTPException(status_code=404, detail="SPLITBOOK_NOT_FOUND")
    return row


@app.post("/v1/splitbooks/{splitbook_id}/ingest", response_model=SubmitJobResponse, status_code=202)
async def splitbook_ingest_route(
    splitbook_id: UUID,
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SubmitJobResponse:
    row = await get_splitbook(db, str(splitbook_id))
    if not row:
        raise HTTPException(status_code=404, detail="SPLITBOOK_NOT_FOUND")
    global_settings = await get_global_settings_scoped(db)
    ingest_cfg = (global_settings or {}).get("ingest") or {}
    req_id = request_id(request)
    payload = {
        "splitbook_id": str(splitbook_id),
        "path": body.get("path") or row.get("source_path"),
        "encoding": body.get("encoding") or ingest_cfg.get("encoding") or "utf-8",
        "chunk_size": int(body.get("chunk_size") or ingest_cfg.get("chunk_size") or 600),
        "overlap": int(body.get("overlap") or ingest_cfg.get("overlap") or 120),
        "batch_insert": int(body.get("batch_insert") or ingest_cfg.get("batch_insert") or 300),
        "auto_optimize": bool(body.get("auto_optimize", True)),
    }
    await update_splitbook_status(db, str(splitbook_id), ingest_status="queued")
    job = await create_job(db, "splitbook.ingest.v1", payload, req_id)
    await job_runner.enqueue(job["job_id"], req_id)
    return SubmitJobResponse(job_id=job["job_id"], status="queued", queued_at=job["created_at"], request_id=req_id)


@app.post("/v1/splitbooks/{splitbook_id}/embed", response_model=SubmitJobResponse, status_code=202)
async def splitbook_embed_route(
    splitbook_id: UUID,
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SubmitJobResponse:
    row = await get_splitbook(db, str(splitbook_id))
    if not row:
        raise HTTPException(status_code=404, detail="SPLITBOOK_NOT_FOUND")
    force_embed = bool(body.get("force") or False)
    if str(row.get("embed_status") or "").strip().lower() == "done" and not force_embed:
        raise HTTPException(status_code=409, detail="SPLITBOOK_EMBED_ALREADY_DONE")
    running = (
        await db.execute(
            text(
                """
                SELECT job_id::text AS job_id
                FROM jobs
                WHERE capability_id='splitbook.embed.v1'
                  AND status IN ('queued', 'running')
                  AND payload->>'splitbook_id' = :sid
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"sid": str(splitbook_id)},
        )
    ).mappings().first()
    if running:
        raise HTTPException(status_code=409, detail="SPLITBOOK_JOB_RUNNING")
    global_settings = await get_global_settings_scoped(db)
    embed_cfg = (global_settings or {}).get("embedding") or {}
    req_id = request_id(request)
    payload = {
        "splitbook_id": str(splitbook_id),
        "model": body.get("model") or embed_cfg.get("model") or settings.embedding_model,
        "batch": int(body.get("batch") or embed_cfg.get("batch") or 64),
        "worker_count": int(body.get("worker_count") or embed_cfg.get("worker_count") or 2),
        "force": force_embed,
        "auto_optimize": bool(body.get("auto_optimize", True)),
        "output_dir": str(body.get("output_dir") or "").strip() or None,
    }
    await update_splitbook_status(db, str(splitbook_id), embed_status="queued")
    job = await create_job(db, "splitbook.embed.v1", payload, req_id)
    await job_runner.enqueue(job["job_id"], req_id)
    return SubmitJobResponse(job_id=job["job_id"], status="queued", queued_at=job["created_at"], request_id=req_id)


@app.post("/v1/splitbooks/{splitbook_id}/build_templates", response_model=SubmitJobResponse, status_code=202)
async def splitbook_build_templates_route(
    splitbook_id: UUID,
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SubmitJobResponse:
    row = await get_splitbook(db, str(splitbook_id))
    if not row:
        raise HTTPException(status_code=404, detail="SPLITBOOK_NOT_FOUND")
    req_id = request_id(request)
    payload = {"splitbook_id": str(splitbook_id), "mode": body.get("mode") or "merge"}
    job = await create_job(db, "splitbook.build_templates.v1", payload, req_id)
    await job_runner.enqueue(job["job_id"], req_id)
    return SubmitJobResponse(job_id=job["job_id"], status="queued", queued_at=job["created_at"], request_id=req_id)


@app.post("/v1/splitbooks/{splitbook_id}/extract_structured", response_model=SubmitJobResponse, status_code=202)
async def splitbook_extract_structured_route(
    splitbook_id: UUID,
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SubmitJobResponse:
    row = await get_splitbook(db, str(splitbook_id))
    if not row:
        raise HTTPException(status_code=404, detail="SPLITBOOK_NOT_FOUND")
    req_id = request_id(request)
    payload = {
        "splitbook_id": str(splitbook_id),
        "mode": body.get("mode") or "full",
        "extract_provider": body.get("extract_provider") or body.get("provider"),
        "extract_model": body.get("extract_model") or body.get("llm_model"),
        "pipeline_mode": body.get("pipeline_mode"),
        "use_scene_judge": body.get("use_scene_judge"),
        "pair_judge_enabled": body.get("pair_judge_enabled"),
        "subtask_retries": body.get("subtask_retries"),
        "subtask_timeout_s": body.get("subtask_timeout_s"),
        "subtask_tasks": body.get("subtask_tasks"),
    }
    job = await create_job(db, "splitbook.extract_structured.v1", payload, req_id)
    await job_runner.enqueue(job["job_id"], req_id)
    return SubmitJobResponse(job_id=job["job_id"], status="queued", queued_at=job["created_at"], request_id=req_id)


@app.post("/v1/splitbooks/{splitbook_id}/build_profile", response_model=SubmitJobResponse, status_code=202)
async def splitbook_build_profile_route(
    splitbook_id: UUID,
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SubmitJobResponse:
    row = await get_splitbook(db, str(splitbook_id))
    if not row:
        raise HTTPException(status_code=404, detail="SPLITBOOK_NOT_FOUND")
    req_id = request_id(request)
    payload = {
        "splitbook_id": str(splitbook_id),
        "mode": body.get("mode") or "create",
        "name": body.get("name") or f"参考风格-{row.get('name') or str(splitbook_id)[:8]}",
    }
    job = await create_job(db, "splitbook.build_profile.v1", payload, req_id)
    await job_runner.enqueue(job["job_id"], req_id)
    return SubmitJobResponse(job_id=job["job_id"], status="queued", queued_at=job["created_at"], request_id=req_id)


@app.post("/v1/splitbooks/{splitbook_id}/writeback_preview_batch", response_model=SubmitJobResponse, status_code=202)
async def splitbook_writeback_preview_batch_route(
    splitbook_id: UUID,
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SubmitJobResponse:
    row = await get_splitbook(db, str(splitbook_id))
    if not row:
        raise HTTPException(status_code=404, detail="SPLITBOOK_NOT_FOUND")
    running = (
        await db.execute(
            text(
                """
                SELECT job_id::text AS job_id
                FROM jobs
                WHERE capability_id='splitbook.writeback_batch.v1'
                  AND status IN ('queued', 'running')
                  AND payload->>'splitbook_id' = :sid
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"sid": str(splitbook_id)},
        )
    ).mappings().first()
    if running:
        raise HTTPException(status_code=409, detail="SPLITBOOK_JOB_RUNNING")
    req_id = request_id(request)
    payload = {
        "splitbook_id": str(splitbook_id),
        "mode": "preview",
        "chapter_nos": body.get("chapter_nos"),
        "max_chapters": body.get("max_chapters"),
        "force": body.get("force"),
    }
    job = await create_job(db, "splitbook.writeback_batch.v1", payload, req_id)
    await job_runner.enqueue(job["job_id"], req_id)
    return SubmitJobResponse(job_id=job["job_id"], status="queued", queued_at=job["created_at"], request_id=req_id)


@app.post("/v1/splitbooks/{splitbook_id}/writeback_confirm_batch", response_model=SubmitJobResponse, status_code=202)
async def splitbook_writeback_confirm_batch_route(
    splitbook_id: UUID,
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SubmitJobResponse:
    row = await get_splitbook(db, str(splitbook_id))
    if not row:
        raise HTTPException(status_code=404, detail="SPLITBOOK_NOT_FOUND")
    running = (
        await db.execute(
            text(
                """
                SELECT job_id::text AS job_id
                FROM jobs
                WHERE capability_id='splitbook.writeback_batch.v1'
                  AND status IN ('queued', 'running')
                  AND payload->>'splitbook_id' = :sid
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"sid": str(splitbook_id)},
        )
    ).mappings().first()
    if running:
        raise HTTPException(status_code=409, detail="SPLITBOOK_JOB_RUNNING")
    req_id = request_id(request)
    payload = {
        "splitbook_id": str(splitbook_id),
        "mode": "confirm",
        "chapter_nos": body.get("chapter_nos"),
        "max_chapters": body.get("max_chapters"),
        "force": body.get("force"),
        "preview_token": body.get("preview_token"),
        "stop_on_error": body.get("stop_on_error"),
    }
    job = await create_job(db, "splitbook.writeback_batch.v1", payload, req_id)
    await job_runner.enqueue(job["job_id"], req_id)
    return SubmitJobResponse(job_id=job["job_id"], status="queued", queued_at=job["created_at"], request_id=req_id)


@app.get("/v1/splitbooks/{splitbook_id}/ledger")
async def splitbook_ledger_route(
    splitbook_id: UUID,
    view: str = Query(default="chapter"),
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
) -> dict:
    sb = await get_splitbook(db, str(splitbook_id))
    if not sb:
        raise HTTPException(status_code=404, detail="SPLITBOOK_NOT_FOUND")
    view_norm = "character" if str(view).lower() == "character" else "chapter"
    return await get_splitbook_ledger_view(db, str(splitbook_id), view=view_norm, limit=limit)


@app.get("/v1/splitbooks/{splitbook_id}/outline")
async def splitbook_outline_route(splitbook_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    sb = await get_splitbook(db, str(splitbook_id))
    if not sb:
        raise HTTPException(status_code=404, detail="SPLITBOOK_NOT_FOUND")
    return await build_splitbook_outline(db, str(splitbook_id))


@app.get("/v1/splitbooks/{splitbook_id}/scenes")
async def splitbook_scene_view_route(
    splitbook_id: UUID,
    chapter_no: int | None = Query(default=None, ge=1, le=999999),
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> dict:
    sb = await get_splitbook(db, str(splitbook_id))
    if not sb:
        raise HTTPException(status_code=404, detail="SPLITBOOK_NOT_FOUND")
    return await get_splitbook_scene_view(db, str(splitbook_id), chapter_no=chapter_no, limit=limit)


@app.get("/v1/splitbooks/{splitbook_id}/pairs")
async def splitbook_pair_view_route(
    splitbook_id: UUID,
    chapter_no: int | None = Query(default=None, ge=1, le=999999),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> dict:
    sb = await get_splitbook(db, str(splitbook_id))
    if not sb:
        raise HTTPException(status_code=404, detail="SPLITBOOK_NOT_FOUND")
    return await get_splitbook_pair_view(
        db,
        str(splitbook_id),
        chapter_no=chapter_no,
        min_confidence=min_confidence,
        limit=limit,
    )


@app.get("/v1/splitbooks/{splitbook_id}/qa_report")
async def splitbook_qa_report_route(splitbook_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    sb = await get_splitbook(db, str(splitbook_id))
    if not sb:
        raise HTTPException(status_code=404, detail="SPLITBOOK_NOT_FOUND")
    return await get_splitbook_qa_report(db, str(splitbook_id))


@app.get("/v1/splitbooks/{splitbook_id}/chapter_pack")
async def splitbook_chapter_pack_route(
    splitbook_id: UUID,
    chapter_no: int = Query(..., ge=1, le=999999),
    db: AsyncSession = Depends(get_db),
) -> dict:
    sb = await get_splitbook(db, str(splitbook_id))
    if not sb:
        raise HTTPException(status_code=404, detail="SPLITBOOK_NOT_FOUND")
    return await build_splitbook_chapter_pack(db, str(splitbook_id), chapter_no=chapter_no)


@app.post("/v1/splitbooks/{splitbook_id}/writeback")
async def splitbook_writeback_route(splitbook_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    sb = await get_splitbook(db, str(splitbook_id))
    if not sb:
        raise HTTPException(status_code=404, detail="SPLITBOOK_NOT_FOUND")
    try:
        return await writeback_splitbook_chapter(db, str(splitbook_id), body or {})
    except RuntimeError as exc:
        detail = str(exc)
        if detail in {"WRITEBACK_CONTENT_REQUIRED"}:
            raise HTTPException(status_code=400, detail=detail) from exc
        raise


@app.post("/v1/splitbooks/{splitbook_id}/chapter_health")
async def splitbook_chapter_health_route(splitbook_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    sb = await get_splitbook(db, str(splitbook_id))
    if not sb:
        raise HTTPException(status_code=404, detail="SPLITBOOK_NOT_FOUND")
    return await splitbook_chapter_health_report(db, str(splitbook_id), body or {})


@app.post("/v1/splitbooks/{splitbook_id}/anti_copy_check")
async def splitbook_anti_copy_check_route(splitbook_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    sb = await get_splitbook(db, str(splitbook_id))
    if not sb:
        raise HTTPException(status_code=404, detail="SPLITBOOK_NOT_FOUND")
    try:
        return await splitbook_anti_copy_check(db, str(splitbook_id), body or {})
    except RuntimeError as exc:
        detail = str(exc)
        if detail in {"ANTI_COPY_CONTENT_REQUIRED", "ANTI_COPY_CONTENT_TOO_SHORT"}:
            raise HTTPException(status_code=400, detail=detail) from exc
        raise


@app.post("/v1/splitbooks/library/build")
async def splitbook_library_build_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await build_splitbook_template_library(db, body or {})
    except RuntimeError as exc:
        detail = str(exc)
        if detail in {"SPLITBOOK_IDS_EMPTY", "SPLITBOOK_STATS_EMPTY"}:
            raise HTTPException(status_code=400, detail=detail) from exc
        raise


@app.get("/v1/splitbooks/{splitbook_id}/diagnose_bundle")
async def splitbook_diagnose_bundle_route(
    splitbook_id: UUID,
    limit: int = Query(default=30, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    sb = await get_splitbook(db, str(splitbook_id))
    if not sb:
        raise HTTPException(status_code=404, detail="SPLITBOOK_NOT_FOUND")

    health = await health_checks(db)

    async def _jobs(status: str) -> list[dict]:
        res = await db.execute(
            text(
                """
                SELECT job_id, book_id, chapter_id, job_type, capability_id, status, stage, progress_value, progress, run_id, payload, result, logs, error, created_at, updated_at
                FROM jobs
                WHERE status=:status
                  AND payload->>'splitbook_id' = :sid
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"status": status, "sid": str(splitbook_id), "limit": limit},
        )
        return [dict(r) for r in res.mappings().all()]

    failed = await _jobs("failed")
    running = await _jobs("running")
    done = await _jobs("succeeded")

    tmpl = await db.execute(
        text(
            """
            SELECT asset_id, asset_type, name, tags, created_at
            FROM template_asset
            WHERE source_splitbook_id = :sid
            ORDER BY created_at DESC
            LIMIT 50
            """
        ),
        {"sid": str(splitbook_id)},
    )
    template_assets = [dict(r) for r in tmpl.mappings().all()]

    prof = await db.execute(
        text(
            """
            SELECT profile_id, name, note, features, dos, donts, created_at, updated_at
            FROM profile
            WHERE note ILIKE :needle
            ORDER BY updated_at DESC
            LIMIT 20
            """
        ),
        {"needle": f"%{str(splitbook_id)}%"},
    )
    related_profiles = [dict(r) for r in prof.mappings().all()]

    return {
        "splitbook_id": str(splitbook_id),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "health": health,
        "splitbook": sb,
        "jobs_failed_recent": failed,
        "jobs_running_recent": running,
        "jobs_done_recent": done,
        "template_assets": template_assets,
        "related_profiles": related_profiles,
        "summary": {
            "failed": len(failed),
            "running": len(running),
            "done": len(done),
            "template_assets": len(template_assets),
            "related_profiles": len(related_profiles),
        },
    }


@app.post("/v1/jobs", response_model=SubmitJobResponse, status_code=202)
async def submit_job(body: JobCreateRequest, request: Request, db: AsyncSession = Depends(get_db)) -> SubmitJobResponse:
    req_id = request_id(request)
    row = await create_job(db, body.capability_id, body.input, req_id)
    await job_runner.enqueue(row["job_id"], req_id)
    return SubmitJobResponse(job_id=row["job_id"], status="queued", queued_at=row["created_at"], request_id=req_id)


@app.get("/v1/jobs")
async def list_jobs_route(
    status: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    items = await list_jobs(db, status=status, limit=limit)
    return {"items": items}


@app.delete("/v1/jobs")
async def delete_jobs_route(
    status: str | None = Query(default=None),
    statuses: str | None = Query(default=None),
    limit: int = Query(default=5000, ge=1, le=50000),
    db: AsyncSession = Depends(get_db),
) -> dict:
    status_value = str(status or "").strip().lower() or None
    statuses_value = [str(x).strip().lower() for x in str(statuses or "").split(",") if str(x).strip()]
    if status_value == "running" or "running" in statuses_value:
        raise HTTPException(status_code=400, detail="JOB_DELETE_RUNNING_FORBIDDEN")
    deleted_count = await delete_jobs(
        db,
        status=status_value,
        statuses=statuses_value or None,
        limit=limit,
        exclude_running=True,
    )
    return {"ok": True, "deleted_count": int(deleted_count), "status": status_value, "statuses": statuses_value}


@app.delete("/v1/jobs/{job_id}")
async def delete_job_route(job_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        row = await delete_job_by_id(db, str(job_id), allow_active=False)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="JOB_NOT_FOUND")
    return {"ok": True, "deleted": {"job_id": str(row.get("job_id") or ""), "status": str(row.get("status") or "")}}


@app.get("/v1/jobs/examples")
async def list_job_examples_route() -> dict:
    return {"items": JOB_EXAMPLES}


@app.get("/v1/jobs/examples/{job_type}")
async def get_job_example_route(job_type: str) -> dict:
    key = job_type.upper()
    item = JOB_EXAMPLES.get(key)
    if not item:
        raise HTTPException(status_code=404, detail="JOB_EXAMPLE_NOT_FOUND")
    return {"job_type": key, **item}


@app.post("/v1/jobs/{job_id}/cancel")
async def cancel_job_route(job_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    row = await get_job(db, job_id)
    if not row:
        raise HTTPException(status_code=404, detail="JOB_NOT_FOUND")
    capability_id = str(row.get("capability_id") or "")
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    splitbook_id = str(payload.get("splitbook_id") or "").strip() if capability_id.startswith("splitbook.") else ""
    if row["status"] in ("succeeded", "failed", "canceled"):
        if splitbook_id:
            await reconcile_splitbook_state(db, splitbook_id=splitbook_id)
        return {"ok": True, "status": row["status"]}
    await db.execute(
        text(
            """
            UPDATE jobs
            SET status='canceled', stage='CANCELED', updated_at=now()
            WHERE job_id=:job_id
            """
        ),
        {"job_id": str(job_id)},
    )
    await db.commit()
    if splitbook_id:
        await reconcile_splitbook_state(db, splitbook_id=splitbook_id)
    return {"ok": True, "status": "canceled"}


@app.post("/v1/jobs/{job_id}/resume")
async def resume_job_route(
    job_id: UUID,
    request: Request,
    force: bool = Query(default=False),
    stale_seconds: int = Query(default=90, ge=10, le=3600),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await get_job(db, job_id)
    if not row:
        raise HTTPException(status_code=404, detail="JOB_NOT_FOUND")
    capability_id = str(row.get("capability_id") or "")
    payload = row.get("payload")
    if not isinstance(payload, dict):
        payload = {}
    splitbook_id = str(payload.get("splitbook_id") or "").strip() if capability_id.startswith("splitbook.") else ""

    status = str(row.get("status") or "").strip().lower()
    if status == "succeeded":
        raise HTTPException(status_code=400, detail="JOB_RESUME_FORBIDDEN_DONE")
    if status == "canceled":
        raise HTTPException(status_code=400, detail="JOB_RESUME_FORBIDDEN_CANCELED")

    now = datetime.now(timezone.utc)
    updated_at = row.get("updated_at")
    stale = False
    if isinstance(updated_at, datetime):
        dt = updated_at if updated_at.tzinfo else updated_at.replace(tzinfo=timezone.utc)
        stale = (now - dt).total_seconds() >= float(stale_seconds)
    if status == "running" and not stale and not force:
        raise HTTPException(status_code=409, detail="JOB_RESUME_RUNNING_ACTIVE")

    progress = row.get("progress")
    if not isinstance(progress, dict):
        progress = {}
    pct = int(progress.get("pct") or max(1, int(float(row.get("progress_value") or 0) * 100)))
    await db.execute(
        text(
            """
            UPDATE jobs
            SET status='queued',
                stage='QUEUED',
                error=NULL,
                progress=CAST(:progress AS jsonb),
                progress_value=:progress_value,
                updated_at=now()
            WHERE job_id=:job_id
            """
        ),
        {
            "job_id": str(job_id),
            "progress": json.dumps(
                {
                    "pct": max(1, min(99, pct)),
                    "phase": "queued",
                    "message": "任务已重新排队，等待继续执行",
                    "counters": progress.get("counters") or {},
                }
            ),
            "progress_value": max(0.01, min(0.99, max(1, pct) / 100.0)),
        },
    )
    await db.commit()
    if splitbook_id:
        await reconcile_splitbook_state(db, splitbook_id=splitbook_id)

    req_id = request_id(request)
    await job_runner.enqueue(row["job_id"], str(payload.get("request_id") or req_id))
    return {
        "ok": True,
        "job_id": str(job_id),
        "status": "queued",
        "stale": stale,
        "forced": bool(force),
        "request_id": req_id,
    }


@app.post("/v1/books/{book_id}/extract/structure_beats", response_model=SubmitJobResponse, status_code=202)
async def extract_structure_beats_route(
    book_id: UUID,
    body: StructureBeatsExtractRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SubmitJobResponse:
    req_id = request_id(request)
    payload = {"book_id": str(book_id), "scope": body.scope, "schema_ver": body.schema_ver}
    if body.llm_model:
        payload["llm_model"] = body.llm_model
    _attach_trigger_meta(
        payload,
        trigger_source=body.trigger_source,
        trigger_entry=body.trigger_entry,
        trigger_mode=body.trigger_mode,
    )
    row = await create_job(db, "extract.structure_beats.v1", payload, req_id)
    await job_runner.enqueue(row["job_id"], req_id)
    return SubmitJobResponse(job_id=row["job_id"], status="queued", queued_at=row["created_at"], request_id=req_id)


@app.get("/v1/jobs/{job_id}")
async def get_job_route(job_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    row = await get_job(db, job_id)
    if not row:
        raise HTTPException(status_code=404, detail="JOB_NOT_FOUND")
    return row


@app.get("/v1/skill_runs/{skill_run_id}")
async def get_skill_run_route(skill_run_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await get_skill_run_output(db, str(skill_run_id))
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/v1/skill_runs/latest")
async def get_latest_skill_run_route(
    chapter_id: UUID = Query(...),
    skill_name: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await get_latest_skill_run_service(db, str(chapter_id), skill_name)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/v1/chapters/{chapter_id}/outline_detail")
async def get_outline_detail_route(
    chapter_id: UUID,
    version: str = Query(default="latest"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        ver_num = None if version == "latest" else int(version)
        return await get_outline_detail_service(db, str(chapter_id), ver_num)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="INVALID_VERSION") from exc


@app.get("/v1/chapters/{chapter_id}/outline_detail/versions")
async def list_outline_versions_route(chapter_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    items = await list_outline_versions_service(db, str(chapter_id))
    return {"items": items}


@app.delete("/v1/chapters/{chapter_id}/outline_detail")
async def delete_outline_detail_route(
    chapter_id: UUID,
    version: str = Query(default="latest"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        ver_num = None if str(version).strip().lower() == "latest" else int(version)
        if ver_num is not None and ver_num < 1:
            raise ValueError("INVALID_VERSION")
        deleted = await delete_outline_detail_service(db, str(chapter_id), ver_num)
        return {"ok": True, **deleted}
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="INVALID_VERSION") from exc


@app.get("/v1/chapters/{chapter_id}/outline_detail/diff")
async def outline_detail_diff_route(
    chapter_id: UUID,
    from_version: int = Query(..., alias="from", ge=1),
    to_version: int = Query(..., alias="to", ge=1),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await get_outline_detail_diff(db, str(chapter_id), from_version, to_version)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/v1/chapters/{chapter_id}/eval/compare")
async def eval_compare_route(
    chapter_id: UUID,
    before_run_id: UUID = Query(...),
    after_run_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await compare_eval_runs(db, str(chapter_id), str(before_run_id), str(after_run_id))
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/v1/chapters/{chapter_id}/outline_detail/save")
async def save_outline_detail_route(
    chapter_id: UUID,
    body: OutlineDetailSaveRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        saved = await save_outline_detail_service(db, str(chapter_id), body.outline, body.note)
        return {"ok": True, **saved}
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/v1/chapters/{chapter_id}/outline_detail/auto_generate")
async def auto_generate_outline_detail_route(
    chapter_id: UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await db.execute(
        text(
            """
            SELECT c.chapter_id::text AS chapter_id, c.book_id::text AS book_id, c.title AS chapter_title,
                   c."order" AS chapter_no,
                   v.volume_id::text AS volume_id, v.volume_no, v.title AS volume_title
            FROM chapter c
            LEFT JOIN volume v
              ON v.book_id=c.book_id
             AND c."order" BETWEEN v.start_chapter_no AND v.end_chapter_no
            WHERE c.chapter_id=CAST(:chapter_id AS uuid)
            ORDER BY v.volume_no DESC
            LIMIT 1
            """
        ),
        {"chapter_id": str(chapter_id)},
    )
    hit = row.mappings().first()
    if not hit:
        raise HTTPException(status_code=404, detail="CHAPTER_NOT_FOUND")

    force = bool((body or {}).get("force", True))
    if not force:
        try:
            existing = await get_outline_detail_service(db, str(chapter_id), None)
            detail = existing.get("outline_detail") if isinstance(existing.get("outline_detail"), dict) else {}
            nodes = detail.get("nodes") if isinstance(detail.get("nodes"), list) else []
            if nodes:
                return {
                    "ok": True,
                    "chapter_id": str(chapter_id),
                    "reused": True,
                    "outline": detail,
                    "meta": {"reason": "outline_exists"},
                }
        except RuntimeError:
            pass

    book_id = str(hit.get("book_id") or "")
    chapter_no = int(hit.get("chapter_no") or 0)
    chapter_title = str(hit.get("chapter_title") or f"第{chapter_no}章").strip()
    volume_id = str(hit.get("volume_id") or "").strip()

    settings_value = await get_book_settings(db, book_id) or {}
    brief_from_settings = settings_value.get("writing_brief") if isinstance(settings_value.get("writing_brief"), dict) else {}
    outline_from_settings = settings_value.get("writing_master_outline") if isinstance(settings_value.get("writing_master_outline"), dict) else {}
    volume_plan = await _load_active_volume_plan(db, book_id=book_id, volume_id=volume_id) if volume_id else None
    plan_items = volume_plan.get("items") if isinstance(volume_plan, dict) and isinstance(volume_plan.get("items"), list) else []

    structure_hints = _normalize_structure_hints(body or {})
    splitbook_id = _resolve_splitbook_id_from_body(body or {})
    if not splitbook_id:
        splitbook_id = str((body or {}).get("splitbook_id") or "").strip()
    splitbook_outline_reference: dict[str, Any] = {}
    splitbook_chapter_pack: dict[str, Any] = {}
    if splitbook_id:
        structure_hints = await _merge_splitbook_hints(db, splitbook_id=splitbook_id, hints=structure_hints)
        splitbook_outline_reference = await _build_splitbook_outline_reference(db, splitbook_id=splitbook_id)
        try:
            splitbook_chapter_pack = await build_splitbook_chapter_pack(db, splitbook_id, chapter_no if chapter_no > 0 else 1)
        except Exception:
            splitbook_chapter_pack = {}
    safe_hints = _outline_safe_structure_hints(structure_hints)
    prompt_reference_text, prompt_reference_source = _load_master_outline_prompt_reference()

    plan_samples: list[dict[str, Any]] = []
    for item in plan_items[:8]:
        if not isinstance(item, dict):
            continue
        plan_samples.append(
            {
                "kind": str(item.get("kind") or ""),
                "summary": str(item.get("summary") or "")[:180],
                "target_window": str(item.get("target_window") or ""),
                "priority": int(item.get("priority") or 3),
            }
        )

    prompt_payload = {
        "chapter": {
            "chapter_no": chapter_no,
            "chapter_title": chapter_title,
            "volume_no": int(hit.get("volume_no") or 0),
            "volume_title": str(hit.get("volume_title") or ""),
        },
        "writing_brief": _build_master_outline_brief_payload(brief_from_settings),
        "master_outline": {
            "summary": str(outline_from_settings.get("summary") or "")[:1200],
            "core_conflict": str(outline_from_settings.get("core_conflict") or "")[:600],
            "theme": str(outline_from_settings.get("theme") or "")[:200],
            "phases": (outline_from_settings.get("phases") if isinstance(outline_from_settings.get("phases"), list) else [])[:10],
        },
        "volume_plan_items": plan_samples,
        "material_guidance": material_guidance,
        "structure_hints": safe_hints,
        "splitbook_outline_reference": splitbook_outline_reference,
        "splitbook_chapter_pack": {
            "chapter_no": int(splitbook_chapter_pack.get("chapter_no") or chapter_no),
            "key_conflicts": (splitbook_chapter_pack.get("key_conflicts") if isinstance(splitbook_chapter_pack.get("key_conflicts"), list) else [])[:5],
            "foreshadow": (splitbook_chapter_pack.get("foreshadow") if isinstance(splitbook_chapter_pack.get("foreshadow"), list) else [])[:5],
            "payoff": (splitbook_chapter_pack.get("payoff") if isinstance(splitbook_chapter_pack.get("payoff"), list) else [])[:5],
            "growth": (splitbook_chapter_pack.get("growth") if isinstance(splitbook_chapter_pack.get("growth"), list) else [])[:5],
        }
        if splitbook_chapter_pack
        else {},
        "requirements": {
            "language": "简体中文",
            "node_count": 4,
            "must_cover": ["目标", "冲突", "转折", "章末钩子"],
            "anti_copy": "仅借鉴结构，不复述任何来源原句",
        },
    }
    user_prompt = (
        "请生成章节章纲（结构节点），用于后续正文生成。\n"
        "输出 JSON：{chapter_title,nodes:[{node_id,type,summary}]}\n"
        "规则：\n"
        "1) 节点顺序建议 setup→conflict→turn→hook；可额外包含 payoff/reveal。\n"
        "2) 每个节点 summary 要可执行、可写成正文。\n"
        "3) 只借鉴拆书结构节奏，不可复述原文。\n"
        "4) 必须与总纲/卷纲保持连贯。\n\n"
        f"输入：{json.dumps(prompt_payload, ensure_ascii=False)}"
    )
    schema_hint = '{"chapter_title":"string","nodes":[{"node_id":"beat-setup","type":"setup","summary":"string"}]}'
    system_prompt = (
        "你是小说章节策划编辑，只输出合法 JSON。\n"
        "以下为总纲提示词参考：\n"
        f"{prompt_reference_text}"
    )
    try:
        client = OllamaClient(settings.ollama_host)
        raw = await client.chat_json(
            model=DEFAULT_LLM_MODEL,
            user=user_prompt,
            system=system_prompt,
            temperature=0.35,
            max_tokens=1800,
            timeout_s=150,
            retries=1,
            schema_hint=schema_hint,
            validate=_validate_chapter_outline_ai_json,
            meta={"route": "chapter_outline_auto_generate", "chapter_id": str(chapter_id)},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"OUTLINE_AUTO_GENERATE_FAILED:{str(exc)[:200]}") from exc

    outline_data = _normalize_chapter_outline_ai_json(raw if isinstance(raw, dict) else {}, chapter_title=chapter_title)
    saved = await save_outline_detail_service(db, str(chapter_id), outline_data, "auto_generate_with_ai")
    meta_payload = {
        "basis": [
            "writing_brief",
            "master_outline",
            "volume_plan",
            "splitbook_structure" if splitbook_id else "structure_hints",
            "prompt_md_template",
        ],
        "structure_hints_applied": int(structure_hints.get("total_lines") or 0),
        "material_guidance_count": len(material_guidance),
        "splitbook_id": splitbook_id or None,
        "prompt_template_source": prompt_reference_source,
        "ai_debug": {
            "route": "chapter_outline_auto_generate",
            "provider": "ollama",
            "model": DEFAULT_LLM_MODEL,
            "prompt_payload": prompt_payload,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "schema_hint": schema_hint,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    try:
        chapter_settings = await get_chapter_settings(db, str(chapter_id))
        chapter_settings_obj = chapter_settings if isinstance(chapter_settings, dict) else {}
        chapter_settings_obj["writing_chapter_outline_meta"] = meta_payload
        await set_chapter_settings(db, str(chapter_id), chapter_settings_obj)
    except Exception:
        pass
    return {
        "ok": True,
        "chapter_id": str(chapter_id),
        "saved": saved,
        "outline": outline_data,
        "meta": meta_payload,
    }


@app.post("/v1/chapters/{chapter_id}/outline_detail/apply_patches")
async def apply_outline_patches_route(
    chapter_id: UUID,
    body: OutlinePatchApplyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    row_book = await db.execute(text("SELECT book_id FROM chapter WHERE chapter_id=:chapter_id"), {"chapter_id": str(chapter_id)})
    book_id = row_book.scalar()
    if not book_id:
        raise HTTPException(status_code=404, detail="CHAPTER_NOT_FOUND")
    plan_skill_run_id = body.plan_skill_run_id or body.skill_run_id
    if not plan_skill_run_id:
        raise HTTPException(status_code=400, detail="MISSING_PLAN_SKILL_RUN_ID")
    req_id = request_id(request)
    repair_txn_id = str(uuid4())
    payload = {
        "book_id": str(book_id),
        "chapter_id": str(chapter_id),
        "plan_skill_run_id": str(plan_skill_run_id),
        "selected_patch_ids": body.selected_patch_ids,
        "targets": body.targets.model_dump(),
        "style": body.style.model_dump(),
        "auto_eval": body.auto_eval,
        "repair_txn_id": repair_txn_id,
    }
    _attach_trigger_meta(
        payload,
        trigger_source=body.trigger_source,
        trigger_entry=body.trigger_entry,
        trigger_mode=body.trigger_mode,
    )
    row = await create_job(db, "apply.measure.v1", payload, req_id)
    await job_runner.enqueue(row["job_id"], req_id)
    return {"ok": True, "repair_txn_id": repair_txn_id, "apply_job_id": str(row["job_id"])}


@app.get("/v1/events")
async def events(job_id: str | None = Query(default=None)):
    key = job_id or "all"
    queue = await event_bus.subscribe(key)

    async def generator():
        try:
            async for message in stream_sse(queue):
                yield message
        finally:
            await event_bus.unsubscribe(key, queue)

    return StreamingResponse(generator(), media_type="text/event-stream")


@app.get("/v1/search/chunks", response_model=SearchResponse)
async def search_chunks_route(
    q: str = Query(min_length=1),
    book_id: str = Query(min_length=1),
    top_k: int = Query(default=20, ge=1, le=100),
    hybrid: bool = Query(default=False),
    vector_weight: float = Query(default=0.7, ge=0.0, le=1.0),
    keyword_weight: float = Query(default=0.3, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    items = await hybrid_search(db, q, book_id, top_k, hybrid, vector_weight, keyword_weight)
    return SearchResponse(query=q, items=items)


@app.get("/v1/search")
async def unified_search_route(
    q: str = Query(default="", min_length=0),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> dict:
    items = await unified_search(db, q, limit)
    return {"q": q, "limit": limit, "items": items}


@app.post("/v1/skill_runs", response_model=SkillRunCreateResponse)
async def create_skill_run_route(body: SkillRunCreateRequest, db: AsyncSession = Depends(get_db)) -> SkillRunCreateResponse:
    row = await create_skill_run(db, str(body.book_id), body.skill_name, body.schema_ver, body.output)
    return SkillRunCreateResponse(**row)


@app.get("/v1/books/{book_id}/asset_snapshots")
async def list_asset_snapshots_route(
    book_id: UUID,
    limit: int = Query(default=30, ge=1, le=200),
    include_outline_versions: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
) -> dict:
    bid = str(book_id)
    await _ensure_asset_snapshot_tables(db)
    rows = await db.execute(
        text(
            """
            SELECT s.snapshot_id::text AS snapshot_id, s.book_id::text AS book_id, s.snapshot_name, s.reason, s.tag,
                   s.summary, s.created_by, s.created_at,
                   COALESCE(i.item_count, 0)::int AS item_count
            FROM asset_snapshot s
            LEFT JOIN (
              SELECT snapshot_id, COUNT(*)::int AS item_count
              FROM asset_snapshot_item
              GROUP BY snapshot_id
            ) i ON i.snapshot_id=s.snapshot_id
            WHERE s.book_id=CAST(:book_id AS uuid)
            ORDER BY s.created_at DESC
            LIMIT :limit
            """
        ),
        {"book_id": bid, "limit": limit},
    )
    items = [dict(r) for r in rows.mappings().all()]
    try:
        current_state = await _collect_book_asset_state(db, book_id=bid, include_chapter_outlines=include_outline_versions)
    except RuntimeError as exc:
        if str(exc) == "BOOK_NOT_FOUND":
            raise HTTPException(status_code=404, detail="BOOK_NOT_FOUND") from exc
        raise
    return {
        "book_id": bid,
        "items": items,
        "current_state": current_state.get("summary") if isinstance(current_state.get("summary"), dict) else {},
        "prompt_pack": _asset_optimize_prompt_pack(),
    }


@app.post("/v1/books/{book_id}/asset_snapshots/capture")
async def capture_asset_snapshot_route(book_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    bid = str(book_id)
    snapshot_name = str((body or {}).get("snapshot_name") or "").strip()
    reason = str((body or {}).get("reason") or "").strip()
    tag = str((body or {}).get("tag") or "manual").strip() or "manual"
    include_chapter_outlines = bool((body or {}).get("include_chapter_outlines", True))
    if not snapshot_name:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        snapshot_name = f"资产快照 {now_str}"
    try:
        out = await _capture_asset_snapshot(
            db,
            book_id=bid,
            snapshot_name=snapshot_name,
            reason=reason,
            tag=tag,
            include_chapter_outlines=include_chapter_outlines,
        )
        return {"ok": True, "book_id": bid, **out}
    except RuntimeError as exc:
        await db.rollback()
        code = str(exc)
        if code == "BOOK_NOT_FOUND":
            raise HTTPException(status_code=404, detail=code) from exc
        raise HTTPException(status_code=400, detail=code) from exc


@app.get("/v1/books/{book_id}/asset_snapshots/{snapshot_id}")
async def get_asset_snapshot_detail_route(book_id: UUID, snapshot_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    bid = str(book_id)
    sid = str(snapshot_id)
    await _ensure_asset_snapshot_tables(db)
    head = await db.execute(
        text(
            """
            SELECT snapshot_id::text AS snapshot_id, book_id::text AS book_id, snapshot_name, reason, tag, summary, created_by, created_at
            FROM asset_snapshot
            WHERE book_id=CAST(:book_id AS uuid)
              AND snapshot_id=CAST(:snapshot_id AS uuid)
            LIMIT 1
            """
        ),
        {"book_id": bid, "snapshot_id": sid},
    )
    snapshot = head.mappings().first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="ASSET_SNAPSHOT_NOT_FOUND")
    item_rows = await db.execute(
        text(
            """
            SELECT item_id::text AS item_id, asset_type, asset_key, ref_id::text AS ref_id, version, payload, created_at
            FROM asset_snapshot_item
            WHERE snapshot_id=CAST(:snapshot_id AS uuid)
            ORDER BY asset_type ASC, asset_key ASC, created_at ASC
            """
        ),
        {"snapshot_id": sid},
    )
    items = [dict(r) for r in item_rows.mappings().all()]
    by_type: dict[str, int] = {}
    for item in items:
        key = str(item.get("asset_type") or "unknown")
        by_type[key] = int(by_type.get(key) or 0) + 1
    return {
        "book_id": bid,
        "snapshot": dict(snapshot),
        "items": items,
        "item_count": len(items),
        "type_counts": by_type,
    }


@app.post("/v1/books/{book_id}/asset_snapshots/{snapshot_id}/rollback")
async def rollback_asset_snapshot_route(book_id: UUID, snapshot_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    bid = str(book_id)
    sid = str(snapshot_id)
    note = str((body or {}).get("note") or "").strip()
    restore_chapter_outlines = bool((body or {}).get("restore_chapter_outlines", False))
    try:
        out = await _rollback_asset_snapshot(
            db,
            book_id=bid,
            snapshot_id=sid,
            note=note,
            restore_chapter_outlines=restore_chapter_outlines,
        )
        return {"ok": True, "book_id": bid, "snapshot_id": sid, **out}
    except RuntimeError as exc:
        await db.rollback()
        code = str(exc)
        if code == "ASSET_SNAPSHOT_NOT_FOUND":
            raise HTTPException(status_code=404, detail=code) from exc
        raise HTTPException(status_code=400, detail=code) from exc


@app.get("/v1/materials", response_model=MaterialCardListResponse)
async def list_materials_route(
    book_id: UUID | None = Query(default=None),
    tag: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> MaterialCardListResponse:
    rows = await list_material_cards(
        db,
        book_id=str(book_id) if book_id else None,
        tag=tag,
        q=q,
        limit=limit,
        offset=offset,
    )
    return MaterialCardListResponse(items=[MaterialCardItem(**row) for row in rows])


@app.post("/v1/materials", response_model=MaterialCardItem)
async def create_material_route(body: MaterialCardCreateRequest, db: AsyncSession = Depends(get_db)) -> MaterialCardItem:
    row = await create_material_card(
        db,
        book_id=str(body.book_id) if body.book_id else None,
        source_type=body.source_type,
        title=body.title,
        content=body.content,
        tag=body.tag,
        importance=body.importance,
    )
    return MaterialCardItem(**row)


@app.get("/v1/materials/{card_id}", response_model=MaterialCardItem)
async def get_material_route(card_id: UUID, db: AsyncSession = Depends(get_db)) -> MaterialCardItem:
    row = await get_material_card(db, str(card_id))
    if not row:
        raise HTTPException(status_code=404, detail="MATERIAL_NOT_FOUND")
    return MaterialCardItem(**row)


@app.delete("/v1/materials/{card_id}")
async def delete_material_route(card_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    ok = await delete_material_card(db, str(card_id))
    if not ok:
        raise HTTPException(status_code=404, detail="MATERIAL_NOT_FOUND")
    return {"ok": True}


@app.post("/v1/materials/{card_id}/embed")
async def embed_material_route(card_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    row = await get_material_card(db, str(card_id))
    if not row:
        raise HTTPException(status_code=404, detail="MATERIAL_NOT_FOUND")
    client = OllamaClient(settings.ollama_host)
    vecs = await client.embeddings(
        model=settings.embedding_model,
        texts=[row.get("content") or ""],
        timeout_s=60,
        retries=1,
        meta={"job_type": "MATERIAL", "stage": "EMBED"},
    )
    if not vecs:
        raise HTTPException(status_code=500, detail="EMBED_FAILED")
    saved = await upsert_material_embedding(db, card_id=str(card_id), embedding=vecs[0], model=settings.embedding_model)
    return {"ok": True, **saved}


@app.post("/v1/materials/knn", response_model=MaterialCardListResponse)
async def material_knn_route(body: MaterialKnnRequest, db: AsyncSession = Depends(get_db)) -> MaterialCardListResponse:
    client = OllamaClient(settings.ollama_host)
    try:
        vecs = await client.embeddings(
            model=settings.embedding_model,
            texts=[body.query_text],
            timeout_s=45,
            retries=1,
            meta={"job_type": "MATERIAL", "stage": "KNN_QUERY_EMBED"},
        )
        qvec = vecs[0] if vecs else None
    except Exception:
        qvec = None

    rows: list[dict]
    if qvec:
        rows = await search_material_knn(
            db,
            query_embedding=qvec,
            k=body.k,
            book_id=str(body.book_id) if body.book_id else None,
            tag=body.tag,
        )
    else:
        rows = await list_material_cards(
            db,
            book_id=str(body.book_id) if body.book_id else None,
            tag=body.tag,
            q=body.query_text,
            limit=body.k,
            offset=0,
        )
        for r in rows:
            r["score"] = 0.0

    return MaterialCardListResponse(items=[MaterialCardItem(**row) for row in rows])


@app.post("/v1/materials/import_from_chunks")
async def import_materials_from_chunks_route(
    body: MaterialImportFromChunksRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    card_ids = await import_material_cards_from_chunks(
        db,
        book_id=str(body.book_id),
        source_id=str(body.source_id) if body.source_id else None,
        tag=body.tag,
        limit=body.limit,
        source_type=body.source_type,
        importance=body.importance,
    )
    created = len(card_ids)
    embedded = 0
    failed = 0

    if body.auto_embed and card_ids:
        rows = await db.execute(
            text(
                """
                SELECT card_id, content
                FROM material_card
                WHERE card_id = ANY(CAST(:card_ids AS uuid[]))
                ORDER BY created_at ASC
                """
            ),
            {"card_ids": card_ids},
        )
        records = [dict(r) for r in rows.mappings().all()]
        if records:
            client = OllamaClient(settings.ollama_host)
            batch_size = 16
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]
                texts = [(it.get("content") or "") for it in batch]
                ids = [str(it["card_id"]) for it in batch]
                try:
                    vecs = await client.embeddings(
                        model=settings.embedding_model,
                        texts=texts,
                        timeout_s=120,
                        retries=1,
                        meta={"job_type": "MATERIAL", "stage": "IMPORT_EMBED"},
                    )
                    if len(vecs) != len(ids):
                        failed += len(ids)
                        continue
                    for cid, vec in zip(ids, vecs):
                        await upsert_material_embedding(db, card_id=cid, embedding=vec, model=settings.embedding_model)
                        embedded += 1
                except Exception:
                    failed += len(ids)

    return {"ok": True, "created": created, "embedded": embedded, "failed": failed}


@app.post("/v1/books/{book_id}/materials/import_from_splitbook/{splitbook_id}")
async def import_materials_from_splitbook_route(
    book_id: UUID,
    splitbook_id: UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> dict:
    splitbook = await get_splitbook(db, str(splitbook_id))
    if not splitbook:
        raise HTTPException(status_code=404, detail="SPLITBOOK_NOT_FOUND")

    limit = max(1, min(1200, int((body or {}).get("limit") or 300)))
    importance = max(1, min(5, int((body or {}).get("importance") or 3)))
    auto_embed = bool((body or {}).get("auto_embed", True))
    tag_base = str((body or {}).get("tag") or "splitbook_structure").strip() or "splitbook_structure"

    ins = await db.execute(
        text(
            """
            INSERT INTO material_card(book_id, source_type, title, content, tag, importance)
            SELECT
              CAST(:book_id AS uuid),
              'splitbook_fact',
              CONCAT('拆书#', COALESCE(f.chapter_no, 0), ' ', LEFT(COALESCE(f.chapter_title, ''), 40), ' [', COALESCE(f.fact_type, 'fact'), ']'),
              LEFT(COALESCE(f.statement, ''), 2000),
              CONCAT(:tag_base, ':', COALESCE(f.fact_type, 'fact')),
              :importance
            FROM splitbook_fact f
            WHERE f.splitbook_id=CAST(:splitbook_id AS uuid)
              AND COALESCE(f.statement, '') <> ''
            ORDER BY COALESCE(f.chapter_no, 999999), f.created_at DESC
            LIMIT :limit
            RETURNING card_id::text AS card_id
            """
        ),
        {
            "book_id": str(book_id),
            "splitbook_id": str(splitbook_id),
            "tag_base": tag_base,
            "importance": importance,
            "limit": limit,
        },
    )
    card_ids = [str(r.get("card_id") or "") for r in ins.mappings().all() if str(r.get("card_id") or "").strip()]
    await db.commit()

    created = len(card_ids)
    embedded = 0
    failed = 0
    if auto_embed and card_ids:
        rows = await db.execute(
            text(
                """
                SELECT card_id::text AS card_id, content
                FROM material_card
                WHERE card_id = ANY(CAST(:card_ids AS uuid[]))
                ORDER BY created_at ASC
                """
            ),
            {"card_ids": card_ids},
        )
        records = [dict(r) for r in rows.mappings().all()]
        if records:
            client = OllamaClient(settings.ollama_host)
            batch_size = 16
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]
                texts = [str(it.get("content") or "") for it in batch]
                ids = [str(it.get("card_id") or "") for it in batch if str(it.get("card_id") or "").strip()]
                if not ids:
                    continue
                try:
                    vecs = await client.embeddings(
                        model=settings.embedding_model,
                        texts=texts,
                        timeout_s=120,
                        retries=1,
                        meta={"job_type": "MATERIAL", "stage": "SPLITBOOK_IMPORT_EMBED"},
                    )
                    if len(vecs) != len(ids):
                        failed += len(ids)
                        continue
                    for cid, vec in zip(ids, vecs):
                        await upsert_material_embedding(db, card_id=cid, embedding=vec, model=settings.embedding_model)
                        embedded += 1
                except Exception:
                    failed += len(ids)

    return {
        "ok": True,
        "book_id": str(book_id),
        "splitbook_id": str(splitbook_id),
        "splitbook_name": str(splitbook.get("name") or ""),
        "created": created,
        "embedded": embedded,
        "failed": failed,
    }


@app.get("/v1/chapters/{chapter_id}/ref_inbox")
async def list_ref_inbox_route(
    chapter_id: UUID,
    status: str | None = Query(default="new"),
    limit: int = Query(default=100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = await list_ref_inbox_items(db, chapter_id=str(chapter_id), status=status, limit=limit)
    return {"chapter_id": str(chapter_id), "items": rows}


@app.post("/v1/chapters/{chapter_id}/ref_inbox/from_material")
async def create_ref_inbox_from_material_route(
    chapter_id: UUID,
    body: RefInboxFromMaterialRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    card = await get_material_card(db, str(body.card_id))
    if not card:
        raise HTTPException(status_code=404, detail="MATERIAL_NOT_FOUND")

    client = OllamaClient(settings.ollama_host)
    material_payload = {
        "card_id": str(card.get("card_id")),
        "title": card.get("title"),
        "tag": card.get("tag"),
        "content": str(card.get("content") or "")[:1200],
    }
    user_prompt = build_material_extract_user_prompt(material=material_payload, context=body.context or {})
    try:
        raw = await client.chat_json(
            model=DEFAULT_LLM_MODEL,
            user=user_prompt,
            system=STRICT_JSON_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=1200,
            timeout_s=120,
            retries=1,
            schema_hint='{"schema_name":"MATERIAL_EXTRACT_POINTS","schema_ver":1,"result":{"card_id":"UUID","extracted_points":[{"kind":"fact","point":"STRING","rewrite_hint":"STRING"}],"risk_flags":[{"code":"COPY_RISK","severity":"low","detail":"STRING"}]},"warnings":[]}',
            validate=None,
            meta={"job_type": "MATERIAL", "stage": "EXTRACT_POINTS", "card_id": str(body.card_id)},
        )
        checked, _ = validate_material_extract_output(raw if isinstance(raw, dict) else {})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"MATERIAL_EXTRACT_FAILED:{exc}") from exc

    ref_block = _build_material_ref_block(card, checked)
    created = await create_ref_inbox_item(
        db,
        chapter_id=str(chapter_id),
        source_type="material",
        source_id=str(body.card_id),
        title=str(card.get("title") or "material"),
        tag=card.get("tag"),
        ref_block=ref_block,
        extracted_points=((checked.get("result") or {}).get("extracted_points") or []),
    )
    return {"ok": True, **created}


@app.post("/v1/ref_inbox/{ref_id}/status")
async def set_ref_inbox_status_route(
    ref_id: UUID,
    body: RefInboxStatusRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await set_ref_inbox_status(db, ref_id=str(ref_id), status=body.status)
    if not row:
        raise HTTPException(status_code=404, detail="REF_NOT_FOUND")
    return {"ok": True, **row}


@app.get("/v1/templates")
async def list_templates_asset_route(
    type: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = await list_template_assets(db, asset_type=type, tag=tag, q=q, limit=limit, offset=offset)
    return {"items": rows}


@app.get("/v1/templates/assets/{asset_id}")
async def get_template_asset_route(asset_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    row = await get_template_asset(db, str(asset_id))
    if not row:
        raise HTTPException(status_code=404, detail="TEMPLATE_ASSET_NOT_FOUND")
    return row


@app.delete("/v1/templates/assets/{asset_id}")
async def delete_template_asset_route(asset_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    row = await delete_template_asset(db, str(asset_id))
    if not row:
        raise HTTPException(status_code=404, detail="TEMPLATE_ASSET_NOT_FOUND")
    return {"ok": True, "deleted": row}


@app.post("/v1/chapters/{chapter_id}/ref_inbox/from_template")
async def create_ref_inbox_from_template_route(
    chapter_id: UUID,
    body: RefInboxFromTemplateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    asset = await get_template_asset(db, str(body.asset_id))
    if not asset:
        raise HTTPException(status_code=404, detail="TEMPLATE_ASSET_NOT_FOUND")
    ref_block = _build_template_ref_block(asset, body.note)
    created = await create_ref_inbox_item(
        db,
        chapter_id=str(chapter_id),
        source_type="template",
        source_id=str(body.asset_id),
        title=str(asset.get("name") or "template"),
        tag=str(asset.get("asset_type") or "template"),
        ref_block=ref_block,
        extracted_points=[],
    )
    return {"ok": True, **created}


@app.post("/v1/chapters/{chapter_id}/draft/commit", response_model=SubmitJobResponse, status_code=202)
async def draft_commit_route(
    chapter_id: UUID,
    body: DraftCommitRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SubmitJobResponse:
    req_id = request_id(request)
    row_book = await db.execute(text("SELECT book_id FROM chapter WHERE chapter_id=:chapter_id"), {"chapter_id": str(chapter_id)})
    book_id = row_book.scalar()
    if not book_id:
        raise HTTPException(status_code=404, detail="CHAPTER_NOT_FOUND")
    profile_id_used: str | None = None
    profile_version_used: int | None = None
    rprof = await db.execute(
        text(
            """
            SELECT b.profile_id, p.active_version
            FROM book b
            LEFT JOIN profile p ON p.profile_id=b.profile_id
            WHERE b.book_id=:book_id
            """
        ),
        {"book_id": str(book_id)},
    )
    pmap = rprof.mappings().first()
    if pmap and pmap.get("profile_id"):
        profile_id_used = str(pmap.get("profile_id"))
        profile_version_used = int(pmap.get("active_version") or 1)
    payload = {
        "book_id": str(book_id),
        "chapter_id": str(chapter_id),
        "commit_txn_id": str(uuid4()),
        "text_ver_id": str(body.text_ver_id) if body.text_ver_id else None,
        "text_content": body.text_content,
        "outline_version": body.outline_version,
        "writeback": body.writeback.model_dump(),
        "profile_id_used": profile_id_used,
        "profile_version_used": profile_version_used,
    }
    _attach_trigger_meta(
        payload,
        trigger_source=body.trigger_source,
        trigger_entry=body.trigger_entry,
        trigger_mode=body.trigger_mode,
    )
    row = await create_job(db, "draft.commit.v1", payload, req_id)
    await job_runner.enqueue(row["job_id"], req_id)
    return SubmitJobResponse(job_id=row["job_id"], status="queued", queued_at=row["created_at"], request_id=req_id)


@app.post("/v1/books/{book_id}/ledger/apply", response_model=LedgerApplyResponse)
async def ledger_apply_route(book_id: UUID, body: LedgerApplyRequest, db: AsyncSession = Depends(get_db)) -> LedgerApplyResponse:
    try:
        result = await apply_from_skill_run(str(book_id), str(body.skill_run_id), body.apply_policy, db)
        return LedgerApplyResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/v1/profiles/{profile_id}/templates", response_model=TemplateItem)
async def create_template_route(profile_id: UUID, body: TemplateCreateRequest, db: AsyncSession = Depends(get_db)) -> TemplateItem:
    row = await create_template(
        db,
        str(profile_id),
        body.name,
        body.level,
        body.tags,
        body.schema_ver,
        body.graph,
        body.meta,
    )
    if body.source_book_id or body.source_chunk_ids or body.source_note:
        await add_template_source(
            db,
            str(row["template_id"]),
            str(body.source_book_id) if body.source_book_id else None,
            [str(x) for x in body.source_chunk_ids],
            body.source_note,
        )
    return TemplateItem(**row)


@app.get("/v1/profiles/{profile_id}/templates", response_model=TemplateListResponse)
async def list_templates_route(
    profile_id: UUID,
    level: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> TemplateListResponse:
    rows = await list_templates(db, str(profile_id), level, tag)
    return TemplateListResponse(items=[TemplateItem(**row) for row in rows])


@app.delete("/v1/templates/{template_id}")
async def delete_template_route(template_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    row = await delete_structure_template(db, str(template_id))
    if not row:
        raise HTTPException(status_code=404, detail="TEMPLATE_NOT_FOUND")
    return {"ok": True, "deleted": row}


@app.post("/v1/books/{book_id}/templates/recommend", response_model=TemplateListResponse)
async def recommend_templates_route(
    book_id: UUID, body: TemplateRecommendRequest, db: AsyncSession = Depends(get_db)
) -> TemplateListResponse:
    _ = book_id
    rows = await recommend_templates(db, str(body.profile_id), body.level, body.top_k)
    cleaned: list[dict] = []
    for row in rows:
        row.pop("usage_count", None)
        cleaned.append(row)
    return TemplateListResponse(items=[TemplateItem(**row) for row in cleaned])


@app.post("/v1/books/{book_id}/templates/generate_from_beats", response_model=SubmitJobResponse, status_code=202)
async def generate_template_from_beats_route(
    book_id: UUID,
    body: GenerateTemplateFromBeatsRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SubmitJobResponse:
    req_id = request_id(request)
    profile_row = await db.execute(text("SELECT profile_id FROM book WHERE book_id=:book_id"), {"book_id": str(book_id)})
    profile_id = profile_row.scalar()
    payload = {
        "book_id": str(book_id),
        "profile_id": str(profile_id) if profile_id else None,
        "skill_run_id": str(body.skill_run_id),
        "level": body.level,
        "name": body.name,
        "tags": body.tags,
    }
    row = await create_job(db, "generate.structure_template.v1", payload, req_id)
    await job_runner.enqueue(row["job_id"], req_id)
    return SubmitJobResponse(job_id=row["job_id"], status="queued", queued_at=row["created_at"], request_id=req_id)


@app.post("/v1/books/{book_id}/tension/analyze", response_model=SubmitJobResponse, status_code=202)
async def analyze_book_tension_route(
    book_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SubmitJobResponse:
    req_id = request_id(request)
    row = await create_job(db, "book.tension.analyze.v1", {"book_id": str(book_id)}, req_id)
    await job_runner.enqueue(row["job_id"], req_id)
    return SubmitJobResponse(job_id=row["job_id"], status="queued", queued_at=row["created_at"], request_id=req_id)


@app.get("/v1/books/{book_id}/tension/report")
async def get_book_tension_report_route(
    book_id: UUID,
    latest: int = Query(default=1),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _ = latest
    try:
        return await get_latest_book_tension_report(db, str(book_id))
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/v1/books/{book_id}/tension/repair_plan")
async def create_repair_plan_route(
    book_id: UUID,
    body: BookTensionRepairPlanRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    req_id = request_id(request)
    raw_actions = list(body.actions_override)
    for row in body.actions_override_by_chapter:
        ch_no = int(row.get("chapter_no") or 0)
        for act in (row.get("actions") or []):
            raw_actions.append({"chapter_no": ch_no, "action": str(act)})

    if not raw_actions:
        report = await get_latest_book_tension_report(db, str(book_id))
        out = report.get("output") or {}
        diagnosis = (((out.get("result") or {}).get("diagnosis")) or [])
        for d in diagnosis:
            for a in (d.get("suggest_actions") or []):
                raw_actions.append(a)
    merged = merge_actions(raw_actions)

    chapter_map_res = await db.execute(
        text('SELECT chapter_id, "order" FROM chapter WHERE book_id=:book_id ORDER BY "order" ASC'),
        {"book_id": str(book_id)},
    )
    chapter_map = {int(r["order"]): str(r["chapter_id"]) for r in chapter_map_res.mappings().all()}

    ch_from = body.chapter_from
    ch_to = body.chapter_to

    created: list[dict[str, str | int]] = []
    for item in merged:
        ch_no = int(item.get("chapter_no", 0))
        actions = [str(a) for a in (item.get("actions") or []) if str(a).strip()]
        if ch_no <= 0 or not actions:
            continue
        if ch_from is not None and ch_to is not None and not (ch_from <= ch_no <= ch_to):
            continue
        chapter_id = chapter_map.get(ch_no)
        if not chapter_id:
            continue
        payload = {
            "book_id": str(book_id),
            "chapter_id": chapter_id,
            "targets": body.targets.model_dump(),
            "style": body.style.model_dump(),
            "schema_ver": 1,
            "actions_override": actions,
        }
        row = await create_job(db, "control_plan.tension.v1", payload, req_id)
        created.append({"chapter_no": ch_no, "job_id": str(row["job_id"])})
        await job_runner.enqueue(row["job_id"], req_id)

    return {"ok": True, "jobs_created": len(created), "created_jobs": created}


@app.get("/v1/books/{book_id}/arc_targets", response_model=ArcTargetListResponse)
async def list_arc_targets_route(book_id: UUID, db: AsyncSession = Depends(get_db)) -> ArcTargetListResponse:
    rows = await list_arc_targets(db, str(book_id))
    return ArcTargetListResponse(items=[ArcTargetItem(**row) for row in rows])


@app.post("/v1/books/{book_id}/arc_targets", response_model=ArcTargetItem)
async def upsert_arc_target_route(
    book_id: UUID,
    body: ArcTargetUpsertRequest,
    db: AsyncSession = Depends(get_db),
) -> ArcTargetItem:
    row = await upsert_arc_target(
        db,
        book_id=str(book_id),
        arc_id=body.arc_id,
        target_shape=body.target_shape,
        target_points=[float(x) for x in body.target_points],
        weights=body.weights.model_dump(),
    )
    return ArcTargetItem(**row)


@app.post("/v1/templates/evolve", response_model=SubmitJobResponse, status_code=202)
async def evolve_templates_route(
    body: TemplateEvolveRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SubmitJobResponse:
    req_id = request_id(request)
    payload = body.model_dump()
    row = await create_job(db, "template.evolve.v1", payload, req_id)
    await job_runner.enqueue(row["job_id"], req_id)
    return SubmitJobResponse(job_id=row["job_id"], status="queued", queued_at=row["created_at"], request_id=req_id)


@app.get("/v1/templates/variants", response_model=TemplateVariantListResponse)
async def list_template_variants_route(
    enabled: str = Query(default="all"),
    base_template_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> TemplateVariantListResponse:
    rows = await list_template_variants(db, enabled=enabled, base_template_id=base_template_id)
    return TemplateVariantListResponse(items=[TemplateVariantItem(**row) for row in rows])


@app.get("/v1/templates/variants/{variant_id}", response_model=TemplateVariantItem)
async def get_template_variant_route(variant_id: UUID, db: AsyncSession = Depends(get_db)) -> TemplateVariantItem:
    row = await get_template_variant(db, str(variant_id))
    if not row:
        raise HTTPException(status_code=404, detail="VARIANT_NOT_FOUND")
    return TemplateVariantItem(**row)


@app.post("/v1/templates/variants/{variant_id}/enable", response_model=TemplateVariantItem)
async def enable_template_variant_route(
    variant_id: UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> TemplateVariantItem:
    enabled = bool(body.get("enabled", True))
    weight = body.get("weight")
    try:
        row = await set_template_variant_enabled(
            db,
            variant_id=str(variant_id),
            enabled=enabled,
            weight=float(weight) if weight is not None else None,
        )
        return TemplateVariantItem(**row)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/v1/templates/variants/{variant_id}/disable", response_model=TemplateVariantItem)
async def disable_template_variant_route(variant_id: UUID, db: AsyncSession = Depends(get_db)) -> TemplateVariantItem:
    try:
        row = await set_template_variant_enabled(db, variant_id=str(variant_id), enabled=False)
        return TemplateVariantItem(**row)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/v1/templates/effect_samples")
async def create_repair_effect_sample_route(
    body: RepairEffectSampleCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await create_repair_effect_sample(
        db,
        book_id=str(body.book_id),
        arc_id=body.arc_id,
        chapter_no=body.chapter_no,
        before_eval_run_id=str(body.before_eval_run_id),
        after_eval_run_id=str(body.after_eval_run_id),
        applied_mechanics=body.applied_mechanics,
        delta=body.delta,
        context=body.context,
    )
    return {"ok": True, "sample": row}


@app.post("/v1/reports/chapter_revision")
async def chapter_revision_report_route(
    body: ChapterRevisionReportRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await create_chapter_revision_report(
            db,
            book_id=str(body.book_id),
            chapter_id=str(body.chapter_id),
            from_version=body.from_version,
            to_version=body.to_version,
            before_eval_run_id=str(body.before_eval_run_id),
            after_eval_run_id=str(body.after_eval_run_id),
            include_similarity_guard=body.include_similarity_guard,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/v1/chapters/{chapter_id}/report/latest")
async def chapter_latest_report_route(
    chapter_id: UUID,
    report_type: str = Query(default="draft_commit"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await db.execute(
        text(
            """
            SELECT report_id, book_id, chapter_id, profile_id_used, profile_version_used, report_type, payload, created_at
            FROM report
            WHERE chapter_id=:chapter_id
              AND (:report_type='' OR report_type=:report_type)
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"chapter_id": str(chapter_id), "report_type": (report_type or "").strip()},
    )
    r = row.mappings().first()
    if not r:
        raise HTTPException(status_code=404, detail="REPORT_NOT_FOUND")
    payload = r.get("payload") or {}
    return {
        "report_id": str(r["report_id"]),
        "book_id": str(r["book_id"]),
        "chapter_id": str(r["chapter_id"]),
        "report_type": str(r["report_type"]),
        "profile_id_used": str(r["profile_id_used"]) if r.get("profile_id_used") else (payload.get("profile_id_used")),
        "profile_version_used": int(r["profile_version_used"]) if r.get("profile_version_used") is not None else payload.get("profile_version_used"),
        "text_ver_id": payload.get("text_ver_id"),
        "payload": payload,
        "created_at": r.get("created_at"),
    }


def _apply_profile_text_stub(source_text: str, profile_row: dict | None) -> str:
    txt = (source_text or "").strip()
    if not txt:
        txt = "本章内容待生成。"
    if not profile_row:
        return txt
    name = str(profile_row.get("name") or "")
    features = profile_row.get("features") if isinstance(profile_row.get("features"), dict) else {}
    avg_len = str(features.get("avg_sentence_len") or "mix")
    dialogue_ratio = features.get("dialogue_ratio")
    style_head = f"【风格:{name or 'default'}|句长:{avg_len}|对话比:{dialogue_ratio if dialogue_ratio is not None else '-'}】"
    if not txt.startswith("【风格:"):
        txt = style_head + "\n" + txt
    return txt


def _simple_style_metrics(text_value: str) -> dict:
    txt = str(text_value or "").strip()
    if not txt:
        return {
            "sentence_avg_len": 0,
            "short_sentence_ratio": 0,
            "dialog_ratio": 0,
            "paragraph_avg_sentences": 0,
            "rhythm_rules": [],
            "taboos": [],
        }
    sents = [s for s in re.split(r"[。！？!?]", txt) if s.strip()]
    sent_lens = [len(s.strip()) for s in sents if s.strip()]
    avg_len = round((sum(sent_lens) / len(sent_lens)) if sent_lens else 0, 2)
    short_ratio = 0.0
    if sent_lens:
        short_ratio = round(sum(1 for x in sent_lens if x <= 12) / len(sent_lens), 3)
    dialog_chars = len(re.findall(r"[“”\"「」『』]", txt))
    dialog_ratio = round(min(1.0, (dialog_chars / max(1, len(txt))) * 8.0), 3)
    paras = [p for p in txt.splitlines() if p.strip()]
    paragraph_avg_sentences = round((len(sents) / len(paras)) if paras else 0, 2)
    return {
        "sentence_avg_len": avg_len,
        "short_sentence_ratio": short_ratio,
        "dialog_ratio": dialog_ratio,
        "paragraph_avg_sentences": paragraph_avg_sentences,
        "rhythm_rules": ["每2-3段推进一次冲突或信息变化", "段末尽量留下一处未完全解释的信息差"],
        "taboos": ["避免连续空泛总结句", "避免重复同构句式超过3次"],
    }


def _try_parse_json_text(v: object) -> dict:
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        s = v.strip()
        if s.startswith("{") and s.endswith("}"):
            try:
                out = json.loads(s)
                if isinstance(out, dict):
                    return out
            except Exception:
                return {}
    return {}


def _sha1_hex(text_value: str) -> str:
    return hashlib.sha1(str(text_value or "").encode("utf-8")).hexdigest()


def _norm_fp_text(v: object, max_len: int = 800) -> str:
    s = str(v or "").lower()
    out_chars: list[str] = []
    for ch in s:
        if ch.isalnum() or ("\u4e00" <= ch <= "\u9fff"):
            out_chars.append(ch)
    return "".join(out_chars)[:max_len]


def _tag_token(v: object, max_len: int = 40) -> str:
    s = _norm_fp_text(v, max_len=max_len)
    return s.replace(" ", "_")


def _split_tone_tags(tone: str) -> list[str]:
    s = str(tone or "").strip()
    if not s:
        return []
    raw = re.split(r"[+,，、/\s]+", s)
    out: list[str] = []
    for x in raw:
        t = _tag_token(x, 24)
        if t:
            out.append(f"tone:{t}")
    return out[:4]


def _canonical_intent(intent: dict | None) -> dict:
    src = intent if isinstance(intent, dict) else {}
    pacing = str(src.get("pacing") or "").strip().lower()
    if pacing in {"fast", "fast_paced"}:
        pacing = "fast"
    elif pacing in {"slow", "slow_burn"}:
        pacing = "slow"
    else:
        pacing = "mid"
    conflict = str(src.get("conflict") or "").strip().lower()
    conflict = "high" if conflict in {"high", "high_conflict"} else "low"
    focus = str(src.get("focus") or "").strip().lower()
    if focus not in {"dialog", "action", "introspection"}:
        focus = "action"
    end = str(src.get("end") or "").strip().lower()
    end = "cliffhanger" if end in {"cliffhanger", "cliffhanger_end"} else "soft"
    goals_raw = src.get("goal") if isinstance(src.get("goal"), list) else []
    goals: list[str] = []
    for g in goals_raw:
        gg = re.sub(r"[^a-zA-Z0-9_]+", "", str(g or "").strip().lower())[:32]
        if gg:
            goals.append(gg)
    goals = list(dict.fromkeys(goals))[:6]
    return {
        "pacing": pacing,
        "conflict": conflict,
        "focus": focus,
        "end": end,
        "goal": goals,
    }


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _compute_structure(progress: float) -> dict:
    p = max(0.0, min(1.0, float(progress)))
    conflict = math.pow(max(0.0, math.sin(math.pi * p)), 1.5)
    reveal = _sigmoid((p - 0.4) * 8.0)
    tension = math.pow(p, 1.2)
    growth = math.pow(p, 1.5)
    closure = max(0.0, (p - 0.85) / 0.15)
    return {
        "progress": round(p, 6),
        "conflict": round(conflict, 6),
        "reveal": round(reveal, 6),
        "tension": round(tension, 6),
        "growth": round(growth, 6),
        "closure": round(closure, 6),
    }


def _phase_from_progress(progress: float) -> str:
    p = max(0.0, min(1.0, float(progress)))
    if p < 0.25:
        return "setup"
    if p < 0.75:
        return "midgame"
    if p < 0.9:
        return "climax"
    return "closure"


def _curve_bucket(v: float) -> str:
    x = float(v)
    if x >= 0.67:
        return "high"
    if x >= 0.34:
        return "mid"
    return "low"


def _clamp_int(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(n)))


def _apply_structure_modifiers(
    *,
    intent: dict,
    structure: dict,
    hooks_n: int,
    beats_n: int,
    styles_n: int,
    templates_n: int,
) -> tuple[dict, dict]:
    i2 = _canonical_intent(intent)
    goals = list(i2.get("goal") or [])
    conflict = float(structure.get("conflict") or 0.0)
    reveal = float(structure.get("reveal") or 0.0)
    tension = float(structure.get("tension") or 0.0)
    growth = float(structure.get("growth") or 0.0)
    closure = float(structure.get("closure") or 0.0)

    if reveal > 0.6 and "info_reveal" not in goals:
        goals.append("info_reveal")
    if growth > 0.6 and "character_growth" not in goals:
        goals.append("character_growth")
    if tension > 0.7:
        i2["end"] = "cliffhanger"
    if closure > 0.5:
        i2["end"] = "soft"
    i2["goal"] = goals[:6]

    hook_mult = 1.0 + conflict * 0.8
    beat_mult = 1.0 + conflict * 1.2
    hooks_eff = hooks_n
    beats_eff = beats_n
    styles_eff = styles_n
    templates_eff = templates_n
    if closure > 0.5:
        hooks_eff = max(0, int(round(hooks_n * 0.6)))
        styles_eff = styles_n + 1
        templates_eff = max(0, int(round(templates_n * 0.8)))
    hooks_eff = int(round(hooks_eff * hook_mult))
    beats_eff = int(round(beats_eff * beat_mult))

    mod = {
        "hook_mult": round(hook_mult, 4),
        "beat_mult": round(beat_mult, 4),
        "inject_hooks_n": _clamp_int(hooks_eff, 0, 6),
        "inject_beats_n": _clamp_int(beats_eff, 0, 8),
        "inject_styles_n": _clamp_int(styles_eff, 0, 3),
        "inject_templates_n": _clamp_int(templates_eff, 0, 3),
    }
    return i2, mod


def _apply_volume_plan_shaping(
    *,
    structure: dict,
    p_vol: float,
    plan_items: list[dict],
    shaping_cfg: dict | None = None,
) -> tuple[dict, dict]:
    base = {
        "progress": float(structure.get("progress") or 0.0),
        "conflict": float(structure.get("conflict") or 0.0),
        "reveal": float(structure.get("reveal") or 0.0),
        "tension": float(structure.get("tension") or 0.0),
        "growth": float(structure.get("growth") or 0.0),
        "closure": float(structure.get("closure") or 0.0),
    }
    cfg = shaping_cfg if isinstance(shaping_cfg, dict) else {}
    max_total_boost = float(cfg.get("max_total_boost") or 0.35)
    sigma_scale = float(cfg.get("sigma_scale") or 0.7)
    a_by_kind = cfg.get("A_by_kind") if isinstance(cfg.get("A_by_kind"), dict) else {}
    default_amp = {
        "growth": {"conflict": 0.22, "tension": 0.18, "growth": 0.15},
        "foreshadow_payoff": {"reveal": 0.18, "tension": 0.12},
        "cliffhanger": {"tension": 0.20},
        "foreshadow_seed": {"tension": 0.06},
        "reveal": {"reveal": 0.12, "tension": 0.05},
    }
    inc = {"conflict": 0.0, "reveal": 0.0, "tension": 0.0, "growth": 0.0, "closure": 0.0}
    bumps: list[dict] = []
    for item in plan_items:
        if not bool(item.get("must_happen", True)):
            continue
        kind = str(item.get("kind") or "").strip().lower()
        pmin = _clamp01(float(item.get("target_p_vol_min") or 0.0))
        pmax = _clamp01(float(item.get("target_p_vol_max") or 1.0))
        if pmax < pmin:
            pmin, pmax = pmax, pmin
        mu = (pmin + pmax) * 0.5
        sigma = max(0.04, (pmax - pmin) * 0.5 * max(0.2, sigma_scale))
        weight = math.exp(-((float(p_vol) - mu) ** 2) / (2.0 * (sigma**2)))
        if weight <= 0.0005:
            continue
        amp = a_by_kind.get(kind) if isinstance(a_by_kind.get(kind), dict) else default_amp.get(kind, {})
        if not isinstance(amp, dict) or not amp:
            continue
        delta = {}
        for dim in ("conflict", "reveal", "tension", "growth", "closure"):
            a = float(amp.get(dim) or 0.0)
            if a <= 0:
                continue
            d = a * weight
            inc[dim] += d
            delta[dim] = round(d, 6)
        if delta:
            bumps.append(
                {
                    "item_id": str(item.get("item_id") or ""),
                    "kind": kind,
                    "window": str(item.get("target_window") or ""),
                    "mu": round(mu, 6),
                    "sigma": round(sigma, 6),
                    "weight": round(weight, 6),
                    "delta": delta,
                }
            )
    peak_boost = max(inc.values()) if inc else 0.0
    scale = 1.0
    if peak_boost > max_total_boost > 0:
        scale = max_total_boost / peak_boost
        for dim in inc:
            inc[dim] = inc[dim] * scale
        for b in bumps:
            d0 = b.get("delta") if isinstance(b.get("delta"), dict) else {}
            b["delta"] = {k: round(float(v) * scale, 6) for k, v in d0.items()}
    shaped = {
        "progress": round(base["progress"], 6),
        "conflict": round(_clamp01(base["conflict"] + inc["conflict"]), 6),
        "reveal": round(_clamp01(base["reveal"] + inc["reveal"]), 6),
        "tension": round(_clamp01(base["tension"] + inc["tension"]), 6),
        "growth": round(_clamp01(base["growth"] + inc["growth"]), 6),
        "closure": round(_clamp01(base["closure"] + inc["closure"]), 6),
    }
    trace = {
        "p_vol": round(_clamp01(p_vol), 6),
        "applied": len(bumps),
        "scale": round(scale, 6),
        "max_total_boost": round(max_total_boost, 6),
        "boost": {k: round(float(v), 6) for k, v in inc.items()},
        "bumps": bumps[:24],
    }
    return shaped, trace


def _suggest_intent_from_effective(effective: dict, chapter_no: int | None = None) -> tuple[dict, float, list[str]]:
    eval_cfg = effective.get("eval") if isinstance(effective.get("eval"), dict) else {}
    targets = eval_cfg.get("targets") if isinstance(eval_cfg.get("targets"), dict) else {}
    draft_cfg = effective.get("draft") if isinstance(effective.get("draft"), dict) else {}
    pacing_score = float(targets.get("pacing") or 0.7)
    conflict_score = float(targets.get("conflict") or 0.7)
    hook_score = float(targets.get("hook") or 0.7)
    foreshadow_score = float(targets.get("foreshadow") or 0.0)
    stakes_score = float(targets.get("stakes") or 0.0)
    tone = str(draft_cfg.get("tone") or "").lower()
    focus = "action"
    if any(x in tone for x in ["对话", "dialog"]):
        focus = "dialog"
    elif any(x in tone for x in ["克制", "内心", "introspection"]):
        focus = "introspection"
    pacing = "mid"
    if pacing_score >= 0.72:
        pacing = "fast"
    elif pacing_score <= 0.56:
        pacing = "slow"
    conflict = "high" if conflict_score >= 0.68 else "low"
    ending = "cliffhanger" if hook_score >= 0.72 else "soft"
    goals: list[str] = []
    if stakes_score >= 0.7:
        goals.append("character_growth")
    if foreshadow_score >= 0.62:
        goals.append("mystery_build")
    goals.append("info_reveal")
    if chapter_no == 1:
        goals.append("worldbuilding")
    intent = _canonical_intent(
        {
            "pacing": pacing,
            "conflict": conflict,
            "focus": focus,
            "end": ending,
            "goal": goals,
        }
    )
    confidence = 0.72
    rationale = [
        f"pacing target={pacing_score:.2f}",
        f"conflict target={conflict_score:.2f}",
        f"hook target={hook_score:.2f}",
    ]
    return intent, confidence, rationale


async def _load_tag_dictionary(session: AsyncSession) -> tuple[set[str], dict[str, str]]:
    enabled: set[str] = set()
    alias_map: dict[str, str] = {}
    try:
        rows = await session.execute(
            text(
                """
                SELECT tag
                FROM tag_dictionary
                WHERE is_enabled=true
                """
            )
        )
        for r in rows.fetchall():
            t = str(r[0] or "").strip().lower()
            if t:
                enabled.add(t)
        alias_rows = await session.execute(text("SELECT from_tag, to_tag FROM tag_alias"))
        for rr in alias_rows.fetchall():
            fk = str(rr[0] or "").strip().lower()
            tv = str(rr[1] or "").strip().lower()
            if fk and tv:
                alias_map[fk] = tv
    except Exception:
        enabled = {
            "draft", "rewrite", "scene_start", "scene_mid", "scene_end",
            "fast_paced", "mid_paced", "slow_burn",
            "high_conflict", "low_conflict",
            "dialog_heavy", "action_heavy", "introspection_heavy",
            "cliffhanger_end", "soft_end",
            "character_growth", "relationship_shift", "worldbuilding", "info_reveal", "mystery_build",
            "eval_on", "simguard_on",
            "phase_setup", "phase_midgame", "phase_climax", "phase_closure",
            "conflict_low", "conflict_mid", "conflict_high",
            "reveal_low", "reveal_mid", "reveal_high",
            "tension_low", "tension_mid", "tension_high",
            "growth_low", "growth_mid", "growth_high",
            "closure_low", "closure_mid", "closure_high",
        }
        alias_map = {
            "fast": "fast_paced", "mid": "mid_paced", "slow": "slow_burn",
            "high": "high_conflict", "low": "low_conflict",
            "dialog": "dialog_heavy", "action": "action_heavy", "introspection": "introspection_heavy",
            "cliffhanger": "cliffhanger_end", "soft": "soft_end",
        }
    return enabled, alias_map


def _dict_pick_tag(tag: str, enabled: set[str], alias_map: dict[str, str]) -> str | None:
    t = str(tag or "").strip().lower()
    if not t:
        return None
    t = alias_map.get(t, t)
    return t if t in enabled else None


def _build_ctx_tags_for_batch(
    *,
    intent: dict,
    purpose: str,
    scene_pos: str | None,
    genre: str | None,
    runtime_flags: dict,
    structure: dict | None,
    phase: str | None,
    enabled_tags: set[str],
    alias_map: dict[str, str],
    do_eval: bool,
    do_simguard: bool,
) -> list[str]:
    tags: list[str] = []
    structure_obj = structure if isinstance(structure, dict) else {}
    for candidate in [
        genre or "",
        purpose,
        scene_pos or "",
        f"phase_{str(phase or '').strip().lower()}",
        f"{str((intent or {}).get('pacing') or '').strip().lower()}_paced",
        f"{str((intent or {}).get('conflict') or '').strip().lower()}_conflict",
        f"{str((intent or {}).get('focus') or '').strip().lower()}_heavy",
        "cliffhanger_end" if str((intent or {}).get("end") or "").strip().lower() == "cliffhanger" else "soft_end",
        f"conflict_{_curve_bucket(float(structure_obj.get('conflict') or 0.0))}",
        f"reveal_{_curve_bucket(float(structure_obj.get('reveal') or 0.0))}",
        f"tension_{_curve_bucket(float(structure_obj.get('tension') or 0.0))}",
        f"growth_{_curve_bucket(float(structure_obj.get('growth') or 0.0))}",
        f"closure_{_curve_bucket(float(structure_obj.get('closure') or 0.0))}",
    ]:
        t = _dict_pick_tag(candidate, enabled_tags, alias_map)
        if t:
            tags.append(t)
    for g in ((intent or {}).get("goal") if isinstance((intent or {}).get("goal"), list) else []):
        t = _dict_pick_tag(str(g), enabled_tags, alias_map)
        if t:
            tags.append(t)
    if do_eval:
        t = _dict_pick_tag("eval_on", enabled_tags, alias_map)
        if t:
            tags.append(t)
    if do_simguard:
        t = _dict_pick_tag("simguard_on", enabled_tags, alias_map)
        if t:
            tags.append(t)
    if bool(runtime_flags.get("include_baseline")):
        t = _dict_pick_tag("rewrite" if purpose == "rewrite" else "draft", enabled_tags, alias_map)
        if t:
            tags.append(t)
    uniq = []
    seen = set()
    for t in tags:
        tt = str(t).strip().lower()
        if tt and tt not in seen:
            seen.add(tt)
            uniq.append(tt[:48])
    return sorted(uniq)[:12]


async def _find_volume_for_chapter(db: AsyncSession, *, book_id: str, chapter_no: int | None) -> dict | None:
    if chapter_no is None:
        return None
    row = await db.execute(
        text(
            """
            SELECT volume_id::text AS volume_id, volume_no, title, start_chapter_no, end_chapter_no
            FROM volume
            WHERE book_id=CAST(:book_id AS uuid)
              AND start_chapter_no <= :chapter_no
              AND end_chapter_no >= :chapter_no
            ORDER BY volume_no
            LIMIT 1
            """
        ),
        {"book_id": book_id, "chapter_no": int(chapter_no)},
    )
    r = row.mappings().first()
    return dict(r) if r else None


def _build_foreshadow_task_block(seed_items: list[dict], reinforce_items: list[dict], payoff_items: list[dict]) -> str:
    if not seed_items and not reinforce_items and not payoff_items:
        return ""
    lines: list[str] = []
    lines.append("[FORESHADOW_TASK]")
    if seed_items:
        lines.append("- Seed:")
        for item in seed_items[:2]:
            lines.append(f"  - Title: {str(item.get('title') or '')}")
            lines.append(f"    ReaderQuestion: {str(item.get('question') or '')}")
            lines.append("    HowToPlant: 使用一个异常细节埋下疑问，不要解释清楚。")
    if reinforce_items:
        lines.append("- Reinforce:")
        for item in reinforce_items[:2]:
            lines.append(f"  - Title: {str(item.get('title') or '')}")
            lines.append("    HowToReinforce: 用模糊反应/证据缺口强化疑问。")
    if payoff_items:
        lines.append("- Payoff:")
        for item in payoff_items[:2]:
            lines.append(f"  - Title: {str(item.get('title') or '')}")
            lines.append(f"    ExpectedPayoff: {str(item.get('expected_payoff') or '')}")
            lines.append("    HowToPayoff: 回收前文问题，并给出代价/反转。")
    lines.append("Rules:")
    lines.append("- Do NOT copy phrases; use structural rewrite only.")
    lines.append("- Do NOT fully resolve unless marked Payoff.")
    lines.append("[/FORESHADOW_TASK]")
    payoff_tasks: list[dict] = []
    for item in payoff_items[:2]:
        tpl = item.get("payoff_template") if isinstance(item.get("payoff_template"), dict) else {}
        if not tpl:
            continue
        payoff_tasks.append(
            {
                "title": str(item.get("title") or ""),
                "foreshadow_type": str(item.get("type") or ""),
                "template_type": str(tpl.get("type") or ""),
                "structure_pattern": str(tpl.get("structure_pattern") or ""),
                "rewrite_instruction": str(tpl.get("rewrite_instruction") or ""),
                "intensity": int(tpl.get("intensity_level") or 2),
            }
        )
    if payoff_tasks:
        lines.append("[PAYOFF_TASK]")
        for pt in payoff_tasks:
            lines.append(f"Foreshadow: {pt['title']}")
            lines.append(f"ForeshadowType: {pt['foreshadow_type']}")
            lines.append(f"Payoff Style: {pt['template_type']}")
            lines.append(f"Intensity: {pt['intensity']}")
            lines.append(f"Structure Rule: {pt['structure_pattern']}")
            lines.append(f"Rewrite Rule: {pt['rewrite_instruction']}")
        lines.append("[/PAYOFF_TASK]")
    return "\n".join(lines)


def _compute_payoff_intensity(structure: dict | None) -> int:
    s = structure if isinstance(structure, dict) else {}
    conflict = float(s.get("conflict") or 0.0)
    closure = float(s.get("closure") or 0.0)
    intensity = int(round(1.0 + conflict * 1.5 + closure * 1.0))
    return max(1, min(3, intensity))


async def _pick_payoff_template(
    db: AsyncSession,
    *,
    foreshadow_type: str,
    preferred_type: str | None,
    intensity: int,
) -> dict | None:
    ptype = str(preferred_type or "").strip().lower()
    ftype = str(foreshadow_type or "").strip().lower()
    query = text(
        """
        SELECT template_id::text AS template_id, type, applicable_foreshadow_type, structure_pattern, rewrite_instruction, intensity_level, risk_score, meta
        FROM payoff_template
        WHERE
          (:ptype = '' OR type=:ptype)
          AND (
            COALESCE(array_length(applicable_foreshadow_type, 1), 0)=0
            OR :ftype = ANY(applicable_foreshadow_type)
          )
        ORDER BY ABS(intensity_level - :intensity) ASC, created_at DESC
        LIMIT 1
        """
    )
    params = {"ptype": ptype, "ftype": ftype, "intensity": int(max(1, min(3, intensity)))}
    row = await db.execute(query, params)
    r = row.mappings().first()
    if not r and ptype:
        # fallback: ignore preferred type, keep foreshadow compatibility + intensity
        row2 = await db.execute(query, {**params, "ptype": ""})
        r = row2.mappings().first()
    return dict(r) if r else None


def _build_growth_task_block(growth_task: dict | None) -> str:
    g = growth_task if isinstance(growth_task, dict) else {}
    m = g.get("milestone") if isinstance(g.get("milestone"), dict) else {}
    action = str(g.get("action") or "none")
    if action == "none" or not m:
        return ""
    req = g.get("requirements") if isinstance(g.get("requirements"), dict) else {}
    lines = ["[GROWTH_TASK]"]
    lines.append(f"Character: {str(m.get('character_name') or '主角')}")
    lines.append(f"Milestone: {str(m.get('title') or '')}")
    lines.append(f"Stage: {str(m.get('stage') or '')}")
    lines.append(f"Action: {action}")
    lines.append(f"Trigger: {str(m.get('trigger') or '')}")
    lines.append(f"Cost: {str(m.get('cost') or '')}")
    lines.append(f"Choice: {str(m.get('choice_text') or '')}")
    lines.append(f"NewBelief: {str(m.get('new_belief') or '')}")
    lines.append("Rules:")
    if bool(req.get("cost_must_show")):
        lines.append("- Must show cost on-screen.")
    if bool(req.get("choice_must_be_explicit")):
        lines.append("- Must make choice explicit via dialogue/action.")
    lines.append("[/GROWTH_TASK]")
    return "\n".join(lines)


async def _select_growth_task(
    db: AsyncSession,
    *,
    book_id: str,
    chapter_no: int | None,
    volume_id: str | None,
    structure: dict | None,
    p_vol: float | None = None,
    plan_items: list[dict] | None = None,
) -> dict:
    s = structure if isinstance(structure, dict) else {}
    conflict = float(s.get("conflict") or 0.0)
    tension = float(s.get("tension") or 0.0)
    closure = float(s.get("closure") or 0.0)
    is_breakthrough_window = conflict > 0.65 and tension > 0.65
    is_payoff_window = closure > 0.55
    now_no = int(chapter_no or 0)
    res = await db.execute(
        text(
            """
            SELECT
              milestone_id::text AS milestone_id,
              book_id::text AS book_id,
              character_name,
              milestone_no,
              title,
              stage,
              priority,
              planned_scope,
              planned_chapter_no,
              planned_volume_id::text AS planned_volume_id,
              trigger,
              cost,
              choice_text,
              new_belief,
              bind_foreshadow_ids,
              payoff_template_type,
              status,
              meta
            FROM growth_milestone
            WHERE book_id=CAST(:book_id AS uuid)
              AND status IN ('planned','seeded','in_progress')
            ORDER BY
              CASE WHEN status='in_progress' THEN 0 ELSE 1 END,
              priority DESC,
              COALESCE(planned_chapter_no, 999999) ASC,
              milestone_no ASC
            LIMIT 40
            """
        ),
        {"book_id": book_id},
    )
    rows = [dict(r) for r in res.mappings().all()]
    preferred_ids: set[str] = set()
    pv = _clamp01(float(p_vol)) if p_vol is not None else None
    if pv is not None and isinstance(plan_items, list):
        for it in plan_items:
            if str(it.get("kind") or "").strip().lower() != "growth":
                continue
            rid = str(it.get("ref_id") or "").strip()
            if not rid:
                continue
            pmin = _clamp01(float(it.get("target_p_vol_min") or 0.0))
            pmax = _clamp01(float(it.get("target_p_vol_max") or 1.0))
            if pmin <= pv <= pmax:
                preferred_ids.add(rid)

    if preferred_ids:
        rows = sorted(rows, key=lambda x: (0 if str(x.get("milestone_id") or "") in preferred_ids else 1, -int(x.get("priority") or 0), int(x.get("planned_chapter_no") or 999999)))

    selected: dict | None = None
    for r in rows:
        planned_no = int(r.get("planned_chapter_no") or 0)
        planned_vol = str(r.get("planned_volume_id") or "")
        if planned_vol and volume_id and planned_vol != volume_id:
            continue
        if planned_no and now_no and abs(planned_no - now_no) > 4:
            continue
        selected = r
        break
    if not selected and rows:
        selected = rows[0]
    if not selected:
        return {"action": "none", "milestone": None, "requirements": {"cost_must_show": False, "choice_must_be_explicit": False}, "why": "no milestone"}
    if isinstance(selected.get("bind_foreshadow_ids"), list):
        selected["bind_foreshadow_ids"] = [str(x) for x in selected.get("bind_foreshadow_ids") if str(x).strip()]
    if selected.get("planned_volume_id") is not None:
        selected["planned_volume_id"] = str(selected.get("planned_volume_id"))
    if selected.get("milestone_id") is not None:
        selected["milestone_id"] = str(selected.get("milestone_id"))

    stage = str(selected.get("stage") or "pressure").strip().lower()
    cur_window = None
    if pv is not None:
        if pv < 0.18:
            cur_window = "vol_setup"
        elif pv < 0.65:
            cur_window = "vol_build"
        elif pv < 0.90:
            cur_window = "vol_spike"
        else:
            cur_window = "vol_release"
    action = "advance"
    if stage == "breakthrough" and (is_breakthrough_window or is_payoff_window or cur_window == "vol_spike"):
        action = "achieve"
    elif stage in {"integration", "reflect"} and cur_window == "vol_release":
        action = "reflect"
    elif stage == "pressure" and cur_window == "vol_setup":
        action = "advance"
    elif stage == "cost" and cur_window == "vol_build":
        action = "advance"
    elif stage in {"pressure", "cost"} and (conflict > 0.5 or tension > 0.5):
        action = "advance"
    elif closure > 0.75:
        action = "reflect"
    else:
        action = "seed"
    return {
        "action": action,
        "milestone": selected,
        "requirements": {
            "cost_must_show": stage in {"cost", "breakthrough"},
            "choice_must_be_explicit": stage in {"pressure", "cost", "breakthrough"},
        },
        "why": f"conflict={round(conflict,3)} tension={round(tension,3)} closure={round(closure,3)}",
    }


async def _select_foreshadow_tasks(
    db: AsyncSession,
    *,
    book_id: str,
    chapter_no: int | None,
    volume_id: str | None,
    structure: dict | None = None,
    growth_task: dict | None = None,
) -> dict:
    rows = await db.execute(
        text(
            """
            SELECT foreshadow_id::text AS foreshadow_id, title, type, scope, priority, status, question, expected_payoff, tags
            FROM foreshadow
            WHERE book_id=CAST(:book_id AS uuid)
              AND status IN ('seeded','reinforced','payoff_planned')
            ORDER BY priority DESC, updated_at ASC
            LIMIT 30
            """
        ),
        {"book_id": book_id},
    )
    items = [dict(r) for r in rows.mappings().all()]
    seeds = [x for x in items if str(x.get("status") or "") == "seeded"]
    reinforces = [x for x in items if str(x.get("status") or "") in {"seeded", "reinforced"}]
    payoffs = [x for x in items if str(x.get("status") or "") == "payoff_planned"]
    p_vol = 0.5
    if chapter_no is not None:
        if volume_id:
            vrow = await db.execute(
                text(
                    """
                    SELECT start_chapter_no, end_chapter_no
                    FROM volume
                    WHERE volume_id=CAST(:volume_id AS uuid)
                    """
                ),
                {"volume_id": volume_id},
            )
            vv = vrow.mappings().first()
            if vv:
                start_no = int(vv.get("start_chapter_no") or chapter_no)
                end_no = int(vv.get("end_chapter_no") or chapter_no)
                denom = max(1, end_no - start_no)
                p_vol = max(0.0, min(1.0, float(chapter_no - start_no) / float(denom)))
    pick_seed: list[dict] = []
    pick_reinforce: list[dict] = []
    pick_payoff: list[dict] = []
    growth_obj = growth_task if isinstance(growth_task, dict) else {}
    g_m = growth_obj.get("milestone") if isinstance(growth_obj.get("milestone"), dict) else {}
    g_action = str(growth_obj.get("action") or "none")
    bind_ids = [str(x) for x in (g_m.get("bind_foreshadow_ids") if isinstance(g_m.get("bind_foreshadow_ids"), list) else []) if str(x).strip()]
    preferred_payoff_type = str(g_m.get("payoff_template_type") or "").strip().lower()
    if bind_ids:
        idset = set(bind_ids)
        reinforces = sorted(reinforces, key=lambda x: (0 if str(x.get("foreshadow_id") or "") in idset else 1, -int(x.get("priority") or 0)))
        payoffs = sorted(payoffs, key=lambda x: (0 if str(x.get("foreshadow_id") or "") in idset else 1, -int(x.get("priority") or 0)))
        seeds = sorted(seeds, key=lambda x: (0 if str(x.get("foreshadow_id") or "") in idset else 1, -int(x.get("priority") or 0)))

    if g_action == "achieve":
        pick_payoff = payoffs[:1] if payoffs else [x for x in reinforces[:1]]
        pick_reinforce = [x for x in reinforces if x not in pick_payoff][:1]
        pick_seed = []
    elif p_vol < 0.2:
        pick_seed = seeds[:1]
        pick_reinforce = [x for x in reinforces if x not in pick_seed][:1]
    elif p_vol <= 0.8:
        pick_reinforce = reinforces[:2]
    else:
        pick_payoff = payoffs[:1]
        pick_reinforce = [x for x in reinforces if x not in pick_payoff][:1]
    intensity = _compute_payoff_intensity(structure)
    for x in pick_payoff:
        x["payoff_template"] = await _pick_payoff_template(
            db,
            foreshadow_type=str(x.get("type") or ""),
            preferred_type=preferred_payoff_type or None,
            intensity=intensity,
        )
    selected = list(dict.fromkeys([*(x.get("foreshadow_id") for x in pick_seed), *(x.get("foreshadow_id") for x in pick_reinforce), *(x.get("foreshadow_id") for x in pick_payoff)]))
    block = _build_foreshadow_task_block(pick_seed, pick_reinforce, pick_payoff)
    return {
        "volume_progress": round(p_vol, 6),
        "payoff_intensity": intensity,
        "seed": pick_seed,
        "reinforce": pick_reinforce,
        "payoff": pick_payoff,
        "selected_ids": [str(x) for x in selected if str(x)],
        "block": block,
    }


def _window_from_p_vol(p_vol: float | None) -> str:
    p = _clamp01(float(p_vol)) if p_vol is not None else 0.0
    if p < 0.18:
        return "vol_setup"
    if p < 0.65:
        return "vol_build"
    if p < 0.90:
        return "vol_spike"
    return "vol_release"


def _combo_task_type(step: dict) -> str:
    kind = str((step or {}).get("kind") or "").strip().lower()
    if kind == "foreshadow_payoff":
        return "payoff"
    if kind == "foreshadow_seed":
        return "seed"
    if kind == "cliffhanger":
        return "cliff"
    if kind == "growth":
        stage = str((step or {}).get("stage") or "").strip().lower()
        if stage == "breakthrough":
            return "breakthrough"
        if stage in {"integration", "reflect"}:
            return "integration"
        return "growth_pressure"
    if kind == "reveal":
        return "reveal"
    if kind == "cost":
        return "cost"
    if kind == "hook":
        return "hook"
    if kind == "goal":
        return "goal"
    if kind == "obstacle":
        return "obstacle"
    if kind == "new_lead":
        return "new_lead"
    return kind or "combo_step"


def _task_weight(task_type: str, intensity: int) -> int:
    t = str(task_type or "").strip().lower()
    i = max(1, min(3, int(intensity or 1)))
    if t == "breakthrough":
        return 3
    if t == "payoff":
        return 2 if i >= 2 else 1
    if t in {"growth_pressure", "cost", "seed", "cliff", "hook", "reveal", "integration", "reinforce"}:
        return 1
    return 1


def _task_curve_alignment(task_type: str, structure: dict | None) -> float:
    s = structure if isinstance(structure, dict) else {}
    conflict = _clamp01(float(s.get("conflict") or 0.0))
    reveal = _clamp01(float(s.get("reveal") or 0.0))
    tension = _clamp01(float(s.get("tension") or 0.0))
    growth = _clamp01(float(s.get("growth") or 0.0))
    closure = _clamp01(float(s.get("closure") or 0.0))
    t = str(task_type or "").strip().lower()
    if t == "breakthrough":
        return _clamp01(0.45 * conflict + 0.35 * tension + 0.2 * growth)
    if t == "payoff":
        return _clamp01(0.4 * reveal + 0.35 * closure + 0.25 * tension)
    if t == "cliff":
        return _clamp01(0.55 * tension + 0.45 * closure)
    if t == "seed":
        return _clamp01(0.5 * (1.0 - closure) + 0.5 * (1.0 - reveal))
    if t in {"growth_pressure", "cost"}:
        return _clamp01(0.5 * conflict + 0.3 * tension + 0.2 * growth)
    if t == "reveal":
        return reveal
    if t == "hook":
        return _clamp01(0.5 * tension + 0.5 * (1.0 - closure))
    return _clamp01(0.3 * conflict + 0.3 * reveal + 0.4 * tension)


DEFAULT_READER_STATE = {
    "expectation": 0.6,
    "tension": 0.4,
    "clarity": 0.7,
    "satisfaction": 0.3,
    "fatigue": 0.1,
}


def _normalize_reader_state(state: dict | None) -> dict:
    s = state if isinstance(state, dict) else {}
    out = {}
    for k, dv in DEFAULT_READER_STATE.items():
        out[k] = _clamp01(float(s.get(k) if s.get(k) is not None else dv))
    return out


async def _load_latest_reader_state(db: AsyncSession, *, book_id: str) -> dict:
    row = await db.execute(
        text(
            """
            SELECT payload
            FROM report
            WHERE book_id=CAST(:book_id AS uuid)
              AND report_type='ab_batch_item'
              AND COALESCE(payload->>'variant','')='exp'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"book_id": book_id},
    )
    r = row.mappings().first()
    if not r:
        return dict(DEFAULT_READER_STATE)
    payload = r.get("payload") if isinstance(r.get("payload"), dict) else {}
    rs = payload.get("reader_state") if isinstance(payload.get("reader_state"), dict) else {}
    return _normalize_reader_state(rs)


async def _load_recent_replay_stats(db: AsyncSession, *, book_id: str, limit: int = 5) -> dict:
    lim = max(1, min(20, int(limit)))
    row = await db.execute(
        text(
            """
            WITH last_trace AS (
              SELECT ct.payload
              FROM chapter_trace ct
              JOIN chapter c ON c.chapter_id = ct.chapter_id
              WHERE c.book_id = CAST(:book_id AS uuid)
              ORDER BY ct.created_at DESC
              LIMIT :limit
            ),
            reason_rows AS (
              SELECT COALESCE((x->>'reason'), '') AS reason
              FROM last_trace lt
              LEFT JOIN LATERAL jsonb_array_elements(COALESCE(lt.payload->'dropped_tasks', '[]'::jsonb)) AS x ON true
            )
            SELECT
              COALESCE(AVG(COALESCE((lt.payload #>> '{orchestrator_explain,replay_filtered_count}')::numeric, 0)), 0) AS avg_replay_filtered,
              COALESCE(SUM(CASE WHEN rr.reason = 'replay_filtered:max_defer_rounds_reached' THEN 1 ELSE 0 END), 0) AS max_round_hits,
              COALESCE(SUM(CASE WHEN rr.reason = 'replay_filtered:expired_window' THEN 1 ELSE 0 END), 0) AS expired_hits
            FROM last_trace lt
            LEFT JOIN reason_rows rr ON true
            """
        ),
        {"book_id": book_id, "limit": lim},
    )
    r = row.mappings().first() or {}
    return {
        "sample_size": lim,
        "avg_replay_filtered": round(float(r.get("avg_replay_filtered") or 0.0), 6),
        "max_round_hits": int(r.get("max_round_hits") or 0),
        "expired_hits": int(r.get("expired_hits") or 0),
    }


def _reader_alerts(reader_state: dict | None, thresholds: dict | None) -> list[dict]:
    r = _normalize_reader_state(reader_state)
    thr = thresholds if isinstance(thresholds, dict) else _reader_thresholds({})
    alerts: list[dict] = []
    if float(r.get("fatigue") or 0.0) > float(thr.get("fatigue_warn") or 0.65):
        alerts.append(
            {
                "code": "FATIGUE_HIGH",
                "severity": "warn",
                "detail": f"fatigue={round(float(r.get('fatigue') or 0.0), 4)}",
            }
        )
    if float(r.get("tension") or 0.0) > float(thr.get("tension_overload") or 0.85):
        alerts.append(
            {
                "code": "TENSION_OVERLOAD",
                "severity": "warn",
                "detail": f"tension={round(float(r.get('tension') or 0.0), 4)}",
            }
        )
    if float(r.get("clarity") or 0.0) < float(thr.get("clarity_low") or 0.35):
        alerts.append(
            {
                "code": "CLARITY_LOW",
                "severity": "warn",
                "detail": f"clarity={round(float(r.get('clarity') or 0.0), 4)}",
            }
        )
    if float(r.get("expectation") or 0.0) < float(thr.get("expectation_low") or 0.4):
        alerts.append(
            {
                "code": "EXPECTATION_LOW",
                "severity": "info",
                "detail": f"expectation={round(float(r.get('expectation') or 0.0), 4)}",
            }
        )
    if float(r.get("satisfaction") or 0.0) > float(thr.get("satisfaction_high") or 0.8):
        alerts.append(
            {
                "code": "SATISFACTION_HIGH",
                "severity": "info",
                "detail": f"satisfaction={round(float(r.get('satisfaction') or 0.0), 4)}",
            }
        )
    return alerts


def _reader_thresholds(effective_settings: dict | None) -> dict:
    eff = effective_settings if isinstance(effective_settings, dict) else {}
    reader_cfg = eff.get("reader") if isinstance(eff.get("reader"), dict) else {}
    thr = reader_cfg.get("thresholds") if isinstance(reader_cfg.get("thresholds"), dict) else {}
    return {
        "fatigue_warn": _clamp01(float(thr.get("fatigue_warn") if thr.get("fatigue_warn") is not None else 0.65)),
        "tension_overload": _clamp01(float(thr.get("tension_overload") if thr.get("tension_overload") is not None else 0.85)),
        "clarity_low": _clamp01(float(thr.get("clarity_low") if thr.get("clarity_low") is not None else 0.35)),
        "expectation_low": _clamp01(float(thr.get("expectation_low") if thr.get("expectation_low") is not None else 0.4)),
        "satisfaction_high": _clamp01(float(thr.get("satisfaction_high") if thr.get("satisfaction_high") is not None else 0.8)),
    }


def _merge_dict(base: dict, override: dict) -> dict:
    out = json.loads(json.dumps(base if isinstance(base, dict) else {}))
    ov = override if isinstance(override, dict) else {}
    for k, v in ov.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge_dict(out.get(k) or {}, v)
        else:
            out[k] = v
    return out


def _replay_tuning_thresholds(effective_settings: dict | None) -> dict:
    eff = effective_settings if isinstance(effective_settings, dict) else {}
    orch = eff.get("orchestrator") if isinstance(eff.get("orchestrator"), dict) else {}
    replay = orch.get("replay") if isinstance(orch.get("replay"), dict) else {}
    tuning = replay.get("tuning") if isinstance(replay.get("tuning"), dict) else {}
    medium = max(0.1, min(10.0, float(tuning.get("avg_filtered_medium") if tuning.get("avg_filtered_medium") is not None else 1.5)))
    high = max(medium, min(12.0, float(tuning.get("avg_filtered_high") if tuning.get("avg_filtered_high") is not None else 3.0)))
    low = max(0.0, min(2.0, float(tuning.get("avg_filtered_low") if tuning.get("avg_filtered_low") is not None else 0.3)))
    return {
        "avg_filtered_medium": medium,
        "avg_filtered_high": high,
        "avg_filtered_low": low,
        "max_round_hits_red": max(1, min(30, int(tuning.get("max_round_hits_red") if tuning.get("max_round_hits_red") is not None else 3))),
        "expired_hits_red": max(1, min(30, int(tuning.get("expired_hits_red") if tuning.get("expired_hits_red") is not None else 4))),
    }


def _update_reader_state(
    *,
    prev: dict | None,
    structure: dict | None,
    structure_weight: int,
    cliff_present: bool,
    growth_action: str,
    payoff_intensity: int,
    unresolved_foreshadow_ratio: float,
    reveal_ratio: float,
    over_twist: float,
) -> dict:
    p = _normalize_reader_state(prev)
    s = structure if isinstance(structure, dict) else {}
    conflict = _clamp01(float(s.get("conflict") or 0.0))
    tension_curve = _clamp01(float(s.get("tension") or 0.0))
    sat_prev = _clamp01(float(p.get("satisfaction") or 0.0))
    cliff_v = 1.0 if cliff_present else 0.0
    payoff_v = _clamp01(float(payoff_intensity) / 3.0)
    growth_v = 1.0 if str(growth_action or "").strip().lower() == "achieve" else 0.0
    unresolved = _clamp01(float(unresolved_foreshadow_ratio or 0.0))
    reveal_v = _clamp01(float(reveal_ratio or 0.0))
    twist_v = _clamp01(float(over_twist or 0.0))
    sw = _clamp01(float(max(0, min(int(structure_weight), 8))) / 8.0)

    tension_next = _clamp01(0.6 * p["tension"] + 0.4 * conflict + 0.3 * cliff_v - 0.2 * sat_prev)
    expectation_next = _clamp01(0.5 * p["expectation"] + 0.4 * cliff_v + 0.3 * unresolved)
    satisfaction_next = _clamp01(0.4 * p["satisfaction"] + 0.5 * payoff_v + 0.3 * growth_v)
    clarity_next = _clamp01(0.6 * p["clarity"] + 0.4 * reveal_v - 0.2 * twist_v)
    fatigue_next = _clamp01(
        p["fatigue"] + 0.25 * sw + 0.2 * tension_curve - 0.3 * satisfaction_next - 0.2 * clarity_next
    )
    return {
        "expectation": round(expectation_next, 6),
        "tension": round(tension_next, 6),
        "clarity": round(clarity_next, 6),
        "satisfaction": round(satisfaction_next, 6),
        "fatigue": round(fatigue_next, 6),
    }


async def _ensure_agent_audit_table(db: AsyncSession) -> None:
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS agent_action_audit_log (
              audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
              chapter_id UUID NULL REFERENCES chapter(chapter_id) ON DELETE SET NULL,
              proposal_id TEXT NOT NULL DEFAULT '',
              action_type TEXT NOT NULL,
              action_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
              before_state JSONB NULL,
              after_state JSONB NULL,
              status TEXT NOT NULL DEFAULT 'applied',
              note TEXT NOT NULL DEFAULT '',
              rollback_of UUID NULL REFERENCES agent_action_audit_log(audit_id) ON DELETE SET NULL,
              rolled_back_at TIMESTAMPTZ NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    await db.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_agent_action_audit_book_time
            ON agent_action_audit_log(book_id, created_at DESC)
            """
        )
    )
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS book_state (
              book_id UUID PRIMARY KEY REFERENCES book(book_id) ON DELETE CASCADE,
              orchestrator_limits JSONB NOT NULL DEFAULT '{}'::jsonb,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS combo_injection (
              inj_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
              volume_id UUID NULL REFERENCES volume(volume_id) ON DELETE SET NULL,
              combo_type TEXT NOT NULL,
              window_next_chapters INT NOT NULL DEFAULT 2,
              priority INT NOT NULL DEFAULT 3,
              status TEXT NOT NULL DEFAULT 'pending',
              expires_after_chapter_no INT NULL,
              consumed_chapter_id UUID NULL REFERENCES chapter(chapter_id) ON DELETE SET NULL,
              consumed_at TIMESTAMPTZ NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    await db.execute(text("ALTER TABLE combo_injection ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending'"))
    await db.execute(text("ALTER TABLE combo_injection ADD COLUMN IF NOT EXISTS expires_after_chapter_no INT NULL"))
    await db.execute(text("ALTER TABLE combo_injection ADD COLUMN IF NOT EXISTS consumed_chapter_id UUID NULL"))
    await db.execute(text("ALTER TABLE combo_injection ADD COLUMN IF NOT EXISTS consumed_at TIMESTAMPTZ NULL"))
    await db.execute(text("CREATE INDEX IF NOT EXISTS idx_combo_injection_book_time ON combo_injection(book_id, created_at DESC)"))
    await db.execute(text("CREATE INDEX IF NOT EXISTS idx_combo_injection_book_status ON combo_injection(book_id, status, created_at DESC)"))
    await db.commit()


async def _replace_book_settings(db: AsyncSession, book_id: str, settings_value: dict) -> dict:
    normalized = settings_value if isinstance(settings_value, dict) else {}
    await db.execute(
        text(
            """
            INSERT INTO book_settings(book_id, settings, updated_at)
            VALUES (CAST(:book_id AS uuid), CAST(:settings AS jsonb), now())
            ON CONFLICT (book_id)
            DO UPDATE SET settings=EXCLUDED.settings, updated_at=now()
            """
        ),
        {"book_id": book_id, "settings": json.dumps(normalized, ensure_ascii=False)},
    )
    await db.commit()
    return normalized


async def _replace_chapter_settings(db: AsyncSession, chapter_id: str, settings_value: dict) -> dict:
    normalized = settings_value if isinstance(settings_value, dict) else {}
    await db.execute(
        text(
            """
            INSERT INTO chapter_settings(chapter_id, settings, updated_at)
            VALUES (CAST(:chapter_id AS uuid), CAST(:settings AS jsonb), now())
            ON CONFLICT (chapter_id)
            DO UPDATE SET settings=EXCLUDED.settings, updated_at=now()
            """
        ),
        {"chapter_id": chapter_id, "settings": json.dumps(normalized, ensure_ascii=False)},
    )
    await db.commit()
    return normalized


def _asset_optimize_prompt_pack() -> dict[str, str]:
    return {
        "review_and_plan": (
            "你是“写作资产架构师”，请只处理结构，不生成正文，不复述原文。\n\n"
            "任务：\n"
            "1. 读取资产：创作简报、总纲、卷纲版本、章纲版本、素材卡、模板资产、风格画像。\n"
            "2. 做一致性审查：目标冲突、设定冲突、节奏冲突、重复资产、失效资产。\n"
            "3. 输出“优化计划”：\n"
            "   - 保留项（原因）\n"
            "   - 合并项（A+B->C）\n"
            "   - 删除项（原因+风险）\n"
            "   - 新增项（补齐缺口）\n"
            "4. 输出“可执行变更清单（JSON）”，每条必须包含：\n"
            "   - asset_type\n"
            "   - action (keep/merge/delete/create/update)\n"
            "   - target_id\n"
            "   - patch\n"
            "   - reason\n"
            "   - risk_level\n"
            "5. 严格要求：\n"
            "   - 禁止输出原书原文\n"
            "   - 禁止改写剧情正文\n"
            "   - 只允许结构化建议"
        ),
        "rollback_safe_patch": (
            "请基于“优化计划JSON”生成“回滚安全版本”：\n"
            "- 每个变更都要附 before/after 摘要\n"
            "- 每个变更都要给 rollback_hint\n"
            "- 若风险为 high，标记 requires_manual_confirm=true"
        ),
    }


async def _ensure_asset_snapshot_tables(db: AsyncSession) -> None:
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS asset_snapshot (
              snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
              snapshot_name TEXT NOT NULL DEFAULT '',
              reason TEXT NOT NULL DEFAULT '',
              tag TEXT NOT NULL DEFAULT '',
              summary JSONB NOT NULL DEFAULT '{}'::jsonb,
              created_by TEXT NOT NULL DEFAULT 'desktop_user',
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    await db.execute(text("CREATE INDEX IF NOT EXISTS idx_asset_snapshot_book_time ON asset_snapshot(book_id, created_at DESC)"))
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS asset_snapshot_item (
              item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              snapshot_id UUID NOT NULL REFERENCES asset_snapshot(snapshot_id) ON DELETE CASCADE,
              asset_type TEXT NOT NULL,
              asset_key TEXT NOT NULL DEFAULT '',
              ref_id UUID NULL,
              version INTEGER NULL,
              payload JSONB NOT NULL DEFAULT '{}'::jsonb,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              UNIQUE(snapshot_id, asset_type, asset_key)
            )
            """
        )
    )
    await db.execute(
        text("CREATE INDEX IF NOT EXISTS idx_asset_snapshot_item_snapshot ON asset_snapshot_item(snapshot_id, asset_type, created_at DESC)")
    )


def _safe_uuid_or_none(raw: str | None) -> str | None:
    value = str(raw or "").strip()
    if not value:
        return None
    try:
        return str(UUID(value))
    except Exception:
        return None


async def _collect_book_asset_state(
    db: AsyncSession,
    *,
    book_id: str,
    include_chapter_outlines: bool = True,
) -> dict[str, Any]:
    book_row = await db.execute(
        text(
            """
            SELECT b.book_id::text AS book_id, b.title, b.profile_id::text AS profile_id, b.updated_at
            FROM book b
            WHERE b.book_id=CAST(:book_id AS uuid)
            LIMIT 1
            """
        ),
        {"book_id": book_id},
    )
    book = book_row.mappings().first()
    if not book:
        raise RuntimeError("BOOK_NOT_FOUND")

    settings_value = await get_book_settings(db, book_id) or {}
    master_outline = settings_value.get("writing_master_outline") if isinstance(settings_value.get("writing_master_outline"), dict) else {}

    chapter_count_row = await db.execute(
        text("SELECT COUNT(*)::int AS c FROM chapter WHERE book_id=CAST(:book_id AS uuid)"),
        {"book_id": book_id},
    )
    chapter_count = int(chapter_count_row.mappings().first().get("c") or 0)

    volume_count_row = await db.execute(
        text("SELECT COUNT(*)::int AS c FROM volume WHERE book_id=CAST(:book_id AS uuid)"),
        {"book_id": book_id},
    )
    volume_count = int(volume_count_row.mappings().first().get("c") or 0)

    material_count_row = await db.execute(
        text("SELECT COUNT(*)::int AS c FROM material_card WHERE book_id=CAST(:book_id AS uuid)"),
        {"book_id": book_id},
    )
    material_count = int(material_count_row.mappings().first().get("c") or 0)

    template_default_row = await db.execute(
        text(
            """
            SELECT COUNT(*)::int AS c
            FROM book_default_assets d
            JOIN asset_bundle_item i ON i.bundle_id=d.bundle_id
            WHERE d.book_id=CAST(:book_id AS uuid)
              AND i.item_type='template'
            """
        ),
        {"book_id": book_id},
    )
    template_default_count = int(template_default_row.mappings().first().get("c") or 0)

    template_used_row = await db.execute(
        text(
            """
            SELECT COUNT(DISTINCT x.tid)::int AS c
            FROM (
              SELECT unnest(injected_template_ids) AS tid
              FROM asset_usage_log
              WHERE book_id=CAST(:book_id AS uuid)
            ) x
            """
        ),
        {"book_id": book_id},
    )
    template_used_count = int(template_used_row.mappings().first().get("c") or 0)

    profile_row = await db.execute(
        text(
            """
            SELECT p.profile_id::text AS profile_id, p.name, p.active_version, p.updated_at
            FROM profile p
            JOIN book b ON b.profile_id=p.profile_id
            WHERE b.book_id=CAST(:book_id AS uuid)
            LIMIT 1
            """
        ),
        {"book_id": book_id},
    )
    profile_hit = profile_row.mappings().first()

    volume_plan_rows = await db.execute(
        text(
            """
            SELECT v.volume_id::text AS volume_id, v.volume_no, v.title,
                   p.vol_plan_id::text AS vol_plan_id, p.version, p.created_at
            FROM volume v
            LEFT JOIN volume_plan p
              ON p.volume_id=v.volume_id
             AND p.status='active'
            WHERE v.book_id=CAST(:book_id AS uuid)
            ORDER BY v.volume_no ASC
            """
        ),
        {"book_id": book_id},
    )
    active_volume_plans = [dict(r) for r in volume_plan_rows.mappings().all()]

    outline_rows: list[dict[str, Any]] = []
    if include_chapter_outlines:
        outline_res = await db.execute(
            text(
                """
                SELECT c.chapter_id::text AS chapter_id, c."order" AS chapter_no, c.title,
                       COALESCE(o.version, 0)::int AS outline_version
                FROM chapter c
                LEFT JOIN LATERAL (
                  SELECT version
                  FROM outline
                  WHERE chapter_id=c.chapter_id
                    AND scope='chapter'
                  ORDER BY version DESC
                  LIMIT 1
                ) o ON true
                WHERE c.book_id=CAST(:book_id AS uuid)
                ORDER BY c."order" ASC
                """
            ),
            {"book_id": book_id},
        )
        outline_rows = [dict(r) for r in outline_res.mappings().all()]

    style_row = await db.execute(
        text(
            """
            SELECT skill_run_id::text AS skill_run_id, output, created_at
            FROM skill_run
            WHERE book_id=CAST(:book_id AS uuid)
              AND skill_name='STYLE_EVOLVE_V1'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"book_id": book_id},
    )
    style_hit = style_row.mappings().first()

    items: list[dict[str, Any]] = [
        {
            "asset_type": "book_settings",
            "asset_key": "book_settings",
            "ref_id": None,
            "version": None,
            "payload": {"settings": settings_value},
        },
        {
            "asset_type": "master_outline",
            "asset_key": "writing_master_outline",
            "ref_id": None,
            "version": int(master_outline.get("version") or 0) if isinstance(master_outline, dict) else 0,
            "payload": {"master_outline": master_outline},
        },
    ]
    if profile_hit:
        items.append(
            {
                "asset_type": "profile",
                "asset_key": str(profile_hit.get("profile_id") or ""),
                "ref_id": str(profile_hit.get("profile_id") or ""),
                "version": int(profile_hit.get("active_version") or 1),
                "payload": {
                    "name": str(profile_hit.get("name") or ""),
                    "updated_at": str(profile_hit.get("updated_at") or ""),
                },
            }
        )
    for row in active_volume_plans:
        volume_id = str(row.get("volume_id") or "").strip()
        if not volume_id:
            continue
        items.append(
            {
                "asset_type": "volume_plan",
                "asset_key": volume_id,
                "ref_id": volume_id,
                "version": int(row.get("version") or 0),
                "payload": {
                    "volume_no": int(row.get("volume_no") or 0),
                    "volume_title": str(row.get("title") or ""),
                    "vol_plan_id": str(row.get("vol_plan_id") or ""),
                    "plan_created_at": str(row.get("created_at") or ""),
                },
            }
        )
    for row in outline_rows:
        chapter_id = str(row.get("chapter_id") or "").strip()
        if not chapter_id:
            continue
        items.append(
            {
                "asset_type": "chapter_outline",
                "asset_key": chapter_id,
                "ref_id": chapter_id,
                "version": int(row.get("outline_version") or 0),
                "payload": {
                    "chapter_no": int(row.get("chapter_no") or 0),
                    "chapter_title": str(row.get("title") or ""),
                },
            }
        )
    if style_hit:
        out_obj = style_hit.get("output") if isinstance(style_hit.get("output"), dict) else {}
        profile_ver_after = int((((out_obj.get("result") or {}) if isinstance(out_obj.get("result"), dict) else {}).get("profile_version_after") or 0))
        items.append(
            {
                "asset_type": "style_evolution",
                "asset_key": "latest",
                "ref_id": None,
                "version": profile_ver_after if profile_ver_after > 0 else None,
                "payload": {
                    "skill_run_id": str(style_hit.get("skill_run_id") or ""),
                    "created_at": str(style_hit.get("created_at") or ""),
                    "profile_version_after": profile_ver_after,
                },
            }
        )

    summary = {
        "book_id": str(book.get("book_id") or book_id),
        "book_title": str(book.get("title") or ""),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "chapters": chapter_count,
            "volumes": volume_count,
            "material_cards": material_count,
            "template_defaults": template_default_count,
            "template_used_distinct": template_used_count,
            "chapter_outline_versions": len([x for x in outline_rows if int(x.get("outline_version") or 0) > 0]),
        },
        "active_versions": {
            "profile_id": str((profile_hit or {}).get("profile_id") or ""),
            "profile_version": int((profile_hit or {}).get("active_version") or 0),
            "volume_plan_versions": [
                {
                    "volume_id": str(v.get("volume_id") or ""),
                    "volume_no": int(v.get("volume_no") or 0),
                    "version": int(v.get("version") or 0),
                }
                for v in active_volume_plans
                if str(v.get("volume_id") or "").strip()
            ],
        },
    }
    return {
        "summary": summary,
        "items": items,
    }


async def _capture_asset_snapshot(
    db: AsyncSession,
    *,
    book_id: str,
    snapshot_name: str,
    reason: str,
    tag: str,
    include_chapter_outlines: bool = True,
) -> dict[str, Any]:
    await _ensure_asset_snapshot_tables(db)
    state = await _collect_book_asset_state(db, book_id=book_id, include_chapter_outlines=include_chapter_outlines)
    summary = state.get("summary") if isinstance(state.get("summary"), dict) else {}
    items = state.get("items") if isinstance(state.get("items"), list) else []
    created = await db.execute(
        text(
            """
            INSERT INTO asset_snapshot(book_id, snapshot_name, reason, tag, summary)
            VALUES (CAST(:book_id AS uuid), :snapshot_name, :reason, :tag, CAST(:summary AS jsonb))
            RETURNING snapshot_id::text AS snapshot_id, book_id::text AS book_id, snapshot_name, reason, tag, summary, created_by, created_at
            """
        ),
        {
            "book_id": book_id,
            "snapshot_name": snapshot_name,
            "reason": reason,
            "tag": tag,
            "summary": json.dumps(summary, ensure_ascii=False),
        },
    )
    row = created.mappings().first()
    if not row:
        raise RuntimeError("ASSET_SNAPSHOT_CAPTURE_FAILED")
    snapshot_id = str(row.get("snapshot_id") or "")

    for item in items:
        if not isinstance(item, dict):
            continue
        ref_id = _safe_uuid_or_none(str(item.get("ref_id") or ""))
        await db.execute(
            text(
                """
                INSERT INTO asset_snapshot_item(snapshot_id, asset_type, asset_key, ref_id, version, payload)
                VALUES (
                  CAST(:snapshot_id AS uuid),
                  :asset_type,
                  :asset_key,
                  CAST(:ref_id AS uuid),
                  :version,
                  CAST(:payload AS jsonb)
                )
                ON CONFLICT (snapshot_id, asset_type, asset_key)
                DO UPDATE SET
                  ref_id=EXCLUDED.ref_id,
                  version=EXCLUDED.version,
                  payload=EXCLUDED.payload,
                  created_at=now()
                """
            ),
            {
                "snapshot_id": snapshot_id,
                "asset_type": str(item.get("asset_type") or "unknown"),
                "asset_key": str(item.get("asset_key") or ""),
                "ref_id": ref_id,
                "version": int(item.get("version") or 0) if item.get("version") is not None else None,
                "payload": json.dumps(item.get("payload") if isinstance(item.get("payload"), dict) else {}, ensure_ascii=False),
            },
        )
    await db.commit()
    return {
        "snapshot": dict(row),
        "item_count": len(items),
        "summary": summary,
    }


async def _rollback_asset_snapshot(
    db: AsyncSession,
    *,
    book_id: str,
    snapshot_id: str,
    note: str,
    restore_chapter_outlines: bool,
) -> dict[str, Any]:
    await _ensure_asset_snapshot_tables(db)
    snap_res = await db.execute(
        text(
            """
            SELECT snapshot_id::text AS snapshot_id, book_id::text AS book_id, snapshot_name, reason, tag, summary, created_by, created_at
            FROM asset_snapshot
            WHERE snapshot_id=CAST(:snapshot_id AS uuid)
              AND book_id=CAST(:book_id AS uuid)
            LIMIT 1
            """
        ),
        {"snapshot_id": snapshot_id, "book_id": book_id},
    )
    snapshot = snap_res.mappings().first()
    if not snapshot:
        raise RuntimeError("ASSET_SNAPSHOT_NOT_FOUND")

    item_res = await db.execute(
        text(
            """
            SELECT item_id::text AS item_id, asset_type, asset_key, ref_id::text AS ref_id, version, payload, created_at
            FROM asset_snapshot_item
            WHERE snapshot_id=CAST(:snapshot_id AS uuid)
            ORDER BY created_at ASC
            """
        ),
        {"snapshot_id": snapshot_id},
    )
    items = [dict(r) for r in item_res.mappings().all()]
    by_type: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        by_type.setdefault(str(item.get("asset_type") or "unknown"), []).append(item)

    result = {"applied": [], "skipped": [], "errors": []}

    settings_items = by_type.get("book_settings") or []
    if settings_items:
        settings_payload = settings_items[0].get("payload") if isinstance(settings_items[0].get("payload"), dict) else {}
        settings_obj = settings_payload.get("settings") if isinstance(settings_payload.get("settings"), dict) else {}
        await db.execute(
            text(
                """
                INSERT INTO book_settings(book_id, settings, updated_at)
                VALUES (CAST(:book_id AS uuid), CAST(:settings AS jsonb), now())
                ON CONFLICT (book_id)
                DO UPDATE SET settings=EXCLUDED.settings, updated_at=now()
                """
            ),
            {"book_id": book_id, "settings": json.dumps(settings_obj, ensure_ascii=False)},
        )
        result["applied"].append({"asset_type": "book_settings", "message": "已回滚书籍设置"})

    profile_items = by_type.get("profile") or []
    if profile_items:
        profile_item = profile_items[0]
        profile_id = str(profile_item.get("ref_id") or profile_item.get("asset_key") or "").strip()
        profile_version = int(profile_item.get("version") or 0)
        if profile_id and profile_version > 0:
            await db.execute(
                text("UPDATE profile SET active_version=:version, updated_at=now() WHERE profile_id=CAST(:profile_id AS uuid)"),
                {"profile_id": profile_id, "version": profile_version},
            )
            result["applied"].append(
                {"asset_type": "profile", "profile_id": profile_id, "profile_version": profile_version, "message": "已回滚画像激活版本"}
            )

    for item in by_type.get("volume_plan") or []:
        volume_id = str(item.get("ref_id") or item.get("asset_key") or "").strip()
        version = int(item.get("version") or 0)
        if not volume_id or version <= 0:
            result["skipped"].append({"asset_type": "volume_plan", "volume_id": volume_id, "reason": "缺少版本信息"})
            continue
        target_row = await db.execute(
            text(
                """
                SELECT vol_plan_id::text AS vol_plan_id
                FROM volume_plan
                WHERE volume_id=CAST(:volume_id AS uuid) AND version=:version
                LIMIT 1
                """
            ),
            {"volume_id": volume_id, "version": version},
        )
        target = target_row.mappings().first()
        if not target:
            result["errors"].append(
                {
                    "asset_type": "volume_plan",
                    "volume_id": volume_id,
                    "version": version,
                    "error": "TARGET_VERSION_NOT_FOUND",
                }
            )
            continue
        await db.execute(
            text("UPDATE volume_plan SET status='archived' WHERE volume_id=CAST(:volume_id AS uuid) AND status='active'"),
            {"volume_id": volume_id},
        )
        await db.execute(
            text("UPDATE volume_plan SET status='active' WHERE volume_id=CAST(:volume_id AS uuid) AND version=:version"),
            {"volume_id": volume_id, "version": version},
        )
        result["applied"].append(
            {"asset_type": "volume_plan", "volume_id": volume_id, "version": version, "message": "已切换分卷方案版本"}
        )

    if restore_chapter_outlines:
        for item in by_type.get("chapter_outline") or []:
            chapter_id = str(item.get("ref_id") or item.get("asset_key") or "").strip()
            target_version = int(item.get("version") or 0)
            if not chapter_id or target_version <= 0:
                continue
            content_row = await db.execute(
                text(
                    """
                    SELECT content, title
                    FROM outline
                    WHERE chapter_id=CAST(:chapter_id AS uuid)
                      AND scope='chapter'
                      AND version=:version
                    LIMIT 1
                    """
                ),
                {"chapter_id": chapter_id, "version": target_version},
            )
            target = content_row.mappings().first()
            if not target:
                result["errors"].append(
                    {
                        "asset_type": "chapter_outline",
                        "chapter_id": chapter_id,
                        "version": target_version,
                        "error": "OUTLINE_VERSION_NOT_FOUND",
                    }
                )
                continue
            latest_row = await db.execute(
                text(
                    """
                    SELECT COALESCE(MAX(version), 0)::int AS latest_version
                    FROM outline
                    WHERE chapter_id=CAST(:chapter_id AS uuid)
                      AND scope='chapter'
                    """
                ),
                {"chapter_id": chapter_id},
            )
            latest_version = int((latest_row.mappings().first() or {}).get("latest_version") or 0)
            if latest_version == target_version:
                result["skipped"].append(
                    {"asset_type": "chapter_outline", "chapter_id": chapter_id, "version": target_version, "reason": "已是当前最新版本"}
                )
                continue
            chapter_book = await db.execute(
                text("SELECT book_id::text AS book_id FROM chapter WHERE chapter_id=CAST(:chapter_id AS uuid) LIMIT 1"),
                {"chapter_id": chapter_id},
            )
            chapter_book_hit = chapter_book.mappings().first()
            if not chapter_book_hit:
                result["errors"].append({"asset_type": "chapter_outline", "chapter_id": chapter_id, "error": "CHAPTER_NOT_FOUND"})
                continue
            await db.execute(
                text(
                    """
                    INSERT INTO outline(book_id, chapter_id, scope, title, version, content)
                    VALUES (
                      CAST(:book_id AS uuid),
                      CAST(:chapter_id AS uuid),
                      'chapter',
                      :title,
                      :version,
                      CAST(:content AS jsonb)
                    )
                    """
                ),
                {
                    "book_id": str(chapter_book_hit.get("book_id") or ""),
                    "chapter_id": chapter_id,
                    "title": f"{str(target.get('title') or 'chapter_outline')} | rollback_snapshot",
                    "version": latest_version + 1,
                    "content": json.dumps(target.get("content") if isinstance(target.get("content"), dict) else {}, ensure_ascii=False),
                },
            )
            result["applied"].append(
                {
                    "asset_type": "chapter_outline",
                    "chapter_id": chapter_id,
                    "from_version": latest_version,
                    "to_version": latest_version + 1,
                    "source_version": target_version,
                    "message": "已创建回滚章纲版本",
                }
            )

    await db.commit()
    return {
        "snapshot": dict(snapshot),
        "note": note,
        "restore_chapter_outlines": restore_chapter_outlines,
        "result": result,
    }


WORKFLOW_DEFINITIONS: dict[str, dict] = {
    "draft_runner_v1": {
        "workflow_id": "draft_runner_v1",
        "version": 2,
        "nodes": [
            {"id": "resolve_chapter", "type": "sql", "inputs": {"query_id": "draft.resolve_chapter"}},
            {"id": "load_context", "type": "sql", "inputs": {"query_id": "draft.load_context"}},
            {"id": "compute_progress_and_curves", "type": "rule", "inputs": {"fn": "compute_progress_and_curves_v1"}},
            {"id": "load_volume_plan_and_combos", "type": "sql", "inputs": {"query_id": "draft.load_plan_combos"}},
            {"id": "build_candidate_tasks", "type": "rule", "inputs": {"fn": "build_candidate_tasks_v1"}},
            {"id": "combo_executor", "type": "rule", "inputs": {"fn": "combo_executor_v1"}},
            {"id": "chapter_orchestrator", "type": "rule", "inputs": {"fn": "chapter_orchestrator_v1"}},
            {"id": "pacing_controller", "type": "rule", "inputs": {"fn": "pacing_controller_v1"}},
            {"id": "task_intent_mapper", "type": "rule", "inputs": {"fn": "task_intent_mapper_v1"}},
            {"id": "memory_pack", "type": "memory_pack", "inputs": {"task_type": "write_chapter", "enabled": True}},
            {"id": "compose_prompt", "type": "compose", "inputs": {"template_id": "prompt.draft_runner_v2"}},
            {
                "id": "llm_generate",
                "type": "llm",
                "inputs": {
                    "provider": "ollama",
                    "model": DEFAULT_LLM_MODEL,
                    "temperature": 0.75,
                    "max_tokens": 5200,
                },
            },
            {"id": "post_extract_actions", "type": "rule", "inputs": {"fn": "post_extract_actions_v1"}},
            {"id": "validate_executed_tasks", "type": "rule", "inputs": {"fn": "validate_executed_tasks_v1"}},
            {"id": "quality_report", "type": "rule", "inputs": {"fn": "quality_report_v1"}},
            {"id": "update_reader_state", "type": "rule", "inputs": {"fn": "update_reader_state_v1"}},
            {"id": "commit_draft_and_logs", "type": "sql", "inputs": {"query_id": "draft.commit_all"}},
            {"id": "memory_writeback", "type": "memory_writeback", "inputs": {"enabled": True, "persist": True}},
            {"id": "audit_snapshot", "type": "sql", "inputs": {"query_id": "draft.write_audit_snapshot"}},
        ],
    }
}

WORKFLOW_SQL_FILES: dict[str, str] = {
    "draft.resolve_chapter": "draft_resolve_chapter.sql",
    "draft.load_context": "draft_load_context.sql",
    "draft.load_plan_combos": "draft_load_plan_combos.sql",
    "draft.commit_all": "draft_commit_all.sql",
    "draft.write_audit_snapshot": "draft_write_audit_snapshot.sql",
}


def _workflow_get_definition(workflow_id: str) -> dict:
    base = WORKFLOW_DEFINITIONS.get(workflow_id)
    if not isinstance(base, dict):
        raise RuntimeError("WORKFLOW_NOT_FOUND")
    return json.loads(json.dumps(base, ensure_ascii=False))


async def _ensure_workflow_tables(db: AsyncSession) -> None:
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS workflow_run (
              run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              workflow_id TEXT NOT NULL,
              workflow_version INTEGER NOT NULL,
              book_id UUID NULL REFERENCES book(book_id) ON DELETE SET NULL,
              chapter_id UUID NULL REFERENCES chapter(chapter_id) ON DELETE SET NULL,
              idempotency_key TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'running',
              started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              ended_at TIMESTAMPTZ NULL,
              error JSONB NULL,
              ctx_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
              meta JSONB NOT NULL DEFAULT '{}'::jsonb
            )
            """
        )
    )
    await db.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_workflow_run_idem ON workflow_run(workflow_id, idempotency_key)"))
    await db.execute(text("CREATE INDEX IF NOT EXISTS idx_workflow_run_time ON workflow_run(workflow_id, started_at DESC)"))
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS workflow_step (
              step_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              run_id UUID NOT NULL REFERENCES workflow_run(run_id) ON DELETE CASCADE,
              node_id TEXT NOT NULL,
              node_type TEXT NOT NULL,
              attempt INTEGER NOT NULL DEFAULT 1,
              status TEXT NOT NULL DEFAULT 'running',
              started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              ended_at TIMESTAMPTZ NULL,
              input JSONB NOT NULL DEFAULT '{}'::jsonb,
              output JSONB NOT NULL DEFAULT '{}'::jsonb,
              metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
              error JSONB NULL
            )
            """
        )
    )
    await db.execute(text("CREATE INDEX IF NOT EXISTS idx_workflow_step_run ON workflow_step(run_id, started_at)"))
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS state_apply_audit (
              audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
              chapter_id UUID NULL REFERENCES chapter(chapter_id) ON DELETE SET NULL,
              run_id UUID NULL REFERENCES workflow_run(run_id) ON DELETE SET NULL,
              action_type TEXT NOT NULL,
              before_state JSONB NOT NULL DEFAULT '{}'::jsonb,
              after_state JSONB NOT NULL DEFAULT '{}'::jsonb,
              diff JSONB NOT NULL DEFAULT '{}'::jsonb,
              reason TEXT NOT NULL DEFAULT '',
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    await db.execute(text("CREATE INDEX IF NOT EXISTS idx_state_apply_audit_book_time ON state_apply_audit(book_id, created_at DESC)"))
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS book_state (
              book_id UUID PRIMARY KEY REFERENCES book(book_id) ON DELETE CASCADE,
              orchestrator_limits JSONB NOT NULL DEFAULT '{}'::jsonb,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS combo_injection (
              inj_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
              volume_id UUID NULL REFERENCES volume(volume_id) ON DELETE SET NULL,
              combo_type TEXT NOT NULL,
              window_next_chapters INT NOT NULL DEFAULT 2,
              priority INT NOT NULL DEFAULT 3,
              status TEXT NOT NULL DEFAULT 'pending',
              expires_after_chapter_no INT NULL,
              consumed_chapter_id UUID NULL REFERENCES chapter(chapter_id) ON DELETE SET NULL,
              consumed_at TIMESTAMPTZ NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    await db.execute(text("ALTER TABLE combo_injection ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending'"))
    await db.execute(text("ALTER TABLE combo_injection ADD COLUMN IF NOT EXISTS expires_after_chapter_no INT NULL"))
    await db.execute(text("ALTER TABLE combo_injection ADD COLUMN IF NOT EXISTS consumed_chapter_id UUID NULL"))
    await db.execute(text("ALTER TABLE combo_injection ADD COLUMN IF NOT EXISTS consumed_at TIMESTAMPTZ NULL"))
    await db.execute(text("CREATE INDEX IF NOT EXISTS idx_combo_injection_book_status_time ON combo_injection(book_id, status, created_at DESC)"))
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS chapter_draft (
              draft_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
              chapter_id UUID NOT NULL REFERENCES chapter(chapter_id) ON DELETE CASCADE,
              run_id UUID NOT NULL REFERENCES workflow_run(run_id) ON DELETE CASCADE,
              variant TEXT NOT NULL DEFAULT 'A',
              text TEXT NOT NULL DEFAULT '',
              created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              UNIQUE(run_id, variant)
            )
            """
        )
    )
    await db.execute(text("ALTER TABLE chapter ADD COLUMN IF NOT EXISTS active_draft_id UUID NULL"))
    await db.execute(text("ALTER TABLE chapter_draft ADD COLUMN IF NOT EXISTS parent_draft_id UUID NULL REFERENCES chapter_draft(draft_id) ON DELETE SET NULL"))
    await db.execute(text("ALTER TABLE chapter_draft ADD COLUMN IF NOT EXISTS branch TEXT NOT NULL DEFAULT 'A'"))
    await db.execute(text("ALTER TABLE chapter_draft ADD COLUMN IF NOT EXISTS is_candidate BOOLEAN NOT NULL DEFAULT true"))
    await db.execute(text("ALTER TABLE chapter_draft ADD COLUMN IF NOT EXISTS is_selected BOOLEAN NOT NULL DEFAULT false"))
    await db.execute(text("ALTER TABLE chapter_draft ADD COLUMN IF NOT EXISTS selected_at TIMESTAMPTZ NULL"))
    await db.execute(text("ALTER TABLE chapter_draft ADD COLUMN IF NOT EXISTS rewrite_level TEXT NULL"))
    await db.execute(text("ALTER TABLE chapter_draft ADD COLUMN IF NOT EXISTS rewrite_meta JSONB NOT NULL DEFAULT '{}'::jsonb"))
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS chapter_selected (
              chapter_id UUID PRIMARY KEY REFERENCES chapter(chapter_id) ON DELETE CASCADE,
              selected_draft_id UUID NOT NULL REFERENCES chapter_draft(draft_id) ON DELETE RESTRICT,
              selected_branch TEXT NOT NULL DEFAULT 'A',
              selected_by TEXT NOT NULL DEFAULT 'user',
              selected_reason TEXT NOT NULL DEFAULT '',
              selected_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    await db.execute(text("CREATE INDEX IF NOT EXISTS idx_selected_draft ON chapter_selected(selected_draft_id)"))
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS chapter_events (
              draft_id UUID PRIMARY KEY REFERENCES chapter_draft(draft_id) ON DELETE CASCADE,
              book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
              chapter_id UUID NOT NULL REFERENCES chapter(chapter_id) ON DELETE CASCADE,
              events JSONB NOT NULL DEFAULT '{}'::jsonb,
              validated BOOLEAN NOT NULL DEFAULT false,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    await db.execute(text("CREATE INDEX IF NOT EXISTS idx_chapter_events_chapter ON chapter_events(chapter_id, created_at DESC)"))
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS foreshadow_state (
              foreshadow_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
              key TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'open',
              last_chapter_no INT NOT NULL DEFAULT 0,
              meta JSONB NOT NULL DEFAULT '{}'::jsonb,
              UNIQUE(book_id, key)
            )
            """
        )
    )
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS growth_state (
              milestone_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
              key TEXT NOT NULL,
              stage TEXT NOT NULL DEFAULT 'pending',
              last_chapter_no INT NOT NULL DEFAULT 0,
              meta JSONB NOT NULL DEFAULT '{}'::jsonb,
              UNIQUE(book_id, key)
            )
            """
        )
    )
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS chapter_trace (
              trace_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
              chapter_id UUID NOT NULL REFERENCES chapter(chapter_id) ON DELETE CASCADE,
              run_id UUID NOT NULL REFERENCES workflow_run(run_id) ON DELETE CASCADE,
              payload JSONB NOT NULL DEFAULT '{}'::jsonb,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              UNIQUE(run_id)
            )
            """
        )
    )
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS chapter_report (
              report_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
              chapter_id UUID NOT NULL REFERENCES chapter(chapter_id) ON DELETE CASCADE,
              run_id UUID NOT NULL REFERENCES workflow_run(run_id) ON DELETE CASCADE,
              report JSONB NOT NULL DEFAULT '{}'::jsonb,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              UNIQUE(run_id)
            )
            """
        )
    )
    await db.commit()


def _workflow_merge_ctx(base: dict, patch: dict) -> dict:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _workflow_merge_ctx(dict(base.get(key) or {}), value)
        else:
            base[key] = value
    return base


def _workflow_curve(progress: float) -> dict:
    p = _clamp01(float(progress))
    conflict = math.pow(max(0.0, math.sin(math.pi * p)), 1.5)
    reveal = 1.0 / (1.0 + math.exp(-((p - 0.4) * 8.0)))
    tension = math.pow(p, 1.2)
    growth = math.pow(p, 1.5)
    closure = max(0.0, (p - 0.85) / 0.15)
    return {
        "progress": round(p, 6),
        "conflict": round(_clamp01(conflict), 6),
        "reveal": round(_clamp01(reveal), 6),
        "tension": round(_clamp01(tension), 6),
        "growth": round(_clamp01(growth), 6),
        "closure": round(_clamp01(closure), 6),
    }


def _workflow_rule_compute_progress_and_curves(ctx: dict) -> dict:
    chapter_no = int(ctx.get("chapter_no") or 1)
    planned = max(1, int(ctx.get("planned_book_chapters") or chapter_no))
    progress = _clamp01(float(chapter_no) / float(planned))
    phase = "phase_setup"
    if progress >= 0.85:
        phase = "phase_climax"
    elif progress >= 0.5:
        phase = "phase_midgame"
    return {
        "structure": _workflow_curve(progress),
        "phase": phase,
    }


def _workflow_rule_build_candidate_tasks(ctx: dict) -> dict:
    structure = ctx.get("structure") if isinstance(ctx.get("structure"), dict) else {}
    p_vol = float(ctx.get("p_vol") or 0.0)
    tasks: list[dict] = []
    conflict = float(structure.get("conflict") or 0.0)
    reveal = float(structure.get("reveal") or 0.0)
    tension = float(structure.get("tension") or 0.0)
    growth = float(structure.get("growth") or 0.0)
    closure = float(structure.get("closure") or 0.0)

    def _mk_task(
        *,
        task_type: str,
        source: str,
        must_happen: bool,
        priority: int,
        intensity: int,
        structure_weight: int,
        target_min: float,
        target_max: float,
        defer_count: int = 0,
        refs: dict | None = None,
        meta: dict | None = None,
    ) -> dict:
        return {
            "task_id": str(uuid4()),
            "type": task_type,
            "source": source,
            "must_happen": bool(must_happen),
            "priority": int(priority),
            "intensity": max(1, min(3, int(intensity))),
            "structure_weight": max(1, int(structure_weight)),
            "target_window": {"min": _clamp01(float(target_min)), "max": _clamp01(float(target_max))},
            "p_vol": _clamp01(p_vol),
            "defer_count": max(0, int(defer_count)),
            "refs": refs if isinstance(refs, dict) else {},
            "constraints": {},
            "meta": meta if isinstance(meta, dict) else {},
        }

    # Replay deferred tasks from previous chapter first (priority-boosted carry-over).
    replay_filtered: list[dict] = []
    replay_seen: set[str] = set()
    limits_cfg = ctx.get("orchestrator_limits") if isinstance(ctx.get("orchestrator_limits"), dict) else {}
    max_defer_rounds = max(1, min(8, int(limits_cfg.get("defer_max_rounds") or 3)))
    defer_expire_grace = max(0.0, min(0.5, float(limits_cfg.get("defer_expire_grace") or 0.12)))
    for d in (ctx.get("deferred_tasks_in") if isinstance(ctx.get("deferred_tasks_in"), list) else []):
        if not isinstance(d, dict):
            continue
        ttype = str(d.get("type") or "").strip().lower()
        if not ttype:
            continue
        must_happen = bool(d.get("must_happen", True))
        pri = int(d.get("priority") or 3) + int(d.get("priority_boost") or 0)
        intensity = int(d.get("intensity") or 1)
        sw = int(d.get("structure_weight") or 1)
        defer_count = max(0, int(d.get("defer_count") or 0))
        tw = d.get("target_window") if isinstance(d.get("target_window"), dict) else {}
        minv = float(tw.get("min") or 0.0)
        maxv = float(tw.get("max") or 1.0)
        overdue = bool(d.get("overdue", False))
        refs = d.get("refs") if isinstance(d.get("refs"), dict) else {}
        meta = d.get("meta") if isinstance(d.get("meta"), dict) else {}
        origin_task_id = str(meta.get("origin_task_id") or d.get("task_id") or "").strip()
        ref_id = str(refs.get("ref_id") or "").strip()
        plan_item_id = str(refs.get("plan_item_id") or "").strip()
        dedupe_key = (
            f"plan:{plan_item_id}" if plan_item_id else
            f"origin:{origin_task_id}" if origin_task_id else
            f"type_ref:{ttype}:{ref_id}" if ref_id else
            f"type_only:{ttype}"
        )
        if dedupe_key in replay_seen:
            replay_filtered.append({"type": ttype, "reason": "duplicate_replay", "refs": refs})
            continue
        if (not must_happen) and defer_count >= max_defer_rounds:
            replay_filtered.append({"type": ttype, "reason": "max_defer_rounds_reached", "refs": refs})
            continue
        if (not must_happen) and p_vol > (_clamp01(maxv) + defer_expire_grace):
            replay_filtered.append({"type": ttype, "reason": "expired_window", "refs": refs})
            continue
        replay_seen.add(dedupe_key)
        meta = {
            **meta,
            "replayed_from_deferred": True,
            "defer_reason": str(d.get("reason") or ""),
            "origin_task_id": str(d.get("task_id") or ""),
        }
        tasks.append(
            _mk_task(
                task_type=ttype,
                source="deferred_replay",
                must_happen=must_happen,
                priority=(pri + 1 if overdue else pri),
                intensity=intensity,
                structure_weight=sw,
                target_min=minv,
                target_max=maxv,
                defer_count=defer_count,
                refs=refs,
                meta=meta,
            )
        )

    # Curve-forced baseline candidates
    if conflict > 0.62:
        tasks.append(_mk_task(task_type="growth", source="curve_force", must_happen=True, priority=5, intensity=3, structure_weight=3, target_min=0.65, target_max=0.9, meta={"stage": "breakthrough"}))
    elif conflict > 0.4:
        tasks.append(_mk_task(task_type="growth", source="curve_force", must_happen=False, priority=3, intensity=2, structure_weight=1, target_min=0.25, target_max=0.8, meta={"stage": "pressure"}))
    if reveal > 0.55:
        tasks.append(_mk_task(task_type="reveal", source="curve_force", must_happen=True, priority=4, intensity=2, structure_weight=1, target_min=0.4, target_max=0.95, meta={"combo_hint": "reveal_combo"}))
    if tension > 0.7 or closure > 0.5:
        tasks.append(_mk_task(task_type="cliff", source="curve_force", must_happen=True, priority=4, intensity=(2 if closure < 0.65 else 3), structure_weight=1, target_min=0.72, target_max=1.0, meta={"style": "question_end"}))
    if growth > 0.55:
        tasks.append(_mk_task(task_type="payoff", source="curve_force", must_happen=False, priority=3, intensity=2, structure_weight=2, target_min=0.5, target_max=1.0, meta={"payoff_template_type": "emotional"}))
    tasks.append(_mk_task(task_type="seed", source="default", must_happen=False, priority=2, intensity=1, structure_weight=1, target_min=0.0, target_max=0.95))

    # Plan items mapped into candidate tasks.
    # Combo items stay as type=combo and are expanded by combo_executor_v1.
    for it in (ctx.get("volume_plan_items") if isinstance(ctx.get("volume_plan_items"), list) else []):
        if not isinstance(it, dict):
            continue
        kind = str(it.get("kind") or "").strip().lower()
        ttype = kind
        if kind == "foreshadow_payoff":
            ttype = "payoff"
        elif kind == "foreshadow_seed":
            ttype = "seed"
        elif kind == "cliffhanger":
            ttype = "cliff"
        elif kind == "growth":
            ttype = "growth"
        elif kind == "combo":
            ttype = "combo"
        if not ttype:
            continue
        minv = float(it.get("target_p_vol_min") or 0.0)
        maxv = float(it.get("target_p_vol_max") or 1.0)
        pri = int(it.get("priority") or 3)
        must = bool(it.get("must_happen"))
        intensity = int(((it.get("meta") if isinstance(it.get("meta"), dict) else {}).get("intensity") or 2))
        weight = 1
        if ttype == "growth" and str(((it.get("meta") if isinstance(it.get("meta"), dict) else {}).get("stage") or "")).lower() == "breakthrough":
            weight = 3
        elif ttype == "payoff" and intensity >= 2:
            weight = 2
        base_refs = {
            "plan_item_id": str(it.get("item_id") or ""),
            "ref_id": str(it.get("ref_id") or ""),
        }
        base_meta = {
            "summary": str(it.get("summary") or ""),
            "target_window": str(it.get("target_window") or ""),
            **((it.get("meta") if isinstance(it.get("meta"), dict) else {})),
        }
        if ttype != "combo":
            tasks.append(
                _mk_task(
                    task_type=ttype,
                    source="plan",
                    must_happen=must,
                    priority=pri,
                    intensity=intensity,
                    structure_weight=weight,
                    target_min=minv,
                    target_max=maxv,
                    refs=base_refs,
                    meta=base_meta,
                )
            )
            continue

        combo_meta = it.get("meta") if isinstance(it.get("meta"), dict) else {}
        combo_type = str(combo_meta.get("combo_type") or "").strip().lower()
        if not combo_type:
            ref_id = str(it.get("ref_id") or "").strip().lower()
            if ref_id in {"setup_hook_combo", "mid_spike_combo", "reveal_combo", "vol_end_combo"}:
                combo_type = ref_id
        tasks.append(
            _mk_task(
                task_type="combo",
                source="plan_combo",
                must_happen=must,
                priority=max(pri, 4),
                intensity=max(1, min(3, intensity)),
                structure_weight=max(1, weight),
                target_min=minv,
                target_max=maxv,
                refs={**base_refs, "combo_type": combo_type or "unknown"},
                meta={**base_meta, "from_combo": combo_type or "unknown"},
            )
        )

    # Runtime forced tasks from SQL (e.g. near-end cliff).
    for rt in (ctx.get("near_end_force") if isinstance(ctx.get("near_end_force"), list) else []):
        if not isinstance(rt, dict):
            continue
        tasks.append(
            _mk_task(
                task_type=str(rt.get("type") or "cliff"),
                source=str(rt.get("source") or "runtime_force"),
                must_happen=bool(rt.get("must_happen", True)),
                priority=int(rt.get("priority") or 5),
                intensity=int(rt.get("intensity") or 2),
                structure_weight=int(rt.get("structure_weight") or 1),
                target_min=float(((rt.get("target_window") if isinstance(rt.get("target_window"), dict) else {}).get("min") or p_vol)),
                target_max=float(((rt.get("target_window") if isinstance(rt.get("target_window"), dict) else {}).get("max") or 1.0)),
                refs=rt.get("refs") if isinstance(rt.get("refs"), dict) else {},
                meta=rt.get("meta") if isinstance(rt.get("meta"), dict) else {},
            )
        )

    # Agent injected combo queue (reversible via /agent/rollback delete by inj_id).
    for inj in (ctx.get("combo_injections") if isinstance(ctx.get("combo_injections"), list) else []):
        if not isinstance(inj, dict):
            continue
        combo_type = str(inj.get("combo_type") or "").strip().lower()
        if not combo_type:
            continue
        win_next = max(1, min(8, int(inj.get("window_next_chapters") or 2)))
        pri = max(1, min(10, int(inj.get("priority") or 4)))
        target_max = min(1.0, _clamp01(p_vol) + (0.08 * float(win_next)))
        tasks.append(
            _mk_task(
                task_type="combo",
                source="agent_injection",
                must_happen=True,
                priority=pri,
                intensity=2,
                structure_weight=1,
                target_min=_clamp01(p_vol),
                target_max=target_max,
                refs={
                    "inj_id": str(inj.get("inj_id") or ""),
                    "combo_type": combo_type,
                    "volume_id": str(inj.get("volume_id") or ""),
                },
                meta={"injected": True, "window_next_chapters": win_next},
            )
        )
    return {"candidate_tasks": tasks, "replay_filtered_tasks": replay_filtered}


def _combo_steps_v1(combo_type: str) -> list[dict]:
    ct = str(combo_type or "").strip().lower()
    if ct == "setup_hook_combo":
        return [
            {"step": "hook", "task_type": "hook", "base_weight": 1, "base_intensity": 2, "group": "setup_hook"},
            {"step": "goal", "task_type": "hook", "base_weight": 1, "base_intensity": 1, "group": "setup_hook"},
            {"step": "threat", "task_type": "cost", "base_weight": 1, "base_intensity": 2, "group": "setup_hook"},
        ]
    if ct == "mid_spike_combo":
        return [
            {"step": "pressure", "task_type": "growth", "base_weight": 1, "base_intensity": 2, "group": "mid_spike"},
            {"step": "reversal", "task_type": "reveal", "base_weight": 1, "base_intensity": 2, "group": "mid_spike"},
            {"step": "cost", "task_type": "cost", "base_weight": 1, "base_intensity": 2, "group": "mid_spike"},
        ]
    if ct == "reveal_combo":
        return [
            {"step": "clue", "task_type": "reveal", "base_weight": 1, "base_intensity": 1, "group": "reveal_combo"},
            {"step": "reinterpret", "task_type": "reveal", "base_weight": 1, "base_intensity": 2, "group": "reveal_combo"},
            {"step": "partial_payoff", "task_type": "payoff", "base_weight": 1, "base_intensity": 2, "group": "reveal_combo"},
        ]
    if ct == "vol_end_combo":
        return [
            {"step": "trap", "task_type": "cost", "base_weight": 1, "base_intensity": 2, "group": "vol_end_main"},
            {"step": "main_payoff", "task_type": "payoff", "base_weight": 2, "base_intensity": 3, "group": "vol_end_main"},
            {"step": "cliff", "task_type": "cliff", "base_weight": 1, "base_intensity": 2, "group": "vol_end_main"},
        ]
    return [{"step": "hook", "task_type": "hook", "base_weight": 1, "base_intensity": 2, "group": "unknown_combo"}]


def _workflow_rule_combo_executor(ctx: dict) -> dict:
    tasks = [x for x in (ctx.get("candidate_tasks") if isinstance(ctx.get("candidate_tasks"), list) else []) if isinstance(x, dict)]
    p_vol = _clamp01(float(ctx.get("p_vol") or 0.0))
    chapters_to_end = int(ctx.get("chapters_to_end") or 9999)
    reader = ctx.get("reader_state") if isinstance(ctx.get("reader_state"), dict) else {}
    clarity = _clamp01(float(reader.get("clarity") or 0.7))
    fatigue = _clamp01(float(reader.get("fatigue") or 0.1))
    expanded: list[dict] = []
    expanded_count = 0

    for t in tasks:
        if str(t.get("type") or "") != "combo":
            expanded.append(t)
            continue

        refs = t.get("refs") if isinstance(t.get("refs"), dict) else {}
        meta = t.get("meta") if isinstance(t.get("meta"), dict) else {}
        combo_type = str(refs.get("combo_type") or meta.get("combo_type") or "unknown").strip().lower()
        plan_item_id = str(refs.get("plan_item_id") or t.get("task_id") or uuid4())
        combo_fp = str(meta.get("combo_fingerprint") or f"{combo_type}:{plan_item_id}")
        base_priority = int(t.get("priority") or 3)
        base_intensity = max(1, min(3, int(t.get("intensity") or 2)))
        must_happen = bool(t.get("must_happen", False))
        tw = t.get("target_window") if isinstance(t.get("target_window"), dict) else {"min": 0.0, "max": 1.0}

        for idx, s in enumerate(_combo_steps_v1(combo_type), start=1):
            step = str(s.get("step") or "").strip().lower()
            task_type = str(s.get("task_type") or "hook").strip().lower()
            pr = base_priority + 1
            intensity = max(1, min(3, int(round((base_intensity + int(s.get("base_intensity") or 1)) / 2))))
            sw = max(1, int(s.get("base_weight") or 1))
            group = str(s.get("group") or f"{combo_type}_group")

            if fatigue > 0.65 and step in {"cost", "reversal", "main_payoff"}:
                intensity = max(1, intensity - 1)
            if combo_type == "vol_end_combo":
                if chapters_to_end <= 2 and step in {"main_payoff", "cliff"}:
                    pr += 3
                    must_happen = True
                    intensity = max(2, intensity)
                if chapters_to_end > 2 and step == "cliff":
                    pr -= 2
            if combo_type == "reveal_combo" and clarity < 0.35 and step == "reinterpret":
                pr += 3
            if combo_type == "setup_hook_combo" and p_vol < 0.18 and step == "hook":
                pr += 2

            expanded.append(
                {
                    "task_id": f"{plan_item_id}:{step}",
                    "type": task_type,
                    "source": "combo_step",
                    "combo": {"combo_type": combo_type, "step": step, "combo_fp": combo_fp},
                    "must_happen": must_happen,
                    "priority": pr,
                    "intensity": intensity,
                    "structure_weight": sw,
                    "target_window": {"min": _clamp01(float(tw.get("min") or 0.0)), "max": _clamp01(float(tw.get("max") or 1.0))},
                    "p_vol": p_vol,
                    "constraints": {"exclusive_group": group, "max_per_chapter": 1},
                    "refs": {
                        "plan_item_id": plan_item_id,
                        "ref_id": str(refs.get("ref_id") or ""),
                        "combo_type": combo_type,
                        "inj_id": str(refs.get("inj_id") or ""),
                    },
                    "meta": {
                        **meta,
                        "from_combo": combo_type,
                        "combo_step": step,
                        "step_order": idx,
                        "combo_fp": combo_fp,
                        "window_hint": _window_from_p_vol(p_vol),
                    },
                }
            )
            expanded_count += 1

    return {"candidate_tasks": expanded, "combo_expanded_count": expanded_count}


def _workflow_rule_pacing_controller(ctx: dict) -> dict:
    reader = _normalize_reader_state(ctx.get("reader_state") if isinstance(ctx.get("reader_state"), dict) else None)
    structure = ctx.get("structure") if isinstance(ctx.get("structure"), dict) else {}
    final_tasks = ctx.get("final_tasks") if isinstance(ctx.get("final_tasks"), list) else []
    tension = _clamp01(float(structure.get("tension") or 0.0))
    has_reveal = any(str((x or {}).get("type") or "") in {"reveal"} for x in final_tasks if isinstance(x, dict))
    has_payoff = any(str((x or {}).get("type") or "") in {"payoff"} for x in final_tasks if isinstance(x, dict))

    target_length = 2400
    if reader.get("fatigue", 0.0) > 0.65:
        target_length -= 400
    if reader.get("clarity", 1.0) < 0.35:
        target_length += 200
    if tension > 0.7:
        target_length -= 150
    target_length = max(1400, min(3200, int(target_length)))

    short_ratio = 0.45
    medium_ratio = 0.4
    long_ratio = 0.15
    if tension > 0.7:
        short_ratio, medium_ratio, long_ratio = 0.58, 0.34, 0.08
    if reader.get("fatigue", 0.0) > 0.65:
        short_ratio, medium_ratio, long_ratio = max(short_ratio, 0.55), 0.35, 0.10

    dialogue_ratio = 0.36
    if reader.get("clarity", 1.0) < 0.35:
        dialogue_ratio += 0.08
    if reader.get("fatigue", 0.0) > 0.65:
        dialogue_ratio += 0.06
    if has_payoff:
        dialogue_ratio -= 0.04
    dialogue_ratio = _clamp01(dialogue_ratio)

    info_density = "medium"
    if reader.get("fatigue", 0.0) > 0.65:
        info_density = "low"
    if has_reveal and reader.get("clarity", 1.0) >= 0.35:
        info_density = "medium_high"

    pacer = {
        "target_length": target_length,
        "paragraph_plan": {
            "short": round(short_ratio, 3),
            "medium": round(medium_ratio, 3),
            "long": round(long_ratio, 3),
        },
        "dialogue_ratio": round(dialogue_ratio, 3),
        "info_density": info_density,
        "style_toggles": {
            "ban_world_dump": True,
            "ban_meta_explain": True,
            "prefer_actions_over_thoughts": True,
        },
    }
    return {"pacer": pacer}


def _task_intent_definitions() -> dict[str, dict]:
    return {
        "hook": {
            "intent": "第一屏抓人，给出反常细节并提出可追的问题。",
            "evidence_required": ["至少一个反常细节", "一句明确问题钩子"],
            "banned_moves": ["大段世界观说明", "纯设定旁白"],
        },
        "goal": {
            "intent": "明确本章可执行短期目标与行动方向。",
            "evidence_required": ["目标陈述", "行动起步"],
            "banned_moves": ["抽象口号", "空泛决心"],
        },
        "threat": {
            "intent": "把威胁具体化，让代价可感知。",
            "evidence_required": ["威胁来源", "触发条件或后果"],
            "banned_moves": ["只说很危险", "无证据威胁"],
        },
        "cost": {
            "intent": "代价上镜，推动情绪与局势变化。",
            "evidence_required": ["损失具体化", "关系或资源后果"],
            "banned_moves": ["轻描淡写", "一句带过代价"],
        },
        "reveal": {
            "intent": "释放关键信息并提升理解度。",
            "evidence_required": ["新线索", "旧线索关联说明"],
            "banned_moves": ["说明书式解释", "一次性全揭底"],
        },
        "reinterpret": {
            "intent": "重解读既有事件，产生认知翻转。",
            "evidence_required": ["新证据触发", "旧事实新含义"],
            "banned_moves": ["靠巧合翻转", "旁白硬解释"],
        },
        "payoff": {
            "intent": "兑现伏笔并形成明确结果。",
            "evidence_required": ["前置伏笔回收", "结果可验证"],
            "banned_moves": ["回忆补丁", "结果不落地"],
        },
        "cliff": {
            "intent": "章节末尾制造立即性的下一步问题。",
            "evidence_required": ["新风险或新目标", "立即行动压力"],
            "banned_moves": ["敬请期待式空钩子", "无新信息断章"],
        },
    }


def _workflow_rule_task_intent_mapper(ctx: dict) -> dict:
    defs = _task_intent_definitions()
    final_tasks = ctx.get("final_tasks") if isinstance(ctx.get("final_tasks"), list) else []
    enriched: list[dict] = []
    for t in final_tasks:
        if not isinstance(t, dict):
            continue
        ttype = str(t.get("type") or t.get("task_type") or "").strip().lower()
        spec = defs.get(ttype, {
            "intent": "推进本章结构任务，保持连贯与可读性。",
            "evidence_required": ["至少一个可观察证据点"],
            "banned_moves": ["元叙事说明"],
        })
        row = dict(t)
        row["intent"] = str(spec.get("intent") or "")
        row["evidence_required"] = [str(x) for x in (spec.get("evidence_required") if isinstance(spec.get("evidence_required"), list) else [])]
        row["banned_moves"] = [str(x) for x in (spec.get("banned_moves") if isinstance(spec.get("banned_moves"), list) else [])]
        enriched.append(row)
    return {"final_tasks_intent": enriched}


def _workflow_rule_orchestrator(ctx: dict) -> dict:
    limits = ctx.get("orchestrator_limits") if isinstance(ctx.get("orchestrator_limits"), dict) else {}
    reader = ctx.get("reader_state") if isinstance(ctx.get("reader_state"), dict) else {}
    structure = ctx.get("structure") if isinstance(ctx.get("structure"), dict) else {}
    p_vol = _clamp01(float(ctx.get("p_vol") or 0.0))
    chapters_to_end = int(ctx.get("chapters_to_end") or 9999)

    limits_eff = {
        "max_structure_weight": max(2, min(7, int(limits.get("max_structure_weight") or 4))),
        "max_tasks_per_chapter": max(1, min(5, int(limits.get("max_tasks_per_chapter") or 3))),
        "ban_strong_cliff": bool(limits.get("ban_strong_cliff", False)),
        "defer_max_rounds": max(1, min(8, int(limits.get("defer_max_rounds") or 3))),
        "defer_expire_grace": max(0.0, min(0.5, float(limits.get("defer_expire_grace") or 0.12))),
    }
    if _clamp01(float(reader.get("fatigue") or 0.0)) > 0.65:
        limits_eff["max_structure_weight"] = min(int(limits_eff["max_structure_weight"]), 3)
        limits_eff["max_tasks_per_chapter"] = min(int(limits_eff["max_tasks_per_chapter"]), 2)
        limits_eff["ban_strong_cliff"] = True

    require_task_types: set[str] = set()
    if p_vol < 0.18:
        require_task_types.add("hook")
    if p_vol > 0.80:
        require_task_types.add("cliff")
    if _clamp01(float(reader.get("clarity") or 0.0)) < 0.35:
        require_task_types.add("reveal")
    if _clamp01(float(reader.get("expectation") or 0.0)) < 0.4:
        require_task_types.add("cliff")
    require_reinterpret = _clamp01(float(reader.get("clarity") or 0.0)) < 0.35
    require_cliff_int2 = chapters_to_end <= 2

    raw_candidates = [x for x in (ctx.get("candidate_tasks") if isinstance(ctx.get("candidate_tasks"), list) else []) if isinstance(x, dict)]
    candidates: list[dict] = []
    for task in raw_candidates:
        t = dict(task)
        t["type"] = str(t.get("type") or t.get("task_type") or "").strip()
        t["priority"] = int(t.get("priority") or 3)
        t["intensity"] = max(1, min(3, int(t.get("intensity") or 1)))
        t["structure_weight"] = max(1, int(t.get("structure_weight") or t.get("weight") or 1))
        t["must_happen"] = bool(t.get("must_happen", False))
        tw = t.get("target_window") if isinstance(t.get("target_window"), dict) else {}
        t["target_window"] = {"min": _clamp01(float(tw.get("min") if tw.get("min") is not None else 0.0)), "max": _clamp01(float(tw.get("max") if tw.get("max") is not None else 1.0))}
        t["p_vol"] = _clamp01(float(t.get("p_vol") if t.get("p_vol") is not None else p_vol))
        t["defer_count"] = max(0, int(t.get("defer_count") or 0))
        t["meta"] = t.get("meta") if isinstance(t.get("meta"), dict) else {}
        t["refs"] = t.get("refs") if isinstance(t.get("refs"), dict) else {}
        t["constraints"] = t.get("constraints") if isinstance(t.get("constraints"), dict) else {}
        t["task_id"] = str(t.get("task_id") or uuid4())
        candidates.append(t)

    deferred_tasks: list[dict] = []
    window_open_candidates: list[dict] = []
    for t in candidates:
        tw = t.get("target_window") if isinstance(t.get("target_window"), dict) else {}
        tmin = _clamp01(float(tw.get("min") if tw.get("min") is not None else 0.0))
        if p_vol + 0.01 < tmin:
            deferred_tasks.append(
                {
                    "task_id": str(t.get("task_id")),
                    "type": str(t.get("type") or ""),
                    "source": str(t.get("source") or ""),
                    "must_happen": bool(t.get("must_happen")),
                    "priority": int(t.get("priority") or 3),
                    "intensity": int(t.get("intensity") or 1),
                    "structure_weight": int(t.get("structure_weight") or 1),
                    "target_window": t.get("target_window") if isinstance(t.get("target_window"), dict) else {"min": 0.0, "max": 1.0},
                    "reason": "window_not_open",
                    "priority_boost": 0,
                    "overdue": False,
                    "defer_to_chapter_offset": 1,
                    "refs": t.get("refs") if isinstance(t.get("refs"), dict) else {},
                    "meta": t.get("meta") if isinstance(t.get("meta"), dict) else {},
                }
            )
            continue
        window_open_candidates.append(t)
    candidates = window_open_candidates

    def _mergeable(a: dict, b: dict) -> str:
        pair = {str(a.get("type") or ""), str(b.get("type") or "")}
        if pair == {"seed", "cliff"}:
            return "seed_cliff"
        if pair == {"reveal", "payoff"} and int(a.get("intensity") or 1) <= 2 and int(b.get("intensity") or 1) <= 2:
            return "reveal_payoff"
        if pair == {"growth", "payoff"}:
            a_stage = str((a.get("meta") or {}).get("stage") or "")
            b_stage = str((b.get("meta") or {}).get("stage") or "")
            if "breakthrough" not in {a_stage, b_stage}:
                return "growth_payoff"
        return ""

    merged: list[dict] = []
    used_ids: set[str] = set()
    for i in range(len(candidates)):
        a = candidates[i]
        aid = str(a.get("task_id"))
        if aid in used_ids:
            continue
        merged_any = False
        for j in range(i + 1, len(candidates)):
            b = candidates[j]
            bid = str(b.get("task_id"))
            if bid in used_ids:
                continue
            mode = _mergeable(a, b)
            if not mode:
                continue
            used_ids.add(aid)
            used_ids.add(bid)
            minw = min(float((a.get("target_window") or {}).get("min") or 0.0), float((b.get("target_window") or {}).get("min") or 0.0))
            maxw = max(float((a.get("target_window") or {}).get("max") or 1.0), float((b.get("target_window") or {}).get("max") or 1.0))
            ttype = "cliff" if mode == "seed_cliff" else ("payoff" if mode in {"reveal_payoff", "growth_payoff"} else str(a.get("type") or ""))
            m = {
                "task_id": str(uuid4()),
                "type": ttype,
                "source": "merge",
                "must_happen": bool(a.get("must_happen") or b.get("must_happen")),
                "priority": max(int(a.get("priority") or 3), int(b.get("priority") or 3)),
                "intensity": max(int(a.get("intensity") or 1), int(b.get("intensity") or 1)),
                "structure_weight": max(1, min(int(a.get("structure_weight") or 1) + int(b.get("structure_weight") or 1), 3)),
                "target_window": {"min": _clamp01(minw), "max": _clamp01(maxw)},
                "p_vol": p_vol,
                "refs": {**(a.get("refs") or {}), **(b.get("refs") or {})},
                "meta": {
                    "merge_mode": mode,
                    "merged_from": [aid, bid],
                    "style": "new_condition" if mode == "seed_cliff" else ((a.get("meta") or {}).get("style") or (b.get("meta") or {}).get("style") or "question_end"),
                    "payoff_template_type": (a.get("meta") or {}).get("payoff_template_type")
                    or (b.get("meta") or {}).get("payoff_template_type")
                    or ("misinterpretation" if mode == "reveal_payoff" else "cost"),
                },
            }
            merged.append(m)
            merged_any = True
            break
        if not merged_any and aid not in used_ids:
            merged.append(a)

    def _task_score(task: dict) -> tuple[float, dict]:
        must = 5.0 if bool(task.get("must_happen")) else 0.0
        tmin = float((task.get("target_window") or {}).get("min") or 0.0)
        tmax = float((task.get("target_window") or {}).get("max") or 1.0)
        overdue = 4.0 if bool(task.get("must_happen")) and p_vol > tmax else 0.0
        window_closing = 3.0 if bool(task.get("must_happen")) and 0 <= (tmax - p_vol) < 0.04 else 0.0
        pri = float(int(task.get("priority") or 3) * 2)
        curve_align = 0.0
        ttype = str(task.get("type") or "")
        if ttype in {"payoff", "reveal"}:
            curve_align += float(structure.get("reveal") or 0.0) * 2.0
        if ttype in {"growth", "cost"}:
            curve_align += float(structure.get("conflict") or 0.0) * 2.0
        if ttype in {"cliff", "hook"}:
            curve_align += float(structure.get("tension") or 0.0) * 2.0
        reader_align = 0.0
        fatigue = _clamp01(float(reader.get("fatigue") or 0.0))
        if fatigue > 0.65:
            if ttype == "reveal":
                reader_align += 2.0
            if ttype == "payoff" and str((task.get("meta") or {}).get("payoff_template_type") or "") == "emotional":
                reader_align += 1.0
            if int(task.get("structure_weight") or 1) >= 3:
                reader_align -= 2.0
        combo_bonus = 1.0 if bool((task.get("meta") or {}).get("combo_completion_bonus")) else 0.0
        risk_penalty = float((task.get("meta") or {}).get("risk_penalty") or 0.0)
        score = must + overdue + window_closing + pri + curve_align + reader_align + combo_bonus - risk_penalty
        return score, {
            "must": must,
            "overdue": overdue,
            "window_closing": window_closing,
            "priority": pri,
            "curve_alignment": round(curve_align, 4),
            "reader_alignment": round(reader_align, 4),
            "combo_bonus": combo_bonus,
            "risk_penalty": risk_penalty,
        }

    scored: list[dict] = []
    for t in merged:
        sc, breakdown = _task_score(t)
        scored.append({**t, "_score": float(sc), "_score_breakdown": breakdown})
    scored.sort(key=lambda x: float(x.get("_score") or 0.0), reverse=True)

    selected: list[dict] = []
    dropped: list[dict] = []
    replay_filtered = [x for x in (ctx.get("replay_filtered_tasks") if isinstance(ctx.get("replay_filtered_tasks"), list) else []) if isinstance(x, dict)]
    for rf in replay_filtered:
        dropped.append(
            {
                "task_id": str((rf.get("refs") or {}).get("ref_id") or ""),
                "type": str(rf.get("type") or ""),
                "reason": f"replay_filtered:{str(rf.get('reason') or '')}",
            }
        )
    structure_weight_sum = 0
    breakthrough_cnt = 0
    strong_payoff_cnt = 0
    has_seed_selected = False
    has_main_payoff_selected = False
    conflict_reasons: list[str] = []
    exclusive_group_count: dict[str, int] = {}

    def _is_main_payoff(task: dict) -> bool:
        if str(task.get("type") or "") != "payoff":
            return False
        meta = task.get("meta") if isinstance(task.get("meta"), dict) else {}
        if bool(meta.get("secondary", False)):
            return False
        return int(task.get("intensity") or 1) >= 2

    for t in scored:
        ttype = str(t.get("type") or "")
        intensity = int(t.get("intensity") or 1)
        sw = int(t.get("structure_weight") or 1)
        reason = ""
        if limits_eff["ban_strong_cliff"] and ttype == "cliff" and intensity >= 3:
            reason = "ban_strong_cliff"
        elif ttype == "growth" and str((t.get("meta") or {}).get("stage") or "").lower() == "breakthrough" and breakthrough_cnt >= 1:
            reason = "breakthrough_limit"
        elif ttype == "payoff" and intensity >= 3 and strong_payoff_cnt >= 1:
            reason = "strong_payoff_limit"
        elif ttype == "seed" and has_main_payoff_selected and not bool((t.get("meta") or {}).get("allow_seed_with_payoff")):
            reason = "seed_with_main_payoff_blocked"
        elif _is_main_payoff(t) and has_seed_selected and not bool((t.get("meta") or {}).get("allow_seed_with_payoff")):
            reason = "main_payoff_with_seed_blocked"
        elif _clamp01(float(reader.get("fatigue") or 0.0)) > 0.65 and str((t.get("meta") or {}).get("stage") or "").lower() == "breakthrough" and has_main_payoff_selected:
            reason = "fatigue_breakthrough_payoff_blocked"
        elif _clamp01(float(reader.get("fatigue") or 0.0)) > 0.65 and _is_main_payoff(t) and breakthrough_cnt >= 1:
            reason = "fatigue_breakthrough_payoff_blocked"
        elif (
            str((t.get("constraints") or {}).get("exclusive_group") or "").strip()
            and int(
                exclusive_group_count.get(
                    str((t.get("constraints") or {}).get("exclusive_group") or "").strip(), 0
                )
            )
            >= max(1, int((t.get("constraints") or {}).get("max_per_chapter") or 1))
        ):
            reason = "exclusive_group_limit"
        elif len(selected) >= int(limits_eff["max_tasks_per_chapter"]):
            reason = "max_tasks"
        elif (structure_weight_sum + sw) > int(limits_eff["max_structure_weight"]):
            reason = "overload"
        if reason:
            conflict_reasons.append(reason)
            if bool(t.get("must_happen")):
                deferred_tasks.append(
                    {
                        "task_id": str(t.get("task_id")),
                        "type": ttype,
                        "source": str(t.get("source") or ""),
                        "must_happen": bool(t.get("must_happen")),
                        "priority": int(t.get("priority") or 3),
                        "intensity": int(t.get("intensity") or 1),
                        "structure_weight": int(t.get("structure_weight") or 1),
                        "target_window": t.get("target_window")
                        if isinstance(t.get("target_window"), dict)
                        else {"min": 0.0, "max": 1.0},
                        "defer_count": int(t.get("defer_count") or 0) + 1,
                        "reason": reason,
                        "priority_boost": 1 if reason in {"overload", "max_tasks"} else 2,
                        "overdue": bool(p_vol > float((t.get("target_window") or {}).get("max") or 1.0)),
                        "defer_to_chapter_offset": 1,
                        "refs": t.get("refs") if isinstance(t.get("refs"), dict) else {},
                        "meta": t.get("meta") if isinstance(t.get("meta"), dict) else {},
                    }
                )
            else:
                dropped.append({"task_id": str(t.get("task_id")), "type": ttype, "reason": reason})
            continue
        selected.append(t)
        structure_weight_sum += sw
        if ttype == "growth" and str((t.get("meta") or {}).get("stage") or "").lower() == "breakthrough":
            breakthrough_cnt += 1
        if ttype == "payoff" and intensity >= 3:
            strong_payoff_cnt += 1
        if ttype == "seed":
            has_seed_selected = True
        if _is_main_payoff(t):
            has_main_payoff_selected = True
        ex_group = str((t.get("constraints") or {}).get("exclusive_group") or "").strip()
        if ex_group:
            exclusive_group_count[ex_group] = int(exclusive_group_count.get(ex_group, 0)) + 1

    # require types swap
    for need in list(require_task_types):
        if need == "cliff" and require_cliff_int2:
            if any(str(x.get("type") or "") == "cliff" and int(x.get("intensity") or 1) >= 2 for x in selected):
                continue
            cand = next(
                (
                    x
                    for x in scored
                    if str(x.get("type") or "") == "cliff"
                    and int(x.get("intensity") or 1) >= 2
                    and not any(str(y.get("task_id")) == str(x.get("task_id")) for y in selected)
                ),
                None,
            )
        else:
            if any(str(x.get("type") or "") == need for x in selected):
                continue
            cand = next((x for x in scored if str(x.get("type") or "") == need and not any(str(y.get("task_id")) == str(x.get("task_id")) for y in selected)), None)
        if not cand:
            continue
        evict_candidates = [x for x in selected if not bool(x.get("must_happen"))]
        if not evict_candidates:
            continue
        evict_candidates.sort(key=lambda x: float(x.get("_score") or 0.0))
        evict = evict_candidates[0]
        new_weight = structure_weight_sum - int(evict.get("structure_weight") or 1) + int(cand.get("structure_weight") or 1)
        if new_weight > int(limits_eff["max_structure_weight"]):
            continue
        selected = [x for x in selected if str(x.get("task_id")) != str(evict.get("task_id"))]
        selected.append(cand)
        structure_weight_sum = new_weight
        dropped.append({"task_id": str(evict.get("task_id")), "type": str(evict.get("type") or ""), "reason": f"swap_for_required_{need}"})

    if require_reinterpret and not any(str((x.get("meta") or {}).get("combo_step") or "") == "reinterpret" for x in selected):
        cand_re = next(
            (
                x
                for x in scored
                if str((x.get("meta") or {}).get("combo_step") or "") == "reinterpret"
                and not any(str(y.get("task_id")) == str(x.get("task_id")) for y in selected)
            ),
            None,
        )
        if cand_re:
            evict_candidates = [x for x in selected if not bool(x.get("must_happen"))]
            evict_candidates.sort(key=lambda x: float(x.get("_score") or 0.0))
            if evict_candidates:
                ev = evict_candidates[0]
                new_weight = structure_weight_sum - int(ev.get("structure_weight") or 1) + int(cand_re.get("structure_weight") or 1)
                if new_weight <= int(limits_eff["max_structure_weight"]):
                    selected = [x for x in selected if str(x.get("task_id")) != str(ev.get("task_id"))]
                    selected.append(cand_re)
                    structure_weight_sum = new_weight
                    dropped.append({"task_id": str(ev.get("task_id")), "type": str(ev.get("type") or ""), "reason": "swap_for_required_reinterpret"})

    selected.sort(key=lambda x: float(x.get("_score") or 0.0), reverse=True)
    final_tasks = []
    for t in selected:
        final_tasks.append(
            {
                "task_id": str(t.get("task_id")),
                "type": str(t.get("type") or ""),
                "source": str(t.get("source") or ""),
                "must_happen": bool(t.get("must_happen")),
                "priority": int(t.get("priority") or 3),
                "intensity": int(t.get("intensity") or 1),
                "structure_weight": int(t.get("structure_weight") or 1),
                "defer_count": int(t.get("defer_count") or 0),
                "target_window": t.get("target_window") if isinstance(t.get("target_window"), dict) else {"min": 0.0, "max": 1.0},
                "refs": t.get("refs") if isinstance(t.get("refs"), dict) else {},
                "constraints": t.get("constraints") if isinstance(t.get("constraints"), dict) else {},
                "combo": t.get("combo") if isinstance(t.get("combo"), dict) else {},
                "meta": t.get("meta") if isinstance(t.get("meta"), dict) else {},
            }
        )
    return {
        "final_tasks": final_tasks,
        "deferred_tasks": deferred_tasks,
        "dropped_tasks": dropped,
        "structure_weight": structure_weight_sum,
        "orchestrator_explain": {
            "limits_eff": limits_eff,
            "required_types": sorted(list(require_task_types)),
            "require_reinterpret": require_reinterpret,
            "require_cliff_int2": require_cliff_int2,
            "weight_sum": structure_weight_sum,
            "conflicts": sorted(list(set(conflict_reasons))),
            "selected_scores": [
                {
                    "task_id": str(t.get("task_id")),
                    "type": str(t.get("type") or ""),
                    "score": round(float(t.get("_score") or 0.0), 4),
                    "breakdown": t.get("_score_breakdown") if isinstance(t.get("_score_breakdown"), dict) else {},
                }
                for t in selected
            ],
            "merge_count": sum(1 for t in selected if isinstance(t.get("meta"), dict) and isinstance((t.get("meta") or {}).get("merged_from"), list)),
            "replay_filtered_count": len(replay_filtered),
        },
        "orchestrator_limits_eff": limits_eff,
    }


def _workflow_rule_quality_report(ctx: dict) -> dict:
    text_value = str(((ctx.get("llm_output") or {}).get("text")) or "")
    structure = ctx.get("structure") if isinstance(ctx.get("structure"), dict) else {}
    score = 0.45 + min(0.35, len(text_value) / 6000.0)
    score += float(structure.get("conflict") or 0.0) * 0.1
    score += float(structure.get("closure") or 0.0) * 0.05
    return {
        "quality_report": {
            "overall": round(_clamp01(score), 6),
            "length_chars": len(text_value),
            "phase": str(ctx.get("phase") or "phase_setup"),
        }
    }


def _workflow_rule_post_extract_actions(ctx: dict) -> dict:
    llm_obj = ctx.get("llm_output") if isinstance(ctx.get("llm_output"), dict) else {}
    events_json = llm_obj.get("events_json")
    if not isinstance(events_json, dict):
        raise RuntimeError("EVENTS_JSON_MISSING_IN_LLM_OUTPUT")
    normalized = _workflow_validate_events_json(events_json)
    return {"extracted_actions": normalized}


def _workflow_rule_validate_executed_tasks(ctx: dict) -> dict:
    extracted = ctx.get("extracted_actions") if isinstance(ctx.get("extracted_actions"), dict) else {}
    final_tasks = [x for x in (ctx.get("final_tasks") if isinstance(ctx.get("final_tasks"), list) else []) if isinstance(x, dict)]
    task_by_id = {str(x.get("task_id") or ""): x for x in final_tasks if str(x.get("task_id") or "")}
    valid_rows: list[dict] = []
    dropped_rows: list[dict] = []
    for row in (extracted.get("executed_tasks") if isinstance(extracted.get("executed_tasks"), list) else []):
        if not isinstance(row, dict):
            continue
        task_id = str(row.get("task_id") or "").strip()
        if not task_id or task_id not in task_by_id:
            dropped_rows.append({"task_id": task_id, "reason": "task_not_in_final_tasks"})
            continue
        base = task_by_id[task_id]
        combo = base.get("combo") if isinstance(base.get("combo"), dict) else {}
        meta = base.get("meta") if isinstance(base.get("meta"), dict) else {}
        step_fallback = str(combo.get("step") or meta.get("combo_step") or "").strip().lower()
        fp_fallback = str(combo.get("combo_fp") or meta.get("combo_fp") or "").strip()
        valid_rows.append(
            {
                "task_id": task_id,
                "type": str(row.get("type") or base.get("type") or "").strip().lower(),
                "combo_fp": str(row.get("combo_fp") or fp_fallback),
                "step": str(row.get("step") or step_fallback).strip().lower(),
                "evidence": str(row.get("evidence") or "").strip()[:280],
            }
        )
    extracted_out = dict(extracted)
    extracted_out["executed_tasks"] = valid_rows
    alerts = []
    if dropped_rows:
        alerts.append({"code": "EXECUTED_TASKS_DROPPED", "count": len(dropped_rows), "items": dropped_rows[:20]})
    return {
        "extracted_actions": extracted_out,
        "executed_tasks_valid": valid_rows,
        "executed_tasks_dropped": dropped_rows,
        "executed_tasks_alerts": alerts,
    }


def _workflow_rule_update_reader_state(ctx: dict) -> dict:
    structure = ctx.get("structure") if isinstance(ctx.get("structure"), dict) else {}
    extracted = ctx.get("extracted_actions") if isinstance(ctx.get("extracted_actions"), dict) else {}
    growth_events = extracted.get("growth_events") if isinstance(extracted.get("growth_events"), list) else []
    growth_action = "achieve" if any(str(x.get("action") or "") == "achieve" for x in growth_events if isinstance(x, dict)) else "advance"
    foreshadow_events = extracted.get("foreshadow_events") if isinstance(extracted.get("foreshadow_events"), list) else []
    payoff_intensity = 0
    for ev in foreshadow_events:
        if not isinstance(ev, dict):
            continue
        if str(ev.get("event_type") or "") == "payoff":
            payoff_intensity = max(payoff_intensity, int(ev.get("intensity") or 1))
    cliff_obj = extracted.get("cliff") if isinstance(extracted.get("cliff"), dict) else {}
    reveal_obj = extracted.get("reveal") if isinstance(extracted.get("reveal"), dict) else {}
    reader_state = _update_reader_state(
        prev=(ctx.get("reader_state") if isinstance(ctx.get("reader_state"), dict) else None),
        structure=structure,
        structure_weight=int(ctx.get("structure_weight") or 0),
        cliff_present=bool(cliff_obj.get("present")),
        growth_action=growth_action,
        payoff_intensity=payoff_intensity,
        unresolved_foreshadow_ratio=0.5,
        reveal_ratio=float(reveal_obj.get("ratio") or structure.get("reveal") or 0.0),
        over_twist=0.0,
    )
    return {"reader_state_next": reader_state}


def _workflow_rule_execute(fn_name: str, ctx: dict) -> dict:
    if fn_name == "compute_progress_and_curves_v1":
        return _workflow_rule_compute_progress_and_curves(ctx)
    if fn_name == "build_candidate_tasks_v1":
        return _workflow_rule_build_candidate_tasks(ctx)
    if fn_name == "combo_executor_v1":
        return _workflow_rule_combo_executor(ctx)
    if fn_name == "chapter_orchestrator_v1":
        return _workflow_rule_orchestrator(ctx)
    if fn_name == "pacing_controller_v1":
        return _workflow_rule_pacing_controller(ctx)
    if fn_name == "task_intent_mapper_v1":
        return _workflow_rule_task_intent_mapper(ctx)
    if fn_name == "quality_report_v1":
        return _workflow_rule_quality_report(ctx)
    if fn_name == "post_extract_actions_v1":
        return _workflow_rule_post_extract_actions(ctx)
    if fn_name == "validate_executed_tasks_v1":
        return _workflow_rule_validate_executed_tasks(ctx)
    if fn_name == "update_reader_state_v1":
        return _workflow_rule_update_reader_state(ctx)
    raise RuntimeError("RULE_FN_NOT_FOUND")


async def _workflow_sql_execute(query_id: str, ctx: dict, db: AsyncSession) -> dict:
    sql_file = WORKFLOW_SQL_FILES.get(query_id)
    if sql_file:
        sql_path = Path(__file__).resolve().parent / "workflow" / "sql" / sql_file
        if sql_path.exists():
            sql_text = sql_path.read_text(encoding="utf-8")
            res = await db.execute(text(sql_text), {"ctx": json.dumps(ctx, ensure_ascii=False)})
            row = res.mappings().first()
            data = row.get("data") if row is not None else None
            if not isinstance(data, dict):
                data = {}
            if query_id in {"draft.commit_all", "draft.write_audit_snapshot"}:
                await db.commit()
            return data

    if query_id == "draft.resolve_chapter":
        chapter_id = str(ctx.get("chapter_id") or "").strip()
        book_id = str(ctx.get("book_id") or "").strip()
        chapter_no = int(ctx.get("chapter_no") or 0)
        row = None
        if chapter_id:
            res = await db.execute(
                text(
                    """
                    SELECT c.chapter_id::text AS chapter_id, c.book_id::text AS book_id, c."order" AS chapter_no, c.title AS chapter_title
                    FROM chapter c
                    WHERE c.chapter_id=CAST(:chapter_id AS uuid)
                    LIMIT 1
                    """
                ),
                {"chapter_id": chapter_id},
            )
            row = res.mappings().first()
        else:
            if not book_id or chapter_no <= 0:
                raise RuntimeError("chapter_id or (book_id+chapter_no) required")
            res = await db.execute(
                text(
                    """
                    SELECT c.chapter_id::text AS chapter_id, c.book_id::text AS book_id, c."order" AS chapter_no, c.title AS chapter_title
                    FROM chapter c
                    WHERE c.book_id=CAST(:book_id AS uuid) AND c."order"=:chapter_no
                    LIMIT 1
                    """
                ),
                {"book_id": book_id, "chapter_no": chapter_no},
            )
            row = res.mappings().first()
        if not row:
            raise RuntimeError("CHAPTER_NOT_FOUND")
        book_id = str(row.get("book_id"))
        chapter_no = int(row.get("chapter_no") or 1)
        max_res = await db.execute(
            text("SELECT COALESCE(MAX(\"order\"), 1) AS max_order FROM chapter WHERE book_id=CAST(:book_id AS uuid)"),
            {"book_id": book_id},
        )
        max_order = max(1, int((max_res.mappings().first() or {}).get("max_order") or 1))
        vol_res = await db.execute(
            text(
                """
                SELECT volume_id::text AS volume_id, start_chapter_no, end_chapter_no
                FROM volume
                WHERE book_id=CAST(:book_id AS uuid)
                  AND :chapter_no BETWEEN start_chapter_no AND end_chapter_no
                ORDER BY volume_no
                LIMIT 1
                """
            ),
            {"book_id": book_id, "chapter_no": chapter_no},
        )
        vol = vol_res.mappings().first() or {}
        start_no = int(vol.get("start_chapter_no") or chapter_no)
        end_no = int(vol.get("end_chapter_no") or max(chapter_no, start_no))
        p_vol = _clamp01(
            0.0
            if end_no <= start_no
            else float(chapter_no - start_no) / float(max(1, (end_no - start_no)))
        )
        return {
            "chapter_id": str(row.get("chapter_id")),
            "book_id": book_id,
            "chapter_no": chapter_no,
            "chapter_title": str(row.get("chapter_title") or ""),
            "planned_book_chapters": max_order,
            "volume_id": str(vol.get("volume_id")) if vol.get("volume_id") else None,
            "volume_start_chapter_no": start_no,
            "volume_end_chapter_no": end_no,
            "p_book": round(_clamp01(float(chapter_no) / float(max_order)), 6),
            "p_vol": round(p_vol, 6),
        }

    if query_id == "draft.load_context":
        chapter_id = str(ctx.get("chapter_id") or "").strip()
        if not chapter_id:
            raise RuntimeError("CHAPTER_REQUIRED")
        res = await db.execute(
            text(
                """
                SELECT b.book_id::text AS book_id, b.title AS book_title, c.title AS chapter_title
                FROM chapter c
                JOIN book b ON b.book_id=c.book_id
                WHERE c.chapter_id=CAST(:chapter_id AS uuid)
                LIMIT 1
                """
            ),
            {"chapter_id": chapter_id},
        )
        row = res.mappings().first()
        if not row:
            raise RuntimeError("CHAPTER_NOT_FOUND")
        recent = await db.execute(
            text(
                """
                SELECT "order" AS chapter_no, title
                FROM chapter
                WHERE book_id=CAST(:book_id AS uuid) AND "order" < :chapter_no
                ORDER BY "order" DESC
                LIMIT 3
                """
            ),
            {"book_id": str(row.get("book_id")), "chapter_no": int(ctx.get("chapter_no") or 1)},
        )
        book_settings = await get_book_settings(db, str(row.get("book_id"))) or {}
        reader_state = await _load_latest_reader_state(db, book_id=str(row.get("book_id")))
        outline_row = await db.execute(
            text(
                """
                SELECT version, content
                FROM outline
                WHERE chapter_id=CAST(:chapter_id AS uuid)
                  AND scope='chapter'
                ORDER BY version DESC, created_at DESC
                LIMIT 1
                """
            ),
            {"chapter_id": chapter_id},
        )
        outline_hit = outline_row.mappings().first()
        outline_content = outline_hit.get("content") if outline_hit and isinstance(outline_hit.get("content"), dict) else {}
        outline_nodes_raw = outline_content.get("nodes") if isinstance(outline_content.get("nodes"), list) else []
        outline_nodes: list[dict] = []
        for n in outline_nodes_raw[:20]:
            if not isinstance(n, dict):
                continue
            outline_nodes.append(
                {
                    "node_id": str(n.get("node_id") or ""),
                    "type": str(n.get("type") or ""),
                    "summary": str(n.get("summary") or "")[:180],
                }
            )
        return {
            "context": {
                "book_title": str(row.get("book_title") or ""),
                "chapter_title": str(row.get("chapter_title") or ""),
                "recent_chapters": [dict(x) for x in recent.mappings().all()],
            },
            "book_settings": book_settings if isinstance(book_settings, dict) else {},
            "chapter_outline": {
                "version": int((outline_hit or {}).get("version") or 0),
                "chapter_title": str(outline_content.get("chapter_title") or ""),
                "nodes": outline_nodes,
            },
            "reader_state": reader_state,
        }

    if query_id == "draft.load_plan_combos":
        volume_id = str(ctx.get("volume_id") or "").strip()
        book_id = str(ctx.get("book_id") or "").strip()
        chapter_no = int(ctx.get("chapter_no") or 0)
        plan: dict = {}
        items: list[dict] = []
        injections: list[dict] = []
        if volume_id:
            plan_res = await db.execute(
                text(
                    """
                    SELECT vol_plan_id::text AS vol_plan_id, version, assumptions
                    FROM volume_plan
                    WHERE volume_id=CAST(:volume_id AS uuid) AND status='active'
                    ORDER BY version DESC
                    LIMIT 1
                    """
                ),
                {"volume_id": volume_id},
            )
            p = plan_res.mappings().first()
            if p:
                plan = dict(p)
                item_res = await db.execute(
                    text(
                        """
                        SELECT item_id::text AS item_id, kind, summary, target_window,
                               target_p_vol_min::double precision AS target_p_vol_min,
                               target_p_vol_max::double precision AS target_p_vol_max,
                               priority, must_happen, meta
                        FROM volume_plan_item
                        WHERE vol_plan_id=CAST(:vol_plan_id AS uuid)
                        ORDER BY priority DESC, created_at
                        """
                    ),
                    {"vol_plan_id": str(p.get("vol_plan_id"))},
                )
                items = [dict(r) for r in item_res.mappings().all()]
        if book_id:
            if chapter_no > 0:
                await db.execute(
                    text(
                        """
                        UPDATE combo_injection
                        SET status='expired'
                        WHERE book_id=CAST(:book_id AS uuid)
                          AND status='pending'
                          AND expires_after_chapter_no IS NOT NULL
                          AND expires_after_chapter_no < :chapter_no
                        """
                    ),
                    {"book_id": book_id, "chapter_no": chapter_no},
                )
            inj_res = await db.execute(
                text(
                    """
                    SELECT inj_id::text AS inj_id, combo_type, window_next_chapters, priority, volume_id::text AS volume_id,
                           status, expires_after_chapter_no
                    FROM combo_injection
                    WHERE book_id=CAST(:book_id AS uuid)
                      AND status='pending'
                      AND (volume_id IS NULL OR volume_id=CAST(:volume_id AS uuid))
                    ORDER BY created_at DESC
                    """
                ),
                {"book_id": book_id, "volume_id": volume_id or None},
            )
            injections = [dict(r) for r in inj_res.mappings().all()]
        settings_obj = ctx.get("book_settings") if isinstance(ctx.get("book_settings"), dict) else {}
        orch = settings_obj.get("orchestrator") if isinstance(settings_obj.get("orchestrator"), dict) else {}
        state_orch: dict = {}
        if book_id:
            bs = await db.execute(
                text("SELECT orchestrator_limits FROM book_state WHERE book_id=CAST(:book_id AS uuid) LIMIT 1"),
                {"book_id": book_id},
            )
            bs_row = bs.mappings().first()
            state_orch = bs_row.get("orchestrator_limits") if bs_row and isinstance(bs_row.get("orchestrator_limits"), dict) else {}
        return {
            "volume_plan": plan,
            "volume_plan_items": items,
            "combo_injections": injections,
            "orchestrator_limits": {
                "max_structure_weight": int((state_orch.get("max_structure_weight") if isinstance(state_orch, dict) else None) or orch.get("max_structure_weight") or 4),
                "max_tasks_per_chapter": int((state_orch.get("max_tasks_per_chapter") if isinstance(state_orch, dict) else None) or (state_orch.get("max_tasks") if isinstance(state_orch, dict) else None) or orch.get("max_tasks_per_chapter") or 3),
                "ban_strong_cliff": bool((state_orch.get("ban_strong_cliff") if isinstance(state_orch, dict) else None) if isinstance(state_orch.get("ban_strong_cliff"), bool) else bool(orch.get("ban_strong_cliff"))),
            },
        }

    if query_id == "draft.commit_all":
        if bool(ctx.get("dry_run")):
            return {"commit_result": {"dry_run": True}}
        chapter_id = str(ctx.get("chapter_id") or "").strip()
        book_id = str(ctx.get("book_id") or "").strip()
        if not chapter_id or not book_id:
            raise RuntimeError("CHAPTER_OR_BOOK_MISSING")
        llm_obj = ctx.get("llm_output") if isinstance(ctx.get("llm_output"), dict) else {}
        content = str(llm_obj.get("chapter_text") or llm_obj.get("text") or "").strip()
        if not content:
            raise RuntimeError("EMPTY_DRAFT_CONTENT")
        events_json = llm_obj.get("events_json")
        if not isinstance(events_json, dict):
            raise RuntimeError("EVENTS_JSON_REQUIRED_BEFORE_COMMIT")
        before_res = await db.execute(
            text("SELECT COUNT(*) AS c FROM chapter_text_version WHERE chapter_id=CAST(:chapter_id AS uuid)"),
            {"chapter_id": chapter_id},
        )
        before_count = int((before_res.mappings().first() or {}).get("c") or 0)
        ins = await db.execute(
            text(
                """
                INSERT INTO chapter_text_version(chapter_id, outline_version, source, content, note, meta)
                VALUES (
                  CAST(:chapter_id AS uuid),
                  :outline_version,
                  :source,
                  :content,
                  :note,
                  CAST(:meta AS jsonb)
                )
                RETURNING text_ver_id::text AS text_ver_id
                """
            ),
            {
                "chapter_id": chapter_id,
                "outline_version": 1,
                "source": "workflow_draft",
                "content": content,
                "note": "draft_runner_v1",
                "meta": json.dumps(
                    {
                        "workflow_run_id": str(ctx.get("run_id") or ""),
                        "workflow_id": "draft_runner_v1",
                        "structure": ctx.get("structure") if isinstance(ctx.get("structure"), dict) else {},
                        "phase": str(ctx.get("phase") or ""),
                        "final_tasks": ctx.get("final_tasks") if isinstance(ctx.get("final_tasks"), list) else [],
                        "events_json": events_json,
                        "orchestrator_explain": ctx.get("orchestrator_explain") if isinstance(ctx.get("orchestrator_explain"), dict) else {},
                    },
                    ensure_ascii=False,
                ),
            },
        )
        text_ver_id = str((ins.mappings().first() or {}).get("text_ver_id") or "")
        after_res = await db.execute(
            text("SELECT COUNT(*) AS c FROM chapter_text_version WHERE chapter_id=CAST(:chapter_id AS uuid)"),
            {"chapter_id": chapter_id},
        )
        after_count = int((after_res.mappings().first() or {}).get("c") or 0)
        consumed_injection_ids: list[str] = []
        for ft in (ctx.get("final_tasks") if isinstance(ctx.get("final_tasks"), list) else []):
            if not isinstance(ft, dict):
                continue
            refs = ft.get("refs") if isinstance(ft.get("refs"), dict) else {}
            inj_id = str(refs.get("inj_id") or "").strip()
            if not inj_id:
                continue
            await db.execute(
                text(
                    """
                    UPDATE combo_injection
                    SET status='consumed', consumed_chapter_id=CAST(:chapter_id AS uuid), consumed_at=now()
                    WHERE inj_id=CAST(:inj_id AS uuid) AND status='pending'
                    """
                ),
                {"inj_id": inj_id, "chapter_id": chapter_id},
            )
            consumed_injection_ids.append(inj_id)
        await db.commit()
        return {
            "commit_result": {
                "dry_run": False,
                "text_ver_id": text_ver_id,
                "chapter_id": chapter_id,
                "book_id": book_id,
                "consumed_injection_ids": consumed_injection_ids,
            },
            "audit_before_state": {"chapter_text_version_count": before_count},
            "audit_after_state": {"chapter_text_version_count": after_count, "created_text_ver_id": text_ver_id},
            "audit_diff": [{"op": "inc", "path": "/chapter_text_version_count", "from": before_count, "to": after_count}],
        }

    if query_id == "draft.write_audit_snapshot":
        if bool(ctx.get("dry_run")):
            return {"audit_result": {"dry_run": True}}
        book_id = str(ctx.get("book_id") or "").strip()
        chapter_id = str(ctx.get("chapter_id") or "").strip()
        run_id = str(ctx.get("run_id") or "").strip()
        before_state = ctx.get("audit_before_state") if isinstance(ctx.get("audit_before_state"), dict) else {}
        after_state = ctx.get("audit_after_state") if isinstance(ctx.get("audit_after_state"), dict) else {}
        diff = ctx.get("audit_diff") if isinstance(ctx.get("audit_diff"), list) else []
        if not book_id:
            raise RuntimeError("BOOK_ID_MISSING")
        ins = await db.execute(
            text(
                """
                INSERT INTO state_apply_audit(book_id, chapter_id, run_id, action_type, before_state, after_state, diff, reason)
                VALUES (
                  CAST(:book_id AS uuid),
                  CAST(:chapter_id AS uuid),
                  CAST(:run_id AS uuid),
                  'draft_commit',
                  CAST(:before_state AS jsonb),
                  CAST(:after_state AS jsonb),
                  CAST(:diff AS jsonb),
                  :reason
                )
                RETURNING audit_id::text AS audit_id
                """
            ),
            {
                "book_id": book_id,
                "chapter_id": chapter_id or None,
                "run_id": run_id or None,
                "before_state": json.dumps(before_state, ensure_ascii=False),
                "after_state": json.dumps(after_state, ensure_ascii=False),
                "diff": json.dumps(diff, ensure_ascii=False),
                "reason": "workflow commit snapshot",
            },
        )
        await db.commit()
        return {"audit_result": {"audit_id": str((ins.mappings().first() or {}).get("audit_id") or "")}}

    raise RuntimeError("QUERY_ID_NOT_FOUND")


def _workflow_parse_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    raw = str(value).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def _workflow_parse_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = int(default)
    return max(low, min(high, parsed))


async def _workflow_load_memory_conflict_card(
    db: AsyncSession,
    *,
    book_id: str,
    chapter_id: str,
    chapter_no: int,
) -> dict[str, Any]:
    params: dict[str, Any] = {"book_id": book_id}
    cond = ""
    if chapter_id:
        cond = "AND chapter_id=CAST(:chapter_id AS uuid)"
        params["chapter_id"] = chapter_id
    elif chapter_no > 0:
        cond = "AND chapter_no=:chapter_no"
        params["chapter_no"] = chapter_no
    else:
        return {}
    row = (
        await db.execute(
            text(
                f"""
                SELECT payload
                FROM chapter_scene_pack
                WHERE book_id=CAST(:book_id AS uuid) {cond}
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            params,
        )
    ).mappings().first()
    payload = row.get("payload") if row and isinstance(row.get("payload"), dict) else {}
    return payload.get("conflict_card") if isinstance(payload.get("conflict_card"), dict) else {}


async def _workflow_load_overdue_foreshadow_seeds(
    db: AsyncSession,
    *,
    book_id: str,
    chapter_no: int,
    limit: int = 8,
) -> list[dict[str, Any]]:
    if chapter_no <= 0:
        return []
    lim = _workflow_parse_int(limit, 8, 1, 20)
    rows = (
        await db.execute(
            text(
                """
                SELECT
                  f.foreshadow_id::text AS foreshadow_id,
                  f.title,
                  cp."order" AS planned_chapter_no
                FROM foreshadow f
                JOIN chapter cp ON cp.chapter_id=f.planned_payoff_chapter_id
                WHERE f.book_id=CAST(:book_id AS uuid)
                  AND f.status IN ('seeded', 'reinforced', 'payoff_planned')
                  AND cp."order" <= :chapter_no
                ORDER BY cp."order" ASC, f.priority DESC, f.updated_at DESC
                LIMIT :limit
                """
            ),
            {"book_id": book_id, "chapter_no": chapter_no, "limit": lim},
        )
    ).mappings().all()
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        title = str((row or {}).get("title") or "").strip()
        if not title:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "foreshadow_id": str((row or {}).get("foreshadow_id") or ""),
                "title": title[:80],
                "planned_chapter_no": int((row or {}).get("planned_chapter_no") or 0),
            }
        )
    return out


def _workflow_build_memory_focus_instruction(
    *,
    chapter_goal: str,
    conflict_label: str,
    upgrade_method: str,
    cliffhanger: str,
    task_types: list[str],
    overdue_titles: list[str],
) -> str:
    parts: list[str] = []
    if chapter_goal:
        parts.append(f"本章目标是{chapter_goal}")
    if conflict_label:
        parts.append(f"冲突主轴为{conflict_label}")
    if upgrade_method:
        parts.append(f"冲突升级方式为{upgrade_method}")
    if cliffhanger:
        parts.append(f"章末钩子需指向{cliffhanger}")
    if task_types:
        parts.append(f"关键任务包含{'/'.join(task_types[:6])}")
    if overdue_titles:
        parts.append(f"优先处理到期伏笔：{'、'.join(overdue_titles[:4])}")
    if not parts:
        return ""
    text_value = "；".join(parts)
    if not text_value.endswith("。"):
        text_value += "。"
    return text_value[:320]


def _workflow_compose_prompt(ctx: dict, template_id: str) -> dict:
    if template_id not in {"prompt.draft_runner_v1", "prompt.draft_runner_v2"}:
        raise RuntimeError("PROMPT_TEMPLATE_NOT_FOUND")
    context = ctx.get("context") if isinstance(ctx.get("context"), dict) else {}
    settings_obj = ctx.get("book_settings") if isinstance(ctx.get("book_settings"), dict) else {}
    draft_cfg = settings_obj.get("draft") if isinstance(settings_obj.get("draft"), dict) else {}
    min_chars = int(draft_cfg.get("min_chars") or 3000)
    min_chars = max(800, min(12000, min_chars))
    character_facts = ctx.get("character_facts") if isinstance(ctx.get("character_facts"), list) else []
    timeline_facts = ctx.get("timeline_facts") if isinstance(ctx.get("timeline_facts"), list) else []
    open_foreshadows = ctx.get("open_foreshadows") if isinstance(ctx.get("open_foreshadows"), list) else []
    growth_milestones = ctx.get("growth_milestones") if isinstance(ctx.get("growth_milestones"), list) else []
    chapter_outline = ctx.get("chapter_outline") if isinstance(ctx.get("chapter_outline"), dict) else {}
    chapter_outline_nodes = chapter_outline.get("nodes") if isinstance(chapter_outline.get("nodes"), list) else []
    cfg_budget = ctx.get("orchestrator_context_budget") if isinstance(ctx.get("orchestrator_context_budget"), dict) else {}
    memory_pack = ctx.get("writing_memory_pack") if isinstance(ctx.get("writing_memory_pack"), dict) else {}
    memory_layers = memory_pack.get("memory_layers") if isinstance(memory_pack.get("memory_layers"), dict) else {}
    memory_meta = memory_layers.get("meta") if isinstance(memory_layers.get("meta"), dict) else {}
    memory_hot = memory_layers.get("hot") if isinstance(memory_layers.get("hot"), dict) else {}
    memory_context_obj = memory_pack.get("context_assembled") if isinstance(memory_pack.get("context_assembled"), dict) else {}
    memory_context_text = str(memory_context_obj.get("context_text") or "").strip()
    if len(memory_context_text) > 9000:
        memory_context_text = memory_context_text[:9000]
    memory_instruction = str(memory_context_obj.get("instruction") or "").strip()
    memory_token_est = int(memory_context_obj.get("token_est") or 0)
    memory_session_key = str(memory_meta.get("session_key") or memory_hot.get("session_key") or "")
    memory_hard_constraints = [
        str(x).strip()
        for x in (memory_context_obj.get("hard_constraints") if isinstance(memory_context_obj.get("hard_constraints"), list) else [])
        if str(x).strip()
    ][:16]

    def _truncate_items(items: list, max_items: int, max_chars: int) -> tuple[list, dict]:
        seq = [x for x in items if isinstance(x, dict)]
        serialized = [json.dumps(x, ensure_ascii=False) for x in seq]
        input_chars = sum(len(s) for s in serialized)
        kept: list[dict] = []
        kept_chars = 0
        for i, raw in enumerate(serialized):
            if len(kept) >= max_items:
                break
            if kept_chars + len(raw) > max_chars:
                break
            kept.append(seq[i])
            kept_chars += len(raw)
        stats = {
            "input_items": len(seq),
            "kept_items": len(kept),
            "max_items": max_items,
            "max_chars": max_chars,
            "input_chars": input_chars,
            "kept_chars": kept_chars,
            "truncated_items": max(0, len(seq) - len(kept)),
            "truncated_chars": max(0, input_chars - kept_chars),
        }
        return kept, stats

    def _budget_pair(name: str, default_items: int, default_chars: int) -> tuple[int, int]:
        row = cfg_budget.get(name) if isinstance(cfg_budget.get(name), dict) else {}
        max_items = max(1, min(20, int(row.get("max_items") or default_items)))
        max_chars = max(120, min(6000, int(row.get("max_chars") or default_chars)))
        return max_items, max_chars

    c_items, c_chars = _budget_pair("character_facts", 8, 1000)
    t_items, t_chars = _budget_pair("timeline_facts", 8, 1000)
    f_items, f_chars = _budget_pair("open_foreshadows", 6, 900)
    g_items, g_chars = _budget_pair("growth_milestones", 6, 900)
    o_items, o_chars = _budget_pair("chapter_outline_nodes", 8, 1200)

    char_compact, char_budget = _truncate_items(character_facts, c_items, c_chars)
    timeline_compact, timeline_budget = _truncate_items(timeline_facts, t_items, t_chars)
    foreshadow_compact, foreshadow_budget = _truncate_items(open_foreshadows, f_items, f_chars)
    growth_compact, growth_budget = _truncate_items(growth_milestones, g_items, g_chars)
    outline_compact, outline_budget = _truncate_items(chapter_outline_nodes, o_items, o_chars)
    context_budget = {
        "character_facts": char_budget,
        "timeline_facts": timeline_budget,
        "open_foreshadows": foreshadow_budget,
        "growth_milestones": growth_budget,
        "chapter_outline_nodes": outline_budget,
    }
    structure = ctx.get("structure") if isinstance(ctx.get("structure"), dict) else {}
    p_book = _clamp01(float(ctx.get("p_book") or structure.get("progress") or 0.0))
    p_vol = _clamp01(float(ctx.get("p_vol") or 0.0))
    final_tasks = ctx.get("final_tasks") if isinstance(ctx.get("final_tasks"), list) else []
    final_tasks_intent = ctx.get("final_tasks_intent") if isinstance(ctx.get("final_tasks_intent"), list) else final_tasks
    pacer = ctx.get("pacer") if isinstance(ctx.get("pacer"), dict) else {}
    intent = str(ctx.get("intent_confirmed") or "延续章节目标，保持连贯")
    if memory_instruction:
        intent = memory_instruction
    recent_chapters = context.get("recent_chapters") if isinstance(context.get("recent_chapters"), list) else []
    recent_summary = "；".join(
        [
            f"#{int(x.get('chapter_no') or 0)} {str(x.get('title') or '').strip()}"
            for x in recent_chapters[:3]
            if isinstance(x, dict)
        ]
    ) or "无"
    limits_eff = ctx.get("orchestrator_limits_eff") if isinstance(ctx.get("orchestrator_limits_eff"), dict) else {}
    final_structure_json = {
        "p_book": round(p_book, 6),
        "p_vol": round(p_vol, 6),
        "phase": str(ctx.get("phase") or "phase_setup"),
        "curves": {
            "conflict": round(_clamp01(float(structure.get("conflict") or 0.0)), 6),
            "reveal": round(_clamp01(float(structure.get("reveal") or 0.0)), 6),
            "tension": round(_clamp01(float(structure.get("tension") or 0.0)), 6),
            "growth": round(_clamp01(float(structure.get("growth") or 0.0)), 6),
            "closure": round(_clamp01(float(structure.get("closure") or 0.0)), 6),
        },
        "limits_eff": {
            "max_structure_weight": int(limits_eff.get("max_structure_weight") or 4),
            "max_tasks_per_chapter": int(limits_eff.get("max_tasks_per_chapter") or 3),
            "ban_strong_cliff": bool(limits_eff.get("ban_strong_cliff", False)),
        },
    }
    constraints = [
        "Keep continuity with CONTEXT facts.",
        "Use show-dont-tell and avoid meta commentary.",
        "If a task requires cost_shown, show cost on-screen.",
        "If a task requires choice_explicit, make choice explicit in dialogue or action.",
        "Respect ChapterOutlineJSON node order and intent when writing scene progression.",
        "Do not copy any source text; use original wording.",
        "Output exactly two sections: CHAPTER_TEXT and EVENTS_JSON.",
        f"CHAPTER_TEXT must be at least {min_chars} Chinese characters (excluding spaces).",
    ]
    for item in memory_hard_constraints:
        constraints.append(f"Memory hard constraint: {item}")
    schema = {
        "foreshadow_events": [{"foreshadow_id": "optional-uuid", "event_type": "seed|reinforce|payoff", "intensity": 1, "note": "short"}],
        "growth_events": [{"milestone_id": "optional-uuid", "action": "advance|achieve", "cost_shown": True, "choice_explicit": True, "note": "short"}],
        "cliff": {"present": True, "style": "question_end|interrupt_end", "note": "short"},
        "reveal": {"ratio": 0.4, "note": "short"},
        "executed_tasks": [{"task_id": "from_TASKS_JSON", "type": "task_type", "combo_fp": "optional", "step": "optional", "evidence": "short"}],
    }
    lines: list[str] = []
    lines.append("[SYS]")
    lines.append("You are writing a Chinese web novel chapter. Follow TASKS_JSON and CONSTRAINTS strictly.")
    lines.append("Do NOT copy source text. Keep style coherent.")
    lines.append("[/SYS]")
    lines.append("")
    lines.append("[CONTEXT]")
    lines.append(f"- Book: {str(context.get('book_title') or '')}")
    lines.append(f"- Chapter: {str(context.get('chapter_title') or '')}")
    lines.append(f"- ChapterNo: {int(ctx.get('chapter_no') or 0)}")
    lines.append(f"- Intent: {intent}")
    lines.append(f"- RecentSummary: {recent_summary}")
    lines.append(f"- CharacterFactsJSON: {json.dumps(char_compact, ensure_ascii=False)}")
    lines.append(f"- TimelineFactsJSON: {json.dumps(timeline_compact, ensure_ascii=False)}")
    lines.append(f"- OpenForeshadowsJSON: {json.dumps(foreshadow_compact, ensure_ascii=False)}")
    lines.append(f"- GrowthMilestonesJSON: {json.dumps(growth_compact, ensure_ascii=False)}")
    lines.append(
        f"- ChapterOutlineJSON: {json.dumps({'version': int(chapter_outline.get('version') or 0), 'chapter_title': str(chapter_outline.get('chapter_title') or ''), 'nodes': outline_compact}, ensure_ascii=False)}"
    )
    if memory_session_key:
        lines.append(f"- MemorySessionKey: {memory_session_key}")
    if memory_token_est > 0:
        lines.append(f"- MemoryTokenEst: {memory_token_est}")
    lines.append("[/CONTEXT]")
    lines.append("")
    if memory_context_text:
        lines.append("[MEMORY_CONTEXT]")
        lines.append(memory_context_text)
        lines.append("[/MEMORY_CONTEXT]")
        lines.append("")
    lines.append("[STRUCTURE_JSON]")
    lines.append(json.dumps(final_structure_json, ensure_ascii=False))
    lines.append("[/STRUCTURE_JSON]")
    lines.append("")
    lines.append("[PACER_JSON]")
    lines.append(json.dumps(pacer, ensure_ascii=False))
    lines.append("[/PACER_JSON]")
    lines.append("")
    lines.append("[TASKS_JSON]")
    lines.append(json.dumps(final_tasks[:6], ensure_ascii=False))
    lines.append("[/TASKS_JSON]")
    lines.append("")
    lines.append("[TASKS_INTENT_JSON]")
    lines.append(json.dumps(final_tasks_intent[:6], ensure_ascii=False))
    lines.append("[/TASKS_INTENT_JSON]")
    lines.append("")
    lines.append("[CONSTRAINTS]")
    for i, c in enumerate(constraints, start=1):
        lines.append(f"{i}) {c}")
    lines.append(f"{len(constraints)+1}) Satisfy evidence_required for each task in TASKS_INTENT_JSON.")
    lines.append(f"{len(constraints)+2}) Do not use any banned_moves from TASKS_INTENT_JSON.")
    lines.append("[/CONSTRAINTS]")
    lines.append("")
    lines.append("[OUTPUT_FORMAT]")
    lines.append("Return:")
    lines.append("A) CHAPTER_TEXT: chapter prose only.")
    lines.append("B) EVENTS_JSON: strict JSON object matching schema below.")
    lines.append(f"C) CHAPTER_TEXT minimum length: {min_chars} Chinese characters.")
    lines.append("No extra keys. No trailing text after EVENTS_JSON.")
    lines.append(json.dumps(schema, ensure_ascii=False))
    lines.append("[/OUTPUT_FORMAT]")
    lines.append("")
    lines.append("CHAPTER_TEXT:")
    return {
        "prompt": "\n".join(lines),
        "prompt_blocks": {
            "structure": final_structure_json,
            "tasks": final_tasks[:6],
            "tasks_intent": final_tasks_intent[:6],
            "pacer": pacer,
            "constraints": constraints,
            "context_budget": context_budget,
            "context_compact": {
                "character_facts": char_compact,
                "timeline_facts": timeline_compact,
                "open_foreshadows": foreshadow_compact,
                "growth_milestones": growth_compact,
                "chapter_outline_nodes": outline_compact,
            },
            "memory": {
                "enabled": bool(memory_context_text),
                "session_key": memory_session_key,
                "token_est": memory_token_est,
                "hard_constraints": memory_hard_constraints,
            },
        },
    }


def _workflow_validate_events_json(obj: dict) -> dict:
    if not isinstance(obj, dict):
        raise RuntimeError("EVENTS_JSON_INVALID_TYPE")
    required_top = {"foreshadow_events", "growth_events", "cliff", "reveal"}
    optional_top = {"executed_tasks"}
    allowed_top = required_top | optional_top
    unknown_top = [k for k in obj.keys() if k not in allowed_top]
    if unknown_top:
        raise RuntimeError(f"EVENTS_JSON_UNKNOWN_KEYS:{','.join(sorted(unknown_top))}")
    missing_top = [k for k in required_top if k not in obj]
    if missing_top:
        raise RuntimeError(f"EVENTS_JSON_MISSING_KEYS:{','.join(sorted(missing_top))}")
    out: dict[str, object] = {}
    fev_raw = obj.get("foreshadow_events")
    if fev_raw is None:
        fev_raw = []
    if not isinstance(fev_raw, list):
        raise RuntimeError("EVENTS_JSON_FORESHADOW_EVENTS_INVALID")
    fev: list[dict] = []
    for x in fev_raw:
        if not isinstance(x, dict):
            continue
        ev_type = str(x.get("event_type") or "").strip().lower()
        if ev_type not in {"seed", "reinforce", "payoff"}:
            continue
        fev.append(
            {
                "foreshadow_id": str(x.get("foreshadow_id") or "").strip() or None,
                "event_type": ev_type,
                "intensity": max(1, min(3, int(x.get("intensity") or 1))),
                "note": str(x.get("note") or "").strip()[:280],
            }
        )
    out["foreshadow_events"] = fev

    gev_raw = obj.get("growth_events")
    if gev_raw is None:
        gev_raw = []
    if not isinstance(gev_raw, list):
        raise RuntimeError("EVENTS_JSON_GROWTH_EVENTS_INVALID")
    gev: list[dict] = []
    for x in gev_raw:
        if not isinstance(x, dict):
            continue
        action = str(x.get("action") or "").strip().lower()
        if action not in {"advance", "achieve"}:
            continue
        gev.append(
            {
                "milestone_id": str(x.get("milestone_id") or "").strip() or None,
                "action": action,
                "cost_shown": bool(x.get("cost_shown", False)),
                "choice_explicit": bool(x.get("choice_explicit", False)),
                "note": str(x.get("note") or "").strip()[:280],
            }
        )
    out["growth_events"] = gev

    cliff_raw = obj.get("cliff")
    if cliff_raw is None:
        cliff_raw = {}
    if not isinstance(cliff_raw, dict):
        raise RuntimeError("EVENTS_JSON_CLIFF_INVALID")
    out["cliff"] = {
        "present": bool(cliff_raw.get("present", False)),
        "style": str(cliff_raw.get("style") or "question_end").strip()[:48],
        "note": str(cliff_raw.get("note") or "").strip()[:280],
    }

    reveal_raw = obj.get("reveal")
    if reveal_raw is None:
        reveal_raw = {}
    if not isinstance(reveal_raw, dict):
        raise RuntimeError("EVENTS_JSON_REVEAL_INVALID")
    out["reveal"] = {
        "ratio": _clamp01(float(reveal_raw.get("ratio") or 0.0)),
        "note": str(reveal_raw.get("note") or "").strip()[:280],
    }
    ex_raw = obj.get("executed_tasks")
    if ex_raw is None:
        ex_raw = []
    if not isinstance(ex_raw, list):
        raise RuntimeError("EVENTS_JSON_EXECUTED_TASKS_INVALID")
    executed_tasks: list[dict] = []
    for x in ex_raw:
        if not isinstance(x, dict):
            continue
        executed_tasks.append(
            {
                "task_id": str(x.get("task_id") or "").strip(),
                "type": str(x.get("type") or x.get("task_type") or "").strip().lower(),
                "combo_fp": str(x.get("combo_fp") or "").strip(),
                "step": str(x.get("step") or "").strip().lower(),
                "evidence": str(x.get("evidence") or "").strip()[:280],
            }
        )
    out["executed_tasks"] = executed_tasks
    return out


def _slugify_filename(value: str, fallback: str = "book") -> str:
    raw = str(value or "").strip().lower()
    raw = re.sub(r"[^a-z0-9\u4e00-\u9fff_-]+", "-", raw)
    raw = re.sub(r"-{2,}", "-", raw).strip("-")
    return raw or fallback


def _ensure_path_within(root: Path, target: Path) -> None:
    root_r = root.resolve()
    target_r = target.resolve()
    common = os.path.commonpath([str(root_r), str(target_r)])
    if common != str(root_r):
        raise HTTPException(status_code=400, detail="PATH_OUTSIDE_WORKSPACE")


def _write_text_file(path: Path, content: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path.stat().st_size


def _as_uuid_str_or_empty(value: object) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    try:
        return str(UUID(s))
    except Exception:
        return ""


def _preflight_render_markdown(report: dict) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    fail_items = report.get("fail") if isinstance(report.get("fail"), list) else []
    warn_items = report.get("warn") if isinstance(report.get("warn"), list) else []
    suggest_items = report.get("suggest") if isinstance(report.get("suggest"), list) else []
    ctx = report.get("context") if isinstance(report.get("context"), dict) else {}
    metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else {}
    notes = report.get("notes") if isinstance(report.get("notes"), list) else []
    note_hints = report.get("note_hints") if isinstance(report.get("note_hints"), list) else []

    def _line_item(x: dict) -> list[str]:
        code = str(x.get("code") or "")
        msg = str(x.get("message") or "")
        fix = str(x.get("fix") or "").strip()
        out = [f"- [{code}] {msg}"]
        if fix:
            out.append(f"  - Fix: {fix}")
        return out

    lines: list[str] = []
    lines.append("# Preflight Report")
    lines.append(
        f"book: {str(ctx.get('book_id') or '-')} | volume: {str(ctx.get('volume_label') or '-')} | generated: {datetime.now(timezone.utc).isoformat()}"
    )
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Overall: {str(summary.get('overall') or 'OK')}")
    lines.append(
        f"- FAIL: {int(summary.get('fail_count') or 0)}  |  WARN: {int(summary.get('warn_count') or 0)}  |  SUGGEST: {int(summary.get('suggest_count') or 0)}"
    )
    if metrics:
        lines.append(
            f"- Metrics: chapters={int(metrics.get('chapter_count') or 0)} | current_chapter={int(metrics.get('current_chapter_no') or 0)} | avg_fatigue={metrics.get('avg_fatigue')} | avg_clarity={metrics.get('avg_clarity')}"
        )
    lines.append("")

    lines.append("## FAIL")
    if fail_items:
        for item in fail_items:
            lines.extend(_line_item(item if isinstance(item, dict) else {"message": str(item)}))
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## WARN")
    if warn_items:
        for item in warn_items:
            lines.extend(_line_item(item if isinstance(item, dict) else {"message": str(item)}))
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## Suggest Rewrite")
    if suggest_items:
        for item in suggest_items:
            lines.extend(_line_item(item if isinstance(item, dict) else {"message": str(item)}))
    else:
        lines.append("- none")

    if notes:
        lines.append("")
        lines.append("## Notes")
        for n in notes:
            lines.append(f"- {str(n)}")
    if note_hints:
        lines.append("")
        lines.append("## Note Hints")
        for h in note_hints:
            if not isinstance(h, dict):
                continue
            code = str(h.get("code") or "").strip()
            title = str(h.get("title_zh") or h.get("title") or "").strip()
            action = str(h.get("action_zh") or h.get("action") or "").strip()
            msg = f"- [{code}] {title}" if code else f"- {title}"
            lines.append(msg)
            if action:
                lines.append(f"  - Action: {action}")
    lines.append("")
    return "\n".join(lines)


_PREFLIGHT_NOTE_HINTS: dict[str, dict[str, str]] = {
    "PLAN_ITEM_NOT_READY": {
        "title": "计划表未初始化",
        "title_zh": "计划表未初始化",
        "action": "Run Auto-Builder to create volume plan items.",
        "action_zh": "请先运行 Auto-Builder 生成卷计划项。",
    },
    "FORESHADOW_STATE_NOT_READY": {
        "title": "伏笔状态表未初始化",
        "title_zh": "伏笔状态表未初始化",
        "action": "Enable ledger promote flow to materialize foreshadow states.",
        "action_zh": "请先执行 Ledger Promote，生成伏笔状态记录。",
    },
    "GROWTH_STATE_NOT_READY": {
        "title": "成长状态表未初始化",
        "title_zh": "成长状态表未初始化",
        "action": "Enable ledger promote flow to materialize growth states.",
        "action_zh": "请先执行 Ledger Promote，生成成长状态记录。",
    },
    "CHARACTER_TABLE_NOT_READY": {
        "title": "角色表未就绪",
        "title_zh": "角色表未就绪",
        "action": "Create/import core characters for continuity checks.",
        "action_zh": "请先创建/导入核心角色以启用连贯性检查。",
    },
    "INVALID_UUID_INPUT": {
        "title": "输入标识格式错误",
        "title_zh": "输入标识格式错误",
        "action": "Verify UUID fields in request payload.",
        "action_zh": "请检查请求中的 UUID 字段格式。",
    },
}


def _preflight_compact_note(prefix: str, exc: Exception, code: str) -> str:
    msg = str(exc)
    lower = msg.lower()
    if "undefinedtableerror" in lower or "does not exist" in lower:
        return f"{prefix}: {code}"
    if "invalid input syntax for type uuid" in lower:
        return f"{prefix}: INVALID_UUID_INPUT"
    return f"{prefix}: {code}_ERROR"


def _preflight_extract_note_code(note: str) -> str:
    s = str(note or "").strip()
    if ":" not in s:
        return ""
    code = s.split(":", 1)[1].strip()
    if " " in code:
        code = code.split(" ", 1)[0]
    if not re.match(r"^[A-Z0-9_]+$", code):
        return ""
    return code


def _preflight_note_hints(notes: list[str]) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for n in notes:
        code = _preflight_extract_note_code(n)
        if not code or code in seen:
            continue
        hint = _PREFLIGHT_NOTE_HINTS.get(code)
        if not hint:
            continue
        seen.add(code)
        out.append({"code": code, **hint})
    return out


async def _run_preflight_for_volume(
    db: AsyncSession,
    *,
    book_id: str,
    volume_id: str,
    volume_no: int,
    chapters: list[dict] | None = None,
) -> dict:
    fail: list[dict] = []
    warn: list[dict] = []
    suggest: list[dict] = []
    notes: list[str] = []

    chs = chapters or []
    if not chs:
        ch_rows = await db.execute(
            text(
                """
                SELECT c.chapter_id::text AS chapter_id, c."order" AS chapter_no, c.title AS chapter_title,
                       d.text, d.draft_id::text AS draft_id, d.run_id::text AS run_id
                FROM chapter c
                JOIN chapter_selected cs ON cs.chapter_id=c.chapter_id
                JOIN chapter_draft d ON d.draft_id=cs.selected_draft_id
                JOIN volume v ON v.book_id=c.book_id AND c."order" BETWEEN v.start_chapter_no AND v.end_chapter_no
                WHERE c.book_id=CAST(:book_id AS uuid) AND v.volume_id=CAST(:volume_id AS uuid)
                ORDER BY c."order" ASC
                """
            ),
            {"book_id": book_id, "volume_id": volume_id},
        )
        chs = [dict(r) for r in ch_rows.mappings().all()]

    if not chs:
        return {
            "summary": {"overall": "WARN", "fail_count": 0, "warn_count": 1, "suggest_count": 0},
            "fail": [],
            "warn": [{"code": "P0", "message": "No selected chapters in volume.", "fix": "Select/activate draft versions first."}],
            "suggest": [],
            "context": {"book_id": book_id, "volume_id": volume_id, "volume_label": f"V{int(volume_no):02d}"},
            "metrics": {"chapter_count": 0, "current_chapter_no": 0},
            "notes": notes,
        }

    current_chapter_no = int(chs[-1].get("chapter_no") or 0)
    current_p_vol = 1.0
    chapter_count = len(chs)

    # C1: core character continuity in last 3 chapters
    core_names: list[str] = []
    try:
        c_rows = await db.execute(
            text("SELECT name FROM character WHERE book_id=CAST(:book_id AS uuid) ORDER BY created_at ASC LIMIT 5"),
            {"book_id": book_id},
        )
        core_names = [str(r.get("name") or "").strip() for r in c_rows.mappings().all() if str(r.get("name") or "").strip()]
    except Exception as exc:
        await db.rollback()
        notes.append(_preflight_compact_note("Character continuity C1 skipped", exc, "CHARACTER_TABLE_NOT_READY"))
    if core_names:
        recent_text = "\n".join(str((x.get("text") or "")) for x in chs[-3:])
        missing = [n for n in core_names if n and n not in recent_text]
        if missing and len(missing) >= max(1, len(core_names) // 2):
            warn.append(
                {
                    "code": "C1",
                    "message": f"Core characters under-represented in recent chapters: {', '.join(missing[:4])}",
                    "fix": "Re-introduce at least one core character with on-screen action/dialogue in next chapter.",
                }
            )

    # C2: timeline conflict (MVP: soft note only unless structured timeline is available)
    notes.append("C2 timeline conflict check is in lightweight mode (no strict structured conflict detector enabled).")

    # C3: cliff validity (selected chapter events + ending keyword)
    cliff_keywords = ("？", "?", "危险", "威胁", "必须", "否则", "倒计时", "下一步")
    for ch in chs[-3:]:
        draft_id = str(ch.get("draft_id") or "")
        if not draft_id:
            continue
        ev_row = await db.execute(
            text("SELECT events FROM chapter_events WHERE draft_id=CAST(:draft_id AS uuid) LIMIT 1"),
            {"draft_id": draft_id},
        )
        ev = ev_row.mappings().first()
        events = ev.get("events") if ev and isinstance(ev.get("events"), dict) else {}
        cliff_obj = events.get("cliff") if isinstance(events.get("cliff"), dict) else {}
        present = bool(cliff_obj.get("present"))
        if present:
            tail = str(ch.get("text") or "")[-220:]
            if not any(k in tail for k in cliff_keywords):
                warn.append(
                    {
                        "code": "C3",
                        "message": f"Chapter {int(ch.get('chapter_no') or 0)} cliff flagged but ending signal looks weak.",
                        "fix": "End with one immediate risk/goal question sentence.",
                    }
                )

    # F1: must_happen overdue
    try:
        p_rows = await db.execute(
            text(
                """
                SELECT item_id::text AS item_id, kind, status, target_p_vol_min, target_p_vol_max, must_happen, ref
                FROM plan_item
                WHERE book_id=CAST(:book_id AS uuid)
                  AND volume_id=CAST(:volume_id AS uuid)
                  AND must_happen=true
                  AND status='todo'
                """
            ),
            {"book_id": book_id, "volume_id": volume_id},
        )
        plan_rows = [dict(r) for r in p_rows.mappings().all()]
    except Exception as exc:
        await db.rollback()
        plan_rows = []
        try:
            alt_rows = await db.execute(
                text(
                    """
                    SELECT i.item_id::text AS item_id, i.kind, i.status, i.target_p_vol_min, i.target_p_vol_max, i.must_happen,
                           COALESCE(i.meta,'{}'::jsonb) AS ref
                    FROM volume_plan_item i
                    JOIN volume_plan p ON p.vol_plan_id=i.vol_plan_id
                    WHERE p.book_id=CAST(:book_id AS uuid)
                      AND p.volume_id=CAST(:volume_id AS uuid)
                      AND p.status='active'
                      AND i.must_happen=true
                      AND i.status='todo'
                    """
                ),
                {"book_id": book_id, "volume_id": volume_id},
            )
            plan_rows = [dict(r) for r in alt_rows.mappings().all()]
        except Exception as exc2:
            await db.rollback()
            notes.append(_preflight_compact_note("Plan-item debt check skipped", exc2, "PLAN_ITEM_NOT_READY"))

    for r in plan_rows:
        vmax = float(r.get("target_p_vol_max") or 0)
        kind = str(r.get("kind") or "")
        item_id = str(r.get("item_id") or "")
        ref = r.get("ref") if isinstance(r.get("ref"), dict) else {}
        combo_type = str(ref.get("combo_type") or "").strip()
        label = combo_type or kind or "item"
        if current_p_vol > vmax + 0.03:
            fail.append(
                {
                    "code": "F1",
                    "message": f"must_happen overdue: {label} ({item_id}) window_max={vmax:.2f} current_p_vol={current_p_vol:.2f}",
                    "fix": "Prioritize corresponding combo/task in next chapter and reduce competing load.",
                }
            )
        elif current_p_vol >= vmax - 0.02:
            warn.append(
                {
                    "code": "F1",
                    "message": f"must_happen near overdue: {label} ({item_id}) window_max={vmax:.2f}",
                    "fix": "Schedule this item immediately in next chapter.",
                }
            )

    # F2: stale foreshadow
    try:
        f_rows = await db.execute(
            text(
                """
                SELECT key, status, last_chapter_no
                FROM foreshadow_state
                WHERE book_id=CAST(:book_id AS uuid)
                  AND status IN ('open','seeded','reinforced')
                """
            ),
            {"book_id": book_id},
        )
        for r in f_rows.mappings().all():
            last_no = int(r.get("last_chapter_no") or 0)
            if current_chapter_no - last_no >= 20:
                warn.append(
                    {
                        "code": "F2",
                        "message": f"Foreshadow stale: key={str(r.get('key') or '')} last_seen=第{last_no:04d}章",
                        "fix": "Add one reinforce beat before payoff.",
                    }
                )
    except Exception as exc:
        await db.rollback()
        notes.append(_preflight_compact_note("Foreshadow debt check skipped", exc, "FORESHADOW_STATE_NOT_READY"))

    # G1: growth debt
    try:
        g_rows = await db.execute(
            text("SELECT key, stage, last_chapter_no FROM growth_state WHERE book_id=CAST(:book_id AS uuid)"),
            {"book_id": book_id},
        )
        for r in g_rows.mappings().all():
            stage = str(r.get("stage") or "")
            last_no = int(r.get("last_chapter_no") or 0)
            key = str(r.get("key") or "")
            if stage != "achieved" and current_chapter_no - last_no >= 25:
                warn.append(
                    {
                        "code": "G1",
                        "message": f"Growth line stale: key={key} stage={stage} last=第{last_no:04d}章",
                        "fix": "Advance or resolve one growth milestone within next 1-2 chapters.",
                    }
                )
            if current_p_vol > 0.8 and stage in {"pending", "planned"}:
                fail.append(
                    {
                        "code": "G1",
                        "message": f"Near volume end but growth still pending: key={key}",
                        "fix": "Bind a payoff/growth action to closing chapters.",
                    }
                )
    except Exception as exc:
        await db.rollback()
        notes.append(_preflight_compact_note("Growth debt check skipped", exc, "GROWTH_STATE_NOT_READY"))

    # Reader risk from last 5 selected chapters
    rs_rows: list[dict] = []
    for ch in chs[-5:]:
        run_id = _as_uuid_str_or_empty(ch.get("run_id"))
        if not run_id:
            continue
        try:
            r_row = await db.execute(
                text("SELECT report FROM chapter_report WHERE run_id=CAST(:run_id AS uuid) LIMIT 1"),
                {"run_id": run_id},
            )
            hit = r_row.mappings().first()
            report = hit.get("report") if hit and isinstance(hit.get("report"), dict) else {}
            rs = report.get("reader_state") if isinstance(report.get("reader_state"), dict) else {}
            if rs:
                rs_rows.append({k: float(rs.get(k) or 0) for k in ("expectation", "tension", "clarity", "satisfaction", "fatigue")})
        except Exception:
            await db.rollback()
            continue
    avg_fatigue = None
    avg_clarity = None
    if rs_rows:
        n = len(rs_rows)
        avg_fatigue = sum(x.get("fatigue", 0) for x in rs_rows) / n
        avg_clarity = sum(x.get("clarity", 0) for x in rs_rows) / n
        avg_tension = sum(x.get("tension", 0) for x in rs_rows) / n
        avg_satisfaction = sum(x.get("satisfaction", 0) for x in rs_rows) / n
        fatigue_trend = rs_rows[-1].get("fatigue", 0) - rs_rows[0].get("fatigue", 0)
        if avg_fatigue > 0.65 and fatigue_trend > 0.10:
            fail.append(
                {
                    "code": "R1",
                    "message": f"Fatigue high and rising: avg={avg_fatigue:.2f} trend=+{fatigue_trend:.2f}",
                    "fix": "Schedule a decompression chapter: lower cost/reversal intensity, add reveal/partial payoff.",
                }
            )
        elif avg_fatigue > 0.65:
            warn.append(
                {
                    "code": "R1",
                    "message": f"Fatigue high: avg={avg_fatigue:.2f}",
                    "fix": "Reduce structural load for next chapter (max_structure_weight=3).",
                }
            )
        low_clarity_count = sum(1 for x in rs_rows[-3:] if x.get("clarity", 0) < 0.35)
        if avg_clarity < 0.40 and low_clarity_count >= min(3, len(rs_rows[-3:])):
            fail.append(
                {
                    "code": "R2",
                    "message": f"Clarity persistently low: avg={avg_clarity:.2f}, recent_low_count={low_clarity_count}",
                    "fix": "Inject reveal/reinterpret combo in immediate next chapter.",
                }
            )
        elif avg_clarity < 0.40:
            warn.append(
                {
                    "code": "R2",
                    "message": f"Clarity low: avg={avg_clarity:.2f}",
                    "fix": "Prefer reinterpret evidence over adding new mysteries.",
                }
            )
        if avg_tension > 0.75 and avg_satisfaction < 0.35:
            warn.append(
                {
                    "code": "R3",
                    "message": f"Tension high without release: avg_tension={avg_tension:.2f}, avg_satisfaction={avg_satisfaction:.2f}",
                    "fix": "Add one payoff beat before next strong cliff.",
                }
            )
    else:
        notes.append("Reader-state checks skipped (no chapter_report reader_state found for selected drafts).")

    # AI-tone suggestions (text-only, advisory)
    all_text = "\n".join(str(x.get("text") or "") for x in chs)
    phrases = ["不由得", "旋即", "片刻", "非常", "极其", "无比"]
    for p in phrases:
        c = all_text.count(p)
        if c >= 6:
            suggest.append(
                {
                    "code": "A1",
                    "message": f"Repeated phrase '{p}' x{c}",
                    "fix": "Suggest rewrite L1 (lexical diversity).",
                }
            )
    sentence_parts = re.split(r"[。！？!?]", all_text)
    sentence_parts = [s for s in sentence_parts if s.strip()]
    long_count = 0
    for s in sentence_parts:
        if s.count("，") >= 4 or len(s) >= 90:
            long_count += 1
    long_ratio = (long_count / len(sentence_parts)) if sentence_parts else 0.0
    if long_ratio > 0.35:
        suggest.append(
            {
                "code": "A2",
                "message": f"Long-sentence ratio high: {long_ratio:.2f}",
                "fix": "Suggest rewrite L2 (split long sentences, increase dialogue/action cadence).",
            }
        )

    overall = "OK"
    if fail:
        overall = "FAIL"
    elif warn:
        overall = "WARN"
    report = {
        "summary": {
            "overall": overall,
            "fail_count": len(fail),
            "warn_count": len(warn),
            "suggest_count": len(suggest),
        },
        "fail": fail,
        "warn": warn,
        "suggest": suggest,
        "context": {
            "book_id": book_id,
            "volume_id": volume_id,
            "volume_label": f"V{int(volume_no):02d}",
        },
        "metrics": {
            "chapter_count": chapter_count,
            "current_chapter_no": current_chapter_no,
            "avg_fatigue": None if avg_fatigue is None else round(avg_fatigue, 4),
            "avg_clarity": None if avg_clarity is None else round(avg_clarity, 4),
        },
        "notes": notes,
        "note_hints": _preflight_note_hints(notes),
    }
    report["markdown"] = _preflight_render_markdown(report)
    return report


async def _ensure_fixwizard_tables(db: AsyncSession) -> None:
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS fix_chain (
              chain_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
              volume_id UUID NULL REFERENCES volume(volume_id) ON DELETE SET NULL,
              pack_name TEXT NOT NULL DEFAULT '',
              preflight_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
              executed JSONB NOT NULL DEFAULT '[]'::jsonb,
              status TEXT NOT NULL DEFAULT 'applied',
              rolled_back_at TIMESTAMPTZ NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    await db.execute(text("ALTER TABLE fix_chain ADD COLUMN IF NOT EXISTS preflight_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb"))
    await db.execute(text("ALTER TABLE fix_chain ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'applied'"))
    await db.execute(text("ALTER TABLE fix_chain ADD COLUMN IF NOT EXISTS rolled_back_at TIMESTAMPTZ NULL"))
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS plan_patch_log (
              patch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
              volume_id UUID NULL REFERENCES volume(volume_id) ON DELETE SET NULL,
              item_id UUID NOT NULL,
              before JSONB NOT NULL DEFAULT '{}'::jsonb,
              after JSONB NOT NULL DEFAULT '{}'::jsonb,
              reason TEXT NOT NULL DEFAULT '',
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    await db.execute(text("CREATE INDEX IF NOT EXISTS idx_plan_patch_log_book_time ON plan_patch_log(book_id, created_at DESC)"))
    await db.execute(text("CREATE INDEX IF NOT EXISTS idx_fix_chain_book_time ON fix_chain(book_id, created_at DESC)"))
    await db.commit()


def _fixwizard_level_from_severity(sev: str) -> str:
    s = str(sev or "").upper()
    if s == "FAIL":
        return "high"
    if s == "WARN":
        return "mid"
    return "low"


def _fixwizard_build_fixes(book_id: str, volume_id: str, preflight: dict) -> list[dict]:
    out: list[dict] = []
    id_used: dict[str, int] = {}

    def next_fix_id(base: str) -> str:
        b = str(base or "fix").strip().lower().replace(" ", "_")
        id_used[b] = int(id_used.get(b, 0)) + 1
        return f"{b}_{id_used[b]}"

    def push(issue: dict, severity: str) -> None:
        code = str(issue.get("code") or "").strip().upper()
        message = str(issue.get("message") or "").strip()
        risk = _fixwizard_level_from_severity(severity)
        target = code or severity
        base = {
            "target": target,
            "risk": risk,
            "rollback_supported": True,
            "source_issue": issue,
        }
        if code == "F1":
            out.append(
                {
                    "fix_id": next_fix_id("f1_inject_reveal_combo"),
                    "title": "注入 reveal_combo（2章窗口）",
                    "type": "agent_apply",
                    "payload": {
                        "action_type": "inject_combo",
                        "action_payload": {"combo_type": "reveal_combo", "window_next_chapters": 2, "priority": 5},
                    },
                    "expected_effect": ["提升清晰度", "缓解 must_happen 欠账"],
                    "reason": message or "must_happen overdue",
                    **base,
                }
            )
            out.append(
                {
                    "fix_id": next_fix_id("f1_reduce_load"),
                    "title": "临时降低章节结构负载",
                    "type": "agent_apply",
                    "payload": {
                        "action_type": "patch_limits",
                        "action_payload": {
                            "max_structure_weight": 3,
                            "max_tasks_per_chapter": 2,
                            "ban_strong_cliff": True,
                        },
                    },
                    "expected_effect": ["提高逾期任务命中率", "减少任务拥塞"],
                    "reason": "给 must_happen 腾出执行空间",
                    **base,
                }
            )
        elif code == "R1":
            out.append(
                {
                    "fix_id": next_fix_id("r1_reduce_load"),
                    "title": "减压策略（max_weight=3 + 禁强 cliff）",
                    "type": "agent_apply",
                    "payload": {
                        "action_type": "patch_limits",
                        "action_payload": {
                            "max_structure_weight": 3,
                            "max_tasks_per_chapter": 2,
                            "ban_strong_cliff": True,
                        },
                    },
                    "expected_effect": ["fatigue 下降", "提高连贯性"],
                    "reason": message or "fatigue high",
                    **base,
                }
            )
        elif code == "R2":
            out.append(
                {
                    "fix_id": next_fix_id("r2_inject_reveal"),
                    "title": "强制补充 reveal/reinterpret",
                    "type": "agent_apply",
                    "payload": {
                        "action_type": "inject_combo",
                        "action_payload": {"combo_type": "reveal_combo", "window_next_chapters": 2, "priority": 5},
                    },
                    "expected_effect": ["clarity 回升", "减少理解断裂"],
                    "reason": message or "clarity low",
                    **base,
                }
            )
        elif code == "C3":
            out.append(
                {
                    "fix_id": next_fix_id("c3_schedule_vol_end"),
                    "title": "补强收尾钩子（vol_end combo）",
                    "type": "agent_apply",
                    "payload": {
                        "action_type": "inject_combo",
                        "action_payload": {"combo_type": "vol_end_combo", "window_next_chapters": 1, "priority": 5},
                    },
                    "expected_effect": ["章末问题更明确", "提升追更驱动"],
                    "reason": message or "cliff weak",
                    **base,
                }
            )
            out.append(
                {
                    "fix_id": next_fix_id("c3_rewrite_l1"),
                    "title": "建议对当前章执行 Rewrite L1（只修表达）",
                    "type": "rewrite_suggest",
                    "payload": {"level": "L1"},
                    "expected_effect": ["钩子表达更利落", "不改剧情事实"],
                    "reason": "弱 cliff 常由表达而非结构造成",
                    **base,
                }
            )
        elif code in {"A1", "A2"}:
            lvl = "L2" if code == "A2" else "L1"
            out.append(
                {
                    "fix_id": next_fix_id(f"{code.lower()}_rewrite"),
                    "title": f"建议 Rewrite {lvl}",
                    "type": "rewrite_suggest",
                    "payload": {"level": lvl},
                    "expected_effect": ["降低模板感", "提升句式多样性"],
                    "reason": message or "ai-tone suggestion",
                    **base,
                }
            )

    for sev in ("fail", "warn", "suggest"):
        items = preflight.get(sev)
        if not isinstance(items, list):
            continue
        sev_tag = sev.upper()
        for item in items:
            if isinstance(item, dict):
                push(item, sev_tag)

    note_hints = preflight.get("note_hints")
    if isinstance(note_hints, list):
        for h in note_hints:
            if not isinstance(h, dict):
                continue
            code = str(h.get("code") or "").strip().upper()
            if code == "PLAN_ITEM_NOT_READY":
                out.append(
                    {
                        "fix_id": next_fix_id("plan_autobuild"),
                        "target": code,
                        "title": "初始化卷计划（Auto-Builder）",
                        "type": "plan_autobuild",
                        "payload": {"book_id": book_id, "volume_id": volume_id},
                        "risk": "low",
                        "expected_effect": ["生成 setup/mid/reveal/vol_end 计划项", "恢复 must_happen 检查能力"],
                        "rollback_supported": True,
                        "reason": str(h.get("action_zh") or h.get("action") or ""),
                        "source_issue": h,
                    }
                )

    # Generic, always available for volume-level tuning.
    if str(volume_id or "").strip():
        out.append(
            {
                "fix_id": next_fix_id("plan_patch_boost_priority"),
                "target": "PLAN",
                "title": "提高本卷 must_happen(todo) priority（+1）",
                "type": "plan_patch",
                "payload": {"mode": "boost_must_happen_priority", "delta": 1},
                "risk": "mid",
                "expected_effect": ["must_happen 更易被 Orchestrator 选中"],
                "rollback_supported": True,
                "reason": "generic scheduling boost",
                "source_issue": {"code": "PLAN", "message": "generic plan boost"},
            }
        )

    return out


async def _fixwizard_insert_state_audit(
    db: AsyncSession,
    *,
    book_id: str,
    volume_id: str | None,
    action_type: str,
    before_state: dict,
    after_state: dict,
    diff: dict,
    reason: str,
) -> str:
    row = await db.execute(
        text(
            """
            INSERT INTO state_apply_audit(book_id, chapter_id, run_id, action_type, before_state, after_state, diff, reason)
            VALUES (
              CAST(:book_id AS uuid), NULL, NULL, :action_type,
              CAST(:before_state AS jsonb), CAST(:after_state AS jsonb), CAST(:diff AS jsonb), :reason
            )
            RETURNING audit_id::text
            """
        ),
        {
            "book_id": book_id,
            "action_type": action_type,
            "before_state": json.dumps(before_state or {}, ensure_ascii=False, default=str),
            "after_state": json.dumps(after_state or {}, ensure_ascii=False, default=str),
            "diff": json.dumps(diff or {}, ensure_ascii=False, default=str),
            "reason": reason[:240],
        },
    )
    return str(row.scalar_one())


def _fixwizard_summary_delta(before: dict | None, after: dict | None) -> dict:
    b = before if isinstance(before, dict) else {}
    a = after if isinstance(after, dict) else {}
    bf = int(b.get("fail_count") or 0)
    bw = int(b.get("warn_count") or 0)
    bs = int(b.get("suggest_count") or 0)
    af = int(a.get("fail_count") or 0)
    aw = int(a.get("warn_count") or 0)
    ass = int(a.get("suggest_count") or 0)
    return {
        "before": {"fail_count": bf, "warn_count": bw, "suggest_count": bs},
        "after": {"fail_count": af, "warn_count": aw, "suggest_count": ass},
        "delta": {
            "fail_count": af - bf,
            "warn_count": aw - bw,
            "suggest_count": ass - bs,
        },
    }


async def _ensure_export_tables(db: AsyncSession) -> None:
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS book_workspace (
              book_id UUID PRIMARY KEY REFERENCES book(book_id) ON DELETE CASCADE,
              workspace_path TEXT NOT NULL,
              book_slug TEXT NOT NULL DEFAULT '',
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS export_log (
              export_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
              volume_id UUID NULL REFERENCES volume(volume_id) ON DELETE SET NULL,
              pack_name TEXT NOT NULL,
              output_dir TEXT NOT NULL,
              manifest JSONB NOT NULL DEFAULT '{}'::jsonb,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    await db.execute(text("CREATE INDEX IF NOT EXISTS idx_export_log_book_time ON export_log(book_id, created_at DESC)"))
    await db.commit()


async def _load_workspace_binding(db: AsyncSession, book_id: str) -> dict | None:
    row = await db.execute(
        text(
            """
            SELECT book_id::text AS book_id, workspace_path, book_slug, updated_at
            FROM book_workspace
            WHERE book_id=CAST(:book_id AS uuid)
            LIMIT 1
            """
        ),
        {"book_id": book_id},
    )
    hit = row.mappings().first()
    return dict(hit) if hit else None


async def _resolve_book_workspace(db: AsyncSession, book_id: str) -> tuple[Path, str, str]:
    ws = await _load_workspace_binding(db, book_id)
    if not ws:
        raise HTTPException(status_code=400, detail="BOOK_WORKSPACE_NOT_SET")
    b_row = await db.execute(
        text("SELECT title FROM book WHERE book_id=CAST(:book_id AS uuid) LIMIT 1"),
        {"book_id": book_id},
    )
    b = b_row.mappings().first()
    title = str((b or {}).get("title") or "")
    book_slug = str(ws.get("book_slug") or "").strip() or _slugify_filename(title, fallback=book_id)
    workspace_root = Path(str(ws.get("workspace_path") or "")).expanduser()
    if not workspace_root.exists():
        raise HTTPException(status_code=400, detail="WORKSPACE_PATH_NOT_FOUND")
    books_dir = (workspace_root / "books" / book_slug).resolve()
    _ensure_path_within(workspace_root, books_dir)
    books_dir.mkdir(parents=True, exist_ok=True)
    return workspace_root.resolve(), books_dir, book_slug


def _workflow_extract_chapter_and_events(text_value: str) -> tuple[str, dict]:
    data = str(text_value or "")
    if not data.strip():
        raise RuntimeError("LLM_EMPTY_OUTPUT")
    upper = data.upper()
    idx_events = upper.find("EVENTS_JSON:")
    if idx_events < 0:
        raise RuntimeError("EVENTS_JSON_MISSING")
    idx_chapter = upper.find("CHAPTER_TEXT:")
    chapter_text = ""
    if idx_chapter >= 0 and idx_chapter < idx_events:
        chapter_text = data[idx_chapter + len("CHAPTER_TEXT:") : idx_events].strip()
    else:
        chapter_text = data[:idx_events].strip()
    events_blob = data[idx_events + len("EVENTS_JSON:") :].strip()
    if not events_blob:
        raise RuntimeError("EVENTS_JSON_EMPTY")
    # Deterministic section parse: only one JSON object/array allowed in EVENTS_JSON section.
    candidate = ""
    try:
        from .services.json_guard import extract_json_candidate, sanitize_json_like

        candidate = sanitize_json_like(extract_json_candidate(events_blob))
    except Exception as exc:
        raise RuntimeError(f"EVENTS_JSON_PARSE_FAILED: {exc}") from exc
    if events_blob.strip() != candidate.strip():
        raise RuntimeError("EVENTS_JSON_EXTRA_TOKENS")
    try:
        parsed = json_guard_parse(candidate)
    except JSONGuardError as exc:
        raise RuntimeError(f"EVENTS_JSON_PARSE_FAILED: {exc}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("EVENTS_JSON_NOT_OBJECT")
    events = _workflow_validate_events_json(parsed)
    if not chapter_text:
        raise RuntimeError("CHAPTER_TEXT_EMPTY")
    return chapter_text, events


async def _workflow_memory_pack_execute(ctx: dict, node_inputs: dict, db: AsyncSession) -> dict:
    enabled = _workflow_parse_bool(
        node_inputs.get("enabled"),
        _workflow_parse_bool(ctx.get("memory_pack_enabled"), True),
    )
    if not enabled:
        return {"memory_pack_status": {"ok": True, "enabled": False, "skipped": True, "reason": "disabled"}}

    required = _workflow_parse_bool(
        node_inputs.get("required"),
        _workflow_parse_bool(ctx.get("memory_pack_required"), False),
    )
    book_id = str(ctx.get("book_id") or "").strip()
    chapter_id = str(ctx.get("chapter_id") or "").strip()
    chapter_no = _workflow_parse_int(ctx.get("chapter_no"), 0, 0, 100000)
    if not book_id or (not chapter_id and chapter_no <= 0):
        missing_reason = "book_id_or_chapter_missing"
        if required:
            raise RuntimeError(missing_reason)
        return {
            "memory_pack_status": {
                "ok": False,
                "enabled": True,
                "required": False,
                "skipped": True,
                "reason": missing_reason,
            }
        }

    session_key = str(node_inputs.get("session_key") or ctx.get("memory_session_key") or ctx.get("session_key") or "").strip()
    if not session_key:
        session_key = "draft_runner_v1"
    task_type = str(node_inputs.get("task_type") or ctx.get("memory_task_type") or "write_chapter").strip().lower() or "write_chapter"
    chapter_window = _workflow_parse_int(
        node_inputs.get("chapter_window"),
        _workflow_parse_int(ctx.get("memory_chapter_window"), 3, 1, 12),
        1,
        12,
    )
    evidence_top_k = _workflow_parse_int(
        node_inputs.get("evidence_top_k"),
        _workflow_parse_int(ctx.get("memory_evidence_top_k"), 24, 6, 80),
        6,
        80,
    )
    hard_constraints = [str(x).strip() for x in (ctx.get("memory_hard_constraints") if isinstance(ctx.get("memory_hard_constraints"), list) else []) if str(x).strip()]
    final_task_types = [
        str((x or {}).get("type") or (x or {}).get("task_type") or "").strip().lower()
        for x in (ctx.get("final_tasks") if isinstance(ctx.get("final_tasks"), list) else [])
        if isinstance(x, dict)
    ]
    final_task_types = [x for x in final_task_types if x]
    conflict_card = await _workflow_load_memory_conflict_card(
        db,
        book_id=book_id,
        chapter_id=chapter_id,
        chapter_no=chapter_no,
    )
    chapter_goal = str(conflict_card.get("chapter_goal") or "").strip()
    conflict_label = str(conflict_card.get("conflict_label") or conflict_card.get("conflict_type") or "").strip()
    upgrade_method = str(conflict_card.get("upgrade_method") or "").strip()
    cliffhanger = str(conflict_card.get("cliffhanger") or "").strip()
    overdue_seeds = await _workflow_load_overdue_foreshadow_seeds(
        db,
        book_id=book_id,
        chapter_no=chapter_no,
        limit=8,
    )
    overdue_titles = [str((x or {}).get("title") or "").strip() for x in overdue_seeds if str((x or {}).get("title") or "").strip()]
    focus_instruction = _workflow_build_memory_focus_instruction(
        chapter_goal=chapter_goal,
        conflict_label=conflict_label,
        upgrade_method=upgrade_method,
        cliffhanger=cliffhanger,
        task_types=final_task_types,
        overdue_titles=overdue_titles,
    )
    signal_constraints: list[str] = []
    if chapter_goal:
        signal_constraints.append(f"本章目标不得偏离：{chapter_goal}")
    if conflict_label:
        signal_constraints.append(f"冲突主轴必须保持：{conflict_label}")
    if overdue_titles:
        signal_constraints.append(f"到期伏笔需回收或明确延期：{'、'.join(overdue_titles[:4])}")
    merged_constraints = hard_constraints + signal_constraints
    query = str(node_inputs.get("query") or ctx.get("memory_query") or "").strip()
    if not query:
        query_parts = [
            str(ctx.get("intent_confirmed") or "").strip(),
            str(ctx.get("chapter_title") or "").strip(),
            chapter_goal,
            conflict_label,
            " ".join([x for x in final_task_types[:6] if x]),
            " ".join(overdue_titles[:4]),
        ]
        query = " ".join([x for x in query_parts if x]).strip()
    task_instruction = str(node_inputs.get("task_instruction") or ctx.get("memory_task_instruction") or ctx.get("intent_confirmed") or "").strip()
    if focus_instruction:
        if task_instruction:
            task_instruction = f"{task_instruction}；{focus_instruction}"
        else:
            task_instruction = focus_instruction
    task_instruction = task_instruction[:360]
    query = query[:260]

    payload: dict[str, Any] = {
        "session_key": session_key,
        "task_type": task_type,
        "query": query,
        "task_instruction": task_instruction,
        "chapter_window": chapter_window,
        "evidence_top_k": evidence_top_k,
        "hard_constraints": merged_constraints[:28],
    }
    if chapter_id:
        payload["chapter_id"] = chapter_id
    if chapter_no > 0:
        payload["chapter_no"] = chapter_no
    splitbook_id = str(node_inputs.get("splitbook_id") or ctx.get("splitbook_id") or "").strip()
    if splitbook_id:
        payload["splitbook_id"] = splitbook_id

    try:
        pack = await build_writing_memory_pack(db, book_id, payload)
    except Exception as exc:
        if required:
            raise
        return {
            "memory_pack_status": {
                "ok": False,
                "enabled": True,
                "required": False,
                "degraded": True,
                "error": str(exc),
            }
        }
    return {
        "writing_memory_pack": pack,
        "memory_pack_status": {
            "ok": bool(pack.get("ok")),
            "enabled": True,
            "required": required,
            "checkpoint_id": str(pack.get("checkpoint_id") or ""),
            "token_est": int(((pack.get("context_assembled") or {}).get("token_est") or 0)),
            "signals": {
                "chapter_goal": chapter_goal,
                "conflict_label": conflict_label,
                "overdue_foreshadow_titles": overdue_titles[:6],
                "overdue_foreshadow_seeds": overdue_seeds[:8],
                "task_types": final_task_types[:8],
                "query": query,
            },
        },
    }


async def _workflow_memory_writeback_execute(ctx: dict, node_inputs: dict, db: AsyncSession) -> dict:
    enabled = _workflow_parse_bool(
        node_inputs.get("enabled"),
        _workflow_parse_bool(ctx.get("memory_writeback_enabled"), True),
    )
    if not enabled:
        return {"memory_writeback_report": {"ok": True, "enabled": False, "skipped": True, "reason": "disabled"}}
    if bool(ctx.get("dry_run")):
        return {"memory_writeback_report": {"ok": True, "enabled": True, "skipped": True, "reason": "dry_run"}}

    required = _workflow_parse_bool(
        node_inputs.get("required"),
        _workflow_parse_bool(ctx.get("memory_writeback_required"), False),
    )
    book_id = str(ctx.get("book_id") or "").strip()
    chapter_id = str(ctx.get("chapter_id") or "").strip()
    chapter_no = _workflow_parse_int(ctx.get("chapter_no"), 0, 0, 100000)
    llm_obj = ctx.get("llm_output") if isinstance(ctx.get("llm_output"), dict) else {}
    chapter_text = str(llm_obj.get("chapter_text") or llm_obj.get("text") or "").strip()
    if not book_id or not chapter_id or not chapter_text:
        missing_reason = "book_id_chapter_id_or_content_missing"
        if required:
            raise RuntimeError(missing_reason)
        return {
            "memory_writeback_report": {
                "ok": False,
                "enabled": True,
                "required": False,
                "skipped": True,
                "reason": missing_reason,
            }
        }

    persist = _workflow_parse_bool(
        node_inputs.get("persist"),
        _workflow_parse_bool(ctx.get("memory_writeback_persist"), True),
    )
    session_key = str(node_inputs.get("session_key") or ctx.get("memory_session_key") or ctx.get("session_key") or "").strip()
    if not session_key:
        session_key = "draft_runner_v1"
    payload = {
        "session_key": session_key,
        "chapter_id": chapter_id,
        "chapter_no": chapter_no if chapter_no > 0 else None,
        "chapter_title": str(ctx.get("chapter_title") or ""),
        "content": chapter_text,
        "writeback": persist,
    }
    try:
        report = await validate_and_writeback_memory(db, book_id, payload)
    except Exception as exc:
        if required:
            raise
        return {
            "memory_writeback_report": {
                "ok": False,
                "enabled": True,
                "required": False,
                "degraded": True,
                "error": str(exc),
            }
        }
    return {"memory_writeback_report": report}


async def _workflow_llm_execute(ctx: dict, node_inputs: dict) -> dict:
    prompt = str(ctx.get("prompt") or "").strip()
    if bool(ctx.get("dry_run")) or bool(ctx.get("force_stub_llm")):
        preview_tasks = [str((x or {}).get("type") or (x or {}).get("task_type") or "") for x in (ctx.get("final_tasks") or []) if isinstance(x, dict)]
        chapter_part = (
            f"第{int(ctx.get('chapter_no') or 1)}章\n"
            f"在{str(ctx.get('phase') or '')}阶段，人物沿着任务推进：{','.join(preview_tasks[:4]) or 'none'}。\n"
            f"冲突被推进，线索得到部分揭示，结尾留下下一章钩子。"
        )
        events_obj = {
            "foreshadow_events": [],
            "growth_events": [],
            "cliff": {"present": False, "style": "question_end", "note": "stub"},
            "reveal": {"ratio": 0.0, "note": "stub"},
            "executed_tasks": [],
        }
        for t in (ctx.get("final_tasks") if isinstance(ctx.get("final_tasks"), list) else []):
            if not isinstance(t, dict):
                continue
            ttype = str(t.get("type") or t.get("task_type") or "")
            intensity = max(1, min(3, int(t.get("intensity") or 1)))
            combo = t.get("combo") if isinstance(t.get("combo"), dict) else {}
            meta = t.get("meta") if isinstance(t.get("meta"), dict) else {}
            events_obj["executed_tasks"].append(
                {
                    "task_id": str(t.get("task_id") or ""),
                    "type": ttype,
                    "combo_fp": str(combo.get("combo_fp") or meta.get("combo_fp") or ""),
                    "step": str(combo.get("step") or meta.get("combo_step") or ""),
                    "evidence": "from task",
                }
            )
            if ttype == "cliff":
                events_obj["cliff"] = {"present": True, "style": str((t.get("meta") or {}).get("style") or "question_end"), "note": "from task"}
            if ttype == "reveal":
                events_obj["reveal"] = {"ratio": 0.4, "note": "from task"}
                events_obj["foreshadow_events"].append({"foreshadow_id": None, "event_type": "payoff", "intensity": intensity, "note": "reveal payoff"})
            if ttype == "growth":
                events_obj["growth_events"].append(
                    {
                        "milestone_id": str((t.get("refs") or {}).get("milestone_id") or "") or None,
                        "action": "achieve" if str((t.get("meta") or {}).get("stage") or "") == "breakthrough" else "advance",
                        "cost_shown": str((t.get("meta") or {}).get("stage") or "") == "breakthrough",
                        "choice_explicit": str((t.get("meta") or {}).get("stage") or "") == "breakthrough",
                        "note": "from task",
                    }
                )
        if bool(ctx.get("force_bad_events_json")):
            text_value = "CHAPTER_TEXT:\n" + chapter_part + "\n\nEVENTS_JSON:\n" + '{"bad":'
        else:
            text_value = (
                "CHAPTER_TEXT:\n"
                + chapter_part
                + "\n\nEVENTS_JSON:\n"
                + json.dumps(events_obj, ensure_ascii=False)
            )
        chapter_text, events_json = _workflow_extract_chapter_and_events(text_value)
        return {
            "llm_output": {
                "text": text_value,
                "chapter_text": chapter_text,
                "events_json": events_json,
                "dry_run": bool(ctx.get("dry_run")),
                "stubbed": True,
                "model": str(node_inputs.get("model") or DEFAULT_LLM_MODEL),
            }
        }
    if not prompt:
        raise RuntimeError("PROMPT_EMPTY")
    model = str(node_inputs.get("model") or DEFAULT_LLM_MODEL)
    temperature = float(node_inputs.get("temperature") or 0.75)
    settings_obj = ctx.get("book_settings") if isinstance(ctx.get("book_settings"), dict) else {}
    draft_cfg = settings_obj.get("draft") if isinstance(settings_obj.get("draft"), dict) else {}
    min_chars = max(800, min(12000, int(draft_cfg.get("min_chars") or 3000)))
    max_tokens = int(node_inputs.get("max_tokens") or 2200)
    max_tokens = max(max_tokens, min(9000, int(min_chars * 2.2)))
    client = OllamaClient(settings.ollama_host)
    out = await client.chat(
        model=model,
        user=prompt,
        system="你是小说写作助手。输出正文，不要解释。",
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_s=150,
        retries=1,
        meta={"workflow": "draft_runner_v1", "run_id": str(ctx.get("run_id") or "")},
    )
    raw_text = str(out.get("text") or "")
    chapter_text, events_json = _workflow_extract_chapter_and_events(raw_text)
    return {
        "llm_output": {
            "text": raw_text,
            "chapter_text": chapter_text,
            "events_json": events_json,
            "model": model,
            "latency_ms": int(out.get("latency_ms") or 0),
            "tokens_in_est": int(out.get("tokens_in_est") or 0),
            "tokens_out_est": int(out.get("tokens_out_est") or 0),
        }
    }


async def _workflow_execute_node(node: dict, ctx: dict, db: AsyncSession) -> dict:
    ntype = str(node.get("type") or "")
    inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
    if ntype == "sql":
        query_id = str(inputs.get("query_id") or "")
        return await _workflow_sql_execute(query_id, ctx, db)
    if ntype == "rule":
        fn_name = str(inputs.get("fn") or "")
        return _workflow_rule_execute(fn_name, ctx)
    if ntype == "memory_pack":
        return await _workflow_memory_pack_execute(ctx, inputs, db)
    if ntype == "compose":
        return _workflow_compose_prompt(ctx, str(inputs.get("template_id") or ""))
    if ntype == "llm":
        return await _workflow_llm_execute(ctx, inputs)
    if ntype == "memory_writeback":
        return await _workflow_memory_writeback_execute(ctx, inputs, db)
    raise RuntimeError("NODE_TYPE_NOT_SUPPORTED")


def _workflow_make_idempotency_key(workflow_id: str, workflow_version: int, input_ctx: dict, dry_run: bool) -> str:
    raw = json.dumps(
        {
            "workflow_id": workflow_id,
            "workflow_version": workflow_version,
            "input": input_ctx,
            "dry_run": dry_run,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


async def _workflow_execute_run(
    *,
    db: AsyncSession,
    workflow_id: str,
    definition: dict,
    input_ctx: dict,
    idempotency_key: str,
    dry_run: bool,
    reuse_if_exists: bool,
) -> dict:
    version = int(definition.get("version") or 1)
    if reuse_if_exists:
        existing = await db.execute(
            text(
                """
                SELECT run_id::text AS run_id, status, started_at, ended_at, meta, error
                FROM workflow_run
                WHERE workflow_id=:workflow_id
                  AND idempotency_key=:idempotency_key
                ORDER BY started_at DESC
                LIMIT 1
                """
            ),
            {"workflow_id": workflow_id, "idempotency_key": idempotency_key},
        )
        old = existing.mappings().first()
        if old:
            return {
                "ok": True,
                "reused": True,
                "run_id": str(old.get("run_id")),
                "status": str(old.get("status")),
                "idempotency_key": idempotency_key,
                "meta": old.get("meta") if isinstance(old.get("meta"), dict) else {},
                "error": old.get("error") if isinstance(old.get("error"), dict) else None,
            }

    try:
        run_ins = await db.execute(
            text(
                """
                INSERT INTO workflow_run(
                  workflow_id, workflow_version, book_id, chapter_id, idempotency_key, status, ctx_snapshot, meta
                )
                VALUES(
                  :workflow_id, :workflow_version, CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), :idempotency_key, 'running',
                  CAST(:ctx_snapshot AS jsonb), CAST(:meta AS jsonb)
                )
                RETURNING run_id::text AS run_id
                """
            ),
            {
                "workflow_id": workflow_id,
                "workflow_version": version,
                "book_id": str(input_ctx.get("book_id") or "") or None,
                "chapter_id": str(input_ctx.get("chapter_id") or "") or None,
                "idempotency_key": idempotency_key,
                "ctx_snapshot": json.dumps(input_ctx, ensure_ascii=False),
                "meta": json.dumps({"dry_run": dry_run}, ensure_ascii=False),
            },
        )
        run_id = str((run_ins.mappings().first() or {}).get("run_id") or "")
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await db.execute(
            text(
                """
                SELECT run_id::text AS run_id, status, meta, error
                FROM workflow_run
                WHERE workflow_id=:workflow_id AND idempotency_key=:idempotency_key
                ORDER BY started_at DESC
                LIMIT 1
                """
            ),
            {"workflow_id": workflow_id, "idempotency_key": idempotency_key},
        )
        old = existing.mappings().first()
        if old:
            return {
                "ok": True,
                "reused": True,
                "run_id": str(old.get("run_id")),
                "status": str(old.get("status")),
                "idempotency_key": idempotency_key,
                "meta": old.get("meta") if isinstance(old.get("meta"), dict) else {},
                "error": old.get("error") if isinstance(old.get("error"), dict) else None,
            }
        raise
    if not run_id:
        raise RuntimeError("RUN_CREATE_FAILED")

    ctx = dict(input_ctx)
    ctx["run_id"] = run_id
    ctx["dry_run"] = dry_run
    nodes = definition.get("nodes") if isinstance(definition.get("nodes"), list) else []

    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "")
        node_type = str(node.get("type") or "")
        step_input = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
        step_ins = await db.execute(
            text(
                """
                INSERT INTO workflow_step(run_id, node_id, node_type, attempt, status, input)
                VALUES (CAST(:run_id AS uuid), :node_id, :node_type, 1, 'running', CAST(:input AS jsonb))
                RETURNING step_id::text AS step_id
                """
            ),
            {
                "run_id": run_id,
                "node_id": node_id,
                "node_type": node_type,
                "input": json.dumps(step_input, ensure_ascii=False),
            },
        )
        step_id = str((step_ins.mappings().first() or {}).get("step_id") or "")
        await db.commit()
        t0 = datetime.now(timezone.utc)
        try:
            patch = await _workflow_execute_node(node, ctx, db)
            if not isinstance(patch, dict):
                patch = {}
            _workflow_merge_ctx(ctx, patch)
            latency_ms = max(0, int((datetime.now(timezone.utc) - t0).total_seconds() * 1000))
            await db.execute(
                text(
                    """
                    UPDATE workflow_step
                    SET status='succeeded', ended_at=now(), output=CAST(:output AS jsonb), metrics=CAST(:metrics AS jsonb)
                    WHERE step_id=CAST(:step_id AS uuid)
                    """
                ),
                {
                    "step_id": step_id,
                    "output": json.dumps(patch, ensure_ascii=False),
                    "metrics": json.dumps({"latency_ms": latency_ms}, ensure_ascii=False),
                },
            )
            await db.commit()
        except Exception as exc:
            latency_ms = max(0, int((datetime.now(timezone.utc) - t0).total_seconds() * 1000))
            err_obj = {"code": "STEP_FAILED", "message": str(exc), "node_id": node_id}
            await db.rollback()
            await db.execute(
                text(
                    """
                    UPDATE workflow_step
                    SET status='failed', ended_at=now(), error=CAST(:error AS jsonb), metrics=CAST(:metrics AS jsonb)
                    WHERE step_id=CAST(:step_id AS uuid)
                    """
                ),
                {
                    "step_id": step_id,
                    "error": json.dumps(err_obj, ensure_ascii=False),
                    "metrics": json.dumps({"latency_ms": latency_ms}, ensure_ascii=False),
                },
            )
            await db.execute(
                text(
                    """
                    UPDATE workflow_run
                    SET status='failed', ended_at=now(), error=CAST(:error AS jsonb), meta=CAST(:meta AS jsonb)
                    WHERE run_id=CAST(:run_id AS uuid)
                    """
                ),
                {
                    "run_id": run_id,
                    "error": json.dumps(err_obj, ensure_ascii=False),
                    "meta": json.dumps({"dry_run": dry_run, "failed_node": node_id}, ensure_ascii=False),
                },
            )
            await db.commit()
            return {
                "ok": False,
                "reused": False,
                "run_id": run_id,
                "status": "failed",
                "idempotency_key": idempotency_key,
                "error": err_obj,
            }

    result_meta = {
        "dry_run": dry_run,
        "phase": str(ctx.get("phase") or ""),
        "structure": ctx.get("structure") if isinstance(ctx.get("structure"), dict) else {},
        "commit_result": ctx.get("commit_result") if isinstance(ctx.get("commit_result"), dict) else {},
        "memory_pack_status": ctx.get("memory_pack_status") if isinstance(ctx.get("memory_pack_status"), dict) else {},
        "memory_writeback_report": ctx.get("memory_writeback_report") if isinstance(ctx.get("memory_writeback_report"), dict) else {},
        "quality_report": ctx.get("quality_report") if isinstance(ctx.get("quality_report"), dict) else {},
        "reader_state_next": ctx.get("reader_state_next") if isinstance(ctx.get("reader_state_next"), dict) else {},
    }
    await db.execute(
        text(
            """
            UPDATE workflow_run
            SET status='succeeded', ended_at=now(), meta=CAST(:meta AS jsonb)
            WHERE run_id=CAST(:run_id AS uuid)
            """
        ),
        {"run_id": run_id, "meta": json.dumps(result_meta, ensure_ascii=False)},
    )
    await db.commit()
    return {
        "ok": True,
        "reused": False,
        "run_id": run_id,
        "status": "succeeded",
        "idempotency_key": idempotency_key,
        "output": result_meta,
    }


def _build_combo_task_block(tasks: list[dict]) -> str:
    combo_rows = [x for x in tasks if isinstance(x, dict) and str(x.get("source") or "") == "combo"]
    if not combo_rows:
        return ""
    lines = ["[COMBO_TASK]"]
    grouped: dict[str, list[dict]] = {}
    for t in combo_rows:
        key = str(t.get("combo_type") or "combo")
        grouped.setdefault(key, []).append(t)
    for ctype, rows in grouped.items():
        lines.append(f"- Combo: {ctype}")
        for r in rows[:4]:
            lines.append(
                "  - "
                + str(r.get("task_type") or "")
                + f" (intensity={int(r.get('intensity') or 1)})"
            )
    lines.append("Rules:")
    lines.append("- Merge actions when possible; avoid overloading one chapter.")
    lines.append("- Keep narrative coherence over quantity.")
    lines.append("[/COMBO_TASK]")
    return "\n".join(lines)


def _orchestrate_chapter_tasks(
    *,
    growth_task: dict | None,
    foreshadow_selection: dict | None,
    plan_items: list[dict] | None,
    p_vol: float | None,
    structure: dict | None,
    reader_state: dict | None,
    enable_combo: bool,
    max_tasks: int = 3,
    max_weight: int = 4,
) -> dict:
    pv = _clamp01(float(p_vol)) if p_vol is not None else 0.0
    win = _window_from_p_vol(pv)
    s = structure if isinstance(structure, dict) else {}
    conflict = _clamp01(float(s.get("conflict") or 0.0))
    tension = _clamp01(float(s.get("tension") or 0.0))
    closure = _clamp01(float(s.get("closure") or 0.0))
    reader = _normalize_reader_state(reader_state)
    dynamic_max_weight = int(max_weight)
    if conflict > 0.75 or closure > 0.6:
        dynamic_max_weight = max(dynamic_max_weight, 5)
    if tension < 0.4:
        dynamic_max_weight = min(dynamic_max_weight, 3)
    dynamic_max_weight = max(2, min(7, dynamic_max_weight))
    reader_adjust = {"fatigue_limit": False, "tension_limit": False, "clarity_reveal_boost": False, "expectation_hook_boost": False}
    if reader["fatigue"] > 0.65:
        dynamic_max_weight = min(dynamic_max_weight, 3)
        reader_adjust["fatigue_limit"] = True
    tension_overload = reader["tension"] > 0.85
    if tension_overload:
        reader_adjust["tension_limit"] = True
    clarity_low = reader["clarity"] < 0.35
    expectation_low = reader["expectation"] < 0.4
    if clarity_low:
        reader_adjust["clarity_reveal_boost"] = True
    if expectation_low:
        reader_adjust["expectation_hook_boost"] = True
    candidates: list[dict] = []
    dropped: list[dict] = []

    g = growth_task if isinstance(growth_task, dict) else {}
    gm = g.get("milestone") if isinstance(g.get("milestone"), dict) else {}
    g_action = str(g.get("action") or "none").strip().lower()
    if g_action != "none" and gm:
        stage = str(gm.get("stage") or "").strip().lower()
        ttype = "breakthrough" if (g_action == "achieve" or stage == "breakthrough") else ("integration" if g_action == "reflect" else "growth_pressure")
        intensity = 3 if ttype == "breakthrough" else (2 if stage == "cost" else 1)
        candidates.append(
            {
                "task_type": ttype,
                "intensity": intensity,
                "source": "growth",
                "priority": int(gm.get("priority") or 3),
                "must_happen": ttype == "breakthrough",
                "milestone_id": str(gm.get("milestone_id") or ""),
            }
        )

    fs = foreshadow_selection if isinstance(foreshadow_selection, dict) else {}
    for i, x in enumerate(fs.get("payoff") if isinstance(fs.get("payoff"), list) else []):
        if not isinstance(x, dict):
            continue
        tpl = x.get("payoff_template") if isinstance(x.get("payoff_template"), dict) else {}
        intensity = int(tpl.get("intensity_level") or fs.get("payoff_intensity") or 2)
        candidates.append(
            {
                "task_type": "payoff",
                "intensity": max(1, min(3, intensity)),
                "source": "foreshadow",
                "priority": int(x.get("priority") or 3) + (1 if i == 0 else 0),
                "must_happen": i == 0 and pv > 0.8,
                "foreshadow_id": str(x.get("foreshadow_id") or ""),
                "foreshadow_payload": x,
                "payoff_rank": i,
            }
        )
    for x in fs.get("reinforce") if isinstance(fs.get("reinforce"), list) else []:
        if not isinstance(x, dict):
            continue
        candidates.append(
            {
                "task_type": "reinforce",
                "intensity": 1,
                "source": "foreshadow",
                "priority": int(x.get("priority") or 2),
                "must_happen": False,
                "foreshadow_id": str(x.get("foreshadow_id") or ""),
                "foreshadow_payload": x,
            }
        )
    for x in fs.get("seed") if isinstance(fs.get("seed"), list) else []:
        if not isinstance(x, dict):
            continue
        candidates.append(
            {
                "task_type": "seed",
                "intensity": 1,
                "source": "foreshadow",
                "priority": int(x.get("priority") or 2),
                "must_happen": False,
                "foreshadow_id": str(x.get("foreshadow_id") or ""),
                "foreshadow_payload": x,
            }
        )

    if enable_combo and isinstance(plan_items, list):
        for it in plan_items:
            if not isinstance(it, dict) or str(it.get("kind") or "").strip().lower() != "combo":
                continue
            pmin = _clamp01(float(it.get("target_p_vol_min") or 0.0))
            pmax = _clamp01(float(it.get("target_p_vol_max") or 1.0))
            if not (pmin <= pv <= pmax):
                continue
            it_meta = it.get("meta") if isinstance(it.get("meta"), dict) else {}
            combo_type = str(it_meta.get("combo_type") or "vol_end_combo")
            combo_pattern = it_meta.get("combo_pattern") if isinstance(it_meta.get("combo_pattern"), dict) else {}
            steps = combo_pattern.get("steps") if isinstance(combo_pattern.get("steps"), list) else []
            closing = 1.0 - max(0.0, min(1.0, pmax - pv))
            overdue = pv > pmax
            for step in steps:
                if not isinstance(step, dict):
                    continue
                ttype = _combo_task_type(step)
                intensity = int(step.get("intensity") or 1)
                candidates.append(
                    {
                        "task_type": ttype,
                        "intensity": max(1, min(3, intensity)),
                        "source": "combo",
                        "priority": int(it.get("priority") or 3),
                        "must_happen": bool(it.get("must_happen")),
                        "combo_id": str(it.get("ref_id") or ""),
                        "combo_type": combo_type,
                        "combo_fingerprint": str(it_meta.get("combo_fingerprint") or ""),
                        "window_closing": closing,
                        "overdue": overdue,
                    }
                )

    merged: list[dict] = []
    used = [False] * len(candidates)
    for i, a in enumerate(candidates):
        if used[i]:
            continue
        if str(a.get("task_type") or "") == "reveal":
            for j, b in enumerate(candidates):
                if i == j or used[j]:
                    continue
                if str(b.get("task_type") or "") == "payoff" and str(a.get("source") or "") == "combo" and str(b.get("source") or "") == "combo":
                    merged_task = dict(b)
                    merged_task["task_type"] = "payoff"
                    merged_task["intensity"] = max(int(a.get("intensity") or 1), int(b.get("intensity") or 1))
                    merged_task["merge_note"] = "merge_reveal_payoff"
                    merged.append(merged_task)
                    used[i] = True
                    used[j] = True
                    break
        if used[i]:
            continue
        if str(a.get("task_type") or "") == "seed":
            for j, b in enumerate(candidates):
                if i == j or used[j]:
                    continue
                if str(b.get("task_type") or "") == "cliff" and str(a.get("source") or "") == "combo" and str(b.get("source") or "") == "combo":
                    merged_task = dict(b)
                    merged_task["task_type"] = "cliff"
                    merged_task["intensity"] = max(int(a.get("intensity") or 1), int(b.get("intensity") or 1))
                    merged_task["merge_note"] = "merge_seed_cliff"
                    merged.append(merged_task)
                    used[i] = True
                    used[j] = True
                    break
        if not used[i]:
            merged.append(dict(a))
            used[i] = True

    for x in merged:
        x["window_closing"] = float(x.get("window_closing") or 0.0)
        x["overdue"] = bool(x.get("overdue"))
        x["must_happen"] = bool(x.get("must_happen"))
        x["weight"] = _task_weight(str(x.get("task_type") or ""), int(x.get("intensity") or 1))
        align = _task_curve_alignment(str(x.get("task_type") or ""), structure)
        x["curve_alignment"] = align
        x["priority_score"] = (
            (5.0 if x["must_happen"] else 0.0)
            + (4.0 if x["overdue"] else 0.0)
            + (3.0 * float(x["window_closing"]))
            + (2.0 * float(x.get("priority") or 0.0))
            + (2.0 * align)
            + (1.0 if str(x.get("source") or "") == "combo" else 0.0)
        )
        ttype = str(x.get("task_type") or "")
        if clarity_low and ttype in {"reveal", "payoff"}:
            x["priority_score"] = float(x["priority_score"]) + 1.5
        if expectation_low and ttype in {"hook", "cliff"}:
            x["priority_score"] = float(x["priority_score"]) + 1.2
        if reader["satisfaction"] > 0.8 and ttype in {"seed", "new_lead"}:
            x["priority_score"] = float(x["priority_score"]) + 1.0
    merged.sort(key=lambda z: float(z.get("priority_score") or 0.0), reverse=True)

    selected: list[dict] = []
    used_weight = 0
    has_breakthrough = False
    heavy_payoff = False
    has_reveal = False
    main_payoff_combo = ""
    for c in merged:
        ttype = str(c.get("task_type") or "")
        if len(selected) >= int(max_tasks):
            dropped.append({"task_type": ttype, "reason": "task_cap_reached", "source": str(c.get("source") or "")})
            continue
        if used_weight + int(c.get("weight") or 1) > dynamic_max_weight:
            dropped.append({"task_type": ttype, "reason": "structure_overload", "source": str(c.get("source") or "")})
            continue
        if ttype == "breakthrough":
            if has_breakthrough:
                dropped.append({"task_type": ttype, "reason": "semantic_conflict_breakthrough", "source": str(c.get("source") or "")})
                continue
        if ttype == "payoff" and int(c.get("intensity") or 1) >= 3:
            if heavy_payoff:
                dropped.append({"task_type": ttype, "reason": "semantic_conflict_heavy_payoff", "source": str(c.get("source") or "")})
                continue
            if has_reveal:
                dropped.append({"task_type": ttype, "reason": "pacing_conflict_reveal_heavy_payoff", "source": str(c.get("source") or "")})
                continue
            if tension_overload:
                dropped.append({"task_type": ttype, "reason": "reader_tension_overload", "source": str(c.get("source") or "")})
                continue
        if ttype == "reveal" and has_reveal:
            dropped.append({"task_type": ttype, "reason": "semantic_conflict_reveal_repeat", "source": str(c.get("source") or "")})
            continue
        if ttype == "seed" and main_payoff_combo and str(c.get("combo_type") or "") != "vol_end_combo":
            dropped.append({"task_type": ttype, "reason": "pacing_conflict_seed_vs_main_payoff", "source": str(c.get("source") or "")})
            continue
        if ttype == "cliff" and tension_overload:
            dropped.append({"task_type": ttype, "reason": "reader_tension_overload", "source": str(c.get("source") or "")})
            continue
        selected.append(c)
        used_weight += int(c.get("weight") or 1)
        if ttype == "breakthrough":
            has_breakthrough = True
        if ttype == "payoff" and int(c.get("intensity") or 1) >= 3:
            heavy_payoff = True
            main_payoff_combo = str(c.get("combo_type") or "")
        if ttype == "reveal":
            has_reveal = True

    selected_growth = any(str(x.get("source") or "") == "growth" for x in selected)
    if selected_growth:
        growth_final = g
    else:
        growth_final = {
            "action": "none",
            "milestone": None,
            "requirements": {"cost_must_show": False, "choice_must_be_explicit": False},
            "why": "orchestrator_dropped",
        }

    sel_seed_ids = {
        str(x.get("foreshadow_id") or "")
        for x in selected
        if str(x.get("task_type") or "") == "seed" and str(x.get("foreshadow_id") or "")
    }
    sel_reinforce_ids = {
        str(x.get("foreshadow_id") or "")
        for x in selected
        if str(x.get("task_type") or "") == "reinforce" and str(x.get("foreshadow_id") or "")
    }
    sel_payoff_ids = {
        str(x.get("foreshadow_id") or "")
        for x in selected
        if str(x.get("task_type") or "") == "payoff" and str(x.get("foreshadow_id") or "")
    }
    seed_final = [x for x in (fs.get("seed") if isinstance(fs.get("seed"), list) else []) if str((x or {}).get("foreshadow_id") or "") in sel_seed_ids]
    reinforce_final = [x for x in (fs.get("reinforce") if isinstance(fs.get("reinforce"), list) else []) if str((x or {}).get("foreshadow_id") or "") in sel_reinforce_ids]
    payoff_final = [x for x in (fs.get("payoff") if isinstance(fs.get("payoff"), list) else []) if str((x or {}).get("foreshadow_id") or "") in sel_payoff_ids]
    foreshadow_final = {
        **fs,
        "seed": seed_final,
        "reinforce": reinforce_final,
        "payoff": payoff_final,
        "selected_ids": sorted(list({*sel_seed_ids, *sel_reinforce_ids, *sel_payoff_ids})),
        "block": _build_foreshadow_task_block(seed_final, reinforce_final, payoff_final),
    }

    selected_combo_rows = [x for x in selected if str(x.get("source") or "") == "combo"]
    combo_selected = []
    seen_combo = set()
    for x in selected_combo_rows:
        cid = str(x.get("combo_id") or "")
        cfp = str(x.get("combo_fingerprint") or "")
        key = f"{cid}:{cfp}"
        if key in seen_combo:
            continue
        seen_combo.add(key)
        combo_selected.append(
            {
                "combo_id": cid,
                "combo_fingerprint": cfp,
                "combo_type": str(x.get("combo_type") or ""),
            }
        )
    combo_block = _build_combo_task_block(selected_combo_rows)
    delayed = [
        x
        for x in dropped
        if str(x.get("reason") or "") in {"structure_overload", "task_cap_reached"}
    ]
    return {
        "growth_task": growth_final,
        "foreshadow_selection": foreshadow_final,
        "combo_block": combo_block,
        "selected_combo": combo_selected,
        "trace": {
            "window": win,
            "reader_state": reader,
            "reader_adjustments": reader_adjust,
            "max_tasks": int(max_tasks),
            "max_weight": int(dynamic_max_weight),
            "used_weight": int(used_weight),
            "kept": [
                {
                    "task_type": str(x.get("task_type") or ""),
                    "source": str(x.get("source") or ""),
                    "priority_score": round(float(x.get("priority_score") or 0.0), 6),
                    "weight": int(x.get("weight") or 1),
                    "intensity": int(x.get("intensity") or 1),
                    "combo_type": str(x.get("combo_type") or ""),
                    "merge_note": str(x.get("merge_note") or ""),
                }
                for x in selected
            ],
            "dropped": dropped,
            "delayed": delayed,
            "candidate_count": len(merged),
            "enable_combo": bool(enable_combo),
        },
    }


async def _foreshadow_audit_snapshot(
    db: AsyncSession,
    *,
    book_id: str,
    chapter_no: int | None,
) -> dict:
    rows = await db.execute(
        text(
            """
            SELECT f.foreshadow_id::text AS foreshadow_id, f.scope, f.status, c."order" AS created_chapter_no, cp."order" AS planned_payoff_no
            FROM foreshadow f
            LEFT JOIN chapter c ON c.chapter_id=f.created_chapter_id
            LEFT JOIN chapter cp ON cp.chapter_id=f.planned_payoff_chapter_id
            WHERE f.book_id=CAST(:book_id AS uuid)
            """
        ),
        {"book_id": book_id},
    )
    seeded_count = 0
    reinforced_count = 0
    payoff_count = 0
    overdue = 0
    dangling = 0
    now_no = int(chapter_no or 0)
    for r in rows.mappings().all():
        status = str(r.get("status") or "")
        scope = str(r.get("scope") or "")
        created_no = int(r.get("created_chapter_no") or 0)
        planned_no = int(r.get("planned_payoff_no") or 0)
        if status == "seeded":
            seeded_count += 1
        if status == "reinforced":
            reinforced_count += 1
        if status in {"paid_off", "closed"}:
            payoff_count += 1
        is_open = status in {"seeded", "reinforced", "payoff_planned"}
        if is_open:
            if scope == "chapter" and now_no > 0 and created_no > 0 and (now_no - created_no) > 3:
                overdue += 1
            if scope == "volume" and now_no > 0 and planned_no > 0 and now_no > planned_no:
                overdue += 1
            if now_no > 0 and created_no > 0 and (now_no - created_no) > 8:
                dangling += 1
    return {
        "seeded_count": seeded_count,
        "reinforced_count": reinforced_count,
        "payoff_count": payoff_count,
        "overdue_payoff": overdue,
        "dangling": dangling,
    }


def _foreshadow_status_by_event(event_type: str) -> str | None:
    et = str(event_type or "").strip().lower()
    if et == "seed":
        return "seeded"
    if et in {"reinforce", "hint"}:
        return "reinforced"
    if et in {"payoff", "close"}:
        return "paid_off"
    if et == "retcon":
        return "retcon"
    if et == "drop":
        return "dropped"
    return None


def _fingerprint_material(tag: str, content: dict) -> str | None:
    t = str(tag or "").strip().lower()
    if t == "hook":
        pat = _norm_fp_text(content.get("pattern"))
        slots = content.get("slots") if isinstance(content.get("slots"), list) else []
        slots_s = "|".join(sorted([str(x).strip() for x in slots if str(x).strip()]))
        base = f"hook|{pat}|{slots_s}"
        return _sha1_hex(base) if pat or slots_s else None
    if t == "conflict_beat":
        beats = content.get("beats") if isinstance(content.get("beats"), list) else []
        beats_s = ">".join([_norm_fp_text(x, 60) for x in beats])[:300]
        hint = _norm_fp_text(content.get("rewrite_hint"), 200)
        base = f"beat|{beats_s}|{hint}"
        return _sha1_hex(base) if beats_s or hint else None
    if t == "style_pattern":
        rr = content.get("rhythm_rules") if isinstance(content.get("rhythm_rules"), list) else []
        tb = content.get("taboos") if isinstance(content.get("taboos"), list) else []
        base = f"style|{_norm_fp_text('|'.join([str(x) for x in rr]), 300)}|{_norm_fp_text('|'.join([str(x) for x in tb]), 300)}"
        return _sha1_hex(base) if rr or tb else None
    raw = _norm_fp_text(json.dumps(content, ensure_ascii=False) if isinstance(content, dict) else str(content), 400)
    return _sha1_hex(f"{t}|{raw}") if raw else None


def _fingerprint_template(purpose: str, template_text: str, slots: list[object]) -> str | None:
    slots_s = "|".join(sorted([str(x).strip() for x in (slots or []) if str(x).strip()]))
    head = _norm_fp_text(str(template_text or "")[:600], 600)
    base = f"tpl|{str(purpose or 'draft').lower()}|{slots_s}|{head}"
    return _sha1_hex(base) if slots_s or head else None


def _tags_overlap(tags: list[str], ctx_tags: list[str]) -> int:
    if not tags or not ctx_tags:
        return 0
    s = set([str(x).strip().lower() for x in ctx_tags if str(x).strip()])
    return sum(1 for x in tags if str(x).strip().lower() in s)


async def _load_recent_usage_counts(db: AsyncSession, *, book_id: str, cooldown_cfg: dict) -> dict[str, int]:
    days = max(1, min(int(cooldown_cfg.get("time_window_days") or 14), 90))
    window_uses = max(1, min(int(cooldown_cfg.get("window_uses") or 20), 200))
    rows = await db.execute(
        text(
            """
            SELECT injected_material_ids, injected_template_ids
            FROM asset_usage_log
            WHERE book_id=CAST(:book_id AS uuid)
              AND assets_injection=true
              AND created_at > now() - make_interval(days => :days)
            ORDER BY created_at DESC
            LIMIT :window_uses
            """
        ),
        {"book_id": book_id, "days": days, "window_uses": window_uses},
    )
    out: dict[str, int] = {}
    for r in rows.mappings().all():
        mids = r.get("injected_material_ids") if isinstance(r.get("injected_material_ids"), list) else []
        tids = r.get("injected_template_ids") if isinstance(r.get("injected_template_ids"), list) else []
        for mid in mids:
            k = f"material:{str(mid)}"
            out[k] = int(out.get(k) or 0) + 1
        for tid in tids:
            k = f"template:{str(tid)}"
            out[k] = int(out.get(k) or 0) + 1
    return out


async def _resolve_default_assets_injection(
    db: AsyncSession,
    *,
    book_id: str,
    max_hooks: int = 2,
    max_beats: int = 2,
    max_styles: int = 1,
    max_templates: int = 1,
    max_chars: int = 2000,
    ctx_tags: list[str] | None = None,
    settings_effective: dict | None = None,
) -> dict:
    def _empty(bundle_id_value: str | None = None) -> dict:
        return {"bundle_id": bundle_id_value, "block": "", "counts": {"hooks": 0, "beats": 0, "styles": 0, "templates": 0}}

    row = await db.execute(
        text("SELECT bundle_id FROM book_default_assets WHERE book_id=CAST(:book_id AS uuid)"),
        {"book_id": book_id},
    )
    bundle = row.scalar()
    if not bundle:
        return _empty(None)
    bundle_id = str(bundle)
    effective = settings_effective if isinstance(settings_effective, dict) else {}
    assets_cfg = effective.get("assets") if isinstance(effective.get("assets"), dict) else {}
    risk_cfg = assets_cfg.get("risk") if isinstance(assets_cfg.get("risk"), dict) else {}
    select_cfg = assets_cfg.get("select") if isinstance(assets_cfg.get("select"), dict) else {}
    cooldown_cfg = assets_cfg.get("cooldown") if isinstance(assets_cfg.get("cooldown"), dict) else {}
    risk_block_threshold = float(risk_cfg.get("block_threshold") or 0.25)
    epsilon = max(0.0, min(1.0, float(select_cfg.get("epsilon") or 0.1)))
    top_k = max(1, min(100, int(select_cfg.get("top_k") or 10)))
    hard_cap = max(1, min(20, int(cooldown_cfg.get("hard_cap") or 3)))
    penalty_per_use = max(0.0, min(1.0, float(cooldown_cfg.get("penalty_per_use") or 0.12)))
    pinned_penalty_multiplier = max(0.0, min(1.0, float(cooldown_cfg.get("pinned_penalty_multiplier") or 0.5)))

    bmeta_res = await db.execute(
        text("SELECT status, risk_score FROM asset_bundle WHERE bundle_id=CAST(:bundle_id AS uuid)"),
        {"bundle_id": bundle_id},
    )
    bmeta = bmeta_res.mappings().first() or {}
    if str(bmeta.get("status") or "") != "ready":
        return _empty(bundle_id)
    risk_val = float(bmeta.get("risk_score")) if bmeta.get("risk_score") is not None else 0.0
    if risk_val >= risk_block_threshold:
        return _empty(bundle_id)

    items_res = await db.execute(
        text("SELECT item_type, item_id::text AS item_id FROM asset_bundle_item WHERE bundle_id=CAST(:bundle_id AS uuid)"),
        {"bundle_id": bundle_id},
    )
    items = items_res.mappings().all()
    mat_ids = [str(x["item_id"]) for x in items if str(x.get("item_type") or "") == "material"]
    tpl_ids = [str(x["item_id"]) for x in items if str(x.get("item_type") or "") == "template"]
    if not mat_ids and not tpl_ids:
        return _empty(bundle_id)

    recent_count_map = await _load_recent_usage_counts(db, book_id=book_id, cooldown_cfg=cooldown_cfg)
    lower_ctx_tags = [str(x).strip().lower() for x in (ctx_tags or []) if str(x).strip()]

    materials: list[dict] = []
    templates: list[dict] = []
    if mat_ids:
        mres = await db.execute(
            text(
                """
                SELECT
                  m.card_id::text AS card_id, m.title, m.content, m.tag, m.risk_score, m.policy, m.fingerprint, m.extract_meta,
                  COALESCE(s.weight, 0) AS learned_weight
                FROM material_card m
                LEFT JOIN asset_score_stat s
                  ON s.item_type='material' AND s.item_id=m.card_id AND s.book_id=CAST(:book_id AS uuid)
                WHERE m.card_id = ANY(CAST(:ids AS uuid[]))
                """
            ),
            {"ids": mat_ids, "book_id": book_id},
        )
        materials = [dict(r) for r in mres.mappings().all()]
    if tpl_ids:
        tres = await db.execute(
            text(
                """
                SELECT
                  t.template_id::text AS template_id, t.name, t.purpose, t.template, t.slots, t.tags, t.risk_score, t.policy, t.fingerprint, t.extract_meta,
                  COALESCE(s.weight, 0) AS learned_weight
                FROM prompt_template t
                LEFT JOIN asset_score_stat s
                  ON s.item_type='template' AND s.item_id=t.template_id AND s.book_id=CAST(:book_id AS uuid)
                WHERE t.template_id = ANY(CAST(:ids AS uuid[]))
                """
            ),
            {"ids": tpl_ids, "book_id": book_id},
        )
        templates = [dict(r) for r in tres.mappings().all()]

    def _score_common(
        *,
        item_type: str,
        item_id: str,
        policy: str,
        risk_score: object,
        learned_weight: object,
        tags: list[str],
        good_tags: list[str],
        bad_tags: list[str],
    ) -> tuple[float, bool, int, str | None, dict]:
        p = str(policy or "normal").strip().lower()
        overlap = _tags_overlap(tags, lower_ctx_tags)
        good_overlap = _tags_overlap(good_tags, lower_ctx_tags)
        bad_overlap = _tags_overlap(bad_tags, lower_ctx_tags)
        learned = float(learned_weight or 0.0)
        risk_raw = float(risk_score or 0.0)
        risk_penalty = min(0.35, risk_raw) * 0.5
        rc = int(recent_count_map.get(f"{item_type}:{item_id}") or 0)
        breakdown = {
            "tag_overlap": overlap,
            "tag_score": overlap * 1.0,
            "good_tag_overlap": good_overlap,
            "good_tag_bonus": good_overlap * 0.6,
            "bad_tag_overlap": bad_overlap,
            "bad_tag_penalty": bad_overlap * 0.8,
            "learned_weight": learned,
            "learned_score": learned * 1.5,
            "risk_score": risk_raw,
            "risk_penalty": risk_penalty,
            "cooldown_count": rc,
            "cooldown_penalty": 0.0,
            "pin_bonus": 0.5 if p == "pinned" else 0.0,
            "policy": p,
        }
        if p == "banned":
            return (-1e9, True, rc, "banned", breakdown)
        score = overlap * 1.0 + learned * 1.5 - risk_penalty
        score += good_overlap * 0.6
        score -= bad_overlap * 0.8
        if bad_overlap > 0 and p != "pinned":
            return (-1e9, True, rc, "tag_bad_match", breakdown)
        if p == "pinned":
            score += 0.5
        if rc >= hard_cap:
            return (-1e9, True, rc, "cooldown_hard_cap", breakdown)
        cd_penalty = rc * penalty_per_use * (pinned_penalty_multiplier if p == "pinned" else 1.0)
        breakdown["cooldown_penalty"] = cd_penalty
        score -= cd_penalty
        return (score, False, rc, None, breakdown)

    filtered: dict[str, list[dict]] = {"hooks": [], "beats": [], "styles": [], "templates": []}
    hook_cands: list[dict] = []
    beat_cands: list[dict] = []
    style_cands: list[dict] = []
    for m in materials:
        mid = str(m.get("card_id") or "")
        tag = str(m.get("tag") or "").strip().lower()
        c = _try_parse_json_text(m.get("content"))
        em = m.get("extract_meta") if isinstance(m.get("extract_meta"), dict) else {}
        good_tags = [str(x).strip().lower() for x in (em.get("good_tags") or []) if str(x).strip()]
        bad_tags = [str(x).strip().lower() for x in (em.get("bad_tags") or []) if str(x).strip()]
        fp = str(m.get("fingerprint") or "").strip() or (_fingerprint_material(tag, c) or "")
        tags = [tag] if tag else []
        score, blocked, _, reason, breakdown = _score_common(
            item_type="material",
            item_id=mid,
            policy=str(m.get("policy") or "normal"),
            risk_score=m.get("risk_score"),
            learned_weight=m.get("learned_weight"),
            tags=tags,
            good_tags=good_tags,
            bad_tags=bad_tags,
        )
        if blocked:
            filtered["hooks" if tag == "hook" else ("beats" if tag == "conflict_beat" else ("styles" if tag == "style_pattern" else "hooks"))].append(
                {"id": mid, "reason": reason or "filtered"}
            )
            continue
        rec = {
            "card_id": mid,
            "title": str(m.get("title") or ""),
            "policy": str(m.get("policy") or "normal").lower(),
            "fingerprint": fp,
            "_score": score,
            "_breakdown": breakdown,
        }
        if tag == "hook":
            rec["pattern"] = str(c.get("pattern") or "")
            rec["rewrite_example"] = str(c.get("rewrite_example") or "")
            hook_cands.append(rec)
        elif tag == "conflict_beat":
            rec["beats"] = c.get("beats") if isinstance(c.get("beats"), list) else []
            rec["rewrite_hint"] = str(c.get("rewrite_hint") or "")
            beat_cands.append(rec)
        elif tag == "style_pattern":
            rec["metrics"] = c
            style_cands.append(rec)

    tpl_cands: list[dict] = []
    for t in templates:
        tid = str(t.get("template_id") or "")
        tags = [str(x).strip().lower() for x in (t.get("tags") or []) if str(x).strip()]
        em = t.get("extract_meta") if isinstance(t.get("extract_meta"), dict) else {}
        good_tags = [str(x).strip().lower() for x in (em.get("good_tags") or []) if str(x).strip()]
        bad_tags = [str(x).strip().lower() for x in (em.get("bad_tags") or []) if str(x).strip()]
        fp = str(t.get("fingerprint") or "").strip() or (
            _fingerprint_template(str(t.get("purpose") or "draft"), str(t.get("template") or ""), t.get("slots") if isinstance(t.get("slots"), list) else [])
            or ""
        )
        score, blocked, _, reason, breakdown = _score_common(
            item_type="template",
            item_id=tid,
            policy=str(t.get("policy") or "normal"),
            risk_score=t.get("risk_score"),
            learned_weight=t.get("learned_weight"),
            tags=tags,
            good_tags=good_tags,
            bad_tags=bad_tags,
        )
        if blocked:
            filtered["templates"].append({"id": tid, "reason": reason or "filtered"})
            continue
        tpl_cands.append(
            {
                "template_id": tid,
                "name": str(t.get("name") or ""),
                "purpose": str(t.get("purpose") or "draft"),
                "template": str(t.get("template") or ""),
                "policy": str(t.get("policy") or "normal").lower(),
                "fingerprint": fp,
                "_score": score,
                "_breakdown": breakdown,
            }
        )

    def _top_rows(cands: list[dict]) -> list[dict]:
        arr = sorted(cands, key=lambda x: float(x.get("_score") or 0.0), reverse=True)[:top_k]
        out: list[dict] = []
        for c in arr:
            out.append(
                {
                    "id": str(c.get("card_id") or c.get("template_id") or ""),
                    "title": str(c.get("title") or c.get("name") or ""),
                    "fingerprint": str(c.get("fingerprint") or ""),
                    "score_total": round(float(c.get("_score") or 0.0), 6),
                    "breakdown": c.get("_breakdown") if isinstance(c.get("_breakdown"), dict) else {},
                    "filtered_reason": None,
                }
            )
        return out

    def _pick(cands: list[dict], n: int, used_fp: set[str], filtered_rows: list[dict]) -> list[dict]:
        if n <= 0:
            return []
        arr = sorted(cands, key=lambda x: float(x.get("_score") or 0.0), reverse=True)
        pinned = [x for x in arr if str(x.get("policy") or "normal") == "pinned"]
        normals = [x for x in arr if str(x.get("policy") or "normal") != "pinned"]
        out: list[dict] = []
        for src in (pinned, normals):
            while src and len(out) < n:
                choose_idx = 0
                if src is normals and len(src) > 1 and random.random() < epsilon:
                    choose_idx = random.randint(0, min(len(src), top_k) - 1)
                cand = src.pop(choose_idx)
                fp = str(cand.get("fingerprint") or "").strip()
                if fp and fp in used_fp:
                    filtered_rows.append({"id": str(cand.get("card_id") or cand.get("template_id") or ""), "reason": "fingerprint_duplicate"})
                    continue
                out.append(cand)
                if fp:
                    used_fp.add(fp)
        return out

    used_fps: set[str] = set()
    hooks_top = _top_rows(hook_cands)
    beats_top = _top_rows(beat_cands)
    styles_top = _top_rows(style_cands)
    templates_top = _top_rows(tpl_cands)
    hooks = _pick(hook_cands, max(0, int(max_hooks)), used_fps, filtered["hooks"])
    beats = _pick(beat_cands, max(0, int(max_beats)), used_fps, filtered["beats"])
    styles = _pick(style_cands, max(0, int(max_styles)), used_fps, filtered["styles"])
    templates_sel = _pick(tpl_cands, max(0, int(max_templates)), used_fps, filtered["templates"])

    lines: list[str] = []
    lines.append(f"[ASSETS_INJECTION v1 bundle={bundle_id}]")
    lines.append("Rules: 仅借结构与节奏，不得照抄句子；必须替换实体名并重排语序。")
    if hooks:
        lines.append("- Hook Patterns:")
        for i, h in enumerate(hooks, start=1):
            lines.append(f"  {i}) {h['title']} pattern={str(h.get('pattern') or '')[:180]}")
            if h.get("rewrite_example"):
                lines.append(f"     rewrite_example={str(h['rewrite_example'])[:220]}")
    if beats:
        lines.append("- Conflict Beats:")
        for i, b in enumerate(beats, start=1):
            beat_s = " > ".join([str(x) for x in (b.get("beats") or [])][:7])
            lines.append(f"  {i}) {b['title']} beats={beat_s}")
            if b.get("rewrite_hint"):
                lines.append(f"     hint={str(b['rewrite_hint'])[:220]}")
    if styles:
        sm = styles[0].get("metrics") if isinstance(styles[0].get("metrics"), dict) else {}
        lines.append("- Style Micro-pattern:")
        lines.append(
            "  sentence_avg_len="
            + str(sm.get("sentence_avg_len", "-"))
            + " short_sentence_ratio="
            + str(sm.get("short_sentence_ratio", "-"))
            + " dialog_ratio="
            + str(sm.get("dialog_ratio", "-"))
        )
    if templates_sel:
        t0 = templates_sel[0]
        lines.append(f"- Prompt Template: {str(t0.get('name') or '')}")
        lines.append(f"  guidance={str(t0.get('template') or '')[:600]}")
    lines.append("[/ASSETS_INJECTION]")
    block = "\n".join(lines)
    if len(block) > int(max_chars):
        block = block[: max(0, int(max_chars) - 24)] + "\n[/ASSETS_INJECTION]"
    explain = {
        "version": "v1",
        "cooldown_cfg": {
            "window_uses": int(cooldown_cfg.get("window_uses") or 20),
            "time_window_days": int(cooldown_cfg.get("time_window_days") or 14),
            "hard_cap": hard_cap,
            "penalty_per_use": penalty_per_use,
            "pinned_penalty_multiplier": pinned_penalty_multiplier,
        },
        "selection": {
            "hooks": {
                "picked": [str(x.get("card_id") or "") for x in hooks if str(x.get("card_id") or "")],
                "top": hooks_top,
                "filtered": filtered["hooks"],
            },
            "beats": {
                "picked": [str(x.get("card_id") or "") for x in beats if str(x.get("card_id") or "")],
                "top": beats_top,
                "filtered": filtered["beats"],
            },
            "styles": {
                "picked": [str(x.get("card_id") or "") for x in styles if str(x.get("card_id") or "")],
                "top": styles_top,
                "filtered": filtered["styles"],
            },
            "templates": {
                "picked": [str(x.get("template_id") or "") for x in templates_sel if str(x.get("template_id") or "")],
                "top": templates_top,
                "filtered": filtered["templates"],
            },
        },
    }
    return {
        "bundle_id": bundle_id,
        "block": block,
        "material_ids": [str(x.get("card_id") or "") for x in (hooks + beats + styles) if str(x.get("card_id") or "").strip()],
        "template_ids": [str(x.get("template_id") or "") for x in templates_sel if str(x.get("template_id") or "").strip()],
        "counts": {"hooks": len(hooks), "beats": len(beats), "styles": len(styles), "templates": len(templates_sel)},
        "trace": explain,
    }


async def _extract_assets_internal(
    db: AsyncSession,
    *,
    text_ver_id: str,
    batch_id: str | None = None,
    mode: str = "safe",
    max_cards: int = 12,
    max_templates: int = 6,
) -> dict:
    row = await db.execute(
        text(
            """
            SELECT tv.text_ver_id, tv.chapter_id, tv.content, tv.profile_id_used, tv.profile_version_used, c.book_id
            FROM chapter_text_version tv
            JOIN chapter c ON c.chapter_id=tv.chapter_id
            WHERE tv.text_ver_id=CAST(:text_ver_id AS uuid)
            """
        ),
        {"text_ver_id": text_ver_id},
    )
    tv = row.mappings().first()
    if not tv:
        raise HTTPException(status_code=404, detail="TEXT_VERSION_NOT_FOUND")
    chapter_id = str(tv["chapter_id"])
    book_id = str(tv["book_id"])
    text_value = str(tv.get("content") or "")
    profile_id_used = str(tv.get("profile_id_used")) if tv.get("profile_id_used") else None
    profile_version_used = int(tv.get("profile_version_used")) if tv.get("profile_version_used") is not None else None
    cfg = {"mode": mode, "max_cards": int(max_cards), "max_templates": int(max_templates)}

    run_res = await db.execute(
        text(
            """
            INSERT INTO extraction_run(kind, book_id, chapter_id, text_ver_id, batch_id, status, config)
            VALUES (
              'winner_assets',
              CAST(:book_id AS uuid),
              CAST(:chapter_id AS uuid),
              CAST(:text_ver_id AS uuid),
              CAST(:batch_id AS uuid),
              'running',
              CAST(:config AS jsonb)
            )
            RETURNING run_id
            """
        ),
        {
            "book_id": book_id,
            "chapter_id": chapter_id,
            "text_ver_id": text_ver_id,
            "batch_id": batch_id,
            "config": json.dumps(cfg, ensure_ascii=False),
        },
    )
    run_id = str(run_res.scalar_one())
    bundle_res = await db.execute(
        text(
            """
            INSERT INTO asset_bundle(book_id, chapter_id, batch_id, text_ver_id, kind, status, note)
            VALUES (
              CAST(:book_id AS uuid),
              CAST(:chapter_id AS uuid),
              CAST(:batch_id AS uuid),
              CAST(:text_ver_id AS uuid),
              'winner_assets',
              'ready',
              ''
            )
            RETURNING bundle_id
            """
        ),
        {"book_id": book_id, "chapter_id": chapter_id, "batch_id": batch_id, "text_ver_id": text_ver_id},
    )
    bundle_id = str(bundle_res.scalar_one())
    await db.commit()

    try:
        style = _simple_style_metrics(text_value)
        hook_cards = [
            {
                "title": "目标-代价钩子",
                "pattern": "在首段给出目标并立刻绑定代价或时限，制造推进压力",
                "rewrite_example": "他必须在天亮前做出选择，否则会失去关键同盟。",
                "tags": ["hook", "pressure"],
            },
            {
                "title": "信息差钩子",
                "pattern": "先展示结果异样，再延后解释原因",
                "rewrite_example": "门已经开着，但本该在门内的人不见了。",
                "tags": ["hook", "mystery"],
            },
        ][: max(1, min(int(max_cards), 12))]
        beat_cards = [
            {
                "title": "冲突五拍",
                "beats": ["desire", "obstacle", "cost", "turn", "aftershock"],
                "rewrite_hint": "每一拍都要体现选择成本，不要只写结果",
                "tags": ["conflict", "beat"],
            }
        ][: max(1, min(int(max_cards), 12))]
        tpl_cards = [
            {
                "name": "Draft-冲突推进模板",
                "purpose": "draft",
                "template": "围绕{{goal}}推进一段冲突：先给阻力{{obstacle}}，再给代价{{cost}}，最后用{{turn}}形成下一段钩子。",
                "slots": ["{{goal}}", "{{obstacle}}", "{{cost}}", "{{turn}}"],
                "tags": ["draft", "conflict"],
            }
        ][: max(1, min(int(max_templates), 6))]

        excerpt_count = 0 if mode == "safe" else 1
        risk_score = round(max(0.0, min(1.0, excerpt_count * 0.1)), 3)
        status = "blocked" if risk_score >= 0.25 else "ready"

        material_ids: list[str] = []
        template_ids: list[str] = []
        for h in hook_cards:
            card_res = await db.execute(
                text(
                    """
                    INSERT INTO material_card(
                      book_id, source_type, title, content, tag, importance,
                      source_text_ver_id, source_batch_id, profile_id_used, profile_version_used, risk_score, extract_meta,
                      policy, fingerprint
                    )
                    VALUES (
                      CAST(:book_id AS uuid), 'winner_extract', :title, :content, :tag, 4,
                      CAST(:text_ver_id AS uuid), CAST(:batch_id AS uuid), CAST(:profile_id_used AS uuid), :profile_version_used, :risk_score,
                      CAST(:extract_meta AS jsonb),
                      'normal', :fingerprint
                    )
                    RETURNING card_id
                    """
                ),
                {
                    "book_id": book_id,
                    "title": h["title"],
                    "content": json.dumps(
                        {
                            "pattern": h["pattern"],
                            "rewrite_example": h["rewrite_example"],
                            "anti_plagiarism_rules": ["禁止照抄原句", "必须替换实体名并重组语序"],
                        },
                        ensure_ascii=False,
                    ),
                    "tag": "hook",
                    "text_ver_id": text_ver_id,
                    "batch_id": batch_id,
                    "profile_id_used": profile_id_used,
                    "profile_version_used": profile_version_used,
                    "risk_score": risk_score,
                    "extract_meta": json.dumps({"run_id": run_id, "mode": mode}, ensure_ascii=False),
                    "fingerprint": _fingerprint_material(
                        "hook",
                        {
                            "pattern": h["pattern"],
                            "slots": [],
                        },
                    ),
                },
            )
            card_id = str(card_res.scalar_one())
            material_ids.append(card_id)
            await db.execute(
                text(
                    """
                    INSERT INTO asset_bundle_item(bundle_id, item_type, item_id)
                    VALUES (CAST(:bundle_id AS uuid), 'material', CAST(:item_id AS uuid))
                    """
                ),
                {"bundle_id": bundle_id, "item_id": card_id},
            )
        for b in beat_cards:
            card_res = await db.execute(
                text(
                    """
                    INSERT INTO material_card(
                      book_id, source_type, title, content, tag, importance,
                      source_text_ver_id, source_batch_id, profile_id_used, profile_version_used, risk_score, extract_meta,
                      policy, fingerprint
                    )
                    VALUES (
                      CAST(:book_id AS uuid), 'winner_extract', :title, :content, :tag, 4,
                      CAST(:text_ver_id AS uuid), CAST(:batch_id AS uuid), CAST(:profile_id_used AS uuid), :profile_version_used, :risk_score,
                      CAST(:extract_meta AS jsonb),
                      'normal', :fingerprint
                    )
                    RETURNING card_id
                    """
                ),
                {
                    "book_id": book_id,
                    "title": b["title"],
                    "content": json.dumps({"beats": b["beats"], "rewrite_hint": b["rewrite_hint"]}, ensure_ascii=False),
                    "tag": "conflict_beat",
                    "text_ver_id": text_ver_id,
                    "batch_id": batch_id,
                    "profile_id_used": profile_id_used,
                    "profile_version_used": profile_version_used,
                    "risk_score": risk_score,
                    "extract_meta": json.dumps({"run_id": run_id, "mode": mode}, ensure_ascii=False),
                    "fingerprint": _fingerprint_material(
                        "conflict_beat",
                        {"beats": b["beats"], "rewrite_hint": b["rewrite_hint"]},
                    ),
                },
            )
            card_id = str(card_res.scalar_one())
            material_ids.append(card_id)
            await db.execute(
                text(
                    """
                    INSERT INTO asset_bundle_item(bundle_id, item_type, item_id)
                    VALUES (CAST(:bundle_id AS uuid), 'material', CAST(:item_id AS uuid))
                    """
                ),
                {"bundle_id": bundle_id, "item_id": card_id},
            )
        style_res = await db.execute(
            text(
                """
                INSERT INTO material_card(
                  book_id, source_type, title, content, tag, importance,
                  source_text_ver_id, source_batch_id, profile_id_used, profile_version_used, risk_score, extract_meta,
                  policy, fingerprint
                )
                VALUES (
                  CAST(:book_id AS uuid), 'winner_extract', 'Style Micro-pattern', :content, 'style_pattern', 4,
                  CAST(:text_ver_id AS uuid), CAST(:batch_id AS uuid), CAST(:profile_id_used AS uuid), :profile_version_used, :risk_score,
                  CAST(:extract_meta AS jsonb),
                  'normal', :fingerprint
                )
                RETURNING card_id
                """
            ),
            {
                "book_id": book_id,
                "content": json.dumps(style, ensure_ascii=False),
                "text_ver_id": text_ver_id,
                "batch_id": batch_id,
                "profile_id_used": profile_id_used,
                "profile_version_used": profile_version_used,
                "risk_score": risk_score,
                "extract_meta": json.dumps({"run_id": run_id, "mode": mode}, ensure_ascii=False),
                "fingerprint": _fingerprint_material("style_pattern", style),
            },
        )
        style_card_id = str(style_res.scalar_one())
        material_ids.append(style_card_id)
        await db.execute(
            text(
                """
                INSERT INTO asset_bundle_item(bundle_id, item_type, item_id)
                VALUES (CAST(:bundle_id AS uuid), 'material', CAST(:item_id AS uuid))
                """
            ),
            {"bundle_id": bundle_id, "item_id": style_card_id},
        )
        for t in tpl_cards:
            tpl_res = await db.execute(
                text(
                    """
                    INSERT INTO prompt_template(
                      name, purpose, template, slots, tags,
                      source_text_ver_id, source_batch_id, profile_id_used, profile_version_used, risk_score, extract_meta,
                      policy, fingerprint
                    )
                    VALUES (
                      :name, :purpose, :template, CAST(:slots AS jsonb), :tags,
                      CAST(:text_ver_id AS uuid), CAST(:batch_id AS uuid), CAST(:profile_id_used AS uuid), :profile_version_used, :risk_score, CAST(:extract_meta AS jsonb),
                      'normal', :fingerprint
                    )
                    RETURNING template_id
                    """
                ),
                {
                    "name": t["name"],
                    "purpose": t["purpose"],
                    "template": t["template"],
                    "slots": json.dumps(t["slots"], ensure_ascii=False),
                    "tags": t["tags"],
                    "text_ver_id": text_ver_id,
                    "batch_id": batch_id,
                    "profile_id_used": profile_id_used,
                    "profile_version_used": profile_version_used,
                    "risk_score": risk_score,
                    "extract_meta": json.dumps({"run_id": run_id, "mode": mode}, ensure_ascii=False),
                    "fingerprint": _fingerprint_template(t["purpose"], t["template"], t["slots"]),
                },
            )
            template_id = str(tpl_res.scalar_one())
            template_ids.append(template_id)
            await db.execute(
                text(
                    """
                    INSERT INTO asset_bundle_item(bundle_id, item_type, item_id)
                    VALUES (CAST(:bundle_id AS uuid), 'template', CAST(:item_id AS uuid))
                    """
                ),
                {"bundle_id": bundle_id, "item_id": template_id},
            )

        await db.execute(
            text("UPDATE asset_bundle SET status=:status, risk_score=:risk WHERE bundle_id=CAST(:bundle_id AS uuid)"),
            {"bundle_id": bundle_id, "status": status, "risk": risk_score},
        )
        await db.execute(
            text(
                """
                UPDATE extraction_run
                SET status='done', finished_at=now(), result_summary=CAST(:summary AS jsonb)
                WHERE run_id=CAST(:run_id AS uuid)
                """
            ),
            {
                "run_id": run_id,
                "summary": json.dumps(
                    {
                        "bundle_id": bundle_id,
                        "created": {"material_card_ids": material_ids, "prompt_template_ids": template_ids},
                        "risk_score": risk_score,
                        "status": status,
                    },
                    ensure_ascii=False,
                ),
            },
        )
        if batch_id:
            await db.execute(
                text("UPDATE ab_batch_run SET winner_bundle_id=CAST(:bundle_id AS uuid) WHERE batch_id=CAST(:batch_id AS uuid)"),
                {"batch_id": batch_id, "bundle_id": bundle_id},
            )
        await db.commit()
        return {
            "run_id": run_id,
            "bundle_id": bundle_id,
            "status": status,
            "risk_score": risk_score,
            "created": {"material_card_ids": material_ids, "prompt_template_ids": template_ids},
        }
    except Exception as exc:
        await db.execute(
            text("UPDATE extraction_run SET status='failed', finished_at=now(), error=:error WHERE run_id=CAST(:run_id AS uuid)"),
            {"run_id": run_id, "error": str(exc)[:400]},
        )
        await db.execute(
            text("UPDATE asset_bundle SET status='failed', note=:note WHERE bundle_id=CAST(:bundle_id AS uuid)"),
            {"bundle_id": bundle_id, "note": str(exc)[:400]},
        )
        await db.commit()
        raise


@app.post("/v1/chapters/{chapter_id}/ab_batch/run")
async def ab_batch_run_route(
    chapter_id: UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> dict:
    row_ch = await db.execute(
        text('SELECT chapter_id, book_id, title, "order" AS chapter_no, arc_id FROM chapter WHERE chapter_id=:chapter_id'),
        {"chapter_id": str(chapter_id)},
    )
    ch = row_ch.mappings().first()
    if not ch:
        raise HTTPException(status_code=404, detail="CHAPTER_NOT_FOUND")
    book_id = str(ch["book_id"])
    chapter_no = int(ch.get("chapter_no")) if ch.get("chapter_no") is not None else None

    profiles_mode = str((body or {}).get("profiles") or "all")
    custom_ids = [str(x) for x in ((body or {}).get("profile_ids") or []) if str(x).strip()]
    do_eval = bool((body or {}).get("do_eval", True))
    do_simguard = bool((body or {}).get("do_simguard", True))
    note = str((body or {}).get("note") or "")
    purpose = str((body or {}).get("purpose") or "draft").strip().lower()
    if purpose not in {"draft", "rewrite"}:
        purpose = "draft"
    auto_confirm_intent = bool((body or {}).get("auto_confirm_intent", True))
    effective_settings = await get_effective_settings(db, str(chapter_id))
    ab_cfg = (((effective_settings or {}).get("effective") or {}).get("ab") or {})
    effective = (effective_settings or {}).get("effective") if isinstance((effective_settings or {}).get("effective"), dict) else {}
    draft_cfg = effective.get("draft") if isinstance(effective.get("draft"), dict) else {}
    enabled_tags, alias_map = await _load_tag_dictionary(db)
    penalty = float((ab_cfg.get("penalty") if isinstance(ab_cfg, dict) else None) or 0.8)
    penalty = max(0.0, min(5.0, penalty))
    include_baseline = bool((body or {}).get("include_baseline", ab_cfg.get("include_baseline", False) if isinstance(ab_cfg, dict) else False))
    baseline_profile = str((body or {}).get("baseline_profile") or "main").lower()
    baseline_profile_id = str((body or {}).get("baseline_profile_id") or "").strip()
    include_combo_baseline = bool((body or {}).get("include_combo_baseline", False))
    combo_baseline_profile = str((body or {}).get("combo_baseline_profile") or "main").lower()
    combo_baseline_profile_id = str((body or {}).get("combo_baseline_profile_id") or "").strip()
    orchestrator_cfg = effective.get("orchestrator") if isinstance(effective.get("orchestrator"), dict) else {}
    orchestrator_max_tasks = int((body or {}).get("orchestrator_max_tasks") or orchestrator_cfg.get("max_tasks") or 3)
    orchestrator_max_weight = int((body or {}).get("orchestrator_max_weight") or orchestrator_cfg.get("max_weight") or 4)
    orchestrator_enabled_default = bool((body or {}).get("orchestrator_enabled", orchestrator_cfg.get("enabled", True)))
    genre = str((body or {}).get("genre") or draft_cfg.get("genre") or "").strip().lower()
    genre = _dict_pick_tag(genre, enabled_tags, alias_map) if genre else None

    row_cnt = await db.execute(text('SELECT count(*) FROM chapter WHERE book_id=:book_id'), {"book_id": book_id})
    total_chapters = int(row_cnt.scalar() or 0)
    planned_chapters_raw = int((body or {}).get("planned_chapters") or 0)
    planned_chapters = planned_chapters_raw if planned_chapters_raw > 0 else max(1, total_chapters)
    chapter_idx = int(chapter_no) if chapter_no is not None else 1
    progress = max(0.0, min(1.0, float(chapter_idx) / float(max(1, planned_chapters))))
    structure_base = _compute_structure(progress)
    structure = dict(structure_base)
    phase = _phase_from_progress(progress)
    if chapter_no is None:
        scene_pos = None
    elif chapter_no <= 1:
        scene_pos = "scene_start"
    elif total_chapters > 0 and chapter_no >= total_chapters:
        scene_pos = "scene_end"
    else:
        scene_pos = "scene_mid"
    volume_row = await _find_volume_for_chapter(db, book_id=book_id, chapter_no=chapter_no)
    volume_id = str(volume_row.get("volume_id")) if volume_row and volume_row.get("volume_id") else None
    volume_progress = _compute_volume_progress(chapter_no, volume_row)
    volume_plan = None
    volume_plan_id = None
    volume_plan_version = None
    volume_shaping = {}
    if volume_id:
        volume_plan = await _load_active_volume_plan(db, book_id=book_id, volume_id=volume_id)
        if not volume_plan:
            try:
                created_plan = await _create_volume_plan_auto(
                    db,
                    book_id=book_id,
                    volume_row=volume_row or {},
                    note="auto_bootstrap_on_ab_batch",
                    reason="ab_batch_bootstrap",
                )
                volume_plan = created_plan.get("plan") if isinstance(created_plan.get("plan"), dict) else None
            except Exception:
                volume_plan = None
        if volume_plan:
            volume_plan_id = str(volume_plan.get("vol_plan_id") or "") or None
            volume_plan_version = int(volume_plan.get("version") or 0) or None
            structure_cfg = effective.get("structure") if isinstance(effective.get("structure"), dict) else {}
            shaping_cfg = structure_cfg.get("volume_shaping") if isinstance(structure_cfg.get("volume_shaping"), dict) else {}
            plan_assumptions = volume_plan.get("assumptions") if isinstance(volume_plan.get("assumptions"), dict) else {}
            plan_shaping_cfg = plan_assumptions.get("shaping") if isinstance(plan_assumptions.get("shaping"), dict) else {}
            if plan_shaping_cfg:
                shaping_cfg = _deep_merge_local(shaping_cfg, plan_shaping_cfg)
            shaped, shaping_trace = _apply_volume_plan_shaping(
                structure=structure,
                p_vol=volume_progress,
                plan_items=volume_plan.get("items") if isinstance(volume_plan.get("items"), list) else [],
                shaping_cfg=shaping_cfg,
            )
            structure = shaped
            volume_shaping = shaping_trace

    row_intent = await db.execute(
        text("SELECT intent, intent_status FROM chapter WHERE chapter_id=:chapter_id"),
        {"chapter_id": str(chapter_id)},
    )
    intent_row = row_intent.mappings().first() or {}
    raw_intent = body.get("intent") if isinstance(body, dict) and isinstance(body.get("intent"), dict) else intent_row.get("intent")
    intent_status = str(intent_row.get("intent_status") or "suggested")
    suggested_conf = None
    suggested_rationale: list[str] = []
    if not isinstance(raw_intent, dict) or not raw_intent:
        sug, conf, rationale = _suggest_intent_from_effective(effective, chapter_no=chapter_no)
        raw_intent = sug
        suggested_conf = conf
        suggested_rationale = rationale
        intent_status = "confirmed" if auto_confirm_intent and conf >= 0.7 else "suggested"
    intent_snapshot = _canonical_intent(raw_intent if isinstance(raw_intent, dict) else {})
    if isinstance(raw_intent, dict) and body.get("intent") is not None:
        intent_status = "confirmed" if bool((body or {}).get("intent_confirmed", True)) else "suggested"
    await db.execute(
        text(
            """
            UPDATE chapter
            SET intent=CAST(:intent AS jsonb), intent_status=:intent_status
            WHERE chapter_id=:chapter_id
            """
        ),
        {
            "chapter_id": str(chapter_id),
            "intent": json.dumps(intent_snapshot, ensure_ascii=False),
            "intent_status": intent_status,
        },
    )

    profile_ids: list[str] = []
    book_profiles = await list_book_profiles(db, book_id)
    main = (book_profiles or {}).get("main") or {}
    exps = (book_profiles or {}).get("experiments") or []
    if profiles_mode == "main_only":
        if main.get("profile_id"):
            profile_ids = [str(main["profile_id"])]
    elif profiles_mode == "custom":
        profile_ids = list(dict.fromkeys(custom_ids))
    else:
        if main.get("profile_id"):
            profile_ids.append(str(main["profile_id"]))
        for e in exps:
            pid = str(e.get("profile_id") or "")
            if pid and pid not in profile_ids:
                profile_ids.append(pid)
    if not profile_ids:
        raise HTTPException(status_code=400, detail="NO_PROFILES_FOR_BATCH")

    source_text = ""
    src_row = await db.execute(
        text(
            """
            SELECT content
            FROM chapter_text_version
            WHERE chapter_id=:chapter_id
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"chapter_id": str(chapter_id)},
    )
    src = src_row.mappings().first()
    if src:
        source_text = str(src.get("content") or "")
    if not source_text.strip():
        fallback = await db.execute(text("SELECT text FROM chapter WHERE chapter_id=:chapter_id"), {"chapter_id": str(chapter_id)})
        f = fallback.first()
        source_text = str(f[0] or "") if f else ""
    if not source_text.strip():
        source_text = "本章：剧情推进。"

    b = await db.execute(
        text(
            """
            INSERT INTO ab_batch_run(
              book_id, chapter_id, status, note, settings_snapshot, score_cfg, intent_snapshot,
              volume_id, volume_plan_id, volume_plan_version
            )
            VALUES (
              :book_id, :chapter_id, 'running', :note, CAST(:settings_snapshot AS jsonb),
              CAST(:score_cfg AS jsonb), CAST(:intent_snapshot AS jsonb),
              CAST(:volume_id AS uuid), CAST(:volume_plan_id AS uuid), :volume_plan_version
            )
            RETURNING batch_id, created_at
            """
        ),
        {
            "book_id": book_id,
            "chapter_id": str(chapter_id),
            "note": note,
            "settings_snapshot": json.dumps(((effective_settings or {}).get("effective") or {}), ensure_ascii=False),
            "score_cfg": json.dumps({"penalty": penalty}, ensure_ascii=False),
            "intent_snapshot": json.dumps(intent_snapshot, ensure_ascii=False),
            "volume_id": volume_id,
            "volume_plan_id": volume_plan_id,
            "volume_plan_version": volume_plan_version,
        },
    )
    batch = b.mappings().one()
    batch_id = str(batch["batch_id"])

    run_items: list[dict] = []
    for pid in profile_ids:
        prof = await get_profile(db, pid)
        if not prof:
            continue
        run_items.append(
            {
                "profile_id": pid,
                "profile_version": int(prof.get("active_version") or 1),
                "variant": "exp",
                "assets_injection": True,
                "combo_enabled": bool(orchestrator_enabled_default),
            }
        )
    if include_baseline:
        base_pid = baseline_profile_id if (baseline_profile == "custom" and baseline_profile_id) else str(main.get("profile_id") or "")
        if not base_pid and profile_ids:
            base_pid = profile_ids[0]
        if base_pid:
            base_prof = await get_profile(db, base_pid)
            if base_prof:
                run_items.append(
                    {
                        "profile_id": base_pid,
                        "profile_version": int(base_prof.get("active_version") or 1),
                        "variant": "baseline",
                        "assets_injection": False,
                        "combo_enabled": False,
                    }
                )

    if include_combo_baseline:
        cbase_pid = combo_baseline_profile_id if (combo_baseline_profile == "custom" and combo_baseline_profile_id) else str(main.get("profile_id") or "")
        if not cbase_pid and profile_ids:
            cbase_pid = profile_ids[0]
        if cbase_pid:
            cbase_prof = await get_profile(db, cbase_pid)
            if cbase_prof:
                run_items.append(
                    {
                        "profile_id": cbase_pid,
                        "profile_version": int(cbase_prof.get("active_version") or 1),
                        "variant": "combo_baseline",
                        "assets_injection": True,
                        "combo_enabled": False,
                    }
                )

    for it in run_items:
        await db.execute(
            text(
                """
                INSERT INTO ab_batch_item(batch_id, profile_id, variant, assets_injection, profile_version, status)
                VALUES (:batch_id, :profile_id, :variant, :assets_injection, :profile_version, 'queued')
                ON CONFLICT (batch_id, profile_id, variant) DO NOTHING
                """
            ),
            {
                "batch_id": batch_id,
                "profile_id": it["profile_id"],
                "variant": it["variant"],
                "assets_injection": bool(it["assets_injection"]),
                "profile_version": int(it["profile_version"]),
            },
        )
    await db.commit()

    row_outline = await db.execute(
        text(
            """
            SELECT content
            FROM outline
            WHERE chapter_id=:chapter_id AND scope='chapter'
            ORDER BY version DESC
            LIMIT 1
            """
        ),
        {"chapter_id": str(chapter_id)},
    )
    o = row_outline.mappings().first()
    outline_nodes = []
    if o and isinstance(o.get("content"), dict):
        outline_nodes = list((o["content"] or {}).get("nodes") or [])
    assets_cfg = effective.get("assets") if isinstance(effective.get("assets"), dict) else {}
    inject_cfg = assets_cfg.get("inject") if isinstance(assets_cfg.get("inject"), dict) else {}
    inject_hooks_n = int(inject_cfg.get("hooks_n") or 2)
    inject_beats_n = int(inject_cfg.get("beats_n") or 2)
    inject_styles_n = int(inject_cfg.get("styles_n") or 1)
    inject_templates_n = int(inject_cfg.get("templates_n") or 1)
    inject_max_chars = int(inject_cfg.get("max_chars") or 2000)
    intent_effective, curve_mod = _apply_structure_modifiers(
        intent=intent_snapshot,
        structure=structure,
        hooks_n=inject_hooks_n,
        beats_n=inject_beats_n,
        styles_n=inject_styles_n,
        templates_n=inject_templates_n,
    )
    growth_task_base = await _select_growth_task(
        db,
        book_id=book_id,
        chapter_no=chapter_no,
        volume_id=volume_id,
        structure=structure,
        p_vol=volume_progress,
        plan_items=volume_plan.get("items") if isinstance(volume_plan, dict) and isinstance(volume_plan.get("items"), list) else None,
    )
    reader_prev = await _load_latest_reader_state(db, book_id=book_id)
    reader_thr = _reader_thresholds(effective)

    for it in run_items:
        pid = str(it["profile_id"])
        variant = str(it["variant"])
        assets_injection = bool(it["assets_injection"])
        combo_enabled = bool(it.get("combo_enabled", orchestrator_enabled_default))
        ctx_tags = _build_ctx_tags_for_batch(
            intent=intent_effective,
            purpose=purpose,
            scene_pos=scene_pos,
            genre=genre,
            runtime_flags={"include_baseline": include_baseline, "variant": variant},
            structure=structure,
            phase=phase,
            enabled_tags=enabled_tags,
            alias_map=alias_map,
            do_eval=do_eval,
            do_simguard=do_simguard,
        )
        prof = await get_profile(db, pid)
        if not prof:
            await db.execute(
                text("UPDATE ab_batch_item SET status='failed', error='PROFILE_NOT_FOUND', finished_at=now() WHERE batch_id=:batch_id AND profile_id=:profile_id AND variant=:variant"),
                {"batch_id": batch_id, "profile_id": pid, "variant": variant},
            )
            await db.commit()
            continue
        pver = int(prof.get("active_version") or 1)
        await db.execute(
            text("UPDATE ab_batch_item SET status='running', started_at=now(), profile_version=:v WHERE batch_id=:batch_id AND profile_id=:profile_id AND variant=:variant"),
            {"batch_id": batch_id, "profile_id": pid, "variant": variant, "v": pver},
        )
        await db.commit()
        try:
            draft_text = _apply_profile_text_stub(source_text, prof)
            foreshadow_selection = await _select_foreshadow_tasks(
                db,
                book_id=book_id,
                chapter_no=chapter_no,
                volume_id=volume_id,
                structure=structure,
                growth_task=growth_task_base,
            )
            orchestrated = _orchestrate_chapter_tasks(
                growth_task=growth_task_base,
                foreshadow_selection=foreshadow_selection,
                plan_items=volume_plan.get("items") if isinstance(volume_plan, dict) and isinstance(volume_plan.get("items"), list) else [],
                p_vol=volume_progress,
                structure=structure,
                reader_state=reader_prev,
                enable_combo=combo_enabled and bool(orchestrator_enabled_default),
                max_tasks=orchestrator_max_tasks,
                max_weight=orchestrator_max_weight,
            )
            growth_task = orchestrated.get("growth_task") if isinstance(orchestrated.get("growth_task"), dict) else growth_task_base
            growth_block = _build_growth_task_block(growth_task)
            if growth_block:
                draft_text = growth_block + "\n\n" + draft_text
            foreshadow_selection = orchestrated.get("foreshadow_selection") if isinstance(orchestrated.get("foreshadow_selection"), dict) else foreshadow_selection
            used_foreshadow_ids = [str(x) for x in (foreshadow_selection.get("selected_ids") or []) if str(x).strip()]
            foreshadow_block = str(foreshadow_selection.get("block") or "").strip()
            if foreshadow_block:
                draft_text = foreshadow_block + "\n\n" + draft_text
            combo_block = str(orchestrated.get("combo_block") or "").strip()
            if combo_block:
                draft_text = combo_block + "\n\n" + draft_text
            selected_combo = orchestrated.get("selected_combo") if isinstance(orchestrated.get("selected_combo"), list) else []
            orchestrator_trace = orchestrated.get("trace") if isinstance(orchestrated.get("trace"), dict) else {}
            kept = orchestrator_trace.get("kept") if isinstance(orchestrator_trace.get("kept"), list) else []
            kept_types = [str((x or {}).get("task_type") or "") for x in kept if isinstance(x, dict)]
            cliff_present = "cliff" in kept_types
            reveal_ratio = _clamp01(float(structure.get("reveal") or 0.0) + (0.2 if "reveal" in kept_types else 0.0))
            payoff_intensity = 0
            for x in (foreshadow_selection.get("payoff") or []):
                if not isinstance(x, dict):
                    continue
                tpl = x.get("payoff_template") if isinstance(x.get("payoff_template"), dict) else {}
                payoff_intensity = max(
                    payoff_intensity,
                    int(tpl.get("intensity_level") or foreshadow_selection.get("payoff_intensity") or 0),
                )
            over_twist = 1.0 if (("reveal" in kept_types) and cliff_present and payoff_intensity >= 3) else 0.0
            foreshadow_audit_pre = await _foreshadow_audit_snapshot(
                db,
                book_id=book_id,
                chapter_no=chapter_no,
            )
            overdue = int(foreshadow_audit_pre.get("overdue_payoff") or 0) + int(foreshadow_audit_pre.get("dangling") or 0)
            open_count = int(foreshadow_audit_pre.get("open_count") or 0)
            unresolved_ratio = _clamp01(float(overdue) / float(max(1, open_count)))
            reader_state_next = _update_reader_state(
                prev=reader_prev,
                structure=structure,
                structure_weight=int(orchestrator_trace.get("used_weight") or 0),
                cliff_present=cliff_present,
                growth_action=str(growth_task.get("action") or ""),
                payoff_intensity=payoff_intensity,
                unresolved_foreshadow_ratio=unresolved_ratio,
                reveal_ratio=reveal_ratio,
                over_twist=over_twist,
            )
            reader_alerts = _reader_alerts(reader_state_next, reader_thr)
            injected_bundle_id = None
            injected_counts = {"hooks": 0, "beats": 0, "styles": 0, "templates": 0}
            injected_material_ids: list[str] = []
            injected_template_ids: list[str] = []
            injected_trace: dict = {}
            try:
                if assets_injection:
                    inj = await _resolve_default_assets_injection(
                        db,
                        book_id=book_id,
                        max_hooks=max(0, min(int(curve_mod.get("inject_hooks_n") or inject_hooks_n), 6)),
                        max_beats=max(0, min(int(curve_mod.get("inject_beats_n") or inject_beats_n), 8)),
                        max_styles=max(0, min(int(curve_mod.get("inject_styles_n") or inject_styles_n), 3)),
                        max_templates=max(0, min(int(curve_mod.get("inject_templates_n") or inject_templates_n), 3)),
                        max_chars=max(200, min(inject_max_chars, 5000)),
                        ctx_tags=ctx_tags,
                        settings_effective=effective,
                    )
                    injected_bundle_id = inj.get("bundle_id")
                    injected_counts = inj.get("counts") if isinstance(inj.get("counts"), dict) else injected_counts
                    injected_material_ids = [str(x) for x in (inj.get("material_ids") or []) if str(x).strip()]
                    injected_template_ids = [str(x) for x in (inj.get("template_ids") or []) if str(x).strip()]
                    injected_trace = inj.get("trace") if isinstance(inj.get("trace"), dict) else {}
                    block = str(inj.get("block") or "").strip()
                    if block:
                        draft_text = block + "\n\n" + draft_text
            except Exception:
                injected_bundle_id = None
                injected_counts = {"hooks": 0, "beats": 0, "styles": 0, "templates": 0}
                injected_trace = {}
            ins = await db.execute(
                text(
                    """
                    INSERT INTO chapter_text_version(
                      chapter_id, outline_version, profile_id_used, profile_version_used, meta, source, content, note
                    )
                    VALUES (
                      :chapter_id, 1, CAST(:profile_id AS uuid), :profile_version,
                      CAST(:meta AS jsonb),
                      'draft', :content, :note
                    )
                    RETURNING text_ver_id
                    """
                ),
                {
                    "chapter_id": str(chapter_id),
                    "profile_id": pid,
                    "profile_version": pver,
                    "meta": json.dumps(
                        {
                            "ab_batch_id": batch_id,
                            "variant": variant,
                            "assets_injection": assets_injection,
                            "combo_enabled": combo_enabled,
                            "injected_bundle_id": injected_bundle_id,
                            "injected_counts": injected_counts,
                            "intent_snapshot": intent_effective,
                            "intent_status": intent_status,
                            "ctx_tags": ctx_tags,
                            "structure": structure,
                            "structure_base": structure_base,
                            "phase": phase,
                            "curve_modifiers": curve_mod,
                            "volume_progress": volume_progress,
                            "volume_plan_id": volume_plan_id,
                            "volume_plan_version": volume_plan_version,
                            "volume_shaping": volume_shaping,
                            "growth_task": growth_task,
                            "foreshadow_selection": foreshadow_selection,
                            "used_foreshadow_ids": used_foreshadow_ids,
                            "orchestrator": orchestrator_trace,
                            "selected_combo": selected_combo,
                            "volume_id": volume_id,
                            "reader_state_prev": reader_prev,
                            "reader_state": reader_state_next,
                            "reader_alerts": reader_alerts,
                        },
                        ensure_ascii=False,
                    ),
                    "content": draft_text,
                    "note": f"ab_batch:{batch_id}",
                },
            )
            text_ver_id = str(ins.scalar_one())
            await db.execute(
                text(
                    """
                    INSERT INTO asset_usage_log(
                      book_id, chapter_id, text_ver_id, batch_id,
                      profile_id_used, profile_version_used, assets_injection, injected_bundle_id,
                      injected_material_ids, injected_template_ids, used_structure_template_ids, used_payoff_template_ids,
                      used_combo_ids, used_combo_fingerprints,
                      used_foreshadow_ids, ctx_tags, purpose,
                      growth_milestone_id, growth_action
                    )
                    VALUES (
                      CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), CAST(:text_ver_id AS uuid), CAST(:batch_id AS uuid),
                      CAST(:profile_id_used AS uuid), :profile_version_used, :assets_injection, CAST(:injected_bundle_id AS uuid),
                      CAST(:injected_material_ids AS uuid[]), CAST(:injected_template_ids AS uuid[]), CAST(:used_structure_template_ids AS uuid[]), CAST(:used_payoff_template_ids AS uuid[]),
                      CAST(:used_combo_ids AS uuid[]), CAST(:used_combo_fingerprints AS text[]),
                      CAST(:used_foreshadow_ids AS uuid[]), CAST(:ctx_tags AS text[]), :purpose,
                      CAST(:growth_milestone_id AS uuid), :growth_action
                    )
                    """
                ),
                {
                    "book_id": book_id,
                    "chapter_id": str(chapter_id),
                    "text_ver_id": text_ver_id,
                    "batch_id": batch_id,
                    "profile_id_used": pid,
                    "profile_version_used": pver,
                    "assets_injection": assets_injection,
                    "injected_bundle_id": injected_bundle_id,
                    "injected_material_ids": injected_material_ids,
                    "injected_template_ids": injected_template_ids,
                    "used_structure_template_ids": [
                        str(x.get("template_id") or "")
                        for x in (
                            (
                                (volume_plan.get("assumptions") or {}).get("selected_structure_templates", {})
                                if isinstance(volume_plan, dict) and isinstance(volume_plan.get("assumptions"), dict)
                                else {}
                            ).values()
                        )
                        if isinstance(x, dict) and str(x.get("template_id") or "").strip()
                    ],
                    "used_payoff_template_ids": [
                        str((x.get("meta") or {}).get("structure_template_id") or "")
                        for x in (volume_plan.get("items") if isinstance(volume_plan, dict) and isinstance(volume_plan.get("items"), list) else [])
                        if isinstance(x, dict)
                        and str(x.get("kind") or "") == "foreshadow_payoff"
                        and isinstance(x.get("meta"), dict)
                        and str((x.get("meta") or {}).get("structure_template_id") or "")
                    ],
                    "used_combo_ids": [
                        str((x or {}).get("combo_id") or "")
                        for x in selected_combo
                        if isinstance(x, dict) and str((x or {}).get("combo_id") or "")
                    ],
                    "used_combo_fingerprints": [
                        str((x or {}).get("combo_fingerprint") or "")
                        for x in selected_combo
                        if isinstance(x, dict) and str((x or {}).get("combo_fingerprint") or "")
                    ],
                    "used_foreshadow_ids": used_foreshadow_ids,
                    "ctx_tags": ctx_tags,
                    "purpose": purpose,
                    "growth_milestone_id": (growth_task.get("milestone") or {}).get("milestone_id") if isinstance(growth_task.get("milestone"), dict) else None,
                    "growth_action": str(growth_task.get("action") or ""),
                },
            )
            if assets_injection:
                await db.execute(
                    text(
                        """
                        INSERT INTO asset_selection_trace(
                          book_id, chapter_id, text_ver_id, batch_id,
                          injected_bundle_id, assets_injection, ctx_tags,
                          selected_material_ids, selected_template_ids, trace
                        )
                        VALUES (
                          CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), CAST(:text_ver_id AS uuid), CAST(:batch_id AS uuid),
                          CAST(:injected_bundle_id AS uuid), :assets_injection, CAST(:ctx_tags AS text[]),
                          CAST(:selected_material_ids AS uuid[]), CAST(:selected_template_ids AS uuid[]), CAST(:trace AS jsonb)
                        )
                        """
                    ),
                    {
                        "book_id": book_id,
                        "chapter_id": str(chapter_id),
                        "text_ver_id": text_ver_id,
                        "batch_id": batch_id,
                        "injected_bundle_id": injected_bundle_id,
                        "assets_injection": True,
                        "ctx_tags": ctx_tags,
                        "selected_material_ids": injected_material_ids,
                        "selected_template_ids": injected_template_ids,
                        "trace": json.dumps(
                            {
                                **(injected_trace or {}),
                                "structure": structure,
                                "structure_base": structure_base,
                                "phase": phase,
                                "curve_modifiers": curve_mod,
                                "volume_progress": volume_progress,
                                "volume_plan_id": volume_plan_id,
                                "volume_plan_version": volume_plan_version,
                                "volume_shaping": volume_shaping,
                                "combo": {
                                    "picked": selected_combo
                                },
                                "growth_task": growth_task,
                                "foreshadow": foreshadow_selection,
                                "orchestrator": orchestrator_trace,
                                "reader_state_prev": reader_prev,
                                "reader_state": reader_state_next,
                                "reader_alerts": reader_alerts,
                            },
                            ensure_ascii=False,
                        ),
                    },
                )
            if used_foreshadow_ids:
                for f in (foreshadow_selection.get("seed") or []):
                    fid = str((f or {}).get("foreshadow_id") or "")
                    if not fid:
                        continue
                    await db.execute(
                        text(
                            """
                            INSERT INTO foreshadow_event(foreshadow_id, chapter_id, event_type, intensity, note)
                            VALUES (CAST(:foreshadow_id AS uuid), CAST(:chapter_id AS uuid), 'seed', 1, 'auto from draft inject')
                            """
                        ),
                        {"foreshadow_id": fid, "chapter_id": str(chapter_id)},
                    )
                    await db.execute(
                        text("UPDATE foreshadow SET status='seeded', updated_at=now() WHERE foreshadow_id=CAST(:foreshadow_id AS uuid)"),
                        {"foreshadow_id": fid},
                    )
                for f in (foreshadow_selection.get("reinforce") or []):
                    fid = str((f or {}).get("foreshadow_id") or "")
                    if not fid:
                        continue
                    await db.execute(
                        text(
                            """
                            INSERT INTO foreshadow_event(foreshadow_id, chapter_id, event_type, intensity, note)
                            VALUES (CAST(:foreshadow_id AS uuid), CAST(:chapter_id AS uuid), 'reinforce', 1, 'auto from draft inject')
                            """
                        ),
                        {"foreshadow_id": fid, "chapter_id": str(chapter_id)},
                    )
                    await db.execute(
                        text("UPDATE foreshadow SET status='reinforced', updated_at=now() WHERE foreshadow_id=CAST(:foreshadow_id AS uuid)"),
                        {"foreshadow_id": fid},
                    )
                for f in (foreshadow_selection.get("payoff") or []):
                    fid = str((f or {}).get("foreshadow_id") or "")
                    if not fid:
                        continue
                    await db.execute(
                        text(
                            """
                            INSERT INTO foreshadow_event(foreshadow_id, chapter_id, event_type, intensity, note)
                            VALUES (CAST(:foreshadow_id AS uuid), CAST(:chapter_id AS uuid), 'payoff', 2, 'auto from draft inject')
                            """
                        ),
                        {"foreshadow_id": fid, "chapter_id": str(chapter_id)},
                    )
                    await db.execute(
                        text("UPDATE foreshadow SET status='paid_off', updated_at=now() WHERE foreshadow_id=CAST(:foreshadow_id AS uuid)"),
                        {"foreshadow_id": fid},
                    )
            gm = growth_task.get("milestone") if isinstance(growth_task.get("milestone"), dict) else {}
            gm_id = str(gm.get("milestone_id") or "").strip()
            g_action = str(growth_task.get("action") or "").strip().lower()
            if gm_id and g_action in {"seed", "advance", "achieve", "reflect"}:
                g_status = {
                    "seed": "seeded",
                    "advance": "in_progress",
                    "achieve": "achieved",
                    "reflect": "reflected",
                }.get(g_action, "in_progress")
                await db.execute(
                    text(
                        """
                        UPDATE growth_milestone
                        SET status=:status,
                            meta = COALESCE(meta, '{}'::jsonb) || jsonb_build_object(
                              'last_auto_action', CAST(:action AS text),
                              'last_auto_chapter_id', CAST(:chapter_id AS text),
                              'last_auto_text_ver_id', CAST(:text_ver_id AS text),
                              'last_auto_at', now()
                            ),
                            updated_at=now()
                        WHERE milestone_id=CAST(:milestone_id AS uuid)
                        """
                    ),
                    {
                        "milestone_id": gm_id,
                        "status": g_status,
                        "action": g_action,
                        "chapter_id": str(chapter_id),
                        "text_ver_id": text_ver_id,
                    },
                )
            foreshadow_audit = await _foreshadow_audit_snapshot(
                db,
                book_id=book_id,
                chapter_no=chapter_no,
            )
            growth_requirements = growth_task.get("requirements") if isinstance(growth_task.get("requirements"), dict) else {}
            growth_cost_check = "pass"
            growth_choice_check = "pass"
            if g_action in {"achieve", "advance"}:
                cost_text = str(gm.get("cost") or "").strip()
                choice_text = str(gm.get("choice_text") or "").strip()
                if bool(growth_requirements.get("cost_must_show")) and cost_text and cost_text[:8] not in draft_text:
                    growth_cost_check = "warn"
                if bool(growth_requirements.get("choice_must_be_explicit")) and choice_text and choice_text[:8] not in draft_text:
                    growth_choice_check = "warn"

            eval_overall = None
            eval_obj = None
            if do_eval:
                eval_obj = evaluate_tension_score_v1(draft_text, outline_nodes)
                eval_overall = float((((eval_obj or {}).get("result") or {}).get("scores") or {}).get("overall") or 0.0)

            simguard_max = None
            sim_report = None
            if do_simguard:
                async def _nop_progress(_pct: int, _phase: str, _message: str) -> None:
                    return None
                async def _nop_log(_level: str, _phase: str, _message: str) -> None:
                    return None
                try:
                    sim_out = await run_similarity_guard_text_job(
                        db,
                        {
                            "chapter_id": str(chapter_id),
                            "text_ver_id": text_ver_id,
                            "scope": ["material_card"],
                            "sim_threshold": 0.86,
                            "top_k": 3,
                        },
                        on_progress=_nop_progress,
                        on_log=_nop_log,
                    )
                    sim_report = sim_out.get("report")
                    simguard_max = float((((sim_report or {}).get("result") or {}).get("summary") or {}).get("max_score") or 0.0)
                except Exception:
                    simguard_max = None

            report_payload = {
                "batch_id": batch_id,
                "chapter_id": str(chapter_id),
                "text_ver_id": text_ver_id,
                "profile_id_used": pid,
                "profile_version_used": pver,
                "variant": variant,
                "assets_injection": assets_injection,
                "injected_bundle_id": injected_bundle_id,
                "injected_counts": injected_counts,
                "intent_snapshot": intent_effective,
                "intent_status": intent_status,
                "intent_suggested_confidence": suggested_conf,
                "intent_suggested_rationale": suggested_rationale,
                "ctx_tags": ctx_tags,
                "structure": structure,
                "structure_base": structure_base,
                "phase": phase,
                "curve_modifiers": curve_mod,
                "volume_progress": volume_progress,
                "volume_plan_id": volume_plan_id,
                "volume_plan_version": volume_plan_version,
                "volume_shaping": volume_shaping,
                "growth_task": growth_task,
                "growth_check": {
                    "cost_check": growth_cost_check,
                    "choice_explicit": growth_choice_check,
                },
                "foreshadow_selection": foreshadow_selection,
                "foreshadow_audit": foreshadow_audit,
                "used_foreshadow_ids": used_foreshadow_ids,
                "volume_id": volume_id,
                "reader_state_prev": reader_prev,
                "reader_state": reader_state_next,
                "reader_alerts": reader_alerts,
                "score_cfg": {"penalty": penalty},
                "eval_summary": {"overall": eval_overall} if eval_overall is not None else {},
                "simguard_summary": {"max_score": simguard_max} if simguard_max is not None else {},
                "eval": eval_obj,
                "simguard": sim_report,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            score = round((float(eval_overall or 0.0) - float(simguard_max or 0.0) * penalty), 4)
            report_payload["score"] = score
            rep = await db.execute(
                text(
                    """
                    INSERT INTO report(
                      book_id, chapter_id, profile_id_used, profile_version_used, report_type, payload, html
                    )
                    VALUES (
                      :book_id, :chapter_id, CAST(:profile_id AS uuid), :profile_version, 'ab_batch_item', CAST(:payload AS jsonb), ''
                    )
                    RETURNING report_id
                    """
                ),
                {
                    "book_id": book_id,
                    "chapter_id": str(chapter_id),
                    "profile_id": pid,
                    "profile_version": pver,
                    "payload": json.dumps(report_payload, ensure_ascii=False),
                },
            )
            report_id = str(rep.scalar_one())
            await db.execute(
                text(
                    """
                    UPDATE ab_batch_item
                    SET status='done',
                        text_ver_id=CAST(:text_ver_id AS uuid),
                        report_id=CAST(:report_id AS uuid),
                        eval_overall=:eval_overall,
                        simguard_max=:simguard_max,
                        score=:score,
                        error='',
                        finished_at=now()
                    WHERE batch_id=:batch_id AND profile_id=CAST(:profile_id AS uuid) AND variant=:variant
                    """
                ),
                {
                    "batch_id": batch_id,
                    "profile_id": pid,
                    "variant": variant,
                    "text_ver_id": text_ver_id,
                    "report_id": report_id,
                    "eval_overall": eval_overall,
                    "simguard_max": simguard_max,
                    "score": score,
                },
            )
            await db.commit()
            if variant == "exp":
                reader_prev = _normalize_reader_state(reader_state_next)
        except Exception as exc:
            await db.execute(
                text(
                    """
                    UPDATE ab_batch_item
                    SET status='failed', error=:error, finished_at=now()
                    WHERE batch_id=:batch_id AND profile_id=CAST(:profile_id AS uuid) AND variant=:variant
                    """
                ),
                {"batch_id": batch_id, "profile_id": pid, "variant": variant, "error": str(exc)[:400]},
            )
            await db.commit()

    failed_count_res = await db.execute(
        text("SELECT COUNT(*) FROM ab_batch_item WHERE batch_id=:batch_id AND status='failed'"),
        {"batch_id": batch_id},
    )
    failed_count = int(failed_count_res.scalar() or 0)
    await db.execute(
        text(
            """
            UPDATE ab_batch_run
            SET status=:status, finished_at=now()
            WHERE batch_id=:batch_id
            """
        ),
        {"batch_id": batch_id, "status": "failed" if failed_count > 0 else "done"},
    )
    await db.commit()

    if failed_count == 0:
        top_res = await db.execute(
            text(
                """
                SELECT text_ver_id::text AS text_ver_id
                FROM ab_batch_item
                WHERE batch_id=:batch_id AND status='done' AND score IS NOT NULL AND variant='exp'
                ORDER BY score DESC, profile_id
                LIMIT 1
                """
            ),
            {"batch_id": batch_id},
        )
        top = top_res.mappings().first()
        if top and top.get("text_ver_id"):
            try:
                await _extract_assets_internal(
                    db,
                    text_ver_id=str(top["text_ver_id"]),
                    batch_id=batch_id,
                    mode="safe",
                    max_cards=12,
                    max_templates=6,
                )
            except Exception:
                # Asset extraction failure should not fail the completed batch.
                pass

        # learn delta from exp vs baseline
        items_done_res = await db.execute(
            text(
                """
                SELECT profile_id::text AS profile_id, variant, score, text_ver_id::text AS text_ver_id
                FROM ab_batch_item
                WHERE batch_id=:batch_id AND status='done' AND score IS NOT NULL
                """
            ),
            {"batch_id": batch_id},
        )
        done_rows = [dict(r) for r in items_done_res.mappings().all()]
        by_pid: dict[str, dict[str, dict]] = {}
        for r in done_rows:
            pid = str(r.get("profile_id") or "")
            if not pid:
                continue
            by_pid.setdefault(pid, {})[str(r.get("variant") or "exp")] = r
        for pid, pair in by_pid.items():
            exp = pair.get("exp")
            base = pair.get("baseline")
            if not exp or not base:
                continue
            delta = float(exp.get("score") or 0.0) - float(base.get("score") or 0.0)
            use_res = await db.execute(
                text(
                    """
                    SELECT injected_material_ids, injected_template_ids, used_combo_ids
                    FROM asset_usage_log
                    WHERE text_ver_id=CAST(:text_ver_id AS uuid)
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"text_ver_id": str(exp.get("text_ver_id"))},
            )
            usage = use_res.mappings().first() or {}
            m_ids = usage.get("injected_material_ids") if isinstance(usage.get("injected_material_ids"), list) else []
            t_ids = usage.get("injected_template_ids") if isinstance(usage.get("injected_template_ids"), list) else []
            c_ids = usage.get("used_combo_ids") if isinstance(usage.get("used_combo_ids"), list) else []
            all_ids = (
                [("material", str(x)) for x in m_ids if str(x).strip()]
                + [("template", str(x)) for x in t_ids if str(x).strip()]
                + [("structure_combo", str(x)) for x in c_ids if str(x).strip()]
            )
            if not all_ids:
                continue
            delta_each = float(delta) / float(len(all_ids))
            alpha = 0.2
            for item_type, iid in all_ids:
                stat_res = await db.execute(
                    text(
                        """
                        SELECT uses, wins, losses, avg_delta
                        FROM asset_score_stat
                        WHERE item_type=:item_type AND item_id=CAST(:item_id AS uuid) AND book_id=CAST(:book_id AS uuid)
                        """
                    ),
                    {"item_type": item_type, "item_id": iid, "book_id": book_id},
                )
                sr = stat_res.mappings().first() or {}
                old_uses = int(sr.get("uses") or 0)
                old_avg = float(sr.get("avg_delta") or 0.0)
                new_avg = old_avg * (1.0 - alpha) + delta_each * alpha
                new_uses = old_uses + 1
                wins = int(sr.get("wins") or 0) + (1 if delta_each > 0 else 0)
                losses = int(sr.get("losses") or 0) + (1 if delta_each < 0 else 0)
                overuse_penalty = 0.01 * (0 if new_uses <= 1 else __import__("math").log(1 + new_uses))
                weight = float(new_avg - overuse_penalty)
                await db.execute(
                    text(
                        """
                        INSERT INTO asset_score_stat(
                          item_type, item_id, book_id, uses, wins, losses, avg_delta, last_delta, weight, updated_at
                        )
                        VALUES (
                          :item_type, CAST(:item_id AS uuid), CAST(:book_id AS uuid), :uses, :wins, :losses, :avg_delta, :last_delta, :weight, now()
                        )
                        ON CONFLICT (item_type, item_id, book_id)
                        DO UPDATE SET
                          uses=EXCLUDED.uses,
                          wins=EXCLUDED.wins,
                          losses=EXCLUDED.losses,
                          avg_delta=EXCLUDED.avg_delta,
                          last_delta=EXCLUDED.last_delta,
                          weight=EXCLUDED.weight,
                          updated_at=now()
                        """
                    ),
                    {
                        "item_type": item_type,
                        "item_id": iid,
                        "book_id": book_id,
                        "uses": new_uses,
                        "wins": wins,
                        "losses": losses,
                        "avg_delta": new_avg,
                        "last_delta": delta_each,
                        "weight": weight,
                    },
                )
        await db.commit()
        try:
            await _generate_asset_policy_proposals(db, book_id=book_id)
        except Exception:
            await db.rollback()
    return {"batch_id": batch_id}


@app.get("/v1/agent/diagnose")
async def agent_diagnose_route(
    book_id: UUID = Query(...),
    chapter_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    bid = str(book_id)
    cid = str(chapter_id) if chapter_id else None
    reader_state = await _load_latest_reader_state(db, book_id=bid)
    replay_thresholds = _replay_tuning_thresholds({})
    thresholds = _reader_thresholds({})
    if cid:
        try:
            effective = await get_effective_settings(db, cid)
            thresholds = _reader_thresholds(effective if isinstance(effective, dict) else {})
            replay_thresholds = _replay_tuning_thresholds(effective if isinstance(effective, dict) else {})
        except Exception:
            thresholds = _reader_thresholds({})
            replay_thresholds = _replay_tuning_thresholds({})
    else:
        try:
            global_cfg = await get_global_settings_scoped(db)
            book_cfg = await get_book_settings(db, bid) or {}
            effective = _merge_dict(global_cfg if isinstance(global_cfg, dict) else {}, book_cfg if isinstance(book_cfg, dict) else {})
            replay_thresholds = _replay_tuning_thresholds(effective)
        except Exception:
            replay_thresholds = _replay_tuning_thresholds({})
    if cid:
        row = await db.execute(
            text(
                """
                SELECT payload
                FROM report
                WHERE book_id=CAST(:book_id AS uuid)
                  AND report_type='ab_batch_item'
                  AND chapter_id=CAST(:chapter_id AS uuid)
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"book_id": bid, "chapter_id": cid},
        )
    else:
        row = await db.execute(
            text(
                """
                SELECT payload
                FROM report
                WHERE book_id=CAST(:book_id AS uuid)
                  AND report_type='ab_batch_item'
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"book_id": bid},
        )
    r = row.mappings().first()
    payload = r.get("payload") if r and isinstance(r.get("payload"), dict) else {}
    structure = payload.get("structure") if isinstance(payload.get("structure"), dict) else {}
    phase = str(payload.get("phase") or "phase_unknown")
    volume_progress = _clamp01(float(payload.get("volume_progress") or 0.0))
    alerts = _reader_alerts(reader_state, thresholds)
    return {
        "mode": "observe",
        "diagnosis": {
            "phase": phase,
            "volume_progress": round(volume_progress, 6),
            "reader": reader_state,
            "structure": structure,
            "alerts": alerts,
            "replay_thresholds": replay_thresholds,
        },
    }


def _agent_orchestrate_parse_uuid(raw_value: object, field_name: str, *, required: bool = False) -> str | None:
    value = str(raw_value or "").strip()
    if not value:
        if required:
            raise HTTPException(status_code=400, detail=f"{field_name} required")
        return None
    try:
        return str(UUID(value))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"{field_name} invalid uuid") from exc


def _agent_orchestrate_extract_code(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        return str(exc.detail or "AGENT_ORCHESTRATE_FAILED")
    return str(exc or "AGENT_ORCHESTRATE_FAILED")


async def _agent_orchestrate_build_plan(
    db: AsyncSession,
    *,
    book_id: str,
    chapter_id: str | None,
    include_snapshot: bool = True,
    include_style: bool = True,
) -> dict:
    diag = await agent_diagnose_route(
        book_id=UUID(book_id),
        chapter_id=UUID(chapter_id) if chapter_id else None,
        db=db,
    )
    proposal = await agent_propose_route(
        {
            "book_id": book_id,
            "chapter_id": chapter_id,
        },
        db=db,
    )
    actions = proposal.get("actions") if isinstance(proposal.get("actions"), list) else []
    requires_confirmation = bool(proposal.get("requires_confirmation")) and len(actions) > 0
    latest_snapshot = None
    if include_snapshot:
        await _ensure_asset_snapshot_tables(db)
        snap_row = await db.execute(
            text(
                """
                SELECT snapshot_id::text AS snapshot_id, snapshot_name, reason, tag, created_at
                FROM asset_snapshot
                WHERE book_id=CAST(:book_id AS uuid)
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"book_id": book_id},
        )
        latest_snapshot = dict(snap_row.mappings().first() or {}) or None
    latest_style = None
    if include_style:
        latest_style = await get_latest_style_evolution(db, book_id=book_id)
    diagnosis = diag.get("diagnosis") if isinstance(diag.get("diagnosis"), dict) else {}
    alerts = diagnosis.get("alerts") if isinstance(diagnosis.get("alerts"), list) else []
    warn_count = len([x for x in alerts if str((x or {}).get("severity") or "").lower() == "warn"])
    return {
        "plan_id": str(uuid4()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "book_id": book_id,
        "chapter_id": chapter_id,
        "requires_confirmation": requires_confirmation,
        "actions_count": len(actions),
        "warn_count": warn_count,
        "diagnosis": diagnosis,
        "proposal": proposal,
        "latest_snapshot": latest_snapshot,
        "latest_style_evolution": latest_style,
        "next_recommended_phase": "EXECUTE" if len(actions) > 0 else "VERIFY",
    }


@app.post("/v1/agent/orchestrate/plan")
async def agent_orchestrate_plan_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    bid = _agent_orchestrate_parse_uuid((body or {}).get("book_id"), "book_id", required=True)
    cid = _agent_orchestrate_parse_uuid((body or {}).get("chapter_id"), "chapter_id", required=False)
    include_snapshot = bool((body or {}).get("include_snapshot", True))
    include_style = bool((body or {}).get("include_style", True))
    plan = await _agent_orchestrate_build_plan(
        db,
        book_id=str(bid),
        chapter_id=str(cid) if cid else None,
        include_snapshot=include_snapshot,
        include_style=include_style,
    )
    return {"ok": True, "phase": "PLAN", "plan": plan}


@app.post("/v1/agent/orchestrate/step")
async def agent_orchestrate_step_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    data = body if isinstance(body, dict) else {}
    bid = _agent_orchestrate_parse_uuid(data.get("book_id"), "book_id", required=True)
    cid = _agent_orchestrate_parse_uuid(data.get("chapter_id"), "chapter_id", required=False)
    phase = str(data.get("phase") or "").strip().upper()
    if phase not in {"PLAN", "EXECUTE", "VERIFY", "COMMIT", "LEARN"}:
        raise HTTPException(status_code=400, detail="AGENT_ORCHESTRATE_PHASE_INVALID")
    dry_run = bool(data.get("dry_run", False))
    trace_id = str(data.get("trace_id") or str(uuid4()))
    book_id = str(bid)
    chapter_id = str(cid) if cid else None

    if phase == "PLAN":
        out = await _agent_orchestrate_build_plan(
            db,
            book_id=book_id,
            chapter_id=chapter_id,
            include_snapshot=bool(data.get("include_snapshot", True)),
            include_style=bool(data.get("include_style", True)),
        )
        return {"ok": True, "phase": phase, "trace_id": trace_id, "result": out}

    if phase == "EXECUTE":
        proposal = data.get("proposal") if isinstance(data.get("proposal"), dict) else {}
        actions = proposal.get("actions") if isinstance(proposal.get("actions"), list) else []
        if not actions:
            fallback = await agent_propose_route({"book_id": book_id, "chapter_id": chapter_id}, db=db)
            actions = fallback.get("actions") if isinstance(fallback.get("actions"), list) else []
        if not actions:
            return {
                "ok": True,
                "phase": phase,
                "trace_id": trace_id,
                "result": {"status": "skipped", "reason": "NO_ACTIONS"},
            }
        apply_result = await agent_apply_route(
            {
                "book_id": book_id,
                "chapter_id": chapter_id,
                "actions": actions,
                "dry_run": dry_run,
                "operator_note": str(data.get("operator_note") or f"agent_orchestrate:{trace_id}"),
            },
            db=db,
        )
        return {
            "ok": True,
            "phase": phase,
            "trace_id": trace_id,
            "result": {"status": "done", "actions_count": len(actions), "apply_result": apply_result},
        }

    if phase == "VERIFY":
        diag = await agent_diagnose_route(
            book_id=UUID(book_id),
            chapter_id=UUID(chapter_id) if chapter_id else None,
            db=db,
        )
        diagnosis = diag.get("diagnosis") if isinstance(diag.get("diagnosis"), dict) else {}
        alerts = diagnosis.get("alerts") if isinstance(diagnosis.get("alerts"), list) else []
        warn_count = len([x for x in alerts if str((x or {}).get("severity") or "").lower() == "warn"])
        result = {
            "status": "done",
            "warn_count": warn_count,
            "alerts_count": len(alerts),
            "has_blocking_alert": warn_count > 0,
            "diagnosis": diagnosis,
        }
        return {"ok": True, "phase": phase, "trace_id": trace_id, "result": result}

    if phase == "COMMIT":
        if dry_run:
            return {
                "ok": True,
                "phase": phase,
                "trace_id": trace_id,
                "result": {"status": "skipped", "reason": "DRY_RUN"},
            }
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        snapshot_name = str(data.get("snapshot_name") or "").strip() or f"总控提交快照 {now_str}"
        reason = str(data.get("snapshot_reason") or "").strip() or "agent orchestrate commit"
        tag = str(data.get("snapshot_tag") or "agent_orchestrate").strip() or "agent_orchestrate"
        capture_result = await _capture_asset_snapshot(
            db,
            book_id=book_id,
            snapshot_name=snapshot_name,
            reason=reason,
            tag=tag,
        )
        return {
            "ok": True,
            "phase": phase,
            "trace_id": trace_id,
            "result": {"status": "done", **capture_result},
        }

    if dry_run:
        return {
            "ok": True,
            "phase": phase,
            "trace_id": trace_id,
            "result": {"status": "skipped", "reason": "DRY_RUN"},
        }
    style_cfg = data.get("style_evolution") if isinstance(data.get("style_evolution"), dict) else {}
    learn_result = await evolve_book_style(
        db,
        book_id=book_id,
        profile_id=(str(style_cfg.get("profile_id") or "").strip() or None),
        sample_limit=int(style_cfg.get("sample_limit") or 24),
        min_sample_count=int(style_cfg.get("min_sample_count") or 6),
        alpha=float(style_cfg.get("alpha") or 0.58),
        force=bool(style_cfg.get("force", False)),
        sync_book_settings=bool(style_cfg.get("sync_book_settings", True)),
        note=str(style_cfg.get("note") or "").strip() or f"agent orchestrate learn:{trace_id}",
    )
    return {"ok": True, "phase": phase, "trace_id": trace_id, "result": {"status": "done", "learn": learn_result}}


@app.post("/v1/agent/orchestrate/run")
async def agent_orchestrate_run_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    data = body if isinstance(body, dict) else {}
    bid = _agent_orchestrate_parse_uuid(data.get("book_id"), "book_id", required=True)
    cid = _agent_orchestrate_parse_uuid(data.get("chapter_id"), "chapter_id", required=False)
    book_id = str(bid)
    chapter_id = str(cid) if cid else None
    trace_id = str(uuid4())
    dry_run = bool(data.get("dry_run", False))
    do_execute = bool(data.get("do_execute", True))
    do_verify = bool(data.get("do_verify", True))
    do_commit = bool(data.get("do_commit", True))
    do_learn = bool(data.get("do_learn", True))
    confirm_execute = bool(data.get("confirm_execute", False))

    phases: dict[str, dict] = {}
    halted = False
    ok = True

    try:
        plan = await _agent_orchestrate_build_plan(
            db,
            book_id=book_id,
            chapter_id=chapter_id,
            include_snapshot=bool(data.get("include_snapshot", True)),
            include_style=bool(data.get("include_style", True)),
        )
        phases["PLAN"] = {"status": "done", "output": plan}
    except Exception as exc:
        code = _agent_orchestrate_extract_code(exc)
        phases["PLAN"] = {"status": "failed", "reason": code}
        return {"ok": False, "state": "failed", "trace_id": trace_id, "book_id": book_id, "chapter_id": chapter_id, "phases": phases}

    if plan.get("requires_confirmation") and do_execute and not confirm_execute:
        halted = True
        ok = False
        phases["EXECUTE"] = {"status": "halted", "reason": "AGENT_ORCHESTRATE_CONFIRM_REQUIRED"}
    elif do_execute:
        try:
            execute_out = await agent_orchestrate_step_route(
                {
                    "book_id": book_id,
                    "chapter_id": chapter_id,
                    "phase": "EXECUTE",
                    "dry_run": dry_run,
                    "trace_id": trace_id,
                    "proposal": plan.get("proposal"),
                    "operator_note": str(data.get("operator_note") or f"agent_orchestrate:{trace_id}"),
                },
                db=db,
            )
            phases["EXECUTE"] = {"status": "done", "output": execute_out.get("result")}
        except Exception as exc:
            ok = False
            phases["EXECUTE"] = {"status": "failed", "reason": _agent_orchestrate_extract_code(exc)}
    else:
        phases["EXECUTE"] = {"status": "skipped", "reason": "DISABLED"}

    if do_verify and ok and not halted:
        try:
            verify_out = await agent_orchestrate_step_route(
                {
                    "book_id": book_id,
                    "chapter_id": chapter_id,
                    "phase": "VERIFY",
                    "trace_id": trace_id,
                },
                db=db,
            )
            phases["VERIFY"] = {"status": "done", "output": verify_out.get("result")}
        except Exception as exc:
            ok = False
            phases["VERIFY"] = {"status": "failed", "reason": _agent_orchestrate_extract_code(exc)}
    else:
        phases["VERIFY"] = {"status": "skipped", "reason": "DISABLED_OR_BLOCKED"}

    if do_commit and ok and not halted:
        try:
            commit_out = await agent_orchestrate_step_route(
                {
                    "book_id": book_id,
                    "phase": "COMMIT",
                    "dry_run": dry_run,
                    "trace_id": trace_id,
                    "snapshot_name": data.get("snapshot_name"),
                    "snapshot_reason": data.get("snapshot_reason"),
                    "snapshot_tag": data.get("snapshot_tag"),
                },
                db=db,
            )
            phases["COMMIT"] = {"status": "done", "output": commit_out.get("result")}
        except Exception as exc:
            ok = False
            phases["COMMIT"] = {"status": "failed", "reason": _agent_orchestrate_extract_code(exc)}
    else:
        phases["COMMIT"] = {"status": "skipped", "reason": "DISABLED_OR_BLOCKED"}

    if do_learn and ok and not halted:
        try:
            learn_out = await agent_orchestrate_step_route(
                {
                    "book_id": book_id,
                    "phase": "LEARN",
                    "dry_run": dry_run,
                    "trace_id": trace_id,
                    "style_evolution": data.get("style_evolution"),
                },
                db=db,
            )
            phases["LEARN"] = {"status": "done", "output": learn_out.get("result")}
        except Exception as exc:
            ok = False
            phases["LEARN"] = {"status": "failed", "reason": _agent_orchestrate_extract_code(exc)}
    else:
        phases["LEARN"] = {"status": "skipped", "reason": "DISABLED_OR_BLOCKED"}

    final_state = "halted" if halted else ("completed" if ok else "failed")
    return {
        "ok": ok,
        "state": final_state,
        "trace_id": trace_id,
        "book_id": book_id,
        "chapter_id": chapter_id,
        "dry_run": dry_run,
        "phases": phases,
    }


@app.post("/v1/agent/propose")
async def agent_propose_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    bid = str(body.get("book_id") or "").strip()
    if not bid:
        raise HTTPException(status_code=400, detail="book_id required")
    cid_raw = str(body.get("chapter_id") or "").strip()
    diag = await agent_diagnose_route(
        book_id=UUID(bid),
        chapter_id=UUID(cid_raw) if cid_raw else None,
        db=db,
    )
    diagnosis = diag.get("diagnosis") if isinstance(diag.get("diagnosis"), dict) else {}
    reader = diagnosis.get("reader") if isinstance(diagnosis.get("reader"), dict) else {}
    alerts = diagnosis.get("alerts") if isinstance(diagnosis.get("alerts"), list) else []
    replay_thr = diagnosis.get("replay_thresholds") if isinstance(diagnosis.get("replay_thresholds"), dict) else _replay_tuning_thresholds({})
    thr_medium = float(replay_thr.get("avg_filtered_medium") or 1.5)
    thr_high = float(replay_thr.get("avg_filtered_high") or 3.0)
    thr_low = float(replay_thr.get("avg_filtered_low") or 0.3)
    thr_max_round_red = int(replay_thr.get("max_round_hits_red") or 3)
    thr_expired_red = int(replay_thr.get("expired_hits_red") or 4)
    replay_stats = await _load_recent_replay_stats(db, book_id=bid, limit=5)
    avg_replay_filtered = float(replay_stats.get("avg_replay_filtered") or 0.0)
    max_round_hits = int(replay_stats.get("max_round_hits") or 0)
    expired_hits = int(replay_stats.get("expired_hits") or 0)
    tuned_defer_grace = 0.12
    if avg_replay_filtered >= thr_high:
        tuned_defer_grace = 0.16
    elif avg_replay_filtered >= thr_medium:
        tuned_defer_grace = 0.14
    elif avg_replay_filtered <= thr_low:
        tuned_defer_grace = 0.10
    tuned_max_rounds = 4 if max_round_hits >= thr_max_round_red else 3
    if expired_hits >= thr_expired_red and tuned_defer_grace < 0.16:
        tuned_defer_grace = round(min(0.16, tuned_defer_grace + 0.02), 2)
    tuned_defer_grace = round(max(0.0, min(0.5, tuned_defer_grace)), 2)
    actions: list[dict] = []
    if float(reader.get("fatigue") or 0.0) > 0.65:
        actions.append(
            {
                "type": "adjust_orchestrator_limits",
                "payload": {
                    "max_structure_weight": 3,
                    "max_tasks": 2,
                    "ban_strong_cliff": True,
                    "replay": {"defer_max_rounds": tuned_max_rounds, "defer_expire_grace": tuned_defer_grace},
                    "context_budget": {
                        "character_facts": {"max_items": 6, "max_chars": 800},
                        "timeline_facts": {"max_items": 6, "max_chars": 800},
                        "open_foreshadows": {"max_items": 4, "max_chars": 700},
                        "growth_milestones": {"max_items": 4, "max_chars": 700},
                    },
                },
                "reason": f"reader fatigue high; replay tuned by recent traces (avg_filtered={avg_replay_filtered:.2f})",
            }
        )
    if float(reader.get("clarity") or 0.0) < 0.35:
        actions.append(
            {
                "type": "inject_reveal_combo",
                "payload": {"combo_type": "reveal_combo", "window_next_chapters": 2},
                "reason": "reader clarity low",
            }
        )
    if float(reader.get("expectation") or 0.0) < 0.4:
        actions.append(
            {
                "type": "schedule_combo_next_chapters",
                "payload": {"combo_type": "setup_hook_combo", "window_next_chapters": 2},
                "reason": "reader expectation low",
            }
        )
    if not actions and alerts:
        actions.append(
            {
                "type": "ab_test_plan",
                "payload": {"kind": "orchestrator_ab", "variants": ["current", "reader_tuned"], "sample_chapters": 3},
                "reason": "alerts present; run controlled experiment",
            }
        )
    diagnosis_out = {**diagnosis, "replay_stats": replay_stats, "replay_thresholds": replay_thr}
    return {"mode": "propose", "diagnosis": diagnosis_out, "actions": actions, "requires_confirmation": True}


@app.post("/v1/agent/apply")
async def agent_apply_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    bid = str(body.get("book_id") or "").strip()
    if not bid:
        raise HTTPException(status_code=400, detail="book_id required")
    await _ensure_agent_audit_table(db)
    cid = str(body.get("chapter_id") or "").strip() or None
    proposal_id = str(body.get("proposal_id") or "").strip()
    note = str(body.get("operator_note") or "").strip()
    dry_run = bool(body.get("dry_run"))
    actions = body.get("actions") if isinstance(body.get("actions"), list) else []
    # Compatibility: accept minimal payload {action, ...} without wrapping in actions[].
    if not actions and isinstance(body.get("action"), str):
        direct_action = str(body.get("action") or "").strip()
        payload_direct = {k: v for k, v in (body or {}).items() if k not in {"book_id", "chapter_id", "proposal_id", "operator_note", "dry_run", "actions", "action"}}
        actions = [{"type": direct_action, "payload": payload_direct}]
    applied: list[dict] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        a_type = str(action.get("type") or "").strip()
        payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
        if a_type in {"patch_limits", "adjust_orchestrator_limits"}:
            if a_type == "patch_limits":
                patch_in = payload.get("patch") if isinstance(payload.get("patch"), dict) else payload
                before_row = await db.execute(
                    text("SELECT orchestrator_limits FROM book_state WHERE book_id=CAST(:book_id AS uuid) LIMIT 1"),
                    {"book_id": bid},
                )
                before_limits = before_row.scalar_one_or_none()
                before_limits = before_limits if isinstance(before_limits, dict) else {}
                after_limits = dict(before_limits)
                for k, v in (patch_in or {}).items():
                    after_limits[str(k)] = v
                if not dry_run:
                    await db.execute(
                        text(
                            """
                            INSERT INTO book_state(book_id, orchestrator_limits)
                            VALUES (CAST(:book_id AS uuid), CAST(:limits AS jsonb))
                            ON CONFLICT (book_id) DO UPDATE SET orchestrator_limits=EXCLUDED.orchestrator_limits, updated_at=now()
                            """
                        ),
                        {"book_id": bid, "limits": json.dumps(after_limits, ensure_ascii=False)},
                    )
                row = await db.execute(
                    text(
                        """
                        INSERT INTO agent_action_audit_log(
                          book_id, chapter_id, proposal_id, action_type, action_payload, before_state, after_state, status, note
                        )
                        VALUES (
                          CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), :proposal_id, :action_type, CAST(:action_payload AS jsonb),
                          CAST(:before_state AS jsonb), CAST(:after_state AS jsonb), :status, :note
                        )
                        RETURNING audit_id
                        """
                    ),
                    {
                        "book_id": bid,
                        "chapter_id": cid,
                        "proposal_id": proposal_id,
                        "action_type": "patch_limits",
                        "action_payload": json.dumps({"patch": patch_in}, ensure_ascii=False),
                        "before_state": json.dumps({"action": "patch_limits", "book_id": bid, "limits": before_limits}, ensure_ascii=False),
                        "after_state": json.dumps({"action": "patch_limits", "book_id": bid, "limits": after_limits}, ensure_ascii=False),
                        "status": "dry_run" if dry_run else "applied",
                        "note": note,
                    },
                )
                await db.commit()
                applied.append(
                    {
                        "type": "patch_limits",
                        "status": "dry_run" if dry_run else "applied",
                        "payload": {"patch": patch_in},
                        "result": {"limits": after_limits},
                        "audit_id": str(row.scalar_one()),
                    }
                )
                continue

            target_scope = str(payload.get("scope") or ("chapter" if cid else "book")).strip().lower()
            target_chapter_id = str(payload.get("chapter_id") or cid or "").strip()
            if target_scope not in {"book", "chapter"}:
                target_scope = "book"
            if target_scope == "chapter" and not target_chapter_id:
                raise HTTPException(status_code=400, detail="chapter scope requires chapter_id")
            before_settings = (await get_chapter_settings(db, target_chapter_id) or {}) if target_scope == "chapter" else (await get_book_settings(db, bid) or {})
            max_weight = max(2, min(7, int(payload.get("max_structure_weight") or 4)))
            max_tasks = max(1, min(5, int(payload.get("max_tasks") or 3)))
            ban_strong = bool(payload.get("ban_strong_cliff"))
            replay_in = payload.get("replay") if isinstance(payload.get("replay"), dict) else {}
            defer_max_rounds = max(1, min(8, int(replay_in.get("defer_max_rounds") or payload.get("defer_max_rounds") or 3)))
            defer_expire_grace = max(0.0, min(0.5, float(replay_in.get("defer_expire_grace") or payload.get("defer_expire_grace") or 0.12)))
            ctx_budget_in = payload.get("context_budget") if isinstance(payload.get("context_budget"), dict) else {}
            norm_budget: dict[str, dict[str, int]] = {}
            for key, dflt in {
                "character_facts": {"max_items": 8, "max_chars": 1000},
                "timeline_facts": {"max_items": 8, "max_chars": 1000},
                "open_foreshadows": {"max_items": 6, "max_chars": 900},
                "growth_milestones": {"max_items": 6, "max_chars": 900},
            }.items():
                raw = ctx_budget_in.get(key) if isinstance(ctx_budget_in.get(key), dict) else {}
                norm_budget[key] = {
                    "max_items": max(1, min(20, int(raw.get("max_items") or dflt["max_items"]))),
                    "max_chars": max(120, min(6000, int(raw.get("max_chars") or dflt["max_chars"]))),
                }
            patch = {
                "orchestrator": {
                    "max_structure_weight": max_weight,
                    "max_tasks_per_chapter": max_tasks,
                    "ban_strong_cliff": ban_strong,
                    "replay": {"defer_max_rounds": defer_max_rounds, "defer_expire_grace": defer_expire_grace},
                    "context_budget": norm_budget,
                },
            }
            merged = before_settings
            if not dry_run:
                if target_scope == "chapter":
                    merged = await set_chapter_settings(db, target_chapter_id, patch)
                else:
                    merged = await set_book_settings(db, bid, patch)
            settings_diff = diff_settings(before_settings, merged)
            row = await db.execute(
                text(
                    """
                    INSERT INTO agent_action_audit_log(
                      book_id, chapter_id, proposal_id, action_type, action_payload, before_state, after_state, status, note
                    )
                    VALUES (
                      CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), :proposal_id, :action_type, CAST(:action_payload AS jsonb),
                      CAST(:before_state AS jsonb), CAST(:after_state AS jsonb), :status, :note
                    )
                    RETURNING audit_id
                    """
                ),
                {
                    "book_id": bid,
                    "chapter_id": cid,
                    "proposal_id": proposal_id,
                    "action_type": a_type,
                    "action_payload": json.dumps(payload, ensure_ascii=False),
                    "before_state": json.dumps(
                        {
                            "scope": target_scope,
                            "chapter_id": target_chapter_id if target_scope == "chapter" else None,
                            "book_settings": before_settings if target_scope == "book" else None,
                            "chapter_settings": before_settings if target_scope == "chapter" else None,
                        },
                        ensure_ascii=False,
                    ),
                    "after_state": json.dumps(
                        {
                            "scope": target_scope,
                            "chapter_id": target_chapter_id if target_scope == "chapter" else None,
                            "book_settings": merged if target_scope == "book" else None,
                            "chapter_settings": merged if target_scope == "chapter" else None,
                            "patch": patch,
                            "book_settings_diff": settings_diff,
                        },
                        ensure_ascii=False,
                    ),
                    "status": "dry_run" if dry_run else "applied",
                    "note": note,
                },
            )
            await db.commit()
            audit_id = str(row.scalar_one())
            applied.append(
                {
                    "type": a_type,
                    "payload": {
                        "scope": target_scope,
                        "chapter_id": target_chapter_id if target_scope == "chapter" else None,
                        "max_structure_weight": max_weight,
                        "max_tasks": max_tasks,
                        "ban_strong_cliff": ban_strong,
                        "replay": {"defer_max_rounds": defer_max_rounds, "defer_expire_grace": defer_expire_grace},
                        "context_budget": norm_budget,
                    },
                    "book_settings": merged if target_scope == "book" else None,
                    "chapter_settings": merged if target_scope == "chapter" else None,
                    "book_settings_diff": settings_diff,
                    "audit_id": audit_id,
                    "status": "dry_run" if dry_run else "applied",
                }
            )
        elif a_type in {"inject_combo", "inject_reveal_combo", "schedule_combo_next_chapters"}:
            if a_type == "inject_combo":
                combo_type = str(payload.get("combo_type") or "").strip()
                if not combo_type:
                    raise HTTPException(status_code=400, detail="inject_combo requires combo_type")
                win_next = max(1, min(8, int(payload.get("window_next_chapters") or 2)))
                prio = max(1, min(10, int(payload.get("priority") or 3)))
                volume_id = str(payload.get("volume_id") or "").strip() or None
                expires_after_chapter_no = payload.get("expires_after_chapter_no")
                if expires_after_chapter_no is None:
                    base_chapter_no: int | None = None
                    chapter_hint = str(payload.get("chapter_id") or cid or "").strip()
                    if chapter_hint:
                        cno_row = await db.execute(
                            text('SELECT "order" AS chapter_no FROM chapter WHERE chapter_id=CAST(:chapter_id AS uuid) LIMIT 1'),
                            {"chapter_id": chapter_hint},
                        )
                        cno = cno_row.mappings().first()
                        if cno:
                            base_chapter_no = int(cno.get("chapter_no") or 0)
                    if base_chapter_no and base_chapter_no > 0:
                        expires_after_chapter_no = base_chapter_no + win_next
                if expires_after_chapter_no is not None:
                    expires_after_chapter_no = int(expires_after_chapter_no)
                inj_id: str | None = None
                if not dry_run:
                    ins_inj = await db.execute(
                        text(
                            """
                            INSERT INTO combo_injection(
                              book_id, volume_id, combo_type, window_next_chapters, priority, status, expires_after_chapter_no
                            )
                            VALUES (
                              CAST(:book_id AS uuid), CAST(:volume_id AS uuid), :combo_type, :win_next, :priority, 'pending', :expires_after_chapter_no
                            )
                            RETURNING inj_id::text
                            """
                        ),
                        {
                            "book_id": bid,
                            "volume_id": volume_id,
                            "combo_type": combo_type,
                            "win_next": win_next,
                            "priority": prio,
                            "expires_after_chapter_no": expires_after_chapter_no,
                        },
                    )
                    inj_id = str(ins_inj.scalar_one())
                row = await db.execute(
                    text(
                        """
                        INSERT INTO agent_action_audit_log(
                          book_id, chapter_id, proposal_id, action_type, action_payload, before_state, after_state, status, note
                        )
                        VALUES (
                          CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), :proposal_id, :action_type, CAST(:action_payload AS jsonb),
                          CAST(:before_state AS jsonb), CAST(:after_state AS jsonb), :status, :note
                        )
                        RETURNING audit_id
                        """
                    ),
                    {
                        "book_id": bid,
                        "chapter_id": cid,
                        "proposal_id": proposal_id,
                        "action_type": "inject_combo",
                        "action_payload": json.dumps(payload, ensure_ascii=False),
                        "before_state": json.dumps({"action": "inject_combo", "book_id": bid, "volume_id": volume_id}, ensure_ascii=False),
                        "after_state": json.dumps(
                            {
                                "action": "inject_combo",
                                "book_id": bid,
                                "volume_id": volume_id,
                                "inj_id": inj_id,
                                "combo_type": combo_type,
                                "window_next_chapters": win_next,
                                "priority": prio,
                                "status": "pending",
                                "expires_after_chapter_no": expires_after_chapter_no,
                            },
                            ensure_ascii=False,
                        ),
                        "status": "dry_run" if dry_run else "applied",
                        "note": note,
                    },
                )
                await db.commit()
                applied.append(
                    {
                        "type": "inject_combo",
                        "status": "dry_run" if dry_run else "applied",
                        "payload": {
                            "combo_type": combo_type,
                            "window_next_chapters": win_next,
                            "priority": prio,
                            "volume_id": volume_id,
                            "expires_after_chapter_no": expires_after_chapter_no,
                        },
                        "result": {"inj_id": inj_id},
                        "audit_id": str(row.scalar_one()),
                    }
                )
                continue
            row = await db.execute(
                text(
                    """
                    INSERT INTO agent_action_audit_log(
                      book_id, chapter_id, proposal_id, action_type, action_payload, before_state, after_state, status, note
                    )
                    VALUES (
                      CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), :proposal_id, :action_type, CAST(:action_payload AS jsonb),
                      NULL, NULL, :status, :note
                    )
                    RETURNING audit_id
                    """
                ),
                {
                    "book_id": bid,
                    "chapter_id": cid,
                    "proposal_id": proposal_id,
                    "action_type": a_type,
                    "action_payload": json.dumps(payload, ensure_ascii=False),
                    "status": "dry_run" if dry_run else "accepted_noop",
                    "note": note,
                },
            )
            await db.commit()
            applied.append({"type": a_type, "status": "dry_run" if dry_run else "accepted_noop", "payload": payload, "audit_id": str(row.scalar_one())})
    return {"ok": True, "book_id": bid, "applied": applied, "dry_run": dry_run}


@app.post("/v1/agent/audits/list")
async def agent_audits_list_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    bid = str(body.get("book_id") or "").strip()
    if not bid:
        raise HTTPException(status_code=400, detail="book_id required")
    await _ensure_agent_audit_table(db)
    limit = max(1, min(100, int(body.get("limit") or 30)))
    row = await db.execute(
        text(
            """
            SELECT audit_id::text AS audit_id, book_id::text AS book_id, chapter_id::text AS chapter_id,
                   proposal_id, action_type, action_payload, before_state, after_state, status, note,
                   rollback_of::text AS rollback_of, rolled_back_at, created_at
            FROM agent_action_audit_log
            WHERE book_id=CAST(:book_id AS uuid)
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"book_id": bid, "limit": limit},
    )
    return {"audits": [dict(r) for r in row.mappings().all()]}


@app.post("/v1/agent/combo_injections/list")
async def agent_combo_injections_list_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    bid = str((body or {}).get("book_id") or "").strip()
    volume_id = str((body or {}).get("volume_id") or "").strip()
    status = str((body or {}).get("status") or "all").strip().lower()
    if not bid:
        raise HTTPException(status_code=400, detail="book_id required")
    await _ensure_agent_audit_table(db)
    limit = max(1, min(300, int((body or {}).get("limit") or 100)))
    params: dict[str, Any] = {"book_id": bid, "limit": limit, "status": status}
    if volume_id:
        params["volume_id"] = volume_id
        sql = """
            SELECT inj_id::text AS inj_id, book_id::text AS book_id, volume_id::text AS volume_id,
                   combo_type, window_next_chapters, priority, status,
                   expires_after_chapter_no, consumed_chapter_id::text AS consumed_chapter_id,
                   consumed_at, created_at
            FROM combo_injection
            WHERE book_id=CAST(:book_id AS uuid)
              AND volume_id=CAST(:volume_id AS uuid)
              AND (:status='all' OR status=:status)
            ORDER BY created_at DESC
            LIMIT :limit
        """
    else:
        sql = """
            SELECT inj_id::text AS inj_id, book_id::text AS book_id, volume_id::text AS volume_id,
                   combo_type, window_next_chapters, priority, status,
                   expires_after_chapter_no, consumed_chapter_id::text AS consumed_chapter_id,
                   consumed_at, created_at
            FROM combo_injection
            WHERE book_id=CAST(:book_id AS uuid)
              AND (:status='all' OR status=:status)
            ORDER BY created_at DESC
            LIMIT :limit
        """
    rows = await db.execute(text(sql), params)
    items = [dict(r) for r in rows.mappings().all()]
    summary = {
        "pending": len([x for x in items if str(x.get("status") or "") == "pending"]),
        "consumed": len([x for x in items if str(x.get("status") or "") == "consumed"]),
        "expired": len([x for x in items if str(x.get("status") or "") == "expired"]),
    }
    return {"ok": True, "book_id": bid, "volume_id": volume_id or None, "items": items, "summary": summary}


@app.post("/v1/agent/combo_injections/cleanup")
async def agent_combo_injections_cleanup_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    bid = str((body or {}).get("book_id") or "").strip()
    volume_id = str((body or {}).get("volume_id") or "").strip()
    action = str((body or {}).get("action") or "delete_consumed_expired").strip().lower()
    if not bid:
        raise HTTPException(status_code=400, detail="book_id required")
    await _ensure_agent_audit_table(db)

    deleted = 0
    updated = 0
    if action == "delete_consumed_expired":
        if volume_id:
            res = await db.execute(
                text(
                    """
                    DELETE FROM combo_injection
                    WHERE book_id=CAST(:book_id AS uuid)
                      AND volume_id=CAST(:volume_id AS uuid)
                      AND status IN ('consumed','expired')
                    """
                ),
                {"book_id": bid, "volume_id": volume_id},
            )
        else:
            res = await db.execute(
                text(
                    """
                    DELETE FROM combo_injection
                    WHERE book_id=CAST(:book_id AS uuid)
                      AND status IN ('consumed','expired')
                    """
                ),
                {"book_id": bid},
            )
        deleted = int(getattr(res, "rowcount", 0) or 0)
    elif action == "reset_consumed_to_pending":
        if volume_id:
            res = await db.execute(
                text(
                    """
                    UPDATE combo_injection
                    SET status='pending', consumed_chapter_id=NULL, consumed_at=NULL
                    WHERE book_id=CAST(:book_id AS uuid)
                      AND volume_id=CAST(:volume_id AS uuid)
                      AND status='consumed'
                    """
                ),
                {"book_id": bid, "volume_id": volume_id},
            )
        else:
            res = await db.execute(
                text(
                    """
                    UPDATE combo_injection
                    SET status='pending', consumed_chapter_id=NULL, consumed_at=NULL
                    WHERE book_id=CAST(:book_id AS uuid)
                      AND status='consumed'
                    """
                ),
                {"book_id": bid},
            )
        updated = int(getattr(res, "rowcount", 0) or 0)
    else:
        raise HTTPException(status_code=400, detail="unsupported action")

    await db.commit()
    return {
        "ok": True,
        "book_id": bid,
        "volume_id": volume_id or None,
        "action": action,
        "deleted": deleted,
        "updated": updated,
    }


@app.post("/v1/agent/rollback")
async def agent_rollback_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    bid = str(body.get("book_id") or "").strip()
    audit_id = str(body.get("audit_id") or "").strip()
    reason = str(body.get("reason") or "").strip()
    if not audit_id:
        raise HTTPException(status_code=400, detail="audit_id required")
    await _ensure_agent_audit_table(db)
    if bid:
        row = await db.execute(
            text(
                """
                SELECT *
                FROM agent_action_audit_log
                WHERE audit_id=CAST(:audit_id AS uuid) AND book_id=CAST(:book_id AS uuid)
                LIMIT 1
                """
            ),
            {"audit_id": audit_id, "book_id": bid},
        )
    else:
        row = await db.execute(
            text(
                """
                SELECT *
                FROM agent_action_audit_log
                WHERE audit_id=CAST(:audit_id AS uuid)
                LIMIT 1
                """
            ),
            {"audit_id": audit_id},
        )
    audit = row.mappings().first()
    if not audit:
        raise HTTPException(status_code=404, detail="AUDIT_NOT_FOUND")
    bid = str(audit.get("book_id") or "")
    if audit.get("rolled_back_at"):
        return {"ok": True, "book_id": bid, "audit_id": audit_id, "already_rolled_back": True}

    current_before_rollback = await get_book_settings(db, bid) or {}
    current_chapter_before_rollback: dict | None = None
    restored = None
    restored_diff: list[dict] = []
    a_type = str(audit.get("action_type") or "")
    before_state = audit.get("before_state") if isinstance(audit.get("before_state"), dict) else {}
    after_state = audit.get("after_state") if isinstance(audit.get("after_state"), dict) else {}
    rollback_kind = str(before_state.get("action") or after_state.get("action") or a_type).strip().lower()
    if rollback_kind == "patch_limits":
        before_limits = before_state.get("limits") if isinstance(before_state.get("limits"), dict) else {}
        await db.execute(
            text(
                """
                INSERT INTO book_state(book_id, orchestrator_limits)
                VALUES (CAST(:book_id AS uuid), CAST(:limits AS jsonb))
                ON CONFLICT (book_id) DO UPDATE SET orchestrator_limits=EXCLUDED.orchestrator_limits, updated_at=now()
                """
            ),
            {"book_id": bid, "limits": json.dumps(before_limits, ensure_ascii=False)},
        )
        restored = {"limits": before_limits}
    elif rollback_kind == "inject_combo":
        inj_id = str(after_state.get("inj_id") or "").strip()
        if not inj_id:
            raise HTTPException(status_code=400, detail="inject_combo rollback requires after_state.inj_id")
        await db.execute(text("DELETE FROM combo_injection WHERE inj_id=CAST(:inj_id AS uuid)"), {"inj_id": inj_id})
        restored = {"deleted_inj_id": inj_id}
    elif a_type == "adjust_orchestrator_limits":
        scope = str(before_state.get("scope") or "book").strip().lower()
        if scope == "chapter":
            chapter_id = str(before_state.get("chapter_id") or audit.get("chapter_id") or "").strip()
            if chapter_id:
                current_chapter_before_rollback = await get_chapter_settings(db, chapter_id) or {}
                chapter_settings_before = before_state.get("chapter_settings") if isinstance(before_state.get("chapter_settings"), dict) else {}
                restored = await _replace_chapter_settings(db, chapter_id, chapter_settings_before)
                restored_diff = diff_settings(current_chapter_before_rollback, restored if isinstance(restored, dict) else {})
            else:
                restored = {}
                restored_diff = []
        else:
            book_settings_before = before_state.get("book_settings") if isinstance(before_state.get("book_settings"), dict) else {}
            restored = await _replace_book_settings(db, bid, book_settings_before)
            restored_diff = diff_settings(current_before_rollback, restored if isinstance(restored, dict) else {})

    await db.execute(
        text(
            """
            UPDATE agent_action_audit_log
            SET rolled_back_at=now()
            WHERE audit_id=CAST(:audit_id AS uuid)
            """
        ),
        {"audit_id": audit_id},
    )
    ins = await db.execute(
        text(
            """
            INSERT INTO agent_action_audit_log(
              book_id, chapter_id, proposal_id, action_type, action_payload, before_state, after_state, status, note, rollback_of
            )
            VALUES (
              CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), :proposal_id, 'rollback', CAST(:action_payload AS jsonb),
              CAST(:before_state AS jsonb), CAST(:after_state AS jsonb), 'applied', :note, CAST(:rollback_of AS uuid)
            )
            RETURNING audit_id
            """
        ),
        {
            "book_id": bid,
            "chapter_id": str(audit.get("chapter_id")) if audit.get("chapter_id") else None,
            "proposal_id": str(audit.get("proposal_id") or ""),
            "action_payload": json.dumps({"target_audit_id": audit_id, "target_action_type": a_type, "rollback_kind": rollback_kind}, ensure_ascii=False),
            "before_state": json.dumps(
                {
                    "current_book_settings": current_before_rollback,
                    "current_chapter_settings": current_chapter_before_rollback if isinstance(current_chapter_before_rollback, dict) else None,
                },
                ensure_ascii=False,
            ),
            "after_state": json.dumps(
                {
                    "restored_book_settings": restored if isinstance(current_chapter_before_rollback, dict) is False else None,
                    "restored_chapter_settings": restored if isinstance(current_chapter_before_rollback, dict) else None,
                    "book_settings_diff": restored_diff,
                }
                if isinstance(restored, dict)
                else {},
                ensure_ascii=False,
            ),
            "note": reason,
            "rollback_of": audit_id,
        },
    )
    await db.commit()
    return {
        "ok": True,
        "book_id": bid,
        "audit_id": audit_id,
        "rollback_audit_id": str(ins.scalar_one()),
        "restored": restored,
        "book_settings_diff": restored_diff,
    }


def _rewrite_level_rules(level: str) -> tuple[str, float]:
    lv = str(level or "L1").strip().upper()
    if lv not in {"L1", "L2", "L3"}:
        lv = "L1"
    if lv == "L1":
        return (
            "L1 Rules:\n- Light polish only.\n- Keep paragraph structure mostly intact.\n- Remove repetitive robotic phrases.\n- No event/causality change.",
            0.10,
        )
    if lv == "L2":
        return (
            "L2 Rules:\n- Strong de-AI rewrite.\n- Improve rhythm and dialogue naturalness.\n- Allow moderate paragraph reshaping.\n- Keep facts/event order strictly unchanged.",
            0.20,
        )
    return (
        "L3 Rules:\n- Stylized rewrite with stronger voice.\n- Allow larger phrasing and cadence changes.\n- Keep same POV and same factual storyline.\n- Do not change cliff underlying problem.",
        0.25,
    )


def _rewrite_build_prompt(*, source_text: str, level: str, fact_lock: dict, style_profile: dict) -> str:
    level_rules, _ = _rewrite_level_rules(level)
    lines: list[str] = []
    lines.append("[SYS]")
    lines.append("You are rewriting a Chinese web novel chapter to sound human-written.")
    lines.append("You MUST preserve all facts in FACT_LOCK_JSON.")
    lines.append("Do not add new characters/items/events. Do not change causality or event order.")
    lines.append("Return exactly one section: REWRITTEN_TEXT:")
    lines.append("[/SYS]")
    lines.append("")
    lines.append("[FACT_LOCK_JSON]")
    lines.append(json.dumps(fact_lock if isinstance(fact_lock, dict) else {}, ensure_ascii=False))
    lines.append("[/FACT_LOCK_JSON]")
    lines.append("")
    lines.append("[STYLE_PROFILE_JSON]")
    lines.append(json.dumps(style_profile if isinstance(style_profile, dict) else {}, ensure_ascii=False))
    lines.append("[/STYLE_PROFILE_JSON]")
    lines.append("")
    lines.append("[REWRITE_LEVEL]")
    lines.append(level_rules)
    lines.append("[/REWRITE_LEVEL]")
    lines.append("")
    lines.append("[INPUT_TEXT]")
    lines.append(source_text)
    lines.append("[/INPUT_TEXT]")
    lines.append("")
    lines.append("REWRITTEN_TEXT:")
    return "\n".join(lines)


def _extract_rewritten_text(raw: str) -> str:
    txt = str(raw or "")
    up = txt.upper()
    idx = up.find("REWRITTEN_TEXT:")
    if idx >= 0:
        return txt[idx + len("REWRITTEN_TEXT:") :].strip()
    return txt.strip()


def _paragraph_diff(before_text: str, after_text: str) -> dict:
    before = [x for x in re.split(r"\n\s*\n", str(before_text or "").strip())]
    after = [x for x in re.split(r"\n\s*\n", str(after_text or "").strip())]
    sm = difflib.SequenceMatcher(a=before, b=after)
    ops: list[dict] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        ops.append(
            {
                "op": tag,
                "a_idx": [i1, i2],
                "b_idx": [j1, j2],
                "a_text": before[i1:i2],
                "b_text": after[j1:j2],
            }
        )
    unified = "\n".join(
        difflib.unified_diff(
            str(before_text or "").splitlines(),
            str(after_text or "").splitlines(),
            fromfile="before",
            tofile="after",
            lineterm="",
        )
    )
    return {"ops": ops, "unified": unified}


def _rewrite_guard_validate(*, source_text: str, rewritten_text: str, level: str, fact_lock: dict) -> dict:
    _, max_ratio = _rewrite_level_rules(level)
    src = str(source_text or "")
    rew = str(rewritten_text or "")
    src_len = len(src)
    rew_len = len(rew)
    ratio = 0.0 if src_len <= 0 else abs(rew_len - src_len) / float(max(1, src_len))
    risk_flags: list[str] = []
    violations: list[str] = []
    if ratio > max_ratio:
        violations.append(f"length_delta_exceeded:{round(ratio,4)}>{max_ratio}")
    must = fact_lock.get("must_preserve") if isinstance(fact_lock, dict) and isinstance(fact_lock.get("must_preserve"), dict) else {}
    for key in ("characters", "locations", "items"):
        for token in (must.get(key) if isinstance(must.get(key), list) else []):
            tok = str(token or "").strip()
            if not tok:
                continue
            if tok in src and tok not in rew:
                violations.append(f"missing_preserve_token:{key}:{tok}")
    events = must.get("events") if isinstance(must.get("events"), list) else []
    for e in events[:4]:
        ev = str(e or "").strip()
        if not ev:
            continue
        kws = [x for x in re.split(r"[\s,;，。！？、]+", ev) if len(x) >= 2][:3]
        if kws and not any(k in rew for k in kws):
            risk_flags.append(f"event_keyword_weak:{ev[:24]}")
    ok = len(violations) == 0
    return {
        "ok": ok,
        "violations": violations,
        "risk_flags": risk_flags,
        "metrics": {
            "len_before": src_len,
            "len_after": rew_len,
            "length_delta_ratio": round(ratio, 6),
            "max_allowed_delta_ratio": max_ratio,
        },
    }


def _rewrite_build_fact_lock(*, base: dict | None, final_tasks_intent: list[dict] | None) -> dict:
    out = base if isinstance(base, dict) else {}
    must_keep = out.get("must_keep_tasks_evidence") if isinstance(out.get("must_keep_tasks_evidence"), list) else []
    if (not must_keep) and isinstance(final_tasks_intent, list):
        rows = []
        for t in final_tasks_intent[:12]:
            if not isinstance(t, dict):
                continue
            ttype = str(t.get("type") or t.get("task_type") or "").strip()
            ev = t.get("evidence_required") if isinstance(t.get("evidence_required"), list) else []
            if not ttype:
                continue
            rows.append({"task_type": ttype, "evidence": " | ".join([str(x) for x in ev[:3]])})
        out = {**out, "must_keep_tasks_evidence": rows}
    return out


@app.post("/v1/rewrite/run")
async def rewrite_run_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_workflow_tables(db)
    book_id = str((body or {}).get("book_id") or "").strip()
    chapter_id = str((body or {}).get("chapter_id") or "").strip()
    source_draft_id = str((body or {}).get("source_draft_id") or "").strip()
    level = str((body or {}).get("level") or "L1").strip().upper()
    source_text = str((body or {}).get("text") or "").strip()
    style_profile = (body or {}).get("style_profile") if isinstance((body or {}).get("style_profile"), dict) else {}
    fact_lock_in = (body or {}).get("fact_lock") if isinstance((body or {}).get("fact_lock"), dict) else {}
    if not source_text:
        if not source_draft_id:
            raise HTTPException(status_code=400, detail="text or source_draft_id required")
        row = await db.execute(
            text(
                """
                SELECT draft_id::text AS draft_id, book_id::text AS book_id, chapter_id::text AS chapter_id, run_id::text AS run_id, text
                FROM chapter_draft
                WHERE draft_id=CAST(:draft_id AS uuid)
                LIMIT 1
                """
            ),
            {"draft_id": source_draft_id},
        )
        d = row.mappings().first()
        if not d:
            raise HTTPException(status_code=404, detail="SOURCE_DRAFT_NOT_FOUND")
        source_text = str(d.get("text") or "")
        if not book_id:
            book_id = str(d.get("book_id") or "")
        if not chapter_id:
            chapter_id = str(d.get("chapter_id") or "")
    if not source_text.strip():
        raise HTTPException(status_code=400, detail="SOURCE_TEXT_EMPTY")
    if not book_id:
        raise HTTPException(status_code=400, detail="book_id required")
    if not chapter_id:
        raise HTTPException(status_code=400, detail="chapter_id required")

    # Build fallback fact lock from latest run trace if not provided.
    fact_lock = fact_lock_in
    if not fact_lock:
        trace_row = await db.execute(
            text(
                """
                SELECT payload
                FROM chapter_trace
                WHERE chapter_id=CAST(:chapter_id AS uuid)
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"chapter_id": chapter_id},
        )
        tr = trace_row.mappings().first()
        payload = tr.get("payload") if tr and isinstance(tr.get("payload"), dict) else {}
        final_tasks = payload.get("final_tasks") if isinstance(payload.get("final_tasks"), list) else []
        fact_lock = {
            "must_preserve": {"events": []},
            "must_not_add": {"new_characters": True, "new_magic_system": True},
        }
        fact_lock = _rewrite_build_fact_lock(base=fact_lock, final_tasks_intent=final_tasks)
    else:
        fact_lock = _rewrite_build_fact_lock(base=fact_lock, final_tasks_intent=None)

    prompt = _rewrite_build_prompt(source_text=source_text, level=level, fact_lock=fact_lock, style_profile=style_profile)
    client = OllamaClient(settings.ollama_host)
    out = await client.chat(
        model=DEFAULT_LLM_MODEL,
        user=prompt,
        system="你是中文网文润色编辑。只输出 REWRITTEN_TEXT 段落。",
        temperature=0.35 if level == "L1" else (0.45 if level == "L2" else 0.55),
        max_tokens=max(1200, min(9000, int(len(source_text) * 1.5))),
        timeout_s=160,
        retries=1,
        meta={"route": "rewrite_run", "book_id": book_id, "chapter_id": chapter_id, "level": level},
    )
    rewritten_text = _extract_rewritten_text(str(out.get("text") or ""))
    guard = _rewrite_guard_validate(source_text=source_text, rewritten_text=rewritten_text, level=level, fact_lock=fact_lock)
    diff_obj = _paragraph_diff(source_text, rewritten_text)
    rewrite_report = {
        "level": level,
        "risk_flags": guard.get("risk_flags", []),
        "violations": guard.get("violations", []),
        "metrics": guard.get("metrics", {}),
        "guard_ok": bool(guard.get("ok")),
    }
    return {
        "ok": bool(guard.get("ok")),
        "book_id": book_id,
        "chapter_id": chapter_id,
        "source_draft_id": source_draft_id or None,
        "rewritten_text": rewritten_text,
        "diff": diff_obj,
        "rewrite_report": rewrite_report,
        "fact_lock": fact_lock,
    }


@app.post("/v1/rewrite/accept")
async def rewrite_accept_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_workflow_tables(db)
    source_draft_id = str((body or {}).get("source_draft_id") or "").strip()
    rewritten_text = str((body or {}).get("rewritten_text") or "").strip()
    level = str((body or {}).get("level") or "L1").strip().upper()
    rewrite_report = (body or {}).get("rewrite_report") if isinstance((body or {}).get("rewrite_report"), dict) else {}
    diff_obj = (body or {}).get("diff") if isinstance((body or {}).get("diff"), dict) else {}
    if not source_draft_id:
        raise HTTPException(status_code=400, detail="source_draft_id required")
    if not rewritten_text:
        raise HTTPException(status_code=400, detail="rewritten_text required")

    row = await db.execute(
        text(
            """
            SELECT draft_id::text AS draft_id, book_id::text AS book_id, chapter_id::text AS chapter_id, run_id::text AS run_id, variant, text
            FROM chapter_draft
            WHERE draft_id=CAST(:draft_id AS uuid)
            LIMIT 1
            """
        ),
        {"draft_id": source_draft_id},
    )
    src = row.mappings().first()
    if not src:
        raise HTTPException(status_code=404, detail="SOURCE_DRAFT_NOT_FOUND")
    book_id = str(src.get("book_id") or "")
    chapter_id = str(src.get("chapter_id") or "")
    run_id = str(src.get("run_id") or "")
    if not run_id:
        raise HTTPException(status_code=400, detail="SOURCE_DRAFT_RUN_ID_MISSING")

    variant_base = "R1" if level == "L1" else ("R2" if level == "L2" else "R3")
    variant = variant_base
    exists = await db.execute(
        text("SELECT 1 FROM chapter_draft WHERE run_id=CAST(:run_id AS uuid) AND variant=:variant LIMIT 1"),
        {"run_id": run_id, "variant": variant},
    )
    if exists.first():
        for i in range(2, 50):
            cand = f"{variant_base}_{i}"
            chk = await db.execute(
                text("SELECT 1 FROM chapter_draft WHERE run_id=CAST(:run_id AS uuid) AND variant=:variant LIMIT 1"),
                {"run_id": run_id, "variant": cand},
            )
            if not chk.first():
                variant = cand
                break

    ins = await db.execute(
        text(
            """
            INSERT INTO chapter_draft(
              book_id, chapter_id, run_id, variant, text, parent_draft_id,
              rewrite_level, rewrite_meta, branch, is_candidate, is_selected, selected_at
            )
            VALUES (
              CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), CAST(:run_id AS uuid), :variant, :text,
              CAST(:parent_draft_id AS uuid), :rewrite_level, CAST(:rewrite_meta AS jsonb),
              :branch, true, true, now()
            )
            RETURNING draft_id::text AS draft_id
            """
        ),
        {
            "book_id": book_id,
            "chapter_id": chapter_id,
            "run_id": run_id,
            "variant": variant,
            "text": rewritten_text,
            "parent_draft_id": source_draft_id,
            "rewrite_level": level,
            "branch": variant,
            "rewrite_meta": json.dumps(
                {
                    "rewrite_report": rewrite_report,
                    "diff_summary": {
                        "ops_count": len(diff_obj.get("ops") if isinstance(diff_obj.get("ops"), list) else []),
                    },
                },
                ensure_ascii=False,
            ),
        },
    )
    new_draft_id = str((ins.mappings().first() or {}).get("draft_id") or "")
    await db.execute(
        text(
            """
            INSERT INTO chapter_selected(chapter_id, selected_draft_id, selected_branch, selected_by, selected_reason)
            VALUES (CAST(:chapter_id AS uuid), CAST(:draft_id AS uuid), :branch, 'user', 'rewrite_accept')
            ON CONFLICT(chapter_id) DO UPDATE SET
              selected_draft_id=EXCLUDED.selected_draft_id,
              selected_branch=EXCLUDED.selected_branch,
              selected_by=EXCLUDED.selected_by,
              selected_reason=EXCLUDED.selected_reason,
              selected_at=now()
            """
        ),
        {"chapter_id": chapter_id, "draft_id": new_draft_id, "branch": variant},
    )
    await db.execute(
        text(
            """
            UPDATE chapter_draft
            SET is_selected = (draft_id=CAST(:draft_id AS uuid)),
                selected_at = CASE WHEN draft_id=CAST(:draft_id AS uuid) THEN now() ELSE selected_at END
            WHERE chapter_id=CAST(:chapter_id AS uuid)
            """
        ),
        {"chapter_id": chapter_id, "draft_id": new_draft_id},
    )
    await db.execute(
        text("UPDATE chapter SET active_draft_id=CAST(:draft_id AS uuid) WHERE chapter_id=CAST(:chapter_id AS uuid)"),
        {"draft_id": new_draft_id, "chapter_id": chapter_id},
    )
    # Rewrite inherits structure events from parent draft by default.
    await db.execute(
        text(
            """
            INSERT INTO chapter_events(draft_id, book_id, chapter_id, events, validated)
            SELECT CAST(:new_draft_id AS uuid), CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), ce.events, false
            FROM chapter_events ce
            WHERE ce.draft_id=CAST(:parent_draft_id AS uuid)
            ON CONFLICT (draft_id) DO UPDATE
            SET events=EXCLUDED.events, validated=EXCLUDED.validated
            """
        ),
        {
            "new_draft_id": new_draft_id,
            "book_id": book_id,
            "chapter_id": chapter_id,
            "parent_draft_id": source_draft_id,
        },
    )
    audit = await db.execute(
        text(
            """
            INSERT INTO state_apply_audit(book_id, chapter_id, run_id, action_type, before_state, after_state, diff, reason)
            VALUES(
              CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), CAST(:run_id AS uuid), 'rewrite_accept',
              CAST(:before_state AS jsonb), CAST(:after_state AS jsonb), CAST(:diff AS jsonb), :reason
            )
            RETURNING audit_id::text AS audit_id
            """
        ),
        {
            "book_id": book_id,
            "chapter_id": chapter_id,
            "run_id": run_id,
            "before_state": json.dumps({"source_draft_id": source_draft_id, "source_variant": str(src.get("variant") or "")}, ensure_ascii=False),
            "after_state": json.dumps({"accepted_draft_id": new_draft_id, "variant": variant, "rewrite_level": level}, ensure_ascii=False),
            "diff": json.dumps(diff_obj if isinstance(diff_obj, dict) else {}, ensure_ascii=False),
            "reason": "accept rewrite from desktop",
        },
    )
    await db.commit()
    return {
        "ok": True,
        "book_id": book_id,
        "chapter_id": chapter_id,
        "source_draft_id": source_draft_id,
        "accepted_draft_id": new_draft_id,
        "variant": variant,
        "rewrite_level": level,
        "active_draft_id": new_draft_id,
        "audit_id": str((audit.mappings().first() or {}).get("audit_id") or ""),
    }


@app.get("/v1/chapters/{chapter_id}/drafts")
async def chapter_drafts_list_route(chapter_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_workflow_tables(db)
    row_ch = await db.execute(
        text("SELECT chapter_id::text AS chapter_id, book_id::text AS book_id, active_draft_id::text AS active_draft_id FROM chapter WHERE chapter_id=CAST(:chapter_id AS uuid) LIMIT 1"),
        {"chapter_id": str(chapter_id)},
    )
    ch = row_ch.mappings().first()
    if not ch:
        raise HTTPException(status_code=404, detail="CHAPTER_NOT_FOUND")
    sel_row = await db.execute(
        text(
            """
            SELECT selected_draft_id::text AS selected_draft_id, selected_branch, selected_by, selected_reason, selected_at
            FROM chapter_selected
            WHERE chapter_id=CAST(:chapter_id AS uuid)
            LIMIT 1
            """
        ),
        {"chapter_id": str(chapter_id)},
    )
    sel = sel_row.mappings().first()
    selected_id = str((sel.get("selected_draft_id") if sel else "") or "")
    active_id = selected_id or str(ch.get("active_draft_id") or "")
    rows = await db.execute(
        text(
            """
            SELECT
              draft_id::text AS draft_id,
              parent_draft_id::text AS parent_draft_id,
              run_id::text AS run_id,
              variant,
              branch,
              is_candidate,
              is_selected,
              selected_at,
              rewrite_level,
              rewrite_meta,
              created_at,
              length(text) AS text_length
            FROM chapter_draft
            WHERE chapter_id=CAST(:chapter_id AS uuid)
            ORDER BY created_at DESC
            """
        ),
        {"chapter_id": str(chapter_id)},
    )
    items = []
    for r in rows.mappings().all():
        x = dict(r)
        did = str(x.get("draft_id") or "")
        x["is_active"] = bool(active_id and did == active_id)
        items.append(x)
    return {
        "ok": True,
        "chapter_id": str(chapter_id),
        "book_id": str(ch.get("book_id") or ""),
        "selected": dict(sel) if sel else None,
        "active_draft_id": active_id or None,
        "items": items,
    }


@app.get("/v1/drafts/{draft_id}")
async def draft_get_route(draft_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_workflow_tables(db)
    row = await db.execute(
        text(
            """
            SELECT
              d.draft_id::text AS draft_id,
              d.book_id::text AS book_id,
              d.chapter_id::text AS chapter_id,
              d.run_id::text AS run_id,
              d.variant,
              d.branch,
              d.parent_draft_id::text AS parent_draft_id,
              d.is_candidate,
              d.is_selected,
              d.selected_at,
              d.rewrite_level,
              d.rewrite_meta,
              d.created_at,
              d.text
            FROM chapter_draft d
            WHERE d.draft_id=CAST(:draft_id AS uuid)
            LIMIT 1
            """
        ),
        {"draft_id": str(draft_id)},
    )
    hit = row.mappings().first()
    if not hit:
        raise HTTPException(status_code=404, detail="DRAFT_NOT_FOUND")
    return {"ok": True, "item": dict(hit)}


@app.get("/v1/chapters/{chapter_id}/latest_text_preview")
async def chapter_latest_text_preview_route(chapter_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_workflow_tables(db)
    row_ch = await db.execute(
        text("SELECT chapter_id::text AS chapter_id FROM chapter WHERE chapter_id=CAST(:chapter_id AS uuid) LIMIT 1"),
        {"chapter_id": str(chapter_id)},
    )
    ch = row_ch.mappings().first()
    if not ch:
        raise HTTPException(status_code=404, detail="CHAPTER_NOT_FOUND")

    row_draft = await db.execute(
        text(
            """
            SELECT
              d.draft_id::text AS draft_id,
              d.text,
              d.created_at
            FROM chapter c
            LEFT JOIN chapter_selected cs ON cs.chapter_id=c.chapter_id
            LEFT JOIN chapter_draft d ON d.draft_id=COALESCE(cs.selected_draft_id, c.active_draft_id)
            WHERE c.chapter_id=CAST(:chapter_id AS uuid)
            LIMIT 1
            """
        ),
        {"chapter_id": str(chapter_id)},
    )
    d = row_draft.mappings().first()
    draft_text = str((d or {}).get("text") or "").strip()
    if draft_text:
        return {
            "ok": True,
            "chapter_id": str(chapter_id),
            "source": "draft",
            "draft_id": str((d or {}).get("draft_id") or ""),
            "text": draft_text,
            "created_at": (d or {}).get("created_at"),
        }

    row_tv = await db.execute(
        text(
            """
            SELECT text_ver_id::text AS text_ver_id, content, created_at
            FROM chapter_text_version
            WHERE chapter_id=CAST(:chapter_id AS uuid)
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"chapter_id": str(chapter_id)},
    )
    tv = row_tv.mappings().first()
    if not tv:
        raise HTTPException(status_code=404, detail="TEXT_VERSION_NOT_FOUND")
    text_value = str((tv or {}).get("content") or "").strip()
    if not text_value:
        raise HTTPException(status_code=404, detail="TEXT_VERSION_CONTENT_EMPTY")
    return {
        "ok": True,
        "chapter_id": str(chapter_id),
        "source": "text_version",
        "text_ver_id": str((tv or {}).get("text_ver_id") or ""),
        "text": text_value,
        "created_at": (tv or {}).get("created_at"),
    }


@app.post("/v1/chapters/{chapter_id}/manual_import")
async def chapter_manual_import_route(chapter_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_workflow_tables(db)
    chapter_id_text = str(chapter_id)
    row_ch = await db.execute(
        text(
            """
            SELECT chapter_id::text AS chapter_id, book_id::text AS book_id, "order" AS chapter_no, title
            FROM chapter
            WHERE chapter_id=CAST(:chapter_id AS uuid)
            LIMIT 1
            """
        ),
        {"chapter_id": chapter_id_text},
    )
    chapter_hit = row_ch.mappings().first()
    if not chapter_hit:
        raise HTTPException(status_code=404, detail="CHAPTER_NOT_FOUND")

    content = str((body or {}).get("content") or (body or {}).get("text") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="CHAPTER_IMPORT_TEXT_EMPTY")
    note = str((body or {}).get("note") or "manual_import").strip() or "manual_import"
    source = str((body or {}).get("source") or "manual_import").strip() or "manual_import"
    selected_by = str((body or {}).get("selected_by") or "user").strip() or "user"

    book_id_text = str(chapter_hit.get("book_id") or "")
    run_id = str(uuid4())
    idem_key = f"manual_import:{chapter_id_text}:{run_id}"
    now = datetime.now(timezone.utc)
    await db.execute(
        text(
            """
            INSERT INTO workflow_run(
              run_id, workflow_id, workflow_version, book_id, chapter_id, idempotency_key,
              status, started_at, ended_at, ctx_snapshot, meta
            )
            VALUES (
              CAST(:run_id AS uuid), 'manual_import_v1', 1, CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), :idempotency_key,
              'succeeded', :started_at, :ended_at, CAST(:ctx_snapshot AS jsonb), CAST(:meta AS jsonb)
            )
            """
        ),
        {
            "run_id": run_id,
            "book_id": book_id_text,
            "chapter_id": chapter_id_text,
            "idempotency_key": idem_key,
            "started_at": now,
            "ended_at": now,
            "ctx_snapshot": json.dumps({"chapter_id": chapter_id_text, "mode": "manual_import"}, ensure_ascii=False),
            "meta": json.dumps({"mode": "manual_import", "note": note}, ensure_ascii=False),
        },
    )

    ins_draft = await db.execute(
        text(
            """
            INSERT INTO chapter_draft(book_id, chapter_id, run_id, variant, branch, text, is_candidate, is_selected)
            VALUES (
              CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), CAST(:run_id AS uuid),
              :variant, :branch, :text, true, true
            )
            RETURNING draft_id::text AS draft_id, created_at
            """
        ),
        {
            "book_id": book_id_text,
            "chapter_id": chapter_id_text,
            "run_id": run_id,
            "variant": "MANUAL",
            "branch": "MANUAL",
            "text": content,
        },
    )
    draft_row = ins_draft.mappings().first() or {}
    draft_id = str(draft_row.get("draft_id") or "")

    await db.execute(
        text(
            """
            INSERT INTO chapter_selected(chapter_id, selected_draft_id, selected_branch, selected_by, selected_reason)
            VALUES (CAST(:chapter_id AS uuid), CAST(:draft_id AS uuid), 'MANUAL', :selected_by, :selected_reason)
            ON CONFLICT (chapter_id) DO UPDATE SET
              selected_draft_id=EXCLUDED.selected_draft_id,
              selected_branch=EXCLUDED.selected_branch,
              selected_by=EXCLUDED.selected_by,
              selected_reason=EXCLUDED.selected_reason,
              selected_at=now()
            """
        ),
        {
            "chapter_id": chapter_id_text,
            "draft_id": draft_id,
            "selected_by": selected_by,
            "selected_reason": "manual_import",
        },
    )
    await db.execute(
        text("UPDATE chapter SET active_draft_id=CAST(:draft_id AS uuid) WHERE chapter_id=CAST(:chapter_id AS uuid)"),
        {"chapter_id": chapter_id_text, "draft_id": draft_id},
    )
    await db.execute(
        text(
            """
            UPDATE chapter_draft
            SET is_selected=(draft_id=CAST(:draft_id AS uuid)),
                selected_at=CASE WHEN draft_id=CAST(:draft_id AS uuid) THEN now() ELSE selected_at END
            WHERE chapter_id=CAST(:chapter_id AS uuid)
            """
        ),
        {"chapter_id": chapter_id_text, "draft_id": draft_id},
    )

    ins_text_ver = await db.execute(
        text(
            """
            INSERT INTO chapter_text_version(chapter_id, outline_version, source, content, note, meta)
            VALUES (
              CAST(:chapter_id AS uuid), 1, :source, :content, :note, CAST(:meta AS jsonb)
            )
            RETURNING text_ver_id::text AS text_ver_id, created_at
            """
        ),
        {
            "chapter_id": chapter_id_text,
            "source": source,
            "content": content,
            "note": note,
            "meta": json.dumps(
                {
                    "manual_import": True,
                    "selected_by": selected_by,
                    "run_id": run_id,
                    "draft_id": draft_id,
                    "imported_at": now.isoformat(),
                },
                ensure_ascii=False,
            ),
        },
    )
    text_ver_row = ins_text_ver.mappings().first() or {}
    text_ver_id = str(text_ver_row.get("text_ver_id") or "")

    await db.commit()
    return {
        "ok": True,
        "book_id": book_id_text,
        "chapter_id": chapter_id_text,
        "chapter_no": int(chapter_hit.get("chapter_no") or 0),
        "chapter_title": str(chapter_hit.get("title") or ""),
        "mode": "strong_override",
        "run_id": run_id,
        "draft": {
            "draft_id": draft_id,
            "branch": "MANUAL",
            "selected": True,
            "active": True,
            "created_at": draft_row.get("created_at"),
        },
        "text_version": {
            "text_ver_id": text_ver_id,
            "source": source,
            "created_at": text_ver_row.get("created_at"),
        },
    }


@app.delete("/v1/drafts/{draft_id}")
async def draft_delete_route(draft_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_workflow_tables(db)
    draft_id_str = str(draft_id)
    row = await db.execute(
        text(
            """
            SELECT
              d.draft_id::text AS draft_id,
              d.book_id::text AS book_id,
              d.chapter_id::text AS chapter_id,
              d.branch,
              d.created_at,
              c.active_draft_id::text AS active_draft_id,
              cs.selected_draft_id::text AS selected_draft_id
            FROM chapter_draft d
            JOIN chapter c ON c.chapter_id=d.chapter_id
            LEFT JOIN chapter_selected cs ON cs.chapter_id=d.chapter_id
            WHERE d.draft_id=CAST(:draft_id AS uuid)
            LIMIT 1
            """
        ),
        {"draft_id": draft_id_str},
    )
    hit = row.mappings().first()
    if not hit:
        raise HTTPException(status_code=404, detail="DRAFT_NOT_FOUND")

    chapter_id = str(hit.get("chapter_id") or "")
    selected_draft_id = str(hit.get("selected_draft_id") or "")
    active_draft_id = str(hit.get("active_draft_id") or "")
    need_switch_selected = bool(selected_draft_id and selected_draft_id == draft_id_str)
    need_switch_active = bool(active_draft_id and active_draft_id == draft_id_str)

    count_row = await db.execute(
        text("SELECT COUNT(*)::int AS n FROM chapter_draft WHERE chapter_id=CAST(:chapter_id AS uuid)"),
        {"chapter_id": chapter_id},
    )
    total_drafts = int((count_row.mappings().first() or {}).get("n") or 0)
    if total_drafts <= 1:
        raise HTTPException(status_code=400, detail="DRAFT_DELETE_LAST_FORBIDDEN")

    replacement_id = ""
    replacement_branch = ""

    async def _pick_specific(candidate_id: str) -> tuple[str, str]:
        cid = str(candidate_id or "").strip()
        if not cid or cid == draft_id_str:
            return ("", "")
        c_row = await db.execute(
            text(
                """
                SELECT draft_id::text AS draft_id, branch
                FROM chapter_draft
                WHERE chapter_id=CAST(:chapter_id AS uuid)
                  AND draft_id=CAST(:draft_id AS uuid)
                LIMIT 1
                """
            ),
            {"chapter_id": chapter_id, "draft_id": cid},
        )
        c_hit = c_row.mappings().first()
        if not c_hit:
            return ("", "")
        return (str(c_hit.get("draft_id") or ""), str(c_hit.get("branch") or "A"))

    if need_switch_selected:
        replacement_id, replacement_branch = await _pick_specific(active_draft_id)
    if not replacement_id and need_switch_active:
        replacement_id, replacement_branch = await _pick_specific(selected_draft_id)
    if not replacement_id and (need_switch_selected or need_switch_active):
        rep_row = await db.execute(
            text(
                """
                SELECT draft_id::text AS draft_id, branch
                FROM chapter_draft
                WHERE chapter_id=CAST(:chapter_id AS uuid)
                  AND draft_id<>CAST(:draft_id AS uuid)
                ORDER BY
                  CASE WHEN is_selected THEN 0 ELSE 1 END,
                  created_at DESC
                LIMIT 1
                """
            ),
            {"chapter_id": chapter_id, "draft_id": draft_id_str},
        )
        rep_hit = rep_row.mappings().first()
        replacement_id = str((rep_hit or {}).get("draft_id") or "")
        replacement_branch = str((rep_hit or {}).get("branch") or "A")

    if (need_switch_selected or need_switch_active) and not replacement_id:
        raise HTTPException(status_code=400, detail="DRAFT_DELETE_NO_REPLACEMENT")

    switched = False
    if need_switch_selected and replacement_id:
        await db.execute(
            text(
                """
                INSERT INTO chapter_selected(chapter_id, selected_draft_id, selected_branch, selected_by, selected_reason)
                VALUES (CAST(:chapter_id AS uuid), CAST(:draft_id AS uuid), :branch, 'system', 'auto_switch_before_delete')
                ON CONFLICT(chapter_id) DO UPDATE SET
                  selected_draft_id=EXCLUDED.selected_draft_id,
                  selected_branch=EXCLUDED.selected_branch,
                  selected_by=EXCLUDED.selected_by,
                  selected_reason=EXCLUDED.selected_reason,
                  selected_at=now()
                """
            ),
            {"chapter_id": chapter_id, "draft_id": replacement_id, "branch": replacement_branch or "A"},
        )
        await db.execute(
            text(
                """
                UPDATE chapter_draft
                SET is_selected=(draft_id=CAST(:draft_id AS uuid)),
                    selected_at=CASE WHEN draft_id=CAST(:draft_id AS uuid) THEN now() ELSE selected_at END
                WHERE chapter_id=CAST(:chapter_id AS uuid)
                """
            ),
            {"chapter_id": chapter_id, "draft_id": replacement_id},
        )
        switched = True

    if need_switch_active and replacement_id:
        await db.execute(
            text("UPDATE chapter SET active_draft_id=CAST(:draft_id AS uuid) WHERE chapter_id=CAST(:chapter_id AS uuid)"),
            {"chapter_id": chapter_id, "draft_id": replacement_id},
        )
        switched = True

    del_row = await db.execute(
        text(
            """
            DELETE FROM chapter_draft
            WHERE draft_id=CAST(:draft_id AS uuid)
            RETURNING draft_id::text AS draft_id, chapter_id::text AS chapter_id, book_id::text AS book_id, branch
            """
        ),
        {"draft_id": draft_id_str},
    )
    deleted = del_row.mappings().first()
    if not deleted:
        await db.rollback()
        raise HTTPException(status_code=404, detail="DRAFT_NOT_FOUND")
    await db.commit()
    return {
        "ok": True,
        "deleted": dict(deleted),
        "switched": switched,
        "replacement_draft_id": replacement_id or None,
        "replacement_branch": replacement_branch or None,
    }


@app.post("/v1/chapters/{chapter_id}/drafts/{draft_id}/activate")
async def chapter_draft_activate_route(chapter_id: UUID, draft_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_workflow_tables(db)
    row = await db.execute(
        text(
            """
            SELECT draft_id::text AS draft_id, chapter_id::text AS chapter_id
            FROM chapter_draft
            WHERE draft_id=CAST(:draft_id AS uuid)
              AND chapter_id=CAST(:chapter_id AS uuid)
            LIMIT 1
            """
        ),
        {"draft_id": str(draft_id), "chapter_id": str(chapter_id)},
    )
    hit = row.mappings().first()
    if not hit:
        raise HTTPException(status_code=404, detail="DRAFT_NOT_FOUND_FOR_CHAPTER")
    await db.execute(
        text("UPDATE chapter SET active_draft_id=CAST(:draft_id AS uuid) WHERE chapter_id=CAST(:chapter_id AS uuid)"),
        {"draft_id": str(draft_id), "chapter_id": str(chapter_id)},
    )
    drow = await db.execute(
        text("SELECT branch FROM chapter_draft WHERE draft_id=CAST(:draft_id AS uuid) LIMIT 1"),
        {"draft_id": str(draft_id)},
    )
    branch = str((drow.mappings().first() or {}).get("branch") or "A")
    await db.execute(
        text(
            """
            INSERT INTO chapter_selected(chapter_id, selected_draft_id, selected_branch, selected_by, selected_reason)
            VALUES (CAST(:chapter_id AS uuid), CAST(:draft_id AS uuid), :branch, 'user', 'manual_activate')
            ON CONFLICT(chapter_id) DO UPDATE SET
              selected_draft_id=EXCLUDED.selected_draft_id,
              selected_branch=EXCLUDED.selected_branch,
              selected_by=EXCLUDED.selected_by,
              selected_reason=EXCLUDED.selected_reason,
              selected_at=now()
            """
        ),
        {"chapter_id": str(chapter_id), "draft_id": str(draft_id), "branch": branch},
    )
    await db.execute(
        text(
            """
            UPDATE chapter_draft
            SET is_selected = (draft_id=CAST(:draft_id AS uuid)),
                selected_at = CASE WHEN draft_id=CAST(:draft_id AS uuid) THEN now() ELSE selected_at END
            WHERE chapter_id=CAST(:chapter_id AS uuid)
            """
        ),
        {"chapter_id": str(chapter_id), "draft_id": str(draft_id)},
    )
    await db.commit()
    return {"ok": True, "chapter_id": str(chapter_id), "active_draft_id": str(draft_id), "selected_draft_id": str(draft_id)}


@app.post("/v1/draft/list_versions")
async def draft_list_versions_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    chapter_id = str((body or {}).get("chapter_id") or "").strip()
    if not chapter_id:
        raise HTTPException(status_code=400, detail="chapter_id required")
    return await chapter_drafts_list_route(UUID(chapter_id), db)


@app.post("/v1/draft/run")
async def draft_run_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_workflow_tables(db)
    book_id = str((body or {}).get("book_id") or "").strip()
    chapter_id = str((body or {}).get("chapter_id") or "").strip()
    chapter_no_raw = (body or {}).get("chapter_no")
    intent_confirmed = str((body or {}).get("intent_confirmed") or "桌面端 Draft Run").strip()
    dry_run = bool((body or {}).get("dry_run", False))
    reuse_if_exists = bool((body or {}).get("reuse_if_exists", True))
    force_stub_llm = bool((body or {}).get("force_stub_llm", False))
    if not book_id:
        raise HTTPException(status_code=400, detail="book_id required")
    input_ctx: dict[str, Any] = {
        "book_id": book_id,
        "intent_confirmed": intent_confirmed,
        "force_stub_llm": force_stub_llm,
    }
    passthrough_keys = {
        "memory_pack_enabled",
        "memory_pack_required",
        "memory_session_key",
        "memory_task_type",
        "memory_task_instruction",
        "memory_query",
        "memory_chapter_window",
        "memory_evidence_top_k",
        "memory_writeback_enabled",
        "memory_writeback_persist",
        "memory_writeback_required",
        "splitbook_id",
    }
    if isinstance(body.get("memory_hard_constraints"), list):
        input_ctx["memory_hard_constraints"] = body.get("memory_hard_constraints")
    for key in passthrough_keys:
        if key in body:
            input_ctx[key] = body.get(key)
    if chapter_id:
        input_ctx["chapter_id"] = chapter_id
    if chapter_no_raw is not None:
        try:
            input_ctx["chapter_no"] = int(chapter_no_raw)
        except Exception:
            raise HTTPException(status_code=400, detail="chapter_no must be int")
    if not chapter_id and "chapter_no" not in input_ctx:
        raise HTTPException(status_code=400, detail="chapter_id or chapter_no required")

    definition = _workflow_get_definition("draft_runner_v1")
    idem = str((body or {}).get("idempotency_key") or "").strip()
    if not idem:
        idem = _workflow_make_idempotency_key(
            "draft_runner_v1",
            int(definition.get("version") or 1),
            input_ctx,
            dry_run,
        )
    result = await _workflow_execute_run(
        db=db,
        workflow_id="draft_runner_v1",
        definition=definition,
        input_ctx=input_ctx,
        idempotency_key=idem,
        dry_run=dry_run,
        reuse_if_exists=reuse_if_exists,
    )
    return {
        "ok": bool(result.get("ok")),
        "run_id": result.get("run_id"),
        "workflow_id": "draft_runner_v1",
        "status": result.get("status"),
        "reused": bool(result.get("reused", False)),
        "output": result.get("output") if isinstance(result.get("output"), dict) else {},
        "input": input_ctx,
    }


async def _closed_loop_noop_progress(*_args, **_kwargs) -> None:
    return None


async def _closed_loop_noop_log(*_args, **_kwargs) -> None:
    return None


def _visible_text_len(text: str) -> int:
    return len(re.sub(r"\s+", "", str(text or "")))


async def _ensure_closed_loop_min_length(
    db: AsyncSession,
    *,
    book_id: str,
    chapter_id: str,
    chapter_no: int,
    chapter_title: str,
    commit_result: dict[str, Any],
    min_chars: int = 3000,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "ok": True,
        "applied": False,
        "min_chars": int(min_chars),
        "before_chars": 0,
        "after_chars": 0,
    }
    text_ver_id = str(commit_result.get("text_ver_id") or "").strip()
    if not text_ver_id:
        out["ok"] = False
        out["reason"] = "text_ver_missing"
        return out
    row = await db.execute(
        text(
            """
            SELECT content
            FROM chapter_text_version
            WHERE text_ver_id=CAST(:text_ver_id AS uuid)
            LIMIT 1
            """
        ),
        {"text_ver_id": text_ver_id},
    )
    hit = row.mappings().first()
    source_text = str((hit or {}).get("content") or "").strip()
    before_chars = _visible_text_len(source_text)
    out["before_chars"] = before_chars
    if before_chars >= min_chars:
        out["after_chars"] = before_chars
        out["reason"] = "already_enough"
        return out

    try:
        chapter_outline = await get_outline_detail_service(db, chapter_id, None)
    except RuntimeError:
        chapter_outline = {}
    outline_detail = chapter_outline.get("outline_detail") if isinstance(chapter_outline.get("outline_detail"), dict) else {}
    nodes = outline_detail.get("nodes") if isinstance(outline_detail.get("nodes"), list) else []
    brief = await get_book_settings(db, book_id) or {}
    writing_brief = brief.get("writing_brief") if isinstance(brief.get("writing_brief"), dict) else {}
    prompt_payload = {
        "chapter_no": chapter_no,
        "chapter_title": chapter_title,
        "min_chars": min_chars,
        "writing_brief": _build_master_outline_brief_payload(writing_brief),
        "outline_nodes": nodes[:10],
        "source_text": source_text[:9000],
        "rules": [
            "保持原有剧情事实与时间线",
            "仅扩充场景细节、动作、心理、对话",
            "不得删减关键冲突与章末钩子",
        ],
    }
    user_prompt = (
        "请将以下章节正文扩写到指定长度，返回纯正文文本，不要任何解释。\n"
        "要求：保持剧情事实不变，增强可读性与细节，确保章节完整。\n"
        f"输入：{json.dumps(prompt_payload, ensure_ascii=False)}"
    )
    client = OllamaClient(settings.ollama_host)
    try:
        llm_out = await client.chat(
            model=DEFAULT_LLM_MODEL,
            user=user_prompt,
            system="你是网文写作助手。只输出章节正文。",
            temperature=0.55,
            max_tokens=max(3600, min(9000, int(min_chars * 2.4))),
            timeout_s=240,
            retries=1,
            meta={"route": "closed_loop_expand_text", "chapter_id": chapter_id},
        )
    except Exception as exc:
        out["ok"] = False
        out["reason"] = f"expand_failed:{str(exc)[:120]}"
        out["after_chars"] = before_chars
        return out
    expanded = str(llm_out.get("text") or "").strip()
    after_chars = _visible_text_len(expanded)
    out["after_chars"] = after_chars
    if after_chars <= before_chars:
        out["reason"] = "expand_no_growth"
        return out
    await db.execute(
        text(
            """
            UPDATE chapter_text_version
            SET content=:content,
                meta=COALESCE(meta, '{}'::jsonb) || CAST(:meta_patch AS jsonb)
            WHERE text_ver_id=CAST(:text_ver_id AS uuid)
            """
        ),
        {
            "text_ver_id": text_ver_id,
            "content": expanded,
            "meta_patch": json.dumps(
                {
                    "expanded_to_min_chars": min_chars,
                    "expand_before_chars": before_chars,
                    "expand_after_chars": after_chars,
                    "expanded_at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
            ),
        },
    )
    await db.commit()
    out["applied"] = True
    out["reason"] = "expanded"
    return out


async def _resolve_closed_loop_chapter(
    db: AsyncSession,
    *,
    book_id: str | None,
    chapter_id: str | None,
    chapter_no: int | None,
) -> dict:
    if chapter_id:
        row = await db.execute(
            text(
                """
                SELECT chapter_id::text AS chapter_id, book_id::text AS book_id, "order" AS chapter_no, title
                FROM chapter
                WHERE chapter_id=CAST(:chapter_id AS uuid)
                  AND (:book_id = '' OR book_id=CAST(:book_id AS uuid))
                LIMIT 1
                """
            ),
            {"chapter_id": chapter_id, "book_id": str(book_id or "")},
        )
        hit = row.mappings().first()
        if not hit:
            raise RuntimeError("CHAPTER_NOT_FOUND")
        return dict(hit)
    if not book_id or chapter_no is None:
        raise RuntimeError("BOOK_ID_AND_CHAPTER_REQUIRED")
    row = await db.execute(
        text(
            """
            SELECT chapter_id::text AS chapter_id, book_id::text AS book_id, "order" AS chapter_no, title
            FROM chapter
            WHERE book_id=CAST(:book_id AS uuid) AND "order"=:chapter_no
            LIMIT 1
            """
        ),
        {"book_id": book_id, "chapter_no": int(chapter_no)},
    )
    hit = row.mappings().first()
    if not hit:
        raise RuntimeError("CHAPTER_NOT_FOUND")
    return dict(hit)


@app.post("/v1/engine/closed_loop/run")
async def engine_closed_loop_run_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_workflow_tables(db)
    book_id_raw = str((body or {}).get("book_id") or "").strip() or None
    chapter_id_raw = str((body or {}).get("chapter_id") or "").strip() or None
    chapter_no_raw = (body or {}).get("chapter_no")
    chapter_no: int | None
    if chapter_no_raw is None or str(chapter_no_raw).strip() == "":
        chapter_no = None
    else:
        try:
            chapter_no = int(chapter_no_raw)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="chapter_no must be int") from exc
    try:
        chapter_hit = await _resolve_closed_loop_chapter(
            db,
            book_id=book_id_raw,
            chapter_id=chapter_id_raw,
            chapter_no=chapter_no,
        )
    except RuntimeError as exc:
        code = str(exc)
        if code == "CHAPTER_NOT_FOUND":
            raise HTTPException(status_code=404, detail=code) from exc
        raise HTTPException(status_code=400, detail=code) from exc

    book_id = str(chapter_hit.get("book_id") or "")
    chapter_id = str(chapter_hit.get("chapter_id") or "")
    chapter_no_final = int(chapter_hit.get("chapter_no") or 0)

    dry_run = bool((body or {}).get("dry_run", False))
    reuse_if_exists = bool((body or {}).get("reuse_if_exists", True))
    force_stub_llm = bool((body or {}).get("force_stub_llm", False))
    intent_confirmed = str((body or {}).get("intent_confirmed") or "闭环写作执行").strip() or "闭环写作执行"
    fail_on_preflight_fail = bool((body or {}).get("fail_on_preflight_fail", False))
    evolve_style = bool((body or {}).get("evolve_style", True))
    style_evolution_cfg = (body or {}).get("style_evolution") if isinstance((body or {}).get("style_evolution"), dict) else {}

    draft_payload: dict[str, Any] = {
        "book_id": book_id,
        "chapter_id": chapter_id,
        "chapter_no": chapter_no_final,
        "intent_confirmed": intent_confirmed,
        "dry_run": dry_run,
        "reuse_if_exists": reuse_if_exists,
        "force_stub_llm": force_stub_llm,
    }
    if str((body or {}).get("idempotency_key") or "").strip():
        draft_payload["idempotency_key"] = str((body or {}).get("idempotency_key")).strip()

    draft_result = await draft_run_route(draft_payload, db)
    run_id = str(draft_result.get("run_id") or "")
    commit_result = ((draft_result.get("output") or {}).get("commit_result") if isinstance(draft_result.get("output"), dict) else {}) or {}
    if run_id and not commit_result:
        run_row = await db.execute(
            text("SELECT meta FROM workflow_run WHERE run_id=CAST(:run_id AS uuid) LIMIT 1"),
            {"run_id": run_id},
        )
        run_hit = run_row.mappings().first()
        meta = run_hit.get("meta") if run_hit and isinstance(run_hit.get("meta"), dict) else {}
        commit_result = meta.get("commit_result") if isinstance(meta.get("commit_result"), dict) else {}

    book_settings = await get_book_settings(db, book_id) or {}
    draft_cfg = book_settings.get("draft") if isinstance(book_settings.get("draft"), dict) else {}
    min_chars = int((body or {}).get("min_chars") or draft_cfg.get("min_chars") or 3000)
    min_chars = max(800, min(12000, min_chars))
    length_guard_result: dict[str, Any] = {"ok": True, "skipped": True, "reason": "disabled"}
    if bool(draft_result.get("ok")) and not dry_run and min_chars > 0:
        length_guard_result = await _ensure_closed_loop_min_length(
            db,
            book_id=book_id,
            chapter_id=chapter_id,
            chapter_no=chapter_no_final,
            chapter_title=str(chapter_hit.get("title") or chapter_hit.get("chapter_title") or f"第{chapter_no_final}章"),
            commit_result=commit_result if isinstance(commit_result, dict) else {},
            min_chars=min_chars,
        )
        if length_guard_result.get("applied"):
            commit_result = {**(commit_result if isinstance(commit_result, dict) else {}), "min_chars_guard_applied": True}
            if isinstance(draft_result.get("output"), dict):
                draft_result["output"]["commit_result"] = commit_result

    do_writeback = bool((body or {}).get("do_writeback", True))
    writeback_input = (body or {}).get("writeback") if isinstance((body or {}).get("writeback"), dict) else {}
    writeback_cfg = {
        "update_outline": bool(writeback_input.get("update_outline", True)),
        "extract_facts": bool(writeback_input.get("extract_facts", True)),
        "extract_growth": bool(writeback_input.get("extract_growth", True)),
        "extract_timeline": bool(writeback_input.get("extract_timeline", True)),
        "extract_new_materials": bool(writeback_input.get("extract_new_materials", True)),
        "run_eval": bool(writeback_input.get("run_eval", True)),
    }
    writeback_result: dict[str, Any] = {"ok": True, "skipped": True, "reason": "disabled"}
    selected_draft_id = str(commit_result.get("selected_draft_id") or "")
    if do_writeback and not dry_run:
        text_ver_id = str(commit_result.get("text_ver_id") or "").strip()
        text_content = str((body or {}).get("text_content") or "").strip()
        if not text_ver_id and not text_content:
            row_text = await db.execute(
                text(
                    """
                    SELECT d.draft_id::text AS draft_id, d.text
                    FROM chapter c
                    LEFT JOIN chapter_selected cs ON cs.chapter_id=c.chapter_id
                    LEFT JOIN chapter_draft d ON d.draft_id=COALESCE(cs.selected_draft_id, c.active_draft_id)
                    WHERE c.chapter_id=CAST(:chapter_id AS uuid)
                    LIMIT 1
                    """
                ),
                {"chapter_id": chapter_id},
            )
            hit = row_text.mappings().first()
            if hit:
                selected_draft_id = selected_draft_id or str(hit.get("draft_id") or "")
                text_content = text_content or str(hit.get("text") or "").strip()
        if not text_ver_id and not text_content:
            writeback_result = {
                "ok": True,
                "skipped": True,
                "reason": "text_not_found",
                "warning": "WRITEBACK_TEXT_NOT_FOUND",
            }
        else:
            commit_payload = {
                "book_id": book_id,
                "chapter_id": chapter_id,
                "commit_txn_id": str(uuid4()),
                "text_ver_id": text_ver_id or None,
                "text_content": text_content or None,
                "writeback": writeback_cfg,
                "skip_save_text_version": bool(text_ver_id),
                "outline_version": (body or {}).get("outline_version"),
            }
            writeback_data = await run_commit_draft_job(
                db,
                commit_payload,
                on_progress=_closed_loop_noop_progress,
                on_log=_closed_loop_noop_log,
            )
            writeback_result = {"ok": True, "skipped": False, "result": writeback_data}
    elif do_writeback and dry_run:
        writeback_result = {"ok": True, "skipped": True, "reason": "dry_run"}

    run_preflight = bool((body or {}).get("run_preflight", True))
    preflight_result: dict[str, Any] = {"ok": True, "skipped": True, "reason": "disabled"}
    if run_preflight:
        volume_id_raw = str((body or {}).get("volume_id") or "").strip()
        volume_hit: dict | None = None
        if volume_id_raw:
            vr = await db.execute(
                text(
                    """
                    SELECT volume_id::text AS volume_id, volume_no, title
                    FROM volume
                    WHERE volume_id=CAST(:volume_id AS uuid) AND book_id=CAST(:book_id AS uuid)
                    LIMIT 1
                    """
                ),
                {"volume_id": volume_id_raw, "book_id": book_id},
            )
            volume_hit = dict(vr.mappings().first() or {}) if vr else None
        if not volume_hit:
            volume_hit = await _find_volume_for_chapter(db, book_id=book_id, chapter_no=chapter_no_final)
        if not volume_hit:
            preflight_result = {"ok": True, "skipped": True, "reason": "volume_not_found"}
        else:
            report = await _run_preflight_for_volume(
                db,
                book_id=book_id,
                volume_id=str(volume_hit.get("volume_id") or ""),
                volume_no=int(volume_hit.get("volume_no") or 1),
            )
            preflight_result = {"ok": True, "skipped": False, "report": report}

    rewrite_cfg = (body or {}).get("rewrite") if isinstance((body or {}).get("rewrite"), dict) else {}
    rewrite_enabled = bool(rewrite_cfg.get("enabled", False))
    rewrite_result: dict[str, Any] = {"ok": True, "skipped": True, "reason": "disabled"}
    if rewrite_enabled and not dry_run:
        rewrite_level = str(rewrite_cfg.get("level") or "L1").strip().upper()
        source_draft_id = str(rewrite_cfg.get("source_draft_id") or selected_draft_id or "").strip()
        if not source_draft_id:
            row_active = await db.execute(
                text("SELECT active_draft_id::text AS active_draft_id FROM chapter WHERE chapter_id=CAST(:chapter_id AS uuid) LIMIT 1"),
                {"chapter_id": chapter_id},
            )
            source_draft_id = str((row_active.mappings().first() or {}).get("active_draft_id") or "")
        rewrite_run = await rewrite_run_route(
            {
                "book_id": book_id,
                "chapter_id": chapter_id,
                "source_draft_id": source_draft_id,
                "level": rewrite_level,
            },
            db,
        )
        rewrite_accept = None
        if bool(rewrite_cfg.get("auto_accept", False)) and bool(rewrite_run.get("ok")) and source_draft_id:
            rewrite_accept = await rewrite_accept_route(
                {
                    "source_draft_id": source_draft_id,
                    "rewritten_text": str(rewrite_run.get("rewritten_text") or ""),
                    "level": rewrite_level,
                    "rewrite_report": rewrite_run.get("rewrite_report") if isinstance(rewrite_run.get("rewrite_report"), dict) else {},
                    "diff": rewrite_run.get("diff") if isinstance(rewrite_run.get("diff"), dict) else {},
                },
                db,
            )
        rewrite_result = {"ok": bool(rewrite_run.get("ok")), "skipped": False, "run": rewrite_run, "accept": rewrite_accept}
    elif rewrite_enabled and dry_run:
        rewrite_result = {"ok": True, "skipped": True, "reason": "dry_run"}

    style_evolution_result: dict[str, Any] = {"ok": True, "skipped": True, "reason": "disabled"}
    if evolve_style and not dry_run:
        try:
            style_evolution_result = await evolve_book_style(
                db,
                book_id=book_id,
                profile_id=(str(style_evolution_cfg.get("profile_id") or "").strip() or None),
                sample_limit=int(style_evolution_cfg.get("sample_limit") or 24),
                min_sample_count=int(style_evolution_cfg.get("min_sample_count") or 6),
                alpha=float(style_evolution_cfg.get("alpha") or 0.58),
                force=bool(style_evolution_cfg.get("force", False)),
                sync_book_settings=bool(style_evolution_cfg.get("sync_book_settings", True)),
                note=str(style_evolution_cfg.get("note") or "").strip() or None,
            )
        except RuntimeError as exc:
            style_evolution_result = {
                "ok": False,
                "skipped": False,
                "reason": str(exc),
            }
        except Exception as exc:
            style_evolution_result = {
                "ok": False,
                "skipped": False,
                "reason": f"STYLE_EVOLUTION_EXCEPTION:{str(exc)}",
            }
    elif evolve_style and dry_run:
        style_evolution_result = {"ok": True, "skipped": True, "reason": "dry_run"}

    preflight_overall = (
        str((((preflight_result.get("report") if isinstance(preflight_result.get("report"), dict) else {}).get("summary") or {}).get("overall") or "")).upper()
        if isinstance(preflight_result, dict)
        else ""
    )
    ok = bool(draft_result.get("ok"))
    ok = ok and bool(writeback_result.get("ok", True))
    ok = ok and bool(rewrite_result.get("ok", True))
    if fail_on_preflight_fail and preflight_overall == "FAIL":
        ok = False

    return {
        "ok": ok,
        "book_id": book_id,
        "chapter_id": chapter_id,
        "chapter_no": chapter_no_final,
        "workflow_run_id": run_id or None,
        "stages": {
            "draft": draft_result,
            "length_guard": length_guard_result,
            "writeback": writeback_result,
            "preflight": preflight_result,
            "rewrite": rewrite_result,
            "style_evolution": style_evolution_result,
        },
        "summary": {
            "preflight_overall": preflight_overall or "UNKNOWN",
            "fail_on_preflight_fail": fail_on_preflight_fail,
            "style_evolution_updated": bool(style_evolution_result.get("updated")),
            "style_evolution_skipped": bool(style_evolution_result.get("skipped")),
            "min_chars_target": min_chars,
            "chapter_chars": int(length_guard_result.get("after_chars") or 0),
        },
    }


@app.post("/v1/draft/select")
async def draft_select_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_workflow_tables(db)
    book_id = str((body or {}).get("book_id") or "").strip()
    chapter_id = str((body or {}).get("chapter_id") or "").strip()
    draft_id = str((body or {}).get("draft_id") or "").strip()
    selected_by = str((body or {}).get("selected_by") or "user").strip() or "user"
    reason = str((body or {}).get("reason") or "").strip()
    if not chapter_id or not draft_id:
        raise HTTPException(status_code=400, detail="chapter_id and draft_id required")
    if not book_id:
        row_b = await db.execute(
            text("SELECT book_id::text AS book_id FROM chapter WHERE chapter_id=CAST(:chapter_id AS uuid) LIMIT 1"),
            {"chapter_id": chapter_id},
        )
        book_id = str((row_b.mappings().first() or {}).get("book_id") or "")
    cur_row = await db.execute(
        text(
            """
            SELECT selected_draft_id::text AS selected_draft_id, selected_branch, selected_by, selected_reason, selected_at
            FROM chapter_selected
            WHERE chapter_id=CAST(:chapter_id AS uuid)
            LIMIT 1
            """
        ),
        {"chapter_id": chapter_id},
    )
    cur = cur_row.mappings().first()
    drow = await db.execute(
        text(
            """
            SELECT draft_id::text AS draft_id, branch, chapter_id::text AS chapter_id
            FROM chapter_draft
            WHERE draft_id=CAST(:draft_id AS uuid) AND chapter_id=CAST(:chapter_id AS uuid)
            LIMIT 1
            """
        ),
        {"draft_id": draft_id, "chapter_id": chapter_id},
    )
    d = drow.mappings().first()
    if not d:
        raise HTTPException(status_code=404, detail="DRAFT_NOT_FOUND_FOR_CHAPTER")
    branch = str(d.get("branch") or "A")
    await db.execute(
        text(
            """
            INSERT INTO chapter_selected(chapter_id, selected_draft_id, selected_branch, selected_by, selected_reason)
            VALUES (CAST(:chapter_id AS uuid), CAST(:draft_id AS uuid), :branch, :selected_by, :selected_reason)
            ON CONFLICT(chapter_id) DO UPDATE SET
              selected_draft_id=EXCLUDED.selected_draft_id,
              selected_branch=EXCLUDED.selected_branch,
              selected_by=EXCLUDED.selected_by,
              selected_reason=EXCLUDED.selected_reason,
              selected_at=now()
            """
        ),
        {
            "chapter_id": chapter_id,
            "draft_id": draft_id,
            "branch": branch,
            "selected_by": selected_by,
            "selected_reason": reason,
        },
    )
    await db.execute(
        text("UPDATE chapter SET active_draft_id=CAST(:draft_id AS uuid) WHERE chapter_id=CAST(:chapter_id AS uuid)"),
        {"chapter_id": chapter_id, "draft_id": draft_id},
    )
    await db.execute(
        text(
            """
            UPDATE chapter_draft
            SET is_selected=(draft_id=CAST(:draft_id AS uuid)),
                selected_at=CASE WHEN draft_id=CAST(:draft_id AS uuid) THEN now() ELSE selected_at END
            WHERE chapter_id=CAST(:chapter_id AS uuid)
            """
        ),
        {"chapter_id": chapter_id, "draft_id": draft_id},
    )
    audit = await db.execute(
        text(
            """
            INSERT INTO state_apply_audit(book_id, chapter_id, action_type, before_state, after_state, diff, reason)
            VALUES(
              CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), 'select_draft',
              CAST(:before_state AS jsonb), CAST(:after_state AS jsonb), CAST(:diff AS jsonb), :reason
            )
            RETURNING audit_id::text AS audit_id
            """
        ),
        {
            "book_id": book_id,
            "chapter_id": chapter_id,
            "before_state": json.dumps({"selected": cur or {}}, ensure_ascii=False, default=str),
            "after_state": json.dumps({"selected": {"selected_draft_id": draft_id, "selected_branch": branch, "selected_by": selected_by}}, ensure_ascii=False),
            "diff": json.dumps({"from": str((cur or {}).get("selected_draft_id") or ""), "to": draft_id}, ensure_ascii=False),
            "reason": reason or "select_draft",
        },
    )
    await db.commit()
    return {
        "ok": True,
        "book_id": book_id,
        "chapter_id": chapter_id,
        "selected_draft_id": draft_id,
        "selected_branch": branch,
        "audit_id": str((audit.mappings().first() or {}).get("audit_id") or ""),
    }


@app.post("/v1/ledger/promote_selected")
async def ledger_promote_selected_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_workflow_tables(db)
    book_id = str((body or {}).get("book_id") or "").strip()
    chapter_id = str((body or {}).get("chapter_id") or "").strip()
    reason = str((body or {}).get("reason") or "promote_selected").strip()
    if not chapter_id:
        raise HTTPException(status_code=400, detail="chapter_id required")
    ch_row = await db.execute(
        text('SELECT chapter_id::text AS chapter_id, book_id::text AS book_id, "order" AS chapter_no FROM chapter WHERE chapter_id=CAST(:chapter_id AS uuid) LIMIT 1'),
        {"chapter_id": chapter_id},
    )
    ch = ch_row.mappings().first()
    if not ch:
        raise HTTPException(status_code=404, detail="CHAPTER_NOT_FOUND")
    if not book_id:
        book_id = str(ch.get("book_id") or "")
    sel_row = await db.execute(
        text("SELECT selected_draft_id::text AS selected_draft_id FROM chapter_selected WHERE chapter_id=CAST(:chapter_id AS uuid) LIMIT 1"),
        {"chapter_id": chapter_id},
    )
    sel = sel_row.mappings().first()
    selected_draft_id = str((sel.get("selected_draft_id") if sel else "") or "")
    if not selected_draft_id:
        active_row = await db.execute(
            text("SELECT active_draft_id::text AS active_draft_id FROM chapter WHERE chapter_id=CAST(:chapter_id AS uuid) LIMIT 1"),
            {"chapter_id": chapter_id},
        )
        selected_draft_id = str((active_row.mappings().first() or {}).get("active_draft_id") or "")
    if not selected_draft_id:
        raise HTTPException(status_code=400, detail="NO_SELECTED_DRAFT")
    ev_row = await db.execute(
        text("SELECT events FROM chapter_events WHERE draft_id=CAST(:draft_id AS uuid) LIMIT 1"),
        {"draft_id": selected_draft_id},
    )
    ev = ev_row.mappings().first()
    events = ev.get("events") if ev and isinstance(ev.get("events"), dict) else {}
    foreshadow_events = events.get("foreshadow_events") if isinstance(events.get("foreshadow_events"), list) else []
    growth_events = events.get("growth_events") if isinstance(events.get("growth_events"), list) else []
    chapter_no = int(ch.get("chapter_no") or 0)

    affected_foreshadow: list[str] = []
    affected_growth: list[str] = []
    before_snapshot = {"foreshadow": {}, "growth": {}}
    after_snapshot = {"foreshadow": {}, "growth": {}}

    for idx, e in enumerate(foreshadow_events):
        if not isinstance(e, dict):
            continue
        key = str(e.get("foreshadow_id") or e.get("key") or e.get("note") or f"foreshadow_{idx}").strip()
        if not key:
            continue
        old_row = await db.execute(
            text("SELECT key, status, last_chapter_no, meta FROM foreshadow_state WHERE book_id=CAST(:book_id AS uuid) AND key=:key LIMIT 1"),
            {"book_id": book_id, "key": key},
        )
        old = old_row.mappings().first()
        before_snapshot["foreshadow"][key] = dict(old) if old else None
        et = str(e.get("event_type") or "").strip().lower()
        new_status = "open"
        if et == "seed":
            new_status = "seeded"
        elif et == "reinforce":
            new_status = "reinforced"
        elif et == "payoff":
            new_status = "payoff"
        meta = {"last_event_type": et, "intensity": int(e.get("intensity") or 1), "note": str(e.get("note") or "")[:240]}
        await db.execute(
            text(
                """
                INSERT INTO foreshadow_state(book_id, key, status, last_chapter_no, meta)
                VALUES (CAST(:book_id AS uuid), :key, :status, :last_chapter_no, CAST(:meta AS jsonb))
                ON CONFLICT(book_id, key) DO UPDATE SET
                  status=EXCLUDED.status,
                  last_chapter_no=EXCLUDED.last_chapter_no,
                  meta=COALESCE(foreshadow_state.meta,'{}'::jsonb) || EXCLUDED.meta
                """
            ),
            {"book_id": book_id, "key": key, "status": new_status, "last_chapter_no": chapter_no, "meta": json.dumps(meta, ensure_ascii=False)},
        )
        new_row = await db.execute(
            text("SELECT key, status, last_chapter_no, meta FROM foreshadow_state WHERE book_id=CAST(:book_id AS uuid) AND key=:key LIMIT 1"),
            {"book_id": book_id, "key": key},
        )
        after_snapshot["foreshadow"][key] = dict(new_row.mappings().first() or {})
        affected_foreshadow.append(key)

    for idx, e in enumerate(growth_events):
        if not isinstance(e, dict):
            continue
        key = str(e.get("milestone_id") or e.get("key") or e.get("note") or f"growth_{idx}").strip()
        if not key:
            continue
        old_row = await db.execute(
            text("SELECT key, stage, last_chapter_no, meta FROM growth_state WHERE book_id=CAST(:book_id AS uuid) AND key=:key LIMIT 1"),
            {"book_id": book_id, "key": key},
        )
        old = old_row.mappings().first()
        before_snapshot["growth"][key] = dict(old) if old else None
        act = str(e.get("action") or "").strip().lower()
        stage = "achieved" if act == "achieve" else "advance"
        meta = {
            "last_action": act,
            "note": str(e.get("note") or "")[:240],
            "cost_shown": bool(e.get("cost_shown", False)),
            "choice_explicit": bool(e.get("choice_explicit", False)),
        }
        await db.execute(
            text(
                """
                INSERT INTO growth_state(book_id, key, stage, last_chapter_no, meta)
                VALUES (CAST(:book_id AS uuid), :key, :stage, :last_chapter_no, CAST(:meta AS jsonb))
                ON CONFLICT(book_id, key) DO UPDATE SET
                  stage=EXCLUDED.stage,
                  last_chapter_no=EXCLUDED.last_chapter_no,
                  meta=COALESCE(growth_state.meta,'{}'::jsonb) || EXCLUDED.meta
                """
            ),
            {"book_id": book_id, "key": key, "stage": stage, "last_chapter_no": chapter_no, "meta": json.dumps(meta, ensure_ascii=False)},
        )
        new_row = await db.execute(
            text("SELECT key, stage, last_chapter_no, meta FROM growth_state WHERE book_id=CAST(:book_id AS uuid) AND key=:key LIMIT 1"),
            {"book_id": book_id, "key": key},
        )
        after_snapshot["growth"][key] = dict(new_row.mappings().first() or {})
        affected_growth.append(key)

    audit = await db.execute(
        text(
            """
            INSERT INTO state_apply_audit(book_id, chapter_id, action_type, before_state, after_state, diff, reason)
            VALUES (
              CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), 'ledger_promote_selected',
              CAST(:before_state AS jsonb), CAST(:after_state AS jsonb), CAST(:diff AS jsonb), :reason
            )
            RETURNING audit_id::text AS audit_id
            """
        ),
        {
            "book_id": book_id,
            "chapter_id": chapter_id,
            "before_state": json.dumps(before_snapshot, ensure_ascii=False),
            "after_state": json.dumps(after_snapshot, ensure_ascii=False),
            "diff": json.dumps(
                {
                    "selected_draft_id": selected_draft_id,
                    "foreshadow_keys": sorted(list(dict.fromkeys(affected_foreshadow))),
                    "growth_keys": sorted(list(dict.fromkeys(affected_growth))),
                },
                ensure_ascii=False,
            ),
            "reason": reason,
        },
    )
    await db.commit()
    foreshadow_keys = sorted(list(dict.fromkeys(affected_foreshadow)))
    growth_keys = sorted(list(dict.fromkeys(affected_growth)))
    before_foreshadow = {k: before_snapshot["foreshadow"].get(k) for k in foreshadow_keys}
    after_foreshadow = {k: after_snapshot["foreshadow"].get(k) for k in foreshadow_keys}
    before_growth = {k: before_snapshot["growth"].get(k) for k in growth_keys}
    after_growth = {k: after_snapshot["growth"].get(k) for k in growth_keys}
    return {
        "ok": True,
        "book_id": book_id,
        "chapter_id": chapter_id,
        "selected_draft_id": selected_draft_id,
        "affected": {
            # legacy aliases for UI compatibility
            "foreshadow": foreshadow_keys,
            "growth": growth_keys,
            # explicit key lists
            "foreshadow_keys": foreshadow_keys,
            "growth_keys": growth_keys,
            "counts": {
                "foreshadow": len(foreshadow_keys),
                "growth": len(growth_keys),
            },
        },
        "changes": {
            "before": {
                "foreshadow": before_foreshadow,
                "growth": before_growth,
            },
            "after": {
                "foreshadow": after_foreshadow,
                "growth": after_growth,
            },
        },
        "audit_id": str((audit.mappings().first() or {}).get("audit_id") or ""),
    }


@app.get("/v1/books/{book_id}/workspace")
async def book_workspace_get_route(book_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_export_tables(db)
    hit = await _load_workspace_binding(db, str(book_id))
    return {"ok": True, "book_id": str(book_id), "workspace": hit}


@app.post("/v1/books/{book_id}/workspace")
async def book_workspace_set_route(book_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_export_tables(db)
    workspace_path = str((body or {}).get("workspace_path") or "").strip()
    if not workspace_path:
        raise HTTPException(status_code=400, detail="workspace_path required")
    root = Path(workspace_path).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    title_row = await db.execute(
        text("SELECT title FROM book WHERE book_id=CAST(:book_id AS uuid) LIMIT 1"),
        {"book_id": str(book_id)},
    )
    title_hit = title_row.mappings().first()
    if not title_hit:
        raise HTTPException(status_code=404, detail="BOOK_NOT_FOUND")
    title = str((title_hit or {}).get("title") or "")
    slug = _slugify_filename(str((body or {}).get("book_slug") or ""), fallback="") or _slugify_filename(title, fallback=str(book_id))
    await db.execute(
        text(
            """
            INSERT INTO book_workspace(book_id, workspace_path, book_slug, updated_at)
            VALUES (CAST(:book_id AS uuid), :workspace_path, :book_slug, now())
            ON CONFLICT(book_id) DO UPDATE SET
              workspace_path=EXCLUDED.workspace_path,
              book_slug=EXCLUDED.book_slug,
              updated_at=now()
            """
        ),
        {"book_id": str(book_id), "workspace_path": str(root.resolve()), "book_slug": slug},
    )
    await db.commit()
    return {"ok": True, "book_id": str(book_id), "workspace_path": str(root.resolve()), "book_slug": slug}


@app.post("/v1/export/chapter")
async def export_chapter_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_export_tables(db)
    book_id = str((body or {}).get("book_id") or "").strip()
    chapter_id = str((body or {}).get("chapter_id") or "").strip()
    fmt = str((body or {}).get("format") or "md").strip().lower()
    include_header = bool((body or {}).get("include_header", True))
    if fmt not in {"md", "txt"}:
        raise HTTPException(status_code=400, detail="format must be md|txt")
    if not book_id or not chapter_id:
        raise HTTPException(status_code=400, detail="book_id and chapter_id required")
    workspace_root, book_dir, _book_slug = await _resolve_book_workspace(db, book_id)
    row = await db.execute(
        text(
            """
            SELECT c.chapter_id::text AS chapter_id, c."order" AS chapter_no, c.title AS chapter_title,
                   v.volume_id::text AS volume_id, d.text, d.draft_id::text AS draft_id, cs.selected_branch,
                   b.title AS book_title
            FROM chapter c
            JOIN book b ON b.book_id=c.book_id
            JOIN chapter_selected cs ON cs.chapter_id=c.chapter_id
            JOIN chapter_draft d ON d.draft_id=cs.selected_draft_id
            LEFT JOIN volume v
              ON v.book_id=c.book_id
             AND c."order" BETWEEN v.start_chapter_no AND v.end_chapter_no
            WHERE c.book_id=CAST(:book_id AS uuid) AND c.chapter_id=CAST(:chapter_id AS uuid)
            ORDER BY v.volume_no DESC NULLS LAST
            LIMIT 1
            """
        ),
        {"book_id": book_id, "chapter_id": chapter_id},
    )
    ch = row.mappings().first()
    if not ch:
        raise HTTPException(status_code=404, detail="SELECTED_DRAFT_NOT_FOUND_FOR_CHAPTER")
    volume_id = str(ch.get("volume_id") or "").strip()
    vlabel = "V00"
    if volume_id:
        vrow = await db.execute(
            text("SELECT volume_no FROM volume WHERE volume_id=CAST(:volume_id AS uuid) LIMIT 1"),
            {"volume_id": volume_id},
        )
        v = vrow.mappings().first()
        vlabel = f"V{int((v or {}).get('volume_no') or 0):02d}"
    out_path = (book_dir / "volumes" / vlabel / "chapters" / f"{int(ch.get('chapter_no') or 0):04d}.{fmt}").resolve()
    _ensure_path_within(workspace_root, out_path)
    text_body = str(ch.get("text") or "")
    if include_header and fmt == "md":
        content = (
            f"# 第{int(ch.get('chapter_no') or 0):04d}章 {str(ch.get('chapter_title') or '').strip()}\n\n"
            f"> book: {str(ch.get('book_title') or '')} | selected: {str(ch.get('selected_branch') or '')} | draft_id: {str(ch.get('draft_id') or '')}\n\n"
            f"{text_body}\n"
        )
    elif include_header and fmt == "txt":
        content = (
            f"第{int(ch.get('chapter_no') or 0):04d}章 {str(ch.get('chapter_title') or '').strip()}\n"
            f"book={str(ch.get('book_title') or '')} selected={str(ch.get('selected_branch') or '')} draft_id={str(ch.get('draft_id') or '')}\n\n"
            f"{text_body}\n"
        )
    else:
        content = text_body
    sz = _write_text_file(out_path, content)
    return {
        "ok": True,
        "book_id": book_id,
        "chapter_id": chapter_id,
        "output_path": str(out_path),
        "size": int(sz),
        "format": fmt,
    }


@app.post("/v1/export/volume")
async def export_volume_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_export_tables(db)
    book_id = str((body or {}).get("book_id") or "").strip()
    volume_id = str((body or {}).get("volume_id") or "").strip()
    fmt = str((body or {}).get("format") or "md").strip().lower()
    include_ch_titles = bool((body or {}).get("include_chapter_titles", True))
    if fmt not in {"md", "txt"}:
        raise HTTPException(status_code=400, detail="format must be md|txt")
    if not book_id or not volume_id:
        raise HTTPException(status_code=400, detail="book_id and volume_id required")
    workspace_root, book_dir, _book_slug = await _resolve_book_workspace(db, book_id)
    vrow = await db.execute(
        text("SELECT volume_no, title FROM volume WHERE volume_id=CAST(:volume_id AS uuid) AND book_id=CAST(:book_id AS uuid) LIMIT 1"),
        {"book_id": book_id, "volume_id": volume_id},
    )
    vol = vrow.mappings().first()
    if not vol:
        raise HTTPException(status_code=404, detail="VOLUME_NOT_FOUND")
    volume_no = int(vol.get("volume_no") or 0)
    vlabel = f"V{volume_no:02d}"
    rows = await db.execute(
        text(
            """
            SELECT c.chapter_id::text AS chapter_id, c."order" AS chapter_no, c.title AS chapter_title,
                   d.text, d.draft_id::text AS draft_id, cs.selected_branch
            FROM chapter c
            JOIN chapter_selected cs ON cs.chapter_id=c.chapter_id
            JOIN chapter_draft d ON d.draft_id=cs.selected_draft_id
            JOIN volume v
              ON v.book_id=c.book_id
             AND c."order" BETWEEN v.start_chapter_no AND v.end_chapter_no
            WHERE c.book_id=CAST(:book_id AS uuid) AND v.volume_id=CAST(:volume_id AS uuid)
            ORDER BY c."order" ASC
            """
        ),
        {"book_id": book_id, "volume_id": volume_id},
    )
    chapters = [dict(r) for r in rows.mappings().all()]
    if not chapters:
        raise HTTPException(status_code=404, detail="NO_SELECTED_CHAPTERS_IN_VOLUME")
    out_dir = (book_dir / "volumes" / vlabel / "exports" / f"volume_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}").resolve()
    _ensure_path_within(workspace_root, out_dir)
    out_name = f"{vlabel}_full.{fmt}"
    out_path = (out_dir / out_name).resolve()
    chunks: list[str] = []
    if fmt == "md":
        chunks.append(f"# {vlabel} {str(vol.get('title') or '').strip()}\n")
    else:
        chunks.append(f"{vlabel} {str(vol.get('title') or '').strip()}\n")
    for ch in chapters:
        cno = int(ch.get("chapter_no") or 0)
        ctitle = str(ch.get("chapter_title") or "").strip()
        text_body = str(ch.get("text") or "")
        if include_ch_titles:
            if fmt == "md":
                chunks.append(f"\n## 第{cno:04d}章 {ctitle}\n\n{text_body}\n")
            else:
                chunks.append(f"\n第{cno:04d}章 {ctitle}\n\n{text_body}\n")
        else:
            chunks.append(f"\n{text_body}\n")
    sz = _write_text_file(out_path, "\n".join(chunks))
    return {
        "ok": True,
        "book_id": book_id,
        "volume_id": volume_id,
        "output_path": str(out_path),
        "size": int(sz),
        "chapters": len(chapters),
        "format": fmt,
    }


@app.post("/v1/export/publish_pack")
async def export_publish_pack_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_export_tables(db)
    book_id = str((body or {}).get("book_id") or "").strip()
    volume_id = str((body or {}).get("volume_id") or "").strip()
    pack_name = str((body or {}).get("pack_name") or "").strip() or f"publish_pack_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    if not book_id or not volume_id:
        raise HTTPException(status_code=400, detail="book_id and volume_id required")
    workspace_root, book_dir, _book_slug = await _resolve_book_workspace(db, book_id)
    vrow = await db.execute(
        text("SELECT volume_no, title FROM volume WHERE volume_id=CAST(:volume_id AS uuid) AND book_id=CAST(:book_id AS uuid) LIMIT 1"),
        {"book_id": book_id, "volume_id": volume_id},
    )
    vol = vrow.mappings().first()
    if not vol:
        raise HTTPException(status_code=404, detail="VOLUME_NOT_FOUND")
    volume_no = int(vol.get("volume_no") or 0)
    vlabel = f"V{volume_no:02d}"
    chapters_res = await db.execute(
        text(
            """
            SELECT c.chapter_id::text AS chapter_id, c."order" AS chapter_no, c.title AS chapter_title,
                   d.text, d.draft_id::text AS draft_id, d.run_id::text AS run_id, cs.selected_branch
            FROM chapter c
            JOIN chapter_selected cs ON cs.chapter_id=c.chapter_id
            JOIN chapter_draft d ON d.draft_id=cs.selected_draft_id
            JOIN volume v
              ON v.book_id=c.book_id
             AND c."order" BETWEEN v.start_chapter_no AND v.end_chapter_no
            WHERE c.book_id=CAST(:book_id AS uuid) AND v.volume_id=CAST(:volume_id AS uuid)
            ORDER BY c."order" ASC
            """
        ),
        {"book_id": book_id, "volume_id": volume_id},
    )
    chapters = [dict(r) for r in chapters_res.mappings().all()]
    if not chapters:
        raise HTTPException(status_code=404, detail="NO_SELECTED_CHAPTERS_IN_VOLUME")
    out_dir = (book_dir / "volumes" / vlabel / "exports" / _slugify_filename(pack_name, fallback="publish_pack")).resolve()
    _ensure_path_within(workspace_root, out_dir)
    reports_dir = (out_dir / "reports").resolve()
    assets_dir = (out_dir / "assets").resolve()
    ledger_dir = (out_dir / "ledger").resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)
    ledger_dir.mkdir(parents=True, exist_ok=True)

    files: list[dict] = []
    full_md = (out_dir / f"{vlabel}_full.md").resolve()
    full_txt = (out_dir / f"{vlabel}_full.txt").resolve()
    md_chunks = [f"# {vlabel} {str(vol.get('title') or '').strip()}\n"]
    txt_chunks = [f"{vlabel} {str(vol.get('title') or '').strip()}\n"]
    selected_draft_ids: list[str] = []
    for ch in chapters:
        cno = int(ch.get("chapter_no") or 0)
        ctitle = str(ch.get("chapter_title") or "").strip()
        text_body = str(ch.get("text") or "")
        selected_draft_ids.append(str(ch.get("draft_id") or ""))
        md_chunks.append(f"\n## 第{cno:04d}章 {ctitle}\n\n{text_body}\n")
        txt_chunks.append(f"\n第{cno:04d}章 {ctitle}\n\n{text_body}\n")
    files.append({"path": str(full_md), "size": int(_write_text_file(full_md, "\n".join(md_chunks)))})
    files.append({"path": str(full_txt), "size": int(_write_text_file(full_txt, "\n".join(txt_chunks)))})

    chapter_reports_csv = (reports_dir / "chapter_reports.csv").resolve()
    with chapter_reports_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["chapter_no", "chapter_id", "length", "expectation", "tension", "clarity", "satisfaction", "fatigue", "has_events_json"])
        for ch in chapters:
            run_id = str(ch.get("run_id") or "")
            rep_row = await db.execute(
                text("SELECT report FROM chapter_report WHERE run_id=CAST(:run_id AS uuid) LIMIT 1"),
                {"run_id": run_id},
            )
            rep = rep_row.mappings().first()
            report = rep.get("report") if rep and isinstance(rep.get("report"), dict) else {}
            rs = report.get("reader_state") if isinstance(report.get("reader_state"), dict) else {}
            w.writerow(
                [
                    int(ch.get("chapter_no") or 0),
                    str(ch.get("chapter_id") or ""),
                    int(report.get("length") or 0),
                    rs.get("expectation"),
                    rs.get("tension"),
                    rs.get("clarity"),
                    rs.get("satisfaction"),
                    rs.get("fatigue"),
                    bool(report.get("has_events_json", False)),
                ]
            )
    files.append({"path": str(chapter_reports_csv), "size": int(chapter_reports_csv.stat().st_size)})

    preflight = await _run_preflight_for_volume(
        db,
        book_id=book_id,
        volume_id=volume_id,
        volume_no=volume_no,
        chapters=chapters,
    )
    preflight_md = (reports_dir / "preflight_report.md").resolve()
    files.append({"path": str(preflight_md), "size": int(_write_text_file(preflight_md, str(preflight.get("markdown") or "")))})

    foreshadow_csv = (ledger_dir / "foreshadow.csv").resolve()
    fs_rows = await db.execute(
        text("SELECT key, status, last_chapter_no FROM foreshadow_state WHERE book_id=CAST(:book_id AS uuid) ORDER BY key"),
        {"book_id": book_id},
    )
    with foreshadow_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["key", "status", "last_chapter_no"])
        for r in fs_rows.mappings().all():
            w.writerow([str(r.get("key") or ""), str(r.get("status") or ""), int(r.get("last_chapter_no") or 0)])
    files.append({"path": str(foreshadow_csv), "size": int(foreshadow_csv.stat().st_size)})

    growth_csv = (ledger_dir / "growth.csv").resolve()
    gs_rows = await db.execute(
        text("SELECT key, stage, last_chapter_no FROM growth_state WHERE book_id=CAST(:book_id AS uuid) ORDER BY key"),
        {"book_id": book_id},
    )
    with growth_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["key", "stage", "last_chapter_no"])
        for r in gs_rows.mappings().all():
            w.writerow([str(r.get("key") or ""), str(r.get("stage") or ""), int(r.get("last_chapter_no") or 0)])
    files.append({"path": str(growth_csv), "size": int(growth_csv.stat().st_size)})

    combo_csv = (assets_dir / "combos_used.csv").resolve()
    combo_rows = await db.execute(
        text(
            """
            SELECT combo_fp, count(*)::int AS uses
            FROM (
              SELECT unnest(a.used_combo_fingerprints) AS combo_fp
              FROM asset_usage_log a
              JOIN chapter c ON c.chapter_id=a.chapter_id
              JOIN volume v
                ON v.book_id=c.book_id
               AND c."order" BETWEEN v.start_chapter_no AND v.end_chapter_no
              WHERE a.book_id=CAST(:book_id AS uuid) AND v.volume_id=CAST(:volume_id AS uuid)
            ) z
            GROUP BY combo_fp
            ORDER BY uses DESC, combo_fp
            """
        ),
        {"book_id": book_id, "volume_id": volume_id},
    )
    with combo_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["combo_fp", "uses"])
        for r in combo_rows.mappings().all():
            w.writerow([str(r.get("combo_fp") or ""), int(r.get("uses") or 0)])
    files.append({"path": str(combo_csv), "size": int(combo_csv.stat().st_size)})

    chars_json = (assets_dir / "character_cards.json").resolve()
    chars_rows = await db.execute(text("SELECT * FROM character WHERE book_id=CAST(:book_id AS uuid)"), {"book_id": book_id})
    chars_payload = [dict(r) for r in chars_rows.mappings().all()]
    chars_json.write_text(json.dumps(chars_payload, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
    files.append({"path": str(chars_json), "size": int(chars_json.stat().st_size)})

    timeline_json = (assets_dir / "timeline.json").resolve()
    tl_rows = await db.execute(text("SELECT * FROM timeline_event WHERE book_id=CAST(:book_id AS uuid)"), {"book_id": book_id})
    tl_payload = [dict(r) for r in tl_rows.mappings().all()]
    timeline_json.write_text(json.dumps(tl_payload, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
    files.append({"path": str(timeline_json), "size": int(timeline_json.stat().st_size)})

    manifest = {
        "book_id": book_id,
        "volume_id": volume_id,
        "volume_no": volume_no,
        "pack_name": out_dir.name,
        "selected_draft_ids": [x for x in selected_draft_ids if x],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "preflight": {
            "overall": str((preflight.get("summary") or {}).get("overall") or "OK"),
            "fail_count": int((preflight.get("summary") or {}).get("fail_count") or 0),
            "warn_count": int((preflight.get("summary") or {}).get("warn_count") or 0),
            "suggest_count": int((preflight.get("summary") or {}).get("suggest_count") or 0),
            "note_hints": (preflight.get("note_hints") if isinstance(preflight.get("note_hints"), list) else []),
        },
        "files": files,
    }
    await db.execute(
        text(
            """
            INSERT INTO export_log(book_id, volume_id, pack_name, output_dir, manifest)
            VALUES (CAST(:book_id AS uuid), CAST(:volume_id AS uuid), :pack_name, :output_dir, CAST(:manifest AS jsonb))
            """
        ),
        {
            "book_id": book_id,
            "volume_id": volume_id,
            "pack_name": out_dir.name,
            "output_dir": str(out_dir),
            "manifest": json.dumps(manifest, ensure_ascii=False, default=str),
        },
    )
    await db.commit()
    return {"ok": True, "book_id": book_id, "volume_id": volume_id, "output_dir": str(out_dir), "files": files, "manifest": manifest}


@app.post("/v1/preflight/run")
async def preflight_run_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_export_tables(db)
    book_id = str((body or {}).get("book_id") or "").strip()
    volume_id = str((body or {}).get("volume_id") or "").strip()
    write_report = bool((body or {}).get("write_report", False))
    if not book_id or not volume_id:
        raise HTTPException(status_code=400, detail="book_id and volume_id required")
    vrow = await db.execute(
        text("SELECT volume_no FROM volume WHERE volume_id=CAST(:volume_id AS uuid) AND book_id=CAST(:book_id AS uuid) LIMIT 1"),
        {"book_id": book_id, "volume_id": volume_id},
    )
    vol = vrow.mappings().first()
    if not vol:
        raise HTTPException(status_code=404, detail="VOLUME_NOT_FOUND")
    volume_no = int(vol.get("volume_no") or 0)
    report = await _run_preflight_for_volume(
        db,
        book_id=book_id,
        volume_id=volume_id,
        volume_no=volume_no,
        chapters=None,
    )
    output_path = ""
    if write_report:
        workspace_root, book_dir, _book_slug = await _resolve_book_workspace(db, book_id)
        vlabel = f"V{volume_no:02d}"
        out_dir = (book_dir / "volumes" / vlabel / "exports" / f"preflight_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}").resolve()
        _ensure_path_within(workspace_root, out_dir)
        md_path = (out_dir / "reports" / "preflight_report.md").resolve()
        _ensure_path_within(workspace_root, md_path)
        _write_text_file(md_path, str(report.get("markdown") or ""))
        output_path = str(md_path)
    return {
        "ok": True,
        "book_id": book_id,
        "volume_id": volume_id,
        "report": {k: v for k, v in report.items() if k != "markdown"},
        "markdown": str(report.get("markdown") or ""),
        "output_path": output_path,
    }


@app.post("/v1/fixwizard/plan")
async def fixwizard_plan_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    book_id = str((body or {}).get("book_id") or "").strip()
    volume_id = str((body or {}).get("volume_id") or "").strip()
    if not book_id or not volume_id:
        raise HTTPException(status_code=400, detail="book_id and volume_id required")
    volume_row = await db.execute(
        text(
            """
            SELECT volume_no
            FROM volume
            WHERE volume_id=CAST(:volume_id AS uuid) AND book_id=CAST(:book_id AS uuid)
            LIMIT 1
            """
        ),
        {"book_id": book_id, "volume_id": volume_id},
    )
    vr = volume_row.mappings().first()
    if not vr:
        raise HTTPException(status_code=404, detail="VOLUME_NOT_FOUND")
    volume_no = int(vr.get("volume_no") or 1)

    preflight = body.get("preflight") if isinstance(body.get("preflight"), dict) else None
    if not preflight:
        preflight = await _run_preflight_for_volume(
            db,
            book_id=book_id,
            volume_id=volume_id,
            volume_no=volume_no,
        )
    fixes = _fixwizard_build_fixes(book_id, volume_id, preflight if isinstance(preflight, dict) else {})
    return {
        "ok": True,
        "book_id": book_id,
        "volume_id": volume_id,
        "summary": (preflight or {}).get("summary") if isinstance(preflight, dict) else {},
        "fixes": fixes,
    }


@app.post("/v1/fixwizard/execute")
async def fixwizard_execute_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    book_id = str((body or {}).get("book_id") or "").strip()
    volume_id = str((body or {}).get("volume_id") or "").strip()
    chapter_id = str((body or {}).get("chapter_id") or "").strip()
    pack_name = str((body or {}).get("pack_name") or "").strip()
    if not book_id or not volume_id:
        raise HTTPException(status_code=400, detail="book_id and volume_id required")
    await _ensure_fixwizard_tables(db)

    selected_fixes = body.get("selected_fixes") if isinstance(body.get("selected_fixes"), list) else []
    fixes = body.get("fixes") if isinstance(body.get("fixes"), list) else []
    preflight_snapshot = body.get("preflight") if isinstance(body.get("preflight"), dict) else {}
    if not fixes and preflight_snapshot:
        fixes = _fixwizard_build_fixes(book_id, volume_id, preflight_snapshot)
    fixes_map: dict[str, dict] = {}
    for fx in fixes:
        if isinstance(fx, dict):
            fid = str(fx.get("fix_id") or "").strip()
            if fid:
                fixes_map[fid] = fx

    executed: list[dict] = []
    for sf in selected_fixes:
        if isinstance(sf, str):
            sf = {"fix_id": sf}
        if not isinstance(sf, dict):
            continue
        fid = str(sf.get("fix_id") or "").strip()
        fx = sf if isinstance(sf.get("type"), str) else fixes_map.get(fid)
        if not isinstance(fx, dict):
            executed.append({"fix_id": fid, "status": "skipped", "reason": "fix not found"})
            continue
        ftype = str(fx.get("type") or "").strip()
        payload = fx.get("payload") if isinstance(fx.get("payload"), dict) else {}
        overrides = sf.get("overrides") if isinstance(sf.get("overrides"), dict) else {}
        if overrides:
            payload = _merge_dict(payload, overrides)

        if ftype == "agent_apply":
            action_type = str(payload.get("action_type") or "").strip()
            action_payload = payload.get("action_payload") if isinstance(payload.get("action_payload"), dict) else {}
            if not action_type:
                executed.append({"fix_id": fid, "type": ftype, "status": "skipped", "reason": "missing action_type"})
                continue
            apply_out = await agent_apply_route(
                {
                    "book_id": book_id,
                    "chapter_id": chapter_id or None,
                    "proposal_id": f"fixwizard:{fid}",
                    "operator_note": str((body or {}).get("operator_note") or "fixwizard_execute"),
                    "actions": [{"type": action_type, "payload": action_payload}],
                },
                db=db,
            )
            applied_items = apply_out.get("applied") if isinstance(apply_out.get("applied"), list) else []
            audit_ids = [str(x.get("audit_id") or "") for x in applied_items if isinstance(x, dict) and str(x.get("audit_id") or "").strip()]
            if not audit_ids:
                # Fallback observability record only; no safe rollback without agent audit_id.
                state_audit_id = await _fixwizard_insert_state_audit(
                    db,
                    book_id=book_id,
                    volume_id=volume_id or None,
                    action_type="fixwizard_agent_apply_proxy_failed",
                    before_state={"fix_id": fid, "payload": payload},
                    after_state={"apply_out": apply_out},
                    diff={"status": "applied_without_agent_audit_id"},
                    reason=f"fixwizard execute {fid} (agent did not return audit_id)",
                )
                executed.append(
                    {
                        "fix_id": fid,
                        "type": ftype,
                        "status": "applied",
                        "action_type": action_type,
                        "audit_ids": [],
                        "state_audit_id": state_audit_id,
                        "rollback": {
                            "supported": False,
                            "kind": "agent_apply",
                            "audit_ids": [],
                            "reason": "agent_apply did not return audit_id",
                        },
                    }
                )
            else:
                # Use /agent/apply returned audit IDs as source of truth.
                executed.append(
                    {
                        "fix_id": fid,
                        "type": ftype,
                        "status": "applied",
                        "action_type": action_type,
                        "audit_ids": audit_ids,
                        "audit_id": audit_ids[0],
                        "rollback": {
                            "supported": True,
                            "kind": "agent_apply",
                            "audit_ids": audit_ids,
                        },
                    }
                )
        elif ftype == "plan_patch":
            mode = str(payload.get("mode") or "").strip()
            if mode != "boost_must_happen_priority":
                executed.append({"fix_id": fid, "type": ftype, "status": "skipped", "reason": "unsupported plan_patch mode"})
                continue
            delta = int(payload.get("delta") or 1)
            before_rows = await db.execute(
                text(
                    """
                    SELECT item_id::text AS item_id, priority
                    FROM volume_plan_item
                    WHERE vol_plan_id=(
                      SELECT vol_plan_id FROM volume_plan
                      WHERE book_id=CAST(:book_id AS uuid) AND volume_id=CAST(:volume_id AS uuid) AND status='active'
                      ORDER BY version DESC LIMIT 1
                    )
                      AND must_happen=true
                    ORDER BY priority DESC, item_id
                    """
                ),
                {"book_id": book_id, "volume_id": volume_id},
            )
            before_items = [dict(r) for r in before_rows.mappings().all()]
            await db.execute(
                text(
                    """
                    UPDATE volume_plan_item
                    SET priority = priority + :delta
                    WHERE vol_plan_id=(
                      SELECT vol_plan_id FROM volume_plan
                      WHERE book_id=CAST(:book_id AS uuid) AND volume_id=CAST(:volume_id AS uuid) AND status='active'
                      ORDER BY version DESC LIMIT 1
                    )
                      AND must_happen=true
                    """
                ),
                {"book_id": book_id, "volume_id": volume_id, "delta": delta},
            )
            after_rows = await db.execute(
                text(
                    """
                    SELECT item_id::text AS item_id, priority
                    FROM volume_plan_item
                    WHERE vol_plan_id=(
                      SELECT vol_plan_id FROM volume_plan
                      WHERE book_id=CAST(:book_id AS uuid) AND volume_id=CAST(:volume_id AS uuid) AND status='active'
                      ORDER BY version DESC LIMIT 1
                    )
                      AND must_happen=true
                    ORDER BY priority DESC, item_id
                    """
                ),
                {"book_id": book_id, "volume_id": volume_id},
            )
            after_items = [dict(r) for r in after_rows.mappings().all()]
            patch_ids: list[str] = []
            after_map = {str(r.get("item_id") or ""): int(r.get("priority") or 0) for r in after_items}
            for b in before_items:
                iid = str(b.get("item_id") or "")
                if not iid:
                    continue
                a_priority = int(after_map.get(iid, int(b.get("priority") or 0)))
                pid_row = await db.execute(
                    text(
                        """
                        INSERT INTO plan_patch_log(book_id, volume_id, item_id, before, after, reason)
                        VALUES (
                          CAST(:book_id AS uuid), CAST(:volume_id AS uuid), CAST(:item_id AS uuid),
                          CAST(:before AS jsonb), CAST(:after AS jsonb), :reason
                        )
                        RETURNING patch_id::text
                        """
                    ),
                    {
                        "book_id": book_id,
                        "volume_id": volume_id,
                        "item_id": iid,
                        "before": json.dumps({"priority": int(b.get("priority") or 0)}, ensure_ascii=False),
                        "after": json.dumps({"priority": a_priority}, ensure_ascii=False),
                        "reason": f"fixwizard {fid}",
                    },
                )
                patch_ids.append(str(pid_row.scalar_one()))

            state_audit_id = await _fixwizard_insert_state_audit(
                db,
                book_id=book_id,
                volume_id=volume_id or None,
                action_type="fixwizard_plan_patch",
                before_state={"fix_id": fid, "mode": mode, "before": before_items},
                after_state={"after": after_items, "patch_ids": patch_ids},
                diff={"delta": delta, "affected": len(before_items)},
                reason=f"fixwizard execute {fid}",
            )
            executed.append(
                {
                    "fix_id": fid,
                    "type": ftype,
                    "status": "applied",
                    "result": {"mode": mode, "delta": delta, "affected": len(before_items)},
                    "state_audit_id": state_audit_id,
                    "rollback": {"supported": True, "kind": "plan_patch", "patch_ids": patch_ids},
                }
            )
        elif ftype == "plan_autobuild":
            auto_body: dict = {"book_id": book_id, "volume_id": volume_id}
            if chapter_id:
                auto_body["chapter_id"] = chapter_id
            auto_body = _merge_dict(auto_body, payload if isinstance(payload, dict) else {})
            auto_out = await plan_autobuild_route(auto_body, db=db)
            state_audit_id = await _fixwizard_insert_state_audit(
                db,
                book_id=book_id,
                volume_id=volume_id or None,
                action_type="fixwizard_plan_autobuild",
                before_state={"fix_id": fid, "payload": payload},
                after_state={"result": auto_out},
                diff={"ok": bool(auto_out.get("ok"))},
                reason=f"fixwizard execute {fid}",
            )
            executed.append(
                {
                    "fix_id": fid,
                    "type": ftype,
                    "status": "applied",
                    "result": {"ok": bool(auto_out.get("ok")), "route": auto_out.get("route")},
                    "state_audit_id": state_audit_id,
                    "rollback": {"supported": False, "kind": "noop"},
                }
            )
        elif ftype == "rewrite_suggest":
            state_audit_id = await _fixwizard_insert_state_audit(
                db,
                book_id=book_id,
                volume_id=volume_id or None,
                action_type="fixwizard_rewrite_suggest",
                before_state={"fix_id": fid},
                after_state={"payload": payload},
                diff={"status": "suggested"},
                reason=f"fixwizard execute {fid}",
            )
            executed.append(
                {
                    "fix_id": fid,
                    "type": ftype,
                    "status": "suggested",
                    "payload": payload,
                    "state_audit_id": state_audit_id,
                    "rollback": {"supported": False, "kind": "noop"},
                }
            )
        else:
            executed.append({"fix_id": fid, "type": ftype, "status": "skipped", "reason": "unsupported fix type"})

    recheck_report = None
    recheck_delta = None
    if bool((body or {}).get("auto_recheck", True)):
        vr_row = await db.execute(
            text("SELECT volume_no FROM volume WHERE volume_id=CAST(:volume_id AS uuid) AND book_id=CAST(:book_id AS uuid) LIMIT 1"),
            {"book_id": book_id, "volume_id": volume_id},
        )
        vr = vr_row.mappings().first()
        if vr:
            recheck_report = await _run_preflight_for_volume(
                db,
                book_id=book_id,
                volume_id=volume_id,
                volume_no=int(vr.get("volume_no") or 1),
            )
            before_summary = body.get("preflight_summary") if isinstance(body.get("preflight_summary"), dict) else {}
            recheck_delta = _fixwizard_summary_delta(before_summary, recheck_report.get("summary") if isinstance(recheck_report, dict) else {})

    chain_row = await db.execute(
        text(
            """
            INSERT INTO fix_chain(book_id, volume_id, pack_name, preflight_snapshot, executed, status)
            VALUES (
              CAST(:book_id AS uuid), CAST(:volume_id AS uuid), :pack_name,
              CAST(:preflight_snapshot AS jsonb), CAST(:executed AS jsonb), 'applied'
            )
            RETURNING chain_id::text
            """
        ),
        {
            "book_id": book_id,
            "volume_id": volume_id,
            "pack_name": pack_name,
            "preflight_snapshot": json.dumps(preflight_snapshot or {}, ensure_ascii=False),
            "executed": json.dumps(executed, ensure_ascii=False),
        },
    )
    chain_id = str(chain_row.scalar_one())
    chain_state_audit_id = await _fixwizard_insert_state_audit(
        db,
        book_id=book_id,
        volume_id=volume_id or None,
        action_type="fixwizard_chain",
        before_state={},
        after_state={"chain_id": chain_id, "executed_count": len(executed)},
        diff={"executed": [{"fix_id": x.get("fix_id"), "status": x.get("status")} for x in executed]},
        reason="fixwizard chain created",
    )
    await db.commit()
    return {
        "ok": True,
        "book_id": book_id,
        "volume_id": volume_id,
        "chain_id": chain_id,
        "chain_state_audit_id": chain_state_audit_id,
        "executed": executed,
        "recheck": recheck_report,
        "recheck_delta": recheck_delta,
    }


@app.post("/v1/fixwizard/rollback_chain")
async def fixwizard_rollback_chain_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    chain_id = str((body or {}).get("chain_id") or "").strip()
    if not chain_id:
        raise HTTPException(status_code=400, detail="chain_id required")
    await _ensure_fixwizard_tables(db)
    row = await db.execute(
        text(
            """
            SELECT chain_id::text AS chain_id, book_id::text AS book_id, volume_id::text AS volume_id,
                   executed, status, rolled_back_at
            FROM fix_chain
            WHERE chain_id=CAST(:chain_id AS uuid)
            LIMIT 1
            """
        ),
        {"chain_id": chain_id},
    )
    ch = row.mappings().first()
    if not ch:
        raise HTTPException(status_code=404, detail="FIX_CHAIN_NOT_FOUND")
    if ch.get("rolled_back_at"):
        return {"ok": True, "chain_id": chain_id, "already_rolled_back": True}

    book_id = str(ch.get("book_id") or "")
    volume_id = str(ch.get("volume_id") or "") or None
    executed = ch.get("executed") if isinstance(ch.get("executed"), list) else []
    rollback_items: list[dict] = []

    for step in reversed(executed):
        if not isinstance(step, dict):
            continue
        fix_id = str(step.get("fix_id") or "")
        rb = step.get("rollback") if isinstance(step.get("rollback"), dict) else {}
        if not rb.get("supported"):
            rollback_items.append({"fix_id": fix_id, "status": "skipped", "reason": "rollback unsupported"})
            continue
        kind = str(rb.get("kind") or "").strip().lower()
        if kind == "plan_patch":
            patch_ids = rb.get("patch_ids") if isinstance(rb.get("patch_ids"), list) else []
            restored = 0
            for pid in patch_ids:
                pid_str = str(pid or "").strip()
                if not pid_str:
                    continue
                prow = await db.execute(
                    text(
                        """
                        SELECT item_id::text AS item_id, before
                        FROM plan_patch_log
                        WHERE patch_id=CAST(:patch_id AS uuid)
                        LIMIT 1
                        """
                    ),
                    {"patch_id": pid_str},
                )
                p = prow.mappings().first()
                if not p:
                    continue
                before = p.get("before") if isinstance(p.get("before"), dict) else {}
                if "priority" not in before:
                    continue
                await db.execute(
                    text("UPDATE volume_plan_item SET priority=:priority WHERE item_id=CAST(:item_id AS uuid)"),
                    {"item_id": str(p.get("item_id") or ""), "priority": int(before.get("priority") or 0)},
                )
                restored += 1
            state_audit_id = await _fixwizard_insert_state_audit(
                db,
                book_id=book_id,
                volume_id=volume_id,
                action_type="fixwizard_rollback_plan_patch",
                before_state={"fix_id": fix_id, "patch_ids": patch_ids},
                after_state={"restored": restored},
                diff={"restored": restored},
                reason=f"fixwizard rollback chain {chain_id}",
            )
            rollback_items.append({"fix_id": fix_id, "status": "rolled_back", "kind": kind, "restored": restored, "state_audit_id": state_audit_id})
        elif kind == "agent_apply":
            audit_ids = rb.get("audit_ids") if isinstance(rb.get("audit_ids"), list) else []
            agent_results: list[dict] = []
            for aid in audit_ids:
                aid_str = str(aid or "").strip()
                if not aid_str:
                    continue
                out = await agent_rollback_route(
                    {"book_id": book_id, "audit_id": aid_str, "reason": f"fixwizard rollback chain {chain_id}"},
                    db=db,
                )
                agent_results.append({"audit_id": aid_str, "result": out})
            state_audit_id = await _fixwizard_insert_state_audit(
                db,
                book_id=book_id,
                volume_id=volume_id,
                action_type="fixwizard_rollback_agent_apply",
                before_state={"fix_id": fix_id, "audit_ids": audit_ids},
                after_state={"agent_results": agent_results},
                diff={"rolled_back_count": len(agent_results)},
                reason=f"fixwizard rollback chain {chain_id}",
            )
            rollback_items.append(
                {
                    "fix_id": fix_id,
                    "status": "rolled_back",
                    "kind": kind,
                    "agent_rollback_count": len(agent_results),
                    "state_audit_id": state_audit_id,
                }
            )
        else:
            rollback_items.append({"fix_id": fix_id, "status": "skipped", "reason": f"unknown rollback kind: {kind}"})

    await db.execute(
        text(
            """
            UPDATE fix_chain
            SET status='rolled_back', rolled_back_at=now()
            WHERE chain_id=CAST(:chain_id AS uuid)
            """
        ),
        {"chain_id": chain_id},
    )
    chain_state_audit_id = await _fixwizard_insert_state_audit(
        db,
        book_id=book_id,
        volume_id=volume_id,
        action_type="fixwizard_chain_rollback",
        before_state={"chain_id": chain_id},
        after_state={"rollback_items": rollback_items},
        diff={"rolled_back_items": len(rollback_items)},
        reason="fixwizard rollback chain",
    )
    await db.commit()
    return {"ok": True, "chain_id": chain_id, "rollback": rollback_items, "chain_state_audit_id": chain_state_audit_id}


@app.post("/v1/fixwizard/rollback_last")
async def fixwizard_rollback_last_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    book_id = str((body or {}).get("book_id") or "").strip()
    volume_id = str((body or {}).get("volume_id") or "").strip()
    if not book_id:
        raise HTTPException(status_code=400, detail="book_id required")
    await _ensure_fixwizard_tables(db)
    if volume_id:
        row = await db.execute(
            text(
                """
                SELECT chain_id::text AS chain_id
                FROM fix_chain
                WHERE book_id=CAST(:book_id AS uuid) AND volume_id=CAST(:volume_id AS uuid)
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"book_id": book_id, "volume_id": volume_id},
        )
    else:
        row = await db.execute(
            text(
                """
                SELECT chain_id::text AS chain_id
                FROM fix_chain
                WHERE book_id=CAST(:book_id AS uuid)
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"book_id": book_id},
        )
    hit = row.mappings().first()
    if not hit:
        raise HTTPException(status_code=404, detail="FIX_CHAIN_NOT_FOUND")
    return await fixwizard_rollback_chain_route({"chain_id": str(hit.get("chain_id") or "")}, db=db)


@app.post("/v1/fixwizard/chains")
async def fixwizard_chains_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    book_id = str((body or {}).get("book_id") or "").strip()
    volume_id = str((body or {}).get("volume_id") or "").strip()
    limit_raw = (body or {}).get("limit", 20)
    try:
        limit = int(limit_raw)
    except Exception:
        limit = 20
    limit = max(1, min(limit, 200))
    if not book_id:
        raise HTTPException(status_code=400, detail="book_id required")
    await _ensure_fixwizard_tables(db)
    if volume_id:
        rows = await db.execute(
            text(
                """
                SELECT chain_id::text AS chain_id, book_id::text AS book_id, volume_id::text AS volume_id,
                       pack_name, preflight_snapshot, executed, status, rolled_back_at, created_at
                FROM fix_chain
                WHERE book_id=CAST(:book_id AS uuid) AND volume_id=CAST(:volume_id AS uuid)
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"book_id": book_id, "volume_id": volume_id, "limit": limit},
        )
    else:
        rows = await db.execute(
            text(
                """
                SELECT chain_id::text AS chain_id, book_id::text AS book_id, volume_id::text AS volume_id,
                       pack_name, preflight_snapshot, executed, status, rolled_back_at, created_at
                FROM fix_chain
                WHERE book_id=CAST(:book_id AS uuid)
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"book_id": book_id, "limit": limit},
        )
    items: list[dict] = []
    for r in rows.mappings().all():
        d = dict(r)
        executed = d.get("executed") if isinstance(d.get("executed"), list) else []
        d["executed_count"] = len(executed)
        d["ok_count"] = len([x for x in executed if isinstance(x, dict) and str(x.get("status") or "").lower() in {"applied", "suggested"}])
        d["has_rollbackable"] = any(
            isinstance(x, dict) and isinstance(x.get("rollback"), dict) and bool(x.get("rollback", {}).get("supported"))
            for x in executed
        )
        items.append(d)
    return {"ok": True, "book_id": book_id, "volume_id": volume_id or None, "items": items}


@app.post("/v1/fixwizard/recheck")
async def fixwizard_recheck_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    book_id = str((body or {}).get("book_id") or "").strip()
    volume_id = str((body or {}).get("volume_id") or "").strip()
    if not book_id or not volume_id:
        raise HTTPException(status_code=400, detail="book_id and volume_id required")
    row = await db.execute(
        text("SELECT volume_no FROM volume WHERE volume_id=CAST(:volume_id AS uuid) AND book_id=CAST(:book_id AS uuid) LIMIT 1"),
        {"book_id": book_id, "volume_id": volume_id},
    )
    vr = row.mappings().first()
    if not vr:
        raise HTTPException(status_code=404, detail="VOLUME_NOT_FOUND")
    report = await _run_preflight_for_volume(
        db,
        book_id=book_id,
        volume_id=volume_id,
        volume_no=int(vr.get("volume_no") or 1),
    )
    before_summary = body.get("before_summary") if isinstance(body.get("before_summary"), dict) else {}
    return {
        "ok": True,
        "book_id": book_id,
        "volume_id": volume_id,
        "report": report,
        "delta": _fixwizard_summary_delta(before_summary, report.get("summary") if isinstance(report, dict) else {}),
    }


@app.post("/v1/export/logs")
async def export_logs_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_export_tables(db)
    book_id = str((body or {}).get("book_id") or "").strip()
    volume_id = str((body or {}).get("volume_id") or "").strip()
    limit_raw = (body or {}).get("limit", 30)
    try:
        limit = int(limit_raw)
    except Exception:
        limit = 30
    limit = max(1, min(limit, 200))
    if not book_id:
        raise HTTPException(status_code=400, detail="book_id required")
    if volume_id:
        rows = await db.execute(
            text(
                """
                SELECT export_id::text AS export_id, book_id::text AS book_id, volume_id::text AS volume_id,
                       pack_name, output_dir, manifest, created_at
                FROM export_log
                WHERE book_id=CAST(:book_id AS uuid) AND volume_id=CAST(:volume_id AS uuid)
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"book_id": book_id, "volume_id": volume_id, "limit": limit},
        )
    else:
        rows = await db.execute(
            text(
                """
                SELECT export_id::text AS export_id, book_id::text AS book_id, volume_id::text AS volume_id,
                       pack_name, output_dir, manifest, created_at
                FROM export_log
                WHERE book_id=CAST(:book_id AS uuid)
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"book_id": book_id, "limit": limit},
        )
    items: list[dict] = []
    for r in rows.mappings().all():
        d = dict(r)
        manifest = d.get("manifest") if isinstance(d.get("manifest"), dict) else {}
        d["files_count"] = len(manifest.get("files") or []) if isinstance(manifest, dict) else 0
        items.append(d)
    return {"ok": True, "book_id": book_id, "volume_id": volume_id or None, "items": items}


@app.post("/v1/export/logs/cleanup_missing")
async def export_logs_cleanup_missing_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_export_tables(db)
    book_id = str((body or {}).get("book_id") or "").strip()
    volume_id = str((body or {}).get("volume_id") or "").strip()
    dry_run = bool((body or {}).get("dry_run", True))
    export_ids_raw = (body or {}).get("export_ids")
    export_ids_filter: set[str] | None = None
    if isinstance(export_ids_raw, list):
        export_ids_filter = {str(x or "").strip() for x in export_ids_raw if str(x or "").strip()}
    if not book_id:
        raise HTTPException(status_code=400, detail="book_id required")
    if volume_id:
        rows = await db.execute(
            text(
                """
                SELECT export_id::text AS export_id, output_dir, pack_name, created_at
                FROM export_log
                WHERE book_id=CAST(:book_id AS uuid) AND volume_id=CAST(:volume_id AS uuid)
                ORDER BY created_at DESC
                """
            ),
            {"book_id": book_id, "volume_id": volume_id},
        )
    else:
        rows = await db.execute(
            text(
                """
                SELECT export_id::text AS export_id, output_dir, pack_name, created_at
                FROM export_log
                WHERE book_id=CAST(:book_id AS uuid)
                ORDER BY created_at DESC
                """
            ),
            {"book_id": book_id},
        )
    source_rows = rows.mappings().all()
    missing: list[dict] = []
    for r in source_rows:
        d = dict(r)
        xid = str(d.get("export_id") or "").strip()
        if export_ids_filter is not None and xid not in export_ids_filter:
            continue
        p = Path(str(d.get("output_dir") or "")).expanduser()
        if not p.exists():
            missing.append(
                {
                    "export_id": xid,
                    "output_dir": str(d.get("output_dir") or ""),
                    "pack_name": str(d.get("pack_name") or ""),
                    "created_at": d.get("created_at"),
                }
            )
    deleted = 0
    if (not dry_run) and missing:
        ids = [m["export_id"] for m in missing if m.get("export_id")]
        if ids:
            for xid in ids:
                await db.execute(
                    text("DELETE FROM export_log WHERE export_id=CAST(:export_id AS uuid)"),
                    {"export_id": xid},
                )
            await db.commit()
            deleted = len(ids)
    return {
        "ok": True,
        "book_id": book_id,
        "volume_id": volume_id or None,
        "dry_run": dry_run,
        "filter_export_ids_count": len(export_ids_filter or []),
        "missing_count": len(missing),
        "deleted_count": deleted,
        "items": missing,
    }


@app.post("/v1/export/rebuild")
async def export_rebuild_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_export_tables(db)
    export_id = str((body or {}).get("export_id") or "").strip()
    if not export_id:
        raise HTTPException(status_code=400, detail="export_id required")
    row = await db.execute(
        text(
            """
            SELECT export_id::text AS export_id, book_id::text AS book_id, volume_id::text AS volume_id, pack_name
            FROM export_log
            WHERE export_id=CAST(:export_id AS uuid)
            LIMIT 1
            """
        ),
        {"export_id": export_id},
    )
    hit = row.mappings().first()
    if not hit:
        raise HTTPException(status_code=404, detail="EXPORT_LOG_NOT_FOUND")
    pack_name = str((body or {}).get("pack_name") or "").strip() or str(hit.get("pack_name") or "").strip()
    if not pack_name:
        pack_name = f"publish_pack_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    out = await export_publish_pack_route(
        {
            "book_id": str(hit.get("book_id") or ""),
            "volume_id": str(hit.get("volume_id") or ""),
            "pack_name": pack_name,
        },
        db,
    )
    return {"ok": True, "source_export_id": export_id, "rebuild": out}


@app.get("/v1/workflows/definitions/{workflow_id}")
async def workflow_definition_route(workflow_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_workflow_tables(db)
    try:
        return _workflow_get_definition(workflow_id)
    except RuntimeError as exc:
        if str(exc) == "WORKFLOW_NOT_FOUND":
            raise HTTPException(status_code=404, detail="WORKFLOW_NOT_FOUND") from exc
        raise


@app.post("/v1/workflows/run")
async def workflow_run_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_workflow_tables(db)
    workflow_id = str(body.get("workflow_id") or "draft_runner_v1").strip() or "draft_runner_v1"
    dry_run = bool(body.get("dry_run", True))
    reuse_if_exists = bool(body.get("reuse_if_exists", True))
    input_ctx = body.get("input") if isinstance(body.get("input"), dict) else {}
    if not isinstance(input_ctx, dict):
        raise HTTPException(status_code=400, detail="input must be object")
    try:
        definition = _workflow_get_definition(workflow_id)
    except RuntimeError as exc:
        if str(exc) == "WORKFLOW_NOT_FOUND":
            raise HTTPException(status_code=404, detail="WORKFLOW_NOT_FOUND") from exc
        raise
    idem = str(body.get("idempotency_key") or "").strip()
    if not idem:
        idem = _workflow_make_idempotency_key(
            workflow_id,
            int(definition.get("version") or 1),
            input_ctx,
            dry_run,
        )
    result = await _workflow_execute_run(
        db=db,
        workflow_id=workflow_id,
        definition=definition,
        input_ctx=input_ctx,
        idempotency_key=idem,
        dry_run=dry_run,
        reuse_if_exists=reuse_if_exists,
    )
    return result


@app.get("/v1/workflows/runs/{run_id}")
async def workflow_run_get_route(run_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_workflow_tables(db)
    row = await db.execute(
        text(
            """
            SELECT run_id::text AS run_id, workflow_id, workflow_version, book_id::text AS book_id, chapter_id::text AS chapter_id,
                   idempotency_key, status, started_at, ended_at, error, ctx_snapshot, meta
            FROM workflow_run
            WHERE run_id=CAST(:run_id AS uuid)
            LIMIT 1
            """
        ),
        {"run_id": str(run_id)},
    )
    run = row.mappings().first()
    if not run:
        raise HTTPException(status_code=404, detail="WORKFLOW_RUN_NOT_FOUND")
    steps = await db.execute(
        text(
            """
            SELECT step_id::text AS step_id, run_id::text AS run_id, node_id, node_type, attempt, status, started_at, ended_at, input, output, metrics, error
            FROM workflow_step
            WHERE run_id=CAST(:run_id AS uuid)
            ORDER BY started_at, node_id
            """
        ),
        {"run_id": str(run_id)},
    )
    return {
        "run": dict(run),
        "steps": [dict(r) for r in steps.mappings().all()],
    }


@app.post("/v1/workflows/runs/{run_id}/rollback")
async def workflow_run_rollback_route(run_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_workflow_tables(db)
    reason = str(body.get("reason") or "").strip() or f"rollback run {run_id}"
    run_row = await db.execute(
        text("SELECT run_id::text AS run_id, book_id::text AS book_id, chapter_id::text AS chapter_id FROM workflow_run WHERE run_id=CAST(:run_id AS uuid) LIMIT 1"),
        {"run_id": str(run_id)},
    )
    run = run_row.mappings().first()
    if not run:
        raise HTTPException(status_code=404, detail="WORKFLOW_RUN_NOT_FOUND")
    audit_row = await db.execute(
        text(
            """
            SELECT audit_id::text AS audit_id, before_state, after_state
            FROM state_apply_audit
            WHERE run_id=CAST(:run_id AS uuid) AND action_type='draft_commit'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"run_id": str(run_id)},
    )
    audit = audit_row.mappings().first()
    if not audit:
        return {"ok": True, "run_id": str(run_id), "rolled_back": False, "reason": "NO_AUDIT"}
    after_state = audit.get("after_state") if isinstance(audit.get("after_state"), dict) else {}
    text_ver_id = str(after_state.get("created_text_ver_id") or "").strip()
    draft_id = str(after_state.get("created_draft_id") or "").strip()
    trace_id = str(after_state.get("created_trace_id") or "").strip()
    report_id = str(after_state.get("created_report_id") or "").strip()
    usage_id = str(after_state.get("created_asset_usage_id") or "").strip()
    sel_trace_id = str(after_state.get("created_asset_selection_trace_id") or "").strip()
    deleted_any = False
    current_source = ""
    if text_ver_id:
        current_row = await db.execute(
            text(
                """
                SELECT text_ver_id::text AS text_ver_id, chapter_id::text AS chapter_id, source, created_at
                FROM chapter_text_version
                WHERE text_ver_id=CAST(:text_ver_id AS uuid)
                LIMIT 1
                """
            ),
            {"text_ver_id": text_ver_id},
        )
        current = current_row.mappings().first()
        if current:
            current_source = str(current.get("source") or "")
            await db.execute(
                text("DELETE FROM chapter_text_version WHERE text_ver_id=CAST(:text_ver_id AS uuid)"),
                {"text_ver_id": text_ver_id},
            )
            deleted_any = True
    if draft_id:
        await db.execute(text("DELETE FROM chapter_draft WHERE draft_id=CAST(:id AS uuid)"), {"id": draft_id})
        deleted_any = True
    if trace_id:
        await db.execute(text("DELETE FROM chapter_trace WHERE trace_id=CAST(:id AS uuid)"), {"id": trace_id})
        deleted_any = True
    if report_id:
        await db.execute(text("DELETE FROM chapter_report WHERE report_id=CAST(:id AS uuid)"), {"id": report_id})
        deleted_any = True
    if usage_id:
        await db.execute(text("DELETE FROM asset_usage_log WHERE usage_id=CAST(:id AS uuid)"), {"id": usage_id})
        deleted_any = True
    if sel_trace_id:
        await db.execute(text("DELETE FROM asset_selection_trace WHERE trace_id=CAST(:id AS uuid)"), {"id": sel_trace_id})
        deleted_any = True
    if not deleted_any:
        # Fallback by run_id for older/newer commit paths.
        d1 = await db.execute(text("DELETE FROM chapter_draft WHERE run_id=CAST(:rid AS uuid)"), {"rid": str(run_id)})
        d2 = await db.execute(text("DELETE FROM chapter_trace WHERE run_id=CAST(:rid AS uuid)"), {"rid": str(run_id)})
        d3 = await db.execute(text("DELETE FROM chapter_report WHERE run_id=CAST(:rid AS uuid)"), {"rid": str(run_id)})
        if (getattr(d1, "rowcount", 0) or 0) + (getattr(d2, "rowcount", 0) or 0) + (getattr(d3, "rowcount", 0) or 0) > 0:
            deleted_any = True
        d4 = await db.execute(text("DELETE FROM asset_usage_log WHERE text_ver_id=CAST(:tv AS uuid)"), {"tv": text_ver_id}) if text_ver_id else None
        d5 = await db.execute(text("DELETE FROM asset_selection_trace WHERE text_ver_id=CAST(:tv AS uuid)"), {"tv": text_ver_id}) if text_ver_id else None
        if ((getattr(d4, "rowcount", 0) if d4 is not None else 0) or 0) + ((getattr(d5, "rowcount", 0) if d5 is not None else 0) or 0) > 0:
            deleted_any = True
    if not deleted_any:
        return {"ok": True, "run_id": str(run_id), "rolled_back": False, "reason": "NOTHING_TO_ROLLBACK"}
    ins = await db.execute(
        text(
            """
            INSERT INTO state_apply_audit(book_id, chapter_id, run_id, action_type, before_state, after_state, diff, reason)
            VALUES(
              CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), CAST(:run_id AS uuid), 'workflow_rollback',
              CAST(:before_state AS jsonb), CAST(:after_state AS jsonb), CAST(:diff AS jsonb), :reason
            )
            RETURNING audit_id::text AS audit_id
            """
        ),
        {
            "book_id": str(run.get("book_id") or ""),
            "chapter_id": str(run.get("chapter_id") or ""),
            "run_id": str(run_id),
            "before_state": json.dumps(
                {
                    "deleted_text_ver_id": text_ver_id,
                    "deleted_draft_id": draft_id,
                    "deleted_trace_id": trace_id,
                    "deleted_report_id": report_id,
                    "deleted_asset_usage_id": usage_id,
                    "deleted_asset_selection_trace_id": sel_trace_id,
                    "source": current_source,
                },
                ensure_ascii=False,
            ),
            "after_state": json.dumps({"deleted": True}, ensure_ascii=False),
            "diff": json.dumps(
                [
                    {"op": "remove", "path": "/chapter_text_version", "value": text_ver_id},
                    {"op": "remove", "path": "/chapter_draft", "value": draft_id},
                    {"op": "remove", "path": "/chapter_trace", "value": trace_id},
                    {"op": "remove", "path": "/chapter_report", "value": report_id},
                    {"op": "remove", "path": "/asset_usage_log", "value": usage_id},
                    {"op": "remove", "path": "/asset_selection_trace", "value": sel_trace_id},
                ],
                ensure_ascii=False,
            ),
            "reason": reason,
        },
    )
    await db.commit()
    return {
        "ok": True,
        "run_id": str(run_id),
        "rolled_back": True,
        "text_ver_id": text_ver_id,
        "draft_id": draft_id,
        "trace_id": trace_id,
        "report_id": report_id,
        "asset_usage_id": usage_id,
        "asset_selection_trace_id": sel_trace_id,
        "rollback_audit_id": str((ins.mappings().first() or {}).get("audit_id") or ""),
    }


@app.get("/v1/ab_batch/{batch_id}")
async def ab_batch_get_route(batch_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.execute(
        text(
            """
            SELECT batch_id, book_id, chapter_id, status, created_at, finished_at, note, score_cfg,
                   winner_bundle_id, intent_snapshot, volume_id, volume_plan_id, volume_plan_version
            FROM ab_batch_run
            WHERE batch_id=:batch_id
            """
        ),
        {"batch_id": str(batch_id)},
    )
    b = row.mappings().first()
    if not b:
        raise HTTPException(status_code=404, detail="AB_BATCH_NOT_FOUND")
    items_res = await db.execute(
        text(
            """
            SELECT profile_id, profile_version, variant, assets_injection, status, text_ver_id, report_id, eval_overall, simguard_max, score, error, started_at, finished_at
            FROM ab_batch_item
            WHERE batch_id=:batch_id
            ORDER BY started_at NULLS FIRST, profile_id, variant
            """
        ),
        {"batch_id": str(batch_id)},
    )
    items = [dict(r) for r in items_res.mappings().all()]
    text_ids = [str(it.get("text_ver_id")) for it in items if it.get("text_ver_id")]
    injected_map: dict[str, dict] = {}
    if text_ids:
        meta_res = await db.execute(
            text(
                """
                SELECT text_ver_id::text AS text_ver_id, meta
                FROM chapter_text_version
                WHERE text_ver_id = ANY(CAST(:ids AS uuid[]))
                """
            ),
            {"ids": text_ids},
        )
        for mr in meta_res.mappings().all():
            m = mr.get("meta") if isinstance(mr.get("meta"), dict) else {}
            injected_map[str(mr.get("text_ver_id"))] = {
                "injected_bundle_id": str(m.get("injected_bundle_id") or "") if m.get("injected_bundle_id") else None,
                "injected_counts": m.get("injected_counts") if isinstance(m.get("injected_counts"), dict) else None,
            }
    cfg = b.get("score_cfg") if isinstance(b.get("score_cfg"), dict) else {}
    penalty = float(cfg.get("penalty") or 0.8)
    ranking = []
    for it in items:
        if str(it.get("variant") or "exp") != "exp":
            continue
        if it.get("score") is not None:
            score = round(float(it.get("score") or 0.0), 4)
        else:
            ev = float(it.get("eval_overall") or 0.0)
            sm = float(it.get("simguard_max") or 0.0)
            score = round(ev - (sm * penalty), 4)
        ranking.append({"profile_id": str(it.get("profile_id")), "score": score, "report_id": str(it.get("report_id")) if it.get("report_id") else None, "text_ver_id": str(it.get("text_ver_id")) if it.get("text_ver_id") else None})
    ranking.sort(key=lambda x: x["score"], reverse=True)
    by_pid: dict[str, dict[str, dict]] = {}
    for it in items:
        pid = str(it.get("profile_id") or "")
        if not pid:
            continue
        by_pid.setdefault(pid, {})[str(it.get("variant") or "exp")] = it
    delta_ranking: list[dict] = []
    combo_delta_ranking: list[dict] = []
    for pid, pair in by_pid.items():
        exp = pair.get("exp")
        base = pair.get("baseline")
        if not exp or not base:
            pass
        else:
            if exp.get("status") == "done" and base.get("status") == "done" and exp.get("score") is not None and base.get("score") is not None:
                exp_score = float(exp.get("score") or 0.0)
                base_score = float(base.get("score") or 0.0)
                delta_ranking.append(
                    {
                        "profile_id": pid,
                        "baseline_score": base_score,
                        "exp_score": exp_score,
                        "delta": round(exp_score - base_score, 4),
                        "baseline_text_ver_id": str(base.get("text_ver_id")) if base.get("text_ver_id") else None,
                        "exp_text_ver_id": str(exp.get("text_ver_id")) if exp.get("text_ver_id") else None,
                    }
                )
        combo_base = pair.get("combo_baseline")
        if exp and combo_base and exp.get("status") == "done" and combo_base.get("status") == "done" and exp.get("score") is not None and combo_base.get("score") is not None:
            exp_score = float(exp.get("score") or 0.0)
            combo_base_score = float(combo_base.get("score") or 0.0)
            combo_delta_ranking.append(
                {
                    "profile_id": pid,
                    "combo_baseline_score": combo_base_score,
                    "exp_score": exp_score,
                    "delta": round(exp_score - combo_base_score, 4),
                    "combo_baseline_text_ver_id": str(combo_base.get("text_ver_id")) if combo_base.get("text_ver_id") else None,
                    "exp_text_ver_id": str(exp.get("text_ver_id")) if exp.get("text_ver_id") else None,
                }
            )
    delta_ranking.sort(key=lambda x: float(x.get("delta") or 0.0), reverse=True)
    combo_delta_ranking.sort(key=lambda x: float(x.get("delta") or 0.0), reverse=True)
    return {
        "batch_id": str(b["batch_id"]),
        "book_id": str(b["book_id"]),
        "chapter_id": str(b["chapter_id"]),
        "status": str(b["status"]),
        "created_at": b.get("created_at"),
        "finished_at": b.get("finished_at"),
        "score_cfg": {"penalty": penalty},
        "intent_snapshot": b.get("intent_snapshot") if isinstance(b.get("intent_snapshot"), dict) else {},
        "volume_id": str(b.get("volume_id")) if b.get("volume_id") else None,
        "volume_plan_id": str(b.get("volume_plan_id")) if b.get("volume_plan_id") else None,
        "volume_plan_version": int(b.get("volume_plan_version")) if b.get("volume_plan_version") is not None else None,
        "winner_bundle_id": str(b.get("winner_bundle_id")) if b.get("winner_bundle_id") else None,
        "items": [
            {
                **it,
                "profile_id": str(it.get("profile_id")),
                "variant": str(it.get("variant") or "exp"),
                "assets_injection": bool(it.get("assets_injection", True)),
                "text_ver_id": str(it.get("text_ver_id")) if it.get("text_ver_id") else None,
                "report_id": str(it.get("report_id")) if it.get("report_id") else None,
                "eval_overall": float(it.get("eval_overall")) if it.get("eval_overall") is not None else None,
                "simguard_max": float(it.get("simguard_max")) if it.get("simguard_max") is not None else None,
                "score": float(it.get("score")) if it.get("score") is not None else None,
                "injected_bundle_id": (injected_map.get(str(it.get("text_ver_id"))) or {}).get("injected_bundle_id") if it.get("text_ver_id") else None,
                "injected_counts": (injected_map.get(str(it.get("text_ver_id"))) or {}).get("injected_counts") if it.get("text_ver_id") else None,
            }
            for it in items
        ],
        "ranking": ranking,
        "delta_ranking": delta_ranking,
        "combo_delta_ranking": combo_delta_ranking,
    }


@app.post("/v1/ab_batch/{batch_id}/retry_failed")
async def ab_batch_retry_failed_route(batch_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.execute(
        text("SELECT batch_id, chapter_id FROM ab_batch_run WHERE batch_id=:batch_id"),
        {"batch_id": str(batch_id)},
    )
    b = row.mappings().first()
    if not b:
        raise HTTPException(status_code=404, detail="AB_BATCH_NOT_FOUND")
    failed_res = await db.execute(
        text("SELECT profile_id::text AS profile_id FROM ab_batch_item WHERE batch_id=:batch_id AND status='failed'"),
        {"batch_id": str(batch_id)},
    )
    failed_ids = [str(r["profile_id"]) for r in failed_res.mappings().all()]
    if not failed_ids:
        return {"ok": True, "batch_id": str(batch_id), "new_batch_id": None, "retried_profiles": 0}

    # keep old batch immutable; create a new retry batch with failed profiles only
    retry_out = await ab_batch_run_route(
        chapter_id=UUID(str(b["chapter_id"])),
        body={
            "note": f"retry_failed from {batch_id}",
            "profiles": "custom",
            "profile_ids": failed_ids,
            "do_eval": True,
            "do_simguard": True,
        },
        db=db,
    )
    return {
        "ok": True,
        "batch_id": str(batch_id),
        "new_batch_id": retry_out.get("batch_id"),
        "retried_profiles": len(failed_ids),
    }


def _deep_merge_local(base: dict, override: dict) -> dict:
    out = dict(base or {})
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge_local(out[k], v)
        else:
            out[k] = v
    return out


async def _promote_batch(
    db: AsyncSession,
    *,
    batch_id: str,
    strategy: str,
    note: str,
    sim_limit: float,
    settings_cfg: dict | None = None,
    assets_cfg: dict | None = None,
) -> dict:
    run_res = await db.execute(
        text(
            """
            SELECT batch_id, book_id, chapter_id, status, settings_snapshot
            FROM ab_batch_run
            WHERE batch_id=:batch_id
            """
        ),
        {"batch_id": batch_id},
    )
    run = run_res.mappings().first()
    if not run:
        raise HTTPException(status_code=404, detail="AB_BATCH_NOT_FOUND")
    if str(run.get("status") or "") != "done":
        raise HTTPException(status_code=409, detail="BATCH_NOT_DONE")

    items_res = await db.execute(
        text(
            """
            SELECT profile_id, profile_version, variant, status, score, simguard_max, report_id, text_ver_id
            FROM ab_batch_item
            WHERE batch_id=:batch_id
            """
        ),
        {"batch_id": batch_id},
    )
    done_items: list[dict] = []
    for r in items_res.mappings().all():
        if str(r.get("variant") or "exp") != "exp":
            continue
        if str(r.get("status") or "") != "done":
            continue
        if r.get("score") is None:
            continue
        done_items.append(
            {
                "profile_id": str(r.get("profile_id")),
                "profile_version": int(r.get("profile_version") or 1),
                "score": float(r.get("score") or 0.0),
                "simguard_max": float(r.get("simguard_max")) if r.get("simguard_max") is not None else None,
                "report_id": str(r.get("report_id")) if r.get("report_id") else None,
                "text_ver_id": str(r.get("text_ver_id")) if r.get("text_ver_id") else None,
            }
        )
    if not done_items:
        raise HTTPException(status_code=409, detail="NO_DONE_ITEMS")
    done_items.sort(key=lambda x: x["score"], reverse=True)
    winner = done_items[0]

    if winner.get("simguard_max") is not None and float(winner["simguard_max"]) > sim_limit:
        raise HTTPException(status_code=409, detail="WINNER_SIM_TOO_HIGH")

    in_book_res = await db.execute(
        text(
            """
            SELECT 1
            FROM book b
            LEFT JOIN book_profile_link l
              ON l.book_id=b.book_id AND l.profile_id=CAST(:profile_id AS uuid)
            WHERE b.book_id=:book_id
              AND (b.profile_id=CAST(:profile_id AS uuid) OR l.profile_id IS NOT NULL)
            LIMIT 1
            """
        ),
        {"book_id": str(run["book_id"]), "profile_id": winner["profile_id"]},
    )
    if not in_book_res.first():
        raise HTTPException(status_code=409, detail="WINNER_NOT_IN_BOOK")

    result: dict[str, object] = {
        "ok": True,
        "strategy": strategy,
        "book_id": str(run["book_id"]),
        "chapter_id": str(run["chapter_id"]),
        "winner": {
            "profile_id": winner["profile_id"],
            "profile_version": int(winner["profile_version"]),
            "score": float(winner["score"]),
            "report_id": winner.get("report_id"),
            "text_ver_id": winner.get("text_ver_id"),
        },
    }

    if strategy in ("profile", "profile_plus_settings"):
        old_main_res = await db.execute(
            text("SELECT profile_id FROM book WHERE book_id=:book_id"),
            {"book_id": str(run["book_id"])},
        )
        old_main = old_main_res.scalar()
        await db.execute(
            text("UPDATE book SET profile_id=CAST(:profile_id AS uuid) WHERE book_id=:book_id"),
            {"book_id": str(run["book_id"]), "profile_id": winner["profile_id"]},
        )
        await db.execute(
            text(
                """
                INSERT INTO book_profile_link(book_id, profile_id, role)
                VALUES (:book_id, CAST(:profile_id AS uuid), 'main')
                ON CONFLICT (book_id, profile_id) DO UPDATE SET role='main'
                """
            ),
            {"book_id": str(run["book_id"]), "profile_id": winner["profile_id"]},
        )
        await db.execute(
            text(
                """
                UPDATE book_profile_link
                SET role='experiment'
                WHERE book_id=:book_id
                  AND role='main'
                  AND profile_id<>CAST(:profile_id AS uuid)
                """
            ),
            {"book_id": str(run["book_id"]), "profile_id": winner["profile_id"]},
        )
        await db.execute(
            text(
                """
                INSERT INTO book_profile_audit_log(
                  book_id, action, batch_id, old_main_profile_id, new_main_profile_id, score, note
                )
                VALUES (
                  :book_id, 'promote_winner', :batch_id,
                  CAST(:old_main AS uuid), CAST(:new_main AS uuid), :score, :note
                )
                """
            ),
            {
                "book_id": str(run["book_id"]),
                "batch_id": batch_id,
                "old_main": str(old_main) if old_main else None,
                "new_main": winner["profile_id"],
                "score": float(winner["score"]),
                "note": note or "promote winner from ab_batch",
            },
        )
        result["profile_result"] = {
            "old_main_profile_id": str(old_main) if old_main else None,
            "new_main_profile_id": winner["profile_id"],
        }

    if strategy == "version":
        main_res = await db.execute(text("SELECT profile_id FROM book WHERE book_id=:book_id"), {"book_id": str(run["book_id"])})
        main_val = main_res.scalar()
        main_pid = str(main_val) if main_val else None
        if not main_pid:
            raise HTTPException(status_code=409, detail="BOOK_HAS_NO_MAIN_PROFILE")
        if main_pid != winner["profile_id"]:
            raise HTTPException(status_code=409, detail="WINNER_NOT_MAIN_PROFILE")

        cur_res = await db.execute(
            text("SELECT active_version FROM profile WHERE profile_id=CAST(:profile_id AS uuid) FOR UPDATE"),
            {"profile_id": main_pid},
        )
        cur_v = int(cur_res.scalar() or 1)
        snap_res = await db.execute(
            text(
                """
                SELECT snapshot
                FROM profile_version
                WHERE profile_id=CAST(:profile_id AS uuid) AND version=:version
                """
            ),
            {"profile_id": main_pid, "version": int(winner["profile_version"])},
        )
        snap = snap_res.scalar()
        if not isinstance(snap, dict):
            raise HTTPException(status_code=409, detail="WINNER_PROFILE_VERSION_NOT_FOUND")
        new_v = int(cur_v) + 1
        await db.execute(
            text(
                """
                INSERT INTO profile_version(
                  profile_id, version, snapshot, actor, action, note, parent_version, source_text_ver_ids
                )
                VALUES (
                  CAST(:profile_id AS uuid), :version, CAST(:snapshot AS jsonb),
                  'desktop_user', 'promote', :note, :parent_version, '[]'::jsonb
                )
                """
            ),
            {
                "profile_id": main_pid,
                "version": new_v,
                "snapshot": json.dumps(snap, ensure_ascii=False),
                "note": f"promote winner v{int(winner['profile_version'])} from batch {batch_id}",
                "parent_version": cur_v,
            },
        )
        await db.execute(
            text("UPDATE profile SET active_version=:version, updated_at=now() WHERE profile_id=CAST(:profile_id AS uuid)"),
            {"profile_id": main_pid, "version": new_v},
        )
        result["version_result"] = {"profile_id": main_pid, "from_version": cur_v, "to_version": new_v}

    if strategy == "profile_plus_settings":
        s_cfg = settings_cfg or {}
        apply_flag = bool(s_cfg.get("apply", True))
        if apply_flag:
            snap = run.get("settings_snapshot") if isinstance(run.get("settings_snapshot"), dict) else {}
            mode = str(s_cfg.get("mode") or "merge").lower()
            if mode not in ("merge", "replace"):
                mode = "merge"
            base_preset_name = str(s_cfg.get("preset_name") or f"AUTO: batch-{str(batch_id)[:8]} winner").strip()
            preset_name = f"{base_preset_name}-{datetime.now(timezone.utc).strftime('%H%M%S')}"
            preset_desc = str(s_cfg.get("preset_description") or f"auto preset from ab_batch {batch_id}")

            preset_row = await create_settings_preset(db, preset_name, preset_desc, snap if isinstance(snap, dict) else {})
            preset_id = str(preset_row.get("preset_id"))

            before = await get_book_settings(db, str(run["book_id"])) or {}
            after = snap if mode == "replace" else _deep_merge_local(before, snap if isinstance(snap, dict) else {})
            await db.execute(
                text(
                    """
                    INSERT INTO book_settings(book_id, settings, updated_at)
                    VALUES (:book_id, CAST(:settings AS jsonb), now())
                    ON CONFLICT (book_id)
                    DO UPDATE SET settings=EXCLUDED.settings, updated_at=now()
                    """
                ),
                {"book_id": str(run["book_id"]), "settings": json.dumps(after, ensure_ascii=False)},
            )
            await db.execute(
                text(
                    """
                    INSERT INTO settings_audit_log(
                      actor, action, scope, scope_id, preset_id, mode, before_settings, after_settings, note
                    )
                    VALUES (
                      'desktop_user', 'preset_apply', 'book', CAST(:book_id AS uuid),
                      CAST(:preset_id AS uuid), :mode,
                      CAST(:before_settings AS jsonb), CAST(:after_settings AS jsonb), :note
                    )
                    """
                ),
                {
                    "book_id": str(run["book_id"]),
                    "preset_id": preset_id,
                    "mode": mode,
                    "before_settings": json.dumps(before, ensure_ascii=False),
                    "after_settings": json.dumps(after, ensure_ascii=False),
                    "note": f"from promote batch {batch_id}",
                },
            )
            result["settings_result"] = {"preset_id": preset_id, "applied_scope": "book", "mode": mode}

        a_cfg = assets_cfg or {}
        assets_apply = bool(a_cfg.get("apply", True))
        assets_policy = str(a_cfg.get("policy") or "auto_default").lower()
        if assets_apply and assets_policy != "none":
            winner_bundle_id = str(run.get("winner_bundle_id")) if run.get("winner_bundle_id") else None
            if not winner_bundle_id and winner.get("text_ver_id"):
                out = await _extract_assets_internal(
                    db,
                    text_ver_id=str(winner["text_ver_id"]),
                    batch_id=batch_id,
                    mode="safe",
                    max_cards=12,
                    max_templates=6,
                )
                winner_bundle_id = str(out.get("bundle_id") or "")
            if winner_bundle_id:
                bres = await db.execute(
                    text("SELECT status, risk_score FROM asset_bundle WHERE bundle_id=CAST(:bundle_id AS uuid)"),
                    {"bundle_id": winner_bundle_id},
                )
                brow = bres.mappings().first()
                bstatus = str(brow.get("status") or "") if brow else ""
                brisk = float(brow.get("risk_score")) if brow and brow.get("risk_score") is not None else 0.0
                if assets_policy == "auto_default" and bstatus == "ready" and brisk < 0.25:
                    await db.execute(
                        text(
                            """
                            INSERT INTO book_default_assets(book_id, bundle_id, updated_at)
                            VALUES (CAST(:book_id AS uuid), CAST(:bundle_id AS uuid), now())
                            ON CONFLICT (book_id)
                            DO UPDATE SET bundle_id=EXCLUDED.bundle_id, updated_at=now()
                            """
                        ),
                        {"book_id": str(run["book_id"]), "bundle_id": winner_bundle_id},
                    )
                    result["assets_result"] = {"bundle_id": winner_bundle_id, "applied_scope": "book", "policy": assets_policy}
                else:
                    result["assets_result"] = {
                        "bundle_id": winner_bundle_id,
                        "applied_scope": None,
                        "policy": assets_policy,
                        "status": bstatus,
                        "risk_score": brisk,
                    }

    await db.commit()
    return result


async def _generate_asset_policy_proposals(db: AsyncSession, *, book_id: str) -> dict:
    uses_14d_res = await db.execute(
        text(
            """
            WITH used AS (
              SELECT 'material'::text AS item_type, unnest(injected_material_ids) AS item_id
              FROM asset_usage_log
              WHERE book_id=CAST(:book_id AS uuid)
                AND assets_injection=true
                AND created_at > now() - interval '14 days'
              UNION ALL
              SELECT 'template'::text AS item_type, unnest(injected_template_ids) AS item_id
              FROM asset_usage_log
              WHERE book_id=CAST(:book_id AS uuid)
                AND assets_injection=true
                AND created_at > now() - interval '14 days'
              UNION ALL
              SELECT 'structure_template'::text AS item_type, unnest(used_structure_template_ids) AS item_id
              FROM asset_usage_log
              WHERE book_id=CAST(:book_id AS uuid)
                AND created_at > now() - interval '14 days'
              UNION ALL
              SELECT 'structure_combo'::text AS item_type, unnest(used_combo_ids) AS item_id
              FROM asset_usage_log
              WHERE book_id=CAST(:book_id AS uuid)
                AND created_at > now() - interval '14 days'
            )
            SELECT item_type, item_id::text AS item_id, count(*)::int AS uses_14d
            FROM used
            GROUP BY item_type, item_id
            """
        ),
        {"book_id": book_id},
    )
    uses_14d_map: dict[tuple[str, str], int] = {}
    for r in uses_14d_res.mappings().all():
        uses_14d_map[(str(r.get("item_type") or ""), str(r.get("item_id") or ""))] = int(r.get("uses_14d") or 0)

    stats_res = await db.execute(
        text(
            """
            SELECT item_type, item_id::text AS item_id, uses, wins, losses, avg_delta
            FROM asset_score_stat
            WHERE book_id=CAST(:book_id AS uuid) AND uses >= 6
            """
        ),
        {"book_id": book_id},
    )
    stats = [dict(r) for r in stats_res.mappings().all()]
    created = 0
    for s in stats:
        item_type = str(s.get("item_type") or "")
        item_id = str(s.get("item_id") or "")
        uses = int(s.get("uses") or 0)
        wins = int(s.get("wins") or 0)
        losses = int(s.get("losses") or 0)
        avg_delta = float(s.get("avg_delta") or 0.0)
        total = wins + losses
        if total < 6:
            continue
        uses_14d = int(uses_14d_map.get((item_type, item_id)) or 0)
        win_rate = float(wins) / float(total) if total > 0 else 0.0
        loss_rate = float(losses) / float(total) if total > 0 else 0.0
        expected_gain = avg_delta * float(uses_14d)

        policy = "normal"
        risk = 0.0
        if item_type == "material":
            ir = await db.execute(
                text("SELECT policy, COALESCE(risk_score,0)::float AS risk FROM material_card WHERE card_id=CAST(:id AS uuid)"),
                {"id": item_id},
            )
            rr = ir.mappings().first()
            if not rr:
                continue
            policy = str(rr.get("policy") or "normal").lower()
            risk = float(rr.get("risk") or 0.0)
        elif item_type == "template":
            ir = await db.execute(
                text("SELECT policy, COALESCE(risk_score,0)::float AS risk FROM prompt_template WHERE template_id=CAST(:id AS uuid)"),
                {"id": item_id},
            )
            rr = ir.mappings().first()
            if not rr:
                continue
            policy = str(rr.get("policy") or "normal").lower()
            risk = float(rr.get("risk") or 0.0)
        elif item_type == "structure_template":
            ir = await db.execute(
                text("SELECT policy, COALESCE(risk_score,0)::float AS risk FROM structure_template WHERE template_id=CAST(:id AS uuid)"),
                {"id": item_id},
            )
            rr = ir.mappings().first()
            if not rr:
                continue
            policy = str(rr.get("policy") or "normal").lower()
            risk = float(rr.get("risk") or 0.0)
        elif item_type == "structure_combo":
            ir = await db.execute(
                text("SELECT policy, COALESCE(risk_score,0)::float AS risk FROM structure_combo WHERE combo_id=CAST(:id AS uuid)"),
                {"id": item_id},
            )
            rr = ir.mappings().first()
            if not rr:
                continue
            policy = str(rr.get("policy") or "normal").lower()
            risk = float(rr.get("risk") or 0.0)
        else:
            continue

        if policy in {"pinned", "banned"}:
            continue

        proposed: str | None = None
        reason = ""
        if risk >= 0.25:
            proposed = "banned"
            reason = "High risk score"
        elif avg_delta <= -0.03 and loss_rate >= 0.65:
            proposed = "banned"
            reason = "Stable negative delta"
        elif risk < 0.20 and avg_delta >= 0.04 and win_rate >= 0.65 and expected_gain >= 0.20:
            proposed = "pinned"
            reason = "Stable positive delta"

        if not proposed:
            continue

        expected_risk = risk + (math.log(1 + max(0, uses_14d)) * 0.05)
        evidence = {
            "uses": uses,
            "uses_14d": uses_14d,
            "avg_delta": avg_delta,
            "win_rate": round(win_rate, 6),
            "loss_rate": round(loss_rate, 6),
            "risk": round(risk, 6),
            "expected_gain": round(expected_gain, 6),
            "expected_risk": round(expected_risk, 6),
        }
        ins = await db.execute(
            text(
                """
                INSERT INTO asset_policy_proposal(
                  book_id, item_type, item_id, proposed_policy, status, reason, evidence
                )
                VALUES (
                  CAST(:book_id AS uuid), :item_type, CAST(:item_id AS uuid), :proposed_policy, 'pending', :reason, CAST(:evidence AS jsonb)
                )
                ON CONFLICT DO NOTHING
                RETURNING proposal_id
                """
            ),
            {
                "book_id": book_id,
                "item_type": item_type,
                "item_id": item_id,
                "proposed_policy": proposed,
                "reason": reason,
                "evidence": json.dumps(evidence, ensure_ascii=False),
            },
        )
        if ins.scalar() is not None:
            created += 1
    await db.commit()
    return {"created": created}


async def _structure_combo_stats(db: AsyncSession, *, book_id: str, limit: int = 100) -> dict:
    uses_14d_res = await db.execute(
        text(
            """
            WITH used AS (
              SELECT unnest(used_combo_ids) AS combo_id
              FROM asset_usage_log
              WHERE book_id=CAST(:book_id AS uuid)
                AND created_at > now() - interval '14 days'
            )
            SELECT combo_id::text AS combo_id, count(*)::int AS uses_14d
            FROM used
            GROUP BY combo_id
            """
        ),
        {"book_id": book_id},
    )
    uses_14d_map: dict[str, int] = {str(r.get("combo_id") or ""): int(r.get("uses_14d") or 0) for r in uses_14d_res.mappings().all()}

    rows = await db.execute(
        text(
            """
            SELECT
              c.combo_id::text AS combo_id,
              c.combo_type,
              c.fingerprint,
              c.policy,
              COALESCE(c.risk_score,0)::float AS risk_score,
              c.rotation_group,
              c.last_used_volume_no,
              COALESCE(s.uses,0)::int AS uses,
              COALESCE(s.wins,0)::int AS wins,
              COALESCE(s.losses,0)::int AS losses,
              COALESCE(s.avg_delta,0)::float AS avg_delta,
              COALESCE(s.weight,0)::float AS weight
            FROM structure_combo c
            LEFT JOIN asset_score_stat s
              ON s.item_type='structure_combo' AND s.item_id=c.combo_id AND s.book_id=CAST(:book_id AS uuid)
            WHERE c.book_id=CAST(:book_id AS uuid)
            ORDER BY c.created_at DESC
            LIMIT :limit
            """
        ),
        {"book_id": book_id, "limit": int(limit)},
    )
    items: list[dict] = []
    by_type: dict[str, list[dict]] = {}
    for r in rows.mappings().all():
        x = dict(r)
        cid = str(x.get("combo_id") or "")
        uses_14d = int(uses_14d_map.get(cid) or 0)
        avg_delta = float(x.get("avg_delta") or 0.0)
        risk = float(x.get("risk_score") or 0.0)
        expected_gain = avg_delta * float(uses_14d)
        expected_risk = risk + math.log(1 + max(0, uses_14d)) * 0.05
        out = {
            "combo_id": cid,
            "combo_type": str(x.get("combo_type") or ""),
            "fingerprint": str(x.get("fingerprint") or ""),
            "policy": str(x.get("policy") or "normal"),
            "rotation_group": str(x.get("rotation_group") or ""),
            "last_used_volume_no": x.get("last_used_volume_no"),
            "uses": int(x.get("uses") or 0),
            "wins": int(x.get("wins") or 0),
            "losses": int(x.get("losses") or 0),
            "avg_delta": round(avg_delta, 6),
            "weight": round(float(x.get("weight") or 0.0), 6),
            "risk_score": round(risk, 6),
            "uses_14d": uses_14d,
            "expected_gain": round(expected_gain, 6),
            "expected_risk": round(expected_risk, 6),
        }
        items.append(out)
        by_type.setdefault(out["combo_type"], []).append(out)
    items.sort(key=lambda z: float(z.get("expected_gain") or 0.0), reverse=True)
    for k in list(by_type.keys()):
        by_type[k].sort(key=lambda z: float(z.get("expected_gain") or 0.0), reverse=True)
    return {"items": items, "by_type": by_type}


async def _item_meta_for_evidence(db: AsyncSession, *, item_type: str, item_id: str) -> dict | None:
    if item_type == "material":
        res = await db.execute(
            text(
                """
                SELECT card_id::text AS item_id, title, policy, COALESCE(risk_score,0)::float AS risk_score, fingerprint, extract_meta
                FROM material_card
                WHERE card_id=CAST(:item_id AS uuid)
                """
            ),
            {"item_id": item_id},
        )
        r = res.mappings().first()
        if not r:
            return None
        return {
            "item_type": "material",
            "item_id": str(r["item_id"]),
            "title": str(r.get("title") or ""),
            "policy": str(r.get("policy") or "normal"),
            "risk_score": float(r.get("risk_score") or 0.0),
            "fingerprint": str(r.get("fingerprint") or ""),
            "extract_meta": r.get("extract_meta") if isinstance(r.get("extract_meta"), dict) else {},
        }
    if item_type == "template":
        res = await db.execute(
            text(
                """
                SELECT template_id::text AS item_id, name AS title, policy, COALESCE(risk_score,0)::float AS risk_score, fingerprint, extract_meta
                FROM prompt_template
                WHERE template_id=CAST(:item_id AS uuid)
                """
            ),
            {"item_id": item_id},
        )
        r = res.mappings().first()
        if not r:
            return None
        return {
            "item_type": "template",
            "item_id": str(r["item_id"]),
            "title": str(r.get("title") or ""),
            "policy": str(r.get("policy") or "normal"),
            "risk_score": float(r.get("risk_score") or 0.0),
            "fingerprint": str(r.get("fingerprint") or ""),
            "extract_meta": r.get("extract_meta") if isinstance(r.get("extract_meta"), dict) else {},
        }
    if item_type == "structure_template":
        res = await db.execute(
            text(
                """
                SELECT template_id::text AS item_id, name AS title, policy, COALESCE(risk_score,0)::float AS risk_score, fingerprint, source_meta
                FROM structure_template
                WHERE template_id=CAST(:item_id AS uuid)
                """
            ),
            {"item_id": item_id},
        )
        r = res.mappings().first()
        if not r:
            return None
        return {
            "item_type": "structure_template",
            "item_id": str(r["item_id"]),
            "title": str(r.get("title") or ""),
            "policy": str(r.get("policy") or "normal"),
            "risk_score": float(r.get("risk_score") or 0.0),
            "fingerprint": str(r.get("fingerprint") or ""),
            "extract_meta": r.get("source_meta") if isinstance(r.get("source_meta"), dict) else {},
        }
    if item_type == "structure_combo":
        res = await db.execute(
            text(
                """
                SELECT combo_id::text AS item_id, combo_type AS title, policy, COALESCE(risk_score,0)::float AS risk_score, fingerprint, meta
                FROM structure_combo
                WHERE combo_id=CAST(:item_id AS uuid)
                """
            ),
            {"item_id": item_id},
        )
        r = res.mappings().first()
        if not r:
            return None
        return {
            "item_type": "structure_combo",
            "item_id": str(r["item_id"]),
            "title": str(r.get("title") or ""),
            "policy": str(r.get("policy") or "normal"),
            "risk_score": float(r.get("risk_score") or 0.0),
            "fingerprint": str(r.get("fingerprint") or ""),
            "extract_meta": r.get("meta") if isinstance(r.get("meta"), dict) else {},
        }
    return None


def _extract_item_from_trace(trace: dict, *, item_type: str, item_id: str) -> dict:
    sel = trace.get("selection") if isinstance(trace.get("selection"), dict) else {}
    key = "templates" if item_type == "template" else "hooks"
    top_rows = []
    filtered_rows = []
    picked = []
    for k in ("hooks", "beats", "styles", "templates"):
        sec = sel.get(k) if isinstance(sel.get(k), dict) else {}
        if item_type == "template" and k != "templates":
            continue
        top_rows.extend(sec.get("top") if isinstance(sec.get("top"), list) else [])
        filtered_rows.extend(sec.get("filtered") if isinstance(sec.get("filtered"), list) else [])
        picked.extend(sec.get("picked") if isinstance(sec.get("picked"), list) else [])
    rank = None
    breakdown = {}
    filtered_reason = None
    for i, row in enumerate(top_rows, start=1):
        if str(row.get("id") or "") == item_id:
            rank = i
            breakdown = row.get("breakdown") if isinstance(row.get("breakdown"), dict) else {}
            break
    for row in filtered_rows:
        if str(row.get("id") or "") == item_id:
            filtered_reason = str(row.get("reason") or "")
            break
    return {
        "rank": rank,
        "breakdown": breakdown,
        "filtered_reason": filtered_reason,
        "picked": item_id in [str(x) for x in picked],
    }


def _diagnose_samples(samples: list[dict], *, item_type: str, item_id: str) -> dict:
    valid = [s for s in samples if s.get("delta") is not None]
    if not valid:
        return {
            "summary": "No comparable baseline samples.",
            "signals": [],
            "recommendation": "keep_normal",
            "confidence": 0.5,
        }
    deltas = [float(s.get("delta") or 0.0) for s in valid]
    avg_delta = sum(deltas) / len(deltas)
    pos = sum(1 for x in deltas if x > 0.03)
    neg = sum(1 for x in deltas if x < -0.02)
    signals: list[dict] = []
    mismatch_neg = 0
    cooldown_pressure = 0
    duplicate_hits = 0
    for s in valid:
        br = s.get("breakdown") if isinstance(s.get("breakdown"), dict) else {}
        delta = float(s.get("delta") or 0.0)
        if int(br.get("tag_overlap") or 0) == 0 and delta < 0:
            mismatch_neg += 1
        if int(br.get("cooldown_count") or 0) >= 2:
            cooldown_pressure += 1
        if str(s.get("filtered_reason") or "") == "fingerprint_duplicate":
            duplicate_hits += 1
    if mismatch_neg > 0:
        signals.append({"type": "tag_mismatch", "detail": f"{mismatch_neg} sample(s) had zero tag overlap and negative delta."})
    if cooldown_pressure > 0:
        signals.append({"type": "cooldown_pressure", "detail": f"{cooldown_pressure} sample(s) had high cooldown_count."})
    if duplicate_hits > 0:
        signals.append({"type": "fingerprint_duplicate", "detail": f"{duplicate_hits} sample(s) were filtered by fingerprint dedupe."})
    if pos >= 2:
        rec = "pin"
    elif neg >= 2:
        rec = "ban"
    else:
        rec = "keep_normal"
    consistency = max(pos, neg) / max(1, len(valid))
    confidence = min(0.95, 0.55 + 0.15 * abs(avg_delta) + 0.10 * consistency)
    summary = f"avg_delta={round(avg_delta, 4)} over {len(valid)} sample(s)."
    return {
        "summary": summary,
        "signals": signals,
        "recommendation": rec,
        "confidence": round(confidence, 4),
    }


async def _learn_context_tags_for_item(
    db: AsyncSession,
    *,
    book_id: str,
    item_type: str,
    item_id: str,
    limit: int = 30,
    min_samples: int = 6,
) -> dict:
    q = (
        """
        SELECT text_ver_id::text AS text_ver_id, batch_id::text AS batch_id, ctx_tags
        FROM asset_usage_log
        WHERE book_id=CAST(:book_id AS uuid)
          AND assets_injection=true
          AND CAST(:item_id AS uuid) = ANY(injected_material_ids)
        ORDER BY created_at DESC
        LIMIT :limit
        """
        if item_type == "material"
        else """
        SELECT text_ver_id::text AS text_ver_id, batch_id::text AS batch_id, ctx_tags
        FROM asset_usage_log
        WHERE book_id=CAST(:book_id AS uuid)
          AND assets_injection=true
          AND CAST(:item_id AS uuid) = ANY(injected_template_ids)
        ORDER BY created_at DESC
        LIMIT :limit
        """
    )
    rows = await db.execute(text(q), {"book_id": book_id, "item_id": item_id, "limit": max(1, min(limit, 100))})
    usage_rows = [dict(r) for r in rows.mappings().all()]
    min_need = max(3, min(int(min_samples), 20))
    if len(usage_rows) < min_need:
        return {"ok": False, "reason": "NOT_ENOUGH_USAGE"}
    samples: list[dict] = []
    for u in usage_rows:
        exp_row = await db.execute(
            text("SELECT batch_id, profile_id, score FROM ab_batch_item WHERE variant='exp' AND text_ver_id=CAST(:text_ver_id AS uuid) LIMIT 1"),
            {"text_ver_id": str(u.get("text_ver_id") or "")},
        )
        exp = exp_row.mappings().first()
        if not exp:
            continue
        base_row = await db.execute(
            text(
                """
                SELECT score
                FROM ab_batch_item
                WHERE batch_id=:batch_id AND profile_id=:profile_id AND variant='baseline' AND status='done'
                LIMIT 1
                """
            ),
            {"batch_id": str(exp.get("batch_id")), "profile_id": str(exp.get("profile_id"))},
        )
        base = base_row.mappings().first()
        if exp.get("score") is None or not base or base.get("score") is None:
            continue
        samples.append(
            {
                "delta": float(exp.get("score") or 0.0) - float(base.get("score") or 0.0),
                "tags": [str(x).strip().lower() for x in (u.get("ctx_tags") or []) if str(x).strip()],
            }
        )
    if len(samples) < min_need:
        return {"ok": False, "reason": "NOT_ENOUGH_DELTA_SAMPLES"}
    tag_stats: dict[str, dict] = {}
    for s in samples:
        for t in s["tags"]:
            rec = tag_stats.get(t) or {"n": 0, "sum_delta": 0.0}
            rec["n"] = int(rec["n"]) + 1
            rec["sum_delta"] = float(rec["sum_delta"]) + float(s["delta"])
            tag_stats[t] = rec
    stats_out: dict[str, dict] = {}
    good_new: list[str] = []
    bad_new: list[str] = []
    for t, rec in tag_stats.items():
        n = int(rec.get("n") or 0)
        avg = float(rec.get("sum_delta") or 0.0) / float(max(1, n))
        stats_out[t] = {"n": n, "avg_delta": round(avg, 6)}
        if n >= 3 and avg >= 0.03:
            good_new.append(t)
        if n >= 3 and avg <= -0.02:
            bad_new.append(t)
    meta = await _item_meta_for_evidence(db, item_type=item_type, item_id=item_id)
    if not meta:
        return {"ok": False, "reason": "ITEM_NOT_FOUND"}
    old_meta = meta.get("extract_meta") if isinstance(meta.get("extract_meta"), dict) else {}
    good_old = [str(x).strip().lower() for x in (old_meta.get("good_tags") or []) if str(x).strip()]
    bad_old = [str(x).strip().lower() for x in (old_meta.get("bad_tags") or []) if str(x).strip()]
    good = list(dict.fromkeys((good_new + good_old)))[:10]
    bad = list(dict.fromkeys((bad_new + bad_old)))[:10]
    gset = set(good)
    bset = set(bad)
    for t in list(gset):
        if t in bset:
            avg = float((stats_out.get(t) or {}).get("avg_delta") or 0.0)
            if avg >= 0:
                bset.discard(t)
            else:
                gset.discard(t)
    merged = dict(old_meta)
    merged["good_tags"] = sorted(gset)
    merged["bad_tags"] = sorted(bset)
    merged["tag_stats"] = stats_out
    merged["tag_sample_n"] = len(samples)
    merged["tag_learned_at"] = datetime.now(timezone.utc).isoformat()
    if item_type == "material":
        await db.execute(
            text("UPDATE material_card SET extract_meta=CAST(:meta AS jsonb) WHERE card_id=CAST(:item_id AS uuid)"),
            {"item_id": item_id, "meta": json.dumps(merged, ensure_ascii=False)},
        )
    else:
        await db.execute(
            text("UPDATE prompt_template SET extract_meta=CAST(:meta AS jsonb) WHERE template_id=CAST(:item_id AS uuid)"),
            {"item_id": item_id, "meta": json.dumps(merged, ensure_ascii=False)},
        )
    await db.commit()
    return {"ok": True, "good_tags": merged["good_tags"], "bad_tags": merged["bad_tags"], "samples": len(samples)}


@app.post("/v1/ab_batch/{batch_id}/promote")
async def ab_batch_promote_route(batch_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    strategy = str((body or {}).get("strategy") or "profile").strip().lower()
    if strategy not in ("profile", "version", "profile_plus_settings"):
        raise HTTPException(status_code=400, detail="INVALID_STRATEGY")
    note = str((body or {}).get("note") or "").strip()
    sim_limit_raw = (body or {}).get("simguard_limit")
    try:
        sim_limit = float(sim_limit_raw) if sim_limit_raw is not None else 0.25
    except Exception:
        sim_limit = 0.25
    sim_limit = max(0.0, min(1.0, sim_limit))
    return await _promote_batch(
        db,
        batch_id=str(batch_id),
        strategy=strategy,
        note=note,
        sim_limit=sim_limit,
        settings_cfg=((body or {}).get("settings") if isinstance((body or {}).get("settings"), dict) else None),
        assets_cfg=((body or {}).get("assets") if isinstance((body or {}).get("assets"), dict) else None),
    )


@app.post("/v1/ab_batch/{batch_id}/promote_winner")
async def ab_batch_promote_winner_route(batch_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    note = str((body or {}).get("note") or "").strip()
    sim_limit_raw = (body or {}).get("sim_limit")
    try:
        sim_limit = float(sim_limit_raw) if sim_limit_raw is not None else 0.25
    except Exception:
        sim_limit = 0.25
    sim_limit = max(0.0, min(1.0, sim_limit))
    out = await _promote_batch(
        db,
        batch_id=str(batch_id),
        strategy="profile",
        note=note,
        sim_limit=sim_limit,
        settings_cfg=None,
        assets_cfg=None,
    )
    profile_res = out.get("profile_result") if isinstance(out.get("profile_result"), dict) else {}
    winner = out.get("winner") if isinstance(out.get("winner"), dict) else {}
    return {
        "ok": bool(out.get("ok")),
        "book_id": out.get("book_id"),
        "chapter_id": out.get("chapter_id"),
        "old_main_profile_id": profile_res.get("old_main_profile_id"),
        "new_main_profile_id": profile_res.get("new_main_profile_id"),
        "score": winner.get("score"),
    }


@app.get("/v1/chapters/{chapter_id}/reports")
async def chapter_reports_list_route(
    chapter_id: UUID,
    limit: int = Query(default=50, ge=1, le=300),
    db: AsyncSession = Depends(get_db),
) -> dict:
    res = await db.execute(
        text(
            """
            SELECT report_id, report_type, profile_id_used, profile_version_used, payload, created_at
            FROM report
            WHERE chapter_id=:chapter_id
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"chapter_id": str(chapter_id), "limit": int(limit)},
    )
    items = []
    for r in res.mappings().all():
        payload = r.get("payload") or {}
        eval_summary = payload.get("eval_summary") if isinstance(payload.get("eval_summary"), dict) else {}
        sim_summary = payload.get("simguard_summary") if isinstance(payload.get("simguard_summary"), dict) else {}
        growth_task = payload.get("growth_task") if isinstance(payload.get("growth_task"), dict) else {}
        growth_check = payload.get("growth_check") if isinstance(payload.get("growth_check"), dict) else {}
        items.append(
            {
                "report_id": str(r["report_id"]),
                "report_type": str(r["report_type"]),
                "profile_id_used": str(r["profile_id_used"]) if r.get("profile_id_used") else payload.get("profile_id_used"),
                "profile_version_used": int(r["profile_version_used"]) if r.get("profile_version_used") is not None else payload.get("profile_version_used"),
                "text_ver_id": payload.get("text_ver_id"),
                "eval_summary": eval_summary,
                "simguard_summary": sim_summary,
                "growth_task": growth_task,
                "growth_check": growth_check,
                "created_at": r.get("created_at"),
            }
        )
    return {"chapter_id": str(chapter_id), "items": items}


@app.post("/v1/text_versions/{text_ver_id}/extract_assets")
async def extract_assets_route(text_ver_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    mode = str((body or {}).get("mode") or "safe").lower()
    if mode not in ("safe", "full"):
        mode = "safe"
    max_cards = int((body or {}).get("max_cards") or 12)
    max_templates = int((body or {}).get("max_templates") or 6)
    batch_id = str((body or {}).get("batch_id")) if (body or {}).get("batch_id") else None
    return await _extract_assets_internal(
        db,
        text_ver_id=str(text_ver_id),
        batch_id=batch_id,
        mode=mode,
        max_cards=max(1, min(max_cards, 24)),
        max_templates=max(1, min(max_templates, 12)),
    )


@app.get("/v1/extraction_runs/{run_id}")
async def extraction_run_get_route(run_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.execute(
        text(
            """
            SELECT run_id, kind, book_id, chapter_id, text_ver_id, batch_id, status, config, result_summary, error, created_at, finished_at
            FROM extraction_run
            WHERE run_id=CAST(:run_id AS uuid)
            """
        ),
        {"run_id": str(run_id)},
    )
    r = row.mappings().first()
    if not r:
        raise HTTPException(status_code=404, detail="EXTRACTION_RUN_NOT_FOUND")
    out = dict(r)
    out["run_id"] = str(r["run_id"])
    out["book_id"] = str(r["book_id"])
    out["chapter_id"] = str(r["chapter_id"]) if r.get("chapter_id") else None
    out["text_ver_id"] = str(r["text_ver_id"])
    out["batch_id"] = str(r["batch_id"]) if r.get("batch_id") else None
    return out


@app.post("/v1/extraction_runs/{run_id}/retry")
async def extraction_run_retry_route(run_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.execute(
        text(
            """
            SELECT run_id, text_ver_id, batch_id, config
            FROM extraction_run
            WHERE run_id=CAST(:run_id AS uuid)
            """
        ),
        {"run_id": str(run_id)},
    )
    r = row.mappings().first()
    if not r:
        raise HTTPException(status_code=404, detail="EXTRACTION_RUN_NOT_FOUND")
    cfg = r.get("config") if isinstance(r.get("config"), dict) else {}
    return await _extract_assets_internal(
        db,
        text_ver_id=str(r["text_ver_id"]),
        batch_id=str(r["batch_id"]) if r.get("batch_id") else None,
        mode=str(cfg.get("mode") or "safe"),
        max_cards=int(cfg.get("max_cards") or 12),
        max_templates=int(cfg.get("max_templates") or 6),
    )


@app.get("/v1/books/{book_id}/default_assets")
async def get_book_default_assets_route(book_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.execute(
        text(
            """
            SELECT b.bundle_id, a.status, a.risk_score, a.created_at
            FROM book_default_assets b
            JOIN asset_bundle a ON a.bundle_id=b.bundle_id
            WHERE b.book_id=CAST(:book_id AS uuid)
            """
        ),
        {"book_id": str(book_id)},
    )
    r = row.mappings().first()
    if not r:
        return {"book_id": str(book_id), "bundle_id": None}
    return {
        "book_id": str(book_id),
        "bundle_id": str(r["bundle_id"]),
        "status": str(r.get("status") or ""),
        "risk_score": float(r.get("risk_score")) if r.get("risk_score") is not None else None,
        "created_at": r.get("created_at"),
    }


@app.post("/v1/books/{book_id}/default_assets")
async def set_book_default_assets_route(book_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    bundle_id = str((body or {}).get("bundle_id") or "").strip()
    if not bundle_id:
        raise HTTPException(status_code=400, detail="BUNDLE_ID_REQUIRED")
    row = await db.execute(
        text("SELECT bundle_id FROM asset_bundle WHERE bundle_id=CAST(:bundle_id AS uuid) AND book_id=CAST(:book_id AS uuid)"),
        {"bundle_id": bundle_id, "book_id": str(book_id)},
    )
    if not row.first():
        raise HTTPException(status_code=404, detail="BUNDLE_NOT_FOUND")
    await db.execute(
        text(
            """
            INSERT INTO book_default_assets(book_id, bundle_id, updated_at)
            VALUES (CAST(:book_id AS uuid), CAST(:bundle_id AS uuid), now())
            ON CONFLICT (book_id)
            DO UPDATE SET bundle_id=EXCLUDED.bundle_id, updated_at=now()
            """
        ),
        {"book_id": str(book_id), "bundle_id": bundle_id},
    )
    await db.commit()
    return {"ok": True, "book_id": str(book_id), "bundle_id": bundle_id}


@app.post("/v1/ingest/structure_templates")
async def ingest_structure_templates_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    items = (body or {}).get("items") if isinstance((body or {}).get("items"), list) else []
    book_id_raw = str((body or {}).get("book_id") or "").strip()
    profile_id_raw = str((body or {}).get("profile_id") or "").strip()
    force = bool((body or {}).get("force", False))
    if not items:
        raise HTTPException(status_code=400, detail="ITEMS_REQUIRED")
    if not profile_id_raw and book_id_raw:
        row_prof = await db.execute(
            text("SELECT profile_id::text AS profile_id FROM book WHERE book_id=CAST(:book_id AS uuid)"),
            {"book_id": book_id_raw},
        )
        p = row_prof.mappings().first()
        profile_id_raw = str(p.get("profile_id") or "") if p else ""
    if not profile_id_raw:
        raise HTTPException(status_code=400, detail="PROFILE_ID_REQUIRED")

    created = 0
    skipped = 0
    banned = 0
    for raw in items[:500]:
        if not isinstance(raw, dict):
            continue
        st_type = str(raw.get("st_type") or raw.get("type") or "volume_plan").strip().lower()
        subtype = str(raw.get("subtype") or "").strip().lower()
        title = str(raw.get("title") or "")
        pattern = raw.get("pattern") if isinstance(raw.get("pattern"), dict) else {}
        slots = [str(x).strip() for x in (raw.get("slots") if isinstance(raw.get("slots"), list) else []) if str(x).strip()][:20]
        tags = [str(x).strip().lower() for x in (raw.get("tags") if isinstance(raw.get("tags"), list) else []) if str(x).strip()][:20]
        source_meta = raw.get("source_meta") if isinstance(raw.get("source_meta"), dict) else {}
        source_hash = str(source_meta.get("source_book_hash") or raw.get("source_book_hash") or "").strip()
        fp = _structure_pattern_fingerprint(st_type, subtype, pattern)
        risk = _structure_risk_score(pattern, slots)
        policy = str(raw.get("policy") or ("banned" if risk >= 0.35 else "normal")).strip().lower()
        if policy not in {"normal", "pinned", "banned"}:
            policy = "normal"
        if risk >= 0.35:
            policy = "banned"
        rotation_group = str(raw.get("rotation_group") or f"{st_type}:{subtype}:{fp[:12]}").strip()
        if not force:
            dup_row = await db.execute(
                text(
                    """
                    SELECT template_id
                    FROM structure_template
                    WHERE fingerprint=:fingerprint AND st_type=:st_type AND subtype=:subtype
                    LIMIT 1
                    """
                ),
                {"fingerprint": fp, "st_type": st_type, "subtype": subtype},
            )
            if dup_row.first():
                skipped += 1
                continue
        await db.execute(
            text(
                """
                INSERT INTO structure_template(
                  profile_id, name, level, tags, schema_ver, graph, meta,
                  st_type, subtype, pattern, slots, risk_score, policy, fingerprint, source_meta, source_book_hash, rotation_group
                )
                VALUES (
                  CAST(:profile_id AS uuid), :name, :level, CAST(:tags AS text[]), 1, CAST(:graph AS jsonb), CAST(:meta AS jsonb),
                  :st_type, :subtype, CAST(:pattern AS jsonb), CAST(:slots AS text[]), :risk_score, :policy, :fingerprint, CAST(:source_meta AS jsonb), :source_book_hash, :rotation_group
                )
                """
            ),
            {
                "profile_id": profile_id_raw,
                "name": title or f"{st_type}:{subtype}",
                "level": st_type,
                "tags": tags,
                "graph": json.dumps({"pattern": pattern, "slots": slots}, ensure_ascii=False),
                "meta": json.dumps({"ingested_from": "structure_templates", "book_id": book_id_raw}, ensure_ascii=False),
                "st_type": st_type,
                "subtype": subtype,
                "pattern": json.dumps(pattern, ensure_ascii=False),
                "slots": slots,
                "risk_score": risk,
                "policy": policy,
                "fingerprint": fp,
                "source_meta": json.dumps(source_meta, ensure_ascii=False),
                "source_book_hash": source_hash,
                "rotation_group": rotation_group,
            },
        )
        created += 1
        if policy == "banned":
            banned += 1
    await db.commit()
    return {"ok": True, "created": created, "skipped": skipped, "banned": banned}


@app.get("/v1/structure_templates")
async def structure_templates_list_route(
    st_type: str | None = Query(default=None),
    policy: str | None = Query(default=None),
    book_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = await db.execute(
        text(
            """
            SELECT
              template_id::text AS template_id, profile_id::text AS profile_id, name, st_type, subtype,
              tags, pattern, slots, COALESCE(risk_score,0)::float AS risk_score, policy, fingerprint,
              source_meta, source_book_hash, rotation_group, last_used_volume_no, created_at
            FROM structure_template
            WHERE (CAST(:st_type AS text) IS NULL OR st_type=CAST(:st_type AS text))
              AND (CAST(:policy AS text) IS NULL OR policy=CAST(:policy AS text))
              AND (
                CAST(:book_id AS text) IS NULL OR profile_id IN (
                  SELECT profile_id FROM book WHERE book_id=CAST(:book_id AS uuid)
                )
              )
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {
            "st_type": str(st_type).strip().lower() if st_type else None,
            "policy": str(policy).strip().lower() if policy else None,
            "book_id": str(book_id).strip() if book_id else None,
            "limit": int(limit),
        },
    )
    return {"items": [dict(r) for r in rows.mappings().all()]}


@app.post("/v1/structure_templates/{template_id}/policy")
async def structure_template_policy_set_route(template_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    policy = str((body or {}).get("policy") or "").strip().lower()
    if policy not in ("normal", "pinned", "banned"):
        raise HTTPException(status_code=400, detail="INVALID_POLICY")
    row = await db.execute(
        text(
            """
            UPDATE structure_template
            SET policy=:policy
            WHERE template_id=CAST(:template_id AS uuid)
            RETURNING template_id::text AS template_id
            """
        ),
        {"template_id": str(template_id), "policy": policy},
    )
    r = row.mappings().first()
    if not r:
        raise HTTPException(status_code=404, detail="STRUCTURE_TEMPLATE_NOT_FOUND")
    await db.commit()
    return {"ok": True, "template_id": str(r["template_id"]), "policy": policy}


@app.get("/v1/structure_combos")
async def structure_combos_list_route(
    combo_type: str | None = Query(default=None),
    policy: str | None = Query(default=None),
    book_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = await db.execute(
        text(
            """
            SELECT
              combo_id::text AS combo_id, book_id::text AS book_id, combo_type, fingerprint,
              pattern, tags, COALESCE(risk_score,0)::float AS risk_score, policy,
              rotation_group, last_used_volume_no, meta, created_at
            FROM structure_combo
            WHERE (CAST(:combo_type AS text) IS NULL OR combo_type=CAST(:combo_type AS text))
              AND (CAST(:policy AS text) IS NULL OR policy=CAST(:policy AS text))
              AND (CAST(:book_id AS text) IS NULL OR book_id=CAST(:book_id AS uuid))
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {
            "combo_type": str(combo_type).strip().lower() if combo_type else None,
            "policy": str(policy).strip().lower() if policy else None,
            "book_id": str(book_id).strip() if book_id else None,
            "limit": int(limit),
        },
    )
    return {"items": [dict(r) for r in rows.mappings().all()]}


@app.post("/v1/structure_combos/{combo_id}/policy")
async def structure_combo_policy_set_route(combo_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    policy = str((body or {}).get("policy") or "").strip().lower()
    if policy not in ("normal", "pinned", "banned"):
        raise HTTPException(status_code=400, detail="INVALID_POLICY")
    row = await db.execute(
        text(
            """
            UPDATE structure_combo
            SET policy=:policy
            WHERE combo_id=CAST(:combo_id AS uuid)
            RETURNING combo_id::text AS combo_id
            """
        ),
        {"combo_id": str(combo_id), "policy": policy},
    )
    r = row.mappings().first()
    if not r:
        raise HTTPException(status_code=404, detail="STRUCTURE_COMBO_NOT_FOUND")
    await db.commit()
    return {"ok": True, "combo_id": str(r["combo_id"]), "policy": policy}


@app.post("/v1/materials/{card_id}/policy")
async def material_policy_set_route(card_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    policy = str((body or {}).get("policy") or "").strip().lower()
    if policy not in ("normal", "pinned", "banned"):
        raise HTTPException(status_code=400, detail="INVALID_POLICY")
    row = await db.execute(
        text("UPDATE material_card SET policy=:policy WHERE card_id=CAST(:card_id AS uuid) RETURNING card_id::text AS card_id"),
        {"card_id": str(card_id), "policy": policy},
    )
    r = row.mappings().first()
    if not r:
        raise HTTPException(status_code=404, detail="MATERIAL_NOT_FOUND")
    await db.commit()
    return {"ok": True, "card_id": str(r["card_id"]), "policy": policy}


@app.post("/v1/prompt_templates/{template_id}/policy")
async def prompt_template_policy_set_route(template_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    policy = str((body or {}).get("policy") or "").strip().lower()
    if policy not in ("normal", "pinned", "banned"):
        raise HTTPException(status_code=400, detail="INVALID_POLICY")
    row = await db.execute(
        text("UPDATE prompt_template SET policy=:policy WHERE template_id=CAST(:template_id AS uuid) RETURNING template_id::text AS template_id"),
        {"template_id": str(template_id), "policy": policy},
    )
    r = row.mappings().first()
    if not r:
        raise HTTPException(status_code=404, detail="TEMPLATE_NOT_FOUND")
    await db.commit()
    return {"ok": True, "template_id": str(r["template_id"]), "policy": policy}


@app.post("/v1/books/{book_id}/assets/dedupe")
async def assets_dedupe_route(book_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    apply_ban = bool((body or {}).get("apply_ban", True))
    keep_n = max(1, min(5, int((body or {}).get("keep_n") or 1)))
    material_rows = await db.execute(
        text(
            """
            SELECT
              m.card_id::text AS item_id,
              m.tag,
              m.fingerprint,
              m.policy,
              m.created_at,
              COALESCE(s.weight, 0) AS weight
            FROM material_card m
            LEFT JOIN asset_score_stat s
              ON s.item_type='material' AND s.item_id=m.card_id AND s.book_id=CAST(:book_id AS uuid)
            WHERE m.book_id=CAST(:book_id AS uuid)
              AND m.fingerprint IS NOT NULL
              AND m.fingerprint<>''
              AND m.policy<>'banned'
            """
        ),
        {"book_id": str(book_id)},
    )
    template_rows = await db.execute(
        text(
            """
            SELECT
              t.template_id::text AS item_id,
              t.purpose AS tag,
              t.fingerprint,
              t.policy,
              t.created_at,
              COALESCE(s.weight, 0) AS weight
            FROM prompt_template t
            JOIN chapter_text_version tv ON tv.text_ver_id=t.source_text_ver_id
            JOIN chapter c ON c.chapter_id=tv.chapter_id
            LEFT JOIN asset_score_stat s
              ON s.item_type='template' AND s.item_id=t.template_id AND s.book_id=CAST(:book_id AS uuid)
            WHERE c.book_id=CAST(:book_id AS uuid)
              AND t.fingerprint IS NOT NULL
              AND t.fingerprint<>''
              AND t.policy<>'banned'
            """
        ),
        {"book_id": str(book_id)},
    )

    def _pick_duplicates(rows: list[dict]) -> tuple[list[str], int]:
        groups: dict[tuple[str, str], list[dict]] = {}
        for rr in rows:
            key = (str(rr.get("tag") or ""), str(rr.get("fingerprint") or ""))
            groups.setdefault(key, []).append(rr)
        to_ban: list[str] = []
        duplicate_groups = 0
        for _, grp in groups.items():
            if len(grp) <= keep_n:
                continue
            duplicate_groups += 1
            ranked = sorted(
                grp,
                key=lambda x: (float(x.get("weight") or 0.0), str(x.get("created_at") or "")),
                reverse=True,
            )
            for loser in ranked[keep_n:]:
                to_ban.append(str(loser.get("item_id") or ""))
        return to_ban, duplicate_groups

    mats = [dict(r) for r in material_rows.mappings().all()]
    tpls = [dict(r) for r in template_rows.mappings().all()]
    mat_to_ban, mat_dup_groups = _pick_duplicates(mats)
    tpl_to_ban, tpl_dup_groups = _pick_duplicates(tpls)

    if apply_ban and mat_to_ban:
        await db.execute(
            text("UPDATE material_card SET policy='banned' WHERE card_id = ANY(CAST(:ids AS uuid[]))"),
            {"ids": mat_to_ban},
        )
    if apply_ban and tpl_to_ban:
        await db.execute(
            text("UPDATE prompt_template SET policy='banned' WHERE template_id = ANY(CAST(:ids AS uuid[]))"),
            {"ids": tpl_to_ban},
        )
    if apply_ban:
        await db.commit()

    return {
        "ok": True,
        "book_id": str(book_id),
        "apply_ban": apply_ban,
        "material_duplicate_groups": mat_dup_groups,
        "template_duplicate_groups": tpl_dup_groups,
        "material_banned": len(mat_to_ban),
        "template_banned": len(tpl_to_ban),
        "material_ids": mat_to_ban[:200],
        "template_ids": tpl_to_ban[:200],
    }


@app.get("/v1/text_versions/{text_ver_id}/asset_selection_trace/latest")
async def asset_selection_trace_latest_route(text_ver_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.execute(
        text(
            """
            SELECT trace_id, book_id, chapter_id, text_ver_id, batch_id,
                   injected_bundle_id, assets_injection, ctx_tags,
                   selected_material_ids, selected_template_ids, trace, created_at
            FROM asset_selection_trace
            WHERE text_ver_id=CAST(:text_ver_id AS uuid)
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"text_ver_id": str(text_ver_id)},
    )
    r = row.mappings().first()
    if not r:
        raise HTTPException(status_code=404, detail="ASSET_SELECTION_TRACE_NOT_FOUND")
    return {
        "trace_id": str(r["trace_id"]),
        "book_id": str(r["book_id"]),
        "chapter_id": str(r["chapter_id"]) if r.get("chapter_id") else None,
        "text_ver_id": str(r["text_ver_id"]),
        "batch_id": str(r["batch_id"]) if r.get("batch_id") else None,
        "injected_bundle_id": str(r["injected_bundle_id"]) if r.get("injected_bundle_id") else None,
        "assets_injection": bool(r.get("assets_injection")),
        "ctx_tags": [str(x) for x in (r.get("ctx_tags") or [])],
        "selected_material_ids": [str(x) for x in (r.get("selected_material_ids") or [])],
        "selected_template_ids": [str(x) for x in (r.get("selected_template_ids") or [])],
        "trace": r.get("trace") if isinstance(r.get("trace"), dict) else {},
        "created_at": r.get("created_at"),
    }


@app.post("/v1/books/{book_id}/asset_policy_proposals/generate")
async def asset_policy_proposals_generate_route(book_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    out = await _generate_asset_policy_proposals(db, book_id=str(book_id))
    return {"ok": True, "book_id": str(book_id), **out}


@app.get("/v1/books/{book_id}/structure_combos/stats")
async def structure_combo_stats_route(
    book_id: UUID,
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> dict:
    out = await _structure_combo_stats(db, book_id=str(book_id), limit=limit)
    return {"ok": True, "book_id": str(book_id), **out}


@app.get("/v1/books/{book_id}/asset_policy_proposals")
async def asset_policy_proposals_list_route(
    book_id: UUID,
    status: str = Query(default="pending"),
    sort: str = Query(default="impact"),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = await db.execute(
        text(
            """
            SELECT proposal_id, item_type, item_id::text AS item_id, proposed_policy, status, reason, evidence, created_at, decided_at, decided_note
            FROM asset_policy_proposal
            WHERE book_id=CAST(:book_id AS uuid)
              AND (:status='' OR status=:status)
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"book_id": str(book_id), "status": str(status or "").strip(), "limit": int(limit)},
    )
    items = [dict(r) for r in rows.mappings().all()]
    if sort == "impact":
        def _rank(x: dict) -> tuple:
            ev = x.get("evidence") if isinstance(x.get("evidence"), dict) else {}
            risk = float(ev.get("risk") or 0.0)
            avg_delta = float(ev.get("avg_delta") or 0.0)
            uses_14d = int(ev.get("uses_14d") or 0)
            expected_gain = float(ev.get("expected_gain") or 0.0)
            proposed = str(x.get("proposed_policy") or "")
            banned_high_risk = 1 if (proposed == "banned" and risk >= 0.25) else 0
            banned_loss_impact = abs(avg_delta) * float(max(1, uses_14d))
            return (
                banned_high_risk,
                expected_gain if proposed == "pinned" else banned_loss_impact,
                str(x.get("created_at") or ""),
            )
        items = sorted(items, key=_rank, reverse=True)
    out_items = []
    for r in items:
        out_items.append(
            {
                "proposal_id": str(r["proposal_id"]),
                "item_type": str(r["item_type"]),
                "item_id": str(r["item_id"]),
                "proposed_policy": str(r["proposed_policy"]),
                "status": str(r["status"]),
                "reason": str(r.get("reason") or ""),
                "evidence": r.get("evidence") if isinstance(r.get("evidence"), dict) else {},
                "created_at": r.get("created_at"),
                "decided_at": r.get("decided_at"),
                "decided_note": str(r.get("decided_note") or ""),
            }
        )
    return {"book_id": str(book_id), "items": out_items}


@app.get("/v1/books/{book_id}/assets/{item_type}/{item_id}/evidence")
async def asset_item_evidence_route(
    book_id: UUID,
    item_type: str,
    item_id: UUID,
    limit: int = Query(default=3, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
) -> dict:
    it = str(item_type or "").strip().lower()
    if it not in {"material", "template", "structure_template", "structure_combo"}:
        raise HTTPException(status_code=400, detail="INVALID_ITEM_TYPE")
    iid = str(item_id)
    meta = await _item_meta_for_evidence(db, item_type=it, item_id=iid)
    if not meta:
        raise HTTPException(status_code=404, detail="ITEM_NOT_FOUND")
    usage_sql = (
        """
        SELECT usage_id::text AS usage_id, chapter_id::text AS chapter_id, text_ver_id::text AS text_ver_id, batch_id::text AS batch_id, created_at, ctx_tags
        FROM asset_usage_log
        WHERE book_id=CAST(:book_id AS uuid)
          AND assets_injection=true
          AND CAST(:item_id AS uuid) = ANY(injected_material_ids)
        ORDER BY created_at DESC
        LIMIT :limit
        """
        if it == "material"
        else (
            """
        SELECT usage_id::text AS usage_id, chapter_id::text AS chapter_id, text_ver_id::text AS text_ver_id, batch_id::text AS batch_id, created_at, ctx_tags
        FROM asset_usage_log
        WHERE book_id=CAST(:book_id AS uuid)
          AND assets_injection=true
          AND CAST(:item_id AS uuid) = ANY(injected_template_ids)
        ORDER BY created_at DESC
        LIMIT :limit
        """
            if it == "template"
            else (
                """
        SELECT usage_id::text AS usage_id, chapter_id::text AS chapter_id, text_ver_id::text AS text_ver_id, batch_id::text AS batch_id, created_at, ctx_tags
        FROM asset_usage_log
        WHERE book_id=CAST(:book_id AS uuid)
          AND CAST(:item_id AS uuid) = ANY(used_structure_template_ids)
        ORDER BY created_at DESC
        LIMIT :limit
        """
                if it == "structure_template"
                else """
        SELECT usage_id::text AS usage_id, chapter_id::text AS chapter_id, text_ver_id::text AS text_ver_id, batch_id::text AS batch_id, created_at, ctx_tags
        FROM asset_usage_log
        WHERE book_id=CAST(:book_id AS uuid)
          AND CAST(:item_id AS uuid) = ANY(used_combo_ids)
        ORDER BY created_at DESC
        LIMIT :limit
        """
            )
        )
    )
    ures = await db.execute(text(usage_sql), {"book_id": str(book_id), "item_id": iid, "limit": int(limit)})
    usage = [dict(r) for r in ures.mappings().all()]
    samples: list[dict] = []
    for u in usage:
        exp_res = await db.execute(
            text("SELECT batch_id::text AS batch_id, profile_id::text AS profile_id, variant, score FROM ab_batch_item WHERE text_ver_id=CAST(:tv AS uuid) LIMIT 1"),
            {"tv": str(u.get("text_ver_id") or "")},
        )
        exp = exp_res.mappings().first()
        exp_score = None
        baseline_score = None
        delta = None
        if exp and str(exp.get("variant") or "") == "exp":
            exp_score = float(exp.get("score")) if exp.get("score") is not None else None
            base_res = await db.execute(
                text(
                    """
                    SELECT score
                    FROM ab_batch_item
                    WHERE batch_id=CAST(:batch_id AS uuid)
                      AND profile_id=CAST(:profile_id AS uuid)
                      AND variant='baseline'
                      AND status='done'
                    LIMIT 1
                    """
                ),
                {"batch_id": str(exp.get("batch_id")), "profile_id": str(exp.get("profile_id"))},
            )
            base = base_res.mappings().first()
            baseline_score = float(base.get("score")) if base and base.get("score") is not None else None
            if exp_score is not None and baseline_score is not None:
                delta = round(exp_score - baseline_score, 6)
        tr_res = await db.execute(
            text("SELECT trace FROM asset_selection_trace WHERE text_ver_id=CAST(:tv AS uuid) ORDER BY created_at DESC LIMIT 1"),
            {"tv": str(u.get("text_ver_id") or "")},
        )
        tr = tr_res.mappings().first()
        trace = tr.get("trace") if tr and isinstance(tr.get("trace"), dict) else {}
        parsed = _extract_item_from_trace(trace, item_type=it, item_id=iid)
        samples.append(
            {
                "created_at": u.get("created_at"),
                "chapter_id": str(u.get("chapter_id") or "") if u.get("chapter_id") else None,
                "batch_id": str(u.get("batch_id") or "") if u.get("batch_id") else None,
                "text_ver_id": str(u.get("text_ver_id") or ""),
                "ctx_tags": [str(x) for x in (u.get("ctx_tags") or [])],
                "exp_score": exp_score,
                "baseline_score": baseline_score,
                "delta": delta,
                "rank": parsed.get("rank"),
                "breakdown": parsed.get("breakdown") if isinstance(parsed.get("breakdown"), dict) else {},
                "filtered_reason": parsed.get("filtered_reason"),
            }
        )
    diagnosis = _diagnose_samples(samples, item_type=it, item_id=iid)
    return {
        "item": {
            "item_type": it,
            "item_id": iid,
            "title": meta.get("title"),
            "policy": meta.get("policy"),
            "risk_score": meta.get("risk_score"),
            "fingerprint": meta.get("fingerprint"),
            "good_tags": (meta.get("extract_meta") or {}).get("good_tags") if isinstance(meta.get("extract_meta"), dict) else [],
            "bad_tags": (meta.get("extract_meta") or {}).get("bad_tags") if isinstance(meta.get("extract_meta"), dict) else [],
        },
        "samples": samples,
        "diagnosis": diagnosis,
    }


@app.post("/v1/books/{book_id}/assets/{item_type}/{item_id}/learn_tags")
async def asset_item_learn_tags_route(
    book_id: UUID,
    item_type: str,
    item_id: UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> dict:
    it = str(item_type or "").strip().lower()
    if it not in {"material", "template"}:
        raise HTTPException(status_code=400, detail="INVALID_ITEM_TYPE")
    limit = int((body or {}).get("limit") or 30)
    min_samples = int((body or {}).get("min_samples") or 6)
    out = await _learn_context_tags_for_item(
        db,
        book_id=str(book_id),
        item_type=it,
        item_id=str(item_id),
        limit=max(6, min(limit, 100)),
        min_samples=max(3, min(min_samples, 20)),
    )
    if not out.get("ok"):
        raise HTTPException(status_code=400, detail=str(out.get("reason") or "LEARN_FAILED"))
    return {"ok": True, "book_id": str(book_id), "item_type": it, "item_id": str(item_id), **out}


@app.post("/v1/asset_policy_proposals/{proposal_id}/accept")
async def asset_policy_proposal_accept_route(proposal_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    note = str((body or {}).get("note") or "").strip()
    row = await db.execute(
        text(
            """
            SELECT proposal_id, book_id, item_type, item_id::text AS item_id, proposed_policy, status
            FROM asset_policy_proposal
            WHERE proposal_id=CAST(:proposal_id AS uuid)
            """
        ),
        {"proposal_id": str(proposal_id)},
    )
    p = row.mappings().first()
    if not p:
        raise HTTPException(status_code=404, detail="PROPOSAL_NOT_FOUND")
    if str(p.get("status") or "") != "pending":
        raise HTTPException(status_code=400, detail="PROPOSAL_NOT_PENDING")
    item_type = str(p.get("item_type") or "")
    item_id = str(p.get("item_id") or "")
    proposed_policy = str(p.get("proposed_policy") or "")
    from_policy = "normal"
    if item_type == "material":
        rr = await db.execute(text("SELECT policy FROM material_card WHERE card_id=CAST(:id AS uuid)"), {"id": item_id})
        cur = rr.scalar()
        if cur is None:
            raise HTTPException(status_code=404, detail="MATERIAL_NOT_FOUND")
        from_policy = str(cur)
        await db.execute(text("UPDATE material_card SET policy=:policy WHERE card_id=CAST(:id AS uuid)"), {"id": item_id, "policy": proposed_policy})
    elif item_type == "template":
        rr = await db.execute(text("SELECT policy FROM prompt_template WHERE template_id=CAST(:id AS uuid)"), {"id": item_id})
        cur = rr.scalar()
        if cur is None:
            raise HTTPException(status_code=404, detail="TEMPLATE_NOT_FOUND")
        from_policy = str(cur)
        await db.execute(text("UPDATE prompt_template SET policy=:policy WHERE template_id=CAST(:id AS uuid)"), {"id": item_id, "policy": proposed_policy})
    elif item_type == "structure_template":
        rr = await db.execute(text("SELECT policy FROM structure_template WHERE template_id=CAST(:id AS uuid)"), {"id": item_id})
        cur = rr.scalar()
        if cur is None:
            raise HTTPException(status_code=404, detail="STRUCTURE_TEMPLATE_NOT_FOUND")
        from_policy = str(cur)
        await db.execute(text("UPDATE structure_template SET policy=:policy WHERE template_id=CAST(:id AS uuid)"), {"id": item_id, "policy": proposed_policy})
    elif item_type == "structure_combo":
        rr = await db.execute(text("SELECT policy FROM structure_combo WHERE combo_id=CAST(:id AS uuid)"), {"id": item_id})
        cur = rr.scalar()
        if cur is None:
            raise HTTPException(status_code=404, detail="STRUCTURE_COMBO_NOT_FOUND")
        from_policy = str(cur)
        await db.execute(text("UPDATE structure_combo SET policy=:policy WHERE combo_id=CAST(:id AS uuid)"), {"id": item_id, "policy": proposed_policy})
    else:
        raise HTTPException(status_code=400, detail="INVALID_ITEM_TYPE")
    await db.execute(
        text(
            """
            UPDATE asset_policy_proposal
            SET status='accepted', decided_at=now(), decided_note=:note
            WHERE proposal_id=CAST(:proposal_id AS uuid)
            """
        ),
        {"proposal_id": str(proposal_id), "note": note},
    )
    await db.execute(
        text(
            """
            INSERT INTO asset_policy_audit_log(
              book_id, item_type, item_id, from_policy, to_policy, proposal_id, note
            ) VALUES (
              CAST(:book_id AS uuid), :item_type, CAST(:item_id AS uuid), :from_policy, :to_policy, CAST(:proposal_id AS uuid), :note
            )
            """
        ),
        {
            "book_id": str(p["book_id"]),
            "item_type": item_type,
            "item_id": item_id,
            "from_policy": from_policy,
            "to_policy": proposed_policy,
            "proposal_id": str(proposal_id),
            "note": note,
        },
    )
    await db.commit()
    return {"ok": True, "proposal_id": str(proposal_id), "from_policy": from_policy, "to_policy": proposed_policy}


@app.post("/v1/asset_policy_proposals/{proposal_id}/reject")
async def asset_policy_proposal_reject_route(proposal_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    note = str((body or {}).get("note") or "").strip()
    row = await db.execute(
        text("SELECT status FROM asset_policy_proposal WHERE proposal_id=CAST(:proposal_id AS uuid)"),
        {"proposal_id": str(proposal_id)},
    )
    cur = row.scalar()
    if cur is None:
        raise HTTPException(status_code=404, detail="PROPOSAL_NOT_FOUND")
    if str(cur) != "pending":
        raise HTTPException(status_code=400, detail="PROPOSAL_NOT_PENDING")
    await db.execute(
        text(
            """
            UPDATE asset_policy_proposal
            SET status='rejected', decided_at=now(), decided_note=:note
            WHERE proposal_id=CAST(:proposal_id AS uuid)
            """
        ),
        {"proposal_id": str(proposal_id), "note": note},
    )
    await db.commit()
    return {"ok": True, "proposal_id": str(proposal_id), "status": "rejected"}


@app.post("/v1/chapters/{chapter_id}/tension/eval", response_model=SubmitJobResponse, status_code=202)
async def eval_tension_route(
    chapter_id: UUID,
    body: TensionEvalRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SubmitJobResponse:
    req_id = request_id(request)
    row_book = await db.execute(text("SELECT book_id FROM chapter WHERE chapter_id=:chapter_id"), {"chapter_id": str(chapter_id)})
    book_id = row_book.scalar()
    if not book_id:
        raise HTTPException(status_code=404, detail="CHAPTER_NOT_FOUND")
    chapter_version_id: str | None = str(body.chapter_version_id) if body.chapter_version_id else None
    if body.input_mode == "draft" and not chapter_version_id:
        latest_ver = await db.execute(
            text(
                """
                SELECT chapter_version_id
                FROM chapter_version
                WHERE chapter_id=:chapter_id
                ORDER BY version DESC, created_at DESC
                LIMIT 1
                """
            ),
            {"chapter_id": str(chapter_id)},
        )
        latest_id = latest_ver.scalar()
        if latest_id:
            chapter_version_id = str(latest_id)
        else:
            # keep backward-compatible behavior when draft text version is absent
            chapter_version_id = "00000000-0000-0000-0000-000000000000"
    if not chapter_version_id:
        chapter_version_id = "00000000-0000-0000-0000-000000000000"
    effective_settings = await get_effective_settings(db, str(chapter_id))
    eval_cfg = ((effective_settings or {}).get("effective") or {}).get("eval") or {}
    effective_targets = eval_cfg.get("targets") if isinstance(eval_cfg.get("targets"), dict) else {}
    targets_input = body.targets
    if "targets" not in body.model_fields_set and effective_targets:
        targets_input = dict(effective_targets)
    payload: dict = {
        "book_id": str(book_id),
        "chapter_id": str(chapter_id),
        "chapter_version_id": chapter_version_id,
        "input_mode": body.input_mode,
        "llm_model": body.llm_model or DEFAULT_LLM_MODEL,
        "targets": merge_defaults(DEFAULT_TENSION_TARGETS, targets_input),
        "schema_ver": body.schema_ver,
    }
    _attach_trigger_meta(
        payload,
        trigger_source=body.trigger_source,
        trigger_entry=body.trigger_entry,
        trigger_mode=body.trigger_mode,
    )
    profile_id = str(body.profile_id) if body.profile_id else None
    if not profile_id:
        r = await db.execute(text("SELECT profile_id FROM book WHERE book_id=:book_id"), {"book_id": str(book_id)})
        p = r.scalar()
        if p:
            profile_id = str(p)
    if profile_id:
        payload["profile_id"] = profile_id
        prof = await get_profile(db, profile_id)
        if prof:
            payload["profile_version_used"] = int(prof.get("active_version") or 1)
            payload["style_profile"] = {
                "profile_id": profile_id,
                "active_version": int(prof.get("active_version") or 1),
                "name": prof.get("name"),
                "features": prof.get("features") or {},
                "dos": prof.get("dos") or [],
                "donts": prof.get("donts") or [],
            }
    row = await create_job(db, "eval.conflict_tension.v1", payload, req_id)
    await job_runner.enqueue(row["job_id"], req_id)
    return SubmitJobResponse(job_id=row["job_id"], status="queued", queued_at=row["created_at"], request_id=req_id)


@app.post("/v1/chapters/{chapter_id}/tension/control_plan", response_model=SubmitJobResponse, status_code=202)
async def tension_control_plan_route(
    chapter_id: UUID,
    body: TensionControlPlanRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SubmitJobResponse:
    req_id = request_id(request)
    row_book = await db.execute(text("SELECT book_id FROM chapter WHERE chapter_id=:chapter_id"), {"chapter_id": str(chapter_id)})
    book_id = row_book.scalar()
    if not book_id:
        raise HTTPException(status_code=404, detail="CHAPTER_NOT_FOUND")
    effective_settings = await get_effective_settings(db, str(chapter_id))
    effective = (effective_settings or {}).get("effective") or {}
    eval_cfg = effective.get("eval") or {}
    effective_targets = eval_cfg.get("targets") if isinstance(eval_cfg.get("targets"), dict) else {}
    draft_cfg = effective.get("draft") if isinstance(effective.get("draft"), dict) else {}
    body_targets = body.targets.model_dump()
    if "targets" not in body.model_fields_set and effective_targets:
        body_targets = {
            "conflict_strength": float(effective_targets.get("conflict", DEFAULT_TENSION_TARGETS["conflict_strength"])),
            "stakes": float(effective_targets.get("stakes", DEFAULT_TENSION_TARGETS["stakes"])),
            "cost": float(effective_targets.get("cost", DEFAULT_TENSION_TARGETS["cost"])),
            "pace": float(effective_targets.get("pacing", DEFAULT_TENSION_TARGETS["pace"])),
            "reversal": float(effective_targets.get("foreshadow", DEFAULT_TENSION_TARGETS["reversal"])),
            "hook": float(effective_targets.get("hook", DEFAULT_TENSION_TARGETS["hook"])),
        }
    style_input = body.style.model_dump()
    if "style" not in body.model_fields_set and draft_cfg:
        style_input = merge_defaults(DEFAULT_TENSION_STYLE, {
            "face_slap_density": draft_cfg.get("face_slap_density"),
            "upgrade_density": draft_cfg.get("upgrade_density"),
        })
    payload: dict = {
        "book_id": str(book_id),
        "chapter_id": str(chapter_id),
        "outline_id": str(body.outline_id) if body.outline_id else None,
        "targets": merge_defaults(DEFAULT_TENSION_TARGETS, body_targets),
        "style": merge_defaults(DEFAULT_TENSION_STYLE, style_input),
        "material_refs": [str(x) for x in (body.material_refs or []) if str(x).strip()][:20],
        "llm_model": body.llm_model or DEFAULT_LLM_MODEL,
        "schema_ver": body.schema_ver,
    }
    _attach_trigger_meta(
        payload,
        trigger_source=body.trigger_source,
        trigger_entry=body.trigger_entry,
        trigger_mode=body.trigger_mode,
    )
    profile_id = str(body.profile_id) if body.profile_id else None
    if not profile_id:
        r = await db.execute(text("SELECT profile_id FROM book WHERE book_id=:book_id"), {"book_id": str(book_id)})
        p = r.scalar()
        if p:
            profile_id = str(p)
    if profile_id:
        payload["profile_id"] = profile_id
        prof = await get_profile(db, profile_id)
        if prof:
            payload["profile_version_used"] = int(prof.get("active_version") or 1)
            payload["style_profile"] = {
                "profile_id": profile_id,
                "active_version": int(prof.get("active_version") or 1),
                "name": prof.get("name"),
                "features": prof.get("features") or {},
                "dos": prof.get("dos") or [],
                "donts": prof.get("donts") or [],
            }
    row = await create_job(db, "control_plan.tension.v1", payload, req_id)
    await job_runner.enqueue(row["job_id"], req_id)
    return SubmitJobResponse(job_id=row["job_id"], status="queued", queued_at=row["created_at"], request_id=req_id)


@app.post("/v1/chapters/{chapter_id}/tension/apply")
async def apply_tension_route(
    chapter_id: UUID,
    body: TensionApplyRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await apply_tension_patches(
        db,
        str(chapter_id),
        str(body.skill_run_id),
        body.apply_target,
        selected_patch_ids=body.selected_patch_ids,
    )
    return {"ok": True, "mode": body.mode, **result}


@app.post("/v1/chapters/{chapter_id}/mechanics/preview")
async def mechanics_preview_route(
    chapter_id: UUID,
    body: MechanicsPreviewRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    # load outline detail (outline_id preferred, fallback latest chapter outline)
    if body.outline_id:
        res = await db.execute(
            text(
                """
                SELECT content
                FROM outline
                WHERE outline_id=:outline_id AND chapter_id=:chapter_id AND scope='chapter'
                LIMIT 1
                """
            ),
            {"outline_id": str(body.outline_id), "chapter_id": str(chapter_id)},
        )
    else:
        res = await db.execute(
            text(
                """
                SELECT content
                FROM outline
                WHERE chapter_id=:chapter_id AND scope='chapter'
                ORDER BY version DESC
                LIMIT 1
                """
            ),
            {"chapter_id": str(chapter_id)},
        )
    row = res.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="OUTLINE_NOT_FOUND")
    outline_detail = row["content"] or {}
    try:
        preview = mechanics_preview(outline_detail, body.mechanic, body.selected_node_id, body.strength)
        return {"ok": True, **preview}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/chapters/{chapter_id}/similarity/guard", response_model=SubmitJobResponse, status_code=202)
async def similarity_guard_route(
    chapter_id: UUID,
    body: SimilarityGuardRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SubmitJobResponse:
    req_id = request_id(request)
    chapter_exists = await db.execute(text("SELECT 1 FROM chapter WHERE chapter_id=:chapter_id"), {"chapter_id": str(chapter_id)})
    if chapter_exists.first() is None:
        raise HTTPException(status_code=404, detail="CHAPTER_NOT_FOUND")
    payload = {
        "chapter_id": str(chapter_id),
        "book_id": str(body.book_id) if body.book_id else None,
        "chapter_version_id": str(body.chapter_version_id),
        "embedding_model": body.embedding_model,
        "vec_high": body.vec_high,
        "vec_mid": body.vec_mid,
        "ngram_high": body.ngram_high,
        "ngram_mid": body.ngram_mid,
        "schema_ver": body.schema_ver,
    }
    row = await create_job(db, "similarity.guard.v1", payload, req_id)
    await job_runner.enqueue(row["job_id"], req_id)
    return SubmitJobResponse(job_id=row["job_id"], status="queued", queued_at=row["created_at"], request_id=req_id)


@app.post("/v1/chapters/{chapter_id}/guard/similarity", response_model=SubmitJobResponse, status_code=202)
async def similarity_guard_text_route(
    chapter_id: UUID,
    body: SimilarityGuardTextRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SubmitJobResponse:
    req_id = request_id(request)
    chapter_exists = await db.execute(text("SELECT 1 FROM chapter WHERE chapter_id=:chapter_id"), {"chapter_id": str(chapter_id)})
    if chapter_exists.first() is None:
        raise HTTPException(status_code=404, detail="CHAPTER_NOT_FOUND")
    effective_settings = await get_effective_settings(db, str(chapter_id))
    sim_cfg = ((effective_settings or {}).get("effective") or {}).get("simguard") or {}
    embedding_cfg = ((effective_settings or {}).get("effective") or {}).get("embedding") or {}
    scope = body.scope
    if "scope" not in body.model_fields_set:
        scope_default = sim_cfg.get("scope_default")
        if isinstance(scope_default, list) and scope_default:
            scope = [str(x) for x in scope_default]
    sim_threshold = float(body.sim_threshold)
    if "sim_threshold" not in body.model_fields_set and sim_cfg.get("sim_threshold") is not None:
        sim_threshold = float(sim_cfg.get("sim_threshold"))
    top_k = int(body.top_k)
    if "top_k" not in body.model_fields_set and sim_cfg.get("top_k") is not None:
        top_k = int(sim_cfg.get("top_k"))
    payload = {
        "chapter_id": str(chapter_id),
        "text_ver_id": str(body.text_ver_id) if body.text_ver_id else None,
        "scope": scope,
        "sim_threshold": sim_threshold,
        "top_k": top_k,
        "embedding_model": body.embedding_model or embedding_cfg.get("model"),
        "schema_ver": 1,
    }
    row = await create_job(db, "similarity.guard.text.v1", payload, req_id)
    await job_runner.enqueue(row["job_id"], req_id)
    return SubmitJobResponse(job_id=row["job_id"], status="queued", queued_at=row["created_at"], request_id=req_id)


@app.post("/v1/templates/{template_id}/use", response_model=TemplateUseResponse)
async def use_template_route(template_id: UUID, body: TemplateUseRequest, db: AsyncSession = Depends(get_db)) -> TemplateUseResponse:
    row = await log_template_usage(
        db,
        str(template_id),
        str(body.book_id) if body.book_id else None,
        str(body.chapter_id) if body.chapter_id else None,
        body.usage_type,
        body.feedback,
    )
    return TemplateUseResponse(**row)


EXTERNAL_SKILL_PACKS: list[dict] = [
    {
        "pack_id": "chinese-novelist",
        "name": "Chinese Novelist: 中文小说创作助手",
        "source": "github",
        "upstream": "PenglongHuang/chinese-novelist-skill",
        "capabilities": ["chapter_generation", "longform_serialization", "de_ai_rewrite"],
        "defaults": {"auto_preflight": True, "auto_low_risk_fix": True, "auto_rewrite_suggest": True},
    },
    {
        "pack_id": "webnovel-writer",
        "name": "深度模式网络小说",
        "source": "github",
        "upstream": "lingfengQAQ/webnovel-writer",
        "capabilities": ["chapter_generation", "scene_rhythm", "cliffhanger"],
        "defaults": {"auto_preflight": True, "auto_low_risk_fix": True},
    },
    {
        "pack_id": "ordinary-claude-workflow",
        "name": "系统化创作工作流",
        "source": "github",
        "upstream": "Microck/ordinary-claude-skills",
        "capabilities": ["workflow_guidance", "consistency_review", "quality_gate"],
        "defaults": {"auto_preflight": True, "auto_low_risk_fix": True, "max_auto_fixes": 4},
    },
    {
        "pack_id": "workflow-guide",
        "name": "系统化创作工作流指南",
        "source": "skills.sh",
        "upstream": "wordflowlab/novel-writer-skills/novel-writer-workflow-guide",
        "capabilities": ["workflow_guidance", "pre_write_gate"],
        "defaults": {"auto_preflight": True},
    },
    {
        "pack_id": "scene-structure-techniques",
        "name": "场景结构写作技巧",
        "source": "skills.sh",
        "upstream": "wordflowlab/novel-writer-skills/scene-structure-techniques",
        "capabilities": ["scene_structure", "pacing"],
        "defaults": {"auto_preflight": True, "auto_rewrite_suggest": True},
    },
    {
        "pack_id": "story-consistency-monitor",
        "name": "故事一致性监控",
        "source": "skills.sh",
        "upstream": "wordflowlab/novel-writer-skills/story-consistency-monitor",
        "capabilities": ["consistency_monitor", "continuity_checks"],
        "defaults": {"auto_preflight": True, "auto_low_risk_fix": True},
    },
    {
        "pack_id": "novel-architect",
        "name": "小说建筑师",
        "source": "skills.sh",
        "upstream": "junaid18183/novel-architect-skills/novel-architect",
        "capabilities": ["outline_architecture", "arc_planning"],
        "defaults": {"auto_plan_autobuild": True},
    },
    {
        "pack_id": "natural-dialogue-techniques",
        "name": "自然对话写作技巧",
        "source": "skills.sh",
        "upstream": "wordflowlab/novel-writer-skills/natural-dialogue-techniques",
        "capabilities": ["dialogue_naturalness", "de_ai_rewrite"],
        "defaults": {"auto_rewrite_suggest": True},
    },
    {
        "pack_id": "pre-write-checklist",
        "name": "写作前强制检查清单",
        "source": "skills.sh",
        "upstream": "wordflowlab/novel-writer-skills/pre-write-checklist",
        "capabilities": ["pre_write_gate", "risk_precheck"],
        "defaults": {"auto_preflight": True},
    },
    {
        "pack_id": "novelist-analyst",
        "name": "小说家兼分析师",
        "source": "skills.sh",
        "upstream": "rysweet/amplihack/novelist-analyst",
        "capabilities": ["analysis", "quality_gate", "risk_precheck"],
        "defaults": {"auto_preflight": True, "auto_low_risk_fix": True},
    },
    {
        "pack_id": "forgotten-elements-reminder",
        "name": "遗忘元素提醒器",
        "source": "skills.sh",
        "upstream": "wordflowlab/novel-writer-skills/forgotten-elements-reminder",
        "capabilities": ["foreshadow_debt", "growth_debt"],
        "defaults": {"auto_preflight": True, "auto_low_risk_fix": True},
    },
    {
        "pack_id": "webnovel-write",
        "name": "章节写作技巧",
        "source": "skills.sh",
        "upstream": "lingfengqaq/webnovel-writer/webnovel-write",
        "capabilities": ["chapter_generation", "scene_rhythm", "cliffhanger"],
        "defaults": {"auto_preflight": True, "auto_rewrite_suggest": True},
    },
    {
        "pack_id": "setting-detector",
        "name": "故事设定自动检测器",
        "source": "skills.sh",
        "upstream": "wordflowlab/novel-writer-skills/setting-detector",
        "capabilities": ["setting_consistency", "continuity_checks"],
        "defaults": {"auto_preflight": True, "auto_low_risk_fix": True},
    },
]

EXTERNAL_SKILL_PACKS_BY_ID: dict[str, dict] = {str(x["pack_id"]): x for x in EXTERNAL_SKILL_PACKS}

SKILLPACK_AUTOMATION_PRESETS: dict[str, dict] = {
    "conservative": {
        "name": "保守",
        "automation": {
            "auto_preflight": True,
            "auto_low_risk_fix": True,
            "auto_plan_autobuild": False,
            "auto_rewrite_suggest": False,
            "auto_low_risk_only": True,
            "max_auto_fixes": 2,
        },
    },
    "balanced": {
        "name": "平衡",
        "automation": {
            "auto_preflight": True,
            "auto_low_risk_fix": True,
            "auto_plan_autobuild": True,
            "auto_rewrite_suggest": True,
            "auto_low_risk_only": True,
            "max_auto_fixes": 4,
        },
    },
    "aggressive": {
        "name": "激进",
        "automation": {
            "auto_preflight": True,
            "auto_low_risk_fix": True,
            "auto_plan_autobuild": True,
            "auto_rewrite_suggest": True,
            "auto_low_risk_only": False,
            "max_auto_fixes": 8,
        },
    },
}


async def _ensure_skillpack_tables(db: AsyncSession) -> None:
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS book_skillpack_binding (
              book_id UUID PRIMARY KEY,
              selected_pack_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
              automation JSONB NOT NULL DEFAULT '{}'::jsonb,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    await db.commit()


def _skillpack_defaults(pack_ids: list[str]) -> dict:
    merged: dict = {
        "auto_preflight": True,
        "auto_low_risk_fix": True,
        "auto_plan_autobuild": False,
        "auto_rewrite_suggest": False,
        "auto_low_risk_only": True,
        "max_auto_fixes": 3,
    }
    for pid in pack_ids:
        p = EXTERNAL_SKILL_PACKS_BY_ID.get(pid)
        if not p:
            continue
        defaults = p.get("defaults") if isinstance(p.get("defaults"), dict) else {}
        merged = _merge_dict(merged, defaults)
    return merged


def _resolve_skillpack_automation(
    pack_ids: list[str],
    *,
    preset: str | None = None,
    base: dict | None = None,
    patch: dict | None = None,
) -> dict:
    out = _skillpack_defaults(pack_ids)
    key = str(preset or "").strip().lower()
    if key and key in SKILLPACK_AUTOMATION_PRESETS:
        out = _merge_dict(out, SKILLPACK_AUTOMATION_PRESETS[key]["automation"])
    if isinstance(base, dict):
        out = _merge_dict(out, base)
    if isinstance(patch, dict):
        out = _merge_dict(out, patch)
    return out


@app.get("/v1/skillpacks/presets")
async def skillpacks_presets_route() -> dict:
    return {"ok": True, "items": SKILLPACK_AUTOMATION_PRESETS}


@app.get("/v1/skillpacks/catalog")
async def skillpacks_catalog_route() -> dict:
    return {"ok": True, "items": EXTERNAL_SKILL_PACKS}


@app.get("/v1/skillpacks/bindings/{book_id}")
async def skillpacks_binding_get_route(book_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    await _ensure_skillpack_tables(db)
    row = await db.execute(
        text(
            """
            SELECT book_id::text AS book_id, selected_pack_ids, automation, updated_at
            FROM book_skillpack_binding
            WHERE book_id=CAST(:book_id AS uuid)
            LIMIT 1
            """
        ),
        {"book_id": str(book_id)},
    )
    hit = row.mappings().first()
    if not hit:
        return {"ok": True, "book_id": str(book_id), "selected_pack_ids": [], "automation": _skillpack_defaults([]), "bound": False}
    selected_pack_ids = [str(x) for x in (hit.get("selected_pack_ids") or [])]
    automation = _merge_dict(_skillpack_defaults(selected_pack_ids), hit.get("automation") if isinstance(hit.get("automation"), dict) else {})
    return {
        "ok": True,
        "book_id": str(book_id),
        "selected_pack_ids": selected_pack_ids,
        "automation": automation,
        "bound": True,
        "updated_at": str(hit.get("updated_at") or ""),
    }


@app.post("/v1/skillpacks/bind")
async def skillpacks_binding_set_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    book_id = str((body or {}).get("book_id") or "").strip()
    if not book_id:
        raise HTTPException(status_code=400, detail="book_id required")
    await _ensure_skillpack_tables(db)
    selected_raw = body.get("selected_pack_ids") if isinstance(body.get("selected_pack_ids"), list) else []
    selected_pack_ids = [str(x).strip() for x in selected_raw if str(x).strip()]
    invalid = [x for x in selected_pack_ids if x not in EXTERNAL_SKILL_PACKS_BY_ID]
    if invalid:
        raise HTTPException(status_code=400, detail=f"UNKNOWN_PACK_IDS:{','.join(invalid[:8])}")
    selected_pack_ids = list(dict.fromkeys(selected_pack_ids))
    patch = body.get("automation") if isinstance(body.get("automation"), dict) else {}
    preset = str((body or {}).get("automation_preset") or "").strip().lower() or None
    automation = _resolve_skillpack_automation(selected_pack_ids, preset=preset, patch=patch)
    await db.execute(
        text(
            """
            INSERT INTO book_skillpack_binding(book_id, selected_pack_ids, automation, updated_at)
            VALUES (CAST(:book_id AS uuid), CAST(:selected_pack_ids AS jsonb), CAST(:automation AS jsonb), now())
            ON CONFLICT(book_id) DO UPDATE SET
              selected_pack_ids=EXCLUDED.selected_pack_ids,
              automation=EXCLUDED.automation,
              updated_at=now()
            """
        ),
        {
            "book_id": book_id,
            "selected_pack_ids": json.dumps(selected_pack_ids, ensure_ascii=False),
            "automation": json.dumps(automation, ensure_ascii=False),
        },
    )
    await db.commit()
    return {
        "ok": True,
        "book_id": book_id,
        "selected_pack_ids": selected_pack_ids,
        "automation": automation,
        "automation_preset": preset,
    }


@app.post("/v1/skillpacks/auto_run")
async def skillpacks_auto_run_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    book_id = str((body or {}).get("book_id") or "").strip()
    volume_id = str((body or {}).get("volume_id") or "").strip()
    chapter_id = str((body or {}).get("chapter_id") or "").strip()
    if not book_id or not volume_id:
        raise HTTPException(status_code=400, detail="book_id and volume_id required")
    await _ensure_skillpack_tables(db)

    bind_row = await db.execute(
        text(
            """
            SELECT selected_pack_ids, automation
            FROM book_skillpack_binding
            WHERE book_id=CAST(:book_id AS uuid)
            LIMIT 1
            """
        ),
        {"book_id": book_id},
    )
    hit = bind_row.mappings().first()
    selected_from_body = body.get("selected_pack_ids") if isinstance(body.get("selected_pack_ids"), list) else []
    selected_pack_ids = [str(x).strip() for x in selected_from_body if str(x).strip()]
    if not selected_pack_ids and hit:
        selected_pack_ids = [str(x) for x in (hit.get("selected_pack_ids") or []) if str(x).strip()]
    selected_pack_ids = [x for x in selected_pack_ids if x in EXTERNAL_SKILL_PACKS_BY_ID]

    preset = str((body or {}).get("automation_preset") or "").strip().lower() or None
    automation = _resolve_skillpack_automation(
        selected_pack_ids,
        preset=preset,
        base=(hit.get("automation") if (hit and isinstance(hit.get("automation"), dict)) else None),
        patch=(body.get("automation") if isinstance(body.get("automation"), dict) else None),
    )

    vr_row = await db.execute(
        text("SELECT volume_no FROM volume WHERE volume_id=CAST(:volume_id AS uuid) AND book_id=CAST(:book_id AS uuid) LIMIT 1"),
        {"book_id": book_id, "volume_id": volume_id},
    )
    vr = vr_row.mappings().first()
    if not vr:
        raise HTTPException(status_code=404, detail="VOLUME_NOT_FOUND")
    volume_no = int(vr.get("volume_no") or 1)

    preflight = body.get("preflight") if isinstance(body.get("preflight"), dict) else None
    if not preflight and bool(automation.get("auto_preflight", True)):
        preflight = await _run_preflight_for_volume(db, book_id=book_id, volume_id=volume_id, volume_no=volume_no)
    if not preflight:
        preflight = {"summary": {"overall": "UNKNOWN", "fail_count": 0, "warn_count": 0, "suggest_count": 0}}

    fixes = _fixwizard_build_fixes(book_id, volume_id, preflight if isinstance(preflight, dict) else {})
    allow_types = {"agent_apply", "plan_patch"}
    if bool(automation.get("auto_plan_autobuild", False)):
        allow_types.add("plan_autobuild")
    include_rewrite_suggest = bool(automation.get("auto_rewrite_suggest", False))
    if include_rewrite_suggest:
        allow_types.add("rewrite_suggest")
    low_only = bool(automation.get("auto_low_risk_only", True))
    max_auto = max(1, min(10, int(automation.get("max_auto_fixes", 3) or 3)))

    selected_auto_fixes: list[dict] = []
    pending_manual_fixes: list[dict] = []
    for fx in fixes:
        if not isinstance(fx, dict):
            continue
        ftype = str(fx.get("type") or "")
        risk = str(fx.get("risk") or "mid").lower()
        choose = ftype in allow_types and (not low_only or risk == "low")
        target = {
            "fix_id": str(fx.get("fix_id") or ""),
            "title": str(fx.get("title") or ""),
            "type": ftype,
            "risk": risk,
            "payload": fx.get("payload") if isinstance(fx.get("payload"), dict) else {},
        }
        if choose and len(selected_auto_fixes) < max_auto:
            selected_auto_fixes.append(target)
        else:
            pending_manual_fixes.append(target)

    exec_out = {"ok": True, "executed": [], "recheck": None}
    if bool(automation.get("auto_low_risk_fix", True)) and selected_auto_fixes:
        exec_body = {
            "book_id": book_id,
            "volume_id": volume_id,
            "chapter_id": chapter_id or None,
            "pack_name": str((body or {}).get("pack_name") or "skillpack_auto_run"),
            "preflight": preflight if isinstance(preflight, dict) else {},
            "preflight_summary": (preflight.get("summary") if isinstance(preflight, dict) else {}),
            "fixes": fixes,
            "selected_fixes": [{"fix_id": str(x.get("fix_id") or "")} for x in selected_auto_fixes if str(x.get("fix_id") or "").strip()],
            "auto_recheck": True,
            "operator_note": "skillpacks_auto_run",
        }
        exec_out = await fixwizard_execute_route(exec_body, db=db)

    return {
        "ok": True,
        "book_id": book_id,
        "volume_id": volume_id,
        "selected_pack_ids": selected_pack_ids,
        "automation_preset": preset,
        "automation": automation,
        "preflight": preflight,
        "auto_selected_fixes": selected_auto_fixes,
        "manual_fixes": pending_manual_fixes,
        "execution": exec_out,
    }


@app.get("/v1/books/{book_id}/engine/dashboard")
async def story_engine_dashboard_route(book_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await get_story_engine_dashboard(db, str(book_id))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"STORY_ENGINE_DASHBOARD_FAILED:{exc}") from exc


@app.get("/v1/books/{book_id}/engine/quality/metrics")
async def story_engine_quality_metrics_route(
    book_id: UUID,
    checkpoint_limit: int = Query(default=240, ge=40, le=1000),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await get_story_engine_quality_metrics(
            db,
            str(book_id),
            checkpoint_limit=checkpoint_limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"STORY_ENGINE_QUALITY_METRICS_FAILED:{exc}") from exc


@app.post("/v1/books/{book_id}/engine/quality/regression")
async def story_engine_quality_regression_route(book_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await run_story_engine_regression(db, str(book_id), body if isinstance(body, dict) else {})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"STORY_ENGINE_QUALITY_REGRESSION_FAILED:{exc}") from exc


@app.get("/v1/books/{book_id}/story_bible")
async def story_bible_snapshot_route(
    book_id: UUID,
    chapter_id: UUID | None = Query(default=None),
    limit: int = Query(default=80, ge=10, le=400),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await get_story_bible_snapshot(
            db,
            str(book_id),
            chapter_id=(str(chapter_id) if chapter_id else None),
            limit=limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"STORY_BIBLE_SNAPSHOT_FAILED:{exc}") from exc


@app.get("/v1/books/{book_id}/story_bible/proposals")
async def story_bible_proposals_list_route(
    book_id: UUID,
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await list_story_bible_proposals(db, str(book_id), status=status, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"STORY_BIBLE_PROPOSAL_LIST_FAILED:{exc}") from exc


@app.post("/v1/books/{book_id}/story_bible/proposals")
async def story_bible_proposals_create_route(book_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await create_story_bible_proposal(db, str(book_id), body if isinstance(body, dict) else {})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"STORY_BIBLE_PROPOSAL_CREATE_FAILED:{exc}") from exc


@app.post("/v1/books/{book_id}/story_bible/proposals/{proposal_id}/review")
async def story_bible_proposals_review_route(
    book_id: UUID,
    proposal_id: UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await review_story_bible_proposal(
            db,
            str(book_id),
            str(proposal_id),
            body if isinstance(body, dict) else {},
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"STORY_BIBLE_PROPOSAL_REVIEW_FAILED:{exc}") from exc


@app.get("/v1/books/{book_id}/engine/memory/session")
async def writing_memory_session_get_route(
    book_id: UUID,
    session_key: str = Query(default="default"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await get_writing_session_state(db, str(book_id), session_key=session_key)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"WRITING_MEMORY_SESSION_GET_FAILED:{exc}") from exc


@app.post("/v1/books/{book_id}/engine/memory/session")
async def writing_memory_session_upsert_route(book_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await upsert_writing_session_state(db, str(book_id), body if isinstance(body, dict) else {})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"WRITING_MEMORY_SESSION_UPSERT_FAILED:{exc}") from exc


@app.post("/v1/books/{book_id}/engine/memory/pack")
async def writing_memory_pack_route(book_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await build_writing_memory_pack(db, str(book_id), body if isinstance(body, dict) else {})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"WRITING_MEMORY_PACK_FAILED:{exc}") from exc


@app.post("/v1/books/{book_id}/engine/memory/writeback")
async def writing_memory_writeback_route(book_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await validate_and_writeback_memory(db, str(book_id), body if isinstance(body, dict) else {})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"WRITING_MEMORY_WRITEBACK_FAILED:{exc}") from exc


@app.post("/v1/books/{book_id}/engine/chapter_pack")
async def chapter_engine_pack_route(book_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await build_chapter_engine_pack(db, str(book_id), body if isinstance(body, dict) else {})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"CHAPTER_ENGINE_PACK_FAILED:{exc}") from exc


@app.post("/v1/books/{book_id}/engine/chapter_audit")
async def chapter_engine_audit_route(book_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await run_chapter_engine_audit(db, str(book_id), body if isinstance(body, dict) else {})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"CHAPTER_ENGINE_AUDIT_FAILED:{exc}") from exc


@app.post("/v1/books/{book_id}/engine/chapter_repair_plan")
async def chapter_engine_repair_plan_route(book_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await build_chapter_repair_plan(db, str(book_id), body if isinstance(body, dict) else {})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"CHAPTER_ENGINE_REPAIR_PLAN_FAILED:{exc}") from exc


@app.post("/v1/books/{book_id}/engine/model_route")
async def story_engine_model_route(book_id: UUID, body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await route_story_model(db, str(book_id), body if isinstance(body, dict) else {})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"STORY_ENGINE_MODEL_ROUTE_FAILED:{exc}") from exc
