import { useEffect, useMemo, useState } from "react";
import { DeleteConfirmDialog } from "./DeleteConfirmDialog";
import { WorkflowRunnerPanel } from "./WorkflowRunnerPanel";

type Props = {
  selectedBookId?: string;
  selectedChapterId?: string;
  onPickBookId?: (bookId: string) => void;
  onPickChapterId?: (chapterId: string) => void;
};

type CleanupConfirmDialog =
  | null
  | {
      kind: "scope" | "selected";
      title: string;
      targetLabel: string;
      warning: string;
      expectedText: string;
      exportIds: string[];
    };

function asObj(v: any): Record<string, any> {
  return v && typeof v === "object" && !Array.isArray(v) ? v : {};
}

function AuditChangeView({ audit }: { audit: any }) {
  const changes = asObj(audit?.changes);
  const affected = asObj(audit?.affected);
  const before = asObj(changes.before || audit?.before_state);
  const after = asObj(changes.after || audit?.after_state);
  const beforeF = asObj(before.foreshadow);
  const beforeG = asObj(before.growth);
  const afterF = asObj(after.foreshadow);
  const afterG = asObj(after.growth);
  const foreshadowKeys =
    (Array.isArray(affected.foreshadow) ? affected.foreshadow : null) ||
    (Array.isArray(affected.foreshadow_keys) ? affected.foreshadow_keys : null) ||
    Object.keys(afterF);
  const growthKeys =
    (Array.isArray(affected.growth) ? affected.growth : null) ||
    (Array.isArray(affected.growth_keys) ? affected.growth_keys : null) ||
    Object.keys(afterG);
  const counts = asObj(affected.counts);
  const hasStructured =
    foreshadowKeys.length > 0 ||
    growthKeys.length > 0 ||
    Object.keys(beforeF).length > 0 ||
    Object.keys(beforeG).length > 0;
  if (!hasStructured) return null;
  return (
    <details>
      <summary className="small">
        变更概览 · 伏笔={String(counts.foreshadow ?? foreshadowKeys.length)} · 成长=
        {String(counts.growth ?? growthKeys.length)}
      </summary>
      <div className="small" style={{ marginTop: 6 }}>
        {foreshadowKeys.length ? `伏笔：${foreshadowKeys.join(", ")}` : "伏笔：-"}
      </div>
      <div className="small">
        {growthKeys.length ? `成长：${growthKeys.join(", ")}` : "成长：-"}
      </div>
      <div className="agent-grid" style={{ marginTop: 6 }}>
        <div className="agent-col">
          <div className="small">修改前</div>
          <pre className="small">{JSON.stringify({ foreshadow: beforeF, growth: beforeG }, null, 2)}</pre>
        </div>
        <div className="agent-col">
          <div className="small">修改后</div>
          <pre className="small">{JSON.stringify({ foreshadow: afterF, growth: afterG }, null, 2)}</pre>
        </div>
      </div>
    </details>
  );
}

function ActionPayloadEditor({
  action,
  value,
  onChange,
  selectedChapterId,
}: {
  action: any;
  value: any;
  onChange: (patch: any) => void;
  selectedChapterId?: string;
}) {
  const t = String(action?.type || "");
  const v = value || {};
  if (t === "adjust_orchestrator_limits") {
    const scope = String(v.scope ?? "book");
    const replay = (v.replay || {}) as any;
    const budget = (v.context_budget || {}) as any;
    const cf = (budget.character_facts || {}) as any;
    const tf = (budget.timeline_facts || {}) as any;
    const of = (budget.open_foreshadows || {}) as any;
    const gm = (budget.growth_milestones || {}) as any;
    const setBudget = (key: string, patch: any) => {
      onChange({
        context_budget: {
          ...(budget || {}),
          [key]: { ...((budget || {})[key] || {}), ...(patch || {}) },
        },
      });
    };
    return (
      <div className="agent-form-grid">
        <label>
          范围（scope）
          <select
            value={scope}
            onChange={(e) =>
              onChange({
                scope: e.target.value,
                chapter_id: e.target.value === "chapter" ? String(v.chapter_id || selectedChapterId || "") : "",
              })
            }
          >
            <option value="book">书籍（book）</option>
            <option value="chapter">章节（chapter）</option>
          </select>
        </label>
        {scope === "chapter" ? (
          <label>
            章节ID（chapter_id）
            <input
              value={String(v.chapter_id ?? selectedChapterId ?? "")}
              onChange={(e) => onChange({ chapter_id: e.target.value })}
            />
          </label>
        ) : null}
        <label>
          结构权重上限（max_structure_weight）
          <input
            type="number"
            min={1}
            max={6}
            value={v.max_structure_weight ?? 4}
            onChange={(e) => onChange({ max_structure_weight: Number(e.target.value) })}
          />
        </label>
        <label>
          任务上限（max_tasks）
          <input
            type="number"
            min={1}
            max={4}
            value={v.max_tasks ?? 2}
            onChange={(e) => onChange({ max_tasks: Number(e.target.value) })}
          />
        </label>
        <label>
          回放最大轮次（replay.defer_max_rounds）
          <input
            type="number"
            min={1}
            max={8}
            value={Number(replay.defer_max_rounds ?? 3)}
            onChange={(e) =>
              onChange({
                replay: { ...(replay || {}), defer_max_rounds: Number(e.target.value) },
              })
            }
          />
        </label>
        <label>
          回放过期宽限（replay.defer_expire_grace）
          <input
            type="number"
            min={0}
            max={0.5}
            step={0.01}
            value={Number(replay.defer_expire_grace ?? 0.12)}
            onChange={(e) =>
              onChange({
                replay: { ...(replay || {}), defer_expire_grace: Number(e.target.value) },
              })
            }
          />
        </label>
        <label className="agent-checkbox">
          <input
            type="checkbox"
            checked={!!v.ban_strong_cliff}
            onChange={(e) => onChange({ ban_strong_cliff: e.target.checked })}
          />
          禁止强悬崖（ban_strong_cliff）
        </label>
        <label>
          角色事实条目上限（budget.character_facts.max_items）
          <input type="number" min={1} max={20} value={Number(cf.max_items ?? 8)} onChange={(e) => setBudget("character_facts", { max_items: Number(e.target.value) })} />
        </label>
        <label>
          角色事实字符上限（budget.character_facts.max_chars）
          <input type="number" min={120} max={6000} value={Number(cf.max_chars ?? 1000)} onChange={(e) => setBudget("character_facts", { max_chars: Number(e.target.value) })} />
        </label>
        <label>
          时间线事实条目上限（budget.timeline_facts.max_items）
          <input type="number" min={1} max={20} value={Number(tf.max_items ?? 8)} onChange={(e) => setBudget("timeline_facts", { max_items: Number(e.target.value) })} />
        </label>
        <label>
          时间线事实字符上限（budget.timeline_facts.max_chars）
          <input type="number" min={120} max={6000} value={Number(tf.max_chars ?? 1000)} onChange={(e) => setBudget("timeline_facts", { max_chars: Number(e.target.value) })} />
        </label>
        <label>
          未回收伏笔条目上限（budget.open_foreshadows.max_items）
          <input type="number" min={1} max={20} value={Number(of.max_items ?? 6)} onChange={(e) => setBudget("open_foreshadows", { max_items: Number(e.target.value) })} />
        </label>
        <label>
          未回收伏笔字符上限（budget.open_foreshadows.max_chars）
          <input type="number" min={120} max={6000} value={Number(of.max_chars ?? 900)} onChange={(e) => setBudget("open_foreshadows", { max_chars: Number(e.target.value) })} />
        </label>
        <label>
          成长里程碑条目上限（budget.growth_milestones.max_items）
          <input type="number" min={1} max={20} value={Number(gm.max_items ?? 6)} onChange={(e) => setBudget("growth_milestones", { max_items: Number(e.target.value) })} />
        </label>
        <label>
          成长里程碑字符上限（budget.growth_milestones.max_chars）
          <input type="number" min={120} max={6000} value={Number(gm.max_chars ?? 900)} onChange={(e) => setBudget("growth_milestones", { max_chars: Number(e.target.value) })} />
        </label>
      </div>
    );
  }
  if (t === "inject_reveal_combo") {
    return (
      <div className="agent-form-grid">
        <label>
          影响后续章节数（window_next_chapters）
          <input
            type="number"
            min={1}
            max={3}
            value={v.window_next_chapters ?? 2}
            onChange={(e) => onChange({ window_next_chapters: Number(e.target.value) })}
          />
        </label>
        <label>
          组合类型（combo_type）
          <input value={String(v.combo_type ?? "reveal_combo")} onChange={(e) => onChange({ combo_type: e.target.value })} />
        </label>
      </div>
    );
  }
  if (t === "rotate_combo_group") {
    return (
      <div className="agent-form-grid">
        <label>
          轮转组（rotation_group）
          <input value={String(v.rotation_group ?? "")} onChange={(e) => onChange({ rotation_group: e.target.value })} />
        </label>
        <label>
          冷却卷数（cooldown_volumes）
          <input
            type="number"
            min={1}
            max={4}
            value={v.cooldown_volumes ?? 2}
            onChange={(e) => onChange({ cooldown_volumes: Number(e.target.value) })}
          />
        </label>
      </div>
    );
  }
  return <pre className="small">{JSON.stringify(v || {}, null, 2)}</pre>;
}

