import { useEffect, useMemo, useState } from "react";

type Change = { op: "add" | "remove" | "change"; key: string; a?: any; b?: any };

function short(v: any): string {
  if (v === null) return "null";
  if (typeof v === "string") return v.length > 60 ? v.slice(0, 60) + "…" : v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  if (Array.isArray(v)) return `[${v.slice(0, 5).map(short).join(", ")}${v.length > 5 ? ", …" : ""}]`;
  if (typeof v === "object") return "{...}";
  return String(v);
}

export function SettingsDiffPanel({
  title,
  changes,
  onOverrideBToScope,
}: {
  title: string;
  changes: Change[];
  onOverrideBToScope?: (key: string, value: any) => void;
}) {
  const [q, setQ] = useState("");
  const [onlyChanged, setOnlyChanged] = useState(true);
  const [menu, setMenu] = useState<{ x: number; y: number; row: Change } | null>(null);

  const rows = useMemo(() => {
    let r = Array.isArray(changes) ? changes : [];
    if (q.trim()) {
      const qq = q.trim().toLowerCase();
      r = r.filter((x) => x.key.toLowerCase().includes(qq));
    }
    if (onlyChanged) r = r.filter((x) => x.op !== "change" || JSON.stringify(x.a) !== JSON.stringify(x.b));
    return [...r].sort((x, y) => x.key.localeCompare(y.key));
  }, [changes, q, onlyChanged]);

  useEffect(() => {
    if (!menu) return;
    const close = () => setMenu(null);
    window.addEventListener("click", close);
    window.addEventListener("scroll", close, true);
    return () => {
      window.removeEventListener("click", close);
      window.removeEventListener("scroll", close, true);
    };
  }, [menu]);

  async function copyText(text: string) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // no-op fallback
    }
  }

  return (
    <div className="card">
      <div className="h2">{title}</div>
      <div className="row" style={{ gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div style={{ flex: 1, minWidth: 220 }}>
          <div className="label">过滤键</div>
          <input className="input" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <label className="row" style={{ gap: 8, alignItems: "center", marginBottom: 6 }}>
          <input type="checkbox" checked={onlyChanged} onChange={(e) => setOnlyChanged(e.target.checked)} />
          <span className="small">仅显示变更</span>
        </label>
      </div>

      <table className="table" style={{ width: "100%", marginTop: 10 }}>
        <thead>
          <tr>
            <th>操作</th>
            <th>键</th>
            <th>旧值</th>
            <th>新值</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={`${r.op}|${r.key}`}
              onContextMenu={(e) => {
                e.preventDefault();
                setMenu({ x: e.clientX, y: e.clientY, row: r });
              }}
            >
              <td className="mono">{r.op === "add" ? "+" : r.op === "remove" ? "-" : "~"}</td>
              <td className="mono">{r.key}</td>
              <td className="mono">{short(r.a)}</td>
              <td className="mono">{short(r.b)}</td>
              <td style={{ textAlign: "right" }}>
                {onOverrideBToScope && (r.op === "add" || r.op === "change") ? (
                  <button onClick={() => onOverrideBToScope(r.key, r.b)}>覆盖（b）</button>
                ) : null}
              </td>
            </tr>
          ))}
          {rows.length === 0 ? (
            <tr>
              <td colSpan={5} className="small">
                暂无变更。
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
      {menu ? (
        <div
          style={{
            position: "fixed",
            left: menu.x,
            top: menu.y,
            zIndex: 1000,
            background: "#fff",
            border: "1px solid #ddd",
            borderRadius: 8,
            padding: 6,
            minWidth: 180,
            boxShadow: "0 8px 18px rgba(0,0,0,0.16)",
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="small mono" style={{ marginBottom: 6 }}>{menu.row.key}</div>
          {onOverrideBToScope && (menu.row.op === "add" || menu.row.op === "change") ? (
            <button
              style={{ width: "100%", textAlign: "left" }}
              onClick={() => {
                onOverrideBToScope(menu.row.key, menu.row.b);
                setMenu(null);
              }}
            >
              在当前范围覆盖
            </button>
          ) : null}
          <button
            style={{ width: "100%", textAlign: "left", marginTop: 4 }}
            onClick={() => {
              void copyText(menu.row.key);
              setMenu(null);
            }}
          >
            复制键
          </button>
          <button
            style={{ width: "100%", textAlign: "left", marginTop: 4 }}
            onClick={() => {
              void copyText(JSON.stringify(menu.row.b ?? menu.row.a ?? null, null, 2));
              setMenu(null);
            }}
          >
            复制值
          </button>
        </div>
      ) : null}
    </div>
  );
}
