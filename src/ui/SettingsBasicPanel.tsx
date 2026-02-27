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
  const evalLabels: Record<string, string> = {
    hook: "钩子（hook）",
    conflict: "冲突（conflict）",
    pacing: "节奏（pacing）",
    clarity: "清晰度（clarity）",
    character: "人物（character）",
    stakes: "风险（stakes）",
    foreshadow: "伏笔（foreshadow）",
    payoff: "回收（payoff）",
  };

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
  const uiRetryMax = num(getPath(settingsObj, "ui.capability_chain.retry_max", 3), 3);
  const uiRetryBaseMs = num(getPath(settingsObj, "ui.capability_chain.retry_base_ms", 600), 600);
  const uiIngestConfirmKeyword = String(getPath(settingsObj, "ui.ingest_confirm.keyword", "导入")).trim() || "导入";
  const uiDeleteMismatchBeep = !!getPath(settingsObj, "ui.delete_confirm.mismatch_beep", true);
  const uiDeleteMismatchBeepLevel = String(getPath(settingsObj, "ui.delete_confirm.mismatch_beep_level", "soft"));

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
        <div className="h2">草稿</div>
        <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
          <div style={{ width: 160 }}>
            <div className="label">默认字数（default_words）</div>
            <input className="input" value={draftWords} onChange={(e) => onChange("draft.default_words", clamp(Number(e.target.value), 200, 20000))} />
          </div>
          <div style={{ width: 200 }}>
            <div className="label">视角（POV）</div>
            <select className="input" value={draftPov} onChange={(e) => onChange("draft.pov", e.target.value)}>
              <option value="第一人称">第一人称</option>
              <option value="第三人称">第三人称</option>
              <option value="多视角">多视角</option>
            </select>
          </div>
        </div>
        <div className="label" style={{ marginTop: 10 }}>基调（tone）</div>
        <input className="input" value={draftTone} onChange={(e) => onChange("draft.tone", e.target.value)} />
      </div>

      <div className="card" style={{ flex: "1 1 360px", minWidth: 320 }}>
        <div className="h2">相似度守卫（SimGuard）</div>
        <label className="row" style={{ gap: 8, alignItems: "center" }}>
          <input type="checkbox" checked={sgEnabled} onChange={(e) => onChange("simguard.enabled", e.target.checked)} />
          <span className="small">启用（enabled）</span>
        </label>
        <div className="row" style={{ gap: 10, flexWrap: "wrap", marginTop: 10 }}>
          <div style={{ width: 180 }}>
            <div className="label">相似阈值（sim_threshold，0~1）</div>
            <input className="input" value={sgThreshold} onChange={(e) => onChange("simguard.sim_threshold", clamp(Number(e.target.value), 0, 1))} />
          </div>
          <div style={{ width: 120 }}>
            <div className="label">TopK（top_k）</div>
            <input className="input" value={sgTopK} onChange={(e) => onChange("simguard.top_k", clamp(Number(e.target.value), 1, 20))} />
          </div>
        </div>
        <div className="label" style={{ marginTop: 10 }}>默认范围（scope_default）</div>
        <label className="row" style={{ gap: 8, alignItems: "center" }}>
          <input type="checkbox" checked={sgScopeSet.has("material_card")} onChange={(e) => toggleScope("material_card", e.target.checked)} />
          <span className="small">素材卡（material_card）</span>
        </label>
        <label className="row" style={{ gap: 8, alignItems: "center" }}>
          <input type="checkbox" checked={sgScopeSet.has("splitbook_chunk")} onChange={(e) => toggleScope("splitbook_chunk", e.target.checked)} />
          <span className="small">拆书分片（splitbook_chunk）</span>
        </label>
      </div>

      <div className="card" style={{ flex: "2 1 740px", minWidth: 520 }}>
        <div className="h2">评估（Eval）</div>
        <label className="row" style={{ gap: 8, alignItems: "center" }}>
          <input type="checkbox" checked={evEnabled} onChange={(e) => onChange("eval.enabled", e.target.checked)} />
          <span className="small">启用（enabled）</span>
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
              <div className="label">{evalLabels[String(k)] || String(k)}</div>
              <input className="input" value={Number(v).toFixed(2)} onChange={(e) => setTarget(String(k), Number(e.target.value))} />
            </div>
          ))}
        </div>
      </div>

      <div className="card" style={{ flex: "1 1 360px", minWidth: 320 }}>
        <div className="h2">去 AI 润色（Humanize）</div>
        <label className="row" style={{ gap: 8, alignItems: "center" }}>
          <input type="checkbox" checked={hEnabled} onChange={(e) => onChange("humanize.enabled", e.target.checked)} />
          <span className="small">启用（手动触发）</span>
        </label>
        <div className="row" style={{ gap: 10, flexWrap: "wrap", marginTop: 10 }}>
          <div style={{ width: 180 }}>
            <div className="label">默认等级（level_default）</div>
            <select className="input" value={hLevel} onChange={(e) => onChange("humanize.level_default", e.target.value)}>
              <option value="low">低（low）</option>
              <option value="mid">中（mid）</option>
              <option value="high">高（high）</option>
            </select>
          </div>
        </div>
        <label className="row" style={{ gap: 8, alignItems: "center", marginTop: 10 }}>
          <input type="checkbox" checked={hRemoveCliches} onChange={(e) => onChange("humanize.remove_cliches", e.target.checked)} />
          <span className="small">去套话（remove_cliches）</span>
        </label>
        <label className="row" style={{ gap: 8, alignItems: "center" }}>
          <input type="checkbox" checked={hReduceAi} onChange={(e) => onChange("humanize.reduce_ai_markers", e.target.checked)} />
          <span className="small">减少 AI 痕迹（reduce_ai_markers）</span>
        </label>
      </div>

      <div className="card" style={{ flex: "1 1 360px", minWidth: 320 }}>
        <div className="h2">自动补丁（AutoPatch）</div>
        <label className="row" style={{ gap: 8, alignItems: "center" }}>
          <input type="checkbox" checked={apEnabled} onChange={(e) => onChange("autopatch.enabled", e.target.checked)} />
          <span className="small">启用（enabled）</span>
        </label>
        <div className="row" style={{ gap: 10, flexWrap: "wrap", marginTop: 10 }}>
          <div style={{ width: 140 }}>
            <div className="label">最大改动数（max_changes）</div>
            <input className="input" value={apMaxChanges} onChange={(e) => onChange("autopatch.max_changes", clamp(Number(e.target.value), 1, 50))} />
          </div>
          <div style={{ width: 170 }}>
            <div className="label">最大节点数（max_nodes_touched）</div>
            <input className="input" value={apMaxNodes} onChange={(e) => onChange("autopatch.max_nodes_touched", clamp(Number(e.target.value), 1, 20))} />
          </div>
          <div style={{ width: 160 }}>
            <div className="label">严格度（strictness）</div>
            <select className="input" value={apStrict} onChange={(e) => onChange("autopatch.strictness", e.target.value)}>
              <option value="low">低（low）</option>
              <option value="mid">中（mid）</option>
              <option value="high">高（high）</option>
            </select>
          </div>
        </div>
      </div>

      <div className="card" style={{ flex: "1 1 360px", minWidth: 320 }}>
        <div className="h2">A/B 评分</div>
        <div style={{ width: 160 }}>
          <div className="label">惩罚系数（penalty）</div>
          <input className="input" value={abPenalty} onChange={(e) => onChange("ab.penalty", clamp(Number(e.target.value), 0, 5))} />
        </div>
        <div className="small" style={{ marginTop: 8 }}>
          评分 = eval_overall - penalty * simguard_max
        </div>
      </div>

      <div className="card" style={{ flex: "1 1 360px", minWidth: 320 }}>
        <div className="h2">能力观测自动重试</div>
        <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
          <div style={{ width: 180 }}>
            <div className="label">最大重试次数（ui.capability_chain.retry_max）</div>
            <input className="input" value={uiRetryMax} onChange={(e) => onChange("ui.capability_chain.retry_max", clamp(Number(e.target.value), 1, 8))} />
          </div>
          <div style={{ width: 220 }}>
            <div className="label">基础退避毫秒（ui.capability_chain.retry_base_ms）</div>
            <input className="input" value={uiRetryBaseMs} onChange={(e) => onChange("ui.capability_chain.retry_base_ms", clamp(Number(e.target.value), 200, 5000))} />
          </div>
        </div>
        <div className="small" style={{ marginTop: 8 }}>
          自动串联执行失败时，按指数退避重试：delay = base_ms * 2^(attempt-1)
        </div>
        <div className="hr" />
        <div className="h2">导入确认提示</div>
        <div style={{ width: 220 }}>
          <div className="label">导入校验词（ui.ingest_confirm.keyword）</div>
          <input
            className="input"
            value={uiIngestConfirmKeyword}
            placeholder="导入"
            maxLength={16}
            onChange={(e) => {
              const raw = String(e.target.value || "");
              const normalized = raw.replace(/\s+/g, "").slice(0, 16);
              onChange("ui.ingest_confirm.keyword", normalized || "导入");
            }}
          />
        </div>
        <div className="small" style={{ marginTop: 8 }}>
          本地 TXT 导入前会要求输入该校验词，避免误触导入任务。
        </div>
        <div className="hr" />
        <div className="h2">删除确认提示</div>
        <label className="row" style={{ gap: 8, alignItems: "center" }}>
          <input
            type="checkbox"
            checked={uiDeleteMismatchBeep}
            onChange={(e) => onChange("ui.delete_confirm.mismatch_beep", e.target.checked)}
          />
          <span className="small">名称输入错误时播放提示音（ui.delete_confirm.mismatch_beep）</span>
        </label>
        <div style={{ width: 220, marginTop: 8 }}>
          <div className="label">提示音强度（ui.delete_confirm.mismatch_beep_level）</div>
          <select
            className="input"
            value={uiDeleteMismatchBeepLevel}
            disabled={!uiDeleteMismatchBeep}
            onChange={(e) => onChange("ui.delete_confirm.mismatch_beep_level", e.target.value)}
          >
            <option value="soft">轻提示（soft）</option>
            <option value="strong">强提示（strong）</option>
          </select>
        </div>
      </div>

      <div className="card" style={{ flex: "2 1 740px", minWidth: 520 }}>
        <div className="h2">素材注入</div>
        <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
          <div style={{ width: 120 }}>
            <div className="label">钩子数量（hooks_n）</div>
            <input className="input" value={aiHooks} onChange={(e) => onChange("assets.inject.hooks_n", clamp(Number(e.target.value), 0, 6))} />
          </div>
          <div style={{ width: 120 }}>
            <div className="label">拍点数量（beats_n）</div>
            <input className="input" value={aiBeats} onChange={(e) => onChange("assets.inject.beats_n", clamp(Number(e.target.value), 0, 6))} />
          </div>
          <div style={{ width: 120 }}>
            <div className="label">风格数量（styles_n）</div>
            <input className="input" value={aiStyles} onChange={(e) => onChange("assets.inject.styles_n", clamp(Number(e.target.value), 0, 3))} />
          </div>
          <div style={{ width: 140 }}>
            <div className="label">模板数量（templates_n）</div>
            <input className="input" value={aiTemplates} onChange={(e) => onChange("assets.inject.templates_n", clamp(Number(e.target.value), 0, 3))} />
          </div>
          <div style={{ width: 150 }}>
            <div className="label">最大字符（max_chars）</div>
            <input className="input" value={aiMaxChars} onChange={(e) => onChange("assets.inject.max_chars", clamp(Number(e.target.value), 200, 6000))} />
          </div>
          <div style={{ width: 180 }}>
            <div className="label">风险阻断阈值（risk.block_threshold）</div>
            <input className="input" value={aiBlockThreshold} onChange={(e) => onChange("assets.risk.block_threshold", clamp(Number(e.target.value), 0, 1))} />
          </div>
        </div>
        <div className="hr" />
        <div className="h2">素材冷却</div>
        <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
          <div style={{ width: 150 }}>
            <div className="label">窗口使用次数（window_uses）</div>
            <input className="input" value={cdWindowUses} onChange={(e) => onChange("assets.cooldown.window_uses", clamp(Number(e.target.value), 1, 200))} />
          </div>
          <div style={{ width: 170 }}>
            <div className="label">时间窗口天数（time_window_days）</div>
            <input className="input" value={cdDays} onChange={(e) => onChange("assets.cooldown.time_window_days", clamp(Number(e.target.value), 1, 90))} />
          </div>
          <div style={{ width: 120 }}>
            <div className="label">硬上限（hard_cap）</div>
            <input className="input" value={cdHardCap} onChange={(e) => onChange("assets.cooldown.hard_cap", clamp(Number(e.target.value), 1, 20))} />
          </div>
          <div style={{ width: 170 }}>
            <div className="label">单次惩罚（penalty_per_use）</div>
            <input className="input" value={cdPenaltyPerUse} onChange={(e) => onChange("assets.cooldown.penalty_per_use", clamp(Number(e.target.value), 0, 1))} />
          </div>
          <div style={{ width: 220 }}>
            <div className="label">置顶惩罚倍率（pinned_penalty_multiplier）</div>
            <input className="input" value={cdPinnedMul} onChange={(e) => onChange("assets.cooldown.pinned_penalty_multiplier", clamp(Number(e.target.value), 0, 1))} />
          </div>
        </div>
      </div>
    </div>
  );
}
