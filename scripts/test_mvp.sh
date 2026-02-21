#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:17777}"
API_PREFIX="${API_PREFIX:-/v1}"

need_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "Missing command: $1" >&2; exit 2; }; }
need_cmd curl
need_cmd jq

get() {
  curl -sS "${BASE}${API_PREFIX}$1"
}

post() {
  curl -sS -X POST "${BASE}${API_PREFIX}$1" -H "Content-Type: application/json" -d "$2"
}

poll_job() {
  local job_id="$1"
  local max_tries="${2:-300}"
  local i=0
  while true; do
    local j
    j="$(get "/jobs/${job_id}")"
    local st stage prog
    st="$(echo "$j" | jq -r '.status')"
    stage="$(echo "$j" | jq -r '.stage // "-"')"
    prog="$(echo "$j" | jq -r '.progress.pct // .progress_value // 0')"
    echo "[job] ${job_id} status=${st} stage=${stage} progress=${prog}"

    if [[ "$st" == "succeeded" || "$st" == "done" ]]; then
      echo "$j"
      return 0
    fi
    if [[ "$st" == "failed" || "$st" == "canceled" ]]; then
      echo "$j" | jq '.error'
      return 1
    fi
    i=$((i + 1))
    if (( i > max_tries )); then
      echo "Timeout polling job ${job_id}" >&2
      return 1
    fi
    sleep 0.4
  done
}

echo "== 0) health =="
get "/health" | jq

echo "== 1) create book =="
BOOK_ID="$(post "/books" '{"title":"MVP Test Book","author":"tester","language":"zh"}' | jq -r '.book_id')"
echo "BOOK_ID=$BOOK_ID"

echo "== 2) create chapter =="
CHAPTER_ID="$(post "/books/${BOOK_ID}/chapters" '{"chapter_no":1,"title":"第一章","arc_id":"vol-1","arc_index":1}' | jq -r '.chapter_id')"
echo "CHAPTER_ID=$CHAPTER_ID"

echo "== 3) save outline v1 =="
SAVE_REQ="$(cat <<'JSON'
{
  "note": "v1 seed",
  "outline": {
    "schema_name": "OUTLINE_DETAIL",
    "schema_ver": 1,
    "chapter_no": 1,
    "chapter_title": "第一章",
    "template_ref": {},
    "nodes": [
      {
        "node_id": "N1",
        "type": "hook",
        "summary": "主角在雨夜收到匿名信，信中提到失踪父亲。",
        "beats": [],
        "characters": ["主角"],
        "world_facts": [],
        "plot_hooks": ["父亲失踪"],
        "conflict": {"goal_clarity": 0.4, "opposition_strength": 0.2, "stake_level": 0.4, "cost_level": 0.0, "time_pressure": 0.2, "info_gap": 0.5, "reversal_power": 0.1},
        "constraints": {"max_words": 180, "must_exist": true},
        "_meta": {}
      },
      {
        "node_id": "N2",
        "type": "turning_point",
        "summary": "主角来到废弃车站，被不明势力围堵，意识到被引入局。",
        "beats": [],
        "characters": ["主角"],
        "world_facts": [],
        "plot_hooks": ["陷阱"],
        "conflict": {"goal_clarity": 0.5, "opposition_strength": 0.6, "stake_level": 0.6, "cost_level": 0.3, "time_pressure": 0.4, "info_gap": 0.5, "reversal_power": 0.6},
        "constraints": {"max_words": 180, "must_exist": true},
        "_meta": {}
      },
      {
        "node_id": "N3",
        "type": "cliffhanger",
        "summary": "主角脱身后手机多出父亲语音：别相信任何人。",
        "beats": [],
        "characters": ["主角"],
        "world_facts": [],
        "plot_hooks": ["父亲语音"],
        "conflict": {"goal_clarity": 0.5, "opposition_strength": 0.4, "stake_level": 0.6, "cost_level": 0.2, "time_pressure": 0.2, "info_gap": 0.7, "reversal_power": 0.4},
        "constraints": {"max_words": 180, "must_exist": true, "must_open_hook": true},
        "_meta": {}
      }
    ],
    "global_constraints": {"must_have_cost": true, "must_end_with_hook": true}
  }
}
JSON
)"
SAVE_OUT="$(post "/chapters/${CHAPTER_ID}/outline_detail/save" "$SAVE_REQ")"
echo "$SAVE_OUT" | jq
V1="$(echo "$SAVE_OUT" | jq -r '.version')"
echo "OUTLINE_V1=${V1}"

