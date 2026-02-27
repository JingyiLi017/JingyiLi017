import { useEffect, useRef, useState } from "react";
import { DeleteConfirmDialog } from "./DeleteConfirmDialog";

type MaterialItem = {
  card_id: string;
  book_id?: string | null;
  source_type: string;
  title: string;
  content: string;
  tag?: string | null;
  importance: number;
  score?: number | null;
};

type Props = {
  baseUrl: string;
  bookId: string;
  chapterId: string;
  materialRefs: string[];
  onAddRef: (block: string) => void;
  onRemoveRef: (index: number) => void;
  onClearRefs: () => void;
  onStatus: (msg: string) => void;
};

export function MaterialCenter(props: Props) {
  const { baseUrl, bookId, chapterId, materialRefs, onAddRef, onRemoveRef, onClearRefs, onStatus } = props;
  const [materialQ, setMaterialQ] = useState("");
  const [materialTag, setMaterialTag] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [importLimit, setImportLimit] = useState(100);
  const [materialItems, setMaterialItems] = useState<MaterialItem[]>([]);
  const [materialSelected, setMaterialSelected] = useState<MaterialItem | null>(null);
  const [materialTitle, setMaterialTitle] = useState("");
  const [materialContent, setMaterialContent] = useState("");
  const [materialImportance, setMaterialImportance] = useState(3);
  const [materialDeletingId, setMaterialDeletingId] = useState("");
  const [materialDeleteDialog, setMaterialDeleteDialog] = useState<{
    cardId: string;
    title: string;
    typedName: string;
  } | null>(null);
  const [materialDeleteError, setMaterialDeleteError] = useState("");
  const [materialDeleteInputShake, setMaterialDeleteInputShake] = useState(false);
  const materialDeleteInputRef = useRef<HTMLInputElement | null>(null);
  const materialDeleteShakeTimerRef = useRef<number | null>(null);

  function formatErr(err: unknown): string {
    const message = String((err as any)?.message || err || "").trim();
    if (!message) return "操作失败";
    if (/MATERIAL_NOT_FOUND/i.test(message)) return "素材不存在或已删除";
    if (/FAILED:(\d+)/i.test(message)) {
      const code = message.match(/FAILED:(\d+)/i)?.[1] || "";
      return `操作失败（HTTP ${code}）`;
    }
    return message.startsWith("Error:") ? message.replace(/^Error:\s*/, "") : message;
  }

  function openMaterialDeleteDialog(card: MaterialItem | null) {
    if (!card) return;
    setMaterialDeleteError("");
    setMaterialDeleteInputShake(false);
    setMaterialDeleteDialog({
      cardId: card.card_id,
      title: String(card.title || card.card_id).trim(),
      typedName: "",
    });
  }

  function markMaterialDeleteMismatch() {
    setMaterialDeleteError("输入标题与目标素材不一致，请核对后重试。");
    setMaterialDeleteInputShake(true);
    if (materialDeleteShakeTimerRef.current) {
      window.clearTimeout(materialDeleteShakeTimerRef.current);
      materialDeleteShakeTimerRef.current = null;
    }
    materialDeleteShakeTimerRef.current = window.setTimeout(() => {
      setMaterialDeleteInputShake(false);
      materialDeleteShakeTimerRef.current = null;
    }, 280);
    const el = materialDeleteInputRef.current;
    if (el) {
      el.focus();
      el.select();
    }
  }

  async function confirmDeleteMaterialDialog() {
    if (!materialDeleteDialog) return;
    const expected = String(materialDeleteDialog.title || "").trim();

    setMaterialDeletingId(materialDeleteDialog.cardId);
    try {
      const res = await fetch(`${baseUrl}/v1/materials/${materialDeleteDialog.cardId}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`MATERIAL_DELETE_FAILED:${res.status}`);
      let nextItems: MaterialItem[] = [];
      setMaterialItems((prev) => {
        nextItems = prev.filter((x) => x.card_id !== materialDeleteDialog.cardId);
        return nextItems;
      });
      setMaterialSelected((prev) => {
        if (!prev || prev.card_id !== materialDeleteDialog.cardId) return prev;
        return nextItems[0] || null;
      });
      setMaterialDeleteDialog(null);
      setMaterialDeleteError("");
      setMaterialDeleteInputShake(false);
      onStatus(`素材已删除：${expected}`);
    } catch (err) {
      const msg = formatErr(err);
      setMaterialDeleteError(msg);
      onStatus(`删除素材失败：${msg}`);
    } finally {
      setMaterialDeletingId("");
    }
  }

  async function searchMaterialsKnn() {
    if (!materialQ.trim()) return;
    const payload: Record<string, unknown> = {
      query_text: materialQ.trim(),
      k: 20,
      tag: materialTag.trim() || null,
    };
    if (bookId) payload.book_id = bookId;
    const res = await fetch(`${baseUrl}/v1/materials/knn`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`MATERIAL_KNN_FAILED:${res.status}`);
    const data = await res.json();
    setMaterialItems(data.items || []);
    setMaterialSelected((data.items || [])[0] || null);
  }

  async function createMaterialCard() {
    if (!materialTitle.trim() || !materialContent.trim()) return;
    const payload: Record<string, unknown> = {
      source_type: "manual",
      title: materialTitle.trim(),
      content: materialContent.trim(),
      tag: materialTag.trim() || null,
      importance: Number(materialImportance) || 3,
    };
    if (bookId) payload.book_id = bookId;
    const res = await fetch(`${baseUrl}/v1/materials`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`MATERIAL_CREATE_FAILED:${res.status}`);
    const row = await res.json();
    setMaterialTitle("");
    setMaterialContent("");
    setMaterialSelected(row);
    onStatus("素材已创建");
    try {
      await fetch(`${baseUrl}/v1/materials/${row.card_id}/embed`, { method: "POST" });
    } catch {
      // best effort
    }
    if (materialQ.trim()) {
      await searchMaterialsKnn();
    }
  }

  async function importFromChunks() {
    if (!bookId) throw new Error("BOOK_ID_REQUIRED");
    const payload: Record<string, unknown> = {
      book_id: bookId,
      source_id: sourceId.trim() || null,
      tag: materialTag.trim() || null,
      limit: Number(importLimit) || 100,
      source_type: "splitbook",
      importance: Number(materialImportance) || 3,
      auto_embed: true,
    };
    const res = await fetch(`${baseUrl}/v1/materials/import_from_chunks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`MATERIAL_IMPORT_FAILED:${res.status}`);
    const out = await res.json();
    onStatus(`导入完成：新增 ${out.created ?? 0}，向量化 ${out.embedded ?? 0}，失败 ${out.failed ?? 0}`);
    if (materialQ.trim()) {
      await searchMaterialsKnn();
    }
  }

  async function useMaterialAsRef(card: MaterialItem | null) {
    if (!card) return;
    if (!chapterId) {
      onStatus("请选择章节后再引用素材");
      return;
    }
    const res = await fetch(`${baseUrl}/v1/chapters/${chapterId}/ref_inbox/from_material`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        card_id: card.card_id,
        context: {
          need: "本章补强冲突/反转/代价",
        },
      }),
    });
    if (!res.ok) throw new Error(`REF_EXTRACT_FAILED:${res.status}`);
    const out = await res.json();
    onAddRef(String(out.ref_block || ""));
    onStatus(`已加入素材引用：${card.title}`);
  }

  useEffect(() => {
    if (!materialDeleteDialog) {
      setMaterialDeleteError("");
      setMaterialDeleteInputShake(false);
      return;
    }
    const timer = window.setTimeout(() => {
      const el = materialDeleteInputRef.current;
      if (el) {
        el.focus();
        el.select();
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [materialDeleteDialog]);

  useEffect(() => {
    return () => {
      if (materialDeleteShakeTimerRef.current) {
        window.clearTimeout(materialDeleteShakeTimerRef.current);
        materialDeleteShakeTimerRef.current = null;
      }
    };
  }, []);

  return (
    <section className="wb-panel" style={{ minHeight: "auto", marginBottom: 10 }}>
      <h3>素材中心</h3>
      <div className="job-grid">
        <div>
          <div className="row" style={{ marginBottom: 8 }}>
            <input value={materialQ} onChange={(e) => setMaterialQ(e.target.value)} placeholder="按意图搜索素材..." />
            <input value={materialTag} onChange={(e) => setMaterialTag(e.target.value)} placeholder="标签（可选）" />
            <button onClick={() => void searchMaterialsKnn()} disabled={!materialQ.trim()}>
              向量搜索
            </button>
          </div>
          <div className="row" style={{ marginBottom: 8, flexWrap: "wrap" }}>
            <input value={sourceId} onChange={(e) => setSourceId(e.target.value)} placeholder="来源ID(source_id，可选)" />
            <input type="number" min={1} max={1000} value={importLimit} onChange={(e) => setImportLimit(Number(e.target.value))} style={{ width: 120 }} />
            <button onClick={() => void importFromChunks()} disabled={!bookId}>
              从分块导入
            </button>
          </div>
          <div className="scroll" style={{ maxHeight: 260 }}>
            {materialItems.map((it) => (
              <button
                key={it.card_id}
                className={`node-item ${materialSelected?.card_id === it.card_id ? "active" : ""}`}
                onClick={() => setMaterialSelected(it)}
              >
                <div style={{ width: "100%" }}>
                  <div className="row">
                    <strong>{it.title}</strong>
                    <code>{Number(it.score || 0).toFixed(3)}</code>
                  </div>
                  <div className="small">标签={it.tag || "-"} · 重要度={it.importance || 3}</div>
                </div>
              </button>
            ))}
            {materialItems.length === 0 ? <div className="hint">暂无素材结果</div> : null}
          </div>
        </div>
        <div>
          <div className="row" style={{ marginBottom: 8 }}>
            <strong>素材详情</strong>
            <div className="row">
              <button
                onClick={() => {
                  void useMaterialAsRef(materialSelected).catch((e) => onStatus(String(e)));
                }}
                disabled={!materialSelected}
              >
                作为引用
              </button>
              <button
                className="danger"
                onClick={() => openMaterialDeleteDialog(materialSelected)}
                disabled={!materialSelected || materialDeletingId === materialSelected?.card_id}
              >
                {materialSelected && materialDeletingId === materialSelected.card_id ? "删除中..." : "删除素材"}
              </button>
            </div>
          </div>
          {materialSelected ? <pre>{materialSelected.content}</pre> : <div className="hint">请选择一张素材卡</div>}
          <hr />
          <div className="row" style={{ marginBottom: 8 }}>
            <strong>创建素材</strong>
          </div>
          <label>
            标题
            <input value={materialTitle} onChange={(e) => setMaterialTitle(e.target.value)} />
          </label>
          <label>
            内容
            <textarea rows={6} value={materialContent} onChange={(e) => setMaterialContent(e.target.value)} />
          </label>
          <div className="row">
            <label style={{ maxWidth: 120 }}>
              重要度
              <input type="number" min={1} max={5} value={materialImportance} onChange={(e) => setMaterialImportance(Number(e.target.value))} />
            </label>
            <button onClick={() => void createMaterialCard()} disabled={!materialTitle.trim() || !materialContent.trim()}>
              创建
            </button>
          </div>
        </div>
      </div>
      <div style={{ marginTop: 10 }}>
        <div className="row" style={{ marginBottom: 6 }}>
          <strong>引用收件箱 ({materialRefs.length})</strong>
          <div className="row">
            <button onClick={onClearRefs} disabled={materialRefs.length === 0}>
              清空引用
            </button>
          </div>
        </div>
        <div className="scroll" style={{ maxHeight: 200 }}>
          {materialRefs.map((r, idx) => (
            <div key={idx} className="issue-item">
              <div className="row">
                <code>引用 #{idx + 1}</code>
                <button onClick={() => onRemoveRef(idx)}>移除</button>
              </div>
              <pre>{r}</pre>
            </div>
          ))}
          {materialRefs.length === 0 ? <div className="hint">可使用“作为引用”将约束加入生成流程。</div> : null}
        </div>
      </div>

      <DeleteConfirmDialog
        open={!!materialDeleteDialog}
        title="删除素材确认"
        requireInput={false}
        targetLabel={materialDeleteDialog ? <>素材：<strong>{materialDeleteDialog.title}</strong></> : null}
        warning="删除后该素材卡将不可恢复，引用收件箱历史不会自动回滚。"
        promptLabel="请输入素材标题以确认删除"
        expectedText={String(materialDeleteDialog?.title || "")}
        value={String(materialDeleteDialog?.typedName || "")}
        placeholder={String(materialDeleteDialog?.title || "")}
        busy={!!materialDeletingId}
        error={materialDeleteError}
        inputRef={materialDeleteInputRef}
        inputClassName={materialDeleteInputShake ? "shake-once" : ""}
        confirmLabel="确认删除"
        busyLabel="删除中..."
        onValueChange={(nextValue) => {
          setMaterialDeleteDialog((prev) => (prev ? { ...prev, typedName: nextValue } : prev));
          if (materialDeleteError) setMaterialDeleteError("");
          if (materialDeleteInputShake) setMaterialDeleteInputShake(false);
        }}
        onConfirm={() => void confirmDeleteMaterialDialog()}
        onCancel={() => {
          setMaterialDeleteError("");
          setMaterialDeleteInputShake(false);
          setMaterialDeleteDialog(null);
        }}
        onMismatch={markMaterialDeleteMismatch}
      />
    </section>
  );
}
