from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .style_evolution import get_latest_style_evolution
from .search import hybrid_search


CONFLICT_TEMPLATE_LIBRARY: dict[str, dict[str, str]] = {
    "information_gap": {
        "label": "信息差冲突",
        "upgrade": "通过误导信息与真相落差制造反差升级。",
        "payoff": "揭露关键信息，触发立场反转或策略切换。",
        "cliffhanger": "给出更大信息缺口，逼迫角色进入下一轮调查。",
    },
    "interest": {
        "label": "利益冲突",
        "upgrade": "资源稀缺或分配不公，迫使角色做取舍。",
        "payoff": "阶段性赢得资源，但同步引入新的代价与敌意。",
        "cliffhanger": "对手抬高赌注，主角利益链条被卡住。",
    },
    "rules": {
        "label": "规则冲突",
        "upgrade": "新规则上桌，旧打法失效。",
        "payoff": "角色破解规则或找到规则漏洞。",
        "cliffhanger": "规则再次升级，要求主角付出额外成本。",
    },
    "moral": {
        "label": "道德冲突",
        "upgrade": "救谁/舍谁出现不可两全选择。",
        "payoff": "角色做出选择，价值观明确但关系受损。",
        "cliffhanger": "选择后果回流，下一章必须承担。",
    },
    "emotion": {
        "label": "情感冲突",
        "upgrade": "误解、亏欠或背叛推动关系恶化。",
        "payoff": "情绪爆发后达成阶段和解或彻底决裂。",
        "cliffhanger": "关系状态变化带来新的外部威胁。",
    },
    "power": {
        "label": "战力冲突",
        "upgrade": "强弱差扩大，主角被迫变招。",
        "payoff": "以弱制强完成破局，并展示代价机制。",
        "cliffhanger": "更高层级敌人登场，压制感升级。",
    },
}

CONFLICT_ORDER = ["information_gap", "interest", "rules", "moral", "emotion", "power"]
CONFLICT_WORDS = ["冲突", "对抗", "危机", "压制", "反击", "威胁", "反转"]
PAYOFF_WORDS = ["收获", "突破", "回收", "揭露", "反转", "解决", "兑现"]
CAUSAL_WORDS = ["因为", "所以", "因此", "于是", "导致", "结果", "为了", "随后"]
RULE_WORDS = ["规则", "限制", "代价", "禁令", "体系", "法则", "契约"]
SUSPENSE_MARKERS = ["？", "?", "悬", "未完", "下一章", "但", "然而"]
NAME_RE = re.compile(r"[\u4e00-\u9fff]{2,4}")
FORESHADOW_HINT_WORDS = ["异样", "隐约", "不对劲", "似乎", "却不知", "伏笔", "预示", "埋下"]
TIME_CONFLICT_WORD_GROUPS: list[set[str]] = [
    {"清晨", "早晨", "黎明"},
    {"深夜", "夜里", "午夜"},
]
WRITING_MEMORY_SCHEMA_VERSION = "writing_memory_pack_v1"
WRITING_MEMORY_PROMPT_VERSION = "writing_memory_prompt_v1"
TRUTH_LAYER_SCHEMA_VERSION = "truth_layer_v1"
TRUTH_LAYER_PROMPT_VERSION = "truth_layer_prompt_v1"
AI_SMELL_PHRASES = [
    "首先",
    "其次",
    "最后",
    "总之",
    "值得注意的是",
    "可以看到",
    "不难发现",
    "由此可见",
    "与此同时",
]
ABILITY_OVERFLOW_MARKERS = [
    "无代价",
    "零代价",
    "瞬间无敌",
    "直接满级",
    "无限强化",
    "毫无上限",
]
PERSONA_BREAK_MARKERS = [
    "不择手段",
    "违背底线",
    "背弃承诺",
    "毫无原则",
    "完全失控",
]
COPY_NGRAM_N = 8
COPY_RISK_MID = 0.14
COPY_RISK_HIGH = 0.22


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp_int(raw: Any, default: int, low: int, high: int) -> int:
    try:
        value = int(raw)
    except Exception:
        value = default
    return max(low, min(high, value))


def _safe_float(raw: Any, default: float = 0.0) -> float:
    try:
        return float(raw)
    except Exception:
        return default


def _safe_int(raw: Any, default: int = 0) -> int:
    try:
        return int(raw)
    except Exception:
        return default


def _text_head(text_value: str, limit: int = 160) -> str:
    txt = str(text_value or "").strip()
    if len(txt) <= limit:
        return txt
    return txt[: max(20, limit - 1)].rstrip() + "…"


def _tokenize_terms(text_value: str, *, max_terms: int = 160) -> list[str]:
    txt = str(text_value or "").lower()
    if not txt:
        return []
    terms = re.findall(r"[\u4e00-\u9fff]{1,4}|[a-z0-9_]{2,32}", txt)
    out: list[str] = []
    seen: set[str] = set()
    for term in terms:
        t = term.strip()
        if not t or t in seen:
            continue
        out.append(t)
        seen.add(t)
        if len(out) >= max_terms:
            break
    return out


def _lexical_overlap_score(query_text: str, candidate_text: str) -> float:
    q_terms = set(_tokenize_terms(query_text, max_terms=120))
    c_terms = set(_tokenize_terms(candidate_text, max_terms=200))
    if not q_terms or not c_terms:
        return 0.0
    inter = len(q_terms & c_terms)
    union = len(q_terms | c_terms) or 1
    jaccard = inter / union
    contain_bonus = 0.15 if any(term in candidate_text for term in list(q_terms)[:8]) else 0.0
    return round(min(1.0, jaccard + contain_bonus), 6)


def _safe_json_dict(raw: Any) -> dict[str, Any]:
    return raw if isinstance(raw, dict) else {}


def _safe_json_list(raw: Any) -> list[Any]:
    return raw if isinstance(raw, list) else []


def _calc_sentence_metrics(content: str) -> dict[str, float]:
    txt = str(content or "")
    sentences = [seg.strip() for seg in re.split(r"[。！？!?]", txt) if seg.strip()]
    lens = [len(seg) for seg in sentences]
    count = len(lens)
    avg_len = (sum(lens) / count) if count else 0.0
    short_ratio = (sum(1 for value in lens if value <= 12) / count) if count else 0.0
    paragraphs = [seg for seg in txt.splitlines() if seg.strip()]
    para_avg = (count / max(1, len(paragraphs))) if paragraphs else 0.0
    return {
        "sentence_count": float(count),
        "sentence_avg_len": float(avg_len),
        "short_sentence_ratio": float(short_ratio),
        "paragraph_avg_sentences": float(para_avg),
    }


