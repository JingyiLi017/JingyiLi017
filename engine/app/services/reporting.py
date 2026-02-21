from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .tension import compare_eval_runs, get_outline_detail_diff


def _esc(text: Any) -> str:
    value = str(text)
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _delta_class(value: float) -> str:
    if value > 0:
        return "delta-pos"
    if value < 0:
        return "delta-neg"
    return ""


def _score_rows(before: dict[str, float], after: dict[str, float], delta: dict[str, float]) -> str:
    keys = ["overall", "conflict_strength", "stakes", "cost", "pace", "reversal", "hook", "payoff"]
    rows: list[str] = []
    for key in keys:
        b = float(before.get(key, 0.0))
        a = float(after.get(key, 0.0))
        d = float(delta.get(key, 0.0))
        rows.append(
            f"<tr><td>{_esc(key)}</td><td class='mono'>{b:.4f}</td><td class='mono'>{a:.4f}</td>"
            f"<td class='mono {_delta_class(d)}'>{d:+.4f}</td></tr>"
        )
    return "".join(rows)


def _curve_bars(curve: list[float]) -> str:
    blocks: list[str] = []
    for value in curve[:5]:
        width = max(1, int(round(float(value) * 100)))
        blocks.append(
            f"<span><span class='bar' style='width:{width}px'></span>"
            f"<span class='curve-point mono'>{float(value):.2f}</span></span>"
        )
    return "".join(blocks)


def _mechanic_chips(stats: dict[str, Any]) -> str:
    mech = dict((stats.get("mechanics") or {}))
    if not mech:
        return "<span class='chip'>none</span>"
    parts = []
    for key, value in sorted(mech.items(), key=lambda x: (-int(x[1]), str(x[0]))):
        parts.append(f"<span class='chip'>{_esc(key)} × {int(value)}</span>")
    return "".join(parts)


def _inserted_list(changes: dict[str, Any]) -> str:
    inserted = list(changes.get("inserted_nodes") or [])
    if not inserted:
        return "<div class='small'>None</div>"
    lines: list[str] = []
    for item in inserted:
        lines.append(
            "<div class='diff-item'>"
            f"<span class='diff-title mono'>{_esc(item.get('node_id'))}</span> "
            f"<span class='chip'>{_esc(item.get('type'))}</span> "
            f"<span class='chip'>{_esc(item.get('mechanic') or 'n/a')}</span> "
            f"<span class='small'>after {_esc(item.get('after_node_id') or '-')}</span>"
            "</div>"
        )
    return "".join(lines)


def _summary_blocks(changes: dict[str, Any]) -> str:
    rows = list(changes.get("summary_changed") or [])
    if not rows:
        return "<div class='small'>None</div>"
    blocks: list[str] = []
    for row in rows:
        blocks.append(
            "<div class='diff-item'>"
            f"<div class='diff-title mono'>{_esc(row.get('node_id'))} "
            f"<span class='chip'>{_esc(row.get('mechanic') or 'n/a')}</span></div>"
            "<div class='beforeafter'>"
            f"<div class='box'><b class='small'>Before</b><br>{_esc(row.get('before') or '')}</div>"
            f"<div class='box'><b class='small'>After</b><br>{_esc(row.get('after') or '')}</div>"
            "</div></div>"
        )
    return "".join(blocks)


def _similarity_block(similarity_guard: dict[str, Any] | None) -> str:
    if not similarity_guard:
        return "<div class='small'>not executed</div>"
    result = dict(similarity_guard.get("result") or {})
    risk = str(result.get("risk_level") or "unknown")
    cls = "tag-bad" if risk == "high" else "tag-warn" if risk == "mid" else "tag-good"
    top = (result.get("top_hits") or [{}])[0] if isinstance(result.get("top_hits"), list) else {}
    return (
        "<div class='kv'>"
        f"<div class='k'>Risk Level</div><div class='v {cls}'>{_esc(risk)}</div>"
        f"<div class='k'>Max Vec</div><div class='v'>{_esc(result.get('max_vec_score'))}</div>"
        f"<div class='k'>Max Ngram</div><div class='v'>{_esc(result.get('max_ngram_overlap'))}</div>"
        f"<div class='k'>Top Hit</div><div class='v'>chunk={_esc(top.get('chunk_id') or '-')} score={_esc(top.get('score') or '-')}</div>"
        "</div>"
    )


