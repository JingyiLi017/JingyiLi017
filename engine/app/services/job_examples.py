from __future__ import annotations

from typing import Any


JOB_EXAMPLES: dict[str, dict[str, Any]] = {
    "COMMON": {
        "running": {
            "job_id": "uuid",
            "job_type": "EVAL",
            "status": "running",
            "stage": "LLM_SCORE",
            "progress": 0.47,
            "payload": {},
            "result": {},
            "error": {},
            "logs": ["..."],
        },
        "failed": {
            "status": "failed",
            "stage": "LLM_SCORE",
            "progress": 0.47,
            "error": {
                "code": "LLM_TIMEOUT",
                "message": "ollama request timed out",
                "hint": "reduce input size or increase timeout",
            },
        },
    },
    "INGEST": {
        "payload": {
            "book_id": "uuid",
            "path": "/home/user/novels/book.txt",
            "encoding": "utf-8",
            "chunk_size": 900,
            "overlap": 120,
        },
        "result_done": {"source_id": "uuid", "chunks_created": 15234},
        "errors": ["FILE_NOT_FOUND", "READ_FAILED", "DISK_LOW"],
    },
    "EMBED": {
        "payload": {"book_id": "uuid", "embedding_model": "bge-m3:latest", "dim": 1024, "batch_size": 64},
        "result_done": {"embedded": 15234, "skipped_existing": 0},
        "errors": ["MODEL_NOT_FOUND", "EMBED_FAILED", "OLLAMA_UNAVAILABLE"],
    },
    "EVAL": {
        "payload": {
            "book_id": "uuid",
            "chapter_id": "uuid",
            "outline_version": "latest",
            "targets": {
                "conflict_strength": 0.78,
                "stakes": 0.74,
                "cost": 0.7,
                "pace": 0.72,
                "reversal": 0.68,
                "hook": 0.7,
                "payoff": 0.62,
            },
        },
        "result_done": {"skill_run_id": "uuid", "outline_version_resolved": 12},
        "skill_run_output": {
            "schema_name": "EVAL_TENSION_SCORE",
            "schema_ver": 1,
            "generated_at": "ISO8601",
            "result": {
                "scores": {
                    "overall": 0.56,
                    "conflict_strength": 0.58,
                    "stakes": 0.52,
                    "cost": 0.41,
                    "pace": 0.61,
                    "reversal": 0.44,
                    "hook": 0.63,
                    "payoff": 0.5,
                },
                "tension_curve": [0.52, 0.55, 0.5, 0.61, 0.64],
                "issues": [
                    {"code": "NO_COST", "severity": "high", "where": "N5", "detail": "代价不落地"},
                    {"code": "LOW_REVERSAL", "severity": "mid", "where": "N6", "detail": "反转信息差不足"},
                ],
            },
            "warnings": [],
        },
    },
    "PLAN": {
        "payload": {
            "book_id": "uuid",
            "chapter_id": "uuid",
            "outline_version": "latest",
            "targets": {},
            "style": {"face_slap_density": 0.18, "upgrade_density": 0.14},
            "actions_override": ["timer"],
        },
        "result_done": {"skill_run_id": "uuid", "outline_version_resolved": 12},
        "skill_run_output": {
            "schema_name": "TENSION_CONTROL_PLAN",
            "schema_ver": 1,
            "generated_at": "ISO8601",
            "result": {
                "gap": {"cost": 0.29, "reversal": 0.18, "pace": 0.11},
                "selected_actions": [{"mechanic": "timer", "anchor": "N2"}, {"mechanic": "cost_hardening", "anchor": "N5"}],
                "limits": {"max_insert_nodes": 4, "max_change_summary": 2, "max_total_patches": 8},
                "patches": [
                    {
                        "patch_id": "p1",
                        "patch_type": "insert_node",
                        "where": {"after_node_id": "N2"},
                        "insert": {
                            "node": {
                                "node_id": "X_timer_01",
                                "type": "micro_timer",
                                "summary": "期限：…\\n失败后果：…\\n推动：…",
                                "_meta": {"mechanic": "timer"},
                            }
                        },
                    }
                ],
                "fill_nodes": [{"node_id": "X_timer_01", "mechanic": "timer", "max_words": 120}],
            },
            "warnings": [],
        },
    },
    "APPLY_AND_MEASURE": {
        "payload": {
            "book_id": "uuid",
            "chapter_id": "uuid",
            "plan_skill_run_id": "uuid",
            "selected_patch_ids": ["p1", "p2"],
            "auto_eval": True,
            "targets": {},
        },
        "result_done": {
            "repair_txn_id": "uuid",
            "new_outline_version": 13,
            "after_eval_run_id": "uuid",
            "before_eval_run_id": "uuid",
            "delta": {"overall": 0.08, "cost": 0.15, "reversal": 0.06},
        },
        "result_warn": {
            "repair_txn_id": "uuid",
            "new_outline_version": 13,
            "warnings": ["after_eval failed: LLM_TIMEOUT"],
        },
    },
    "DRAFT": {
        "payload": {
            "book_id": "uuid",
            "chapter_id": "uuid",
            "outline_version": 13,
            "llm_model": "qwen2.5:7b",
            "length_hint": "~3500cn",
        },
        "result_done": {"chapter_version_id": "uuid", "kind": "draft"},
    },
    "GUARD": {
        "payload": {
            "book_id": "uuid",
            "chapter_id": "uuid",
            "chapter_version_id": "uuid",
            "vec_high": 0.86,
            "vec_mid": 0.8,
            "ng_high": 0.2,
            "ng_mid": 0.12,
        },
        "result_done": {"skill_run_id": "uuid", "risk_level": "mid"},
        "skill_run_output": {
            "schema_name": "SIMILARITY_GUARD",
            "schema_ver": 1,
            "generated_at": "ISO8601",
            "result": {
                "risk_level": "mid",
                "top_hits": [
                    {
                        "chunk_id": "uuid",
                        "vector_score": 0.82,
                        "ngram_overlap": 0.14,
                        "matched_spans": [{"draft_range": [1200, 1330], "chunk_range": [80, 210]}],
                    }
                ],
                "recommendation": "建议轻度改写命中段落；保持事件不变，重写表达与细节",
            },
            "warnings": [],
        },
    },
    "REWRITE": {
        "payload": {"book_id": "uuid", "chapter_id": "uuid", "chapter_version_id": "uuid", "mode": "mid", "strength": 0.65},
        "result_done": {"chapter_version_id": "uuid", "kind": "rewrite"},
    },
    "BOOK_ANALYZE": {
        "payload": {"book_id": "uuid", "ma_window": 5, "vol_size": 40},
        "result_done": {"skill_run_id": "uuid", "coverage": {"chapters_with_metrics": 86, "chapters_total": 120}},
    },
    "EVOLVE": {
        "payload": {"min_samples": 8, "min_mean_overall": 0.05, "scope": {"arc_shape": "mid_slump"}},
        "result_done": {
            "created_variants": 3,
            "updated_variants": 1,
            "top_clusters": [{"key": "mid_slump|mid|unknown|raise_stakes+face_slap+cost_hardening", "n": 12, "mean_overall": 0.07}],
        },
    },
}
