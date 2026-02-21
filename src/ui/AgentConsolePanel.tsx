import { useEffect, useMemo, useState } from "react";
import { WorkflowRunnerPanel } from "./WorkflowRunnerPanel";

type Props = {
  selectedBookId?: string;
  selectedChapterId?: string;
  onPickBookId?: (bookId: string) => void;
  onPickChapterId?: (chapterId: string) => void;
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
        change summary · foreshadow={String(counts.foreshadow ?? foreshadowKeys.length)} · growth=
        {String(counts.growth ?? growthKeys.length)}
      </summary>
      <div className="small" style={{ marginTop: 6 }}>
        {foreshadowKeys.length ? `foreshadow: ${foreshadowKeys.join(", ")}` : "foreshadow: -"}
      </div>
      <div className="small">
        {growthKeys.length ? `growth: ${growthKeys.join(", ")}` : "growth: -"}
      </div>
      <div className="agent-grid" style={{ marginTop: 6 }}>
        <div className="agent-col">
          <div className="small">before</div>
          <pre className="small">{JSON.stringify({ foreshadow: beforeF, growth: beforeG }, null, 2)}</pre>
        </div>
        <div className="agent-col">
          <div className="small">after</div>
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
          scope
          <select
            value={scope}
            onChange={(e) =>
              onChange({
                scope: e.target.value,
                chapter_id: e.target.value === "chapter" ? String(v.chapter_id || selectedChapterId || "") : "",
              })
            }
          >
            <option value="book">book</option>
            <option value="chapter">chapter</option>
          </select>
        </label>
        {scope === "chapter" ? (
          <label>
            chapter_id
            <input
              value={String(v.chapter_id ?? selectedChapterId ?? "")}
              onChange={(e) => onChange({ chapter_id: e.target.value })}
            />
          </label>
        ) : null}
        <label>
          max_structure_weight
          <input
            type="number"
            min={1}
            max={6}
            value={v.max_structure_weight ?? 4}
            onChange={(e) => onChange({ max_structure_weight: Number(e.target.value) })}
          />
        </label>
        <label>
          max_tasks
          <input
            type="number"
            min={1}
            max={4}
            value={v.max_tasks ?? 2}
            onChange={(e) => onChange({ max_tasks: Number(e.target.value) })}
          />
        </label>
        <label>
          replay.defer_max_rounds
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
          replay.defer_expire_grace
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
          ban_strong_cliff
        </label>
        <label>
          budget.character_facts.max_items
          <input type="number" min={1} max={20} value={Number(cf.max_items ?? 8)} onChange={(e) => setBudget("character_facts", { max_items: Number(e.target.value) })} />
        </label>
        <label>
          budget.character_facts.max_chars
          <input type="number" min={120} max={6000} value={Number(cf.max_chars ?? 1000)} onChange={(e) => setBudget("character_facts", { max_chars: Number(e.target.value) })} />
        </label>
        <label>
          budget.timeline_facts.max_items
          <input type="number" min={1} max={20} value={Number(tf.max_items ?? 8)} onChange={(e) => setBudget("timeline_facts", { max_items: Number(e.target.value) })} />
        </label>
        <label>
          budget.timeline_facts.max_chars
          <input type="number" min={120} max={6000} value={Number(tf.max_chars ?? 1000)} onChange={(e) => setBudget("timeline_facts", { max_chars: Number(e.target.value) })} />
        </label>
        <label>
          budget.open_foreshadows.max_items
          <input type="number" min={1} max={20} value={Number(of.max_items ?? 6)} onChange={(e) => setBudget("open_foreshadows", { max_items: Number(e.target.value) })} />
        </label>
        <label>
          budget.open_foreshadows.max_chars
          <input type="number" min={120} max={6000} value={Number(of.max_chars ?? 900)} onChange={(e) => setBudget("open_foreshadows", { max_chars: Number(e.target.value) })} />
        </label>
        <label>
          budget.growth_milestones.max_items
          <input type="number" min={1} max={20} value={Number(gm.max_items ?? 6)} onChange={(e) => setBudget("growth_milestones", { max_items: Number(e.target.value) })} />
        </label>
        <label>
          budget.growth_milestones.max_chars
          <input type="number" min={120} max={6000} value={Number(gm.max_chars ?? 900)} onChange={(e) => setBudget("growth_milestones", { max_chars: Number(e.target.value) })} />
        </label>
      </div>
    );
  }
  if (t === "inject_reveal_combo") {
    return (
      <div className="agent-form-grid">
        <label>
          window_next_chapters
          <input
            type="number"
            min={1}
            max={3}
            value={v.window_next_chapters ?? 2}
            onChange={(e) => onChange({ window_next_chapters: Number(e.target.value) })}
          />
        </label>
        <label>
          combo_type
          <input value={String(v.combo_type ?? "reveal_combo")} onChange={(e) => onChange({ combo_type: e.target.value })} />
        </label>
      </div>
    );
  }
  if (t === "rotate_combo_group") {
    return (
      <div className="agent-form-grid">
        <label>
          rotation_group
          <input value={String(v.rotation_group ?? "")} onChange={(e) => onChange({ rotation_group: e.target.value })} />
        </label>
        <label>
          cooldown_volumes
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
  const [fixPlan, setFixPlan] = useState<any>(null);
  const [fixSelectedIds, setFixSelectedIds] = useState<Record<string, boolean>>({});
  const [fixExecuteResult, setFixExecuteResult] = useState<any>(null);
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
    if (avg >= high) return { label: "high pressure", color: "#b91c1c" };
    if (avg >= medium) return { label: "medium pressure", color: "#b45309" };
    return { label: "stable", color: "#15803d" };
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
      const k = String(x?.pack_name || "unknown").trim() || "unknown";
      if (!groups[k]) groups[k] = [];
      groups[k].push(x);
    }
    return Object.entries(groups).sort((a, b) => a[0].localeCompare(b[0], "zh-CN"));
  }, [filteredExportLogs]);

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
      setInfo(`Sidecar started at ${String(out?.baseUrl || settings?.baseUrl || "-")}`);
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
      setInfo("Sidecar stopped.");
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
      setInfo(`Desktop ready. sidecar=${String(sh?.ok ? "ok" : "down")} api=${String(h?.ok ? "ok" : "down")}`);
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
      setInfo("No missing combos to add.");
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
    setInfo(`Added ${generated.length} action(s) from missing combos.`);
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
      setInfo("Workspace saved.");
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
      const msg = cleanupOnlyVisible
        ? `将清理“当前筛选结果”范围内的缺失导出记录（候选 ${exportIds.length} 条）。继续？`
        : "将清理本书范围内的缺失导出记录。继续？";
      if (!window.confirm(msg)) return;
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
        setInfo(`Cleanup done. deleted=${String(out?.deleted_count ?? 0)}`);
      }
      await loadExportLogs();
    } catch (e: any) {
      setErr(String(e?.message || e));
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
      setInfo(`Rebuilt from export_id=${exportId}`);
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
          `Fix executed. recheck overall=${String(out.recheck.summary.overall || "-")} fail=${String(
            out.recheck.summary.fail_count ?? "-"
          )} warn=${String(out.recheck.summary.warn_count ?? "-")}`
        );
      } else {
        setInfo("Fix executed.");
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
      setInfo(`Recheck done. overall=${String(s.overall || "-")} fail=${String(s.fail_count ?? "-")} warn=${String(s.warn_count ?? "-")}`);
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
    if (!window.confirm(`将删除已勾选的缺失导出记录 ${ids.length} 条。继续？`)) return;
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
      setInfo(`Deleted selected missing logs: ${String(out?.deleted_count ?? 0)}`);
      await loadExportLogs();
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
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
        <h3 style={{ margin: 0 }}>Agent Console</h3>
        <span className="small">{busy ? `busy: ${busy}` : "idle"}</span>
      </div>

      <div className="agent-topbar">
        <label>
          baseUrl
          <input
            value={String(settings?.baseUrl || "")}
            onChange={(e) => setSettings({ ...(settings || {}), baseUrl: e.target.value })}
            onBlur={() => void saveSettings({ baseUrl: String(settings?.baseUrl || "") })}
          />
        </label>
        <label>
          agentToken
          <input
            type="password"
            value={String(settings?.agentToken || "")}
            onChange={(e) => setSettings({ ...(settings || {}), agentToken: e.target.value })}
            onBlur={() => void saveSettings({ agentToken: String(settings?.agentToken || "") })}
          />
        </label>
        <label>
          timeoutMs
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
          sidecar_python
          <input
            value={String(settings?.sidecarPythonPath || "")}
            onChange={(e) => setSettings({ ...(settings || {}), sidecarPythonPath: e.target.value })}
            onBlur={() => void saveSettings({ sidecarPythonPath: String(settings?.sidecarPythonPath || "") })}
          />
        </label>
        <label>
          sidecar_exe
          <input
            value={String(settings?.sidecarExecutablePath || "")}
            onChange={(e) => setSettings({ ...(settings || {}), sidecarExecutablePath: e.target.value })}
            onBlur={() => void saveSettings({ sidecarExecutablePath: String(settings?.sidecarExecutablePath || "") })}
          />
        </label>
        <label>
          sidecar_cwd
          <input
            value={String(settings?.sidecarCwd || "")}
            onChange={(e) => setSettings({ ...(settings || {}), sidecarCwd: e.target.value })}
            onBlur={() => void saveSettings({ sidecarCwd: String(settings?.sidecarCwd || "") })}
          />
        </label>
        <label>
          sidecar_port
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
          <span className="small">auto_start</span>
        </label>
        <label>
          book_id
          <input
            value={bookId}
            onChange={(e) => {
              setBookId(e.target.value);
              props.onPickBookId?.(e.target.value);
            }}
          />
        </label>
        <label>
          chapter_id
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
          <button onClick={() => void runOneClickReady()} disabled={!!busy}>One-Click Ready</button>
          <button onClick={() => void runHealth()}>Health</button>
          <button onClick={() => void runSidecarStart()}>Start Sidecar</button>
          <button onClick={() => void runSidecarStop()}>Stop Sidecar</button>
          <button onClick={() => void runSidecarHealth()}>Sidecar Health</button>
          <button onClick={() => void runDiagnose()} disabled={!bookId}>Diagnose</button>
          <button onClick={() => void runPropose()} disabled={!bookId}>Propose</button>
          <button onClick={() => void runPlanAutobuild()} disabled={!bookId}>AutoBuild Plan</button>
          <button onClick={() => void runApply(false)} disabled={!bookId}>Apply Selected</button>
          <button onClick={() => void runApply(true)} disabled={!bookId}>Apply Dry Run</button>
          <button onClick={() => void loadAudits()} disabled={!bookId}>Refresh Audits</button>
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

      <div className="agent-grid">
        <div className="agent-col">
          <h4>Diagnosis</h4>
          <div className="small">health</div>
          <pre>{JSON.stringify(health, null, 2)}</pre>
          <div className="small">sidecar health</div>
          <pre>{JSON.stringify(sidecarHealth, null, 2)}</pre>
          <div className="small">sidecar logs</div>
          <div className="scroll" style={{ maxHeight: 120 }}>
            {sidecarLogs.length === 0 ? <div className="hint">No sidecar logs.</div> : null}
            {sidecarLogs.map((x, i) => (
              <div key={`${i}:${x}`} className="small mono">{x}</div>
            ))}
          </div>
          <div className="small">replay stats</div>
          {replayStats ? (
            <div className="agent-audit-row">
              <div className="small">sample_size: {String(replayStats.sample_size ?? "-")}</div>
              <div className="small">
                avg_replay_filtered:{" "}
                <span style={{ color: replayTone.color, fontWeight: 600 }}>
                  {String(replayStats.avg_replay_filtered ?? "-")} ({replayTone.label})
                </span>
              </div>
              <div className="small">
                max_round_hits:{" "}
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
                expired_hits:{" "}
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
                thresholds: medium={String(replayThresholds.avg_filtered_medium)} high={String(replayThresholds.avg_filtered_high)} low=
                {String(replayThresholds.avg_filtered_low)}
              </div>
              <div className="small">
                suggested replay: defer_max_rounds=
                <span style={{ fontWeight: 600 }}>{String(replaySuggestion?.defer_max_rounds ?? "-")}</span>
                {" , "}defer_expire_grace=
                <span style={{ fontWeight: 600 }}>{String(replaySuggestion?.defer_expire_grace ?? "-")}</span>
              </div>
            </div>
          ) : (
            <div className="hint">No replay stats yet.</div>
          )}
          <div className="small">diagnosis</div>
          <pre>{JSON.stringify(diagnosis, null, 2)}</pre>
        </div>

        <div className="agent-col">
          <h4>Proposed Actions</h4>
          {actions.length === 0 ? <div className="hint">No actions</div> : null}
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
                    <strong>{String(a.type || "action")}</strong>
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
          <h4>Execution & Audits</h4>
          <div className="small">chapter engineering export</div>
          <div className="agent-audit-row">
            <label>
              workspace_path
              <input value={workspacePath} onChange={(e) => setWorkspacePath(e.target.value)} />
            </label>
            <div className="row" style={{ gap: 8 }}>
              <button onClick={() => void loadWorkspaceBinding()} disabled={!bookId}>Load Workspace</button>
              <button onClick={() => void saveWorkspaceBinding()} disabled={!bookId || !workspacePath.trim()}>Save Workspace</button>
            </div>
            <label>
              volume_id
              <input value={exportVolumeId} onChange={(e) => setExportVolumeId(e.target.value)} placeholder="for volume/package export" />
            </label>
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <button onClick={() => void runExportChapter()} disabled={!bookId || !chapterId}>Export This Chapter</button>
              <button onClick={() => void runExportVolume()} disabled={!bookId || !exportVolumeId.trim()}>Export Volume</button>
              <button onClick={() => void runPublishPack()} disabled={!bookId || !exportVolumeId.trim()}>Build Publish Pack</button>
              <button onClick={() => void openExportFolder()} disabled={!exportResult?.output_dir && !exportResult?.output_path}>Open Export Folder</button>
              <button onClick={() => void loadExportLogs()} disabled={!bookId}>Refresh Export Logs</button>
            </div>
            <pre>{JSON.stringify(exportResult, null, 2)}</pre>
            <div className="row" style={{ gap: 8, alignItems: "center" }}>
              <div className="small">export logs ({filteredExportLogs.length}/{exportLogs.length})</div>
              <label className="small">
                range
                <select value={exportLogDays} onChange={(e) => setExportLogDays(e.target.value)}>
                  <option value="all">all</option>
                  <option value="7">7d</option>
                  <option value="30">30d</option>
                  <option value="90">90d</option>
                </select>
              </label>
              <button onClick={() => void runCleanupMissing(true)} disabled={!bookId}>Check Missing</button>
              <button onClick={() => void runCleanupMissing(false)} disabled={!bookId}>Cleanup Missing</button>
              <label className="agent-checkbox">
                <input
                  type="checkbox"
                  checked={cleanupOnlyVisible}
                  onChange={(e) => setCleanupOnlyVisible(e.target.checked)}
                />
                only current filtered logs
              </label>
            </div>
            <div className="scroll" style={{ maxHeight: 180 }}>
              {filteredExportLogs.length === 0 ? <div className="hint">No export logs.</div> : null}
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
                        <div className="small">files={String(x?.files_count ?? "-")}</div>
                        <div className="small">{String(x?.created_at || "")}</div>
                        <div className="small" style={{ color: exists === false ? "#b91c1c" : undefined }}>
                          {exists === false ? "path missing" : exists === true ? "path ok" : "checking..."}
                        </div>
                        <button onClick={() => setSelectedExportLogId(String(x?.export_id || ""))}>Details</button>
                        <button onClick={() => void openExportLogItem(x)}>Open</button>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
            <div className="small" style={{ marginTop: 6 }}>export detail</div>
            {!selectedExportLog ? <div className="hint">Select one export log entry.</div> : null}
            {selectedExportLog ? (
              <div className="agent-audit-row">
                <div className="small mono">export_id: {String(selectedExportLog?.export_id || "-")}</div>
                <div className="small">pack: {String(selectedExportLog?.pack_name || "-")}</div>
                <div className="small">output: {String(selectedExportLog?.output_dir || "-")}</div>
                <div className="small">created_at: {String(selectedExportLog?.created_at || "-")}</div>
                <div className="small">files: {String(selectedExportFiles.length)}</div>
                {selectedExportPreflight ? (
                  <div className="small">
                    preflight: {String((selectedExportPreflight as any)?.overall || "-")} · fail=
                    {String((selectedExportPreflight as any)?.fail_count ?? "-")} · warn=
                    {String((selectedExportPreflight as any)?.warn_count ?? "-")} · suggest=
                    {String((selectedExportPreflight as any)?.suggest_count ?? "-")}
                  </div>
                ) : null}
                <div className="row" style={{ gap: 8 }}>
                  <button onClick={() => void runRebuildSelected()}>Rebuild Selected</button>
                  <button onClick={() => void openExportLogItem(selectedExportLog)}>Open Output Dir</button>
                  <button onClick={() => void runFixwizardPlan()} disabled={!bookId || !exportVolumeId.trim()}>
                    Fix Wizard Plan
                  </button>
                  <button onClick={() => void runFixwizardExecute()} disabled={fixPlanItems.length === 0}>
                    Execute Selected Fixes
                  </button>
                  <button onClick={() => void runFixwizardRecheck()} disabled={!bookId || !exportVolumeId.trim()}>
                    Recheck
                  </button>
                </div>
                {selectedExportPreflightHints.length > 0 ? (
                  <details>
                    <summary className="small">preflight hints ({selectedExportPreflightHints.length})</summary>
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
                  {selectedExportFiles.length === 0 ? <div className="hint">No files in manifest.</div> : null}
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
                      <div className="small">size={String(f?.size ?? "-")}</div>
                      <div className="small">
                        {pathExistsMap[String(f?.path || "").trim()] === false ? "missing" : pathExistsMap[String(f?.path || "").trim()] === true ? "ok" : "checking..."}
                      </div>
                      <button onClick={() => void openExportLogFile(f)}>Open File</button>
                    </div>
                  ))}
                </div>
                <details style={{ marginTop: 6 }}>
                  <summary className="small">Fix Wizard</summary>
                  <div className="small" style={{ marginTop: 6 }}>
                    fixes: {String(fixPlanItems.length)} · executed:{" "}
                    {String(Array.isArray(fixExecuteResult?.executed) ? fixExecuteResult.executed.length : 0)}
                  </div>
                  <div className="scroll" style={{ maxHeight: 160, marginTop: 6 }}>
                    {fixPlanItems.length === 0 ? <div className="hint">Run "Fix Wizard Plan" to generate fix options.</div> : null}
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
                          <div className="small">target={String(fx?.target || "-")} · type={String(fx?.type || "-")} · risk={String(fx?.risk || "-")}</div>
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
                  cleanup result · missing={String(cleanupResult?.missing_count ?? 0)} · deleted={String(cleanupResult?.deleted_count ?? 0)}
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
                    Select All Missing
                  </button>
                  <button onClick={() => setCleanupSelectedIds({})}>Clear Selection</button>
                  <button onClick={() => void runCleanupSelectedMissing()}>Delete Selected Missing</button>
                </div>
                <div className="scroll" style={{ maxHeight: 180 }}>
                  {(Array.isArray(cleanupResult?.items) ? cleanupResult.items : []).length === 0 ? (
                    <div className="hint">No missing records in preview.</div>
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
          <div className="small">last plan autobuild</div>
          <div className="agent-audit-row">
            <div className="small">ok: {String(planAutobuildSummary.ok)}</div>
            <div className="small">route: {planAutobuildSummary.route || "-"}</div>
            <div className="small mono">book: {planAutobuildSummary.bookId || "-"}</div>
            <div className="small mono">volume: {planAutobuildSummary.volumeId || "-"}</div>
            <div className="small">plan version: {String(planAutobuildSummary.version || "-")}</div>
            <div className="small">items: {String(planAutobuildSummary.totalItems)}</div>
            <div className="small">
              combos:{" "}
              {planAutobuildSummary.comboCovered.length ? planAutobuildSummary.comboCovered.join(", ") : "-"}
            </div>
            {planAutobuildSummary.comboMissing.length ? (
              <div>
                <div className="small" style={{ color: "#b45309" }}>
                  missing combos: {planAutobuildSummary.comboMissing.join(", ")}
                </div>
                <button onClick={useMissingAsActions} style={{ marginTop: 6 }}>
                  Use Missing as Actions
                </button>
              </div>
            ) : (
              <div className="small" style={{ color: "#15803d" }}>all required combos covered</div>
            )}
          </div>
          <pre>{JSON.stringify(planAutobuildResult, null, 2)}</pre>
          <div className="small">last apply</div>
          <pre>{JSON.stringify(applyResult, null, 2)}</pre>
          <div className="small">audits</div>
          <div className="scroll" style={{ maxHeight: 260 }}>
            <div className="small" style={{ marginBottom: 6 }}>
              showing {visibleAudits.length} / {audits.length}
            </div>
            {visibleAudits.length === 0 ? <div className="hint">No audits / endpoint unsupported.</div> : null}
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
                      <summary className="small">diff ({diff.length})</summary>
                      <pre className="small">{JSON.stringify(diff, null, 2)}</pre>
                    </details>
                  ) : null}
                  <AuditChangeView audit={a} />
                  <details>
                    <summary className="small">raw audit</summary>
                    <pre className="small">{JSON.stringify(a, null, 2)}</pre>
                  </details>
                  <button onClick={() => void rollback(aid)} disabled={!aid}>Rollback</button>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <WorkflowRunnerPanel bookId={bookId} chapterId={chapterId} />
    </section>
  );
}
