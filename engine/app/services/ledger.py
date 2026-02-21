from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

PROTECTED_FIELDS = [
    ("facts", "identity", "background"),
    ("facts", "motivation"),
    ("facts", "goal"),
    ("facts", "fear_or_flaw"),
    ("facts", "taboos_or_bottomline"),
]

MERGE_UNION_FIELDS = [
    ("aliases",),
    ("facts", "traits"),
    ("facts", "skills"),
    ("voice_notes", "catchphrases"),
]


def deep_get(obj: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = obj
    for p in path:
        if not isinstance(current, dict) or p not in current:
            return None
        current = current[p]
    return current


def deep_set(obj: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = obj
    for p in path[:-1]:
        node = current.get(p)
        if not isinstance(node, dict):
            node = {}
            current[p] = node
        current = node
    current[path[-1]] = value


def union_list(a: Any, b: Any) -> list[Any]:
    left = a if isinstance(a, list) else []
    right = b if isinstance(b, list) else []
    merged = [x for x in left if x]
    merged.extend([x for x in right if x and x not in merged])
    return merged


def merge_character_card(old_card: dict[str, Any], new_item: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    merged = dict(old_card or {})
    needs_review = False
    conflicts: list[dict[str, Any]] = []

    for path in MERGE_UNION_FIELDS:
        oldv = deep_get(merged, path) if len(path) > 1 else merged.get(path[0])
        newv = deep_get(new_item, path) if len(path) > 1 else new_item.get(path[0])
        value = union_list(oldv, newv)
        if len(path) == 1:
            merged[path[0]] = value
        else:
            deep_set(merged, path, value)

    for path in PROTECTED_FIELDS:
        oldv = deep_get(merged, path)
        newv = deep_get(new_item, path)
        if oldv in (None, "", [], {}):
            if newv not in (None, "", [], {}):
                deep_set(merged, path, newv)
        elif newv not in (None, "", [], {}) and newv != oldv:
            needs_review = True
            conflicts.append({"path": ".".join(path), "old": oldv, "new": newv})

    old_rel = old_card.get("relationships", []) if isinstance(old_card, dict) else []
    new_rel = new_item.get("relationships", []) or []
    rel_map: dict[str, dict[str, Any]] = {
        (r.get("target_name") or "").strip(): r for r in old_rel if (r.get("target_name") or "").strip()
    }
    for rel in new_rel:
        target = (rel.get("target_name") or "").strip()
        if not target:
            continue
        if target not in rel_map:
            rel_map[target] = rel
            continue
        current = rel_map[target]
        if not current.get("type") and rel.get("type"):
            current["type"] = rel["type"]
        current["confidence"] = max(float(current.get("confidence") or 0), float(rel.get("confidence") or 0))
    merged["relationships"] = list(rel_map.values())

    meta = merged.get("_meta")
    if not isinstance(meta, dict):
        meta = {}
    if conflicts:
        meta.setdefault("conflicts", []).extend(conflicts)
    if needs_review:
        meta["needs_review"] = True
    merged["_meta"] = meta
    return merged, needs_review


def extract_evidence_chunk_ids(item: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for evidence in item.get("evidence", []) or []:
        cid = evidence.get("chunk_id")
        if cid and cid not in ids:
            ids.append(cid)
    return ids


async def _get_skill_run(session: AsyncSession, book_id: str, skill_run_id: str) -> dict[str, Any] | None:
    result = await session.execute(
        text(
            """
            SELECT skill_run_id, skill_name, output
            FROM skill_run
            WHERE skill_run_id=:skill_run_id AND book_id=:book_id
            """
        ),
        {"skill_run_id": skill_run_id, "book_id": book_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def _get_or_create_character(session: AsyncSession, book_id: str, name: str, aliases: list[str], role: str | None) -> str:
    found = await session.execute(
        text("SELECT character_id FROM character WHERE book_id=:book_id AND name=:name"),
        {"book_id": book_id, "name": name},
    )
    row = found.first()
    if row:
        return str(row[0])

    inserted = await session.execute(
        text(
            """
            INSERT INTO character(book_id, name, alias, role)
            VALUES (:book_id, :name, :alias, :role)
            RETURNING character_id
            """
        ),
        {"book_id": book_id, "name": name, "alias": aliases, "role": role},
    )
    return str(inserted.scalar_one())


async def _get_latest_character_version(session: AsyncSession, character_id: str) -> tuple[int, dict[str, Any], list[str]]:
    result = await session.execute(
        text(
            """
            SELECT version, card, source_chunk_ids
            FROM character_version
            WHERE character_id=:character_id
            ORDER BY version DESC
            LIMIT 1
            """
        ),
        {"character_id": character_id},
    )
    row = result.mappings().first()
    if not row:
        return 0, {}, []
    return int(row["version"]), row["card"] or {}, [str(x) for x in (row["source_chunk_ids"] or [])]


async def _insert_character_version(
    session: AsyncSession,
    character_id: str,
    version: int,
    card: dict[str, Any],
    source_chunk_ids: list[str],
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO character_version(character_id, version, card, source_chunk_ids)
            VALUES (:character_id, :version, :card::jsonb, :source_chunk_ids::uuid[])
            """
        ),
        {
            "character_id": character_id,
            "version": version,
            "card": json.dumps(card),
            "source_chunk_ids": source_chunk_ids,
        },
    )


async def apply_from_skill_run(book_id: str, skill_run_id: str, apply_policy: dict[str, str], session: AsyncSession) -> dict[str, Any]:
    skill_run = await _get_skill_run(session, book_id, skill_run_id)
    if not skill_run:
        raise ValueError("SKILL_RUN_NOT_FOUND")

    skill_name = str(skill_run["skill_name"])
    output = skill_run["output"] or {}
    items = output.get("items", []) if isinstance(output, dict) else []

    applied = {"characters": 0, "timeline": 0, "world": 0, "plot_hooks": 0}
    needs_review = {"characters": 0, "timeline": 0, "world": 0, "plot_hooks": 0}

    if skill_name.startswith("EXTRACT_CHARACTERS"):
        if apply_policy.get("characters") != "upsert_safe":
            raise ValueError("INVALID_POLICY_FOR_CHARACTERS")
        for item in items:
            name = (item.get("name") or "").strip()
            if not name:
                continue
            cid = await _get_or_create_character(session, book_id, name, item.get("aliases", []) or [], item.get("role"))
            last_version, old_card, old_evidence = await _get_latest_character_version(session, cid)
            merged, nr = merge_character_card(old_card, item)
            evidence = old_evidence[:]
            for ev in extract_evidence_chunk_ids(item):
                if ev not in evidence:
                    evidence.append(ev)
            await _insert_character_version(session, cid, last_version + 1, merged, evidence)
            applied["characters"] += 1
            if nr:
                needs_review["characters"] += 1

    elif skill_name.startswith("EXTRACT_TIMELINE"):
        if apply_policy.get("timeline") != "append_only":
            raise ValueError("INVALID_POLICY_FOR_TIMELINE")
        for item in items:
            title = (item.get("title") or "").strip()
            if not title:
                continue
            duplicate = await session.execute(
                text(
                    """
                    SELECT event_id FROM timeline_event
                    WHERE book_id=:book_id AND title=:title
                    LIMIT 1
                    """
                ),
                {"book_id": book_id, "title": title},
            )
            is_dup = duplicate.first() is not None
            causality = item.get("cause_effect", {}) or {}
            if is_dup:
                meta = causality.get("_meta", {})
                meta["needs_review"] = True
                causality["_meta"] = meta
            await session.execute(
                text(
                    """
                    INSERT INTO timeline_event(book_id, chapter_id, title, description, causality, source_chunk_ids)
                    VALUES (:book_id, :chapter_id, :title, :description, :causality::jsonb, :source_chunk_ids::uuid[])
                    """
                ),
                {
                    "book_id": book_id,
                    "chapter_id": item.get("chapter_id"),
                    "title": title,
                    "description": item.get("description") or "",
                    "causality": json.dumps(causality),
                    "source_chunk_ids": extract_evidence_chunk_ids(item),
                },
            )
            applied["timeline"] += 1
            if is_dup:
                needs_review["timeline"] += 1

    elif skill_name.startswith("EXTRACT_WORLD"):
        if apply_policy.get("world") != "merge_by_key_needs_review":
            raise ValueError("INVALID_POLICY_FOR_WORLD")
        for item in items:
            key = (item.get("key") or "").strip()
            if not key:
                continue
            value = item.get("value", {}) or {}
            existing = await session.execute(
                text("SELECT fact_id, value, confidence, source_chunk_ids FROM world_fact WHERE book_id=:book_id AND key=:key"),
                {"book_id": book_id, "key": key},
            )
            row = existing.mappings().first()
            if not row:
                await session.execute(
                    text(
                        """
                        INSERT INTO world_fact(book_id, key, value, confidence, source_chunk_ids)
                        VALUES (:book_id, :key, :value::jsonb, :confidence, :source_chunk_ids::uuid[])
                        """
                    ),
                    {
                        "book_id": book_id,
                        "key": key,
                        "value": json.dumps(value),
                        "confidence": float(item.get("confidence") or 0.7),
                        "source_chunk_ids": extract_evidence_chunk_ids(item),
                    },
                )
            else:
                old_value = row["value"] or {}
                for field in ("rule", "cost", "limit", "exception"):
                    if (old_value.get(field) in (None, "", [], {})) and (value.get(field) not in (None, "", [], {})):
                        old_value[field] = value[field]
                merged_evidence = [str(x) for x in (row["source_chunk_ids"] or [])]
                for ev in extract_evidence_chunk_ids(item):
                    if ev not in merged_evidence:
                        merged_evidence.append(ev)
                await session.execute(
                    text(
                        """
                        UPDATE world_fact
                        SET value=:value::jsonb,
                            confidence=:confidence,
                            source_chunk_ids=:source_chunk_ids::uuid[]
                        WHERE fact_id=:fact_id
                        """
                    ),
                    {
                        "fact_id": row["fact_id"],
                        "value": json.dumps(old_value),
                        "confidence": max(float(row["confidence"] or 0), float(item.get("confidence") or 0)),
                        "source_chunk_ids": merged_evidence,
                    },
                )
            applied["world"] += 1

    elif skill_name.startswith("EXTRACT_PLOT_HOOKS"):
        if apply_policy.get("plot_hooks") != "append_only":
            raise ValueError("INVALID_POLICY_FOR_PLOT_HOOKS")
        for item in items:
            content = (item.get("content") or "").strip()
            if not content:
                continue
            duplicate = await session.execute(
                text("SELECT hook_id FROM plot_hook WHERE book_id=:book_id AND content=:content LIMIT 1"),
                {"book_id": book_id, "content": content},
            )
            meta = item.get("meta", {}) or {}
            is_dup = duplicate.first() is not None
            if is_dup:
                meta["needs_review"] = True
            await session.execute(
                text(
                    """
                    INSERT INTO plot_hook(book_id, chapter_id, kind, content, status, meta, source_chunk_ids)
                    VALUES (:book_id, :chapter_id, :kind, :content, 'open', :meta::jsonb, :source_chunk_ids::uuid[])
                    """
                ),
                {
                    "book_id": book_id,
                    "chapter_id": item.get("chapter_id"),
                    "kind": item.get("kind") or "foreshadow",
                    "content": content,
                    "meta": json.dumps(meta),
                    "source_chunk_ids": extract_evidence_chunk_ids(item),
                },
            )
            applied["plot_hooks"] += 1
            if is_dup:
                needs_review["plot_hooks"] += 1

    await session.commit()
    return {"ok": True, "applied": applied, "needs_review": needs_review, "apply_policy": apply_policy}
