import { useEffect, useState } from "react";

type Props = {
  baseUrl: string;
  bookId: string;
  onStatus: (msg: string) => void;
  onOpenTrace: (textVerId: string) => void;
};

export function PolicySuggestionsPanel({ baseUrl, bookId, onStatus, onOpenTrace }: Props) {
  const [proposals, setProposals] = useState<any[]>([]);
  const [scope, setScope] = useState<"pending" | "accepted" | "rejected">("pending");
  const [evidence, setEvidence] = useState<any | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedProposalId, setSelectedProposalId] = useState("");
  const scopeLabels: Record<string, string> = {
    pending: "待处理(pending)",
    accepted: "已接受(accepted)",
    rejected: "已拒绝(rejected)",
  };
  const formatScope = (value: string) => scopeLabels[value] || value;

  async function load(nextScope: "pending" | "accepted" | "rejected" = scope) {
    if (!bookId) return;
    setLoading(true);
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/asset_policy_proposals?status=${nextScope}&sort=impact`);
    if (!res.ok) throw new Error(`ASSET_PROPOSALS_LOAD_FAILED:${res.status}`);
    const out = await res.json();
    setProposals(Array.isArray(out.items) ? out.items : []);
    setScope(nextScope);
    setLoading(false);
  }

  async function generate() {
    if (!bookId) return;
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/asset_policy_proposals/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!res.ok) throw new Error(`ASSET_PROPOSALS_GENERATE_FAILED:${res.status}`);
    const out = await res.json();
    onStatus(`策略建议已生成：${String(out.created ?? 0)}`);
    await load("pending");
  }

  async function accept(proposalId: string) {
    const res = await fetch(`${baseUrl}/v1/asset_policy_proposals/${proposalId}/accept`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: "accepted from desktop queue" }),
    });
    if (!res.ok) throw new Error(`ASSET_PROPOSAL_ACCEPT_FAILED:${res.status}`);
    onStatus(`已接受建议：${proposalId.slice(0, 8)}`);
    await load("pending");
  }

  async function reject(proposalId: string) {
    const res = await fetch(`${baseUrl}/v1/asset_policy_proposals/${proposalId}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: "rejected from desktop queue" }),
    });
    if (!res.ok) throw new Error(`ASSET_PROPOSAL_REJECT_FAILED:${res.status}`);
    onStatus(`已拒绝建议：${proposalId.slice(0, 8)}`);
    await load("pending");
  }

  async function viewEvidence(itemType: string, itemId: string) {
    if (!bookId || !itemType || !itemId) return;
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/assets/${itemType}/${itemId}/evidence?limit=3`);
    if (!res.ok) throw new Error(`ASSET_EVIDENCE_LOAD_FAILED:${res.status}`);
    const out = await res.json();
    setEvidence(out);
    setDrawerOpen(true);
    onStatus(`已加载证据：${String(itemId).slice(0, 8)}`);
  }

  async function learnTags(itemType: string, itemId: string) {
    if (!bookId || !itemType || !itemId) return;
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/assets/${itemType}/${itemId}/learn_tags`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ limit: 30, min_samples: 3 }),
    });
    if (!res.ok) throw new Error(`ASSET_TAG_LEARN_FAILED:${res.status}`);
    const out = await res.json();
    onStatus(`标签学习完成：好标签=${(out.good_tags || []).length}，坏标签=${(out.bad_tags || []).length}`);
    await viewEvidence(itemType, itemId);
  }

  useEffect(() => {
    if (!bookId) {
      setProposals([]);
      setEvidence(null);
      setDrawerOpen(false);
      return;
    }
    void load("pending").catch((err) => onStatus(String(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookId, baseUrl]);

  return (
    <div className="card" style={{ marginTop: 10, position: "relative", overflow: "hidden" }}>
      <div className="h2">策略建议侧栏</div>
      <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <button onClick={() => void generate()} disabled={!bookId}>生成建议</button>
        <button onClick={() => void load("pending")} disabled={!bookId}>待处理</button>
        <button onClick={() => void load("accepted")} disabled={!bookId}>已接受</button>
        <button onClick={() => void load("rejected")} disabled={!bookId}>已拒绝</button>
        <div className="small mono">范围(scope)={formatScope(scope)} · 数量={proposals.length} {loading ? "· 加载中..." : ""}</div>
      </div>
      <div className="scroll" style={{ maxHeight: 300, marginTop: 8, paddingRight: drawerOpen ? 390 : 0 }}>
        {proposals.length === 0 ? (
          <div className="hint">暂无建议。</div>
        ) : (
          <table className="compare-table">
            <thead>
              <tr>
                <th>策略</th>
                <th>对象</th>
                <th>预期增益</th>
                <th>预期风险</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {proposals.map((p: any) => {
                const ev = p?.evidence || {};
                const active = selectedProposalId === String(p.proposal_id || "");
                return (
                  <tr key={String(p.proposal_id || "")} style={active ? { background: "#f4f7ff" } : undefined}>
                    <td className="mono">{String(p.proposed_policy || "-")}</td>
                    <td className="mono">{String(p.item_type || "")}:{String(p.item_id || "").slice(0, 8)}</td>
                    <td className="mono">{String(ev.expected_gain ?? "-")}</td>
                    <td className="mono">{String(ev.expected_risk ?? "-")}</td>
                    <td>
                      <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
                        <button
                          onClick={() => {
                            setSelectedProposalId(String(p.proposal_id || ""));
                            void viewEvidence(String(p.item_type || ""), String(p.item_id || ""));
                          }}
                        >
                          查看证据
                        </button>
                        <button onClick={() => void learnTags(String(p.item_type || ""), String(p.item_id || ""))}>学习标签</button>
                        {String(p.status || "") === "pending" ? (
                          <>
                            <button onClick={() => void accept(String(p.proposal_id || ""))}>接受</button>
                            <button onClick={() => void reject(String(p.proposal_id || ""))}>拒绝</button>
                          </>
                        ) : (
                          <span className="small mono">{formatScope(String(p.status || "-"))}</span>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
      {drawerOpen ? (
        <div
          className="card"
          style={{
            position: "absolute",
            right: 0,
            top: 0,
            bottom: 0,
            width: 380,
            borderLeft: "1px solid #ddd",
            borderRadius: 0,
            overflow: "auto",
            background: "#fff",
            zIndex: 2,
          }}
        >
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
            <div className="h2">证据抽屉</div>
            <button onClick={() => setDrawerOpen(false)}>关闭</button>
          </div>
          {!evidence ? (
            <div className="hint">请选择建议并点击“查看证据”。</div>
          ) : (
            <>
              <div className="small mono">
                {String(evidence?.item?.item_type || "")}:{String(evidence?.item?.item_id || "").slice(0, 8)} · 策略(policy)={String(evidence?.item?.policy || "-")}
              </div>
              <div className="small">标题：{String(evidence?.item?.title || "-")}</div>
              <div className="small">好标签：<span className="mono">{JSON.stringify(evidence?.item?.good_tags || [])}</span></div>
              <div className="small">坏标签：<span className="mono">{JSON.stringify(evidence?.item?.bad_tags || [])}</span></div>
              <div className="row" style={{ gap: 6, marginTop: 8 }}>
                <button
                  onClick={() => {
                    const tv = String((evidence?.samples || [])[0]?.text_ver_id || "");
                    if (!tv) return;
                    onOpenTrace(tv);
                    onStatus(`已跳转追踪：${tv.slice(0, 8)}`);
                  }}
                  disabled={!String((evidence?.samples || [])[0]?.text_ver_id || "")}
                >
                  跳转最近追踪
                </button>
              </div>
              <div className="scroll" style={{ maxHeight: 220, marginTop: 6 }}>
                <table className="compare-table">
                  <thead>
                    <tr>
                      <th>变化量</th>
                      <th>排序</th>
                      <th>过滤原因</th>
                      <th>追踪</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(evidence?.samples || []).map((s: any, idx: number) => (
                      <tr key={`${String(s.text_ver_id || "")}-${idx}`}>
                        <td className="mono">{String(s.delta ?? "-")}</td>
                        <td className="mono">{String(s.rank ?? "-")}</td>
                        <td className="mono">{String(s.filtered_reason || "-")}</td>
                        <td>
                          <button
                            onClick={() => {
                              onOpenTrace(String(s.text_ver_id || ""));
                              onStatus(`已跳转追踪：${String(s.text_ver_id || "").slice(0, 8)}`);
                            }}
                            disabled={!s.text_ver_id}
                          >
                            打开追踪
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="small" style={{ marginTop: 6 }}>
                诊断：<span className="mono">{String(evidence?.diagnosis?.recommendation || "-")}</span> ({String(evidence?.diagnosis?.confidence ?? "-")})
              </div>
              <pre style={{ maxHeight: 160, overflow: "auto", marginTop: 6 }}>
                {JSON.stringify(evidence?.diagnosis?.signals || [], null, 2)}
              </pre>
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}