export function AgentConsolePanel(props: Props) {
  const [bookId, setBookId] = useState(props.selectedBookId || "");
  const [chapterId, setChapterId] = useState(props.selectedChapterId || "");
  const [settings, setSettings] = useState<any>(null);
  const [health, setHealth] = useState<any>(null);
  const [diagnosis, setDiagnosis] = useState<any>(null);
  const [proposal, setProposal] = useState<any>(null);
  const [selectedIds, setSelectedIds] = useState<Record<string, boolean>>({});
  const [payloadEdits, setPayloadEdits] = useState<Record<string, any>>({});
  const [applyResult, setApplyResult] = useState<any>(null);
  const [planAutobuildResult, setPlanAutobuildResult] = useState<any>(null);
  const [audits, setAudits] = useState<any[]>([]);
  const [onlyCurrentChapterAudits, setOnlyCurrentChapterAudits] = useState(true);
  const [auditActionFilter, setAuditActionFilter] = useState("all");
  const [workspacePath, setWorkspacePath] = useState("");
  const [exportVolumeId, setExportVolumeId] = useState("");
  const [exportResult, setExportResult] = useState<any>(null);
  const [exportLogs, setExportLogs] = useState<any[]>([]);
  const [selectedExportLogId, setSelectedExportLogId] = useState("");
  const [exportLogDays, setExportLogDays] = useState("all");
  const [pathExistsMap, setPathExistsMap] = useState<Record<string, boolean>>({});
  const [cleanupResult, setCleanupResult] = useState<any>(null);
  const [cleanupOnlyVisible, setCleanupOnlyVisible] = useState(true);
  const [cleanupSelectedIds, setCleanupSelectedIds] = useState<Record<string, boolean>>({});
  const [cleanupConfirmDialog, setCleanupConfirmDialog] = useState<CleanupConfirmDialog>(null);
  const [cleanupConfirmValue, setCleanupConfirmValue] = useState("");
  const [cleanupConfirmError, setCleanupConfirmError] = useState("");
  const [fixPlan, setFixPlan] = useState<any>(null);
  const [fixSelectedIds, setFixSelectedIds] = useState<Record<string, boolean>>({});
  const [fixExecuteResult, setFixExecuteResult] = useState<any>(null);
  const [orchestratePlanResult, setOrchestratePlanResult] = useState<any>(null);
  const [orchestrateRunResult, setOrchestrateRunResult] = useState<any>(null);
  const [orchestrateStepResults, setOrchestrateStepResults] = useState<Record<string, any>>({});
  const [orchestrateDryRun, setOrchestrateDryRun] = useState(false);
  const [orchestrateConfirmExecute, setOrchestrateConfirmExecute] = useState(false);
  const [orchestrateDoCommit, setOrchestrateDoCommit] = useState(true);
  const [orchestrateDoLearn, setOrchestrateDoLearn] = useState(true);
  const [orchestrateSnapshotName, setOrchestrateSnapshotName] = useState("");
  const [orchestrateSnapshotReason, setOrchestrateSnapshotReason] = useState("");
  const [sidecarHealth, setSidecarHealth] = useState<any>(null);
  const [sidecarLogs, setSidecarLogs] = useState<string[]>([]);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const [info, setInfo] = useState("");

  useEffect(() => setBookId(props.selectedBookId || ""), [props.selectedBookId]);
  useEffect(() => setChapterId(props.selectedChapterId || ""), [props.selectedChapterId]);

  const actions = useMemo(() => (proposal?.actions || []) as any[], [proposal]);
  const auditActionOptions = useMemo(() => {
    const set = new Set<string>();
    for (const a of audits) {
      const t = String(a?.action_type || a?.action || a?.type || "").trim();
      if (t) set.add(t);
    }
    return ["all", ...Array.from(set).sort()];
  }, [audits]);
  const visibleAudits = useMemo(() => {
    return audits.filter((a: any) => {
      if (auditActionFilter !== "all") {
        const t = String(a?.action_type || a?.action || a?.type || "").trim();
        if (t !== auditActionFilter) return false;
      }
      if (!onlyCurrentChapterAudits || !chapterId) return true;
      const aid = String(a?.chapter_id || a?.chapterId || "").trim();
      if (!aid) return true;
      return aid === chapterId;
    });
  }, [audits, onlyCurrentChapterAudits, chapterId, auditActionFilter]);
  const replayStats = useMemo(() => {
    const d = diagnosis && typeof diagnosis === "object" ? diagnosis : {};
    const rs = d?.replay_stats;
    return rs && typeof rs === "object" ? rs : null;
  }, [diagnosis]);
  const replayThresholds = useMemo(() => {
    const d = diagnosis && typeof diagnosis === "object" ? diagnosis : {};
    const rt = d?.replay_thresholds;
    return rt && typeof rt === "object"
      ? rt
      : {
          avg_filtered_medium: 1.5,
          avg_filtered_high: 3.0,
          avg_filtered_low: 0.3,
          max_round_hits_red: 3,
          expired_hits_red: 4,
        };
  }, [diagnosis]);
  const replaySuggestion = useMemo(() => {
    const act = actions.find((x) => String(x?.type || "") === "adjust_orchestrator_limits");
    const payload = act?.payload && typeof act.payload === "object" ? act.payload : {};
    const replay = payload?.replay && typeof payload.replay === "object" ? payload.replay : null;
    return replay;
  }, [actions]);
  const planAutobuildSummary = useMemo(() => {
    const raw = planAutobuildResult && typeof planAutobuildResult === "object" ? planAutobuildResult : {};
    const plan = raw?.plan && typeof raw.plan === "object" ? raw.plan : null;
    const items = Array.isArray(plan?.items) ? plan.items : [];
    const combos = new Set<string>();
    for (const it of items) {
      const meta = it?.meta && typeof it.meta === "object" ? it.meta : {};
      const ct = String(meta?.combo_type || "").trim();
      if (ct) combos.add(ct);
    }
    const needed = ["setup_hook_combo", "mid_spike_combo", "reveal_combo", "vol_end_combo"];
    const covered = needed.filter((x) => combos.has(x));
    const missing = needed.filter((x) => !combos.has(x));
    return {
      ok: !!raw?.ok,
      route: String(raw?.route || ""),
      bookId: String(raw?.book_id || ""),
      volumeId: String(raw?.volume_id || ""),
      version: Number(raw?.version || plan?.version || 0),
      totalItems: items.length,
      comboCovered: covered,
      comboMissing: missing,
    };
  }, [planAutobuildResult]);
  const replayTone = useMemo(() => {
    const avg = Number(replayStats?.avg_replay_filtered ?? 0);
    const high = Number(replayThresholds?.avg_filtered_high ?? 3);
    const medium = Number(replayThresholds?.avg_filtered_medium ?? 1.5);
    if (avg >= high) return { label: "高压（high pressure）", color: "#b91c1c" };
    if (avg >= medium) return { label: "中压（medium pressure）", color: "#b45309" };
    return { label: "稳定（stable）", color: "#15803d" };
  }, [replayStats, replayThresholds]);
  const selectedExportLog = useMemo(() => {
    if (!selectedExportLogId) return exportLogs[0] || null;
    return exportLogs.find((x: any) => String(x?.export_id || "") === selectedExportLogId) || exportLogs[0] || null;
  }, [exportLogs, selectedExportLogId]);
  const selectedExportFiles = useMemo(() => {
    const man = selectedExportLog?.manifest;
    const files = man && typeof man === "object" ? man.files : null;
    return Array.isArray(files) ? files : [];
  }, [selectedExportLog]);
  const selectedExportPreflight = useMemo(() => {
    const man = selectedExportLog?.manifest;
    if (!man || typeof man !== "object") return null;
    const pf = (man as any).preflight;
    return pf && typeof pf === "object" ? pf : null;
  }, [selectedExportLog]);
  const selectedExportPreflightHints = useMemo(() => {
    const pf = selectedExportPreflight;
    const hints = pf && typeof pf === "object" ? (pf as any).note_hints : null;
    return Array.isArray(hints) ? hints : [];
  }, [selectedExportPreflight]);
  const fixPlanItems = useMemo(() => {
    const xs = fixPlan?.fixes;
    return Array.isArray(xs) ? xs : [];
  }, [fixPlan]);
  const filteredExportLogs = useMemo(() => {
    const days = exportLogDays === "all" ? 0 : Number(exportLogDays || 0);
    if (!days) return exportLogs;
    const now = Date.now();
    const winMs = days * 86400000;
    return exportLogs.filter((x: any) => {
      const ts = Date.parse(String(x?.created_at || ""));
      if (!Number.isFinite(ts)) return true;
      return now - ts <= winMs;
    });
  }, [exportLogs, exportLogDays]);
  const groupedExportLogs = useMemo(() => {
    const groups: Record<string, any[]> = {};
    for (const x of filteredExportLogs) {
      const k = String(x?.pack_name || "未知(unknown)").trim() || "未知(unknown)";
      if (!groups[k]) groups[k] = [];
      groups[k].push(x);
    }
    return Object.entries(groups).sort((a, b) => a[0].localeCompare(b[0], "zh-CN"));
  }, [filteredExportLogs]);
  const orchestratePlanSummary = useMemo(() => {
    const plan = orchestratePlanResult?.plan && typeof orchestratePlanResult.plan === "object" ? orchestratePlanResult.plan : {};
    return {
      requiresConfirmation: !!plan?.requires_confirmation,
      actionsCount: Number(plan?.actions_count || 0),
      warnCount: Number(plan?.warn_count || 0),
      nextPhase: String(plan?.next_recommended_phase || "-"),
    };
  }, [orchestratePlanResult]);

  async function loadSettings() {
    setBusy("settings");
    setErr("");
    try {
      const s = await window.desktopApi.settingsGet();
      setSettings(s || {});
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function saveSettings(patch: any) {
    setBusy("settings");
    setErr("");
    try {
      const s = await window.desktopApi.settingsSet(patch);
      setSettings(s || {});
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runHealth() {
    setBusy("health");
    setErr("");
    try {
      setHealth(await window.desktopApi.agentHealth());
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runSidecarStart() {
    setBusy("sidecar:start");
    setErr("");
    try {
      const out = await window.desktopApi.sidecarStart();
      setInfo(`侧车(Sidecar)已启动：${String(out?.baseUrl || settings?.baseUrl || "-")}`);
      const s = await window.desktopApi.settingsGet();
      setSettings(s || {});
      setSidecarHealth(await window.desktopApi.sidecarHealth());
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runSidecarStop() {
    setBusy("sidecar:stop");
    setErr("");
    try {
      await window.desktopApi.sidecarStop();
      setInfo("侧车(Sidecar)已停止。");
      setSidecarHealth(await window.desktopApi.sidecarHealth());
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runSidecarHealth() {
    setBusy("sidecar:health");
    setErr("");
    try {
      setSidecarHealth(await window.desktopApi.sidecarHealth());
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runOneClickReady() {
    setBusy("desktop:ready");
    setErr("");
    try {
      await window.desktopApi.sidecarStart();
      const [sh, h] = await Promise.all([window.desktopApi.sidecarHealth(), window.desktopApi.agentHealth()]);
      setSidecarHealth(sh);
      setHealth(h);
      const s = await window.desktopApi.settingsGet();
      setSettings(s || {});
      setInfo(`桌面已就绪。侧车(Sidecar)=${String(sh?.ok ? "正常(ok)" : "故障(down)")} API=${String(h?.ok ? "正常(ok)" : "故障(down)")}`);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runDiagnose() {
    if (!bookId) return;
    setBusy("diagnose");
    setErr("");
    try {
      const out = await window.desktopApi.agentDiagnose({ book_id: bookId, chapter_id: chapterId || undefined });
      setDiagnosis(out?.diagnosis || out);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runPropose() {
    if (!bookId) return;
    setBusy("propose");
    setErr("");
    try {
      const out = await window.desktopApi.agentPropose({ book_id: bookId, chapter_id: chapterId || undefined });
      setProposal(out || {});
      setSelectedIds({});
      setPayloadEdits({});
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  function useMissingAsActions() {
    const missing = planAutobuildSummary.comboMissing || [];
    if (!missing.length) {
      setInfo("没有缺失组合可添加。");
      return;
    }
    const generated = missing.map((comboType: string) => ({
      action_id: `auto_combo_missing:${comboType}`,
      type: "schedule_combo_next_chapters",
      payload: { combo_type: comboType, window_next_chapters: comboType === "vol_end_combo" ? 1 : 2 },
      reason: `autobuild missing combo: ${comboType}`,
      source: "autobuild_missing",
    }));
    setProposal((prev: any) => {
      const base = prev && typeof prev === "object" ? prev : {};
      const prevActions = Array.isArray(base.actions) ? base.actions : [];
      const seen = new Set(prevActions.map((a: any) => String(a?.action_id || `${a?.type}:${a?.payload?.combo_type || ""}`)));
      const merged = [...prevActions];
      for (const g of generated) {
        if (!seen.has(String(g.action_id))) merged.push(g);
      }
      return { ...base, actions: merged };
    });
    setSelectedIds((m) => {
      const next = { ...m };
      for (const g of generated) next[String(g.action_id)] = true;
      return next;
    });
    setInfo(`已从缺失组合生成 ${generated.length} 个动作。`);
  }

  async function runApply(dryRun = false) {
    if (!bookId) return;
    const chosen = actions.filter((a) => selectedIds[String(a.action_id || a.type)]);
    if (chosen.length === 0) return;
    const patched = chosen.map((a) => {
      const key = String(a.action_id || a.type);
      return { ...a, payload: { ...(a.payload || {}), ...(payloadEdits[key] || {}) } };
    });
    setBusy("apply");
    setErr("");
    try {
      const out = await window.desktopApi.agentApply({
        book_id: bookId,
        chapter_id: chapterId || undefined,
        actions: patched,
        dry_run: !!dryRun,
      });
      setApplyResult(out || {});
      await runDiagnose();
      await loadAudits();
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function loadAudits() {
    if (!bookId) return;
    setBusy("audits");
    setErr("");
    try {
      const out = await window.desktopApi.agentAuditsList({ book_id: bookId, limit: 30 });
      const items = (out?.audits || out?.items || []) as any[];
      setAudits(items);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runPlanAutobuild() {
    if (!bookId) return;
    setBusy("plan_autobuild");
    setErr("");
    try {
      const out = await window.desktopApi.planAutobuild({
        book_id: bookId,
        chapter_id: chapterId || undefined,
      });
      setPlanAutobuildResult(out || {});
      await runDiagnose();
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runOrchestratePlan() {
    if (!bookId) return;
    setBusy("orchestrate:plan");
    setErr("");
    try {
      const out = await window.desktopApi.agentOrchestratePlan({
        book_id: bookId,
        chapter_id: chapterId || undefined,
        include_snapshot: true,
        include_style: true,
      });
      setOrchestratePlanResult(out || {});
      setInfo("总控 PLAN 完成。");
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runOrchestrateStep(phase: "PLAN" | "EXECUTE" | "VERIFY" | "COMMIT" | "LEARN") {
    if (!bookId) return;
    setBusy(`orchestrate:step:${phase.toLowerCase()}`);
    setErr("");
    try {
      const out = await window.desktopApi.agentOrchestrateStep({
        book_id: bookId,
        chapter_id: chapterId || undefined,
        phase,
        dry_run: orchestrateDryRun,
        confirm_execute: orchestrateConfirmExecute,
        snapshot_name: orchestrateSnapshotName.trim() || undefined,
        snapshot_reason: orchestrateSnapshotReason.trim() || undefined,
        proposal: orchestratePlanResult?.plan?.proposal,
      });
      setOrchestrateStepResults((m) => ({ ...m, [phase]: out || {} }));
      if (phase === "PLAN") setOrchestratePlanResult({ ok: true, plan: out?.result || {} });
      if (phase === "VERIFY") await runDiagnose();
      if (phase === "EXECUTE") await loadAudits();
      setInfo(`总控 ${phase} 完成。`);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runOrchestrateAll() {
    if (!bookId) return;
    setBusy("orchestrate:run");
    setErr("");
    try {
      const out = await window.desktopApi.agentOrchestrateRun({
        book_id: bookId,
        chapter_id: chapterId || undefined,
        dry_run: orchestrateDryRun,
        do_execute: true,
        do_verify: true,
        do_commit: orchestrateDoCommit,
        do_learn: orchestrateDoLearn,
        confirm_execute: orchestrateConfirmExecute,
        snapshot_name: orchestrateSnapshotName.trim() || undefined,
        snapshot_reason: orchestrateSnapshotReason.trim() || undefined,
      });
      setOrchestrateRunResult(out || {});
      if (out?.phases && typeof out.phases === "object") {
        setOrchestrateStepResults((m) => ({ ...m, ...out.phases }));
      }
      await runDiagnose();
      await loadAudits();
      setInfo(`总控全流程执行完成：${String(out?.state || "-")}`);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function loadWorkspaceBinding() {
    if (!bookId) return;
    setBusy("workspace:get");
    setErr("");
    try {
      const out = await window.desktopApi.bookWorkspaceGet({ book_id: bookId });
      setWorkspacePath(String(out?.workspace?.workspace_path || ""));
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function saveWorkspaceBinding() {
    if (!bookId || !workspacePath.trim()) return;
    setBusy("workspace:set");
    setErr("");
    try {
      const out = await window.desktopApi.bookWorkspaceSet({
        book_id: bookId,
        body: { workspace_path: workspacePath.trim() },
      });
      setWorkspacePath(String(out?.workspace_path || workspacePath.trim()));
      setInfo("工作区已保存。");
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runExportChapter() {
    if (!bookId || !chapterId) return;
    setBusy("export:chapter");
    setErr("");
    try {
      const out = await window.desktopApi.exportChapter({
        book_id: bookId,
        chapter_id: chapterId,
        format: "md",
        include_header: true,
      });
      setExportResult(out || {});
      const p = String(out?.output_path || "");
      if (p) await window.desktopApi.openPath(p, true);
      await loadExportLogs();
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runExportVolume() {
    if (!bookId || !exportVolumeId.trim()) return;
    setBusy("export:volume");
    setErr("");
    try {
      const out = await window.desktopApi.exportVolume({
        book_id: bookId,
        volume_id: exportVolumeId.trim(),
        format: "md",
        include_chapter_titles: true,
      });
      setExportResult(out || {});
      const p = String(out?.output_path || "");
      if (p) await window.desktopApi.openPath(p, true);
      await loadExportLogs();
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runPublishPack() {
    if (!bookId || !exportVolumeId.trim()) return;
    setBusy("export:publish_pack");
    setErr("");
    try {
      const out = await window.desktopApi.exportPublishPack({
        book_id: bookId,
        volume_id: exportVolumeId.trim(),
      });
      setExportResult(out || {});
      const p = String(out?.output_dir || "");
      if (p) await window.desktopApi.openPath(p, true);
      await loadExportLogs();
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function openExportFolder() {
    const dir = String(exportResult?.output_dir || "");
    const file = String(exportResult?.output_path || "");
    const p = dir || file;
    if (!p) return;
    await window.desktopApi.openPath(p, true);
  }

  async function loadExportLogs() {
    if (!bookId) return;
    setBusy("export:logs");
    setErr("");
    try {
      const out = await window.desktopApi.exportLogs({
        book_id: bookId,
        volume_id: exportVolumeId.trim() || undefined,
        limit: 20,
      });
      const items = Array.isArray(out?.items) ? out.items : [];
      setExportLogs(items);
      if (items.length > 0) {
        const current = String(selectedExportLogId || "");
        const exists = items.some((x: any) => String(x?.export_id || "") === current);
        if (!exists) setSelectedExportLogId(String(items[0]?.export_id || ""));
      } else {
        setSelectedExportLogId("");
      }
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function openExportLogItem(row: any) {
    const p = String(row?.output_dir || "").trim();
    if (!p) return;
    await window.desktopApi.openPath(p, true);
  }

  async function openExportLogFile(file: any) {
    const p = String(file?.path || "").trim();
    if (!p) return;
    await window.desktopApi.openPath(p, true);
  }

  async function runCleanupMissing(dryRun: boolean) {
    if (!bookId) return;
    const exportIds =
      cleanupOnlyVisible
        ? filteredExportLogs
            .map((x: any) => String(x?.export_id || "").trim())
            .filter(Boolean)
        : [];
    if (!dryRun) {
      setCleanupConfirmDialog({
        kind: "scope",
        title: "清理缺失导出记录",
        targetLabel: cleanupOnlyVisible
          ? `范围：当前筛选日志（候选 ${exportIds.length} 条）`
          : "范围：当前书籍 / 当前卷（按接口参数）",
        warning: cleanupOnlyVisible
          ? "将删除当前筛选范围内已缺失文件的导出记录，操作不可撤销。"
          : "将清理当前书籍范围内缺失文件的导出记录，操作不可撤销。",
        expectedText: "清理",
        exportIds,
      });
      setCleanupConfirmValue("");
      setCleanupConfirmError("");
      return;
    }
    setBusy(dryRun ? "export:cleanup:dry" : "export:cleanup");
    setErr("");
    try {
      const out = await window.desktopApi.exportCleanupMissing({
        book_id: bookId,
        volume_id: exportVolumeId.trim() || undefined,
        dry_run: dryRun,
        export_ids: cleanupOnlyVisible ? exportIds : undefined,
      });
      setCleanupResult(out || {});
      if (dryRun) {
        const items = Array.isArray(out?.items) ? out.items : [];
        const next: Record<string, boolean> = {};
        for (const x of items) {
          const xid = String(x?.export_id || "").trim();
          if (xid) next[xid] = true;
        }
        setCleanupSelectedIds(next);
      }
      if (!dryRun) {
        setInfo(`清理完成。已删除=${String(out?.deleted_count ?? 0)}`);
      }
      await loadExportLogs();
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runCleanupMissingCommit(exportIds: string[]): Promise<boolean> {
    if (!bookId) return false;
    setBusy("export:cleanup");
    setErr("");
    try {
      const out = await window.desktopApi.exportCleanupMissing({
        book_id: bookId,
        volume_id: exportVolumeId.trim() || undefined,
        dry_run: false,
        export_ids: cleanupOnlyVisible ? exportIds : undefined,
      });
      setCleanupResult(out || {});
      setInfo(`清理完成。已删除=${String(out?.deleted_count ?? 0)}`);
      await loadExportLogs();
      return true;
    } catch (e: any) {
      setErr(String(e?.message || e));
      return false;
    } finally {
      setBusy("");
    }
  }

  async function runRebuildSelected() {
    const exportId = String(selectedExportLog?.export_id || "").trim();
    if (!exportId) return;
    setBusy("export:rebuild");
    setErr("");
    try {
      const out = await window.desktopApi.exportRebuild({ export_id: exportId });
      const rebuilt = out?.rebuild || {};
      setExportResult(rebuilt);
      const p = String(rebuilt?.output_dir || "");
      if (p) await window.desktopApi.openPath(p, true);
      await loadExportLogs();
      setInfo(`已根据导出ID（export_id）重建：${exportId}`);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runFixwizardPlan() {
    if (!bookId || !exportVolumeId.trim()) return;
    setBusy("fixwizard:plan");
    setErr("");
    try {
      const out = await window.desktopApi.fixwizardPlan({
        book_id: bookId,
        volume_id: exportVolumeId.trim(),
        preflight: selectedExportPreflight ? { summary: selectedExportPreflight, note_hints: selectedExportPreflightHints } : undefined,
      });
      setFixPlan(out || {});
      setFixExecuteResult(null);
      const items = Array.isArray(out?.fixes) ? out.fixes : [];
      const next: Record<string, boolean> = {};
      for (const fx of items) {
        const fid = String(fx?.fix_id || "").trim();
        if (fid) next[fid] = false;
      }
      setFixSelectedIds(next);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runFixwizardExecute() {
    if (!bookId || !exportVolumeId.trim()) return;
    const ids = Object.keys(fixSelectedIds).filter((k) => !!fixSelectedIds[k]);
    if (ids.length === 0) return;
    setBusy("fixwizard:execute");
    setErr("");
    try {
      const all = Array.isArray(fixPlan?.fixes) ? fixPlan.fixes : [];
      const selected = all.filter((x: any) => ids.includes(String(x?.fix_id || "")));
      const out = await window.desktopApi.fixwizardExecute({
        book_id: bookId,
        volume_id: exportVolumeId.trim(),
        chapter_id: chapterId || undefined,
        pack_name: String(selectedExportLog?.pack_name || ""),
        selected_fixes: selected,
        fixes: all,
        preflight_summary: selectedExportPreflight || undefined,
        auto_recheck: true,
      });
      setFixExecuteResult(out || {});
      await loadExportLogs();
      if (out?.recheck?.summary) {
        setInfo(
          `修复已执行。复检 overall=${String(out.recheck.summary.overall || "-")} fail=${String(
            out.recheck.summary.fail_count ?? "-"
          )} warn=${String(out.recheck.summary.warn_count ?? "-")}`
        );
      } else {
        setInfo("修复已执行。");
      }
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runFixwizardRecheck() {
    if (!bookId || !exportVolumeId.trim()) return;
    setBusy("fixwizard:recheck");
    setErr("");
    try {
      const out = await window.desktopApi.fixwizardRecheck({
        book_id: bookId,
        volume_id: exportVolumeId.trim(),
        before_summary: selectedExportPreflight || undefined,
      });
      setFixExecuteResult((m: any) => ({ ...(m || {}), recheck: out?.report || null, recheck_delta: out?.delta || null }));
      const s = out?.report?.summary || {};
      setInfo(`复检完成。overall=${String(s.overall || "-")} fail=${String(s.fail_count ?? "-")} warn=${String(s.warn_count ?? "-")}`);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runCleanupSelectedMissing() {
    if (!bookId) return;
    const ids = Object.keys(cleanupSelectedIds).filter((k) => cleanupSelectedIds[k]);
    if (ids.length === 0) return;
    setCleanupConfirmDialog({
      kind: "selected",
      title: "删除已勾选的缺失记录",
      targetLabel: `将删除 ${ids.length} 条缺失导出记录`,
      warning: "仅删除导出日志记录，不会删除真实文件（文件本身已缺失）。",
      expectedText: "清理",
      exportIds: ids,
    });
    setCleanupConfirmValue("");
    setCleanupConfirmError("");
  }

  async function runCleanupSelectedMissingCommit(ids: string[]): Promise<boolean> {
    if (!bookId) return false;
    setBusy("export:cleanup:selected");
    setErr("");
    try {
      const out = await window.desktopApi.exportCleanupMissing({
        book_id: bookId,
        volume_id: exportVolumeId.trim() || undefined,
        dry_run: false,
        export_ids: ids,
      });
      setCleanupResult(out || {});
      setInfo(`已删除所选缺失日志：${String(out?.deleted_count ?? 0)}`);
      await loadExportLogs();
      return true;
    } catch (e: any) {
      setErr(String(e?.message || e));
      return false;
    } finally {
      setBusy("");
    }
  }

  async function confirmCleanupDialog() {
    if (!cleanupConfirmDialog) return;
    setCleanupConfirmError("");
    const ok =
      cleanupConfirmDialog.kind === "scope"
        ? await runCleanupMissingCommit(cleanupConfirmDialog.exportIds)
        : await runCleanupSelectedMissingCommit(cleanupConfirmDialog.exportIds);
    if (ok) {
      setCleanupConfirmDialog(null);
      setCleanupConfirmValue("");
      setCleanupConfirmError("");
    }
  }

  async function ensurePathStatuses(paths: string[]) {
    const unique = Array.from(new Set(paths.map((x) => String(x || "").trim()).filter(Boolean)));
    const unknown = unique.filter((p) => pathExistsMap[p] === undefined);
    if (unknown.length === 0) return;
    const checks = await Promise.all(
      unknown.map(async (p) => {
        try {
          const out = await window.desktopApi.pathExists(p);
          return [p, !!out?.exists] as const;
        } catch {
          return [p, false] as const;
        }
      })
    );
    setPathExistsMap((m) => {
      const next = { ...m };
      for (const [p, ok] of checks) next[p] = ok;
      return next;
    });
  }

  async function rollback(auditId: string) {
    if (!bookId || !auditId) return;
    setBusy("rollback");
    setErr("");
    try {
      const out = await window.desktopApi.agentRollback({ book_id: bookId, audit_id: auditId });
      setApplyResult(out || {});
      await runDiagnose();
      await loadAudits();
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  useEffect(() => {
    void loadSettings();
  }, []);
  useEffect(() => {
    if (!settings) return;
    if (settings?.autoStartSidecar === false) return;
    void runOneClickReady();
  }, [settings?.autoStartSidecar]);
  useEffect(() => {
    if (!window.desktopApi || typeof window.desktopApi.onLog !== "function") {
      setErr("桌面预加载接口未就绪，请重新安装或重新打包客户端。");
      return;
    }
    window.desktopApi.onLog((line: string) => {
      setSidecarLogs((arr) => [line, ...arr].slice(0, 200));
    });
  }, []);

  useEffect(() => {
    if (bookId) void loadWorkspaceBinding();
  }, [bookId]);

  useEffect(() => {
    if (bookId) void loadExportLogs();
  }, [bookId]);

  useEffect(() => {
    void ensurePathStatuses(
      filteredExportLogs.map((x: any) => String(x?.output_dir || "").trim()).filter(Boolean)
    );
  }, [filteredExportLogs]);

  useEffect(() => {
    void ensurePathStatuses(
      selectedExportFiles.map((f: any) => String(f?.path || "").trim()).filter(Boolean)
    );
  }, [selectedExportFiles]);

  return (
    <section className="wb-panel" style={{ minHeight: "auto", marginBottom: 10 }}>
      <div className="row" style={{ marginBottom: 8 }}>
        <h3 style={{ margin: 0 }}>智能体控制台</h3>
        <span className="small">{busy ? `忙碌：${busy}` : "空闲"}</span>
      </div>

      <div className="agent-topbar">
        <label>
          服务地址（baseUrl）
          <input
            value={String(settings?.baseUrl || "")}
            onChange={(e) => setSettings({ ...(settings || {}), baseUrl: e.target.value })}
            onBlur={() => void saveSettings({ baseUrl: String(settings?.baseUrl || "") })}
          />
        </label>
        <label>
          访问令牌（agentToken）
          <input
            type="password"
            value={String(settings?.agentToken || "")}
            onChange={(e) => setSettings({ ...(settings || {}), agentToken: e.target.value })}
            onBlur={() => void saveSettings({ agentToken: String(settings?.agentToken || "") })}
          />
        </label>
        <label>
          超时时间（timeoutMs）
          <input
            type="number"
            min={3000}
            max={120000}
            value={Number(settings?.timeoutMs || 20000)}
            onChange={(e) => setSettings({ ...(settings || {}), timeoutMs: Number(e.target.value) })}
            onBlur={() => void saveSettings({ timeoutMs: Number(settings?.timeoutMs || 20000) })}
          />
        </label>
        <label>
          数据库地址（database_url）
          <input
            value={String(settings?.databaseUrl || "")}
            onChange={(e) => setSettings({ ...(settings || {}), databaseUrl: e.target.value })}
            onBlur={() => void saveSettings({ databaseUrl: String(settings?.databaseUrl || "") })}
          />
        </label>
        <label>
          基础设施提供方（infra_provider）
          <select
            value={String(settings?.infraProvider || "docker")}
            onChange={(e) => {
              const v = e.target.value;
              setSettings({ ...(settings || {}), infraProvider: v });
              void saveSettings({ infraProvider: v });
            }}
          >
            <option value="docker">Docker（docker）</option>
            <option value="local_pg">本地 PostgreSQL（local_pg）</option>
            <option value="none">不启动（none）</option>
          </select>
        </label>
        <label>
          基础设施编排文件（infra_compose）
          <input
            value={String(settings?.infraComposePath || "")}
            onChange={(e) => setSettings({ ...(settings || {}), infraComposePath: e.target.value })}
            onBlur={() => void saveSettings({ infraComposePath: String(settings?.infraComposePath || "") })}
          />
        </label>
        <label>
          本地PG控制（local_pg_ctl）
          <input
            value={String(settings?.localPgCtlPath || "")}
            onChange={(e) => setSettings({ ...(settings || {}), localPgCtlPath: e.target.value })}
            onBlur={() => void saveSettings({ localPgCtlPath: String(settings?.localPgCtlPath || "") })}
          />
        </label>
        <label>
          本地PG初始化（local_initdb）
          <input
            value={String(settings?.localPgInitDbPath || "")}
            onChange={(e) => setSettings({ ...(settings || {}), localPgInitDbPath: e.target.value })}
            onBlur={() => void saveSettings({ localPgInitDbPath: String(settings?.localPgInitDbPath || "") })}
          />
        </label>
        <label>
          本地PG数据目录（local_pg_data）
          <input
            value={String(settings?.localPgDataDir || "")}
            onChange={(e) => setSettings({ ...(settings || {}), localPgDataDir: e.target.value })}
            onBlur={() => void saveSettings({ localPgDataDir: String(settings?.localPgDataDir || "") })}
          />
        </label>
        <label>
          侧车Python路径（sidecar_python）
          <input
            value={String(settings?.sidecarPythonPath || "")}
            onChange={(e) => setSettings({ ...(settings || {}), sidecarPythonPath: e.target.value })}
            onBlur={() => void saveSettings({ sidecarPythonPath: String(settings?.sidecarPythonPath || "") })}
          />
        </label>
        <label>
          侧车可执行文件（sidecar_exe）
          <input
            value={String(settings?.sidecarExecutablePath || "")}
            onChange={(e) => setSettings({ ...(settings || {}), sidecarExecutablePath: e.target.value })}
            onBlur={() => void saveSettings({ sidecarExecutablePath: String(settings?.sidecarExecutablePath || "") })}
          />
        </label>
        <label>
          侧车工作目录（sidecar_cwd）
          <input
            value={String(settings?.sidecarCwd || "")}
            onChange={(e) => setSettings({ ...(settings || {}), sidecarCwd: e.target.value })}
            onBlur={() => void saveSettings({ sidecarCwd: String(settings?.sidecarCwd || "") })}
          />
        </label>
        <label>
          侧车端口（sidecar_port）
          <input
            type="number"
            min={1000}
            max={65535}
            value={Number(settings?.sidecarPreferredPort || 17777)}
            onChange={(e) => setSettings({ ...(settings || {}), sidecarPreferredPort: Number(e.target.value) })}
            onBlur={() => void saveSettings({ sidecarPreferredPort: Number(settings?.sidecarPreferredPort || 17777) })}
          />
        </label>
        <label className="row" style={{ gap: 6, alignItems: "center", minWidth: 120 }}>
          <input
            type="checkbox"
            checked={Boolean(settings?.autoStartSidecar ?? true)}
            onChange={(e) => {
              const v = e.target.checked;
              setSettings({ ...(settings || {}), autoStartSidecar: v });
              void saveSettings({ autoStartSidecar: v });
            }}
          />
          <span className="small">自动启动（auto_start）</span>
        </label>
        <label className="row" style={{ gap: 6, alignItems: "center", minWidth: 160 }}>
          <input
            type="checkbox"
            checked={Boolean(settings?.autoStartInfra ?? true)}
            onChange={(e) => {
              const v = e.target.checked;
              setSettings({ ...(settings || {}), autoStartInfra: v });
              void saveSettings({ autoStartInfra: v });
            }}
          />
          <span className="small">自动启动基础设施（auto_start_infra）</span>
        </label>
        <label>
          书籍ID（book_id）
          <input
            value={bookId}
            onChange={(e) => {
              setBookId(e.target.value);
              props.onPickBookId?.(e.target.value);
            }}
          />
        </label>
        <label>
          章节ID（chapter_id）
          <input
            value={chapterId}
            onChange={(e) => {
              setChapterId(e.target.value);
              props.onPickChapterId?.(e.target.value);
            }}
          />
        </label>
      </div>

      <div className="row" style={{ marginTop: 8 }}>
        <div className="row" style={{ gap: 8 }}>
          <button onClick={() => void runOneClickReady()} disabled={!!busy}>一键就绪</button>
          <button onClick={() => void runHealth()}>健康检查</button>
          <button onClick={() => void runSidecarStart()}>启动侧车(Sidecar)</button>
          <button onClick={() => void runSidecarStop()}>停止侧车(Sidecar)</button>
          <button onClick={() => void runSidecarHealth()}>侧车(Sidecar) 健康</button>
          <button onClick={() => void runDiagnose()} disabled={!bookId}>诊断</button>
          <button onClick={() => void runPropose()} disabled={!bookId}>生成建议</button>
          <button onClick={() => void runOrchestratePlan()} disabled={!bookId}>总控 PLAN</button>
          <button onClick={() => void runOrchestrateAll()} disabled={!bookId}>总控一键全流程</button>
          <button onClick={() => void runPlanAutobuild()} disabled={!bookId}>自动构建计划</button>
          <button onClick={() => void runApply(false)} disabled={!bookId}>应用已选</button>
          <button onClick={() => void runApply(true)} disabled={!bookId}>应用演练（Dry Run）</button>
          <button onClick={() => void loadAudits()} disabled={!bookId}>刷新审计</button>
          <label>
            audit action
            <select value={auditActionFilter} onChange={(e) => setAuditActionFilter(e.target.value)}>
              {auditActionOptions.map((x) => (
                <option key={x} value={x}>{x}</option>
              ))}
            </select>
          </label>
          <label className="agent-checkbox">
            <input
              type="checkbox"
              checked={onlyCurrentChapterAudits}
              onChange={(e) => setOnlyCurrentChapterAudits(e.target.checked)}
            />
            only current chapter audits
          </label>
        </div>
        {info ? <span className="small" style={{ color: "#15803d" }}>{info}</span> : null}
        {err ? <span className="small" style={{ color: "#b91c1c" }}>{err}</span> : null}
      </div>

      <div className="agent-audit-row" style={{ marginTop: 8 }}>
        <div className="small" style={{ fontWeight: 600 }}>Agent 总控层（PLAN / EXECUTE / VERIFY / COMMIT / LEARN）</div>
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <label className="agent-checkbox">
            <input type="checkbox" checked={orchestrateDryRun} onChange={(e) => setOrchestrateDryRun(e.target.checked)} />
            Dry Run
          </label>
          <label className="agent-checkbox">
            <input
              type="checkbox"
              checked={orchestrateConfirmExecute}
              onChange={(e) => setOrchestrateConfirmExecute(e.target.checked)}
            />
            已确认执行高风险动作
          </label>
          <label className="agent-checkbox">
            <input type="checkbox" checked={orchestrateDoCommit} onChange={(e) => setOrchestrateDoCommit(e.target.checked)} />
            COMMIT（快照）
          </label>
          <label className="agent-checkbox">
            <input type="checkbox" checked={orchestrateDoLearn} onChange={(e) => setOrchestrateDoLearn(e.target.checked)} />
            LEARN（风格进化）
          </label>
          <label>
            快照名（可选）
            <input value={orchestrateSnapshotName} onChange={(e) => setOrchestrateSnapshotName(e.target.value)} />
          </label>
          <label>
            快照原因（可选）
            <input value={orchestrateSnapshotReason} onChange={(e) => setOrchestrateSnapshotReason(e.target.value)} />
          </label>
        </div>
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <button onClick={() => void runOrchestrateStep("PLAN")} disabled={!bookId || !!busy}>PLAN</button>
          <button onClick={() => void runOrchestrateStep("EXECUTE")} disabled={!bookId || !!busy}>EXECUTE</button>
          <button onClick={() => void runOrchestrateStep("VERIFY")} disabled={!bookId || !!busy}>VERIFY</button>
          <button onClick={() => void runOrchestrateStep("COMMIT")} disabled={!bookId || !!busy}>COMMIT</button>
          <button onClick={() => void runOrchestrateStep("LEARN")} disabled={!bookId || !!busy}>LEARN</button>
          <button onClick={() => void runOrchestrateAll()} disabled={!bookId || !!busy}>一键全流程</button>
        </div>
        <div className="small">
          PLAN 概览：动作={String(orchestratePlanSummary.actionsCount)}，告警={String(orchestratePlanSummary.warnCount)}，下一阶段=
          {String(orchestratePlanSummary.nextPhase)}，需确认={orchestratePlanSummary.requiresConfirmation ? "是" : "否"}
        </div>
        <details>
          <summary className="small">总控 PLAN 输出</summary>
          <pre className="small">{JSON.stringify(orchestratePlanResult, null, 2)}</pre>
        </details>
        <details>
          <summary className="small">总控阶段输出</summary>
          <pre className="small">{JSON.stringify(orchestrateStepResults, null, 2)}</pre>
        </details>
        <details>
          <summary className="small">总控全流程输出</summary>
          <pre className="small">{JSON.stringify(orchestrateRunResult, null, 2)}</pre>
        </details>
      </div>

      <div className="agent-grid">
        <div className="agent-col">
          <h4>诊断</h4>
          <div className="small">健康</div>
          <pre>{JSON.stringify(health, null, 2)}</pre>
          <div className="small">侧车(Sidecar) 健康</div>
          <pre>{JSON.stringify(sidecarHealth, null, 2)}</pre>
          <div className="small">侧车(Sidecar) 日志</div>
          <div className="scroll" style={{ maxHeight: 120 }}>
            {sidecarLogs.length === 0 ? <div className="hint">暂无侧车(Sidecar) 日志。</div> : null}
            {sidecarLogs.map((x, i) => (
              <div key={`${i}:${x}`} className="small mono">{x}</div>
            ))}
          </div>
          <div className="small">回放统计</div>
          {replayStats ? (
            <div className="agent-audit-row">
              <div className="small">样本量（sample_size）：{String(replayStats.sample_size ?? "-")}</div>
              <div className="small">
                平均过滤回放（avg_replay_filtered）：{" "}
                <span style={{ color: replayTone.color, fontWeight: 600 }}>
                  {String(replayStats.avg_replay_filtered ?? "-")} ({replayTone.label})
                </span>
              </div>
              <div className="small">
                最大轮次命中（max_round_hits）：{" "}
                <span
                  style={{
                    color:
                      Number(replayStats.max_round_hits ?? 0) >= Number(replayThresholds.max_round_hits_red ?? 3)
                        ? "#b91c1c"
                        : "#15803d",
                  }}
                >
                  {String(replayStats.max_round_hits ?? "-")}
                </span>
              </div>
              <div className="small">
                过期命中（expired_hits）：{" "}
                <span
                  style={{
                    color:
                      Number(replayStats.expired_hits ?? 0) >= Number(replayThresholds.expired_hits_red ?? 4)
                        ? "#b91c1c"
                        : "#15803d",
                  }}
                >
                  {String(replayStats.expired_hits ?? "-")}
                </span>
              </div>
              <div className="small">
                阈值（thresholds）：medium={String(replayThresholds.avg_filtered_medium)} high={String(replayThresholds.avg_filtered_high)} low=
                {String(replayThresholds.avg_filtered_low)}
              </div>
              <div className="small">
                建议回放（suggested replay）：defer_max_rounds=
                <span style={{ fontWeight: 600 }}>{String(replaySuggestion?.defer_max_rounds ?? "-")}</span>
                {" , "}defer_expire_grace=
                <span style={{ fontWeight: 600 }}>{String(replaySuggestion?.defer_expire_grace ?? "-")}</span>
              </div>
            </div>
          ) : (
            <div className="hint">暂无回放统计。</div>
          )}
          <div className="small">诊断详情</div>
          <pre>{JSON.stringify(diagnosis, null, 2)}</pre>
        </div>

        <div className="agent-col">
          <h4>建议动作</h4>
          {actions.length === 0 ? <div className="hint">暂无动作</div> : null}
          <div className="scroll" style={{ maxHeight: 420 }}>
            {actions.map((a) => {
              const key = String(a.action_id || a.type);
              const checked = !!selectedIds[key];
              const mergedPayload = { ...(a.payload || {}), ...(payloadEdits[key] || {}) };
              return (
                <div key={key} className="agent-action-card">
                  <label className="agent-checkbox">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(e) => setSelectedIds((m) => ({ ...m, [key]: e.target.checked }))}
                    />
                    <strong>{String(a.type || "动作")}</strong>
                  </label>
                  <div className="small">{String(a.reason || "")}</div>
              <ActionPayloadEditor
                action={a}
                value={mergedPayload}
                selectedChapterId={chapterId}
                onChange={(patch) => setPayloadEdits((m) => ({ ...m, [key]: { ...(m[key] || {}), ...(patch || {}) } }))}
              />
            </div>
              );
            })}
          </div>
        </div>

        <div className="agent-col">
          <h4>执行与审计</h4>
          <div className="small">章节工程导出</div>
          <div className="agent-audit-row">
            <label>
              工作区路径（workspace_path）
              <input value={workspacePath} onChange={(e) => setWorkspacePath(e.target.value)} />
            </label>
            <div className="row" style={{ gap: 8 }}>
              <button onClick={() => void loadWorkspaceBinding()} disabled={!bookId}>加载工作区</button>
              <button onClick={() => void saveWorkspaceBinding()} disabled={!bookId || !workspacePath.trim()}>保存工作区</button>
            </div>
            <label>
              卷 ID（volume_id）
              <input value={exportVolumeId} onChange={(e) => setExportVolumeId(e.target.value)} placeholder="用于卷/发布包导出" />
            </label>
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <button onClick={() => void runExportChapter()} disabled={!bookId || !chapterId}>导出当前章节</button>
              <button onClick={() => void runExportVolume()} disabled={!bookId || !exportVolumeId.trim()}>导出整卷</button>
              <button onClick={() => void runPublishPack()} disabled={!bookId || !exportVolumeId.trim()}>生成发布包</button>
              <button onClick={() => void openExportFolder()} disabled={!exportResult?.output_dir && !exportResult?.output_path}>打开导出目录</button>
              <button onClick={() => void loadExportLogs()} disabled={!bookId}>刷新导出日志</button>
            </div>
            <pre>{JSON.stringify(exportResult, null, 2)}</pre>
            <div className="row" style={{ gap: 8, alignItems: "center" }}>
              <div className="small">导出日志（{filteredExportLogs.length}/{exportLogs.length}）</div>
              <label className="small">
                范围
                <select value={exportLogDays} onChange={(e) => setExportLogDays(e.target.value)}>
                  <option value="all">全部</option>
                  <option value="7">7天</option>
                  <option value="30">30天</option>
                  <option value="90">90天</option>
                </select>
              </label>
              <button onClick={() => void runCleanupMissing(true)} disabled={!bookId}>检查缺失</button>
              <button onClick={() => void runCleanupMissing(false)} disabled={!bookId}>清理缺失</button>
              <label className="agent-checkbox">
                <input
                  type="checkbox"
                  checked={cleanupOnlyVisible}
                  onChange={(e) => setCleanupOnlyVisible(e.target.checked)}
                />
                仅当前筛选日志
              </label>
            </div>
            <div className="scroll" style={{ maxHeight: 180 }}>
              {filteredExportLogs.length === 0 ? <div className="hint">暂无导出日志。</div> : null}
              {groupedExportLogs.map(([packName, rows]) => (
                <div key={packName}>
                  <div className="small" style={{ fontWeight: 600, marginTop: 6 }}>
                    {packName} ({rows.length})
                  </div>
                  {rows.map((x: any) => {
                    const p = String(x?.output_dir || "").trim();
                    const exists = p ? pathExistsMap[p] : undefined;
                    return (
                      <div
                        key={String(x?.export_id || JSON.stringify(x))}
                        className="agent-audit-row"
                        style={{
                          borderColor:
                            String(x?.export_id || "") === String(selectedExportLogId || "")
                              ? "#2563eb"
                              : exists === false
                                ? "#b91c1c"
                                : "rgba(15,23,42,.08)",
                          background: exists === false ? "rgba(185,28,28,.06)" : undefined,
                        }}
                      >
                        <div className="small mono">{String(x?.export_id || "-")}</div>
                        <div className="small">文件数={String(x?.files_count ?? "-")}</div>
                        <div className="small">{String(x?.created_at || "")}</div>
                        <div className="small" style={{ color: exists === false ? "#b91c1c" : undefined }}>
                          {exists === false ? "路径缺失" : exists === true ? "路径正常" : "检查中..."}
                        </div>
                        <button onClick={() => setSelectedExportLogId(String(x?.export_id || ""))}>详情</button>
                        <button onClick={() => void openExportLogItem(x)}>打开</button>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
            <div className="small" style={{ marginTop: 6 }}>导出详情</div>
            {!selectedExportLog ? <div className="hint">请选择一条导出日志。</div> : null}
            {selectedExportLog ? (
              <div className="agent-audit-row">
                <div className="small mono">导出ID（export_id）：{String(selectedExportLog?.export_id || "-")}</div>
                <div className="small">包名：{String(selectedExportLog?.pack_name || "-")}</div>
                <div className="small">输出目录：{String(selectedExportLog?.output_dir || "-")}</div>
                <div className="small">创建时间：{String(selectedExportLog?.created_at || "-")}</div>
                <div className="small">文件数：{String(selectedExportFiles.length)}</div>
                {selectedExportPreflight ? (
                  <div className="small">
                    预检：{String((selectedExportPreflight as any)?.overall || "-")} · 失败=
                    {String((selectedExportPreflight as any)?.fail_count ?? "-")} · 警告=
                    {String((selectedExportPreflight as any)?.warn_count ?? "-")} · 建议=
                    {String((selectedExportPreflight as any)?.suggest_count ?? "-")}
                  </div>
                ) : null}
                <div className="row" style={{ gap: 8 }}>
                  <button onClick={() => void runRebuildSelected()}>重建所选</button>
                  <button onClick={() => void openExportLogItem(selectedExportLog)}>打开输出目录</button>
                  <button onClick={() => void runFixwizardPlan()} disabled={!bookId || !exportVolumeId.trim()}>
                    修复向导：生成方案
                  </button>
                  <button onClick={() => void runFixwizardExecute()} disabled={fixPlanItems.length === 0}>
                    执行已选修复
                  </button>
                  <button onClick={() => void runFixwizardRecheck()} disabled={!bookId || !exportVolumeId.trim()}>
                    复检
                  </button>
                </div>
                {selectedExportPreflightHints.length > 0 ? (
                  <details>
                    <summary className="small">预检提示（{selectedExportPreflightHints.length}）</summary>
                    <div className="scroll" style={{ maxHeight: 120 }}>
                      {selectedExportPreflightHints.map((h: any, i: number) => (
                        <div key={`${String(h?.code || "hint")}:${i}`} className="small" style={{ marginTop: 6 }}>
                          <div>
                            [{String(h?.code || "-")}] {String(h?.title_zh || h?.title || "-")}
                          </div>
                          <div style={{ color: "#475569" }}>
                            建议：{String(h?.action_zh || h?.action || "-")}
                          </div>
                        </div>
                      ))}
                    </div>
                  </details>
                ) : null}
                <div className="scroll" style={{ maxHeight: 140 }}>
                  {selectedExportFiles.length === 0 ? <div className="hint">清单中暂无文件。</div> : null}
                  {selectedExportFiles.map((f: any, idx: number) => (
                    <div key={`${String(f?.path || "")}:${idx}`} className="row" style={{ gap: 8, alignItems: "center" }}>
                      <div
                        className="small mono"
                        style={{
                          flex: 1,
                          overflowWrap: "anywhere",
                          color:
                            pathExistsMap[String(f?.path || "").trim()] === false ? "#b91c1c" : undefined,
                        }}
                      >
                        {String(f?.path || "-")}
                      </div>
                      <div className="small">大小={String(f?.size ?? "-")}</div>
                      <div className="small">
                        {pathExistsMap[String(f?.path || "").trim()] === false ? "缺失" : pathExistsMap[String(f?.path || "").trim()] === true ? "正常" : "检查中..."}
                      </div>
                      <button onClick={() => void openExportLogFile(f)}>打开文件</button>
                    </div>
                  ))}
                </div>
                <details style={{ marginTop: 6 }}>
                  <summary className="small">修复向导</summary>
                  <div className="small" style={{ marginTop: 6 }}>
                    修复项：{String(fixPlanItems.length)} · 已执行：{" "}
                    {String(Array.isArray(fixExecuteResult?.executed) ? fixExecuteResult.executed.length : 0)}
                  </div>
                  <div className="scroll" style={{ maxHeight: 160, marginTop: 6 }}>
                    {fixPlanItems.length === 0 ? <div className="hint">请先运行“修复向导：生成方案”。</div> : null}
                    {fixPlanItems.map((fx: any) => {
                      const fid = String(fx?.fix_id || "").trim();
                      return (
                        <div key={fid || JSON.stringify(fx)} className="agent-audit-row">
                          <label className="agent-checkbox">
                            <input
                              type="checkbox"
                              checked={!!fixSelectedIds[fid]}
                              onChange={(e) => setFixSelectedIds((m) => ({ ...m, [fid]: e.target.checked }))}
                            />
                            <span className="small" style={{ fontWeight: 600 }}>{String(fx?.title || fid || "-")}</span>
                          </label>
                          <div className="small">目标={String(fx?.target || "-")} · 类型={String(fx?.type || "-")} · 风险={String(fx?.risk || "-")}</div>
                          <div className="small" style={{ color: "#475569" }}>{String(fx?.reason || "")}</div>
                        </div>
                      );
                    })}
                  </div>
                  {fixExecuteResult ? <pre className="small">{JSON.stringify(fixExecuteResult, null, 2)}</pre> : null}
                </details>
              </div>
            ) : null}
            {cleanupResult ? (
              <details>
                <summary className="small">
                  清理结果 · 缺失={String(cleanupResult?.missing_count ?? 0)} · 已删除={String(cleanupResult?.deleted_count ?? 0)}
                </summary>
                <div className="row" style={{ gap: 8, marginTop: 6, marginBottom: 6 }}>
                  <button
                    onClick={() => {
                      const items = Array.isArray(cleanupResult?.items) ? cleanupResult.items : [];
                      const next: Record<string, boolean> = {};
                      for (const x of items) {
                        const xid = String(x?.export_id || "").trim();
                        if (xid) next[xid] = true;
                      }
                      setCleanupSelectedIds(next);
                    }}
                  >
                    全选缺失
                  </button>
                  <button onClick={() => setCleanupSelectedIds({})}>清空选择</button>
                  <button onClick={() => void runCleanupSelectedMissing()}>删除所选缺失</button>
                </div>
                <div className="scroll" style={{ maxHeight: 180 }}>
                  {(Array.isArray(cleanupResult?.items) ? cleanupResult.items : []).length === 0 ? (
                    <div className="hint">预览中无缺失记录。</div>
                  ) : null}
                  {(Array.isArray(cleanupResult?.items) ? cleanupResult.items : []).map((x: any) => {
                    const xid = String(x?.export_id || "").trim();
                    return (
                      <div key={xid || JSON.stringify(x)} className="agent-audit-row">
                        <label className="agent-checkbox">
                          <input
                            type="checkbox"
                            checked={!!cleanupSelectedIds[xid]}
                            onChange={(e) => setCleanupSelectedIds((m) => ({ ...m, [xid]: e.target.checked }))}
                          />
                          <span className="small mono">{xid || "-"}</span>
                        </label>
                        <div className="small">{String(x?.pack_name || "-")}</div>
                        <div className="small mono" style={{ overflowWrap: "anywhere" }}>{String(x?.output_dir || "-")}</div>
                        <div className="small">{String(x?.created_at || "")}</div>
                      </div>
                    );
                  })}
                </div>
                <pre className="small">{JSON.stringify(cleanupResult, null, 2)}</pre>
              </details>
            ) : null}
          </div>
          <div className="small">最近自动计划</div>
          <div className="agent-audit-row">
            <div className="small">状态（ok）：{String(planAutobuildSummary.ok)}</div>
            <div className="small">路径（route）：{planAutobuildSummary.route || "-"}</div>
            <div className="small mono">书籍：{planAutobuildSummary.bookId || "-"}</div>
            <div className="small mono">卷：{planAutobuildSummary.volumeId || "-"}</div>
            <div className="small">计划版本：{String(planAutobuildSummary.version || "-")}</div>
            <div className="small">条目数：{String(planAutobuildSummary.totalItems)}</div>
            <div className="small">
              组合：{" "}
              {planAutobuildSummary.comboCovered.length ? planAutobuildSummary.comboCovered.join(", ") : "-"}
            </div>
            {planAutobuildSummary.comboMissing.length ? (
              <div>
                <div className="small" style={{ color: "#b45309" }}>
                  缺失组合：{planAutobuildSummary.comboMissing.join(", ")}
                </div>
                <button onClick={useMissingAsActions} style={{ marginTop: 6 }}>
                  将缺失项作为动作
                </button>
              </div>
            ) : (
              <div className="small" style={{ color: "#15803d" }}>必需组合已全部覆盖</div>
            )}
          </div>
          <pre>{JSON.stringify(planAutobuildResult, null, 2)}</pre>
          <div className="small">最近应用</div>
          <pre>{JSON.stringify(applyResult, null, 2)}</pre>
          <div className="small">审计</div>
          <div className="scroll" style={{ maxHeight: 260 }}>
            <div className="small" style={{ marginBottom: 6 }}>
              显示 {visibleAudits.length} / {audits.length}
            </div>
            {visibleAudits.length === 0 ? <div className="hint">暂无审计或接口未支持。</div> : null}
            {visibleAudits.map((a: any) => {
              const aid = String(a.audit_id || a.id || "");
              const diff = (a?.after_state?.book_settings_diff || a?.after_state?.chapter_settings_diff || []) as any[];
              return (
                <div key={aid || JSON.stringify(a)} className="agent-audit-row">
                  <div className="small mono">{aid || "-"}</div>
                  <div className="small">{String(a.action_type || a.action || a.type || "")}</div>
                  <div className="small">{String(a.note || "")}</div>
                  {diff.length ? (
                    <details>
                      <summary className="small">差异（{diff.length}）</summary>
                      <pre className="small">{JSON.stringify(diff, null, 2)}</pre>
                    </details>
                  ) : null}
                  <AuditChangeView audit={a} />
                  <details>
                    <summary className="small">原始审计</summary>
                    <pre className="small">{JSON.stringify(a, null, 2)}</pre>
                  </details>
                  <button onClick={() => void rollback(aid)} disabled={!aid}>回滚</button>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <WorkflowRunnerPanel bookId={bookId} chapterId={chapterId} />

      <DeleteConfirmDialog
        open={!!cleanupConfirmDialog}
        title={cleanupConfirmDialog?.title || "清理确认"}
        requireInput={false}
        targetLabel={cleanupConfirmDialog?.targetLabel || ""}
        warning={cleanupConfirmDialog?.warning || "该操作不可撤销。"}
        expectedText={cleanupConfirmDialog?.expectedText || "清理"}
        value={cleanupConfirmValue}
        promptLabel={
          <>
            请输入校验词 <span className="mono">{cleanupConfirmDialog?.expectedText || "清理"}</span> 以继续
          </>
        }
        placeholder={cleanupConfirmDialog?.expectedText || "清理"}
        busy={busy === "export:cleanup" || busy === "export:cleanup:selected"}
        error={cleanupConfirmError}
        confirmLabel={cleanupConfirmDialog?.kind === "selected" ? "确认删除所选" : "确认清理"}
        busyLabel="处理中..."
        onValueChange={(v) => {
          setCleanupConfirmValue(v);
          if (cleanupConfirmError) setCleanupConfirmError("");
        }}
        onConfirm={() => {
          void confirmCleanupDialog();
        }}
        onCancel={() => {
          if (busy === "export:cleanup" || busy === "export:cleanup:selected") return;
          setCleanupConfirmDialog(null);
          setCleanupConfirmValue("");
          setCleanupConfirmError("");
        }}
        onMismatch={() => setCleanupConfirmError(`输入不匹配，请输入“${cleanupConfirmDialog?.expectedText || "清理"}”`)}
      />
    </section>
  );
}
