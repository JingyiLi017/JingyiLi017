import { useState } from "react";

type HelpPanelTarget = "jobs" | "ref" | "splitbooks" | "settings" | "agent" | "versions" | "rewrite" | "release" | "assets";

type HelpCenterPanelProps = {
  onOpenPanel: (target: HelpPanelTarget) => void;
  onStatus?: (msg: string) => void;
};

const writingFlow = [
  "在资料库创建书籍，填写题材、主题、受众、设定与灵感（写作工作台）。",
  "生成卷纲草案并应用，再生成章纲草案；必要时手动微调节点目标与冲突。",
  "执行闭环：章节包 -> 正文生成 -> 回写事实层（人物/时间线/世界观） -> 章节体检。",
  "按需执行“去 AI 味”与“风格进化”，再进入下一章循环。",
];

const splitbookFlow = [
  "创建拆书档案并设置源文本路径、切分参数（chunk_size / overlap）。",
  "先导入切分（Ingest），再向量化（Embed），最后执行结构抽取。",
  "结构抽取产出人物/时间线/世界观账本，可继续生成模板与画像。",
  "若任务中断，先到任务中心确认状态，再在拆书库使用“继续向量化/继续流程”。",
];

const splitbookStatusLegend = [
  ["pending", "待继续：任务不存在或已中断，可手动继续。"],
  ["queued", "排队中：任务已创建，等待 worker 执行。"],
  ["running", "进行中：任务正在处理，会显示阶段和百分比。"],
  ["done", "完成：该阶段已完成，重复触发会被防重。"],
  ["canceled", "已中止：人为停止，允许后续手动继续。"],
  ["failed", "失败：需查看错误并重试。"],
];

