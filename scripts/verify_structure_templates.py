import asyncio
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
import sys

from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.app.main import app


@dataclass
class VerifyResult:
    ok: bool
    report: dict


def _template_payload(book_id: str) -> dict:
    return {
        "book_id": book_id,
        "items": [
            {
                "name": "tmpl-volume-combo",
                "st_type": "volume_plan",
                "subtype": "vol_end_combo",
                "tags": ["mid_paced", "cliffhanger_end"],
                "pattern": {"combo": [{"kind": "growth"}, {"kind": "foreshadow_payoff"}, {"kind": "cliffhanger"}]},
                "slots": ["{{volume_goal}}"],
                "source_meta": {"source_book_hash": "srcA"},
            },
            {
                "name": "tmpl-payoff-reversal",
                "st_type": "payoff",
                "subtype": "reversal",
                "tags": ["info_reveal", "high_conflict"],
                "pattern": {"steps": ["reveal_partial_truth", "reinterpret_previous_clue", "show_cost"]},
                "slots": ["{{foreshadow_question}}"],
                "source_meta": {"source_book_hash": "srcB"},
            },
            {
                "name": "tmpl-cliff-question",
                "st_type": "cliff",
                "subtype": "question_end",
                "tags": ["cliffhanger_end", "high_conflict"],
                "pattern": {"hook_types": ["deadline", "hidden_rule"], "ending_format": "question_or_interrupt"},
                "slots": ["{{new_threat}}"],
                "source_meta": {"source_book_hash": "srcC"},
            },
            {
                "name": "tmpl-beat-pack-hard",
                "st_type": "beat_pack",
                "subtype": "hard_conflict",
                "tags": ["high_conflict", "fast_paced"],
                "pattern": {"beats": ["desire", "obstacle", "cost", "turn", "aftershock"]},
                "slots": ["{{goal}}", "{{cost}}"],
                "source_meta": {"source_book_hash": "srcD"},
            },
        ],
    }


