from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import httpx
import pytest


API_BASE = os.getenv("API_BASE", "http://127.0.0.1:17777").rstrip("/")
API_PREFIX = os.getenv("API_PREFIX", "/v1")
BASE_URL = f"{API_BASE}{API_PREFIX}"


def _wait_job(client: httpx.Client, job_id: str, timeout_s: float = 180.0) -> dict:
    deadline = time.time() + timeout_s
    last = {}
    while time.time() < deadline:
        resp = client.get(f"/jobs/{job_id}")
        assert resp.status_code == 200, resp.text
        last = resp.json()
        status = str(last.get("status") or "").strip().lower()
        if status in {"succeeded", "done"}:
            return last
        if status in {"failed", "canceled"}:
            pytest.fail(f"job {job_id} ended with status={status}, payload={last}")
        time.sleep(0.5)
    pytest.fail(f"job {job_id} timeout, last={last}")


@pytest.fixture(scope="session")
def client() -> httpx.Client:
    timeout = httpx.Timeout(30.0, connect=8.0)
    with httpx.Client(base_url=BASE_URL, timeout=timeout) as c:
        yield c


def test_health_contract(client: httpx.Client) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "status" in body
    assert "checks" in body
    checks = body["checks"]
    assert "postgres" in checks
    assert isinstance(checks["postgres"], dict)
    assert "pgvector" in checks
    assert isinstance(checks["pgvector"], dict)