def _extract_card_anchor_value(card: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = str(card.get(key) or "").strip()
        if value:
            return value
    return ""


def _normalize_text_for_overlap(text_value: str, *, limit_chars: int = 2400) -> str:
    compact = re.sub(r"\s+", "", str(text_value or ""))
    if limit_chars > 0:
        return compact[:limit_chars]
    return compact


def _ngram_overlap_ratio(text_a: str, text_b: str, *, n: int = COPY_NGRAM_N) -> float:
    a = _normalize_text_for_overlap(text_a)
    b = _normalize_text_for_overlap(text_b)
    if len(a) < n or len(b) < n:
        return 0.0
    a_set = {a[idx : idx + n] for idx in range(len(a) - n + 1)}
    b_set = {b[idx : idx + n] for idx in range(len(b) - n + 1)}
    if not a_set or not b_set:
        return 0.0
    return float(len(a_set & b_set) / max(1, len(a_set)))


def _build_humanization_hints(
    *,
    content: str,
    ai_phrase_hits: int,
    repeated_prefix: int,
    current_metrics: dict[str, Any],
) -> list[str]:
    hints: list[str] = []
    if ai_phrase_hits >= 2:
        hints.append("删掉“首先/其次/总之”类逻辑提示词，改成情境动作与角色反应。")
    if repeated_prefix >= 3:
        hints.append("打散连续同起句，优先用动作、对话、感官切换句式。")
    avg_len = _safe_float(current_metrics.get("sentence_avg_len"), 0.0)
    short_ratio = _safe_float(current_metrics.get("short_sentence_ratio"), 0.0)
    if avg_len >= 34:
        hints.append("长句占比偏高，关键冲突段改用短句提速。")
    if short_ratio >= 0.72:
        hints.append("碎句偏多，关键情绪段补充完整复句承载张力。")
    if _safe_int(current_metrics.get("sentence_count"), 0) >= 10:
        hints.append("每 3-4 句插入一个具象细节（触觉/声响/微动作），减少解释性叙述。")
    return hints[:6]


async def _run_inline_anti_copy_guard(
    session: AsyncSession,
    *,
    book_id: str,
    content: str,
    top_k: int = 8,
) -> dict[str, Any]:
    query = _text_head(content, 220)
    if not query:
        return {
            "risk": "low",
            "mode": "skipped_empty_query",
            "max_ngram_overlap": 0.0,
            "hits": [],
            "rewrite_policy": [],
        }
    recall_mode = "vector+bm25_recall"
    try:
        recall_hits = await hybrid_search(
            session,
            query,
            book_id,
            top_k=max(4, min(16, top_k)),
            hybrid=True,
            vector_weight=0.68,
            keyword_weight=0.32,
        )
    except Exception:
        recall_mode = "bm25_recall_fallback"
        try:
            recall_hits = await hybrid_search(
                session,
                query,
                book_id,
                top_k=max(4, min(16, top_k)),
                hybrid=False,
                vector_weight=0.0,
                keyword_weight=1.0,
            )
        except Exception:
            recall_mode = "recall_failed"
            recall_hits = []

    chunk_text_cache: dict[str, str] = {}
    scored_hits: list[dict[str, Any]] = []
    for row in recall_hits[: max(4, min(16, top_k))]:
        chunk_id = str(row.get("chunk_id") or "").strip()
        chapter_no = _safe_int(row.get("chapter_order"), 0)
        raw_text = ""
        if chunk_id:
            if chunk_id not in chunk_text_cache:
                chunk_row = (
                    await session.execute(
                        text(
                            """
                            SELECT text
                            FROM chunk
                            WHERE chunk_id=CAST(:chunk_id AS uuid)
                            LIMIT 1
                            """
                        ),
                        {"chunk_id": chunk_id},
                    )
                ).mappings().first()
                chunk_text_cache[chunk_id] = str((chunk_row or {}).get("text") or "")
            raw_text = chunk_text_cache.get(chunk_id, "")
        if not raw_text:
            raw_text = str(row.get("snippet") or "")
        overlap = _ngram_overlap_ratio(content, raw_text, n=COPY_NGRAM_N)
        scored_hits.append(
            {
                "chunk_id": chunk_id,
                "chapter_no": chapter_no,
                "source_score": round(_safe_float(row.get("score"), 0.0), 6),
                "ngram_overlap": round(overlap, 6),
                "snippet": _text_head(str(row.get("snippet") or ""), 160),
            }
        )
    scored_hits.sort(key=lambda x: (_safe_float(x.get("ngram_overlap"), 0.0), _safe_float(x.get("source_score"), 0.0)), reverse=True)
    top_hits = scored_hits[:6]
    max_overlap = max([_safe_float(x.get("ngram_overlap"), 0.0) for x in top_hits] or [0.0])
    risk = "high" if max_overlap >= COPY_RISK_HIGH else ("mid" if max_overlap >= COPY_RISK_MID else "low")
    rewrite_policy: list[str] = []
    if risk != "low":
        rewrite_policy = [
            "保持事实不变，重排句序并改写叙述视角。",
            "替换标志性短语与比喻，避免连续字面复现。",
            "优先用角色动作/后果表达信息，而非复述来源句。",
        ]
    return {
        "risk": risk,
        "mode": recall_mode,
        "max_ngram_overlap": round(max_overlap, 6),
        "hits": top_hits,
        "rewrite_policy": rewrite_policy,
    }


def _to_uuid_str(raw: Any) -> str | None:
    v = str(raw or "").strip()
    return v or None


async def ensure_story_engine_tables(session: AsyncSession) -> None:
    ddl = [
        """
        CREATE TABLE IF NOT EXISTS story_bible_proposal (
          proposal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
          proposal_type TEXT NOT NULL,
          entity_key TEXT NOT NULL DEFAULT '',
          title TEXT NOT NULL DEFAULT '',
          payload JSONB NOT NULL DEFAULT '{}'::jsonb,
          status TEXT NOT NULL DEFAULT 'pending',
          reason TEXT NOT NULL DEFAULT '',
          review_note TEXT NOT NULL DEFAULT '',
          created_by TEXT NOT NULL DEFAULT 'user',
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_story_bible_proposal_book_status ON story_bible_proposal(book_id, status, created_at DESC)",
        """
        CREATE TABLE IF NOT EXISTS chapter_scene_pack (
          pack_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
          chapter_id UUID NULL REFERENCES chapter(chapter_id) ON DELETE SET NULL,
          chapter_no INTEGER NULL,
          chapter_title TEXT NOT NULL DEFAULT '',
          conflict_type TEXT NOT NULL DEFAULT '',
          payload JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_chapter_scene_pack_book_no ON chapter_scene_pack(book_id, chapter_no, created_at DESC)",
        """
        CREATE TABLE IF NOT EXISTS chapter_audit_snapshot (
          audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
          chapter_id UUID NULL REFERENCES chapter(chapter_id) ON DELETE SET NULL,
          chapter_no INTEGER NULL,
          chapter_title TEXT NOT NULL DEFAULT '',
          total_score INTEGER NOT NULL DEFAULT 0,
          threshold INTEGER NOT NULL DEFAULT 22,
          status TEXT NOT NULL DEFAULT 'needs_rework',
          score_map JSONB NOT NULL DEFAULT '{}'::jsonb,
          issues JSONB NOT NULL DEFAULT '[]'::jsonb,
          repair_plan JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_chapter_audit_snapshot_book_no ON chapter_audit_snapshot(book_id, chapter_no, created_at DESC)",
        """
        CREATE TABLE IF NOT EXISTS writing_session_state (
          state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
          session_key TEXT NOT NULL DEFAULT 'default',
          state JSONB NOT NULL DEFAULT '{}'::jsonb,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE(book_id, session_key)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_writing_session_state_book_time ON writing_session_state(book_id, updated_at DESC)",
        """
        CREATE TABLE IF NOT EXISTS writing_memory_checkpoint (
          checkpoint_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
          chapter_id UUID NULL REFERENCES chapter(chapter_id) ON DELETE SET NULL,
          chapter_no INTEGER NULL,
          task_type TEXT NOT NULL DEFAULT 'write_chapter',
          input_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
          output_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
          quality JSONB NOT NULL DEFAULT '{}'::jsonb,
          schema_version TEXT NOT NULL DEFAULT 'writing_memory_pack_v1',
          prompt_version TEXT NOT NULL DEFAULT 'writing_memory_prompt_v1',
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_writing_memory_checkpoint_book_task ON writing_memory_checkpoint(book_id, task_type, created_at DESC)",
        "ALTER TABLE chapter_fact ADD COLUMN IF NOT EXISTS evidence_ref JSONB NOT NULL DEFAULT '{}'::jsonb",
        "ALTER TABLE chapter_fact ADD COLUMN IF NOT EXISTS schema_version TEXT NOT NULL DEFAULT 'writing_memory_pack_v1'",
        "ALTER TABLE chapter_fact ADD COLUMN IF NOT EXISTS prompt_version TEXT NOT NULL DEFAULT 'writing_memory_prompt_v1'",
        "ALTER TABLE chapter_timeline_event ADD COLUMN IF NOT EXISTS evidence_ref JSONB NOT NULL DEFAULT '{}'::jsonb",
        "ALTER TABLE chapter_timeline_event ADD COLUMN IF NOT EXISTS schema_version TEXT NOT NULL DEFAULT 'writing_memory_pack_v1'",
        "ALTER TABLE chapter_timeline_event ADD COLUMN IF NOT EXISTS prompt_version TEXT NOT NULL DEFAULT 'writing_memory_prompt_v1'",
        "ALTER TABLE world_fact ADD COLUMN IF NOT EXISTS evidence JSONB NOT NULL DEFAULT '{}'::jsonb",
        "ALTER TABLE world_fact ADD COLUMN IF NOT EXISTS schema_version TEXT NOT NULL DEFAULT 'truth_layer_v1'",
        "ALTER TABLE world_fact ADD COLUMN IF NOT EXISTS prompt_version TEXT NOT NULL DEFAULT 'truth_layer_prompt_v1'",
        "ALTER TABLE timeline_event ADD COLUMN IF NOT EXISTS evidence JSONB NOT NULL DEFAULT '{}'::jsonb",
        "ALTER TABLE timeline_event ADD COLUMN IF NOT EXISTS schema_version TEXT NOT NULL DEFAULT 'truth_layer_v1'",
        "ALTER TABLE timeline_event ADD COLUMN IF NOT EXISTS prompt_version TEXT NOT NULL DEFAULT 'truth_layer_prompt_v1'",
    ]
    for sql in ddl:
        await session.execute(text(sql))
    await session.commit()


async def get_writing_session_state(
    session: AsyncSession,
    book_id: str,
    *,
    session_key: str = "default",
) -> dict[str, Any]:
    await ensure_story_engine_tables(session)
    key = str(session_key or "default").strip() or "default"
    row = (
        await session.execute(
            text(
                """
                SELECT state_id::text AS state_id, state, updated_at
                FROM writing_session_state
                WHERE book_id=CAST(:book_id AS uuid) AND session_key=:session_key
                LIMIT 1
                """
            ),
            {"book_id": book_id, "session_key": key},
        )
    ).mappings().first()
    state = _safe_json_dict((row or {}).get("state"))
    return {
        "book_id": book_id,
        "session_key": key,
        "state_id": str((row or {}).get("state_id") or ""),
        "state": state,
        "updated_at": str((row or {}).get("updated_at") or ""),
        "generated_at": _now_iso(),
    }


async def upsert_writing_session_state(session: AsyncSession, book_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    await ensure_story_engine_tables(session)
    key = str(payload.get("session_key") or "default").strip() or "default"
    mode = str(payload.get("mode") or "merge").strip().lower()
    state_in = _safe_json_dict(payload.get("state"))
    current = await get_writing_session_state(session, book_id, session_key=key)
    current_state = _safe_json_dict(current.get("state"))
    if mode == "replace":
        next_state = dict(state_in)
    else:
        next_state = {**current_state, **state_in}
    next_state["session_key"] = key
    next_state["updated_at"] = _now_iso()

    row = (
        await session.execute(
            text(
                """
                INSERT INTO writing_session_state(book_id, session_key, state, updated_at)
                VALUES (CAST(:book_id AS uuid), :session_key, CAST(:state AS jsonb), now())
                ON CONFLICT (book_id, session_key)
                DO UPDATE SET
                  state=EXCLUDED.state,
                  updated_at=now()
                RETURNING state_id::text AS state_id, updated_at
                """
            ),
            {"book_id": book_id, "session_key": key, "state": json.dumps(next_state, ensure_ascii=False)},
        )
    ).mappings().first()
    await session.commit()
    return {
        "ok": True,
        "book_id": book_id,
        "session_key": key,
        "state_id": str((row or {}).get("state_id") or ""),
        "state": next_state,
        "updated_at": str((row or {}).get("updated_at") or ""),
        "generated_at": _now_iso(),
    }


async def _resolve_chapter_context(session: AsyncSession, book_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    chapter_id = _to_uuid_str(payload.get("chapter_id"))
    chapter_no = _safe_int(payload.get("chapter_no"), 0) or None
    chapter_title = str(payload.get("chapter_title") or "").strip()
    row = None
    if chapter_id:
        row = (
            await session.execute(
                text(
                    """
                    SELECT chapter_id::text AS chapter_id, "order" AS chapter_no, title
                    FROM chapter
                    WHERE chapter_id=CAST(:chapter_id AS uuid) AND book_id=CAST(:book_id AS uuid)
                    LIMIT 1
                    """
                ),
                {"chapter_id": chapter_id, "book_id": book_id},
            )
        ).mappings().first()
    elif chapter_no:
        row = (
            await session.execute(
                text(
                    """
                    SELECT chapter_id::text AS chapter_id, "order" AS chapter_no, title
                    FROM chapter
                    WHERE book_id=CAST(:book_id AS uuid) AND "order"=:chapter_no
                    LIMIT 1
                    """
                ),
                {"book_id": book_id, "chapter_no": int(chapter_no)},
            )
        ).mappings().first()
    if row:
        chapter_id = str(row.get("chapter_id") or chapter_id or "")
        chapter_no = _safe_int(row.get("chapter_no"), chapter_no or 0) or chapter_no
        if not chapter_title:
            chapter_title = str(row.get("title") or "")
    if not chapter_title:
        chapter_title = f"第{chapter_no or 0}章"
    return {
        "chapter_id": chapter_id,
        "chapter_no": chapter_no,
        "chapter_title": chapter_title,
    }


def _merge_hard_constraints(
    *,
    session_state: dict[str, Any],
    world_rules: list[dict[str, Any]],
    payload_constraints: list[str] | None = None,
    limit: int = 24,
) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    def push(item: str) -> None:
        text_val = str(item or "").strip()
        if not text_val:
            return
        norm = text_val.lower()
        if norm in seen:
            return
        seen.add(norm)
        out.append(text_val[:180])

    for x in _safe_json_list(session_state.get("hard_constraints"))[:24]:
        push(str(x))
    for x in payload_constraints or []:
        push(str(x))
    for row in world_rules[:40]:
        value = _safe_json_dict(row.get("value"))
        for key in ("rule", "constraint", "must", "cannot", "taboo", "cost"):
            if key in value:
                push(str(value.get(key)))
        key_text = str(row.get("key") or "")
        if key_text and any(w in key_text for w in ["规则", "限制", "禁", "代价", "必须"]):
            push(key_text)
    return out[: max(4, limit)]


async def _load_latest_chapter_pack(session: AsyncSession, book_id: str, chapter_id: str | None, chapter_no: int | None) -> dict[str, Any]:
    params: dict[str, Any] = {"book_id": book_id}
    cond = "AND chapter_no=:chapter_no" if chapter_no else ""
    if chapter_id:
        cond = "AND chapter_id=CAST(:chapter_id AS uuid)"
        params["chapter_id"] = chapter_id
    elif chapter_no:
        params["chapter_no"] = int(chapter_no)
    row = (
        await session.execute(
            text(
                f"""
                SELECT payload, conflict_type, created_at
                FROM chapter_scene_pack
                WHERE book_id=CAST(:book_id AS uuid) {cond}
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            params,
        )
    ).mappings().first()
    payload = _safe_json_dict((row or {}).get("payload"))
    return {
        "conflict_type": str((row or {}).get("conflict_type") or ""),
        "payload": payload,
        "created_at": str((row or {}).get("created_at") or ""),
    }


async def _load_outline_nodes(session: AsyncSession, chapter_id: str | None) -> list[dict[str, Any]]:
    if not chapter_id:
        return []
    row = (
        await session.execute(
            text(
                """
                SELECT nodes
                FROM chapter_outline_detail
                WHERE chapter_id=CAST(:chapter_id AS uuid)
                LIMIT 1
                """
            ),
            {"chapter_id": chapter_id},
        )
    ).mappings().first()
    nodes = _safe_json_list((row or {}).get("nodes"))
    out: list[dict[str, Any]] = []
    for node in nodes[:20]:
        if not isinstance(node, dict):
            continue
        out.append(
            {
                "node_id": str(node.get("node_id") or ""),
                "type": str(node.get("type") or ""),
                "summary": str(node.get("summary") or "")[:220],
            }
        )
    return out


async def _load_recent_chapter_memory_rows(
    session: AsyncSession,
    book_id: str,
    *,
    chapter_no: int | None,
    window: int = 3,
    limit: int = 80,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lim = _clamp_int(limit, default=80, low=20, high=300)
    params: dict[str, Any] = {"book_id": book_id, "limit": lim}
    if chapter_no and chapter_no > 0:
        params["ch_low"] = max(1, int(chapter_no) - _clamp_int(window, default=3, low=1, high=12))
        params["ch_high"] = int(chapter_no) + _clamp_int(window, default=3, low=1, high=12)
        fact_cond = """
            AND EXISTS (
              SELECT 1 FROM chapter c
              WHERE c.chapter_id=cf.chapter_id
                AND c.book_id=CAST(:book_id AS uuid)
                AND c."order" BETWEEN :ch_low AND :ch_high
            )
        """
        timeline_cond = """
            AND EXISTS (
              SELECT 1 FROM chapter c
              WHERE c.chapter_id=cte.chapter_id
                AND c.book_id=CAST(:book_id AS uuid)
                AND c."order" BETWEEN :ch_low AND :ch_high
            )
        """
    else:
        fact_cond = ""
        timeline_cond = ""

    fact_rows = (
        await session.execute(
            text(
                f"""
                SELECT entity_type, entity_name, fact_type, fact, evidence_span, confidence, created_at
                FROM chapter_fact cf
                WHERE book_id=CAST(:book_id AS uuid) {fact_cond}
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            params,
        )
    ).mappings().all()
    timeline_rows = (
        await session.execute(
            text(
                f"""
                SELECT event_no, time_hint, location, actors, event, consequence, created_at
                FROM chapter_timeline_event cte
                WHERE book_id=CAST(:book_id AS uuid) {timeline_cond}
                ORDER BY created_at DESC, event_no DESC
                LIMIT :limit
                """
            ),
            params,
        )
    ).mappings().all()
    return [dict(x) for x in fact_rows], [dict(x) for x in timeline_rows]


async def _load_cold_memory_candidates(
    session: AsyncSession,
    book_id: str,
    *,
    chapter_no: int | None,
    splitbook_id: str | None,
    limit: int = 240,
) -> list[dict[str, Any]]:
    lim = _clamp_int(limit, default=240, low=60, high=800)
    candidates: list[dict[str, Any]] = []

    params_tv: dict[str, Any] = {"book_id": book_id, "limit": lim}
    tv_cond = ""
    if chapter_no and chapter_no > 0:
        params_tv["ch_low"] = max(1, int(chapter_no) - 6)
        params_tv["ch_high"] = int(chapter_no) + 2
        tv_cond = 'AND c."order" BETWEEN :ch_low AND :ch_high'
    tv_rows = (
        await session.execute(
            text(
                f"""
                SELECT c.chapter_id::text AS chapter_id, c."order" AS chapter_no, c.title,
                       ctv.content, ctv.created_at
                FROM chapter_text_version ctv
                JOIN chapter c ON c.chapter_id=ctv.chapter_id
                WHERE c.book_id=CAST(:book_id AS uuid) {tv_cond}
                ORDER BY ctv.created_at DESC
                LIMIT :limit
                """
            ),
            params_tv,
        )
    ).mappings().all()
    for row in tv_rows:
        content = str(row.get("content") or "").strip()
        if not content:
            continue
        candidates.append(
            {
                "source": "chapter_text_version",
                "source_id": str(row.get("chapter_id") or ""),
                "chapter_no": _safe_int(row.get("chapter_no"), 0),
                "title": str(row.get("title") or ""),
                "text": content[:1200],
                "created_at": str(row.get("created_at") or ""),
            }
        )

    if splitbook_id:
        try:
            params_sb: dict[str, Any] = {"sid": splitbook_id, "limit": lim}
            sb_cond = ""
            if chapter_no and chapter_no > 0:
                params_sb["ch_low"] = max(1, int(chapter_no) - 6)
                params_sb["ch_high"] = int(chapter_no) + 2
                sb_cond = "AND chapter_no BETWEEN :ch_low AND :ch_high"
            sb_rows = (
                await session.execute(
                    text(
                        f"""
                        SELECT scene_key, chapter_no, chapter_title, summary, evidence_json, created_at
                        FROM splitbook_scene
                        WHERE splitbook_id=CAST(:sid AS uuid) {sb_cond}
                        ORDER BY chapter_no DESC, scene_no DESC
                        LIMIT :limit
                        """
                    ),
                    params_sb,
                )
            ).mappings().all()
            for row in sb_rows:
                summary = str(row.get("summary") or "").strip()
                if not summary:
                    continue
                evidence = _safe_json_dict(row.get("evidence_json"))
                candidates.append(
                    {
                        "source": "splitbook_scene",
                        "source_id": str(row.get("scene_key") or ""),
                        "chapter_no": _safe_int(row.get("chapter_no"), 0),
                        "title": str(row.get("chapter_title") or ""),
                        "text": summary[:600],
                        "evidence": evidence,
                        "created_at": str(row.get("created_at") or ""),
                    }
                )
        except Exception:
            # splitbook 表是惰性创建；不存在时忽略冷库来源即可
            pass

    return candidates[:lim]


def _rerank_cold_evidence(query_text: str, candidates: list[dict[str, Any]], *, top_k: int = 24) -> list[dict[str, Any]]:
    if not candidates:
        return []
    q = str(query_text or "").strip()
    scored: list[dict[str, Any]] = []
    for row in candidates:
        text_block = str(row.get("text") or "")
        if not text_block:
            continue
        score = _lexical_overlap_score(q, text_block) if q else 0.0
        chapter_boost = min(0.2, max(0.0, (_safe_int(row.get("chapter_no"), 0) / 1000.0)))
        total = round(score + chapter_boost, 6)
        scored.append({**row, "score": total})
    scored.sort(key=lambda x: (float(x.get("score") or 0.0), str(x.get("created_at") or "")), reverse=True)
    out: list[dict[str, Any]] = []
    for row in scored[: max(6, _clamp_int(top_k, default=24, low=6, high=80))]:
        out.append(
            {
                "source": str(row.get("source") or ""),
                "source_id": str(row.get("source_id") or ""),
                "chapter_no": _safe_int(row.get("chapter_no"), 0),
                "title": str(row.get("title") or "")[:80],
                "score": round(_safe_float(row.get("score"), 0.0), 6),
                "snippet": _text_head(str(row.get("text") or ""), 220),
                "evidence": _safe_json_dict(row.get("evidence")),
            }
        )
    return out


def _assemble_context_lines(
    *,
    task_instruction: str,
    hard_constraints: list[str],
    chapter_structure: list[str],
    character_cards: list[str],
    timeline_lines: list[str],
    foreshadow_lines: list[str],
    evidence_lines: list[str],
) -> list[str]:
    lines: list[str] = []
    lines.append("[TASK]")
    lines.append(task_instruction or "执行当前写作任务")
    lines.append("")
    lines.append("[HARD_CONSTRAINTS]")
    lines.extend(hard_constraints or ["（无）"])
    lines.append("")
    lines.append("[CHAPTER_STRUCTURE]")
    lines.extend(chapter_structure or ["（无）"])
    lines.append("")
    lines.append("[CHARACTERS]")
    lines.extend(character_cards or ["（无）"])
    lines.append("")
    lines.append("[TIMELINE_WINDOW]")
    lines.extend(timeline_lines or ["（无）"])
    lines.append("")
    lines.append("[OPEN_FORESHADOWS]")
    lines.extend(foreshadow_lines or ["（无）"])
    lines.append("")
    lines.append("[EVIDENCE_SNIPPETS]")
    lines.extend(evidence_lines or ["（无）"])
    return lines


def _world_rule_to_truth_item(row: dict[str, Any]) -> dict[str, Any]:
    value = _safe_json_dict(row.get("value"))
    rule_text = (
        str(value.get("rule") or "").strip()
        or str(value.get("constraint") or "").strip()
        or str(value.get("must") or "").strip()
        or str(row.get("key") or "").strip()
    )
    limitation = str(value.get("limit") or value.get("limitation") or value.get("must") or value.get("cannot") or "").strip()
    cost = str(value.get("cost") or "").strip()
    exception = str(value.get("exception") or value.get("unless") or "").strip()
    scope = str(value.get("scope") or value.get("apply_scope") or value.get("applies_to") or "global").strip()
    evidence = _safe_json_dict(row.get("evidence"))
    if not evidence:
        source_chunks = _safe_json_list(row.get("source_chunk_ids"))
        if source_chunks:
            evidence = {"source_chunk_ids": [str(x) for x in source_chunks[:12] if str(x).strip()]}
    schema_version = str(row.get("schema_version") or value.get("schema_version") or TRUTH_LAYER_SCHEMA_VERSION)
    prompt_version = str(row.get("prompt_version") or value.get("prompt_version") or TRUTH_LAYER_PROMPT_VERSION)
    return {
        "fact_id": str(row.get("fact_id") or ""),
        "key": str(row.get("key") or ""),
        "rule": rule_text,
        "limitation": limitation,
        "cost": cost,
        "exception": exception,
        "scope": scope,
        "confidence": round(_safe_float(row.get("confidence"), 0.0), 4),
        "evidence_ref": evidence,
        "version": {"schema": schema_version, "prompt": prompt_version},
        "created_at": str(row.get("created_at") or ""),
    }


def _build_character_truth(
    *,
    character_rows: list[dict[str, Any]],
    growth_rows: list[dict[str, Any]],
    fact_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    facts_by_name: dict[str, list[dict[str, Any]]] = {}
    for fact in fact_rows:
        name = str(fact.get("entity_name") or "").strip()
        if not name:
            continue
        facts_by_name.setdefault(name, []).append(fact)
    growth_by_name: dict[str, list[dict[str, Any]]] = {}
    for row in growth_rows:
        name = str(row.get("character_name") or "").strip()
        if not name:
            continue
        growth_by_name.setdefault(name, []).append(row)

    out: list[dict[str, Any]] = []
    for row in character_rows:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        card = _safe_json_dict(row.get("card"))
        milestones = growth_by_name.get(name) or []
        fact_refs = facts_by_name.get(name) or []
        confidence = max([_safe_float(x.get("confidence"), 0.0) for x in fact_refs] or [0.65])
        out.append(
            {
                "character_id": str(row.get("character_id") or ""),
                "name": name,
                "role": str(row.get("role") or ""),
                "goal": _extract_card_anchor_value(card, ["goal", "target", "objective"]),
                "bottom_line": _extract_card_anchor_value(card, ["bottom_line", "taboo", "forbidden", "principle"]),
                "fear": _extract_card_anchor_value(card, ["fear", "core_fear"]),
                "desire": _extract_card_anchor_value(card, ["desire", "want", "motivation"]),
                "growth_milestones": [
                    {
                        "milestone_id": str(x.get("milestone_id") or ""),
                        "title": str(x.get("title") or ""),
                        "stage": str(x.get("stage") or ""),
                        "status": str(x.get("status") or ""),
                        "planned_chapter_no": _safe_int(x.get("planned_chapter_no"), 0) or None,
                    }
                    for x in milestones[:10]
                ],
                "evidence_ref": [
                    {
                        "chapter_id": str(x.get("chapter_id") or ""),
                        "fact_id": str(x.get("fact_id") or ""),
                        "fact_type": str(x.get("fact_type") or ""),
                        "evidence_span": str(x.get("evidence_span") or "")[:140],
                    }
                    for x in fact_refs[:8]
                ],
                "confidence": round(confidence, 4),
                "version": {
                    "schema": str(card.get("schema_version") or TRUTH_LAYER_SCHEMA_VERSION),
                    "prompt": str(card.get("prompt_version") or TRUTH_LAYER_PROMPT_VERSION),
                },
            }
        )
    return out


def _build_conflict_lines(scene_pack_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in scene_pack_rows:
        payload = _safe_json_dict(row.get("payload"))
        conflict_card = _safe_json_dict(payload.get("conflict_card"))
        scene_cards = _safe_json_list(payload.get("scene_cards"))
        escalation_path = [str(x.get("stage") or "") for x in scene_cards if isinstance(x, dict) and str(x.get("stage") or "").strip()]
        out.append(
            {
                "pack_id": str(row.get("pack_id") or ""),
                "chapter_no": _safe_int(row.get("chapter_no"), 0) or None,
                "chapter_title": str(row.get("chapter_title") or ""),
                "conflict_type": str(row.get("conflict_type") or ""),
                "opponent": str(conflict_card.get("resistance_source") or ""),
                "stakes": str(conflict_card.get("chapter_goal") or ""),
                "escalation_path": escalation_path[:8],
                "phase_goal": str(_safe_json_dict(payload.get("fractal_targets")).get("chapter_goal") or ""),
                "confidence": 0.72,
                "evidence_ref": {"pack_id": str(row.get("pack_id") or ""), "created_at": str(row.get("created_at") or "")},
                "version": {"schema": TRUTH_LAYER_SCHEMA_VERSION, "prompt": TRUTH_LAYER_PROMPT_VERSION},
            }
        )
    return out


def _build_foreshadow_graph(
    *,
    foreshadow_rows: list[dict[str, Any]],
    foreshadow_event_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id: dict[str, list[dict[str, Any]]] = {}
    for row in foreshadow_event_rows:
        fid = str(row.get("foreshadow_id") or "").strip()
        if not fid:
            continue
        by_id.setdefault(fid, []).append(row)
    out: list[dict[str, Any]] = []
    for row in foreshadow_rows:
        fid = str(row.get("foreshadow_id") or "").strip()
        if not fid:
            continue
        events = sorted(
            by_id.get(fid) or [],
            key=lambda x: (str(x.get("created_at") or ""), _safe_int(x.get("intensity"), 0)),
        )
        seed_events = [x for x in events if str(x.get("event_type") or "").lower() in {"seed", "reinforce"}]
        payoff_events = [x for x in events if str(x.get("event_type") or "").lower() in {"payoff", "retcon"}]
        out.append(
            {
                "foreshadow_id": fid,
                "title": str(row.get("title") or ""),
                "type": str(row.get("type") or ""),
                "status": str(row.get("status") or ""),
                "question": str(row.get("question") or ""),
                "expected_payoff": str(row.get("expected_payoff") or ""),
                "planned_payoff_chapter_id": str(row.get("planned_payoff_chapter_id") or ""),
                "seed_events": [
                    {
                        "chapter_id": str(x.get("chapter_id") or ""),
                        "event_type": str(x.get("event_type") or ""),
                        "intensity": _safe_int(x.get("intensity"), 0),
                    }
                    for x in seed_events[:8]
                ],
                "payoff_events": [
                    {
                        "chapter_id": str(x.get("chapter_id") or ""),
                        "event_type": str(x.get("event_type") or ""),
                        "intensity": _safe_int(x.get("intensity"), 0),
                    }
                    for x in payoff_events[:8]
                ],
                "confidence": round(max(0.4, min(0.95, 0.45 + (_safe_int(row.get("priority"), 3) * 0.1))), 4),
                "evidence_ref": {"events_count": len(events), "latest_update": str(row.get("updated_at") or "")},
                "version": {"schema": TRUTH_LAYER_SCHEMA_VERSION, "prompt": TRUTH_LAYER_PROMPT_VERSION},
            }
        )
    return out


def _compose_task_context_bundle(
    *,
    task_type: str,
    task_instruction: str,
    hard_constraints: list[str],
    chapter_structure: list[str],
    character_cards: list[str],
    timeline_lines: list[str],
    foreshadow_lines: list[str],
    evidence_lines: list[str],
    world_rule_lines: list[str],
) -> dict[str, Any]:
    mode = str(task_type or "write_chapter").strip().lower() or "write_chapter"
    sections: dict[str, list[str]] = {
        "hard_constraints": hard_constraints[:28],
        "chapter_structure": chapter_structure[:20],
        "character_cards": character_cards[:20],
        "timeline_lines": timeline_lines[:20],
        "foreshadow_lines": foreshadow_lines[:20],
        "evidence_lines": evidence_lines[:24],
        "world_rule_lines": world_rule_lines[:20],
    }
    if mode == "outline":
        sections["character_cards"] = character_cards[:10]
        sections["timeline_lines"] = timeline_lines[:14]
        sections["foreshadow_lines"] = foreshadow_lines[:10]
        sections["evidence_lines"] = evidence_lines[:16]
    elif mode == "consistency_check":
        sections["chapter_structure"] = chapter_structure[:12]
        sections["character_cards"] = character_cards[:24]
        sections["timeline_lines"] = timeline_lines[:24]
        sections["foreshadow_lines"] = foreshadow_lines[:24]
        sections["evidence_lines"] = evidence_lines[:20]
        sections["hard_constraints"] = (hard_constraints + world_rule_lines)[:36]

    context_lines = _assemble_context_lines(
        task_instruction=task_instruction,
        hard_constraints=sections["hard_constraints"],
        chapter_structure=sections["chapter_structure"],
        character_cards=sections["character_cards"],
        timeline_lines=sections["timeline_lines"],
        foreshadow_lines=sections["foreshadow_lines"],
        evidence_lines=sections["evidence_lines"],
    )
    return {"task_type": mode, "sections": sections, "context_lines": context_lines}


async def get_story_bible_snapshot(
    session: AsyncSession,
    book_id: str,
    *,
    limit: int = 80,
    chapter_id: str | None = None,
) -> dict[str, Any]:
    await ensure_story_engine_tables(session)
    lim = _clamp_int(limit, default=80, low=10, high=400)
    char_rows = (
        await session.execute(
            text(
                """
                WITH cv_latest AS (
                  SELECT
                    c.character_id::text AS character_id,
                    c.name,
                    c.role,
                    cv.card,
                    ROW_NUMBER() OVER(PARTITION BY c.character_id ORDER BY cv.version DESC, cv.created_at DESC) AS rn
                  FROM character c
                  LEFT JOIN character_version cv ON cv.character_id=c.character_id
                  WHERE c.book_id=CAST(:book_id AS uuid)
                )
                SELECT character_id, name, role, card
                FROM cv_latest
                WHERE rn=1
                ORDER BY name
                LIMIT :limit
                """
            ),
            {"book_id": book_id, "limit": lim},
        )
    ).mappings().all()
    timeline_rows = (
        await session.execute(
            text(
                """
                SELECT
                  event_id::text AS event_id,
                  chapter_id::text AS chapter_id,
                  title,
                  description,
                  causality,
                  evidence,
                  schema_version,
                  prompt_version,
                  source_chunk_ids,
                  created_at
                FROM timeline_event
                WHERE book_id=CAST(:book_id AS uuid)
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"book_id": book_id, "limit": lim},
        )
    ).mappings().all()
    world_rows = (
        await session.execute(
            text(
                """
                SELECT
                  fact_id::text AS fact_id,
                  key,
                  value,
                  confidence,
                  source_chunk_ids,
                  evidence,
                  schema_version,
                  prompt_version,
                  created_at
                FROM world_fact
                WHERE book_id=CAST(:book_id AS uuid)
                ORDER BY key
                LIMIT :limit
                """
            ),
            {"book_id": book_id, "limit": lim},
        )
    ).mappings().all()
    growth_rows = (
        await session.execute(
            text(
                """
                SELECT
                  milestone_id::text AS milestone_id,
                  character_name,
                  milestone_no,
                  title,
                  stage,
                  status,
                  planned_chapter_no,
                  trigger,
                  cost,
                  choice_text,
                  new_belief,
                  meta,
                  updated_at
                FROM growth_milestone
                WHERE book_id=CAST(:book_id AS uuid)
                ORDER BY character_name, milestone_no
                LIMIT :limit
                """
            ),
            {"book_id": book_id, "limit": lim},
        )
    ).mappings().all()
    foreshadow_rows = (
        await session.execute(
            text(
                """
                SELECT
                  foreshadow_id::text AS foreshadow_id,
                  title,
                  type,
                  status,
                  priority,
                  question,
                  expected_payoff,
                  planned_payoff_chapter_id::text AS planned_payoff_chapter_id,
                  updated_at
                FROM foreshadow
                WHERE book_id=CAST(:book_id AS uuid)
                ORDER BY priority DESC, updated_at DESC
                LIMIT :limit
                """
            ),
            {"book_id": book_id, "limit": lim},
        )
    ).mappings().all()
    foreshadow_event_rows = (
        await session.execute(
            text(
                """
                SELECT
                  fe.foreshadow_id::text AS foreshadow_id,
                  fe.chapter_id::text AS chapter_id,
                  fe.event_type,
                  fe.intensity,
                  fe.note,
                  fe.created_at
                FROM foreshadow_event fe
                JOIN foreshadow f ON f.foreshadow_id = fe.foreshadow_id
                WHERE f.book_id=CAST(:book_id AS uuid)
                ORDER BY fe.created_at DESC
                LIMIT :limit
                """
            ),
            {"book_id": book_id, "limit": lim * 4},
        )
    ).mappings().all()
    chapter_fact_rows = (
        await session.execute(
            text(
                """
                SELECT
                  fact_id::text AS fact_id,
                  chapter_id::text AS chapter_id,
                  entity_type,
                  entity_name,
                  fact_type,
                  fact,
                  evidence_span,
                  evidence_ref,
                  confidence,
                  schema_version,
                  prompt_version,
                  created_at
                FROM chapter_fact
                WHERE book_id=CAST(:book_id AS uuid)
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"book_id": book_id, "limit": lim * 2},
        )
    ).mappings().all()
    conflict_rows = (
        await session.execute(
            text(
                """
                SELECT
                  pack_id::text AS pack_id,
                  chapter_no,
                  chapter_title,
                  conflict_type,
                  payload,
                  created_at
                FROM chapter_scene_pack
                WHERE book_id=CAST(:book_id AS uuid)
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"book_id": book_id, "limit": max(12, min(lim, 64))},
        )
    ).mappings().all()
    proposals = (
        await session.execute(
            text(
                """
                SELECT
                  proposal_id::text AS proposal_id,
                  proposal_type,
                  entity_key,
                  title,
                  status,
                  reason,
                  updated_at
                FROM story_bible_proposal
                WHERE book_id=CAST(:book_id AS uuid)
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"book_id": book_id, "limit": lim},
        )
    ).mappings().all()
    chapter_context: dict[str, Any] = {}
    if chapter_id:
        row = (
            await session.execute(
                text(
                    """
                    SELECT chapter_id::text AS chapter_id, "order" AS chapter_no, title
                    FROM chapter
                    WHERE chapter_id=CAST(:chapter_id AS uuid) AND book_id=CAST(:book_id AS uuid)
                    LIMIT 1
                    """
                ),
                {"book_id": book_id, "chapter_id": chapter_id},
            )
        ).mappings().first()
        if row:
            chapter_context = dict(row)
    truth_world_rules = [_world_rule_to_truth_item(dict(x)) for x in world_rows]
    truth_characters = _build_character_truth(
        character_rows=[dict(x) for x in char_rows],
        growth_rows=[dict(x) for x in growth_rows],
        fact_rows=[dict(x) for x in chapter_fact_rows],
    )
    truth_conflict_lines = _build_conflict_lines([dict(x) for x in conflict_rows])
    truth_foreshadow_graph = _build_foreshadow_graph(
        foreshadow_rows=[dict(x) for x in foreshadow_rows],
        foreshadow_event_rows=[dict(x) for x in foreshadow_event_rows],
    )
    truth_layer = {
        "schema_version": TRUTH_LAYER_SCHEMA_VERSION,
        "prompt_version": TRUTH_LAYER_PROMPT_VERSION,
        "world_rules": truth_world_rules,
        "characters": truth_characters,
        "conflict_lines": truth_conflict_lines,
        "foreshadow_graph": truth_foreshadow_graph,
        "generated_at": _now_iso(),
    }
    return {
        "book_id": book_id,
        "chapter_context": chapter_context,
        "summary": {
            "character_count": len(char_rows),
            "timeline_count": len(timeline_rows),
            "world_rule_count": len(world_rows),
            "growth_milestone_count": len(growth_rows),
            "foreshadow_count": len(foreshadow_rows),
            "proposal_count": len(proposals),
            "truth_world_rule_count": len(truth_world_rules),
            "truth_character_count": len(truth_characters),
            "truth_conflict_count": len(truth_conflict_lines),
            "truth_foreshadow_count": len(truth_foreshadow_graph),
        },
        "characters": [dict(x) for x in char_rows],
        "timeline": [dict(x) for x in timeline_rows],
        "world_rules": [dict(x) for x in world_rows],
        "growth_milestones": [dict(x) for x in growth_rows],
        "foreshadows": [dict(x) for x in foreshadow_rows],
        "proposals": [dict(x) for x in proposals],
        "truth_layer": truth_layer,
        "generated_at": _now_iso(),
    }


async def get_story_engine_dashboard(session: AsyncSession, book_id: str) -> dict[str, Any]:
    await ensure_story_engine_tables(session)
    counts_row = (
        await session.execute(
            text(
                """
                SELECT
                  (SELECT COUNT(*) FROM volume WHERE book_id=CAST(:book_id AS uuid)) AS volume_count,
                  (SELECT COUNT(*) FROM chapter WHERE book_id=CAST(:book_id AS uuid)) AS chapter_count,
                  (SELECT COUNT(*) FROM chapter_scene_pack WHERE book_id=CAST(:book_id AS uuid)) AS scene_pack_count,
                  (SELECT COUNT(*) FROM chapter_audit_snapshot WHERE book_id=CAST(:book_id AS uuid)) AS audit_count,
                  (SELECT COUNT(*) FROM character WHERE book_id=CAST(:book_id AS uuid)) AS character_count,
                  (SELECT COUNT(*) FROM timeline_event WHERE book_id=CAST(:book_id AS uuid)) AS timeline_count,
                  (SELECT COUNT(*) FROM world_fact WHERE book_id=CAST(:book_id AS uuid)) AS world_count,
                  (SELECT COUNT(*) FROM growth_milestone WHERE book_id=CAST(:book_id AS uuid) AND status IN ('planned', 'active')) AS growth_open_count,
                  (SELECT COUNT(*) FROM story_bible_proposal WHERE book_id=CAST(:book_id AS uuid) AND status='pending') AS proposal_pending_count
                """
            ),
            {"book_id": book_id},
        )
    ).mappings().first()
    row = dict(counts_row or {})
    foreshadow_row = (
        await session.execute(
            text(
                """
                WITH latest_chapter AS (
                  SELECT COALESCE(MAX("order"), 0) AS latest_no
                  FROM chapter
                  WHERE book_id=CAST(:book_id AS uuid)
                )
                SELECT
                  COUNT(*) FILTER (WHERE f.status NOT IN ('paid_off', 'closed', 'abandoned')) AS open_count,
                  COUNT(*) FILTER (
                    WHERE f.status NOT IN ('paid_off', 'closed', 'abandoned')
                      AND cp."order" IS NOT NULL
                      AND cp."order" <= lc.latest_no
                  ) AS overdue_count
                FROM foreshadow f
                LEFT JOIN chapter cp ON cp.chapter_id=f.planned_payoff_chapter_id
                CROSS JOIN latest_chapter lc
                WHERE f.book_id=CAST(:book_id AS uuid)
                """
            ),
            {"book_id": book_id},
        )
    ).mappings().first()
    audit_latest = (
        await session.execute(
            text(
                """
                SELECT
                  audit_id::text AS audit_id,
                  chapter_no,
                  total_score,
                  threshold,
                  status,
                  created_at
                FROM chapter_audit_snapshot
                WHERE book_id=CAST(:book_id AS uuid)
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"book_id": book_id},
        )
    ).mappings().first()
    pack_latest = (
        await session.execute(
            text(
                """
                SELECT pack_id::text AS pack_id, chapter_no, chapter_title, conflict_type, created_at
                FROM chapter_scene_pack
                WHERE book_id=CAST(:book_id AS uuid)
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"book_id": book_id},
        )
    ).mappings().first()
    chapter_count = _safe_int(row.get("chapter_count"), 0)
    pack_count = _safe_int(row.get("scene_pack_count"), 0)
    audit_count = _safe_int(row.get("audit_count"), 0)
    return {
        "book_id": book_id,
        "kpi": {
            "volume_count": _safe_int(row.get("volume_count"), 0),
            "chapter_count": chapter_count,
            "scene_pack_count": pack_count,
            "audit_count": audit_count,
            "scene_pack_coverage": round((pack_count / chapter_count), 4) if chapter_count > 0 else 0.0,
            "audit_coverage": round((audit_count / chapter_count), 4) if chapter_count > 0 else 0.0,
            "character_count": _safe_int(row.get("character_count"), 0),
            "timeline_count": _safe_int(row.get("timeline_count"), 0),
            "world_rule_count": _safe_int(row.get("world_count"), 0),
            "growth_open_count": _safe_int(row.get("growth_open_count"), 0),
            "proposal_pending_count": _safe_int(row.get("proposal_pending_count"), 0),
            "foreshadow_open_count": _safe_int((foreshadow_row or {}).get("open_count"), 0),
            "foreshadow_overdue_count": _safe_int((foreshadow_row or {}).get("overdue_count"), 0),
        },
        "latest_scene_pack": dict(pack_latest or {}),
        "latest_audit": dict(audit_latest or {}),
        "generated_at": _now_iso(),
    }


async def get_story_engine_quality_metrics(
    session: AsyncSession,
    book_id: str,
    *,
    checkpoint_limit: int = 240,
) -> dict[str, Any]:
    await ensure_story_engine_tables(session)
    dashboard = await get_story_engine_dashboard(session, book_id)
    lim = _clamp_int(checkpoint_limit, default=240, low=40, high=1000)
    rows = (
        await session.execute(
            text(
                """
                SELECT chapter_no, output_payload, created_at
                FROM writing_memory_checkpoint
                WHERE book_id=CAST(:book_id AS uuid) AND task_type='writeback'
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"book_id": book_id, "limit": lim},
        )
    ).mappings().all()
    issue_counter: dict[str, int] = {}
    chapter_counter: dict[str, set[int]] = {
        "timeline_conflict": set(),
        "setting_conflict": set(),
        "character_drift": set(),
        "style_drift": set(),
        "ai_smell": set(),
        "anti_copy": set(),
    }
    for row in rows:
        payload = _safe_json_dict(row.get("output_payload"))
        issues = _safe_json_list(payload.get("issues"))
        chapter_no = _safe_int(row.get("chapter_no"), 0)
        for item in issues:
            if not isinstance(item, dict):
                continue
            issue_type = str(item.get("type") or "").strip() or "unknown"
            issue_counter[issue_type] = issue_counter.get(issue_type, 0) + 1
            if chapter_no > 0:
                if issue_type == "timeline_conflict":
                    chapter_counter["timeline_conflict"].add(chapter_no)
                if issue_type in {"setting_consistency", "ability_limit_break"}:
                    chapter_counter["setting_conflict"].add(chapter_no)
                if issue_type in {"character_consistency", "character_drift"}:
                    chapter_counter["character_drift"].add(chapter_no)
                if issue_type == "style_drift":
                    chapter_counter["style_drift"].add(chapter_no)
                if issue_type == "ai_smell":
                    chapter_counter["ai_smell"].add(chapter_no)
                if issue_type == "anti_copy":
                    chapter_counter["anti_copy"].add(chapter_no)

    chapter_count = _safe_int(_safe_json_dict(dashboard.get("kpi")).get("chapter_count"), 0)
    with_time = chapter_count if chapter_count > 0 else 1
    consistency = {
        "timeline_conflict_chapters": len(chapter_counter["timeline_conflict"]),
        "setting_conflict_chapters": len(chapter_counter["setting_conflict"]),
        "character_drift_chapters": len(chapter_counter["character_drift"]),
        "style_drift_chapters": len(chapter_counter["style_drift"]),
        "ai_smell_chapters": len(chapter_counter["ai_smell"]),
        "anti_copy_chapters": len(chapter_counter["anti_copy"]),
    }
    consistency_rates = {
        "timeline_conflict_rate": round(consistency["timeline_conflict_chapters"] / with_time, 4),
        "setting_conflict_rate": round(consistency["setting_conflict_chapters"] / with_time, 4),
        "character_drift_rate": round(consistency["character_drift_chapters"] / with_time, 4),
        "style_drift_rate": round(consistency["style_drift_chapters"] / with_time, 4),
        "ai_smell_rate": round(consistency["ai_smell_chapters"] / with_time, 4),
        "anti_copy_rate": round(consistency["anti_copy_chapters"] / with_time, 4),
    }
    return {
        "ok": True,
        "book_id": book_id,
        "coverage": _safe_json_dict(dashboard.get("kpi")),
        "consistency": consistency,
        "consistency_rates": consistency_rates,
        "issue_histogram": issue_counter,
        "sampled_writeback_checkpoints": len(rows),
        "generated_at": _now_iso(),
    }


async def run_story_engine_regression(
    session: AsyncSession,
    book_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    await ensure_story_engine_tables(session)
    samples = [x for x in _safe_json_list(payload.get("samples")) if isinstance(x, dict)]
    threshold = _clamp_int(payload.get("threshold"), default=22, low=10, high=30)
    if not samples:
        raise RuntimeError("samples_required")
    rows: list[dict[str, Any]] = []
    pass_count = 0
    for idx, sample in enumerate(samples[:40], start=1):
        chapter_id = str(sample.get("chapter_id") or "").strip() or None
        chapter_no = _safe_int(sample.get("chapter_no"), 0) or idx
        chapter_title = str(sample.get("chapter_title") or f"Regression-{chapter_no}")
        content = str(sample.get("content") or "").strip()
        if not content:
            rows.append(
                {
                    "index": idx,
                    "chapter_no": chapter_no,
                    "chapter_title": chapter_title,
                    "ok": False,
                    "reason": "empty_content",
                }
            )
            continue
        audit = await run_chapter_engine_audit(
            session,
            book_id,
            {
                "chapter_id": chapter_id,
                "chapter_no": chapter_no,
                "chapter_title": chapter_title,
                "content": content,
                "threshold": threshold,
            },
        )
        expected_min_score = _safe_int(sample.get("expected_min_score"), threshold)
        expected_issue_absent = [str(x) for x in _safe_json_list(sample.get("expected_issue_absent")) if str(x).strip()]
        issue_types = {str(x.get("type") or "") for x in _safe_json_list(audit.get("issues")) if isinstance(x, dict)}
        score = _safe_int(audit.get("total_score"), 0)
        score_ok = score >= expected_min_score
        issue_ok = all(x not in issue_types for x in expected_issue_absent)
        ok = bool(score_ok and issue_ok)
        if ok:
            pass_count += 1
        rows.append(
            {
                "index": idx,
                "chapter_no": chapter_no,
                "chapter_title": chapter_title,
                "score": score,
                "expected_min_score": expected_min_score,
                "score_ok": score_ok,
                "issue_ok": issue_ok,
                "issue_types": sorted(list(issue_types)),
                "ok": ok,
            }
        )
    total = len(rows)
    return {
        "ok": pass_count == total and total > 0,
        "book_id": book_id,
        "threshold": threshold,
        "total": total,
        "passed": pass_count,
        "pass_rate": round((pass_count / max(1, total)), 4),
        "results": rows,
        "generated_at": _now_iso(),
    }


async def build_writing_memory_pack(session: AsyncSession, book_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    await ensure_story_engine_tables(session)
    task_type = str(payload.get("task_type") or "write_chapter").strip().lower() or "write_chapter"
    session_key = str(payload.get("session_key") or "default").strip() or "default"
    splitbook_id = _to_uuid_str(payload.get("splitbook_id"))
    user_query = str(payload.get("query") or payload.get("task_instruction") or "").strip()
    evidence_top_k = _clamp_int(payload.get("evidence_top_k"), default=24, low=6, high=80)
    chapter_window = _clamp_int(payload.get("chapter_window"), default=3, low=1, high=12)

    chapter_ctx = await _resolve_chapter_context(session, book_id, payload)
    chapter_id = _to_uuid_str(chapter_ctx.get("chapter_id"))
    chapter_no = _safe_int(chapter_ctx.get("chapter_no"), 0) or None
    chapter_title = str(chapter_ctx.get("chapter_title") or "")

    hot_state_resp = await get_writing_session_state(session, book_id, session_key=session_key)
    hot_state = _safe_json_dict(hot_state_resp.get("state"))
    hot_patch = _safe_json_dict(payload.get("hot_state_patch"))
    if hot_patch:
        merged_state = {**hot_state, **hot_patch}
        merged_state["last_patch_at"] = _now_iso()
        state_write = await upsert_writing_session_state(
            session,
            book_id,
            {"session_key": session_key, "mode": "replace", "state": merged_state},
        )
        hot_state = _safe_json_dict(state_write.get("state"))

    bible = await get_story_bible_snapshot(session, book_id, limit=120, chapter_id=chapter_id)
    world_rules = [dict(x) for x in _safe_json_list(bible.get("world_rules"))]
    characters = [dict(x) for x in _safe_json_list(bible.get("characters"))]
    timeline = [dict(x) for x in _safe_json_list(bible.get("timeline"))]
    foreshadows = [dict(x) for x in _safe_json_list(bible.get("foreshadows"))]
    open_foreshadows = [x for x in foreshadows if str(x.get("status") or "") not in {"paid_off", "closed", "abandoned"}]

    chapter_pack = await _load_latest_chapter_pack(session, book_id, chapter_id, chapter_no)
    outline_nodes = await _load_outline_nodes(session, chapter_id)
    fact_rows, timeline_rows = await _load_recent_chapter_memory_rows(
        session,
        book_id,
        chapter_no=chapter_no,
        window=chapter_window,
        limit=120,
    )
    cold_candidates = await _load_cold_memory_candidates(
        session,
        book_id,
        chapter_no=chapter_no,
        splitbook_id=splitbook_id,
        limit=360,
    )
    recall_mode = "cold_recall_only"
    recall_hits: list[dict[str, Any]] = []
    if user_query:
        # Stage-1: vector + keyword 召回，失败时自动回退 keyword-only。
        try:
            recall_hits = await hybrid_search(
                session,
                user_query,
                book_id,
                top_k=max(12, min(80, evidence_top_k * 3)),
                hybrid=True,
                vector_weight=0.68,
                keyword_weight=0.32,
            )
            recall_mode = "vector+bm25_recall"
        except Exception:
            try:
                recall_hits = await hybrid_search(
                    session,
                    user_query,
                    book_id,
                    top_k=max(12, min(80, evidence_top_k * 3)),
                    hybrid=False,
                    vector_weight=0.0,
                    keyword_weight=1.0,
                )
                recall_mode = "bm25_recall_fallback"
            except Exception:
                recall_hits = []
                recall_mode = "cold_recall_only"
    for hit in recall_hits:
        cold_candidates.append(
            {
                "source": "book_chunk",
                "source_id": str(hit.get("chunk_id") or ""),
                "chapter_no": _safe_int(hit.get("chapter_order"), 0),
                "title": f"chapter-{_safe_int(hit.get('chapter_order'), 0)}",
                "text": str(hit.get("snippet") or ""),
                "created_at": "",
            }
        )
    dedup_candidates: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in cold_candidates:
        key = (
            str(row.get("source") or ""),
            str(row.get("source_id") or ""),
            _text_head(str(row.get("text") or ""), 96),
        )
        if key not in dedup_candidates:
            dedup_candidates[key] = row
    cold_candidates = list(dedup_candidates.values())

    hot_focus_entities = [str(x) for x in _safe_json_list(hot_state.get("focus_entities")) if str(x).strip()]
    if not user_query:
        seed_parts = [str(hot_state.get("task_instruction") or ""), chapter_title, " ".join(hot_focus_entities[:6])]
        user_query = " ".join([x for x in seed_parts if x]).strip()
    ranked_evidence = _rerank_cold_evidence(user_query, cold_candidates, top_k=evidence_top_k)

    hard_constraints = _merge_hard_constraints(
        session_state=hot_state,
        world_rules=world_rules,
        payload_constraints=[str(x) for x in _safe_json_list(payload.get("hard_constraints"))],
        limit=28,
    )
    style_card = _safe_json_dict(payload.get("style_card"))
    style_card_source = "payload"
    if not style_card:
        style_card = _safe_json_dict(hot_state.get("style_card"))
        style_card_source = "session_state"
    if not style_card:
        latest_style = await get_latest_style_evolution(session, book_id=book_id)
        style_result = _safe_json_dict(_safe_json_dict(latest_style or {}).get("result"))
        style_metrics = _safe_json_dict(style_result.get("metrics"))
        style_guidance = _safe_json_dict(style_result.get("guidance"))
        if style_metrics:
            style_card = {
                "sentence_avg_len_target": round(_safe_float(style_metrics.get("sentence_avg_len"), 0.0), 3),
                "short_sentence_ratio_target": round(_safe_float(style_metrics.get("short_sentence_ratio"), 0.0), 4),
                "dialogue_ratio_target": round(_safe_float(style_metrics.get("dialogue_ratio"), 0.0), 4),
                "first_person_ratio_target": round(_safe_float(style_metrics.get("first_person_ratio"), 0.0), 4),
                "do": _safe_json_list(style_guidance.get("do"))[:8],
                "dont": _safe_json_list(style_guidance.get("dont"))[:8],
            }
            style_card_source = "style_evolution"
    forbidden_phrases = [
        str(x).strip()
        for x in [*_safe_json_list(style_card.get("forbidden_phrases")), *_safe_json_list(payload.get("forbidden_expressions"))]
        if str(x).strip()
    ]
    if forbidden_phrases:
        style_card["forbidden_phrases"] = forbidden_phrases[:16]
    style_constraints: list[str] = []
    if style_card:
        perspective = str(style_card.get("perspective") or "").strip()
        if perspective:
            style_constraints.append(f"叙述视角固定：{perspective}")
        if _safe_float(style_card.get("sentence_avg_len_target"), 0.0) > 0:
            style_constraints.append(f"句长目标：平均句长约 {round(_safe_float(style_card.get('sentence_avg_len_target'), 0.0), 2)} 字")
        if forbidden_phrases:
            style_constraints.append(f"禁用表达：{ ' / '.join(forbidden_phrases[:8]) }")
        for line in _safe_json_list(style_card.get("do"))[:4]:
            txt = str(line).strip()
            if txt:
                style_constraints.append(f"风格强化：{txt}")
        for line in _safe_json_list(style_card.get("dont"))[:4]:
            txt = str(line).strip()
            if txt:
                style_constraints.append(f"风格禁忌：{txt}")
    if style_constraints:
        merged_constraints: list[str] = []
        seen_constraints: set[str] = set()
        for item in [*hard_constraints, *style_constraints]:
            txt = str(item or "").strip()
            if not txt or txt in seen_constraints:
                continue
            seen_constraints.add(txt)
            merged_constraints.append(txt)
            if len(merged_constraints) >= 36:
                break
        hard_constraints = merged_constraints

    task_instruction = str(payload.get("task_instruction") or "").strip()
    if not task_instruction:
        if task_type == "outline":
            task_instruction = f"生成 {chapter_title} 的结构化章纲，并保持与既有时间线/设定一致。"
        elif task_type == "consistency_check":
            task_instruction = f"对 {chapter_title} 执行一致性校验，重点检查人物、设定、时间线、伏笔回收。"
        else:
            task_instruction = f"写作 {chapter_title}，严格遵循硬约束与本章结构，不引入设定漂移。"

    conflict_card = _safe_json_dict(_safe_json_dict(chapter_pack.get("payload")).get("conflict_card"))
    scene_cards = _safe_json_list(_safe_json_dict(chapter_pack.get("payload")).get("scene_cards"))
    chapter_structure: list[str] = []
    if conflict_card:
        chapter_structure.append(f"冲突类型：{conflict_card.get('conflict_label') or conflict_card.get('conflict_type') or ''}")
        chapter_structure.append(f"本章目标：{conflict_card.get('chapter_goal') or ''}")
        chapter_structure.append(f"升级方式：{conflict_card.get('upgrade_method') or ''}")
        chapter_structure.append(f"章末钩子：{conflict_card.get('cliffhanger') or ''}")
    for card in scene_cards[:8]:
        if not isinstance(card, dict):
            continue
        chapter_structure.append(
            f"Scene{_safe_int(card.get('scene_no'), 0)} {card.get('stage') or ''}: {card.get('main_action') or card.get('goal') or ''}"
        )
    if not chapter_structure:
        for node in outline_nodes[:10]:
            chapter_structure.append(f"{node.get('type') or 'node'}: {node.get('summary') or ''}")

    character_cards: list[str] = []
    focus_set = {x.strip() for x in hot_focus_entities if x.strip()}
    for row in characters[:24]:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        if focus_set and name not in focus_set and len(character_cards) >= 8:
            continue
        card = _safe_json_dict(row.get("card"))
        goal = str(card.get("goal") or card.get("target") or "")
        taboo = str(card.get("taboo") or card.get("forbidden") or "")
        character_cards.append(f"{name}({row.get('role') or 'unknown'}): 目标={goal or '未知'}；禁忌={taboo or '无'}")
    if not character_cards:
        for row in fact_rows[:10]:
            if str(row.get("entity_type") or "") == "character":
                character_cards.append(f"{row.get('entity_name')}: {row.get('fact') or ''}")

    timeline_lines: list[str] = []
    for row in timeline_rows[:18]:
        timeline_lines.append(
            f"[{row.get('time_hint') or '当章'}] {(row.get('location') or '未知地点')} - {row.get('event') or ''}"
        )
    if not timeline_lines:
        for row in timeline[:12]:
            timeline_lines.append(f"{row.get('title') or ''}: {_text_head(str(row.get('description') or ''), 100)}")

    foreshadow_lines: list[str] = []
    for row in open_foreshadows[:16]:
        foreshadow_lines.append(
            f"{row.get('title') or ''}（状态={row.get('status') or 'seeded'}，预期回收={row.get('expected_payoff') or '未填'}）"
        )
    world_rule_lines: list[str] = []
    for row in world_rules[:20]:
        value = _safe_json_dict(row.get("value"))
        line = (
            str(value.get("rule") or "").strip()
            or str(value.get("constraint") or "").strip()
            or str(value.get("must") or "").strip()
            or str(row.get("key") or "").strip()
        )
        if line:
            world_rule_lines.append(f"{row.get('key') or 'rule'}: {line}")

    evidence_lines = [
        f"[{row.get('source')}] ch{_safe_int(row.get('chapter_no'), 0)} {row.get('snippet') or ''}"
        for row in ranked_evidence[:evidence_top_k]
    ]

    task_bundle = _compose_task_context_bundle(
        task_type=task_type,
        task_instruction=task_instruction,
        hard_constraints=hard_constraints,
        chapter_structure=chapter_structure,
        character_cards=character_cards,
        timeline_lines=timeline_lines,
        foreshadow_lines=foreshadow_lines,
        evidence_lines=evidence_lines,
        world_rule_lines=world_rule_lines,
    )
    context_lines = [str(x) for x in (task_bundle.get("context_lines") or [])]
    context_text = "\n".join(context_lines)
    source_counter: dict[str, int] = {}
    for row in cold_candidates:
        src = str(row.get("source") or "unknown")
        source_counter[src] = source_counter.get(src, 0) + 1

    working_view = {
        "task_type": task_type,
        "chapter": {"chapter_id": chapter_id, "chapter_no": chapter_no, "chapter_title": chapter_title},
        "characters": characters[:24],
        "world_rules": world_rules[:24],
        "style_card": style_card,
        "style_card_source": style_card_source,
        "timeline_window": timeline_rows[:24],
        "chapter_facts": fact_rows[:24],
        "open_foreshadows": open_foreshadows[:24],
        "chapter_structure": {
            "conflict_card": conflict_card,
            "scene_cards": scene_cards[:10],
            "outline_nodes": outline_nodes[:12],
        },
    }
    cold_view = {
        "query": user_query,
        "candidate_total": len(cold_candidates),
        "evidence_top_k": evidence_top_k,
        "evidence": ranked_evidence[:evidence_top_k],
        "retrieval_pipeline": {
            "stage1_recall": {
                "mode": recall_mode,
                "candidate_total": len(cold_candidates),
                "source_distribution": source_counter,
            },
            "stage2_rerank": {
                "method": "lexical_overlap_rerank",
                "selected_count": len(ranked_evidence[:evidence_top_k]),
            },
        },
    }
    meta_view = {
        "schema_version": WRITING_MEMORY_SCHEMA_VERSION,
        "prompt_version": WRITING_MEMORY_PROMPT_VERSION,
        "task_type": task_type,
        "session_key": session_key,
        "chapter_window": chapter_window,
        "style_card_source": style_card_source,
        "generated_at": _now_iso(),
    }
    hot_view = {
        "session_key": session_key,
        "state": hot_state,
    }

    pack = {
        "book_id": book_id,
        "memory_layers": {
            "hot": hot_view,
            "working": working_view,
            "cold": cold_view,
            "meta": meta_view,
            "hot_memory": hot_view,
            "working_memory": working_view,
            "cold_memory": cold_view,
            "meta_memory": meta_view,
        },
        "context_assembled": {
            "instruction": task_instruction,
            "hard_constraints": hard_constraints,
            "style_card": style_card,
            "context_text": context_text,
            "token_est": int(len(context_text) / 3) + 1,
            "task_bundle": task_bundle,
        },
        "generated_at": _now_iso(),
    }

    checkpoint_row = (
        await session.execute(
            text(
                """
                INSERT INTO writing_memory_checkpoint(
                  book_id, chapter_id, chapter_no, task_type,
                  input_payload, output_payload, quality, schema_version, prompt_version
                )
                VALUES (
                  CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), :chapter_no, :task_type,
                  CAST(:input_payload AS jsonb), CAST(:output_payload AS jsonb), CAST(:quality AS jsonb),
                  :schema_version, :prompt_version
                )
                RETURNING checkpoint_id::text AS checkpoint_id, created_at
                """
            ),
            {
                "book_id": book_id,
                "chapter_id": chapter_id,
                "chapter_no": chapter_no,
                "task_type": task_type,
                "input_payload": json.dumps(payload or {}, ensure_ascii=False),
                "output_payload": json.dumps(pack, ensure_ascii=False),
                "quality": json.dumps(
                    {
                        "hard_constraint_count": len(hard_constraints),
                        "evidence_count": len(ranked_evidence),
                        "token_est": int(len(context_text) / 3) + 1,
                    },
                    ensure_ascii=False,
                ),
                "schema_version": WRITING_MEMORY_SCHEMA_VERSION,
                "prompt_version": WRITING_MEMORY_PROMPT_VERSION,
            },
        )
    ).mappings().first()
    await session.commit()

    return {
        "ok": True,
        "checkpoint_id": str((checkpoint_row or {}).get("checkpoint_id") or ""),
        "created_at": str((checkpoint_row or {}).get("created_at") or ""),
        **pack,
    }


def _extract_writeback_sentence_spans(content: str) -> list[dict[str, Any]]:
    text_value = str(content or "")
    spans: list[dict[str, Any]] = []
    for idx, match in enumerate(re.finditer(r"[^。！？!?;\n\r]+", text_value), start=1):
        raw = str(match.group(0) or "")
        seg = raw.strip()
        if not seg:
            continue
        local_start = raw.find(seg)
        start = match.start() + (local_start if local_start >= 0 else 0)
        end = start + len(seg)
        spans.append(
            {
                "scene_id": f"S{idx}",
                "text": seg,
                "start": start,
                "end": end,
            }
        )
        if len(spans) >= 80:
            break
    return spans


def _extract_writeback_sentences(content: str) -> list[str]:
    return [str(x.get("text") or "") for x in _extract_writeback_sentence_spans(content)]


def _extract_writeback_facts(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in spans:
        sent = str(row.get("text") or "")
        if any(w in sent for w in CONFLICT_WORDS + PAYOFF_WORDS + RULE_WORDS):
            out.append(
                {
                    "entity_type": "character",
                    "entity_name": "主角",
                    "fact_type": "state",
                    "fact": sent[:120],
                    "evidence_span": sent[:160],
                    "evidence_ref": {
                        "scene_id": str(row.get("scene_id") or ""),
                        "offset": {"start": _safe_int(row.get("start"), 0), "end": _safe_int(row.get("end"), 0)},
                    },
                    "confidence": 0.7,
                }
            )
        if len(out) >= 24:
            break
    return out


def _extract_writeback_timeline(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for idx, row in enumerate(spans[:16], start=1):
        sent = str(row.get("text") or "")
        time_hint = ""
        for group in TIME_CONFLICT_WORD_GROUPS:
            for token in group:
                if token in sent:
                    time_hint = token
                    break
            if time_hint:
                break
        events.append(
            {
                "event_no": idx,
                "time_hint": time_hint or "当章",
                "location": "",
                "actors": ["主角"],
                "event": sent[:160],
                "consequence": "",
                "evidence_ref": {
                    "scene_id": str(row.get("scene_id") or ""),
                    "offset": {"start": _safe_int(row.get("start"), 0), "end": _safe_int(row.get("end"), 0)},
                },
            }
        )
    return events


async def validate_and_writeback_memory(session: AsyncSession, book_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    await ensure_story_engine_tables(session)
    content = str(payload.get("content") or "").strip()
    if not content:
        raise RuntimeError("content_required")
    session_key = str(payload.get("session_key") or "default").strip() or "default"
    writeback = bool(payload.get("writeback", True))

    chapter_ctx = await _resolve_chapter_context(session, book_id, payload)
    chapter_id = _to_uuid_str(chapter_ctx.get("chapter_id"))
    chapter_no = _safe_int(chapter_ctx.get("chapter_no"), 0) or None
    chapter_title = str(chapter_ctx.get("chapter_title") or "")

    bible = await get_story_bible_snapshot(session, book_id, limit=120, chapter_id=chapter_id)
    characters = [dict(x) for x in _safe_json_list(bible.get("characters"))]
    world_rules = [dict(x) for x in _safe_json_list(bible.get("world_rules"))]
    foreshadows = [dict(x) for x in _safe_json_list(bible.get("foreshadows"))]
    open_foreshadows = [x for x in foreshadows if str(x.get("status") or "") not in {"paid_off", "closed", "abandoned"}]

    sentence_spans = _extract_writeback_sentence_spans(content)
    sentences = [str(x.get("text") or "") for x in sentence_spans]
    char_names = {str(x.get("name") or "").strip() for x in characters if str(x.get("name") or "").strip()}
    text_names = {x for x in NAME_RE.findall(content) if 2 <= len(x) <= 4}
    unknown_names = sorted([x for x in text_names if x not in char_names])[:12]

    issues: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    baseline_style_row = await get_latest_style_evolution(session, book_id=book_id)
    baseline_metrics = (
        _safe_json_dict(_safe_json_dict(_safe_json_dict(baseline_style_row or {}).get("output")).get("result")).get("metrics")
        if isinstance(_safe_json_dict(_safe_json_dict(baseline_style_row or {}).get("output")).get("result"), dict)
        else {}
    )
    baseline_metrics = _safe_json_dict(baseline_metrics)
    current_metrics = _calc_sentence_metrics(content)
    anti_copy_guard = await _run_inline_anti_copy_guard(
        session,
        book_id=book_id,
        content=content,
        top_k=_clamp_int(payload.get("anti_copy_top_k"), default=8, low=4, high=16),
    )

    if unknown_names:
        issues.append(
            {
                "type": "character_consistency",
                "severity": "mid",
                "detail": f"检测到未入库角色：{', '.join(unknown_names)}",
            }
        )

    time_tokens = {token for group in TIME_CONFLICT_WORD_GROUPS for token in group if token in content}
    if {"清晨", "深夜"} <= time_tokens or {"早晨", "午夜"} <= time_tokens:
        issues.append(
            {
                "type": "timeline_conflict",
                "severity": "mid",
                "detail": "同章出现早晚强冲突时间词，需确认是否场景切换已交代。",
            }
        )

    if world_rules:
        rule_hit = 0
        for row in world_rules[:20]:
            key_text = str(row.get("key") or "").strip()
            val = _safe_json_dict(row.get("value"))
            probes = [key_text, str(val.get("rule") or ""), str(val.get("constraint") or ""), str(val.get("must") or "")]
            for probe in probes:
                p = probe.strip()
                if p and p[:6] in content:
                    rule_hit += 1
                    break
        if rule_hit == 0:
            issues.append(
                {
                    "type": "setting_consistency",
                    "severity": "low",
                    "detail": "正文未显式引用既有世界规则，建议补充限制/代价锚点。",
                }
            )

    rule_blob = " ".join(
        [
            str(x.get("key") or "")
            + " "
            + str(_safe_json_dict(x.get("value")).get("rule") or "")
            + " "
            + str(_safe_json_dict(x.get("value")).get("constraint") or "")
            + " "
            + str(_safe_json_dict(x.get("value")).get("cost") or "")
            for x in world_rules[:40]
        ]
    )
    if any(marker in content for marker in ABILITY_OVERFLOW_MARKERS) and (
        any(token in rule_blob for token in ["限制", "代价", "上限", "必须", "不能"]) or bool(world_rules)
    ):
        issues.append(
            {
                "type": "ability_limit_break",
                "severity": "mid",
                "detail": "正文出现疑似越级/无代价强化表达，与既有规则约束存在冲突风险。",
            }
        )

    drift_hits: list[str] = []
    for row in characters[:20]:
        name = str(row.get("name") or "").strip()
        if not name or name not in content:
            continue
        card = _safe_json_dict(row.get("card"))
        bottom_line = _extract_card_anchor_value(card, ["bottom_line", "taboo", "forbidden", "principle"])
        if bottom_line and any(marker in content for marker in PERSONA_BREAK_MARKERS):
            drift_hits.append(name)
    if drift_hits:
        issues.append(
            {
                "type": "character_drift",
                "severity": "mid",
                "detail": f"检测到潜在人设漂移风险角色：{', '.join(sorted(list(dict.fromkeys(drift_hits)))[:8])}",
            }
        )

    ai_phrase_hits = sum(content.count(p) for p in AI_SMELL_PHRASES if p)
    sentence_prefixes = [str(x.get("text") or "")[:4] for x in sentence_spans if str(x.get("text") or "").strip()]
    repeated_prefix = max([sentence_prefixes.count(x) for x in set(sentence_prefixes)] or [0])
    if ai_phrase_hits >= 3 or repeated_prefix >= 4:
        issues.append(
            {
                "type": "ai_smell",
                "severity": "low",
                "detail": "检测到模板化提示词痕迹或句式重复，建议执行去AI味改写。",
                "evidence": {"phrase_hits": ai_phrase_hits, "repeat_prefix_max": repeated_prefix},
            }
        )
    if str(anti_copy_guard.get("risk") or "") in {"mid", "high"}:
        issues.append(
            {
                "type": "anti_copy",
                "severity": ("high" if str(anti_copy_guard.get("risk") or "") == "high" else "mid"),
                "detail": "检测到较高文本相似风险，需执行强制改写策略后再发布。",
                "evidence": {
                    "max_ngram_overlap": anti_copy_guard.get("max_ngram_overlap"),
                    "top_hit": (anti_copy_guard.get("hits") or [None])[0],
                },
            }
        )

    baseline_avg_len = _safe_float(baseline_metrics.get("sentence_avg_len"), 0.0)
    baseline_short_ratio = _safe_float(baseline_metrics.get("short_sentence_ratio"), 0.0)
    if baseline_avg_len > 0 and current_metrics.get("sentence_count", 0.0) >= 8:
        avg_gap = abs(_safe_float(current_metrics.get("sentence_avg_len"), 0.0) - baseline_avg_len)
        short_gap = abs(_safe_float(current_metrics.get("short_sentence_ratio"), 0.0) - baseline_short_ratio)
        if avg_gap >= 8.0 or short_gap >= 0.22:
            issues.append(
                {
                    "type": "style_drift",
                    "severity": "low",
                    "detail": "句长/节奏与历史风格基线偏离较大，建议回调风格卡或执行风格重写。",
                    "evidence": {
                        "baseline": {
                            "sentence_avg_len": round(baseline_avg_len, 3),
                            "short_sentence_ratio": round(baseline_short_ratio, 4),
                        },
                        "current": {
                            "sentence_avg_len": round(_safe_float(current_metrics.get("sentence_avg_len"), 0.0), 3),
                            "short_sentence_ratio": round(_safe_float(current_metrics.get("short_sentence_ratio"), 0.0), 4),
                        },
                    },
                }
            )
    humanization_hints = _build_humanization_hints(
        content=content,
        ai_phrase_hits=ai_phrase_hits,
        repeated_prefix=repeated_prefix,
        current_metrics=current_metrics,
    )

    def _foreshadow_excerpt(text_value: str, title: str) -> str:
        t = str(title or "").strip()
        if not t:
            return ""
        pos = str(text_value or "").find(t)
        if pos < 0:
            return ""
        start = max(0, pos - 28)
        end = min(len(text_value), pos + len(t) + 36)
        return str(text_value[start:end]).replace("\n", " ").replace("\r", " ").strip()[:140]

    overdue_foreshadow_seeds: list[dict[str, Any]] = []
    if chapter_no and chapter_no > 0:
        for row in open_foreshadows[:40]:
            planned_payoff_chapter_id = _to_uuid_str(row.get("planned_payoff_chapter_id"))
            if not planned_payoff_chapter_id:
                continue
            planned_row = (
                await session.execute(
                    text(
                        """
                        SELECT "order" AS chapter_no
                        FROM chapter
                        WHERE chapter_id=CAST(:chapter_id AS uuid)
                        LIMIT 1
                        """
                    ),
                    {"chapter_id": planned_payoff_chapter_id},
                )
            ).mappings().first()
            planned_no = _safe_int((planned_row or {}).get("chapter_no"), 0)
            if planned_no > 0 and planned_no <= chapter_no:
                title = str(row.get("title") or "").strip()
                if not title:
                    continue
                matched_in_content = title in content
                overdue_foreshadow_seeds.append(
                    {
                        "foreshadow_id": str(row.get("foreshadow_id") or ""),
                        "title": title[:80],
                        "planned_chapter_no": planned_no,
                        "expected_payoff": str(row.get("expected_payoff") or "")[:180],
                        "question": str(row.get("question") or "")[:180],
                        "matched_in_content": matched_in_content,
                    }
                )
    unresolved_overdue_titles = [str(x.get("title") or "") for x in overdue_foreshadow_seeds if not bool(x.get("matched_in_content"))]
    if unresolved_overdue_titles:
        issues.append(
            {
                "type": "foreshadow_management",
                "severity": "mid",
                "detail": f"存在到期未回收伏笔：{', '.join(unresolved_overdue_titles[:6])}",
            }
        )
    foreshadow_resolution_suggestions: list[dict[str, Any]] = []
    for seed in overdue_foreshadow_seeds:
        title = str(seed.get("title") or "").strip()
        matched_in_content = bool(seed.get("matched_in_content"))
        suggestion: dict[str, Any] = {
            "foreshadow_id": str(seed.get("foreshadow_id") or ""),
            "title": title,
            "planned_chapter_no": _safe_int(seed.get("planned_chapter_no"), 0),
            "matched_in_content": matched_in_content,
            "expected_payoff": str(seed.get("expected_payoff") or ""),
            "question": str(seed.get("question") or ""),
        }
        if matched_in_content:
            suggestion.update(
                {
                    "action": "mark_payoff_candidate",
                    "reason": "正文命中伏笔标题，建议核对为回收事件并补充回收说明。",
                    "evidence_excerpt": _foreshadow_excerpt(content, title),
                }
            )
        else:
            suggestion.update(
                {
                    "action": "defer_with_note",
                    "reason": "到期伏笔未命中正文，建议给出延期说明或在下一章优先回收。",
                    "evidence_excerpt": "",
                }
            )
        foreshadow_resolution_suggestions.append(suggestion)
    matched_seed_ids = [str(x.get("foreshadow_id") or "") for x in foreshadow_resolution_suggestions if bool(x.get("matched_in_content")) and str(x.get("foreshadow_id") or "")]
    unresolved_seed_ids = [str(x.get("foreshadow_id") or "") for x in foreshadow_resolution_suggestions if (not bool(x.get("matched_in_content"))) and str(x.get("foreshadow_id") or "")]
    foreshadow_resolution_summary = {
        "overdue_count": len(overdue_foreshadow_seeds),
        "unresolved_count": len(unresolved_overdue_titles),
        "matched_count": len(overdue_foreshadow_seeds) - len(unresolved_overdue_titles),
        "matched_seed_ids": matched_seed_ids[:12],
        "unresolved_seed_ids": unresolved_seed_ids[:12],
    }

    checks.append({"name": "人物一致性", "status": "ok" if not unknown_names else "warn"})
    checks.append({"name": "时间线一致性", "status": "ok" if not any(x.get("type") == "timeline_conflict" for x in issues) else "warn"})
    checks.append({"name": "世界规则对齐", "status": "ok" if not any(x.get("type") == "setting_consistency" for x in issues) else "warn"})
    checks.append({"name": "伏笔负债", "status": "ok" if not unresolved_overdue_titles else "warn"})
    checks.append({"name": "能力上限校验", "status": "ok" if not any(x.get("type") == "ability_limit_break" for x in issues) else "warn"})
    checks.append({"name": "人设漂移校验", "status": "ok" if not any(x.get("type") == "character_drift" for x in issues) else "warn"})
    checks.append({"name": "风格漂移校验", "status": "ok" if not any(x.get("type") == "style_drift" for x in issues) else "warn"})
    checks.append({"name": "AI痕迹校验", "status": "ok" if not any(x.get("type") == "ai_smell" for x in issues) else "warn"})
    checks.append({"name": "反照抄校验", "status": "ok" if not any(x.get("type") == "anti_copy" for x in issues) else "warn"})

    score = 100
    for issue in issues:
        sev = str(issue.get("severity") or "")
        if sev == "high":
            score -= 25
        elif sev == "mid":
            score -= 15
        else:
            score -= 8
    score = max(0, min(100, score))

    writeback_stats = {"facts": 0, "timeline_events": 0, "growth": 0, "proposals": 0}
    commit_txn = str(uuid4())
    facts: list[dict[str, Any]] = []
    timeline_events: list[dict[str, Any]] = []
    proposal_count = 0
    if writeback and chapter_id:
        facts = _extract_writeback_facts(sentence_spans)
        for fact in facts:
            fact_payload = {k: v for k, v in fact.items() if k != "evidence_ref"}
            await session.execute(
                text(
                    """
                    INSERT INTO chapter_fact(
                      book_id, chapter_id, commit_txn_id, entity_type, entity_name, fact_type,
                      fact, evidence_span, evidence_ref, confidence, schema_version, prompt_version
                    )
                    VALUES (
                      CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), CAST(:commit_txn_id AS uuid), :entity_type, :entity_name, :fact_type,
                      :fact, :evidence_span, CAST(:evidence_ref AS jsonb), :confidence, :schema_version, :prompt_version
                    )
                    ON CONFLICT (commit_txn_id, entity_type, entity_name, fact_type, fact)
                    DO UPDATE SET
                      evidence_span=EXCLUDED.evidence_span,
                      evidence_ref=EXCLUDED.evidence_ref,
                      confidence=GREATEST(chapter_fact.confidence, EXCLUDED.confidence),
                      schema_version=EXCLUDED.schema_version,
                      prompt_version=EXCLUDED.prompt_version
                    """
                ),
                {
                    "book_id": book_id,
                    "chapter_id": chapter_id,
                    "commit_txn_id": commit_txn,
                    "schema_version": WRITING_MEMORY_SCHEMA_VERSION,
                    "prompt_version": WRITING_MEMORY_PROMPT_VERSION,
                    **fact_payload,
                    "evidence_ref": json.dumps(_safe_json_dict(fact.get("evidence_ref")), ensure_ascii=False),
                },
            )
        writeback_stats["facts"] = len(facts)

        timeline_events = _extract_writeback_timeline(sentence_spans)
        for event in timeline_events:
            event_payload = {k: v for k, v in event.items() if k != "evidence_ref"}
            await session.execute(
                text(
                    """
                    INSERT INTO chapter_timeline_event(
                      book_id, chapter_id, commit_txn_id, event_no, time_hint, location, actors, event, consequence, evidence_ref, schema_version, prompt_version
                    )
                    VALUES (
                      CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), CAST(:commit_txn_id AS uuid), :event_no, :time_hint, :location, CAST(:actors AS text[]), :event, :consequence,
                      CAST(:evidence_ref AS jsonb), :schema_version, :prompt_version
                    )
                    ON CONFLICT (commit_txn_id, event_no)
                    DO UPDATE SET
                      time_hint=EXCLUDED.time_hint,
                      location=EXCLUDED.location,
                      actors=EXCLUDED.actors,
                      event=EXCLUDED.event,
                      consequence=EXCLUDED.consequence,
                      evidence_ref=EXCLUDED.evidence_ref,
                      schema_version=EXCLUDED.schema_version,
                      prompt_version=EXCLUDED.prompt_version
                    """
                ),
                {
                    "book_id": book_id,
                    "chapter_id": chapter_id,
                    "commit_txn_id": commit_txn,
                    "schema_version": WRITING_MEMORY_SCHEMA_VERSION,
                    "prompt_version": WRITING_MEMORY_PROMPT_VERSION,
                    **event_payload,
                    "evidence_ref": json.dumps(_safe_json_dict(event.get("evidence_ref")), ensure_ascii=False),
                },
            )
        writeback_stats["timeline_events"] = len(timeline_events)

        growth_pressure = "高压推进" if any(w in content for w in CONFLICT_WORDS) else "常规推进"
        growth_gain = "兑现关键进展" if any(w in content for w in PAYOFF_WORDS) else "推进主线"
        growth_cost = "新增代价" if any(w in content for w in ["代价", "失去", "牺牲"]) else "代价待补全"
        await session.execute(
            text(
                """
                INSERT INTO character_growth_log(
                  book_id, chapter_id, commit_txn_id, character_name, pressure, cost, gain, change, trigger_event_no, confidence
                )
                VALUES (
                  CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), CAST(:commit_txn_id AS uuid), :character_name, :pressure, :cost, :gain, :change, :trigger_event_no, :confidence
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
            {
                "book_id": book_id,
                "chapter_id": chapter_id,
                "commit_txn_id": commit_txn,
                "character_name": "主角",
                "pressure": growth_pressure,
                "cost": growth_cost,
                "gain": growth_gain,
                "change": "本章后状态已更新",
                "trigger_event_no": 1,
                "confidence": 0.7,
            },
        )
        writeback_stats["growth"] = 1

        world_rule_keys = {str(x.get("key") or "").strip().lower() for x in world_rules if str(x.get("key") or "").strip()}
        proposal_count = 0
        for sent in sentences[:24]:
            if any(w in sent for w in RULE_WORDS):
                key = _text_head(sent, 32)
                if key.lower() in world_rule_keys:
                    continue
                await session.execute(
                    text(
                        """
                        INSERT INTO story_bible_proposal(book_id, proposal_type, entity_key, title, payload, reason, created_by, status, updated_at)
                        VALUES (
                          CAST(:book_id AS uuid), 'world_rule', :entity_key, :title, CAST(:payload AS jsonb),
                          :reason, 'memory_writeback', 'pending', now()
                        )
                        """
                    ),
                    {
                        "book_id": book_id,
                        "entity_key": key[:80],
                        "title": key[:80],
                        "payload": json.dumps(
                            {
                                "rule": sent[:180],
                                "source": "memory_writeback",
                                "evidence_ref": {"chapter_id": chapter_id, "commit_txn_id": commit_txn},
                                "schema_version": WRITING_MEMORY_SCHEMA_VERSION,
                                "prompt_version": WRITING_MEMORY_PROMPT_VERSION,
                            },
                            ensure_ascii=False,
                        ),
                        "reason": "写作回写识别到潜在新规则",
                    },
                )
                proposal_count += 1
            if any(w in sent for w in FORESHADOW_HINT_WORDS):
                title = _text_head(sent, 36)
                await session.execute(
                    text(
                        """
                        INSERT INTO story_bible_proposal(book_id, proposal_type, entity_key, title, payload, reason, created_by, status, updated_at)
                        VALUES (
                          CAST(:book_id AS uuid), 'foreshadow', :entity_key, :title, CAST(:payload AS jsonb),
                          :reason, 'memory_writeback', 'pending', now()
                        )
                        """
                    ),
                    {
                        "book_id": book_id,
                        "entity_key": title[:80],
                        "title": title[:80],
                        "payload": json.dumps(
                            {
                                "seed": sent[:180],
                                "source": "memory_writeback",
                                "evidence_ref": {"chapter_id": chapter_id, "commit_txn_id": commit_txn},
                                "schema_version": WRITING_MEMORY_SCHEMA_VERSION,
                                "prompt_version": WRITING_MEMORY_PROMPT_VERSION,
                            },
                            ensure_ascii=False,
                        ),
                        "reason": "写作回写识别到伏笔候选",
                    },
                )
                proposal_count += 1
            if proposal_count >= 8:
                break
        writeback_stats["proposals"] = proposal_count

        summary_state = {
            "session_key": session_key,
            "last_chapter_no": chapter_no,
            "last_chapter_title": chapter_title,
            "last_summary": _text_head(content, 220),
            "focus_entities": sorted(list(text_names))[:12],
            "last_commit_txn_id": commit_txn,
            "last_writeback_at": _now_iso(),
        }
        await upsert_writing_session_state(
            session,
            book_id,
            {"session_key": session_key, "mode": "merge", "state": summary_state},
        )
        await session.commit()

    report = {
        "ok": True,
        "book_id": book_id,
        "chapter_id": chapter_id,
        "chapter_no": chapter_no,
        "chapter_title": chapter_title,
        "score": score,
        "checks": checks,
        "issues": issues,
        "foreshadow_resolution_summary": foreshadow_resolution_summary,
        "foreshadow_resolution_suggestions": foreshadow_resolution_suggestions[:12],
        "anti_copy_guard": anti_copy_guard,
        "humanization_hints": humanization_hints,
        "writeback": writeback,
        "writeback_stats": writeback_stats,
        "writeback_delta": {
            "new_facts": [
                {
                    "entity_name": str(x.get("entity_name") or ""),
                    "fact_type": str(x.get("fact_type") or ""),
                    "fact": str(x.get("fact") or "")[:120],
                    "evidence_ref": _safe_json_dict(x.get("evidence_ref")),
                }
                for x in facts[:12]
            ],
            "new_foreshadow_proposals": int(proposal_count),
            "payoff_candidates": matched_seed_ids[:12],
            "contradictions": [x for x in issues if str(x.get("type") or "") in {"timeline_conflict", "setting_consistency", "character_drift", "ability_limit_break"}],
        },
        "consistency_metrics": {
            "issue_count": len(issues),
            "setting_conflict_count": sum(1 for x in issues if str(x.get("type") or "") in {"setting_consistency", "ability_limit_break"}),
            "timeline_conflict_count": sum(1 for x in issues if str(x.get("type") or "") == "timeline_conflict"),
            "character_drift_count": sum(1 for x in issues if str(x.get("type") or "") in {"character_consistency", "character_drift"}),
            "style_drift_count": sum(1 for x in issues if str(x.get("type") or "") == "style_drift"),
            "ai_smell_count": sum(1 for x in issues if str(x.get("type") or "") == "ai_smell"),
            "anti_copy_count": sum(1 for x in issues if str(x.get("type") or "") == "anti_copy"),
        },
        "memory_meta": {
            "schema_version": WRITING_MEMORY_SCHEMA_VERSION,
            "prompt_version": WRITING_MEMORY_PROMPT_VERSION,
            "session_key": session_key,
            "commit_txn_id": commit_txn if writeback and chapter_id else None,
        },
        "generated_at": _now_iso(),
    }
    checkpoint = (
        await session.execute(
            text(
                """
                INSERT INTO writing_memory_checkpoint(
                  book_id, chapter_id, chapter_no, task_type,
                  input_payload, output_payload, quality, schema_version, prompt_version
                )
                VALUES (
                  CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), :chapter_no, 'writeback',
                  CAST(:input_payload AS jsonb), CAST(:output_payload AS jsonb), CAST(:quality AS jsonb),
                  :schema_version, :prompt_version
                )
                RETURNING checkpoint_id::text AS checkpoint_id, created_at
                """
            ),
            {
                "book_id": book_id,
                "chapter_id": chapter_id,
                "chapter_no": chapter_no,
                "input_payload": json.dumps(payload or {}, ensure_ascii=False),
                "output_payload": json.dumps(report, ensure_ascii=False),
                "quality": json.dumps({"score": score, "issue_count": len(issues)}, ensure_ascii=False),
                "schema_version": WRITING_MEMORY_SCHEMA_VERSION,
                "prompt_version": WRITING_MEMORY_PROMPT_VERSION,
            },
        )
    ).mappings().first()
    await session.commit()

    return {
        **report,
        "checkpoint_id": str((checkpoint or {}).get("checkpoint_id") or ""),
        "checkpoint_created_at": str((checkpoint or {}).get("created_at") or ""),
    }


async def list_story_bible_proposals(
    session: AsyncSession,
    book_id: str,
    *,
    status: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    await ensure_story_engine_tables(session)
    lim = _clamp_int(limit, default=50, low=1, high=200)
    status_filter = str(status or "").strip().lower()
    query = """
      SELECT
        proposal_id::text AS proposal_id,
        proposal_type,
        entity_key,
        title,
        payload,
        status,
        reason,
        review_note,
        created_by,
        created_at,
        updated_at
      FROM story_bible_proposal
      WHERE book_id=CAST(:book_id AS uuid)
    """
    params: dict[str, Any] = {"book_id": book_id, "limit": lim}
    if status_filter:
        query += " AND status=:status"
        params["status"] = status_filter
    query += " ORDER BY created_at DESC LIMIT :limit"
    rows = (await session.execute(text(query), params)).mappings().all()
    return {
        "book_id": book_id,
        "status": status_filter or "all",
        "items": [dict(x) for x in rows],
        "total": len(rows),
    }


async def create_story_bible_proposal(session: AsyncSession, book_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    await ensure_story_engine_tables(session)
    proposal_type = str(payload.get("proposal_type") or "").strip().lower()
    if not proposal_type:
        raise RuntimeError("proposal_type_required")
    title = str(payload.get("title") or "").strip()
    entity_key = str(payload.get("entity_key") or "").strip()
    reason = str(payload.get("reason") or "").strip()
    created_by = str(payload.get("created_by") or "user").strip() or "user"
    body = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    if not title and not entity_key:
        raise RuntimeError("title_or_entity_key_required")
    row = (
        await session.execute(
            text(
                """
                INSERT INTO story_bible_proposal(book_id, proposal_type, entity_key, title, payload, reason, created_by, status, updated_at)
                VALUES (CAST(:book_id AS uuid), :proposal_type, :entity_key, :title, CAST(:payload AS jsonb), :reason, :created_by, 'pending', now())
                RETURNING
                  proposal_id::text AS proposal_id,
                  proposal_type,
                  entity_key,
                  title,
                  payload,
                  status,
                  reason,
                  created_by,
                  created_at,
                  updated_at
                """
            ),
            {
                "book_id": book_id,
                "proposal_type": proposal_type,
                "entity_key": entity_key,
                "title": title,
                "payload": json.dumps(body, ensure_ascii=False),
                "reason": reason,
                "created_by": created_by,
            },
        )
    ).mappings().first()
    await session.commit()
    return {"ok": True, "book_id": book_id, "item": dict(row or {})}


async def _apply_story_bible_proposal(session: AsyncSession, book_id: str, proposal: dict[str, Any]) -> dict[str, Any]:
    proposal_type = str(proposal.get("proposal_type") or "").strip().lower()
    entity_key = str(proposal.get("entity_key") or "").strip()
    title = str(proposal.get("title") or "").strip()
    payload = proposal.get("payload") if isinstance(proposal.get("payload"), dict) else {}
    applied: dict[str, Any] = {"applied_type": proposal_type}

    if proposal_type in {"world_rule", "world_fact", "setting"}:
        key = entity_key or title
        if not key:
            raise RuntimeError("world_rule_key_required")
        value = payload.get("value") if "value" in payload else payload
        confidence = _safe_float(payload.get("confidence"), 0.75)
        row = (
            await session.execute(
                text(
                    """
                    INSERT INTO world_fact(book_id, key, value, confidence, source_chunk_ids)
                    VALUES (CAST(:book_id AS uuid), :key, CAST(:value AS jsonb), :confidence, '{}'::uuid[])
                    ON CONFLICT(book_id, key) DO UPDATE SET
                      value=EXCLUDED.value,
                      confidence=GREATEST(world_fact.confidence, EXCLUDED.confidence)
                    RETURNING fact_id::text AS fact_id, key
                    """
                ),
                {
                    "book_id": book_id,
                    "key": key,
                    "value": json.dumps(value, ensure_ascii=False),
                    "confidence": confidence,
                },
            )
        ).mappings().first()
        applied.update({"target_table": "world_fact", "target_id": str((row or {}).get("fact_id") or ""), "target_key": key})
        return applied

    if proposal_type in {"character_fact", "character_card", "character"}:
        name = entity_key or title
        if not name:
            raise RuntimeError("character_name_required")
        role = str(payload.get("role") or "")
        char_row = (
            await session.execute(
                text(
                    """
                    INSERT INTO character(book_id, name, role)
                    VALUES (CAST(:book_id AS uuid), :name, :role)
                    ON CONFLICT(book_id, name) DO UPDATE SET
                      role=COALESCE(NULLIF(EXCLUDED.role, ''), character.role)
                    RETURNING character_id::text AS character_id, name
                    """
                ),
                {"book_id": book_id, "name": name, "role": role},
            )
        ).mappings().first()
        character_id = str((char_row or {}).get("character_id") or "")
        if not character_id:
            raise RuntimeError("character_upsert_failed")
        ver_row = (
            await session.execute(
                text(
                    """
                    SELECT COALESCE(MAX(version), 0) + 1 AS next_version
                    FROM character_version
                    WHERE character_id=CAST(:character_id AS uuid)
                    """
                ),
                {"character_id": character_id},
            )
        ).mappings().first()
        next_version = _safe_int((ver_row or {}).get("next_version"), 1)
        card_obj = payload.get("card") if isinstance(payload.get("card"), dict) else dict(payload)
        card_obj["name"] = name
        if role:
            card_obj["role"] = role
        cv_row = (
            await session.execute(
                text(
                    """
                    INSERT INTO character_version(character_id, version, card, source_chunk_ids)
                    VALUES (CAST(:character_id AS uuid), :version, CAST(:card AS jsonb), '{}'::uuid[])
                    RETURNING character_version_id::text AS character_version_id
                    """
                ),
                {"character_id": character_id, "version": next_version, "card": json.dumps(card_obj, ensure_ascii=False)},
            )
        ).mappings().first()
        applied.update(
            {
                "target_table": "character_version",
                "target_id": str((cv_row or {}).get("character_version_id") or ""),
                "character_id": character_id,
                "character_name": name,
                "version": next_version,
            }
        )
        return applied

    if proposal_type in {"timeline_event", "timeline"}:
        event_title = title or entity_key
        if not event_title:
            raise RuntimeError("timeline_title_required")
        chapter_id = str(payload.get("chapter_id") or "").strip() or None
        description = str(payload.get("description") or payload.get("statement") or payload.get("event") or "").strip()
        causality = payload.get("causality") if isinstance(payload.get("causality"), dict) else {}
        row = (
            await session.execute(
                text(
                    """
                    INSERT INTO timeline_event(book_id, chapter_id, title, description, causality, source_chunk_ids)
                    VALUES (CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), :title, :description, CAST(:causality AS jsonb), '{}'::uuid[])
                    RETURNING event_id::text AS event_id
                    """
                ),
                {
                    "book_id": book_id,
                    "chapter_id": chapter_id,
                    "title": event_title,
                    "description": description or event_title,
                    "causality": json.dumps(causality, ensure_ascii=False),
                },
            )
        ).mappings().first()
        applied.update({"target_table": "timeline_event", "target_id": str((row or {}).get("event_id") or "")})
        return applied

    if proposal_type in {"growth_milestone", "growth"}:
        character_name = str(payload.get("character_name") or entity_key or "主角").strip() or "主角"
        milestone_title = title or str(payload.get("title") or "").strip()
        if not milestone_title:
            raise RuntimeError("growth_title_required")
        no_row = (
            await session.execute(
                text(
                    """
                    SELECT COALESCE(MAX(milestone_no), 0) + 1 AS next_no
                    FROM growth_milestone
                    WHERE book_id=CAST(:book_id AS uuid) AND character_name=:character_name
                    """
                ),
                {"book_id": book_id, "character_name": character_name},
            )
        ).mappings().first()
        milestone_no = _safe_int(payload.get("milestone_no"), _safe_int((no_row or {}).get("next_no"), 1))
        row = (
            await session.execute(
                text(
                    """
                    INSERT INTO growth_milestone(
                      book_id, character_name, milestone_no, title, stage, priority, planned_scope,
                      planned_chapter_no, trigger, cost, choice_text, new_belief, payoff_template_type, status, meta
                    )
                    VALUES (
                      CAST(:book_id AS uuid), :character_name, :milestone_no, :title, :stage, :priority, :planned_scope,
                      :planned_chapter_no, :trigger, :cost, :choice_text, :new_belief, :payoff_template_type, :status, CAST(:meta AS jsonb)
                    )
                    ON CONFLICT(book_id, character_name, milestone_no) DO UPDATE SET
                      title=EXCLUDED.title,
                      stage=EXCLUDED.stage,
                      trigger=EXCLUDED.trigger,
                      cost=EXCLUDED.cost,
                      choice_text=EXCLUDED.choice_text,
                      new_belief=EXCLUDED.new_belief,
                      payoff_template_type=EXCLUDED.payoff_template_type,
                      status=EXCLUDED.status,
                      meta=EXCLUDED.meta,
                      updated_at=now()
                    RETURNING milestone_id::text AS milestone_id
                    """
                ),
                {
                    "book_id": book_id,
                    "character_name": character_name,
                    "milestone_no": milestone_no,
                    "title": milestone_title,
                    "stage": str(payload.get("stage") or "pressure"),
                    "priority": _clamp_int(payload.get("priority"), default=3, low=1, high=5),
                    "planned_scope": str(payload.get("planned_scope") or "volume"),
                    "planned_chapter_no": payload.get("planned_chapter_no"),
                    "trigger": str(payload.get("trigger") or ""),
                    "cost": str(payload.get("cost") or ""),
                    "choice_text": str(payload.get("choice_text") or ""),
                    "new_belief": str(payload.get("new_belief") or ""),
                    "payoff_template_type": str(payload.get("payoff_template_type") or "") or None,
                    "status": str(payload.get("status") or "planned"),
                    "meta": json.dumps(payload.get("meta") if isinstance(payload.get("meta"), dict) else {}, ensure_ascii=False),
                },
            )
        ).mappings().first()
        applied.update({"target_table": "growth_milestone", "target_id": str((row or {}).get("milestone_id") or "")})
        return applied

    if proposal_type in {"foreshadow", "foreshadow_seed"}:
        fs_title = title or str(payload.get("title") or "").strip()
        if not fs_title:
            raise RuntimeError("foreshadow_title_required")
        row = (
            await session.execute(
                text(
                    """
                    INSERT INTO foreshadow(
                      book_id, volume_id, title, type, scope, priority, status,
                      created_chapter_id, planned_payoff_chapter_id, question, expected_payoff, constraints, tags, risk_score, meta
                    )
                    VALUES (
                      CAST(:book_id AS uuid), CAST(:volume_id AS uuid), :title, :type, :scope, :priority, :status,
                      CAST(:created_chapter_id AS uuid), CAST(:planned_payoff_chapter_id AS uuid),
                      :question, :expected_payoff, CAST(:constraints AS text[]), CAST(:tags AS text[]), :risk_score, CAST(:meta AS jsonb)
                    )
                    RETURNING foreshadow_id::text AS foreshadow_id
                    """
                ),
                {
                    "book_id": book_id,
                    "volume_id": str(payload.get("volume_id") or "") or None,
                    "title": fs_title,
                    "type": str(payload.get("type") or "mystery"),
                    "scope": str(payload.get("scope") or "volume"),
                    "priority": _clamp_int(payload.get("priority"), default=3, low=1, high=5),
                    "status": str(payload.get("status") or "seeded"),
                    "created_chapter_id": str(payload.get("created_chapter_id") or "") or None,
                    "planned_payoff_chapter_id": str(payload.get("planned_payoff_chapter_id") or "") or None,
                    "question": str(payload.get("question") or ""),
                    "expected_payoff": str(payload.get("expected_payoff") or ""),
                    "constraints": payload.get("constraints") if isinstance(payload.get("constraints"), list) else [],
                    "tags": payload.get("tags") if isinstance(payload.get("tags"), list) else [],
                    "risk_score": _safe_float(payload.get("risk_score"), 0.0),
                    "meta": json.dumps(payload.get("meta") if isinstance(payload.get("meta"), dict) else {}, ensure_ascii=False),
                },
            )
        ).mappings().first()
        applied.update({"target_table": "foreshadow", "target_id": str((row or {}).get("foreshadow_id") or "")})
        return applied

    raise RuntimeError(f"unsupported_proposal_type:{proposal_type}")


async def review_story_bible_proposal(
    session: AsyncSession,
    book_id: str,
    proposal_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    await ensure_story_engine_tables(session)
    status = str(payload.get("status") or "").strip().lower()
    if status not in {"approved", "rejected"}:
        raise RuntimeError("status_must_be_approved_or_rejected")
    review_note = str(payload.get("review_note") or payload.get("reason") or "").strip()
    auto_apply = bool(payload.get("auto_apply", status == "approved"))
    proposal_row = (
        await session.execute(
            text(
                """
                SELECT
                  proposal_id::text AS proposal_id,
                  proposal_type,
                  entity_key,
                  title,
                  payload,
                  status,
                  reason
                FROM story_bible_proposal
                WHERE proposal_id=CAST(:proposal_id AS uuid) AND book_id=CAST(:book_id AS uuid)
                LIMIT 1
                """
            ),
            {"proposal_id": proposal_id, "book_id": book_id},
        )
    ).mappings().first()
    if not proposal_row:
        raise RuntimeError("proposal_not_found")
    proposal = dict(proposal_row)
    applied_result: dict[str, Any] | None = None
    final_status = status
    if status == "approved" and auto_apply:
        applied_result = await _apply_story_bible_proposal(session, book_id, proposal)
        final_status = "applied"
    updated = (
        await session.execute(
            text(
                """
                UPDATE story_bible_proposal
                SET status=:status, review_note=:review_note, updated_at=now()
                WHERE proposal_id=CAST(:proposal_id AS uuid) AND book_id=CAST(:book_id AS uuid)
                RETURNING proposal_id::text AS proposal_id, status, review_note, updated_at
                """
            ),
            {
                "proposal_id": proposal_id,
                "book_id": book_id,
                "status": final_status,
                "review_note": review_note,
            },
        )
    ).mappings().first()
    await session.commit()
    return {
        "ok": True,
        "book_id": book_id,
        "proposal_id": proposal_id,
        "status": str((updated or {}).get("status") or final_status),
        "review_note": str((updated or {}).get("review_note") or review_note),
        "applied": applied_result,
    }


async def _load_recent_selected_drafts(session: AsyncSession, book_id: str, limit: int = 10) -> list[dict[str, Any]]:
    try:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT
                      c.chapter_id::text AS chapter_id,
                      c."order" AS chapter_no,
                      c.title,
                      cd.text
                    FROM chapter_selected cs
                    JOIN chapter c ON c.chapter_id=cs.chapter_id
                    JOIN chapter_draft cd ON cd.draft_id=cs.selected_draft_id
                    WHERE c.book_id=CAST(:book_id AS uuid)
                    ORDER BY c."order" DESC
                    LIMIT :limit
                    """
                ),
                {"book_id": book_id, "limit": _clamp_int(limit, default=10, low=3, high=20)},
            )
        ).mappings().all()
        return [dict(x) for x in rows]
    except Exception:
        return []


async def _load_recent_conflict_types(session: AsyncSession, book_id: str, limit: int = 3) -> list[str]:
    rows = (
        await session.execute(
            text(
                """
                SELECT conflict_type
                FROM chapter_scene_pack
                WHERE book_id=CAST(:book_id AS uuid)
                  AND conflict_type <> ''
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"book_id": book_id, "limit": _clamp_int(limit, default=3, low=1, high=8)},
        )
    ).mappings().all()
    return [str(x.get("conflict_type") or "").strip() for x in rows if str(x.get("conflict_type") or "").strip()]


def _pick_conflict_type(preferred: str, recent_types: list[str]) -> str:
    if preferred and preferred in CONFLICT_TEMPLATE_LIBRARY:
        return preferred
    blocked = {x for x in recent_types[:3]}
    for key in CONFLICT_ORDER:
        if key not in blocked:
            return key
    return CONFLICT_ORDER[0]


def _build_scene_cards(
    *,
    conflict_key: str,
    chapter_goal: str,
    suspense_type: str,
    scene_count: int,
    active_foreshadows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    count = _clamp_int(scene_count, default=5, low=3, high=8)
    fs_titles = [str(x.get("title") or "") for x in active_foreshadows[:3] if str(x.get("title") or "").strip()]
    template = CONFLICT_TEMPLATE_LIBRARY.get(conflict_key) or CONFLICT_TEMPLATE_LIBRARY["information_gap"]
    cards: list[dict[str, Any]] = []
    for idx in range(count):
        stage = "推进"
        if idx == 0:
            stage = "开场压力"
        elif idx == count - 1:
            stage = "悬念收束"
        elif idx == count - 2:
            stage = "兑现爆发"
        elif idx == 1:
            stage = "冲突升级"
        fs_bind = fs_titles[idx % len(fs_titles)] if fs_titles else ""
        cards.append(
            {
                "scene_no": idx + 1,
                "stage": stage,
                "goal": chapter_goal if idx == 0 else f"围绕“{chapter_goal or '章目标'}”继续推进",
                "main_action": template["upgrade"] if idx <= 1 else ("执行爽点兑现" if idx == count - 2 else "推进信息与情绪"),
                "expected_output": "必须产生可追踪变化（人物/关系/资源至少一项）",
                "foreshadow_bind": fs_bind,
                "suspense": suspense_type if idx == count - 1 else "",
            }
        )
    return cards


async def build_chapter_engine_pack(session: AsyncSession, book_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    await ensure_story_engine_tables(session)
    chapter_id = str(payload.get("chapter_id") or "").strip() or None
    chapter_no = _safe_int(payload.get("chapter_no"), 0) or None
    chapter_title = str(payload.get("chapter_title") or "").strip()
    if chapter_id and not chapter_no:
        row = (
            await session.execute(
                text(
                    """
                    SELECT "order" AS chapter_no, title
                    FROM chapter
                    WHERE chapter_id=CAST(:chapter_id AS uuid) AND book_id=CAST(:book_id AS uuid)
                    LIMIT 1
                    """
                ),
                {"chapter_id": chapter_id, "book_id": book_id},
            )
        ).mappings().first()
        if row:
            chapter_no = _safe_int((row or {}).get("chapter_no"), 0) or chapter_no
            if not chapter_title:
                chapter_title = str((row or {}).get("title") or "")
    if not chapter_title:
        chapter_title = f"第{chapter_no or 0}章"

    preferred_conflict = str(payload.get("conflict_type") or "").strip().lower()
    scene_count = _clamp_int(payload.get("scene_count"), default=5, low=3, high=8)
    suspense_type = str(payload.get("suspense_type") or "new_threat").strip() or "new_threat"
    volume_goal = str(payload.get("volume_goal") or "").strip()
    arc_goal = str(payload.get("arc_goal") or "").strip()
    chapter_goal = str(payload.get("chapter_goal") or "").strip()
    chapter_gain = str(payload.get("chapter_gain") or "兑现一个关键进展").strip()
    chapter_cost = str(payload.get("chapter_cost") or "新增明确代价").strip()
    chapter_function_raw = str(payload.get("chapter_function") or "").strip()

    bible = await get_story_bible_snapshot(session, book_id, limit=40, chapter_id=chapter_id)
    recent_types = await _load_recent_conflict_types(session, book_id, limit=3)
    conflict_key = _pick_conflict_type(preferred_conflict, recent_types)
    conflict_tpl = CONFLICT_TEMPLATE_LIBRARY.get(conflict_key) or CONFLICT_TEMPLATE_LIBRARY["information_gap"]
    recent_chapters = await _load_recent_selected_drafts(session, book_id, limit=10)
    recent_summary = [
        {
            "chapter_no": x.get("chapter_no"),
            "title": x.get("title"),
            "summary": _text_head(str(x.get("text") or ""), limit=180),
        }
        for x in recent_chapters
    ]
    active_foreshadows = [x for x in (bible.get("foreshadows") if isinstance(bible.get("foreshadows"), list) else []) if str((x or {}).get("status") or "") not in {"paid_off", "closed", "abandoned"}]
    chapter_function_cycle = ["信息章", "行动章", "反转章", "回收章"]
    chapter_function = chapter_function_raw if chapter_function_raw in chapter_function_cycle else chapter_function_cycle[(max(1, _safe_int(chapter_no, 1)) - 1) % len(chapter_function_cycle)]
    beat_template = [
        {"beat": "起手钩子", "goal": "开场 20% 内给出风险/异常点", "required": True},
        {"beat": "推进", "goal": "主线目标有可验证推进", "required": True},
        {"beat": "升级", "goal": "对手/规则/代价至少一项升级", "required": True},
        {"beat": "反转", "goal": "新增信息或立场反转", "required": chapter_function in {"反转章", "行动章"}},
        {"beat": "结算", "goal": "兑现阶段性收益并付出成本", "required": chapter_function in {"回收章", "行动章"}},
        {"beat": "新钩子", "goal": "章末抛出下一章驱动力", "required": True},
    ]
    tension_curve_plan = {
        "target_points": [0.52, 0.61, 0.73, 0.82, 0.66, 0.78],
        "must_escalate_count": 2,
        "must_have_reversal": chapter_function in {"反转章", "行动章"},
        "must_have_payoff": chapter_function in {"回收章", "行动章"},
    }
    payoff_priority = sorted(
        [
            x
            for x in active_foreshadows
            if _safe_int(x.get("priority"), 0) >= 3
        ],
        key=lambda r: (_safe_int(r.get("priority"), 0), str(r.get("updated_at") or "")),
        reverse=True,
    )
    foreshadow_budget = {
        "seed_max": 2 if chapter_function in {"信息章", "反转章"} else 1,
        "payoff_min": 1 if chapter_function in {"回收章", "行动章"} else 0,
        "open_total": len(active_foreshadows),
        "priority_payoff_ids": [str(x.get("foreshadow_id") or "") for x in payoff_priority[:6] if str(x.get("foreshadow_id") or "").strip()],
        "priority_payoff_titles": [str(x.get("title") or "") for x in payoff_priority[:6] if str(x.get("title") or "").strip()],
    }
    scene_cards = _build_scene_cards(
        conflict_key=conflict_key,
        chapter_goal=chapter_goal,
        suspense_type=suspense_type,
        scene_count=scene_count,
        active_foreshadows=active_foreshadows,
    )
    conflict_card = {
        "conflict_type": conflict_key,
        "conflict_label": conflict_tpl["label"],
        "chapter_goal": chapter_goal or "推进本章主目标",
        "resistance_source": str(payload.get("resistance_source") or "对手+规则+资源限制"),
        "upgrade_method": conflict_tpl["upgrade"],
        "payoff": str(payload.get("payoff") or conflict_tpl["payoff"]),
        "cliffhanger": str(payload.get("cliffhanger") or conflict_tpl["cliffhanger"]),
        "cost_anchor": chapter_cost,
        "gain_anchor": chapter_gain,
    }
    pack_payload = {
        "book_id": book_id,
        "chapter_id": chapter_id,
        "chapter_no": chapter_no,
        "chapter_title": chapter_title,
        "fractal_targets": {
            "volume_goal": volume_goal,
            "arc_goal": arc_goal,
            "chapter_goal": chapter_goal,
        },
        "conflict_card": conflict_card,
        "scene_cards": scene_cards,
        "checklist": {
            "chapter_must_have": {"推进": 1, "兑现": 1, "悬念": 1},
            "arc_must_have": {"目标变化次数": ">=2"},
            "volume_must_have": {"规则升级次数": ">=1"},
            "required_actions": [
                "正文扩写前必须先确认冲突卡与场景卡",
                "每个场景只承载一个主功能（信息/冲突/情绪/转折）",
                "本章完成后必须更新事实层与伏笔台账",
            ],
        },
        "planner": {
            "chapter_function": chapter_function,
            "beat_template": beat_template,
            "tension_curve_plan": tension_curve_plan,
            "foreshadow_budget": foreshadow_budget,
            "conflict_curve_guard": {
                "target_conflict_type": conflict_key,
                "must_have_upgrade": True,
                "must_have_hook": True,
            },
        },
        "input_package": {
            "story_bible_summary": bible.get("summary"),
            "recent_chapter_summary": recent_summary[:10],
            "active_foreshadows": [
                {
                    "foreshadow_id": x.get("foreshadow_id"),
                    "title": x.get("title"),
                    "status": x.get("status"),
                    "priority": x.get("priority"),
                }
                for x in active_foreshadows[:12]
            ],
            "character_roster": [
                {"name": x.get("name"), "role": x.get("role")}
                for x in (bible.get("characters") if isinstance(bible.get("characters"), list) else [])[:20]
            ],
            "world_rules": [
                {"key": x.get("key"), "confidence": x.get("confidence")}
                for x in (bible.get("world_rules") if isinstance(bible.get("world_rules"), list) else [])[:20]
            ],
            "timeline_refs": [
                {"title": x.get("title"), "description": _text_head(str(x.get("description") or ""), 120)}
                for x in (bible.get("timeline") if isinstance(bible.get("timeline"), list) else [])[:20]
            ],
        },
        "generated_at": _now_iso(),
    }
    inserted = (
        await session.execute(
            text(
                """
                INSERT INTO chapter_scene_pack(book_id, chapter_id, chapter_no, chapter_title, conflict_type, payload)
                VALUES (CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), :chapter_no, :chapter_title, :conflict_type, CAST(:payload AS jsonb))
                RETURNING pack_id::text AS pack_id, created_at
                """
            ),
            {
                "book_id": book_id,
                "chapter_id": chapter_id,
                "chapter_no": chapter_no,
                "chapter_title": chapter_title,
                "conflict_type": conflict_key,
                "payload": json.dumps(pack_payload, ensure_ascii=False),
            },
        )
    ).mappings().first()
    await session.commit()
    return {
        "ok": True,
        "book_id": book_id,
        "pack_id": str((inserted or {}).get("pack_id") or ""),
        "created_at": str((inserted or {}).get("created_at") or ""),
        "pack": pack_payload,
    }


def _score_to_level(score: int) -> str:
    if score >= 4:
        return "good"
    if score >= 3:
        return "watch"
    return "risk"


def _build_repair_actions(score_map: dict[str, int], issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    issue_map = {str(x.get("dimension") or ""): x for x in issues}
    repair_rules: list[tuple[str, str, str]] = [
        ("causal_chain", "补强因果链", "为每个关键结果补一条“因为→所以”桥接句，避免无因转折。"),
        ("character_consistency", "回填人物动机", "为关键行为补充人物目标/底线说明，并与人物卡字段对齐。"),
        ("setting_consistency", "核对设定约束", "在冲突关键段引用世界规则，明确限制与代价。"),
        ("rhythm_payoff", "提升兑现密度", "本章补一个明确爽点回收，避免连续水章。"),
        ("suspense_quality", "强化章末钩子", "章末追加新威胁/新信息/新代价至少一项。"),
        ("foreshadow_management", "清理伏笔负债", "处理过期伏笔：回收或标记废弃并给出解释。"),
    ]
    priority = 1
    for key, title, prompt in repair_rules:
        score = _safe_int(score_map.get(key), 0)
        if score >= 4:
            continue
        issue = issue_map.get(key) or {}
        actions.append(
            {
                "priority": priority,
                "dimension": key,
                "title": title,
                "current_score": score,
                "target_score": 4,
                "problem": str(issue.get("problem") or ""),
                "repair_prompt": prompt,
            }
        )
        priority += 1
    return actions


async def run_chapter_engine_audit(session: AsyncSession, book_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    await ensure_story_engine_tables(session)
    content = str(payload.get("content") or "").strip()
    if not content:
        raise RuntimeError("content_required")
    chapter_id = str(payload.get("chapter_id") or "").strip() or None
    chapter_no = _safe_int(payload.get("chapter_no"), 0) or None
    chapter_title = str(payload.get("chapter_title") or "").strip()
    threshold = _clamp_int(payload.get("threshold"), default=22, low=12, high=30)
    if chapter_id and not chapter_no:
        row = (
            await session.execute(
                text(
                    """
                    SELECT "order" AS chapter_no, title
                    FROM chapter
                    WHERE chapter_id=CAST(:chapter_id AS uuid) AND book_id=CAST(:book_id AS uuid)
                    LIMIT 1
                    """
                ),
                {"chapter_id": chapter_id, "book_id": book_id},
            )
        ).mappings().first()
        if row:
            chapter_no = _safe_int((row or {}).get("chapter_no"), 0) or chapter_no
            if not chapter_title:
                chapter_title = str((row or {}).get("title") or "")
    chapter_title = chapter_title or f"第{chapter_no or 0}章"

    bible = await get_story_bible_snapshot(session, book_id, limit=80, chapter_id=chapter_id)
    characters = bible.get("characters") if isinstance(bible.get("characters"), list) else []
    world_rules = bible.get("world_rules") if isinstance(bible.get("world_rules"), list) else []
    foreshadows = bible.get("foreshadows") if isinstance(bible.get("foreshadows"), list) else []
    char_names = {str(x.get("name") or "") for x in characters if str(x.get("name") or "").strip()}
    text_names = {x for x in NAME_RE.findall(content) if 2 <= len(x) <= 4}
    unknown_names = sorted([x for x in text_names if x not in char_names])[:8]

    causal_hits = sum(content.count(w) for w in CAUSAL_WORDS)
    rule_hits = sum(content.count(w) for w in RULE_WORDS)
    conflict_hits = sum(content.count(w) for w in CONFLICT_WORDS)
    payoff_hits = sum(content.count(w) for w in PAYOFF_WORDS)
    suspense_hits = sum(content.count(w) for w in SUSPENSE_MARKERS)
    paragraph_count = len([x for x in content.splitlines() if x.strip()])

    causal_score = min(5, max(1, 1 + causal_hits))
    if paragraph_count < 3:
        causal_score = max(1, causal_score - 1)

    character_score = 5
    if unknown_names:
        character_score = max(1, 5 - min(3, len(unknown_names)))
    elif char_names and not text_names:
        character_score = 3

    setting_score = 3
    if world_rules:
        setting_score = 5 if rule_hits >= 2 else 3
    if not world_rules:
        setting_score = 2

    rhythm_score = min(5, max(1, 1 + conflict_hits + min(2, payoff_hits)))
    suspense_score = min(5, max(1, 1 + suspense_hits))
    if not content.endswith(("？", "?", "！", "!", "…")):
        suspense_score = max(1, suspense_score - 1)

    open_fs = [x for x in foreshadows if str((x or {}).get("status") or "") not in {"paid_off", "closed", "abandoned"}]
    foreshadow_score = 5
    if len(open_fs) >= 18:
        foreshadow_score = 2
    elif len(open_fs) >= 12:
        foreshadow_score = 3
    elif len(open_fs) >= 8:
        foreshadow_score = 4

    score_map = {
        "causal_chain": int(causal_score),
        "character_consistency": int(character_score),
        "setting_consistency": int(setting_score),
        "rhythm_payoff": int(rhythm_score),
        "suspense_quality": int(suspense_score),
        "foreshadow_management": int(foreshadow_score),
    }
    total_score = int(sum(score_map.values()))
    status = "pass" if total_score >= threshold else "needs_rework"
    issues: list[dict[str, Any]] = []
    if causal_score < 4:
        issues.append(
            {
                "dimension": "causal_chain",
                "level": _score_to_level(int(causal_score)),
                "problem": "因果连接词偏少，可能出现无因跳转。",
                "evidence": {"causal_hits": causal_hits, "paragraph_count": paragraph_count},
            }
        )
    if character_score < 4:
        issues.append(
            {
                "dimension": "character_consistency",
                "level": _score_to_level(int(character_score)),
                "problem": "人物一致性不足，存在未登记角色或行为依据不足。",
                "evidence": {"unknown_names": unknown_names, "known_character_count": len(char_names)},
            }
        )
    if setting_score < 4:
        issues.append(
            {
                "dimension": "setting_consistency",
                "level": _score_to_level(int(setting_score)),
                "problem": "设定引用不足，规则约束不够明确。",
                "evidence": {"world_rule_count": len(world_rules), "rule_word_hits": rule_hits},
            }
        )
    if rhythm_score < 4:
        issues.append(
            {
                "dimension": "rhythm_payoff",
                "level": _score_to_level(int(rhythm_score)),
                "problem": "冲突/爽点密度不足，章节推进感偏弱。",
                "evidence": {"conflict_hits": conflict_hits, "payoff_hits": payoff_hits},
            }
        )
    if suspense_score < 4:
        issues.append(
            {
                "dimension": "suspense_quality",
                "level": _score_to_level(int(suspense_score)),
                "problem": "章末钩子不明显，下一章驱动力不足。",
                "evidence": {"suspense_hits": suspense_hits, "ending": _text_head(content[-120:], 120)},
            }
        )
    if foreshadow_score < 4:
        issues.append(
            {
                "dimension": "foreshadow_management",
                "level": _score_to_level(int(foreshadow_score)),
                "problem": "伏笔负债偏高，建议优先回收或关闭旧伏笔。",
                "evidence": {"open_foreshadow_count": len(open_fs)},
            }
        )

    actions = _build_repair_actions(score_map, issues)
    repair_plan = {
        "status": status,
        "target_threshold": threshold,
        "actions": actions,
        "next_step": "执行定向修订后重新跑章节体检",
    }
    row = (
        await session.execute(
            text(
                """
                INSERT INTO chapter_audit_snapshot(
                  book_id, chapter_id, chapter_no, chapter_title, total_score, threshold, status, score_map, issues, repair_plan
                )
                VALUES (
                  CAST(:book_id AS uuid), CAST(:chapter_id AS uuid), :chapter_no, :chapter_title, :total_score, :threshold, :status,
                  CAST(:score_map AS jsonb), CAST(:issues AS jsonb), CAST(:repair_plan AS jsonb)
                )
                RETURNING audit_id::text AS audit_id, created_at
                """
            ),
            {
                "book_id": book_id,
                "chapter_id": chapter_id,
                "chapter_no": chapter_no,
                "chapter_title": chapter_title,
                "total_score": total_score,
                "threshold": threshold,
                "status": status,
                "score_map": json.dumps(score_map, ensure_ascii=False),
                "issues": json.dumps(issues, ensure_ascii=False),
                "repair_plan": json.dumps(repair_plan, ensure_ascii=False),
            },
        )
    ).mappings().first()
    await session.commit()
    return {
        "ok": True,
        "book_id": book_id,
        "audit_id": str((row or {}).get("audit_id") or ""),
        "chapter_no": chapter_no,
        "chapter_title": chapter_title,
        "total_score": total_score,
        "threshold": threshold,
        "status": status,
        "score_map": score_map,
        "issues": issues,
        "repair_plan": repair_plan,
        "created_at": str((row or {}).get("created_at") or ""),
    }


async def build_chapter_repair_plan(session: AsyncSession, book_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    await ensure_story_engine_tables(session)
    audit_id = str(payload.get("audit_id") or "").strip()
    chapter_no = _safe_int(payload.get("chapter_no"), 0) or None
    chapter_id = str(payload.get("chapter_id") or "").strip() or None
    row = None
    if audit_id:
        row = (
            await session.execute(
                text(
                    """
                    SELECT
                      audit_id::text AS audit_id,
                      chapter_no,
                      chapter_title,
                      total_score,
                      threshold,
                      status,
                      score_map,
                      issues,
                      repair_plan,
                      created_at
                    FROM chapter_audit_snapshot
                    WHERE audit_id=CAST(:audit_id AS uuid) AND book_id=CAST(:book_id AS uuid)
                    LIMIT 1
                    """
                ),
                {"audit_id": audit_id, "book_id": book_id},
            )
        ).mappings().first()
    if not row and chapter_id:
        row = (
            await session.execute(
                text(
                    """
                    SELECT
                      audit_id::text AS audit_id,
                      chapter_no,
                      chapter_title,
                      total_score,
                      threshold,
                      status,
                      score_map,
                      issues,
                      repair_plan,
                      created_at
                    FROM chapter_audit_snapshot
                    WHERE chapter_id=CAST(:chapter_id AS uuid) AND book_id=CAST(:book_id AS uuid)
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"chapter_id": chapter_id, "book_id": book_id},
            )
        ).mappings().first()
    if not row and chapter_no is not None:
        row = (
            await session.execute(
                text(
                    """
                    SELECT
                      audit_id::text AS audit_id,
                      chapter_no,
                      chapter_title,
                      total_score,
                      threshold,
                      status,
                      score_map,
                      issues,
                      repair_plan,
                      created_at
                    FROM chapter_audit_snapshot
                    WHERE chapter_no=:chapter_no AND book_id=CAST(:book_id AS uuid)
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"chapter_no": chapter_no, "book_id": book_id},
            )
        ).mappings().first()
    if not row:
        raise RuntimeError("audit_snapshot_not_found")

    score_map = row.get("score_map") if isinstance(row.get("score_map"), dict) else {}
    issues = row.get("issues") if isinstance(row.get("issues"), list) else []
    actions = _build_repair_actions({str(k): _safe_int(v, 0) for k, v in score_map.items()}, issues)
    out = {
        "book_id": book_id,
        "audit_id": str(row.get("audit_id") or ""),
        "chapter_no": row.get("chapter_no"),
        "chapter_title": str(row.get("chapter_title") or ""),
        "status": str(row.get("status") or ""),
        "total_score": _safe_int(row.get("total_score"), 0),
        "threshold": _safe_int(row.get("threshold"), 22),
        "issues": issues,
        "actions": actions,
        "generated_at": _now_iso(),
    }
    await session.execute(
        text(
            """
            UPDATE chapter_audit_snapshot
            SET repair_plan=CAST(:repair_plan AS jsonb)
            WHERE audit_id=CAST(:audit_id AS uuid)
            """
        ),
        {"audit_id": str(row.get("audit_id") or ""), "repair_plan": json.dumps(out, ensure_ascii=False)},
    )
    await session.commit()
    return {"ok": True, "plan": out}
