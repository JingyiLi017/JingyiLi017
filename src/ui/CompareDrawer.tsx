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
            <strong>对比</strong>
            <div className="small">章节：{props.chapterId || "-"}</div>
          </div>
          <div className="row">
            <button onClick={() => void props.onLoadDiff()}>加载差异</button>
            <button onClick={() => void props.onLoadEvalCompare()}>加载评估</button>
            <button onClick={props.onClose}>关闭</button>
          </div>
        </div>

        <div className="compare-drawer-body">
          <div className="small">版本：v{props.compareFrom} → v{props.compareTo}</div>
          <div className="small">评估：{props.evalBeforeRun || "-"} → {props.evalAfterRun || "-"}</div>

          <h4>评估对比</h4>
          {!props.evalCompare ? (
            <div className="hint">暂无评估对比。</div>
          ) : (
            <table className="compare-table">
              <thead>
                <tr>
                  <th>维度</th>
                  <th>之前</th>
                  <th>之后</th>
                  <th>差值</th>
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

          <h4>大纲差异</h4>
          {!props.compareDiff ? (
            <div className="hint">暂无大纲差异。</div>
          ) : (
            <>
              <div className="row">
                <span className="tiny-chip">新增 {stats.insert_count ?? 0}</span>
                <span className="tiny-chip">变更 {stats.change_summary_count ?? 0}</span>
                <span className="tiny-chip">删除 {stats.remove_count ?? 0}</span>
                <span className="tiny-chip">移动 {stats.move_count ?? 0}</span>
              </div>
              <div className="row" style={{ marginTop: 6, flexWrap: "wrap" }}>
                {Object.keys(mechanics).map((m) => (
                  <span className="tiny-chip" key={m}>
                    {m}×{mechanics[m]}
                  </span>
                ))}
              </div>
              <div style={{ marginTop: 8 }}>
                <strong>新增节点</strong>
                {inserted.length === 0 ? <div className="hint">无</div> : null}
                {inserted.map((x: any) => (
                  <div key={x.node_id} className="issue-item">
                    <div className="small">
                      <code>{x.node_id}</code> · {x.type} · {x.mechanic || "无(n/a)"} · 位于 <code>{x.after_node_id || "-"}</code> 之后
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 8 }}>
                <strong>摘要变更</strong>
                {changed.length === 0 ? <div className="hint">无</div> : null}
                {changed.map((x: any) => (
                  <div key={x.node_id} className="issue-item">
                    <div className="small"><code>{x.node_id}</code> · {x.mechanic || "无(n/a)"}</div>
                    <div className="small">之前：{x.before}</div>
                    <div className="small">之后：{x.after}</div>
                  </div>
                ))}
              </div>
            </>
          )}

          <h4>导出</h4>
          <div className="row">
            <button onClick={() => void props.onExportHtml()}>导出 HTML</button>
            <button onClick={() => void props.onExportPdf()}>导出 PDF</button>
            {props.reportPdfPath ? <button onClick={() => void props.onOpenFolder()}>打开目录</button> : null}
          </div>
          {props.reportPdfPath ? <div className="small"><code>{props.reportPdfPath}</code></div> : null}

          <h4>最新提交画像</h4>
          {!props.latestChapterReport ? (
            <div className="hint">暂无章节报告。</div>
          ) : (
            <>
              <div className="small">报告ID（report_id）：<code>{props.latestChapterReport.report_id || "-"}</code></div>
              <div className="small">文本版本ID（text_ver_id）：<code>{props.latestChapterReport.text_ver_id || "-"}</code></div>
              <div className="small">画像ID（profile_id_used）：<code>{props.latestChapterReport.profile_id_used || "-"}</code></div>
              <div className="small">画像版本（profile_version_used）：<code>{props.latestChapterReport.profile_version_used ?? "-"}</code></div>
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
                    打开画像版本
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
