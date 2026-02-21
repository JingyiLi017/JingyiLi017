import { useMemo, useState } from "react";
import { DiffViewer } from "./DiffViewer";

type Props = {
  bookId: string;
  chapterId: string;
  onStatus?: (msg: string) => void;
};

export function RewritePanel({ bookId, chapterId, onStatus }: Props) {
  const [sourceDraftId, setSourceDraftId] = useState("");
  const [sourceText, setSourceText] = useState("");
  const [level, setLevel] = useState<"L1" | "L2" | "L3">("L2");
  const [result, setResult] = useState<any>(null);
  const [acceptResult, setAcceptResult] = useState<any>(null);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");

  const rewrittenText = useMemo(() => String(result?.rewritten_text || ""), [result]);

  async function runRewrite() {
    if (!bookId || !chapterId) return;
    setBusy("run");
    setErr("");
    setAcceptResult(null);
    try {
      const out = await window.desktopApi.rewriteRun({
        book_id: bookId,
        chapter_id: chapterId,
        source_draft_id: sourceDraftId || undefined,
        level,
        text: sourceText || undefined,
      });
      setResult(out || {});
      onStatus?.(`Rewrite ${level} completed`);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function acceptRewrite() {
    if (!result?.rewritten_text) return;
    const src = String(result?.source_draft_id || sourceDraftId || "").trim();
    if (!src) {
      setErr("source_draft_id missing");
      return;
    }
    setBusy("accept");
    setErr("");
    try {
      const out = await window.desktopApi.rewriteAccept({
        source_draft_id: src,
        rewritten_text: String(result?.rewritten_text || ""),
        level,
        rewrite_report: result?.rewrite_report || {},
        diff: result?.diff || {},
      });
      setAcceptResult(out || {});
      onStatus?.(`Rewrite accepted: ${String(out?.accepted_draft_id || "")}`);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="wb-panel" style={{ minHeight: "auto", marginBottom: 10 }}>
      <h3>Rewrite + Diff</h3>
      <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
        <label>
          source_draft_id
          <input value={sourceDraftId} onChange={(e) => setSourceDraftId(e.target.value)} placeholder="optional uuid" />
        </label>
        <label>
          level
          <select value={level} onChange={(e) => setLevel(e.target.value as any)}>
            <option value="L1">L1</option>
            <option value="L2">L2</option>
            <option value="L3">L3</option>
          </select>
        </label>
        <button onClick={() => void runRewrite()} disabled={!bookId || !chapterId || !!busy}>
          {busy === "run" ? "Running..." : "Run Rewrite"}
        </button>
        <button onClick={() => void acceptRewrite()} disabled={!rewrittenText || !!busy}>
          {busy === "accept" ? "Accepting..." : "Accept Rewrite"}
        </button>
      </div>
      <div className="small" style={{ marginTop: 6 }}>
        Tip: provide either <code>source_draft_id</code> or source text. If both are empty, server will reject.
      </div>
      <textarea
        style={{ marginTop: 8 }}
        value={sourceText}
        onChange={(e) => setSourceText(e.target.value)}
        placeholder="Optional source text override"
      />
      {err ? <div className="hint" style={{ color: "#7f1d1d", marginTop: 8 }}>{err}</div> : null}
      {result ? (
        <>
          <div className="job-grid" style={{ marginTop: 8 }}>
            <div>
              <div className="small">rewrite_report</div>
              <pre>{JSON.stringify(result?.rewrite_report || {}, null, 2)}</pre>
            </div>
            <div>
              <div className="small">accept_result</div>
              <pre>{JSON.stringify(acceptResult || {}, null, 2)}</pre>
            </div>
          </div>
          <DiffViewer before={sourceText} after={rewrittenText} />
        </>
      ) : null}
    </section>
  );
}

