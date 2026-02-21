import { useEffect, useState } from "react";

type Props = {
  baseUrl: string;
  bookId: string;
  chapterId: string;
  onStatus: (msg: string) => void;
};

export function GrowthBoardPanel({ baseUrl, bookId, chapterId, onStatus }: Props) {
  const [board, setBoard] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  async function loadBoard() {
    if (!bookId) return;
    setLoading(true);
    try {
      const q = chapterId ? `?chapter_id=${encodeURIComponent(chapterId)}` : "";
      const res = await fetch(`${baseUrl}/v1/books/${bookId}/growth/board${q}`);
      if (!res.ok) throw new Error(`GROWTH_BOARD_LOAD_FAILED:${res.status}`);
      const out = await res.json();
      setBoard(out);
    } catch (err: any) {
      onStatus(String(err?.message || err));
    } finally {
      setLoading(false);
    }
  }

  async function createDefaultMilestone() {
    if (!bookId) return;
    try {
      const body = {
        items: [
          {
            character_name: "主角",
            milestone_no: 1,
            title: "第一次为选择付出代价",
            stage: "breakthrough",
            priority: 4,
            planned_scope: "volume",
            trigger: "冲突升级到不可回避",
            cost: "失去关键线索或同伴信任",
            choice_text: "必须明确站队并承担后果",
            new_belief: "选择本身比逃避更重要",
            payoff_template_type: "cost",
            status: "planned",
          },
        ],
      };
      const res = await fetch(`${baseUrl}/v1/books/${bookId}/growth/milestones`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`GROWTH_CREATE_FAILED:${res.status}`);
      const out = await res.json();
      onStatus(`Growth milestone upserted: ${(out.items || []).length}`);
      await loadBoard();
    } catch (err: any) {
      onStatus(String(err?.message || err));
    }
  }

  async function markAction(milestoneId: string, action: "advance" | "achieve" | "reflect" | "drop") {
    try {
      const res = await fetch(`${baseUrl}/v1/growth/milestones/${milestoneId}/event`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, note: "from growth board panel" }),
      });
      if (!res.ok) throw new Error(`GROWTH_EVENT_FAILED:${res.status}`);
      onStatus(`Growth ${action}: ${String(milestoneId).slice(0, 8)}`);
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
  }, [bookId, chapterId, baseUrl]);

  const openItems = Array.isArray(board?.open) ? board.open : [];
  const dueSoon = Array.isArray(board?.due_soon) ? board.due_soon : [];
  const overdue = Array.isArray(board?.overdue) ? board.overdue : [];
  const achieved = Array.isArray(board?.achieved) ? board.achieved : [];

  return (
    <div style={{ marginTop: 10 }}>
      <div className="h2">Growth Board</div>
      <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <button onClick={() => void loadBoard()} disabled={!bookId || loading}>Refresh</button>
        <button onClick={() => void createDefaultMilestone()} disabled={!bookId}>Add Default Milestone</button>
        <div className="small mono">open={openItems.length} · due={dueSoon.length} · overdue={overdue.length} · achieved={achieved.length}</div>
      </div>

      <div className="row" style={{ gap: 10, alignItems: "stretch", marginTop: 8 }}>
        <div className="card" style={{ flex: "1 1 60%" }}>
          <div className="h2">Open Milestones</div>
          <div className="scroll" style={{ maxHeight: 220 }}>
            {openItems.length === 0 ? (
              <div className="hint">No open milestones.</div>
            ) : (
              openItems.map((x: any) => (
                <div key={String(x.milestone_id)} className="node-item" style={{ cursor: "default", marginBottom: 6 }}>
                  <div style={{ width: "100%" }}>
                    <div className="row">
                      <strong>{String(x.title || "-")}</strong>
                      <span className="chip">{String(x.stage || "-")}</span>
                      <span className="chip">{String(x.status || "-")}</span>
                    </div>
                    <div className="small mono">
                      {String(x.character_name || "主角")} · no={String(x.milestone_no || "-")} · p={String(x.priority || "-")}
                    </div>
                    <div className="small mono">
                      planned_ch={String(x.planned_chapter_no || "-")} · payoff={String(x.payoff_template_type || "-")}
                    </div>
                    <div className="small">{String(x.trigger || "")}</div>
                    <div className="row" style={{ gap: 6, marginTop: 4 }}>
                      <button onClick={() => void markAction(String(x.milestone_id), "advance")}>Advance</button>
                      <button onClick={() => void markAction(String(x.milestone_id), "achieve")}>Achieve</button>
                      <button onClick={() => void markAction(String(x.milestone_id), "reflect")}>Reflect</button>
                      <button onClick={() => void markAction(String(x.milestone_id), "drop")}>Drop</button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
        <div className="card" style={{ flex: "1 1 40%" }}>
          <div className="h2">Due / Overdue</div>
          <div className="small mono">chapter_no={String(board?.chapter_no || "-")}</div>
          <div className="scroll" style={{ maxHeight: 220, marginTop: 6 }}>
            {(dueSoon.length + overdue.length) === 0 ? (
              <div className="hint">No due/overdue milestones.</div>
            ) : (
              <>
                {dueSoon.map((x: any) => (
                  <div key={`due-${String(x.milestone_id)}`} className="node-item" style={{ cursor: "default", marginBottom: 6 }}>
                    <div className="row"><strong>{String(x.title || "-")}</strong><span className="chip">due_soon</span></div>
                  </div>
                ))}
                {overdue.map((x: any) => (
                  <div key={`over-${String(x.milestone_id)}`} className="node-item" style={{ cursor: "default", marginBottom: 6 }}>
                    <div className="row"><strong>{String(x.title || "-")}</strong><span className="chip on">overdue</span></div>
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

