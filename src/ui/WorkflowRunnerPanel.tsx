import { useEffect, useMemo, useState } from "react";

type Props = {
  bookId: string;
  chapterId: string;
};

function statusClass(status: string): string {
  const s = String(status || "").toLowerCase();
  if (s === "succeeded") return "ok";
  if (s === "failed") return "bad";
  if (s === "running") return "running";
  return "idle";
}

function hasEventsJsonError(step: any): boolean {
  const msg = String(step?.error?.message || "").toUpperCase();
  return msg.includes("EVENTS_JSON");
}

export function WorkflowRunnerPanel({ bookId, chapterId }: Props) {
  const [wfDef, setWfDef] = useState<any>(null);
  const [wfDryRun, setWfDryRun] = useState(true);
  const [wfRunResult, setWfRunResult] = useState<any>(null);
  const [draftRunResult, setDraftRunResult] = useState<any>(null);
  const [wfRunDetail, setWfRunDetail] = useState<any>(null);
  const [wfReason, setWfReason] = useState("rollback from desktop");
  const [selectedStepIndex, setSelectedStepIndex] = useState<number>(-1);
  const [rewriteLevel, setRewriteLevel] = useState<"L1" | "L2" | "L3">("L1");
  const [rewriteResult, setRewriteResult] = useState<any>(null);
  const [rewriteAcceptResult, setRewriteAcceptResult] = useState<any>(null);
  const [draftsList, setDraftsList] = useState<any>(null);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");

  const steps = useMemo(() => ((wfRunDetail?.steps || []) as any[]), [wfRunDetail]);
  const stepByNode = useMemo(() => {
    const m: Record<string, any> = {};
    for (const s of steps) {
      const k = String(s?.node_id || "");
      if (k) m[k] = s;
    }
    return m;
  }, [steps]);
  const pacingData = useMemo(() => {
    const fromPacer = stepByNode["pacing_controller"]?.output?.pacer;
    const fromCompose = stepByNode["compose_prompt"]?.output?.prompt_blocks?.pacer;
    return (fromPacer && typeof fromPacer === "object" ? fromPacer : fromCompose) || null;
  }, [stepByNode]);
  const tasksIntent = useMemo(() => {
    const fromIntent = stepByNode["task_intent_mapper"]?.output?.final_tasks_intent;
    const fromCompose = stepByNode["compose_prompt"]?.output?.prompt_blocks?.tasks_intent;
    const arr = fromIntent || fromCompose;
    return Array.isArray(arr) ? arr : [];
  }, [stepByNode]);
  const executedTasks = useMemo(() => {
    const fromValidate = stepByNode["validate_executed_tasks"]?.output?.executed_tasks_valid;
    const fromExtract = stepByNode["post_extract_actions"]?.output?.extracted_actions?.executed_tasks;
    const arr = fromValidate || fromExtract;
    return Array.isArray(arr) ? arr : [];
  }, [stepByNode]);
  const sourceDraftId = useMemo(() => {
    return String(stepByNode["commit_draft_and_logs"]?.output?.commit_result?.draft_id || "").trim();
  }, [stepByNode]);
  const sourceChapterText = useMemo(() => {
    const s1 = String(stepByNode["llm_generate"]?.output?.llm_output?.chapter_text || "").trim();
    if (s1) return s1;
    const s2 = String(stepByNode["llm_generate"]?.output?.llm_output?.text || "").trim();
    return s2;
  }, [stepByNode]);
  const sourceFactLock = useMemo(() => {
    const rows = tasksIntent.map((t: any) => ({
      task_type: String(t?.type || t?.task_type || ""),
      evidence: Array.isArray(t?.evidence_required) ? t.evidence_required.join(" | ") : "",
    }));
    return {
      must_preserve: {
        events: rows.slice(0, 8).map((x: any) => String(x?.evidence || x?.task_type || "")),
      },
      must_not_add: { new_characters: true, new_magic_system: true },
      must_keep_tasks_evidence: rows.slice(0, 12),
    };
  }, [tasksIntent]);
  const evidenceRows = useMemo(() => {
    const execByTask: Record<string, any> = {};
    for (const ex of executedTasks) {
      const k = String(ex?.task_id || "");
      if (!k) continue;
      execByTask[k] = ex;
    }
    const rows = tasksIntent.map((t: any) => {
      const taskId = String(t?.task_id || "");
      const ex = taskId ? execByTask[taskId] : null;
      const evidence = String(ex?.evidence || "").trim();
      const hasRequired = Array.isArray(t?.evidence_required) ? t.evidence_required.length > 0 : false;
      let status: "green" | "yellow" | "red" = "red";
      let statusLabel = "missing";
      if (ex && evidence) {
        status = "green";
        statusLabel = "evidence ok";
      } else if (ex && !evidence) {
        status = "yellow";
        statusLabel = "executed, weak evidence";
      } else if (!hasRequired) {
        status = "yellow";
        statusLabel = "no evidence_required";
      }
      return {
        taskId,
        type: String(t?.type || t?.task_type || ""),
        intent: String(t?.intent || ""),
        evidenceRequired: Array.isArray(t?.evidence_required) ? t.evidence_required : [],
        bannedMoves: Array.isArray(t?.banned_moves) ? t.banned_moves : [],
        executed: !!ex,
        evidence,
        status,
        statusLabel,
      };
    });
    return rows;
  }, [tasksIntent, executedTasks]);
  const evidenceSummary = useMemo(() => {
    let green = 0;
    let yellow = 0;
    let red = 0;
    for (const r of evidenceRows) {
      if (r.status === "green") green += 1;
      else if (r.status === "yellow") yellow += 1;
      else red += 1;
    }
    return { total: evidenceRows.length, green, yellow, red };
  }, [evidenceRows]);
  const selectedStep = useMemo(() => {
    if (!Array.isArray(steps) || steps.length === 0) return null;
    if (selectedStepIndex >= 0 && selectedStepIndex < steps.length) return steps[selectedStepIndex];
    const failedIdx = steps.findIndex((s: any) => String(s?.status || "").toLowerCase() === "failed");
    return steps[failedIdx >= 0 ? failedIdx : steps.length - 1] || null;
  }, [steps, selectedStepIndex]);

  async function loadWorkflowDefinition() {
    setBusy("workflow:definition");
    setErr("");
    try {
      const out = await window.desktopApi.workflowDefinition({ workflow_id: "draft_runner_v1" });
      setWfDef(out || {});
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runWorkflow() {
    if (!bookId || !chapterId) return;
    setBusy("workflow:run");
    setErr("");
    try {
      const idem = `desktop-wf-${bookId}-${chapterId}-${wfDryRun ? "dry" : "real"}`;
      const out = await window.desktopApi.workflowRun({
        workflow_id: "draft_runner_v1",
        dry_run: wfDryRun,
        reuse_if_exists: true,
        idempotency_key: idem,
        input: {
          book_id: bookId,
          chapter_id: chapterId,
          intent_confirmed: "桌面端 Workflow Runner 验证",
          force_stub_llm: !wfDryRun,
        },
      });
      setWfRunResult(out || {});
      const rid = String(out?.run_id || "");
      if (rid) {
        const detail = await window.desktopApi.workflowGetRun({ run_id: rid });
        setWfRunDetail(detail || {});
        setSelectedStepIndex(-1);
      }
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runDraftApi() {
    if (!bookId) return;
    setBusy("draft:run");
    setErr("");
    try {
      const out = await window.desktopApi.draftRun({
        book_id: bookId,
        chapter_id: chapterId || undefined,
        intent_confirmed: "桌面端 Draft API 验证",
        dry_run: false,
        reuse_if_exists: true,
      });
      setDraftRunResult(out || {});
      const rid = String(out?.run_id || out?.output?.run_id || "").trim();
      if (rid) {
        const detail = await window.desktopApi.workflowGetRun({ run_id: rid });
        setWfRunResult((m: any) => ({ ...(m || {}), run_id: rid, from: "draft_run" }));
        setWfRunDetail(detail || {});
        setSelectedStepIndex(-1);
      }
      await loadChapterDrafts();
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function loadWorkflowRunDetail() {
    const rid = String(wfRunResult?.run_id || "").trim();
    if (!rid) return;
    setBusy("workflow:get-run");
    setErr("");
    try {
      const detail = await window.desktopApi.workflowGetRun({ run_id: rid });
      setWfRunDetail(detail || {});
      setSelectedStepIndex(-1);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function rollbackWorkflowRun() {
    const rid = String(wfRunResult?.run_id || "").trim();
    if (!rid) return;
    setBusy("workflow:rollback");
    setErr("");
    try {
      const out = await window.desktopApi.workflowRollbackRun({
        run_id: rid,
        body: { reason: wfReason || "rollback from desktop" },
      });
      setWfRunResult((prev: any) => ({ ...(prev || {}), rollback: out || {} }));
      await loadWorkflowRunDetail();
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function loadChapterDrafts() {
    if (!chapterId) return;
    setBusy("drafts:list");
    setErr("");
    try {
      const out = await window.desktopApi.draftListVersions({ chapter_id: chapterId });
      setDraftsList(out || {});
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runRewrite() {
    if (!bookId || !chapterId) return;
    if (!sourceDraftId && !sourceChapterText) {
      setErr("No source draft/text found from latest workflow run.");
      return;
    }
    setBusy("rewrite:run");
    setErr("");
    try {
      const out = await window.desktopApi.rewriteRun({
        book_id: bookId,
        chapter_id: chapterId,
        source_draft_id: sourceDraftId || undefined,
        level: rewriteLevel,
        text: sourceChapterText || undefined,
        fact_lock: sourceFactLock,
        style_profile: {
          preferred: ["短句", "动作优先", "减少解释句"],
          banned_phrases: ["忽然间", "不由得", "只见"],
          signature: ["冷幽默", "反问句收束"],
        },
      });
      setRewriteResult(out || {});
      setRewriteAcceptResult(null);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function acceptRewrite() {
    const rewrittenText = String(rewriteResult?.rewritten_text || "").trim();
    const srcId = String(rewriteResult?.source_draft_id || sourceDraftId || "").trim();
    if (!rewrittenText || !srcId) {
      setErr("Rewrite result or source draft id is missing.");
      return;
    }
    setBusy("rewrite:accept");
    setErr("");
    try {
      const out = await window.desktopApi.rewriteAccept({
        source_draft_id: srcId,
        rewritten_text: rewrittenText,
        level: rewriteLevel,
        rewrite_report: rewriteResult?.rewrite_report || {},
        diff: rewriteResult?.diff || {},
      });
      setRewriteAcceptResult(out || {});
      await loadChapterDrafts();
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  function rejectRewrite() {
    setRewriteResult(null);
    setRewriteAcceptResult(null);
  }

  async function activateDraft(draftId: string) {
    if (!chapterId || !draftId) return;
    setBusy("drafts:activate");
    setErr("");
    try {
      await window.desktopApi.draftSelect({ chapter_id: chapterId, draft_id: draftId, selected_by: "user", reason: "desktop select draft" });
      await loadChapterDrafts();
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  useEffect(() => {
    void loadWorkflowDefinition();
  }, []);

  useEffect(() => {
    if (chapterId) void loadChapterDrafts();
  }, [chapterId]);

  return (
    <div className="card" style={{ marginTop: 10 }}>
      <div className="row" style={{ marginBottom: 6 }}>
        <h4 style={{ margin: 0 }}>Workflow Runner</h4>
        <span className="small">draft_runner_v1 · {busy || "idle"}</span>
      </div>
      <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
        <label className="agent-checkbox">
          <input type="checkbox" checked={wfDryRun} onChange={(e) => setWfDryRun(e.target.checked)} />
          dry_run
        </label>
        <button onClick={() => void loadWorkflowDefinition()}>Load Definition</button>
        <button onClick={() => void runWorkflow()} disabled={!bookId || !chapterId}>Run Workflow</button>
        <button onClick={() => void runDraftApi()} disabled={!bookId || !chapterId}>Run Draft API</button>
        <button onClick={() => void loadWorkflowRunDetail()} disabled={!wfRunResult?.run_id}>Refresh Run Detail</button>
        <label>
          rollback reason
          <input value={wfReason} onChange={(e) => setWfReason(e.target.value)} />
        </label>
        <button onClick={() => void rollbackWorkflowRun()} disabled={!wfRunResult?.run_id || !!wfDryRun}>Rollback Run</button>
      </div>
      {err ? <div className="small" style={{ color: "#b91c1c", marginTop: 6 }}>{err}</div> : null}

      {steps.length > 0 ? (
        <div style={{ marginTop: 10 }}>
          <div className="small">Step Timeline</div>
          <div className="wf-timeline">
            {steps.map((s: any, idx: number) => {
              const nid = String(s?.node_id || `step-${idx}`);
              const st = String(s?.status || "idle");
              return (
                <button
                  key={`${nid}-${idx}`}
                  type="button"
                  className={`wf-step ${statusClass(st)} ${selectedStepIndex === idx ? "selected" : ""}`}
                  title={`${nid} · ${st}`}
                  onClick={() => setSelectedStepIndex(idx)}
                >
                  <div className="wf-step-index">{idx + 1}</div>
                  <div className="wf-step-name">{nid}</div>
                  <div className="wf-step-status">{st}</div>
                  {hasEventsJsonError(s) ? <div className="wf-step-badge">EVENTS_JSON</div> : null}
                </button>
              );
            })}
          </div>
          {selectedStep ? (
            <div style={{ marginTop: 8 }}>
              <div className="small">
                Selected Step: <span className="mono">{String(selectedStep?.node_id || "-")}</span> ·{" "}
                <span className="mono">{String(selectedStep?.status || "-")}</span>
              </div>
              <div className="agent-grid" style={{ marginTop: 6 }}>
                <div className="agent-col">
                  <div className="small">input</div>
                  <pre>{JSON.stringify(selectedStep?.input ?? {}, null, 2)}</pre>
                </div>
                <div className="agent-col">
                  <div className="small">output</div>
                  <pre>{JSON.stringify(selectedStep?.output ?? {}, null, 2)}</pre>
                </div>
                <div className="agent-col">
                  <div className="small">error / metrics</div>
                  <pre>{JSON.stringify({ error: selectedStep?.error ?? null, metrics: selectedStep?.metrics ?? {} }, null, 2)}</pre>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      <div style={{ marginTop: 10 }}>
        <div className="small">Pacer & Task Intent QA</div>
        <div className="agent-grid" style={{ marginTop: 6 }}>
          <div className="agent-col">
            <div className="small">pacer</div>
            <pre>{JSON.stringify(pacingData ?? {}, null, 2)}</pre>
          </div>
          <div className="agent-col">
            <div className="small">
              evidence check: total={evidenceSummary.total} ·
              <span style={{ color: "#15803d" }}> green={evidenceSummary.green}</span> ·
              <span style={{ color: "#b45309" }}> yellow={evidenceSummary.yellow}</span> ·
              <span style={{ color: "#b91c1c" }}> red={evidenceSummary.red}</span>
            </div>
            <div className="scroll" style={{ maxHeight: 260 }}>
              {evidenceRows.length === 0 ? <div className="hint">No task intent rows found in run detail.</div> : null}
              {evidenceRows.map((r) => (
                <div key={r.taskId || `${r.type}-${r.intent}`} className="agent-audit-row">
                  <div className="small mono">{r.taskId || "-"}</div>
                  <div className="small"><strong>{r.type || "-"}</strong></div>
                  <div
                    className="small"
                    style={{ color: r.status === "green" ? "#15803d" : r.status === "yellow" ? "#b45309" : "#b91c1c" }}
                  >
                    {r.statusLabel}
                  </div>
                  {r.intent ? <div className="small">{r.intent}</div> : null}
                  {r.evidenceRequired.length ? (
                    <div className="small">required: {r.evidenceRequired.join(" | ")}</div>
                  ) : null}
                  {r.bannedMoves.length ? (
                    <div className="small">banned: {r.bannedMoves.join(" | ")}</div>
                  ) : null}
                  {r.evidence ? <div className="small">evidence: {r.evidence}</div> : null}
                </div>
              ))}
            </div>
          </div>
          <div className="agent-col">
            <div className="small">executed_tasks</div>
            <pre>{JSON.stringify(executedTasks, null, 2)}</pre>
          </div>
        </div>
      </div>

      <div style={{ marginTop: 10 }}>
        <div className="row" style={{ marginBottom: 6 }}>
          <div className="small">De-AI Rewrite (optional)</div>
          <label>
            level
            <select value={rewriteLevel} onChange={(e) => setRewriteLevel(String(e.target.value) as any)}>
              <option value="L1">L1 轻微润色</option>
              <option value="L2">L2 强去味</option>
              <option value="L3">L3 风格化重写</option>
            </select>
          </label>
          <button onClick={() => void runRewrite()} disabled={!bookId || !chapterId}>Run Rewrite</button>
          <button onClick={() => void acceptRewrite()} disabled={!rewriteResult?.rewritten_text}>Accept Rewrite</button>
          <button onClick={rejectRewrite} disabled={!rewriteResult}>Reject</button>
          <button onClick={() => void loadChapterDrafts()} disabled={!chapterId}>Refresh Drafts</button>
        </div>
        <div className="agent-grid">
          <div className="agent-col">
            <div className="small">rewrite result</div>
            <pre>{JSON.stringify(rewriteResult, null, 2)}</pre>
          </div>
          <div className="agent-col">
            <div className="small">accept result</div>
            <pre>{JSON.stringify(rewriteAcceptResult, null, 2)}</pre>
          </div>
          <div className="agent-col">
            <div className="small">diff preview</div>
            <div className="scroll" style={{ maxHeight: 260 }}>
              {Array.isArray(rewriteResult?.diff?.ops) && rewriteResult.diff.ops.length ? (
                rewriteResult.diff.ops.slice(0, 30).map((op: any, idx: number) => (
                  <div key={idx} className="agent-audit-row">
                    <div className="small"><strong>{String(op?.op || "-")}</strong></div>
                    <div className="small mono">a[{String((op?.a_idx || []).join(", "))}] → b[{String((op?.b_idx || []).join(", "))}]</div>
                    <div className="small">before: {Array.isArray(op?.a_text) ? op.a_text.join(" / ").slice(0, 180) : "-"}</div>
                    <div className="small">after: {Array.isArray(op?.b_text) ? op.b_text.join(" / ").slice(0, 180) : "-"}</div>
                  </div>
                ))
              ) : (
                <div className="hint">No diff ops</div>
              )}
            </div>
          </div>
        </div>
        <div style={{ marginTop: 8 }}>
          <div className="small">chapter drafts</div>
          <div className="scroll" style={{ maxHeight: 220 }}>
            {!Array.isArray(draftsList?.items) || draftsList.items.length === 0 ? (
              <div className="hint">No drafts found.</div>
            ) : (
              draftsList.items.map((d: any) => {
                const did = String(d?.draft_id || "");
                const isActive = !!d?.is_active;
                return (
                  <div key={did} className="agent-audit-row">
                    <div className="small mono">{did || "-"}</div>
                    <div className="small">variant: {String(d?.variant || "-")}</div>
                    <div className="small">rewrite: {String(d?.rewrite_level || "-")}</div>
                    <div className="small">len: {String(d?.text_length || "-")}</div>
                    <div className="small" style={{ color: isActive ? "#15803d" : "#6b7280" }}>
                      {isActive ? "active" : "inactive"}
                    </div>
                    <button onClick={() => void activateDraft(did)} disabled={!did || isActive}>
                      Set Active
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      <div className="agent-grid" style={{ marginTop: 8 }}>
        <div className="agent-col">
          <div className="small">definition</div>
          <pre>{JSON.stringify(wfDef, null, 2)}</pre>
        </div>
        <div className="agent-col">
          <div className="small">draft run result</div>
          <pre>{JSON.stringify(draftRunResult, null, 2)}</pre>
        </div>
        <div className="agent-col">
          <div className="small">run result</div>
          <pre>{JSON.stringify(wfRunResult, null, 2)}</pre>
        </div>
        <div className="agent-col">
          <div className="small">run detail</div>
          <pre>{JSON.stringify(wfRunDetail, null, 2)}</pre>
        </div>
      </div>
    </div>
  );
}
