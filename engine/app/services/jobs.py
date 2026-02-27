from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import text

from ..db import session_factory
from ..observability import get_logger, set_request_id, reset_request_id
from .event_bus import event_bus
from .ingest import run_ingest_job
from .similarity import run_similarity_guard_job, run_similarity_guard_text_job
from .book_tension import run_book_tension_analyze_job
from .template_evolution import run_template_evolve_job
from .splitbooks import (
    run_splitbook_build_profile_job,
    run_splitbook_build_templates_job,
    run_splitbook_embed_job,
    run_splitbook_extract_structured_job,
    run_splitbook_ingest_job,
    run_splitbook_writeback_batch_job,
)
from .storage import append_job_log
from .structure import run_extract_structure_beats_job, run_generate_structure_template_job
from .tension import run_apply_and_measure_job, run_eval_tension_job, run_tension_control_plan_job
from .draft_commit import run_commit_draft_job

logger = get_logger("job_runner")


class JobCanceledError(RuntimeError):
    pass


class JobRunner:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[tuple[UUID, str]] = asyncio.Queue()
        self.task: asyncio.Task | None = None
        self.stop_event = asyncio.Event()
        self.llm_semaphore = asyncio.Semaphore(1)
        self.embed_semaphore = asyncio.Semaphore(2)
        self.io_semaphore = asyncio.Semaphore(4)

    async def start(self) -> None:
        if self.task:
            return
        self.stop_event.clear()
        await self.recover_pending_jobs()
        self.task = asyncio.create_task(self.run())

    async def shutdown(self) -> None:
        self.stop_event.set()
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            finally:
                self.task = None

    async def enqueue(self, job_id: UUID, request_id: str) -> None:
        await self.queue.put((job_id, request_id))

    async def recover_pending_jobs(self) -> None:
        resumed_running = 0
        resumed_queued = 0
        try:
            async with session_factory() as session:
                res = await session.execute(
                    text(
                        """
                        SELECT job_id::text AS job_id, status, payload
                        FROM jobs
                        WHERE status IN ('queued', 'running')
                        ORDER BY created_at ASC
                        LIMIT 10000
                        """
                    )
                )
                rows = [dict(r) for r in res.mappings().all()]
                if not rows:
                    return

                for row in rows:
                    job_id_text = str(row.get("job_id") or "").strip()
                    if not job_id_text:
                        continue
                    try:
                        jid = UUID(job_id_text)
                    except ValueError:
                        continue
                    status = str(row.get("status") or "").strip().lower()
                    payload = row.get("payload") or {}
                    if not isinstance(payload, dict):
                        payload = {}
                    req_id = str(payload.get("request_id") or f"recover:{job_id_text[:8]}")

                    if status == "running":
                        resumed_running += 1
                        await session.execute(
                            text(
                                """
                                UPDATE jobs
                                SET status='queued',
                                    stage='QUEUED',
                                    progress_value=GREATEST(COALESCE(progress_value, 0.0), 0.01),
                                    progress=CAST(:progress AS jsonb),
                                    updated_at=now()
                                WHERE job_id=:job_id
                                """
                            ),
                            {
                                "job_id": job_id_text,
                                "progress": json.dumps(
                                    {
                                        "pct": 1,
                                        "phase": "queued",
                                        "message": "检测到引擎重启，任务已恢复为排队状态",
                                        "counters": {},
                                    }
                                ),
                            },
                        )
                        await append_job_log(
                            session,
                            job_id_text,
                            "WARN",
                            "RECOVER",
                            "检测到引擎重启，任务从 running 恢复为 queued，等待手动继续",
                        )
                    else:
                        resumed_queued += 1
                        await append_job_log(
                            session,
                            job_id_text,
                            "INFO",
                            "RECOVER",
                            "检测到引擎启动，queued 任务保留排队状态，等待手动继续",
                        )
                    await session.execute(
                        text(
                            """
                            UPDATE jobs
                            SET progress=CAST(:progress AS jsonb),
                                progress_value=GREATEST(COALESCE(progress_value, 0.0), 0.01),
                                updated_at=now()
                            WHERE job_id=:job_id
                            """
                        ),
                        {
                            "job_id": job_id_text,
                            "progress": json.dumps(
                                {
                                    "pct": 1,
                                    "phase": "queued",
                                    "message": "检测到引擎重启，任务保持排队，需手动继续",
                                    "counters": {},
                                }
                            ),
                        },
                    )
                await session.commit()
        except Exception as exc:
            logger.warning(
                "job.recover.skip",
                extra={
                    "request_id": "system",
                    "job_id": "-",
                    "job_type": "RECOVER",
                    "stage": "SKIP",
                    "meta": {"error": str(exc)},
                },
            )
            return

        logger.info(
            "job.recover",
            extra={
                "request_id": "system",
                "job_id": "-",
                "job_type": "RECOVER",
                "stage": "QUEUED",
                "meta": {
                    "total": resumed_running + resumed_queued,
                    "running_to_queued": resumed_running,
                    "queued_requeued": resumed_queued,
                    "manual_resume_required": True,
                },
            },
        )

    async def run(self) -> None:
        while not self.stop_event.is_set():
            job_id, request_id = await self.queue.get()
            await self._process(job_id, request_id)

    async def _process(self, job_id: UUID, request_id: str) -> None:
        token = set_request_id(request_id)
        async with session_factory() as session:
            data = await session.execute(
                text("SELECT capability_id, payload, status FROM jobs WHERE job_id=:job_id"),
                {"job_id": str(job_id)},
            )
            row = data.mappings().first()
            if not row:
                return
            capability_id = row["capability_id"]
            payload = row["payload"]
            status = str(row.get("status") or "").strip().lower()
            if status not in {"queued", "running"}:
                await append_job_log(
                    session,
                    str(job_id),
                    "INFO",
                    "SKIP",
                    f"任务状态={status}，跳过执行",
                )
                await session.commit()
                logger.info(
                    "job.skip",
                    extra={
                        "request_id": request_id,
                        "job_id": str(job_id),
                        "job_type": str(capability_id).upper(),
                        "stage": "SKIP",
                        "meta": {"status": status},
                    },
                )
                return
            request_id = str((payload or {}).get("request_id") or request_id)

            await session.execute(
                text(
                    """
                    UPDATE jobs
                    SET status='running', stage='RUNNING', progress_value=0.01, progress=CAST(:progress AS jsonb), updated_at=now()
                    WHERE job_id=:job_id
                    """
                ),
                {
                    "job_id": str(job_id),
                    "progress": json.dumps({"pct": 1, "phase": "running", "message": "任务已开始", "counters": {}}),
                },
            )
            await session.commit()
            logger.info(
                "job.start",
                extra={
                    "request_id": request_id,
                    "job_id": str(job_id),
                    "job_type": capability_id.upper(),
                    "stage": "RUNNING",
                    "meta": {"capability_id": capability_id},
                },
            )

        async def run_with_limit(kind: str, coro):
            if kind == "LLM":
                sem = self.llm_semaphore
            elif kind == "EMBED":
                sem = self.embed_semaphore
            elif kind == "IO":
                sem = self.io_semaphore
            else:
                return await coro()
            async with sem:
                return await coro()

        def capability_limit(capability: str) -> str:
            if capability in {
                "eval.conflict_tension.v1",
                "control_plan.tension.v1",
                "similarity.guard.v1",
                "similarity.guard.text.v1",
                "extract.structure_beats.v1",
                "generate.structure_template.v1",
            }:
                return "LLM"
            if capability in {"embed.book.v1"}:
                return "EMBED"
            if capability in {"ingest.book.v1"}:
                return "IO"
            if capability in {
                "splitbook.ingest.v1",
                "splitbook.embed.v1",
                "splitbook.extract_structured.v1",
                "splitbook.build_templates.v1",
                "splitbook.build_profile.v1",
                "splitbook.writeback_batch.v1",
            }:
                return "IO"
            return "NONE"

        async def on_progress(pct: int, phase: str, message: str) -> None:
            payload_json = {"pct": pct, "phase": phase, "message": message, "counters": {}}
            async with session_factory() as session:
                status_row = await session.execute(
                    text("SELECT status FROM jobs WHERE job_id=:job_id"),
                    {"job_id": str(job_id)},
                )
                current_status = str(status_row.scalar() or "").strip().lower()
                if current_status == "canceled":
                    await append_job_log(session, str(job_id), "WARN", "CANCELED", "检测到用户中止，停止后续进度写入")
                    await session.commit()
                    raise JobCanceledError(f"JOB_CANCELED:{job_id}")
                await session.execute(
                    text(
                        """
                        UPDATE jobs
                        SET stage=:stage, progress_value=:progress_value, progress=CAST(:progress AS jsonb), updated_at=now()
                        WHERE job_id=:job_id
                        """
                    ),
                    {
                        "job_id": str(job_id),
                        "stage": str(phase).upper(),
                        "progress_value": max(0.0, min(1.0, pct / 100)),
                        "progress": json.dumps(payload_json),
                    },
                )
                await session.commit()
            await event_bus.publish(
                str(job_id),
                "job.progress",
                {"job_id": str(job_id), "progress": payload_json, "timestamp": datetime.now(timezone.utc).isoformat(), "request_id": request_id},
            )
            logger.info(
                "job.progress",
                extra={
                    "request_id": request_id,
                    "job_id": str(job_id),
                    "job_type": capability_id.upper(),
                    "stage": str(phase).upper(),
                    "meta": {"pct": pct, "message": message},
                },
            )

        async def on_log(level: str, phase: str, message: str) -> None:
            async with session_factory() as session:
                await append_job_log(session, str(job_id), level, phase, message)
            await event_bus.publish(
                str(job_id),
                "job.log",
                {
                    "job_id": str(job_id),
                    "request_id": request_id,
                    "level": level,
                    "phase": phase,
                    "message": message,
                    "ts": datetime.now(timezone.utc).isoformat(),
                },
            )
            log_fn = logger.info if level.upper() in {"INFO"} else logger.warning if level.upper() in {"WARN", "WARNING"} else logger.error
            log_fn(
                "job.log",
                extra={
                    "request_id": request_id,
                    "job_id": str(job_id),
                    "job_type": capability_id.upper(),
                    "stage": str(phase).upper(),
                    "meta": {"level": level, "message": message},
                },
            )

        try:
            async with session_factory() as session:
                async def dispatch():
                    if capability_id == "ingest.book.v1":
                        return await run_ingest_job(session, payload, on_progress=on_progress, on_log=on_log)
                    if capability_id == "extract.structure_beats.v1":
                        return await run_extract_structure_beats_job(session, payload, on_progress=on_progress, on_log=on_log)
                    if capability_id == "generate.structure_template.v1":
                        return await run_generate_structure_template_job(session, payload, on_progress=on_progress, on_log=on_log)
                    if capability_id == "eval.conflict_tension.v1":
                        return await run_eval_tension_job(session, payload, on_progress=on_progress, on_log=on_log)
                    if capability_id == "control_plan.tension.v1":
                        return await run_tension_control_plan_job(session, payload, on_progress=on_progress, on_log=on_log)
                    if capability_id == "apply.measure.v1":
                        return await run_apply_and_measure_job(session, payload, on_progress=on_progress, on_log=on_log)
                    if capability_id == "similarity.guard.v1":
                        return await run_similarity_guard_job(session, payload, on_progress=on_progress, on_log=on_log)
                    if capability_id == "similarity.guard.text.v1":
                        return await run_similarity_guard_text_job(session, payload, on_progress=on_progress, on_log=on_log)
                    if capability_id == "book.tension.analyze.v1":
                        return await run_book_tension_analyze_job(session, payload, on_progress=on_progress, on_log=on_log)
                    if capability_id == "template.evolve.v1":
                        return await run_template_evolve_job(session, payload, on_progress=on_progress, on_log=on_log)
                    if capability_id == "draft.commit.v1":
                        return await run_commit_draft_job(session, payload, on_progress=on_progress, on_log=on_log)
                    if capability_id == "splitbook.ingest.v1":
                        return await run_splitbook_ingest_job(session, payload, on_progress=on_progress, on_log=on_log)
                    if capability_id == "splitbook.embed.v1":
                        return await run_splitbook_embed_job(session, payload, on_progress=on_progress, on_log=on_log)
                    if capability_id == "splitbook.extract_structured.v1":
                        return await run_splitbook_extract_structured_job(session, payload, on_progress=on_progress, on_log=on_log)
                    if capability_id == "splitbook.build_templates.v1":
                        return await run_splitbook_build_templates_job(session, payload, on_progress=on_progress, on_log=on_log)
                    if capability_id == "splitbook.build_profile.v1":
                        return await run_splitbook_build_profile_job(session, payload, on_progress=on_progress, on_log=on_log)
                    if capability_id == "splitbook.writeback_batch.v1":
                        return await run_splitbook_writeback_batch_job(session, payload, on_progress=on_progress, on_log=on_log)
                    raise RuntimeError(f"UNSUPPORTED_CAPABILITY:{capability_id}")

                result = await run_with_limit(capability_limit(capability_id), dispatch)

            run_id = uuid4()
            async with session_factory() as session:
                status_row = await session.execute(
                    text("SELECT status FROM jobs WHERE job_id=:job_id"),
                    {"job_id": str(job_id)},
                )
                current_status = str(status_row.scalar() or "").strip().lower()
                if current_status == "canceled":
                    await append_job_log(session, str(job_id), "WARN", "CANCELED", "任务已被中止，忽略后续成功回写")
                    await session.execute(
                        text(
                            """
                            UPDATE jobs
                            SET status='canceled',
                                stage='CANCELED',
                                progress=CAST(:progress AS jsonb),
                                updated_at=now()
                            WHERE job_id=:job_id
                            """
                        ),
                        {
                            "job_id": str(job_id),
                            "progress": json.dumps({"pct": 100, "phase": "canceled", "message": "用户已中止任务", "counters": {}}),
                        },
                    )
                    await session.commit()
                    await event_bus.publish(
                        str(job_id),
                        "job.canceled",
                        {"job_id": str(job_id), "request_id": request_id, "ts": datetime.now(timezone.utc).isoformat()},
                    )
                    logger.warning(
                        "job.canceled",
                        extra={
                            "request_id": request_id,
                            "job_id": str(job_id),
                            "job_type": capability_id.upper(),
                            "stage": "CANCELED",
                            "meta": {"reason": "canceled_before_finalize"},
                        },
                    )
                    return
                await session.execute(
                    text(
                        """
                        INSERT INTO runs(run_id, capability_id, status, input, output)
                        VALUES (:run_id, :capability_id, 'succeeded', CAST(:input AS jsonb), CAST(:output AS jsonb))
                        """
                    ),
                    {"run_id": str(run_id), "capability_id": capability_id, "input": json.dumps(payload), "output": json.dumps(result)},
                )
                await session.execute(
                    text(
                        """
                        UPDATE jobs
                        SET status='succeeded', stage='DONE', progress_value=1.0, run_id=:run_id, result=CAST(:result AS jsonb), updated_at=now(),
                            progress=CAST(:progress AS jsonb)
                        WHERE job_id=:job_id
                        """
                    ),
                    {
                        "run_id": str(run_id),
                        "job_id": str(job_id),
                        "result": json.dumps(result),
                        "progress": json.dumps({"pct": 100, "phase": "done", "message": "完成", "counters": {}}),
                    },
                )
                await session.commit()

            await event_bus.publish(
                str(job_id),
                "job.done",
                {"job_id": str(job_id), "run_id": str(run_id), "summary": result, "ts": datetime.now(timezone.utc).isoformat()},
            )
            logger.info(
                "job.done",
                extra={
                    "request_id": request_id,
                    "job_id": str(job_id),
                    "job_type": capability_id.upper(),
                    "stage": "DONE",
                    "meta": {"run_id": str(run_id)},
                },
            )
        except JobCanceledError:
            async with session_factory() as session:
                await session.execute(
                    text(
                        """
                        UPDATE jobs
                        SET status='canceled',
                            stage='CANCELED',
                            progress=CAST(:progress AS jsonb),
                            updated_at=now()
                        WHERE job_id=:job_id
                        """
                    ),
                    {
                        "job_id": str(job_id),
                        "progress": json.dumps({"pct": 100, "phase": "canceled", "message": "用户已中止任务", "counters": {}}),
                    },
                )
                await append_job_log(session, str(job_id), "WARN", "CANCELED", "任务执行已中止并退出")
                await session.commit()
            await event_bus.publish(
                str(job_id),
                "job.canceled",
                {"job_id": str(job_id), "request_id": request_id, "ts": datetime.now(timezone.utc).isoformat()},
            )
            logger.warning(
                "job.canceled",
                extra={
                    "request_id": request_id,
                    "job_id": str(job_id),
                    "job_type": capability_id.upper(),
                    "stage": "CANCELED",
                    "meta": {"reason": "progress_interrupt"},
                },
            )
        except Exception as exc:
            err = {"code": "JOB_FAILED", "message": str(exc), "details": {}, "request_id": request_id}
            async with session_factory() as session:
                status_row = await session.execute(
                    text("SELECT status FROM jobs WHERE job_id=:job_id"),
                    {"job_id": str(job_id)},
                )
                current_status = str(status_row.scalar() or "").strip().lower()
                if current_status == "canceled":
                    await append_job_log(session, str(job_id), "WARN", "CANCELED", "任务已中止，忽略失败回写")
                    await session.commit()
                    await event_bus.publish(
                        str(job_id),
                        "job.canceled",
                        {"job_id": str(job_id), "request_id": request_id, "ts": datetime.now(timezone.utc).isoformat()},
                    )
                    logger.warning(
                        "job.canceled",
                        extra={
                            "request_id": request_id,
                            "job_id": str(job_id),
                            "job_type": capability_id.upper(),
                            "stage": "CANCELED",
                            "meta": {"reason": "canceled_during_exception"},
                        },
                    )
                    return
                await session.execute(
                    text(
                        """
                        UPDATE jobs
                        SET status='failed', stage='FAILED', error=CAST(:error AS jsonb), updated_at=now()
                        WHERE job_id=:job_id
                        """
                    ),
                    {"job_id": str(job_id), "error": json.dumps(err)},
                )
                await session.execute(
                    text(
                        """
                        INSERT INTO runs(run_id, capability_id, status, input, output)
                        VALUES (:run_id, :capability_id, 'failed', CAST(:input AS jsonb), CAST(:output AS jsonb))
                        """
                    ),
                    {
                        "run_id": str(uuid4()),
                        "capability_id": capability_id,
                        "input": json.dumps(payload),
                        "output": json.dumps({"error": err}),
                    },
                )
                await session.commit()
            await event_bus.publish(
                str(job_id),
                "job.failed",
                {"job_id": str(job_id), "error": err, "ts": datetime.now(timezone.utc).isoformat()},
            )
            logger.error(
                "job.failed",
                extra={
                    "request_id": request_id,
                    "job_id": str(job_id),
                    "job_type": capability_id.upper(),
                    "stage": "FAILED",
                    "meta": {"error_code": err["code"], "error": err["message"]},
                },
            )
        finally:
            reset_request_id(token)


job_runner = JobRunner()