def _next_step(delta: dict[str, Any], from_version: int, sim: dict[str, Any] | None) -> str:
    overall = float(delta.get("overall", 0.0))
    cost = float(delta.get("cost", 0.0))
    reversal = float(delta.get("reversal", 0.0))
    risk = str(((sim or {}).get("result") or {}).get("risk_level") or "")
    if overall >= 0.05:
        if risk in {"mid", "high"}:
            return "张力改善明显，建议先 rewrite 命中段，再生成 draft。"
        return "张力改善明显，建议直接生成 draft 并进入下一章。"
    if overall > 0:
        if cost < 0.05 and reversal < 0.05:
            return "改善有限，建议追加一个 cost_hardening 或 reversal 后重跑计划。"
        return "改善有限，建议小步追加 1 个机制并复测。"
    return f"本次补丁收益不佳，建议回滚到 v{from_version}，缩小改动（max_insert=2）后重做 plan。"


def build_chapter_revision_html(payload: dict[str, Any], diff: dict[str, Any], compare: dict[str, Any]) -> str:
    meta = dict(payload or {})
    before = ((compare.get("before") or {}).get("scores") or {})
    after = ((compare.get("after") or {}).get("scores") or {})
    delta = (compare.get("delta") or {})
    before_curve = ((compare.get("before") or {}).get("curve") or [])
    after_curve = ((compare.get("after") or {}).get("curve") or [])
    changes = diff.get("changes") or {}
    stats = diff.get("stats") or {}
    diff_meta = diff.get("meta") or {}
    generated_at = datetime.now(timezone.utc).isoformat()
    sim = meta.get("similarity_guard")

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Chapter Revision Report</title>
  <style>
    :root {{
      --fg:#111;--muted:#666;--bg:#fff;--line:#e6e6e6;--chip:#f5f5f5;
      --good:#0a7a3d;--warn:#b26a00;--bad:#b00020;
      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Courier New", monospace;
      --sans: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
    }}
    html,body{{background:var(--bg);color:var(--fg);font-family:var(--sans);}}
    body{{margin:24px;}}
    h1{{font-size:20px;margin:0 0 6px 0;}} h2{{font-size:14px;margin:18px 0 8px 0;}}
    .meta{{color:var(--muted);font-size:12px;line-height:1.6;}}
    .row{{display:flex;gap:12px;flex-wrap:wrap;}} .card{{border:1px solid var(--line);border-radius:10px;padding:12px;flex:1 1 320px;}}
    .kv{{display:grid;grid-template-columns:120px 1fr;gap:6px 10px;font-size:12px;}} .k{{color:var(--muted);}} .v{{font-family:var(--mono);font-size:12px;}}
    table{{width:100%;border-collapse:collapse;font-size:12px;}} th,td{{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line);vertical-align:top;}}
    th{{color:var(--muted);font-weight:600;}} .delta-pos{{color:var(--good);font-weight:700;}} .delta-neg{{color:var(--bad);font-weight:700;}}
    .chip{{display:inline-block;background:var(--chip);border:1px solid var(--line);padding:2px 8px;border-radius:999px;font-size:11px;margin:2px 6px 2px 0;}}
    .small{{font-size:11px;color:var(--muted);}} .mono{{font-family:var(--mono);}}
    .bar{{display:inline-block;height:10px;background:#111;border-radius:6px;vertical-align:middle;margin-right:6px;}}
    .curve-line{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;}}
    .curve-point{{font-size:11px;color:var(--muted);}} .hr{{height:1px;background:var(--line);margin:14px 0;}}
    .note{{padding:10px;border-radius:10px;border:1px dashed var(--line);background:#fafafa;font-size:12px;color:var(--muted);}}
    .tag-good{{color:var(--good);font-weight:700;}} .tag-warn{{color:var(--warn);font-weight:700;}} .tag-bad{{color:var(--bad);font-weight:700;}}
    .diff-item{{margin:6px 0;}} .diff-title{{font-weight:700;}} .beforeafter{{display:grid;grid-template-columns:1fr 1fr;gap:10px;}}
    .box{{border:1px solid var(--line);border-radius:10px;padding:10px;min-height:40px;white-space:pre-wrap;word-break:break-word;}}
    .footer{{margin-top:18px;font-size:11px;color:var(--muted);}}
  </style>
</head>
<body>
  <h1>Chapter Revision Report</h1>
  <div class="meta">
    <div><b>{_esc(meta.get("book_name") or meta.get("book_id") or "-")}</b> · 第 {_esc(meta.get("chapter_no") or "-")} 章 {_esc(meta.get("chapter_title") or "-")} · {_esc(meta.get("arc_id") or "-")}</div>
    <div>Outline Version: v{_esc(meta.get("from_version"))} → v{_esc(meta.get("to_version"))} · Generated: {_esc(meta.get("generated_at") or generated_at)}</div>
  </div>
  <div class="hr"></div>

  <div class="row">
    <div class="card">
      <h2>Score Delta</h2>
      <table>
        <thead><tr><th>Dimension</th><th class="mono">Before</th><th class="mono">After</th><th class="mono">Δ</th></tr></thead>
        <tbody>{_score_rows(before, after, delta)}</tbody>
      </table>
      <div class="small">Note: scores range [0,1].</div>
    </div>
    <div class="card">
      <h2>Tension Curve (5 points)</h2>
      <div class="small">Before</div><div class="curve-line">{_curve_bars(before_curve)}</div>
      <div class="small" style="margin-top:10px;">After</div><div class="curve-line">{_curve_bars(after_curve)}</div>
      <div class="note" style="margin-top:10px;">5 点分别代表开局 / 早段 / 中段 / 晚段 / 收束张力。</div>
    </div>
  </div>

  <div class="row">
    <div class="card">
      <h2>Outline Diff Summary</h2>
      <div class="kv">
        <div class="k">Inserted</div><div class="v">{int(stats.get("insert_count", 0))}</div>
        <div class="k">Changed Summary</div><div class="v">{int(stats.get("change_summary_count", 0))}</div>
        <div class="k">Removed</div><div class="v">{int(stats.get("remove_count", 0))}</div>
        <div class="k">Moved</div><div class="v">{int(stats.get("move_count", 0))}</div>
        <div class="k">Mechanics</div><div>{_mechanic_chips(stats)}</div>
      </div>
      <div class="small" style="margin-top:8px;">Diff generator: {_esc(diff_meta.get("used_applied_log"))}</div>
    </div>
    <div class="card">
      <h2>Inserted Nodes</h2>
      {_inserted_list(changes)}
    </div>
  </div>

  <div class="row">
    <div class="card">
      <h2>Summary Changes</h2>
      {_summary_blocks(changes)}
    </div>
  </div>

  <div class="row">
    <div class="card">
      <h2>Similarity Guard</h2>
      {_similarity_block(sim)}
    </div>
    <div class="card">
      <h2>Next Step</h2>
      <div class="note">{_esc(_next_step(delta, int(meta.get("from_version") or 0), sim if isinstance(sim, dict) else None))}</div>
    </div>
  </div>

  <div class="footer">Generated by Novel Engine · request_id={_esc(meta.get("request_id") or "-")} · repair_txn_id={_esc(meta.get("repair_txn_id") or "-")}</div>
</body>
</html>""".strip()


async def create_chapter_revision_report(
    session: AsyncSession,
    *,
    book_id: str,
    chapter_id: str,
    from_version: int,
    to_version: int,
    before_eval_run_id: str,
    after_eval_run_id: str,
    include_similarity_guard: bool,
) -> dict[str, Any]:
    diff = await get_outline_detail_diff(session, chapter_id, from_version, to_version)
    compare = await compare_eval_runs(session, chapter_id, before_eval_run_id, after_eval_run_id)

    chapter_row = await session.execute(
        text('SELECT "order" AS chapter_no, title, arc_id FROM chapter WHERE chapter_id=:chapter_id'),
        {"chapter_id": chapter_id},
    )
    chapter = chapter_row.mappings().first() or {}
    book_row = await session.execute(text("SELECT title FROM book WHERE book_id=:book_id"), {"book_id": book_id})
    book_title = book_row.scalar()

    similarity_guard: dict[str, Any] | None = None
    if include_similarity_guard:
        sim_row = await session.execute(
            text(
                """
                SELECT output
                FROM skill_run
                WHERE book_id=:book_id AND skill_name='SIMILARITY_GUARD_V1'
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"book_id": book_id},
        )
        sim = sim_row.mappings().first()
        if sim:
            similarity_guard = dict(sim["output"] or {})

    payload = {
        "book_id": book_id,
        "book_name": book_title,
        "chapter_id": chapter_id,
        "chapter_no": chapter.get("chapter_no"),
        "chapter_title": chapter.get("title"),
        "arc_id": chapter.get("arc_id"),
        "from_version": from_version,
        "to_version": to_version,
        "before_eval_run_id": before_eval_run_id,
        "after_eval_run_id": after_eval_run_id,
        "include_similarity_guard": include_similarity_guard,
        "similarity_guard": similarity_guard,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    html = build_chapter_revision_html(payload, diff, compare)
    saved = await session.execute(
        text(
            """
            INSERT INTO report(book_id, chapter_id, report_type, payload, html)
            VALUES (:book_id, :chapter_id, 'chapter_revision', CAST(:payload AS jsonb), :html)
            RETURNING report_id
            """
        ),
        {"book_id": book_id, "chapter_id": chapter_id, "payload": json.dumps(payload), "html": html},
    )
    report_id = str(saved.scalar_one())
    await session.commit()
    return {"report_id": report_id, "html": html, "meta": payload, "diff": diff, "compare": compare}

