import { useState } from "react";

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
    onStatus("Material created");
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
    onStatus(`Imported: ${out.created ?? 0}, embedded: ${out.embedded ?? 0}, failed: ${out.failed ?? 0}`);
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
    onStatus(`Material ref extracted: ${card.title}`);
  }

  return (
    <section className="wb-panel" style={{ minHeight: "auto", marginBottom: 10 }}>
      <h3>Material Center</h3>
      <div className="job-grid">
        <div>
          <div className="row" style={{ marginBottom: 8 }}>
            <input value={materialQ} onChange={(e) => setMaterialQ(e.target.value)} placeholder="search materials by intent..." />
            <input value={materialTag} onChange={(e) => setMaterialTag(e.target.value)} placeholder="tag(optional)" />
            <button onClick={() => void searchMaterialsKnn()} disabled={!materialQ.trim()}>
              Search (KNN)
            </button>
          </div>
          <div className="row" style={{ marginBottom: 8, flexWrap: "wrap" }}>
            <input value={sourceId} onChange={(e) => setSourceId(e.target.value)} placeholder="source_id(optional)" />
            <input type="number" min={1} max={1000} value={importLimit} onChange={(e) => setImportLimit(Number(e.target.value))} style={{ width: 120 }} />
            <button onClick={() => void importFromChunks()} disabled={!bookId}>
              Import from Chunks
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
                  <div className="small">tag={it.tag || "-"} · imp={it.importance || 3}</div>
                </div>
              </button>
            ))}
            {materialItems.length === 0 ? <div className="hint">No material results</div> : null}
          </div>
        </div>
        <div>
          <div className="row" style={{ marginBottom: 8 }}>
            <strong>Material Detail</strong>
            <div className="row">
              <button
                onClick={() => {
                  void useMaterialAsRef(materialSelected).catch((e) => onStatus(String(e)));
                }}
                disabled={!materialSelected}
              >
                Use as Ref
              </button>
            </div>
          </div>
          {materialSelected ? <pre>{materialSelected.content}</pre> : <div className="hint">Select one material card</div>}
          <hr />
          <div className="row" style={{ marginBottom: 8 }}>
            <strong>Create Material</strong>
          </div>
          <label>
            title
            <input value={materialTitle} onChange={(e) => setMaterialTitle(e.target.value)} />
          </label>
          <label>
            content
            <textarea rows={6} value={materialContent} onChange={(e) => setMaterialContent(e.target.value)} />
          </label>
          <div className="row">
            <label style={{ maxWidth: 120 }}>
              importance
              <input type="number" min={1} max={5} value={materialImportance} onChange={(e) => setMaterialImportance(Number(e.target.value))} />
            </label>
            <button onClick={() => void createMaterialCard()} disabled={!materialTitle.trim() || !materialContent.trim()}>
              Create
            </button>
          </div>
        </div>
      </div>
      <div style={{ marginTop: 10 }}>
        <div className="row" style={{ marginBottom: 6 }}>
          <strong>Ref Inbox ({materialRefs.length})</strong>
          <div className="row">
            <button onClick={onClearRefs} disabled={materialRefs.length === 0}>
              Clear Refs
            </button>
          </div>
        </div>
        <div className="scroll" style={{ maxHeight: 200 }}>
          {materialRefs.map((r, idx) => (
            <div key={idx} className="issue-item">
              <div className="row">
                <code>Ref #{idx + 1}</code>
                <button onClick={() => onRemoveRef(idx)}>Remove</button>
              </div>
              <pre>{r}</pre>
            </div>
          ))}
          {materialRefs.length === 0 ? <div className="hint">Use "Use as Ref" to add constraints for generation.</div> : null}
        </div>
      </div>
    </section>
  );
}
