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
      onStatus?.(`改写 ${level} 已完成`);
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
      setErr("缺少 source_draft_id");
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
      onStatus?.(`改写已接纳：${String(out?.accepted_draft_id || "")}`);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="wb-panel" style={{ minHeight: "auto", marginBottom: 10 }}>
      <h3>改写与差异对比</h3>
      <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
        <label>
          源稿 ID
          <input value={sourceDraftId} onChange={(e) => setSourceDraftId(e.target.value)} placeholder="可选 UUID" />
        </label>
        <label>
          改写强度
          <select value={level} onChange={(e) => setLevel(e.target.value as any)}>
            <option value="L1">L1</option>
            <option value="L2">L2</option>
            <option value="L3">L3</option>
          </select>
        </label>
        <button onClick={() => void runRewrite()} disabled={!bookId || !chapterId || !!busy}>
          {busy === "run" ? "执行中..." : "开始改写"}
        </button>
        <button onClick={() => void acceptRewrite()} disabled={!rewrittenText || !!busy}>
          {busy === "accept" ? "接纳中..." : "接纳改写"}
        </button>
      </div>
      <div className="small" style={{ marginTop: 6 }}>
        提示：可提供 <code>source_draft_id</code> 或源文本，二者都为空时服务端会拒绝。
      </div>
      <textarea
        style={{ marginTop: 8 }}
        value={sourceText}
        onChange={(e) => setSourceText(e.target.value)}
        placeholder="可选：覆盖源文本"
      />
      {err ? <div className="hint" style={{ color: "#7f1d1d", marginTop: 8 }}>{err}</div> : null}
      {result ? (
        <>
          <div className="job-grid" style={{ marginTop: 8 }}>
            <div>
              <div className="small">改写报告</div>
              <pre>{JSON.stringify(result?.rewrite_report || {}, null, 2)}</pre>
            </div>
            <div>
              <div className="small">接纳结果</div>
              <pre>{JSON.stringify(acceptResult || {}, null, 2)}</pre>
            </div>
          </div>
          <DiffViewer before={sourceText} after={rewrittenText} />
        </>
      ) : null}
    </section>
  );
}