async def _run() -> VerifyResult:
    report: dict = {}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/v1/system/db/init")
        report["db_init"] = {"status": r.status_code, "ok": r.json().get("ok")}
        assert r.status_code == 200

        book_title = f"StructureVerify-{uuid.uuid4().hex[:8]}"
        r = await client.post("/v1/books", json={"title": book_title, "author": "verify"})
        assert r.status_code == 200, r.text
        book = r.json()
        book_id = str(book["book_id"])
        report["book"] = {"book_id": book_id, "title": book["title"]}

        for i in range(1, 13):
            rr = await client.post(f"/v1/books/{book_id}/chapters", json={"chapter_no": i, "title": f"c{i}"})
            assert rr.status_code == 200, rr.text
        report["chapters_created"] = 12

        r = await client.post(f"/v1/books/{book_id}/volumes/auto_create", json={"chapters_per_volume": 10})
        assert r.status_code == 200, r.text
        report["auto_create"] = {"status": r.status_code, "created": r.json().get("created")}

        r = await client.get(f"/v1/books/{book_id}/volumes")
        assert r.status_code == 200, r.text
        volumes = r.json().get("items") or []
        assert volumes, "no volumes created"
        volume = volumes[0]
        volume_id = str(volume["volume_id"])
        volume_no = int(volume["volume_no"])
        report["volume"] = {
            "volume_id": volume_id,
            "volume_no": volume_no,
            "range": [volume["start_chapter_no"], volume["end_chapter_no"]],
        }

        r = await client.post("/v1/ingest/structure_templates", json=_template_payload(book_id))
        assert r.status_code == 200, r.text
        ingest = r.json()
        report["ingest"] = {
            "status": r.status_code,
            "created": ingest.get("created"),
            "skipped": ingest.get("skipped"),
            "banned": ingest.get("banned"),
        }

        r = await client.get("/v1/structure_templates", params={"book_id": book_id, "limit": 50})
        assert r.status_code == 200, r.text
        templates = r.json().get("items") or []
        report["templates_list_count"] = len(templates)
        assert len(templates) >= 4, f"expected >=4 templates, got {len(templates)}"

        payoff = next((x for x in templates if str(x.get("st_type")) == "payoff"), None)
        assert payoff is not None, "payoff template not found"
        payoff_id = str(payoff["template_id"])

        r = await client.post(f"/v1/structure_templates/{payoff_id}/policy", json={"policy": "pinned"})
        assert r.status_code == 200, r.text
        report["set_policy"] = r.json()

        r = await client.post(
            f"/v1/books/{book_id}/volumes/{volume_id}/plan/apply_auto",
            json={
                "volume_goal": "卷末回收并制造下一卷悬念",
                "volume_theme": "代价与真相",
                "target_pacing": "mid",
                "reason": "verify_structure_templates",
                "note": "auto_verify",
            },
        )
        assert r.status_code == 200, r.text
        apply_out = r.json()
        report["apply_auto"] = {
            "status": r.status_code,
            "ok": apply_out.get("ok"),
            "version": apply_out.get("version"),
        }

        r = await client.get(f"/v1/books/{book_id}/volumes/{volume_id}/plan/active")
        assert r.status_code == 200, r.text
        plan = (r.json().get("plan") or {})
        plan_items = plan.get("items") if isinstance(plan.get("items"), list) else []
        assumptions = plan.get("assumptions") if isinstance(plan.get("assumptions"), dict) else {}
        selected = assumptions.get("selected_structure_templates") if isinstance(assumptions.get("selected_structure_templates"), dict) else {}
        selected_types = sorted(selected.keys())
        report["active_plan_selected_types"] = selected_types
        assert {"volume_plan", "payoff", "cliff", "beat_pack"}.issubset(set(selected_types)), selected_types
        combo_items = [x for x in plan_items if isinstance(x, dict) and str(x.get("kind") or "") == "combo"]
        report["active_plan_combo_items"] = len(combo_items)
        assert len(combo_items) >= 4, f"expected >=4 combo items, got {len(combo_items)}"

        r = await client.get("/v1/structure_templates", params={"book_id": book_id, "limit": 100})
        assert r.status_code == 200, r.text
        templates_after = r.json().get("items") or []
        last_used_count = sum(1 for t in templates_after if t.get("last_used_volume_no") == volume_no)
        report["templates_last_used_updated"] = last_used_count
        assert last_used_count >= 4, f"expected >=4 templates with last_used_volume_no={volume_no}, got {last_used_count}"

        r = await client.get("/v1/structure_combos", params={"book_id": book_id, "limit": 100})
        assert r.status_code == 200, r.text
        combos = r.json().get("items") or []
        report["combos_count"] = len(combos)
        assert len(combos) >= 4, f"expected >=4 combos, got {len(combos)}"

        r = await client.get(f"/v1/books/{book_id}/structure_combos/stats", params={"limit": 100})
        assert r.status_code == 200, r.text
        stats = r.json()
        by_type = stats.get("by_type") if isinstance(stats.get("by_type"), dict) else {}
        report["combo_stats_types"] = sorted(list(by_type.keys()))
        assert "vol_end_combo" in report["combo_stats_types"], report["combo_stats_types"]

        r = await client.post(f"/v1/books/{book_id}/asset_policy_proposals/generate")
        assert r.status_code == 200, r.text
        report["generate_proposals"] = r.json()

        r = await client.get(
            f"/v1/books/{book_id}/assets/structure_template/{payoff_id}/evidence",
            params={"limit": 3},
        )
        assert r.status_code == 200, r.text
        ev = r.json()
        report["evidence"] = {
            "item_type": ((ev.get("item") or {}).get("item_type")),
            "samples": len(ev.get("samples") or []),
            "recommendation": ((ev.get("diagnosis") or {}).get("recommendation")),
        }
        assert report["evidence"]["item_type"] == "structure_template"

    return VerifyResult(ok=True, report=report)


def main() -> None:
    result = asyncio.run(_run())
    print(json.dumps({"ok": result.ok, "report": result.report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
