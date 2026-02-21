import { useMemo } from "react";

function splitParagraphs(text: string): string[] {
  return String(text || "")
    .split(/\n\s*\n/g)
    .map((x) => x.trim())
    .filter(Boolean);
}

export function DiffViewer({ before, after }: { before: string; after: string }) {
  const rows = useMemo(() => {
    const a = splitParagraphs(before);
    const b = splitParagraphs(after);
    const n = Math.max(a.length, b.length);
    return Array.from({ length: n }).map((_, i) => ({
      before: a[i] || "",
      after: b[i] || "",
      changed: (a[i] || "") !== (b[i] || ""),
    }));
  }, [before, after]);

  return (
    <div className="job-grid">
      <div>
        <div className="small" style={{ marginBottom: 6 }}>Before</div>
        <div className="scroll" style={{ maxHeight: 320 }}>
          {rows.map((r, i) => (
            <div
              key={`bf_${i}`}
              className="issue-item"
              style={{ background: r.changed ? "rgba(245,158,11,.08)" : undefined }}
            >
              <div style={{ whiteSpace: "pre-wrap" }}>{r.before || <span className="hint">(empty)</span>}</div>
            </div>
          ))}
        </div>
      </div>
      <div>
        <div className="small" style={{ marginBottom: 6 }}>After</div>
        <div className="scroll" style={{ maxHeight: 320 }}>
          {rows.map((r, i) => (
            <div
              key={`af_${i}`}
              className="issue-item"
              style={{ background: r.changed ? "rgba(34,197,94,.08)" : undefined }}
            >
              <div style={{ whiteSpace: "pre-wrap" }}>{r.after || <span className="hint">(empty)</span>}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

