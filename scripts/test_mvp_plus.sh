#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:17777}"
API_PREFIX="${API_PREFIX:-/v1}"
STRICT_DELTA="${STRICT_DELTA:-0}"
CLEANUP="${CLEANUP:-0}"
BUNDLE_ON_FAIL="${BUNDLE_ON_FAIL:-1}"
BUNDLE_DIR="${BUNDLE_DIR:-./mvp_diagnose}"
MAX_POLL_TRIES="${MAX_POLL_TRIES:-300}"
RUN_STRUCTURE_VERIFY="${RUN_STRUCTURE_VERIFY:-1}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

need_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1" >&2; exit 2; }; }
need_cmd curl
need_cmd jq

mkdir -p "$BUNDLE_DIR"

get() {
  curl -sS "${BASE}${API_PREFIX}$1"
}

post() {
  curl -sS -X POST "${BASE}${API_PREFIX}$1" -H "Content-Type: application/json" -d "$2"
}

dump_json() {
  local name="$1"
  local content="$2"
  echo "$content" | jq . > "${BUNDLE_DIR}/${name}.json" 2>/dev/null || echo "$content" > "${BUNDLE_DIR}/${name}.raw"
}

poll_job() {
  local job_id="$1"
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
      echo "$j"
      return 3
    fi
    i=$((i + 1))
    if (( i > MAX_POLL_TRIES )); then
      echo "Timeout polling job ${job_id}" >&2
      echo "$j"
      return 4
    fi
    sleep 0.3
  done
}

cleanup_book() {
  if [[ "${CLEANUP}" != "1" || -z "${BOOK_ID:-}" ]]; then
    return 0
  fi
  if curl -sS -X DELETE "${BASE}${API_PREFIX}/books/${BOOK_ID}" >/dev/null 2>&1; then
    echo "cleanup: deleted book ${BOOK_ID}"
  else
    echo "cleanup: DELETE /books/{id} not implemented, skip"
  fi
}

bundle_on_fail() {
  local reason="$1"
  [[ "$BUNDLE_ON_FAIL" == "1" ]] || return 0
  echo "== DIAG BUNDLE: ${reason} =="

  dump_json "health" "$(get "/health" || echo '{}')"
  dump_json "jobs_failed_recent" "$(get "/jobs?status=failed&limit=30" || echo '{}')"
  dump_json "jobs_running_recent" "$(get "/jobs?status=running&limit=30" || echo '{}')"
  dump_json "jobs_done_recent" "$(get "/jobs?status=succeeded&limit=30" || echo '{}')"

  if [[ -n "${EVAL_JOB:-}" ]]; then dump_json "job_eval" "$(get "/jobs/${EVAL_JOB}" || echo '{}')"; fi
  if [[ -n "${PLAN_JOB:-}" ]]; then dump_json "job_plan" "$(get "/jobs/${PLAN_JOB}" || echo '{}')"; fi
  if [[ -n "${APPLY_JOB:-}" ]]; then dump_json "job_apply" "$(get "/jobs/${APPLY_JOB}" || echo '{}')"; fi
  if [[ -n "${BEFORE_EVAL_RUN_ID:-}" ]]; then dump_json "skill_eval_before" "$(get "/skill_runs/${BEFORE_EVAL_RUN_ID}" || echo '{}')"; fi
  if [[ -n "${PLAN_RUN_ID:-}" ]]; then dump_json "skill_plan" "$(get "/skill_runs/${PLAN_RUN_ID}" || echo '{}')"; fi
  if [[ -n "${AFTER_EVAL_RUN_ID:-}" ]]; then dump_json "skill_eval_after" "$(get "/skill_runs/${AFTER_EVAL_RUN_ID}" || echo '{}')"; fi
  if [[ -n "${CHAPTER_ID:-}" && -n "${NEW_V:-}" ]]; then
    dump_json "outline_v2" "$(get "/chapters/${CHAPTER_ID}/outline_detail?version=${NEW_V}" || echo '{}')"
  fi

  cat > "${BUNDLE_DIR}/ids.txt" <<EOF
BASE=${BASE}
API_PREFIX=${API_PREFIX}
STRICT_DELTA=${STRICT_DELTA}
CLEANUP=${CLEANUP}
BOOK_ID=${BOOK_ID:-}
CHAPTER_ID=${CHAPTER_ID:-}
EVAL_JOB=${EVAL_JOB:-}
PLAN_JOB=${PLAN_JOB:-}
APPLY_JOB=${APPLY_JOB:-}
BEFORE_EVAL_RUN_ID=${BEFORE_EVAL_RUN_ID:-}
AFTER_EVAL_RUN_ID=${AFTER_EVAL_RUN_ID:-}
PLAN_RUN_ID=${PLAN_RUN_ID:-}
NEW_OUTLINE_VERSION=${NEW_V:-}
EOF

  echo "Saved diagnose bundle to: ${BUNDLE_DIR}"
}

