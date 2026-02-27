import { useMemo, useState } from "react";

type Props = {
  bookId: string;
  volumeId: string;
  onStatus?: (msg: string) => void;
};

type QueueItem = {
  inj_id: string;
  combo_type?: string;
  window_next_chapters?: number;
  priority?: number;
  status?: string;
  expires_after_chapter_no?: number | null;
  consumed_chapter_id?: string | null;
  consumed_at?: string | null;
  created_at?: string;
  volume_id?: string | null;
};

export function ComboInjectionQueuePanel({ bookId, volumeId, onStatus }: Props) {
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [out, setOut] = useState<any>(null);
  const items = Array.isArray(out?.items) ? (out.items as QueueItem[]) : [];

  const summary = useMemo(() => {
    const s = out?.summary && typeof out.summary === "object" ? out.summary : {};
    return {
      pending: Number(s.pending || 0),
      consumed: Number(s.consumed || 0),
      expired: Number(s.expired || 0),
    };
  }, [out]);

  async function refresh() {
    if (!bookId) return;
    setBusy("refresh");
    setErr("");
    try {
      const next = await window.desktopApi.agentComboInjectionsList({
        book_id: bookId,
        volume_id: volumeId || undefined,
        status: statusFilter,
        limit: 200,
      });
      setOut(next || {});
      onStatus?.(`注入队列已加载：${Array.isArray(next?.items) ? next.items.length : 0}`);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function cleanup() {
    if (!bookId) return;
    setBusy("cleanup");
    setErr("");
    try {
      const res = await window.desktopApi.agentComboInjectionsCleanup({
        book_id: bookId,
        volume_id: volumeId || undefined,
        action: "delete_consumed_expired",
      });
      onStatus?.(`清理完成：删除 ${Number(res?.deleted || 0)} 条`);
      await refresh();
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function resetConsumed() {
    if (!bookId) return;
    setBusy("reset");
    setErr("");
    try {
      const res = await window.desktopApi.agentComboInjectionsCleanup({
        book_id: bookId,
        volume_id: volumeId || undefined,
        action: "reset_consumed_to_pending",
      });
      onStatus?.(`重置完成：更新 ${Number(res?.updated || 0)} 条`);
      await refresh();
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="wb-panel" style={{ minHeight: "auto", marginBottom: 10 }}>
      <h3>组合注入队列</h3>
      <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
        <label>
          状态
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="all">全部</option>
            <option value="pending">待处理</option>
            <option value="consumed">已消费</option>
            <option value="expired">已过期</option>
          </select>
        </label>
        <button onClick={() => void refresh()} disabled={!bookId || !!busy}>
          {busy === "refresh" ? "刷新中..." : "刷新"}
        </button>
        <button onClick={() => void cleanup()} disabled={!bookId || !!busy}>
          {busy === "cleanup" ? "清理中..." : "清理已消费+过期"}
        </button>
        <button onClick={() => void resetConsumed()} disabled={!bookId || !!busy}>
          {busy === "reset" ? "重置中..." : "已消费重置为待处理"}
        </button>
      </div>

      {err ? <div className="hint" style={{ color: "#7f1d1d", marginTop: 8 }}>{err}</div> : null}
      <div className="small" style={{ marginTop: 8 }}>
        待处理={summary.pending} | 已消费={summary.consumed} | 已过期={summary.expired}
      </div>

      <div className="scroll" style={{ marginTop: 8, maxHeight: 260 }}>
        {items.length === 0 ? <div className="hint">暂无队列项。</div> : null}
        {items.map((it) => (
          <div key={String(it.inj_id)} className="issue-item">
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <strong>{String(it.combo_type || "-")}</strong>
              <span className="badge">状态={String(it.status || "-")}</span>
              <span className="small">优先级={Number(it.priority || 0)}</span>
              <span className="small">窗口章节数={Number(it.window_next_chapters || 0)}</span>
              {it.expires_after_chapter_no != null ? (
                <span className="small">过期章={Number(it.expires_after_chapter_no)}</span>
              ) : null}
            </div>
            <div className="small" style={{ marginTop: 4 }}>
              注入ID（inj_id）={String(it.inj_id)} | 卷ID（volume_id）={String(it.volume_id || "")}
            </div>
            <div className="small">
              创建时间={String(it.created_at || "")}
              {it.consumed_at ? ` | 已消费时间（consumed_at）=${String(it.consumed_at)}` : ""}
              {it.consumed_chapter_id ? ` | 已消费章节（consumed_chapter_id）=${String(it.consumed_chapter_id)}` : ""}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
