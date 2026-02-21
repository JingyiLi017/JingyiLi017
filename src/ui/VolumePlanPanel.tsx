import { useEffect, useMemo, useState } from "react";

type Props = {
  baseUrl: string;
  bookId: string;
  chapterId: string;
  onStatus: (msg: string) => void;
};

export function VolumePlanPanel({ baseUrl, bookId, chapterId, onStatus }: Props) {
  const [volumes, setVolumes] = useState<any[]>([]);
  const [selectedVolumeId, setSelectedVolumeId] = useState("");
  const [activePlan, setActivePlan] = useState<any | null>(null);
  const [previewPlan, setPreviewPlan] = useState<any | null>(null);
  const [versions, setVersions] = useState<any[]>([]);
  const [dirtyIds, setDirtyIds] = useState<Record<string, boolean>>({});
  const [note, setNote] = useState("manual update");
  const [volumeGoal, setVolumeGoal] = useState("");
  const [volumeTheme, setVolumeTheme] = useState("");
  const [targetPacing, setTargetPacing] = useState("mid");
  const [loading, setLoading] = useState(false);

  const timelineRows = useMemo(() => {
    const items = (activePlan?.items || []) as any[];
    const lanes: { end: number; rows: any[] }[] = [];
    const sorted = [...items].sort(
      (a, b) =>
        Number(a.target_p_vol_min ?? 0) - Number(b.target_p_vol_min ?? 0) ||
        Number(b.priority ?? 0) - Number(a.priority ?? 0)
    );
    for (const it of sorted) {
      const start = Math.max(0, Math.min(1, Number(it.target_p_vol_min ?? 0)));
      const end = Math.max(start, Math.min(1, Number(it.target_p_vol_max ?? 1)));
      let placed = false;
      for (const lane of lanes) {
        if (start >= lane.end) {
          lane.rows.push({ ...it, __start: start, __end: end });
          lane.end = end;
          placed = true;
          break;
        }
      }
      if (!placed) lanes.push({ end, rows: [{ ...it, __start: start, __end: end }] });
    }
    return lanes.map((x) => x.rows);
  }, [activePlan]);

  const timelineConflicts = useMemo(() => {
    const items = ((activePlan?.items || []) as any[])
      .map((x: any) => ({
        ...x,
        __start: Math.max(0, Math.min(1, Number(x.target_p_vol_min ?? 0))),
        __end: Math.max(0, Math.min(1, Number(x.target_p_vol_max ?? 1))),
      }))
      .filter((x: any) => !!x.must_happen);
    const out: any[] = [];
    for (let i = 0; i < items.length; i++) {
      for (let j = i + 1; j < items.length; j++) {
        const a = items[i];
        const b = items[j];
        const overlap = Math.min(a.__end, b.__end) - Math.max(a.__start, b.__start);
        if (overlap <= 0) continue;
        const highPriority = Number(a.priority || 0) >= 4 && Number(b.priority || 0) >= 4;
        if (!highPriority) continue;
        out.push({
          a_id: a.item_id,
          b_id: b.item_id,
          a_kind: a.kind,
          b_kind: b.kind,
          a_p: [a.__start, a.__end],
          b_p: [b.__start, b.__end],
          overlap: Number(overlap.toFixed(3)),
        });
      }
    }
    out.sort((x, y) => y.overlap - x.overlap);
    return out.slice(0, 30);
  }, [activePlan]);

  const conflictSuggestions = useMemo(() => {
    const items = ((activePlan?.items || []) as any[]).map((x: any) => ({
      id: String(x.item_id || ""),
      priority: Number(x.priority || 0),
      min: Math.max(0, Math.min(1, Number(x.target_p_vol_min ?? 0))),
      max: Math.max(0, Math.min(1, Number(x.target_p_vol_max ?? 1))),
      kind: String(x.kind || ""),
      meta: typeof x.meta === "object" && x.meta ? x.meta : {},
    }));
    const idMap = new Map<string, any>();
    for (const it of items) idMap.set(it.id, { ...it });
    const deltas = new Map<string, number>();
    const notes = new Map<string, string[]>();
    const gap = 0.01;
    const sorted = [...timelineConflicts].sort((a: any, b: any) => Number(b.overlap || 0) - Number(a.overlap || 0));

    function addDelta(id: string, d: number, why: string) {
      deltas.set(id, (deltas.get(id) || 0) + d);
      const arr = notes.get(id) || [];
      arr.push(why);
      notes.set(id, arr);
    }

    function isLocked(it: any) {
      if (it?.meta?.lock_auto_shift === true) return true;
      return String(it.kind || "") === "growth" && Number(it.priority || 0) >= 5;
    }

    for (const cf of sorted) {
      const a = idMap.get(String(cf.a_id || ""));
      const b = idMap.get(String(cf.b_id || ""));
      if (!a || !b) continue;
      const overlapNow = Math.min(a.max, b.max) - Math.max(a.min, b.min);
      if (overlapNow <= 0) continue;
      const aLocked = isLocked(a);
      const bLocked = isLocked(b);
      if (aLocked && bLocked) continue;
      let moveB = false;
      if (aLocked && !bLocked) moveB = true;
      else if (!aLocked && bLocked) moveB = false;
      else {
        moveB = a.priority > b.priority ? true : a.priority < b.priority ? false : (b.max - b.min) <= (a.max - a.min);
      }
      const src = moveB ? b : a;
      const fixed = moveB ? a : b;
      const need = overlapNow + gap;
      const srcCenter = (src.min + src.max) / 2;
      const fixedCenter = (fixed.min + fixed.max) / 2;
      const preferLeft = srcCenter <= fixedCenter;
      const leftCap = src.min;
      const rightCap = 1 - src.max;
      let shift = 0;
      if (preferLeft && leftCap >= need) shift = -need;
      else if (!preferLeft && rightCap >= need) shift = need;
      else if (leftCap >= need) shift = -need;
      else if (rightCap >= need) shift = need;
      else if (leftCap >= rightCap && leftCap > 0) shift = -leftCap;
      else if (rightCap > 0) shift = rightCap;
      if (shift === 0) continue;
      src.min = Math.max(0, Math.min(1, src.min + shift));
      src.max = Math.max(src.min + 0.01, Math.min(1, src.max + shift));
      const w = src.max - src.min;
      if (src.max > 1) {
        src.max = 1;
        src.min = Math.max(0, src.max - w);
      }
      const reason = `${moveB ? "move B" : "move A"} for ${a.kind}×${b.kind}${aLocked || bLocked ? " (protect locked growth)" : ""}`;
      addDelta(src.id, shift, reason);
      idMap.set(src.id, src);
    }
    const out = Array.from(deltas.entries())
      .map(([item_id, delta]) => {
        const it = idMap.get(item_id);
        if (!it) return null;
        return {
          item_id,
          delta: Number(delta.toFixed(3)),
          suggested_min: Number(it.min.toFixed(2)),
          suggested_max: Number(it.max.toFixed(2)),
          reasons: (notes.get(item_id) || []).slice(0, 3),
        };
      })
      .filter(Boolean) as any[];
    out.sort((a, b) => Math.abs(Number(b.delta || 0)) - Math.abs(Number(a.delta || 0)));
    return out;
  }, [activePlan, timelineConflicts]);

  const selectedVolume = useMemo(
    () => volumes.find((v: any) => String(v.volume_id || "") === selectedVolumeId) || null,
    [volumes, selectedVolumeId]
  );

  async function loadVolumes() {
    if (!bookId) return;
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/volumes`);
    if (!res.ok) throw new Error(`VOLUMES_LOAD_FAILED:${res.status}`);
    const out = await res.json();
    const items = Array.isArray(out.items) ? out.items : [];
    setVolumes(items);
    if (!selectedVolumeId && items[0]?.volume_id) setSelectedVolumeId(String(items[0].volume_id));
  }

  async function autoCreateVolumes() {
    if (!bookId) return;
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/volumes/auto_create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chapters_per_volume: 50 }),
    });
    if (!res.ok) throw new Error(`VOLUME_AUTO_CREATE_FAILED:${res.status}`);
    const out = await res.json();
    onStatus(`Volumes auto-created: ${String(out.created || 0)}`);
    await loadVolumes();
  }

  async function loadPlan() {
    if (!bookId || !selectedVolumeId) return;
    setLoading(true);
    try {
      const [activeRes, verRes] = await Promise.all([
        fetch(`${baseUrl}/v1/books/${bookId}/volumes/${selectedVolumeId}/plan/active`),
        fetch(`${baseUrl}/v1/books/${bookId}/volumes/${selectedVolumeId}/plan/versions?limit=20`),
      ]);
      if (!activeRes.ok) throw new Error(`VOLUME_PLAN_ACTIVE_FAILED:${activeRes.status}`);
      if (!verRes.ok) throw new Error(`VOLUME_PLAN_VERSIONS_FAILED:${verRes.status}`);
      const activeOut = await activeRes.json();
      const verOut = await verRes.json();
      setActivePlan(activeOut.plan || null);
      setVersions(Array.isArray(verOut.items) ? verOut.items : []);
    } finally {
      setLoading(false);
    }
  }

  async function previewAutoPlan() {
    if (!bookId || !selectedVolumeId) return;
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/volumes/${selectedVolumeId}/plan/preview_auto`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        volume_goal: volumeGoal,
        volume_theme: volumeTheme,
        target_pacing: targetPacing,
      }),
    });
    if (!res.ok) throw new Error(`VOLUME_PLAN_PREVIEW_FAILED:${res.status}`);
    const out = await res.json();
    setPreviewPlan(out.plan || null);
    onStatus(`Preview ready: ${(out.plan?.items || []).length} items`);
  }

  async function applyAutoPlan() {
    if (!bookId || !selectedVolumeId) return;
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/volumes/${selectedVolumeId}/plan/apply_auto`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        volume_goal: volumeGoal,
        volume_theme: volumeTheme,
        target_pacing: targetPacing,
        note,
        reason: "ui_apply_auto",
        plan: previewPlan || undefined,
      }),
    });
    if (!res.ok) throw new Error(`VOLUME_PLAN_APPLY_FAILED:${res.status}`);
    const out = await res.json();
    setPreviewPlan(null);
    onStatus(`Volume plan applied: v${String(out.version || "?")}`);
    await loadPlan();
  }

  async function autoGeneratePlan() {
    if (!bookId || !selectedVolumeId) return;
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/volumes/${selectedVolumeId}/plan/auto_generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        note,
        reason: "ui_generate",
        volume_goal: volumeGoal,
        volume_theme: volumeTheme,
        target_pacing: targetPacing,
      }),
    });
    if (!res.ok) throw new Error(`VOLUME_PLAN_GENERATE_FAILED:${res.status}`);
    const out = await res.json();
    onStatus(`Volume plan generated: v${String(out.version || "?")}`);
    await loadPlan();
  }

  async function promoteVersion(v: number) {
    if (!bookId || !selectedVolumeId || !v) return;
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/volumes/${selectedVolumeId}/plan/${v}/promote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note }),
    });
    if (!res.ok) throw new Error(`VOLUME_PLAN_PROMOTE_FAILED:${res.status}`);
    const out = await res.json();
    onStatus(`Plan promoted: v${String(out.active_version || v)}`);
    await loadPlan();
  }

  async function rollbackLast() {
    if (!bookId || !selectedVolumeId) return;
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/volumes/${selectedVolumeId}/plan/rollback_last`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!res.ok) throw new Error(`VOLUME_PLAN_ROLLBACK_FAILED:${res.status}`);
    const out = await res.json();
    onStatus(`Plan rollback -> active v${String(out.active_version || "-")}`);
    await loadPlan();
  }

  async function learnFromBatches() {
    if (!bookId || !selectedVolumeId) return;
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/volumes/${selectedVolumeId}/plan/learn_from_batches`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lr: 0.02, recent_limit: 30 }),
    });
    if (!res.ok) throw new Error(`VOLUME_PLAN_LEARN_FAILED:${res.status}`);
    const out = await res.json();
    const learning = out.learning || {};
    onStatus(`Learned shaping: A_growth=${String(learning.A_growth ?? "-")} A_payoff=${String(learning.A_payoff ?? "-")}`);
    await loadPlan();
  }

  async function saveItemPatch(item: any) {
    if (!bookId || !selectedVolumeId || !item?.item_id) return;
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/volumes/${selectedVolumeId}/plan/items/${item.item_id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        summary: item.summary || "",
        target_window: item.target_window || "vol_build",
        target_p_vol_min: Number(item.target_p_vol_min || 0.18),
        target_p_vol_max: Number(item.target_p_vol_max || 0.65),
        priority: Number(item.priority || 3),
        must_happen: !!item.must_happen,
        meta: {
          ...(typeof item.meta === "object" && item.meta ? item.meta : {}),
          lock_auto_shift: !!(item?.meta?.lock_auto_shift),
        },
      }),
    });
    if (!res.ok) throw new Error(`VOLUME_PLAN_ITEM_SAVE_FAILED:${res.status}`);
    const out = await res.json();
    setActivePlan(out.plan || null);
    setDirtyIds((prev) => {
      const k = String(item.item_id || "");
      if (!k) return prev;
      const next = { ...prev };
      delete next[k];
      return next;
    });
    onStatus(`Plan item saved: ${String(item.item_id).slice(0, 8)}`);
  }

  async function saveAllDirty() {
    if (!bookId || !selectedVolumeId || !activePlan?.items) return;
    const rows = (activePlan.items || []).filter((x: any) => dirtyIds[String(x.item_id || "")]);
    if (!rows.length) {
      onStatus("No pending item edits");
      return;
    }
    const payload = {
      items: rows.map((it: any) => ({
        item_id: it.item_id,
        summary: String(it.summary || ""),
        target_window: String(it.target_window || "vol_build"),
        target_p_vol_min: Number(it.target_p_vol_min || 0.18),
        target_p_vol_max: Number(it.target_p_vol_max || 0.65),
        priority: Number(it.priority || 3),
        must_happen: !!it.must_happen,
        meta: {
          ...(typeof it.meta === "object" && it.meta ? it.meta : {}),
          lock_auto_shift: !!(it?.meta?.lock_auto_shift),
        },
      })),
    };
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/volumes/${selectedVolumeId}/plan/items_batch_update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`VOLUME_PLAN_BATCH_SAVE_FAILED:${res.status}`);
    const out = await res.json();
    setActivePlan(out.plan || null);
    setDirtyIds({});
    onStatus(`Plan items saved: ${String(out.updated || 0)}`);
  }

  function patchItem(itemId: string, patch: Record<string, any>) {
    setActivePlan((prev: any) => {
      if (!prev || !Array.isArray(prev.items)) return prev;
      return {
        ...prev,
        items: prev.items.map((x: any) => (x.item_id === itemId ? { ...x, ...patch } : x)),
      };
    });
    if (itemId) setDirtyIds((prev) => ({ ...prev, [itemId]: true }));
  }

  function patchRange(itemId: string, key: "target_p_vol_min" | "target_p_vol_max", value: number) {
    setActivePlan((prev: any) => {
      if (!prev || !Array.isArray(prev.items)) return prev;
      return {
        ...prev,
        items: prev.items.map((x: any) => {
          if (x.item_id !== itemId) return x;
          const curMin = Number(x.target_p_vol_min ?? 0.0);
          const curMax = Number(x.target_p_vol_max ?? 1.0);
          let nextMin = curMin;
          let nextMax = curMax;
          if (key === "target_p_vol_min") nextMin = Math.min(Number(value), curMax);
          if (key === "target_p_vol_max") nextMax = Math.max(Number(value), curMin);
          return { ...x, target_p_vol_min: Number(nextMin.toFixed(2)), target_p_vol_max: Number(nextMax.toFixed(2)) };
        }),
      };
    });
    if (itemId) setDirtyIds((prev) => ({ ...prev, [itemId]: true }));
  }

  function shiftItemRange(itemId: string, delta: number) {
    setActivePlan((prev: any) => {
      if (!prev || !Array.isArray(prev.items)) return prev;
      return {
        ...prev,
        items: prev.items.map((x: any) => {
          if (x.item_id !== itemId) return x;
          const curMin = Number(x.target_p_vol_min ?? 0);
          const curMax = Number(x.target_p_vol_max ?? 1);
          const width = Math.max(0.01, curMax - curMin);
          let nextMin = Math.max(0, Math.min(1, curMin + delta));
          let nextMax = nextMin + width;
          if (nextMax > 1) {
            nextMax = 1;
            nextMin = Math.max(0, nextMax - width);
          }
          return { ...x, target_p_vol_min: Number(nextMin.toFixed(2)), target_p_vol_max: Number(nextMax.toFixed(2)) };
        }),
      };
    });
    if (itemId) setDirtyIds((prev) => ({ ...prev, [itemId]: true }));
  }

  function applySuggestions() {
    if (!activePlan || !Array.isArray(activePlan.items) || !conflictSuggestions.length) {
      onStatus("No suggestions to apply");
      return;
    }
    const sugMap = new Map<string, any>(conflictSuggestions.map((x: any) => [String(x.item_id), x]));
    setActivePlan((prev: any) => {
      if (!prev || !Array.isArray(prev.items)) return prev;
      return {
        ...prev,
        items: prev.items.map((x: any) => {
          const s = sugMap.get(String(x.item_id || ""));
          if (!s) return x;
          return { ...x, target_p_vol_min: s.suggested_min, target_p_vol_max: s.suggested_max };
        }),
      };
    });
    setDirtyIds((prev) => {
      const next = { ...prev };
      for (const s of conflictSuggestions) next[String(s.item_id || "")] = true;
      return next;
    });
    onStatus(`Applied ${conflictSuggestions.length} conflict suggestions (dirty, not saved)`);
  }

  function lockAllGrowthP5() {
    if (!activePlan || !Array.isArray(activePlan.items)) return;
    let touched = 0;
    setActivePlan((prev: any) => {
      if (!prev || !Array.isArray(prev.items)) return prev;
      return {
        ...prev,
        items: prev.items.map((x: any) => {
          const isGrowthP5 = String(x.kind || "") === "growth" && Number(x.priority || 0) >= 5;
          if (!isGrowthP5) return x;
          touched += 1;
          return {
            ...x,
            meta: {
              ...(typeof x.meta === "object" && x.meta ? x.meta : {}),
              lock_auto_shift: true,
            },
          };
        }),
      };
    });
    if (touched > 0) {
      setDirtyIds((prev) => {
        const next = { ...prev };
        for (const it of (activePlan.items || [])) {
          const isGrowthP5 = String(it.kind || "") === "growth" && Number(it.priority || 0) >= 5;
          if (isGrowthP5) next[String(it.item_id || "")] = true;
        }
        return next;
      });
    }
    onStatus(`Locked growth p5+: ${touched} item(s) (dirty, not saved)`);
  }

  function unlockAll() {
    if (!activePlan || !Array.isArray(activePlan.items)) return;
    let touched = 0;
    setActivePlan((prev: any) => {
      if (!prev || !Array.isArray(prev.items)) return prev;
      return {
        ...prev,
        items: prev.items.map((x: any) => {
          if (!(x?.meta?.lock_auto_shift === true)) return x;
          touched += 1;
          return {
            ...x,
            meta: {
              ...(typeof x.meta === "object" && x.meta ? x.meta : {}),
              lock_auto_shift: false,
            },
          };
        }),
      };
    });
    if (touched > 0) {
      setDirtyIds((prev) => {
        const next = { ...prev };
        for (const it of (activePlan.items || [])) {
          if (it?.meta?.lock_auto_shift === true) next[String(it.item_id || "")] = true;
        }
        return next;
      });
    }
    onStatus(`Unlocked items: ${touched} (dirty, not saved)`);
  }

  useEffect(() => {
    if (!bookId) {
      setVolumes([]);
      setSelectedVolumeId("");
      setActivePlan(null);
      setPreviewPlan(null);
      setVersions([]);
      return;
    }
    void loadVolumes().catch((err) => onStatus(String(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookId, baseUrl]);

  useEffect(() => {
    if (!bookId || !selectedVolumeId) {
      setActivePlan(null);
      setPreviewPlan(null);
      setVersions([]);
      return;
    }
    void loadPlan().catch((err) => onStatus(String(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookId, selectedVolumeId, baseUrl]);

  return (
    <div style={{ marginTop: 10 }}>
      <div className="h2">Volume Plan Dashboard</div>
      <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <button onClick={() => void autoCreateVolumes()} disabled={!bookId}>Auto Create Volumes</button>
        <button onClick={() => void loadVolumes()} disabled={!bookId}>Reload Volumes</button>
        <label>
          Volume
          <select value={selectedVolumeId} onChange={(e) => setSelectedVolumeId(e.target.value)} disabled={!bookId || volumes.length === 0}>
            <option value="">(none)</option>
            {volumes.map((v: any) => (
              <option key={String(v.volume_id)} value={String(v.volume_id)}>
                V{String(v.volume_no)} · ch{String(v.start_chapter_no)}-{String(v.end_chapter_no)}
              </option>
            ))}
          </select>
        </label>
        <div className="small mono">
          chapter_id={chapterId ? String(chapterId).slice(0, 8) : "-"} · volume={selectedVolume ? String(selectedVolume.volume_no) : "-"} {loading ? "· loading..." : ""}
        </div>
      </div>

      <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "flex-end", marginTop: 8 }}>
        <label style={{ minWidth: 240 }}>
          Volume Goal
          <input value={volumeGoal} onChange={(e) => setVolumeGoal(e.target.value)} placeholder="本卷主线目标" />
        </label>
        <label style={{ minWidth: 220 }}>
          Theme
          <input value={volumeTheme} onChange={(e) => setVolumeTheme(e.target.value)} placeholder="主题（可选）" />
        </label>
        <label>
          Pacing
          <select value={targetPacing} onChange={(e) => setTargetPacing(e.target.value)}>
            <option value="slow">slow</option>
            <option value="mid">mid</option>
            <option value="fast">fast</option>
          </select>
        </label>
      </div>

      <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "flex-end", marginTop: 8 }}>
        <label style={{ minWidth: 260 }}>
          Note
          <input value={note} onChange={(e) => setNote(e.target.value)} />
        </label>
        <button onClick={() => void previewAutoPlan()} disabled={!selectedVolumeId}>Preview Auto Plan</button>
        <button onClick={() => void applyAutoPlan()} disabled={!selectedVolumeId}>Apply Auto Plan</button>
        <button onClick={() => void autoGeneratePlan()} disabled={!selectedVolumeId}>Auto Generate (Legacy)</button>
        <button onClick={() => void learnFromBatches()} disabled={!selectedVolumeId}>Learn From Batches</button>
        <button onClick={() => void rollbackLast()} disabled={!selectedVolumeId}>Rollback Last</button>
      </div>

      {previewPlan ? (
        <div className="card" style={{ marginTop: 8 }}>
          <div className="h2">Preview Plan</div>
          <div className="small mono">items={(previewPlan.items || []).length}</div>
          <pre style={{ maxHeight: 120, overflow: "auto", marginTop: 6 }}>{JSON.stringify(previewPlan.assumptions || {}, null, 2)}</pre>
          <div className="scroll" style={{ maxHeight: 200, marginTop: 6 }}>
            {(previewPlan.items || []).map((it: any, idx: number) => (
              <div key={`${idx}-${String(it.kind || "")}`} className="node-item" style={{ marginBottom: 6 }}>
                <div className="small mono">{String(it.kind || "-")} · {String(it.target_window || "-")} · p={String(it.target_p_vol_min)}~{String(it.target_p_vol_max)}</div>
                <div>{String(it.summary || "(no summary)")}</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="row" style={{ gap: 10, alignItems: "stretch", marginTop: 8 }}>
        <div className="card" style={{ flex: "1 1 60%" }}>
          <div className="h2">Active Plan</div>
          {!activePlan ? (
            <div className="hint">No active plan.</div>
          ) : (
            <>
              <div className="small mono">
                vol_plan_id={String(activePlan.vol_plan_id || "").slice(0, 8)} · version={String(activePlan.version || "-")} · status={String(activePlan.status || "-")}
              </div>
              <div className="small mono">note={String(activePlan.note || "")}</div>
              <div className="row" style={{ marginTop: 6, gap: 8, alignItems: "center" }}>
                <button onClick={() => void saveAllDirty()} disabled={Object.keys(dirtyIds).length === 0}>
                  Save All Dirty ({Object.keys(dirtyIds).length})
                </button>
                <button onClick={lockAllGrowthP5} disabled={!activePlan?.items?.length}>Lock all growth p5+</button>
                <button onClick={unlockAll} disabled={!activePlan?.items?.length}>Unlock all</button>
                <span className="small mono">editable summaries + p_range sliders</span>
              </div>
              <pre style={{ maxHeight: 120, overflow: "auto", marginTop: 6 }}>{JSON.stringify(activePlan.assumptions || {}, null, 2)}</pre>
              <div className="card" style={{ marginTop: 8 }}>
                <div className="h2">Timeline (p_vol 0 → 1)</div>
                <div style={{ position: "relative", height: 16, marginBottom: 6, border: "1px solid #333", borderRadius: 6 }}>
                  {[0, 0.18, 0.65, 0.9, 1].map((x) => (
                    <div
                      key={`tick-${x}`}
                      style={{
                        position: "absolute",
                        left: `${x * 100}%`,
                        top: 0,
                        bottom: 0,
                        width: 1,
                        background: "#333",
                      }}
                    />
                  ))}
                </div>
                <div className="small mono" style={{ marginBottom: 6 }}>
                  setup(0-0.18) · build(0.18-0.65) · spike(0.65-0.90) · release(0.90-1.00)
                </div>
                <div className="scroll" style={{ maxHeight: 180 }}>
                  {timelineRows.length === 0 ? (
                    <div className="hint">No items.</div>
                  ) : (
                    timelineRows.map((lane, idx) => (
                      <div key={`lane-${idx}`} style={{ position: "relative", height: 28, marginBottom: 6, border: "1px solid #2a2a2a", borderRadius: 6 }}>
                        {lane.map((it: any) => {
                          const s = Number(it.__start ?? 0);
                          const e = Number(it.__end ?? s);
                          const left = `${Math.max(0, Math.min(100, s * 100))}%`;
                          const width = `${Math.max(1, (e - s) * 100)}%`;
                          const kind = String(it.kind || "");
                          const bg =
                            kind === "growth"
                              ? "#2f6feb"
                              : kind === "foreshadow_payoff"
                                ? "#1f883d"
                                : kind === "foreshadow_seed"
                                  ? "#9a6700"
                                  : "#8250df";
                          return (
                            <div
                              key={String(it.item_id || `${idx}-${kind}`)}
                              title={`${kind} | p=${s.toFixed(2)}-${e.toFixed(2)} | ${String(it.summary || "")}`}
                              style={{
                                position: "absolute",
                                left,
                                width,
                                top: 3,
                                bottom: 3,
                                background: bg,
                                color: "#fff",
                                borderRadius: 4,
                                overflow: "hidden",
                                whiteSpace: "nowrap",
                                textOverflow: "ellipsis",
                                padding: "2px 6px",
                                fontSize: 12,
                              }}
                            >
                              {kind}
                            </div>
                          );
                        })}
                      </div>
                    ))
                  )}
                </div>
              </div>
              <div className="card" style={{ marginTop: 8 }}>
                <div className="h2">Conflict Detector</div>
                <div className="row" style={{ gap: 8, marginBottom: 6 }}>
                  <button onClick={applySuggestions} disabled={conflictSuggestions.length === 0}>
                    Apply Suggestions ({conflictSuggestions.length})
                  </button>
                </div>
                {conflictSuggestions.length > 0 ? (
                  <div className="scroll" style={{ maxHeight: 120, marginBottom: 8 }}>
                    {conflictSuggestions.map((s: any) => (
                      <div key={`s-${s.item_id}`} className="small mono" style={{ marginBottom: 4 }}>
                        {String(s.item_id).slice(0, 8)} delta={s.delta > 0 ? "+" : ""}
                        {String(s.delta)} {"->"} [{s.suggested_min.toFixed(2)}, {s.suggested_max.toFixed(2)}]
                      </div>
                    ))}
                  </div>
                ) : null}
                {timelineConflicts.length === 0 ? (
                  <div className="hint">No high-priority must_happen overlaps.</div>
                ) : (
                  <div className="scroll" style={{ maxHeight: 180 }}>
                    {timelineConflicts.map((cf: any, idx: number) => (
                      <div key={`${cf.a_id}-${cf.b_id}-${idx}`} className="node-item" style={{ marginBottom: 6 }}>
                        <div className="small mono">
                          overlap={cf.overlap} · {String(cf.a_kind)}({cf.a_p[0].toFixed(2)}-{cf.a_p[1].toFixed(2)}) ×{" "}
                          {String(cf.b_kind)}({cf.b_p[0].toFixed(2)}-{cf.b_p[1].toFixed(2)})
                        </div>
                        <div className="row" style={{ gap: 6, marginTop: 4, flexWrap: "wrap" }}>
                          <button
                            onClick={() => {
                              shiftItemRange(String(cf.a_id), -0.03);
                            }}
                          >
                            Shift A Left
                          </button>
                          <button
                            onClick={() => {
                              shiftItemRange(String(cf.a_id), 0.03);
                            }}
                          >
                            Shift A Right
                          </button>
                          <button
                            onClick={() => {
                              shiftItemRange(String(cf.b_id), -0.03);
                            }}
                          >
                            Shift B Left
                          </button>
                          <button
                            onClick={() => {
                              shiftItemRange(String(cf.b_id), 0.03);
                            }}
                          >
                            Shift B Right
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className="scroll" style={{ maxHeight: 300, marginTop: 6 }}>
                {(activePlan.items || []).map((it: any) => (
                  <div key={String(it.item_id || "")} className="node-item" style={{ marginBottom: 8 }}>
                    <div className="row" style={{ gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                      <span className="mono">{String(it.kind || "-")}</span>
                      <span className="chip">{String(it.target_window || "-")}</span>
                      <span className="small mono">{String(it.item_id || "").slice(0, 8)}</span>
                      {dirtyIds[String(it.item_id || "")] ? <span className="chip on">dirty</span> : null}
                    </div>
                    <textarea
                      rows={2}
                      value={String(it.summary || "")}
                      onChange={(e) => patchItem(String(it.item_id || ""), { summary: e.target.value })}
                    />
                    <div className="row" style={{ gap: 8, marginTop: 4, flexWrap: "wrap" }}>
                      <div style={{ minWidth: 320 }}>
                        <div className="small mono">
                          p_range {Number(it.target_p_vol_min ?? 0).toFixed(2)} ~ {Number(it.target_p_vol_max ?? 0).toFixed(2)}
                        </div>
                        <div className="row" style={{ gap: 6 }}>
                          <input
                            type="range"
                            min={0}
                            max={1}
                            step={0.01}
                            value={Number(it.target_p_vol_min ?? 0)}
                            onChange={(e) => patchRange(String(it.item_id || ""), "target_p_vol_min", Number(e.target.value))}
                          />
                          <input
                            type="range"
                            min={0}
                            max={1}
                            step={0.01}
                            value={Number(it.target_p_vol_max ?? 1)}
                            onChange={(e) => patchRange(String(it.item_id || ""), "target_p_vol_max", Number(e.target.value))}
                          />
                        </div>
                      </div>
                      <label className="small">
                        p_min
                        <input
                          style={{ width: 86 }}
                          value={String(it.target_p_vol_min ?? "")}
                          onChange={(e) => patchRange(String(it.item_id || ""), "target_p_vol_min", Number(e.target.value))}
                        />
                      </label>
                      <label className="small">
                        p_max
                        <input
                          style={{ width: 86 }}
                          value={String(it.target_p_vol_max ?? "")}
                          onChange={(e) => patchRange(String(it.item_id || ""), "target_p_vol_max", Number(e.target.value))}
                        />
                      </label>
                      <label className="small">
                        priority
                        <input
                          style={{ width: 68 }}
                          value={String(it.priority ?? "")}
                          onChange={(e) => patchItem(String(it.item_id || ""), { priority: e.target.value })}
                        />
                      </label>
                      <label className="small row" style={{ gap: 6, alignItems: "center" }}>
                        <input
                          type="checkbox"
                          checked={!!it.must_happen}
                          onChange={(e) => patchItem(String(it.item_id || ""), { must_happen: e.target.checked })}
                        />
                        must
                      </label>
                      <label className="small row" style={{ gap: 6, alignItems: "center" }}>
                        <input
                          type="checkbox"
                          checked={!!(it?.meta?.lock_auto_shift)}
                          onChange={(e) =>
                            patchItem(String(it.item_id || ""), {
                              meta: {
                                ...(typeof it.meta === "object" && it.meta ? it.meta : {}),
                                lock_auto_shift: e.target.checked,
                              },
                            })
                          }
                        />
                        lock
                      </label>
                      <button onClick={() => void saveItemPatch(it)}>Save</button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        <div className="card" style={{ flex: "1 1 40%" }}>
          <div className="h2">Versions</div>
          <div className="scroll" style={{ maxHeight: 380 }}>
            {versions.length === 0 ? (
              <div className="hint">No versions.</div>
            ) : (
              versions.map((v: any) => (
                <div key={String(v.vol_plan_id || "")} className="node-item" style={{ marginBottom: 6 }}>
                  <div className="row">
                    <strong>v{String(v.version || "-")}</strong>
                    <span className={`chip ${String(v.status || "") === "active" ? "on" : ""}`}>{String(v.status || "-")}</span>
                  </div>
                  <div className="small mono">{String(v.vol_plan_id || "").slice(0, 8)} · {String(v.created_at || "")}</div>
                  <div className="small">{String(v.note || "")}</div>
                  <div className="row" style={{ gap: 6, marginTop: 4 }}>
                    <button onClick={() => void promoteVersion(Number(v.version || 0))} disabled={String(v.status || "") === "active"}>
                      Promote
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
