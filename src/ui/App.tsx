import { useEffect, useMemo, useRef, useState } from "react";
import { CompareDrawer } from "./CompareDrawer";
import { ForeshadowBoardPanel } from "./ForeshadowBoardPanel";
import { GrowthBoardPanel } from "./GrowthBoardPanel";
import { PayoffTemplatePanel } from "./PayoffTemplatePanel";
import { MaterialCenter } from "./MaterialCenter";
import { PolicySuggestionsPanel } from "./PolicySuggestionsPanel";
import { ComboLeaderboardPanel } from "./ComboLeaderboardPanel";
import { VolumePlanPanel } from "./VolumePlanPanel";
import { SettingsBasicPanel } from "./SettingsBasicPanel";
import { SettingsDiffPanel } from "./SettingsDiffPanel";
import { SettingsAuditPanel } from "./SettingsAuditPanel";
import { AgentConsolePanel } from "./AgentConsolePanel";
import { VersionsPanel } from "./VersionsPanel";
import { RewritePanel } from "./RewritePanel";
import { PublishPackPanel } from "./PublishPackPanel";
import { PreflightFixWizardPanel } from "./PreflightFixWizardPanel";
import { ComboInjectionQueuePanel } from "./ComboInjectionQueuePanel";
import { SkillPackHubPanel } from "./SkillPackHubPanel";
type OutlineNode = {
  node_id: string;
  type: string;
  summary: string;
};

type OutlineDetail = {
  chapter_no?: number;
  chapter_title?: string;
  nodes: OutlineNode[];
};

type SkillRun = {
  skill_run_id: string;
  skill_name: string;
  output: any;
};

type VersionItem = {
  outline_id: string;
  version: number;
  title: string;
  created_at: string;
};

type BookItem = {
  book_id: string;
  profile_id?: string | null;
  title: string;
  author?: string | null;
  language?: string;
  notes?: string | null;
  created_at: string;
};

type ChapterItem = {
  chapter_id: string;
  book_id: string;
  chapter_no: number;
  title: string;
  arc_id?: string | null;
  arc_index?: number | null;
  created_at: string;
};

type JobItem = {
  job_id: string;
  job_type: string;
  capability_id: string;
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
};

type Health = {
  status: string;
  checks: Record<string, any>;
};

type ArcTarget = {
  book_id: string;
  arc_id: string;
  target_shape: "ramp" | "late_peak" | "early_peak" | "plateau" | "sawtooth";
  target_points: number[];
  weights: { overall: number; cost: number; reversal: number };
};

type TemplateVariant = {
  variant_id: string;
  name: string;
  enabled: boolean;
  weight: number;
  scope: Record<string, unknown>;
  stats: Record<string, unknown>;
  recipe: Record<string, unknown>;
};

type TemplateAssetItem = {
  asset_id: string;
  asset_type: string;
  name: string;
  description: string;
  tags?: string[];
  source_splitbook_id?: string | null;
  source_span?: Record<string, unknown> | null;
  created_at?: string;
};

type RefUnifiedItem = {
  kind: "material" | "template";
  id: string;
  title: string;
  subtitle: string;
  score: number;
};

type GlobalSearchItem = {
  type: "book" | "chapter" | "material" | "skill_run";
  id: string;
  title: string;
  subtitle: string;
  score: number;
  book_id?: string;
};

