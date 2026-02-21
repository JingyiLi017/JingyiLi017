import { useEffect, useMemo, useState } from "react";

type Props = {
  baseUrl: string;
  onStatus: (msg: string) => void;
};

const TYPES = ["reversal", "cost", "misinterpretation", "emotional", "parallel"];

function emptyDraft() {
  return {
    template_id: "",
    type: "reversal",
    applicable_foreshadow_type: "mystery,secret",
    structure_pattern: "",
    rewrite_instruction: "",
    intensity_level: 2,
    risk_score: "",
  };
}

export function PayoffTemplatePanel({ baseUrl, onStatus }: Props) {
  const [items, setItems] = useState<any[]>([]);
  const [statsMap, setStatsMap] = useState<Record<string, { hits: number; avg_delta: number; impact: number }>>({});
  const [filterType, setFilterType] = useState("");
  const [sortBy, setSortBy] = useState<"hits_desc" | "gain_desc" | "impact_desc">("impact_desc");
  const [draft, setDraft] = useState<any>(emptyDraft());
  const [loading, setLoading] = useState(false);

  const filtered = useMemo(() => {
    let arr = !filterType ? [...items] : items.filter((x) => String(x.type || "") === filterType);
    arr.sort((a, b) => {
      const aId = String(a?.template_id || "");
      const bId = String(b?.template_id || "");
      const sa = statsMap[aId] || { hits: 0, avg_delta: 0, impact: 0 };
      const sb = statsMap[bId] || { hits: 0, avg_delta: 0, impact: 0 };
      if (sortBy === "hits_desc") {
        if (sb.hits !== sa.hits) return sb.hits - sa.hits;
      } else if (sortBy === "gain_desc") {
        if (sb.avg_delta !== sa.avg_delta) return sb.avg_delta - sa.avg_delta;
      } else {
        if (sb.impact !== sa.impact) return sb.impact - sa.impact;
      }
      return String(a?.type || "").localeCompare(String(b?.type || "")) || aId.localeCompare(bId);
    });
    return arr;
  }, [items, filterType, statsMap, sortBy]);

  async function load() {
    setLoading(true);
    try {
      const q = filterType ? `?ftype=${encodeURIComponent(filterType)}` : "";
      const res = await fetch(`${baseUrl}/v1/payoff_templates${q}`);
      if (!res.ok) throw new Error(`PAYOFF_TEMPLATES_LOAD_FAILED:${res.status}`);
      const out = await res.json();
      setItems(Array.isArray(out.items) ? out.items : []);
      const sres = await fetch(`${baseUrl}/v1/payoff_templates/stats?days=30&limit=500`);
      if (sres.ok) {
        const sout = await sres.json();
        const sm: Record<string, { hits: number; avg_delta: number; impact: number }> = {};
        for (const it of (sout.items || [])) {
          const id = String(it?.template_id || "");
          if (!id) continue;
          sm[id] = {
            hits: Number(it?.hits || 0),
            avg_delta: Number(it?.avg_delta || 0),
            impact: Number(it?.impact || 0),
          };
        }
        setStatsMap(sm);
      }
    } catch (err: any) {
      onStatus(String(err?.message || err));
    } finally {
      setLoading(false);
    }
  }

  function selectEdit(it: any) {
    setDraft({
      template_id: String(it.template_id || ""),
      type: String(it.type || "reversal"),
      applicable_foreshadow_type: Array.isArray(it.applicable_foreshadow_type) ? it.applicable_foreshadow_type.join(",") : "",
      structure_pattern: String(it.structure_pattern || ""),
      rewrite_instruction: String(it.rewrite_instruction || ""),
      intensity_level: Number(it.intensity_level || 2),
      risk_score: it.risk_score == null ? "" : String(it.risk_score),
    });
  }

  async function save() {
    try {
      const payload: any = {
        template_id: String(draft.template_id || "").trim() || undefined,
        type: String(draft.type || "").trim(),
        applicable_foreshadow_type: String(draft.applicable_foreshadow_type || "")
          .split(",")
          .map((x) => x.trim().toLowerCase())
          .filter(Boolean),
        structure_pattern: String(draft.structure_pattern || "").trim(),
        rewrite_instruction: String(draft.rewrite_instruction || "").trim(),
        intensity_level: Math.max(1, Math.min(3, Number(draft.intensity_level || 2))),
      };
      const rs = String(draft.risk_score || "").trim();
      if (rs) payload.risk_score = Number(rs);
      const res = await fetch(`${baseUrl}/v1/payoff_templates`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`PAYOFF_TEMPLATE_SAVE_FAILED:${res.status}`);
      const out = await res.json();
      onStatus(`Payoff template ${String(out.mode || "saved")}: ${String(out?.item?.template_id || "").slice(0, 8)}`);
      setDraft(emptyDraft());
      await load();
    } catch (err: any) {
      onStatus(String(err?.message || err));
    }
  }

  async function remove(templateId: string) {
    try {
      const res = await fetch(`${baseUrl}/v1/payoff_templates/${templateId}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`PAYOFF_TEMPLATE_DELETE_FAILED:${res.status}`);
      onStatus(`Payoff template deleted: ${templateId.slice(0, 8)}`);
      if (String(draft.template_id || "") === templateId) {
        setDraft(emptyDraft());
      }
      await load();
    } catch (err: any) {
      onStatus(String(err?.message || err));
    }
  }

  function cloneAsNew(it: any) {
    setDraft({
      template_id: "",
      type: String(it.type || "reversal"),
      applicable_foreshadow_type: Array.isArray(it.applicable_foreshadow_type) ? it.applicable_foreshadow_type.join(",") : "",
      structure_pattern: String(it.structure_pattern || ""),
      rewrite_instruction: String(it.rewrite_instruction || ""),
      intensity_level: Number(it.intensity_level || 2),
      risk_score: it.risk_score == null ? "" : String(it.risk_score),
    });
    onStatus(`Template cloned to editor: ${String(it.template_id || "").slice(0, 8)}`);
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseUrl, filterType]);

  return (
    <div style={{ marginTop: 10 }}>
      <div className="h2">Payoff Templates</div>
      <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <button onClick={() => void load()} disabled={loading}>{loading ? "Loading..." : "Refresh"}</button>
        <label>
          Type
          <select value={filterType} onChange={(e) => setFilterType(e.target.value)}>
            <option value="">(all)</option>
            {TYPES.map((x) => (
              <option key={x} value={x}>{x}</option>
            ))}
          </select>
        </label>
        <label>
          Sort
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value as any)}>
            <option value="impact_desc">impact(desc)</option>
            <option value="gain_desc">gain(desc)</option>
            <option value="hits_desc">hits(desc)</option>
          </select>
        </label>
        <div className="small mono">count={filtered.length}</div>
      </div>

      <div className="row" style={{ gap: 10, alignItems: "stretch", marginTop: 8 }}>
        <div className="card" style={{ flex: "1 1 55%" }}>
          <div className="h2">Library</div>
          <div className="scroll" style={{ maxHeight: 240 }}>
            {filtered.length === 0 ? (
              <div className="hint">No templates.</div>
            ) : (
              filtered.map((it) => (
                <div key={String(it.template_id)} className="node-item" style={{ cursor: "default", marginBottom: 6 }}>
                  {(() => {
                    const s = statsMap[String(it.template_id || "")] || { hits: 0, avg_delta: 0, impact: 0 };
                    return (
                  <div style={{ width: "100%" }}>
                    <div className="row">
                      <strong>{String(it.type || "-")}</strong>
                      <span className="chip">L{String(it.intensity_level || "-")}</span>
                      <span className="chip">hits30d:{String(s.hits)}</span>
                      <span className="chip">gain:{s.avg_delta.toFixed(3)}</span>
                      <span className="chip">impact:{s.impact.toFixed(3)}</span>
                    </div>
                    <div className="small mono">{String(it.template_id || "").slice(0, 8)} · foreshadow={JSON.stringify(it.applicable_foreshadow_type || [])}</div>
                    <div className="small">{String(it.structure_pattern || "").slice(0, 140)}</div>
                    <div className="row" style={{ gap: 6, marginTop: 4 }}>
                      <button onClick={() => selectEdit(it)}>Edit</button>
                      <button onClick={() => cloneAsNew(it)}>Clone</button>
                      <button onClick={() => void remove(String(it.template_id))}>Delete</button>
                    </div>
                  </div>
                    );
                  })()}
                </div>
              ))
            )}
          </div>
        </div>

        <div className="card" style={{ flex: "1 1 45%" }}>
          <div className="h2">{draft.template_id ? "Edit Template" : "Create Template"}</div>
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <label>
              Type
              <select value={draft.type} onChange={(e) => setDraft({ ...draft, type: e.target.value })}>
                {TYPES.map((x) => (
                  <option key={x} value={x}>{x}</option>
                ))}
              </select>
            </label>
            <label>
              Intensity
              <input
                value={String(draft.intensity_level)}
                onChange={(e) => setDraft({ ...draft, intensity_level: Math.max(1, Math.min(3, Number(e.target.value || 2))) })}
              />
            </label>
            <label>
              Risk
              <input value={String(draft.risk_score)} onChange={(e) => setDraft({ ...draft, risk_score: e.target.value })} placeholder="optional" />
            </label>
          </div>
          <label>
            Applicable Foreshadow Types (comma)
            <input
              value={String(draft.applicable_foreshadow_type)}
              onChange={(e) => setDraft({ ...draft, applicable_foreshadow_type: e.target.value })}
              placeholder="mystery,secret,relationship"
            />
          </label>
          <label>
            Structure Pattern
            <textarea
              value={String(draft.structure_pattern)}
              onChange={(e) => setDraft({ ...draft, structure_pattern: e.target.value })}
              rows={4}
            />
          </label>
          <label>
            Rewrite Instruction
            <textarea
              value={String(draft.rewrite_instruction)}
              onChange={(e) => setDraft({ ...draft, rewrite_instruction: e.target.value })}
              rows={4}
            />
          </label>
          <div className="row" style={{ gap: 6, marginTop: 6 }}>
            <button onClick={() => void save()}>Save</button>
            <button onClick={() => setDraft(emptyDraft())}>Reset</button>
          </div>
        </div>
      </div>
    </div>
  );
}
