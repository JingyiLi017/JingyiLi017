import { useEffect, useMemo, useState } from "react";

type Props = {
  baseUrl: string;
  bookId: string;
  chapterId: string;
  onStatus: (msg: string) => void;
  onOpenTrace?: (textVerId: string) => void;
};

export function ForeshadowBoardPanel({ baseUrl, bookId, chapterId, onStatus, onOpenTrace }: Props) {
  const [board, setBoard] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [lastTextVerId, setLastTextVerId] = useState("");
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [selectedKeys, setSelectedKeys] = useState<Record<string, boolean>>({});

  const chapterNo = useMemo(() => {
    const raw = board?.chapter_no ?? 0;
    const n = Number(raw);
    return Number.isFinite(n) ? n : 0;
  }, [board]);

  async function loadBoard() {
    if (!bookId) return;
    setLoading(true);
    try {
      const res = await fetch(`${baseUrl}/v1/books/${bookId}/foreshadow/board`);
      if (!res.ok) throw new Error(`FORESHADOW_BOARD_FAILED:${res.status}`);
      const out = await res.json();
      setBoard(out);
    } catch (err: any) {
      onStatus(String(err?.message || err));
    } finally {
      setLoading(false);
    }
  }

  async function autoCreateVolumes() {
    if (!bookId) return;
    try {
      const res = await fetch(`${baseUrl}/v1/books/${bookId}/volumes/auto_create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chapters_per_volume: 50 }),
      });
      if (!res.ok) throw new Error(`AUTO_CREATE_VOLUMES_FAILED:${res.status}`);
      const out = await res.json();
      onStatus(`Volumes auto-created: ${String(out.created || 0)}`);
    } catch (err: any) {
      onStatus(String(err?.message || err));
    }
  }

  async function autoPlanForChapter() {
    if (!chapterId) return;
    try {
      const body = {
        create: [
          {
            title: "未知动机暗线",
            type: "mystery",
            scope: "volume",
            priority: 4,
            question: "谁在推动当前冲突升级？",
            expected_payoff: "在卷末揭示代价与目的",
            tags: ["high_conflict", "mystery_build"],
          },
        ],
        reinforce: [],
        payoff_plan: [],
      };
      const res = await fetch(`${baseUrl}/v1/chapters/${chapterId}/foreshadow/plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`FORESHADOW_PLAN_FAILED:${res.status}`);
      const out = await res.json();
      onStatus(`Foreshadow planned: create=${(out.created || []).length}`);
      await loadBoard();
    } catch (err: any) {
      onStatus(String(err?.message || err));
    }
  }

  async function markEvent(foreshadowId: string, eventType: "payoff" | "drop" | "retcon") {
    if (!chapterId) return;
    try {
      const res = await fetch(`${baseUrl}/v1/foreshadow/${foreshadowId}/event`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chapter_id: chapterId, event_type: eventType, note: "from board panel" }),
      });
      if (!res.ok) throw new Error(`FORESHADOW_EVENT_FAILED:${res.status}`);
      onStatus(`Foreshadow ${eventType}: ${foreshadowId.slice(0, 8)}`);
      await loadBoard();
    } catch (err: any) {
      onStatus(String(err?.message || err));
    }
  }

  async function suggestEvents() {
    if (!chapterId) return;
    try {
      const body: any = {};
      if (lastTextVerId) body.text_ver_id = lastTextVerId;
      const res = await fetch(`${baseUrl}/v1/chapters/${chapterId}/foreshadow/suggest_events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`FORESHADOW_SUGGEST_FAILED:${res.status}`);
      const out = await res.json();
      const next = Array.isArray(out.suggestions) ? out.suggestions : [];
      const nextTextVerId = String(out.text_ver_id || "");
      setSuggestions(next);
      setLastTextVerId(nextTextVerId);
      const checked: Record<string, boolean> = {};
      for (const s of next) {
        const key = `${String(s.foreshadow_id || "")}:${String(s.event_type || "")}`;
        if (key !== ":") checked[key] = true;
      }
      setSelectedKeys(checked);
      onStatus(`Foreshadow suggestions: ${next.length}`);
    } catch (err: any) {
      onStatus(String(err?.message || err));
    }
  }

  async function confirmSelected() {
    if (!chapterId) return;
    const picked = suggestions.filter((s) => selectedKeys[`${String(s.foreshadow_id || "")}:${String(s.event_type || "")}`]);
    if (picked.length === 0) {
      onStatus("No foreshadow suggestion selected");
      return;
    }
    try {
      const body = {
        text_ver_id: lastTextVerId || null,
        events: picked.map((s: any) => ({
          foreshadow_id: s.foreshadow_id,
          event_type: s.event_type,
          intensity: s.intensity ?? 1,
          note: s.note || "confirmed from board panel",
        })),
      };
      const res = await fetch(`${baseUrl}/v1/chapters/${chapterId}/foreshadow/confirm_events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`FORESHADOW_CONFIRM_FAILED:${res.status}`);
      const out = await res.json();
      const applied = Array.isArray(out.applied) ? out.applied.length : 0;
      onStatus(`Foreshadow confirmed: ${applied}`);
      await loadBoard();
    } catch (err: any) {
      onStatus(String(err?.message || err));
    }
  }

  useEffect(() => {
    if (!bookId) {
      setBoard(null);
      return;
    }
    void loadBoard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookId, baseUrl]);

  const openItems = Array.isArray(board?.open) ? board.open : [];
  const dueSoon = Array.isArray(board?.due_soon) ? board.due_soon : [];
  const overdue = Array.isArray(board?.overdue) ? board.overdue : [];
  const closed = Array.isArray(board?.closed) ? board.closed : [];

  return (
    <div style={{ marginTop: 10 }}>
      <div className="h2">Foreshadow Board</div>
      <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <button onClick={() => void loadBoard()} disabled={!bookId || loading}>Refresh</button>
        <button onClick={() => void autoCreateVolumes()} disabled={!bookId}>Auto Create Volumes</button>
        <button onClick={() => void autoPlanForChapter()} disabled={!chapterId}>Auto Plan For Chapter</button>
        <button onClick={() => void suggestEvents()} disabled={!chapterId}>Suggest Events</button>
        <button onClick={() => void confirmSelected()} disabled={!chapterId || suggestions.length === 0}>Confirm Selected</button>
        <button onClick={() => onOpenTrace?.(lastTextVerId)} disabled={!lastTextVerId || !onOpenTrace}>Open Last Trace</button>
        <div className="small mono">open={openItems.length} · due={dueSoon.length} · overdue={overdue.length} · closed={closed.length}</div>
      </div>

      {suggestions.length > 0 ? (
        <div className="card" style={{ marginTop: 8 }}>
          <div className="h2">Suggested Events</div>
          <div className="small mono">text_ver_id={lastTextVerId ? String(lastTextVerId).slice(0, 8) : "-"}</div>
          <div className="scroll" style={{ maxHeight: 160, marginTop: 6 }}>
            <table className="compare-table">
              <thead>
                <tr>
                  <th></th>
                  <th>title</th>
                  <th>event</th>
                  <th>status</th>
                  <th>source</th>
                </tr>
              </thead>
              <tbody>
                {suggestions.map((s: any, idx: number) => {
                  const key = `${String(s.foreshadow_id || "")}:${String(s.event_type || "")}`;
                  return (
                    <tr key={`${key}-${idx}`}>
                      <td>
                        <input
                          type="checkbox"
                          checked={Boolean(selectedKeys[key])}
                          onChange={(e) => setSelectedKeys({ ...selectedKeys, [key]: e.target.checked })}
                        />
                      </td>
                      <td>{String(s.title || "").slice(0, 28) || String(s.foreshadow_id || "").slice(0, 8)}</td>
                      <td className="mono">{String(s.event_type || "-")}</td>
                      <td className="mono">{String(s.current_status || "-")}</td>
                      <td className="mono">{String(s.source || "-")}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      <div className="row" style={{ gap: 10, alignItems: "stretch", marginTop: 8 }}>
        <div className="card" style={{ flex: "1 1 45%" }}>
          <div className="h2">Open</div>
          <div className="scroll" style={{ maxHeight: 220 }}>
            {openItems.length === 0 ? (
              <div className="hint">No open foreshadow.</div>
            ) : (
              openItems.map((x: any) => (
                <div key={String(x.foreshadow_id)} className="node-item" style={{ cursor: "default", marginBottom: 6 }}>
                  <div style={{ width: "100%" }}>
                    <div className="row">
                      <strong>{String(x.title || "-")}</strong>
                      <span className="chip">{String(x.status || "-")}</span>
                    </div>
                    <div className="small mono">
                      {String(x.foreshadow_id || "").slice(0, 8)} · scope={String(x.scope || "-")} · p={String(x.priority ?? "-")}
                    </div>
                    <div className="small mono">planned_payoff_ch={String(x.planned_payoff_chapter_no || "-")}</div>
                    <div className="row" style={{ gap: 6, marginTop: 4 }}>
                      <button onClick={() => void markEvent(String(x.foreshadow_id), "payoff")} disabled={!chapterId}>Mark Payoff</button>
                      <button onClick={() => void markEvent(String(x.foreshadow_id), "retcon")} disabled={!chapterId}>Retcon</button>
                      <button onClick={() => void markEvent(String(x.foreshadow_id), "drop")} disabled={!chapterId}>Drop</button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="card" style={{ flex: "1 1 55%" }}>
          <div className="h2">Due / Overdue</div>
          <div className="small mono">chapter_no={chapterNo || "-"}</div>
          <div className="scroll" style={{ maxHeight: 220, marginTop: 6 }}>
            {(dueSoon.length + overdue.length) === 0 ? (
              <div className="hint">No due/overdue items.</div>
            ) : (
              <>
                {dueSoon.map((x: any) => (
                  <div key={`due-${String(x.foreshadow_id)}`} className="node-item" style={{ cursor: "default", marginBottom: 6 }}>
                    <div style={{ width: "100%" }}>
                      <div className="row"><strong>{String(x.title || "-")}</strong><span className="chip">due_soon</span></div>
                      <div className="small mono">payoff_ch={String(x.planned_payoff_chapter_no || "-")}</div>
                    </div>
                  </div>
                ))}
                {overdue.map((x: any) => (
                  <div key={`over-${String(x.foreshadow_id)}`} className="node-item" style={{ cursor: "default", marginBottom: 6 }}>
                    <div style={{ width: "100%" }}>
                      <div className="row"><strong>{String(x.title || "-")}</strong><span className="chip on">overdue</span></div>
                      <div className="small mono">payoff_ch={String(x.planned_payoff_chapter_no || "-")}</div>
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
