import { useEffect, useMemo, useState } from "react";

type Props = {
  bookId: string;
  volumeId: string;
  onStatus?: (msg: string) => void;
};

export function SkillPackHubPanel({ bookId, volumeId, onStatus }: Props) {
  const [busy, setBusy] = useState("");
  const [catalog, setCatalog] = useState<any[]>([]);
  const [presets, setPresets] = useState<Record<string, any>>({});
  const [preset, setPreset] = useState("balanced");
  const [selectedPackIds, setSelectedPackIds] = useState<string[]>([]);
  const [automation, setAutomation] = useState<any>({
    auto_preflight: true,
    auto_low_risk_fix: true,
    auto_plan_autobuild: false,
    auto_rewrite_suggest: false,
    auto_low_risk_only: true,
    max_auto_fixes: 3,
  });
  const [bindingOut, setBindingOut] = useState<any>(null);
  const [runOut, setRunOut] = useState<any>(null);
  const [err, setErr] = useState("");

  const canRun = !!bookId.trim() && !!volumeId.trim();

  useEffect(() => {
    void loadCatalog();
    void loadPresets();
  }, []);

  useEffect(() => {
    if (!bookId.trim()) return;
    void loadBinding();
  }, [bookId]);

  async function loadCatalog() {
    try {
      setBusy("catalog");
      setErr("");
      const out = await window.desktopApi.skillpacksCatalog();
      setCatalog(Array.isArray(out?.items) ? out.items : []);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function loadPresets() {
    try {
      const out = await window.desktopApi.skillpacksPresets();
      setPresets((out?.items && typeof out.items === "object") ? out.items : {});
    } catch {
      setPresets({});
    }
  }

  async function loadBinding() {
    if (!bookId.trim()) return;
    try {
      setBusy("binding:get");
      setErr("");
      const out = await window.desktopApi.skillpacksBindGet({ book_id: bookId });
      setBindingOut(out || null);
      setSelectedPackIds(Array.isArray(out?.selected_pack_ids) ? out.selected_pack_ids : []);
      if (out?.automation && typeof out.automation === "object") setAutomation(out.automation);
      if (typeof out?.automation_preset === "string" && out.automation_preset.trim()) setPreset(out.automation_preset.trim());
      onStatus?.("技能包绑定已加载");
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function saveBinding() {
    if (!bookId.trim()) return;
    try {
      setBusy("binding:set");
      setErr("");
      const out = await window.desktopApi.skillpacksBindSet({
        book_id: bookId,
        selected_pack_ids: selectedPackIds,
        automation_preset: preset,
        automation,
      });
      setBindingOut(out || null);
      onStatus?.(`技能包绑定已保存（${selectedPackIds.length}）`);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runAuto() {
    if (!canRun) return;
    try {
      setBusy("auto:run");
      setErr("");
      const out = await window.desktopApi.skillpacksAutoRun({
        book_id: bookId,
        volume_id: volumeId,
        selected_pack_ids: selectedPackIds,
        automation_preset: preset,
        automation,
      });
      setRunOut(out || null);
      const executed = Array.isArray(out?.execution?.executed) ? out.execution.executed.length : 0;
      onStatus?.(`技能自动运行完成（已执行 ${executed} 项）`);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  const manualFixCount = useMemo(() => {
    return Array.isArray(runOut?.manual_fixes) ? runOut.manual_fixes.length : 0;
  }, [runOut]);

  function applyPreset(key: string) {
    const hit = presets?.[key];
    if (!hit || typeof hit !== "object") return;
    const auto = hit.automation;
    if (auto && typeof auto === "object") {
      setPreset(key);
      setAutomation(auto);
    }
  }

  return (
    <section className="wb-panel">
      <h3>技能包中心</h3>
      <div className="row">
        <button onClick={() => void loadCatalog()} disabled={!!busy}>
          刷新目录
        </button>
        <button onClick={() => void loadBinding()} disabled={!bookId || !!busy}>
          加载绑定
        </button>
        <button onClick={() => void saveBinding()} disabled={!bookId || !!busy}>
          保存绑定
        </button>
        <button onClick={() => void runAuto()} disabled={!canRun || !!busy}>
          {busy === "auto:run" ? "执行中..." : "一键自动运行"}
        </button>
      </div>
      <div className="small" style={{ marginTop: 6 }}>
        自动模式会执行低风险修复；高风险与关键改写仍保留人工确认。
      </div>
      <div className="row" style={{ marginTop: 6 }}>
        <span className="small">预设</span>
        <button onClick={() => applyPreset("conservative")} disabled={!!busy}>保守</button>
        <button onClick={() => applyPreset("balanced")} disabled={!!busy}>平衡</button>
        <button onClick={() => applyPreset("aggressive")} disabled={!!busy}>激进</button>
        <code>{preset}</code>
      </div>

      <div className="agent-grid" style={{ marginTop: 8 }}>
        <div className="agent-col">
          <div className="small">技能包列表</div>
          <div className="scroll" style={{ maxHeight: 220 }}>
            {catalog.map((it) => {
              const pid = String(it?.pack_id || "");
              const checked = selectedPackIds.includes(pid);
              return (
                <label key={pid} className="row" style={{ marginBottom: 4 }}>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) => {
                      if (e.target.checked) setSelectedPackIds((prev) => Array.from(new Set([...prev, pid])));
                      else setSelectedPackIds((prev) => prev.filter((x) => x !== pid));
                    }}
                  />
                  <span>
                    {String(it?.name || pid)}
                    <span className="small"> · {String(it?.upstream || "")}</span>
                  </span>
                </label>
              );
            })}
            {catalog.length === 0 ? <div className="hint">尚未加载目录</div> : null}
          </div>
        </div>

        <div className="agent-col">
          <div className="small">自动化策略</div>
          <label className="row">
            <input
              type="checkbox"
              checked={!!automation.auto_preflight}
              onChange={(e) => setAutomation((p: any) => ({ ...p, auto_preflight: e.target.checked }))}
            />
            <span>自动预检</span>
          </label>
          <label className="row">
            <input
              type="checkbox"
              checked={!!automation.auto_low_risk_fix}
              onChange={(e) => setAutomation((p: any) => ({ ...p, auto_low_risk_fix: e.target.checked }))}
            />
            <span>自动低风险修复</span>
          </label>
          <label className="row">
            <input
              type="checkbox"
              checked={!!automation.auto_plan_autobuild}
              onChange={(e) => setAutomation((p: any) => ({ ...p, auto_plan_autobuild: e.target.checked }))}
            />
            <span>自动规划自动构建</span>
          </label>
          <label className="row">
            <input
              type="checkbox"
              checked={!!automation.auto_rewrite_suggest}
              onChange={(e) => setAutomation((p: any) => ({ ...p, auto_rewrite_suggest: e.target.checked }))}
            />
            <span>自动改写建议</span>
          </label>
          <label className="row">
            <input
              type="checkbox"
              checked={!!automation.auto_low_risk_only}
              onChange={(e) => setAutomation((p: any) => ({ ...p, auto_low_risk_only: e.target.checked }))}
            />
            <span>仅低风险</span>
          </label>
          <label className="row">
            <span className="small">自动修复上限</span>
            <input
              type="number"
              min={1}
              max={10}
              value={Number(automation.max_auto_fixes || 3)}
              onChange={(e) => setAutomation((p: any) => ({ ...p, max_auto_fixes: Number(e.target.value || 3) }))}
              style={{ width: 80 }}
            />
          </label>
        </div>

        <div className="agent-col">
          <div className="small">运行结果</div>
          {runOut ? (
            <div className="small" style={{ marginBottom: 6 }}>
              待人工处理修复：{manualFixCount}
            </div>
          ) : null}
          <pre>{JSON.stringify(runOut || bindingOut || {}, null, 2)}</pre>
        </div>
      </div>

      {err ? <div className="danger" style={{ marginTop: 8 }}>{err}</div> : null}
    </section>
  );
}
