import { useState } from "react";

type Props = {
  bookId: string;
  volumeId: string;
  onStatus?: (msg: string) => void;
};

type FixItem = {
  fix_id: string;
  title?: string;
  type?: string;
  target?: string;
  risk?: string;
  expected_effect?: string[];
  payload?: any;
};

type ChainItem = {
  chain_id: string;
  created_at?: string;
  status?: string;
  executed_count?: number;
  ok_count?: number;
  has_rollbackable?: boolean;
  pack_name?: string;
};

type ExecutedFixItem = {
  fix_id?: string;
  type?: string;
  status?: string;
  audit_id?: string;
  audit_ids?: string[];
  state_audit_id?: string;
  rollback?: {
    supported?: boolean;
    kind?: string;
    reason?: string;
  };
  reason?: string;
};

export function PreflightFixWizardPanel({ bookId, volumeId, onStatus }: Props) {
  const [packName, setPackName] = useState("publish_pack_desktop");
  const [preflightOut, setPreflightOut] = useState<any>(null);
  const [fixPlanOut, setFixPlanOut] = useState<any>(null);
  const [fixExecOut, setFixExecOut] = useState<any>(null);
  const [fixRecheckOut, setFixRecheckOut] = useState<any>(null);
  const [fixRollbackOut, setFixRollbackOut] = useState<any>(null);
  const [chainsOut, setChainsOut] = useState<any>(null);
  const [selectedFixes, setSelectedFixes] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");

  const fixes = Array.isArray(fixPlanOut?.fixes) ? (fixPlanOut.fixes as FixItem[]) : [];
  const executedFixes = Array.isArray(fixExecOut?.executed) ? (fixExecOut.executed as ExecutedFixItem[]) : [];
  const chains = Array.isArray(chainsOut?.items)
    ? (chainsOut.items as ChainItem[])
    : Array.isArray(chainsOut?.chains)
      ? (chainsOut.chains as ChainItem[])
      : [];

  async function runPreflight() {
    if (!bookId || !volumeId) return;
    setBusy("preflight");
    setErr("");
    try {
      const out = await window.desktopApi.preflightRun({
        book_id: bookId,
        volume_id: volumeId,
        pack_name: packName,
      });
      setPreflightOut(out || {});
      onStatus?.("预检完成");
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function planFixes() {
    if (!bookId || !volumeId) return;
    setBusy("plan");
    setErr("");
    try {
      const out = await window.desktopApi.fixwizardPlan({
        book_id: bookId,
        volume_id: volumeId,
        preflight: preflightOut || {},
      });
      setFixPlanOut(out || {});
      setFixExecOut(null);
      setFixRecheckOut(null);
      const map: Record<string, boolean> = {};
      for (const fx of Array.isArray(out?.fixes) ? out.fixes : []) {
        const id = String(fx?.fix_id || "").trim();
        if (id) map[id] = false;
      }
      setSelectedFixes(map);
      onStatus?.(`修复方案已生成：${Object.keys(map).length}`);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function executeSelected() {
    if (!bookId || !volumeId) return;
    const picked = Object.entries(selectedFixes)
      .filter(([, ok]) => ok)
      .map(([fix_id]) => ({ fix_id }));
    if (!picked.length) {
      setErr("尚未选择修复项");
      return;
    }
    setBusy("execute");
    setErr("");
    try {
      const out = await window.desktopApi.fixwizardExecute({
        book_id: bookId,
        volume_id: volumeId,
        preflight: preflightOut || {},
        fixes,
        selected_fixes: picked,
      });
      setFixExecOut(out || {});
      onStatus?.(`已执行修复项：${picked.length}`);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function recheck() {
    if (!bookId || !volumeId) return;
    setBusy("recheck");
    setErr("");
    try {
      const out = await window.desktopApi.fixwizardRecheck({
        book_id: bookId,
        volume_id: volumeId,
      });
      setFixRecheckOut(out || {});
      onStatus?.("修复复检完成");
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function rollbackLast() {
    if (!bookId) return;
    setBusy("rollback");
    setErr("");
    try {
      const out = await window.desktopApi.fixwizardRollbackLast({
        book_id: bookId,
        volume_id: volumeId || undefined,
      });
      setFixRollbackOut(out || {});
      onStatus?.("修复回滚完成");
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function loadChains() {
    if (!bookId) return;
    setBusy("chains");
    setErr("");
    try {
      const out = await window.desktopApi.fixwizardChains({
        book_id: bookId,
        volume_id: volumeId || undefined,
        limit: 20,
      });
      setChainsOut(out || {});
      const count = Array.isArray(out?.items) ? out.items.length : Array.isArray(out?.chains) ? out.chains.length : 0;
      onStatus?.(`已加载链路：${count}`);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function rollbackChain(chainId: string) {
    if (!chainId) return;
    setBusy("rollback-chain");
    setErr("");
    try {
      const out = await window.desktopApi.fixwizardRollbackChain({
        chain_id: chainId,
      });
      setFixRollbackOut(out || {});
      onStatus?.(`链路回滚完成：${chainId}`);
      await loadChains();
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="wb-panel" style={{ minHeight: "auto", marginBottom: 10 }}>
      <h3>预检与修复向导</h3>
      <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
        <label>
          包名
          <input value={packName} onChange={(e) => setPackName(e.target.value)} />
        </label>
        <button onClick={() => void runPreflight()} disabled={!bookId || !volumeId || !!busy}>
          {busy === "preflight" ? "执行中..." : "运行预检"}
        </button>
        <button onClick={() => void planFixes()} disabled={!bookId || !volumeId || !!busy}>
          {busy === "plan" ? "规划中..." : "生成修复方案"}
        </button>
        <button onClick={() => void executeSelected()} disabled={!!busy || fixes.length === 0}>
          {busy === "execute" ? "执行中..." : "执行已选修复"}
        </button>
        <button onClick={() => void recheck()} disabled={!bookId || !volumeId || !!busy}>
          {busy === "recheck" ? "复检中..." : "复检"}
        </button>
        <button onClick={() => void rollbackLast()} disabled={!bookId || !!busy}>
          {busy === "rollback" ? "回滚中..." : "回滚最近链路"}
        </button>
        <button onClick={() => void loadChains()} disabled={!bookId || !!busy}>
          {busy === "chains" ? "加载中..." : "加载链路"}
        </button>
      </div>
      {err ? <div className="hint" style={{ color: "#7f1d1d", marginTop: 8 }}>{err}</div> : null}
      {fixes.length > 0 ? (
        <div className="scroll" style={{ maxHeight: 220, marginTop: 8 }}>
          {fixes.map((fx, idx) => {
            const id = String(fx?.fix_id || `fix_${idx}`);
            const effects = Array.isArray(fx?.expected_effect) ? fx.expected_effect : [];
            return (
              <div key={id} className="issue-item">
                <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                  <input
                    type="checkbox"
                    checked={Boolean(selectedFixes[id])}
                    onChange={(e) => setSelectedFixes((m) => ({ ...m, [id]: e.target.checked }))}
                  />
                  <strong>{String(fx?.title || id)}</strong>
                  <span className="badge">{String(fx?.type || "-")}</span>
                  <span className="small">风险={String(fx?.risk || "-")}</span>
                  <span className="small">目标={String(fx?.target || "-")}</span>
                </div>
                {effects.length ? <div className="small" style={{ marginTop: 4 }}>预期效果：{effects.join(" | ")}</div> : null}
              </div>
            );
          })}
        </div>
      ) : null}
      <div className="job-grid" style={{ marginTop: 8 }}>
        <div>
          <div className="small">预检结果</div>
          <pre>{JSON.stringify(preflightOut, null, 2)}</pre>
        </div>
        <div>
          <div className="small">修复方案</div>
          <pre>{JSON.stringify(fixPlanOut, null, 2)}</pre>
        </div>
      </div>
      <div className="job-grid" style={{ marginTop: 8 }}>
        <div>
          <div className="small">执行结果</div>
          {executedFixes.length > 0 ? (
            <div className="scroll" style={{ maxHeight: 220, marginBottom: 8 }}>
              {executedFixes.map((ex, idx) => {
                const rollbackSupported = Boolean(ex?.rollback?.supported);
                const hasAgentAudit = Array.isArray(ex?.audit_ids) ? ex.audit_ids.length > 0 : Boolean(ex?.audit_id);
                const source = hasAgentAudit ? "agent" : ex?.state_audit_id ? "proxy" : "none";
                const sourceLabel = source === "agent" ? "智能体(agent)" : source === "proxy" ? "代理(proxy)" : "无(none)";
                const sourceColor = source === "agent" ? "#065f46" : source === "proxy" ? "#92400e" : "#7f1d1d";
                const rbColor = rollbackSupported ? "#065f46" : "#7f1d1d";
                return (
                  <div key={`${String(ex?.fix_id || "fix")}_${idx}`} className="issue-item">
                    <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                      <strong>{String(ex?.fix_id || "-")}</strong>
                      <span className="badge">{String(ex?.status || "-")}</span>
                      <span className="small">类型(type)={String(ex?.type || "-")}</span>
                    </div>
                    <div className="row" style={{ gap: 8, flexWrap: "wrap", marginTop: 4 }}>
                      <span className="small" style={{ color: sourceColor }}>
                        审计来源(audit_source)={sourceLabel}
                      </span>
                      <span className="small" style={{ color: rbColor }}>
                        回滚={rollbackSupported ? "可用" : "不可用"}
                      </span>
                      <span className="small">回滚类型(kind)={String(ex?.rollback?.kind || "-")}</span>
                    </div>
                    {hasAgentAudit ? (
                      <div className="small" style={{ marginTop: 2 }}>
                        审计ID(audit_ids)={JSON.stringify(ex?.audit_ids && ex.audit_ids.length ? ex.audit_ids : [ex?.audit_id])}
                      </div>
                    ) : ex?.state_audit_id ? (
                      <div className="small" style={{ marginTop: 2 }}>
                        代理审计ID(proxy_state_audit_id)={String(ex.state_audit_id)}
                      </div>
                    ) : null}
                    {ex?.rollback?.reason || ex?.reason ? (
                      <div className="small" style={{ marginTop: 2 }}>
                        原因(reason)={String(ex?.rollback?.reason || ex?.reason)}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          ) : null}
          <pre>{JSON.stringify(fixExecOut, null, 2)}</pre>
        </div>
        <div>
          <div className="small">复检结果</div>
          <pre>{JSON.stringify(fixRecheckOut, null, 2)}</pre>
        </div>
      </div>
      <div style={{ marginTop: 8 }}>
        <div className="small">回滚结果</div>
        <pre>{JSON.stringify(fixRollbackOut, null, 2)}</pre>
      </div>
      <div style={{ marginTop: 8 }}>
        <div className="small">链路记录</div>
        {chains.length > 0 ? (
          <div className="scroll" style={{ maxHeight: 220 }}>
            {chains.map((c) => {
              const id = String(c.chain_id || "");
              return (
                <div key={id} className="issue-item">
                  <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                    <strong>{id}</strong>
                    <span className="badge">状态(status)={String(c.status || "-")}</span>
                    <span className="small">执行数(exec)={Number(c.executed_count || 0)}</span>
                    <span className="small">成功(ok)={Number(c.ok_count || 0)}</span>
                    <span className="small">可回滚(rollbackable)={String(Boolean(c.has_rollbackable))}</span>
                    {c.pack_name ? <span className="small">包名(pack)={String(c.pack_name)}</span> : null}
                  </div>
                  <div className="row" style={{ gap: 8, flexWrap: "wrap", marginTop: 4 }}>
                    <span className="small">{String(c.created_at || "")}</span>
                    <button onClick={() => void rollbackChain(id)} disabled={!!busy}>
                      {busy === "rollback-chain" ? "回滚中..." : "回滚该链路"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <pre>{JSON.stringify(chainsOut, null, 2)}</pre>
        )}
      </div>
    </section>
  );
}
