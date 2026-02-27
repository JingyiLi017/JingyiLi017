from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from .llm_provider import resolve_llm_provider
from .ollama_client import OllamaClient
from .splitbook_prompt_pack import (
    CANDIDATE_SCHEMA_VERSION as PROMPT_CANDIDATE_SCHEMA_VERSION,
    PROMPT_VERSION as PROMPT_PACK_VERSION,
    SCENE_SCHEMA_VERSION as PROMPT_SCENE_SCHEMA_VERSION,
    build_user_prompt_a as build_candidate_user_prompt,
    build_user_prompt_b as build_judge_user_prompt,
    build_user_prompt_c as build_fix_json_user_prompt,
    candidate_schema_hint as candidate_schema_hint_text,
    scene_record_schema_hint as scene_record_schema_hint_text,
    system_prompt_a as candidate_system_prompt_text,
    system_prompt_b as judge_system_prompt_text,
    system_prompt_c as fix_json_system_prompt_text,
)
from .storage import create_profile, get_splitbook, update_splitbook_status


CHAPTER_RE = re.compile(
    r"^\s*(?:"
    r"第\s*[0-9零一二三四五六七八九十百千万两〇○Ｏ]+\s*[章回节卷部幕](?:\s*[:：\-—_.、]?\s*.*)?"
    r"|chapter\s*\d+(?:\s*[:：\-—_.、]?\s*.*)?"
    r"|序章|楔子|引子|终章|尾声|后记|番外.*"
    r")\s*$",
    re.IGNORECASE,
)
CHAPTER_INLINE_RE = re.compile(
    r"(?:"
    r"第\s*[0-9零一二三四五六七八九十百千万两〇○Ｏ]+\s*[章回节卷部幕](?:\s*[:：\-—_.、]?\s*[^\n\r]{0,56})?"
    r"|chapter\s*\d+(?:\s*[:：\-—_.、]?\s*[^\n\r]{0,56})?"
    r"|序章|楔子|引子|终章|尾声|后记|番外[^\n\r]{0,36}"
    r")",
    re.IGNORECASE,
)
CHAPTER_MARKER_BOUNDARY_PREV = set(" \t\r\n　([{【<“‘\"'|/\\-—_~·。！？!?；;，,、")
NAME_RE = re.compile(r"([\u4e00-\u9fff]{2,4})(?:说道|说|问|想|看|笑|哭|点头|摇头|沉默|开口)")
TIME_WORDS = ["今天", "昨日", "昨天", "次日", "清晨", "上午", "中午", "下午", "傍晚", "夜里", "深夜", "随后", "然后", "最终", "同时"]
WORLD_WORDS = ["规则", "设定", "系统", "法则", "世界", "等级", "境界", "能力", "技能", "约束", "限制", "宗门", "契约"]
CONFLICT_WORDS = ["冲突", "对抗", "矛盾", "危机", "威胁", "压制", "反击", "追杀", "陷阱"]
FORESHADOW_WORDS = ["伏笔", "暗示", "预示", "将会", "似乎", "隐约", "埋下"]
PAYOFF_WORDS = ["回收", "揭晓", "兑现", "真相", "答案", "反转", "应验"]
PRESSURE_WORDS = ["压力", "逼迫", "倒计时", "追击", "濒临", "危急", "窒息", "崩溃"]
COST_WORDS = ["代价", "牺牲", "损失", "受伤", "失去", "透支", "后果", "惩罚"]
GAIN_WORDS = ["收获", "突破", "成长", "觉醒", "提升", "获得", "领悟", "掌握"]
SCENE_HARD_MARKERS = ["——", "***", "***", "【", "】", "与此同时", "另一边", "另一处", "同一时间"]
SCENE_TIME_SHIFT_WORDS = [
    "次日",
    "翌日",
    "三天后",
    "两天后",
    "一天后",
    "数日后",
    "当晚",
    "入夜",
    "清晨",
    "傍晚",
]
LOCATION_RE = re.compile(r"(?:在|到|回到|来到|抵达|进入|潜入)([\u4e00-\u9fff]{2,12}(?:镇|城|村|山|谷|宫|殿|门|派|府|州|岛|海|街|楼|塔|院))")
FORESHADOW_SIGNAL_WORDS = ["发烫", "异响", "裂纹", "符文", "隐约", "没在意", "却不知", "异常", "不对劲", "改口", "隐瞒"]
PAYOFF_SIGNAL_WORDS = ["开启", "触发", "揭晓", "真相", "终于", "兑现", "应验", "身份暴露", "解释了"]
SCENE_SCHEMA_VERSION = PROMPT_SCENE_SCHEMA_VERSION
SCENE_SUBTASK_SCHEMA_VERSION = "scene_subtask_v1"
SCENE_CANDIDATE_SCHEMA_VERSION = PROMPT_CANDIDATE_SCHEMA_VERSION
SCENE_PROMPT_VERSION = PROMPT_PACK_VERSION
PAIR_PROMPT_VERSION = "pair_prompt_v1"
SCENE_SUBTASKS = (
    "events",
    "time",
    "location",
    "characters",
    "conflict",
    "worldbuilding",
    "foreshadow",
    "payoff",
)
SUPPORTED_EXTRACT_PROVIDERS = {"rules", "ollama", "auto"}
SCENE_STRICT_JSON_SYSTEM_PROMPT = (
    "你是结构化信息抽取器。"
    "只输出 JSON，不要 markdown，不要解释，不要注释。"
    "禁止编造，字段必须来自输入文本；不确定填空字符串或空数组。"
)
SCENE_CANDIDATE_SYSTEM_PROMPT = candidate_system_prompt_text()
SCENE_JUDGE_SYSTEM_PROMPT = judge_system_prompt_text()
SCENE_REPAIR_SYSTEM_PROMPT = fix_json_system_prompt_text()
PAIR_JUDGE_SYSTEM_PROMPT = (
    "你是伏笔回收配对裁决器。只输出 JSON。"
    "基于 seed/payoff 及其证据判断是否配对。"
    "若不确定，is_pair=false 并给出 not_pair_reason。"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp_int(raw: Any, default: int, low: int, high: int) -> int:
    try:
        value = int(raw)
    except Exception:
        value = default
    return max(low, min(high, value))


def _coerce_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    raw = str(value).strip().lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _normalize_chapter_nos(raw: Any, *, low: int = 1, high: int = 999999, max_items: int = 5000) -> list[int]:
    if raw is None:
        return []
    tokens: list[str] = []
    if isinstance(raw, (list, tuple, set)):
        tokens = [str(x).strip() for x in raw]
    else:
        tokens = [x.strip() for x in re.split(r"[,\s]+", str(raw))]
    picked: set[int] = set()
    for token in tokens:
        if not token:
            continue
        if "-" in token:
            left, right = token.split("-", 1)
            try:
                start = int(left.strip())
                end = int(right.strip())
            except Exception:
                continue
            if start > end:
                start, end = end, start
            span = min(max_items, max(0, end - start + 1))
            for value in range(start, start + span):
                if low <= value <= high:
                    picked.add(value)
                if len(picked) >= max_items:
                    break
            if len(picked) >= max_items:
                break
            continue
        try:
            value = int(token)
        except Exception:
            continue
        if low <= value <= high:
            picked.add(value)
        if len(picked) >= max_items:
            break
    return sorted(picked)


def _find_inline_chapter_markers(text_value: str, *, max_hits: int = 24) -> list[tuple[int, int, str]]:
    txt = str(text_value or "")
    if not txt:
        return []
    markers: list[tuple[int, int, str]] = []
    last_end = -1
    for match in CHAPTER_INLINE_RE.finditer(txt):
        start, end = int(match.start()), int(match.end())
        if start <= last_end:
            continue
        prev = txt[start - 1] if start > 0 else " "
        if start > 0 and prev not in CHAPTER_MARKER_BOUNDARY_PREV:
            continue
        marker = re.sub(r"\s+", " ", str(match.group(0) or "").strip())
        if not marker:
            continue
        if not CHAPTER_RE.match(marker):
            continue
        markers.append((start, end, marker[:120]))
        last_end = end
        if len(markers) >= max_hits:
            break
    return markers


def _hash_writeback_content(content: str) -> str:
    normalized = str(content or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _detect_encoding(path: str, preferred: str | None = None) -> str:
    candidates: list[str] = []
    if preferred:
        candidates.append(str(preferred).strip())
    candidates.extend(["utf-8", "utf-8-sig", "ascii", "gb18030", "big5", "shift_jis", "latin-1"])
    with open(path, "rb") as f:
        sample = f.read(65536)
    if sample.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    for enc in candidates:
        if not enc:
            continue
        try:
            sample.decode(enc)
            return enc
        except Exception:
            continue
    return "utf-8"


def _hard_split(text_value: str, chunk_size: int, overlap: int) -> list[str]:
    cleaned = str(text_value or "").strip()
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [cleaned]
    step = max(1, chunk_size - overlap)
    out: list[str] = []
    index = 0
    while index < len(cleaned):
        piece = cleaned[index : index + chunk_size].strip()
        if piece:
            out.append(piece)
        index += step
    return out


def _fallback_embedding(text_value: str, dim: int = 64) -> list[float]:
    vec = [0.0] * dim
    terms = re.findall(r"[\u4e00-\u9fff]{1}|[a-zA-Z0-9_]+", (text_value or "").lower())
    if not terms:
        return vec
    for term in terms[:4096]:
        digest = hashlib.sha1(term.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:2], "big") % dim
        sign = -1.0 if (digest[2] & 1) else 1.0
        vec[idx] += sign
    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [round(v / norm, 8) for v in vec]
    return vec


def _split_sentences(text_value: str) -> list[str]:
    raw = re.split(r"[。！？!?;\n]+", text_value or "")
    return [x.strip() for x in raw if x and x.strip()]


def _split_sentences_with_spans(text_value: str) -> list[dict[str, Any]]:
    text_norm = str(text_value or "")
    out: list[dict[str, Any]] = []
    for m in re.finditer(r"[^。！？!?;\n]+(?:[。！？!?;]|$)", text_norm):
        seg = str(m.group(0) or "").strip()
        if not seg:
            continue
        out.append({"text": seg[:240], "start": int(m.start()), "end": int(m.end())})
    return out


def _keyword_pick(sentences: list[str], words: list[str], default_text: str = "") -> str:
    for sent in sentences:
        for word in words:
            if word in sent:
                return sent[:180]
    return default_text


def _find_spans(text_value: str, keyword: str, max_hits: int = 3) -> list[list[int]]:
    txt = str(text_value or "")
    kw = str(keyword or "")
    if not txt or not kw:
        return []
    out: list[list[int]] = []
    cursor = 0
    while cursor < len(txt):
        idx = txt.find(kw, cursor)
        if idx < 0:
            break
        out.append([int(idx), int(idx + len(kw))])
        if len(out) >= max_hits:
            break
        cursor = idx + max(1, len(kw))
    return out


def _normalize_time_phrase(raw: str) -> tuple[str, float]:
    txt = str(raw or "").strip()
    if not txt:
        return "", 0.0
    m_digit = re.search(r"([0-9]{1,3})\s*天后", txt)
    if m_digit:
        return f"T+{int(m_digit.group(1))}D", 0.86
    cn_map = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    m_cn = re.search(r"([一二两三四五六七八九十])\s*天后", txt)
    if m_cn:
        n = int(cn_map.get(str(m_cn.group(1) or ""), 0) or 0)
        if n > 0:
            return f"T+{n}D", 0.82
    if "次日" in txt or "翌日" in txt:
        return "T+1D", 0.8
    if "清晨" in txt:
        return "DAYTIME_MORNING", 0.72
    if "上午" in txt:
        return "DAYTIME_AM", 0.72
    if "中午" in txt:
        return "DAYTIME_NOON", 0.72
    if "下午" in txt:
        return "DAYTIME_PM", 0.72
    if "傍晚" in txt:
        return "DAYTIME_DUSK", 0.72
    if "夜里" in txt or "深夜" in txt or "入夜" in txt:
        return "DAYTIME_NIGHT", 0.72
    if "随后" in txt or "然后" in txt:
        return "T+SEQ", 0.58
    return "TIME_UNKNOWN", 0.4


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    dim = min(len(vec_a), len(vec_b))
    if dim <= 0:
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for i in range(dim):
        a = float(vec_a[i] or 0.0)
        b = float(vec_b[i] or 0.0)
        dot += a * b
        norm_a += a * a
        norm_b += b * b
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return float(dot / ((norm_a ** 0.5) * (norm_b ** 0.5)))


def _scene_has_shift_signal(paragraph: str) -> bool:
    txt = str(paragraph or "").strip()
    if not txt:
        return False
    if any(mark in txt for mark in SCENE_HARD_MARKERS):
        return True
    return any(word in txt for word in SCENE_TIME_SHIFT_WORDS)


def _split_paragraphs_with_spans(text_value: str) -> list[dict[str, Any]]:
    txt = str(text_value or "")
    out: list[dict[str, Any]] = []
    for m in re.finditer(r"\S[\s\S]*?(?:(?:\n\s*\n)|$)", txt):
        raw = str(m.group(0) or "")
        seg = raw.strip()
        if not seg:
            continue
        out.append({"text": seg, "start": int(m.start()), "end": int(m.end())})
    if not out and txt.strip():
        out.append({"text": txt.strip(), "start": 0, "end": len(txt)})
    return out


def _split_scene_units(text_value: str, *, min_chars: int = 420, target_chars: int = 1400, max_chars: int = 2600) -> list[dict[str, Any]]:
    paragraphs = _split_paragraphs_with_spans(text_value)
    if not paragraphs:
        return []
    scenes: list[dict[str, Any]] = []
    current_parts: list[str] = []
    current_start = int(paragraphs[0]["start"])
    current_end = current_start

    def flush() -> None:
        nonlocal current_parts, current_start, current_end, scenes
        merged = "\n\n".join([str(x or "").strip() for x in current_parts if str(x or "").strip()]).strip()
        if not merged:
            current_parts = []
            return
        scenes.append(
            {
                "text": merged,
                "start": int(current_start),
                "end": int(max(current_end, current_start + len(merged))),
            }
        )
        current_parts = []

    for idx, para in enumerate(paragraphs):
        ptxt = str(para.get("text") or "").strip()
        if not ptxt:
            continue
        pstart = int(para.get("start") or 0)
        pend = int(para.get("end") or (pstart + len(ptxt)))
        if not current_parts:
            current_parts = [ptxt]
            current_start = pstart
            current_end = pend
            continue
        current_text = "\n\n".join(current_parts).strip()
        candidate = f"{current_text}\n\n{ptxt}".strip()
        force_cut = _scene_has_shift_signal(ptxt) and len(current_text) >= min_chars
        overflow_cut = len(candidate) > max_chars and len(current_text) >= min_chars
        target_cut = len(current_text) >= target_chars and _scene_has_shift_signal(ptxt)
        if force_cut or overflow_cut or target_cut:
            flush()
            current_parts = [ptxt]
            current_start = pstart
            current_end = pend
        else:
            current_parts.append(ptxt)
            current_end = pend
        if idx == len(paragraphs) - 1:
            flush()
    if current_parts:
        flush()

    if not scenes:
        return [{"text": str(text_value or "").strip(), "start": 0, "end": len(str(text_value or ""))}]
    return scenes


def _repair_scene_schema(scene: dict[str, Any]) -> dict[str, Any]:
    out = dict(scene or {})
    out.setdefault("summary", "")
    out.setdefault("time", {"raw": "", "normalized": "", "confidence": 0.0, "evidence": []})
    out.setdefault("location", {"raw": "", "normalized": "", "evidence": []})
    out.setdefault("characters", [])
    out.setdefault("worldbuilding", [])
    out.setdefault("conflict", {"type": "", "stakes": "", "goal_a": "", "goal_b": "", "turning_point": "", "evidence": []})
    out.setdefault("foreshadow_candidates", [])
    out.setdefault("payoff_candidates", [])
    out.setdefault("events", [])
    out.setdefault("evidence", {"scene_span": []})
    if not isinstance(out.get("time"), dict):
        out["time"] = {"raw": "", "normalized": "", "confidence": 0.0, "evidence": []}
    if not isinstance(out.get("location"), dict):
        out["location"] = {"raw": "", "normalized": "", "evidence": []}
    if not isinstance(out.get("characters"), list):
        out["characters"] = []
    if not isinstance(out.get("worldbuilding"), list):
        out["worldbuilding"] = []
    if not isinstance(out.get("foreshadow_candidates"), list):
        out["foreshadow_candidates"] = []
    if not isinstance(out.get("payoff_candidates"), list):
        out["payoff_candidates"] = []
    if not isinstance(out.get("events"), list):
        out["events"] = []
    if not isinstance(out.get("conflict"), dict):
        out["conflict"] = {"type": "", "stakes": "", "goal_a": "", "goal_b": "", "turning_point": "", "evidence": []}
    if not isinstance(out.get("evidence"), dict):
        out["evidence"] = {"scene_span": []}
    return out


def _normalize_extract_provider(raw: Any) -> str:
    provider = str(raw or "").strip().lower()
    if not provider:
        return "rules"
    if provider not in SUPPORTED_EXTRACT_PROVIDERS:
        return "rules"
    if provider == "auto":
        return "ollama" if str(settings.ollama_host or "").strip() else "rules"
    return provider


def _normalize_subtask_list(raw: Any) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return SCENE_SUBTASKS
    keep: list[str] = []
    valid = set(SCENE_SUBTASKS)
    for item in raw:
        name = str(item or "").strip().lower()
        if name and name in valid and name not in keep:
            keep.append(name)
    return tuple(keep) if keep else SCENE_SUBTASKS


def _clamp_float(raw: Any, default: float, low: float, high: float) -> float:
    try:
        value = float(raw)
    except Exception:
        value = float(default)
    return max(float(low), min(float(high), float(value)))


def _err_brief(exc: Exception, *, limit: int = 240) -> str:
    msg = str(exc or "").strip()
    if not msg:
        msg = exc.__class__.__name__
    return msg[:limit]


def _scene_subtask_candidates_from_row(scene_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "events": {
            "summary": str(scene_row.get("summary") or ""),
            "events": scene_row.get("events_json") if isinstance(scene_row.get("events_json"), list) else [],
        },
        "time": {
            "raw": str(scene_row.get("time_raw") or ""),
            "normalized": str(scene_row.get("time_norm") or ""),
            "confidence": float(scene_row.get("time_confidence") or 0.0),
        },
        "location": {
            "raw": str(scene_row.get("location_raw") or ""),
            "normalized": str(scene_row.get("location_norm") or ""),
        },
        "characters": {
            "characters": scene_row.get("characters_json") if isinstance(scene_row.get("characters_json"), list) else [],
        },
        "conflict": scene_row.get("conflict_json") if isinstance(scene_row.get("conflict_json"), dict) else {},
        "worldbuilding": {
            "items": scene_row.get("worldbuilding_json") if isinstance(scene_row.get("worldbuilding_json"), list) else [],
        },
        "foreshadow": {
            "items": scene_row.get("foreshadow_json") if isinstance(scene_row.get("foreshadow_json"), list) else [],
        },
        "payoff": {
            "items": scene_row.get("payoff_json") if isinstance(scene_row.get("payoff_json"), list) else [],
        },
    }


def _scene_subtask_schema_hint(task: str) -> str:
    hints: dict[str, str] = {
        "events": '{"summary":"一句话概述","events":[{"beat":"推进|冲突|代价|收获","what":"事件","cause":"原因","result":"结果","evidence":"原文短句"}]}',
        "time": '{"raw":"时间原词","normalized":"T+1D|DAYTIME_NIGHT|TIME_UNKNOWN","confidence":0.0,"evidence":"原文短句"}',
        "location": '{"raw":"地点原词","normalized":"规范地点","evidence":"原文短句"}',
        "characters": '{"characters":[{"name":"角色名","role":"主角|配角|对手|unknown","state_change":"状态变化","evidence":"原文短句"}]}',
        "conflict": '{"type":"man_vs_man|man_vs_system|man_vs_self|man_vs_nature|man_vs_unknown","stakes":"赌注","goal_a":"A目标","goal_b":"B目标","turning_point":"转折","outcome":"结果","evidence":"原文短句"}',
        "worldbuilding": '{"items":[{"type":"rule|resource|faction|geography|system|taboo|cost|power_level","item":"设定条目","constraints":"限制","cost":"代价","evidence":"原文短句"}]}',
        "foreshadow": '{"items":[{"seed":"伏笔句","why":"为何像伏笔","entity_tags":["实体"],"promise":"暗示未来","evidence":"原文短句"}]}',
        "payoff": '{"items":[{"event":"回收事件","trigger":"触发条件","effect":"结果","resolves":"解决了什么","entity_tags":["实体"],"evidence":"原文短句"}]}',
    }
    return hints.get(task, "{}")


def _scene_subtask_instruction(task: str) -> str:
    instructions: dict[str, str] = {
        "events": "提取场景摘要与 1-8 个事件 beat，必须按因果顺序。",
        "time": "提取时间表达并归一化；不确定时 normalized=TIME_UNKNOWN。",
        "location": "提取场景主要地点，给出原词和规范词。",
        "characters": "提取出现人物及状态变化；禁止虚构新角色。",
        "conflict": "提取冲突结构槽位（类型/双方目标/赌注/转折/结果）。",
        "worldbuilding": "提取世界观条目（规则/资源/势力等），每条有 evidence。",
        "foreshadow": "提取伏笔候选，先候选不要过度判断。",
        "payoff": "提取回收候选（解释/触发/兑现）。",
    }
    return instructions.get(task, "执行结构化抽取。")


def _build_scene_subtask_prompt(
    *,
    task: str,
    scene_key: str,
    chapter_no: int,
    scene_no: int,
    scene_text: str,
    candidate: dict[str, Any],
) -> str:
    scene_excerpt = str(scene_text or "")[:3200]
    candidate_json = json.dumps(candidate or {}, ensure_ascii=False)[:1800]
    schema_hint = _scene_subtask_schema_hint(task)
    instruction = _scene_subtask_instruction(task)
    return (
        f"任务={task}\n"
        f"{instruction}\n"
        f"scene_key={scene_key} chapter_no={chapter_no} scene_no={scene_no}\n"
        f"输出要求：仅输出一个 JSON 对象，严格满足 schema_hint；不允许输出多余字段。\n"
        f"schema_hint={schema_hint}\n"
        f"候选结果（可参考可修正）={candidate_json}\n"
        f"scene_text:\n{scene_excerpt}"
    )


def _scene_candidate_schema_hint() -> str:
    return candidate_schema_hint_text()


def _build_scene_candidate_prompt(
    *,
    scene_key: str,
    chapter_no: int,
    scene_no: int,
    scene_text: str,
) -> str:
    excerpt = str(scene_text or "")[:4200]
    return build_candidate_user_prompt(
        scene_key=scene_key,
        chapter_no=chapter_no,
        scene_no=scene_no,
        scene_excerpt=excerpt,
    )


def _validate_scene_candidate_output(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, dict):
        return []
    rows = raw.get("candidates") if isinstance(raw.get("candidates"), list) else []
    out: list[dict[str, Any]] = []
    for row in rows[:48]:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind") or "other").strip().lower()[:32] or "other"
        content = str(row.get("content") or "").strip()[:220]
        if not content:
            continue
        evidence = row.get("evidence") if isinstance(row.get("evidence"), list) else []
        evidence_out = [str(x).strip()[:160] for x in evidence[:3] if str(x).strip()]
        tags = row.get("entity_tags") if isinstance(row.get("entity_tags"), list) else []
        tags_out = [str(x).strip()[:24] for x in tags[:8] if str(x).strip()]
        out.append(
            {
                "kind": kind,
                "content": content,
                "evidence": evidence_out,
                "entity_tags": tags_out,
            }
        )
    return out


def _scene_judge_schema_hint() -> str:
    return scene_record_schema_hint_text()


def _build_scene_judge_prompt(
    *,
    scene_key: str,
    chapter_no: int,
    scene_no: int,
    scene_text: str,
    candidates: list[dict[str, Any]],
) -> str:
    excerpt = str(scene_text or "")[:4200]
    candidate_json = json.dumps(candidates or [], ensure_ascii=False)[:2800]
    return build_judge_user_prompt(
        scene_key=scene_key,
        chapter_no=chapter_no,
        scene_no=scene_no,
        candidate_json=candidate_json,
        scene_excerpt=excerpt,
    )


def _validate_scene_judge_output(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("judge output must be object")

    def _imp(value: Any, default: int = 1) -> int:
        return _clamp_int(value, default=default, low=0, high=3)

    def _conf(value: Any, default: float = 0.55) -> float:
        return round(_clamp_float(value, default=default, low=0.0, high=1.0), 4)

    out: dict[str, Any] = {
        "scene_key": str(raw.get("scene_key") or "").strip()[:64],
        "chapter_no": _clamp_int(raw.get("chapter_no"), default=0, low=0, high=1000000),
        "scene_no": _clamp_int(raw.get("scene_no"), default=0, low=0, high=1000000),
        "events": [],
        "world_facts": [],
        "artifacts": [],
        "conflict": {},
        "foreshadow_candidates": [],
        "payoff_candidates": [],
        "time": {},
        "location": {},
        "characters": [],
    }

    events = raw.get("events") if isinstance(raw.get("events"), list) else []
    for item in events[:16]:
        if not isinstance(item, dict):
            continue
        what = str(item.get("what") or "").strip()[:200]
        if not what:
            continue
        ev = item.get("evidence") if isinstance(item.get("evidence"), list) else []
        out["events"].append(
            {
                "beat": str(item.get("beat") or "推进").strip()[:24] or "推进",
                "what": what,
                "cause": str(item.get("cause") or "").strip()[:160],
                "result": str(item.get("result") or "").strip()[:160],
                "tension_score": _clamp_int(item.get("tension_score"), default=5, low=0, high=10),
                "importance": _imp(item.get("importance"), default=2),
                "confidence": _conf(item.get("confidence"), default=0.6),
                "evidence": [str(x).strip()[:160] for x in ev[:3] if str(x).strip()],
            }
        )

    world_facts = raw.get("world_facts") if isinstance(raw.get("world_facts"), list) else []
    for item in world_facts[:20]:
        if not isinstance(item, dict):
            continue
        subject = str(item.get("subject") or "").strip()[:120]
        predicate = str(item.get("predicate") or "").strip()[:80]
        obj = str(item.get("object") or "").strip()[:180]
        line = f"{subject}{predicate}{obj}".strip()
        if not line:
            continue
        ev = item.get("evidence") if isinstance(item.get("evidence"), list) else []
        tags = item.get("entity_tags") if isinstance(item.get("entity_tags"), list) else []
        out["world_facts"].append(
            {
                "fact_type": str(item.get("fact_type") or "other").strip()[:24] or "other",
                "subject": subject,
                "predicate": predicate,
                "object": obj,
                "constraints": str(item.get("constraints") or "").strip()[:160],
                "cost_or_risk": str(item.get("cost_or_risk") or "").strip()[:160],
                "importance": _imp(item.get("importance"), default=2),
                "confidence": _conf(item.get("confidence"), default=0.58),
                "evidence": [str(x).strip()[:160] for x in ev[:3] if str(x).strip()],
                "entity_tags": [str(x).strip()[:24] for x in tags[:8] if str(x).strip()],
            }
        )

    artifacts = raw.get("artifacts") if isinstance(raw.get("artifacts"), list) else []
    for item in artifacts[:16]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()[:120]
        if not name:
            continue
        ev = item.get("evidence") if isinstance(item.get("evidence"), list) else []
        out["artifacts"].append(
            {
                "name": name,
                "type": str(item.get("type") or "").strip()[:64],
                "effect": str(item.get("effect") or "").strip()[:180],
                "risk_or_cost": str(item.get("risk_or_cost") or "").strip()[:180],
                "owner_or_source": str(item.get("owner_or_source") or "").strip()[:120],
                "importance": _imp(item.get("importance"), default=2),
                "confidence": _conf(item.get("confidence"), default=0.58),
                "evidence": [str(x).strip()[:160] for x in ev[:3] if str(x).strip()],
            }
        )

    conflict = raw.get("conflict") if isinstance(raw.get("conflict"), dict) else {}
    conflict_evidence = conflict.get("evidence") if isinstance(conflict.get("evidence"), list) else []
    out["conflict"] = {
        "type": str(conflict.get("type") or "none").strip()[:40] or "none",
        "side_a_goal": str(conflict.get("side_a_goal") or "").strip()[:160],
        "side_b_goal": str(conflict.get("side_b_goal") or "").strip()[:160],
        "stakes": str(conflict.get("stakes") or "").strip()[:180],
        "escalation": str(conflict.get("escalation") or "").strip()[:180],
        "turning_point": str(conflict.get("turning_point") or "").strip()[:180],
        "outcome": str(conflict.get("outcome") or "").strip()[:180],
        "tension_score": _clamp_int(conflict.get("tension_score"), default=0, low=0, high=10),
        "confidence": _conf(conflict.get("confidence"), default=0.55),
        "evidence": [str(x).strip()[:160] for x in conflict_evidence[:3] if str(x).strip()],
    }

    seeds = raw.get("foreshadow_candidates") if isinstance(raw.get("foreshadow_candidates"), list) else []
    for item in seeds[:16]:
        if not isinstance(item, dict):
            continue
        seed = str(item.get("seed") or "").strip()[:180]
        if not seed:
            continue
        ev = item.get("evidence") if isinstance(item.get("evidence"), list) else []
        tags = item.get("entity_tags") if isinstance(item.get("entity_tags"), list) else []
        out["foreshadow_candidates"].append(
            {
                "seed": seed,
                "why": str(item.get("why") or "").strip()[:140],
                "promise": str(item.get("promise") or "").strip()[:160],
                "importance": _imp(item.get("importance"), default=2),
                "confidence": _conf(item.get("confidence"), default=0.55),
                "entity_tags": [str(x).strip()[:24] for x in tags[:8] if str(x).strip()],
                "evidence": [str(x).strip()[:160] for x in ev[:3] if str(x).strip()],
            }
        )

    payoffs = raw.get("payoff_candidates") if isinstance(raw.get("payoff_candidates"), list) else []
    for item in payoffs[:16]:
        if not isinstance(item, dict):
            continue
        payoff = str(item.get("payoff") or item.get("event") or "").strip()[:180]
        if not payoff:
            continue
        ev = item.get("evidence") if isinstance(item.get("evidence"), list) else []
        tags = item.get("entity_tags") if isinstance(item.get("entity_tags"), list) else []
        out["payoff_candidates"].append(
            {
                "payoff": payoff,
                "trigger": str(item.get("trigger") or "").strip()[:140],
                "effect": str(item.get("effect") or "").strip()[:160],
                "resolves": str(item.get("resolves") or "").strip()[:160],
                "importance": _imp(item.get("importance"), default=2),
                "confidence": _conf(item.get("confidence"), default=0.55),
                "entity_tags": [str(x).strip()[:24] for x in tags[:8] if str(x).strip()],
                "evidence": [str(x).strip()[:160] for x in ev[:3] if str(x).strip()],
            }
        )

    time_obj = raw.get("time") if isinstance(raw.get("time"), dict) else {}
    time_ev = time_obj.get("evidence") if isinstance(time_obj.get("evidence"), list) else []
    out["time"] = {
        "raw": str(time_obj.get("raw") or "").strip()[:60],
        "normalized": str(time_obj.get("normalized") or "").strip()[:64],
        "confidence": _conf(time_obj.get("confidence"), default=0.0),
        "evidence": [str(x).strip()[:120] for x in time_ev[:2] if str(x).strip()],
    }

    loc_obj = raw.get("location") if isinstance(raw.get("location"), dict) else {}
    loc_ev = loc_obj.get("evidence") if isinstance(loc_obj.get("evidence"), list) else []
    out["location"] = {
        "raw": str(loc_obj.get("raw") or "").strip()[:80],
        "normalized": str(loc_obj.get("normalized") or "").strip()[:80],
        "evidence": [str(x).strip()[:120] for x in loc_ev[:2] if str(x).strip()],
    }

    chars = raw.get("characters") if isinstance(raw.get("characters"), list) else []
    for item in chars[:16]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()[:12]
        if len(name) < 2:
            continue
        ev = item.get("evidence") if isinstance(item.get("evidence"), list) else []
        out["characters"].append(
            {
                "name": name,
                "role": str(item.get("role") or "unknown").strip()[:24] or "unknown",
                "state_change": str(item.get("state_change") or "").strip()[:160],
                "evidence": [str(x).strip()[:120] for x in ev[:2] if str(x).strip()],
            }
        )

    return out


def _validate_scene_subtask_output(task: str, raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{task}: output must be object")

    if task == "events":
        summary = str(raw.get("summary") or "").strip()[:220]
        events_raw = raw.get("events") if isinstance(raw.get("events"), list) else []
        events: list[dict[str, Any]] = []
        for item in events_raw[:12]:
            if not isinstance(item, dict):
                continue
            what = str(item.get("what") or item.get("event") or "").strip()[:180]
            if not what:
                continue
            events.append(
                {
                    "beat": str(item.get("beat") or "推进").strip()[:24] or "推进",
                    "what": what,
                    "cause": str(item.get("cause") or "").strip()[:120],
                    "result": str(item.get("result") or "").strip()[:120],
                    "tension_score": _clamp_int(item.get("tension_score"), default=5, low=0, high=10),
                    "importance": _clamp_int(item.get("importance"), default=2, low=0, high=3),
                    "confidence": _clamp_float(item.get("confidence"), default=0.6, low=0.0, high=1.0),
                    "evidence": str(item.get("evidence") or "").strip()[:160],
                }
            )
        if not summary and events:
            summary = str(events[0].get("what") or "")[:180]
        return {"summary": summary, "events": events}

    if task == "time":
        time_raw = str(raw.get("raw") or "").strip()[:60]
        time_norm = str(raw.get("normalized") or "").strip()[:64]
        if time_raw and not time_norm:
            time_norm, auto_conf = _normalize_time_phrase(time_raw)
        else:
            auto_conf = 0.45 if time_raw or time_norm else 0.0
        conf = _clamp_float(raw.get("confidence"), default=auto_conf, low=0.0, high=1.0)
        return {
            "raw": time_raw,
            "normalized": time_norm or ("TIME_UNKNOWN" if time_raw else ""),
            "confidence": round(conf, 4),
            "evidence": str(raw.get("evidence") or "").strip()[:160],
        }

    if task == "location":
        loc_raw = str(raw.get("raw") or "").strip()[:80]
        loc_norm = str(raw.get("normalized") or "").strip()[:80] or loc_raw
        return {
            "raw": loc_raw,
            "normalized": loc_norm,
            "evidence": str(raw.get("evidence") or "").strip()[:160],
        }

    if task == "characters":
        chars_raw = raw.get("characters") if isinstance(raw.get("characters"), list) else []
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in chars_raw[:16]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()[:12]
            if len(name) < 2 or name in seen:
                continue
            seen.add(name)
            out.append(
                {
                    "name": name,
                    "role": str(item.get("role") or "unknown").strip()[:24] or "unknown",
                    "state_change": str(item.get("state_change") or "").strip()[:120],
                    "evidence": str(item.get("evidence") or "").strip()[:160],
                }
            )
        return {"characters": out}

    if task == "conflict":
        conflict_type = str(raw.get("type") or "").strip()[:40]
        stakes = str(raw.get("stakes") or "").strip()[:180]
        goal_a = str(raw.get("goal_a") or "").strip()[:140]
        goal_b = str(raw.get("goal_b") or "").strip()[:140]
        turning_point = str(raw.get("turning_point") or "").strip()[:180]
        outcome = str(raw.get("outcome") or "").strip()[:180]
        if not conflict_type and (stakes or turning_point or goal_a or goal_b):
            conflict_type = "man_vs_man"
        return {
            "type": conflict_type,
            "stakes": stakes,
            "goal_a": goal_a,
            "goal_b": goal_b,
            "turning_point": turning_point,
            "outcome": outcome,
            "tension_score": _clamp_int(raw.get("tension_score"), default=6 if conflict_type else 0, low=0, high=10),
            "confidence": _clamp_float(raw.get("confidence"), default=0.55 if conflict_type else 0.0, low=0.0, high=1.0),
            "evidence": str(raw.get("evidence") or "").strip()[:160],
        }

    if task == "worldbuilding":
        items_raw = raw.get("items") if isinstance(raw.get("items"), list) else []
        out: list[dict[str, Any]] = []
        for item in items_raw[:16]:
            if not isinstance(item, dict):
                continue
            item_text = str(item.get("item") or "").strip()[:180]
            if not item_text:
                continue
            out.append(
                {
                    "type": str(item.get("type") or "rule").strip()[:24] or "rule",
                    "item": item_text,
                    "constraints": str(item.get("constraints") or "").strip()[:140],
                    "cost": str(item.get("cost") or "").strip()[:120],
                    "importance": _clamp_int(item.get("importance"), default=2, low=0, high=3),
                    "confidence": _clamp_float(item.get("confidence"), default=0.58, low=0.0, high=1.0),
                    "evidence": str(item.get("evidence") or "").strip()[:160],
                }
            )
        return {"items": out}

    if task == "foreshadow":
        items_raw = raw.get("items") if isinstance(raw.get("items"), list) else []
        out: list[dict[str, Any]] = []
        for item in items_raw[:12]:
            if not isinstance(item, dict):
                continue
            seed = str(item.get("seed") or "").strip()[:180]
            if not seed:
                continue
            tags = item.get("entity_tags") if isinstance(item.get("entity_tags"), list) else []
            out.append(
                {
                    "seed": seed,
                    "why": str(item.get("why") or "").strip()[:120],
                    "entity_tags": [str(x).strip()[:24] for x in tags[:6] if str(x).strip()],
                    "promise": str(item.get("promise") or "").strip()[:140],
                    "importance": _clamp_int(item.get("importance"), default=2, low=0, high=3),
                    "confidence": _clamp_float(item.get("confidence"), default=0.55, low=0.0, high=1.0),
                    "evidence": str(item.get("evidence") or "").strip()[:160],
                }
            )
        return {"items": out}

    if task == "payoff":
        items_raw = raw.get("items") if isinstance(raw.get("items"), list) else []
        out: list[dict[str, Any]] = []
        for item in items_raw[:12]:
            if not isinstance(item, dict):
                continue
            event = str(item.get("event") or "").strip()[:180]
            if not event:
                continue
            tags = item.get("entity_tags") if isinstance(item.get("entity_tags"), list) else []
            out.append(
                {
                    "event": event,
                    "trigger": str(item.get("trigger") or "").strip()[:120],
                    "effect": str(item.get("effect") or "").strip()[:140],
                    "resolves": str(item.get("resolves") or "").strip()[:140],
                    "entity_tags": [str(x).strip()[:24] for x in tags[:6] if str(x).strip()],
                    "importance": _clamp_int(item.get("importance"), default=2, low=0, high=3),
                    "confidence": _clamp_float(item.get("confidence"), default=0.55, low=0.0, high=1.0),
                    "evidence": str(item.get("evidence") or "").strip()[:160],
                }
            )
        return {"items": out}

    raise ValueError(f"unsupported task={task}")


def _evidence_to_spans(
    *,
    scene_text: str,
    span_start: int,
    evidence_text: str,
    fallback_text: str = "",
    max_hits: int = 2,
) -> list[list[int]]:
    primary = str(evidence_text or "").strip()
    backup = str(fallback_text or "").strip()
    probes: list[str] = []
    if primary:
        probes.append(primary[:60])
    if backup and backup not in probes:
        probes.append(backup[:60])
    if not probes:
        return []
    seen: set[tuple[int, int]] = set()
    out: list[list[int]] = []
    for probe in probes:
        spans = _find_spans(scene_text, probe, max_hits=max_hits)
        for rel in spans:
            if not isinstance(rel, list) or len(rel) < 2:
                continue
            abs_span = (span_start + int(rel[0]), span_start + int(rel[1]))
            if abs_span in seen:
                continue
            seen.add(abs_span)
            out.append([int(abs_span[0]), int(abs_span[1])])
            if len(out) >= max_hits:
                return out
    return out


def _rebuild_seed_items_from_scene_row(scene_row: dict[str, Any]) -> list[dict[str, Any]]:
    foreshadow = scene_row.get("foreshadow_json") if isinstance(scene_row.get("foreshadow_json"), list) else []
    out: list[dict[str, Any]] = []
    for item in foreshadow:
        if not isinstance(item, dict):
            continue
        seed_text = str(item.get("seed") or "").strip()
        if not seed_text:
            continue
        ev = item.get("evidence")
        evidence: list[int] = []
        if isinstance(ev, list) and len(ev) >= 2 and isinstance(ev[0], int) and isinstance(ev[1], int):
            evidence = [int(ev[0]), int(ev[1])]
        out.append(
            {
                "splitbook_id": str(scene_row.get("splitbook_id") or ""),
                "scene_key": str(scene_row.get("scene_key") or ""),
                "chapter_no": int(scene_row.get("chapter_no") or 0),
                "scene_no": int(scene_row.get("scene_no") or 0),
                "seed_text": seed_text[:180],
                "why": str(item.get("why") or "").strip()[:140],
                "promise": str(item.get("promise") or "").strip()[:160],
                "importance": _clamp_int(item.get("importance"), default=1, low=0, high=3),
                "confidence": _clamp_float(item.get("confidence"), default=0.0, low=0.0, high=1.0),
                "entity_tags": item.get("entity_tags") if isinstance(item.get("entity_tags"), list) else [],
                "evidence": evidence,
                "evidence_json": evidence,
            }
        )
    return out


def _rebuild_payoff_items_from_scene_row(scene_row: dict[str, Any]) -> list[dict[str, Any]]:
    payoff = scene_row.get("payoff_json") if isinstance(scene_row.get("payoff_json"), list) else []
    out: list[dict[str, Any]] = []
    for item in payoff:
        if not isinstance(item, dict):
            continue
        payoff_text = str(item.get("event") or "").strip()
        if not payoff_text:
            continue
        ev = item.get("evidence")
        evidence: list[int] = []
        if isinstance(ev, list) and len(ev) >= 2 and isinstance(ev[0], int) and isinstance(ev[1], int):
            evidence = [int(ev[0]), int(ev[1])]
        out.append(
            {
                "splitbook_id": str(scene_row.get("splitbook_id") or ""),
                "scene_key": str(scene_row.get("scene_key") or ""),
                "chapter_no": int(scene_row.get("chapter_no") or 0),
                "scene_no": int(scene_row.get("scene_no") or 0),
                "payoff_text": payoff_text[:180],
                "trigger": str(item.get("trigger") or "").strip()[:140],
                "effect": str(item.get("effect") or "").strip()[:160],
                "resolves": str(item.get("resolves") or "").strip()[:160],
                "importance": _clamp_int(item.get("importance"), default=1, low=0, high=3),
                "confidence": _clamp_float(item.get("confidence"), default=0.0, low=0.0, high=1.0),
                "entity_tags": item.get("entity_tags") if isinstance(item.get("entity_tags"), list) else [],
                "evidence": evidence,
                "evidence_json": evidence,
            }
        )
    return out


def _rebuild_event_items_from_scene_row(scene_row: dict[str, Any]) -> list[dict[str, Any]]:
    events = scene_row.get("events_json") if isinstance(scene_row.get("events_json"), list) else []
    out: list[dict[str, Any]] = []
    for item in events:
        if not isinstance(item, dict):
            continue
        what = str(item.get("what") or "").strip()
        if not what:
            continue
        ev = item.get("evidence")
        evidence: list[int] = []
        if isinstance(ev, list) and len(ev) >= 2 and isinstance(ev[0], int) and isinstance(ev[1], int):
            evidence = [int(ev[0]), int(ev[1])]
        out.append(
            {
                "splitbook_id": str(scene_row.get("splitbook_id") or ""),
                "scene_key": str(scene_row.get("scene_key") or ""),
                "chapter_no": int(scene_row.get("chapter_no") or 0),
                "scene_no": int(scene_row.get("scene_no") or 0),
                "beat": str(item.get("beat") or "推进").strip()[:24] or "推进",
                "what": what[:180],
                "cause": str(item.get("cause") or "").strip()[:140],
                "result": str(item.get("result") or "").strip()[:140],
                "tension_score": _clamp_int(item.get("tension_score"), default=0, low=0, high=10),
                "importance": _clamp_int(item.get("importance"), default=1, low=0, high=3),
                "confidence": _clamp_float(item.get("confidence"), default=0.0, low=0.0, high=1.0),
                "evidence_json": evidence,
            }
        )
    return out


def _recompute_scene_qa(scene_row: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    qa = scene_row.get("qa_json") if isinstance(scene_row.get("qa_json"), dict) else {}
    out = dict(qa)
    out.update(
        {
            "has_time": bool(str(scene_row.get("time_raw") or "").strip()),
            "has_conflict": bool((scene_row.get("conflict_json") if isinstance(scene_row.get("conflict_json"), dict) else {}).get("type")),
            "has_worldbuilding": bool(scene_row.get("worldbuilding_json") if isinstance(scene_row.get("worldbuilding_json"), list) else []),
            "has_foreshadow": bool(scene_row.get("foreshadow_json") if isinstance(scene_row.get("foreshadow_json"), list) else []),
            "has_payoff": bool(scene_row.get("payoff_json") if isinstance(scene_row.get("payoff_json"), list) else []),
            "has_evidence": bool((scene_row.get("evidence_json") if isinstance(scene_row.get("evidence_json"), dict) else {}).get("scene_span")),
        }
    )
    if isinstance(extra, dict) and extra:
        out.update(extra)
    return out


def _apply_scene_subtask_result(
    *,
    scene_row: dict[str, Any],
    task: str,
    result: dict[str, Any],
    scene_text: str,
    span_start: int,
) -> dict[str, Any]:
    row = dict(scene_row)
    evidence_json = row.get("evidence_json") if isinstance(row.get("evidence_json"), dict) else {}
    evidence_out = dict(evidence_json)
    if not isinstance(evidence_out.get("scene_span"), list):
        evidence_out["scene_span"] = [int(span_start), int(span_start + len(scene_text or ""))]

    if task == "events":
        summary = str(result.get("summary") or "").strip()[:220]
        events_raw = result.get("events") if isinstance(result.get("events"), list) else []
        events: list[dict[str, Any]] = []
        for item in events_raw[:12]:
            if not isinstance(item, dict):
                continue
            what = str(item.get("what") or "").strip()[:180]
            if not what:
                continue
            spans = _evidence_to_spans(
                scene_text=scene_text,
                span_start=span_start,
                evidence_text=str(item.get("evidence") or ""),
                fallback_text=what,
                max_hits=1,
            )
            events.append(
                {
                    "beat": str(item.get("beat") or "推进").strip()[:24] or "推进",
                    "what": what,
                    "cause": str(item.get("cause") or "").strip()[:120],
                    "result": str(item.get("result") or "").strip()[:120],
                    "tension_score": _clamp_int(item.get("tension_score"), default=5, low=0, high=10),
                    "importance": _clamp_int(item.get("importance"), default=2, low=0, high=3),
                    "confidence": _clamp_float(item.get("confidence"), default=0.6, low=0.0, high=1.0),
                    "evidence": spans[0] if spans else [],
                }
            )
        if summary:
            row["summary"] = summary
        if events:
            row["events_json"] = events
        evidence_out["events"] = [x.get("evidence") for x in events if isinstance(x.get("evidence"), list) and len(x.get("evidence")) >= 2][:6]

    elif task == "time":
        raw_time = str(result.get("raw") or "").strip()[:60]
        norm_time = str(result.get("normalized") or "").strip()[:64]
        conf = _clamp_float(result.get("confidence"), default=0.0, low=0.0, high=1.0)
        spans = _evidence_to_spans(
            scene_text=scene_text,
            span_start=span_start,
            evidence_text=str(result.get("evidence") or ""),
            fallback_text=raw_time,
            max_hits=2,
        )
        row["time_raw"] = raw_time
        row["time_norm"] = norm_time
        row["time_confidence"] = float(round(conf, 4))
        evidence_out["time"] = spans

    elif task == "location":
        raw_loc = str(result.get("raw") or "").strip()[:80]
        norm_loc = str(result.get("normalized") or "").strip()[:80] or raw_loc
        spans = _evidence_to_spans(
            scene_text=scene_text,
            span_start=span_start,
            evidence_text=str(result.get("evidence") or ""),
            fallback_text=raw_loc or norm_loc,
            max_hits=2,
        )
        row["location_raw"] = raw_loc
        row["location_norm"] = norm_loc
        evidence_out["location"] = spans

    elif task == "characters":
        chars_raw = result.get("characters") if isinstance(result.get("characters"), list) else []
        chars_out: list[dict[str, Any]] = []
        for item in chars_raw[:16]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()[:12]
            if len(name) < 2:
                continue
            spans = _evidence_to_spans(
                scene_text=scene_text,
                span_start=span_start,
                evidence_text=str(item.get("evidence") or ""),
                fallback_text=name,
                max_hits=1,
            )
            chars_out.append(
                {
                    "name": name,
                    "role": str(item.get("role") or "unknown").strip()[:24] or "unknown",
                    "state_change": str(item.get("state_change") or "").strip()[:120],
                    "evidence": spans[0] if spans else [],
                }
            )
        if chars_out:
            row["characters_json"] = chars_out
            evidence_out["characters"] = [x.get("evidence") for x in chars_out if isinstance(x.get("evidence"), list) and len(x.get("evidence")) >= 2][:10]

    elif task == "conflict":
        spans = _evidence_to_spans(
            scene_text=scene_text,
            span_start=span_start,
            evidence_text=str(result.get("evidence") or ""),
            fallback_text=str(result.get("turning_point") or result.get("stakes") or ""),
            max_hits=2,
        )
        row["conflict_json"] = {
            "type": str(result.get("type") or "").strip()[:40],
            "stakes": str(result.get("stakes") or "").strip()[:180],
            "goal_a": str(result.get("goal_a") or "").strip()[:140],
            "goal_b": str(result.get("goal_b") or "").strip()[:140],
            "turning_point": str(result.get("turning_point") or "").strip()[:180],
            "outcome": str(result.get("outcome") or "").strip()[:180],
            "tension_score": _clamp_int(result.get("tension_score"), default=0, low=0, high=10),
            "confidence": _clamp_float(result.get("confidence"), default=0.55, low=0.0, high=1.0),
            "evidence": spans,
        }
        evidence_out["conflict"] = spans

    elif task == "worldbuilding":
        items_raw = result.get("items") if isinstance(result.get("items"), list) else []
        world_out: list[dict[str, Any]] = []
        for item in items_raw[:16]:
            if not isinstance(item, dict):
                continue
            item_text = str(item.get("item") or "").strip()[:180]
            if not item_text:
                continue
            spans = _evidence_to_spans(
                scene_text=scene_text,
                span_start=span_start,
                evidence_text=str(item.get("evidence") or ""),
                fallback_text=item_text,
                max_hits=1,
            )
            world_out.append(
                {
                    "type": str(item.get("type") or "rule").strip()[:24] or "rule",
                    "item": item_text,
                    "constraints": str(item.get("constraints") or "").strip()[:140],
                    "cost": str(item.get("cost") or "").strip()[:120],
                    "importance": _clamp_int(item.get("importance"), default=2, low=0, high=3),
                    "confidence": _clamp_float(item.get("confidence"), default=0.58, low=0.0, high=1.0),
                    "evidence": spans[0] if spans else [],
                }
            )
        if world_out:
            row["worldbuilding_json"] = world_out
            evidence_out["worldbuilding"] = [x.get("evidence") for x in world_out if isinstance(x.get("evidence"), list) and len(x.get("evidence")) >= 2][:10]

    elif task == "foreshadow":
        items_raw = result.get("items") if isinstance(result.get("items"), list) else []
        seed_out: list[dict[str, Any]] = []
        for item in items_raw[:12]:
            if not isinstance(item, dict):
                continue
            seed = str(item.get("seed") or "").strip()[:180]
            if not seed:
                continue
            spans = _evidence_to_spans(
                scene_text=scene_text,
                span_start=span_start,
                evidence_text=str(item.get("evidence") or ""),
                fallback_text=seed,
                max_hits=1,
            )
            tags = item.get("entity_tags") if isinstance(item.get("entity_tags"), list) else []
            seed_out.append(
                {
                    "seed": seed,
                    "why": str(item.get("why") or "").strip()[:120],
                    "entity_tags": [str(x).strip()[:24] for x in tags[:6] if str(x).strip()],
                    "promise": str(item.get("promise") or "").strip()[:140],
                    "importance": _clamp_int(item.get("importance"), default=2, low=0, high=3),
                    "confidence": _clamp_float(item.get("confidence"), default=0.55, low=0.0, high=1.0),
                    "evidence": spans[0] if spans else [],
                }
            )
        if seed_out:
            row["foreshadow_json"] = seed_out
            evidence_out["foreshadow"] = [x.get("evidence") for x in seed_out if isinstance(x.get("evidence"), list) and len(x.get("evidence")) >= 2][:10]

    elif task == "payoff":
        items_raw = result.get("items") if isinstance(result.get("items"), list) else []
        payoff_out: list[dict[str, Any]] = []
        for item in items_raw[:12]:
            if not isinstance(item, dict):
                continue
            event = str(item.get("event") or "").strip()[:180]
            if not event:
                continue
            spans = _evidence_to_spans(
                scene_text=scene_text,
                span_start=span_start,
                evidence_text=str(item.get("evidence") or ""),
                fallback_text=event,
                max_hits=1,
            )
            tags = item.get("entity_tags") if isinstance(item.get("entity_tags"), list) else []
            payoff_out.append(
                {
                    "event": event,
                    "trigger": str(item.get("trigger") or "").strip()[:120],
                    "effect": str(item.get("effect") or "").strip()[:140],
                    "resolves": str(item.get("resolves") or "").strip()[:140],
                    "entity_tags": [str(x).strip()[:24] for x in tags[:6] if str(x).strip()],
                    "importance": _clamp_int(item.get("importance"), default=2, low=0, high=3),
                    "confidence": _clamp_float(item.get("confidence"), default=0.55, low=0.0, high=1.0),
                    "evidence": spans[0] if spans else [],
                }
            )
        if payoff_out:
            row["payoff_json"] = payoff_out
            evidence_out["payoff"] = [x.get("evidence") for x in payoff_out if isinstance(x.get("evidence"), list) and len(x.get("evidence")) >= 2][:10]

    row["evidence_json"] = evidence_out
    row["qa_json"] = _recompute_scene_qa(row)
    return row


def _apply_scene_judge_record(
    *,
    scene_row: dict[str, Any],
    judged: dict[str, Any],
    scene_text: str,
    span_start: int,
    model_id: str,
    candidate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    row = dict(scene_row)
    evidence_out = row.get("evidence_json") if isinstance(row.get("evidence_json"), dict) else {}
    if not isinstance(evidence_out.get("scene_span"), list):
        evidence_out["scene_span"] = [int(span_start), int(span_start + len(scene_text or ""))]

    events_out: list[dict[str, Any]] = []
    for item in (judged.get("events") if isinstance(judged.get("events"), list) else [])[:16]:
        if not isinstance(item, dict):
            continue
        what = str(item.get("what") or "").strip()[:180]
        if not what:
            continue
        ev_texts = item.get("evidence") if isinstance(item.get("evidence"), list) else []
        spans: list[list[int]] = []
        for ev in ev_texts[:3]:
            spans.extend(
                _evidence_to_spans(
                    scene_text=scene_text,
                    span_start=span_start,
                    evidence_text=str(ev),
                    fallback_text=what,
                    max_hits=1,
                )
            )
        event_evidence = spans[0] if spans else []
        events_out.append(
            {
                "beat": str(item.get("beat") or "推进").strip()[:24] or "推进",
                "what": what,
                "cause": str(item.get("cause") or "").strip()[:120],
                "result": str(item.get("result") or "").strip()[:120],
                "tension_score": _clamp_int(item.get("tension_score"), default=5, low=0, high=10),
                "importance": _clamp_int(item.get("importance"), default=2, low=0, high=3),
                "confidence": _clamp_float(item.get("confidence"), default=0.6, low=0.0, high=1.0),
                "evidence": event_evidence,
            }
        )
    if events_out:
        row["events_json"] = events_out
        evidence_out["events"] = [x.get("evidence") for x in events_out if isinstance(x.get("evidence"), list) and len(x.get("evidence")) >= 2][:10]

    world_out: list[dict[str, Any]] = []
    for item in (judged.get("world_facts") if isinstance(judged.get("world_facts"), list) else [])[:24]:
        if not isinstance(item, dict):
            continue
        subject = str(item.get("subject") or "").strip()[:120]
        predicate = str(item.get("predicate") or "").strip()[:60]
        obj = str(item.get("object") or "").strip()[:180]
        item_text = " ".join([x for x in [subject, predicate, obj] if x]).strip()
        if not item_text:
            continue
        ev_texts = item.get("evidence") if isinstance(item.get("evidence"), list) else []
        spans: list[list[int]] = []
        for ev in ev_texts[:2]:
            spans.extend(
                _evidence_to_spans(
                    scene_text=scene_text,
                    span_start=span_start,
                    evidence_text=str(ev),
                    fallback_text=item_text,
                    max_hits=1,
                )
            )
        world_evidence = spans[0] if spans else []
        tags = item.get("entity_tags") if isinstance(item.get("entity_tags"), list) else []
        world_out.append(
            {
                "type": str(item.get("fact_type") or "other").strip()[:24] or "other",
                "item": item_text[:180],
                "constraints": str(item.get("constraints") or "").strip()[:140],
                "cost": str(item.get("cost_or_risk") or "").strip()[:140],
                "importance": _clamp_int(item.get("importance"), default=2, low=0, high=3),
                "confidence": _clamp_float(item.get("confidence"), default=0.58, low=0.0, high=1.0),
                "entity_tags": [str(x).strip()[:24] for x in tags[:8] if str(x).strip()],
                "evidence": world_evidence,
            }
        )
    artifact_out: list[dict[str, Any]] = []
    for item in (judged.get("artifacts") if isinstance(judged.get("artifacts"), list) else [])[:16]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()[:120]
        if not name:
            continue
        effect = str(item.get("effect") or "").strip()[:180]
        owner = str(item.get("owner_or_source") or "").strip()[:120]
        artifact_text = " | ".join([x for x in [name, effect, owner] if x]).strip()
        ev_texts = item.get("evidence") if isinstance(item.get("evidence"), list) else []
        spans: list[list[int]] = []
        for ev in ev_texts[:2]:
            spans.extend(
                _evidence_to_spans(
                    scene_text=scene_text,
                    span_start=span_start,
                    evidence_text=str(ev),
                    fallback_text=artifact_text or name,
                    max_hits=1,
                )
            )
        artifact_evidence = spans[0] if spans else []
        artifact_item = {
            "type": "artifact",
            "item": artifact_text[:180] if artifact_text else name,
            "constraints": str(item.get("type") or "").strip()[:140],
            "cost": str(item.get("risk_or_cost") or "").strip()[:140],
            "importance": _clamp_int(item.get("importance"), default=2, low=0, high=3),
            "confidence": _clamp_float(item.get("confidence"), default=0.58, low=0.0, high=1.0),
            "entity_tags": [],
            "evidence": artifact_evidence,
        }
        artifact_out.append(artifact_item)
        world_out.append(artifact_item)
    if world_out:
        row["worldbuilding_json"] = world_out
        evidence_out["worldbuilding"] = [x.get("evidence") for x in world_out if isinstance(x.get("evidence"), list) and len(x.get("evidence")) >= 2][:10]
    if artifact_out:
        evidence_out["artifacts"] = [x.get("evidence") for x in artifact_out if isinstance(x.get("evidence"), list) and len(x.get("evidence")) >= 2][:10]

    conflict = judged.get("conflict") if isinstance(judged.get("conflict"), dict) else {}
    if conflict:
        c_ev_texts = conflict.get("evidence") if isinstance(conflict.get("evidence"), list) else []
        c_spans: list[list[int]] = []
        for ev in c_ev_texts[:2]:
            c_spans.extend(
                _evidence_to_spans(
                    scene_text=scene_text,
                    span_start=span_start,
                    evidence_text=str(ev),
                    fallback_text=str(conflict.get("turning_point") or conflict.get("stakes") or ""),
                    max_hits=1,
                )
            )
        row["conflict_json"] = {
            "type": str(conflict.get("type") or "none").strip()[:40] or "none",
            "stakes": str(conflict.get("stakes") or "").strip()[:180],
            "goal_a": str(conflict.get("side_a_goal") or "").strip()[:140],
            "goal_b": str(conflict.get("side_b_goal") or "").strip()[:140],
            "escalation": str(conflict.get("escalation") or "").strip()[:180],
            "turning_point": str(conflict.get("turning_point") or "").strip()[:180],
            "outcome": str(conflict.get("outcome") or "").strip()[:180],
            "tension_score": _clamp_int(conflict.get("tension_score"), default=0, low=0, high=10),
            "confidence": _clamp_float(conflict.get("confidence"), default=0.55, low=0.0, high=1.0),
            "evidence": c_spans[:2],
        }
        evidence_out["conflict"] = c_spans[:2]

    seed_out: list[dict[str, Any]] = []
    for item in (judged.get("foreshadow_candidates") if isinstance(judged.get("foreshadow_candidates"), list) else [])[:16]:
        if not isinstance(item, dict):
            continue
        seed = str(item.get("seed") or "").strip()[:180]
        if not seed:
            continue
        ev_texts = item.get("evidence") if isinstance(item.get("evidence"), list) else []
        spans: list[list[int]] = []
        for ev in ev_texts[:2]:
            spans.extend(
                _evidence_to_spans(
                    scene_text=scene_text,
                    span_start=span_start,
                    evidence_text=str(ev),
                    fallback_text=seed,
                    max_hits=1,
                )
            )
        tags = item.get("entity_tags") if isinstance(item.get("entity_tags"), list) else []
        seed_out.append(
            {
                "seed": seed,
                "why": str(item.get("why") or "").strip()[:120],
                "promise": str(item.get("promise") or "").strip()[:140],
                "importance": _clamp_int(item.get("importance"), default=2, low=0, high=3),
                "confidence": _clamp_float(item.get("confidence"), default=0.55, low=0.0, high=1.0),
                "entity_tags": [str(x).strip()[:24] for x in tags[:8] if str(x).strip()],
                "evidence": spans[0] if spans else [],
            }
        )
    if seed_out:
        row["foreshadow_json"] = seed_out
        evidence_out["foreshadow"] = [x.get("evidence") for x in seed_out if isinstance(x.get("evidence"), list) and len(x.get("evidence")) >= 2][:10]

    payoff_out: list[dict[str, Any]] = []
    for item in (judged.get("payoff_candidates") if isinstance(judged.get("payoff_candidates"), list) else [])[:16]:
        if not isinstance(item, dict):
            continue
        payoff = str(item.get("payoff") or item.get("event") or "").strip()[:180]
        if not payoff:
            continue
        ev_texts = item.get("evidence") if isinstance(item.get("evidence"), list) else []
        spans: list[list[int]] = []
        for ev in ev_texts[:2]:
            spans.extend(
                _evidence_to_spans(
                    scene_text=scene_text,
                    span_start=span_start,
                    evidence_text=str(ev),
                    fallback_text=payoff,
                    max_hits=1,
                )
            )
        tags = item.get("entity_tags") if isinstance(item.get("entity_tags"), list) else []
        payoff_out.append(
            {
                "event": payoff,
                "trigger": str(item.get("trigger") or "").strip()[:120],
                "effect": str(item.get("effect") or "").strip()[:140],
                "resolves": str(item.get("resolves") or "").strip()[:140],
                "importance": _clamp_int(item.get("importance"), default=2, low=0, high=3),
                "confidence": _clamp_float(item.get("confidence"), default=0.55, low=0.0, high=1.0),
                "entity_tags": [str(x).strip()[:24] for x in tags[:8] if str(x).strip()],
                "evidence": spans[0] if spans else [],
            }
        )
    if payoff_out:
        row["payoff_json"] = payoff_out
        evidence_out["payoff"] = [x.get("evidence") for x in payoff_out if isinstance(x.get("evidence"), list) and len(x.get("evidence")) >= 2][:10]

    t_obj = judged.get("time") if isinstance(judged.get("time"), dict) else {}
    if t_obj:
        time_raw = str(t_obj.get("raw") or "").strip()[:60]
        row["time_raw"] = time_raw
        row["time_norm"] = str(t_obj.get("normalized") or "").strip()[:64]
        row["time_confidence"] = _clamp_float(t_obj.get("confidence"), default=0.0, low=0.0, high=1.0)
        t_spans: list[list[int]] = []
        for ev in (t_obj.get("evidence") if isinstance(t_obj.get("evidence"), list) else [])[:2]:
            t_spans.extend(
                _evidence_to_spans(
                    scene_text=scene_text,
                    span_start=span_start,
                    evidence_text=str(ev),
                    fallback_text=time_raw,
                    max_hits=1,
                )
            )
        evidence_out["time"] = t_spans[:2]

    l_obj = judged.get("location") if isinstance(judged.get("location"), dict) else {}
    if l_obj:
        loc_raw = str(l_obj.get("raw") or "").strip()[:80]
        row["location_raw"] = loc_raw
        row["location_norm"] = str(l_obj.get("normalized") or "").strip()[:80] or loc_raw
        l_spans: list[list[int]] = []
        for ev in (l_obj.get("evidence") if isinstance(l_obj.get("evidence"), list) else [])[:2]:
            l_spans.extend(
                _evidence_to_spans(
                    scene_text=scene_text,
                    span_start=span_start,
                    evidence_text=str(ev),
                    fallback_text=loc_raw,
                    max_hits=1,
                )
            )
        evidence_out["location"] = l_spans[:2]

    chars = judged.get("characters") if isinstance(judged.get("characters"), list) else []
    chars_out: list[dict[str, Any]] = []
    for item in chars[:16]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()[:12]
        if len(name) < 2:
            continue
        c_spans: list[list[int]] = []
        for ev in (item.get("evidence") if isinstance(item.get("evidence"), list) else [])[:2]:
            c_spans.extend(
                _evidence_to_spans(
                    scene_text=scene_text,
                    span_start=span_start,
                    evidence_text=str(ev),
                    fallback_text=name,
                    max_hits=1,
                )
            )
        chars_out.append(
            {
                "name": name,
                "role": str(item.get("role") or "unknown").strip()[:24] or "unknown",
                "state_change": str(item.get("state_change") or "").strip()[:120],
                "evidence": c_spans[0] if c_spans else [],
            }
        )
    if chars_out:
        row["characters_json"] = chars_out
        evidence_out["characters"] = [x.get("evidence") for x in chars_out if isinstance(x.get("evidence"), list) and len(x.get("evidence")) >= 2][:10]

    confidences: list[float] = []
    for evt in events_out:
        confidences.append(float(evt.get("confidence") or 0.0))
    for item in world_out:
        confidences.append(float(item.get("confidence") or 0.0))
    for item in seed_out:
        confidences.append(float(item.get("confidence") or 0.0))
    for item in payoff_out:
        confidences.append(float(item.get("confidence") or 0.0))
    conflict_obj = row.get("conflict_json") if isinstance(row.get("conflict_json"), dict) else {}
    if conflict_obj:
        confidences.append(float(conflict_obj.get("confidence") or 0.0))
    confidence_overall = round(sum(confidences) / max(1, len(confidences)), 4) if confidences else 0.0

    row["evidence_json"] = evidence_out
    row["candidate_json"] = {"candidates": candidate_rows}
    row["prompt_version"] = SCENE_PROMPT_VERSION
    row["model_id"] = str(model_id or "")
    row["confidence_overall"] = float(confidence_overall)
    row["qa_json"] = _recompute_scene_qa(
        row,
        extra={
            "candidate_count": len(candidate_rows),
            "judge_applied": True,
            "confidence_overall": confidence_overall,
        },
    )
    return row


def _apply_scene_quality_gates(scene_row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    row = dict(scene_row)
    dropped = {"event": 0, "world": 0, "seed": 0, "payoff": 0}

    def _valid(item: dict[str, Any]) -> bool:
        if not isinstance(item, dict):
            return False
        importance = _clamp_int(item.get("importance"), default=1, low=0, high=3)
        evidence = item.get("evidence")
        has_evidence = isinstance(evidence, list) and len(evidence) >= 2
        return bool(importance > 0 and has_evidence)

    events = row.get("events_json") if isinstance(row.get("events_json"), list) else []
    events2 = [x for x in events if _valid(x)]
    dropped["event"] = max(0, len(events) - len(events2))
    row["events_json"] = events2

    world = row.get("worldbuilding_json") if isinstance(row.get("worldbuilding_json"), list) else []
    world2 = [x for x in world if _valid(x)]
    dropped["world"] = max(0, len(world) - len(world2))
    row["worldbuilding_json"] = world2

    seeds = row.get("foreshadow_json") if isinstance(row.get("foreshadow_json"), list) else []
    seeds2 = [x for x in seeds if _valid(x)]
    dropped["seed"] = max(0, len(seeds) - len(seeds2))
    row["foreshadow_json"] = seeds2

    payoffs = row.get("payoff_json") if isinstance(row.get("payoff_json"), list) else []
    payoffs2 = [x for x in payoffs if _valid(x)]
    dropped["payoff"] = max(0, len(payoffs) - len(payoffs2))
    row["payoff_json"] = payoffs2

    qa = row.get("qa_json") if isinstance(row.get("qa_json"), dict) else {}
    qa["gate_dropped"] = dropped
    row["qa_json"] = _recompute_scene_qa(row, extra=qa)
    return row, dropped


async def _extract_scene_subtask_via_provider(
    *,
    extract_ctx: dict[str, Any],
    scene_row: dict[str, Any],
    scene_text: str,
    task: str,
    candidate: dict[str, Any],
    on_log,
) -> dict[str, Any] | None:
    provider = str(extract_ctx.get("provider") or "rules")
    adapter = extract_ctx.get("provider_adapter")
    if not adapter or not getattr(adapter, "supports_chat_json", False):
        return None
    model = str(extract_ctx.get("model") or "").strip()
    if not model:
        return None

    max_attempts = _clamp_int(extract_ctx.get("max_attempts"), default=2, low=1, high=4)
    timeout_s = _clamp_int(extract_ctx.get("timeout_s"), default=90, low=20, high=240)
    scene_key = str(scene_row.get("scene_key") or "")
    chapter_no = int(scene_row.get("chapter_no") or 0)
    scene_no = int(scene_row.get("scene_no") or 0)
    schema_hint = _scene_subtask_schema_hint(task)

    for attempt in range(1, max_attempts + 1):
        prompt = _build_scene_subtask_prompt(
            task=task,
            scene_key=scene_key,
            chapter_no=chapter_no,
            scene_no=scene_no,
            scene_text=scene_text,
            candidate=candidate,
        )
        try:
            raw = await adapter.chat_json(
                model=model,
                user=prompt,
                system=SCENE_STRICT_JSON_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=900,
                timeout_s=timeout_s,
                retries=1,
                schema_hint=schema_hint,
                meta={
                    "stage": "SPLITBOOK_SCENE_SUBTASK",
                    "task": task,
                    "scene_key": scene_key,
                    "prompt_version": SCENE_PROMPT_VERSION,
                    "schema_version": SCENE_SUBTASK_SCHEMA_VERSION,
                    "attempt": attempt,
                },
            )
            normalized = _validate_scene_subtask_output(task, raw)
            return normalized
        except Exception as exc:
            if callable(on_log):
                await on_log(
                    "WARN",
                    "EXTRACT_SUBTASK",
                    f"scene={scene_key} task={task} attempt={attempt}/{max_attempts} failed: {_err_brief(exc)}",
                )
            if attempt >= max_attempts:
                break
    return None


async def _extract_scene_candidates_via_provider(
    *,
    extract_ctx: dict[str, Any],
    scene_row: dict[str, Any],
    scene_text: str,
    on_log,
) -> list[dict[str, Any]]:
    adapter = extract_ctx.get("provider_adapter")
    if not adapter or not getattr(adapter, "supports_chat_json", False):
        return []
    model = str(extract_ctx.get("candidate_model") or extract_ctx.get("model") or "").strip()
    if not model:
        return []
    max_attempts = _clamp_int(extract_ctx.get("max_attempts"), default=2, low=1, high=4)
    timeout_s = _clamp_int(extract_ctx.get("timeout_s"), default=90, low=20, high=240)
    scene_key = str(scene_row.get("scene_key") or "")
    chapter_no = int(scene_row.get("chapter_no") or 0)
    scene_no = int(scene_row.get("scene_no") or 0)
    prompt = _build_scene_candidate_prompt(
        scene_key=scene_key,
        chapter_no=chapter_no,
        scene_no=scene_no,
        scene_text=scene_text,
    )
    for attempt in range(1, max_attempts + 1):
        try:
            raw = await adapter.chat_json(
                model=model,
                user=prompt,
                system=SCENE_CANDIDATE_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=1200,
                timeout_s=timeout_s,
                retries=1,
                schema_hint=_scene_candidate_schema_hint(),
                meta={
                    "stage": "SPLITBOOK_SCENE_CANDIDATE",
                    "scene_key": scene_key,
                    "prompt_version": SCENE_PROMPT_VERSION,
                    "schema_version": SCENE_CANDIDATE_SCHEMA_VERSION,
                    "attempt": attempt,
                },
            )
            return _validate_scene_candidate_output(raw)
        except Exception as exc:
            if callable(on_log):
                await on_log(
                    "WARN",
                    "EXTRACT_CANDIDATE",
                    f"scene={scene_key} attempt={attempt}/{max_attempts} failed: {_err_brief(exc)}",
                )
            if attempt >= max_attempts:
                break
    return []


async def _extract_scene_judge_via_provider(
    *,
    extract_ctx: dict[str, Any],
    scene_row: dict[str, Any],
    scene_text: str,
    candidate_rows: list[dict[str, Any]],
    on_log,
) -> dict[str, Any] | None:
    adapter = extract_ctx.get("provider_adapter")
    if not adapter or not getattr(adapter, "supports_chat_json", False):
        return None
    model = str(extract_ctx.get("judge_model") or extract_ctx.get("model") or "").strip()
    if not model:
        return None
    max_attempts = _clamp_int(extract_ctx.get("max_attempts"), default=2, low=1, high=4)
    timeout_s = _clamp_int(extract_ctx.get("timeout_s"), default=90, low=20, high=240)
    scene_key = str(scene_row.get("scene_key") or "")
    chapter_no = int(scene_row.get("chapter_no") or 0)
    scene_no = int(scene_row.get("scene_no") or 0)
    prompt = _build_scene_judge_prompt(
        scene_key=scene_key,
        chapter_no=chapter_no,
        scene_no=scene_no,
        scene_text=scene_text,
        candidates=candidate_rows,
    )

    for attempt in range(1, max_attempts + 1):
        try:
            raw = await adapter.chat_json(
                model=model,
                user=prompt,
                system=SCENE_JUDGE_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=1800,
                timeout_s=timeout_s,
                retries=1,
                schema_hint=_scene_judge_schema_hint(),
                meta={
                    "stage": "SPLITBOOK_SCENE_JUDGE",
                    "scene_key": scene_key,
                    "prompt_version": SCENE_PROMPT_VERSION,
                    "schema_version": SCENE_SCHEMA_VERSION,
                    "attempt": attempt,
                },
            )
            return _validate_scene_judge_output(raw)
        except Exception as exc:
            if callable(on_log):
                await on_log(
                    "WARN",
                    "EXTRACT_JUDGE",
                    f"scene={scene_key} attempt={attempt}/{max_attempts} failed: {_err_brief(exc)}",
                )
            # Schema repair fallback: retry once with explicit repair role.
            if attempt < max_attempts:
                broken_json = json.dumps(
                    {
                        "scene_key": scene_key,
                        "candidate_json": candidate_rows or [],
                        "scene_text": str(scene_text or "")[:2200],
                        "error": _err_brief(exc),
                    },
                    ensure_ascii=False,
                )[:4200]
                repair_prompt = build_fix_json_user_prompt(
                    schema_hint=_scene_judge_schema_hint(),
                    broken_json=broken_json,
                )
                try:
                    repaired = await adapter.chat_json(
                        model=model,
                        user=repair_prompt,
                        system=SCENE_REPAIR_SYSTEM_PROMPT,
                        temperature=0.0,
                        max_tokens=1600,
                        timeout_s=timeout_s,
                        retries=1,
                        schema_hint=_scene_judge_schema_hint(),
                        meta={
                            "stage": "SPLITBOOK_SCENE_JUDGE_REPAIR",
                            "scene_key": scene_key,
                            "prompt_version": SCENE_PROMPT_VERSION,
                            "schema_version": SCENE_SCHEMA_VERSION,
                            "attempt": attempt,
                        },
                    )
                    return _validate_scene_judge_output(repaired)
                except Exception:
                    pass
            if attempt >= max_attempts:
                break
    return None


async def _run_scene_subtasks(
    *,
    scene_row: dict[str, Any],
    scene_text: str,
    span_start: int,
    extract_ctx: dict[str, Any] | None,
    on_log,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    if not extract_ctx:
        return scene_row, _rebuild_seed_items_from_scene_row(scene_row), _rebuild_payoff_items_from_scene_row(scene_row)
    provider = str(extract_ctx.get("provider") or "rules")
    if provider == "rules":
        row = dict(scene_row)
        row["qa_json"] = _recompute_scene_qa(
            row,
            extra={
                "subtask_runner": {
                    "provider": "rules",
                    "prompt_version": SCENE_PROMPT_VERSION,
                    "schema_version": SCENE_SUBTASK_SCHEMA_VERSION,
                    "task_total": 0,
                    "task_ok": 0,
                    "task_fallback": 0,
                }
            },
        )
        row, _ = _apply_scene_quality_gates(row)
        return row, _rebuild_seed_items_from_scene_row(row), _rebuild_payoff_items_from_scene_row(row)

    row = dict(scene_row)
    use_scene_judge = bool(extract_ctx.get("use_scene_judge", True))
    if use_scene_judge:
        candidate_rows = await _extract_scene_candidates_via_provider(
            extract_ctx=extract_ctx,
            scene_row=row,
            scene_text=scene_text,
            on_log=on_log,
        )
        judged = await _extract_scene_judge_via_provider(
            extract_ctx=extract_ctx,
            scene_row=row,
            scene_text=scene_text,
            candidate_rows=candidate_rows,
            on_log=on_log,
        )
        if isinstance(judged, dict):
            row = _apply_scene_judge_record(
                scene_row=row,
                judged=judged,
                scene_text=scene_text,
                span_start=span_start,
                model_id=str(extract_ctx.get("judge_model") or extract_ctx.get("model") or ""),
                candidate_rows=candidate_rows,
            )
            row, dropped = _apply_scene_quality_gates(row)
            row["qa_json"] = _recompute_scene_qa(
                row,
                extra={
                    "pipeline": "candidate_judge",
                    "provider": provider,
                    "candidate_count": len(candidate_rows),
                    "task_total": 2,
                    "task_ok": 2,
                    "task_fallback": 0,
                    "task_status": {"candidate": "ok", "judge": "ok"},
                    "gate_dropped": dropped,
                },
            )
            return row, _rebuild_seed_items_from_scene_row(row), _rebuild_payoff_items_from_scene_row(row)

    tasks = extract_ctx.get("tasks")
    if not isinstance(tasks, (list, tuple)):
        tasks = list(SCENE_SUBTASKS)
    candidates = _scene_subtask_candidates_from_row(row)
    task_ok = 0
    task_fallback = 0
    task_status: dict[str, str] = {}
    for task in tasks:
        task_name = str(task or "").strip().lower()
        if not task_name:
            continue
        candidate = candidates.get(task_name) if isinstance(candidates.get(task_name), dict) else {}
        result = await _extract_scene_subtask_via_provider(
            extract_ctx=extract_ctx,
            scene_row=row,
            scene_text=scene_text,
            task=task_name,
            candidate=candidate,
            on_log=on_log,
        )
        if not isinstance(result, dict):
            task_fallback += 1
            task_status[task_name] = "fallback"
            continue
        row = _apply_scene_subtask_result(
            scene_row=row,
            task=task_name,
            result=result,
            scene_text=scene_text,
            span_start=span_start,
        )
        candidates = _scene_subtask_candidates_from_row(row)
        task_ok += 1
        task_status[task_name] = "ok"

    row, dropped = _apply_scene_quality_gates(row)
    row["qa_json"] = _recompute_scene_qa(
        row,
        extra={
            "subtask_runner": {
                "provider": provider,
                "model": str(extract_ctx.get("model") or ""),
                "prompt_version": SCENE_PROMPT_VERSION,
                "schema_version": SCENE_SUBTASK_SCHEMA_VERSION,
                "task_total": len(list(tasks)),
                "task_ok": task_ok,
                "task_fallback": task_fallback,
                "task_status": task_status,
                "gate_dropped": dropped,
            }
        },
    )
    return row, _rebuild_seed_items_from_scene_row(row), _rebuild_payoff_items_from_scene_row(row)


def _stage_by_score(score: int) -> str:
    if score <= 0:
        return "潜伏期"
    if score <= 2:
        return "起步期"
    if score <= 5:
        return "攀升期"
    if score <= 8:
        return "拐点期"
    return "稳定强化期"


def _char_ngram_set(text_value: str, n: int = 5, max_chars: int = 24000) -> set[str]:
    text_norm = re.sub(r"\s+", "", str(text_value or ""))[: max(0, int(max_chars))]
    if not text_norm:
        return set()
    if len(text_norm) <= n:
        return {text_norm}
    out: set[str] = set()
    for i in range(0, len(text_norm) - n + 1):
        out.add(text_norm[i : i + n])
    return out


def _auto_tune_ingest(file_size_bytes: int, chunk_size: int, overlap: int, batch_insert: int) -> tuple[int, int, int]:
    size_mb = max(0.0, float(file_size_bytes) / 1024.0 / 1024.0)
    tuned_chunk = chunk_size
    tuned_overlap = overlap
    tuned_batch = batch_insert
    if size_mb >= 30:
        tuned_chunk = max(tuned_chunk, 2100)
        tuned_overlap = max(tuned_overlap, 220)
        tuned_batch = max(tuned_batch, 1000)
    elif size_mb >= 15:
        tuned_chunk = max(tuned_chunk, 1800)
        tuned_overlap = max(tuned_overlap, 200)
        tuned_batch = max(tuned_batch, 800)
    elif size_mb >= 8:
        tuned_chunk = max(tuned_chunk, 1500)
        tuned_overlap = max(tuned_overlap, 180)
        tuned_batch = max(tuned_batch, 600)
    elif size_mb >= 4:
        tuned_chunk = max(tuned_chunk, 1300)
        tuned_overlap = max(tuned_overlap, 160)
        tuned_batch = max(tuned_batch, 400)
    tuned_chunk = _clamp_int(tuned_chunk, default=1200, low=600, high=5000)
    tuned_overlap = _clamp_int(tuned_overlap, default=180, low=80, high=max(80, tuned_chunk - 100))
    tuned_batch = _clamp_int(tuned_batch, default=400, low=100, high=2000)
    return tuned_chunk, tuned_overlap, tuned_batch


def _auto_tune_embed(total_chunks: int, batch: int, worker_count: int) -> tuple[int, int]:
    tuned_batch = batch
    tuned_workers = worker_count
    if total_chunks >= 12000:
        tuned_batch = max(tuned_batch, 192)
        tuned_workers = max(tuned_workers, 3)
    elif total_chunks >= 6000:
        tuned_batch = max(tuned_batch, 160)
        tuned_workers = max(tuned_workers, 3)
    elif total_chunks >= 2500:
        tuned_batch = max(tuned_batch, 128)
        tuned_workers = max(tuned_workers, 2)
    else:
        tuned_batch = max(tuned_batch, 96)
        tuned_workers = max(tuned_workers, 2)
    cpu_hint = os.cpu_count() or 4
    tuned_workers = min(tuned_workers, max(2, min(6, cpu_hint // 2)))
    tuned_batch = _clamp_int(tuned_batch, default=128, low=32, high=512)
    tuned_workers = _clamp_int(tuned_workers, default=2, low=1, high=8)
    return tuned_batch, tuned_workers


async def _ensure_splitbook_tables(session: AsyncSession) -> None:
    ddl = [
        """
        CREATE TABLE IF NOT EXISTS splitbook_chunk (
          chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          splitbook_id UUID NOT NULL REFERENCES splitbook(splitbook_id) ON DELETE CASCADE,
          chunk_no INTEGER NOT NULL,
          chapter_no INTEGER NULL,
          chapter_title TEXT NULL,
          text TEXT NOT NULL,
          char_len INTEGER NOT NULL DEFAULT 0,
          token_est INTEGER NOT NULL DEFAULT 0,
          meta JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE(splitbook_id, chunk_no)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_splitbook_chunk_sid_no ON splitbook_chunk(splitbook_id, chunk_no)",
        "CREATE INDEX IF NOT EXISTS idx_splitbook_chunk_sid_chapter ON splitbook_chunk(splitbook_id, chapter_no)",
        """
        CREATE TABLE IF NOT EXISTS splitbook_chunk_embedding (
          chunk_id UUID PRIMARY KEY REFERENCES splitbook_chunk(chunk_id) ON DELETE CASCADE,
          model TEXT NOT NULL,
          dim INTEGER NOT NULL DEFAULT 0,
          vector_json JSONB NOT NULL,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS splitbook_fact (
          fact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          splitbook_id UUID NOT NULL REFERENCES splitbook(splitbook_id) ON DELETE CASCADE,
          chunk_id UUID NULL REFERENCES splitbook_chunk(chunk_id) ON DELETE SET NULL,
          chapter_no INTEGER NULL,
          chapter_title TEXT NULL,
          fact_type TEXT NOT NULL,
          entity TEXT NULL,
          statement TEXT NOT NULL,
          evidence TEXT NULL,
          importance INTEGER NOT NULL DEFAULT 3,
          confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
          evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
          tags TEXT[] NOT NULL DEFAULT '{}'::text[],
          extra JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_splitbook_fact_sid ON splitbook_fact(splitbook_id, chapter_no, fact_type)",
        """
        CREATE TABLE IF NOT EXISTS splitbook_growth_ledger (
          ledger_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          splitbook_id UUID NOT NULL REFERENCES splitbook(splitbook_id) ON DELETE CASCADE,
          chapter_no INTEGER NULL,
          chapter_title TEXT NULL,
          character_name TEXT NOT NULL,
          growth_stage TEXT NOT NULL DEFAULT '',
          growth TEXT NOT NULL DEFAULT '',
          cost TEXT NOT NULL DEFAULT '',
          pressure TEXT NOT NULL DEFAULT '',
          gain TEXT NOT NULL DEFAULT '',
          evidence TEXT NOT NULL DEFAULT '',
          extra JSONB NOT NULL DEFAULT '{}'::jsonb,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_splitbook_growth_sid ON splitbook_growth_ledger(splitbook_id, chapter_no, character_name)",
        """
        CREATE TABLE IF NOT EXISTS splitbook_scene (
          scene_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          splitbook_id UUID NOT NULL REFERENCES splitbook(splitbook_id) ON DELETE CASCADE,
          chunk_id UUID NULL REFERENCES splitbook_chunk(chunk_id) ON DELETE SET NULL,
          chunk_no INTEGER NULL,
          chapter_no INTEGER NULL,
          chapter_title TEXT NULL,
          scene_key TEXT NOT NULL,
          scene_no INTEGER NOT NULL DEFAULT 1,
          span_start INTEGER NOT NULL DEFAULT 0,
          span_end INTEGER NOT NULL DEFAULT 0,
          summary TEXT NOT NULL DEFAULT '',
          time_raw TEXT NOT NULL DEFAULT '',
          time_norm TEXT NOT NULL DEFAULT '',
          time_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
          location_raw TEXT NOT NULL DEFAULT '',
          location_norm TEXT NOT NULL DEFAULT '',
          characters_json JSONB NOT NULL DEFAULT '[]'::jsonb,
          worldbuilding_json JSONB NOT NULL DEFAULT '[]'::jsonb,
          conflict_json JSONB NOT NULL DEFAULT '{}'::jsonb,
          foreshadow_json JSONB NOT NULL DEFAULT '[]'::jsonb,
          payoff_json JSONB NOT NULL DEFAULT '[]'::jsonb,
          events_json JSONB NOT NULL DEFAULT '[]'::jsonb,
          evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
          candidate_json JSONB NOT NULL DEFAULT '{}'::jsonb,
          qa_json JSONB NOT NULL DEFAULT '{}'::jsonb,
          schema_version TEXT NOT NULL DEFAULT 'scene_record_v1',
          prompt_version TEXT NOT NULL DEFAULT 'scene_prompt_v3',
          model_id TEXT NOT NULL DEFAULT '',
          confidence_overall DOUBLE PRECISION NOT NULL DEFAULT 0.0,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE(splitbook_id, scene_key)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_splitbook_scene_sid_chapter ON splitbook_scene(splitbook_id, chapter_no, scene_no)",
        """
        CREATE TABLE IF NOT EXISTS splitbook_pair (
          pair_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          splitbook_id UUID NOT NULL REFERENCES splitbook(splitbook_id) ON DELETE CASCADE,
          seed_scene_key TEXT NOT NULL DEFAULT '',
          payoff_scene_key TEXT NOT NULL DEFAULT '',
          seed_chapter_no INTEGER NULL,
          payoff_chapter_no INTEGER NULL,
          seed_text TEXT NOT NULL DEFAULT '',
          payoff_text TEXT NOT NULL DEFAULT '',
          relation TEXT NOT NULL DEFAULT 'candidate',
          confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
          score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
          rationale TEXT NOT NULL DEFAULT '',
          evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_splitbook_pair_sid_conf ON splitbook_pair(splitbook_id, confidence DESC, created_at DESC)",
        """
        CREATE TABLE IF NOT EXISTS splitbook_event (
          event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          splitbook_id UUID NOT NULL REFERENCES splitbook(splitbook_id) ON DELETE CASCADE,
          scene_key TEXT NOT NULL,
          chapter_no INTEGER NULL,
          scene_no INTEGER NULL,
          beat TEXT NOT NULL DEFAULT '',
          what TEXT NOT NULL DEFAULT '',
          cause TEXT NOT NULL DEFAULT '',
          result TEXT NOT NULL DEFAULT '',
          tension_score INTEGER NOT NULL DEFAULT 0,
          importance INTEGER NOT NULL DEFAULT 1,
          confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
          evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_splitbook_event_sid_chapter ON splitbook_event(splitbook_id, chapter_no, scene_no)",
        """
        CREATE TABLE IF NOT EXISTS splitbook_seed (
          seed_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          splitbook_id UUID NOT NULL REFERENCES splitbook(splitbook_id) ON DELETE CASCADE,
          scene_key TEXT NOT NULL,
          chapter_no INTEGER NULL,
          scene_no INTEGER NULL,
          seed_text TEXT NOT NULL DEFAULT '',
          why TEXT NOT NULL DEFAULT '',
          promise TEXT NOT NULL DEFAULT '',
          importance INTEGER NOT NULL DEFAULT 1,
          confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
          entity_tags TEXT[] NOT NULL DEFAULT '{}'::text[],
          evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_splitbook_seed_sid_chapter ON splitbook_seed(splitbook_id, chapter_no, scene_no)",
        """
        CREATE TABLE IF NOT EXISTS splitbook_payoff_candidate (
          payoff_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          splitbook_id UUID NOT NULL REFERENCES splitbook(splitbook_id) ON DELETE CASCADE,
          scene_key TEXT NOT NULL,
          chapter_no INTEGER NULL,
          scene_no INTEGER NULL,
          payoff_text TEXT NOT NULL DEFAULT '',
          trigger TEXT NOT NULL DEFAULT '',
          effect TEXT NOT NULL DEFAULT '',
          resolves TEXT NOT NULL DEFAULT '',
          importance INTEGER NOT NULL DEFAULT 1,
          confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
          entity_tags TEXT[] NOT NULL DEFAULT '{}'::text[],
          evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_splitbook_payoff_sid_chapter ON splitbook_payoff_candidate(splitbook_id, chapter_no, scene_no)",
        """
        CREATE TABLE IF NOT EXISTS splitbook_item_embedding (
          emb_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          splitbook_id UUID NOT NULL REFERENCES splitbook(splitbook_id) ON DELETE CASCADE,
          item_type TEXT NOT NULL,
          item_key TEXT NOT NULL,
          model TEXT NOT NULL DEFAULT '',
          vector_json JSONB NOT NULL DEFAULT '[]'::jsonb,
          text_value TEXT NOT NULL DEFAULT '',
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE(splitbook_id, item_type, item_key, model)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_splitbook_item_embedding_sid_type ON splitbook_item_embedding(splitbook_id, item_type, created_at DESC)",
        "ALTER TABLE splitbook_fact ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0",
        "ALTER TABLE splitbook_fact ADD COLUMN IF NOT EXISTS evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb",
        "ALTER TABLE splitbook_scene ADD COLUMN IF NOT EXISTS candidate_json JSONB NOT NULL DEFAULT '{}'::jsonb",
        "ALTER TABLE splitbook_scene ADD COLUMN IF NOT EXISTS prompt_version TEXT NOT NULL DEFAULT 'scene_prompt_v3'",
        "ALTER TABLE splitbook_scene ADD COLUMN IF NOT EXISTS model_id TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE splitbook_scene ADD COLUMN IF NOT EXISTS confidence_overall DOUBLE PRECISION NOT NULL DEFAULT 0.0",
    ]
    for sql in ddl:
        await session.execute(text(sql))
    await session.commit()

async def _insert_chunk_rows(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    stmt = text(
        """
        INSERT INTO splitbook_chunk(splitbook_id, chunk_no, chapter_no, chapter_title, text, char_len, token_est, meta)
        VALUES (:splitbook_id, :chunk_no, :chapter_no, :chapter_title, :text, :char_len, :token_est, CAST(:meta AS jsonb))
        ON CONFLICT (splitbook_id, chunk_no)
        DO UPDATE SET
          chapter_no=EXCLUDED.chapter_no,
          chapter_title=EXCLUDED.chapter_title,
          text=EXCLUDED.text,
          char_len=EXCLUDED.char_len,
          token_est=EXCLUDED.token_est,
          meta=EXCLUDED.meta
        """
    )
    params_list: list[dict[str, Any]] = []
    for row in rows:
        params = dict(row)
        params["meta"] = json.dumps(params.get("meta") or {})
        params_list.append(params)
    await session.execute(stmt, params_list)
    await session.commit()


async def _insert_fact_rows(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    stmt = text(
        """
        INSERT INTO splitbook_fact(
          splitbook_id, chunk_id, chapter_no, chapter_title, fact_type, entity, statement, evidence, importance, confidence, evidence_json, tags, extra
        )
        VALUES (
          :splitbook_id, :chunk_id, :chapter_no, :chapter_title, :fact_type, :entity, :statement, :evidence, :importance, :confidence, CAST(:evidence_json AS jsonb), CAST(:tags AS text[]), CAST(:extra AS jsonb)
        )
        """
    )
    params_list: list[dict[str, Any]] = []
    for row in rows:
        params = dict(row)
        params["tags"] = row.get("tags") or []
        params["confidence"] = float(row.get("confidence") or 0.0)
        params["evidence_json"] = json.dumps(row.get("evidence_json") or [], ensure_ascii=False)
        params["extra"] = json.dumps(row.get("extra") or {})
        params_list.append(params)
    await session.execute(stmt, params_list)
    await session.commit()


async def _insert_growth_rows(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    stmt = text(
        """
        INSERT INTO splitbook_growth_ledger(splitbook_id, chapter_no, chapter_title, character_name, growth_stage, growth, cost, pressure, gain, evidence, extra, updated_at)
        VALUES (:splitbook_id, :chapter_no, :chapter_title, :character_name, :growth_stage, :growth, :cost, :pressure, :gain, :evidence, CAST(:extra AS jsonb), now())
        """
    )
    params_list: list[dict[str, Any]] = []
    for row in rows:
        params = dict(row)
        params["extra"] = json.dumps(row.get("extra") or {})
        params_list.append(params)
    await session.execute(stmt, params_list)
    await session.commit()


async def _insert_scene_rows(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    stmt = text(
        """
        INSERT INTO splitbook_scene(
          splitbook_id, chunk_id, chunk_no, chapter_no, chapter_title,
          scene_key, scene_no, span_start, span_end, summary,
          time_raw, time_norm, time_confidence, location_raw, location_norm,
          characters_json, worldbuilding_json, conflict_json,
          foreshadow_json, payoff_json, events_json, evidence_json, candidate_json, qa_json,
          schema_version, prompt_version, model_id, confidence_overall
        )
        VALUES (
          :splitbook_id, CAST(:chunk_id AS uuid), :chunk_no, :chapter_no, :chapter_title,
          :scene_key, :scene_no, :span_start, :span_end, :summary,
          :time_raw, :time_norm, :time_confidence, :location_raw, :location_norm,
          CAST(:characters_json AS jsonb), CAST(:worldbuilding_json AS jsonb), CAST(:conflict_json AS jsonb),
          CAST(:foreshadow_json AS jsonb), CAST(:payoff_json AS jsonb), CAST(:events_json AS jsonb),
          CAST(:evidence_json AS jsonb), CAST(:candidate_json AS jsonb), CAST(:qa_json AS jsonb),
          :schema_version, :prompt_version, :model_id, :confidence_overall
        )
        ON CONFLICT (splitbook_id, scene_key) DO UPDATE SET
          chunk_id=EXCLUDED.chunk_id,
          chunk_no=EXCLUDED.chunk_no,
          chapter_no=EXCLUDED.chapter_no,
          chapter_title=EXCLUDED.chapter_title,
          scene_no=EXCLUDED.scene_no,
          span_start=EXCLUDED.span_start,
          span_end=EXCLUDED.span_end,
          summary=EXCLUDED.summary,
          time_raw=EXCLUDED.time_raw,
          time_norm=EXCLUDED.time_norm,
          time_confidence=EXCLUDED.time_confidence,
          location_raw=EXCLUDED.location_raw,
          location_norm=EXCLUDED.location_norm,
          characters_json=EXCLUDED.characters_json,
          worldbuilding_json=EXCLUDED.worldbuilding_json,
          conflict_json=EXCLUDED.conflict_json,
          foreshadow_json=EXCLUDED.foreshadow_json,
          payoff_json=EXCLUDED.payoff_json,
          events_json=EXCLUDED.events_json,
          evidence_json=EXCLUDED.evidence_json,
          candidate_json=EXCLUDED.candidate_json,
          qa_json=EXCLUDED.qa_json,
          schema_version=EXCLUDED.schema_version,
          prompt_version=EXCLUDED.prompt_version,
          model_id=EXCLUDED.model_id,
          confidence_overall=EXCLUDED.confidence_overall
        """
    )
    params_list: list[dict[str, Any]] = []
    for row in rows:
        params = dict(row)
        params["characters_json"] = json.dumps(row.get("characters_json") or [], ensure_ascii=False)
        params["worldbuilding_json"] = json.dumps(row.get("worldbuilding_json") or [], ensure_ascii=False)
        params["conflict_json"] = json.dumps(row.get("conflict_json") or {}, ensure_ascii=False)
        params["foreshadow_json"] = json.dumps(row.get("foreshadow_json") or [], ensure_ascii=False)
        params["payoff_json"] = json.dumps(row.get("payoff_json") or [], ensure_ascii=False)
        params["events_json"] = json.dumps(row.get("events_json") or [], ensure_ascii=False)
        params["evidence_json"] = json.dumps(row.get("evidence_json") or {}, ensure_ascii=False)
        params["candidate_json"] = json.dumps(row.get("candidate_json") or {}, ensure_ascii=False)
        params["qa_json"] = json.dumps(row.get("qa_json") or {}, ensure_ascii=False)
        params["prompt_version"] = str(row.get("prompt_version") or SCENE_PROMPT_VERSION)
        params["model_id"] = str(row.get("model_id") or "")
        params["confidence_overall"] = float(row.get("confidence_overall") or 0.0)
        params_list.append(params)
    await session.execute(stmt, params_list)
    await session.commit()


async def _insert_pair_rows(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    stmt = text(
        """
        INSERT INTO splitbook_pair(
          splitbook_id, seed_scene_key, payoff_scene_key, seed_chapter_no, payoff_chapter_no,
          seed_text, payoff_text, relation, confidence, score, rationale, evidence_json
        )
        VALUES (
          :splitbook_id, :seed_scene_key, :payoff_scene_key, :seed_chapter_no, :payoff_chapter_no,
          :seed_text, :payoff_text, :relation, :confidence, :score, :rationale, CAST(:evidence_json AS jsonb)
        )
        """
    )
    params_list: list[dict[str, Any]] = []
    for row in rows:
        params = dict(row)
        params["evidence_json"] = json.dumps(row.get("evidence_json") or {}, ensure_ascii=False)
        params_list.append(params)
    await session.execute(stmt, params_list)
    await session.commit()


async def _insert_event_rows(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    stmt = text(
        """
        INSERT INTO splitbook_event(
          splitbook_id, scene_key, chapter_no, scene_no, beat, what, cause, result, tension_score, importance, confidence, evidence_json
        )
        VALUES (
          :splitbook_id, :scene_key, :chapter_no, :scene_no, :beat, :what, :cause, :result, :tension_score, :importance, :confidence, CAST(:evidence_json AS jsonb)
        )
        """
    )
    params_list: list[dict[str, Any]] = []
    for row in rows:
        p = dict(row)
        p["evidence_json"] = json.dumps(row.get("evidence_json") or [], ensure_ascii=False)
        params_list.append(p)
    await session.execute(stmt, params_list)
    await session.commit()


async def _insert_seed_rows(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    stmt = text(
        """
        INSERT INTO splitbook_seed(
          splitbook_id, scene_key, chapter_no, scene_no, seed_text, why, promise, importance, confidence, entity_tags, evidence_json
        )
        VALUES (
          :splitbook_id, :scene_key, :chapter_no, :scene_no, :seed_text, :why, :promise, :importance, :confidence, CAST(:entity_tags AS text[]), CAST(:evidence_json AS jsonb)
        )
        """
    )
    params_list: list[dict[str, Any]] = []
    for row in rows:
        p = dict(row)
        p["entity_tags"] = row.get("entity_tags") if isinstance(row.get("entity_tags"), list) else []
        p["evidence_json"] = json.dumps(row.get("evidence_json") or [], ensure_ascii=False)
        params_list.append(p)
    await session.execute(stmt, params_list)
    await session.commit()


async def _insert_payoff_rows(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    stmt = text(
        """
        INSERT INTO splitbook_payoff_candidate(
          splitbook_id, scene_key, chapter_no, scene_no, payoff_text, trigger, effect, resolves, importance, confidence, entity_tags, evidence_json
        )
        VALUES (
          :splitbook_id, :scene_key, :chapter_no, :scene_no, :payoff_text, :trigger, :effect, :resolves, :importance, :confidence, CAST(:entity_tags AS text[]), CAST(:evidence_json AS jsonb)
        )
        """
    )
    params_list: list[dict[str, Any]] = []
    for row in rows:
        p = dict(row)
        p["entity_tags"] = row.get("entity_tags") if isinstance(row.get("entity_tags"), list) else []
        p["evidence_json"] = json.dumps(row.get("evidence_json") or [], ensure_ascii=False)
        params_list.append(p)
    await session.execute(stmt, params_list)
    await session.commit()


async def _insert_item_embedding_rows(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    stmt = text(
        """
        INSERT INTO splitbook_item_embedding(splitbook_id, item_type, item_key, model, vector_json, text_value)
        VALUES (:splitbook_id, :item_type, :item_key, :model, CAST(:vector_json AS jsonb), :text_value)
        ON CONFLICT (splitbook_id, item_type, item_key, model)
        DO UPDATE SET vector_json=EXCLUDED.vector_json, text_value=EXCLUDED.text_value, created_at=now()
        """
    )
    params_list: list[dict[str, Any]] = []
    for row in rows:
        p = dict(row)
        p["vector_json"] = json.dumps(row.get("vector_json") or [], ensure_ascii=False)
        params_list.append(p)
    await session.execute(stmt, params_list)
    await session.commit()


async def run_splitbook_ingest_job(session: AsyncSession, payload: dict[str, Any], on_progress, on_log) -> dict[str, Any]:
    splitbook_id = str(payload.get("splitbook_id") or "")
    path = str(payload.get("path") or "")
    preferred_encoding = str(payload.get("encoding") or "").strip() or None
    chunk_size = _clamp_int(payload.get("chunk_size"), default=1200, low=300, high=5000)
    overlap = _clamp_int(payload.get("overlap"), default=180, low=0, high=max(0, chunk_size - 60))
    batch_insert = _clamp_int(payload.get("batch_insert"), default=200, low=20, high=1000)
    auto_optimize = bool(payload.get("auto_optimize", True))
    if not splitbook_id:
        raise RuntimeError("SPLITBOOK_ID_REQUIRED")
    if not path:
        raise RuntimeError("PATH_REQUIRED")
    if not os.path.exists(path):
        await update_splitbook_status(session, splitbook_id, ingest_status="failed", stats={"last_error": f"FILE_NOT_FOUND:{path}"})
        raise RuntimeError(f"FILE_NOT_FOUND:{path}")
    file_size = os.path.getsize(path)
    if auto_optimize and not str(path).lower().endswith(".jsonl"):
        chunk_size, overlap, batch_insert = _auto_tune_ingest(file_size, chunk_size, overlap, batch_insert)

    await _ensure_splitbook_tables(session)
    await update_splitbook_status(session, splitbook_id, ingest_status="ingesting", embed_status="pending")
    await on_progress(5, "PREPARE", "准备拆书导入")
    await on_log("INFO", "PREPARE", f"path={path}")
    await on_log(
        "INFO",
        "PREPARE",
        f"size_mb={round(file_size / 1024 / 1024, 2)} chunk_size={chunk_size} overlap={overlap} batch_insert={batch_insert} auto_optimize={auto_optimize}",
    )

    await session.execute(text("DELETE FROM splitbook_chunk_embedding WHERE chunk_id IN (SELECT chunk_id FROM splitbook_chunk WHERE splitbook_id=:sid)"), {"sid": splitbook_id})
    await session.execute(text("DELETE FROM splitbook_pair WHERE splitbook_id=:sid"), {"sid": splitbook_id})
    await session.execute(text("DELETE FROM splitbook_scene WHERE splitbook_id=:sid"), {"sid": splitbook_id})
    await session.execute(text("DELETE FROM splitbook_fact WHERE splitbook_id=:sid"), {"sid": splitbook_id})
    await session.execute(text("DELETE FROM splitbook_growth_ledger WHERE splitbook_id=:sid"), {"sid": splitbook_id})
    await session.execute(text("DELETE FROM splitbook_chunk WHERE splitbook_id=:sid"), {"sid": splitbook_id})
    await session.commit()

    encoding = _detect_encoding(path, preferred=preferred_encoding)
    await on_log("INFO", "PREPARE", f"encoding={encoding}")
    await on_progress(12, "LOAD_FILE", "流式读取并分段")

    if str(path).lower().endswith(".jsonl"):
        await on_progress(20, "LOAD_JSONL", "检测到预切分 JSONL，直接分批入库")
        chunk_rows: list[dict[str, Any]] = []
        chunk_no = 0
        chars_read = 0
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line_no, raw in enumerate(f, start=1):
                line = raw.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                text_value = str(row.get("text") or "").strip()
                if not text_value:
                    continue
                chunk_no += 1
                chars_read += len(text_value)
                chunk_rows.append(
                    {
                        "splitbook_id": splitbook_id,
                        "chunk_no": chunk_no,
                        "chapter_no": row.get("chapter_no"),
                        "chapter_title": str(row.get("chapter_title") or "未分章"),
                        "text": text_value,
                        "char_len": len(text_value),
                        "token_est": max(1, len(text_value) // 2),
                        "meta": {"source": "prechunk_jsonl", "line_no": line_no},
                    }
                )
                if len(chunk_rows) >= batch_insert:
                    await _insert_chunk_rows(session, chunk_rows)
                    chunk_rows = []
            if chunk_rows:
                await _insert_chunk_rows(session, chunk_rows)
        await update_splitbook_status(
            session,
            splitbook_id,
            ingest_status="done",
            embed_status="pending",
            stats={
                "chars_read": chars_read,
                "chunks_total": chunk_no,
                "chunk_size": chunk_size,
                "overlap": overlap,
                "paragraph_total": 0,
                "chapter_total": 0,
                "encoding": "utf-8(jsonl)",
                "ingest_source": "prechunk_jsonl",
            },
        )
        await on_progress(100, "DONE", "JSONL 预切分导入完成")
        return {
            "splitbook_id": splitbook_id,
            "status": "done",
            "encoding": "utf-8(jsonl)",
            "chars_read": chars_read,
            "chunks_written": chunk_no,
            "chapters_detected": 0,
        }

    chunk_rows: list[dict[str, Any]] = []
    chunk_no = 0
    chars_read = 0
    paragraph_count = 0
    chapter_count = 0
    current_chapter_no = 0
    current_chapter_title = "第1章（自动分章）"
    paragraph_buf: list[str] = []
    current_chunk = ""
    overlap_seed = ""

    async def flush_chunk(keep_overlap: bool = True) -> None:
        nonlocal current_chunk, chunk_no, overlap_seed, chunk_rows
        text_value = current_chunk.strip()
        if not text_value:
            current_chunk = ""
            overlap_seed = ""
            return
        chunk_no += 1
        chunk_rows.append(
            {
                "splitbook_id": splitbook_id,
                "chunk_no": chunk_no,
                "chapter_no": current_chapter_no or 1,
                "chapter_title": current_chapter_title,
                "text": text_value,
                "char_len": len(text_value),
                "token_est": max(1, len(text_value) // 2),
                "meta": {"chunk_size": chunk_size, "overlap": overlap, "ingested_at": _now_iso()},
            }
        )
        overlap_seed = text_value[-overlap:] if keep_overlap and overlap > 0 else ""
        current_chunk = overlap_seed
        if len(chunk_rows) >= batch_insert:
            await _insert_chunk_rows(session, chunk_rows)
            chunk_rows = []

    async def append_paragraph(paragraph: str) -> None:
        nonlocal current_chunk
        para = paragraph.strip()
        if not para:
            return
        if not current_chunk and overlap_seed:
            current_chunk = overlap_seed
        if not current_chunk:
            current_chunk = para
            if len(current_chunk) >= chunk_size:
                for piece in _hard_split(current_chunk, chunk_size=chunk_size, overlap=overlap):
                    current_chunk = piece
                    await flush_chunk(keep_overlap=True)
            return
        candidate = f"{current_chunk}\n\n{para}".strip()
        if len(candidate) <= chunk_size:
            current_chunk = candidate
            return
        await flush_chunk(keep_overlap=True)
        if len(para) <= chunk_size:
            current_chunk = para if not overlap_seed else f"{overlap_seed}\n\n{para}".strip()
            if len(current_chunk) > chunk_size:
                for piece in _hard_split(current_chunk, chunk_size=chunk_size, overlap=overlap):
                    current_chunk = piece
                    await flush_chunk(keep_overlap=True)
            return
        for piece in _hard_split(para, chunk_size=chunk_size, overlap=overlap):
            current_chunk = piece
            await flush_chunk(keep_overlap=True)

    async def flush_paragraph() -> None:
        nonlocal paragraph_count, paragraph_buf
        if not paragraph_buf:
            return
        paragraph = " ".join(paragraph_buf).strip()
        paragraph_buf = []
        if not paragraph:
            return
        paragraph_count += 1
        await append_paragraph(paragraph)

    async def switch_chapter(next_title: str) -> None:
        nonlocal current_chapter_no, chapter_count, current_chapter_title, overlap_seed, current_chunk
        await flush_paragraph()
        await flush_chunk(keep_overlap=False)
        overlap_seed = ""
        current_chunk = ""
        current_chapter_no += 1
        chapter_count += 1
        title = str(next_title or f"第{current_chapter_no}章").strip()
        current_chapter_title = title[:120] if title else f"第{current_chapter_no}章"

    with open(path, "r", encoding=encoding, errors="replace") as f:
        for idx, raw_line in enumerate(f, start=1):
            line = raw_line.replace("\r\n", "\n").replace("\r", "\n")
            chars_read += len(line)
            stripped = line.strip()
            if stripped:
                markers = _find_inline_chapter_markers(stripped)
                if markers:
                    cursor = 0
                    for start, end, marker_title in markers:
                        before = stripped[cursor:start].strip()
                        if before:
                            paragraph_buf.append(before)
                        await switch_chapter(marker_title)
                        cursor = end
                    tail = stripped[cursor:].strip()
                    if tail:
                        paragraph_buf.append(tail)
                    if idx % 2000 == 0:
                        pct = min(85, 15 + idx // 2000)
                        await on_progress(pct, "LOAD_FILE", f"已处理行数：{idx}")
                    continue
            if not stripped:
                await flush_paragraph()
            else:
                paragraph_buf.append(stripped)
            if idx % 2000 == 0:
                pct = min(85, 15 + idx // 2000)
                await on_progress(pct, "LOAD_FILE", f"已处理行数：{idx}")
    await flush_paragraph()
    await flush_chunk(keep_overlap=False)
    if chunk_rows:
        await _insert_chunk_rows(session, chunk_rows)

    await update_splitbook_status(
        session,
        splitbook_id,
        ingest_status="done",
        embed_status="pending",
        stats={
            "chars_read": chars_read,
            "chunks_total": chunk_no,
            "chunk_size": chunk_size,
            "overlap": overlap,
            "paragraph_total": paragraph_count,
            "chapter_total": chapter_count,
            "encoding": encoding,
            "auto_optimize": auto_optimize,
            "chapter_detection_mode": "line_and_inline_v2",
        },
    )
    await on_progress(100, "DONE", "拆书导入完成")
    return {
        "splitbook_id": splitbook_id,
        "status": "done",
        "encoding": encoding,
        "chars_read": chars_read,
        "chunks_written": chunk_no,
        "chapters_detected": chapter_count,
    }

async def run_splitbook_embed_job(session: AsyncSession, payload: dict[str, Any], on_progress, on_log) -> dict[str, Any]:
    splitbook_id = str(payload.get("splitbook_id") or "")
    model = str(payload.get("model") or settings.embedding_model or "bge-m3:latest")
    batch = _clamp_int(payload.get("batch"), default=32, low=1, high=256)
    force = bool(payload.get("force") or False)
    auto_optimize = bool(payload.get("auto_optimize", True))
    worker_count = _clamp_int(payload.get("worker_count"), default=2, low=1, high=8)
    output_dir = str(payload.get("output_dir") or "").strip()
    if not splitbook_id:
        raise RuntimeError("SPLITBOOK_ID_REQUIRED")

    report_path = ""
    report_error = ""
    report_started_at = _now_iso()
    if output_dir:
        try:
            os.makedirs(output_dir, exist_ok=True)
            report_path = os.path.join(
                output_dir,
                f"splitbook_{splitbook_id.replace('-', '')[:12]}_embed_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json",
            )
        except Exception as exc:
            report_error = f"REPORT_DIR_INIT_FAILED:{exc}"
            await on_log("WARN", "EMBED", report_error)

    await _ensure_splitbook_tables(session)
    await update_splitbook_status(session, splitbook_id, embed_status="running")
    await on_progress(10, "LOAD", "加载分块")
    query = text(
        """
        SELECT c.chunk_id, c.text
        FROM splitbook_chunk c
        LEFT JOIN splitbook_chunk_embedding e
          ON e.chunk_id=c.chunk_id AND e.model=:model
        WHERE c.splitbook_id=:sid
          AND (:force = true OR e.chunk_id IS NULL)
        ORDER BY c.chunk_no
        """
    )
    rows = (await session.execute(query, {"sid": splitbook_id, "model": model, "force": force})).mappings().all()
    total = len(rows)
    if auto_optimize and total > 0:
        batch, worker_count = _auto_tune_embed(total, batch, worker_count)
    if total == 0:
        report = {
            "splitbook_id": splitbook_id,
            "status": "done",
            "embedded_total": 0,
            "model": model,
            "batch": batch,
            "force": force,
            "fallback": False,
            "storage": "postgres:splitbook_chunk_embedding",
            "report_started_at": report_started_at,
            "report_generated_at": _now_iso(),
        }
        if report_path:
            try:
                with open(report_path, "w", encoding="utf-8") as fw:
                    fw.write(json.dumps(report, ensure_ascii=False, indent=2))
            except Exception as exc:
                report_error = f"REPORT_WRITE_FAILED:{exc}"
                await on_log("WARN", "EMBED", report_error)
        await update_splitbook_status(
            session,
            splitbook_id,
            embed_status="done",
            stats={
                "embedded_total": 0,
                "embedding_model": model,
                "embedding_report_path": report_path or None,
                "embedding_report_error": report_error or None,
            },
        )
        await on_progress(100, "DONE", "无待向量化分块")
        return {
            "splitbook_id": splitbook_id,
            "embedded_total": 0,
            "status": "done",
            "storage": "postgres:splitbook_chunk_embedding",
            "report_path": report_path or None,
            "report_error": report_error or None,
        }

    client = OllamaClient(settings.ollama_host)
    done = 0
    fallback_mode = False
    await on_log(
        "INFO",
        "EMBED",
        f"model={model} total={total} batch={batch} workers={worker_count} auto_optimize={auto_optimize}",
    )
    upsert_stmt = text(
        """
        INSERT INTO splitbook_chunk_embedding(chunk_id, model, dim, vector_json, updated_at)
        VALUES (:chunk_id, :model, :dim, CAST(:vector_json AS jsonb), now())
        ON CONFLICT (chunk_id)
        DO UPDATE SET model=EXCLUDED.model, dim=EXCLUDED.dim, vector_json=EXCLUDED.vector_json, updated_at=now()
        """
    )
    segments = [rows[start : start + batch] for start in range(0, total, batch)]
    sem = asyncio.Semaphore(max(1, worker_count))

    async def _embed_segment(seg_idx: int, seg_rows: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]], bool]:
        async with sem:
            texts = [str(x["text"] or "") for x in seg_rows]
            used_fallback = False
            try:
                vectors = await client.embeddings(
                    model=model,
                    texts=texts,
                    timeout_s=120,
                    retries=1,
                    meta={"scope": "splitbook.embed", "segment": seg_idx},
                )
            except Exception as exc:
                used_fallback = True
                await on_log("WARN", "EMBED", f"segment={seg_idx} fallback due to: {exc}")
                vectors = [_fallback_embedding(t) for t in texts]
            params_list: list[dict[str, Any]] = []
            for row, vec in zip(seg_rows, vectors):
                params_list.append(
                    {
                        "chunk_id": str(row["chunk_id"]),
                        "model": model,
                        "dim": len(vec),
                        "vector_json": json.dumps(vec),
                    }
                )
            return seg_idx, params_list, used_fallback

    tasks = [asyncio.create_task(_embed_segment(i + 1, seg), name=f"embed-seg-{i+1}") for i, seg in enumerate(segments)]
    for fut in asyncio.as_completed(tasks):
        seg_idx, params_list, used_fallback = await fut
        if params_list:
            await session.execute(upsert_stmt, params_list)
            await session.commit()
            done += len(params_list)
        if used_fallback:
            fallback_mode = True
        pct = min(98, int((done / max(1, total)) * 100))
        await on_progress(pct, "EMBED", f"向量化 {done}/{total}（segment={seg_idx}）")

    report = {
        "splitbook_id": splitbook_id,
        "status": "done",
        "embedded_total": done,
        "model": model,
        "batch": batch,
        "force": force,
        "fallback": fallback_mode,
        "storage": "postgres:splitbook_chunk_embedding",
        "report_started_at": report_started_at,
        "report_generated_at": _now_iso(),
    }
    if report_path:
        try:
            with open(report_path, "w", encoding="utf-8") as fw:
                fw.write(json.dumps(report, ensure_ascii=False, indent=2))
        except Exception as exc:
            report_error = f"REPORT_WRITE_FAILED:{exc}"
            await on_log("WARN", "EMBED", report_error)
    await update_splitbook_status(
        session,
        splitbook_id,
        embed_status="done",
        stats={
            "embedded_total": done,
            "embedding_model": model,
            "embedding_batch": batch,
            "embedding_fallback": fallback_mode,
            "embedding_report_path": report_path or None,
            "embedding_report_error": report_error or None,
        },
    )
    await on_progress(100, "DONE", "向量化完成")
    return {
        "splitbook_id": splitbook_id,
        "status": "done",
        "embedded_total": done,
        "model": model,
        "fallback": fallback_mode,
        "storage": "postgres:splitbook_chunk_embedding",
        "report_path": report_path or None,
        "report_error": report_error or None,
    }


def _extract_chunk_structured(chunk: dict[str, Any], cumulative: dict[str, int]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    splitbook_id = str(chunk.get("splitbook_id") or "")
    chunk_id = str(chunk.get("chunk_id") or "") or None
    chapter_no = chunk.get("chapter_no")
    chapter_title = str(chunk.get("chapter_title") or "")
    text_value = str(chunk.get("text") or "")
    sentences = _split_sentences(text_value)
    facts: list[dict[str, Any]] = []
    growth_rows: list[dict[str, Any]] = []
    names: set[str] = set()
    for sent in sentences:
        for name in NAME_RE.findall(sent):
            if 2 <= len(name) <= 4:
                names.add(name)
                facts.append(
                    {
                        "splitbook_id": splitbook_id,
                        "chunk_id": chunk_id,
                        "chapter_no": chapter_no,
                        "chapter_title": chapter_title,
                        "fact_type": "character",
                        "entity": name,
                        "statement": sent[:220],
                        "evidence": sent[:220],
                        "importance": 3,
                        "tags": ["人物", "关系"],
                        "extra": {"source": "extract", "dimension": "character"},
                    }
                )
        for word in TIME_WORDS:
            if word in sent:
                facts.append(
                    {
                        "splitbook_id": splitbook_id,
                        "chunk_id": chunk_id,
                        "chapter_no": chapter_no,
                        "chapter_title": chapter_title,
                        "fact_type": "timeline",
                        "entity": word,
                        "statement": sent[:220],
                        "evidence": sent[:220],
                        "importance": 3,
                        "tags": ["时间线"],
                        "extra": {"source": "extract", "dimension": "timeline"},
                    }
                )
                break
        for word in WORLD_WORDS:
            if word in sent:
                facts.append(
                    {
                        "splitbook_id": splitbook_id,
                        "chunk_id": chunk_id,
                        "chapter_no": chapter_no,
                        "chapter_title": chapter_title,
                        "fact_type": "world",
                        "entity": word,
                        "statement": sent[:220],
                        "evidence": sent[:220],
                        "importance": 4,
                        "tags": ["世界观", "设定"],
                        "extra": {"source": "extract", "dimension": "world"},
                    }
                )
                break
        if any(word in sent for word in CONFLICT_WORDS):
            facts.append(
                {
                    "splitbook_id": splitbook_id,
                    "chunk_id": chunk_id,
                    "chapter_no": chapter_no,
                    "chapter_title": chapter_title,
                    "fact_type": "conflict",
                    "entity": None,
                    "statement": sent[:220],
                    "evidence": sent[:220],
                    "importance": 4,
                    "tags": ["冲突"],
                    "extra": {"source": "extract", "dimension": "plot"},
                }
            )
        if any(word in sent for word in FORESHADOW_WORDS):
            facts.append(
                {
                    "splitbook_id": splitbook_id,
                    "chunk_id": chunk_id,
                    "chapter_no": chapter_no,
                    "chapter_title": chapter_title,
                    "fact_type": "foreshadow",
                    "entity": None,
                    "statement": sent[:220],
                    "evidence": sent[:220],
                    "importance": 4,
                    "tags": ["伏笔"],
                    "extra": {"source": "extract", "dimension": "plot"},
                }
            )
        if any(word in sent for word in PAYOFF_WORDS):
            facts.append(
                {
                    "splitbook_id": splitbook_id,
                    "chunk_id": chunk_id,
                    "chapter_no": chapter_no,
                    "chapter_title": chapter_title,
                    "fact_type": "payoff",
                    "entity": None,
                    "statement": sent[:220],
                    "evidence": sent[:220],
                    "importance": 4,
                    "tags": ["回收", "反转"],
                    "extra": {"source": "extract", "dimension": "plot"},
                }
            )

    for fact in facts:
        if not isinstance(fact, dict):
            continue
        if "confidence" not in fact:
            ftype = str(fact.get("fact_type") or "")
            fact["confidence"] = 0.62 if ftype in {"world", "conflict", "foreshadow", "payoff"} else 0.55
        if "evidence_json" not in fact:
            fact["evidence_json"] = []

    pressure_text = _keyword_pick(sentences, PRESSURE_WORDS)
    cost_text = _keyword_pick(sentences, COST_WORDS)
    gain_text = _keyword_pick(sentences, GAIN_WORDS)
    growth_text = gain_text or _keyword_pick(sentences, ["决定", "变化", "转变", "明白", "选择"], default_text=text_value[:120])
    evidence = pressure_text or cost_text or gain_text or text_value[:160]
    first_sentence = (sentences[0] if sentences else text_value[:180]).strip()[:220]

    if not facts and first_sentence:
        facts.append(
            {
                "splitbook_id": splitbook_id,
                "chunk_id": chunk_id,
                "chapter_no": chapter_no,
                "chapter_title": chapter_title,
                "fact_type": "timeline",
                "entity": "章节推进",
                "statement": first_sentence,
                "evidence": first_sentence,
                "importance": 2,
                "confidence": 0.5,
                "evidence_json": [],
                "tags": ["时间线", "自动补全"],
                "extra": {"source": "extract", "dimension": "timeline", "fallback": True},
            }
        )

    if not names:
        has_growth_signal = bool(
            pressure_text
            or cost_text
            or gain_text
            or any(str(x.get("fact_type") or "") == "conflict" for x in facts)
        )
        if not has_growth_signal:
            return facts, growth_rows
        pseudo_name = "主角（待识别）"
        delta = 0
        if pressure_text:
            delta += 1
        if cost_text:
            delta += 2
        if gain_text:
            delta += 2
        cumulative[pseudo_name] = cumulative.get(pseudo_name, 0) + delta
        growth_rows.append(
            {
                "splitbook_id": splitbook_id,
                "chapter_no": chapter_no,
                "chapter_title": chapter_title,
                "character_name": pseudo_name,
                "growth_stage": _stage_by_score(cumulative[pseudo_name]),
                "growth": growth_text[:220],
                "cost": cost_text[:220],
                "pressure": pressure_text[:220],
                "gain": gain_text[:220],
                "evidence": evidence[:220],
                "extra": {"score": cumulative[pseudo_name], "source": "extract", "fallback": True},
            }
        )
        return facts, growth_rows

    for name in sorted(names):
        delta = 0
        if pressure_text:
            delta += 1
        if cost_text:
            delta += 2
        if gain_text:
            delta += 2
        cumulative[name] = cumulative.get(name, 0) + delta
        growth_rows.append(
            {
                "splitbook_id": splitbook_id,
                "chapter_no": chapter_no,
                "chapter_title": chapter_title,
                "character_name": name,
                "growth_stage": _stage_by_score(cumulative[name]),
                "growth": growth_text[:220],
                "cost": cost_text[:220],
                "pressure": pressure_text[:220],
                "gain": gain_text[:220],
                "evidence": evidence[:220],
                "extra": {"score": cumulative[name], "source": "extract"},
            }
        )
    return facts, growth_rows


def _build_scene_record(
    *,
    scene_unit: dict[str, Any],
    chunk: dict[str, Any],
    cumulative: dict[str, int],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    splitbook_id = str(chunk.get("splitbook_id") or "")
    chunk_id = str(chunk.get("chunk_id") or "") or None
    chunk_no = int(chunk.get("chunk_no") or 0)
    chapter_no = int(chunk.get("chapter_no") or 0)
    chapter_title = str(chunk.get("chapter_title") or "")
    scene_no = int(scene_unit.get("scene_no") or 1)
    scene_text = str(scene_unit.get("text") or "")
    span_start = int(scene_unit.get("start") or 0)
    span_end = int(scene_unit.get("end") or max(span_start, span_start + len(scene_text)))
    scene_key = f"ch{chapter_no:05d}_c{chunk_no:05d}_s{scene_no:03d}"

    sentences = _split_sentences_with_spans(scene_text)
    sentence_texts = [str(x.get("text") or "") for x in sentences]
    summary = "；".join([x for x in sentence_texts[:2] if x])[:220] if sentence_texts else scene_text[:220]
    names = sorted({x for sent in sentence_texts for x in NAME_RE.findall(sent) if 2 <= len(x) <= 4})

    time_raw = ""
    time_span: list[int] = []
    for sent in sentences:
        stxt = str(sent.get("text") or "")
        for word in TIME_WORDS:
            if word in stxt:
                time_raw = word
                time_span = [span_start + int(sent.get("start") or 0), span_start + int(sent.get("end") or 0)]
                break
        if time_raw:
            break
    time_norm, time_conf = _normalize_time_phrase(time_raw)

    location_raw = ""
    location_span: list[int] = []
    for sent in sentences:
        stxt = str(sent.get("text") or "")
        m_loc = LOCATION_RE.search(stxt)
        if m_loc:
            location_raw = str(m_loc.group(1) or "").strip()
            location_span = [span_start + int(sent.get("start") or 0), span_start + int(sent.get("end") or 0)]
            break
    location_norm = location_raw

    conflict_sentences: list[dict[str, Any]] = []
    for sent in sentences:
        stxt = str(sent.get("text") or "")
        if any(word in stxt for word in CONFLICT_WORDS):
            conflict_sentences.append(sent)
    conflict_type = ""
    if conflict_sentences:
        joined = " ".join([str(x.get("text") or "") for x in conflict_sentences[:2]])
        if any(x in joined for x in ["制度", "规则", "法则", "宗门"]):
            conflict_type = "man_vs_system"
        elif any(x in joined for x in ["内心", "犹豫", "恐惧", "后悔"]):
            conflict_type = "man_vs_self"
        else:
            conflict_type = "man_vs_man"
    stakes_text = _keyword_pick(sentence_texts, COST_WORDS, default_text="")
    turning_point = _keyword_pick(sentence_texts, ["却", "但", "然而", "突然", "反转", "没想到"], default_text="")
    conflict_obj = {
        "type": conflict_type,
        "stakes": stakes_text[:180],
        "goal_a": "推进当前目标并脱离不利局面" if conflict_type else "",
        "goal_b": "阻止主角达成目标" if conflict_type else "",
        "turning_point": turning_point[:180],
        "tension_score": 7 if conflict_type else 0,
        "confidence": 0.6 if conflict_type else 0.0,
        "evidence": [
            [span_start + int(x.get("start") or 0), span_start + int(x.get("end") or 0)]
            for x in conflict_sentences[:2]
        ],
    }

    worldbuilding_items: list[dict[str, Any]] = []
    for sent in sentences:
        stxt = str(sent.get("text") or "")
        for word in WORLD_WORDS:
            if word in stxt:
                worldbuilding_items.append(
                    {
                        "type": "rule" if word in {"规则", "法则", "设定", "约束", "限制"} else "system",
                        "item": stxt[:180],
                        "importance": 2,
                        "confidence": 0.62,
                        "evidence": [span_start + int(sent.get("start") or 0), span_start + int(sent.get("end") or 0)],
                    }
                )
                break

    foreshadow_items: list[dict[str, Any]] = []
    payoff_items: list[dict[str, Any]] = []
    for sent in sentences:
        stxt = str(sent.get("text") or "")
        span = [span_start + int(sent.get("start") or 0), span_start + int(sent.get("end") or 0)]
        if any(word in stxt for word in FORESHADOW_WORDS) or any(word in stxt for word in FORESHADOW_SIGNAL_WORDS):
            foreshadow_items.append(
                {
                    "seed": stxt[:180],
                    "why": "异常/暗示信号",
                    "entity_tags": [x for x in NAME_RE.findall(stxt) if 2 <= len(x) <= 4][:4],
                    "promise": "后续可能触发解释或关键事件",
                    "importance": 2,
                    "confidence": 0.55,
                    "evidence": span,
                }
            )
        if any(word in stxt for word in PAYOFF_WORDS) or any(word in stxt for word in PAYOFF_SIGNAL_WORDS):
            payoff_items.append(
                {
                    "event": stxt[:180],
                    "trigger": _keyword_pick([stxt], ["触发", "开启", "揭晓", "终于"], default_text=""),
                    "effect": _keyword_pick([stxt], ["导致", "于是", "结果", "因此"], default_text=""),
                    "resolves": "解释前文异常或兑现前置承诺",
                    "entity_tags": [x for x in NAME_RE.findall(stxt) if 2 <= len(x) <= 4][:4],
                    "importance": 2,
                    "confidence": 0.56,
                    "evidence": span,
                }
            )

    event_beats: list[dict[str, Any]] = []
    for sent in sentences[:8]:
        stxt = str(sent.get("text") or "")
        if not stxt:
            continue
        beat = "推进"
        if any(x in stxt for x in CONFLICT_WORDS):
            beat = "冲突"
        elif any(x in stxt for x in GAIN_WORDS):
            beat = "收获"
        elif any(x in stxt for x in COST_WORDS):
            beat = "代价"
        event_beats.append(
            {
                "beat": beat,
                "what": stxt[:180],
                "tension_score": 7 if beat == "冲突" else 5 if beat == "代价" else 4,
                "importance": 2 if beat in {"冲突", "代价", "收获"} else 1,
                "confidence": 0.58,
                "evidence": [span_start + int(sent.get("start") or 0), span_start + int(sent.get("end") or 0)],
            }
        )

    # Reuse existing chunk-level extraction to keep continuity with historical fields.
    pseudo_chunk = {
        "splitbook_id": splitbook_id,
        "chunk_id": chunk_id,
        "chapter_no": chapter_no,
        "chapter_title": chapter_title,
        "text": scene_text,
    }
    facts, growth_rows = _extract_chunk_structured(pseudo_chunk, cumulative)
    for row in facts:
        extra = row.get("extra") if isinstance(row.get("extra"), dict) else {}
        row["extra"] = {
            **extra,
            "scene_key": scene_key,
            "scene_span": [span_start, span_end],
            "schema_version": SCENE_SCHEMA_VERSION,
        }
    for row in growth_rows:
        extra = row.get("extra") if isinstance(row.get("extra"), dict) else {}
        row["extra"] = {
            **extra,
            "scene_key": scene_key,
            "scene_span": [span_start, span_end],
            "schema_version": SCENE_SCHEMA_VERSION,
        }

    # Scene-level schema validation/repair.
    scene_record = _repair_scene_schema(
        {
            "scene_key": scene_key,
            "summary": summary[:220],
            "time": {"raw": time_raw[:60], "normalized": time_norm[:60], "confidence": round(float(time_conf), 4), "evidence": [time_span] if time_span else []},
            "location": {"raw": location_raw[:80], "normalized": location_norm[:80], "evidence": [location_span] if location_span else []},
            "characters": [{"name": name, "role": "unknown"} for name in names[:12]],
            "worldbuilding": worldbuilding_items[:12],
            "conflict": conflict_obj,
            "foreshadow_candidates": foreshadow_items[:8],
            "payoff_candidates": payoff_items[:8],
            "events": event_beats[:12],
            "evidence": {"scene_span": [span_start, span_end]},
        }
    )

    scene_row = {
        "splitbook_id": splitbook_id,
        "chunk_id": chunk_id,
        "chunk_no": chunk_no,
        "chapter_no": chapter_no,
        "chapter_title": chapter_title,
        "scene_key": scene_key,
        "scene_no": scene_no,
        "span_start": span_start,
        "span_end": span_end,
        "summary": str(scene_record.get("summary") or "")[:220],
        "time_raw": str((scene_record.get("time") or {}).get("raw") or "")[:60],
        "time_norm": str((scene_record.get("time") or {}).get("normalized") or "")[:60],
        "time_confidence": float((scene_record.get("time") or {}).get("confidence") or 0.0),
        "location_raw": str((scene_record.get("location") or {}).get("raw") or "")[:80],
        "location_norm": str((scene_record.get("location") or {}).get("normalized") or "")[:80],
        "characters_json": scene_record.get("characters") if isinstance(scene_record.get("characters"), list) else [],
        "worldbuilding_json": scene_record.get("worldbuilding") if isinstance(scene_record.get("worldbuilding"), list) else [],
        "conflict_json": scene_record.get("conflict") if isinstance(scene_record.get("conflict"), dict) else {},
        "foreshadow_json": scene_record.get("foreshadow_candidates") if isinstance(scene_record.get("foreshadow_candidates"), list) else [],
        "payoff_json": scene_record.get("payoff_candidates") if isinstance(scene_record.get("payoff_candidates"), list) else [],
        "events_json": scene_record.get("events") if isinstance(scene_record.get("events"), list) else [],
        "evidence_json": scene_record.get("evidence") if isinstance(scene_record.get("evidence"), dict) else {},
        "candidate_json": {},
        "qa_json": {
            "has_time": bool((scene_record.get("time") or {}).get("raw")),
            "has_conflict": bool((scene_record.get("conflict") or {}).get("type")),
            "has_worldbuilding": bool(scene_record.get("worldbuilding")),
            "has_foreshadow": bool(scene_record.get("foreshadow_candidates")),
            "has_payoff": bool(scene_record.get("payoff_candidates")),
            "has_evidence": bool((scene_record.get("evidence") or {}).get("scene_span")),
        },
        "schema_version": SCENE_SCHEMA_VERSION,
        "prompt_version": SCENE_PROMPT_VERSION,
        "model_id": "rules",
        "confidence_overall": 0.0,
    }

    seed_items_out = [
        {
            "splitbook_id": splitbook_id,
            "scene_key": scene_key,
            "chapter_no": chapter_no,
            "scene_no": scene_no,
            "seed_text": str(item.get("seed") or "")[:180],
            "entity_tags": item.get("entity_tags") if isinstance(item.get("entity_tags"), list) else [],
            "evidence": item.get("evidence") if isinstance(item.get("evidence"), list) else [],
        }
        for item in (scene_record.get("foreshadow_candidates") if isinstance(scene_record.get("foreshadow_candidates"), list) else [])
        if str(item.get("seed") or "").strip()
    ]
    payoff_items_out = [
        {
            "splitbook_id": splitbook_id,
            "scene_key": scene_key,
            "chapter_no": chapter_no,
            "scene_no": scene_no,
            "payoff_text": str(item.get("event") or "")[:180],
            "entity_tags": item.get("entity_tags") if isinstance(item.get("entity_tags"), list) else [],
            "evidence": item.get("evidence") if isinstance(item.get("evidence"), list) else [],
        }
        for item in (scene_record.get("payoff_candidates") if isinstance(scene_record.get("payoff_candidates"), list) else [])
        if str(item.get("event") or "").strip()
    ]
    return scene_row, facts, growth_rows, seed_items_out, payoff_items_out


def _pair_seed_payoff_items(seed_items: list[dict[str, Any]], payoff_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not seed_items or not payoff_items:
        return []
    pairs: list[dict[str, Any]] = []
    payoff_sorted = sorted(payoff_items, key=lambda x: (int(x.get("chapter_no") or 0), int(x.get("scene_no") or 0)))
    for seed in sorted(seed_items, key=lambda x: (int(x.get("chapter_no") or 0), int(x.get("scene_no") or 0))):
        seed_ch = int(seed.get("chapter_no") or 0)
        seed_scene = int(seed.get("scene_no") or 0)
        seed_text = str(seed.get("seed_text") or "").strip()
        if not seed_text:
            continue
        seed_tags = {str(x).strip() for x in (seed.get("entity_tags") if isinstance(seed.get("entity_tags"), list) else []) if str(x).strip()}
        seed_desc = f"{seed_text} {' '.join(sorted(seed_tags))}"
        seed_vec = _fallback_embedding(seed_desc, dim=96)

        best: dict[str, Any] | None = None
        best_score = 0.0
        for pay in payoff_sorted:
            pay_ch = int(pay.get("chapter_no") or 0)
            pay_scene = int(pay.get("scene_no") or 0)
            if (pay_ch < seed_ch) or (pay_ch == seed_ch and pay_scene <= seed_scene):
                continue
            pay_text = str(pay.get("payoff_text") or "").strip()
            if not pay_text:
                continue
            pay_tags = {str(x).strip() for x in (pay.get("entity_tags") if isinstance(pay.get("entity_tags"), list) else []) if str(x).strip()}
            pay_desc = f"{pay_text} {' '.join(sorted(pay_tags))}"
            pay_vec = _fallback_embedding(pay_desc, dim=96)
            cosine = _cosine_similarity(seed_vec, pay_vec)
            ngram_a = _char_ngram_set(seed_desc, n=3, max_chars=1200)
            ngram_b = _char_ngram_set(pay_desc, n=3, max_chars=1200)
            inter = len(ngram_a & ngram_b)
            union = len(ngram_a | ngram_b) or 1
            jaccard = float(inter / union)
            seq = float(SequenceMatcher(None, seed_desc, pay_desc).ratio())
            overlap = len(seed_tags & pay_tags)
            overlap_bonus = 0.18 if overlap > 0 else 0.0
            chapter_gap = max(0, pay_ch - seed_ch)
            gap_penalty = min(0.16, chapter_gap * 0.004)
            score = max(0.0, (0.45 * cosine + 0.28 * jaccard + 0.22 * seq + overlap_bonus) - gap_penalty)
            if score > best_score:
                best_score = score
                best = {
                    "pay": pay,
                    "score": round(score, 4),
                    "cosine": round(cosine, 4),
                    "jaccard": round(jaccard, 4),
                    "seq": round(seq, 4),
                    "overlap": overlap,
                }
        if not best or float(best.get("score") or 0.0) < 0.22:
            continue
        score = float(best.get("score") or 0.0)
        if score >= 0.72:
            relation = "direct_payoff"
        elif score >= 0.52:
            relation = "indirect_payoff"
        elif score >= 0.38:
            relation = "twist_payoff"
        else:
            relation = "weak_link"
        confidence = round(max(0.2, min(0.99, score)), 4)
        pay = best.get("pay") if isinstance(best.get("pay"), dict) else {}
        pairs.append(
            {
                "splitbook_id": str(seed.get("splitbook_id") or ""),
                "seed_scene_key": str(seed.get("scene_key") or ""),
                "payoff_scene_key": str(pay.get("scene_key") or ""),
                "seed_chapter_no": int(seed.get("chapter_no") or 0),
                "payoff_chapter_no": int(pay.get("chapter_no") or 0),
                "seed_text": str(seed.get("seed_text") or "")[:180],
                "payoff_text": str(pay.get("payoff_text") or "")[:180],
                "relation": relation,
                "confidence": confidence,
                "score": score,
                "rationale": (
                    f"相似度={score:.3f}（cos={float(best.get('cosine') or 0.0):.3f}, jac={float(best.get('jaccard') or 0.0):.3f}, "
                    f"seq={float(best.get('seq') or 0.0):.3f}, overlap={int(best.get('overlap') or 0)}）"
                )[:260],
                "evidence_json": {
                    "seed": seed.get("evidence") if isinstance(seed.get("evidence"), list) else [],
                    "payoff": pay.get("evidence") if isinstance(pay.get("evidence"), list) else [],
                },
            }
        )
    return pairs


def _scene_rows_to_event_rows(scene_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in scene_rows:
        out.extend(_rebuild_event_items_from_scene_row(row))
    return out


def _scene_rows_to_seed_rows(scene_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in scene_rows:
        out.extend(_rebuild_seed_items_from_scene_row(row))
    return out


def _scene_rows_to_payoff_rows(scene_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in scene_rows:
        out.extend(_rebuild_payoff_items_from_scene_row(row))
    return out


def _scene_rows_to_fact_rows(scene_rows: list[dict[str, Any]], *, chapter_title_fallback: str = "") -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in scene_rows:
        splitbook_id = str(row.get("splitbook_id") or "")
        chapter_no = int(row.get("chapter_no") or 0)
        chapter_title = str(row.get("chapter_title") or chapter_title_fallback or f"第{chapter_no}章")
        chunk_id = row.get("chunk_id")
        world_items = row.get("worldbuilding_json") if isinstance(row.get("worldbuilding_json"), list) else []
        for item in world_items[:24]:
            if not isinstance(item, dict):
                continue
            statement = str(item.get("item") or "").strip()[:220]
            if not statement:
                continue
            evidence = item.get("evidence") if isinstance(item.get("evidence"), list) else []
            out.append(
                {
                    "splitbook_id": splitbook_id,
                    "chunk_id": chunk_id,
                    "chapter_no": chapter_no,
                    "chapter_title": chapter_title,
                    "fact_type": "world",
                    "entity": str(item.get("type") or "").strip()[:32] or None,
                    "statement": statement,
                    "evidence": statement[:220],
                    "importance": _clamp_int(item.get("importance"), default=2, low=0, high=3),
                    "confidence": _clamp_float(item.get("confidence"), default=0.58, low=0.0, high=1.0),
                    "evidence_json": evidence if isinstance(evidence, list) else [],
                    "tags": ["scene", "world"],
                    "extra": {
                        "source": "scene_judge",
                        "scene_key": str(row.get("scene_key") or ""),
                        "constraints": str(item.get("constraints") or "").strip()[:140],
                        "cost": str(item.get("cost") or "").strip()[:140],
                    },
                }
            )
        conflict = row.get("conflict_json") if isinstance(row.get("conflict_json"), dict) else {}
        if str(conflict.get("type") or "").strip() and str(conflict.get("type") or "") != "none":
            statement = str(conflict.get("turning_point") or conflict.get("stakes") or "").strip()[:220]
            if statement:
                out.append(
                    {
                        "splitbook_id": splitbook_id,
                        "chunk_id": chunk_id,
                        "chapter_no": chapter_no,
                        "chapter_title": chapter_title,
                        "fact_type": "conflict",
                        "entity": str(conflict.get("type") or "").strip()[:40],
                        "statement": statement,
                        "evidence": statement[:220],
                        "importance": 3,
                        "confidence": _clamp_float(conflict.get("confidence"), default=0.55, low=0.0, high=1.0),
                        "evidence_json": conflict.get("evidence") if isinstance(conflict.get("evidence"), list) else [],
                        "tags": ["scene", "conflict"],
                        "extra": {
                            "source": "scene_judge",
                            "scene_key": str(row.get("scene_key") or ""),
                            "tension_score": _clamp_int(conflict.get("tension_score"), default=0, low=0, high=10),
                        },
                    }
                )
        for seed in (row.get("foreshadow_json") if isinstance(row.get("foreshadow_json"), list) else [])[:24]:
            if not isinstance(seed, dict):
                continue
            statement = str(seed.get("seed") or "").strip()[:220]
            if not statement:
                continue
            out.append(
                {
                    "splitbook_id": splitbook_id,
                    "chunk_id": chunk_id,
                    "chapter_no": chapter_no,
                    "chapter_title": chapter_title,
                    "fact_type": "foreshadow",
                    "entity": None,
                    "statement": statement,
                    "evidence": statement[:220],
                    "importance": _clamp_int(seed.get("importance"), default=2, low=0, high=3),
                    "confidence": _clamp_float(seed.get("confidence"), default=0.55, low=0.0, high=1.0),
                    "evidence_json": seed.get("evidence") if isinstance(seed.get("evidence"), list) else [],
                    "tags": ["scene", "foreshadow"],
                    "extra": {
                        "source": "scene_judge",
                        "scene_key": str(row.get("scene_key") or ""),
                        "promise": str(seed.get("promise") or "").strip()[:160],
                    },
                }
            )
        for payoff in (row.get("payoff_json") if isinstance(row.get("payoff_json"), list) else [])[:24]:
            if not isinstance(payoff, dict):
                continue
            statement = str(payoff.get("event") or "").strip()[:220]
            if not statement:
                continue
            out.append(
                {
                    "splitbook_id": splitbook_id,
                    "chunk_id": chunk_id,
                    "chapter_no": chapter_no,
                    "chapter_title": chapter_title,
                    "fact_type": "payoff",
                    "entity": None,
                    "statement": statement,
                    "evidence": statement[:220],
                    "importance": _clamp_int(payoff.get("importance"), default=2, low=0, high=3),
                    "confidence": _clamp_float(payoff.get("confidence"), default=0.55, low=0.0, high=1.0),
                    "evidence_json": payoff.get("evidence") if isinstance(payoff.get("evidence"), list) else [],
                    "tags": ["scene", "payoff"],
                    "extra": {
                        "source": "scene_judge",
                        "scene_key": str(row.get("scene_key") or ""),
                        "resolves": str(payoff.get("resolves") or "").strip()[:160],
                    },
                }
            )
    return out


def _pair_judge_schema_hint() -> str:
    return (
        '{"is_pair":true,"pair_type":"direct|indirect|twist|subversion|false_lead",'
        '"confidence":0.0,"rationale":"string","what_resolved":"string","not_pair_reason":"string",'
        '"evidence":{"seed":["string"],"payoff":["string"]}}'
    )


def _build_pair_judge_prompt(seed: dict[str, Any], payoff: dict[str, Any]) -> str:
    return (
        "任务=judge_seed_payoff_pair\n"
        f"seed={json.dumps(seed, ensure_ascii=False)}\n"
        f"payoff={json.dumps(payoff, ensure_ascii=False)}\n"
        f"schema_hint={_pair_judge_schema_hint()}\n"
        "请判断二者是否形成伏笔-回收关系。"
    )


def _validate_pair_judge_output(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"is_pair": False, "pair_type": "false_lead", "confidence": 0.0, "rationale": "invalid_response", "what_resolved": "", "not_pair_reason": "invalid_response", "evidence": {"seed": [], "payoff": []}}
    ev = raw.get("evidence") if isinstance(raw.get("evidence"), dict) else {}
    seed_ev = ev.get("seed") if isinstance(ev.get("seed"), list) else []
    payoff_ev = ev.get("payoff") if isinstance(ev.get("payoff"), list) else []
    return {
        "is_pair": bool(raw.get("is_pair")),
        "pair_type": str(raw.get("pair_type") or "false_lead").strip()[:24] or "false_lead",
        "confidence": _clamp_float(raw.get("confidence"), default=0.0, low=0.0, high=1.0),
        "rationale": str(raw.get("rationale") or "").strip()[:260],
        "what_resolved": str(raw.get("what_resolved") or "").strip()[:180],
        "not_pair_reason": str(raw.get("not_pair_reason") or "").strip()[:180],
        "evidence": {
            "seed": [str(x).strip()[:160] for x in seed_ev[:3] if str(x).strip()],
            "payoff": [str(x).strip()[:160] for x in payoff_ev[:3] if str(x).strip()],
        },
    }


async def _judge_pair_candidate_via_provider(
    *,
    extract_ctx: dict[str, Any],
    seed: dict[str, Any],
    payoff: dict[str, Any],
    on_log,
) -> dict[str, Any] | None:
    adapter = extract_ctx.get("provider_adapter")
    if not adapter or not getattr(adapter, "supports_chat_json", False):
        return None
    model = str(extract_ctx.get("pair_judge_model") or extract_ctx.get("judge_model") or extract_ctx.get("model") or "").strip()
    if not model:
        return None
    prompt = _build_pair_judge_prompt(seed, payoff)
    try:
        raw = await adapter.chat_json(
            model=model,
            user=prompt,
            system=PAIR_JUDGE_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=700,
            timeout_s=_clamp_int(extract_ctx.get("timeout_s"), default=90, low=20, high=240),
            retries=1,
            schema_hint=_pair_judge_schema_hint(),
            meta={
                "stage": "SPLITBOOK_PAIR_JUDGE",
                "prompt_version": PAIR_PROMPT_VERSION,
                "seed_scene_key": str(seed.get("scene_key") or ""),
                "payoff_scene_key": str(payoff.get("scene_key") or ""),
            },
        )
        return _validate_pair_judge_output(raw)
    except Exception as exc:
        if callable(on_log):
            await on_log("WARN", "PAIR_JUDGE", f"seed={seed.get('scene_key')} payoff={payoff.get('scene_key')} failed: {_err_brief(exc)}")
        return None


async def _pair_seed_payoff_items_advanced(
    *,
    seed_items: list[dict[str, Any]],
    payoff_items: list[dict[str, Any]],
    extract_ctx: dict[str, Any] | None,
    on_log,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not seed_items or not payoff_items:
        return [], {"seed_total": len(seed_items), "payoff_total": len(payoff_items), "recall_pairs": 0, "judge_pairs": 0}

    adapter = extract_ctx.get("provider_adapter") if isinstance(extract_ctx, dict) else None
    embed_model = str((extract_ctx or {}).get("embedding_model") or (extract_ctx or {}).get("model") or settings.embedding_model or "").strip()

    payoff_desc = [
        f"{str(p.get('payoff_text') or '')} {' '.join([str(x) for x in (p.get('entity_tags') if isinstance(p.get('entity_tags'), list) else [])])}"
        for p in payoff_items
    ]
    payoff_vecs: list[list[float]] = []
    if adapter and getattr(adapter, "supports_embeddings", False):
        try:
            payoff_vecs = await adapter.embed(model=embed_model, texts=payoff_desc, timeout_s=90, retries=1, meta={"stage": "PAIR_PAYOFF_EMBED"})
        except Exception:
            payoff_vecs = [_fallback_embedding(x, dim=96) for x in payoff_desc]
    else:
        payoff_vecs = [_fallback_embedding(x, dim=96) for x in payoff_desc]

    pairs: list[dict[str, Any]] = []
    recall_pairs = 0
    judge_pairs = 0
    for seed in sorted(seed_items, key=lambda x: (int(x.get("chapter_no") or 0), int(x.get("scene_no") or 0))):
        seed_ch = int(seed.get("chapter_no") or 0)
        seed_scene = int(seed.get("scene_no") or 0)
        seed_text = str(seed.get("seed_text") or "").strip()
        if not seed_text:
            continue
        seed_tags = {str(x).strip() for x in (seed.get("entity_tags") if isinstance(seed.get("entity_tags"), list) else []) if str(x).strip()}
        seed_desc = f"{seed_text} {' '.join(sorted(seed_tags))}".strip()
        if adapter and getattr(adapter, "supports_embeddings", False):
            try:
                vecs = await adapter.embed(model=embed_model, texts=[seed_desc], timeout_s=90, retries=1, meta={"stage": "PAIR_SEED_EMBED"})
                seed_vec = vecs[0] if vecs else _fallback_embedding(seed_desc, dim=96)
            except Exception:
                seed_vec = _fallback_embedding(seed_desc, dim=96)
        else:
            seed_vec = _fallback_embedding(seed_desc, dim=96)

        scored: list[dict[str, Any]] = []
        for idx, pay in enumerate(payoff_items):
            pay_ch = int(pay.get("chapter_no") or 0)
            pay_scene = int(pay.get("scene_no") or 0)
            if (pay_ch < seed_ch) or (pay_ch == seed_ch and pay_scene <= seed_scene):
                continue
            pay_text = str(pay.get("payoff_text") or "").strip()
            if not pay_text:
                continue
            pay_tags = {str(x).strip() for x in (pay.get("entity_tags") if isinstance(pay.get("entity_tags"), list) else []) if str(x).strip()}
            pay_desc = payoff_desc[idx]
            pay_vec = payoff_vecs[idx] if idx < len(payoff_vecs) else _fallback_embedding(pay_desc, dim=96)
            cosine = _cosine_similarity(seed_vec, pay_vec)
            ngram_a = _char_ngram_set(seed_desc, n=3, max_chars=1200)
            ngram_b = _char_ngram_set(pay_desc, n=3, max_chars=1200)
            inter = len(ngram_a & ngram_b)
            union = len(ngram_a | ngram_b) or 1
            jaccard = float(inter / union)
            seq = float(SequenceMatcher(None, seed_desc, pay_desc).ratio())
            overlap = len(seed_tags & pay_tags)
            overlap_bonus = 0.18 if overlap > 0 else 0.0
            chapter_gap = max(0, pay_ch - seed_ch)
            gap_penalty = min(0.16, chapter_gap * 0.004)
            score = max(0.0, (0.45 * cosine + 0.28 * jaccard + 0.22 * seq + overlap_bonus) - gap_penalty)
            scored.append(
                {
                    "pay": pay,
                    "score": float(round(score, 4)),
                    "cosine": round(cosine, 4),
                    "jaccard": round(jaccard, 4),
                    "seq": round(seq, 4),
                    "overlap": overlap,
                }
            )
        if not scored:
            continue
        scored.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
        recall_top = scored[:20]
        recall_pairs += len(recall_top)

        filtered: list[dict[str, Any]] = []
        for rank, cand in enumerate(recall_top):
            overlap = int(cand.get("overlap") or 0)
            if overlap > 0:
                filtered.append(cand)
                continue
            if rank == 0:
                cand2 = dict(cand)
                cand2["score"] = min(float(cand2.get("score") or 0.0), 0.6)
                filtered.append(cand2)
        if not filtered:
            continue
        best = filtered[0]
        pay = best.get("pay") if isinstance(best.get("pay"), dict) else {}
        score = float(best.get("score") or 0.0)
        if score < 0.22:
            continue

        relation = "direct"
        if score >= 0.72:
            relation = "direct"
        elif score >= 0.52:
            relation = "indirect"
        elif score >= 0.38:
            relation = "twist"
        else:
            relation = "false_lead"
        confidence = round(max(0.2, min(0.99, score)), 4)

        judge = await _judge_pair_candidate_via_provider(extract_ctx=extract_ctx or {}, seed=seed, payoff=pay, on_log=on_log)
        if isinstance(judge, dict):
            judge_pairs += 1
            if not bool(judge.get("is_pair")):
                continue
            relation = str(judge.get("pair_type") or relation).strip() or relation
            confidence = round(_clamp_float(judge.get("confidence"), default=confidence, low=0.0, high=1.0), 4)
            rationale = str(judge.get("rationale") or "").strip()[:260]
            resolved = str(judge.get("what_resolved") or "").strip()[:180]
            judge_ev = judge.get("evidence") if isinstance(judge.get("evidence"), dict) else {}
        else:
            rationale = (
                f"相似度={score:.3f}（cos={float(best.get('cosine') or 0.0):.3f}, jac={float(best.get('jaccard') or 0.0):.3f}, "
                f"seq={float(best.get('seq') or 0.0):.3f}, overlap={int(best.get('overlap') or 0)}）"
            )[:260]
            resolved = ""
            judge_ev = {}

        pairs.append(
            {
                "splitbook_id": str(seed.get("splitbook_id") or ""),
                "seed_scene_key": str(seed.get("scene_key") or ""),
                "payoff_scene_key": str(pay.get("scene_key") or ""),
                "seed_chapter_no": int(seed.get("chapter_no") or 0),
                "payoff_chapter_no": int(pay.get("chapter_no") or 0),
                "seed_text": str(seed.get("seed_text") or "")[:180],
                "payoff_text": str(pay.get("payoff_text") or "")[:180],
                "relation": relation,
                "confidence": confidence,
                "score": score,
                "rationale": rationale,
                "evidence_json": {
                    "seed": seed.get("evidence") if isinstance(seed.get("evidence"), list) else [],
                    "payoff": pay.get("evidence") if isinstance(pay.get("evidence"), list) else [],
                    "judge_seed": judge_ev.get("seed") if isinstance(judge_ev.get("seed"), list) else [],
                    "judge_payoff": judge_ev.get("payoff") if isinstance(judge_ev.get("payoff"), list) else [],
                    "resolved": resolved,
                },
            }
        )

    return pairs, {
        "seed_total": len(seed_items),
        "payoff_total": len(payoff_items),
        "recall_pairs": recall_pairs,
        "judge_pairs": judge_pairs,
        "pair_total": len(pairs),
    }


async def _build_item_embedding_rows(
    *,
    splitbook_id: str,
    extract_ctx: dict[str, Any],
    seed_rows: list[dict[str, Any]],
    payoff_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    adapter = extract_ctx.get("provider_adapter")
    if not adapter or not getattr(adapter, "supports_embeddings", False):
        return []
    model = str(extract_ctx.get("embedding_model") or extract_ctx.get("model") or settings.embedding_model or "").strip()
    items: list[tuple[str, str, str]] = []
    for idx, row in enumerate(seed_rows):
        scene_key = str(row.get("scene_key") or "")
        key = f"{scene_key}:seed:{idx}" if scene_key else f"seed:{idx}"
        text_value = str(row.get("seed_text") or "")
        if key and text_value:
            items.append(("seed", key, text_value))
    for idx, row in enumerate(payoff_rows):
        scene_key = str(row.get("scene_key") or "")
        key = f"{scene_key}:payoff:{idx}" if scene_key else f"payoff:{idx}"
        text_value = str(row.get("payoff_text") or "")
        if key and text_value:
            items.append(("payoff", key, text_value))
    if not items:
        return []
    texts = [x[2] for x in items]
    try:
        vecs = await adapter.embed(model=model, texts=texts, timeout_s=90, retries=1, meta={"stage": "SPLITBOOK_ITEM_EMBED"})
    except Exception:
        vecs = [_fallback_embedding(x, dim=96) for x in texts]

    out: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        v = vecs[idx] if idx < len(vecs) else _fallback_embedding(item[2], dim=96)
        out.append(
            {
                "splitbook_id": splitbook_id,
                "item_type": item[0],
                "item_key": item[1],
                "model": model,
                "vector_json": v,
                "text_value": item[2][:500],
            }
        )
    return out


def _build_structured_qa_report(
    scene_rows: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
    fact_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    scene_total = len(scene_rows)
    if scene_total <= 0:
        return {
            "coverage": {"scene_total": 0},
            "consistency": {"timeline_conflicts": 0},
            "pairing": {"pair_total": len(pair_rows), "seed_total": 0, "payoff_total": 0, "seed_pair_coverage": 0.0},
            "gates": {"overall": "warn"},
            "generated_at": _now_iso(),
        }
    has_time = sum(1 for s in scene_rows if str(s.get("time_raw") or "").strip())
    has_conflict = sum(1 for s in scene_rows if bool((s.get("conflict_json") if isinstance(s.get("conflict_json"), dict) else {}).get("type")))
    has_world = sum(1 for s in scene_rows if bool(s.get("worldbuilding_json") if isinstance(s.get("worldbuilding_json"), list) else []))
    has_seed = sum(1 for s in scene_rows if bool(s.get("foreshadow_json") if isinstance(s.get("foreshadow_json"), list) else []))
    has_payoff = sum(1 for s in scene_rows if bool(s.get("payoff_json") if isinstance(s.get("payoff_json"), list) else []))
    has_evidence = sum(1 for s in scene_rows if bool((s.get("evidence_json") if isinstance(s.get("evidence_json"), dict) else {}).get("scene_span")))

    seed_total = sum(len(s.get("foreshadow_json") if isinstance(s.get("foreshadow_json"), list) else []) for s in scene_rows)
    payoff_total = sum(len(s.get("payoff_json") if isinstance(s.get("payoff_json"), list) else []) for s in scene_rows)
    paired_seed_count = len({str(p.get("seed_scene_key") or "") for p in pair_rows if str(p.get("seed_scene_key") or "").strip()})
    seed_pair_coverage = round(paired_seed_count / max(1, seed_total), 4)

    chapter_time_bins: dict[int, set[str]] = defaultdict(set)
    for f in fact_rows:
        if str(f.get("fact_type") or "") != "timeline":
            continue
        ch = int(f.get("chapter_no") or 0)
        word = str(f.get("entity") or "").strip()
        if ch > 0 and word:
            chapter_time_bins[ch].add(word)
    timeline_conflicts = sum(1 for words in chapter_time_bins.values() if ("清晨" in words and "深夜" in words))

    chapter_metrics: dict[int, dict[str, Any]] = {}
    review_pool_estimated = 0
    for scene in scene_rows:
        ch = int(scene.get("chapter_no") or 0)
        metrics = chapter_metrics.setdefault(
            ch,
            {
                "events_total": 0,
                "important_events": 0,
                "conflict_tension_ok": False,
                "world_important": 0,
                "has_seed_or_payoff": False,
            },
        )
        events = scene.get("events_json") if isinstance(scene.get("events_json"), list) else []
        metrics["events_total"] += len(events)
        for ev in events:
            if not isinstance(ev, dict):
                continue
            if _clamp_int(ev.get("importance"), default=1, low=0, high=3) >= 2:
                metrics["important_events"] += 1
            if _clamp_int(ev.get("importance"), default=1, low=0, high=3) >= 2 and _clamp_float(ev.get("confidence"), default=0.0, low=0.0, high=1.0) < 0.45:
                review_pool_estimated += 1
        conflict = scene.get("conflict_json") if isinstance(scene.get("conflict_json"), dict) else {}
        if _clamp_int(conflict.get("tension_score"), default=0, low=0, high=10) > 0:
            metrics["conflict_tension_ok"] = True
        world = scene.get("worldbuilding_json") if isinstance(scene.get("worldbuilding_json"), list) else []
        for item in world:
            if not isinstance(item, dict):
                continue
            if _clamp_int(item.get("importance"), default=1, low=0, high=3) >= 2:
                metrics["world_important"] += 1
            if _clamp_int(item.get("importance"), default=1, low=0, high=3) >= 2 and _clamp_float(item.get("confidence"), default=0.0, low=0.0, high=1.0) < 0.45:
                review_pool_estimated += 1
        seeds = scene.get("foreshadow_json") if isinstance(scene.get("foreshadow_json"), list) else []
        payoffs = scene.get("payoff_json") if isinstance(scene.get("payoff_json"), list) else []
        metrics["has_seed_or_payoff"] = bool(metrics["has_seed_or_payoff"] or seeds or payoffs)
        for item in seeds + payoffs:
            if not isinstance(item, dict):
                continue
            if _clamp_int(item.get("importance"), default=1, low=0, high=3) >= 2 and _clamp_float(item.get("confidence"), default=0.0, low=0.0, high=1.0) < 0.45:
                review_pool_estimated += 1

    chapter_gate_failures = 0
    for ch, metrics in chapter_metrics.items():
        _ = ch
        if metrics["events_total"] < 3:
            chapter_gate_failures += 1
            continue
        if metrics["important_events"] < 1:
            chapter_gate_failures += 1
            continue
        if not metrics["conflict_tension_ok"]:
            chapter_gate_failures += 1
            continue
        if metrics["world_important"] < 1:
            chapter_gate_failures += 1
            continue
        if not metrics["has_seed_or_payoff"]:
            chapter_gate_failures += 1

    coverage = {
        "scene_total": scene_total,
        "time_coverage": round(has_time / scene_total, 4),
        "conflict_coverage": round(has_conflict / scene_total, 4),
        "world_coverage": round(has_world / scene_total, 4),
        "foreshadow_coverage": round(has_seed / scene_total, 4),
        "payoff_coverage": round(has_payoff / scene_total, 4),
        "evidence_coverage": round(has_evidence / scene_total, 4),
    }
    pairing = {
        "pair_total": len(pair_rows),
        "seed_total": seed_total,
        "payoff_total": payoff_total,
        "seed_pair_coverage": seed_pair_coverage,
        "low_confidence_pairs": sum(1 for p in pair_rows if float(p.get("confidence") or 0.0) < 0.45),
    }
    consistency = {
        "timeline_conflicts": timeline_conflicts,
        "setting_conflicts": 0,
        "character_drift_alerts": 0,
    }
    gate_ok = (
        coverage["time_coverage"] >= 0.55
        and coverage["conflict_coverage"] >= 0.55
        and coverage["evidence_coverage"] >= 0.9
        and chapter_gate_failures == 0
    )
    return {
        "coverage": coverage,
        "pairing": pairing,
        "consistency": consistency,
        "gates": {
            "overall": "ok" if gate_ok else "warn",
            "chapter_gate_failures": int(chapter_gate_failures),
            "chapter_total": int(len(chapter_metrics)),
        },
        "review_pool_estimated": int(review_pool_estimated),
        "generated_at": _now_iso(),
    }


async def _extract_chunk_structured_advanced(
    chunk: dict[str, Any],
    cumulative: dict[str, int],
    *,
    extract_ctx: dict[str, Any] | None = None,
    on_log=None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    text_value = str(chunk.get("text") or "")
    units = _split_scene_units(text_value)
    all_scene_rows: list[dict[str, Any]] = []
    all_facts: list[dict[str, Any]] = []
    all_growth: list[dict[str, Any]] = []
    all_seed_items: list[dict[str, Any]] = []
    all_payoff_items: list[dict[str, Any]] = []
    for idx, unit in enumerate(units, start=1):
        scene_unit = {**unit, "scene_no": idx}
        scene_row, facts, growth_rows, seed_items, payoff_items = _build_scene_record(
            scene_unit=scene_unit,
            chunk=chunk,
            cumulative=cumulative,
        )
        scene_row, seed_items, payoff_items = await _run_scene_subtasks(
            scene_row=scene_row,
            scene_text=str(scene_unit.get("text") or ""),
            span_start=int(scene_unit.get("start") or 0),
            extract_ctx=extract_ctx,
            on_log=on_log,
        )
        all_scene_rows.append(scene_row)
        all_facts.extend(facts)
        all_growth.extend(growth_rows)
        all_seed_items.extend(seed_items)
        all_payoff_items.extend(payoff_items)
    return all_facts, all_growth, all_scene_rows, all_seed_items, all_payoff_items

async def run_splitbook_extract_structured_job(session: AsyncSession, payload: dict[str, Any], on_progress, on_log) -> dict[str, Any]:
    def _coerce_bool(value: Any, *, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        raw = str(value).strip().lower()
        if raw in {"1", "true", "yes", "y", "on"}:
            return True
        if raw in {"0", "false", "no", "n", "off"}:
            return False
        return default

    splitbook_id = str(payload.get("splitbook_id") or "")
    if not splitbook_id:
        raise RuntimeError("SPLITBOOK_ID_REQUIRED")
    await _ensure_splitbook_tables(session)
    await on_progress(8, "LOAD", "读取分块并抽取结构")
    rows = (
        await session.execute(
            text(
                """
                SELECT chunk_id, splitbook_id, chunk_no, chapter_no, chapter_title, text
                FROM splitbook_chunk
                WHERE splitbook_id=:sid
                ORDER BY chunk_no
                """
            ),
            {"sid": splitbook_id},
        )
    ).mappings().all()
    if not rows:
        raise RuntimeError("SPLITBOOK_CHUNKS_EMPTY")
    await session.execute(text("DELETE FROM splitbook_fact WHERE splitbook_id=:sid"), {"sid": splitbook_id})
    await session.execute(text("DELETE FROM splitbook_growth_ledger WHERE splitbook_id=:sid"), {"sid": splitbook_id})
    await session.execute(text("DELETE FROM splitbook_scene WHERE splitbook_id=:sid"), {"sid": splitbook_id})
    await session.execute(text("DELETE FROM splitbook_pair WHERE splitbook_id=:sid"), {"sid": splitbook_id})
    await session.execute(text("DELETE FROM splitbook_event WHERE splitbook_id=:sid"), {"sid": splitbook_id})
    await session.execute(text("DELETE FROM splitbook_seed WHERE splitbook_id=:sid"), {"sid": splitbook_id})
    await session.execute(text("DELETE FROM splitbook_payoff_candidate WHERE splitbook_id=:sid"), {"sid": splitbook_id})
    await session.execute(text("DELETE FROM splitbook_item_embedding WHERE splitbook_id=:sid"), {"sid": splitbook_id})
    await session.commit()

    requested_provider = payload.get("extract_provider") or payload.get("provider") or settings.splitbook_extract_provider
    provider = _normalize_extract_provider(requested_provider)
    pipeline_mode_raw = str(payload.get("pipeline_mode") or "").strip().lower()
    pipeline_mode = pipeline_mode_raw if pipeline_mode_raw in {"high_precision", "legacy"} else "high_precision"
    default_use_scene_judge = pipeline_mode != "legacy"
    use_scene_judge = _coerce_bool(payload.get("use_scene_judge"), default=default_use_scene_judge)
    default_pair_judge_enabled = pipeline_mode != "legacy"
    pair_judge_enabled = _coerce_bool(payload.get("pair_judge_enabled"), default=default_pair_judge_enabled)
    model = str(payload.get("extract_model") or payload.get("llm_model") or settings.splitbook_extract_model or "").strip()
    candidate_model = str(payload.get("candidate_model") or model or "").strip()
    judge_model = str(payload.get("judge_model") or model or "").strip()
    pair_judge_model = str(payload.get("pair_judge_model") or judge_model or model or "").strip()
    if not pair_judge_enabled:
        pair_judge_model = ""
    embedding_model = str(payload.get("embedding_model") or settings.embedding_model or model or "").strip()
    max_attempts = _clamp_int(
        payload.get("subtask_retries"),
        default=_clamp_int(settings.splitbook_extract_subtask_retries, default=2, low=1, high=4),
        low=1,
        high=4,
    )
    timeout_s = _clamp_int(
        payload.get("subtask_timeout_s"),
        default=_clamp_int(settings.splitbook_extract_timeout_s, default=90, low=20, high=240),
        low=20,
        high=240,
    )
    tasks = list(_normalize_subtask_list(payload.get("subtask_tasks")))
    if provider == "ollama" and not model:
        await on_log("WARN", "EXTRACT", "extract_model 为空，自动降级到 rules")
        provider = "rules"
    provider_adapter = resolve_llm_provider(provider, ollama_host=settings.ollama_host)
    extract_ctx: dict[str, Any] = {
        "provider": provider,
        "model": model,
        "candidate_model": candidate_model,
        "judge_model": judge_model,
        "pair_judge_model": pair_judge_model,
        "embedding_model": embedding_model,
        "use_scene_judge": use_scene_judge,
        "pair_judge_enabled": pair_judge_enabled,
        "pipeline_mode": pipeline_mode,
        "max_attempts": max_attempts,
        "timeout_s": timeout_s,
        "tasks": tasks,
        "provider_adapter": provider_adapter,
        "prompt_version": SCENE_PROMPT_VERSION,
        "schema_version": SCENE_SUBTASK_SCHEMA_VERSION,
    }
    await on_log(
        "INFO",
        "EXTRACT",
        (
            f"provider={provider} model={model or '-'} candidate_model={candidate_model or '-'} judge_model={judge_model or '-'} "
            f"pair_judge_model={pair_judge_model or '-'} tasks={','.join(tasks)} retries={max_attempts} timeout_s={timeout_s} "
            f"use_scene_judge={use_scene_judge} pair_judge_enabled={pair_judge_enabled} pipeline_mode={pipeline_mode}"
        ),
    )

    all_facts: list[dict[str, Any]] = []
    all_growth: list[dict[str, Any]] = []
    all_scenes: list[dict[str, Any]] = []
    all_seed_items: list[dict[str, Any]] = []
    all_payoff_items: list[dict[str, Any]] = []
    cumulative_score: dict[str, int] = {}
    total = len(rows)
    for idx, row in enumerate(rows, start=1):
        facts, growth, scene_rows, seed_items, payoff_items = await _extract_chunk_structured_advanced(
            dict(row),
            cumulative_score,
            extract_ctx=extract_ctx,
            on_log=on_log,
        )
        all_facts.extend(facts)
        all_growth.extend(growth)
        all_scenes.extend(scene_rows)
        all_seed_items.extend(seed_items)
        all_payoff_items.extend(payoff_items)
        if idx % 80 == 0:
            await on_progress(min(95, int((idx / total) * 100)), "EXTRACT", f"已抽取 {idx}/{total} 分块")
    scene_fact_rows = _scene_rows_to_fact_rows(all_scenes)
    all_facts.extend(scene_fact_rows)
    await _insert_fact_rows(session, all_facts)
    await _insert_growth_rows(session, all_growth)
    await _insert_scene_rows(session, all_scenes)
    event_rows = _scene_rows_to_event_rows(all_scenes)
    seed_rows = _scene_rows_to_seed_rows(all_scenes)
    payoff_rows = _scene_rows_to_payoff_rows(all_scenes)
    await _insert_event_rows(session, event_rows)
    await _insert_seed_rows(session, seed_rows)
    await _insert_payoff_rows(session, payoff_rows)

    if pipeline_mode == "legacy":
        pair_rows = _pair_seed_payoff_items(seed_rows or all_seed_items, payoff_rows or all_payoff_items)
        pair_stats = {
            "mode": "legacy",
            "seed_total": len(seed_rows or all_seed_items),
            "payoff_total": len(payoff_rows or all_payoff_items),
            "recall_pairs": len(pair_rows),
            "judge_pairs": 0,
            "pair_total": len(pair_rows),
        }
    else:
        pair_rows, pair_stats = await _pair_seed_payoff_items_advanced(
            seed_items=seed_rows or all_seed_items,
            payoff_items=payoff_rows or all_payoff_items,
            extract_ctx=extract_ctx,
            on_log=on_log,
        )
    await _insert_pair_rows(session, pair_rows)
    if pipeline_mode == "legacy":
        embedding_rows = []
    else:
        embedding_rows = await _build_item_embedding_rows(
            splitbook_id=splitbook_id,
            extract_ctx=extract_ctx,
            seed_rows=seed_rows,
            payoff_rows=payoff_rows,
        )
    await _insert_item_embedding_rows(session, embedding_rows)
    qa_report = _build_structured_qa_report(all_scenes, pair_rows, all_facts)

    character_count = len({str(x.get("character_name") or "") for x in all_growth if str(x.get("character_name") or "").strip()})
    subtask_ok = 0
    subtask_fallback = 0
    candidate_judge_ok = 0
    for scene in all_scenes:
        qa = scene.get("qa_json") if isinstance(scene.get("qa_json"), dict) else {}
        if str(qa.get("pipeline") or "") == "candidate_judge":
            candidate_judge_ok += 1
        runner = qa.get("subtask_runner") if isinstance(qa.get("subtask_runner"), dict) else {}
        subtask_ok += int(runner.get("task_ok") or 0)
        subtask_fallback += int(runner.get("task_fallback") or 0)
    await update_splitbook_status(
        session,
        splitbook_id,
        stats={
            "fact_total": len(all_facts),
            "growth_rows": len(all_growth),
            "scene_total": len(all_scenes),
            "seed_total": len(seed_rows),
            "payoff_total": len(payoff_rows),
            "event_total": len(event_rows),
            "pair_total": len(pair_rows),
            "embedding_item_total": len(embedding_rows),
            "character_total": character_count,
            "structured_schema_version": SCENE_SCHEMA_VERSION,
            "structured_candidate_schema_version": SCENE_CANDIDATE_SCHEMA_VERSION,
            "structured_subtask_schema_version": SCENE_SUBTASK_SCHEMA_VERSION,
            "structured_prompt_version": SCENE_PROMPT_VERSION,
            "structured_pair_prompt_version": PAIR_PROMPT_VERSION,
            "structured_extract_provider": provider,
            "structured_extract_model": model,
            "structured_pipeline_mode": pipeline_mode,
            "structured_use_scene_judge": bool(use_scene_judge),
            "structured_pair_judge_enabled": bool(pair_judge_enabled),
            "structured_subtask_total": int(subtask_ok + subtask_fallback),
            "structured_subtask_ok": int(subtask_ok),
            "structured_subtask_fallback": int(subtask_fallback),
            "structured_candidate_judge_ok": int(candidate_judge_ok),
            "structured_pair_stats": pair_stats,
            "structured_qa": qa_report,
            "structured_extracted_at": _now_iso(),
        },
    )
    await on_log(
        "INFO",
        "EXTRACT",
        (
            f"facts={len(all_facts)} growth={len(all_growth)} scenes={len(all_scenes)} "
            f"pairs={len(pair_rows)} characters={character_count} "
            f"provider={provider} candidate_judge_ok={candidate_judge_ok} "
            f"subtask_ok={subtask_ok} subtask_fallback={subtask_fallback} embeddings={len(embedding_rows)} "
            f"pipeline_mode={pipeline_mode}"
        ),
    )
    await on_progress(100, "DONE", "结构化抽取完成")
    return {
        "splitbook_id": splitbook_id,
        "status": "done",
        "fact_total": len(all_facts),
        "growth_rows": len(all_growth),
        "scene_total": len(all_scenes),
        "pair_total": len(pair_rows),
        "event_total": len(event_rows),
        "seed_total": len(seed_rows),
        "payoff_total": len(payoff_rows),
        "embedding_item_total": len(embedding_rows),
        "qa": qa_report,
        "pair_stats": pair_stats,
        "character_total": character_count,
        "extract_provider": provider,
        "extract_model": model,
        "pipeline_mode": pipeline_mode,
        "use_scene_judge_effective": bool(use_scene_judge),
        "pair_judge_enabled": bool(pair_judge_enabled),
        "candidate_judge_ok": int(candidate_judge_ok),
        "subtask_ok": int(subtask_ok),
        "subtask_fallback": int(subtask_fallback),
    }


async def run_splitbook_build_templates_job(session: AsyncSession, payload: dict[str, Any], on_progress, on_log) -> dict[str, Any]:
    splitbook_id = str(payload.get("splitbook_id") or "")
    mode = str(payload.get("mode") or "merge")
    if not splitbook_id:
        raise RuntimeError("SPLITBOOK_ID_REQUIRED")
    await on_progress(15, "AGGREGATE", "聚合结构账本并生成模板")
    fact_rows = (
        await session.execute(
            text(
                """
                SELECT fact_type, COUNT(*) AS n
                FROM splitbook_fact
                WHERE splitbook_id=:sid
                GROUP BY fact_type
                """
            ),
            {"sid": splitbook_id},
        )
    ).mappings().all()
    counts = {str(r["fact_type"]): int(r["n"]) for r in fact_rows}
    assets = [
        ("mechanic", "冲突升级模板", "围绕主冲突分三层升级，层层加压，并在章节尾留钩。", ["splitbook", "conflict", "template"]),
        ("plot", "伏笔回收模板", "每 2~4 章投放一条伏笔，在关键节点触发回收与反转。", ["splitbook", "foreshadow", "payoff"]),
        ("character", "角色成长模板", "以压力→代价→收获为主轴推进角色成长曲线。", ["splitbook", "growth", "ledger"]),
    ]
    created = 0
    for asset_type, name, desc, tags in assets:
        await session.execute(
            text(
                """
                INSERT INTO template_asset(asset_type, name, description, tags, source_splitbook_id, source_span)
                VALUES (:asset_type, :name, :desc, CAST(:tags AS text[]), :sid, CAST(:span AS jsonb))
                """
            ),
            {
                "asset_type": asset_type,
                "name": name,
                "desc": desc,
                "tags": tags,
                "sid": splitbook_id,
                "span": json.dumps({"mode": mode, "fact_counts": counts}),
            },
        )
        created += 1
    await session.commit()
    await on_log("INFO", "AGGREGATE", f"templates_created={created} counts={counts}")
    await on_progress(100, "DONE", "模板资产已写入")
    return {"splitbook_id": splitbook_id, "templates_created": created, "mode": mode, "fact_counts": counts}


async def run_splitbook_build_profile_job(session: AsyncSession, payload: dict[str, Any], on_progress, on_log) -> dict[str, Any]:
    splitbook_id = str(payload.get("splitbook_id") or "")
    name = str(payload.get("name") or f"splitbook-profile-{splitbook_id[:8]}")
    mode = str(payload.get("mode") or "create")
    if not splitbook_id:
        raise RuntimeError("SPLITBOOK_ID_REQUIRED")
    await on_progress(25, "AGGREGATE", "汇总人物成长与节奏特征")
    ledger_rows = (
        await session.execute(
            text(
                """
                SELECT character_name, COUNT(*) AS n, MAX(growth_stage) AS growth_stage
                FROM splitbook_growth_ledger
                WHERE splitbook_id=:sid
                GROUP BY character_name
                ORDER BY n DESC
                LIMIT 12
                """
            ),
            {"sid": splitbook_id},
        )
    ).mappings().all()
    key_characters = [str(r["character_name"]) for r in ledger_rows]
    features = {
        "avg_sentence_len": "mix",
        "dialogue_ratio": 0.32,
        "source_splitbook_id": splitbook_id,
        "key_characters": key_characters,
        "growth_focus_character": key_characters[:5],
    }
    dos = ["维持角色成长链路：压力→代价→收获", "在章节尾保留推进钩子", "每章至少一个明确冲突目标"]
    donts = ["设定前后冲突", "无代价成长", "信息堆砌且无推进"]
    await on_log("INFO", "AGGREGATE", f"mode={mode} name={name} key_characters={len(key_characters)}")
    row = await create_profile(session, name=name, note=f"from_splitbook:{splitbook_id}", features=features, dos=dos, donts=donts)
    await on_progress(100, "DONE", "风格画像已生成")
    return {"splitbook_id": splitbook_id, "profile_id": str(row["profile_id"]), "mode": mode}


async def _load_splitbook_writeback_chapters(
    session: AsyncSession,
    splitbook_id: str,
    *,
    chapter_nos: list[int],
    max_chapters: int,
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            text(
                """
                SELECT
                  chapter_no,
                  COALESCE(NULLIF(MAX(chapter_title), ''), CONCAT('第', chapter_no, '章')) AS chapter_title,
                  STRING_AGG(text, E'\n\n' ORDER BY chunk_no) AS content,
                  COUNT(*)::int AS chunk_count
                FROM splitbook_chunk
                WHERE splitbook_id=:sid
                  AND chapter_no IS NOT NULL
                GROUP BY chapter_no
                ORDER BY chapter_no
                """
            ),
            {"sid": splitbook_id},
        )
    ).mappings().all()
    wanted = set(chapter_nos)
    out: list[dict[str, Any]] = []
    for row in rows:
        chapter_no = int(row.get("chapter_no") or 0)
        if chapter_no <= 0:
            continue
        if wanted and chapter_no not in wanted:
            continue
        content = str(row.get("content") or "").strip()
        if not content:
            continue
        out.append(
            {
                "chapter_no": chapter_no,
                "chapter_title": str(row.get("chapter_title") or f"第{chapter_no}章"),
                "content": content,
                "chunk_count": int(row.get("chunk_count") or 0),
            }
        )
        if len(out) >= max_chapters:
            break
    return out


async def run_splitbook_writeback_batch_job(session: AsyncSession, payload: dict[str, Any], on_progress, on_log) -> dict[str, Any]:
    splitbook_id = str(payload.get("splitbook_id") or "")
    if not splitbook_id:
        raise RuntimeError("SPLITBOOK_ID_REQUIRED")
    mode = str(payload.get("mode") or "preview").strip().lower()
    if mode not in {"preview", "confirm"}:
        mode = "preview"
    force = _coerce_bool(payload.get("force"), default=False)
    stop_on_error = _coerce_bool(payload.get("stop_on_error"), default=False)
    max_chapters = _clamp_int(payload.get("max_chapters"), default=1200, low=1, high=5000)
    chapter_nos = _normalize_chapter_nos(payload.get("chapter_nos"), max_items=max_chapters)
    preview_token_input = str(payload.get("preview_token") or "").strip()

    await _ensure_splitbook_tables(session)
    splitbook = await get_splitbook(session, splitbook_id)
    if not splitbook:
        raise RuntimeError("SPLITBOOK_NOT_FOUND")

    await on_progress(8, "LOAD", "读取章节聚合内容")
    chapters = await _load_splitbook_writeback_chapters(
        session,
        splitbook_id,
        chapter_nos=chapter_nos,
        max_chapters=max_chapters,
    )
    if not chapters:
        raise RuntimeError("SPLITBOOK_CHAPTERS_EMPTY")

    stats = splitbook.get("stats") if isinstance(splitbook.get("stats"), dict) else {}
    hash_map_raw = stats.get("writeback_chapter_hashes")
    hash_map_old: dict[str, str] = {}
    if isinstance(hash_map_raw, dict):
        for key, value in hash_map_raw.items():
            key_text = str(key).strip()
            value_text = str(value).strip()
            if key_text and value_text:
                hash_map_old[key_text] = value_text

    chapter_hash_map: dict[str, str] = {}
    changed_rows: list[dict[str, Any]] = []
    unchanged_chapter_nos: list[int] = []
    for row in chapters:
        chapter_no = int(row["chapter_no"])
        chapter_key = str(chapter_no)
        content_hash = _hash_writeback_content(str(row["content"]))
        chapter_hash_map[chapter_key] = content_hash
        previous_hash = hash_map_old.get(chapter_key, "")
        if force or previous_hash != content_hash:
            changed_rows.append(
                {
                    "chapter_no": chapter_no,
                    "chapter_title": str(row["chapter_title"] or f"第{chapter_no}章"),
                    "chunk_count": int(row.get("chunk_count") or 0),
                    "hash": content_hash,
                    "hash_prev": previous_hash,
                    "reason": "force" if force else ("new" if not previous_hash else "changed"),
                }
            )
        else:
            unchanged_chapter_nos.append(chapter_no)

    preview_seed = {
        "splitbook_id": splitbook_id,
        "chapter_hash_map": chapter_hash_map,
        "chapter_nos": [int(row["chapter_no"]) for row in chapters],
    }
    preview_token = hashlib.sha1(json.dumps(preview_seed, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:24]
    changed_chapter_nos = [int(row["chapter_no"]) for row in changed_rows]
    requested_total = len(chapters)
    changed_total = len(changed_rows)
    unchanged_total = len(unchanged_chapter_nos)
    max_chunk_count = max([int(row.get("chunk_count") or 0) for row in chapters] + [0])
    single_chapter_mode = requested_total <= 1
    single_chapter_warning = bool(single_chapter_mode and max_chunk_count >= 128)

    if mode == "preview":
        await update_splitbook_status(
            session,
            splitbook_id,
            stats={
                "writeback_last_preview_at": _now_iso(),
                "writeback_last_preview_token": preview_token,
                "writeback_pending_total": changed_total,
                "writeback_pending_chapter_nos": changed_chapter_nos,
                "writeback_pending_force": bool(force),
                "writeback_detected_chapter_total": requested_total,
                "writeback_single_chapter_warning": single_chapter_warning,
            },
        )
        await on_log(
            "INFO",
            "PREVIEW",
            (
                f"requested_total={requested_total} changed_total={changed_total} unchanged_total={unchanged_total} "
                f"max_chunk_count={max_chunk_count} single_chapter_warning={single_chapter_warning}"
            ),
        )
        await on_progress(100, "DONE", "批量回写预览完成")
        return {
            "splitbook_id": splitbook_id,
            "mode": "preview",
            "requested_total": requested_total,
            "changed_total": changed_total,
            "unchanged_total": unchanged_total,
            "chapter_nos_requested": chapter_nos,
            "chapter_nos_changed": changed_chapter_nos,
            "preview_token": preview_token,
            "force": bool(force),
            "max_chunk_count": max_chunk_count,
            "single_chapter_mode": single_chapter_mode,
            "single_chapter_warning": single_chapter_warning,
            "rows": changed_rows,
        }

    if preview_token_input:
        expected_preview_token = str(stats.get("writeback_last_preview_token") or "")
        if not expected_preview_token or preview_token_input != expected_preview_token:
            raise RuntimeError("SPLITBOOK_WRITEBACK_PREVIEW_TOKEN_MISMATCH")
        if preview_token_input != preview_token:
            raise RuntimeError("SPLITBOOK_WRITEBACK_PREVIEW_TOKEN_MISMATCH")

    await on_progress(15, "WRITEBACK", f"开始批量回写，目标章节 {changed_total}")
    chapter_index = {int(row["chapter_no"]): row for row in chapters}
    writeback_results: list[dict[str, Any]] = []
    failed_rows: list[dict[str, Any]] = []
    hash_map_new = dict(hash_map_old)
    total_changed_safe = max(1, changed_total)

    for idx, chapter_no in enumerate(changed_chapter_nos, start=1):
        row = chapter_index.get(chapter_no) or {}
        chapter_title = str(row.get("chapter_title") or f"第{chapter_no}章")
        content = str(row.get("content") or "")
        pct = min(95, 15 + int(80 * idx / total_changed_safe))
        await on_progress(pct, "WRITEBACK", f"回写第 {chapter_no} 章")
        try:
            result = await writeback_splitbook_chapter(
                session,
                splitbook_id,
                {
                    "chapter_no": chapter_no,
                    "chapter_title": chapter_title,
                    "content": content,
                },
            )
            writeback_results.append(
                {
                    "chapter_no": chapter_no,
                    "facts_written": int(result.get("facts_written") or 0),
                    "growth_written": int(result.get("growth_written") or 0),
                }
            )
            hash_map_new[str(chapter_no)] = chapter_hash_map.get(str(chapter_no), "")
        except Exception as exc:
            failed_rows.append({"chapter_no": chapter_no, "error": str(exc)})
            await on_log("ERROR", "WRITEBACK", f"chapter_no={chapter_no} error={exc}")
            if stop_on_error:
                raise

    applied_chapter_nos = [int(row.get("chapter_no") or 0) for row in writeback_results if int(row.get("chapter_no") or 0) > 0]
    applied_chapter_set = set(applied_chapter_nos)
    pending_chapter_nos = [chapter_no for chapter_no in changed_chapter_nos if chapter_no not in applied_chapter_set]
    facts_written_total = sum(int(row.get("facts_written") or 0) for row in writeback_results)
    growth_written_total = sum(int(row.get("growth_written") or 0) for row in writeback_results)

    await update_splitbook_status(
        session,
        splitbook_id,
        stats={
            "writeback_updated_at": _now_iso(),
            "writeback_last_mode": "batch_confirm",
            "writeback_last_preview_token": preview_token,
            "writeback_chapter_hashes": hash_map_new,
            "writeback_last_confirm_total": len(writeback_results),
            "writeback_last_confirm_failed": len(failed_rows),
            "writeback_pending_total": len(pending_chapter_nos),
            "writeback_pending_chapter_nos": pending_chapter_nos,
            "writeback_last_facts_written_total": facts_written_total,
            "writeback_last_growth_written_total": growth_written_total,
            "writeback_single_chapter_warning": single_chapter_warning,
        },
    )
    await on_log(
        "INFO",
        "WRITEBACK",
        (
            f"requested_total={requested_total} changed_total={changed_total} "
            f"applied_total={len(writeback_results)} failed_total={len(failed_rows)} "
            f"facts_written_total={facts_written_total} growth_written_total={growth_written_total}"
        ),
    )
    await on_progress(100, "DONE", "批量回写完成")
    return {
        "splitbook_id": splitbook_id,
        "mode": "confirm",
        "requested_total": requested_total,
        "changed_total": changed_total,
        "unchanged_total": unchanged_total,
        "applied_total": len(writeback_results),
        "failed_total": len(failed_rows),
        "facts_written_total": facts_written_total,
        "growth_written_total": growth_written_total,
        "chapter_nos_requested": chapter_nos,
        "chapter_nos_changed": changed_chapter_nos,
        "chapter_nos_unchanged": unchanged_chapter_nos,
        "preview_token": preview_token,
        "force": bool(force),
        "stop_on_error": bool(stop_on_error),
        "max_chunk_count": max_chunk_count,
        "single_chapter_mode": single_chapter_mode,
        "single_chapter_warning": single_chapter_warning,
        "results": writeback_results,
        "failed": failed_rows,
    }


async def get_splitbook_ledger_view(session: AsyncSession, splitbook_id: str, *, view: str = "chapter", limit: int = 500) -> dict[str, Any]:
    await _ensure_splitbook_tables(session)
    limit = max(1, min(int(limit), 2000))
    if view == "character":
        rows = (
            await session.execute(
                text(
                    """
                    SELECT
                      character_name,
                      COUNT(*) AS chapter_hits,
                      MAX(growth_stage) AS latest_stage,
                      MAX(growth) AS latest_growth,
                      MAX(cost) AS latest_cost,
                      MAX(pressure) AS latest_pressure,
                      MAX(gain) AS latest_gain
                    FROM splitbook_growth_ledger
                    WHERE splitbook_id=:sid
                    GROUP BY character_name
                    ORDER BY chapter_hits DESC, character_name
                    LIMIT :limit
                    """
                ),
                {"sid": splitbook_id, "limit": limit},
            )
        ).mappings().all()
    else:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT chapter_no, chapter_title, character_name, growth_stage, growth, cost, pressure, gain, evidence
                    FROM splitbook_growth_ledger
                    WHERE splitbook_id=:sid
                    ORDER BY COALESCE(chapter_no, 999999), character_name
                    LIMIT :limit
                    """
                ),
                {"sid": splitbook_id, "limit": limit},
            )
        ).mappings().all()
        if not rows:
            fact_rows = (
                await session.execute(
                    text(
                        """
                        SELECT
                          COALESCE(chapter_no, 1) AS chapter_no,
                          COALESCE(NULLIF(chapter_title, ''), CONCAT('第', COALESCE(chapter_no, 1), '章')) AS chapter_title,
                          MIN(statement) AS sample_statement
                        FROM splitbook_fact
                        WHERE splitbook_id=:sid
                        GROUP BY COALESCE(chapter_no, 1), COALESCE(NULLIF(chapter_title, ''), CONCAT('第', COALESCE(chapter_no, 1), '章'))
                        ORDER BY COALESCE(chapter_no, 1)
                        LIMIT :limit
                        """
                    ),
                    {"sid": splitbook_id, "limit": limit},
                )
            ).mappings().all()
            rows = [
                {
                    "chapter_no": row.get("chapter_no"),
                    "chapter_title": row.get("chapter_title"),
                    "character_name": "主角（待识别）",
                    "growth_stage": "待补全",
                    "growth": str(row.get("sample_statement") or "")[:220],
                    "cost": "",
                    "pressure": "",
                    "gain": "",
                    "evidence": str(row.get("sample_statement") or "")[:220],
                }
                for row in fact_rows
            ]
        if not rows:
            chunk_rows = (
                await session.execute(
                    text(
                        """
                        SELECT
                          COALESCE(chapter_no, 1) AS chapter_no,
                          COALESCE(NULLIF(chapter_title, ''), CONCAT('第', COALESCE(chapter_no, 1), '章')) AS chapter_title,
                          MIN(SUBSTRING(text FROM 1 FOR 220)) AS sample_text
                        FROM splitbook_chunk
                        WHERE splitbook_id=:sid
                        GROUP BY COALESCE(chapter_no, 1), COALESCE(NULLIF(chapter_title, ''), CONCAT('第', COALESCE(chapter_no, 1), '章'))
                        ORDER BY COALESCE(chapter_no, 1)
                        LIMIT :limit
                        """
                    ),
                    {"sid": splitbook_id, "limit": limit},
                )
            ).mappings().all()
            rows = [
                {
                    "chapter_no": row.get("chapter_no"),
                    "chapter_title": row.get("chapter_title"),
                    "character_name": "主角（待识别）",
                    "growth_stage": "待抽取",
                    "growth": str(row.get("sample_text") or "")[:220],
                    "cost": "",
                    "pressure": "",
                    "gain": "",
                    "evidence": str(row.get("sample_text") or "")[:220],
                }
                for row in chunk_rows
            ]
    summary_row = (
        await session.execute(
            text(
                """
                SELECT
                  (SELECT COUNT(*) FROM splitbook_growth_ledger WHERE splitbook_id=:sid) AS growth_rows,
                  (SELECT COUNT(*) FROM splitbook_fact WHERE splitbook_id=:sid) AS fact_rows,
                  (SELECT COUNT(DISTINCT character_name) FROM splitbook_growth_ledger WHERE splitbook_id=:sid) AS character_rows
                """
            ),
            {"sid": splitbook_id},
        )
    ).mappings().first()
    return {
        "splitbook_id": splitbook_id,
        "view": view,
        "rows": [dict(r) for r in rows],
        "summary": dict(summary_row or {}),
        "generated_at": _now_iso(),
    }


async def build_splitbook_outline(session: AsyncSession, splitbook_id: str) -> dict[str, Any]:
    await _ensure_splitbook_tables(session)
    scene_rows = (
        await session.execute(
            text(
                """
                SELECT chapter_no, chapter_title, scene_no, summary, time_raw, location_norm,
                       conflict_json, foreshadow_json, payoff_json, events_json, worldbuilding_json
                FROM splitbook_scene
                WHERE splitbook_id=:sid
                ORDER BY COALESCE(chapter_no, 999999), scene_no
                """
            ),
            {"sid": splitbook_id},
        )
    ).mappings().all()

    grouped: dict[int, dict[str, Any]] = {}
    if scene_rows:
        for row in scene_rows:
            chapter_no = int(row.get("chapter_no") or 0)
            data = grouped.setdefault(
                chapter_no,
                {
                    "chapter_no": chapter_no,
                    "chapter_title": str(row.get("chapter_title") or f"第{chapter_no}章"),
                    "scene_rows": [],
                },
            )
            data["scene_rows"].append(dict(row))
    else:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT chapter_no, chapter_title, fact_type, statement
                    FROM splitbook_fact
                    WHERE splitbook_id=:sid
                    ORDER BY COALESCE(chapter_no, 999999), created_at
                    """
                ),
                {"sid": splitbook_id},
            )
        ).mappings().all()
        for row in rows:
            chapter_no = int(row.get("chapter_no") or 0)
            data = grouped.setdefault(
                chapter_no,
                {
                    "chapter_no": chapter_no,
                    "chapter_title": str(row.get("chapter_title") or f"第{chapter_no}章"),
                    "facts": defaultdict(list),
                },
            )
            data["facts"][str(row.get("fact_type") or "")].append(str(row.get("statement") or ""))
        if not grouped:
            chunk_rows = (
                await session.execute(
                    text(
                        """
                        SELECT
                          COALESCE(chapter_no, 1) AS chapter_no,
                          COALESCE(NULLIF(chapter_title, ''), CONCAT('第', COALESCE(chapter_no, 1), '章')) AS chapter_title,
                          MIN(SUBSTRING(text FROM 1 FOR 180)) AS sample_text
                        FROM splitbook_chunk
                        WHERE splitbook_id=:sid
                        GROUP BY COALESCE(chapter_no, 1), COALESCE(NULLIF(chapter_title, ''), CONCAT('第', COALESCE(chapter_no, 1), '章'))
                        ORDER BY COALESCE(chapter_no, 1)
                        """
                    ),
                    {"sid": splitbook_id},
                )
            ).mappings().all()
            for row in chunk_rows:
                chapter_no = int(row.get("chapter_no") or 0)
                data = grouped.setdefault(
                    chapter_no,
                    {
                        "chapter_no": chapter_no,
                        "chapter_title": str(row.get("chapter_title") or f"第{chapter_no}章"),
                        "facts": defaultdict(list),
                    },
                )
                sample = str(row.get("sample_text") or "").strip()
                if sample:
                    data["facts"]["conflict"].append(sample[:160])
                    data["facts"]["timeline"].append("待补全（来自分块回退）")

    pair_rows = (
        await session.execute(
            text(
                """
                SELECT seed_chapter_no, payoff_chapter_no, relation, confidence
                FROM splitbook_pair
                WHERE splitbook_id=:sid
                """
            ),
            {"sid": splitbook_id},
        )
    ).mappings().all()
    seed_pair_count: dict[int, int] = defaultdict(int)
    payoff_pair_count: dict[int, int] = defaultdict(int)
    for row in pair_rows:
        seed_ch = int(row.get("seed_chapter_no") or 0)
        pay_ch = int(row.get("payoff_chapter_no") or 0)
        if seed_ch > 0:
            seed_pair_count[seed_ch] += 1
        if pay_ch > 0:
            payoff_pair_count[pay_ch] += 1

    chapters: list[dict[str, Any]] = []
    for chapter_no in sorted(grouped.keys()):
        data = grouped[chapter_no]
        if isinstance(data.get("scene_rows"), list):
            scene_items = data.get("scene_rows") if isinstance(data.get("scene_rows"), list) else []
            first_scene = scene_items[0] if scene_items else {}
            conflict_text = ""
            timeline_text = ""
            world_text = ""
            foreshadow_count = 0
            payoff_count = 0
            conflict_beats: list[str] = []
            foreshadow_beats: list[str] = []
            payoff_beats: list[str] = []
            for scene in scene_items:
                conflict = scene.get("conflict_json") if isinstance(scene.get("conflict_json"), dict) else {}
                world_items = scene.get("worldbuilding_json") if isinstance(scene.get("worldbuilding_json"), list) else []
                seed_items = scene.get("foreshadow_json") if isinstance(scene.get("foreshadow_json"), list) else []
                pay_items = scene.get("payoff_json") if isinstance(scene.get("payoff_json"), list) else []
                if not conflict_text:
                    conflict_text = str(conflict.get("turning_point") or conflict.get("stakes") or scene.get("summary") or "")[:180]
                if not timeline_text:
                    timeline_text = str(scene.get("time_raw") or "")[:120]
                if not world_text and world_items:
                    world_text = str((world_items[0] if isinstance(world_items[0], dict) else {}).get("item") or "")[:160]
                foreshadow_count += len(seed_items)
                payoff_count += len(pay_items)
                conflict_beats.extend([str(scene.get("summary") or "")[:120]] if str(scene.get("summary") or "").strip() else [])
                foreshadow_beats.extend(
                    [str((x if isinstance(x, dict) else {}).get("seed") or "")[:120] for x in seed_items[:2] if str((x if isinstance(x, dict) else {}).get("seed") or "").strip()]
                )
                payoff_beats.extend(
                    [str((x if isinstance(x, dict) else {}).get("event") or "")[:120] for x in pay_items[:2] if str((x if isinstance(x, dict) else {}).get("event") or "").strip()]
                )
            summary = {
                "conflict": conflict_text,
                "timeline": timeline_text,
                "world": world_text,
                "foreshadow_count": foreshadow_count,
                "payoff_count": payoff_count,
                "scene_count": len(scene_items),
                "pair_seed_count": int(seed_pair_count.get(chapter_no, 0)),
                "pair_payoff_count": int(payoff_pair_count.get(chapter_no, 0)),
                "tension_peak": max(
                    [
                        _clamp_int(
                            ((x.get("conflict_json") if isinstance(x.get("conflict_json"), dict) else {}).get("tension_score")),
                            default=0,
                            low=0,
                            high=10,
                        )
                        for x in scene_items
                    ]
                    + [
                        _clamp_int(
                            ((evt if isinstance(evt, dict) else {}).get("tension_score")),
                            default=0,
                            low=0,
                            high=10,
                        )
                        for x in scene_items
                        for evt in ((x.get("events_json") if isinstance(x.get("events_json"), list) else [])[:8])
                    ]
                    + [0]
                ),
            }
            chapters.append(
                {
                    "chapter_no": chapter_no,
                    "chapter_title": str(data.get("chapter_title") or first_scene.get("chapter_title") or f"第{chapter_no}章"),
                    "summary": summary,
                    "beats": {
                        "conflict": conflict_beats[:3],
                        "foreshadow": foreshadow_beats[:3],
                        "payoff": payoff_beats[:3],
                    },
                }
            )
        else:
            facts = data.get("facts") if isinstance(data.get("facts"), dict) else {}
            summary = {
                "conflict": (facts.get("conflict") or [""])[0][:180],
                "timeline": (facts.get("timeline") or [""])[0][:180],
                "world": (facts.get("world") or [""])[0][:180],
                "foreshadow_count": len(facts.get("foreshadow") or []),
                "payoff_count": len(facts.get("payoff") or []),
                "pair_seed_count": int(seed_pair_count.get(chapter_no, 0)),
                "pair_payoff_count": int(payoff_pair_count.get(chapter_no, 0)),
                "tension_peak": 6 if (facts.get("conflict") or []) else 3,
            }
            chapters.append(
                {
                    "chapter_no": chapter_no,
                    "chapter_title": data["chapter_title"],
                    "summary": summary,
                    "beats": {
                        "conflict": (facts.get("conflict") or [])[:3],
                        "foreshadow": (facts.get("foreshadow") or [])[:3],
                        "payoff": (facts.get("payoff") or [])[:3],
                    },
                }
            )
    sorted_chapters = sorted(chapters, key=lambda x: int(x.get("chapter_no") or 0))
    volumes: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    volume_no = 1
    for ch in sorted_chapters:
        current.append(ch)
        summary = ch.get("summary") if isinstance(ch.get("summary"), dict) else {}
        tension_peak = _clamp_int(summary.get("tension_peak"), default=0, low=0, high=10)
        payoff_hits = int(summary.get("pair_payoff_count") or 0)
        should_cut = False
        if len(current) >= 12:
            should_cut = True
        elif len(current) >= 3 and payoff_hits >= 2 and tension_peak <= 5:
            should_cut = True
        if should_cut:
            start_no = int((current[0].get("chapter_no") or 0))
            end_no = int((current[-1].get("chapter_no") or 0))
            avg_tension = round(
                sum(_clamp_int(((x.get("summary") if isinstance(x.get("summary"), dict) else {}).get("tension_peak")), default=0, low=0, high=10) for x in current)
                / max(1, len(current)),
                3,
            )
            key_conflicts = [
                str((x.get("summary") if isinstance(x.get("summary"), dict) else {}).get("conflict") or "")[:120]
                for x in current
                if str((x.get("summary") if isinstance(x.get("summary"), dict) else {}).get("conflict") or "").strip()
            ][:5]
            volumes.append(
                {
                    "volume_no": volume_no,
                    "start_chapter_no": start_no,
                    "end_chapter_no": end_no,
                    "chapter_count": len(current),
                    "avg_tension": avg_tension,
                    "key_conflicts": key_conflicts,
                }
            )
            volume_no += 1
            current = []
    if current:
        start_no = int((current[0].get("chapter_no") or 0))
        end_no = int((current[-1].get("chapter_no") or 0))
        avg_tension = round(
            sum(_clamp_int(((x.get("summary") if isinstance(x.get("summary"), dict) else {}).get("tension_peak")), default=0, low=0, high=10) for x in current)
            / max(1, len(current)),
            3,
        )
        key_conflicts = [
            str((x.get("summary") if isinstance(x.get("summary"), dict) else {}).get("conflict") or "")[:120]
            for x in current
            if str((x.get("summary") if isinstance(x.get("summary"), dict) else {}).get("conflict") or "").strip()
        ][:5]
        volumes.append(
            {
                "volume_no": volume_no,
                "start_chapter_no": start_no,
                "end_chapter_no": end_no,
                "chapter_count": len(current),
                "avg_tension": avg_tension,
                "key_conflicts": key_conflicts,
            }
        )

    core_rules = [str((x.get("summary") if isinstance(x.get("summary"), dict) else {}).get("world") or "")[:140] for x in sorted_chapters if str((x.get("summary") if isinstance(x.get("summary"), dict) else {}).get("world") or "").strip()][:10]
    core_conflicts = [str((x.get("summary") if isinstance(x.get("summary"), dict) else {}).get("conflict") or "")[:140] for x in sorted_chapters if str((x.get("summary") if isinstance(x.get("summary"), dict) else {}).get("conflict") or "").strip()][:10]
    book_outline = {
        "main_conflict_spine": core_conflicts[:5],
        "growth_curve_hint": "沿 tension 峰谷推进：高压章节后插入局部结算与新钩子。",
        "core_world_rules": core_rules[:6],
        "foreshadow_pair_total": len(pair_rows),
    }

    return {
        "splitbook_id": splitbook_id,
        "chapters": chapters,
        "volumes": volumes,
        "book_outline": book_outline,
        "chapter_total": len(chapters),
        "scene_total": len(scene_rows),
        "pair_total": len(pair_rows),
        "generated_at": _now_iso(),
    }


async def build_splitbook_chapter_pack(session: AsyncSession, splitbook_id: str, chapter_no: int) -> dict[str, Any]:
    await _ensure_splitbook_tables(session)
    requested_chapter_no = int(chapter_no)
    actual_chapter_no = requested_chapter_no

    available_rows = (
        await session.execute(
            text(
                """
                SELECT chapter_no, COUNT(*) AS n
                FROM splitbook_fact
                WHERE splitbook_id=:sid
                GROUP BY chapter_no
                ORDER BY n DESC, chapter_no
                LIMIT 200
                """
            ),
            {"sid": splitbook_id},
        )
    ).mappings().all()
    available_chapter_nos = sorted({int(row.get("chapter_no") or 1) for row in available_rows})
    if not available_chapter_nos:
        growth_rows = (
            await session.execute(
                text(
                    """
                    SELECT chapter_no, COUNT(*) AS n
                    FROM splitbook_growth_ledger
                    WHERE splitbook_id=:sid
                    GROUP BY chapter_no
                    ORDER BY n DESC, chapter_no
                    LIMIT 200
                    """
                ),
                {"sid": splitbook_id},
            )
        ).mappings().all()
        available_chapter_nos = sorted({int(row.get("chapter_no") or 1) for row in growth_rows})
    if not available_chapter_nos:
        scene_rows = (
            await session.execute(
                text(
                    """
                    SELECT chapter_no, COUNT(*) AS n
                    FROM splitbook_scene
                    WHERE splitbook_id=:sid
                    GROUP BY chapter_no
                    ORDER BY n DESC, chapter_no
                    LIMIT 200
                    """
                ),
                {"sid": splitbook_id},
            )
        ).mappings().all()
        available_chapter_nos = sorted({int(row.get("chapter_no") or 1) for row in scene_rows})
    if not available_chapter_nos:
        chunk_rows = (
            await session.execute(
                text(
                    """
                    SELECT chapter_no, COUNT(*) AS n
                    FROM splitbook_chunk
                    WHERE splitbook_id=:sid
                    GROUP BY chapter_no
                    ORDER BY n DESC, chapter_no
                    LIMIT 200
                    """
                ),
                {"sid": splitbook_id},
            )
        ).mappings().all()
        available_chapter_nos = sorted({int(row.get("chapter_no") or 1) for row in chunk_rows})

    facts = (
        await session.execute(
            text(
                """
                SELECT fact_type, entity, statement, chapter_title
                FROM splitbook_fact
                WHERE splitbook_id=:sid AND chapter_no=:chapter_no
                ORDER BY created_at
                """
            ),
            {"sid": splitbook_id, "chapter_no": actual_chapter_no},
        )
    ).mappings().all()
    growth = (
        await session.execute(
            text(
                """
                SELECT character_name, growth_stage, growth, cost, pressure, gain, evidence
                FROM splitbook_growth_ledger
                WHERE splitbook_id=:sid AND chapter_no=:chapter_no
                ORDER BY character_name
                """
            ),
            {"sid": splitbook_id, "chapter_no": actual_chapter_no},
        )
    ).mappings().all()

    scene_view_rows = (
        await session.execute(
            text(
                """
                SELECT scene_key, scene_no, summary, time_raw, location_norm, conflict_json, foreshadow_json, payoff_json
                FROM splitbook_scene
                WHERE splitbook_id=:sid AND chapter_no=:chapter_no
                ORDER BY scene_no
                """
            ),
            {"sid": splitbook_id, "chapter_no": actual_chapter_no},
        )
    ).mappings().all()
    event_rows = (
        await session.execute(
            text(
                """
                SELECT scene_key, scene_no, beat, what, cause, result, tension_score, importance, confidence
                FROM splitbook_event
                WHERE splitbook_id=:sid AND chapter_no=:chapter_no
                ORDER BY scene_no, created_at
                LIMIT 64
                """
            ),
            {"sid": splitbook_id, "chapter_no": actual_chapter_no},
        )
    ).mappings().all()

    if not facts and not growth and not scene_view_rows and not event_rows and available_chapter_nos:
        actual_chapter_no = available_chapter_nos[0]
        facts = (
            await session.execute(
                text(
                    """
                    SELECT fact_type, entity, statement, chapter_title
                    FROM splitbook_fact
                    WHERE splitbook_id=:sid AND chapter_no=:chapter_no
                    ORDER BY created_at
                    """
                ),
                {"sid": splitbook_id, "chapter_no": actual_chapter_no},
            )
        ).mappings().all()
        event_rows = (
            await session.execute(
                text(
                    """
                    SELECT scene_key, scene_no, beat, what, cause, result, tension_score, importance, confidence
                    FROM splitbook_event
                    WHERE splitbook_id=:sid AND chapter_no=:chapter_no
                    ORDER BY scene_no, created_at
                    LIMIT 64
                    """
                ),
                {"sid": splitbook_id, "chapter_no": actual_chapter_no},
            )
        ).mappings().all()
        growth = (
            await session.execute(
                text(
                    """
                    SELECT character_name, growth_stage, growth, cost, pressure, gain, evidence
                    FROM splitbook_growth_ledger
                    WHERE splitbook_id=:sid AND chapter_no=:chapter_no
                    ORDER BY character_name
                    """
                ),
                {"sid": splitbook_id, "chapter_no": actual_chapter_no},
            )
        ).mappings().all()
        scene_view_rows = (
            await session.execute(
                text(
                    """
                    SELECT scene_key, scene_no, summary, time_raw, location_norm, conflict_json, foreshadow_json, payoff_json
                    FROM splitbook_scene
                    WHERE splitbook_id=:sid AND chapter_no=:chapter_no
                    ORDER BY scene_no
                    """
                ),
                {"sid": splitbook_id, "chapter_no": actual_chapter_no},
            )
        ).mappings().all()

    chapter_title = str((facts[0]["chapter_title"] if facts else "") or f"第{actual_chapter_no}章")
    world_rules = [str(x["statement"]) for x in facts if str(x["fact_type"]) == "world"][:8]
    timeline = [str(x["statement"]) for x in facts if str(x["fact_type"]) == "timeline"][:8]
    conflicts = [str(x["statement"]) for x in facts if str(x["fact_type"]) == "conflict"][:8]
    foreshadow = [str(x["statement"]) for x in facts if str(x["fact_type"]) == "foreshadow"][:8]
    payoff = [str(x["statement"]) for x in facts if str(x["fact_type"]) == "payoff"][:8]
    scene_summaries: list[dict[str, Any]] = []
    for row in scene_view_rows[:12]:
        conflict = row.get("conflict_json") if isinstance(row.get("conflict_json"), dict) else {}
        seeds = row.get("foreshadow_json") if isinstance(row.get("foreshadow_json"), list) else []
        pays = row.get("payoff_json") if isinstance(row.get("payoff_json"), list) else []
        scene_summaries.append(
            {
                "scene_key": str(row.get("scene_key") or ""),
                "scene_no": int(row.get("scene_no") or 0),
                "summary": str(row.get("summary") or "")[:180],
                "time": str(row.get("time_raw") or "")[:60],
                "location": str(row.get("location_norm") or "")[:80],
                "conflict": str(conflict.get("turning_point") or conflict.get("stakes") or "")[:140],
                "foreshadow_count": len(seeds),
                "payoff_count": len(pays),
            }
        )
    if scene_summaries:
        for row in scene_summaries:
            if row.get("conflict") and len(conflicts) < 8:
                conflicts.append(str(row.get("conflict") or ""))
            if row.get("time") and len(timeline) < 8:
                timeline.append(str(row.get("time") or ""))

    pair_rows = (
        await session.execute(
            text(
                """
                SELECT seed_scene_key, payoff_scene_key, seed_text, payoff_text, relation, confidence, score
                FROM splitbook_pair
                WHERE splitbook_id=:sid
                  AND (seed_chapter_no=:chapter_no OR payoff_chapter_no=:chapter_no)
                ORDER BY confidence DESC, score DESC, created_at DESC
                LIMIT 16
                """
            ),
            {"sid": splitbook_id, "chapter_no": actual_chapter_no},
        )
    ).mappings().all()
    pair_links = [
        {
            "seed_scene_key": str(row.get("seed_scene_key") or ""),
            "payoff_scene_key": str(row.get("payoff_scene_key") or ""),
            "seed_text": str(row.get("seed_text") or "")[:160],
            "payoff_text": str(row.get("payoff_text") or "")[:160],
            "relation": str(row.get("relation") or ""),
            "confidence": round(float(row.get("confidence") or 0.0), 4),
            "score": round(float(row.get("score") or 0.0), 4),
            "direction": "seed" if str(row.get("seed_scene_key") or "").startswith(f"ch{actual_chapter_no:05d}_") else "payoff",
        }
        for row in pair_rows
    ]

    return {
        "splitbook_id": splitbook_id,
        "chapter_no": actual_chapter_no,
        "requested_chapter_no": requested_chapter_no,
        "fallback_used": actual_chapter_no != requested_chapter_no,
        "available_chapter_nos": available_chapter_nos,
        "chapter_title": chapter_title,
        "constraints": {"world_rules": world_rules, "timeline": timeline},
        "key_conflicts": conflicts,
        "foreshadow": foreshadow,
        "payoff": payoff,
        "growth_cards": [dict(x) for x in growth],
        "events": [dict(x) for x in event_rows],
        "scene_summaries": scene_summaries,
        "pair_links": pair_links,
        "style_hint": "按“压力→代价→收获”推进角色变化，避免照抄原句。",
        "generated_at": _now_iso(),
    }

async def writeback_splitbook_chapter(session: AsyncSession, splitbook_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    await _ensure_splitbook_tables(session)
    chapter_no = _clamp_int(payload.get("chapter_no"), default=1, low=1, high=999999)
    chapter_title = str(payload.get("chapter_title") or f"第{chapter_no}章")
    content = str(payload.get("content") or "").strip()
    if not content:
        raise RuntimeError("WRITEBACK_CONTENT_REQUIRED")
    await session.execute(
        text("DELETE FROM splitbook_fact WHERE splitbook_id=:sid AND chapter_no=:chapter_no AND COALESCE(extra->>'source','')='writeback'"),
        {"sid": splitbook_id, "chapter_no": chapter_no},
    )
    await session.execute(
        text("DELETE FROM splitbook_growth_ledger WHERE splitbook_id=:sid AND chapter_no=:chapter_no AND COALESCE(extra->>'source','')='writeback'"),
        {"sid": splitbook_id, "chapter_no": chapter_no},
    )
    await session.commit()
    pseudo_chunk = {
        "splitbook_id": splitbook_id,
        "chunk_id": None,
        "chapter_no": chapter_no,
        "chapter_title": chapter_title,
        "text": content,
    }
    facts, growth_rows = _extract_chunk_structured(pseudo_chunk, cumulative={})
    for row in facts:
        row["extra"] = {"source": "writeback", "origin": "chapter_writeback"}
    for row in growth_rows:
        row["extra"] = {"source": "writeback", "origin": "chapter_writeback"}
    await _insert_fact_rows(session, facts)
    await _insert_growth_rows(session, growth_rows)
    await update_splitbook_status(session, splitbook_id, stats={"writeback_updated_at": _now_iso(), "writeback_chapter_no": chapter_no})
    return {"splitbook_id": splitbook_id, "chapter_no": chapter_no, "facts_written": len(facts), "growth_written": len(growth_rows)}


async def splitbook_chapter_health_report(session: AsyncSession, splitbook_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    await _ensure_splitbook_tables(session)
    chapter_no_raw = payload.get("chapter_no")
    chapter_no = int(chapter_no_raw) if chapter_no_raw is not None else None
    content = str(payload.get("content") or "")
    filters = " AND chapter_no=:chapter_no" if chapter_no is not None else ""
    params: dict[str, Any] = {"sid": splitbook_id}
    if chapter_no is not None:
        params["chapter_no"] = chapter_no
    fact_rows = (
        await session.execute(
            text(f"SELECT fact_type, entity, statement FROM splitbook_fact WHERE splitbook_id=:sid{filters} ORDER BY created_at"),
            params,
        )
    ).mappings().all()
    growth_rows = (
        await session.execute(
            text(f"SELECT character_name, growth_stage, pressure, cost, gain FROM splitbook_growth_ledger WHERE splitbook_id=:sid{filters} ORDER BY updated_at"),
            params,
        )
    ).mappings().all()

    issues: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    known_characters = {str(x["character_name"]) for x in growth_rows}
    if content.strip():
        names_in_text = {x for x in NAME_RE.findall(content) if 2 <= len(x) <= 4}
        new_names = sorted(x for x in names_in_text if x not in known_characters)
        if new_names:
            issues.append({"type": "character_consistency", "severity": "mid", "detail": f"发现未在账本登记的新角色：{', '.join(new_names[:8])}"})
    timeline_terms = [str(x["entity"] or "") for x in fact_rows if str(x["fact_type"]) == "timeline" and str(x["entity"] or "")]
    if "清晨" in timeline_terms and "深夜" in timeline_terms:
        issues.append({"type": "timeline_conflict", "severity": "mid", "detail": "同一章同时出现“清晨/深夜”，请确认是否跨场景切换。"})
    world_fact_count = sum(1 for x in fact_rows if str(x["fact_type"]) == "world")
    if world_fact_count == 0:
        issues.append({"type": "world_rule_gap", "severity": "low", "detail": "本章没有显式设定约束，可能导致设定一致性难检查。"})
    conflict_count = sum(1 for x in fact_rows if str(x["fact_type"]) == "conflict")
    if conflict_count == 0:
        issues.append({"type": "plot_gap", "severity": "mid", "detail": "本章未抽取到明显冲突，可能出现剧情断裂。"})

    checks.append({"name": "人物一致性", "status": "ok" if not any(x["type"] == "character_consistency" for x in issues) else "warn"})
    checks.append({"name": "时间线冲突", "status": "ok" if not any(x["type"] == "timeline_conflict" for x in issues) else "warn"})
    checks.append({"name": "设定约束", "status": "ok" if world_fact_count > 0 else "warn"})
    checks.append({"name": "剧情连续性", "status": "ok" if conflict_count > 0 else "warn"})

    score = 100
    for issue in issues:
        severity = str(issue.get("severity") or "")
        if severity == "high":
            score -= 25
        elif severity == "mid":
            score -= 15
        else:
            score -= 8
    score = max(0, min(100, score))
    return {
        "splitbook_id": splitbook_id,
        "chapter_no": chapter_no,
        "score": score,
        "checks": checks,
        "issues": issues,
        "fact_rows": len(fact_rows),
        "growth_rows": len(growth_rows),
        "generated_at": _now_iso(),
    }


async def splitbook_anti_copy_check(session: AsyncSession, splitbook_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    await _ensure_splitbook_tables(session)
    chapter_no_raw = payload.get("chapter_no")
    chapter_no = int(chapter_no_raw) if chapter_no_raw is not None and str(chapter_no_raw).strip() else None
    content = str(payload.get("content") or "").strip()
    if not content:
        raise RuntimeError("ANTI_COPY_CONTENT_REQUIRED")
    top_k = _clamp_int(payload.get("top_k"), default=160, low=20, high=800)
    ngram_size = _clamp_int(payload.get("ngram_size"), default=5, low=2, high=8)

    params: dict[str, Any] = {"sid": splitbook_id, "limit": top_k}
    if chapter_no is not None:
        params["chapter_no"] = chapter_no
        rows = (
            await session.execute(
                text(
                    """
                    SELECT chunk_id::text AS chunk_id, chapter_no, chapter_title, text, char_len
                    FROM splitbook_chunk
                    WHERE splitbook_id=:sid AND chapter_no=:chapter_no
                    ORDER BY chunk_no
                    LIMIT :limit
                    """
                ),
                params,
            )
        ).mappings().all()
    else:
        params["char_len"] = len(content)
        rows = (
            await session.execute(
                text(
                    """
                    SELECT chunk_id::text AS chunk_id, chapter_no, chapter_title, text, char_len
                    FROM splitbook_chunk
                    WHERE splitbook_id=:sid
                    ORDER BY ABS(char_len - :char_len), chunk_no
                    LIMIT :limit
                    """
                ),
                params,
            )
        ).mappings().all()

    if not rows:
        raise RuntimeError("SPLITBOOK_CHUNKS_EMPTY")

    content_slice = content[:24000]
    content_ngrams = _char_ngram_set(content_slice, n=ngram_size)
    if not content_ngrams:
        raise RuntimeError("ANTI_COPY_CONTENT_TOO_SHORT")

    hit_rows: list[dict[str, Any]] = []
    for row in rows:
        text_value = str(row.get("text") or "")[:24000]
        if not text_value:
            continue
        ref_ngrams = _char_ngram_set(text_value, n=ngram_size)
        if not ref_ngrams:
            continue
        inter = len(content_ngrams & ref_ngrams)
        union = len(content_ngrams | ref_ngrams) or 1
        overlap_ratio = round(inter / max(1, len(content_ngrams)), 4)
        jaccard = round(inter / union, 4)
        lcs_len = SequenceMatcher(None, content_slice, text_value).find_longest_match(0, len(content_slice), 0, len(text_value)).size
        lcs_ratio = round(lcs_len / max(1, len(content_slice)), 4)
        copy_index = round(max(overlap_ratio, lcs_ratio), 4)
        hit_rows.append(
            {
                "chunk_id": str(row.get("chunk_id") or ""),
                "chapter_no": row.get("chapter_no"),
                "chapter_title": str(row.get("chapter_title") or ""),
                "overlap_ratio": overlap_ratio,
                "jaccard": jaccard,
                "lcs_len": int(lcs_len),
                "lcs_ratio": lcs_ratio,
                "copy_index": copy_index,
            }
        )

    hit_rows.sort(key=lambda x: (float(x.get("copy_index") or 0.0), float(x.get("overlap_ratio") or 0.0)), reverse=True)
    top_hits = hit_rows[:8]
    max_overlap = max((float(x.get("overlap_ratio") or 0.0) for x in hit_rows), default=0.0)
    max_lcs_ratio = max((float(x.get("lcs_ratio") or 0.0) for x in hit_rows), default=0.0)
    top3 = top_hits[:3]
    avg_copy_index = round(sum(float(x.get("copy_index") or 0.0) for x in top3) / max(1, len(top3)), 4)
    risk_signal = max(max_overlap, max_lcs_ratio, avg_copy_index)
    anti_copy_score = int(max(0, min(100, round(100 - risk_signal * 100))))

    if risk_signal >= 0.35:
        risk_level = "high"
    elif risk_signal >= 0.2:
        risk_level = "medium"
    else:
        risk_level = "low"

    suggestions: list[str] = [
        "优先保留结构，不复用原句；将句子重写为本书角色口吻。",
        "将冲突触发点与信息披露顺序改写为“同功能不同表达”。",
        "关键段落建议改为“动作+心理+代价”三段式重写。",  # noqa: E501
    ]
    if risk_level == "high":
        suggestions.insert(0, "高风险：建议先重建章节包再生成正文，避免直接参考原文段落。")
    elif risk_level == "medium":
        suggestions.insert(0, "中风险：建议先做分段改写，再进行一次章节体检。")

    return {
        "splitbook_id": splitbook_id,
        "chapter_no": chapter_no,
        "anti_copy_score": anti_copy_score,
        "risk_level": risk_level,
        "metrics": {
            "max_overlap_ratio": round(max_overlap, 4),
            "max_lcs_ratio": round(max_lcs_ratio, 4),
            "avg_top3_copy_index": avg_copy_index,
            "sampled_chunks": len(hit_rows),
            "ngram_size": ngram_size,
        },
        "top_hits": top_hits,
        "suggestions": suggestions,
        "generated_at": _now_iso(),
    }


async def get_splitbook_scene_view(
    session: AsyncSession,
    splitbook_id: str,
    *,
    chapter_no: int | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    await _ensure_splitbook_tables(session)
    lim = max(1, min(int(limit), 1000))
    if chapter_no is not None:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT scene_key, chapter_no, chapter_title, scene_no, span_start, span_end, summary,
                           time_raw, time_norm, time_confidence, location_raw, location_norm,
                           characters_json, worldbuilding_json, conflict_json, foreshadow_json, payoff_json, events_json, evidence_json, candidate_json, qa_json,
                           prompt_version, model_id, confidence_overall
                    FROM splitbook_scene
                    WHERE splitbook_id=:sid AND chapter_no=:chapter_no
                    ORDER BY scene_no
                    LIMIT :limit
                    """
                ),
                {"sid": splitbook_id, "chapter_no": int(chapter_no), "limit": lim},
            )
        ).mappings().all()
    else:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT scene_key, chapter_no, chapter_title, scene_no, span_start, span_end, summary,
                           time_raw, time_norm, time_confidence, location_raw, location_norm,
                           characters_json, worldbuilding_json, conflict_json, foreshadow_json, payoff_json, events_json, evidence_json, candidate_json, qa_json,
                           prompt_version, model_id, confidence_overall
                    FROM splitbook_scene
                    WHERE splitbook_id=:sid
                    ORDER BY COALESCE(chapter_no, 999999), scene_no
                    LIMIT :limit
                    """
                ),
                {"sid": splitbook_id, "limit": lim},
            )
        ).mappings().all()
    scene_rows = [dict(r) for r in rows]
    chapter_set = {int(x.get("chapter_no") or 0) for x in scene_rows if int(x.get("chapter_no") or 0) > 0}
    return {
        "splitbook_id": splitbook_id,
        "chapter_no": chapter_no,
        "rows": scene_rows,
        "summary": {
            "scene_total": len(scene_rows),
            "chapter_total": len(chapter_set),
        },
        "generated_at": _now_iso(),
    }


async def get_splitbook_pair_view(
    session: AsyncSession,
    splitbook_id: str,
    *,
    chapter_no: int | None = None,
    min_confidence: float = 0.0,
    limit: int = 200,
) -> dict[str, Any]:
    await _ensure_splitbook_tables(session)
    lim = max(1, min(int(limit), 1000))
    conf = max(0.0, min(float(min_confidence), 1.0))
    if chapter_no is not None:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT pair_id::text AS pair_id, seed_scene_key, payoff_scene_key, seed_chapter_no, payoff_chapter_no,
                           seed_text, payoff_text, relation, confidence, score, rationale, evidence_json, created_at
                    FROM splitbook_pair
                    WHERE splitbook_id=:sid
                      AND confidence >= :conf
                      AND (seed_chapter_no=:chapter_no OR payoff_chapter_no=:chapter_no)
                    ORDER BY confidence DESC, score DESC, created_at DESC
                    LIMIT :limit
                    """
                ),
                {"sid": splitbook_id, "conf": conf, "chapter_no": int(chapter_no), "limit": lim},
            )
        ).mappings().all()
    else:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT pair_id::text AS pair_id, seed_scene_key, payoff_scene_key, seed_chapter_no, payoff_chapter_no,
                           seed_text, payoff_text, relation, confidence, score, rationale, evidence_json, created_at
                    FROM splitbook_pair
                    WHERE splitbook_id=:sid
                      AND confidence >= :conf
                    ORDER BY confidence DESC, score DESC, created_at DESC
                    LIMIT :limit
                    """
                ),
                {"sid": splitbook_id, "conf": conf, "limit": lim},
            )
        ).mappings().all()
    pair_rows = [dict(r) for r in rows]
    return {
        "splitbook_id": splitbook_id,
        "chapter_no": chapter_no,
        "rows": pair_rows,
        "summary": {
            "pair_total": len(pair_rows),
            "min_confidence": conf,
        },
        "generated_at": _now_iso(),
    }


async def get_splitbook_qa_report(session: AsyncSession, splitbook_id: str) -> dict[str, Any]:
    await _ensure_splitbook_tables(session)
    sb_row = (
        await session.execute(
            text("SELECT stats FROM splitbook WHERE splitbook_id=CAST(:sid AS uuid) LIMIT 1"),
            {"sid": splitbook_id},
        )
    ).mappings().first()
    stats = (sb_row.get("stats") if sb_row and isinstance(sb_row.get("stats"), dict) else {}) if sb_row else {}
    qa = stats.get("structured_qa") if isinstance(stats.get("structured_qa"), dict) else {}
    if qa:
        return {
            "splitbook_id": splitbook_id,
            "qa": qa,
            "source": "splitbook.stats",
            "generated_at": _now_iso(),
        }

    scene_rows = (
        await session.execute(
            text(
                """
                SELECT chapter_no, time_raw, conflict_json, worldbuilding_json, foreshadow_json, payoff_json, events_json, evidence_json
                FROM splitbook_scene
                WHERE splitbook_id=:sid
                ORDER BY chapter_no, scene_no
                """
            ),
            {"sid": splitbook_id},
        )
    ).mappings().all()
    pair_rows = (
        await session.execute(
            text("SELECT seed_scene_key, confidence FROM splitbook_pair WHERE splitbook_id=:sid"),
            {"sid": splitbook_id},
        )
    ).mappings().all()
    fact_rows = (
        await session.execute(
            text("SELECT chapter_no, fact_type, entity FROM splitbook_fact WHERE splitbook_id=:sid"),
            {"sid": splitbook_id},
        )
    ).mappings().all()
    qa_out = _build_structured_qa_report([dict(x) for x in scene_rows], [dict(x) for x in pair_rows], [dict(x) for x in fact_rows])
    return {
        "splitbook_id": splitbook_id,
        "qa": qa_out,
        "source": "computed",
        "generated_at": _now_iso(),
    }


async def build_splitbook_template_library(session: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    await _ensure_splitbook_tables(session)
    mode = str(payload.get("mode") or "append").strip().lower()
    max_splitbooks = _clamp_int(payload.get("max_splitbooks"), default=8, low=1, high=40)
    raw_ids = payload.get("splitbook_ids")
    splitbook_ids: list[str] = []
    if isinstance(raw_ids, list):
        for item in raw_ids:
            sid = str(item or "").strip()
            if sid and sid not in splitbook_ids:
                splitbook_ids.append(sid)
    if not splitbook_ids:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT splitbook_id::text AS splitbook_id
                    FROM splitbook
                    ORDER BY updated_at DESC
                    LIMIT :limit
                    """
                ),
                {"limit": max_splitbooks},
            )
        ).mappings().all()
        splitbook_ids = [str(r.get("splitbook_id") or "") for r in rows if str(r.get("splitbook_id") or "").strip()]
    splitbook_ids = splitbook_ids[:max_splitbooks]
    if not splitbook_ids:
        raise RuntimeError("SPLITBOOK_IDS_EMPTY")

    stat_rows: list[dict[str, Any]] = []
    for sid in splitbook_ids:
        row = (
            await session.execute(
                text(
                    """
                    SELECT
                      :sid::text AS splitbook_id,
                      (SELECT COUNT(*) FROM splitbook_fact WHERE splitbook_id=CAST(:sid AS uuid)) AS fact_rows,
                      (SELECT COUNT(*) FROM splitbook_growth_ledger WHERE splitbook_id=CAST(:sid AS uuid)) AS growth_rows,
                      (SELECT COUNT(DISTINCT chapter_no) FROM splitbook_fact WHERE splitbook_id=CAST(:sid AS uuid) AND chapter_no IS NOT NULL) AS chapter_rows,
                      (SELECT COUNT(*) FROM splitbook_fact WHERE splitbook_id=CAST(:sid AS uuid) AND fact_type='conflict') AS conflict_rows,
                      (SELECT COUNT(*) FROM splitbook_fact WHERE splitbook_id=CAST(:sid AS uuid) AND fact_type='foreshadow') AS foreshadow_rows,
                      (SELECT COUNT(*) FROM splitbook_fact WHERE splitbook_id=CAST(:sid AS uuid) AND fact_type='payoff') AS payoff_rows,
                      (SELECT COUNT(*) FROM splitbook_fact WHERE splitbook_id=CAST(:sid AS uuid) AND fact_type='world') AS world_rows,
                      (SELECT COUNT(*) FROM splitbook_growth_ledger WHERE splitbook_id=CAST(:sid AS uuid) AND pressure<>'') AS pressure_rows,
                      (SELECT COUNT(*) FROM splitbook_growth_ledger WHERE splitbook_id=CAST(:sid AS uuid) AND cost<>'') AS cost_rows,
                      (SELECT COUNT(*) FROM splitbook_growth_ledger WHERE splitbook_id=CAST(:sid AS uuid) AND gain<>'') AS gain_rows
                    """
                ),
                {"sid": sid},
            )
        ).mappings().first()
        if row:
            stat_rows.append(dict(row))

    if not stat_rows:
        raise RuntimeError("SPLITBOOK_STATS_EMPTY")

    total_books = len(stat_rows)
    total_chapters = sum(int(x.get("chapter_rows") or 0) for x in stat_rows)
    total_conflict = sum(int(x.get("conflict_rows") or 0) for x in stat_rows)
    total_foreshadow = sum(int(x.get("foreshadow_rows") or 0) for x in stat_rows)
    total_payoff = sum(int(x.get("payoff_rows") or 0) for x in stat_rows)
    total_world = sum(int(x.get("world_rows") or 0) for x in stat_rows)
    total_growth = sum(int(x.get("growth_rows") or 0) for x in stat_rows)
    total_pressure = sum(int(x.get("pressure_rows") or 0) for x in stat_rows)
    total_cost = sum(int(x.get("cost_rows") or 0) for x in stat_rows)
    total_gain = sum(int(x.get("gain_rows") or 0) for x in stat_rows)

    per_chapter_conflict = round(total_conflict / max(1, total_chapters), 3)
    foreshadow_payoff_ratio = round(total_foreshadow / max(1, total_payoff), 3)
    growth_balance = round(min(total_pressure, total_cost, total_gain) / max(1, total_growth), 3)

    summary = {
        "books": total_books,
        "chapters": total_chapters,
        "fact_rows": sum(int(x.get("fact_rows") or 0) for x in stat_rows),
        "growth_rows": total_growth,
        "per_chapter_conflict": per_chapter_conflict,
        "foreshadow_payoff_ratio": foreshadow_payoff_ratio,
        "growth_balance": growth_balance,
        "world_rows": total_world,
    }

    now_tag = datetime.now(timezone.utc).strftime("%Y%m%d")
    asset_defs = [
        {
            "asset_type": "strategy",
            "name": f"跨书冲突推进模型-{now_tag}",
            "description": (
                f"抽样{total_books}本拆书后，冲突密度≈{per_chapter_conflict}/章。"
                "建议每章设置“目标-阻力-反制”链路，并在章尾给出下一章压力锚点。"
            ),
            "tags": ["splitbook", "abstract_library", "conflict_model"],
        },
        {
            "asset_type": "plot",
            "name": f"跨书伏笔回收节奏-{now_tag}",
            "description": (
                f"伏笔/回收比≈{foreshadow_payoff_ratio}。"
                "建议采用“早埋点、中强化、关键章回收”的节奏，避免伏笔悬空。"
            ),
            "tags": ["splitbook", "abstract_library", "foreshadow_model"],
        },
        {
            "asset_type": "character",
            "name": f"跨书角色成长弧线-{now_tag}",
            "description": (
                f"成长完整度≈{growth_balance}（压力/代价/收获三要素齐备比例）。"
                "建议固定使用“压力→代价→收获→阶段跃迁”四段式角色推进。"
            ),
            "tags": ["splitbook", "abstract_library", "growth_arc_model"],
        },
    ]

    if mode == "replace":
        await session.execute(
            text(
                """
                DELETE FROM template_asset
                WHERE COALESCE(source_span->>'library_key','')='splitbook_multi_abstract'
                """
            )
        )
        await session.commit()

    created_items: list[dict[str, Any]] = []
    for item in asset_defs:
        row = (
            await session.execute(
                text(
                    """
                    INSERT INTO template_asset(asset_type, name, description, tags, source_splitbook_id, source_span)
                    VALUES (:asset_type, :name, :description, CAST(:tags AS text[]), NULL, CAST(:source_span AS jsonb))
                    RETURNING asset_id::text AS asset_id
                    """
                ),
                {
                    "asset_type": item["asset_type"],
                    "name": item["name"],
                    "description": item["description"],
                    "tags": item["tags"],
                    "source_span": json.dumps(
                        {
                            "library_key": "splitbook_multi_abstract",
                            "mode": mode,
                            "summary": summary,
                            "source_splitbook_ids": splitbook_ids,
                            "generated_at": _now_iso(),
                        },
                        ensure_ascii=False,
                    ),
                },
            )
        ).mappings().first()
        created_items.append({"asset_id": str((row or {}).get("asset_id") or ""), **item})
    await session.commit()

    return {
        "ok": True,
        "mode": mode,
        "source_splitbook_ids": splitbook_ids,
        "summary": summary,
        "created_items": created_items,
        "created_count": len(created_items),
        "generated_at": _now_iso(),
    }