type ProfileCfg = {
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

type ProfileVersionItem = {
  profile_id: string;
  version: number;
  created_at: string;
  actor?: string;
  action: string;
  note?: string;
  parent_version?: number | null;
  source_text_ver_ids?: string[];
};

type SplitbookItem = {
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

type ProviderId = "ollama" | "openai" | "openai_compatible";
type ProviderConfig = {
  base_url: string;
  api_key?: string;
  llm_model: string;
  embedding_model: string;
  chat_path?: string;
  embeddings_path?: string;
};

const defaultTargets = {
  conflict_strength: 0.72,
  stakes: 0.65,
  cost: 0.6,
  pace: 0.62,
  reversal: 0.55,
  hook: 0.6
};

const defaultStyle = {
  face_slap_density: 0.18,
  upgrade_density: 0.14
};

const defaultSettings = {
  ollama: { base_url: "http://127.0.0.1:11434", llm_model: "qwen2.5:7b", embedding_model: "bge-m3:latest" },
  ai_provider: "ollama",
  providers: {
    ollama: {
      base_url: "http://127.0.0.1:11434",
      llm_model: "qwen2.5:7b",
      embedding_model: "bge-m3:latest",
      chat_path: "/api/chat",
      embeddings_path: "/api/embeddings"
    },
    openai: {
      base_url: "https://api.openai.com/v1",
      api_key: "",
      llm_model: "gpt-4o-mini",
      embedding_model: "text-embedding-3-small",
      chat_path: "/chat/completions",
      embeddings_path: "/embeddings"
    },
    openai_compatible: {
      base_url: "http://127.0.0.1:8000/v1",
      api_key: "",
      llm_model: "qwen2.5:7b",
      embedding_model: "bge-m3:latest",
      chat_path: "/chat/completions",
      embeddings_path: "/embeddings"
    }
  },
  similarity: { vec_high: 0.86, vec_mid: 0.8, ng_high: 0.2, ng_mid: 0.12 },
  limits: { llm_concurrency: 1, embed_concurrency: 2, max_insert_nodes: 4 }
};

function getProviderConfig(settingsData: any, provider: ProviderId): ProviderConfig {
  const fallback = defaultSettings.providers[provider];
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

function syncLegacyOllama(settingsData: any): any {
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
    }
  };
}

async function createJob(baseUrl: string, capability_id: string, input: Record<string, unknown>) {
  const res = await fetch(`${baseUrl}/v1/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ capability_id, input })
  });
  if (!res.ok) throw new Error(`CREATE_JOB_FAILED:${res.status}`);
  return res.json() as Promise<{ job_id: string }>;
}

async function getJob(baseUrl: string, jobId: string) {
  const res = await fetch(`${baseUrl}/v1/jobs/${jobId}`);
  if (!res.ok) throw new Error(`JOB_FETCH_FAILED:${res.status}`);
  return res.json();
}

async function waitJobDone(baseUrl: string, jobId: string, onTick?: (job: any) => void) {
  while (true) {
    const job = await getJob(baseUrl, jobId);
    onTick?.(job);
    if (job.status === "succeeded") return job;
    if (job.status === "failed" || job.status === "canceled") throw new Error(job.error?.message || "JOB_FAILED");
    await new Promise((r) => setTimeout(r, 1200));
  }
}

export function App() {
  const [baseUrl, setBaseUrl] = useState("http://127.0.0.1:17777");
  const [chapterId, setChapterId] = useState("");
  const [bookId, setBookId] = useState("");
  const [outline, setOutline] = useState<OutlineDetail | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [versions, setVersions] = useState<VersionItem[]>([]);
  const [selectedVersion, setSelectedVersion] = useState("latest");
  const [bookQuery, setBookQuery] = useState("");
  const [chapterQuery, setChapterQuery] = useState("");
  const [bookItems, setBookItems] = useState<BookItem[]>([]);
  const [chapterItems, setChapterItems] = useState<ChapterItem[]>([]);
  const [newBookName, setNewBookName] = useState("");
  const [newChapterNo, setNewChapterNo] = useState(1);
  const [newChapterTitle, setNewChapterTitle] = useState("");
  const [newChapterArcId, setNewChapterArcId] = useState("vol-1");
  const [newChapterArcIndex, setNewChapterArcIndex] = useState(1);
  const [dirty, setDirty] = useState(false);
  const [targets, setTargets] = useState(defaultTargets);
  const [style, setStyle] = useState(defaultStyle);
  const [evalRun, setEvalRun] = useState<SkillRun | null>(null);
  const [planRun, setPlanRun] = useState<SkillRun | null>(null);
  const [selectedPatches, setSelectedPatches] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Ready");
  const [quickVolumeId, setQuickVolumeId] = useState("");
  const [quickDraftRunOut, setQuickDraftRunOut] = useState<any>(null);
  const [quickVersionsOut, setQuickVersionsOut] = useState<any>(null);
  const [quickPublishOut, setQuickPublishOut] = useState<any>(null);
  const [quickRunMode, setQuickRunMode] = useState<"manual_gate" | "balanced_auto" | "safe_auto">("balanced_auto");
  const [quickAutoSelectLatest, setQuickAutoSelectLatest] = useState(true);
  const [quickAutoPublish, setQuickAutoPublish] = useState(true);
  const [quickAutoFixOnPublishFail, setQuickAutoFixOnPublishFail] = useState(true);
  const [quickAutoFixMax, setQuickAutoFixMax] = useState(3);
  const [quickAutoOpenFolder, setQuickAutoOpenFolder] = useState(true);
  const [quickPipelineBusy, setQuickPipelineBusy] = useState(false);
  const [quickPipelineSteps, setQuickPipelineSteps] = useState<Record<string, string>>({
    sidecar: "idle",
    draft: "idle",
    versions: "idle",
    select: "idle",
    publish: "idle",
  });
  const [quickPipelineError, setQuickPipelineError] = useState<{ step: string; message: string } | null>(null);
  const [quickFixPreview, setQuickFixPreview] = useState<any>(null);
  const [quickFixExecuteOut, setQuickFixExecuteOut] = useState<any>(null);
  const [flowBusy, setFlowBusy] = useState(false);
  const [flowSteps, setFlowSteps] = useState<Record<string, string>>({
    splitbook: "idle",
    smart: "idle",
    preflight: "idle",
  });
  const [flowAutoSplitbook, setFlowAutoSplitbook] = useState(false);

  const [showJobs, setShowJobs] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [showRefCenter, setShowRefCenter] = useState(false);
  const [showSplitbooks, setShowSplitbooks] = useState(false);
  const [showAgentConsole, setShowAgentConsole] = useState(true);
  const [showVersionCenter, setShowVersionCenter] = useState(false);
  const [showRewriteCenter, setShowRewriteCenter] = useState(false);
  const [showReleaseCenter, setShowReleaseCenter] = useState(false);
  const [refCenterTab, setRefCenterTab] = useState<"material" | "template">("material");
  const [jobTab, setJobTab] = useState<"running" | "succeeded" | "failed">("running");
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [selectedJob, setSelectedJob] = useState<JobItem | null>(null);
  const [jobSkillRunFilter, setJobSkillRunFilter] = useState("");

  const [settingsData, setSettingsData] = useState<any>(defaultSettings);
  const [settingsScope, setSettingsScope] = useState<"global" | "book" | "chapter">("global");
  const [settingsEditorMode, setSettingsEditorMode] = useState<"basic" | "advanced">("basic");
  const [scopedSettingsObj, setScopedSettingsObj] = useState<any>({});
  const [scopedSettingsText, setScopedSettingsText] = useState("{}");
  const [scopedSettingsSavedText, setScopedSettingsSavedText] = useState("{}");
  const [scopedSettingsParseError, setScopedSettingsParseError] = useState("");
  const [effectiveSourcesObj, setEffectiveSourcesObj] = useState<any>({});
  const [effectiveSettingsText, setEffectiveSettingsText] = useState("{}");
  const [settingsPresets, setSettingsPresets] = useState<any[]>([]);
  const [settingsPresetName, setSettingsPresetName] = useState("");
  const [settingsPresetDesc, setSettingsPresetDesc] = useState("");
  const [settingsDiffRows, setSettingsDiffRows] = useState<any[]>([]);
  const [settingsDiffPair, setSettingsDiffPair] = useState<"global_book" | "book_chapter" | "global_effective">("global_book");
  const [traceMenu, setTraceMenu] = useState<{ x: number; y: number; key: string; value: any; source: string } | null>(null);
  const [settingsAuditRows, setSettingsAuditRows] = useState<any[]>([]);
  const [settingsAuditLoading, setSettingsAuditLoading] = useState(false);
  const [rollbackPreviewAudit, setRollbackPreviewAudit] = useState<any | null>(null);
  const [rollbackPreviewDiffRows, setRollbackPreviewDiffRows] = useState<any[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [bookTensionReport, setBookTensionReport] = useState<any | null>(null);
  const [arcTargets, setArcTargets] = useState<ArcTarget[]>([]);
  const [variants, setVariants] = useState<TemplateVariant[]>([]);
  const [arcTargetForm, setArcTargetForm] = useState<ArcTarget>({
    book_id: "",
    arc_id: "vol-1",
    target_shape: "ramp",
    target_points: [0.42, 0.52, 0.6, 0.7, 0.74],
    weights: { overall: 0.6, cost: 0.2, reversal: 0.2 }
  });
  const [compareFrom, setCompareFrom] = useState<number>(1);
  const [compareTo, setCompareTo] = useState<number>(1);
  const [compareDiff, setCompareDiff] = useState<any | null>(null);
  const [evalBeforeRun, setEvalBeforeRun] = useState("");
  const [evalAfterRun, setEvalAfterRun] = useState("");
  const [evalCompare, setEvalCompare] = useState<any | null>(null);
  const [reportHtml, setReportHtml] = useState("");
  const [reportPdfPath, setReportPdfPath] = useState("");
  const [latestChapterReport, setLatestChapterReport] = useState<any | null>(null);
  const [compareOpen, setCompareOpen] = useState(false);
  const [compareUnread, setCompareUnread] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchItems, setSearchItems] = useState<GlobalSearchItem[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchSelectedIndex, setSearchSelectedIndex] = useState(0);
  const [librarySearchQuery, setLibrarySearchQuery] = useState("");
  const [librarySearchItems, setLibrarySearchItems] = useState<GlobalSearchItem[]>([]);
  const [librarySearchLoading, setLibrarySearchLoading] = useState(false);
  const [materialRefs, setMaterialRefs] = useState<string[]>([]);
  const [profiles, setProfiles] = useState<ProfileCfg[]>([]);
  const [selectedBookProfileId, setSelectedBookProfileId] = useState("");
  const [profileLearning, setProfileLearning] = useState(false);
  const [profileVersions, setProfileVersions] = useState<ProfileVersionItem[]>([]);
  const [profileActiveVersion, setProfileActiveVersion] = useState<number>(0);
  const [profileDiffFrom, setProfileDiffFrom] = useState<number>(0);
  const [profileDiffTo, setProfileDiffTo] = useState<number>(0);
  const [profileDiffResult, setProfileDiffResult] = useState<any>(null);
  const [profileVersionSnapshot, setProfileVersionSnapshot] = useState<any>(null);
  const [profileCloneName, setProfileCloneName] = useState("");
  const [bookProfileMeta, setBookProfileMeta] = useState<any>(null);
  const [focusProfileVersion, setFocusProfileVersion] = useState<number>(0);
  const [abBatchId, setAbBatchId] = useState("");
  const [abBatchData, setAbBatchData] = useState<any | null>(null);
  const [assetTraceView, setAssetTraceView] = useState<any | null>(null);
  const [abPromoteStrategy, setAbPromoteStrategy] = useState<"profile" | "version" | "profile_plus_settings">("profile");
  const [abBatchLoading, setAbBatchLoading] = useState(false);
  const [abIncludeComboBaseline, setAbIncludeComboBaseline] = useState(true);
  const [chapterReports, setChapterReports] = useState<any[]>([]);
  const [splitbooks, setSplitbooks] = useState<SplitbookItem[]>([]);
  const [selectedSplitbookId, setSelectedSplitbookId] = useState("");
  const [splitbookName, setSplitbookName] = useState("");
  const [splitbookAuthor, setSplitbookAuthor] = useState("");
  const [splitbookPath, setSplitbookPath] = useState("/data/novels/");
  const [splitbookChunkSize, setSplitbookChunkSize] = useState(600);
  const [splitbookOverlap, setSplitbookOverlap] = useState(120);
  const [splitbookRunningJobs, setSplitbookRunningJobs] = useState<JobItem[]>([]);
  const [templateType, setTemplateType] = useState("");
  const [templateTag, setTemplateTag] = useState("");
  const [templateQuery, setTemplateQuery] = useState("");
  const [templateItems, setTemplateItems] = useState<TemplateAssetItem[]>([]);
  const [templateSelected, setTemplateSelected] = useState<TemplateAssetItem | null>(null);
  const [templateLoading, setTemplateLoading] = useState(false);
  const [templateNote, setTemplateNote] = useState("");
  const [refUnifiedQuery, setRefUnifiedQuery] = useState("");
  const [refUnifiedLoading, setRefUnifiedLoading] = useState(false);
  const [refUnifiedItems, setRefUnifiedItems] = useState<RefUnifiedItem[]>([]);

  const timerRef = useRef<number | null>(null);
  const seenJobIdsRef = useRef<Set<string>>(new Set());
  const pollInitializedRef = useRef(false);

  const selectedNode = useMemo(() => outline?.nodes?.find((n) => n.node_id === selectedNodeId) ?? null, [outline, selectedNodeId]);

  function extractSkillRunId(job: JobItem): string {
    const resultId = String((job.result as any)?.skill_run_id || "");
    if (resultId) return resultId;
    const runId = String((job as any)?.run_id || "");
    if (runId) return runId;
    return "";
  }

  async function loadOutline(version = selectedVersion) {
    if (!chapterId.trim()) return;
    setBusy(true);
    setStatus("Loading outline...");
    try {
      const detailRes = await fetch(`${baseUrl}/v1/chapters/${chapterId}/outline_detail?version=${encodeURIComponent(version)}`);
      if (!detailRes.ok) throw new Error(`OUTLINE_LOAD_FAILED:${detailRes.status}`);
      const detail = await detailRes.json();
      setOutline(detail.content || { nodes: [] });
      setSelectedNodeId(detail.content?.nodes?.[0]?.node_id || null);
      setDirty(false);

      const verRes = await fetch(`${baseUrl}/v1/chapters/${chapterId}/outline_detail/versions`);
      if (verRes.ok) {
        const data = await verRes.json();
        setVersions(data.items || []);
      }
      setStatus("Outline loaded");
    } catch (err) {
      setStatus(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function loadBooks() {
    const q = encodeURIComponent(bookQuery.trim());
    const res = await fetch(`${baseUrl}/v1/books?query=${q}&limit=50`);
    if (!res.ok) throw new Error(`BOOKS_LOAD_FAILED:${res.status}`);
    const data = await res.json();
    setBookItems((data.items || []) as BookItem[]);
    if (bookId) {
      const cur = ((data.items || []) as BookItem[]).find((x) => x.book_id === bookId);
      setSelectedBookProfileId(cur?.profile_id ? String(cur.profile_id) : "");
    }
  }

  async function loadProfilesList() {
    const res = await fetch(`${baseUrl}/v1/profiles?limit=100`);
    if (!res.ok) throw new Error(`PROFILES_LOAD_FAILED:${res.status}`);
    const data = await res.json();
    setProfiles((data.items || []) as ProfileCfg[]);
  }

  async function loadProfileVersions(profileId: string) {
    if (!profileId) {
      setProfileVersions([]);
      setProfileActiveVersion(0);
      setProfileDiffFrom(0);
      setProfileDiffTo(0);
      setProfileDiffResult(null);
      setProfileVersionSnapshot(null);
      return;
    }
    const res = await fetch(`${baseUrl}/v1/profiles/${profileId}/versions?limit=50`);
    if (!res.ok) throw new Error(`PROFILE_VERSIONS_LOAD_FAILED:${res.status}`);
    const out = await res.json();
    const items = (out.items || []) as ProfileVersionItem[];
    setProfileVersions(items);
    setProfileActiveVersion(Number(out.active_version || 0));
    const active = Number(out.active_version || 0);
    setProfileDiffTo(active);
    setProfileDiffFrom(active > 1 ? active - 1 : active);
  }

  async function openProfileVersionSnapshot(profileId: string, version: number) {
    if (!profileId || !version) return;
    const res = await fetch(`${baseUrl}/v1/profiles/${profileId}/versions/${version}`);
    if (!res.ok) throw new Error(`PROFILE_VERSION_LOAD_FAILED:${res.status}`);
    const out = await res.json();
    setProfileVersionSnapshot(out.snapshot || null);
  }

  async function setActiveProfileVersion(version: number) {
    if (!selectedBookProfileId || !version) return;
    const res = await fetch(`${baseUrl}/v1/profiles/${selectedBookProfileId}/active_version`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ version, note: `set active to v${version}` }),
    });
    if (!res.ok) throw new Error(`PROFILE_SET_ACTIVE_FAILED:${res.status}`);
    await loadProfilesList();
    await loadProfileVersions(selectedBookProfileId);
    setStatus(`Profile active_version -> v${version}`);
  }

  async function runProfileVersionDiff() {
    if (!selectedBookProfileId || !profileDiffFrom || !profileDiffTo) return;
    const res = await fetch(`${baseUrl}/v1/profiles/${selectedBookProfileId}/diff`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ from: profileDiffFrom, to: profileDiffTo, mode: "leaf" }),
    });
    if (!res.ok) throw new Error(`PROFILE_DIFF_FAILED:${res.status}`);
    const out = await res.json();
    setProfileDiffResult(out);
  }

  async function cloneCurrentProfileBranch() {
    if (!selectedBookProfileId) return;
    const fallbackName = `Profile-branch-${new Date().toISOString().slice(11, 19).replace(/:/g, "")}`;
    const newName = (profileCloneName || "").trim() || fallbackName;
    const res = await fetch(`${baseUrl}/v1/profiles/${selectedBookProfileId}/clone`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_name: newName, note: `clone from ${selectedBookProfileId}` }),
    });
    if (!res.ok) throw new Error(`PROFILE_CLONE_FAILED:${res.status}`);
    const out = await res.json();
    const newProfileId = String(out.profile_id || "");
    setProfileCloneName("");
    await loadProfilesList();
    if (bookId && newProfileId) {
      await fetch(`${baseUrl}/v1/books/${bookId}/profiles`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_id: newProfileId, role: "experiment" }),
      });
      await loadBookProfilesMeta();
    }
    setStatus(`Profile cloned: ${newName}`);
  }

  async function loadBookProfilesMeta() {
    if (!bookId) {
      setBookProfileMeta(null);
      return;
    }
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/profiles`);
    if (!res.ok) throw new Error(`BOOK_PROFILES_LOAD_FAILED:${res.status}`);
    const out = await res.json();
    setBookProfileMeta(out);
  }

  async function addExperimentProfile(profileId: string) {
    if (!bookId || !profileId) return;
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/profiles`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: profileId, role: "experiment" }),
    });
    if (!res.ok) throw new Error(`BOOK_PROFILE_LINK_FAILED:${res.status}`);
    await loadBookProfilesMeta();
    setStatus(`Added experiment profile: ${profileId}`);
  }

  async function runAbBatch() {
    if (!chapterId || !bookId) return;
    setAbBatchLoading(true);
    try {
      const res = await fetch(`${baseUrl}/v1/chapters/${chapterId}/ab_batch/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          note: "A/B batch from desktop",
          profiles: "all",
          include_baseline: true,
          baseline_profile: "main",
          include_combo_baseline: abIncludeComboBaseline,
          combo_baseline_profile: "main",
          do_eval: true,
          do_simguard: true,
        }),
      });
      if (!res.ok) throw new Error(`AB_BATCH_RUN_FAILED:${res.status}`);
      const out = await res.json();
      setAbBatchId(String(out.batch_id || ""));
      setStatus(`A/B batch started: ${out.batch_id}`);
    } finally {
      setAbBatchLoading(false);
    }
  }

  async function loadAbBatch(batchId: string) {
    if (!batchId) return;
    const res = await fetch(`${baseUrl}/v1/ab_batch/${batchId}`);
    if (!res.ok) throw new Error(`AB_BATCH_LOAD_FAILED:${res.status}`);
    const out = await res.json();
    setAbBatchData(out);
  }

  async function retryAbBatchFailed(batchId: string) {
    if (!batchId) return;
    const res = await fetch(`${baseUrl}/v1/ab_batch/${batchId}/retry_failed`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!res.ok) throw new Error(`AB_BATCH_RETRY_FAILED:${res.status}`);
    const out = await res.json();
    const nextId = String(out.new_batch_id || "");
    if (nextId) {
      setAbBatchId(nextId);
      setStatus(`Retry batch created: ${nextId}`);
    } else {
      setStatus(`No failed items to retry: ${batchId}`);
    }
  }

  async function promoteAbBatchWinner(batchId: string) {
    if (!batchId) return;
    const payload: any = {
      strategy: abPromoteStrategy,
      note: "promote best score",
      simguard_limit: 0.25,
    };
    if (abPromoteStrategy === "profile_plus_settings") {
      payload.settings = {
        apply: true,
        mode: "merge",
        preset_name: `AUTO: batch-${String(batchId).slice(0, 8)} winner`,
        preset_description: `auto created from ab_batch ${batchId}`,
      };
    }
    const res = await fetch(`${baseUrl}/v1/ab_batch/${batchId}/promote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`AB_BATCH_PROMOTE_FAILED:${res.status}`);
    const out = await res.json();
    const winner = out?.winner || {};
    const profileResult = out?.profile_result || {};
    const promotedTo = String(profileResult.new_main_profile_id || winner.profile_id || "").slice(0, 8);
    setStatus(`Winner promoted [${abPromoteStrategy}]: ${promotedTo || "-"} (score=${winner.score ?? "-"})`);
    await loadBookProfilesMeta();
    await loadBooks();
    const nextProfileId = String(profileResult.new_main_profile_id || "");
    if (nextProfileId) {
      setSelectedBookProfileId(nextProfileId);
      await loadProfileVersions(nextProfileId);
    }
  }

  async function loadChapterReports() {
    if (!chapterId) return;
    const res = await fetch(`${baseUrl}/v1/chapters/${chapterId}/reports?limit=50`);
    if (!res.ok) throw new Error(`CHAPTER_REPORTS_LOAD_FAILED:${res.status}`);
    const out = await res.json();
    setChapterReports(Array.isArray(out.items) ? out.items : []);
  }

  async function viewAssetSelectionTrace(textVerId: string) {
    if (!textVerId) return;
    const res = await fetch(`${baseUrl}/v1/text_versions/${textVerId}/asset_selection_trace/latest`);
    if (!res.ok) throw new Error(`ASSET_TRACE_LOAD_FAILED:${res.status}`);
    const out = await res.json();
    setAssetTraceView(out);
    setStatus(`Loaded asset trace: ${String(out.trace_id || "").slice(0, 8)}`);
  }

  async function bindProfileToBook(profileId: string) {
    if (!bookId) return;
    const body = { profile_id: profileId || null };
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/profile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`BOOK_PROFILE_BIND_FAILED:${res.status}`);
    setSelectedBookProfileId(profileId || "");
    await loadBooks();
    await loadBookProfilesMeta();
    if (profileId) await loadProfileVersions(profileId);
    setStatus(profileId ? `Book profile bound: ${profileId}` : "Book profile cleared");
  }

  async function learnProfileFromCurrentBook() {
    if (!bookId || !selectedBookProfileId) return;
    setProfileLearning(true);
    try {
      const res = await fetch(`${baseUrl}/v1/profiles/actions/learn_from_texts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile_id: selectedBookProfileId,
          book_id: bookId,
          mode: "merge",
        }),
      });
      if (!res.ok) throw new Error(`PROFILE_LEARN_FAILED:${res.status}`);
      const out = await res.json();
      setStatus(`Profile learned -> v${out.new_version || "?"}: ${JSON.stringify(out.diff || {})}`);
      await loadProfilesList();
      await loadProfileVersions(selectedBookProfileId);
    } finally {
      setProfileLearning(false);
    }
  }

  async function loadSplitbooks() {
    const res = await fetch(`${baseUrl}/v1/splitbooks?limit=100`);
    if (!res.ok) throw new Error(`SPLITBOOKS_LOAD_FAILED:${res.status}`);
    const data = await res.json();
    const items = (data.items || []) as SplitbookItem[];
    setSplitbooks(items);
    if (items.length && !selectedSplitbookId) setSelectedSplitbookId(items[0].splitbook_id);
  }

  async function createSplitbookFromUi() {
    if (!splitbookName.trim()) return;
    const res = await fetch(`${baseUrl}/v1/splitbooks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: splitbookName.trim(), author: splitbookAuthor.trim() || null, source_path: splitbookPath.trim() || null }),
    });
    if (!res.ok) throw new Error(`SPLITBOOK_CREATE_FAILED:${res.status}`);
    const row = await res.json();
    setSplitbookName("");
    setSplitbookAuthor("");
    setSelectedSplitbookId(row.splitbook_id);
    await loadSplitbooks();
    setStatus(`Splitbook created: ${row.name}`);
  }

  async function triggerSplitbookJob(kind: "ingest" | "embed" | "build_templates" | "build_profile") {
    if (!selectedSplitbookId) return;
    const body =
      kind === "ingest"
        ? { path: splitbookPath.trim(), encoding: "utf-8", chunk_size: splitbookChunkSize, overlap: splitbookOverlap }
        : kind === "embed"
          ? { model: activeProviderConfig.embedding_model || "bge-m3:latest", batch: 64 }
          : kind === "build_templates"
            ? { mode: "merge" }
            : { mode: "create", name: `参考风格-${selectedSplitbook?.name || "splitbook"}` };
    const res = await fetch(`${baseUrl}/v1/splitbooks/${selectedSplitbookId}/${kind}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`SPLITBOOK_${kind.toUpperCase()}_FAILED:${res.status}`);
    const out = await res.json();
    setStatus(`${kind} job queued: ${out.job_id}`);
    if (showJobs) await pollJobs();
    return out;
  }

  async function waitJobTerminal(jobId: string, maxMs = 10 * 60 * 1000) {
    const started = Date.now();
    while (Date.now() - started < maxMs) {
      const res = await fetch(`${baseUrl}/v1/jobs/${encodeURIComponent(jobId)}`);
      if (!res.ok) throw new Error(`JOB_STATUS_FAILED:${res.status}`);
      const out = await res.json();
      const status = String(out?.status || "").toLowerCase();
      if (status === "succeeded" || status === "done") return out;
      if (status === "failed" || status === "canceled" || status === "cancelled") {
        throw new Error(`JOB_FAILED:${jobId}:${status}`);
      }
      await new Promise((r) => setTimeout(r, 600));
    }
    throw new Error(`JOB_TIMEOUT:${jobId}`);
  }

  async function runSplitbookPipeline() {
    if (!selectedSplitbookId) {
      setStatus("Splitbook pipeline skipped: no splitbook selected");
      return;
    }
    const ingest = await triggerSplitbookJob("ingest");
    if (ingest?.job_id) await waitJobTerminal(String(ingest.job_id));
    const embed = await triggerSplitbookJob("embed");
    if (embed?.job_id) await waitJobTerminal(String(embed.job_id));
    const tpl = await triggerSplitbookJob("build_templates");
    if (tpl?.job_id) await waitJobTerminal(String(tpl.job_id));
    const profile = await triggerSplitbookJob("build_profile");
    if (profile?.job_id) await waitJobTerminal(String(profile.job_id));
  }

  async function runUnifiedDesktopFlow() {
    if (flowBusy) return;
    if (!bookId || !chapterId || !quickVolumeId.trim()) {
      setStatus("Unified Flow 需要 book_id + chapter_id + volume_id");
      return;
    }
    setFlowBusy(true);
    setFlowSteps({ splitbook: flowAutoSplitbook ? "running" : "idle", smart: "idle", preflight: "idle" });
    try {
      if (flowAutoSplitbook) {
        await runSplitbookPipeline();
        setFlowSteps((m) => ({ ...m, splitbook: "ok" }));
      }
      setFlowSteps((m) => ({ ...m, smart: "running" }));
      await quickRunSmart();
      setFlowSteps((m) => ({ ...m, smart: "ok", preflight: "running" }));
      const pf = await window.desktopApi.preflightRun({
        book_id: bookId,
        volume_id: quickVolumeId.trim(),
        write_report: false,
      });
      setStatus(`Unified Flow 完成（preflight=${String(pf?.report?.summary?.overall || "unknown")}）`);
      setFlowSteps((m) => ({ ...m, preflight: "ok" }));
    } catch (e: any) {
      const msg = String(e?.message || e);
      setStatus(msg);
      setFlowSteps((m) => {
        const next = { ...m };
        for (const k of Object.keys(next)) {
          if (next[k] === "running") next[k] = "failed";
        }
        return next;
      });
    } finally {
      setFlowBusy(false);
    }
  }

  async function setSplitbookAllowGuard(allowGuard: boolean) {
    if (!selectedSplitbookId) return;
    const res = await fetch(`${baseUrl}/v1/splitbooks/${selectedSplitbookId}/allow_guard`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ allow_guard: allowGuard }),
    });
    if (!res.ok) throw new Error(`SPLITBOOK_ALLOW_GUARD_FAILED:${res.status}`);
    await loadSplitbooks();
    setStatus(`allow_guard=${allowGuard}`);
  }

  async function exportSplitbookDiagnose() {
    if (!selectedSplitbookId) return;
    const res = await fetch(`${baseUrl}/v1/splitbooks/${selectedSplitbookId}/diagnose_bundle?limit=50`);
    if (!res.ok) throw new Error(`SPLITBOOK_DIAGNOSE_FAILED:${res.status}`);
    const bundle = await res.json();
    const stem = `splitbook_diagnose_${selectedSplitbookId}_${new Date().toISOString().replace(/[:.]/g, "-")}`;
    const saved = await window.desktopApi.saveDiagnoseBundle(stem, bundle);
    const target = saved.zipPath || saved.directoryPath;
    setStatus(`Diagnose saved: ${target}`);
    await window.desktopApi.openPath(target, true);
  }

  async function loadChapters(currentBookId = bookId) {
    if (!currentBookId) {
      setChapterItems([]);
      return;
    }
    const q = encodeURIComponent(chapterQuery.trim());
    const res = await fetch(`${baseUrl}/v1/books/${currentBookId}/chapters?query=${q}&limit=200`);
    if (!res.ok) throw new Error(`CHAPTERS_LOAD_FAILED:${res.status}`);
    const data = await res.json();
    setChapterItems((data.chapters || []) as ChapterItem[]);
  }

  async function createBookFromLibrary() {
    if (!newBookName.trim()) return;
    const res = await fetch(`${baseUrl}/v1/books`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newBookName.trim(), language: "zh" }),
    });
    if (!res.ok) throw new Error(`BOOK_CREATE_FAILED:${res.status}`);
    const row = (await res.json()) as BookItem;
    setNewBookName("");
    setBookId(row.book_id);
    setStatus(`Book created: ${row.title}`);
    await loadBooks();
    await loadChapters(row.book_id);
  }

  async function createChapterFromLibrary() {
    if (!bookId) return;
    const payload = {
      chapter_no: Number(newChapterNo),
      title: newChapterTitle.trim() || `第${newChapterNo}章`,
      arc_id: newChapterArcId || null,
      arc_index: Number(newChapterArcIndex) || null,
    };
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/chapters`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`CHAPTER_CREATE_FAILED:${res.status}`);
    const row = (await res.json()) as ChapterItem;
    setChapterId(row.chapter_id);
    setStatus(`Chapter created: ${row.chapter_no}`);
    await loadChapters(bookId);
  }

  async function saveOutline(note?: string) {
    if (!outline || !chapterId) return;
    setBusy(true);
    setStatus("Saving outline...");
    try {
      const res = await fetch(`${baseUrl}/v1/chapters/${chapterId}/outline_detail/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ outline, note: note || "manual edit" })
      });
      if (!res.ok) throw new Error(`OUTLINE_SAVE_FAILED:${res.status}`);
      setDirty(false);
      await loadOutline("latest");
      setStatus("Saved new version");
    } catch (err) {
      setStatus(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function runEval() {
    if (!chapterId) return;
    setBusy(true);
    setStatus("Creating eval job...");
    try {
      const evalRes = await fetch(`${baseUrl}/v1/chapters/${chapterId}/tension/eval`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chapter_version_id: "00000000-0000-0000-0000-000000000000",
          input_mode: "outline",
          schema_ver: 1,
          profile_id: selectedBookProfileId || undefined,
        })
      });
      if (!evalRes.ok) throw new Error(`EVAL_START_FAILED:${evalRes.status}`);
      const evalJob = (await evalRes.json()) as { job_id: string };

      await waitJobDone(baseUrl, evalJob.job_id, (job) => setStatus(`Eval ${job.progress?.phase || "running"} ${job.progress?.pct || 0}%`));

      const srRes = await fetch(`${baseUrl}/v1/skill_runs/latest?chapter_id=${encodeURIComponent(chapterId)}&skill_name=EVAL_CONFLICT_TENSION_V1`);
      if (!srRes.ok) throw new Error("EVAL_RESULT_NOT_FOUND");
      const sr: SkillRun = await srRes.json();
      setEvalRun(sr);
      setStatus("Eval completed");
    } catch (err) {
      setStatus(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function runControlPlan() {
    if (!chapterId) return;
    setBusy(true);
    setStatus("Creating control plan job...");
    try {
      const res = await fetch(`${baseUrl}/v1/chapters/${chapterId}/tension/control_plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          targets,
          style,
          schema_ver: 1,
          material_refs: materialRefs,
          profile_id: selectedBookProfileId || undefined,
        })
      });
      if (!res.ok) throw new Error(`CONTROL_PLAN_START_FAILED:${res.status}`);
      const job = (await res.json()) as { job_id: string };

      await waitJobDone(baseUrl, job.job_id, (j) => setStatus(`Control ${j.progress?.phase || "running"} ${j.progress?.pct || 0}%`));

      const srRes = await fetch(`${baseUrl}/v1/skill_runs/latest?chapter_id=${encodeURIComponent(chapterId)}&skill_name=TENSION_CONTROL_PLAN_V1`);
      if (!srRes.ok) throw new Error("CONTROL_PLAN_NOT_FOUND");
      const sr: SkillRun = await srRes.json();
      setPlanRun(sr);

      const patches = (((sr.output || {}).result || {}).patches || []) as any[];
      const selected: Record<string, boolean> = {};
      for (const p of patches) {
        if (p.patch_id) selected[p.patch_id] = true;
      }
      setSelectedPatches(selected);
      setStatus(`Control plan ready: ${patches.length} patches`);
    } catch (err) {
      setStatus(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function runBookTensionAnalyze() {
    if (!bookId) return;
    setBusy(true);
    setStatus("Creating book tension analyze job...");
    try {
      const res = await fetch(`${baseUrl}/v1/books/${bookId}/tension/analyze`, { method: "POST" });
      if (!res.ok) throw new Error(`BOOK_ANALYZE_START_FAILED:${res.status}`);
      const job = (await res.json()) as { job_id: string };
      await waitJobDone(baseUrl, job.job_id, (j) => setStatus(`Book analyze ${j.progress?.phase || "running"} ${j.progress?.pct || 0}%`));
      await loadBookTensionReport();
      setStatus("Book tension analysis completed");
    } catch (err) {
      setStatus(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function loadBookTensionReport() {
    if (!bookId) return;
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/tension/report?latest=1`);
    if (!res.ok) throw new Error(`BOOK_REPORT_FAILED:${res.status}`);
    const data = await res.json();
    setBookTensionReport(data.output || null);
    await loadArcTargets();
  }

  async function loadArcTargets() {
    if (!bookId) return;
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/arc_targets`);
    if (!res.ok) throw new Error(`ARC_TARGETS_FAILED:${res.status}`);
    const data = await res.json();
    setArcTargets(data.items || []);
  }

  async function saveArcTarget() {
    if (!bookId) return;
    const body = {
      arc_id: arcTargetForm.arc_id,
      target_shape: arcTargetForm.target_shape,
      target_points: arcTargetForm.target_points,
      weights: arcTargetForm.weights
    };
    const res = await fetch(`${baseUrl}/v1/books/${bookId}/arc_targets`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    if (!res.ok) throw new Error(`SAVE_ARC_TARGET_FAILED:${res.status}`);
    setStatus(`Arc target saved: ${arcTargetForm.arc_id}`);
    await loadArcTargets();
  }

  async function loadOutlineDiff() {
    if (!chapterId || !compareFrom || !compareTo) return;
    const res = await fetch(`${baseUrl}/v1/chapters/${chapterId}/outline_detail/diff?from=${compareFrom}&to=${compareTo}`);
    if (!res.ok) throw new Error(`DIFF_FAILED:${res.status}`);
    const data = await res.json();
    setCompareDiff(data);
  }

  async function loadEvalCompare() {
    if (!chapterId || !evalBeforeRun || !evalAfterRun) return;
    const res = await fetch(`${baseUrl}/v1/chapters/${chapterId}/eval/compare?before_run_id=${evalBeforeRun}&after_run_id=${evalAfterRun}`);
    if (!res.ok) throw new Error(`EVAL_COMPARE_FAILED:${res.status}`);
    const data = await res.json();
    setEvalCompare(data);
  }

  async function requestChapterRevisionReport() {
    if (!bookId || !chapterId || !compareFrom || !compareTo || !evalBeforeRun || !evalAfterRun) return;
    const res = await fetch(`${baseUrl}/v1/reports/chapter_revision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        book_id: bookId,
        chapter_id: chapterId,
        from_version: compareFrom,
        to_version: compareTo,
        before_eval_run_id: evalBeforeRun,
        after_eval_run_id: evalAfterRun,
        include_similarity_guard: false
      })
    });
    if (!res.ok) throw new Error(`REPORT_EXPORT_FAILED:${res.status}`);
    return (await res.json()) as { report_id?: string; html?: string };
  }

  async function exportChapterRevisionHtml() {
    const data = await requestChapterRevisionReport();
    if (!data) return;
    setReportHtml(data.html || "");
    setReportPdfPath("");
    setStatus(`Report exported: ${data.report_id || "n/a"}`);
  }

  async function exportChapterRevisionPdf() {
    const data = await requestChapterRevisionReport();
    if (!data?.html) throw new Error("REPORT_HTML_EMPTY");
    const stem = `chapter-revision-${chapterId || "report"}-v${compareFrom}-v${compareTo}`;
    const out = await window.desktopApi.exportPdf(data.html, stem);
    setReportHtml(data.html);
    setReportPdfPath(out.pdfPath);
    setStatus(`PDF exported: ${out.pdfPath}`);
  }

  async function openReportFolder() {
    if (!reportPdfPath) return;
    const out = await window.desktopApi.openPath(reportPdfPath, true);
    if (!out.ok) {
      throw new Error(`OPEN_PATH_FAILED:${out.error || "unknown"}`);
    }
  }

  async function loadLatestChapterReport() {
    if (!chapterId) return;
    const res = await fetch(`${baseUrl}/v1/chapters/${chapterId}/report/latest?report_type=draft_commit`);
    if (!res.ok) throw new Error(`CHAPTER_REPORT_LOAD_FAILED:${res.status}`);
    const out = await res.json();
    setLatestChapterReport(out);
    setStatus(`Latest report loaded: ${out.report_id || "-"}`);
  }

  async function openProfileVersionFromReport(profileId: string, version: number) {
    if (!profileId || !version) return;
    setShowSettings(true);
    setSelectedBookProfileId(profileId);
    await loadProfilesList();
    await loadProfileVersions(profileId);
    await openProfileVersionSnapshot(profileId, version);
    setProfileDiffTo(version);
    setProfileDiffFrom(version > 1 ? version - 1 : version);
    setFocusProfileVersion(version);
    setStatus(`Opened profile ${profileId} v${version}`);
  }

  useEffect(() => {
    if (!focusProfileVersion) return;
    const id = `profile-version-${focusProfileVersion}`;
    const el = document.getElementById(id);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.add("flash");
    const t = window.setTimeout(() => {
      el.classList.remove("flash");
      setFocusProfileVersion(0);
    }, 1100);
    return () => window.clearTimeout(t);
  }, [focusProfileVersion, profileVersions]);

  function closeGlobalSearch() {
    setSearchOpen(false);
    setSearchQuery("");
    setSearchItems([]);
    setSearchSelectedIndex(0);
  }

  async function openSkillRunInJobs(skillRunId: string) {
    setShowJobs(true);
    setJobTab("succeeded");
    setJobSkillRunFilter(skillRunId);
    const res = await fetch(`${baseUrl}/v1/jobs?status=succeeded&limit=200`);
    if (!res.ok) throw new Error(`JOB_LIST_FAILED:${res.status}`);
    const data = await res.json();
    const items = ((data.items || data.jobs || []) as JobItem[]) ?? [];
    setJobs(items);
    const found =
      items.find((j) => String((j.result as any)?.skill_run_id || "") === skillRunId) ||
      items.find((j) => String((j as any).run_id || "") === skillRunId) ||
      null;
    setSelectedJob(found);
    if (found) {
      setStatus(`Opened skill_run in Job Center: ${skillRunId}`);
      window.setTimeout(() => {
        const el = document.querySelector(`[data-job-id="${found.job_id}"]`) as HTMLElement | null;
        el?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 80);
    } else {
      setStatus(`skill_run not found in recent succeeded jobs: ${skillRunId}`);
    }
  }

  async function applyGlobalSearchItem(item: GlobalSearchItem | undefined) {
    if (!item) return;
    if (item.type === "book") {
      setBookId(item.id);
      setChapterId("");
      setStatus(`Selected book: ${item.title}`);
      closeGlobalSearch();
      return;
    }
    if (item.type === "chapter") {
      if (item.book_id) setBookId(item.book_id);
      setChapterId(item.id);
      setStatus(`Open chapter: ${item.title}`);
      closeGlobalSearch();
      return;
    }
    if (item.type === "material") {
      setStatus(`Material selected: ${item.title}`);
      closeGlobalSearch();
      return;
    }
    if (item.type === "skill_run") {
      await openSkillRunInJobs(item.id);
      closeGlobalSearch();
    }
  }

  async function applyLibrarySearchItem(item: GlobalSearchItem | undefined) {
    if (!item) return;
    if (item.type === "book") {
      setBookId(item.id);
      setChapterId("");
      setStatus(`Selected book: ${item.title}`);
      return;
    }
    if (item.type === "chapter") {
      if (item.book_id) setBookId(item.book_id);
      setChapterId(item.id);
      setStatus(`Open chapter: ${item.title}`);
      return;
    }
    if (item.type === "skill_run") {
      await openSkillRunInJobs(item.id);
      return;
    }
    setStatus(`Material selected: ${item.title}`);
  }

  async function searchTemplateAssets() {
    const params = new URLSearchParams();
    if (templateType.trim()) params.set("type", templateType.trim());
    if (templateTag.trim()) params.set("tag", templateTag.trim());
    if (templateQuery.trim()) params.set("q", templateQuery.trim());
    params.set("limit", "50");
    params.set("offset", "0");

    setTemplateLoading(true);
    try {
      const res = await fetch(`${baseUrl}/v1/templates?${params.toString()}`);
      if (!res.ok) throw new Error(`TEMPLATE_LIST_FAILED:${res.status}`);
      const data = await res.json();
      const items = (data.items || []) as TemplateAssetItem[];
      setTemplateItems(items);
      setTemplateSelected((prev) => {
        if (!items.length) return null;
        if (!prev) return items[0];
        return items.find((x) => x.asset_id === prev.asset_id) || items[0];
      });
      setStatus(`Templates loaded: ${items.length}`);
    } catch (err) {
      setStatus(String(err));
    } finally {
      setTemplateLoading(false);
    }
  }

  async function addTemplateAssetToRefInbox(assetId: string, note?: string, name?: string) {
    if (!chapterId) {
      setStatus("请选择章节后再加入 TemplateRef");
      return;
    }
    if (!assetId) return;
    const res = await fetch(`${baseUrl}/v1/chapters/${chapterId}/ref_inbox/from_template`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ asset_id: assetId, note: note?.trim() || null }),
    });
    if (!res.ok) throw new Error(`TEMPLATE_REF_CREATE_FAILED:${res.status}`);
    const out = await res.json();
    const refBlock = String(out.ref_block || "");
    if (refBlock) {
      setMaterialRefs((prev) => [refBlock, ...prev].slice(0, 20));
    }
    setStatus(`Template ref added: ${name || assetId}`);
  }

  async function addTemplateToRefInbox() {
    if (!templateSelected?.asset_id) return;
    await addTemplateAssetToRefInbox(templateSelected.asset_id, templateNote, templateSelected.name);
  }

  async function addMaterialCardToRefInbox(cardId: string, title?: string) {
    if (!chapterId) {
      setStatus("请选择章节后再加入 MaterialRef");
      return;
    }
    const res = await fetch(`${baseUrl}/v1/chapters/${chapterId}/ref_inbox/from_material`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        card_id: cardId,
        context: { need: "本章补强冲突/反转/代价" },
      }),
    });
    if (!res.ok) throw new Error(`MATERIAL_REF_CREATE_FAILED:${res.status}`);
    const out = await res.json();
    const refBlock = String(out.ref_block || "");
    if (refBlock) {
      setMaterialRefs((prev) => [refBlock, ...prev].slice(0, 20));
    }
    setStatus(`Material ref added: ${title || cardId}`);
  }

  async function searchRefUnified() {
    const q = refUnifiedQuery.trim();
    if (!q) {
      setRefUnifiedItems([]);
      return;
    }
    setRefUnifiedLoading(true);
    try {
      const templateParams = new URLSearchParams();
      templateParams.set("q", q);
      templateParams.set("limit", "10");
      templateParams.set("offset", "0");
      const templateReq = fetch(`${baseUrl}/v1/templates?${templateParams.toString()}`);

      const materialPayload: Record<string, unknown> = { query_text: q, k: 10 };
      if (bookId) materialPayload.book_id = bookId;
      const materialReq = fetch(`${baseUrl}/v1/materials/knn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(materialPayload),
      });

      const [templateRes, materialRes] = await Promise.all([templateReq, materialReq]);
      if (!templateRes.ok) throw new Error(`TEMPLATE_SEARCH_FAILED:${templateRes.status}`);
      if (!materialRes.ok) throw new Error(`MATERIAL_SEARCH_FAILED:${materialRes.status}`);
      const templateData = await templateRes.json();
      const materialData = await materialRes.json();

      const templateItemsMapped: RefUnifiedItem[] = ((templateData.items || []) as TemplateAssetItem[]).map((x) => ({
        kind: "template",
        id: x.asset_id,
        title: x.name,
        subtitle: `${x.asset_type}${x.tags?.length ? ` · ${x.tags.slice(0, 3).join("/")}` : ""}`,
        score: 0.5,
      }));
      const materialItemsMapped: RefUnifiedItem[] = ((materialData.items || []) as any[]).map((x) => ({
        kind: "material",
        id: String(x.card_id || ""),
        title: String(x.title || ""),
        subtitle: `${String(x.tag || "-")} · imp=${Number(x.importance || 0)}`,
        score: Number(x.score || 0),
      }));

      const merged = [...materialItemsMapped, ...templateItemsMapped].sort((a, b) => b.score - a.score).slice(0, 20);
      setRefUnifiedItems(merged);
      setStatus(`Ref search loaded: ${merged.length}`);
    } catch (err) {
      setStatus(String(err));
    } finally {
      setRefUnifiedLoading(false);
    }
  }

  async function evolveTemplates() {
    const res = await fetch(`${baseUrl}/v1/templates/evolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ book_id: bookId || null, min_samples: 8, min_mean_overall: 0.05 })
    });
    if (!res.ok) throw new Error(`EVOLVE_FAILED:${res.status}`);
    const job = await res.json();
    await waitJobDone(baseUrl, job.job_id, (j) => setStatus(`Evolve ${j.progress?.phase || "running"} ${j.progress?.pct || 0}%`));
    setStatus("Template evolve completed");
    await loadVariants();
  }

  async function loadVariants() {
    const res = await fetch(`${baseUrl}/v1/templates/variants?enabled=all`);
    if (!res.ok) throw new Error(`LOAD_VARIANTS_FAILED:${res.status}`);
    const data = await res.json();
    setVariants(data.items || []);
  }

  async function setVariantEnabled(variantId: string, enabled: boolean, weight?: number) {
    const endpoint = enabled ? "enable" : "disable";
    const res = await fetch(`${baseUrl}/v1/templates/variants/${variantId}/${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: enabled ? JSON.stringify({ enabled: true, weight: weight ?? 0.1 }) : "{}"
    });
    if (!res.ok) throw new Error(`VARIANT_TOGGLE_FAILED:${res.status}`);
    await loadVariants();
  }

  async function createRepairPlan() {
    if (!bookId) return;
    setBusy(true);
    setStatus("Creating repair plan jobs...");
    try {
      const res = await fetch(`${baseUrl}/v1/books/${bookId}/tension/repair_plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ targets, style })
      });
      if (!res.ok) throw new Error(`REPAIR_PLAN_FAILED:${res.status}`);
      const data = await res.json();
      setStatus(`Repair plan created: ${data.jobs_created} jobs`);
      if (showJobs) await pollJobs();
    } catch (err) {
      setStatus(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function applySelectedPatches() {
    if (!chapterId || !planRun) return;
    const patchIds = Object.entries(selectedPatches).filter(([, checked]) => checked).map(([id]) => id);
    if (!patchIds.length) return;

    setBusy(true);
    setStatus("Applying selected patches...");
    try {
      const res = await fetch(`${baseUrl}/v1/chapters/${chapterId}/outline_detail/apply_patches`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_skill_run_id: planRun.skill_run_id, selected_patch_ids: patchIds, auto_eval: true, targets, style })
      });
      if (!res.ok) throw new Error(`APPLY_PATCHES_FAILED:${res.status}`);
      const created = await res.json();
      const applyJobId = created.apply_job_id as string;
      if (applyJobId) {
        await waitJobDone(baseUrl, applyJobId, (j) => setStatus(`Apply+Measure ${j.progress?.phase || "running"} ${j.progress?.pct || 0}%`));
      }
      await loadOutline("latest");
      setStatus("Applied + measured. New outline version created");
    } catch (err) {
      setStatus(String(err));
    } finally {
      setBusy(false);
    }
  }

  function updateNodeSummary(value: string) {
    if (!outline || !selectedNodeId) return;
    setOutline({ ...outline, nodes: outline.nodes.map((n) => (n.node_id === selectedNodeId ? { ...n, summary: value } : n)) });
    setDirty(true);
  }

  async function pollJobs() {
    const fetchJobs = async (status: string, limit = 30): Promise<JobItem[]> => {
      const res = await fetch(`${baseUrl}/v1/jobs?status=${status}&limit=${limit}`);
      if (!res.ok) throw new Error(`JOB_LIST_FAILED:${res.status}:${status}`);
      const data = await res.json();
      return ((data.items || data.jobs || []) as JobItem[]) ?? [];
    };

    const running = await fetchJobs("running", 50);
    const succeeded = await fetchJobs("succeeded", 30);
    const failed = await fetchJobs("failed", 30);
    const sbRunning = running.filter((j) => String(j.capability_id || "").startsWith("splitbook."));
    setSplitbookRunningJobs(sbRunning);

    const byTab: Record<string, JobItem[]> = { running, succeeded, failed };
    const tabItemsRaw = byTab[jobTab] || running;
    const needle = jobSkillRunFilter.trim();
    const tabItems = needle
      ? tabItemsRaw.filter((j) => extractSkillRunId(j).toLowerCase().includes(needle.toLowerCase()))
      : tabItemsRaw;
    setJobs(tabItems);

    if (selectedJob) {
      const merged = [...running, ...succeeded, ...failed];
      const next = merged.find((j) => j.job_id === selectedJob.job_id) || null;
      setSelectedJob(next);
    }

    if (!pollInitializedRef.current) {
      for (const j of [...succeeded, ...failed]) {
        seenJobIdsRef.current.add(j.job_id);
      }
      pollInitializedRef.current = true;
      return running.length > 0;
    }

    const handleDone = async (job: JobItem) => {
      const jobType = String(job.job_type || "").toUpperCase();
      const result = (job.result || {}) as Record<string, any>;
      const payload = (job.payload || {}) as Record<string, any>;
      const cid = String(payload.chapter_id || job.chapter_id || chapterId || "");

      if (jobType.includes("EVAL")) {
        const runId = String(result.skill_run_id || "");
        if (runId) {
          setEvalBeforeRun(runId);
          const srRes = await fetch(`${baseUrl}/v1/skill_runs/${runId}`);
          if (srRes.ok) setEvalRun(await srRes.json());
          setStatus(`EVAL done: ${runId}`);
        }
        return;
      }

      if (jobType.includes("PLAN")) {
        const runId = String(result.skill_run_id || "");
        if (runId) {
          const srRes = await fetch(`${baseUrl}/v1/skill_runs/${runId}`);
          if (srRes.ok) {
            const sr: SkillRun = await srRes.json();
            setPlanRun(sr);
            const patches = (((sr.output || {}).result || {}).patches || []) as any[];
            const selected: Record<string, boolean> = {};
            for (const p of patches) if (p.patch_id) selected[p.patch_id] = true;
            setSelectedPatches(selected);
          }
          setStatus(`PLAN done: ${runId}`);
        }
        return;
      }

      if (jobType.includes("APPLY")) {
        const newVersion = Number(result.new_outline_version || 0);
        const oldVersion = Number(result.old_outline_version || (newVersion > 0 ? newVersion - 1 : 0));
        const beforeRun = String(result.before_eval_run_id || "");
        const afterRun = String(result.after_eval_run_id || "");

        if (beforeRun) setEvalBeforeRun(beforeRun);
        if (afterRun) setEvalAfterRun(afterRun);

        if (cid && newVersion > 0) {
          const detailRes = await fetch(`${baseUrl}/v1/chapters/${cid}/outline_detail?version=${newVersion}`);
          if (detailRes.ok) {
            const detail = await detailRes.json();
            setOutline(detail.content || { nodes: [] });
            setSelectedVersion(String(newVersion));
            setCompareFrom(oldVersion > 0 ? oldVersion : compareFrom);
            setCompareTo(newVersion);
            setStatus(`APPLY done: outline v${newVersion}`);
          }
        }

        if (cid && beforeRun && afterRun) {
          const cmpRes = await fetch(`${baseUrl}/v1/chapters/${cid}/eval/compare?before_run_id=${beforeRun}&after_run_id=${afterRun}`);
          if (cmpRes.ok) setEvalCompare(await cmpRes.json());
        }

        if (cid && oldVersion > 0 && newVersion > 0) {
          const diffRes = await fetch(`${baseUrl}/v1/chapters/${cid}/outline_detail/diff?from=${oldVersion}&to=${newVersion}`);
          if (diffRes.ok) setCompareDiff(await diffRes.json());
        }
        setCompareUnread(true);
        return;
      }

      if (jobType.includes("SPLITBOOK") || String(job.capability_id || "").startsWith("splitbook.")) {
        await loadSplitbooks().catch(() => {});
        setStatus(`Splitbook job done: ${job.job_type}`);
      }
    };

    for (const j of succeeded) {
      if (!seenJobIdsRef.current.has(j.job_id)) {
        seenJobIdsRef.current.add(j.job_id);
        await handleDone(j);
      }
    }

    for (const j of failed) {
      if (!seenJobIdsRef.current.has(j.job_id)) {
        seenJobIdsRef.current.add(j.job_id);
        setStatus(`Job failed: ${j.job_type} ${j.error?.code || ""}`);
        setSelectedJob(j);
        if (String(j.capability_id || "").startsWith("splitbook.")) {
          await loadSplitbooks().catch(() => {});
        }
      }
    }

    return running.length > 0;
  }

  function stopPolling() {
    if (timerRef.current) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }

  function startPolling() {
    stopPolling();
    const tick = async () => {
      try {
        const hasRunning = await pollJobs();
        const interval = hasRunning ? 1000 : 2500;
        timerRef.current = window.setTimeout(tick, interval);
      } catch {
        timerRef.current = window.setTimeout(tick, 3000);
      }
    };
    void tick();
  }

  async function retryJob(job: JobItem) {
    if (!job.capability_id || !job.payload) return;
    setStatus(`Retrying ${job.job_type}...`);
    await createJob(baseUrl, job.capability_id, job.payload as Record<string, unknown>);
    await pollJobs();
  }

  async function openJobInCenter(job: JobItem) {
    const s = String(job.status || "").toLowerCase();
    const tab: "running" | "succeeded" | "failed" = s === "failed" ? "failed" : s === "succeeded" ? "succeeded" : "running";
    setShowJobs(true);
    setJobTab(tab);
    setJobSkillRunFilter("");
    await pollJobs();
    setSelectedJob(job);
    setStatus(`Opened job in center: ${job.job_id}`);
    window.setTimeout(() => {
      const el = document.querySelector(`[data-job-id="${job.job_id}"]`) as HTMLElement | null;
      el?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 80);
  }

  async function loadSettings() {
    const res = await fetch(`${baseUrl}/v1/settings`);
    if (!res.ok) throw new Error(`SETTINGS_LOAD_FAILED:${res.status}`);
    const data = await res.json();
    const merged = {
      ...defaultSettings,
      ...data,
      providers: {
        ...defaultSettings.providers,
        ...(data.providers || {}),
      },
    };
    setSettingsData(syncLegacyOllama(merged));
  }

  async function saveSettings() {
    const payload = syncLegacyOllama(settingsData);
    setSettingsData(payload);
    const res = await fetch(`${baseUrl}/v1/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error(`SETTINGS_SAVE_FAILED:${res.status}`);
    setStatus("Settings saved");
  }

  async function loadScopedSettings(scope: "global" | "book" | "chapter" = settingsScope) {
    let url = `${baseUrl}/v1/settings/global`;
    if (scope === "book") {
      if (!bookId) {
        setScopedSettingsText("{}");
        setStatus("Select book_id first for book scope settings");
        return;
      }
      url = `${baseUrl}/v1/books/${bookId}/settings`;
    } else if (scope === "chapter") {
      if (!chapterId) {
        setScopedSettingsText("{}");
        setStatus("Select chapter_id first for chapter scope settings");
        return;
      }
      url = `${baseUrl}/v1/chapters/${chapterId}/settings`;
    }
    const res = await fetch(url);
    if (!res.ok) throw new Error(`SCOPED_SETTINGS_LOAD_FAILED:${res.status}`);
    const data = await res.json();
    const obj = data.settings || {};
    const txt = JSON.stringify(obj, null, 2);
    setScopedSettingsObj(obj);
    setScopedSettingsText(txt);
    setScopedSettingsSavedText(txt);
    setScopedSettingsParseError("");
  }

  async function saveScopedSettings() {
    let url = `${baseUrl}/v1/settings/global`;
    if (settingsScope === "book") {
      if (!bookId) throw new Error("BOOK_ID_REQUIRED");
      url = `${baseUrl}/v1/books/${bookId}/settings`;
    } else if (settingsScope === "chapter") {
      if (!chapterId) throw new Error("CHAPTER_ID_REQUIRED");
      url = `${baseUrl}/v1/chapters/${chapterId}/settings`;
    }
    let payload: any = {};
    try {
      payload = JSON.parse(scopedSettingsText || "{}");
      setScopedSettingsParseError("");
    } catch {
      setScopedSettingsParseError("INVALID_SETTINGS_JSON");
      throw new Error("INVALID_SETTINGS_JSON");
    }
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`SCOPED_SETTINGS_SAVE_FAILED:${res.status}`);
    await loadScopedSettings(settingsScope);
    if (chapterId) await loadEffectiveSettings();
    setStatus(`Scoped settings saved (${settingsScope})`);
  }

  function setPath(obj: any, path: string, value: any) {
    const parts = path.split(".");
    const out = structuredClone(obj || {});
    let cur = out;
    for (let i = 0; i < parts.length - 1; i++) {
      const k = parts[i];
      if (!cur[k] || typeof cur[k] !== "object") cur[k] = {};
      cur = cur[k];
    }
    cur[parts[parts.length - 1]] = value;
    return out;
  }

  function applyBasicSettingsChange(path: string, value: any) {
    const updated = setPath(scopedSettingsObj || {}, path, value);
    setScopedSettingsObj(updated);
    setScopedSettingsText(JSON.stringify(updated, null, 2));
    setScopedSettingsParseError("");
  }

  async function restoreDefaultScopedTemplate() {
    const res = await fetch(`${baseUrl}/v1/settings/default_template`);
    if (!res.ok) throw new Error(`DEFAULT_TEMPLATE_LOAD_FAILED:${res.status}`);
    const data = await res.json();
    const obj = data.settings || {};
    setScopedSettingsObj(obj);
    setScopedSettingsText(JSON.stringify(obj, null, 2));
    setScopedSettingsParseError("");
    setStatus("Default template loaded (not saved yet)");
  }

  async function loadEffectiveSettings() {
    if (!chapterId) {
      setEffectiveSettingsText("{}");
      setEffectiveSourcesObj({});
      return;
    }
    const res = await fetch(`${baseUrl}/v1/chapters/${chapterId}/settings/effective`);
    if (!res.ok) throw new Error(`EFFECTIVE_SETTINGS_LOAD_FAILED:${res.status}`);
    const data = await res.json();
    setEffectiveSettingsText(JSON.stringify(data, null, 2));
    setEffectiveSourcesObj(data.sources || {});
  }

  async function loadSettingsPresets() {
    const res = await fetch(`${baseUrl}/v1/settings/presets?limit=100`);
    if (!res.ok) throw new Error(`PRESETS_LOAD_FAILED:${res.status}`);
    const data = await res.json();
    setSettingsPresets(Array.isArray(data.items) ? data.items : []);
  }

  async function createSettingsPresetFromCurrent() {
    const name = settingsPresetName.trim();
    if (!name) throw new Error("PRESET_NAME_REQUIRED");
    const description = settingsPresetDesc.trim();
    let settingsValue: any = {};
    try {
      settingsValue = JSON.parse(scopedSettingsText || "{}");
    } catch {
      throw new Error("INVALID_SETTINGS_JSON");
    }
    const res = await fetch(`${baseUrl}/v1/settings/presets`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description, settings: settingsValue }),
    });
    if (!res.ok) throw new Error(`PRESET_CREATE_FAILED:${res.status}`);
    setStatus(`Preset created: ${name}`);
    setSettingsPresetName("");
    setSettingsPresetDesc("");
    await loadSettingsPresets();
  }

  async function applyPresetToCurrentScope(presetId: string) {
    const payload: any = { scope: settingsScope, mode: "merge" };
    if (settingsScope === "book") payload.book_id = bookId;
    if (settingsScope === "chapter") payload.chapter_id = chapterId;
    const res = await fetch(`${baseUrl}/v1/settings/presets/${presetId}/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`PRESET_APPLY_FAILED:${res.status}`);
    setStatus(`Preset applied to ${settingsScope}`);
    await loadScopedSettings(settingsScope);
    if (chapterId) await loadEffectiveSettings();
  }

  async function deletePreset(presetId: string) {
    const res = await fetch(`${baseUrl}/v1/settings/presets/${presetId}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`PRESET_DELETE_FAILED:${res.status}`);
    await loadSettingsPresets();
    setStatus("Preset deleted");
  }

  async function computeSettingsDiff(pair: "global_book" | "book_chapter" | "global_effective" = settingsDiffPair) {
    const src = effectiveSourcesObj || {};
    let a: any = {};
    let b: any = {};
    if (pair === "global_book") {
      a = src.global || {};
      b = src.book || {};
    } else if (pair === "book_chapter") {
      a = src.book || {};
      b = src.chapter || {};
    } else {
      a = src.global || {};
      try {
        const parsed = JSON.parse(effectiveSettingsText || "{}");
        b = parsed.effective || {};
      } catch {
        b = {};
      }
    }
    const res = await fetch(`${baseUrl}/v1/settings/diff`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ a, b }),
    });
    if (!res.ok) throw new Error(`SETTINGS_DIFF_FAILED:${res.status}`);
    const out = await res.json();
    setSettingsDiffRows(Array.isArray(out.changes) ? out.changes : []);
  }

  async function loadSettingsAudit() {
    setSettingsAuditLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("scope", settingsScope);
      if (settingsScope === "book" && bookId) params.set("scope_id", bookId);
      if (settingsScope === "chapter" && chapterId) params.set("scope_id", chapterId);
      params.set("limit", "50");
      const res = await fetch(`${baseUrl}/v1/settings/audit?${params.toString()}`);
      if (!res.ok) throw new Error(`SETTINGS_AUDIT_LOAD_FAILED:${res.status}`);
      const out = await res.json();
      setSettingsAuditRows(Array.isArray(out.items) ? out.items : []);
    } finally {
      setSettingsAuditLoading(false);
    }
  }

  async function rollbackSettingsAuditItem(auditId: string) {
    const res = await fetch(`${baseUrl}/v1/settings/audit/${auditId}/rollback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!res.ok) throw new Error(`SETTINGS_AUDIT_ROLLBACK_FAILED:${res.status}`);
    await loadScopedSettings(settingsScope);
    if (chapterId) await loadEffectiveSettings();
    await loadSettingsAudit();
    setStatus(`Rollback success: ${auditId}`);
  }

  async function openRollbackPreview(item: any) {
    const before = item?.before_settings || {};
    const after = item?.after_settings || {};
    const res = await fetch(`${baseUrl}/v1/settings/diff`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ a: after, b: before }),
    });
    if (!res.ok) throw new Error(`ROLLBACK_PREVIEW_DIFF_FAILED:${res.status}`);
    const out = await res.json();
    setRollbackPreviewDiffRows(Array.isArray(out.changes) ? out.changes : []);
    setRollbackPreviewAudit(item);
  }

  async function confirmRollbackFromPreview() {
    if (!rollbackPreviewAudit?.audit_id) return;
    await rollbackSettingsAuditItem(String(rollbackPreviewAudit.audit_id));
    setRollbackPreviewAudit(null);
    setRollbackPreviewDiffRows([]);
  }

  async function checkHealth() {
    const res = await fetch(`${baseUrl}/v1/health`);
    if (!res.ok) throw new Error(`HEALTH_FAILED:${res.status}`);
    const data = await res.json();
    setHealth(data);
  }

  async function runMaintenance(endpoint: string) {
    const res = await fetch(`${baseUrl}${endpoint}`, { method: "POST" });
    if (!res.ok) throw new Error(`MAINT_FAILED:${res.status}`);
    setStatus(`${endpoint} done`);
    await checkHealth();
  }

  async function quickStartSidecar() {
    try {
      const out = await window.desktopApi.sidecarStart();
      const b = String(out?.baseUrl || "").trim();
      if (b) setBaseUrl(b);
      const h = await window.desktopApi.sidecarHealth();
      if (h?.body && typeof h.body === "object") setHealth(h.body);
      setStatus(`Sidecar started at ${b || "-"}`);
    } catch (err: any) {
      setStatus(String(err?.message || err));
    }
  }

  async function quickDraftRun() {
    if (!bookId || !chapterId) {
      setStatus("Quick Draft Run needs book_id + chapter_id");
      return;
    }
    try {
      const out = await window.desktopApi.draftRun({
        book_id: bookId,
        chapter_id: chapterId,
        intent_confirmed: "Quick Draft Run",
        dry_run: false,
        reuse_if_exists: true,
        force_stub_llm: true,
      });
      setQuickDraftRunOut(out || {});
      const resolvedChapterId = String(out?.output?.commit_result?.chapter_id || "").trim();
      if (resolvedChapterId) setChapterId(resolvedChapterId);
      setStatus(`Quick Draft Run done: ${String(out?.run_id || "-")}`);
    } catch (err: any) {
      setStatus(String(err?.message || err));
    }
  }

  async function quickLoadVersions() {
    if (!chapterId) {
      setStatus("Quick Versions needs chapter_id");
      return;
    }
    try {
      const out = await window.desktopApi.draftListVersions({ chapter_id: chapterId });
      setQuickVersionsOut(out || {});
      const n = Array.isArray(out?.items) ? out.items.length : 0;
      setStatus(`Quick Versions loaded: ${n}`);
    } catch (err: any) {
      setStatus(String(err?.message || err));
    }
  }

  async function quickSelectLatest() {
    if (!chapterId) {
      setStatus("Quick Select needs chapter_id");
      return;
    }
    const items = Array.isArray(quickVersionsOut?.items) ? quickVersionsOut.items : [];
    const first = items[0];
    const draftId = String(first?.draft_id || "").trim();
    if (!draftId) {
      setStatus("No draft version available to select");
      return;
    }
    try {
      const out = await window.desktopApi.draftSelect({
        chapter_id: chapterId,
        draft_id: draftId,
        selected_by: "user",
        reason: "quick select latest",
      });
      setQuickVersionsOut((m: any) => ({ ...(m || {}), selected: out || {} }));
      setStatus(`Quick Select done: ${draftId}`);
    } catch (err: any) {
      setStatus(String(err?.message || err));
    }
  }

  async function quickPublishPack() {
    if (!bookId || !quickVolumeId.trim()) {
      setStatus("Quick Publish needs book_id + volume_id");
      return;
    }
    try {
      const out = await window.desktopApi.exportPublishPack({
        book_id: bookId,
        volume_id: quickVolumeId.trim(),
      });
      setQuickPublishOut(out || {});
      const outputDir = String(out?.output_dir || "").trim();
      if (outputDir && quickAutoOpenFolder) await window.desktopApi.openPath(outputDir, true);
      setStatus(`Quick Publish done: ${outputDir || "-"}`);
    } catch (err: any) {
      setStatus(String(err?.message || err));
    }
  }

  async function quickRunAll() {
    if (quickPipelineBusy) return;
    if (!bookId || !chapterId || !quickVolumeId.trim()) {
      setStatus("One-Click 需要 book_id + chapter_id + volume_id");
      return;
    }
    setQuickPipelineBusy(true);
    setQuickPipelineError(null);
    setQuickFixPreview(null);
    setQuickPipelineSteps({
      sidecar: "running",
      draft: "idle",
      versions: "idle",
      select: "idle",
      publish: "idle",
    });
    try {
      const startOut = await window.desktopApi.sidecarStart();
      const nextBase = String(startOut?.baseUrl || "").trim();
      if (nextBase) setBaseUrl(nextBase);
      setQuickPipelineSteps((m) => ({ ...m, sidecar: "ok", draft: "running" }));

      const draftOut = await window.desktopApi.draftRun({
        book_id: bookId,
        chapter_id: chapterId,
        intent_confirmed: "One-Click Pipeline",
        dry_run: false,
        reuse_if_exists: true,
        force_stub_llm: true,
        idempotency_key: `oneclick-${Date.now()}`,
      });
      setQuickDraftRunOut(draftOut || {});
      setQuickPipelineSteps((m) => ({ ...m, draft: "ok", versions: "running" }));

      const listOut = await window.desktopApi.draftListVersions({ chapter_id: chapterId });
      setQuickVersionsOut(listOut || {});
      const versions = Array.isArray(listOut?.items) ? listOut.items : [];
      setQuickPipelineSteps((m) => ({ ...m, versions: "ok", select: "running" }));

      const latestDraftId = String(versions[0]?.draft_id || "").trim();
      if (!latestDraftId) throw new Error("ONECLICK_NO_DRAFT_VERSION");
      await window.desktopApi.draftSelect({
        chapter_id: chapterId,
        draft_id: latestDraftId,
        selected_by: "user",
        reason: "one-click select latest",
      });
      setQuickPipelineSteps((m) => ({ ...m, select: "ok", publish: "running" }));

      const packOut = await window.desktopApi.exportPublishPack({
        book_id: bookId,
        volume_id: quickVolumeId.trim(),
      });
      setQuickPublishOut(packOut || {});
      const outputDir = String(packOut?.output_dir || "").trim();
      if (outputDir) await window.desktopApi.openPath(outputDir, true);
      setQuickPipelineSteps((m) => ({ ...m, publish: "ok" }));
      setStatus("One-Click 完成");
    } catch (err: any) {
      const msg = String(err?.message || err);
      setStatus(msg);
      setQuickPipelineSteps((m) => {
        const next = { ...m };
        let failedStep = "";
        for (const k of Object.keys(next)) {
          if (next[k] === "running") {
            next[k] = "failed";
            if (!failedStep) failedStep = k;
          }
        }
        if (!failedStep) {
          const order = ["sidecar", "draft", "versions", "select", "publish"];
          for (const s of order) {
            if (next[s] === "idle") {
              failedStep = s;
              break;
            }
          }
        }
        setQuickPipelineError({ step: failedStep || "unknown", message: msg });
        return next;
      });
    } finally {
      setQuickPipelineBusy(false);
    }
  }

  async function quickRunSmart() {
    if (quickPipelineBusy) return;
    if (!bookId || !chapterId || !quickVolumeId.trim()) {
      setStatus("Smart Run 需要 book_id + chapter_id + volume_id");
      return;
    }
    setQuickPipelineBusy(true);
    setQuickPipelineError(null);
    setQuickFixPreview(null);
    setQuickFixExecuteOut(null);
    setQuickPipelineSteps({
      sidecar: "running",
      draft: "idle",
      versions: "idle",
      select: "idle",
      publish: "idle",
    });
    try {
      const runAutoSelectLatest = quickRunMode === "safe_auto" ? true : quickAutoSelectLatest;
      const runAutoPublish = quickRunMode === "safe_auto" ? true : quickAutoPublish;
      const runAutoFixOnPublishFail = quickRunMode === "safe_auto" ? true : quickAutoFixOnPublishFail;
      const runFixMax = Math.max(1, quickAutoFixMax);

      const startOut = await window.desktopApi.sidecarStart();
      const nextBase = String(startOut?.baseUrl || "").trim();
      if (nextBase) setBaseUrl(nextBase);
      setQuickPipelineSteps((m) => ({ ...m, sidecar: "ok", draft: "running" }));

      const draftOut = await window.desktopApi.draftRun({
        book_id: bookId,
        chapter_id: chapterId,
        intent_confirmed: `Smart Run (${quickRunMode})`,
        dry_run: false,
        reuse_if_exists: true,
        force_stub_llm: true,
        idempotency_key: `smartrun-${Date.now()}`,
      });
      setQuickDraftRunOut(draftOut || {});
      if (quickRunMode === "manual_gate") {
        setQuickPipelineSteps((m) => ({ ...m, draft: "ok" }));
        setStatus("Smart Run 已完成到 Draft。后续请人工执行 Versions/Select/Publish。");
        return;
      }

      setQuickPipelineSteps((m) => ({ ...m, draft: "ok", versions: "running" }));
      const listOut = await window.desktopApi.draftListVersions({ chapter_id: chapterId });
      setQuickVersionsOut(listOut || {});
      setQuickPipelineSteps((m) => ({ ...m, versions: "ok", select: runAutoSelectLatest ? "running" : "ok" }));

      if (runAutoSelectLatest) {
        const versions = Array.isArray(listOut?.items) ? listOut.items : [];
        const latestDraftId = String(versions[0]?.draft_id || "").trim();
        if (!latestDraftId) throw new Error("SMARTRUN_NO_DRAFT_VERSION");
        await window.desktopApi.draftSelect({
          chapter_id: chapterId,
          draft_id: latestDraftId,
          selected_by: "user",
          reason: "smart-run select latest",
        });
      }

      if (!runAutoPublish) {
        setQuickPipelineSteps((m) => ({ ...m, select: "ok", publish: "idle" }));
        setStatus("Smart Run 已到 Select。发布留给人工。");
        return;
      }

      setQuickPipelineSteps((m) => ({ ...m, select: "ok", publish: "running" }));
      try {
        const packOut = await window.desktopApi.exportPublishPack({
          book_id: bookId,
          volume_id: quickVolumeId.trim(),
        });
        setQuickPublishOut(packOut || {});
        const outputDir = String(packOut?.output_dir || "").trim();
        if (outputDir && quickAutoOpenFolder) await window.desktopApi.openPath(outputDir, true);
        setQuickPipelineSteps((m) => ({ ...m, publish: "ok" }));
        setStatus("Smart Run 完成");
      } catch (pubErr: any) {
        if (!runAutoFixOnPublishFail) throw pubErr;
        // Auto-fix low-risk items, then retry publish once.
        const planOut = await window.desktopApi.fixwizardPlan({
          book_id: bookId,
          volume_id: quickVolumeId.trim(),
        });
        setQuickFixPreview(planOut || {});
        const fixes = Array.isArray(planOut?.fixes) ? planOut.fixes : [];
        const lowOnly = fixes.filter((x: any) => String(x?.risk || "").toLowerCase() === "low").slice(0, runFixMax);
        if (lowOnly.length > 0) {
          const execOut = await window.desktopApi.fixwizardExecute({
            book_id: bookId,
            volume_id: quickVolumeId.trim(),
            chapter_id: chapterId || undefined,
            selected_fixes: lowOnly.map((x: any) => ({ fix_id: x.fix_id })),
            fixes,
            preflight_summary: planOut?.summary || undefined,
            auto_recheck: true,
          });
          setQuickFixExecuteOut(execOut || {});
        }
        const retryOut = await window.desktopApi.exportPublishPack({
          book_id: bookId,
          volume_id: quickVolumeId.trim(),
        });
        setQuickPublishOut(retryOut || {});
        const outputDir = String(retryOut?.output_dir || "").trim();
        if (outputDir && quickAutoOpenFolder) await window.desktopApi.openPath(outputDir, true);
        setQuickPipelineSteps((m) => ({ ...m, publish: "ok" }));
        setStatus("Smart Run 完成（自动修复后重试发布成功）");
      }
    } catch (err: any) {
      const msg = String(err?.message || err);
      setStatus(msg);
      setQuickPipelineSteps((m) => {
        const next = { ...m };
        let failedStep = "";
        for (const k of Object.keys(next)) {
          if (next[k] === "running") {
            next[k] = "failed";
            if (!failedStep) failedStep = k;
          }
        }
        if (!failedStep) {
          const order = ["sidecar", "draft", "versions", "select", "publish"];
          for (const s of order) {
            if (next[s] === "idle") {
              failedStep = s;
              break;
            }
          }
        }
        setQuickPipelineError({ step: failedStep || "unknown", message: msg });
        return next;
      });
    } finally {
      setQuickPipelineBusy(false);
    }
  }

  function stepColor(status: string): string {
    const s = String(status || "idle");
    if (s === "ok") return "#15803d";
    if (s === "running") return "#b45309";
    if (s === "failed") return "#b91c1c";
    return "#64748b";
  }

  function statusDot(status: string): string {
    const s = String(status || "idle");
    if (s === "ok") return "●";
    if (s === "running") return "◐";
    if (s === "failed") return "✖";
    return "○";
  }

  function riskBadgeStyle(risk: string): { fg: string; bg: string; border: string } {
    const r = String(risk || "").toLowerCase();
    if (r === "low") return { fg: "#166534", bg: "rgba(22,101,52,.08)", border: "rgba(22,101,52,.25)" };
    if (r === "mid" || r === "medium") return { fg: "#9a3412", bg: "rgba(154,52,18,.08)", border: "rgba(154,52,18,.25)" };
    if (r === "high") return { fg: "#991b1b", bg: "rgba(153,27,27,.08)", border: "rgba(153,27,27,.25)" };
    return { fg: "#334155", bg: "rgba(51,65,85,.08)", border: "rgba(51,65,85,.2)" };
  }

  async function retryFailedStep() {
    const step = String(quickPipelineError?.step || "").trim();
    if (!step) return;
    if (step === "sidecar") return void (await quickStartSidecar());
    if (step === "draft") return void (await quickDraftRun());
    if (step === "versions") return void (await quickLoadVersions());
    if (step === "select") return void (await quickSelectLatest());
    if (step === "publish") return void (await quickPublishPack());
    setStatus(`Unknown failed step: ${step}`);
  }

  async function quickFixwizardPlanForPublish() {
    if (!bookId || !quickVolumeId.trim()) {
      setStatus("Fix Wizard 需要 book_id + volume_id");
      return;
    }
    try {
      const out = await window.desktopApi.fixwizardPlan({
        book_id: bookId,
        volume_id: quickVolumeId.trim(),
      });
      setQuickFixPreview(out || {});
      setQuickFixExecuteOut(null);
      setShowAgentConsole(true);
      const n = Array.isArray(out?.fixes) ? out.fixes.length : 0;
      setStatus(`Fix Wizard Plan ready: ${n} fixes`);
    } catch (err: any) {
      setStatus(String(err?.message || err));
    }
  }

  async function quickFixwizardExecuteTop(topN: number) {
    if (!bookId || !quickVolumeId.trim()) {
      setStatus("Fix Execute 需要 book_id + volume_id");
      return;
    }
    const fixes = Array.isArray(quickFixPreview?.fixes) ? quickFixPreview.fixes : [];
    if (fixes.length === 0) {
      setStatus("No fixes to execute.");
      return;
    }
    const riskRank = (r: string): number => {
      const x = String(r || "").toLowerCase();
      if (x === "low") return 0;
      if (x === "mid" || x === "medium") return 1;
      if (x === "high") return 2;
      return 9;
    };
    const sorted = [...fixes].sort((a: any, b: any) => {
      const ra = riskRank(String(a?.risk || ""));
      const rb = riskRank(String(b?.risk || ""));
      if (ra !== rb) return ra - rb;
      return String(a?.title || "").localeCompare(String(b?.title || ""), "zh-CN");
    });
    const selected = sorted.slice(0, Math.max(1, topN));
    try {
      const out = await window.desktopApi.fixwizardExecute({
        book_id: bookId,
        volume_id: quickVolumeId.trim(),
        chapter_id: chapterId || undefined,
        selected_fixes: selected,
        fixes,
        preflight_summary: quickFixPreview?.summary || undefined,
        auto_recheck: true,
      });
      setQuickFixExecuteOut(out || {});
      const s = out?.recheck?.summary || {};
      setStatus(
        `Fix executed(${selected.length}). recheck overall=${String(s.overall || "-")} fail=${String(
          s.fail_count ?? "-"
        )} warn=${String(s.warn_count ?? "-")}`
      );
    } catch (err: any) {
      setStatus(String(err?.message || err));
    }
  }

  async function quickFixwizardExecuteLowRisk(maxN: number) {
    if (!bookId || !quickVolumeId.trim()) {
      setStatus("Fix Execute 需要 book_id + volume_id");
      return;
    }
    const fixes = Array.isArray(quickFixPreview?.fixes) ? quickFixPreview.fixes : [];
    const lowOnly = fixes.filter((x: any) => String(x?.risk || "").toLowerCase() === "low").slice(0, Math.max(1, maxN));
    if (lowOnly.length === 0) {
      setStatus("No low-risk fixes available.");
      return;
    }
    try {
      const out = await window.desktopApi.fixwizardExecute({
        book_id: bookId,
        volume_id: quickVolumeId.trim(),
        chapter_id: chapterId || undefined,
        selected_fixes: lowOnly,
        fixes,
        preflight_summary: quickFixPreview?.summary || undefined,
        auto_recheck: true,
      });
      setQuickFixExecuteOut(out || {});
      const s = out?.recheck?.summary || {};
      setStatus(
        `Low-risk fixes executed(${lowOnly.length}). recheck overall=${String(s.overall || "-")} fail=${String(
          s.fail_count ?? "-"
        )} warn=${String(s.warn_count ?? "-")}`
      );
    } catch (err: any) {
      setStatus(String(err?.message || err));
    }
  }

  function canonicalizeJsonText(txt: string): string | null {
    try {
      const obj = JSON.parse(txt || "{}");
      return JSON.stringify(obj);
    } catch {
      return null;
    }
  }

  const scopedDirty = useMemo(() => {
    const cur = canonicalizeJsonText(scopedSettingsText);
    const saved = canonicalizeJsonText(scopedSettingsSavedText);
    if (cur === null || saved === null) return scopedSettingsText.trim() !== scopedSettingsSavedText.trim();
    return cur !== saved;
  }, [scopedSettingsText, scopedSettingsSavedText]);

  function hasPath(obj: any, path: string): boolean {
    const parts = path.split(".");
    let cur = obj;
    for (const p of parts) {
      if (!cur || typeof cur !== "object" || !(p in cur)) return false;
      cur = cur[p];
    }
    return true;
  }

  function sourceOfPath(path: string): "chapter" | "book" | "global" | "-" {
    const src = effectiveSourcesObj || {};
    if (hasPath(src.chapter || {}, path)) return "chapter";
    if (hasPath(src.book || {}, path)) return "book";
    if (hasPath(src.global || {}, path)) return "global";
    return "-";
  }

  function getPathValue(obj: any, path: string, def: any = undefined) {
    const parts = path.split(".");
    let cur = obj;
    for (const p of parts) {
      if (!cur || typeof cur !== "object" || !(p in cur)) return def;
      cur = cur[p];
    }
    return cur;
  }

  const effectiveSettingsObj = useMemo(() => {
    try {
      const parsed = JSON.parse(effectiveSettingsText || "{}");
      const out = parsed?.effective;
      return out && typeof out === "object" ? out : {};
    } catch {
      return {};
    }
  }, [effectiveSettingsText]);

  const canOverrideCurrentScope =
    settingsScope === "global" ||
    (settingsScope === "book" && !!bookId) ||
    (settingsScope === "chapter" && !!chapterId);

  const basicSourcePaths = [
    "draft.default_words",
    "draft.pov",
    "draft.tone",
    "simguard.enabled",
    "simguard.sim_threshold",
    "simguard.top_k",
    "simguard.scope_default",
    "eval.enabled",
    "eval.targets.hook",
    "eval.targets.conflict",
    "eval.targets.pacing",
    "eval.targets.clarity",
    "eval.targets.character",
    "eval.targets.stakes",
    "eval.targets.foreshadow",
    "eval.targets.payoff",
    "humanize.enabled",
    "humanize.level_default",
    "humanize.remove_cliches",
    "humanize.reduce_ai_markers",
    "autopatch.enabled",
    "autopatch.max_changes",
    "autopatch.max_nodes_touched",
    "autopatch.strictness",
  ];

  function overrideScopedKey(keypath: string, value: any) {
    const updated = setPath(scopedSettingsObj || {}, keypath, value);
    setScopedSettingsObj(updated);
    setScopedSettingsText(JSON.stringify(updated, null, 2));
    setScopedSettingsParseError("");
    setStatus(`Overrode ${keypath} at ${settingsScope} (not saved yet)`);
  }

  useEffect(() => {
    if (!traceMenu) return;
    const close = () => setTraceMenu(null);
    window.addEventListener("click", close);
    window.addEventListener("scroll", close, true);
    return () => {
      window.removeEventListener("click", close);
      window.removeEventListener("scroll", close, true);
    };
  }, [traceMenu]);

  useEffect(() => {
    if (!showJobs && !showSplitbooks) {
      stopPolling();
      return;
    }
    startPolling();
    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showJobs, showSplitbooks, jobTab, baseUrl, jobSkillRunFilter]);

  useEffect(() => {
    if (showSettings) {
      void loadSettings();
      void loadScopedSettings(settingsScope).catch(() => {});
      void loadEffectiveSettings().catch(() => {});
      void loadSettingsPresets().catch(() => {});
      void loadSettingsAudit().catch(() => {});
      void checkHealth();
      void loadProfilesList().catch(() => {});
    }
  }, [showSettings, baseUrl, settingsScope, bookId, chapterId]);

  useEffect(() => {
    if (showSettings && chapterId) {
      void computeSettingsDiff(settingsDiffPair).catch(() => {});
    }
  }, [showSettings, chapterId, effectiveSettingsText, settingsDiffPair]);

  useEffect(() => {
    if (showSplitbooks) {
      void loadSplitbooks().catch(() => {});
    }
  }, [showSplitbooks, baseUrl]);

  useEffect(() => {
    void loadBooks().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseUrl]);

  useEffect(() => {
    if (bookId) {
      void loadChapters(bookId).catch(() => {});
    } else {
      setChapterItems([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookId, chapterQuery, baseUrl]);

  useEffect(() => {
    if (!chapterId) return;
    void loadOutline("latest");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapterId]);

  useEffect(() => {
    if (bookId) {
      void loadArcTargets().catch(() => {});
      void loadVariants().catch(() => {});
    }
  }, [bookId]);

  useEffect(() => {
    if (!bookId) {
      setSelectedBookProfileId("");
      return;
    }
    const cur = bookItems.find((x) => x.book_id === bookId);
    setSelectedBookProfileId(cur?.profile_id ? String(cur.profile_id) : "");
  }, [bookId, bookItems]);

  useEffect(() => {
    if (!showSettings) return;
    if (!selectedBookProfileId) {
      setProfileVersions([]);
      setProfileActiveVersion(0);
      setProfileDiffResult(null);
      setProfileVersionSnapshot(null);
      return;
    }
    void loadProfileVersions(selectedBookProfileId).catch((err) => setStatus(String(err)));
  }, [showSettings, selectedBookProfileId]);

  useEffect(() => {
    if (!showSettings) return;
    if (!bookId) {
      setBookProfileMeta(null);
      return;
    }
    void loadBookProfilesMeta().catch((err) => setStatus(String(err)));
  }, [showSettings, bookId]);

  useEffect(() => {
    if (!abBatchId) return;
    void loadAbBatch(abBatchId).catch((err) => setStatus(String(err)));
    const t = window.setInterval(() => {
      void loadAbBatch(abBatchId).catch(() => {});
    }, 2000);
    return () => window.clearInterval(t);
  }, [abBatchId]);

  useEffect(() => {
    if (!showSettings || !chapterId) return;
    void loadChapterReports().catch((err) => setStatus(String(err)));
  }, [showSettings, chapterId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const isMac = navigator.platform.toLowerCase().includes("mac");
      const openHotkey = (isMac ? e.metaKey : e.ctrlKey) && e.key.toLowerCase() === "k";
      if (openHotkey) {
        e.preventDefault();
        setSearchOpen(true);
      }
      if (searchOpen && e.key === "Escape") {
        e.preventDefault();
        closeGlobalSearch();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [searchOpen]);

  useEffect(() => {
    if (!searchOpen) return;
    const q = searchQuery.trim();
    if (!q) {
      setSearchItems([]);
      setSearchLoading(false);
      setSearchSelectedIndex(0);
      return;
    }
    const timer = window.setTimeout(async () => {
      setSearchLoading(true);
      try {
        const res = await fetch(`${baseUrl}/v1/search?q=${encodeURIComponent(q)}&limit=20`);
        if (!res.ok) throw new Error(`SEARCH_FAILED:${res.status}`);
        const data = await res.json();
        setSearchItems((data.items || []) as GlobalSearchItem[]);
        setSearchSelectedIndex(0);
      } catch (err) {
        setStatus(String(err));
      } finally {
        setSearchLoading(false);
      }
    }, 250);
    return () => window.clearTimeout(timer);
  }, [searchOpen, searchQuery, baseUrl]);

  useEffect(() => {
    const q = librarySearchQuery.trim();
    if (!q) {
      setLibrarySearchItems([]);
      setLibrarySearchLoading(false);
      return;
    }
    const timer = window.setTimeout(async () => {
      setLibrarySearchLoading(true);
      try {
        const res = await fetch(`${baseUrl}/v1/search?q=${encodeURIComponent(q)}&limit=20`);
        if (!res.ok) throw new Error(`SEARCH_FAILED:${res.status}`);
        const data = await res.json();
        setLibrarySearchItems((data.items || []) as GlobalSearchItem[]);
      } catch (err) {
        setStatus(String(err));
      } finally {
        setLibrarySearchLoading(false);
      }
    }, 250);
    return () => window.clearTimeout(timer);
  }, [librarySearchQuery, baseUrl]);

  const patches = (((planRun?.output || {}).result || {}).patches || []) as any[];
  const issues = (((evalRun?.output || {}).result || {}).issues || []) as any[];
  const report = bookTensionReport?.result || {};
  const fatigueZones = report?.book_trends?.fatigue_zones || [];
  const arcSummary = report?.arc_summary || [];
  const diagnosis = report?.diagnosis || [];
  const advanced = report?.advanced || {};
  const arcTargetAnalysis = report?.arc_targets || [];
  const activeProvider = ((settingsData?.ai_provider || "ollama") as ProviderId);
  const activeProviderConfig = getProviderConfig(settingsData, activeProvider);
  const selectedSplitbook = splitbooks.find((x) => x.splitbook_id === selectedSplitbookId) || null;
  const selectedSplitbookJobs = splitbookRunningJobs.filter((j) => {
    const sid = String((j.payload as any)?.splitbook_id || "");
    return sid && sid === selectedSplitbookId;
  });
  const libraryBookHits = librarySearchItems.filter((x) => x.type === "book");
  const libraryChapterHits = librarySearchItems.filter((x) => x.type === "chapter");
  const libraryMaterialHits = librarySearchItems.filter((x) => x.type === "material");
  const librarySkillRunHits = librarySearchItems.filter((x) => x.type === "skill_run");

  return (
    <div className="wb-page">
      <header className="wb-header">
        <h1>Chapter Outline Workbench</h1>
        <div className="row">
          <button onClick={() => setSearchOpen(true)}>Search (Ctrl/Cmd+K)</button>
          <button onClick={() => setShowAgentConsole((v) => !v)}>{showAgentConsole ? "Hide" : "Show"} Agent Console</button>
          <button onClick={() => setShowVersionCenter((v) => !v)}>{showVersionCenter ? "Hide" : "Show"} Versions</button>
          <button onClick={() => setShowRewriteCenter((v) => !v)}>{showRewriteCenter ? "Hide" : "Show"} Rewrite</button>
          <button onClick={() => setShowReleaseCenter((v) => !v)}>{showReleaseCenter ? "Hide" : "Show"} Release</button>
          <button onClick={() => setShowJobs((v) => !v)}>{showJobs ? "Hide" : "Show"} Job Center</button>
          <button onClick={() => setShowRefCenter((v) => !v)}>{showRefCenter ? "Hide" : "Show"} Ref Center</button>
          <button onClick={() => setShowSplitbooks((v) => !v)}>{showSplitbooks ? "Hide" : "Show"} Splitbooks</button>
          <button onClick={() => setShowSettings((v) => !v)}>{showSettings ? "Hide" : "Show"} Settings</button>
          <div className="status">{status}</div>
        </div>
      </header>

      <section className="wb-panel" style={{ minHeight: "auto", marginBottom: 10 }}>
        <h3>Quick Start</h3>
        <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
          <label>
            baseUrl
            <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
          </label>
          <label>
            book_id
            <input value={bookId} onChange={(e) => setBookId(e.target.value)} placeholder="uuid" />
          </label>
          <label>
            chapter_id
            <input value={chapterId} onChange={(e) => setChapterId(e.target.value)} placeholder="uuid" />
          </label>
          <label>
            volume_id
            <input value={quickVolumeId} onChange={(e) => setQuickVolumeId(e.target.value)} placeholder="uuid" />
          </label>
          <label>
            smart_mode
            <select value={quickRunMode} onChange={(e) => setQuickRunMode(e.target.value as any)}>
              <option value="safe_auto">Safe Auto（自动执行低风险，失败自动修复）</option>
              <option value="balanced_auto">Balanced（自动到发布，可选自动修复）</option>
              <option value="manual_gate">Manual Gate（自动到 Draft，其余人工）</option>
            </select>
          </label>
          <label className="small">
            <input type="checkbox" checked={quickAutoSelectLatest} onChange={(e) => setQuickAutoSelectLatest(e.target.checked)} />
            auto select latest
          </label>
          <label className="small">
            <input type="checkbox" checked={quickAutoPublish} onChange={(e) => setQuickAutoPublish(e.target.checked)} />
            auto publish
          </label>
          <label className="small">
            <input type="checkbox" checked={quickAutoFixOnPublishFail} onChange={(e) => setQuickAutoFixOnPublishFail(e.target.checked)} />
            auto low-risk fix on publish fail
          </label>
          <label className="small">
            fix_max
            <input
              style={{ width: 64, marginLeft: 6 }}
              type="number"
              min={1}
              max={10}
              value={quickAutoFixMax}
              onChange={(e) => setQuickAutoFixMax(Math.max(1, Math.min(10, Number(e.target.value) || 1)))}
            />
          </label>
          <label className="small">
            <input type="checkbox" checked={quickAutoOpenFolder} onChange={(e) => setQuickAutoOpenFolder(e.target.checked)} />
            auto open export folder
          </label>
          <button onClick={() => void quickRunSmart()} disabled={quickPipelineBusy}>
            {quickPipelineBusy ? "Smart Running..." : "Smart Run (Unified)"}
          </button>
          <details>
            <summary>Advanced Manual Actions</summary>
            <div className="row" style={{ gap: 8, marginTop: 6, flexWrap: "wrap" }}>
              <button onClick={() => void quickStartSidecar()}>Start Sidecar</button>
              <button onClick={() => void checkHealth()}>Health</button>
              <button onClick={() => void quickDraftRun()}>Draft Run</button>
              <button onClick={() => void quickLoadVersions()}>Load Versions</button>
              <button onClick={() => void quickSelectLatest()}>Select Latest</button>
              <button onClick={() => void quickPublishPack()}>Publish Pack</button>
              <button onClick={() => void quickRunAll()} disabled={quickPipelineBusy}>
                {quickPipelineBusy ? "One-Click Running..." : "Legacy One-Click"}
              </button>
            </div>
          </details>
        </div>
        <div className="row" style={{ gap: 8, marginTop: 6, flexWrap: "wrap" }}>
          <span className="small">unified:</span>
          <label className="small">
            <input type="checkbox" checked={flowAutoSplitbook} onChange={(e) => setFlowAutoSplitbook(e.target.checked)} />
            run splitbook pipeline first
          </label>
          <button onClick={() => void runUnifiedDesktopFlow()} disabled={flowBusy || quickPipelineBusy}>
            {flowBusy ? "Unified Running..." : "Run Unified Flow"}
          </button>
          {(["splitbook", "smart", "preflight"] as const).map((k) => (
            <span key={k} className="small" style={{ color: stepColor(flowSteps[k]) }}>
              {statusDot(flowSteps[k])} {k}={flowSteps[k]}
            </span>
          ))}
        </div>
        <div className="row" style={{ gap: 8, marginTop: 6, flexWrap: "wrap" }}>
          <span className="small">steps:</span>
          {(["sidecar", "draft", "versions", "select", "publish"] as const).map((k) => (
            <span key={k} className="small" style={{ color: stepColor(quickPipelineSteps[k]) }}>
              {statusDot(quickPipelineSteps[k])} {k}={quickPipelineSteps[k]}
            </span>
          ))}
        </div>
        {quickPipelineError ? (
          <div
            className="small"
            style={{
              marginTop: 8,
              border: "1px solid rgba(185,28,28,.35)",
              background: "rgba(185,28,28,.08)",
              borderRadius: 8,
              padding: 8,
              color: "#7f1d1d",
            }}
          >
            <strong>Pipeline failed</strong>
            <div>step: {quickPipelineError.step || "-"}</div>
            <div style={{ whiteSpace: "pre-wrap" }}>{quickPipelineError.message}</div>
            <div className="row" style={{ gap: 8, marginTop: 8, flexWrap: "wrap" }}>
              <button onClick={() => void retryFailedStep()}>Retry Failed Step</button>
              <button onClick={() => setShowAgentConsole(true)}>Open Agent Console</button>
              {String(quickPipelineError.step || "") === "publish" ? (
                <button onClick={() => void quickFixwizardPlanForPublish()}>Fix Wizard Plan</button>
              ) : null}
              {String(quickPipelineError.step || "") === "publish" && Array.isArray(quickFixPreview?.fixes) && quickFixPreview.fixes.length > 0 ? (
                <>
                  <button onClick={() => void quickFixwizardExecuteLowRisk(3)}>Execute Low-Risk (max 3)</button>
                  <button onClick={() => void quickFixwizardExecuteTop(1)}>Execute Top-1 Fix</button>
                  <button onClick={() => void quickFixwizardExecuteTop(3)}>Execute Top-3 Fixes</button>
                </>
              ) : null}
            </div>
            {quickFixPreview ? (
              <details style={{ marginTop: 8 }}>
                <summary>quick fix preview</summary>
                <div className="scroll" style={{ maxHeight: 220, marginTop: 8 }}>
                  {!Array.isArray(quickFixPreview?.fixes) || quickFixPreview.fixes.length === 0 ? (
                    <div className="hint">No fixes.</div>
                  ) : (
                    quickFixPreview.fixes.map((fx: any, idx: number) => {
                      const risk = String(fx?.risk || "-").toLowerCase();
                      const st = riskBadgeStyle(risk);
                      const effects = Array.isArray(fx?.expected_effect) ? fx.expected_effect : [];
                      return (
                        <div
                          key={`${String(fx?.fix_id || "fx")}:${idx}`}
                          className="agent-audit-row"
                          style={{ borderColor: st.border, background: st.bg }}
                        >
                          <div className="row" style={{ gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                            <span
                              className="small"
                              style={{
                                color: st.fg,
                                border: `1px solid ${st.border}`,
                                borderRadius: 999,
                                padding: "2px 8px",
                                fontWeight: 600,
                              }}
                            >
                              {risk}
                            </span>
                            <span className="small" style={{ fontWeight: 600 }}>{String(fx?.title || "-")}</span>
                            <span className="small">type={String(fx?.type || "-")}</span>
                            <span className="small">target={String(fx?.target || "-")}</span>
                          </div>
                          {String(fx?.reason || "").trim() ? (
                            <div className="small" style={{ marginTop: 4 }}>{String(fx?.reason || "")}</div>
                          ) : null}
                          {effects.length > 0 ? (
                            <div className="small" style={{ marginTop: 4 }}>
                              expected: {effects.slice(0, 3).join(" | ")}
                            </div>
                          ) : null}
                        </div>
                      );
                    })
                  )}
                </div>
                <details style={{ marginTop: 8 }}>
                  <summary className="small">raw fix preview json</summary>
                  <pre>{JSON.stringify(quickFixPreview, null, 2)}</pre>
                </details>
              </details>
            ) : null}
            {quickFixExecuteOut ? (
              <details style={{ marginTop: 8 }}>
                <summary>quick fix execute result</summary>
                <pre>{JSON.stringify(quickFixExecuteOut, null, 2)}</pre>
              </details>
            ) : null}
          </div>
        ) : null}
        <div className="agent-grid" style={{ marginTop: 8 }}>
          <div className="agent-col">
            <div className="small">quick draft run</div>
            <pre>{JSON.stringify(quickDraftRunOut, null, 2)}</pre>
          </div>
          <div className="agent-col">
            <div className="small">quick versions</div>
            <pre>{JSON.stringify(quickVersionsOut, null, 2)}</pre>
          </div>
          <div className="agent-col">
            <div className="small">quick publish</div>
            <pre>{JSON.stringify(quickPublishOut, null, 2)}</pre>
          </div>
        </div>
      </section>

      {showAgentConsole ? (
        <AgentConsolePanel
          selectedBookId={bookId}
          selectedChapterId={chapterId}
          onPickBookId={(id) => setBookId(id)}
          onPickChapterId={(id) => setChapterId(id)}
        />
      ) : null}

      {showVersionCenter ? (
        <VersionsPanel
          bookId={bookId}
          chapterId={chapterId}
          onPickChapterId={(id) => setChapterId(id)}
          onStatus={(msg) => setStatus(msg)}
        />
      ) : null}

      {showRewriteCenter ? (
        <RewritePanel
          bookId={bookId}
          chapterId={chapterId}
          onStatus={(msg) => setStatus(msg)}
        />
      ) : null}

      {showReleaseCenter ? (
        <>
          <SkillPackHubPanel
            bookId={bookId}
            volumeId={quickVolumeId}
            onStatus={(msg) => setStatus(msg)}
          />
          <PublishPackPanel
            bookId={bookId}
            volumeId={quickVolumeId}
            onPickVolumeId={(id) => setQuickVolumeId(id)}
            onStatus={(msg) => setStatus(msg)}
          />
          <PreflightFixWizardPanel
            bookId={bookId}
            volumeId={quickVolumeId}
            onStatus={(msg) => setStatus(msg)}
          />
          <ComboInjectionQueuePanel
            bookId={bookId}
            volumeId={quickVolumeId}
            onStatus={(msg) => setStatus(msg)}
          />
        </>
      ) : null}

      <section className="wb-panel" style={{ minHeight: "auto", marginBottom: 10 }}>
        <h3>Library</h3>
        <div className="row" style={{ marginBottom: 8 }}>
          <input
            value={librarySearchQuery}
            onChange={(e) => setLibrarySearchQuery(e.target.value)}
            placeholder="Unified search: books / chapters / materials / skill_runs"
          />
          <button onClick={() => setSearchOpen(true)}>Open Global (Ctrl/Cmd+K)</button>
        </div>
        {librarySearchQuery.trim() ? (
          <div className="wb-panel" style={{ minHeight: "auto", marginBottom: 10, padding: 10 }}>
            <div className="row" style={{ marginBottom: 6 }}>
              <strong>Search Results</strong>
              <span className="small">{librarySearchLoading ? "searching..." : `${librarySearchItems.length} items`}</span>
            </div>
            <div className="job-grid">
              <div>
                <div className="small" style={{ marginBottom: 6 }}>Books</div>
                <div className="scroll" style={{ maxHeight: 160 }}>
                  {libraryBookHits.map((it) => (
                    <button key={`book_${it.id}`} className="node-item" onClick={() => void applyLibrarySearchItem(it)}>
                      <div style={{ width: "100%" }}>
                        <div className="row"><span><span className="badge">book</span> {it.title}</span><code>{Number(it.score || 0).toFixed(2)}</code></div>
                        <div className="small">{it.subtitle}</div>
                      </div>
                    </button>
                  ))}
                  {libraryBookHits.length === 0 ? <div className="hint">No books</div> : null}
                </div>
              </div>
              <div>
                <div className="small" style={{ marginBottom: 6 }}>Chapters</div>
                <div className="scroll" style={{ maxHeight: 160 }}>
                  {libraryChapterHits.map((it) => (
                    <button key={`chapter_${it.id}`} className="node-item" onClick={() => void applyLibrarySearchItem(it)}>
                      <div style={{ width: "100%" }}>
                        <div className="row"><span><span className="badge">chapter</span> {it.title}</span><code>{Number(it.score || 0).toFixed(2)}</code></div>
                        <div className="small">{it.subtitle}</div>
                      </div>
                    </button>
                  ))}
                  {libraryChapterHits.length === 0 ? <div className="hint">No chapters</div> : null}
                </div>
              </div>
            </div>
            <div className="job-grid" style={{ marginTop: 8 }}>
              <div>
                <div className="small" style={{ marginBottom: 6 }}>Materials</div>
                <div className="scroll" style={{ maxHeight: 160 }}>
                  {libraryMaterialHits.map((it) => (
                    <button key={`material_${it.id}`} className="node-item" onClick={() => void applyLibrarySearchItem(it)}>
                      <div style={{ width: "100%" }}>
                        <div className="row"><span><span className="badge">material</span> {it.title}</span><code>{Number(it.score || 0).toFixed(2)}</code></div>
                        <div className="small">{it.subtitle}</div>
                      </div>
                    </button>
                  ))}
                  {libraryMaterialHits.length === 0 ? <div className="hint">No materials</div> : null}
                </div>
              </div>
              <div>
                <div className="small" style={{ marginBottom: 6 }}>Skill Runs</div>
                <div className="scroll" style={{ maxHeight: 160 }}>
                  {librarySkillRunHits.map((it) => (
                    <button key={`skill_${it.id}`} className="node-item" onClick={() => void applyLibrarySearchItem(it)}>
                      <div style={{ width: "100%" }}>
                        <div className="row"><span><span className="badge">skill_run</span> {it.title}</span><code>{Number(it.score || 0).toFixed(2)}</code></div>
                        <div className="small">{it.subtitle}</div>
                      </div>
                    </button>
                  ))}
                  {librarySkillRunHits.length === 0 ? <div className="hint">No skill runs</div> : null}
                </div>
              </div>
            </div>
          </div>
        ) : null}
        <div className="job-grid">
          <div>
            <div className="row" style={{ marginBottom: 8 }}>
              <input value={bookQuery} onChange={(e) => setBookQuery(e.target.value)} placeholder="search books..." />
              <button onClick={() => void loadBooks()}>Search</button>
            </div>
            <div className="row" style={{ marginBottom: 8 }}>
              <input value={newBookName} onChange={(e) => setNewBookName(e.target.value)} placeholder="new book name" />
              <button onClick={() => void createBookFromLibrary()}>Create Book</button>
            </div>
            <div className="scroll" style={{ maxHeight: 220 }}>
              {bookItems.map((b) => (
                <button
                  key={b.book_id}
                  className={`node-item ${bookId === b.book_id ? "active" : ""}`}
                  onClick={() => setBookId(b.book_id)}
                >
                  <div style={{ width: "100%" }}>
                    <div className="row"><strong>{b.title}</strong><code>{b.language || "zh"}</code></div>
                    <div className="small">{b.book_id}</div>
                  </div>
                </button>
              ))}
              {bookItems.length === 0 ? <div className="hint">No books</div> : null}
            </div>
          </div>

          <div>
            <div className="row" style={{ marginBottom: 8 }}>
              <input value={chapterQuery} onChange={(e) => setChapterQuery(e.target.value)} placeholder="search chapters..." disabled={!bookId} />
              <button onClick={() => void loadChapters()} disabled={!bookId}>Search</button>
            </div>
            <div className="row" style={{ marginBottom: 8, flexWrap: "wrap" }}>
              <input style={{ width: 96 }} type="number" value={newChapterNo} onChange={(e) => setNewChapterNo(Number(e.target.value))} placeholder="no" disabled={!bookId} />
              <input value={newChapterTitle} onChange={(e) => setNewChapterTitle(e.target.value)} placeholder="title" disabled={!bookId} />
              <input style={{ width: 120 }} value={newChapterArcId} onChange={(e) => setNewChapterArcId(e.target.value)} placeholder="arc_id" disabled={!bookId} />
              <input style={{ width: 96 }} type="number" value={newChapterArcIndex} onChange={(e) => setNewChapterArcIndex(Number(e.target.value))} placeholder="arc_idx" disabled={!bookId} />
              <button onClick={() => void createChapterFromLibrary()} disabled={!bookId}>Create Chapter</button>
            </div>
            <div className="scroll" style={{ maxHeight: 220 }}>
              {chapterItems.map((c) => (
                <button
                  key={c.chapter_id}
                  className={`node-item ${chapterId === c.chapter_id ? "active" : ""}`}
                  onClick={() => setChapterId(c.chapter_id)}
                >
                  <div style={{ width: "100%" }}>
                    <div className="row"><strong>第{c.chapter_no}章 · {c.title}</strong><code>{c.arc_id || "-"}</code></div>
                    <div className="small">{c.chapter_id}</div>
                  </div>
                </button>
              ))}
              {bookId && chapterItems.length === 0 ? <div className="hint">No chapters</div> : null}
            </div>
          </div>
        </div>
      </section>

      {showRefCenter ? (
        <section className="wb-panel" style={{ minHeight: "auto", marginBottom: 10 }}>
          <div className="row" style={{ marginBottom: 8 }}>
            <h3 style={{ margin: 0 }}>Ref Center</h3>
            <div className="row">
              <button className={refCenterTab === "material" ? "active" : ""} onClick={() => setRefCenterTab("material")}>Materials</button>
              <button className={refCenterTab === "template" ? "active" : ""} onClick={() => setRefCenterTab("template")}>Templates</button>
            </div>
          </div>
          <div className="row" style={{ marginBottom: 8, flexWrap: "wrap" }}>
            <input
              value={refUnifiedQuery}
              onChange={(e) => setRefUnifiedQuery(e.target.value)}
              placeholder="Unified search in Ref Center (materials + templates)..."
            />
            <button onClick={() => void searchRefUnified()} disabled={!refUnifiedQuery.trim() || refUnifiedLoading}>
              {refUnifiedLoading ? "Searching..." : "Search Refs"}
            </button>
          </div>
          {refUnifiedItems.length ? (
            <div className="scroll" style={{ maxHeight: 180, marginBottom: 10 }}>
              {refUnifiedItems.map((it) => (
                <div key={`${it.kind}:${it.id}`} className="issue-item">
                  <div className="row">
                    <span><span className="badge">{it.kind}</span> {it.title}</span>
                    <code>{it.score.toFixed(2)}</code>
                  </div>
                  <div className="small" style={{ marginBottom: 6 }}>{it.subtitle}</div>
                  <div className="row">
                    <button
                      onClick={() => {
                        const promise = it.kind === "template"
                          ? addTemplateAssetToRefInbox(it.id, undefined, it.title)
                          : addMaterialCardToRefInbox(it.id, it.title);
                        void promise.catch((e) => setStatus(String(e)));
                      }}
                      disabled={!chapterId}
                    >
                      Add Ref
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
          {refCenterTab === "material" ? (
            <MaterialCenter
              baseUrl={baseUrl}
              bookId={bookId}
              chapterId={chapterId}
              materialRefs={materialRefs}
              onAddRef={(block) => setMaterialRefs((prev) => [block, ...prev].slice(0, 20))}
              onRemoveRef={(index) => setMaterialRefs((prev) => prev.filter((_, i) => i !== index))}
              onClearRefs={() => setMaterialRefs([])}
              onStatus={(msg) => setStatus(msg)}
            />
          ) : (
            <div className="job-grid">
              <div>
                <div className="row" style={{ marginBottom: 8, flexWrap: "wrap" }}>
                  <select value={templateType} onChange={(e) => setTemplateType(e.target.value)} style={{ width: 160 }}>
                    <option value="">(all types)</option>
                    <option value="structure">structure</option>
                    <option value="mechanic">mechanic</option>
                    <option value="style">style</option>
                    <option value="foreshadow">foreshadow</option>
                    <option value="payoff">payoff</option>
                  </select>
                  <input value={templateTag} onChange={(e) => setTemplateTag(e.target.value)} placeholder="tag(optional)" style={{ width: 180 }} />
                  <input value={templateQuery} onChange={(e) => setTemplateQuery(e.target.value)} placeholder="search templates..." />
                  <button onClick={() => void searchTemplateAssets()} disabled={templateLoading}>{templateLoading ? "Loading..." : "Search"}</button>
                </div>
                <div className="scroll" style={{ maxHeight: 260 }}>
                  {templateItems.map((it) => (
                    <button
                      key={it.asset_id}
                      className={`node-item ${templateSelected?.asset_id === it.asset_id ? "active" : ""}`}
                      onClick={() => setTemplateSelected(it)}
                    >
                      <div style={{ width: "100%" }}>
                        <div className="row">
                          <strong>{it.name}</strong>
                          <code>{it.asset_type}</code>
                        </div>
                        <div className="small">{(it.tags || []).slice(0, 4).join(" / ") || "-"}</div>
                        <div className="small">{it.asset_id}</div>
                      </div>
                    </button>
                  ))}
                  {templateItems.length === 0 ? <div className="hint">No templates</div> : null}
                </div>
              </div>
              <div>
                <div className="row" style={{ marginBottom: 8 }}>
                  <strong>Template Detail</strong>
                  <div className="row">
                    <button
                      onClick={() => {
                        void addTemplateToRefInbox().catch((e) => setStatus(String(e)));
                      }}
                      disabled={!templateSelected}
                    >
                      Add to Ref Inbox
                    </button>
                  </div>
                </div>
                {templateSelected ? (
                  <>
                    <div className="small">type: <code>{templateSelected.asset_type}</code></div>
                    <div className="small">asset_id: <code>{templateSelected.asset_id}</code></div>
                    <div className="small">tags: {(templateSelected.tags || []).join(", ") || "-"}</div>
                    <label style={{ marginTop: 8 }}>
                      note(optional)
                      <input value={templateNote} onChange={(e) => setTemplateNote(e.target.value)} placeholder="本章映射备注（可选）" />
                    </label>
                    <pre>{templateSelected.description}</pre>
                  </>
                ) : (
                  <div className="hint">Select one template</div>
                )}
              </div>
            </div>
          )}
          <div className="hint" style={{ marginTop: 8 }}>
            Templates 加入后会进入当前章节 Ref Inbox，并同步进入页面 Ref 列表给 Control Plan 使用。
          </div>
        </section>
      ) : null}

      {showSplitbooks ? (
        <section className="wb-panel" style={{ minHeight: "auto", marginBottom: 10 }}>
          <div className="row" style={{ marginBottom: 8 }}>
            <h3 style={{ margin: 0 }}>Splitbooks</h3>
            <div className="row">
              <button onClick={() => void loadSplitbooks()}>Refresh</button>
            </div>
          </div>
          <div className="job-grid">
            <div>
              <div className="row" style={{ marginBottom: 8, flexWrap: "wrap" }}>
                <input value={splitbookName} onChange={(e) => setSplitbookName(e.target.value)} placeholder="name" />
                <input value={splitbookAuthor} onChange={(e) => setSplitbookAuthor(e.target.value)} placeholder="author(optional)" />
                <input value={splitbookPath} onChange={(e) => setSplitbookPath(e.target.value)} placeholder="/data/novels/xxx.txt" />
                <button onClick={() => void createSplitbookFromUi()} disabled={!splitbookName.trim()}>Create</button>
              </div>
              <div className="scroll" style={{ maxHeight: 260 }}>
                {splitbooks.map((sb) => (
                  <button
                    key={sb.splitbook_id}
                    className={`node-item ${selectedSplitbookId === sb.splitbook_id ? "active" : ""}`}
                    onClick={() => {
                      setSelectedSplitbookId(sb.splitbook_id);
                      if (sb.source_path) setSplitbookPath(sb.source_path);
                    }}
                  >
                    <div style={{ width: "100%" }}>
                      <div className="row"><strong>{sb.name}</strong><code>{sb.allow_guard ? "guard:on" : "guard:off"}</code></div>
                      <div className="small">ingest={sb.ingest_status} · embed={sb.embed_status}</div>
                      <div className="small">{sb.splitbook_id}</div>
                    </div>
                  </button>
                ))}
                {splitbooks.length === 0 ? <div className="hint">No splitbooks</div> : null}
              </div>
            </div>
            <div>
              <div className="row" style={{ marginBottom: 8 }}>
                <strong>Detail</strong>
              </div>
              {selectedSplitbook ? (
                <>
                  <div className="small">path: <code>{selectedSplitbook.source_path || "-"}</code></div>
                  <div className="small">chunks: <code>{Number(selectedSplitbook.stats?.chunks_total || 0)}</code></div>
                  <div className="small">embedded: <code>{Number(selectedSplitbook.stats?.embedded_total || 0)}</code></div>
                  <div className="small">running jobs: <code>{selectedSplitbookJobs.length}</code></div>
                  {selectedSplitbookJobs.length ? (
                    <div className="scroll" style={{ maxHeight: 160, marginTop: 8 }}>
                      {selectedSplitbookJobs.map((j) => {
                        const pct = Math.max(0, Math.min(100, Math.round(Number((j.progress as any)?.pct ?? (j.progress_value || 0) * 100))));
                        return (
                          <div key={j.job_id} className="issue-item">
                            <div className="row">
                              <strong>{j.job_type}</strong>
                              <code>{pct}%</code>
                            </div>
                            <div className="small">{j.stage}</div>
                            <div className="row" style={{ marginTop: 4 }}>
                              <button onClick={() => void openJobInCenter(j)}>Open in Job Center</button>
                            </div>
                            <div style={{ height: 8, background: "#eee", borderRadius: 6, overflow: "hidden", marginTop: 4 }}>
                              <div style={{ width: `${pct}%`, height: "100%", background: "#2d7ef7" }} />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : null}
                  <div className="row" style={{ marginTop: 8, flexWrap: "wrap" }}>
                    <label style={{ width: 120 }}>
                      chunk_size
                      <input type="number" value={splitbookChunkSize} onChange={(e) => setSplitbookChunkSize(Number(e.target.value))} />
                    </label>
                    <label style={{ width: 120 }}>
                      overlap
                      <input type="number" value={splitbookOverlap} onChange={(e) => setSplitbookOverlap(Number(e.target.value))} />
                    </label>
                  </div>
                  <div className="row" style={{ marginTop: 8, flexWrap: "wrap" }}>
                    <button onClick={() => void triggerSplitbookJob("ingest")}>Start Ingest</button>
                    <button onClick={() => void triggerSplitbookJob("embed")} disabled={selectedSplitbook.ingest_status !== "done"}>Start Embed</button>
                    <button onClick={() => void triggerSplitbookJob("build_templates")} disabled={selectedSplitbook.ingest_status !== "done"}>Build Templates</button>
                    <button onClick={() => void triggerSplitbookJob("build_profile")} disabled={selectedSplitbook.ingest_status !== "done"}>Build Profile</button>
                    <button onClick={() => void setSplitbookAllowGuard(!selectedSplitbook.allow_guard)}>
                      allow_guard: {selectedSplitbook.allow_guard ? "ON" : "OFF"}
                    </button>
                    <button onClick={() => void exportSplitbookDiagnose()}>
                      Export Diagnose JSON
                    </button>
                  </div>
                </>
              ) : (
                <div className="hint">Select splitbook</div>
              )}
            </div>
          </div>
        </section>
      ) : null}

      <section className="wb-topbar">
        <label>
          Engine URL
          <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
        </label>
        <label>
          Chapter ID
          <input value={chapterId} onChange={(e) => setChapterId(e.target.value)} placeholder="uuid" />
        </label>
        <label>
          Book ID
          <input value={bookId} onChange={(e) => setBookId(e.target.value)} placeholder="uuid" />
        </label>
        <label>
          Version
          <select value={selectedVersion} onChange={(e) => setSelectedVersion(e.target.value)}>
            <option value="latest">latest</option>
            {versions.map((v) => (
              <option key={v.outline_id} value={String(v.version)}>
                v{v.version}
              </option>
            ))}
          </select>
        </label>
        <button onClick={() => loadOutline(selectedVersion)} disabled={busy}>Load Outline</button>
        <button onClick={() => saveOutline("manual edit")} disabled={busy || !dirty || !outline}>Save Outline</button>
        <button onClick={runEval} disabled={busy || !outline}>Eval</button>
        <button onClick={runControlPlan} disabled={busy || !outline}>Control Plan</button>
        <button onClick={applySelectedPatches} disabled={busy || !planRun}>Apply Selected</button>
        <button
          onClick={() => {
            setCompareOpen(true);
            setCompareUnread(false);
          }}
          disabled={!chapterId}
          style={{ position: "relative" }}
        >
          Compare
          {compareUnread ? (
            <span
              style={{
                display: "inline-block",
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: "#b00020",
                marginLeft: 6,
                verticalAlign: "middle",
              }}
            />
          ) : null}
        </button>
        <button onClick={() => void runBookTensionAnalyze()} disabled={busy || !bookId}>Analyze Book</button>
        <button onClick={() => void loadBookTensionReport()} disabled={busy || !bookId}>Load Report</button>
        <button onClick={() => void loadLatestChapterReport()} disabled={busy || !chapterId}>Load Chapter Report</button>
        <button onClick={() => void createRepairPlan()} disabled={busy || !bookId}>Repair Plan</button>
        <div className="small" style={{ flexBasis: "100%", marginTop: 4 }}>
          Eval 提示：`chapter_version_id` 留空时，后端会自动使用该章节最新版本。
        </div>
      </section>

      <section className="wb-sliders">
        {Object.entries(targets).map(([k, v]) => (
          <label key={k}>
            {k}: {v.toFixed(2)}
            <input type="range" min={0} max={1} step={0.01} value={v} onChange={(e) => setTargets({ ...targets, [k]: Number(e.target.value) })} />
          </label>
        ))}
        {Object.entries(style).map(([k, v]) => (
          <label key={k}>
            {k}: {v.toFixed(2)}
            <input type="range" min={0} max={1} step={0.01} value={v} onChange={(e) => setStyle({ ...style, [k]: Number(e.target.value) })} />
          </label>
        ))}
      </section>

      <main className="wb-grid">
        <aside className="wb-panel node-list">
          <h3>Nodes</h3>
          <div className="scroll">
            {(outline?.nodes || []).map((n) => (
              <button key={n.node_id} className={`node-item ${selectedNodeId === n.node_id ? "active" : ""}`} onClick={() => setSelectedNodeId(n.node_id)}>
                <div>
                  <div className="row"><code>{n.node_id}</code><span className="badge">{n.type}</span></div>
                  <div className="summary-line">{(n.summary || "").split("\n")[0] || "(empty)"}</div>
                </div>
              </button>
            ))}
          </div>
        </aside>

        <section className="wb-panel node-editor">
          <h3>Node Editor</h3>
          {selectedNode ? (
            <>
              <div className="meta-row"><code>{selectedNode.node_id}</code><span className="badge">{selectedNode.type}</span></div>
              <textarea rows={12} value={selectedNode.summary || ""} onChange={(e) => updateNodeSummary(e.target.value)} />
              <div className="hint">编辑后点击 Save Outline 生成新版本</div>
            </>
          ) : (
            <div className="hint">选择一个节点开始编辑</div>
          )}

          <h4>Eval Issues</h4>
          <div className="issues">
            {issues.length === 0 ? <div className="hint">暂无评估结果</div> : null}
            {issues.map((it, idx) => (
              <div key={idx} className="issue-item"><strong>{it.type}</strong> @ {it.where?.node_id} - {it.detail}</div>
            ))}
          </div>
        </section>

        <aside className="wb-panel patch-panel">
          <h3>Patches</h3>
          <div className="scroll">
            {patches.length === 0 ? <div className="hint">先执行 Control Plan</div> : null}
            {patches.map((p) => (
              <label key={p.patch_id || Math.random()} className="patch-item">
                <input type="checkbox" checked={Boolean(selectedPatches[p.patch_id])} onChange={(e) => setSelectedPatches({ ...selectedPatches, [p.patch_id]: e.target.checked })} />
                <div>
                  <div className="row"><strong>{p.patch_type}</strong><code>{p.patch_id || "no-id"}</code></div>
                  <div className="small">where: {JSON.stringify(p.where || {})}</div>
                  {p.change?.after ? <pre>{p.change.after}</pre> : null}
                  {p.insert?.node?.summary ? <pre>{p.insert.node.summary}</pre> : null}
                </div>
              </label>
            ))}
          </div>
        </aside>
      </main>

      {showJobs ? (
        <section className="wb-panel" style={{ marginTop: 10 }}>
          <div className="row" style={{ marginBottom: 8 }}>
            <h3 style={{ margin: 0 }}>Job Center</h3>
            <div className="row">
              <button onClick={() => setJobTab("running")} className={jobTab === "running" ? "active" : ""}>Running</button>
              <button onClick={() => setJobTab("succeeded")} className={jobTab === "succeeded" ? "active" : ""}>Done</button>
              <button onClick={() => setJobTab("failed")} className={jobTab === "failed" ? "active" : ""}>Failed</button>
            </div>
          </div>
          <div className="row" style={{ marginBottom: 8 }}>
            <label style={{ flex: 1 }}>
              skill_run_id filter
              <input
                value={jobSkillRunFilter}
                onChange={(e) => setJobSkillRunFilter(e.target.value)}
                placeholder="paste skill_run_id to locate job"
              />
            </label>
            <button onClick={() => setJobSkillRunFilter("")}>Clear</button>
          </div>
          <div className="job-grid">
            <div className="scroll">
              {jobs.map((j) => (
                <button data-job-id={j.job_id} key={j.job_id} className={`node-item ${selectedJob?.job_id === j.job_id ? "active" : ""}`} onClick={() => setSelectedJob(j)}>
                  <div style={{ width: "100%" }}>
                    <div className="row"><strong>{j.job_type}</strong><code>{j.status}</code></div>
                    <div className="small">{j.stage} · {Math.round((j.progress_value || 0) * 100)}%</div>
                    {extractSkillRunId(j) ? <div className="small">skill_run: {extractSkillRunId(j)}</div> : null}
                    <div className="small">{j.job_id}</div>
                  </div>
                </button>
              ))}
            </div>
            <div>
              {selectedJob ? (
                <>
                  <h4>{selectedJob.job_type}</h4>
                  <div className="small">stage: {selectedJob.stage}</div>
                  <div className="small">status: {selectedJob.status}</div>
                  <div className="small">payload: {JSON.stringify(selectedJob.payload || {}, null, 2)}</div>
                  <div className="small">result: {JSON.stringify(selectedJob.result || {}, null, 2)}</div>
                  <div className="small">error: {JSON.stringify(selectedJob.error || {}, null, 2)}</div>
                  <h5>Logs</h5>
                  <pre style={{ maxHeight: 220, overflow: "auto" }}>{(selectedJob.logs || []).join("\n") || "(no logs)"}</pre>
                  {selectedJob.status === "failed" ? (
                    <button onClick={() => retryJob(selectedJob)}>Retry Job</button>
                  ) : null}
                </>
              ) : (
                <div className="hint">选择一个 job 查看详情</div>
              )}
            </div>
          </div>
        </section>
      ) : null}

      <section className="wb-panel" style={{ marginTop: 10 }}>
        <h3>Book Tension Dashboard</h3>
        {!bookTensionReport ? <div className="hint">Run Analyze Book or Load Report</div> : null}
        {bookTensionReport ? (
          <>
            <div className="top-summary-grid">
              <div className="summary-card">
                <div className="k">Coverage</div>
                <div className="v">
                  {report.coverage?.chapters_with_metrics || 0} / {report.coverage?.chapters_total || 0}
                </div>
              </div>
              <div className="summary-card">
                <div className="k">Peak Density</div>
                <div className="v">{report.peaks?.density_per_10 ?? 0} / 10章</div>
              </div>
              <div className="summary-card">
                <div className="k">Valley Density</div>
                <div className="v">{report.valleys?.density_per_10 ?? 0} / 10章</div>
              </div>
              <div className="summary-card">
                <div className="k">Fatigue Zones</div>
                <div className="v">{fatigueZones.length}</div>
              </div>
            </div>

            <h4>Trend Snapshot</h4>
            <div className="trend-grid">
              <div>
                <div className="small">overall_ma</div>
                <div className="trend-strip">
                  {(report.book_trends?.overall_ma || []).slice(-20).map((v: number, i: number) => (
                    <span key={i} style={{ height: `${Math.max(8, Math.round(v * 70))}px` }} />
                  ))}
                </div>
              </div>
              <div>
                <div className="small">cost_ma</div>
                <div className="trend-strip">
                  {(report.book_trends?.cost_ma || []).slice(-20).map((v: number, i: number) => (
                    <span key={i} style={{ height: `${Math.max(8, Math.round(v * 70))}px` }} />
                  ))}
                </div>
              </div>
              <div>
                <div className="small">reversal_ma</div>
                <div className="trend-strip">
                  {(report.book_trends?.reversal_ma || []).slice(-20).map((v: number, i: number) => (
                    <span key={i} style={{ height: `${Math.max(8, Math.round(v * 70))}px` }} />
                  ))}
                </div>
              </div>
            </div>

            <h4>Fatigue Zones</h4>
            <div className="zone-list">
              {fatigueZones.length === 0 ? <div className="hint">No fatigue zones</div> : null}
              {fatigueZones.map((z: any, idx: number) => (
                <div key={idx} className="zone-item">
                  <div>
                    <strong>
                      {z.from} - {z.to}
                    </strong>
                    <div className="small">{z.reason}</div>
                  </div>
                  <div className="row">
                    <button onClick={() => setStatus(`Jump to chapter ${z.from}`)}>Jump</button>
                    <button onClick={() => void fetch(`${baseUrl}/v1/books/${bookId}/tension/repair_plan`, {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ chapter_from: z.from, chapter_to: z.to, targets, style })
                    }).then(() => setStatus(`Repair plan created for ${z.from}-${z.to}`))}>
                      Generate Repair Plan
                    </button>
                  </div>
                </div>
              ))}
            </div>

            <h4>Arc Summary</h4>
            <div className="arc-table-wrap">
              <table className="arc-table">
                <thead>
                  <tr>
                    <th>Arc</th>
                    <th>Chapters</th>
                    <th>Overall</th>
                    <th>Cost</th>
                    <th>Reversal</th>
                    <th>Pace</th>
                    <th>Shape</th>
                    <th>Issues Top</th>
                    <th>Mechanics Mix</th>
                  </tr>
                </thead>
                <tbody>
                  {arcSummary.map((arc: any, i: number) => (
                    <tr key={i}>
                      <td>{arc.arc_id}</td>
                      <td>{arc.chapter_from}-{arc.chapter_to}</td>
                      <td>{arc.avg_scores?.overall ?? 0}</td>
                      <td>{arc.avg_scores?.cost ?? 0}</td>
                      <td>{arc.avg_scores?.reversal ?? 0}</td>
                      <td>{arc.avg_scores?.pace ?? 0}</td>
                      <td>{arc.curve_shape}</td>
                      <td>{(arc.issues_top || []).join(", ")}</td>
                      <td>{Object.entries(arc.mechanics_mix || {}).slice(0, 3).map(([k, v]) => `${k}×${v}`).join(", ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <h4>Advanced Alerts</h4>
            <div className="zone-list">
              {(diagnosis || []).slice(0, 12).map((d: any, i: number) => (
                <div key={i} className="zone-item">
                  <div>
                    <strong>{d.type}</strong>
                    <div className="small">
                      {d.where?.chapter_from} - {d.where?.chapter_to} | {d.detail}
                    </div>
                    <div className="small">
                      {(d.suggest_actions || []).slice(0, 4).map((a: any) => `${a.chapter_no}:${a.action}`).join(" | ")}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <h4>Arc Target Settings</h4>
            <div className="settings-grid">
              <label>
                Arc ID
                <input value={arcTargetForm.arc_id} onChange={(e) => setArcTargetForm({ ...arcTargetForm, arc_id: e.target.value })} />
              </label>
              <label>
                Shape
                <select
                  value={arcTargetForm.target_shape}
                  onChange={(e) => setArcTargetForm({ ...arcTargetForm, target_shape: e.target.value as ArcTarget["target_shape"] })}
                >
                  <option value="ramp">ramp</option>
                  <option value="late_peak">late_peak</option>
                  <option value="early_peak">early_peak</option>
                  <option value="plateau">plateau</option>
                  <option value="sawtooth">sawtooth</option>
                </select>
              </label>
              <label>
                Target Points (5)
                <input
                  value={arcTargetForm.target_points.join(",")}
                  onChange={(e) => {
                    const vals = e.target.value.split(",").map((x) => Number(x.trim())).filter((x) => !Number.isNaN(x)).slice(0, 5);
                    setArcTargetForm({ ...arcTargetForm, target_points: vals.length === 5 ? vals : arcTargetForm.target_points });
                  }}
                />
              </label>
            </div>
            <div className="row" style={{ marginTop: 8 }}>
              <button onClick={() => void saveArcTarget()}>Save Arc Target</button>
              <button onClick={() => void loadArcTargets()}>Reload Arc Targets</button>
              <button onClick={() => void evolveTemplates()}>Evolve Templates</button>
              <button onClick={() => void loadVariants()}>Reload Variants</button>
            </div>
            <pre>{JSON.stringify({ advanced, arc_targets: arcTargetAnalysis, configured_targets: arcTargets }, null, 2)}</pre>

            <h4>Template Lab</h4>
            <div className="zone-list">
              {variants.length === 0 ? <div className="hint">No variants yet. Run Evolve Templates.</div> : null}
              {variants.map((v) => (
                <div key={v.variant_id} className="zone-item">
                  <div className="row">
                    <div>
                      <strong>{v.name}</strong>
                      <div className="small">enabled: {String(v.enabled)} | weight: {v.weight}</div>
                      <div className="small">scope: {JSON.stringify(v.scope)}</div>
                      <div className="small">stats: {JSON.stringify(v.stats)}</div>
                    </div>
                    <div className="row">
                      <button onClick={() => void setVariantEnabled(v.variant_id, true, Math.max(0.1, v.weight || 0.1))}>Enable</button>
                      <button onClick={() => void setVariantEnabled(v.variant_id, false)}>Disable</button>
                    </div>
                  </div>
                  <pre>{JSON.stringify(v.recipe, null, 2)}</pre>
                </div>
              ))}
            </div>
          </>
        ) : null}
      </section>

      {showSettings ? (
        <section className="wb-panel" style={{ marginTop: 10 }}>
          <h3>Settings & Health</h3>
          <div className="small" style={{ marginBottom: 8 }}>
            支持 Ollama / OpenAI / OpenAI-compatible（本地兼容网关）。当前 provider 会自动同步到运行时配置。
          </div>
          <div className="wb-panel" style={{ minHeight: "auto", marginBottom: 10 }}>
            <h4 style={{ marginTop: 0 }}>Stylistic Profile</h4>
            <div className="row" style={{ marginBottom: 8, flexWrap: "wrap" }}>
              <label style={{ minWidth: 320 }}>
                Current Book
                <input value={bookId} onChange={(e) => setBookId(e.target.value)} placeholder="select in Library preferred" />
              </label>
              <label style={{ minWidth: 320 }}>
                Profile
                <select
                  value={selectedBookProfileId}
                  onChange={(e) => {
                    const next = e.target.value;
                    setSelectedBookProfileId(next);
                  }}
                >
                  <option value="">(none)</option>
                  {profiles.map((p) => (
                    <option key={p.profile_id} value={p.profile_id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="row" style={{ alignItems: "end" }}>
                <button onClick={() => void bindProfileToBook(selectedBookProfileId)} disabled={!bookId}>Bind Profile</button>
                <button onClick={() => void bindProfileToBook("")} disabled={!bookId}>Clear</button>
                <button onClick={() => void loadProfilesList()} disabled={!showSettings}>Reload Profiles</button>
                <button onClick={() => void addExperimentProfile(selectedBookProfileId)} disabled={!bookId || !selectedBookProfileId}>
                  Add as Experiment
                </button>
                <button onClick={() => void learnProfileFromCurrentBook()} disabled={!bookId || !selectedBookProfileId || profileLearning}>
                  {profileLearning ? "Learning..." : "Learn From Book Texts"}
                </button>
              </div>
            </div>
            <div className="small">
              当前 Eval/Control Plan 会自动注入该 profile_id；后端也会在未显式传入时回退到 book.profile_id。
            </div>
            <div className="row" style={{ gap: 10, marginTop: 10, alignItems: "stretch", flexWrap: "wrap" }}>
              <div style={{ flex: "1 1 360px", minWidth: 320 }}>
                <div className="small" style={{ marginBottom: 6 }}>
                  Profile Versions · active v{profileActiveVersion || "-"}
                </div>
                <div className="scroll" style={{ maxHeight: 220 }}>
                  {profileVersions.length === 0 ? <div className="hint">No versions.</div> : null}
                  {profileVersions.map((v) => (
                    <div
                      id={`profile-version-${v.version}`}
                      key={`${v.profile_id}:${v.version}`}
                      className="node-item"
                      style={{ cursor: "default" }}
                    >
                      <div style={{ width: "100%" }}>
                        <div className="row">
                          <strong>v{v.version}</strong>
                          <span className="small">{v.action}</span>
                          <span className="small">{new Date(v.created_at).toLocaleString()}</span>
                        </div>
                        <div className="small">{v.note || ""}</div>
                        <div className="row" style={{ marginTop: 6 }}>
                          <button onClick={() => void openProfileVersionSnapshot(selectedBookProfileId, Number(v.version))}>Snapshot</button>
                          <button onClick={() => void setActiveProfileVersion(Number(v.version))} disabled={Number(v.version) === profileActiveVersion}>
                            Set Active
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div style={{ flex: "2 1 560px", minWidth: 360 }}>
                <div className="small">Version Diff</div>
                <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "end" }}>
                  <label style={{ minWidth: 120 }}>
                    from
                    <select value={profileDiffFrom || 0} onChange={(e) => setProfileDiffFrom(Number(e.target.value) || 0)}>
                      {profileVersions.map((v) => (
                        <option key={`from-${v.version}`} value={v.version}>v{v.version}</option>
                      ))}
                    </select>
                  </label>
                  <label style={{ minWidth: 120 }}>
                    to
                    <select value={profileDiffTo || 0} onChange={(e) => setProfileDiffTo(Number(e.target.value) || 0)}>
                      {profileVersions.map((v) => (
                        <option key={`to-${v.version}`} value={v.version}>v{v.version}</option>
                      ))}
                    </select>
                  </label>
                  <button onClick={() => void runProfileVersionDiff()} disabled={!selectedBookProfileId || !profileDiffFrom || !profileDiffTo}>
                    Run Diff
                  </button>
                </div>
                <pre style={{ maxHeight: 160, overflow: "auto" }}>{JSON.stringify(profileDiffResult || {}, null, 2)}</pre>
                <div className="small">Snapshot Preview</div>
                <pre style={{ maxHeight: 160, overflow: "auto" }}>{JSON.stringify(profileVersionSnapshot || {}, null, 2)}</pre>
              </div>
            </div>
            <div className="row" style={{ gap: 8, marginTop: 8, flexWrap: "wrap", alignItems: "end" }}>
              <label style={{ minWidth: 260 }}>
                Clone Branch Name
                <input value={profileCloneName} onChange={(e) => setProfileCloneName(e.target.value)} placeholder="B-悬疑更冷" />
              </label>
              <button onClick={() => void cloneCurrentProfileBranch()} disabled={!selectedBookProfileId}>
                Clone Profile Branch
              </button>
            </div>
            {bookProfileMeta ? (
              <div className="small" style={{ marginTop: 8 }}>
                main={bookProfileMeta?.main?.profile_id || "-"} · experiments={(bookProfileMeta?.experiments || []).length}
              </div>
            ) : null}
            <div className="hr" />
            <div className="h2">A/B Batch</div>
            <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <label style={{ minWidth: 220 }}>
                Promote Strategy
                <select value={abPromoteStrategy} onChange={(e) => setAbPromoteStrategy(e.target.value as any)}>
                  <option value="profile">profile</option>
                  <option value="profile_plus_settings">profile_plus_settings</option>
                  <option value="version">version</option>
                </select>
              </label>
              <label className="small" style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={abIncludeComboBaseline}
                  onChange={(e) => setAbIncludeComboBaseline(e.target.checked)}
                />
                include combo baseline
              </label>
              <button onClick={() => void runAbBatch()} disabled={!chapterId || !bookId || abBatchLoading}>
                {abBatchLoading ? "Starting..." : "Run A/B Batch"}
              </button>
              <button onClick={() => void loadAbBatch(abBatchId)} disabled={!abBatchId}>Refresh Batch</button>
              <button onClick={() => void retryAbBatchFailed(abBatchId)} disabled={!abBatchId}>Retry Failed</button>
              <button
                onClick={() => void promoteAbBatchWinner(abBatchId)}
                disabled={!abBatchId || !abBatchData?.ranking?.length || String(abBatchData?.status || "") !== "done"}
              >
                Promote Winner → Set as Main
              </button>
              <button onClick={() => void loadChapterReports()} disabled={!chapterId}>Load Chapter Reports</button>
              <div className="small mono">batch_id={abBatchId || "-"}</div>
            </div>
            {abBatchData ? (
              <div style={{ marginTop: 8 }}>
                <div className="small">
                  status: <span className="mono">{String(abBatchData.status || "-")}</span> · items:{" "}
                  <span className="mono">{Array.isArray(abBatchData.items) ? abBatchData.items.length : 0}</span>
                  {" "}· penalty: <span className="mono">{String((abBatchData.score_cfg || {}).penalty ?? "-")}</span>
                  {" "}· winner_bundle: <span className="mono">{abBatchData.winner_bundle_id ? String(abBatchData.winner_bundle_id).slice(0, 8) : "-"}</span>
                </div>
                <div className="scroll" style={{ maxHeight: 180, marginTop: 6 }}>
                  {Array.isArray(abBatchData.items) && abBatchData.items.length > 0 ? (
                    <table className="compare-table">
                      <thead>
                        <tr>
                          <th>profile</th>
                          <th>variant</th>
                          <th>inject</th>
                          <th>ver</th>
                          <th>status</th>
                          <th>eval</th>
                          <th>sim</th>
                          <th>score</th>
                          <th>inj.bundle</th>
                          <th>inj.counts</th>
                          <th>text</th>
                          <th>trace</th>
                        </tr>
                      </thead>
                      <tbody>
                        {abBatchData.items.map((it: any) => (
                          <tr key={`${String(it.profile_id)}:${String(it.variant || "exp")}`}>
                            <td className="mono">{String(it.profile_id || "").slice(0, 8)}</td>
                            <td className="mono">{String(it.variant || "exp")}</td>
                            <td className="mono">{String(!!it.assets_injection)}</td>
                            <td className="mono">v{String(it.profile_version ?? "-")}</td>
                            <td className="mono">{String(it.status || "-")}</td>
                            <td className="mono">{it.eval_overall ?? "-"}</td>
                            <td className="mono">{it.simguard_max ?? "-"}</td>
                            <td className="mono">{it.score ?? "-"}</td>
                            <td className="mono">{it.injected_bundle_id ? String(it.injected_bundle_id).slice(0, 8) : "-"}</td>
                            <td className="mono">
                              {it.injected_counts
                                ? `h${it.injected_counts.hooks ?? 0}/b${it.injected_counts.beats ?? 0}/s${it.injected_counts.styles ?? 0}/t${it.injected_counts.templates ?? 0}`
                                : "-"}
                            </td>
                            <td className="mono">{it.text_ver_id ? String(it.text_ver_id).slice(0, 8) : "-"}</td>
                            <td>
                              <button
                                onClick={() => void viewAssetSelectionTrace(String(it.text_ver_id || ""))}
                                disabled={!it.text_ver_id || !it.assets_injection}
                              >
                                View
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div className="hint">No batch items.</div>
                  )}
                </div>
              </div>
            ) : null}

            {abBatchData?.delta_ranking?.length ? (
              <div style={{ marginTop: 10 }}>
                <div className="h2">Delta Ranking (exp - baseline)</div>
                <div className="scroll" style={{ maxHeight: 180 }}>
                  <table className="compare-table">
                    <thead>
                      <tr>
                        <th>profile</th>
                        <th>baseline</th>
                        <th>exp</th>
                        <th>delta</th>
                        <th>baseline text</th>
                        <th>exp text</th>
                      </tr>
                    </thead>
                    <tbody>
                      {abBatchData.delta_ranking.map((d: any) => (
                        <tr key={String(d.profile_id)}>
                          <td className="mono">{String(d.profile_id || "").slice(0, 8)}</td>
                          <td className="mono">{String(d.baseline_score ?? "-")}</td>
                          <td className="mono">{String(d.exp_score ?? "-")}</td>
                          <td className="mono">{String(d.delta ?? "-")}</td>
                          <td className="mono">{d.baseline_text_ver_id ? String(d.baseline_text_ver_id).slice(0, 8) : "-"}</td>
                          <td className="mono">{d.exp_text_ver_id ? String(d.exp_text_ver_id).slice(0, 8) : "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}

            {abBatchData?.combo_delta_ranking?.length ? (
              <div style={{ marginTop: 10 }}>
                <div className="h2">Combo Delta (exp - combo_baseline)</div>
                <div className="scroll" style={{ maxHeight: 180 }}>
                  <table className="compare-table">
                    <thead>
                      <tr>
                        <th>profile</th>
                        <th>combo baseline</th>
                        <th>exp</th>
                        <th>delta</th>
                        <th>combo text</th>
                        <th>exp text</th>
                      </tr>
                    </thead>
                    <tbody>
                      {abBatchData.combo_delta_ranking.map((d: any) => (
                        <tr key={`combo-${String(d.profile_id)}`}>
                          <td className="mono">{String(d.profile_id || "").slice(0, 8)}</td>
                          <td className="mono">{String(d.combo_baseline_score ?? "-")}</td>
                          <td className="mono">{String(d.exp_score ?? "-")}</td>
                          <td className="mono">{String(d.delta ?? "-")}</td>
                          <td className="mono">{d.combo_baseline_text_ver_id ? String(d.combo_baseline_text_ver_id).slice(0, 8) : "-"}</td>
                          <td className="mono">{d.exp_text_ver_id ? String(d.exp_text_ver_id).slice(0, 8) : "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}

            {assetTraceView ? (
              <div style={{ marginTop: 10 }}>
                <div className="h2">Injection Explanation</div>
                <div className="small mono">
                  trace_id={String(assetTraceView.trace_id || "").slice(0, 8)} · text_ver_id={String(assetTraceView.text_ver_id || "").slice(0, 8)} · bundle={assetTraceView.injected_bundle_id ? String(assetTraceView.injected_bundle_id).slice(0, 8) : "-"}
                </div>
                <pre style={{ maxHeight: 280, overflow: "auto", marginTop: 6 }}>
                  {JSON.stringify(assetTraceView.trace || {}, null, 2)}
                </pre>
              </div>
            ) : null}

            {bookId ? (
              <PolicySuggestionsPanel
                baseUrl={baseUrl}
                bookId={bookId}
                onStatus={setStatus}
                onOpenTrace={(textVerId) => {
                  void viewAssetSelectionTrace(textVerId).catch((err) => setStatus(String(err)));
                }}
              />
            ) : null}

            {bookId ? (
              <ComboLeaderboardPanel
                baseUrl={baseUrl}
                bookId={bookId}
                onStatus={setStatus}
                onOpenTrace={(textVerId) => {
                  void viewAssetSelectionTrace(textVerId).catch((err) => setStatus(String(err)));
                }}
              />
            ) : null}

            {bookId ? (
              <VolumePlanPanel
                baseUrl={baseUrl}
                bookId={bookId}
                chapterId={chapterId}
                onStatus={setStatus}
              />
            ) : null}

            {bookId ? (
              <ForeshadowBoardPanel
                baseUrl={baseUrl}
                bookId={bookId}
                chapterId={chapterId}
                onStatus={setStatus}
                onOpenTrace={(textVerId) => {
                  void viewAssetSelectionTrace(textVerId).catch((err) => setStatus(String(err)));
                }}
              />
            ) : null}
            {bookId ? (
              <GrowthBoardPanel
                baseUrl={baseUrl}
                bookId={bookId}
                chapterId={chapterId}
                onStatus={setStatus}
              />
            ) : null}
            <PayoffTemplatePanel
              baseUrl={baseUrl}
              onStatus={setStatus}
            />

            <div style={{ marginTop: 10 }}>
              <div className="h2">A/B Compare (from chapter reports)</div>
              <div className="scroll" style={{ maxHeight: 220 }}>
                {chapterReports.length === 0 ? (
                  <div className="hint">No reports loaded.</div>
                ) : (
                  Object.entries(
                    chapterReports.reduce((acc: Record<string, any[]>, it: any) => {
                      const key = String(it.profile_id_used || "unknown");
                      if (!acc[key]) acc[key] = [];
                      acc[key].push(it);
                      return acc;
                    }, {})
                  ).map(([pid, rows]) => {
                    const latest = [...rows].sort((a: any, b: any) => String(b.created_at).localeCompare(String(a.created_at)))[0] || {};
                    return (
                      <div key={pid} className="node-item" style={{ cursor: "default" }}>
                        <div style={{ width: "100%" }}>
                          <div className="row">
                            <strong className="mono">{pid.slice(0, 8)}</strong>
                            <span className="small">v{String(latest.profile_version_used ?? "-")}</span>
                            <span className="small">reports={rows.length}</span>
                          </div>
                          <div className="small">
                            eval_overall={String((latest.eval_summary || {}).overall ?? "-")} · sim_max=
                            {String((latest.simguard_summary || {}).max_score ?? "-")}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>
          <div className="wb-panel" style={{ minHeight: "auto", marginBottom: 10 }}>
            <h4 style={{ marginTop: 0 }}>Scoped Settings Center</h4>
            <div className="row" style={{ gap: 10, flexWrap: "wrap", alignItems: "end" }}>
              <label>
                Scope
                <select
                  value={settingsScope}
                  onChange={(e) => {
                    const scope = e.target.value as "global" | "book" | "chapter";
                    setSettingsScope(scope);
                  }}
                >
                  <option value="global">global</option>
                  <option value="book">book</option>
                  <option value="chapter">chapter</option>
                </select>
              </label>
              <label>
                book_id
                <input value={bookId} onChange={(e) => setBookId(e.target.value)} placeholder="required for book scope" />
              </label>
              <label>
                chapter_id
                <input value={chapterId} onChange={(e) => setChapterId(e.target.value)} placeholder="required for chapter/effective" />
              </label>
              <button onClick={() => void loadScopedSettings(settingsScope)}>Load Scoped</button>
              <button onClick={() => void saveScopedSettings()}>Save Scoped</button>
              <button onClick={() => void loadEffectiveSettings()}>Load Effective</button>
              <button onClick={() => void restoreDefaultScopedTemplate()}>Restore Defaults (Load)</button>
            </div>
            <div className="row" style={{ gap: 8, marginTop: 8 }}>
              <button className={settingsEditorMode === "basic" ? "on" : ""} onClick={() => setSettingsEditorMode("basic")}>Basic</button>
              <button className={settingsEditorMode === "advanced" ? "on" : ""} onClick={() => setSettingsEditorMode("advanced")}>Advanced</button>
              <span className="small" style={{ marginLeft: 8 }}>
                {scopedDirty ? "unsaved changes" : "saved"}
              </span>
              {scopedSettingsParseError ? <span className="small" style={{ color: "#b00020" }}>{scopedSettingsParseError}</span> : null}
            </div>
            <div className="row" style={{ gap: 10, marginTop: 10, alignItems: "stretch" }}>
              <div style={{ flex: 1 }}>
                <div className="small">Scoped JSON</div>
                {settingsEditorMode === "basic" ? (
                  <SettingsBasicPanel settingsObj={scopedSettingsObj || {}} onChange={applyBasicSettingsChange} />
                ) : (
                  <textarea
                    style={{ width: "100%", minHeight: 180 }}
                    value={scopedSettingsText}
                    onChange={(e) => {
                      const txt = e.target.value;
                      setScopedSettingsText(txt);
                      try {
                        const obj = JSON.parse(txt || "{}");
                        setScopedSettingsObj(obj && typeof obj === "object" ? obj : {});
                        setScopedSettingsParseError("");
                      } catch {
                        setScopedSettingsParseError("INVALID_SETTINGS_JSON");
                        // keep text editable even when JSON is temporarily invalid
                      }
                    }}
                  />
                )}
              </div>
              <div style={{ flex: 1 }}>
                <div className="small">Effective JSON (chapter merged)</div>
                <textarea style={{ width: "100%", minHeight: 180 }} value={effectiveSettingsText} readOnly />
                <div className="small" style={{ marginTop: 8 }}>Source hints</div>
                <div className="scroll" style={{ maxHeight: 180 }}>
                  {basicSourcePaths.map((p) => {
                    const src = sourceOfPath(p);
                    const val = getPathValue(effectiveSettingsObj, p, null);
                    return (
                      <div
                        key={p}
                        className="small mono"
                        style={{ cursor: "context-menu" }}
                        onContextMenu={(e) => {
                          e.preventDefault();
                          setTraceMenu({ x: e.clientX, y: e.clientY, key: p, value: val, source: src });
                        }}
                      >
                        {p} = {src}
                      </div>
                    );
                  })}
                </div>
                {traceMenu ? (
                  <div
                    style={{
                      position: "fixed",
                      left: traceMenu.x,
                      top: traceMenu.y,
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
                    <div className="small mono" style={{ marginBottom: 6 }}>{traceMenu.key}</div>
                    {canOverrideCurrentScope && traceMenu.source !== settingsScope ? (
                      <button
                        style={{ width: "100%", textAlign: "left" }}
                        onClick={() => {
                          overrideScopedKey(traceMenu.key, traceMenu.value);
                          setTraceMenu(null);
                        }}
                      >
                        Override at current scope
                      </button>
                    ) : null}
                    <button
                      style={{ width: "100%", textAlign: "left", marginTop: 4 }}
                      onClick={async () => {
                        try { await navigator.clipboard.writeText(traceMenu.key); } catch {}
                        setTraceMenu(null);
                      }}
                    >
                      Copy key
                    </button>
                    <button
                      style={{ width: "100%", textAlign: "left", marginTop: 4 }}
                      onClick={async () => {
                        try { await navigator.clipboard.writeText(JSON.stringify(traceMenu.value ?? null, null, 2)); } catch {}
                        setTraceMenu(null);
                      }}
                    >
                      Copy value
                    </button>
                  </div>
                ) : null}
                <div className="row" style={{ gap: 8, marginTop: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
                  <div style={{ minWidth: 220 }}>
                    <div className="label">Diff Pair</div>
                    <select className="input" value={settingsDiffPair} onChange={(e) => setSettingsDiffPair(e.target.value as any)}>
                      <option value="global_book">global ↔ book</option>
                      <option value="book_chapter">book ↔ chapter</option>
                      <option value="global_effective">global ↔ effective</option>
                    </select>
                  </div>
                  <button onClick={() => void computeSettingsDiff(settingsDiffPair)}>Refresh Diff</button>
                </div>
                <div style={{ marginTop: 10 }}>
                  <SettingsDiffPanel
                    title="Settings Diff"
                    changes={settingsDiffRows}
                    onOverrideBToScope={(k, v) => overrideScopedKey(k, v)}
                  />
                </div>
                <div className="card" style={{ marginTop: 10 }}>
                  <div className="h2">Presets</div>
                  <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
                    <label style={{ minWidth: 180 }}>
                      Name
                      <input value={settingsPresetName} onChange={(e) => setSettingsPresetName(e.target.value)} placeholder="热血快节奏" />
                    </label>
                    <label style={{ minWidth: 220 }}>
                      Description
                      <input value={settingsPresetDesc} onChange={(e) => setSettingsPresetDesc(e.target.value)} placeholder="optional" />
                    </label>
                    <button onClick={() => void createSettingsPresetFromCurrent()}>Save Current as Preset</button>
                    <button onClick={() => void loadSettingsPresets()}>Reload Presets</button>
                  </div>
                  <div className="scroll" style={{ maxHeight: 220, marginTop: 10 }}>
                    {settingsPresets.length === 0 ? <div className="hint">No presets.</div> : null}
                    {settingsPresets.map((p) => (
                      <div key={p.preset_id} className="node-item" style={{ cursor: "default" }}>
                        <div style={{ width: "100%" }}>
                          <div className="row">
                            <strong>{p.name}</strong>
                            <span className="small">{p.description || ""}</span>
                          </div>
                          <div className="row" style={{ marginTop: 6 }}>
                            <button onClick={() => void applyPresetToCurrentScope(String(p.preset_id))}>Apply to {settingsScope}</button>
                            <button onClick={() => void deletePreset(String(p.preset_id))}>Delete</button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <SettingsAuditPanel
                  items={settingsAuditRows}
                  loading={settingsAuditLoading}
                  onRefresh={() => void loadSettingsAudit()}
                  onPreviewRollback={(it) => void openRollbackPreview(it)}
                  onRollback={(id) => void rollbackSettingsAuditItem(id)}
                />
                {rollbackPreviewAudit ? (
                  <div className="card" style={{ marginTop: 10 }}>
                    <div className="h2">Rollback Preview</div>
                    <div className="small mono">
                      audit_id={String(rollbackPreviewAudit.audit_id)} · action={String(rollbackPreviewAudit.action)}
                    </div>
                    <div style={{ marginTop: 10 }}>
                      <SettingsDiffPanel title="After (current) → Before (rollback target)" changes={rollbackPreviewDiffRows} />
                    </div>
                    <div className="row" style={{ gap: 8, marginTop: 10 }}>
                      <button onClick={() => void confirmRollbackFromPreview()}>Confirm Rollback</button>
                      <button onClick={() => { setRollbackPreviewAudit(null); setRollbackPreviewDiffRows([]); }}>Cancel</button>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
          <div className="settings-grid">
            <label>
              Active Provider
              <select
                value={activeProvider}
                onChange={(e) => {
                  const provider = e.target.value as ProviderId;
                  setSettingsData(syncLegacyOllama({ ...settingsData, ai_provider: provider }));
                }}
              >
                <option value="ollama">ollama (local)</option>
                <option value="openai">openai (cloud/local proxy)</option>
                <option value="openai_compatible">openai-compatible (local)</option>
              </select>
            </label>
            <label>
              Provider Preset
              <select
                value=""
                onChange={(e) => {
                  const preset = e.target.value;
                  if (!preset) return;
                  if (preset === "ollama_local") {
                    const next = {
                      ...settingsData,
                      ai_provider: "ollama",
                      providers: {
                        ...settingsData.providers,
                        ollama: {
                          ...getProviderConfig(settingsData, "ollama"),
                          base_url: "http://127.0.0.1:11434",
                          llm_model: "qwen2.5:7b",
                          embedding_model: "bge-m3:latest",
                          chat_path: "/api/chat",
                          embeddings_path: "/api/embeddings",
                        }
                      }
                    };
                    setSettingsData(syncLegacyOllama(next));
                  } else if (preset === "openai_default") {
                    const next = {
                      ...settingsData,
                      ai_provider: "openai",
                      providers: {
                        ...settingsData.providers,
                        openai: {
                          ...getProviderConfig(settingsData, "openai"),
                          base_url: "https://api.openai.com/v1",
                          chat_path: "/chat/completions",
                          embeddings_path: "/embeddings",
                        }
                      }
                    };
                    setSettingsData(syncLegacyOllama(next));
                  } else if (preset === "openai_local") {
                    const next = {
                      ...settingsData,
                      ai_provider: "openai_compatible",
                      providers: {
                        ...settingsData.providers,
                        openai_compatible: {
                          ...getProviderConfig(settingsData, "openai_compatible"),
                          base_url: "http://127.0.0.1:8000/v1",
                          chat_path: "/chat/completions",
                          embeddings_path: "/embeddings",
                        }
                      }
                    };
                    setSettingsData(syncLegacyOllama(next));
                  }
                }}
              >
                <option value="">apply preset...</option>
                <option value="ollama_local">Ollama local (127.0.0.1:11434)</option>
                <option value="openai_default">OpenAI official</option>
                <option value="openai_local">OpenAI-compatible local (127.0.0.1:8000/v1)</option>
              </select>
            </label>
          </div>
          <div className="settings-grid">
            <label>
              API Base URL
              <input
                value={activeProviderConfig.base_url || ""}
                onChange={(e) =>
                  setSettingsData(syncLegacyOllama({
                    ...settingsData,
                    providers: {
                      ...settingsData.providers,
                      [activeProvider]: {
                        ...getProviderConfig(settingsData, activeProvider),
                        base_url: e.target.value
                      }
                    }
                  }))
                }
              />
            </label>
            <label>
              API Key
              <input
                type="password"
                placeholder="optional for local providers"
                value={activeProviderConfig.api_key || ""}
                onChange={(e) =>
                  setSettingsData(syncLegacyOllama({
                    ...settingsData,
                    providers: {
                      ...settingsData.providers,
                      [activeProvider]: {
                        ...getProviderConfig(settingsData, activeProvider),
                        api_key: e.target.value
                      }
                    }
                  }))
                }
              />
            </label>
            <label>
              LLM Model
              <input
                value={activeProviderConfig.llm_model || ""}
                onChange={(e) =>
                  setSettingsData(syncLegacyOllama({
                    ...settingsData,
                    providers: {
                      ...settingsData.providers,
                      [activeProvider]: {
                        ...getProviderConfig(settingsData, activeProvider),
                        llm_model: e.target.value
                      }
                    }
                  }))
                }
              />
            </label>
            <label>
              Embedding Model
              <input
                value={activeProviderConfig.embedding_model || ""}
                onChange={(e) =>
                  setSettingsData(syncLegacyOllama({
                    ...settingsData,
                    providers: {
                      ...settingsData.providers,
                      [activeProvider]: {
                        ...getProviderConfig(settingsData, activeProvider),
                        embedding_model: e.target.value
                      }
                    }
                  }))
                }
              />
            </label>
            <label>
              Chat Path
              <input
                value={activeProviderConfig.chat_path || ""}
                onChange={(e) =>
                  setSettingsData(syncLegacyOllama({
                    ...settingsData,
                    providers: {
                      ...settingsData.providers,
                      [activeProvider]: {
                        ...getProviderConfig(settingsData, activeProvider),
                        chat_path: e.target.value
                      }
                    }
                  }))
                }
              />
            </label>
            <label>
              Embeddings Path
              <input
                value={activeProviderConfig.embeddings_path || ""}
                onChange={(e) =>
                  setSettingsData(syncLegacyOllama({
                    ...settingsData,
                    providers: {
                      ...settingsData.providers,
                      [activeProvider]: {
                        ...getProviderConfig(settingsData, activeProvider),
                        embeddings_path: e.target.value
                      }
                    }
                  }))
                }
              />
            </label>
            <label>
              vec_high
              <input
                type="number"
                step={0.01}
                value={settingsData.similarity?.vec_high ?? 0.86}
                onChange={(e) => setSettingsData({ ...settingsData, similarity: { ...settingsData.similarity, vec_high: Number(e.target.value) } })}
              />
            </label>
            <label>
              llm_concurrency
              <input
                type="number"
                value={settingsData.limits?.llm_concurrency ?? 1}
                onChange={(e) => setSettingsData({ ...settingsData, limits: { ...settingsData.limits, llm_concurrency: Number(e.target.value) } })}
              />
            </label>
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <button onClick={() => void saveSettings()}>Save Settings</button>
            <button onClick={() => void checkHealth()}>Health Check</button>
            <button onClick={() => void runMaintenance("/v1/system/rebuild_fts")}>Rebuild FTS</button>
            <button onClick={() => void runMaintenance("/v1/system/cleanup_jobs")}>Cleanup Jobs</button>
          </div>
          <pre style={{ marginTop: 10 }}>{JSON.stringify(health, null, 2)}</pre>
        </section>
      ) : null}

      {searchOpen ? (
        <div className="global-search-overlay" onMouseDown={closeGlobalSearch}>
          <div className="global-search-modal" onMouseDown={(e) => e.stopPropagation()}>
            <div className="row" style={{ marginBottom: 8 }}>
              <strong>Unified Search</strong>
              <span className="small">books / chapters / material / skill_runs</span>
            </div>
            <input
              autoFocus
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "ArrowDown") {
                  e.preventDefault();
                  setSearchSelectedIndex((v) => Math.min(v + 1, Math.max(0, searchItems.length - 1)));
                } else if (e.key === "ArrowUp") {
                  e.preventDefault();
                  setSearchSelectedIndex((v) => Math.max(v - 1, 0));
                } else if (e.key === "Enter") {
                  e.preventDefault();
                  void applyGlobalSearchItem(searchItems[searchSelectedIndex]);
                } else if (e.key === "Escape") {
                  e.preventDefault();
                  closeGlobalSearch();
                }
              }}
              placeholder="Search by title/name..."
            />
            <div className="small" style={{ marginTop: 8 }}>
              {searchLoading ? "Searching..." : `${searchItems.length} results`}
            </div>
            <div className="scroll" style={{ marginTop: 8, maxHeight: 380 }}>
              {searchItems.map((it, idx) => (
                <button
                  key={`${it.type}:${it.id}`}
                  className={`node-item ${idx === searchSelectedIndex ? "active" : ""}`}
                  onMouseEnter={() => setSearchSelectedIndex(idx)}
                  onClick={() => void applyGlobalSearchItem(it)}
                >
                  <div style={{ width: "100%" }}>
                    <div className="row">
                      <span>
                        <span className="badge">{it.type}</span> {it.title}
                      </span>
                      <code>{Number(it.score || 0).toFixed(2)}</code>
                    </div>
                    <div className="small">{it.subtitle}</div>
                  </div>
                </button>
              ))}
              {!searchLoading && searchItems.length === 0 ? <div className="hint">Type keyword to search.</div> : null}
            </div>
            <div className="small" style={{ marginTop: 8 }}>
              ↑↓ navigate · Enter open · Esc close
            </div>
          </div>
        </div>
      ) : null}

      {compareOpen ? (
        <CompareDrawer
          chapterId={chapterId}
          compareFrom={compareFrom}
          compareTo={compareTo}
          compareDiff={compareDiff}
          evalCompare={evalCompare}
          evalBeforeRun={evalBeforeRun}
          evalAfterRun={evalAfterRun}
          reportPdfPath={reportPdfPath}
          latestChapterReport={latestChapterReport}
          onOpenProfileVersion={(profileId, version) => void openProfileVersionFromReport(profileId, version)}
          onClose={() => setCompareOpen(false)}
          onLoadDiff={loadOutlineDiff}
          onLoadEvalCompare={loadEvalCompare}
          onExportHtml={exportChapterRevisionHtml}
          onExportPdf={exportChapterRevisionPdf}
          onOpenFolder={openReportFolder}
        />
      ) : null}
    </div>
  );
}