echo "== 4) eval tension (outline mode) =="
EVAL_REQ='{"chapter_version_id":"00000000-0000-0000-0000-000000000000","input_mode":"outline","schema_ver":1}'
EVAL_JOB="$(post "/chapters/${CHAPTER_ID}/tension/eval" "$EVAL_REQ" | jq -r '.job_id')"
echo "EVAL_JOB=${EVAL_JOB}"
EVAL_JOB_JSON="$(poll_job "$EVAL_JOB")"
BEFORE_EVAL_RUN_ID="$(echo "$EVAL_JOB_JSON" | jq -r '.result.skill_run_id')"
echo "BEFORE_EVAL_RUN_ID=${BEFORE_EVAL_RUN_ID}"

echo "== 5) control plan =="
PLAN_REQ='{
  "targets":{"conflict_strength":0.78,"stakes":0.74,"cost":0.70,"pace":0.72,"reversal":0.68,"hook":0.70},
  "style":{"face_slap_density":0.18,"upgrade_density":0.14},
  "schema_ver":1
}'
PLAN_JOB="$(post "/chapters/${CHAPTER_ID}/tension/control_plan" "$PLAN_REQ" | jq -r '.job_id')"
echo "PLAN_JOB=${PLAN_JOB}"
PLAN_JOB_JSON="$(poll_job "$PLAN_JOB")"
PLAN_RUN_ID="$(echo "$PLAN_JOB_JSON" | jq -r '.result.skill_run_id')"
echo "PLAN_RUN_ID=${PLAN_RUN_ID}"

echo "== 6) fetch patches =="
PLAN_SR="$(get "/skill_runs/${PLAN_RUN_ID}")"
PATCH_COUNT="$(echo "$PLAN_SR" | jq '.output.result.patches | length')"
echo "PATCH_COUNT=${PATCH_COUNT}"
if (( PATCH_COUNT < 1 )); then
  echo "No patches produced by PLAN job." >&2
  exit 1
fi
P1="$(echo "$PLAN_SR" | jq -r '.output.result.patches[0].patch_id')"
P2="$(echo "$PLAN_SR" | jq -r '.output.result.patches[1].patch_id // empty')"
if [[ -n "$P2" ]]; then
  SELECTED_PATCH_IDS="[\"${P1}\",\"${P2}\"]"
else
  SELECTED_PATCH_IDS="[\"${P1}\"]"
fi
echo "SELECTED_PATCH_IDS=${SELECTED_PATCH_IDS}"

echo "== 7) apply + measure =="
APPLY_REQ="$(cat <<JSON
{
  "plan_skill_run_id": "${PLAN_RUN_ID}",
  "selected_patch_ids": ${SELECTED_PATCH_IDS},
  "auto_eval": true,
  "targets": {"conflict_strength":0.78,"stakes":0.74,"cost":0.70,"pace":0.72,"reversal":0.68,"hook":0.70}
}
JSON
)"
APPLY_SUBMIT="$(post "/chapters/${CHAPTER_ID}/outline_detail/apply_patches" "$APPLY_REQ")"
echo "$APPLY_SUBMIT" | jq
APPLY_JOB="$(echo "$APPLY_SUBMIT" | jq -r '.apply_job_id // .job_id')"
echo "APPLY_JOB=${APPLY_JOB}"
APPLY_JOB_JSON="$(poll_job "$APPLY_JOB")"
echo "$APPLY_JOB_JSON" | jq '.result'

NEW_OUTLINE_VERSION="$(echo "$APPLY_JOB_JSON" | jq -r '.result.new_outline_version')"
BEFORE_EVAL_2="$(echo "$APPLY_JOB_JSON" | jq -r '.result.before_eval_run_id // empty')"
AFTER_EVAL_RUN_ID="$(echo "$APPLY_JOB_JSON" | jq -r '.result.after_eval_run_id // empty')"

echo "== 8) verify new outline version =="
get "/chapters/${CHAPTER_ID}/outline_detail?version=${NEW_OUTLINE_VERSION}" | jq '.content.nodes | length'

echo "== 9) summary =="
echo "BOOK_ID=${BOOK_ID}"
echo "CHAPTER_ID=${CHAPTER_ID}"
echo "PLAN_RUN_ID=${PLAN_RUN_ID}"
echo "NEW_OUTLINE_VERSION=${NEW_OUTLINE_VERSION}"
echo "BEFORE_EVAL_RUN_ID=${BEFORE_EVAL_RUN_ID}"
echo "BEFORE_EVAL_2=${BEFORE_EVAL_2}"
echo "AFTER_EVAL_RUN_ID=${AFTER_EVAL_RUN_ID}"
echo "DELTA="
echo "$APPLY_JOB_JSON" | jq '.result.delta // {}'

if [[ -n "${BEFORE_EVAL_2}" && -n "${AFTER_EVAL_RUN_ID}" ]]; then
  echo "== 10) eval compare =="
  get "/chapters/${CHAPTER_ID}/eval/compare?before_run_id=${BEFORE_EVAL_2}&after_run_id=${AFTER_EVAL_RUN_ID}" | jq
fi

echo "✅ MVP pipeline OK"

