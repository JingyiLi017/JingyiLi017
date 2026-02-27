import { useEffect, useMemo, useState } from "react";

type CapabilityClarityPanelProps = {
  baseUrl: string;
  bookId: string;
  chapterId: string;
  volumeId: string;
  splitbookId: string;
  retryMax?: number;
  retryBaseMs?: number;
  antiCopyReport?: any | null;
  onStatus?: (msg: string) => void;
  onRunRepairPlan?: () => Promise<void> | void;
  onRunTemplateEvolve?: () => Promise<void> | void;
  onRunAntiCopy?: () => Promise<void> | void;
};

function toNum(value: unknown, fallback = 0): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function pct(value: unknown): string {
  const n = toNum(value, 0);
  return `${Math.round(n * 100)}%`;
}

function riskText(risk: string): string {
  const x = String(risk || "").toLowerCase();
  if (x === "high") return "高风险";
  if (x === "medium" || x === "mid") return "中风险";
  if (x === "low") return "低风险";
  return "未评估";
}

function Sparkline(props: { values: number[]; color?: string }) {
  const color = props.color || "#0f766e";
  const values = props.values.filter((x) => Number.isFinite(x));
  if (!values.length) {
    return <div className="clarity-empty">暂无曲线数据</div>;
  }
  const w = 420;
  const h = 120;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(0.0001, max - min);
  const points = values
    .map((v, i) => {
      const x = (i / Math.max(1, values.length - 1)) * (w - 8) + 4;
      const y = h - 6 - ((v - min) / span) * (h - 16);
      return `${x},${y}`;
    })
    .join(" ");
  const latest = values[values.length - 1];
  return (
    <div className="clarity-chart-wrap">
      <svg viewBox={`0 0 ${w} ${h}`} className="clarity-sparkline" role="img" aria-label="趋势曲线">
        <polyline points={points} fill="none" stroke={color} strokeWidth={2.6} strokeLinejoin="round" strokeLinecap="round" />
      </svg>
      <div className="clarity-chart-meta">
        <span>最小 {min.toFixed(3)}</span>
        <span>最新 {latest.toFixed(3)}</span>
        <span>最大 {max.toFixed(3)}</span>
      </div>
    </div>
  );
}