def test_splitbook_embed_duplicate_guard_contract(client: httpx.Client, tmp_path: Path) -> None:
    source = tmp_path / "splitbook_contract.txt"
    source.write_text("这是一段用于契约验证的文本。\n" * 80, encoding="utf-8")
    splitbook_name = f"contract-{uuid.uuid4().hex[:8]}"
    create_resp = client.post(
        "/splitbooks",
        json={
            "name": splitbook_name,
            "author": "qa",
            "source_path": str(source),
            "note": "api contract",
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    splitbook_id = str(create_resp.json().get("splitbook_id") or "")
    assert splitbook_id

    try:
        ingest_resp = client.post(
            f"/splitbooks/{splitbook_id}/ingest",
            json={"path": str(source), "auto_optimize": True},
        )
        assert ingest_resp.status_code == 202, ingest_resp.text
        ingest_job_id = str(ingest_resp.json().get("job_id") or "")
        assert ingest_job_id
        _wait_job(client, ingest_job_id)

        embed_resp = client.post(
            f"/splitbooks/{splitbook_id}/embed",
            json={"auto_optimize": True, "batch": 32},
        )
        assert embed_resp.status_code == 202, embed_resp.text
        embed_job_id = str(embed_resp.json().get("job_id") or "")
        assert embed_job_id
        _wait_job(client, embed_job_id, timeout_s=240.0)

        dup_resp = client.post(f"/splitbooks/{splitbook_id}/embed", json={})
        assert dup_resp.status_code == 409, dup_resp.text
        dup_body = dup_resp.json()
        assert dup_body.get("detail_code") == "SPLITBOOK_EMBED_ALREADY_DONE"
    finally:
        client.delete(f"/splitbooks/{splitbook_id}")


def test_splitbook_high_precision_extract_contract(client: httpx.Client, tmp_path: Path) -> None:
    source = tmp_path / "splitbook_high_precision.txt"
    source.write_text(
        (
            "清晨，林渊在青石城外发现符文裂纹，却被告知不可触碰。"
            "他选择压下好奇，先按宗门规则回报。"
            "\n\n"
            "深夜，对手在城门布下陷阱。林渊被迫反击并付出代价，冲突升级。"
            "他在撤离时留下了未解释的异常线索。"
            "\n\n"
            "翌日，裂纹被触发，前夜异常得到部分解释，但更大的威胁出现。"
        ),
        encoding="utf-8",
    )
    splitbook_name = f"hp-{uuid.uuid4().hex[:8]}"
    create_resp = client.post(
        "/splitbooks",
        json={
            "name": splitbook_name,
            "author": "qa",
            "source_path": str(source),
            "note": "high precision contract",
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    splitbook_id = str(create_resp.json().get("splitbook_id") or "")
    assert splitbook_id

    try:
        ingest_resp = client.post(
            f"/splitbooks/{splitbook_id}/ingest",
            json={"path": str(source), "auto_optimize": True},
        )
        assert ingest_resp.status_code == 202, ingest_resp.text
        ingest_job_id = str(ingest_resp.json().get("job_id") or "")
        assert ingest_job_id
        _wait_job(client, ingest_job_id)

        extract_resp = client.post(
            f"/splitbooks/{splitbook_id}/extract_structured",
            json={
                "extract_provider": "rules",
                "pipeline_mode": "high_precision",
                "use_scene_judge": False,
            },
        )
        assert extract_resp.status_code == 202, extract_resp.text
        extract_job_id = str(extract_resp.json().get("job_id") or "")
        assert extract_job_id
        extract_job = _wait_job(client, extract_job_id, timeout_s=240.0)
        result = extract_job.get("result") if isinstance(extract_job.get("result"), dict) else {}
        assert int(result.get("scene_total") or 0) >= 1
        assert int(result.get("event_total") or 0) >= 1
        assert isinstance(result.get("pair_stats"), dict)
        qa = result.get("qa") if isinstance(result.get("qa"), dict) else {}
        assert isinstance(qa.get("gates"), dict)
        assert str(result.get("pipeline_mode") or "") == "high_precision"
        assert bool(result.get("use_scene_judge_effective")) is False

        legacy_resp = client.post(
            f"/splitbooks/{splitbook_id}/extract_structured",
            json={
                "extract_provider": "rules",
                "pipeline_mode": "legacy",
            },
        )
        assert legacy_resp.status_code == 202, legacy_resp.text
        legacy_job_id = str(legacy_resp.json().get("job_id") or "")
        assert legacy_job_id
        legacy_job = _wait_job(client, legacy_job_id, timeout_s=240.0)
        legacy_result = legacy_job.get("result") if isinstance(legacy_job.get("result"), dict) else {}
        assert str(legacy_result.get("pipeline_mode") or "") == "legacy"
        assert bool(legacy_result.get("use_scene_judge_effective")) is False
        legacy_pair_stats = legacy_result.get("pair_stats") if isinstance(legacy_result.get("pair_stats"), dict) else {}
        assert str(legacy_pair_stats.get("mode") or "") == "legacy"

        scenes_resp = client.get(f"/splitbooks/{splitbook_id}/scenes", params={"limit": 20})
        assert scenes_resp.status_code == 200, scenes_resp.text
        scenes_body = scenes_resp.json()
        rows = scenes_body.get("rows") if isinstance(scenes_body.get("rows"), list) else []
        assert rows
        first_scene = rows[0] if isinstance(rows[0], dict) else {}
        assert "candidate_json" in first_scene
        assert "prompt_version" in first_scene
        assert "model_id" in first_scene
        assert "confidence_overall" in first_scene

        outline_resp = client.get(f"/splitbooks/{splitbook_id}/outline")
        assert outline_resp.status_code == 200, outline_resp.text
        outline = outline_resp.json()
        assert isinstance(outline.get("chapters"), list)
        assert isinstance(outline.get("volumes"), list)
        assert isinstance(outline.get("book_outline"), dict)

        chapter_pack_resp = client.get(
            f"/splitbooks/{splitbook_id}/chapter_pack",
            params={"chapter_no": 1},
        )
        assert chapter_pack_resp.status_code == 200, chapter_pack_resp.text
        chapter_pack = chapter_pack_resp.json()
        assert isinstance(chapter_pack.get("events"), list)
    finally:
        client.delete(f"/splitbooks/{splitbook_id}")


def test_splitbook_writeback_batch_contract(client: httpx.Client, tmp_path: Path) -> None:
    source = tmp_path / "splitbook_writeback_batch.txt"
    source.write_text(
        (
            "第1章 初始异常\n"
            "清晨，林渊在城门外发现符文裂纹，却没有贸然触碰。\n\n"
            "第2章 冲突升级\n"
            "深夜，对手提前设下陷阱，林渊被迫反击并付出代价。\n\n"
            "第3章 线索回收\n"
            "翌日，前夜埋下的异常被触发，真相出现了第一层解释。\n"
        ),
        encoding="utf-8",
    )
    splitbook_name = f"wb-{uuid.uuid4().hex[:8]}"
    create_resp = client.post(
        "/splitbooks",
        json={
            "name": splitbook_name,
            "author": "qa",
            "source_path": str(source),
            "note": "writeback batch contract",
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    splitbook_id = str(create_resp.json().get("splitbook_id") or "")
    assert splitbook_id

    try:
        ingest_resp = client.post(
            f"/splitbooks/{splitbook_id}/ingest",
            json={"path": str(source), "auto_optimize": True},
        )
        assert ingest_resp.status_code == 202, ingest_resp.text
        ingest_job_id = str(ingest_resp.json().get("job_id") or "")
        assert ingest_job_id
        _wait_job(client, ingest_job_id)

        preview_resp = client.post(f"/splitbooks/{splitbook_id}/writeback_preview_batch", json={})
        assert preview_resp.status_code == 202, preview_resp.text
        preview_job_id = str(preview_resp.json().get("job_id") or "")
        assert preview_job_id
        preview_job = _wait_job(client, preview_job_id)
        preview_result = preview_job.get("result") if isinstance(preview_job.get("result"), dict) else {}
        assert str(preview_result.get("mode") or "") == "preview"
        assert int(preview_result.get("changed_total") or 0) >= 1
        preview_token = str(preview_result.get("preview_token") or "")
        assert preview_token

        confirm_resp = client.post(
            f"/splitbooks/{splitbook_id}/writeback_confirm_batch",
            json={"preview_token": preview_token},
        )
        assert confirm_resp.status_code == 202, confirm_resp.text
        confirm_job_id = str(confirm_resp.json().get("job_id") or "")
        assert confirm_job_id
        confirm_job = _wait_job(client, confirm_job_id)
        confirm_result = confirm_job.get("result") if isinstance(confirm_job.get("result"), dict) else {}
        assert str(confirm_result.get("mode") or "") == "confirm"
        assert int(confirm_result.get("applied_total") or 0) >= 1
        assert int(confirm_result.get("failed_total") or 0) == 0

        preview_resp_2 = client.post(f"/splitbooks/{splitbook_id}/writeback_preview_batch", json={})
        assert preview_resp_2.status_code == 202, preview_resp_2.text
        preview_job_2_id = str(preview_resp_2.json().get("job_id") or "")
        assert preview_job_2_id
        preview_job_2 = _wait_job(client, preview_job_2_id)
        preview_result_2 = preview_job_2.get("result") if isinstance(preview_job_2.get("result"), dict) else {}
        assert str(preview_result_2.get("mode") or "") == "preview"
        assert int(preview_result_2.get("changed_total") or 0) == 0
    finally:
        client.delete(f"/splitbooks/{splitbook_id}")


def test_story_engine_pack_and_audit_contract(client: httpx.Client) -> None:
    book_resp = client.post(
        "/books",
        json={"title": f"contract-book-{uuid.uuid4().hex[:6]}", "author": "qa", "language": "zh"},
    )
    assert book_resp.status_code == 200, book_resp.text
    book_id = str(book_resp.json().get("book_id") or "")
    assert book_id

    chapter_resp = client.post(
        f"/books/{book_id}/chapters",
        json={"chapter_no": 1, "title": "契约章节", "arc_id": "arc-1", "arc_index": 1},
    )
    assert chapter_resp.status_code == 200, chapter_resp.text
    chapter = chapter_resp.json()
    chapter_id = str(chapter.get("chapter_id") or "")
    chapter_no = int(chapter.get("chapter_no") or 1)
    assert chapter_id

    pack_resp = client.post(
        f"/books/{book_id}/engine/chapter_pack",
        json={
            "chapter_id": chapter_id,
            "chapter_no": chapter_no,
            "chapter_goal": "推进主线并保留悬念",
            "scene_count": 4,
            "suspense_type": "new_threat",
        },
    )
    assert pack_resp.status_code == 200, pack_resp.text
    pack_body = pack_resp.json()
    assert pack_body.get("ok") is True
    pack = pack_body.get("pack") or {}
    assert isinstance(pack.get("conflict_card"), dict)
    assert len(pack.get("scene_cards") or []) == 4

    audit_content = (
        "因为主角收到线索，所以他决定深夜前往废站。"
        "然而对手提前设下陷阱，冲突骤然升级。"
        "主角付出代价后勉强脱身，并发现更大的威胁？"
    )
    audit_resp = client.post(
        f"/books/{book_id}/engine/chapter_audit",
        json={
            "chapter_id": chapter_id,
            "chapter_no": chapter_no,
            "chapter_title": "契约章节",
            "content": audit_content,
            "threshold": 22,
        },
    )
    assert audit_resp.status_code == 200, audit_resp.text
    audit_body = audit_resp.json()
    assert audit_body.get("ok") is True
    audit_id = str(audit_body.get("audit_id") or "")
    assert audit_id
    assert isinstance(audit_body.get("score_map"), dict)

    repair_resp = client.post(
        f"/books/{book_id}/engine/chapter_repair_plan",
        json={"audit_id": audit_id},
    )
    assert repair_resp.status_code == 200, repair_resp.text
    repair_body = repair_resp.json()
    assert repair_body.get("ok") is True
    plan = repair_body.get("plan") or {}
    assert str(plan.get("audit_id") or "") == audit_id


def test_writing_memory_pack_and_writeback_contract(client: httpx.Client) -> None:
    book_resp = client.post(
        "/books",
        json={"title": f"memory-book-{uuid.uuid4().hex[:6]}", "author": "qa", "language": "zh"},
    )
    assert book_resp.status_code == 200, book_resp.text
    book_id = str(book_resp.json().get("book_id") or "")
    assert book_id

    chapter_resp = client.post(
        f"/books/{book_id}/chapters",
        json={"chapter_no": 1, "title": "记忆章节", "arc_id": "arc-memory", "arc_index": 1},
    )
    assert chapter_resp.status_code == 200, chapter_resp.text
    chapter = chapter_resp.json()
    chapter_id = str(chapter.get("chapter_id") or "")
    chapter_no = int(chapter.get("chapter_no") or 1)
    assert chapter_id

    session_set = client.post(
        f"/books/{book_id}/engine/memory/session",
        json={
            "session_key": "contract",
            "mode": "merge",
            "state": {
                "task_instruction": "保持角色设定与时间线一致",
                "hard_constraints": ["不得让主角无代价突破", "章末必须保留悬念"],
                "focus_entities": ["主角"],
            },
        },
    )
    assert session_set.status_code == 200, session_set.text
    assert session_set.json().get("ok") is True

    session_get = client.get(f"/books/{book_id}/engine/memory/session", params={"session_key": "contract"})
    assert session_get.status_code == 200, session_get.text
    state = session_get.json().get("state") or {}
    assert "hard_constraints" in state

    pack_resp = client.post(
        f"/books/{book_id}/engine/memory/pack",
        json={
            "session_key": "contract",
            "task_type": "write_chapter",
            "chapter_id": chapter_id,
            "chapter_no": chapter_no,
            "chapter_title": "记忆章节",
            "query": "主角在代价约束下推进冲突并埋伏笔",
        },
    )
    assert pack_resp.status_code == 200, pack_resp.text
    pack_body = pack_resp.json()
    assert pack_body.get("ok") is True
    assert isinstance((pack_body.get("memory_layers") or {}).get("hot"), dict)
    assembled = pack_body.get("context_assembled") or {}
    assert int(assembled.get("token_est") or 0) > 0

    writeback_resp = client.post(
        f"/books/{book_id}/engine/memory/writeback",
        json={
            "session_key": "contract",
            "chapter_id": chapter_id,
            "chapter_no": chapter_no,
            "chapter_title": "记忆章节",
            "writeback": True,
            "content": "清晨主角因规则限制选择隐忍。深夜他发现异常线索，却不知更大危机将至。",
        },
    )
    assert writeback_resp.status_code == 200, writeback_resp.text
    writeback_body = writeback_resp.json()
    assert writeback_body.get("ok") is True
    assert isinstance(writeback_body.get("checks"), list)
    assert isinstance(writeback_body.get("writeback_stats"), dict)
    assert isinstance(writeback_body.get("foreshadow_resolution_summary"), dict)
    assert isinstance(writeback_body.get("foreshadow_resolution_suggestions"), list)


def test_draft_workflow_memory_loop_contract(client: httpx.Client) -> None:
    book_resp = client.post(
        "/books",
        json={"title": f"workflow-memory-{uuid.uuid4().hex[:6]}", "author": "qa", "language": "zh"},
    )
    assert book_resp.status_code == 200, book_resp.text
    book_id = str(book_resp.json().get("book_id") or "")
    assert book_id

    chapter_resp = client.post(
        f"/books/{book_id}/chapters",
        json={"chapter_no": 1, "title": "工作流记忆章节", "arc_id": "arc-memory-loop", "arc_index": 1},
    )
    assert chapter_resp.status_code == 200, chapter_resp.text
    chapter_id = str(chapter_resp.json().get("chapter_id") or "")
    assert chapter_id

    run_resp = client.post(
        "/workflows/run",
        json={
            "workflow_id": "draft_runner_v1",
            "dry_run": True,
            "reuse_if_exists": False,
            "input": {
                "book_id": book_id,
                "chapter_id": chapter_id,
                "intent_confirmed": "验证 workflow memory pack/writeback 闭环",
                "force_stub_llm": True,
                "memory_pack_enabled": True,
                "memory_writeback_enabled": True,
                "memory_session_key": "contract-workflow",
            },
        },
    )
    assert run_resp.status_code == 200, run_resp.text
    run_body = run_resp.json()
    assert run_body.get("ok") is True
    run_id = str(run_body.get("run_id") or "")
    assert run_id

    detail_resp = client.get(f"/workflows/runs/{run_id}")
    assert detail_resp.status_code == 200, detail_resp.text
    detail = detail_resp.json()
    steps = detail.get("steps") or []
    assert isinstance(steps, list)
    step_by_node = {str((s or {}).get("node_id") or ""): (s or {}) for s in steps if isinstance(s, dict)}

    memory_pack_step = step_by_node.get("memory_pack") or {}
    assert memory_pack_step.get("status") == "succeeded"
    memory_pack_output = memory_pack_step.get("output") or {}
    memory_pack_status = memory_pack_output.get("memory_pack_status") or {}
    assert memory_pack_status.get("ok") is True
    signals = memory_pack_status.get("signals") or {}
    assert isinstance(signals, dict)
    assert isinstance(signals.get("task_types"), list)
    assert isinstance(signals.get("overdue_foreshadow_titles"), list)
    assert isinstance(signals.get("overdue_foreshadow_seeds"), list)

    compose_step = step_by_node.get("compose_prompt") or {}
    compose_output = compose_step.get("output") or {}
    prompt_text = str(compose_output.get("prompt") or "")
    assert "[MEMORY_CONTEXT]" in prompt_text

    writeback_step = step_by_node.get("memory_writeback") or {}
    assert writeback_step.get("status") == "succeeded"
    writeback_output = writeback_step.get("output") or {}
    writeback_report = writeback_output.get("memory_writeback_report") or {}
    assert writeback_report.get("skipped") is True
    assert writeback_report.get("reason") == "dry_run"


def test_story_engine_quality_metrics_and_regression_contract(client: httpx.Client) -> None:
    book_resp = client.post(
        "/books",
        json={"title": f"quality-book-{uuid.uuid4().hex[:6]}", "author": "qa", "language": "zh"},
    )
    assert book_resp.status_code == 200, book_resp.text
    book_id = str(book_resp.json().get("book_id") or "")
    assert book_id

    chapter_resp = client.post(
        f"/books/{book_id}/chapters",
        json={"chapter_no": 1, "title": "质量章节", "arc_id": "arc-quality", "arc_index": 1},
    )
    assert chapter_resp.status_code == 200, chapter_resp.text
    chapter = chapter_resp.json()
    chapter_id = str(chapter.get("chapter_id") or "")
    assert chapter_id

    writeback_resp = client.post(
        f"/books/{book_id}/engine/memory/writeback",
        json={
            "session_key": "quality-contract",
            "chapter_id": chapter_id,
            "chapter_no": 1,
            "chapter_title": "质量章节",
            "writeback": True,
            "content": "清晨主角遵守规则推进计划。对手突然反击，冲突升级，但他付出代价后稳住局面。章末出现新的悬念。",
        },
    )
    assert writeback_resp.status_code == 200, writeback_resp.text

    metrics_resp = client.get(f"/books/{book_id}/engine/quality/metrics", params={"checkpoint_limit": 120})
    assert metrics_resp.status_code == 200, metrics_resp.text
    metrics = metrics_resp.json()
    assert metrics.get("ok") is True
    assert isinstance(metrics.get("coverage"), dict)
    assert isinstance(metrics.get("consistency"), dict)
    assert isinstance(metrics.get("consistency_rates"), dict)
    assert isinstance(metrics.get("issue_histogram"), dict)

    regression_resp = client.post(
        f"/books/{book_id}/engine/quality/regression",
        json={
            "threshold": 22,
            "samples": [
                {
                    "chapter_no": 1,
                    "chapter_title": "质量样章",
                    "content": "主角收到情报后立即行动。敌人提前布置反制，冲突升级。主角付出明显代价后获得阶段线索，并留下新钩子。",
                    "expected_min_score": 0,
                }
            ],
        },
    )
    assert regression_resp.status_code == 200, regression_resp.text
    regression = regression_resp.json()
    assert isinstance(regression.get("results"), list)
    assert int(regression.get("total") or 0) == 1
    assert "pass_rate" in regression


def test_story_engine_model_route_contract(client: httpx.Client) -> None:
    book_resp = client.post(
        "/books",
        json={"title": f"route-book-{uuid.uuid4().hex[:6]}", "author": "qa", "language": "zh"},
    )
    assert book_resp.status_code == 200, book_resp.text
    book_id = str(book_resp.json().get("book_id") or "")
    assert book_id

    route_resp = client.post(
        f"/books/{book_id}/engine/model_route",
        json={
            "task_type": "write_chapter",
            "privacy_mode": "strict",
            "cost_mode": "balanced",
            "provider_health": {"local": True, "cloud": True},
        },
    )
    assert route_resp.status_code == 200, route_resp.text
    route_body = route_resp.json()
    assert route_body.get("ok") is True
    assert isinstance(route_body.get("selection"), dict)
    assert isinstance(route_body.get("fallback_chain"), list)
    assert str((route_body.get("policy") or {}).get("failure_downgrade") or "") in {"none", "local_to_cloud", "cloud_to_local"}
