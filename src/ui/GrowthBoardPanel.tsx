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
  const actionLabels: Record<string, string> = {
    advance: "推进",
    achieve: "达成",
    reflect: "反思",
    drop: "放弃",
  };
  const formatAction = (value: string) => {
    const hit = actionLabels[value];
    return hit ? `${hit}(${value})` : value;
  };

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
      onStatus(`成长里程碑已更新：${(out.items || []).length} 条`);
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
      onStatus(`成长${formatAction(action)}：${String(milestoneId).slice(0, 8)}`);
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
      <div className="h2">成长看板</div>
      <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <button onClick={() => void loadBoard()} disabled={!bookId || loading}>刷新</button>
        <button onClick={() => void createDefaultMilestone()} disabled={!bookId}>添加默认里程碑</button>
        <div className="small mono">开放={openItems.length} · 即将到期={dueSoon.length} · 已逾期={overdue.length} · 已达成={achieved.length}</div>
      </div>

      <div className="row" style={{ gap: 10, alignItems: "stretch", marginTop: 8 }}>
        <div className="card" style={{ flex: "1 1 60%" }}>
          <div className="h2">开放里程碑</div>
          <div className="scroll" style={{ maxHeight: 220 }}>
            {openItems.length === 0 ? (
              <div className="hint">暂无开放里程碑。</div>
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
                      {String(x.character_name || "主角")} · 序号(no)={String(x.milestone_no || "-")} · 优先级(p)={String(x.priority || "-")}
                    </div>
                    <div className="small mono">
                      计划章节(planned_ch)={String(x.planned_chapter_no || "-")} · 回收模板(payoff)={String(x.payoff_template_type || "-")}
                    </div>
                    <div className="small">{String(x.trigger || "")}</div>
                    <div className="row" style={{ gap: 6, marginTop: 4 }}>
                      <button onClick={() => void markAction(String(x.milestone_id), "advance")}>推进</button>
                      <button onClick={() => void markAction(String(x.milestone_id), "achieve")}>达成</button>
                      <button onClick={() => void markAction(String(x.milestone_id), "reflect")}>反思</button>
                      <button onClick={() => void markAction(String(x.milestone_id), "drop")}>放弃</button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
        <div className="card" style={{ flex: "1 1 40%" }}>
          <div className="h2">即将到期 / 已逾期</div>
          <div className="small mono">章节号(chapter_no)={String(board?.chapter_no || "-")}</div>
          <div className="scroll" style={{ maxHeight: 220, marginTop: 6 }}>
            {(dueSoon.length + overdue.length) === 0 ? (
              <div className="hint">暂无即将到期或已逾期里程碑。</div>
            ) : (
              <>
                {dueSoon.map((x: any) => (
                  <div key={`due-${String(x.milestone_id)}`} className="node-item" style={{ cursor: "default", marginBottom: 6 }}>
                    <div className="row"><strong>{String(x.title || "-")}</strong><span className="chip">即将到期(due_soon)</span></div>
                  </div>
                ))}
                {overdue.map((x: any) => (
                  <div key={`over-${String(x.milestone_id)}`} className="node-item" style={{ cursor: "default", marginBottom: 6 }}>
                    <div className="row"><strong>{String(x.title || "-")}</strong><span className="chip on">已逾期(overdue)</span></div>
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
