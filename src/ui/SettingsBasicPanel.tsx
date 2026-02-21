import { useMemo } from "react";

function getPath(obj: any, path: string, def: any) {
  const parts = path.split(".");
  let cur = obj;
  for (const p of parts) {
    if (!cur || typeof cur !== "object") return def;
    cur = cur[p];
  }
  return cur === undefined ? def : cur;
}

function clamp(n: number, a: number, b: number) {
  if (!Number.isFinite(n)) return a;
  return Math.max(a, Math.min(b, n));
}

function num(v: any, def: number) {
  const n = Number(v);
  return Number.isFinite(n) ? n : def;
}

function isArr(x: any) {
  return Array.isArray(x);
}

type Props = {
  settingsObj: any;
  onChange: (path: string, value: any) => void;
};

export function SettingsBasicPanel({ settingsObj, onChange }: Props) {
  const draftWords = num(getPath(settingsObj, "draft.default_words", 2200), 2200);
  const draftPov = String(getPath(settingsObj, "draft.pov", "第三人称"));
  const draftTone = String(getPath(settingsObj, "draft.tone", "热血+克制"));

  const sgEnabled = !!getPath(settingsObj, "simguard.enabled", true);
  const sgThreshold = num(getPath(settingsObj, "simguard.sim_threshold", 0.86), 0.86);
  const sgTopK = num(getPath(settingsObj, "simguard.top_k", 5), 5);
  const sgScope = getPath(settingsObj, "simguard.scope_default", ["material_card"]);
  const sgScopeSet = useMemo(() => new Set<string>(isArr(sgScope) ? sgScope : []), [sgScope]);

  function toggleScope(key: string, checked: boolean) {
    const set = new Set<string>(Array.from(sgScopeSet));
    if (checked) set.add(key);
    else set.delete(key);
    onChange("simguard.scope_default", Array.from(set));
  }

  const evEnabled = !!getPath(settingsObj, "eval.enabled", true);
  const targets = getPath(settingsObj, "eval.targets", {});
  const tHook = num(targets?.hook ?? 0.75, 0.75);
  const tConflict = num(targets?.conflict ?? 0.70, 0.70);
  const tPacing = num(targets?.pacing ?? 0.70, 0.70);
  const tClarity = num(targets?.clarity ?? 0.68, 0.68);
  const tCharacter = num(targets?.character ?? 0.70, 0.70);
  const tStakes = num(targets?.stakes ?? 0.72, 0.72);
  const tForeshadow = num(targets?.foreshadow ?? 0.65, 0.65);
  const tPayoff = num(targets?.payoff ?? 0.68, 0.68);

  function setTarget(k: string, v: number) {
    const out = { ...(typeof targets === "object" && targets ? targets : {}) };
    out[k] = clamp(v, 0, 1);
    onChange("eval.targets", out);
  }

  const hEnabled = !!getPath(settingsObj, "humanize.enabled", false);
  const hLevel = String(getPath(settingsObj, "humanize.level_default", "mid"));
  const hRemoveCliches = !!getPath(settingsObj, "humanize.remove_cliches", true);
  const hReduceAi = !!getPath(settingsObj, "humanize.reduce_ai_markers", true);

  const apEnabled = !!getPath(settingsObj, "autopatch.enabled", true);
  const apMaxChanges = num(getPath(settingsObj, "autopatch.max_changes", 8), 8);
  const apMaxNodes = num(getPath(settingsObj, "autopatch.max_nodes_touched", 5), 5);
  const apStrict = String(getPath(settingsObj, "autopatch.strictness", "mid"));
  const abPenalty = num(getPath(settingsObj, "ab.penalty", 0.8), 0.8);

  const aiHooks = num(getPath(settingsObj, "assets.inject.hooks_n", 2), 2);
  const aiBeats = num(getPath(settingsObj, "assets.inject.beats_n", 2), 2);
  const aiStyles = num(getPath(settingsObj, "assets.inject.styles_n", 1), 1);
  const aiTemplates = num(getPath(settingsObj, "assets.inject.templates_n", 1), 1);
  const aiMaxChars = num(getPath(settingsObj, "assets.inject.max_chars", 2000), 2000);
  const aiBlockThreshold = num(getPath(settingsObj, "assets.risk.block_threshold", 0.25), 0.25);
  const cdWindowUses = num(getPath(settingsObj, "assets.cooldown.window_uses", 20), 20);
  const cdDays = num(getPath(settingsObj, "assets.cooldown.time_window_days", 14), 14);
  const cdHardCap = num(getPath(settingsObj, "assets.cooldown.hard_cap", 3), 3);
  const cdPenaltyPerUse = num(getPath(settingsObj, "assets.cooldown.penalty_per_use", 0.12), 0.12);
  const cdPinnedMul = num(getPath(settingsObj, "assets.cooldown.pinned_penalty_multiplier", 0.5), 0.5);

  return (
    <div className="row" style={{ alignItems: "stretch", gap: 10, flexWrap: "wrap" }}>
      <div className="card" style={{ flex: "1 1 360px", minWidth: 320 }}>
        <div className="h2">Draft</div>
        <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
          <div style={{ width: 160 }}>
            <div className="label">default_words</div>
            <input className="input" value={draftWords} onChange={(e) => onChange("draft.default_words", clamp(Number(e.target.value), 200, 20000))} />
          </div>
          <div style={{ width: 200 }}>
            <div className="label">POV</div>
            <select className="input" value={draftPov} onChange={(e) => onChange("draft.pov", e.target.value)}>
              <option value="第一人称">第一人称</option>
              <option value="第三人称">第三人称</option>
              <option value="多视角">多视角</option>
            </select>
          </div>
        </div>
        <div className="label" style={{ marginTop: 10 }}>tone</div>
        <input className="input" value={draftTone} onChange={(e) => onChange("draft.tone", e.target.value)} />
      </div>

      <div className="card" style={{ flex: "1 1 360px", minWidth: 320 }}>
        <div className="h2">SimGuard</div>
        <label className="row" style={{ gap: 8, alignItems: "center" }}>
          <input type="checkbox" checked={sgEnabled} onChange={(e) => onChange("simguard.enabled", e.target.checked)} />
          <span className="small">enabled</span>
        </label>
        <div className="row" style={{ gap: 10, flexWrap: "wrap", marginTop: 10 }}>
          <div style={{ width: 180 }}>
            <div className="label">sim_threshold (0~1)</div>
            <input className="input" value={sgThreshold} onChange={(e) => onChange("simguard.sim_threshold", clamp(Number(e.target.value), 0, 1))} />
          </div>
          <div style={{ width: 120 }}>
            <div className="label">top_k</div>
            <input className="input" value={sgTopK} onChange={(e) => onChange("simguard.top_k", clamp(Number(e.target.value), 1, 20))} />
          </div>
        </div>
        <div className="label" style={{ marginTop: 10 }}>scope_default</div>
        <label className="row" style={{ gap: 8, alignItems: "center" }}>
          <input type="checkbox" checked={sgScopeSet.has("material_card")} onChange={(e) => toggleScope("material_card", e.target.checked)} />
          <span className="small">material_card</span>
        </label>
        <label className="row" style={{ gap: 8, alignItems: "center" }}>
          <input type="checkbox" checked={sgScopeSet.has("splitbook_chunk")} onChange={(e) => toggleScope("splitbook_chunk", e.target.checked)} />
          <span className="small">splitbook_chunk</span>
        </label>
      </div>

      <div className="card" style={{ flex: "2 1 740px", minWidth: 520 }}>
        <div className="h2">Eval</div>
        <label className="row" style={{ gap: 8, alignItems: "center" }}>
          <input type="checkbox" checked={evEnabled} onChange={(e) => onChange("eval.enabled", e.target.checked)} />
          <span className="small">enabled</span>
        </label>
        <div className="row" style={{ gap: 10, flexWrap: "wrap", marginTop: 10 }}>
          {[
            ["hook", tHook],
            ["conflict", tConflict],
            ["pacing", tPacing],
            ["clarity", tClarity],
            ["character", tCharacter],
            ["stakes", tStakes],
            ["foreshadow", tForeshadow],
            ["payoff", tPayoff],
          ].map(([k, v]) => (
            <div key={String(k)} style={{ width: 150 }}>
              <div className="label">{String(k)}</div>
              <input className="input" value={Number(v).toFixed(2)} onChange={(e) => setTarget(String(k), Number(e.target.value))} />
            </div>
          ))}
        </div>
      </div>

      <div className="card" style={{ flex: "1 1 360px", minWidth: 320 }}>
        <div className="h2">Humanize</div>
        <label className="row" style={{ gap: 8, alignItems: "center" }}>
          <input type="checkbox" checked={hEnabled} onChange={(e) => onChange("humanize.enabled", e.target.checked)} />
          <span className="small">enabled (manual trigger)</span>
        </label>
        <div className="row" style={{ gap: 10, flexWrap: "wrap", marginTop: 10 }}>
          <div style={{ width: 180 }}>
            <div className="label">level_default</div>
            <select className="input" value={hLevel} onChange={(e) => onChange("humanize.level_default", e.target.value)}>
              <option value="low">low</option>
              <option value="mid">mid</option>
              <option value="high">high</option>
            </select>
          </div>
        </div>
        <label className="row" style={{ gap: 8, alignItems: "center", marginTop: 10 }}>
          <input type="checkbox" checked={hRemoveCliches} onChange={(e) => onChange("humanize.remove_cliches", e.target.checked)} />
          <span className="small">remove_cliches</span>
        </label>
        <label className="row" style={{ gap: 8, alignItems: "center" }}>
          <input type="checkbox" checked={hReduceAi} onChange={(e) => onChange("humanize.reduce_ai_markers", e.target.checked)} />
          <span className="small">reduce_ai_markers</span>
        </label>
      </div>

      <div className="card" style={{ flex: "1 1 360px", minWidth: 320 }}>
        <div className="h2">AutoPatch</div>
        <label className="row" style={{ gap: 8, alignItems: "center" }}>
          <input type="checkbox" checked={apEnabled} onChange={(e) => onChange("autopatch.enabled", e.target.checked)} />
          <span className="small">enabled</span>
        </label>
        <div className="row" style={{ gap: 10, flexWrap: "wrap", marginTop: 10 }}>
          <div style={{ width: 140 }}>
            <div className="label">max_changes</div>
            <input className="input" value={apMaxChanges} onChange={(e) => onChange("autopatch.max_changes", clamp(Number(e.target.value), 1, 50))} />
          </div>
          <div style={{ width: 170 }}>
            <div className="label">max_nodes_touched</div>
            <input className="input" value={apMaxNodes} onChange={(e) => onChange("autopatch.max_nodes_touched", clamp(Number(e.target.value), 1, 20))} />
          </div>
          <div style={{ width: 160 }}>
            <div className="label">strictness</div>
            <select className="input" value={apStrict} onChange={(e) => onChange("autopatch.strictness", e.target.value)}>
              <option value="low">low</option>
              <option value="mid">mid</option>
              <option value="high">high</option>
            </select>
          </div>
        </div>
      </div>

      <div className="card" style={{ flex: "1 1 360px", minWidth: 320 }}>
        <div className="h2">A/B Score</div>
        <div style={{ width: 160 }}>
          <div className="label">penalty</div>
          <input className="input" value={abPenalty} onChange={(e) => onChange("ab.penalty", clamp(Number(e.target.value), 0, 5))} />
        </div>
        <div className="small" style={{ marginTop: 8 }}>
          score = eval_overall - penalty * simguard_max
        </div>
      </div>

      <div className="card" style={{ flex: "2 1 740px", minWidth: 520 }}>
        <div className="h2">Assets Inject</div>
        <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
          <div style={{ width: 120 }}>
            <div className="label">hooks_n</div>
            <input className="input" value={aiHooks} onChange={(e) => onChange("assets.inject.hooks_n", clamp(Number(e.target.value), 0, 6))} />
          </div>
          <div style={{ width: 120 }}>
            <div className="label">beats_n</div>
            <input className="input" value={aiBeats} onChange={(e) => onChange("assets.inject.beats_n", clamp(Number(e.target.value), 0, 6))} />
          </div>
          <div style={{ width: 120 }}>
            <div className="label">styles_n</div>
            <input className="input" value={aiStyles} onChange={(e) => onChange("assets.inject.styles_n", clamp(Number(e.target.value), 0, 3))} />
          </div>
          <div style={{ width: 140 }}>
            <div className="label">templates_n</div>
            <input className="input" value={aiTemplates} onChange={(e) => onChange("assets.inject.templates_n", clamp(Number(e.target.value), 0, 3))} />
          </div>
          <div style={{ width: 150 }}>
            <div className="label">max_chars</div>
            <input className="input" value={aiMaxChars} onChange={(e) => onChange("assets.inject.max_chars", clamp(Number(e.target.value), 200, 6000))} />
          </div>
          <div style={{ width: 180 }}>
            <div className="label">risk.block_threshold</div>
            <input className="input" value={aiBlockThreshold} onChange={(e) => onChange("assets.risk.block_threshold", clamp(Number(e.target.value), 0, 1))} />
          </div>
        </div>
        <div className="hr" />
        <div className="h2">Assets Cooldown</div>
        <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
          <div style={{ width: 150 }}>
            <div className="label">window_uses</div>
            <input className="input" value={cdWindowUses} onChange={(e) => onChange("assets.cooldown.window_uses", clamp(Number(e.target.value), 1, 200))} />
          </div>
          <div style={{ width: 170 }}>
            <div className="label">time_window_days</div>
            <input className="input" value={cdDays} onChange={(e) => onChange("assets.cooldown.time_window_days", clamp(Number(e.target.value), 1, 90))} />
          </div>
          <div style={{ width: 120 }}>
            <div className="label">hard_cap</div>
            <input className="input" value={cdHardCap} onChange={(e) => onChange("assets.cooldown.hard_cap", clamp(Number(e.target.value), 1, 20))} />
          </div>
          <div style={{ width: 170 }}>
            <div className="label">penalty_per_use</div>
            <input className="input" value={cdPenaltyPerUse} onChange={(e) => onChange("assets.cooldown.penalty_per_use", clamp(Number(e.target.value), 0, 1))} />
          </div>
          <div style={{ width: 220 }}>
            <div className="label">pinned_penalty_multiplier</div>
            <input className="input" value={cdPinnedMul} onChange={(e) => onChange("assets.cooldown.pinned_penalty_multiplier", clamp(Number(e.target.value), 0, 1))} />
          </div>
        </div>
      </div>
    </div>
  );
}
