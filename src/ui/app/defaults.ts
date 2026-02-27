import type { ProviderConfig, ProviderId } from "./types";

export const defaultTargets = {
  conflict_strength: 0.72,
  stakes: 0.65,
  cost: 0.6,
  pace: 0.62,
  reversal: 0.55,
  hook: 0.6,
};

export const defaultStyle = {
  face_slap_density: 0.18,
  upgrade_density: 0.14,
};

export const defaultSettings: any = {
  ollama: { base_url: "http://127.0.0.1:11434", llm_model: "qwen2.5:7b", embedding_model: "bge-m3:latest" },
  ai_provider: "ollama",
  providers: {
    ollama: {
      base_url: "http://127.0.0.1:11434",
      llm_model: "qwen2.5:7b",
      embedding_model: "bge-m3:latest",
      chat_path: "/api/chat",
      embeddings_path: "/api/embeddings",
    },
    openai: {
      base_url: "https://api.openai.com/v1",
      api_key: "",
      llm_model: "gpt-4o-mini",
      embedding_model: "text-embedding-3-small",
      chat_path: "/chat/completions",
      embeddings_path: "/embeddings",
    },
    openai_compatible: {
      base_url: "http://127.0.0.1:8000/v1",
      api_key: "",
      llm_model: "qwen2.5:7b",
      embedding_model: "bge-m3:latest",
      chat_path: "/chat/completions",
      embeddings_path: "/embeddings",
    },
  },
  similarity: { vec_high: 0.86, vec_mid: 0.8, ng_high: 0.2, ng_mid: 0.12 },
  limits: { llm_concurrency: 1, embed_concurrency: 2, max_insert_nodes: 4 },
  ui: {
    capability_chain: {
      retry_max: 3,
      retry_base_ms: 600,
    },
    ingest_confirm: {
      keyword: "导入",
    },
    delete_confirm: {
      mismatch_beep: true,
      mismatch_beep_level: "soft",
    },
  },
};

const scopeLabels: Record<string, string> = {
  global: "全局",
  book: "书籍",
  chapter: "章节",
};

const searchTypeLabels: Record<string, string> = {
  book: "书籍",
  chapter: "章节",
  material: "素材",
  skill_run: "技能运行",
};

const refKindLabels: Record<string, string> = {
  material: "素材",
  template: "模板",
};

const jobStatusLabels: Record<string, string> = {
  queued: "排队中",
  running: "进行中",
  succeeded: "已完成",
  failed: "失败",
  canceled: "已中止",
  cancelled: "已中止",
};

const flowStepLabels: Record<string, string> = {
  splitbook: "拆书",
  smart: "智能流程",
  preflight: "预检",
};

const quickStepLabels: Record<string, string> = {
  sidecar: "侧车(Sidecar)",
  draft: "草稿",
  versions: "版本",
  select: "选稿",
  publish: "发布",
};

const pipelineStatusLabels: Record<string, string> = {
  idle: "空闲",
  queued: "排队中",
  running: "进行中",
  ingesting: "导入中",
  pending: "待继续",
  done: "完成",
  canceled: "已中止",
  cancelled: "已中止",
  failed: "失败",
};

const phaseLabels: Record<string, string> = {
  running: "运行中",
  queued: "排队中",
  pending: "待继续",
  started: "已开始",
  preparing: "准备中",
  applying: "应用中",
  measuring: "评测中",
  ingest: "导入文本",
  embed: "向量化",
  extract_structured: "结构抽取",
  build_templates: "生成模板",
  build_profile: "生成画像",
  writeback: "回写",
  preflight: "体检",
  rewrite: "改写",
  style_evolution: "风格进化",
  succeeded: "已完成",
  canceled: "已中止",
  cancelled: "已中止",
  completed: "已完成",
  done: "已完成",
  failed: "失败",
};

const jobTypeLabels: Record<string, string> = {
  "splitbook.ingest.v1": "拆书导入",
  "splitbook.embed.v1": "拆书向量化",
  "splitbook.extract_structured.v1": "拆书结构抽取",
  "splitbook.build_templates.v1": "拆书模板沉淀",
  "splitbook.build_profile.v1": "拆书画像生成",
  "splitbook.writeback_batch.v1": "拆书批量回写",
  "extract.structure_beats.v1": "结构节拍抽取",
  "draft.commit.v1": "正文生成",
  "apply.measure.v1": "应用并评测",
  "eval.conflict_tension.v1": "张力评估",
  "control_plan.tension.v1": "张力修复规划",
  "book.tension.analyze.v1": "全书张力分析",
  "template.evolve.v1": "模板进化",
  "generate.structure_template.v1": "结构模板生成",
  "similarity.guard.v1": "相似度守卫",
  "similarity.guard.text.v1": "文本相似度守卫",
};