export function CapabilityClarityPanel(props: CapabilityClarityPanelProps) {
  const {
    baseUrl,
    bookId,
    chapterId,
    volumeId,
    splitbookId,
    retryMax,
    retryBaseMs,
    antiCopyReport,
    onStatus,
    onRunRepairPlan,
    onRunTemplateEvolve,
    onRunAntiCopy,
  } = props;
  const AUTO_RETRY_MAX = Math.max(1, Math.min(8, Math.round(toNum(retryMax, 3))));
  const AUTO_RETRY_BASE_MS = Math.max(200, Math.min(5000, Math.round(toNum(retryBaseMs, 600))));
  type ChainStepId = "anti_copy" | "repair" | "template" | "agent";
  type ChainFailure = { id: ChainStepId; label: string; error: string; attempts: number };
  type ChainStep = { id: ChainStepId; label: string; enabled: boolean };
  const [loading, setLoading] = useState(false);
  const [autoRunBusy, setAutoRunBusy] = useState(false);
  const [chainBusy, setChainBusy] = useState(false);
  const [chainStepIndex, setChainStepIndex] = useState(0);
  const [chainStepTotal, setChainStepTotal] = useState(0);
  const [chainStepLabel, setChainStepLabel] = useState("");
  const [chainFailures, setChainFailures] = useState<ChainFailure[]>([]);
  const [chainSuccesses, setChainSuccesses] = useState<string[]>([]);
  const [chainPlanLabels, setChainPlanLabels] = useState<string[]>([]);
  const [compactMode, setCompactMode] = useState(true);
  const [growthCurve, setGrowthCurve] = useState<any | null>(null);
  const [tensionReport, setTensionReport] = useState<any | null>(null);
  const [engineDashboard, setEngineDashboard] = useState<any | null>(null);
  const [storyBibleSnapshot, setStoryBibleSnapshot] = useState<any | null>(null);
  const [agentDiag, setAgentDiag] = useState<any | null>(null);
  const [styleLatest, setStyleLatest] = useState<any | null>(null);
  const [variantRows, setVariantRows] = useState<any[]>([]);
  const [compareRows, setCompareRows] = useState<any | null>(null);
  const [autoRunResult, setAutoRunResult] = useState<any | null>(null);
  const [errorText, setErrorText] = useState("");

  async function fetchJson(url: string, init?: RequestInit): Promise<any> {
    const res = await fetch(url, init);
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(`${res.status}: ${txt || "REQUEST_FAILED"}`);
    }
    return res.json();
  }

  async function refreshAll() {
    if (!bookId.trim()) {
      setGrowthCurve(null);
      setTensionReport(null);
      setEngineDashboard(null);
      setStoryBibleSnapshot(null);
      setAgentDiag(null);
      setStyleLatest(null);
      setVariantRows([]);
      setCompareRows(null);
      setErrorText("");
      return;
    }
    setLoading(true);
    setErrorText("");
    try {
      const qChapter = chapterId.trim() ? `&chapter_id=${encodeURIComponent(chapterId.trim())}` : "";
      const compareQs = splitbookId.trim()
        ? `splitbook_ids=${encodeURIComponent(splitbookId.trim())}&limit=6`
        : "limit=6";
      const [growth, tension, engineDash, storyBible, agent, style, variants, compare] = await Promise.all([
        fetchJson(`${baseUrl}/v1/books/${bookId}/growth/curve`),
        fetchJson(`${baseUrl}/v1/books/${bookId}/tension/report?latest=1`),
        fetchJson(`${baseUrl}/v1/books/${bookId}/engine/dashboard`),
        fetchJson(`${baseUrl}/v1/books/${bookId}/story_bible?limit=20${chapterId.trim() ? `&chapter_id=${encodeURIComponent(chapterId.trim())}` : ""}`),
        fetchJson(`${baseUrl}/v1/agent/diagnose?book_id=${encodeURIComponent(bookId)}${qChapter}`),
        fetchJson(`${baseUrl}/v1/books/${bookId}/style/evolution/latest`),
        fetchJson(`${baseUrl}/v1/templates/variants?enabled=all`),
        fetchJson(`${baseUrl}/v1/splitbooks/compare?${compareQs}`),
      ]);
      setGrowthCurve(growth || null);
      setTensionReport(tension || null);
      setEngineDashboard(engineDash || null);
      setStoryBibleSnapshot(storyBible || null);
      setAgentDiag(agent || null);
      setStyleLatest(style || null);
      setVariantRows(Array.isArray(variants?.items) ? variants.items : []);
      setCompareRows(compare || null);
      setErrorText("");
    } catch (err) {
      const msg = `能力观测刷新失败：${String(err)}`;
      setErrorText(msg);
      onStatus?.(msg);
    } finally {
      setLoading(false);
    }
  }

  async function runAgentAuto(opts?: { throwOnError?: boolean }) {
    if (!bookId.trim() || !volumeId.trim()) {
      onStatus?.("Agent 总控需要先选择书籍与卷");
      return;
    }
    setAutoRunBusy(true);
    try {
      const payload: any = {
        book_id: bookId.trim(),
        volume_id: volumeId.trim(),
        automation_preset: "balanced",
      };
      if (chapterId.trim()) payload.chapter_id = chapterId.trim();
      const out = await fetchJson(`${baseUrl}/v1/skillpacks/auto_run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setAutoRunResult(out || null);
      const autoCount = Array.isArray(out?.auto_selected_fixes) ? out.auto_selected_fixes.length : 0;
      const manualCount = Array.isArray(out?.manual_fixes) ? out.manual_fixes.length : 0;
      onStatus?.(`Agent 总控已执行：自动处理 ${autoCount} 项，待人工 ${manualCount} 项`);
      await refreshAll();
    } catch (err) {
      onStatus?.(`Agent 总控执行失败：${String(err)}`);
      if (opts?.throwOnError) throw err;
    } finally {
      setAutoRunBusy(false);
    }
  }

  useEffect(() => {
    void refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseUrl, bookId, chapterId, splitbookId]);

  const growthGlobal = useMemo(() => (Array.isArray(growthCurve?.global_curve) ? growthCurve.global_curve : []), [growthCurve]);
  const growthCharacters = useMemo(() => (Array.isArray(growthCurve?.characters) ? growthCurve.characters : []), [growthCurve]);
  const tensionResult = useMemo(
    () => (tensionReport?.output?.result && typeof tensionReport.output.result === "object" ? tensionReport.output.result : {}),
    [tensionReport]
  );
  const storyEngineKpi = useMemo(() => (engineDashboard?.kpi && typeof engineDashboard.kpi === "object" ? engineDashboard.kpi : {}), [engineDashboard]);
  const storyBibleSummary = useMemo(
    () => (storyBibleSnapshot?.summary && typeof storyBibleSnapshot.summary === "object" ? storyBibleSnapshot.summary : {}),
    [storyBibleSnapshot]
  );
  const trends = useMemo(() => (tensionResult?.book_trends && typeof tensionResult.book_trends === "object" ? tensionResult.book_trends : {}), [tensionResult]);
  const tensionOverall = Array.isArray(trends?.overall_ma) ? trends.overall_ma.map((x: unknown) => toNum(x, 0)) : [];
  const tensionConflict = Array.isArray(trends?.conflict_ma) ? trends.conflict_ma.map((x: unknown) => toNum(x, 0)) : [];
  const tensionPeaks = tensionResult?.peaks && typeof tensionResult.peaks === "object" ? tensionResult.peaks : {};
  const tensionDiagnosis = Array.isArray(tensionResult?.diagnosis) ? tensionResult.diagnosis : [];
  const agentDiagnosis = agentDiag?.diagnosis && typeof agentDiag.diagnosis === "object" ? agentDiag.diagnosis : {};
  const agentAlerts = Array.isArray(agentDiagnosis?.alerts) ? agentDiagnosis.alerts : [];
  const styleOutput = styleLatest?.item?.output && typeof styleLatest.item.output === "object" ? styleLatest.item.output : {};
  const comparePairwise = Array.isArray(compareRows?.pairwise) ? compareRows.pairwise : [];
  const compareItems = Array.isArray(compareRows?.items) ? compareRows.items : [];

  const growthLatest = growthGlobal.length ? toNum(growthGlobal[growthGlobal.length - 1]?.cumulative, 0) : 0;
  const growthDeltaLatest = growthGlobal.length ? toNum(growthGlobal[growthGlobal.length - 1]?.delta, 0) : 0;
  const peakDensity = toNum(tensionPeaks?.density_per_10, 0);
  const tensionLatest = tensionOverall.length ? tensionOverall[tensionOverall.length - 1] : 0;
  const antiCopyScore = toNum(antiCopyReport?.anti_copy_score, -1);
  const antiCopyRisk = String(antiCopyReport?.risk_level || "");
  const variantsEnabled = variantRows.filter((x) => Boolean(x?.enabled)).length;
  const avgSimilarity =
    comparePairwise.length > 0
      ? comparePairwise.reduce((acc: number, row: any) => acc + toNum(row?.similarity, 0), 0) / comparePairwise.length
      : 0;
  const scenePackCoverage = toNum(storyEngineKpi?.scene_pack_coverage, 0);
  const auditCoverage = toNum(storyEngineKpi?.audit_coverage, 0);
  const pendingProposalCount = toNum(storyEngineKpi?.proposal_pending_count, 0);
  const overdueForeshadowCount = toNum(storyEngineKpi?.foreshadow_overdue_count, 0);
  const bibleCharacterCount = toNum(storyBibleSummary?.character_count, toNum(storyEngineKpi?.character_count, 0));
  const bibleWorldCount = toNum(storyBibleSummary?.world_rule_count, toNum(storyEngineKpi?.world_rule_count, 0));

  const recommendedActions = useMemo(() => {
    const out: string[] = [];
    if (peakDensity < 0.9) out.push("冲突峰值密度偏低，建议先执行“自动补冲突”。");
    if (scenePackCoverage < 0.6) out.push("场景卡覆盖率偏低，建议先生成章节包再扩写正文。");
    if (auditCoverage < 0.6) out.push("章节体检覆盖率偏低，建议开启“每章必体检”流程。");
    if (overdueForeshadowCount > 0) out.push(`存在 ${overdueForeshadowCount} 条过期伏笔，建议优先回收或关闭。`);
    if (pendingProposalCount > 0) out.push(`Story Bible 待审核提案 ${pendingProposalCount} 条，建议先裁决后继续写作。`);
    if (tensionDiagnosis.length > 0) out.push(`存在 ${tensionDiagnosis.length} 条张力诊断，优先处理 high 严重项。`);
    if (agentAlerts.length > 0) out.push(`Agent 监测到 ${agentAlerts.length} 条读者/结构告警。`);
    if (antiCopyRisk === "high") out.push("反照抄高风险，建议先重建章节包后再生成正文。");
    if (variantsEnabled < 2) out.push("模板变体启用数量偏少，建议执行模板进化。");
    if (!out.length) out.push("当前节奏与约束较稳定，可继续推进章节闭环。");
    return out.slice(0, 5);
  }, [peakDensity, tensionDiagnosis.length, agentAlerts.length, antiCopyRisk, variantsEnabled]);

  const antiCopyLevel: "high" | "mid" | "low" = antiCopyRisk === "high" ? "high" : antiCopyRisk === "medium" || antiCopyRisk === "mid" ? "mid" : "low";
  const tensionLevel: "high" | "mid" | "low" =
    tensionDiagnosis.length >= 3 || peakDensity < 0.7 ? "high" : tensionDiagnosis.length > 0 || peakDensity < 0.9 ? "mid" : "low";
  const agentLevel: "high" | "mid" | "low" = agentAlerts.length >= 3 ? "high" : agentAlerts.length > 0 ? "mid" : "low";
  const templateLevel: "high" | "mid" | "low" = variantsEnabled <= 0 ? "high" : variantsEnabled <= 1 ? "mid" : "low";
  const compareLevel: "high" | "mid" | "low" =
    compareItems.length <= 1 ? "mid" : avgSimilarity >= 0.9 ? "high" : avgSimilarity >= 0.75 ? "mid" : "low";
  const styleLevel: "high" | "mid" | "low" = styleOutput?.updated ? "low" : styleOutput?.skipped ? "mid" : "mid";
  const bibleLevel: "high" | "mid" | "low" =
    overdueForeshadowCount >= 3 || pendingProposalCount >= 8 || bibleCharacterCount <= 0 ? "high" : overdueForeshadowCount > 0 || pendingProposalCount > 0 ? "mid" : "low";
  const processLevel: "high" | "mid" | "low" =
    scenePackCoverage < 0.45 || auditCoverage < 0.35 ? "high" : scenePackCoverage < 0.75 || auditCoverage < 0.7 ? "mid" : "low";

  function maxLevel(levels: Array<"high" | "mid" | "low">): "high" | "mid" | "low" {
    if (levels.includes("high")) return "high";
    if (levels.includes("mid")) return "mid";
    return "low";
  }
  const overallLevel = maxLevel([antiCopyLevel, tensionLevel, agentLevel, templateLevel, compareLevel, styleLevel, bibleLevel, processLevel]);
  const overallText = overallLevel === "high" ? "红灯（需先修复）" : overallLevel === "mid" ? "黄灯（建议优化）" : "绿灯（可继续）";

  type PrimaryAction = "repair" | "anti_copy" | "template" | "agent" | "none";
  const primaryAction: PrimaryAction =
    antiCopyLevel === "high"
      ? "anti_copy"
      : processLevel === "high" || bibleLevel === "high"
        ? "agent"
      : tensionLevel !== "low"
        ? "repair"
        : templateLevel !== "low"
          ? "template"
          : agentLevel !== "low"
            ? "agent"
            : "none";
  const primaryActionText =
    primaryAction === "anti_copy"
      ? "先做反照抄检测"
      : processLevel === "high" || bibleLevel === "high"
        ? "先做 Agent 总控（补章包/体检）"
      : primaryAction === "repair"
        ? "先做自动补冲突"
        : primaryAction === "template"
          ? "先做自动模板进化"
          : primaryAction === "agent"
            ? "先做 Agent 总控执行"
            : "继续章节闭环";

  const autoChainSteps = useMemo<ChainStep[]>(() => {
    const steps: ChainStep[] = [
      { id: "anti_copy", label: "反照抄检测", enabled: antiCopyLevel === "high" && !!splitbookId },
      { id: "repair", label: "自动补冲突", enabled: tensionLevel !== "low" },
      { id: "template", label: "自动模板进化", enabled: templateLevel !== "low" },
      { id: "agent", label: "Agent 总控执行", enabled: agentLevel !== "low" || overallLevel !== "low" },
    ];
    return steps.filter((x) => x.enabled);
  }, [antiCopyLevel, splitbookId, tensionLevel, templateLevel, agentLevel, overallLevel]);

  async function runPrimaryAction() {
    if (primaryAction === "anti_copy") {
      await onRunAntiCopy?.();
      return;
    }
    if (primaryAction === "repair") {
      await onRunRepairPlan?.();
      return;
    }
    if (primaryAction === "template") {
      await onRunTemplateEvolve?.();
      return;
    }
    if (primaryAction === "agent") {
      await runAgentAuto();
      return;
    }
    onStatus?.("当前状态稳定，可继续执行章节闭环。");
  }

  async function runChainStep(step: ChainStep): Promise<void> {
    if (step.id === "anti_copy") {
      if (!onRunAntiCopy) throw new Error("ANTI_COPY_HANDLER_NOT_BOUND");
      await onRunAntiCopy();
      await refreshAll();
      return;
    }
    if (step.id === "repair") {
      if (!onRunRepairPlan) throw new Error("REPAIR_HANDLER_NOT_BOUND");
      await onRunRepairPlan();
      await refreshAll();
      return;
    }
    if (step.id === "template") {
      if (!onRunTemplateEvolve) throw new Error("TEMPLATE_HANDLER_NOT_BOUND");
      await onRunTemplateEvolve();
      await refreshAll();
      return;
    }
    await runAgentAuto({ throwOnError: true });
  }

  function sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function isRetryableError(err: unknown): boolean {
    const txt = String(err || "").toUpperCase();
    if (txt.includes("NOT_BOUND")) return false;
    if (txt.includes("REQUIRED")) return false;
    if (txt.includes("400")) return false;
    return true;
  }

  async function executeStepWithRetry(step: ChainStep): Promise<{ ok: boolean; attempts: number; error?: string }> {
    let attempts = 0;
    let lastError = "";
    while (attempts < AUTO_RETRY_MAX) {
      attempts += 1;
      try {
        await runChainStep(step);
        return { ok: true, attempts };
      } catch (err) {
        lastError = String(err);
        if (!isRetryableError(err)) break;
        if (attempts >= AUTO_RETRY_MAX) break;
        const delay = AUTO_RETRY_BASE_MS * Math.pow(2, attempts - 1);
        await sleep(delay);
      }
    }
    return { ok: false, attempts, error: lastError || "UNKNOWN_STEP_ERROR" };
  }

  async function runAutoChain() {
    if (chainBusy || !bookId) return;
    if (!autoChainSteps.length) {
      onStatus?.("当前无高优先级自动处置步骤，可继续章节闭环。");
      return;
    }
    setChainBusy(true);
    setChainStepIndex(0);
    setChainStepTotal(autoChainSteps.length);
    setChainStepLabel("准备开始");
    setChainFailures([]);
    setChainSuccesses([]);
    setChainPlanLabels(autoChainSteps.map((x) => x.label));
    const failures: ChainFailure[] = [];
    const successes: string[] = [];
    try {
      for (let i = 0; i < autoChainSteps.length; i += 1) {
        const step = autoChainSteps[i];
        setChainStepIndex(i + 1);
        setChainStepLabel(step.label);
        const exec = await executeStepWithRetry(step);
        if (exec.ok) {
          successes.push(step.label);
          setChainSuccesses([...successes]);
          if (exec.attempts > 1) onStatus?.(`${step.label} 在第 ${exec.attempts} 次尝试后成功`);
        } else {
          const msg = String(exec.error || "UNKNOWN_STEP_ERROR");
          failures.push({ id: step.id, label: step.label, error: msg, attempts: exec.attempts });
          setChainFailures([...failures]);
          onStatus?.(`串联步骤失败（已重试 ${exec.attempts} 次并跳过）：${step.label} - ${msg}`);
        }
      }
      setChainStepLabel(failures.length ? "部分失败（已完成）" : "已完成");
      if (failures.length) {
        onStatus?.(`自动串联执行完成：成功 ${successes.length} 步，失败 ${failures.length} 步（已跳过并继续）`);
      } else {
        onStatus?.(`自动串联执行完成：共 ${autoChainSteps.length} 步`);
      }
    } catch (err) {
      const msg = `自动串联执行失败：${String(err)}`;
      setChainStepLabel("执行失败");
      onStatus?.(msg);
    } finally {
      setChainBusy(false);
    }
  }

  async function retryFailedChainSteps() {
    if (chainBusy || !bookId) return;
    if (!chainFailures.length) {
      onStatus?.("当前没有失败步骤可重试。");
      return;
    }
    const retrySteps: ChainStep[] = chainFailures.map((f) => ({ id: f.id, label: f.label, enabled: true }));
    setChainBusy(true);
    setChainStepIndex(0);
    setChainStepTotal(retrySteps.length);
    setChainStepLabel("重试失败步骤");
    setChainPlanLabels(retrySteps.map((x) => x.label));
    const failures: ChainFailure[] = [];
    const successes = [...chainSuccesses];
    try {
      for (let i = 0; i < retrySteps.length; i += 1) {
        const step = retrySteps[i];
        setChainStepIndex(i + 1);
        setChainStepLabel(`重试：${step.label}`);
        const exec = await executeStepWithRetry(step);
        if (exec.ok) {
          if (!successes.includes(step.label)) successes.push(step.label);
          setChainSuccesses([...successes]);
          if (exec.attempts > 1) onStatus?.(`${step.label} 在第 ${exec.attempts} 次尝试后重试成功`);
        } else {
          const msg = String(exec.error || "UNKNOWN_STEP_ERROR");
          failures.push({ id: step.id, label: step.label, error: msg, attempts: exec.attempts });
          setChainFailures([...failures]);
          onStatus?.(`重试失败（已重试 ${exec.attempts} 次并跳过）：${step.label} - ${msg}`);
        }
      }
      setChainFailures(failures);
      setChainStepLabel(failures.length ? "重试结束（仍有失败）" : "重试全部成功");
      if (failures.length) {
        onStatus?.(`重试结束：成功 ${retrySteps.length - failures.length} 步，仍失败 ${failures.length} 步`);
      } else {
        onStatus?.(`重试完成：${retrySteps.length} 步全部成功`);
      }
    } finally {
      setChainBusy(false);
    }
  }

  async function retrySingleFailedStep(targetIndex: number) {
    if (chainBusy || !bookId) return;
    const target = chainFailures[targetIndex];
    if (!target) {
      onStatus?.("目标失败步骤不存在。");
      return;
    }
    const step: ChainStep = { id: target.id, label: target.label, enabled: true };
    setChainBusy(true);
    setChainStepIndex(0);
    setChainStepTotal(1);
    setChainStepLabel("重试单项");
    setChainPlanLabels([step.label]);
    try {
      setChainStepIndex(1);
      setChainStepLabel(`重试：${step.label}`);
      const exec = await executeStepWithRetry(step);
      if (exec.ok) {
        setChainFailures((prev) => prev.filter((_, idx) => idx !== targetIndex));
        setChainSuccesses((prev) => (prev.includes(step.label) ? prev : [...prev, step.label]));
        setChainStepLabel("单项重试成功");
        onStatus?.(`单项重试成功：${step.label}${exec.attempts > 1 ? `（第 ${exec.attempts} 次）` : ""}`);
      } else {
        const msg = String(exec.error || "UNKNOWN_STEP_ERROR");
        setChainFailures((prev) => prev.map((f, idx) => (idx === targetIndex ? { ...f, error: msg, attempts: exec.attempts } : f)));
        setChainStepLabel("单项重试失败");
        onStatus?.(`单项重试失败：${step.label}（已重试 ${exec.attempts} 次） - ${msg}`);
      }
    } finally {
      setChainBusy(false);
    }
  }

  const chainPct = chainStepTotal > 0 ? Math.min(100, Math.round((chainStepIndex / chainStepTotal) * 100)) : 0;

  return (
    <section id="section-capability-clarity" className="wb-panel capability-clarity-panel" style={{ minHeight: "auto", marginBottom: 10 }}>
      <div className="row" style={{ marginBottom: 8, alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <h3 style={{ margin: 0 }}>③ 能力观测总览</h3>
          <div className="small">默认驾驶舱模式（红黄绿）+ 一键推荐动作；需要时再展开细节。</div>
        </div>
        <div className="clarity-actions">
          <button onClick={() => void refreshAll()} disabled={loading}>{loading ? "刷新中..." : "刷新观测"}</button>
          <button onClick={() => void runPrimaryAction()} disabled={!bookId || autoRunBusy}>{primaryActionText}</button>
          <button onClick={() => void runAutoChain()} disabled={!bookId || chainBusy || autoRunBusy}>
            {chainBusy ? "串联执行中..." : "自动串联执行"}
          </button>
          <button onClick={() => void retryFailedChainSteps()} disabled={!bookId || chainBusy || autoRunBusy || !chainFailures.length}>
            重试失败步骤
          </button>
          <button onClick={() => setCompactMode((v) => !v)}>{compactMode ? "展开细节" : "收起细节"}</button>
        </div>
      </div>

      {!bookId ? <div className="hint">请先在“写作引擎工作台”选择书籍，能力观测面板会自动加载。</div> : null}
      {errorText ? <div className="hint" style={{ color: "#b91c1c" }}>{errorText}</div> : null}
      {chainStepTotal > 0 ? (
        <div className="clarity-chain-panel">
          <div className="small">自动处置进度：{chainStepIndex}/{chainStepTotal} · {chainStepLabel || "-"}</div>
          <div className="clarity-chain-bar">
            <span style={{ width: `${chainPct}%` }} />
          </div>
          <div className="small">计划步骤：{chainPlanLabels.join(" -> ") || "无"}</div>
          {chainSuccesses.length ? (
            <div className="small">成功步骤：{chainSuccesses.join("、")}</div>
          ) : null}
          {chainFailures.length ? (
            <details className="clarity-chain-failures">
              <summary>失败清单（{chainFailures.length}）</summary>
              <div className="clarity-chain-failure-list">
                {chainFailures.map((f, idx) => (
                  <div key={`${f.id}-${idx}`} className="clarity-chain-failure-item">
                    <div className="clarity-chain-failure-head">
                      <strong>{idx + 1}. {f.label}</strong>
                      <button onClick={() => void retrySingleFailedStep(idx)} disabled={chainBusy || autoRunBusy}>重试此项</button>
                    </div>
                    <span className="small">已重试次数：{f.attempts}</span>
                    <span>{f.error}</span>
                  </div>
                ))}
              </div>
            </details>
          ) : null}
        </div>
      ) : null}

      <div className="clarity-cockpit-grid">
        <div className={`clarity-cockpit-card level-${overallLevel}`}>
          <div className="k">总状态</div>
          <div className="v">{overallText}</div>
          <div className="small">推荐动作：{primaryActionText}</div>
        </div>
        <div className={`clarity-cockpit-card level-${tensionLevel}`}>
          <div className="k">冲突/张力</div>
          <div className="v">{tensionLevel === "high" ? "红灯" : tensionLevel === "mid" ? "黄灯" : "绿灯"}</div>
          <div className="small">告警 {tensionDiagnosis.length} · 峰值密度 {peakDensity.toFixed(2)}</div>
        </div>
        <div className={`clarity-cockpit-card level-${antiCopyLevel}`}>
          <div className="k">反照抄</div>
          <div className="v">{antiCopyLevel === "high" ? "红灯" : antiCopyLevel === "mid" ? "黄灯" : "绿灯"}</div>
          <div className="small">评分 {antiCopyScore >= 0 ? antiCopyScore : "-"} · {riskText(antiCopyRisk)}</div>
        </div>
        <div className={`clarity-cockpit-card level-${agentLevel}`}>
          <div className="k">Agent 总控</div>
          <div className="v">{agentLevel === "high" ? "红灯" : agentLevel === "mid" ? "黄灯" : "绿灯"}</div>
          <div className="small">结构告警 {agentAlerts.length}</div>
        </div>
        <div className={`clarity-cockpit-card level-${templateLevel}`}>
          <div className="k">模板进化</div>
          <div className="v">{templateLevel === "high" ? "红灯" : templateLevel === "mid" ? "黄灯" : "绿灯"}</div>
          <div className="small">启用变体 {variantsEnabled}/{variantRows.length}</div>
        </div>
        <div className={`clarity-cockpit-card level-${bibleLevel}`}>
          <div className="k">Story Bible</div>
          <div className="v">{bibleLevel === "high" ? "红灯" : bibleLevel === "mid" ? "黄灯" : "绿灯"}</div>
          <div className="small">待审提案 {pendingProposalCount} · 过期伏笔 {overdueForeshadowCount}</div>
        </div>
        <div className={`clarity-cockpit-card level-${processLevel}`}>
          <div className="k">章包/体检覆盖</div>
          <div className="v">{processLevel === "high" ? "红灯" : processLevel === "mid" ? "黄灯" : "绿灯"}</div>
          <div className="small">章包 {Math.round(scenePackCoverage * 100)}% · 体检 {Math.round(auditCoverage * 100)}%</div>
        </div>
        <div className={`clarity-cockpit-card level-${compareLevel}`}>
          <div className="k">多书对比</div>
          <div className="v">{compareLevel === "high" ? "红灯" : compareLevel === "mid" ? "黄灯" : "绿灯"}</div>
          <div className="small">均值相似度 {comparePairwise.length ? `${Math.round(avgSimilarity * 100)}%` : "-"}</div>
        </div>
      </div>

      <details className="clarity-advanced-actions" open={!compactMode}>
        <summary>高级动作（手动）</summary>
        <div className="clarity-actions" style={{ marginTop: 8 }}>
          <button onClick={() => void onRunRepairPlan?.()} disabled={!bookId}>自动补冲突</button>
          <button onClick={() => void onRunTemplateEvolve?.()} disabled={!bookId}>自动模板进化</button>
          <button onClick={() => void runAgentAuto()} disabled={autoRunBusy || !bookId || !volumeId}>
            {autoRunBusy ? "总控执行中..." : "Agent 总控执行"}
          </button>
          <button onClick={() => void onRunAntiCopy?.()} disabled={!splitbookId}>反照抄检测</button>
        </div>
      </details>

      {!compactMode ? <div className="clarity-kpi-grid">
        <div className="clarity-kpi-card">
          <div className="k">成长总强度</div>
          <div className="v">{growthLatest.toFixed(2)}</div>
          <div className="small">本章增量 {growthDeltaLatest.toFixed(2)} · 角色 {growthCharacters.length}</div>
        </div>
        <div className="clarity-kpi-card">
          <div className="k">剧情张力</div>
          <div className="v">{pct(tensionLatest)}</div>
          <div className="small">峰值密度/10章 {peakDensity.toFixed(2)}</div>
        </div>
        <div className="clarity-kpi-card">
          <div className="k">冲突告警</div>
          <div className="v">{tensionDiagnosis.length}</div>
          <div className="small">建议自动补冲突并回收伏笔</div>
        </div>
        <div className="clarity-kpi-card">
          <div className="k">反照抄评分</div>
          <div className="v">{antiCopyScore >= 0 ? antiCopyScore : "-"}</div>
          <div className={`clarity-risk-badge risk-${antiCopyRisk || "none"}`}>{riskText(antiCopyRisk)}</div>
        </div>
        <div className="clarity-kpi-card">
          <div className="k">Agent 告警</div>
          <div className="v">{agentAlerts.length}</div>
          <div className="small">阶段：{String(agentDiagnosis?.phase || "-")}</div>
        </div>
        <div className="clarity-kpi-card">
          <div className="k">模板变体</div>
          <div className="v">{variantsEnabled}/{variantRows.length}</div>
          <div className="small">启用/总数</div>
        </div>
        <div className="clarity-kpi-card">
          <div className="k">Story Bible 规模</div>
          <div className="v">{bibleCharacterCount + bibleWorldCount}</div>
          <div className="small">人物 {bibleCharacterCount} · 设定 {bibleWorldCount}</div>
        </div>
        <div className="clarity-kpi-card">
          <div className="k">流程覆盖率</div>
          <div className="v">{Math.round(((scenePackCoverage + auditCoverage) / 2) * 100)}%</div>
          <div className="small">章包 {Math.round(scenePackCoverage * 100)}% · 体检 {Math.round(auditCoverage * 100)}%</div>
        </div>
        <div className="clarity-kpi-card">
          <div className="k">多书相似度</div>
          <div className="v">{comparePairwise.length ? `${Math.round(avgSimilarity * 100)}%` : "-"}</div>
          <div className="small">与基准拆书风格余弦相似度</div>
        </div>
        <div className="clarity-kpi-card">
          <div className="k">风格进化</div>
          <div className="v">{styleOutput?.updated ? "已更新" : styleOutput?.skipped ? "已评估" : "-"}</div>
          <div className="small">{styleLatest?.item?.created_at ? `最近：${String(styleLatest.item.created_at).replace("T", " ").slice(0, 16)}` : "暂无记录"}</div>
        </div>
      </div> : null}

      {!compactMode ? <div className="clarity-chart-grid">
        <div className="clarity-chart-card">
          <h4>角色成长曲线（累计）</h4>
          <Sparkline values={growthGlobal.map((x: any) => toNum(x?.cumulative, 0))} color="#0f766e" />
        </div>
        <div className="clarity-chart-card">
          <h4>剧情张力曲线（整体/冲突）</h4>
          <Sparkline values={tensionOverall} color="#b45309" />
          <div style={{ marginTop: 8 }}>
            <Sparkline values={tensionConflict} color="#0ea5e9" />
          </div>
        </div>
      </div> : null}

      {!compactMode ? <div className="clarity-bottom-grid">
        <div className="clarity-chart-card">
          <h4>自动建议（按风险优先）</h4>
          <div className="clarity-suggest-list">
            {recommendedActions.map((item, idx) => (
              <div key={`${idx}-${item}`} className="clarity-suggest-item">
                <strong>{idx + 1}.</strong>
                <span>{item}</span>
              </div>
            ))}
          </div>
          {autoRunResult ? (
            <div className="small" style={{ marginTop: 10 }}>
              Agent 总控最近执行：自动 {Array.isArray(autoRunResult?.auto_selected_fixes) ? autoRunResult.auto_selected_fixes.length : 0} 项，
              待人工 {Array.isArray(autoRunResult?.manual_fixes) ? autoRunResult.manual_fixes.length : 0} 项。
            </div>
          ) : null}
        </div>
        <div className="clarity-chart-card">
          <h4>多书结构差异（基准对比）</h4>
          {compareItems.length <= 1 ? (
            <div className="clarity-empty">可比拆书不足，至少需要 2 本拆书。</div>
          ) : (
            <div className="clarity-compare-list">
              {comparePairwise.slice(0, 5).map((row: any) => (
                <div key={`${row?.baseline_splitbook_id || ""}-${row?.compare_splitbook_id || ""}`} className="clarity-compare-item">
                  <div className="k">相似度</div>
                  <div className="v">{Math.round(toNum(row?.similarity, 0) * 100)}%</div>
                  <div className="small">
                    对话 {toNum(row?.deltas?.dialog_ratio, 0).toFixed(3)} · 冲突密度 {toNum(row?.deltas?.conflict_density_per_10k_chars, 0).toFixed(2)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div> : null}
    </section>
  );
}
