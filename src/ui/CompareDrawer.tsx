type CompareDrawerProps = {
  chapterId: string;
  compareFrom: number;
  compareTo: number;
  compareDiff: any;
  evalCompare: any;
  evalBeforeRun: string;
  evalAfterRun: string;
  reportPdfPath: string;
  latestChapterReport?: any;
  onOpenProfileVersion?: (profileId: string, version: number) => void;
  onClose: () => void;
  onLoadDiff: () => Promise<void> | void;
  onLoadEvalCompare: () => Promise<void> | void;
  onExportHtml: () => Promise<void> | void;
  onExportPdf: () => Promise<void> | void;
  onOpenFolder: () => Promise<void> | void;
};

const SCORE_KEYS = ["overall", "conflict_strength", "stakes", "cost", "pace", "reversal", "hook", "payoff"];

function fmt(value: any, withSign = false) {
  const n = Number(value);
  if (Number.isNaN(n)) return "-";
  if (withSign) return `${n >= 0 ? "+" : ""}${n.toFixed(2)}`;
  return n.toFixed(2);
}

export function CompareDrawer(props: CompareDrawerProps) {
  const inserted = props.compareDiff?.changes?.inserted_nodes || [];
  const changed = props.compareDiff?.changes?.summary_changed || [];
  const stats = props.compareDiff?.stats || {};
  const mechanics = stats.mechanics || {};

  return (
    <div className="compare-drawer-overlay" onClick={props.onClose}>
      <aside className="compare-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="compare-drawer-head">
          <div>
            <strong>Compare</strong>
            <div className="small">chapter: {props.chapterId || "-"}</div>
          </div>
          <div className="row">
            <button onClick={() => void props.onLoadDiff()}>Load Diff</button>
            <button onClick={() => void props.onLoadEvalCompare()}>Load Eval</button>
            <button onClick={props.onClose}>Close</button>
          </div>
        </div>

        <div className="compare-drawer-body">
          <div className="small">version: v{props.compareFrom} → v{props.compareTo}</div>
          <div className="small">eval: {props.evalBeforeRun || "-"} → {props.evalAfterRun || "-"}</div>

          <h4>Eval Compare</h4>
          {!props.evalCompare ? (
            <div className="hint">No eval compare loaded</div>
          ) : (
            <table className="compare-table">
              <thead>
                <tr>
                  <th>dim</th>
                  <th>before</th>
                  <th>after</th>
                  <th>delta</th>
                </tr>
              </thead>
              <tbody>
                {SCORE_KEYS.map((key) => {
                  const delta = Number(props.evalCompare?.delta?.[key] ?? 0);
                  return (
                    <tr key={key}>
                      <td>{key}</td>
                      <td>{fmt(props.evalCompare?.before?.scores?.[key])}</td>
                      <td>{fmt(props.evalCompare?.after?.scores?.[key])}</td>
                      <td className={delta >= 0 ? "delta-pos" : "delta-neg"}>{fmt(delta, true)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}

          <h4>Outline Diff</h4>
          {!props.compareDiff ? (
            <div className="hint">No outline diff loaded</div>
          ) : (
            <>
              <div className="row">
                <span className="tiny-chip">insert {stats.insert_count ?? 0}</span>
                <span className="tiny-chip">change {stats.change_summary_count ?? 0}</span>
                <span className="tiny-chip">remove {stats.remove_count ?? 0}</span>
                <span className="tiny-chip">move {stats.move_count ?? 0}</span>
              </div>
              <div className="row" style={{ marginTop: 6, flexWrap: "wrap" }}>
                {Object.keys(mechanics).map((m) => (
                  <span className="tiny-chip" key={m}>
                    {m}×{mechanics[m]}
                  </span>
                ))}
              </div>
              <div style={{ marginTop: 8 }}>
                <strong>Inserted</strong>
                {inserted.length === 0 ? <div className="hint">None</div> : null}
                {inserted.map((x: any) => (
                  <div key={x.node_id} className="issue-item">
                    <div className="small">
                      <code>{x.node_id}</code> · {x.type} · {x.mechanic || "n/a"} · after <code>{x.after_node_id || "-"}</code>
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 8 }}>
                <strong>Summary Changed</strong>
                {changed.length === 0 ? <div className="hint">None</div> : null}
                {changed.map((x: any) => (
                  <div key={x.node_id} className="issue-item">
                    <div className="small"><code>{x.node_id}</code> · {x.mechanic || "n/a"}</div>
                    <div className="small">before: {x.before}</div>
                    <div className="small">after: {x.after}</div>
                  </div>
                ))}
              </div>
            </>
          )}

          <h4>Export</h4>
          <div className="row">
            <button onClick={() => void props.onExportHtml()}>Export HTML</button>
            <button onClick={() => void props.onExportPdf()}>Export PDF</button>
            {props.reportPdfPath ? <button onClick={() => void props.onOpenFolder()}>Open Folder</button> : null}
          </div>
          {props.reportPdfPath ? <div className="small"><code>{props.reportPdfPath}</code></div> : null}

          <h4>Latest Commit Profile</h4>
          {!props.latestChapterReport ? (
            <div className="hint">No chapter report loaded</div>
          ) : (
            <>
              <div className="small"><code>report_id</code>: {props.latestChapterReport.report_id || "-"}</div>
              <div className="small"><code>text_ver_id</code>: {props.latestChapterReport.text_ver_id || "-"}</div>
              <div className="small"><code>profile_id_used</code>: {props.latestChapterReport.profile_id_used || "-"}</div>
              <div className="small"><code>profile_version_used</code>: {props.latestChapterReport.profile_version_used ?? "-"}</div>
              {props.onOpenProfileVersion &&
              props.latestChapterReport.profile_id_used &&
              Number(props.latestChapterReport.profile_version_used || 0) > 0 ? (
                <div className="row" style={{ marginTop: 8 }}>
                  <button
                    onClick={() =>
                      props.onOpenProfileVersion?.(
                        String(props.latestChapterReport.profile_id_used),
                        Number(props.latestChapterReport.profile_version_used),
                      )
                    }
                  >
                    Open Profile Version
                  </button>
                </div>
              ) : null}
            </>
          )}
        </div>
      </aside>
    </div>
  );
}