export function formatScopeLabel(scope: string) {
  return scopeLabels[scope] ? `${scopeLabels[scope]}（${scope}）` : scope;
}

export function formatSearchTypeLabel(type: string) {
  return searchTypeLabels[type] || type;
}

export function formatRefKindLabel(kind: string) {
  return refKindLabels[kind] || kind;
}

export function formatJobStatusLabel(status: string) {
  const raw = String(status || "").trim();
  const key = raw.toLowerCase();
  return jobStatusLabels[key] ? `${jobStatusLabels[key]}（${raw}）` : raw;
}

export function flowStepLabel(step: string) {
  return flowStepLabels[step] ? `${flowStepLabels[step]}（${step}）` : step;
}

export function quickStepLabel(step: string) {
  return quickStepLabels[step] ? `${quickStepLabels[step]}（${step}）` : step;
}

export function formatPipelineStatus(status: string) {
  const raw = String(status || "").trim();
  const key = raw.toLowerCase();
  return pipelineStatusLabels[key] ? `${pipelineStatusLabels[key]}（${raw}）` : raw;
}

export function formatPhaseLabel(phase?: string) {
  const raw = String(phase || "running").trim();
  const key = raw.toLowerCase();
  return phaseLabels[key] ? `${phaseLabels[key]}（${raw}）` : raw;
}

export function formatJobTypeLabel(jobType?: string, capabilityId?: string) {
  const rawType = String(jobType || "").trim();
  const rawCapability = String(capabilityId || "").trim();
  const candidates = [
    rawCapability.toLowerCase(),
    rawType.toLowerCase(),
    rawType.toLowerCase().replace(/_/g, "."),
  ].filter(Boolean);

  const baseKey = candidates.find((k) => Boolean(jobTypeLabels[k])) || "";
  if (baseKey) {
    const raw = rawCapability || rawType;
    return `${jobTypeLabels[baseKey]}（${raw}）`;
  }

  const key = candidates[0] || candidates[1] || "";
  if (key.startsWith("splitbook.")) return `拆书任务（${rawCapability || rawType}）`;
  if (key.startsWith("draft.")) return `草稿任务（${rawCapability || rawType}）`;
  if (key.startsWith("eval.")) return `评估任务（${rawCapability || rawType}）`;
  if (key.startsWith("control_plan.")) return `控制规划任务（${rawCapability || rawType}）`;
  if (key.startsWith("template.")) return `模板任务（${rawCapability || rawType}）`;
  if (key.startsWith("similarity.")) return `相似度任务（${rawCapability || rawType}）`;

  return rawType || rawCapability || "未知任务";
}

export function getProviderConfig(settingsData: any, provider: ProviderId): ProviderConfig {
  const fallback = defaultSettings.providers[provider] as ProviderConfig;
  const cfg = settingsData?.providers?.[provider] || {};
  return {
    base_url: cfg.base_url || fallback.base_url,
    api_key: cfg.api_key || "",
    llm_model: cfg.llm_model || fallback.llm_model,
    embedding_model: cfg.embedding_model || fallback.embedding_model,
    chat_path: cfg.chat_path || fallback.chat_path,
    embeddings_path: cfg.embeddings_path || fallback.embeddings_path,
  };
}

export function syncLegacyOllama(settingsData: any): any {
  const provider = (settingsData?.ai_provider || "ollama") as ProviderId;
  const cfg = getProviderConfig(settingsData, provider);
  return {
    ...settingsData,
    ai_provider: provider,
    ollama: {
      ...(settingsData?.ollama || {}),
      base_url: cfg.base_url,
      llm_model: cfg.llm_model,
      embedding_model: cfg.embedding_model,
      api_key: cfg.api_key || "",
      provider,
      chat_path: cfg.chat_path || "",
      embeddings_path: cfg.embeddings_path || "",
    },
  };
}
