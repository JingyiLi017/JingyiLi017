import { useState } from "react";

type Props = {
  bookId: string;
  volumeId: string;
  onPickVolumeId: (id: string) => void;
  onStatus?: (msg: string) => void;
};

export function PublishPackPanel({ bookId, volumeId, onPickVolumeId, onStatus }: Props) {
  const [packName, setPackName] = useState("publish_pack_desktop");
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function runPublishPack() {
    if (!bookId || !volumeId) return;
    setBusy(true);
    setErr("");
    try {
      const out = await window.desktopApi.exportPublishPack({
        book_id: bookId,
        volume_id: volumeId,
        pack_name: packName,
      });
      setResult(out || {});
      onStatus?.("Publish pack generated");
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function openFolder() {
    const p = String(result?.output_dir || "").trim();
    if (!p) return;
    await window.desktopApi.openPath(p, false);
  }

  const files = Array.isArray(result?.files) ? result.files : [];

  return (
    <section className="wb-panel" style={{ minHeight: "auto", marginBottom: 10 }}>
      <h3>Publish Pack</h3>
      <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
        <label>
          volume_id
          <input value={volumeId} onChange={(e) => onPickVolumeId(e.target.value)} placeholder="uuid" />
        </label>
        <label>
          pack_name
          <input value={packName} onChange={(e) => setPackName(e.target.value)} />
        </label>
        <button onClick={() => void runPublishPack()} disabled={!bookId || !volumeId || busy}>
          {busy ? "Building..." : "Build Publish Pack"}
        </button>
        <button onClick={() => void openFolder()} disabled={!String(result?.output_dir || "").trim()}>
          Open Folder
        </button>
      </div>
      {err ? <div className="hint" style={{ color: "#7f1d1d", marginTop: 8 }}>{err}</div> : null}
      {result ? (
        <div className="job-grid" style={{ marginTop: 8 }}>
          <div>
            <div className="small">output_dir</div>
            <pre>{String(result?.output_dir || "")}</pre>
          </div>
          <div>
            <div className="small">files ({files.length})</div>
            <div className="scroll" style={{ maxHeight: 160 }}>
              {files.map((f: any, idx: number) => (
                <div key={`pf_${idx}`} className="issue-item">
                  <div className="row">
                    <span className="mono">{String(f?.path || "-")}</span>
                    <code>{Number(f?.size || 0)}</code>
                  </div>
                </div>
              ))}
              {files.length === 0 ? <div className="hint">No file list in response.</div> : null}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

