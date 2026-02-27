import { useEffect, useMemo, useState } from "react";

type AssetSnapshotHead = {
  snapshot_id: string;
  book_id: string;
  snapshot_name: string;
  reason: string;
  tag: string;
  summary?: Record<string, any>;
  created_by?: string;
  created_at: string;
  item_count?: number;
};

type AssetSnapshotDetail = {
  snapshot: AssetSnapshotHead;
  items: Array<Record<string, any>>;
  item_count: number;
  type_counts: Record<string, number>;
};

type AssetCenterPanelProps = {
  baseUrl: string;
  bookId: string;
  onStatus?: (msg: string) => void;
  onAfterRollback?: () => void | Promise<void>;
};

function toText(value: unknown): string {
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

async function readJson(res: Response): Promise<any> {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

function formatErr(payload: any, fallback: string): string {
  const detail = toText(payload?.detail_zh || payload?.detail || payload?.message || "").trim();
  return detail || fallback;
}

export function AssetCenterPanel(props: AssetCenterPanelProps) {
  const { baseUrl, bookId, onStatus, onAfterRollback } = props;
  const [loading, setLoading] = useState(false);
  const [captureBusy, setCaptureBusy] = useState(false);
  const [rollbackBusy, setRollbackBusy] = useState(false);
  const [snapshots, setSnapshots] = useState<AssetSnapshotHead[]>([]);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState("");
  const [snapshotDetail, setSnapshotDetail] = useState<AssetSnapshotDetail | null>(null);
  const [snapshotName, setSnapshotName] = useState("");
  const [snapshotReason, setSnapshotReason] = useState("");
  const [rollbackNote, setRollbackNote] = useState("");
  const [restoreChapterOutlines, setRestoreChapterOutlines] = useState(false);
  const [promptPack, setPromptPack] = useState<Record<string, string>>({});
  const [currentState, setCurrentState] = useState<Record<string, any> | null>(null);

  const selectedSnapshot = useMemo(
    () => snapshots.find((item) => String(item.snapshot_id) === String(selectedSnapshotId)) || null,
    [snapshots, selectedSnapshotId]
  );

  async function loadSnapshots(targetSnapshotId?: string) {
    if (!bookId) return;
    setLoading(true);
    try {
      const res = await fetch(`${baseUrl}/v1/books/${bookId}/asset_snapshots?limit=40&include_outline_versions=true`);
      const payload = await readJson(res);
      if (!res.ok) throw new Error(formatErr(payload, "加载资产快照失败"));
      const items = Array.isArray(payload?.items) ? payload.items : [];
      setSnapshots(items);
      setPromptPack(
        payload?.prompt_pack && typeof payload.prompt_pack === "object"
          ? payload.prompt_pack
          : {}
      );
      setCurrentState(payload?.current_state && typeof payload.current_state === "object" ? payload.current_state : null);
      const nextId = toText(targetSnapshotId || selectedSnapshotId || items?.[0]?.snapshot_id).trim();
      setSelectedSnapshotId(nextId);
      if (nextId) await loadSnapshotDetail(nextId);
      else setSnapshotDetail(null);
      onStatus?.("资产快照列表已刷新");
    } catch (err: any) {
      onStatus?.(`资产快照刷新失败：${toText(err?.message || err)}`);
    } finally {
      setLoading(false);
    }
  }

  async function loadSnapshotDetail(snapshotId: string) {
    const sid = toText(snapshotId).trim();
    if (!bookId || !sid) return;
    try {
      const res = await fetch(`${baseUrl}/v1/books/${bookId}/asset_snapshots/${sid}`);
      const payload = await readJson(res);
      if (!res.ok) throw new Error(formatErr(payload, "加载快照详情失败"));
      setSnapshotDetail(payload as AssetSnapshotDetail);
      setSelectedSnapshotId(sid);
    } catch (err: any) {
      onStatus?.(`快照详情加载失败：${toText(err?.message || err)}`);
    }
  }

  async function captureSnapshot() {
    if (!bookId) return;
    setCaptureBusy(true);
    try {
      const res = await fetch(`${baseUrl}/v1/books/${bookId}/asset_snapshots/capture`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          snapshot_name: snapshotName.trim() || undefined,
          reason: snapshotReason.trim() || undefined,
          tag: "manual",
          include_chapter_outlines: true,
        }),
      });
      const payload = await readJson(res);
      if (!res.ok) throw new Error(formatErr(payload, "创建快照失败"));
      const sid = toText(payload?.snapshot?.snapshot_id).trim();
      setSnapshotName("");
      onStatus?.(`资产快照已创建：${toText(payload?.snapshot?.snapshot_name || sid)}`);
      await loadSnapshots(sid || undefined);
    } catch (err: any) {
      onStatus?.(`创建资产快照失败：${toText(err?.message || err)}`);
    } finally {
      setCaptureBusy(false);
    }
  }

  async function rollbackSnapshot() {
    if (!bookId || !selectedSnapshotId) return;
    setRollbackBusy(true);
    try {
      const res = await fetch(`${baseUrl}/v1/books/${bookId}/asset_snapshots/${selectedSnapshotId}/rollback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          note: rollbackNote.trim() || undefined,
          restore_chapter_outlines: restoreChapterOutlines,
        }),
      });
      const payload = await readJson(res);
      if (!res.ok) throw new Error(formatErr(payload, "回滚失败"));
      onStatus?.(
        `资产回滚完成：已应用 ${Number(payload?.result?.applied?.length || 0)} 项，跳过 ${Number(
          payload?.result?.skipped?.length || 0
        )} 项`
      );
      if (onAfterRollback) await onAfterRollback();
      await loadSnapshots(selectedSnapshotId);
    } catch (err: any) {
      onStatus?.(`资产回滚失败：${toText(err?.message || err)}`);
    } finally {
      setRollbackBusy(false);
    }
  }

  async function copyPrompt(textValue: string, label: string) {
    try {
      await navigator.clipboard.writeText(textValue || "");
      onStatus?.(`已复制提示词：${label}`);
    } catch {
      onStatus?.(`复制失败，请手动复制：${label}`);
    }
  }

  useEffect(() => {
    setSnapshots([]);
    setSelectedSnapshotId("");
    setSnapshotDetail(null);
    setPromptPack({});
    setCurrentState(null);
    if (bookId) {
      void loadSnapshots();
    }
  }, [bookId]);

  return (
    <div className="asset-center-panel">
      <div className="row" style={{ marginBottom: 8 }}>
        <strong>资产沉淀管理</strong>
        <span className="small">目标：可审查、可优化、可回滚，确保写作资产持续进化。</span>
      </div>
      {!bookId ? (
        <div className="small">请先在写作工作台选择书籍，再使用资产沉淀管理。</div>
      ) : (
        <>
          <div className="asset-center-grid">
            <div className="asset-center-card">
              <div className="row">
                <strong>创建快照</strong>
                <button onClick={() => void loadSnapshots()} disabled={loading || captureBusy}>
                  {loading ? "刷新中..." : "刷新列表"}
                </button>
              </div>
              <label style={{ marginTop: 8 }}>
                快照名称（可选）
                <input
                  value={snapshotName}
                  onChange={(e) => setSnapshotName(e.target.value)}
                  placeholder="例如：卷纲迭代前"
                />
              </label>
              <label style={{ marginTop: 8 }}>
                快照说明
                <textarea
                  rows={2}
                  value={snapshotReason}
                  onChange={(e) => setSnapshotReason(e.target.value)}
                  placeholder="记录当前阶段与目的，便于审计与回滚"
                />
              </label>
              <div className="row" style={{ marginTop: 8 }}>
                <button onClick={() => void captureSnapshot()} disabled={captureBusy || !bookId}>
                  {captureBusy ? "创建中..." : "创建资产快照"}
                </button>
                <span className="small">当前快照数：{snapshots.length}</span>
              </div>
              <hr style={{ margin: "10px 0" }} />
              <div className="small" style={{ marginBottom: 6 }}>快照列表（最新在前）</div>
              <div className="scroll" style={{ maxHeight: 320 }}>
                {snapshots.length === 0 ? (
                  <div className="small">暂无快照。</div>
                ) : (
                  snapshots.map((item) => (
                    <button
                      key={item.snapshot_id}
                      className={`node-item ${selectedSnapshotId === item.snapshot_id ? "active" : ""}`}
                      onClick={() => void loadSnapshotDetail(item.snapshot_id)}
                    >
                      <div style={{ flex: 1 }}>
                        <div><strong>{toText(item.snapshot_name || "未命名快照")}</strong></div>
                        <div className="small">
                          {toText(item.reason || "无说明")} · 项目 {Number(item.item_count || 0)} 个
                        </div>
                        <div className="small">{new Date(item.created_at).toLocaleString("zh-CN", { hour12: false })}</div>
                      </div>
                    </button>
                  ))
                )}
              </div>
            </div>
            <div className="asset-center-card">
              <div className="row">
                <strong>快照详情与回滚</strong>
                <span className="small">{selectedSnapshot ? `已选：${selectedSnapshot.snapshot_name || selectedSnapshot.snapshot_id}` : "未选择"}</span>
              </div>
              {currentState ? (
                <div className="small" style={{ marginTop: 6 }}>
                  当前资产：章节 {Number(currentState?.counts?.chapters || 0)} · 卷 {Number(currentState?.counts?.volumes || 0)} · 素材 {Number(currentState?.counts?.material_cards || 0)} · 章纲版本 {Number(currentState?.counts?.chapter_outline_versions || 0)}
                </div>
              ) : null}
              {snapshotDetail ? (
                <>
                  <div className="small" style={{ marginTop: 8 }}>
                    快照时间：{new Date(toText(snapshotDetail.snapshot.created_at)).toLocaleString("zh-CN", { hour12: false })}
                  </div>
                  <div className="small" style={{ marginTop: 4 }}>
                    类型统计：{Object.entries(snapshotDetail.type_counts || {})
                      .map(([k, v]) => `${k}:${v}`)
                      .join(" / ") || "无"}
                  </div>
                  <label style={{ marginTop: 10 }}>
                    回滚说明（可选）
                    <input
                      value={rollbackNote}
                      onChange={(e) => setRollbackNote(e.target.value)}
                      placeholder="例如：回退到章节生成前结构基线"
                    />
                  </label>
                  <label className="small" style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 8 }}>
                    <input
                      type="checkbox"
                      checked={restoreChapterOutlines}
                      onChange={(e) => setRestoreChapterOutlines(e.target.checked)}
                    />
                    同时回滚章纲版本（可能较慢，默认关闭）
                  </label>
                  <div className="row" style={{ marginTop: 8 }}>
                    <button className="danger" onClick={() => void rollbackSnapshot()} disabled={rollbackBusy}>
                      {rollbackBusy ? "回滚中..." : "回滚到此快照"}
                    </button>
                  </div>
                  <div className="scroll" style={{ maxHeight: 220, marginTop: 10 }}>
                    {snapshotDetail.items.map((item) => (
                      <div key={toText(item.item_id)} className="issue-item">
                        <div><strong>{toText(item.asset_type)}</strong> · {toText(item.asset_key || "-")}</div>
                        <div className="small">version={item.version ?? "-"}</div>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="small" style={{ marginTop: 8 }}>请先选择一个快照查看详情。</div>
              )}
            </div>
          </div>

          <div className="asset-center-card" style={{ marginTop: 10 }}>
            <div className="row">
              <strong>AI 资产整理提示词（可直接复用）</strong>
              <span className="small">用于审查、压缩、优化资产并保留回滚安全性</span>
            </div>
            <label style={{ marginTop: 8 }}>
              资产审查与优化计划 Prompt
              <textarea rows={9} readOnly value={toText(promptPack?.review_and_plan)} />
            </label>
            <div className="row" style={{ marginTop: 6 }}>
              <button onClick={() => void copyPrompt(toText(promptPack?.review_and_plan), "资产审查与优化计划")}>复制 Prompt</button>
            </div>
            <label style={{ marginTop: 8 }}>
              回滚安全变更 Prompt
              <textarea rows={5} readOnly value={toText(promptPack?.rollback_safe_patch)} />
            </label>
            <div className="row" style={{ marginTop: 6 }}>
              <button onClick={() => void copyPrompt(toText(promptPack?.rollback_safe_patch), "回滚安全变更")}>复制 Prompt</button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