export function HelpCenterPanel(props: HelpCenterPanelProps) {
  const { onOpenPanel, onStatus } = props;
  const [helpMode, setHelpMode] = useState<"newbie" | "advanced">("newbie");

  const newbieFlow = [
    "第 1 步：先在“资料库”创建书籍，并填写题材、基调、设定与灵感。",
    "第 2 步：在写作主链路生成卷纲与章纲，确认冲突与伏笔。",
    "第 3 步：执行闭环（章节包 -> 正文 -> 回写 -> 体检）。",
    "第 4 步：如需学习风格，在拆书库执行“导入 -> 向量化 -> 结构抽取”。",
    "第 5 步：遇到卡住先看任务中心（排队中/进行中/已中止）。",
    "第 6 步：章节稳定后再执行“去 AI 味”与“风格进化”。",
    "第 7 步：每次大改后执行验证命令，确保状态一致性。",
  ];

  const advancedApiList = [
    "POST /v1/engine/closed_loop/run（写作闭环）",
    "POST /v1/chapters/{chapter_id}/manual_import（导入自写章节并强覆盖）",
    "GET /v1/books/{book_id}/ai_debug（AI 调用明细：数据与提示词）",
    "POST /v1/agent/orchestrate/plan（总控计划）",
    "POST /v1/agent/orchestrate/run（总控全流程）",
    "POST /v1/agent/orchestrate/step（总控单阶段）",
    "POST /v1/books/{book_id}/style/evolve（风格进化）",
    "POST /v1/splitbooks/{id}/ingest（导入切分）",
    "POST /v1/splitbooks/{id}/embed（向量化）",
    "POST /v1/splitbooks/{id}/extract_structured（结构抽取）",
    "POST /v1/splitbooks/{id}/writeback_preview_batch（批量回写预览）",
    "POST /v1/splitbooks/{id}/writeback_confirm_batch（批量回写确认）",
    "POST /v1/jobs/{job_id}/cancel（中止任务）",
  ];

  function copyCommand(cmd: string) {
    const api = globalThis?.navigator?.clipboard;
    if (!api) {
      onStatus?.(`请手动复制命令：${cmd}`);
      return;
    }
    void api
      .writeText(cmd)
      .then(() => onStatus?.(`已复制命令：${cmd}`))
      .catch(() => onStatus?.(`复制失败，请手动复制：${cmd}`));
  }

  return (
    <section className="help-center-panel">
      <div className="row" style={{ marginBottom: 8 }}>
        <div>
          <h3 style={{ margin: 0 }}>引擎功能使用说明</h3>
          <div className="small">覆盖拆书系统 + AI 写作引擎 + 任务恢复 + 质量验证。按作业顺序执行即可。</div>
        </div>
        <div className="row">
          <button onClick={() => onOpenPanel("splitbooks")}>打开拆书库</button>
          <button onClick={() => onOpenPanel("jobs")}>打开任务中心</button>
          <button onClick={() => onOpenPanel("settings")}>打开设置与健康</button>
          <button onClick={() => onOpenPanel("assets")}>打开资产沉淀</button>
          <button onClick={() => onOpenPanel("agent")}>打开智能体总控</button>
        </div>
      </div>

      <div className="help-mode-switch">
        <button className={helpMode === "newbie" ? "active" : ""} onClick={() => setHelpMode("newbie")}>
          新手模式（按顺序）
        </button>
        <button className={helpMode === "advanced" ? "active" : ""} onClick={() => setHelpMode("advanced")}>
          高级模式（能力全览）
        </button>
        <span className="small">当前：{helpMode === "newbie" ? "新手模式" : "高级模式"}</span>
      </div>

      {helpMode === "newbie" ? (
        <div className="help-grid">
          <article className="help-card">
            <h4>① 快速上手（推荐）</h4>
            <ol className="help-steps">
              {newbieFlow.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ol>
            <div className="small">目标：用最少步骤完成“可持续写作 + 可恢复拆书”。</div>
          </article>

          <article className="help-card">
            <h4>② 必看状态词</h4>
            <div className="help-status-list">
              {splitbookStatusLegend.map(([code, desc]) => (
                <div key={code} className="help-status-row">
                  <span className="badge">{code}</span>
                  <span>{desc}</span>
                </div>
              ))}
            </div>
          </article>

          <article className="help-card">
            <h4>③ 常见问题一键定位</h4>
            <ul className="help-steps">
              <li>任务不动：先打开任务中心，查看是否为“排队中/已中止/失败”。</li>
              <li>拆书卡住：在拆书库点击刷新，确认状态后再“继续向量化”。</li>
              <li>删除失败：确认该对象没有活动任务（queued/running）。</li>
            </ul>
          </article>

          <article className="help-card">
            <h4>④ 推荐入口</h4>
            <div className="help-command-grid">
              <button onClick={() => onOpenPanel("splitbooks")}>去拆书库作业</button>
              <button onClick={() => onOpenPanel("jobs")}>去任务中心排障</button>
              <button onClick={() => onOpenPanel("agent")}>去能力观测总览</button>
            </div>
          </article>
        </div>
      ) : (
        <div className="help-grid">
          <article className="help-card">
            <h4>① AI 写作引擎主链路</h4>
            <ol className="help-steps">
              {writingFlow.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ol>
            <div className="small">建议节奏：每章至少完成“推进 + 兑现 + 悬念”三件事。</div>
          </article>

          <article className="help-card">
            <h4>② 拆书主链路（百万字适配）</h4>
            <ol className="help-steps">
              {splitbookFlow.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ol>
            <div className="small">大文本默认走分批处理，避免一次性全量加载导致卡死。</div>
          </article>

          <article className="help-card">
            <h4>③ 拆书状态说明</h4>
            <div className="help-status-list">
              {splitbookStatusLegend.map(([code, desc]) => (
                <div key={code} className="help-status-row">
                  <span className="badge">{code}</span>
                  <span>{desc}</span>
                </div>
              ))}
            </div>
            <div className="small">当状态与任务不一致时，使用拆书库“刷新”触发对账（sync=true）。</div>
          </article>

          <article className="help-card">
            <h4>④ 任务中心怎么用</h4>
            <ul className="help-steps">
              <li>排队中 / 进行中 / 已完成 / 失败 / 已中止 全部中文显示。</li>
              <li>运行中可中止；中止后状态会回落为“已中止”并允许后续继续。</li>
              <li>终态任务可“删除记录”，便于清理历史噪声。</li>
              <li>中断重开后，先看“排队中/进行中（含排队）”页签，确认任务是否恢复可见。</li>
            </ul>
          </article>

          <article className="help-card">
            <h4>⑤ 数据删除与清理</h4>
            <ul className="help-steps">
              <li>资料库：支持删除书籍、章节等数据（有确认提示）。</li>
              <li>拆书库：支持删除拆书档案（无活动任务时可删）。</li>
              <li>任务中心：支持按状态批量清理，也支持单条删除终态记录。</li>
            </ul>
            <div className="small">建议先中止活动任务，再执行删除，防止被运行中的任务回写状态。</div>
          </article>

          <article className="help-card">
            <h4>⑥ 能力观测与进化</h4>
            <ul className="help-steps">
              <li>能力观测总览：成长曲线、张力曲线、反照抄、Agent 告警一屏查看。</li>
              <li>自动补冲突：当爽点密度不足或张力过低时执行。</li>
              <li>模板进化：根据评分结果迭代结构模板。</li>
              <li>风格进化：基于数据库累计样本更新风格画像。</li>
              <li>多书对比：比较不同拆书样本的结构与节奏差异。</li>
            </ul>
          </article>

          <article className="help-card">
            <h4>⑦ 核心 API（高级）</h4>
            <ul className="help-steps help-api-list">
              {advancedApiList.map((api) => (
                <li key={api}>
                  <code>{api}</code>
                </li>
              ))}
            </ul>
          </article>
        </div>
      )}

      <div className="help-card" style={{ marginTop: 10 }}>
        <h4>{helpMode === "newbie" ? "⑤ 验证命令与排障" : "⑧ 验证命令与排障"}</h4>
        <div className="help-command-grid">
          <button onClick={() => copyCommand("npm run verify:core")}>复制核心验证命令</button>
          <button onClick={() => copyCommand("npm run verify:splitbook-state")}>复制拆书一致性验证命令</button>
          <button onClick={() => copyCommand("npm run typecheck")}>复制前端类型检查命令</button>
        </div>
        <ul className="help-steps" style={{ marginTop: 8 }}>
          <li>若出现 `ERR_CONNECTION_REFUSED`：先检查 sidecar 与 engine 是否已启动。</li>
          <li>若任务长期不动：到任务中心确认状态，再在拆书库执行刷新与继续。</li>
          <li>若删除无效：确认该对象没有活动任务（queued/running）。</li>
        </ul>
      </div>
    </section>
  );
}
