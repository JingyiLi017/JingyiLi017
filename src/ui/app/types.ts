export type OutlineNode = {
  node_id: string;
  type: string;
  summary: string;
};

export type OutlineDetail = {
  chapter_no?: number;
  chapter_title?: string;
  nodes: OutlineNode[];
};

export type SkillRun = {
  skill_run_id: string;
  skill_name: string;
  output: any;
};

export type VersionItem = {
  outline_id: string;
  version: number;
  title: string;
  created_at: string;
};

export type BookItem = {
  book_id: string;
  profile_id?: string | null;
  title: string;
  author?: string | null;
  language?: string;
  notes?: string | null;
  created_at: string;
};

export type ChapterItem = {
  chapter_id: string;
  book_id: string;
  chapter_no: number;
  title: string;
  arc_id?: string | null;
  arc_index?: number | null;
  created_at: string;
};

export type JobItem = {
  job_id: string;
  job_type: string;
  capability_id: string;
  book_id?: string;
  status: string;
  stage: string;
  progress_value: number;
  progress?: { pct?: number; phase?: string; message?: string };
  payload?: Record<string, unknown>;
  result?: Record<string, unknown>;
  logs?: string[];
  error?: { code?: string; message?: string };
  created_at: string;
  updated_at: string;
  chapter_id?: string;
  book_title?: string;
  chapter_title?: string;
  splitbook_id?: string;
  splitbook_name?: string;
  splitbook_author?: string;
  job_book_label?: string;
};

export type Health = {
  status: string;
  checks: Record<string, any>;
};

export type ArcTarget = {
  book_id: string;
  arc_id: string;
  target_shape: "ramp" | "late_peak" | "early_peak" | "plateau" | "sawtooth";
  target_points: number[];
  weights: { overall: number; cost: number; reversal: number };
};

export type TemplateVariant = {
  variant_id: string;
  name: string;
  enabled: boolean;
  weight: number;
  scope: Record<string, unknown>;
  stats: Record<string, unknown>;
  recipe: Record<string, unknown>;
};

export type TemplateAssetItem = {
  asset_id: string;
  asset_type: string;
  name: string;
  description: string;
  tags?: string[];
  source_splitbook_id?: string | null;
  source_span?: Record<string, unknown> | null;
  created_at?: string;
};

export type RefUnifiedItem = {
  kind: "material" | "template";
  id: string;
  title: string;
  subtitle: string;
  score: number;
};

export type GlobalSearchItem = {
  type: "book" | "chapter" | "material" | "skill_run";
  id: string;
  title: string;
  subtitle: string;
  score: number;
  book_id?: string;
};

export type ProfileCfg = {
  profile_id: string;
  name: string;
  active_version?: number;
  note?: string | null;
  features?: Record<string, unknown>;
  dos?: string[];
  donts?: string[];
  updated_at?: string | null;
  created_at?: string;
};

export type ProfileVersionItem = {
  profile_id: string;
  version: number;
  created_at: string;
  actor?: string;
  action: string;
  note?: string;
  parent_version?: number | null;
  source_text_ver_ids?: string[];
};

export type SplitbookItem = {
  splitbook_id: string;
  name: string;
  author?: string | null;
  source_path?: string | null;
  note?: string | null;
  ingest_status: string;
  embed_status: string;
  allow_guard: boolean;
  stats?: Record<string, any>;
  created_at: string;
  updated_at: string;
};

export type ProviderId = "ollama" | "openai" | "openai_compatible";

export type ProviderConfig = {
  base_url: string;
  api_key?: string;
  llm_model: string;
  embedding_model: string;
  chat_path?: string;
  embeddings_path?: string;
};
