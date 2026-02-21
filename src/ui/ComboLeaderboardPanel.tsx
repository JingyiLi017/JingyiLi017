import { useEffect, useMemo, useState } from "react";

type Props = {
  baseUrl: string;
  bookId: string;
  onStatus: (msg: string) => void;
  onOpenTrace: (textVerId: string) => void;
};

type ComboRow = {
  combo_id: string;
  combo_type: string;
  policy: string;
  expected_gain?: number;
  expected_risk?: number;
  avg_delta?: number;
  uses_14d?: number;
  last_used_volume_no?: number | null;
  fingerprint?: string;
};

const comboTypeOrder = ["setup_hook_combo", "mid_spike_combo", "reveal_combo", "vol_end_combo"];

function typeLabel(t: string) {
  if (t === "setup_hook_combo") return "Setup Hook";
  if (t === "mid_spike_combo") return "Mid Spike";
  if (t === "reveal_combo") return "Reveal";
  if (t === "vol_end_combo") return "Vol End";
  return t;
}

export function ComboLeaderboardPanel({ baseUrl, bookId, onStatus, onOpenTrace }: Props) {
  const [rows, setRows] = useState<ComboRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [evidence, setEvidence] = useState<any | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedComboId, setSelectedComboId] = useState("");

  async function load() {
    if (!bookId) return;
    setLoading(true);
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/structure_combos/stats?limit=200`);
    if (!res.ok) throw new Error(`STRUCTURE_COMBO_STATS_LOAD_FAILED:${res.status}`);
    const out = await res.json();
    const items = Array.isArray(out.items) ? out.items : [];
    setRows(items as ComboRow[]);
    setLoading(false);
  }

  async function setPolicy(comboId: string, policy: "normal" | "pinned" | "banned") {
    const res = await fetch(`${baseUrl}/v1/structure_combos/${comboId}/policy`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ policy }),
    });
    if (!res.ok) throw new Error(`STRUCTURE_COMBO_POLICY_FAILED:${res.status}`);
    onStatus(`Combo policy updated: ${comboId.slice(0, 8)} -> ${policy}`);
    await load();
  }

  async function viewEvidence(comboId: string) {
    if (!bookId || !comboId) return;
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/assets/structure_combo/${comboId}/evidence?limit=3`);
    if (!res.ok) throw new Error(`STRUCTURE_COMBO_EVIDENCE_FAILED:${res.status}`);
    const out = await res.json();
    setEvidence(out);
    setSelectedComboId(comboId);
    setDrawerOpen(true);
    onStatus(`Combo evidence loaded: ${comboId.slice(0, 8)}`);
  }

  const grouped = useMemo(() => {
    const m: Record<string, ComboRow[]> = {};
    for (const r of rows) {
      const t = String(r.combo_type || "unknown");
      if (!m[t]) m[t] = [];
      m[t].push(r);
    }
    for (const t of Object.keys(m)) {
      m[t].sort((a, b) => Number(b.expected_gain || 0) - Number(a.expected_gain || 0));
    }
    return m;
  }, [rows]);

  useEffect(() => {
    if (!bookId) {
      setRows([]);
      setEvidence(null);
      setDrawerOpen(false);
      return;
    }
    void load().catch((err) => onStatus(String(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookId, baseUrl]);

  const orderedTypes = [
    ...comboTypeOrder.filter((x) => grouped[x]?.length),
    ...Object.keys(grouped).filter((x) => !comboTypeOrder.includes(x)).sort(),
  ];

  return (
    <div className="card" style={{ marginTop: 10, position: "relative", overflow: "hidden" }}>
      <div className="h2">Combo Leaderboard</div>
      <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <button onClick={() => void load()} disabled={!bookId}>Refresh</button>
        <div className="small mono">types={orderedTypes.length} · combos={rows.length} {loading ? "· loading..." : ""}</div>
      </div>

      <div className="scroll" style={{ maxHeight: 360, marginTop: 8, paddingRight: drawerOpen ? 390 : 0 }}>
        {rows.length === 0 ? <div className="hint">No combo stats.</div> : null}
        {orderedTypes.map((tp) => (
          <div key={tp} style={{ marginTop: 8 }}>
            <div className="row">
              <strong>{typeLabel(tp)}</strong>
              <span className="small mono">{tp}</span>
            </div>
            <table className="compare-table">
              <thead>
                <tr>
                  <th>combo</th>
                  <th>gain</th>
                  <th>risk</th>
                  <th>avg_delta</th>
                  <th>uses14d</th>
                  <th>policy</th>
                  <th>ops</th>
                </tr>
              </thead>
              <tbody>
                {(grouped[tp] || []).map((r) => {
                  const active = selectedComboId === String(r.combo_id || "");
                  return (
                    <tr key={String(r.combo_id || "")} style={active ? { background: "#f4f7ff" } : undefined}>
                      <td className="mono">{String(r.combo_id || "").slice(0, 8)}</td>
                      <td className="mono">{String(r.expected_gain ?? "-")}</td>
                      <td className="mono">{String(r.expected_risk ?? "-")}</td>
                      <td className="mono">{String(r.avg_delta ?? "-")}</td>
                      <td className="mono">{String(r.uses_14d ?? "-")}</td>
                      <td className="mono">{String(r.policy || "-")}</td>
                      <td>
                        <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
                          <button onClick={() => void viewEvidence(String(r.combo_id || ""))}>Evidence</button>
                          <button onClick={() => void setPolicy(String(r.combo_id || ""), "pinned")}>Pin</button>
                          <button onClick={() => void setPolicy(String(r.combo_id || ""), "banned")}>Ban</button>
                          <button onClick={() => void setPolicy(String(r.combo_id || ""), "normal")}>Normal</button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ))}
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
            <div className="h2">Combo Evidence</div>
            <button onClick={() => setDrawerOpen(false)}>Close</button>
          </div>
          {!evidence ? (
            <div className="hint">Select combo and open Evidence.</div>
          ) : (
            <>
              <div className="small mono">
                {String(evidence?.item?.item_type || "")}:{String(evidence?.item?.item_id || "").slice(0, 8)} · policy={String(evidence?.item?.policy || "-")}
              </div>
              <div className="small">title: {String(evidence?.item?.title || "-")}</div>
              <div className="small mono">fingerprint={String(evidence?.item?.fingerprint || "").slice(0, 12)}</div>
              <div className="row" style={{ gap: 6, marginTop: 8 }}>
                <button
                  onClick={() => {
                    const tv = String((evidence?.samples || [])[0]?.text_ver_id || "");
                    if (!tv) return;
                    onOpenTrace(tv);
                    onStatus(`Jumped to trace: ${tv.slice(0, 8)}`);
                  }}
                  disabled={!String((evidence?.samples || [])[0]?.text_ver_id || "")}
                >
                  Jump Latest Trace
                </button>
              </div>
              <div className="scroll" style={{ maxHeight: 220, marginTop: 6 }}>
                <table className="compare-table">
                  <thead>
                    <tr>
                      <th>delta</th>
                      <th>rank</th>
                      <th>filtered</th>
                      <th>trace</th>
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
                              onStatus(`Jumped to trace: ${String(s.text_ver_id || "").slice(0, 8)}`);
                            }}
                            disabled={!s.text_ver_id}
                          >
                            Open Trace
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="small" style={{ marginTop: 6 }}>
                diagnosis: <span className="mono">{String(evidence?.diagnosis?.recommendation || "-")}</span> ({String(evidence?.diagnosis?.confidence ?? "-")})
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

