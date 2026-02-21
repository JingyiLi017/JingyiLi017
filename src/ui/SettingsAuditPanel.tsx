type AuditItem = {
  audit_id: string;
  action: string;
  scope: string;
  scope_id?: string | null;
  note?: string;
  created_at?: string;
  before_settings?: any;
  after_settings?: any;
};

export function SettingsAuditPanel({
  items,
  loading,
  onRefresh,
  onPreviewRollback,
  onRollback,
}: {
  items: AuditItem[];
  loading?: boolean;
  onRefresh?: () => void;
  onPreviewRollback?: (item: AuditItem) => void;
  onRollback?: (auditId: string) => void;
}) {
  return (
    <div className="card" style={{ marginTop: 10 }}>
      <div className="h2">Settings Audit</div>
      <div className="row" style={{ gap: 8 }}>
        <button onClick={() => onRefresh?.()}>{loading ? "Loading..." : "Refresh"}</button>
      </div>
      <div className="scroll" style={{ maxHeight: 220, marginTop: 10 }}>
        {items.length === 0 ? <div className="hint">No records.</div> : null}
        {items.map((it) => (
          <div key={it.audit_id} className="node-item" style={{ cursor: "default" }}>
            <div style={{ width: "100%" }}>
              <div className="row">
                <strong>{it.action}</strong>
                <span className="small">{it.created_at ? new Date(it.created_at).toLocaleString() : ""}</span>
              </div>
              <div className="small mono">
                {it.scope}
                {it.scope_id ? `:${it.scope_id}` : ""} · {it.audit_id}
              </div>
              {it.note ? <div className="small">{it.note}</div> : null}
              {it.action === "preset_apply" ? (
                <div className="row" style={{ marginTop: 6 }}>
                  <button onClick={() => onPreviewRollback?.(it)}>Preview</button>
                  <button onClick={() => onRollback?.(it.audit_id)}>Rollback</button>
                </div>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
