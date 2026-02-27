import { useEffect, useMemo, useRef, useState } from "react";
import { DeleteConfirmDialog } from "./DeleteConfirmDialog";

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
  const [note, setNote] = useState("手动更新");
  const [volumeGoal, setVolumeGoal] = useState("");
  const [volumeTheme, setVolumeTheme] = useState("");
  const [targetPacing, setTargetPacing] = useState("mid");
  const [loading, setLoading] = useState(false);
  const [versionDeleting, setVersionDeleting] = useState(0);
  const [deleteDialog, setDeleteDialog] = useState<{
    version: number;
    token: string;
    typedToken: string;
    status: string;
  } | null>(null);
  const [deleteError, setDeleteError] = useState("");
  const [deleteInputShake, setDeleteInputShake] = useState(false);
  const deleteInputRef = useRef<HTMLInputElement | null>(null);
  const deleteShakeTimerRef = useRef<number | null>(null);

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
      const reason = `${moveB ? "移动B(move B)" : "移动A(move A)"} 处理 ${a.kind}×${b.kind}${aLocked || bLocked ? "（保护锁定成长）" : ""}`;
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

  function formatDeleteError(err: any): string {
    const message = String(err?.message || err || "").trim();
    if (!message) return "删除失败";
    if (/VOLUME_PLAN_DELETE_LAST_FORBIDDEN/i.test(message)) return "当前分卷仅剩一个方案版本，不能删除。";
    if (/VOLUME_PLAN_DELETE_NO_REPLACEMENT/i.test(message)) return "删除失败：没有可切换的替代分卷方案。";
    if (/VOLUME_PLAN_VERSION_NOT_FOUND/i.test(message)) return "方案版本不存在或已删除。";
    if (/FAILED:(\d+)/i.test(message)) {
      const code = message.match(/FAILED:(\d+)/i)?.[1] || "";
      return `删除失败（HTTP ${code}）`;
    }
    return message.replace(/^Error:\s*/i, "");
  }

  function openDeleteVersionDialog(version: number, status: string) {
    const v = Number(version || 0);
    if (!v) return;
    setDeleteError("");
    setDeleteInputShake(false);
    setDeleteDialog({
      version: v,
      status: String(status || "").trim().toLowerCase(),
      token: `v${v}`,
      typedToken: "",
    });
  }

  function markDeleteMismatch() {
    setDeleteError("输入校验码不一致，请核对后重试。");
    setDeleteInputShake(true);
    if (deleteShakeTimerRef.current) {
      window.clearTimeout(deleteShakeTimerRef.current);
      deleteShakeTimerRef.current = null;
    }
    deleteShakeTimerRef.current = window.setTimeout(() => {
      setDeleteInputShake(false);
      deleteShakeTimerRef.current = null;
    }, 280);
    const el = deleteInputRef.current;
    if (el) {
      el.focus();
      el.select();
    }
  }

  async function confirmDeleteVersionDialog() {
    if (!bookId || !selectedVolumeId || !deleteDialog) return;
    setVersionDeleting(deleteDialog.version);
    setDeleteError("");
    try {
      const res = await fetch(`${baseUrl}/v1/books/${bookId}/volumes/${selectedVolumeId}/plan/${deleteDialog.version}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        let detail = "";
        try {
          const out = await res.json();
          detail = String(out?.detail_zh || out?.detail || "").trim();
        } catch {
          // ignore
        }
        throw new Error(detail || `VOLUME_PLAN_DELETE_FAILED:${res.status}`);
      }
      const out = await res.json();
      setDeleteDialog(null);
      await loadPlan();
      const replacement = Number(out?.replacement_version || 0);
      if (replacement > 0) {
        onStatus(`已删除 v${deleteDialog.version}，并自动切换当前方案到 v${replacement}`);
      } else {
        onStatus(`已删除方案版本：v${deleteDialog.version}`);
      }
    } catch (err: any) {
      const msg = formatDeleteError(err);
      setDeleteError(msg);
      onStatus(`删除分卷方案失败：${msg}`);
    } finally {
      setVersionDeleting(0);
    }
  }

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
    onStatus(`分卷已自动创建：${String(out.created || 0)}`);
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
    onStatus(`预览已就绪：${(out.plan?.items || []).length} 条目`);
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
    onStatus(`分卷方案已应用：v${String(out.version || "?")}`);
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
    onStatus(`分卷方案已生成：v${String(out.version || "?")}`);
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
    onStatus(`方案已设为当前版本：v${String(out.active_version || v)}`);
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
    onStatus(`方案已回滚至当前版本：v${String(out.active_version || "-")}`);
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
    onStatus(`学习完成：A_growth=${String(learning.A_growth ?? "-")} A_payoff=${String(learning.A_payoff ?? "-")}`);
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
    onStatus(`方案条目已保存：${String(item.item_id).slice(0, 8)}`);
  }

  async function saveAllDirty() {
    if (!bookId || !selectedVolumeId || !activePlan?.items) return;
    const rows = (activePlan.items || []).filter((x: any) => dirtyIds[String(x.item_id || "")]);
    if (!rows.length) {
      onStatus("暂无待保存修改");
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
    onStatus(`方案条目已保存：${String(out.updated || 0)}`);
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
      onStatus("暂无可应用的建议");
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
    onStatus(`已应用 ${conflictSuggestions.length} 条冲突建议（未保存）`);
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
    onStatus(`已锁定成长 p5+：${touched} 条（未保存）`);
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
    onStatus(`已解锁条目：${touched} 条（未保存）`);
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

  useEffect(() => {
    if (!deleteDialog) {
      setDeleteError("");
      setDeleteInputShake(false);
      return;
    }
    const timer = window.setTimeout(() => {
      const el = deleteInputRef.current;
      if (el) {
        el.focus();
        el.select();
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [deleteDialog]);

  useEffect(() => {
    return () => {
      if (deleteShakeTimerRef.current) {
        window.clearTimeout(deleteShakeTimerRef.current);
        deleteShakeTimerRef.current = null;
      }
    };
  }, []);

  return (
    <div style={{ marginTop: 10 }}>
      <div className="h2">分卷规划看板</div>
      <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <button onClick={() => void autoCreateVolumes()} disabled={!bookId}>自动创建分卷</button>
        <button onClick={() => void loadVolumes()} disabled={!bookId}>刷新分卷</button>
        <label>
          分卷
          <select value={selectedVolumeId} onChange={(e) => setSelectedVolumeId(e.target.value)} disabled={!bookId || volumes.length === 0}>
            <option value="">(无)</option>
            {volumes.map((v: any) => (
              <option key={String(v.volume_id)} value={String(v.volume_id)}>
                卷{String(v.volume_no)} · 章{String(v.start_chapter_no)}-{String(v.end_chapter_no)}
              </option>
            ))}
          </select>
        </label>
        <div className="small mono">
          章节ID(chapter_id)={chapterId ? String(chapterId).slice(0, 8) : "-"} · 分卷={selectedVolume ? String(selectedVolume.volume_no) : "-"} {loading ? "· 加载中..." : ""}
        </div>
      </div>

      <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "flex-end", marginTop: 8 }}>
        <label style={{ minWidth: 240 }}>
          本卷目标
          <input value={volumeGoal} onChange={(e) => setVolumeGoal(e.target.value)} placeholder="本卷主线目标" />
        </label>
        <label style={{ minWidth: 220 }}>
          主题
          <input value={volumeTheme} onChange={(e) => setVolumeTheme(e.target.value)} placeholder="主题（可选）" />
        </label>
        <label>
          节奏
          <select value={targetPacing} onChange={(e) => setTargetPacing(e.target.value)}>
            <option value="slow">慢(slow)</option>
            <option value="mid">中(mid)</option>
            <option value="fast">快(fast)</option>
          </select>
        </label>
      </div>

      <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "flex-end", marginTop: 8 }}>
        <label style={{ minWidth: 260 }}>
          备注
          <input value={note} onChange={(e) => setNote(e.target.value)} />
        </label>
        <button onClick={() => void previewAutoPlan()} disabled={!selectedVolumeId}>预览自动方案</button>
        <button onClick={() => void applyAutoPlan()} disabled={!selectedVolumeId}>应用自动方案</button>
        <button onClick={() => void autoGeneratePlan()} disabled={!selectedVolumeId}>自动生成（旧版）</button>
        <button onClick={() => void learnFromBatches()} disabled={!selectedVolumeId}>批次学习</button>
        <button onClick={() => void rollbackLast()} disabled={!selectedVolumeId}>回滚上一版</button>
      </div>

      {previewPlan ? (
        <div className="card" style={{ marginTop: 8 }}>
          <div className="h2">预览方案</div>
          <div className="small mono">条目数={(previewPlan.items || []).length}</div>
          <pre style={{ maxHeight: 120, overflow: "auto", marginTop: 6 }}>{JSON.stringify(previewPlan.assumptions || {}, null, 2)}</pre>
          <div className="scroll" style={{ maxHeight: 200, marginTop: 6 }}>
            {(previewPlan.items || []).map((it: any, idx: number) => (
              <div key={`${idx}-${String(it.kind || "")}`} className="node-item" style={{ marginBottom: 6 }}>
                <div className="small mono">{String(it.kind || "-")} · {String(it.target_window || "-")} · p={String(it.target_p_vol_min)}~{String(it.target_p_vol_max)}</div>
                <div>{String(it.summary || "(无摘要)")}</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="row" style={{ gap: 10, alignItems: "stretch", marginTop: 8 }}>
        <div className="card" style={{ flex: "1 1 60%" }}>
          <div className="h2">当前方案</div>
          {!activePlan ? (
            <div className="hint">暂无当前方案。</div>
          ) : (
            <>
              <div className="small mono">
                方案ID(vol_plan_id)={String(activePlan.vol_plan_id || "").slice(0, 8)} · 版本={String(activePlan.version || "-")} · 状态={String(activePlan.status || "-")}
              </div>
              <div className="small mono">备注={String(activePlan.note || "")}</div>
              <div className="row" style={{ marginTop: 6, gap: 8, alignItems: "center" }}>
                <button onClick={() => void saveAllDirty()} disabled={Object.keys(dirtyIds).length === 0}>
                  保存全部未保存项 ({Object.keys(dirtyIds).length})
                </button>
                <button onClick={lockAllGrowthP5} disabled={!activePlan?.items?.length}>锁定所有成长 p5+</button>
                <button onClick={unlockAll} disabled={!activePlan?.items?.length}>全部解锁</button>
                <span className="small mono">可编辑摘要 + p范围(p_range)滑杆</span>
              </div>
              <pre style={{ maxHeight: 120, overflow: "auto", marginTop: 6 }}>{JSON.stringify(activePlan.assumptions || {}, null, 2)}</pre>
              <div className="card" style={{ marginTop: 8 }}>
                <div className="h2">时间线 (p_vol 0 → 1)</div>
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
                  铺垫(setup)(0-0.18) · 累积(build)(0.18-0.65) · 高潮(spike)(0.65-0.90) · 收束(release)(0.90-1.00)
                </div>
                <div className="scroll" style={{ maxHeight: 180 }}>
                  {timelineRows.length === 0 ? (
                    <div className="hint">暂无条目。</div>
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
                <div className="h2">冲突检测器</div>
                <div className="row" style={{ gap: 8, marginBottom: 6 }}>
                  <button onClick={applySuggestions} disabled={conflictSuggestions.length === 0}>
                    应用建议 ({conflictSuggestions.length})
                  </button>
                </div>
                {conflictSuggestions.length > 0 ? (
                  <div className="scroll" style={{ maxHeight: 120, marginBottom: 8 }}>
                    {conflictSuggestions.map((s: any) => (
                      <div key={`s-${s.item_id}`} className="small mono" style={{ marginBottom: 4 }}>
                        {String(s.item_id).slice(0, 8)} 变动={s.delta > 0 ? "+" : ""}
                        {String(s.delta)} {"->"} [{s.suggested_min.toFixed(2)}, {s.suggested_max.toFixed(2)}]
                      </div>
                    ))}
                  </div>
                ) : null}
                {timelineConflicts.length === 0 ? (
                  <div className="hint">无高优先级必须发生(must_happen)重叠。</div>
                ) : (
                  <div className="scroll" style={{ maxHeight: 180 }}>
                    {timelineConflicts.map((cf: any, idx: number) => (
                      <div key={`${cf.a_id}-${cf.b_id}-${idx}`} className="node-item" style={{ marginBottom: 6 }}>
                        <div className="small mono">
                          重叠={cf.overlap} · {String(cf.a_kind)}({cf.a_p[0].toFixed(2)}-{cf.a_p[1].toFixed(2)}) ×{" "}
                          {String(cf.b_kind)}({cf.b_p[0].toFixed(2)}-{cf.b_p[1].toFixed(2)})
                        </div>
                        <div className="row" style={{ gap: 6, marginTop: 4, flexWrap: "wrap" }}>
                          <button
                            onClick={() => {
                              shiftItemRange(String(cf.a_id), -0.03);
                            }}
                          >
                            A 左移
                          </button>
                          <button
                            onClick={() => {
                              shiftItemRange(String(cf.a_id), 0.03);
                            }}
                          >
                            A 右移
                          </button>
                          <button
                            onClick={() => {
                              shiftItemRange(String(cf.b_id), -0.03);
                            }}
                          >
                            B 左移
                          </button>
                          <button
                            onClick={() => {
                              shiftItemRange(String(cf.b_id), 0.03);
                            }}
                          >
                            B 右移
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
                      {dirtyIds[String(it.item_id || "")] ? <span className="chip on">未保存</span> : null}
                    </div>
                    <textarea
                      rows={2}
                      value={String(it.summary || "")}
                      onChange={(e) => patchItem(String(it.item_id || ""), { summary: e.target.value })}
                    />
                    <div className="row" style={{ gap: 8, marginTop: 4, flexWrap: "wrap" }}>
                      <div style={{ minWidth: 320 }}>
                        <div className="small mono">
                          p范围(p_range) {Number(it.target_p_vol_min ?? 0).toFixed(2)} ~ {Number(it.target_p_vol_max ?? 0).toFixed(2)}
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
                        下限(p_min)
                        <input
                          style={{ width: 86 }}
                          value={String(it.target_p_vol_min ?? "")}
                          onChange={(e) => patchRange(String(it.item_id || ""), "target_p_vol_min", Number(e.target.value))}
                        />
                      </label>
                      <label className="small">
                        上限(p_max)
                        <input
                          style={{ width: 86 }}
                          value={String(it.target_p_vol_max ?? "")}
                          onChange={(e) => patchRange(String(it.item_id || ""), "target_p_vol_max", Number(e.target.value))}
                        />
                      </label>
                      <label className="small">
                        优先级
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
                        必须
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
                        锁定
                      </label>
                      <button onClick={() => void saveItemPatch(it)}>保存</button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        <div className="card" style={{ flex: "1 1 40%" }}>
          <div className="h2">版本列表</div>
          {deleteError && !deleteDialog ? <div className="small danger" style={{ marginBottom: 6 }}>{deleteError}</div> : null}
          <div className="scroll" style={{ maxHeight: 380 }}>
            {versions.length === 0 ? (
              <div className="hint">暂无版本。</div>
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
                      设为当前
                    </button>
                    <button
                      className="danger"
                      onClick={() => openDeleteVersionDialog(Number(v.version || 0), String(v.status || ""))}
                      disabled={versions.length <= 1 || versionDeleting === Number(v.version || 0)}
                    >
                      {versionDeleting === Number(v.version || 0) ? "删除中..." : "删除版本"}
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <DeleteConfirmDialog
        open={!!deleteDialog}
        title="删除分卷方案版本"
        requireInput={false}
        targetLabel={
          deleteDialog ? (
            <>目标版本：<strong>v{deleteDialog.version}</strong>（状态：{deleteDialog.status || "-"}）</>
          ) : null
        }
        warning={
          deleteDialog?.status === "active"
            ? "该版本为当前方案，删除后会自动切换到其他版本。"
            : "删除后该方案版本与其条目将不可恢复。"
        }
        promptLabel={deleteDialog ? <>请输入校验码 <strong>{deleteDialog.token}</strong> 以确认删除</> : "请输入校验码以确认删除"}
        expectedText={String(deleteDialog?.token || "")}
        value={String(deleteDialog?.typedToken || "")}
        placeholder={String(deleteDialog?.token || "")}
        busy={!!versionDeleting}
        error={deleteError}
        inputRef={deleteInputRef}
        inputClassName={deleteInputShake ? "shake-once" : ""}
        confirmLabel="确认删除"
        busyLabel="删除中..."
        onValueChange={(next) => {
          setDeleteDialog((prev) => (prev ? { ...prev, typedToken: next } : prev));
          if (deleteError) setDeleteError("");
          if (deleteInputShake) setDeleteInputShake(false);
        }}
        onConfirm={() => void confirmDeleteVersionDialog()}
        onCancel={() => {
          setDeleteError("");
          setDeleteInputShake(false);
          setDeleteDialog(null);
        }}
        onMismatch={markDeleteMismatch}
      />
    </div>
  );
}