on_exit() {
  local code=$?
  if (( code != 0 )); then
    bundle_on_fail "script_exit_code=${code}"
  else
    cleanup_book
  fi
  exit $code
}
trap on_exit EXIT

echo "== 0) health =="
HEALTH="$(get "/health")"
echo "$HEALTH" | jq
dump_json "health" "$HEALTH"

echo "== 1) create book =="
BOOK_ID="$(post "/books" '{"title":"MVP Test Book","author":"tester","language":"zh"}' | jq -r '.book_id')"
echo "BOOK_ID=${BOOK_ID}"

echo "== 2) create chapter =="
CHAPTER_ID="$(post "/books/${BOOK_ID}/chapters" '{"chapter_no":1,"title":"第一章","arc_id":"vol-1","arc_index":1}' | jq -r '.chapter_id')"
echo "CHAPTER_ID=${CHAPTER_ID}"

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
[[ "$V1" == "1" ]] || { echo "Expected outline version=1, got ${V1}" >&2; exit 1; }

echo "== 4) eval tension (job) =="
EVAL_REQ='{"chapter_version_id":"00000000-0000-0000-0000-000000000000","input_mode":"outline","schema_ver":1}'
EVAL_JOB="$(post "/chapters/${CHAPTER_ID}/tension/eval" "$EVAL_REQ" | jq -r '.job_id')"
echo "EVAL_JOB=${EVAL_JOB}"
EVAL_JOB_JSON="$(poll_job "$EVAL_JOB")" || { dump_json "job_eval" "${EVAL_JOB_JSON:-{}}"; exit 1; }
dump_json "job_eval" "$EVAL_JOB_JSON"
BEFORE_EVAL_RUN_ID="$(echo "$EVAL_JOB_JSON" | jq -r '.result.skill_run_id')"
dump_json "skill_eval_before" "$(get "/skill_runs/${BEFORE_EVAL_RUN_ID}")"

echo "== 5) control plan (job) =="
PLAN_REQ='{
  "targets":{"conflict_strength":0.78,"stakes":0.74,"cost":0.70,"pace":0.72,"reversal":0.68,"hook":0.70},
  "style":{"face_slap_density":0.18,"upgrade_density":0.14},
  "schema_ver":1
}'
PLAN_JOB="$(post "/chapters/${CHAPTER_ID}/tension/control_plan" "$PLAN_REQ" | jq -r '.job_id')"
echo "PLAN_JOB=${PLAN_JOB}"
PLAN_JOB_JSON="$(poll_job "$PLAN_JOB")" || { dump_json "job_plan" "${PLAN_JOB_JSON:-{}}"; exit 1; }
dump_json "job_plan" "$PLAN_JOB_JSON"
PLAN_RUN_ID="$(echo "$PLAN_JOB_JSON" | jq -r '.result.skill_run_id')"
PLAN_SR="$(get "/skill_runs/${PLAN_RUN_ID}")"
dump_json "skill_plan" "$PLAN_SR"

PATCH_COUNT="$(echo "$PLAN_SR" | jq '.output.result.patches | length')"
(( PATCH_COUNT >= 1 )) || { echo "No patches produced by PLAN job." >&2; exit 1; }
P1="$(echo "$PLAN_SR" | jq -r '.output.result.patches[0].patch_id')"
P2="$(echo "$PLAN_SR" | jq -r '.output.result.patches[1].patch_id // empty')"
if [[ -n "$P2" ]]; then
  SELECTED_PATCHES="$(jq -n --arg p1 "$P1" --arg p2 "$P2" '[ $p1, $p2 ]')"
else
  SELECTED_PATCHES="$(jq -n --arg p1 "$P1" '[ $p1 ]')"
fi

echo "== 6) apply + measure (job) =="
APPLY_REQ="$(jq -n --arg plan "$PLAN_RUN_ID" --argjson sp "$SELECTED_PATCHES" '{
  plan_skill_run_id:$plan,
  selected_patch_ids:$sp,
  auto_eval:true,
  targets:{"conflict_strength":0.78,"stakes":0.74,"cost":0.70,"pace":0.72,"reversal":0.68,"hook":0.70}
}')"
APPLY_SUBMIT="$(post "/chapters/${CHAPTER_ID}/outline_detail/apply_patches" "$APPLY_REQ")"
APPLY_JOB="$(echo "$APPLY_SUBMIT" | jq -r '.apply_job_id // .job_id')"
echo "APPLY_JOB=${APPLY_JOB}"
APPLY_JOB_JSON="$(poll_job "$APPLY_JOB")" || { dump_json "job_apply" "${APPLY_JOB_JSON:-{}}"; exit 1; }
dump_json "job_apply" "$APPLY_JOB_JSON"

NEW_V="$(echo "$APPLY_JOB_JSON" | jq -r '.result.new_outline_version')"
AFTER_EVAL_RUN_ID="$(echo "$APPLY_JOB_JSON" | jq -r '.result.after_eval_run_id')"
DELTA_JSON="$(echo "$APPLY_JOB_JSON" | jq '.result.delta')"
dump_json "skill_eval_after" "$(get "/skill_runs/${AFTER_EVAL_RUN_ID}")"
dump_json "outline_v2" "$(get "/chapters/${CHAPTER_ID}/outline_detail?version=${NEW_V}")"

echo "== 7) strict delta check (optional) =="
if [[ "$STRICT_DELTA" == "1" ]]; then
  ov="$(echo "$DELTA_JSON" | jq -r '.overall // 0')"
  cost="$(echo "$DELTA_JSON" | jq -r '.cost // 0')"
  rev="$(echo "$DELTA_JSON" | jq -r '.reversal // 0')"
  if ! awk -v ov="$ov" -v c="$cost" -v r="$rev" 'BEGIN{ exit ! (ov>=0 && (c>=0.05 || r>=0.05)); }'; then
    echo "STRICT_DELTA failed: overall=${ov}, cost=${cost}, reversal=${rev}" >&2
    exit 1
  fi
  echo "STRICT_DELTA passed."
fi

echo "✅ MVP+ pipeline OK"

if [[ "${RUN_STRUCTURE_VERIFY}" == "1" ]]; then
  echo "== 8) structure template auto-builder verify =="
  if [[ -x "${REPO_ROOT}/engine/.venv/Scripts/python.exe" ]]; then
    "${REPO_ROOT}/engine/.venv/Scripts/python.exe" "${REPO_ROOT}/scripts/verify_structure_templates.py"
  elif command -v python3 >/dev/null 2>&1; then
    python3 "${REPO_ROOT}/scripts/verify_structure_templates.py"
  elif command -v python >/dev/null 2>&1; then
    python "${REPO_ROOT}/scripts/verify_structure_templates.py"
  else
    echo "No python found for structure verify script" >&2
    exit 2
  fi
fi
