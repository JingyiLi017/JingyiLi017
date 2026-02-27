import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
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
import { CapabilityClarityPanel } from "./CapabilityClarityPanel";
import { HelpCenterPanel } from "./HelpCenterPanel";
import { AssetCenterPanel } from "./AssetCenterPanel";
import { DeleteConfirmDialog } from "./DeleteConfirmDialog";
import type { ArcTarget, BookItem, ChapterItem, GlobalSearchItem, Health, JobItem, OutlineDetail, ProfileCfg, ProfileVersionItem, ProviderId, RefUnifiedItem, SkillRun, SplitbookItem, TemplateAssetItem, TemplateVariant, VersionItem } from "./app/types";
import { defaultSettings, defaultStyle, defaultTargets, flowStepLabel, formatJobStatusLabel, formatJobTypeLabel, formatPhaseLabel, formatPipelineStatus, formatRefKindLabel, formatScopeLabel, formatSearchTypeLabel, getProviderConfig, quickStepLabel, syncLegacyOllama } from "./app/defaults";
import { createJob, waitJobDone } from "./app/jobs";

export function App() {
  type RecommendedRunItem = {
    id: string;
    ts: string;
    track: "writing" | "splitbook";
    step: string;
    detail: string;
  };
  type RecommendedExecStatus = {
    state: "idle" | "processing" | "success" | "error";
    message: string;
    progressPct?: number;
    progressText?: string;
  };
  type TriggerMode = "manual" | "recommended" | "one_click" | "auto";
  type TriggerMetaInput = {
    source: string;
    entry: string;
    mode: TriggerMode;
  };
  type StructureStepBasisState = {
    status: "idle" | "running" | "success" | "error";
    basis: string;
    detail: string;
    updatedAt: string;
  };
  type ChapterGenerationTraceState = {
    status: "idle" | "running" | "success" | "error";
    mode: "single" | "batch";
    basis: string;
    chapters: string;
    chapterIds: string[];
    detail: string;
    updatedAt: string;
  };
  type ChapterOutlineOverviewItem = {
    chapterId: string;
    chapterNo: number;
    title: string;
    outlineVersion: number;
    outlineNodes: number;
    outlineSummary: string;
    updatedAt: string;
    loadError: string;
  };
  type ChapterOutlinePreviewDialogState = {
    chapterId: string;
    chapterNo: number;
    title: string;
    selectedVersion: string;
    outlineVersion: number;
    outline: OutlineDetail | null;
    versions: VersionItem[];
  };
  type ChapterOutlinePreviewMatchState = {
    nodeId: string;
    keyword: string;
    start: number;
    end: number;
    matched: boolean;
  };
  type DataDeleteKind =
    | "book"
    | "chapter"
    | "profile"
    | "template_asset"
    | "structure_template"
    | "settings_preset"
    | "jobs_cleanup";
  const [baseUrl, setBaseUrl] = useState("http://127.0.0.1:17777");
  const [chapterId, setChapterId] = useState("");
  const [bookId, setBookId] = useState("");
  const [outline, setOutline] = useState<OutlineDetail | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [versions, setVersions] = useState<VersionItem[]>([]);
  const [selectedVersion, setSelectedVersion] = useState("latest");
  const [outlineInjectStatus, setOutlineInjectStatus] = useState<{
    ready: boolean;
    version: number;
    nodeCount: number;
    updatedAt: string;
    message: string;
  }>({
    ready: false,
    version: 0,
    nodeCount: 0,
    updatedAt: "",
    message: "未检测",
  });
  const [bookQuery, setBookQuery] = useState("");
  const [chapterQuery, setChapterQuery] = useState("");
  const [bookItems, setBookItems] = useState<BookItem[]>([]);
  const [chapterItems, setChapterItems] = useState<ChapterItem[]>([]);
  const [bookDeleting, setBookDeleting] = useState(false);
  const [chapterDeleting, setChapterDeleting] = useState(false);
  const [writerSimpleMode, setWriterSimpleMode] = useState(true);
  const [workspaceMode, setWorkspaceMode] = useState<"dual" | "writing" | "splitbook">("dual");
  const [recommendedRuns, setRecommendedRuns] = useState<RecommendedRunItem[]>([]);
  const [recommendedWritingStatus, setRecommendedWritingStatus] = useState<RecommendedExecStatus>({
    state: "idle",
    message: "未执行",
    progressPct: 0,
  });
  const [recommendedSplitbookStatus, setRecommendedSplitbookStatus] = useState<RecommendedExecStatus>({
    state: "idle",
    message: "未执行",
    progressPct: 0,
  });
  const [newBookName, setNewBookName] = useState("");
  const [newBookAuthor, setNewBookAuthor] = useState("");
  const [newBookLanguage, setNewBookLanguage] = useState("zh");
  const [newBookNotes, setNewBookNotes] = useState("");
  const [newBookWorkspacePath, setNewBookWorkspacePath] = useState("");
  const [storyGenre, setStoryGenre] = useState("");
  const [storyTheme, setStoryTheme] = useState("");
  const [storyTone, setStoryTone] = useState("");
  const [storyAudience, setStoryAudience] = useState("");
  const [storyIdea, setStoryIdea] = useState("");
  const [storySetting, setStorySetting] = useState("");
  const [masterOutline, setMasterOutline] = useState<any | null>(null);
  const [masterOutlineSummary, setMasterOutlineSummary] = useState("");
  const [masterOutlinePlannedChapters, setMasterOutlinePlannedChapters] = useState(0);
  const [masterOutlineBusy, setMasterOutlineBusy] = useState(false);
  const [masterOutlineAiMeta, setMasterOutlineAiMeta] = useState<any | null>(null);
  const [aiDebugBusy, setAiDebugBusy] = useState(false);
  const [aiDebugError, setAiDebugError] = useState("");
  const [aiDebugData, setAiDebugData] = useState<any | null>(null);
  const [volumeItems, setVolumeItems] = useState<any[]>([]);
  const [volumePlanPreview, setVolumePlanPreview] = useState<any | null>(null);
  const [volumePlanApplied, setVolumePlanApplied] = useState<any | null>(null);
  const [chapterOutlineSeed, setChapterOutlineSeed] = useState<any | null>(null);
  const [chapterOutlineOverview, setChapterOutlineOverview] = useState<ChapterOutlineOverviewItem[]>([]);
  const [chapterOutlineOverviewLoading, setChapterOutlineOverviewLoading] = useState(false);
  const [chapterOutlinePreviewBusyId, setChapterOutlinePreviewBusyId] = useState("");
  const [chapterOutlineDeleteBusyId, setChapterOutlineDeleteBusyId] = useState("");
  const [chapterOutlinePreviewDialog, setChapterOutlinePreviewDialog] = useState<ChapterOutlinePreviewDialogState | null>(null);
  const [chapterOutlinePreviewDialogLoading, setChapterOutlinePreviewDialogLoading] = useState(false);
  const [chapterOutlinePreviewApplyBusy, setChapterOutlinePreviewApplyBusy] = useState(false);
  const [chapterOutlinePreviewText, setChapterOutlinePreviewText] = useState("");
  const [chapterOutlinePreviewTextDraftId, setChapterOutlinePreviewTextDraftId] = useState("");
  const [chapterOutlinePreviewTextSource, setChapterOutlinePreviewTextSource] = useState<"draft" | "text_version" | "">("");
  const [chapterOutlinePreviewTextUpdatedAt, setChapterOutlinePreviewTextUpdatedAt] = useState("");
  const [chapterOutlinePreviewTextLoading, setChapterOutlinePreviewTextLoading] = useState(false);
  const [chapterOutlinePreviewTextSaving, setChapterOutlinePreviewTextSaving] = useState(false);
  const [chapterOutlinePreviewTextDirty, setChapterOutlinePreviewTextDirty] = useState(false);
  const [chapterOutlinePreviewActiveNodeId, setChapterOutlinePreviewActiveNodeId] = useState("");
  const [chapterOutlinePreviewMatchInfo, setChapterOutlinePreviewMatchInfo] = useState<ChapterOutlinePreviewMatchState | null>(null);
  const [writerStudioBusy, setWriterStudioBusy] = useState(false);
  const [structurePipelineBusy, setStructurePipelineBusy] = useState(false);
  const [structurePipelineStep, setStructurePipelineStep] = useState<"idle" | "volume_preview" | "volume_apply" | "chapter_seed" | "control_plan" | "done" | "failed">("idle");
  const [structurePipelineError, setStructurePipelineError] = useState("");
  const [structureStepBasis, setStructureStepBasis] = useState<Record<"1.3.1" | "1.3.2" | "1.4.1" | "1.4.2", StructureStepBasisState>>({
    "1.3.1": { status: "idle", basis: "待执行", detail: "", updatedAt: "" },
    "1.3.2": { status: "idle", basis: "待执行", detail: "", updatedAt: "" },
    "1.4.1": { status: "idle", basis: "待执行", detail: "", updatedAt: "" },
    "1.4.2": { status: "idle", basis: "待执行", detail: "", updatedAt: "" },
  });
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
  const [status, setStatus] = useState("就绪");
  const [quickVolumeId, setQuickVolumeId] = useState("");
  const [quickDraftRunOut, setQuickDraftRunOut] = useState<any>(null);
  const [quickVersionsOut, setQuickVersionsOut] = useState<any>(null);
  const [quickPublishOut, setQuickPublishOut] = useState<any>(null);
  const [quickDraftConfirmBusy, setQuickDraftConfirmBusy] = useState(false);
  const [quickDraftConfirmAt, setQuickDraftConfirmAt] = useState("");
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
  const [closedLoopBusy, setClosedLoopBusy] = useState(false);
  const [closedLoopSteps, setClosedLoopSteps] = useState<Record<string, string>>({
    draft: "idle",
    writeback: "idle",
    preflight: "idle",
    rewrite: "idle",
    style_evolution: "idle",
  });
  const [closedLoopDoWriteback, setClosedLoopDoWriteback] = useState(true);
  const [closedLoopRunPreflight, setClosedLoopRunPreflight] = useState(true);
  const [closedLoopRewriteEnabled, setClosedLoopRewriteEnabled] = useState(false);
  const [closedLoopRewriteAutoAccept, setClosedLoopRewriteAutoAccept] = useState(false);
  const [closedLoopFailOnPreflightFail, setClosedLoopFailOnPreflightFail] = useState(false);
  const [closedLoopEvolveStyle, setClosedLoopEvolveStyle] = useState(true);
  const [closedLoopOutput, setClosedLoopOutput] = useState<any>(null);
  const [chapterDraftPreviewText, setChapterDraftPreviewText] = useState("");
  const [chapterDraftPreviewDraftId, setChapterDraftPreviewDraftId] = useState("");
  const [chapterDraftPreviewSource, setChapterDraftPreviewSource] = useState<"draft" | "text_version" | "">("");
  const [chapterDraftPreviewUpdatedAt, setChapterDraftPreviewUpdatedAt] = useState("");
  const [chapterDraftPreviewLoading, setChapterDraftPreviewLoading] = useState(false);
  const [chapterDraftPreviewDirty, setChapterDraftPreviewDirty] = useState(false);
  const [manualChapterImportBusy, setManualChapterImportBusy] = useState(false);
  const [manualChapterImportText, setManualChapterImportText] = useState("");
  const [manualChapterImportNote, setManualChapterImportNote] = useState("手动导入自写章节");
  const [chapterGenerationTrace, setChapterGenerationTrace] = useState<ChapterGenerationTraceState>({
    status: "idle",
    mode: "single",
    basis: "待执行",
    chapters: "",
    chapterIds: [],
    detail: "",
    updatedAt: "",
  });
  const [batchGenerateCount, setBatchGenerateCount] = useState(1);
  const [batchGenerateBusy, setBatchGenerateBusy] = useState(false);
  const [styleEvolutionBusy, setStyleEvolutionBusy] = useState(false);
  const [styleEvolutionOutput, setStyleEvolutionOutput] = useState<any>(null);
  const [styleEvolutionLatest, setStyleEvolutionLatest] = useState<any>(null);

  const [showJobs, setShowJobs] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showRefCenter, setShowRefCenter] = useState(false);
  const [showSplitbooks, setShowSplitbooks] = useState(false);
  const [showAgentConsole, setShowAgentConsole] = useState(false);
  const [showVersionCenter, setShowVersionCenter] = useState(false);
  const [showRewriteCenter, setShowRewriteCenter] = useState(false);
  const [showReleaseCenter, setShowReleaseCenter] = useState(false);
  const [showTensionCenter, setShowTensionCenter] = useState(false);
  const [showHelpCenter, setShowHelpCenter] = useState(false);
  const [showAssetCenter, setShowAssetCenter] = useState(false);
  const [refCenterTab, setRefCenterTab] = useState<"material" | "template">("material");
  const [jobTab, setJobTab] = useState<"queued" | "running" | "succeeded" | "failed" | "canceled">("running");
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [selectedJob, setSelectedJob] = useState<JobItem | null>(null);
  const [jobSkillRunFilter, setJobSkillRunFilter] = useState("");
  const [jobCleanupBusy, setJobCleanupBusy] = useState(false);
  const [jobResumeBusyId, setJobResumeBusyId] = useState("");
  const [jobResumeBatchBusy, setJobResumeBatchBusy] = useState(false);
  const [jobDeleteBusyId, setJobDeleteBusyId] = useState("");
  const [jobAutoRefreshEnabled, setJobAutoRefreshEnabled] = useState(true);
  const [jobPollIntervalMs, setJobPollIntervalMs] = useState(5000);
  const [jobInspectLock, setJobInspectLock] = useState(true);
  const [jobAutoPauseOnInspect, setJobAutoPauseOnInspect] = useState(true);
  const [jobInspectingDetail, setJobInspectingDetail] = useState(false);
  const [draftConfirmTasks, setDraftConfirmTasks] = useState<any[]>([]);
  const [draftConfirmSummary, setDraftConfirmSummary] = useState<{ total: number; confirmed: number; pending: number } | null>(null);
  const [draftConfirmLoading, setDraftConfirmLoading] = useState(false);

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
  const [presetDeletingId, setPresetDeletingId] = useState("");
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
  const [writingMaterialQuickNote, setWritingMaterialQuickNote] = useState("");
  const [writingMaterialImportBusy, setWritingMaterialImportBusy] = useState(false);
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
  const [splitbookPath, setSplitbookPath] = useState("");
  const [splitbookChunkSize, setSplitbookChunkSize] = useState(600);
  const [splitbookOverlap, setSplitbookOverlap] = useState(120);
  const [splitbookRunningJobs, setSplitbookRunningJobs] = useState<JobItem[]>([]);
  const [splitbookRecentJobs, setSplitbookRecentJobs] = useState<JobItem[]>([]);
  const [splitbookPipelineBusy, setSplitbookPipelineBusy] = useState(false);
  const [splitbookRefreshBusy, setSplitbookRefreshBusy] = useState(false);
  const [splitbookPipelineStep, setSplitbookPipelineStep] = useState<
    "idle" | "ingest" | "embed" | "extract_structured" | "build_templates" | "build_profile" | "writeback_batch" | "done" | "failed"
  >("idle");
  const [splitbookPipelineError, setSplitbookPipelineError] = useState("");
  const [splitbookPathCheck, setSplitbookPathCheck] = useState<{ ok: boolean; message: string } | null>(null);
  const [splitbookOutputDir, setSplitbookOutputDir] = useState("");
  const [splitbookOutputDirCheck, setSplitbookOutputDirCheck] = useState<{ ok: boolean; message: string } | null>(null);
  const [splitbookLedgerView, setSplitbookLedgerView] = useState<"chapter" | "character">("chapter");
  const [splitbookLedgerRows, setSplitbookLedgerRows] = useState<any[]>([]);
  const [splitbookLedgerSummary, setSplitbookLedgerSummary] = useState<any | null>(null);
  const [splitbookOutlinePreview, setSplitbookOutlinePreview] = useState<any | null>(null);
  const [splitbookChapterNo, setSplitbookChapterNo] = useState(1);
  const [splitbookChapterPack, setSplitbookChapterPack] = useState<any | null>(null);
  const [writingSplitbookRefId, setWritingSplitbookRefId] = useState("");
  const [writingSplitbookRefScope, setWritingSplitbookRefScope] = useState<"book" | "chapter">("book");
  const [writingSplitbookRefChapterNo, setWritingSplitbookRefChapterNo] = useState(1);
  const [writingSplitbookRefBusy, setWritingSplitbookRefBusy] = useState(false);
  const [writingSplitbookRefLast, setWritingSplitbookRefLast] = useState<{
    splitbookId: string;
    splitbookName: string;
    scope: "book" | "chapter";
    chapterNo: number | null;
    conflicts: number;
    foreshadow: number;
    payoff: number;
    injectedAt: string;
  } | null>(null);
  const [splitbookWritebackText, setSplitbookWritebackText] = useState("");
  const [splitbookWritebackChapterFilter, setSplitbookWritebackChapterFilter] = useState("");
  const [splitbookWritebackBatchForce, setSplitbookWritebackBatchForce] = useState(false);
  const [splitbookWritebackBatchBusy, setSplitbookWritebackBatchBusy] = useState(false);
  const [splitbookWritebackBatchPreview, setSplitbookWritebackBatchPreview] = useState<any | null>(null);
  const [splitbookWritebackBatchConfirm, setSplitbookWritebackBatchConfirm] = useState<any | null>(null);
  const [splitbookHealthReport, setSplitbookHealthReport] = useState<any | null>(null);
  const [splitbookAntiCopyReport, setSplitbookAntiCopyReport] = useState<any | null>(null);
  const [splitbookLibraryIds, setSplitbookLibraryIds] = useState("");
  const [splitbookLibraryResult, setSplitbookLibraryResult] = useState<any | null>(null);
  const [splitbookSimpleMode, setSplitbookSimpleMode] = useState(true);
  const [splitbookShowAdvanced, setSplitbookShowAdvanced] = useState(false);
  const [splitbookStep4Busy, setSplitbookStep4Busy] = useState(false);
  const [splitbookResegmentBusy, setSplitbookResegmentBusy] = useState(false);
  const [splitbookStep3TreeOpen, setSplitbookStep3TreeOpen] = useState(true);
  const [splitbookDeletingId, setSplitbookDeletingId] = useState("");
  const [splitbookDeleteError, setSplitbookDeleteError] = useState("");
  const [splitbookDeleteInputShake, setSplitbookDeleteInputShake] = useState(false);
  const [splitbookDeleteDialog, setSplitbookDeleteDialog] = useState<{
    splitbookId: string;
    name: string;
    purgeAssets: boolean;
    typedName: string;
  } | null>(null);
  const [splitbookIngestDialog, setSplitbookIngestDialog] = useState<{
    actionText: string;
    splitbookName: string;
    sourcePath: string;
    expectedText: string;
    typedText: string;
  } | null>(null);
  const [splitbookIngestConfirmError, setSplitbookIngestConfirmError] = useState("");
  const [splitbookIngestInputShake, setSplitbookIngestInputShake] = useState(false);
  const [templateType, setTemplateType] = useState("");
  const [templateTag, setTemplateTag] = useState("");
  const [templateQuery, setTemplateQuery] = useState("");
  const [templateItems, setTemplateItems] = useState<TemplateAssetItem[]>([]);
  const [templateSelected, setTemplateSelected] = useState<TemplateAssetItem | null>(null);
  const [templateLoading, setTemplateLoading] = useState(false);
  const [templateNote, setTemplateNote] = useState("");
  const [templateAssetDeletingId, setTemplateAssetDeletingId] = useState("");
  const [structureTemplateDeletingId, setStructureTemplateDeletingId] = useState("");
  const [refUnifiedQuery, setRefUnifiedQuery] = useState("");
  const [refUnifiedLoading, setRefUnifiedLoading] = useState(false);
  const [refUnifiedItems, setRefUnifiedItems] = useState<RefUnifiedItem[]>([]);
  const [profileDeleting, setProfileDeleting] = useState(false);
  const [dataDeleteDialog, setDataDeleteDialog] = useState<{
    kind: DataDeleteKind;
    id: string;
    name: string;
    message: string;
    typedName: string;
  } | null>(null);
  const [dataDeleteError, setDataDeleteError] = useState("");
  const [dataDeleteInputShake, setDataDeleteInputShake] = useState(false);

  const timerRef = useRef<number | null>(null);
  const seenJobIdsRef = useRef<Set<string>>(new Set());
  const pollInitializedRef = useRef(false);
  const selectedJobRef = useRef<JobItem | null>(null);
  const jobInspectLockRef = useRef(true);
  const jobPollIntervalRef = useRef(5000);
  const embedTelemetryRef = useRef<Record<string, { samples: Array<{ ts: number; done: number; total: number }> }>>({});
  const splitbookDeleteInputRef = useRef<HTMLInputElement | null>(null);
  const splitbookDeleteShakeTimerRef = useRef<number | null>(null);
  const splitbookIngestInputRef = useRef<HTMLInputElement | null>(null);
  const splitbookIngestShakeTimerRef = useRef<number | null>(null);
  const splitbookIngestConfirmResolverRef = useRef<((ok: boolean) => void) | null>(null);
  const dataDeleteInputRef = useRef<HTMLInputElement | null>(null);
  const dataDeleteShakeTimerRef = useRef<number | null>(null);
  const chapterOutlinePreviewTextRef = useRef<HTMLTextAreaElement | null>(null);
  const chapterDraftPreviewTextRef = useRef<HTMLTextAreaElement | null>(null);

  function extractStructureTemplateId(asset: TemplateAssetItem | null): string {
    const span = asset?.source_span;
    if (!span || typeof span !== "object") return "";
    const bag = span as Record<string, unknown>;
    const keys = ["template_id", "structure_template_id", "source_template_id", "id"];
    for (const k of keys) {
      const v = String((bag as any)?.[k] || "").trim();
      if (v) return v;
    }
    return "";
  }

  const selectedNode = useMemo(() => outline?.nodes?.find((n) => n.node_id === selectedNodeId) ?? null, [outline, selectedNodeId]);
  const selectedTemplateStructureId = useMemo(() => extractStructureTemplateId(templateSelected), [templateSelected]);

  useEffect(() => {
    selectedJobRef.current = selectedJob;
  }, [selectedJob]);

  useEffect(() => {
    jobInspectLockRef.current = jobInspectLock;
  }, [jobInspectLock]);

  useEffect(() => {
    jobPollIntervalRef.current = jobPollIntervalMs;
  }, [jobPollIntervalMs]);

  useEffect(() => {
    if (!showJobs) setJobInspectingDetail(false);
  }, [showJobs]);

  useEffect(() => {
    setSplitbookWritebackBatchPreview(null);
    setSplitbookWritebackBatchConfirm(null);
  }, [selectedSplitbookId]);

  function extractSkillRunId(job: JobItem): string {
    const resultId = String((job.result as any)?.skill_run_id || "");
    if (resultId) return resultId;
    const runId = String((job as any)?.run_id || "");
    if (runId) return runId;
    return "";
  }

  function canCancelJob(status: string): boolean {
    const s = String(status || "").trim().toLowerCase();
    return s === "queued" || s === "running";
  }

  function canDeleteJobRecord(status: string): boolean {
    const s = String(status || "").trim().toLowerCase();
    return s === "succeeded" || s === "failed" || s === "canceled" || s === "cancelled";
  }

  function isActiveJobStatus(status: string): boolean {
    const s = String(status || "").trim().toLowerCase();
    return s === "queued" || s === "running";
  }

  function getJobUpdateAgeSeconds(job: JobItem): number {
    const ts = Date.parse(String(job?.updated_at || job?.created_at || ""));
    if (!Number.isFinite(ts)) return 0;
    return Math.max(0, Math.round((Date.now() - ts) / 1000));
  }

  function getJobStallThresholdSeconds(job: JobItem): number {
    const status = String(job?.status || "").trim().toLowerCase();
    const capability = String(job?.capability_id || "").trim().toLowerCase();
    if (status === "queued") {
      if (capability.startsWith("splitbook.")) return 900;
      return 300;
    }
    if (status !== "running") return 240;
    if (capability === "splitbook.embed.v1") return 1200;
    if (capability === "splitbook.ingest.v1") return 900;
    if (capability.startsWith("splitbook.")) return 600;
    return 240;
  }

  function isJobLikelyStalled(job: JobItem, thresholdSeconds?: number): boolean {
    const status = String(job?.status || "").trim().toLowerCase();
    if (status !== "running" && status !== "queued") return false;
    const ageSeconds = getJobUpdateAgeSeconds(job);
    const threshold = thresholdSeconds ?? getJobStallThresholdSeconds(job);
    return ageSeconds >= threshold;
  }

  function isJobLongGapButExpected(job: JobItem): boolean {
    const status = String(job?.status || "").trim().toLowerCase();
    const capability = String(job?.capability_id || "").trim().toLowerCase();
    if (status !== "running" || !capability.startsWith("splitbook.")) return false;
    if (isJobLikelyStalled(job)) return false;
    const ageSeconds = getJobUpdateAgeSeconds(job);
    return ageSeconds >= 120;
  }

  function canResumeJob(job: JobItem): boolean {
    const status = String(job?.status || "").trim().toLowerCase();
    if (status === "queued" || status === "failed") return true;
    if (status === "running") return isJobLikelyStalled(job);
    return false;
  }

  function parseEmbedDoneTotal(job: JobItem): { done: number; total: number } | null {
    const capability = String(job?.capability_id || "").trim().toLowerCase();
    if (capability !== "splitbook.embed.v1") return null;
    const progress = (job?.progress || {}) as Record<string, any>;
    const msg = String(progress?.message || "");
    const m = msg.match(/向量化\s*(\d+)\s*\/\s*(\d+)/) || msg.match(/(\d+)\s*\/\s*(\d+)/);
    if (!m) return null;
    const done = Math.max(0, Number(m[1]) || 0);
    const total = Math.max(0, Number(m[2]) || 0);
    if (total <= 0) return null;
    return { done, total };
  }

  function formatDurationCompact(sec: number): string {
    const s = Math.max(0, Math.round(sec));
    if (s < 60) return `${s}秒`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}分${s % 60}秒`;
    const h = Math.floor(m / 60);
    return `${h}小时${m % 60}分`;
  }

  function refreshEmbedTelemetry(jobItems: JobItem[]): void {
    const now = Date.now();
    const next: Record<string, { samples: Array<{ ts: number; done: number; total: number }> }> = {};
    for (const job of jobItems) {
      const st = String(job?.status || "").trim().toLowerCase();
      if (st !== "running" && st !== "queued") continue;
      const p = parseEmbedDoneTotal(job);
      if (!p) continue;
      const key = String(job.job_id || "").trim();
      if (!key) continue;
      const prev = embedTelemetryRef.current[key]?.samples || [];
      let samples = prev
        .filter((x) => now - x.ts <= 15 * 60 * 1000)
        .sort((a, b) => a.ts - b.ts);
      const last = samples[samples.length - 1];
      if (!last || p.done !== last.done || p.total !== last.total || now - last.ts >= 45000) {
        samples = [...samples, { ts: now, done: p.done, total: p.total }];
      }
      next[key] = { samples };
    }
    embedTelemetryRef.current = next;
  }

  function getEmbedTelemetryText(job: JobItem): string {
    const p = parseEmbedDoneTotal(job);
    if (!p) return "";
    const key = String(job.job_id || "").trim();
    const samples = (embedTelemetryRef.current[key]?.samples || []).slice().sort((a, b) => a.ts - b.ts);
    if (p.done >= p.total) return "向量化速度：已完成";
    if (samples.length < 2) return "向量化速度：计算中...";
    const first = samples[0];
    const last = samples[samples.length - 1];
    const deltaDone = last.done - first.done;
    const deltaSec = Math.max(1, (last.ts - first.ts) / 1000);
    if (deltaDone <= 0) return "向量化速度：等待更多进度样本...";
    const rate = deltaDone / deltaSec;
    if (!Number.isFinite(rate) || rate <= 0) return "向量化速度：计算中...";
    const remain = Math.max(0, p.total - p.done);
    const etaSec = remain / rate;
    return `向量化速度：${rate.toFixed(2)} 块/秒 · 预计剩余：${formatDurationCompact(etaSec)}`;
  }

  function getJobRefreshIndicatorState(): { text: string; color: string; bg: string } {
    if (!jobAutoRefreshEnabled) {
      return { text: "刷新关闭（手动）", color: "#9ca3af", bg: "#111827" };
    }
    if (jobAutoPauseOnInspect && jobInspectingDetail) {
      return { text: "已暂停（查看详情）", color: "#f59e0b", bg: "#2b1b05" };
    }
    return { text: "自动刷新中", color: "#22c55e", bg: "#052e16" };
  }

  function translateErrorCodeZh(code: string): string {
    const key = String(code || "").trim().toUpperCase();
    const map: Record<string, string> = {
      JOB_NOT_FOUND: "任务不存在",
      JOB_TIMEOUT: "任务执行超时",
      JOB_FAILED: "任务执行失败",
      JOB_STATUS_FAILED: "任务状态读取失败",
      JOB_LIST_FAILED: "任务列表读取失败",
      JOB_DELETE_RUNNING_FORBIDDEN: "运行中任务不允许删除，请先中止任务",
      JOB_RESUME_FORBIDDEN_DONE: "已完成任务不能继续",
      JOB_RESUME_FORBIDDEN_CANCELED: "已中止任务不能继续",
      JOB_RESUME_RUNNING_ACTIVE: "任务仍在活跃运行，请稍后再试或使用强制继续",
      SPLITBOOK_JOB_RUNNING: "当前拆书已有任务在运行",
      SPLITBOOK_NOT_FOUND: "拆书不存在",
      SPLITBOOK_EMBED_ALREADY_DONE: "向量化已存在，无需重复执行",
      SPLITBOOK_EMBED_REPORT_FAILED: "拆书向量化报告写入失败",
      TEMPLATE_ASSET_NOT_FOUND: "模板资产不存在",
      TEMPLATE_NOT_FOUND: "模板不存在",
      FILE_NOT_FOUND: "文件不存在",
      BOOK_NOT_FOUND: "书籍不存在",
      CHAPTER_NOT_FOUND: "章节不存在",
      PROFILE_NOT_FOUND: "画像不存在",
      SETTINGS_LOAD_FAILED: "设置加载失败",
      SETTINGS_SAVE_FAILED: "设置保存失败",
      API_REQUEST_FAILED: "接口请求失败",
      API_TIMEOUT: "接口请求超时",
      CONNECTION_REFUSED: "服务连接被拒绝",
      INVALID_SETTINGS_JSON: "设置 JSON 格式错误",
      BOOK_ID_REQUIRED: "缺少书籍 ID",
      CHAPTER_ID_REQUIRED: "缺少章节 ID",
      PRESET_NAME_REQUIRED: "缺少预设名称",
      REPORT_HTML_EMPTY: "报告内容为空",
      EVAL_RESULT_NOT_FOUND: "评估结果不存在",
      CONTROL_PLAN_NOT_FOUND: "控制计划不存在",
      MASTER_OUTLINE_AI_UNAVAILABLE: "总纲生成失败：AI 服务不可用",
      VOLUME_PLAN_AI_REQUIRED: "卷纲生成失败：必须启用 AI 生成",
      VOLUME_PLAN_AI_UNAVAILABLE: "卷纲生成失败：AI 服务不可用",
      EVAL_AI_REQUIRED: "张力评估失败：AI 服务不可用",
      CONTROL_PLAN_AI_REQUIRED: "控制计划失败：AI 服务不可用",
      DRAFT_DETAIL_LOAD_FAILED: "正文详情加载失败",
      LATEST_TEXT_PREVIEW_FAILED: "最新正文预览加载失败",
      TEXT_PREVIEW_EMPTY: "正文预览为空",
      TEXT_VERSION_NOT_FOUND: "未找到正文版本",
      TEXT_VERSION_CONTENT_EMPTY: "正文版本内容为空",
      BATCH_CREATE_CHAPTER_FAILED: "批量补齐章节失败",
      STRUCTURE_STEP_1_3_1_FAILED: "结构流程失败：1.3.1 生成卷纲草案失败",
      STRUCTURE_STEP_1_3_2_FAILED: "结构流程失败：1.3.2 应用卷纲失败",
      STRUCTURE_STEP_1_4_1_FAILED: "结构流程失败：1.4.1 生成章纲草案失败",
      STRUCTURE_STEP_1_4_2_FAILED: "结构流程失败：1.4.2 控制计划细化失败",
      WRITEBACK_TEXT_NOT_FOUND: "回写阶段未找到可用正文，已跳过回写",
      ONECLICK_NO_DRAFT_VERSION: "没有可用草稿版本",
      SMARTRUN_NO_DRAFT_VERSION: "智能运行未找到草稿版本",
      DRAFT_DELETE_LAST_FORBIDDEN: "当前章节仅剩一个版本，不能删除",
      DRAFT_DELETE_NO_REPLACEMENT: "删除失败：没有可切换的替代版本",
      CHAPTER_IMPORT_TEXT_EMPTY: "导入失败：章节正文不能为空",
      VOLUME_PLAN_DELETE_LAST_FORBIDDEN: "当前分卷仅剩一个方案版本，不能删除",
      VOLUME_PLAN_DELETE_NO_REPLACEMENT: "删除失败：没有可切换的替代分卷方案",
    };
    if (map[key]) return map[key];
    if (key.endsWith("_LOAD_FAILED")) return "加载失败";
    if (key.endsWith("_SAVE_FAILED")) return "保存失败";
    if (key.endsWith("_CREATE_FAILED")) return "创建失败";
    if (key.endsWith("_UPDATE_FAILED")) return "更新失败";
    if (key.endsWith("_DELETE_FAILED")) return "删除失败";
    if (key.endsWith("_START_FAILED")) return "启动失败";
    if (key.endsWith("_RUN_FAILED")) return "运行失败";
    if (key.endsWith("_APPLY_FAILED")) return "应用失败";
    if (key.endsWith("_PROMOTE_FAILED")) return "提升失败";
    if (key.endsWith("_RETRY_FAILED")) return "重试失败";
    if (key.endsWith("_EXPORT_FAILED")) return "导出失败";
    if (key.endsWith("_FETCH_FAILED")) return "拉取失败";
    if (key.endsWith("_COMPARE_FAILED")) return "对比失败";
    if (key.endsWith("_DIFF_FAILED")) return "差异计算失败";
    if (key.endsWith("_REQUIRED")) return "缺少必填参数";
    if (key.endsWith("_INVALID")) return "输入无效";
    if (key.endsWith("_EMPTY")) return "结果为空";
    if (key.startsWith("SPLITBOOK_") && key.endsWith("_FAILED")) return "拆书流程执行失败";
    if (key.endsWith("_NOT_FOUND")) return "请求资源不存在";
    if (key.endsWith("_FAILED")) return "操作执行失败";
    if (key.endsWith("_TIMEOUT")) return "操作超时";
    if (key.endsWith("_ERROR")) return "操作异常";
    return "";
  }

  function formatJobBookContext(job: JobItem): string {
    const labeled = String((job as any)?.job_book_label || "").trim();
    if (labeled) return labeled;
    const bookTitle = String((job as any)?.book_title || "").trim();
    const splitbookName = String((job as any)?.splitbook_name || "").trim();
    if (bookTitle && splitbookName) return `${bookTitle} / 拆书：${splitbookName}`;
    if (bookTitle) return bookTitle;
    if (splitbookName) return `拆书：${splitbookName}`;
    const payload = (job.payload || {}) as Record<string, unknown>;
    const payloadBookId = String(payload.book_id || "").trim();
    const payloadSplitbookId = String(payload.splitbook_id || "").trim();
    if (payloadBookId) return `book:${payloadBookId}`;
    if (payloadSplitbookId) return `splitbook:${payloadSplitbookId}`;
    return "未关联书籍";
  }

  function buildTriggerMeta(meta: TriggerMetaInput): { trigger_source: string; trigger_entry: string; trigger_mode: TriggerMode } {
    return {
      trigger_source: String(meta.source || "").trim(),
      trigger_entry: String(meta.entry || "").trim(),
      trigger_mode: meta.mode,
    };
  }

  function getJobTriggerMeta(job: JobItem): { source: string; entry: string; mode: TriggerMode | "" } {
    const payload = (job.payload || {}) as Record<string, unknown>;
    const source = String(payload.trigger_source || "").trim();
    const entry = String(payload.trigger_entry || "").trim();
    const modeRaw = String(payload.trigger_mode || "").trim().toLowerCase();
    const mode: TriggerMode | "" =
      modeRaw === "manual" || modeRaw === "recommended" || modeRaw === "one_click" || modeRaw === "auto"
        ? (modeRaw as TriggerMode)
        : "";
    return { source, entry, mode };
  }

  function formatTriggerModeLabel(mode: TriggerMode | ""): string {
    if (mode === "manual") return "手动执行";
    if (mode === "recommended") return "推荐步骤";
    if (mode === "one_click") return "一键流程";
    if (mode === "auto") return "自动触发";
    return "未标记";
  }

  function getJobSourceInfo(job: JobItem): { origin: string; actionLabel: string } {
    const trigger = getJobTriggerMeta(job);
    if (trigger.source) {
      return { origin: trigger.source, actionLabel: "定位到来源区域" };
    }
    const capability = String(job?.capability_id || "").trim().toLowerCase();
    if (capability === "control_plan.tension.v1") {
      return { origin: "写作工作台 > 1.3/1.4 结构迭代 > 1.4.2 控制计划细化", actionLabel: "定位到结构步骤 1.4.2" };
    }
    if (capability === "eval.conflict_tension.v1") {
      return { origin: "写作工作台 > 章节操作 > 张力评估", actionLabel: "定位到章节操作" };
    }
    if (capability === "apply.measure.v1") {
      return { origin: "写作工作台 > 章节操作 > 应用并评测", actionLabel: "定位到章节操作" };
    }
    if (capability === "draft.commit.v1") {
      return { origin: "写作工作台 > 4) 闭环正文生成", actionLabel: "定位到闭环区域" };
    }
    if (capability === "extract.structure_beats.v1") {
      return { origin: "写作工作台 > 章节操作 > 结构节拍抽取", actionLabel: "定位到章节操作" };
    }
    if (capability === "book.tension.analyze.v1") {
      return { origin: "写作工作台 > 全书张力看板 > 分析全书", actionLabel: "定位到张力看板" };
    }
    if (capability === "template.evolve.v1") {
      return { origin: "写作工作台 > 模板与画像 > 模板进化", actionLabel: "定位到模板区域" };
    }
    if (capability.startsWith("splitbook.")) {
      return { origin: "拆书工作台 > 拆书流程步骤", actionLabel: "打开拆书库" };
    }
    return { origin: "通用任务入口（可能由自动流程触发）", actionLabel: "定位到写作工作台" };
  }

  function navigateToJobSource(job: JobItem) {
    const capability = String(job?.capability_id || "").trim().toLowerCase();
    if (capability.startsWith("splitbook.")) {
      setShowJobs(false);
      openOptionalPanel("splitbooks");
      return;
    }
    setShowJobs(false);
    setWorkspaceMode("writing");
    window.setTimeout(() => {
      if (capability === "control_plan.tension.v1" || capability === "draft.commit.v1") {
        scrollToSection("section-writing-studio");
      } else if (
        capability === "eval.conflict_tension.v1" ||
        capability === "apply.measure.v1" ||
        capability === "extract.structure_beats.v1"
      ) {
        scrollToSection("section-outline-tools");
      } else if (capability === "book.tension.analyze.v1") {
        scrollToSection("section-capability-clarity");
      } else {
        scrollToSection("section-writing-studio");
      }
    }, 80);
  }

  function normalizeErrorCode(raw: string): string {
    const msg = String(raw || "").trim().replace(/^Error:\s*/i, "");
    if (!msg) return "";
    const token = String(msg.split(":")[0] || "").trim();
    if (!token) return "";
    const upper = token.toUpperCase();
    if (!/^[A-Z0-9_.-]+$/.test(upper)) return "";
    if (!upper.includes("_") && !upper.includes(".") && upper.length < 4) return "";
    return upper;
  }

  function formatAnyError(err: unknown): string {
    const rawMessage =
      typeof err === "string"
        ? err
        : err && typeof err === "object" && "message" in err
          ? String((err as any).message || "")
          : String(err || "");
    const message = String(rawMessage || "").trim();
    if (!message) return "操作失败";

    if (/failed to fetch/i.test(message) || /err_connection_refused/i.test(message) || /connection refused/i.test(message)) {
      return "网络请求失败：无法连接到本地引擎，请确认 Sidecar 已启动。";
    }

    const code = normalizeErrorCode(message);
    const zh = translateErrorCodeZh(code);
    if (zh && code) {
      const cleaned = message.replace(/^Error:\s*/i, "").trim();
      let detail = "";
      if (cleaned.toUpperCase().startsWith(`${code}:`)) detail = cleaned.slice(code.length + 1).trim();
      if (detail) {
        const detailText = /^\d+$/.test(detail) ? `HTTP ${detail}` : detail;
        return `${zh}（${code}）：${detailText}`;
      }
      return `${zh}（${code}）`;
    }

    if (/[\u4e00-\u9fff]/.test(message)) return message;
    if (/^typeerror:/i.test(message)) return `错误：${message.replace(/^typeerror:\s*/i, "")}`;
    if (/^error:/i.test(message)) return `错误：${message.replace(/^error:\s*/i, "")}`;
    return `错误：${message}`;
  }

  function toCleanSingleLine(value: unknown, maxLen = 120): string {
    const raw = String(value ?? "").replace(/\s+/g, " ").trim();
    if (!raw) return "";
    if (raw.length <= maxLen) return raw;
    return `${raw.slice(0, Math.max(1, maxLen - 1))}...`;
  }

  function extractOutlineNodeKeywords(node: unknown): string[] {
    if (!node || typeof node !== "object") return [];
    const row = node as Record<string, unknown>;
    const out: string[] = [];
    const pushUnique = (raw: unknown, maxLen = 72) => {
      const text = String(raw ?? "").replace(/\s+/g, " ").trim();
      if (!text || text.length < 2) return;
      const value = text.length > maxLen ? text.slice(0, maxLen) : text;
      if (!out.includes(value)) out.push(value);
    };
    const collect = (raw: unknown) => {
      const text = String(raw ?? "").replace(/\s+/g, " ").trim();
      if (!text) return;
      if (text.length <= 72) pushUnique(text, 72);
      const parts = text
        .split(/[，。；、：！？,.!?;:\n\r]+/)
        .map((part) => part.replace(/\s+/g, " ").trim())
        .filter((part) => part.length >= 2 && part.length <= 40)
        .sort((a, b) => b.length - a.length);
      for (const part of parts) pushUnique(part, 40);
    };
    collect(row.summary);
    collect(row.goal);
    collect(row.note);
    collect(row.title);
    collect(row.conflict);
    collect(row.event);
    return out.slice(0, 24);
  }

  function foldTextWithoutWhitespace(text: string): { folded: string; indexMap: number[] } {
    const source = String(text || "");
    const indexMap: number[] = [];
    let folded = "";
    for (let idx = 0; idx < source.length; idx += 1) {
      const ch = source[idx];
      if (/\s/.test(ch)) continue;
      indexMap.push(idx);
      folded += ch;
    }
    return { folded, indexMap };
  }

  function findTextRangeByKeywords(text: string, keywords: string[]): { keyword: string; start: number; end: number } | null {
    const source = String(text || "");
    const uniq = Array.from(new Set((keywords || []).map((k) => String(k || "").trim()).filter((k) => k.length >= 2)));
    if (!source || uniq.length <= 0) return null;
    const sorted = [...uniq].sort((a, b) => b.length - a.length);
    const foldedSource = foldTextWithoutWhitespace(source);
    for (const keyword of sorted) {
      const directIdx = source.indexOf(keyword);
      if (directIdx >= 0) {
        return { keyword, start: directIdx, end: directIdx + keyword.length };
      }
      const foldedKeyword = keyword.replace(/\s+/g, "");
      if (!foldedKeyword || foldedKeyword.length < 2 || !foldedSource.folded) continue;
      const foldedIdx = foldedSource.folded.indexOf(foldedKeyword);
      if (foldedIdx < 0) continue;
      const start = foldedSource.indexMap[foldedIdx];
      const last = foldedSource.indexMap[foldedIdx + foldedKeyword.length - 1];
      if (typeof start !== "number" || typeof last !== "number") continue;
      return { keyword, start, end: last + 1 };
    }
    return null;
  }

  function focusTextareaRange(targetRef: { current: HTMLTextAreaElement | null }, start: number, end: number): boolean {
    const el = targetRef.current;
    if (!el) return false;
    const length = el.value.length;
    const safeStart = Math.max(0, Math.min(length, Number.isFinite(start) ? Math.floor(start) : 0));
    const safeEnd = Math.max(safeStart, Math.min(length, Number.isFinite(end) ? Math.floor(end) : safeStart));
    el.focus();
    try {
      el.setSelectionRange(safeStart, safeEnd);
    } catch {
      return false;
    }
    const lineCount = el.value.slice(0, safeStart).split(/\r?\n/).length;
    const lineHeightRaw = window.getComputedStyle(el).lineHeight;
    const lineHeight = Number.parseFloat(lineHeightRaw || "20");
    if (Number.isFinite(lineHeight) && lineHeight > 0) {
      el.scrollTop = Math.max(0, (lineCount - 3) * lineHeight);
    } else if (length > 0) {
      const ratio = safeStart / length;
      el.scrollTop = ratio * Math.max(0, el.scrollHeight - el.clientHeight);
    }
    return true;
  }

  function pickTextFromUnknown(item: unknown): string {
    if (typeof item === "string") return toCleanSingleLine(item);
    if (typeof item === "number" || typeof item === "boolean") return toCleanSingleLine(item);
    if (!item || typeof item !== "object") return "";
    const row = item as Record<string, unknown>;
    const keys = [
      "summary",
      "detail",
      "text",
      "description",
      "title",
      "conflict",
      "event",
      "fact",
      "point",
      "name",
      "note",
      "value",
      "content",
      "hint",
    ];
    for (const key of keys) {
      const v = row[key];
      if (typeof v === "string" && v.trim()) return toCleanSingleLine(v);
    }
    if (typeof row.chapter_no === "number" && typeof row.chapter_title === "string") {
      return toCleanSingleLine(`第${row.chapter_no}章 ${row.chapter_title}`);
    }
    return "";
  }

  function extractTextLines(items: unknown, maxItems = 6): string[] {
    if (!Array.isArray(items)) return [];
    const out: string[] = [];
    for (const item of items) {
      const text = pickTextFromUnknown(item);
      if (!text) continue;
      if (out.includes(text)) continue;
      out.push(text);
      if (out.length >= maxItems) break;
    }
    return out;
  }

  function escapeRegex(input: string): string {
    return String(input || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function extractRefSectionLines(block: string, heading: string, maxItems = 6): string[] {
    const text = String(block || "");
    if (!text || !heading) return [];
    const re = new RegExp(`${escapeRegex(heading)}\\s*([\\s\\S]*?)(?:\\n【|$)`, "m");
    const match = text.match(re);
    if (!match) return [];
    return String(match[1] || "")
      .split(/\r?\n/)
      .map((line) => line.replace(/^[-*•]\s*/, "").trim())
      .filter((line) => line && !/^（待补充/.test(line))
      .slice(0, maxItems);
  }

  function buildStructureHintsFromMaterialRefs(refs: string[]) {
    const sourceSet = new Set<string>();
    const pushUnique = (arr: string[], next: string) => {
      if (!next || arr.includes(next)) return;
      arr.push(next);
    };
    const conflicts: string[] = [];
    const foreshadows: string[] = [];
    const payoffs: string[] = [];
    const growths: string[] = [];
    const strategies: string[] = [];
    for (const blockRaw of refs) {
      const block = String(blockRaw || "");
      if (!block.includes("[拆书结构引用]")) continue;
      const source = toCleanSingleLine((block.match(/source_splitbook_name=([^\n\r]+)/i) || [])[1] || "", 40);
      if (source) sourceSet.add(source);
      for (const line of extractRefSectionLines(block, "【冲突驱动（可复用结构）】", 8)) pushUnique(conflicts, line);
      for (const line of extractRefSectionLines(block, "【伏笔铺设（仅结构，不取原句）】", 8)) pushUnique(foreshadows, line);
      for (const line of extractRefSectionLines(block, "【回收节点（仅策略，不取原句）】", 8)) pushUnique(payoffs, line);
      for (const line of extractRefSectionLines(block, "【角色成长维度（成长/代价/压力/收获）】", 8)) pushUnique(growths, line);
      for (const line of extractRefSectionLines(block, "【节奏与调参建议】", 8)) pushUnique(strategies, line);
    }
    const totalLines = conflicts.length + foreshadows.length + payoffs.length + growths.length + strategies.length;
    if (totalLines <= 0) return null;
    return {
      sources: Array.from(sourceSet).slice(0, 8),
      conflicts: conflicts.slice(0, 8),
      foreshadows: foreshadows.slice(0, 8),
      payoffs: payoffs.slice(0, 8),
      growths: growths.slice(0, 8),
      strategies: strategies.slice(0, 8),
      total_lines: totalLines,
    };
  }

  function normalizeIssueTypeKey(raw: unknown): string {
    return String(raw || "")
      .trim()
      .toLowerCase()
      .replace(/[\s.-]+/g, "_");
  }

  function translateEvalIssueTypeZh(rawType: unknown): string {
    const key = normalizeIssueTypeKey(rawType);
    const map: Record<string, string> = {
      weak_conflict: "冲突强度不足",
      low_stakes: "利害关系不足",
      pace_flat: "节奏平缓",
      pacing_flat: "节奏平缓",
      hook_weak: "章节钩子偏弱",
      reversal_missing: "反转不足",
      payoff_missing: "回收不足",
      payoff_weak: "回收力度偏弱",
      character_inconsistent: "人物一致性风险",
      character_ooc: "角色行为偏离设定",
      world_rule_conflict: "设定规则冲突",
      timeline_conflict: "时间线冲突",
      continuity_break: "剧情连贯性断裂",
      clarity_low: "信息清晰度不足",
      cost_low: "代价感不足",
      pressure_low: "压力不足",
      growth_weak: "成长推进不足",
      foreshadow_missing: "伏笔铺设不足",
      foreshadow_unresolved: "伏笔未回收",
      saturation_risk: "爽点密度失衡",
      tension_low: "张力偏低",
      tension_overload: "张力过载",
    };
    return map[key] || toCleanSingleLine(rawType) || "未命名问题";
  }

  function translateEvalIssueSeverityZh(rawSeverity: unknown): string {
    const key = String(rawSeverity || "").trim().toLowerCase();
    if (key === "high" || key === "critical" || key === "fatal") return "高";
    if (key === "medium" || key === "warn" || key === "warning") return "中";
    if (key === "low" || key === "info") return "低";
    return "未标记";
  }

  function formatEvalIssueView(issue: any): {
    typeZh: string;
    typeRaw: string;
    where: string;
    severityZh: string;
    detailZh: string;
  } {
    const typeRaw = toCleanSingleLine(issue?.type || issue?.code || "unknown");
    const key = normalizeIssueTypeKey(typeRaw);
    const typeZh = translateEvalIssueTypeZh(typeRaw);
    const severityZh = translateEvalIssueSeverityZh(issue?.severity || issue?.level || issue?.priority);
    const whereNode = toCleanSingleLine(issue?.where?.node_id || issue?.node_id || "");
    const where = whereNode ? `节点 ${whereNode}` : "全局";
    const detailRaw = toCleanSingleLine(issue?.detail || issue?.message || issue?.hint || "", 180);
    const detailMap: Record<string, string> = {
      weak_conflict: "建议补强阻力与对抗，确保主角目标有明确阻挡。",
      low_stakes: "建议明确失败代价与损失，提升读者在意程度。",
      pace_flat: "建议增加节奏波动，安排推进点与爆点交替。",
      pacing_flat: "建议增加节奏波动，安排推进点与爆点交替。",
      hook_weak: "建议强化章节结尾钩子，形成继续阅读驱动力。",
      payoff_missing: "建议增加伏笔回收或阶段兑现，避免长期欠账。",
      reversal_missing: "建议增加信息反转或立场变化，提升戏剧张力。",
      continuity_break: "建议补充因果衔接，避免剧情跳跃。",
      timeline_conflict: "建议核对时间锚点，修正事件先后顺序。",
      character_inconsistent: "建议核对人物动机/底线与既有设定是否一致。",
      character_ooc: "建议核对人物动机/底线与既有设定是否一致。",
      world_rule_conflict: "建议对照世界规则卡，修正违背设定的内容。",
      growth_weak: "建议补充角色成长触发点与代价证据链。",
      tension_low: "建议提升冲突强度或增加倒计时/风险约束。",
      tension_overload: "建议补充释放点与信息澄清，防止疲劳堆压。",
    };
    const fallbackDetail = detailMap[key] || "建议结合控制计划补丁进行定向修订。";
    const detailZh = detailRaw && /[\u4e00-\u9fff]/.test(detailRaw)
      ? detailRaw
      : detailRaw
        ? `${fallbackDetail}（原文：${detailRaw}）`
        : fallbackDetail;
    return { typeZh, typeRaw, where, severityZh, detailZh };
  }

  async function getApiErrorDetail(res: Response): Promise<string> {
    try {
      const out = await res.json();
      return String(out?.detail_zh || out?.detail || out?.message || "").trim();
    } catch {
      return "";
    }
  }

  function formatJobErrorMessage(error?: { code?: string; message?: string } | null): string {
    if (!error) return "无";
    const rawCode = String(error.code || "").trim();
    const rawMessage = String(error.message || "").trim();
    const extractedCode = String((rawCode || rawMessage.split(":")[0] || "").trim());
    const codeUpper = extractedCode.toUpperCase();
    const zh = translateErrorCodeZh(codeUpper);

    let detail = "";
    if (rawMessage) {
      if (codeUpper && rawMessage.toUpperCase().startsWith(`${codeUpper}:`)) {
        detail = rawMessage.slice(codeUpper.length + 1).trim();
      } else if (rawMessage !== rawCode) {
        detail = rawMessage;
      }
    }

    if (zh && codeUpper) {
      if (!detail) return `${zh}（${codeUpper}）`;
      const detailText = /^\d+$/.test(detail) ? `HTTP ${detail}` : detail;
      return `${zh}（${codeUpper}）：${detailText}`;
    }
    if (rawMessage) return `错误信息：${rawMessage}`;
    if (rawCode) return `错误代码：${rawCode}`;
    return "未知错误";
  }

  async function loadOutline(version = selectedVersion) {
    if (!chapterId.trim()) return;
    setBusy(true);
    setStatus("大纲加载中...");
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
      await refreshOutlineInjectionStatus(chapterId);
      setStatus("大纲已加载");
    } catch (err) {
      setStatus(formatAnyError(err));
    } finally {
      setBusy(false);
    }
  }

  async function refreshOutlineInjectionStatus(currentChapterId = chapterId) {
    if (!currentChapterId) {
      setOutlineInjectStatus({
        ready: false,
        version: 0,
        nodeCount: 0,
        updatedAt: "",
        message: "未选择章节",
      });
      return;
    }
    try {
      const res = await fetch(`${baseUrl}/v1/chapters/${currentChapterId}/outline_detail?version=latest`);
      if (!res.ok) {
        setOutlineInjectStatus({
          ready: false,
          version: 0,
          nodeCount: 0,
          updatedAt: "",
          message: "章纲未就绪",
        });
        return;
      }
      const out = await res.json();
      const version = Number(out?.version || 0);
      const nodeCount = Array.isArray(out?.content?.nodes) ? out.content.nodes.length : 0;
      const ready = version > 0 && nodeCount > 0;
      setOutlineInjectStatus({
        ready,
        version,
        nodeCount,
        updatedAt: new Date().toISOString(),
        message: ready ? "已注入写作引擎（自动生效）" : "章纲未就绪（请先执行 1.4.1）",
      });
    } catch {
      setOutlineInjectStatus({
        ready: false,
        version: 0,
        nodeCount: 0,
        updatedAt: "",
        message: "状态检测失败",
      });
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
    setStatus(`画像已切换当前版本：v${version}`);
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
    const fallbackName = `画像分支-${new Date().toISOString().slice(11, 19).replace(/:/g, "")}`;
    const newName = (profileCloneName || "").trim() || fallbackName;
    const res = await fetch(`${baseUrl}/v1/profiles/${selectedBookProfileId}/clone`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_name: newName, note: `克隆自 ${selectedBookProfileId}` }),
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
    setStatus(`画像已复制：${newName}`);
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
    setStatus(`已添加实验画像：${profileId}`);
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
      setStatus(`A/B 批次已启动：${out.batch_id}`);
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
      setStatus(`重试批次已创建：${nextId}`);
    } else {
      setStatus(`无失败项可重试：${batchId}`);
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
        preset_name: `自动：批次-${String(batchId).slice(0, 8)} 胜出`,
        preset_description: `由 A/B 批次 ${batchId} 自动生成`,
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
    setStatus(`优胜者已提升（${abPromoteStrategy}）：${promotedTo || "-"}（分数=${winner.score ?? "-"}）`);
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
    setStatus(`素材追踪已加载：${String(out.trace_id || "").slice(0, 8)}`);
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
    setStatus(profileId ? `书籍画像已绑定：${profileId}` : "书籍画像已清除");
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
      setStatus(`画像学习完成：v${out.new_version || "?"} · 差异=${JSON.stringify(out.diff || {})}`);
      await loadProfilesList();
      await loadProfileVersions(selectedBookProfileId);
    } finally {
      setProfileLearning(false);
    }
  }

  async function loadSplitbooks(opts?: { sync?: boolean }) {
    const sync = opts?.sync ?? true;
    const res = await fetch(`${baseUrl}/v1/splitbooks?limit=100&sync=${sync ? "true" : "false"}`);
    if (!res.ok) throw new Error(`SPLITBOOKS_LOAD_FAILED:${res.status}`);
    const data = await res.json();
    const items = (data.items || []) as SplitbookItem[];
    setSplitbooks(items);
    if (items.length && !selectedSplitbookId) setSelectedSplitbookId(items[0].splitbook_id);
    return items;
  }

  function inferSplitbookNameByPath(sourcePath: string) {
    const fileName = sourcePath.split(/[\\/]/).pop() || "";
    return fileName.replace(/\.[^.]+$/, "").trim();
  }

  function normalizeSplitbookPath(sourcePath: string) {
    return sourcePath.trim().replace(/\\/g, "/").replace(/\/+/g, "/").toLowerCase();
  }

  function inferDirectoryFromFilePath(sourcePath: string) {
    const p = String(sourcePath || "").trim();
    if (!p) return "";
    const normalized = p.replace(/\\/g, "/");
    const idx = normalized.lastIndexOf("/");
    if (idx <= 0) return "";
    return p.slice(0, idx);
  }

  function validateSplitbookSourcePath(sourcePath: string) {
    const trimmed = sourcePath.trim();
    if (!trimmed) return "请先选择本地文件路径";
    const lower = trimmed.toLowerCase();
    if (!lower.endsWith(".txt") && !lower.endsWith(".md") && !lower.endsWith(".jsonl")) {
      return "仅支持 .txt / .md / .jsonl 文件导入";
    }
    return "";
  }

  function validateSplitbookOutputDir(pathRaw: string) {
    const trimmed = String(pathRaw || "").trim();
    if (!trimmed) return "请先设置拆书产物存储目录";
    if (/[<>|?*"]/g.test(trimmed)) return "目录包含非法字符";
    return "";
  }

  function sanitizeExportStem(input: string) {
    return String(input || "")
      .replace(/[\\/:*?"<>|]/g, "_")
      .replace(/\s+/g, "_")
      .replace(/_+/g, "_")
      .replace(/^_+|_+$/g, "")
      .slice(0, 90)
      .trim();
  }

  function parseSplitbookIdsInput(raw: string) {
    return Array.from(
      new Set(
        String(raw || "")
          .split(/[\s,，;；]+/)
          .map((x) => x.trim())
          .filter(Boolean)
      )
    );
  }

  function parseSplitbookChapterFilterInput(raw: string) {
    const out = new Set<number>();
    const tokens = String(raw || "")
      .split(/[\s,，;；]+/)
      .map((x) => x.trim())
      .filter(Boolean);
    for (const token of tokens) {
      if (token.includes("-")) {
        const [leftRaw, rightRaw] = token.split("-", 2);
        const left = Number(leftRaw);
        const right = Number(rightRaw);
        if (!Number.isFinite(left) || !Number.isFinite(right)) continue;
        const start = Math.max(1, Math.min(Math.trunc(left), Math.trunc(right)));
        const end = Math.max(Math.trunc(left), Math.trunc(right));
        const span = Math.min(end - start + 1, 2000);
        for (let n = 0; n < span; n += 1) {
          out.add(start + n);
        }
        if (out.size >= 5000) break;
        continue;
      }
      const value = Number(token);
      if (!Number.isFinite(value)) continue;
      const chapterNo = Math.trunc(value);
      if (chapterNo >= 1) out.add(chapterNo);
      if (out.size >= 5000) break;
    }
    return Array.from(out).sort((a, b) => a - b);
  }

  async function pickProjectWorkspaceDir() {
    try {
      const picker = window.desktopApi?.pickSplitbookOutputDir;
      if (!picker) {
        setStatus("当前运行环境不支持目录选择");
        return;
      }
      const out = await picker();
      const nextPath = String(out?.path || "").trim();
      if (out?.canceled || !nextPath) return;
      setNewBookWorkspacePath(nextPath);
    } catch (err) {
      setStatus(`选择书籍存储目录失败：${formatAnyError(err)}`);
    }
  }

  async function verifySplitbookPath(pathRaw: string, opts?: { silent?: boolean }) {
    const trimmed = String(pathRaw || "").trim();
    const formatError = validateSplitbookSourcePath(trimmed);
    if (formatError) {
      setSplitbookPathCheck({ ok: false, message: formatError });
      if (!opts?.silent) setStatus(`路径校验失败：${formatError}`);
      return false;
    }
    const checker = window.desktopApi?.pathExists;
    if (!checker) {
      setSplitbookPathCheck({ ok: true, message: "路径格式通过（当前环境无法验证本地文件存在）" });
      return true;
    }
    try {
      const out = await checker(trimmed);
      if (out?.exists) {
        setSplitbookPathCheck({ ok: true, message: "文件存在，可开始拆书导入" });
        return true;
      }
      const msg = "文件不存在，请重新选择本地文件";
      setSplitbookPathCheck({ ok: false, message: msg });
      if (!opts?.silent) setStatus(msg);
      return false;
    } catch {
      const msg = "文件校验失败，请检查本地路径";
      setSplitbookPathCheck({ ok: false, message: msg });
      if (!opts?.silent) setStatus(msg);
      return false;
    }
  }

  async function verifySplitbookOutputDir(pathRaw: string, opts?: { silent?: boolean }) {
    const trimmed = String(pathRaw || "").trim();
    const formatError = validateSplitbookOutputDir(trimmed);
    if (formatError) {
      setSplitbookOutputDirCheck({ ok: false, message: formatError });
      if (!opts?.silent) setStatus(`输出目录校验失败：${formatError}`);
      return false;
    }
    const checker = window.desktopApi?.pathExists;
    if (!checker) {
      setSplitbookOutputDirCheck({ ok: true, message: "目录格式通过（当前环境无法验证路径存在）" });
      return true;
    }
    try {
      const out = await checker(trimmed);
      const exists = !!out?.exists;
      if (!exists) {
        setSplitbookOutputDirCheck({ ok: false, message: "目录不存在，请先创建或重新选择" });
        if (!opts?.silent) setStatus("输出目录不存在");
        return false;
      }
      setSplitbookOutputDirCheck({ ok: true, message: "目录可用" });
      return true;
    } catch {
      setSplitbookOutputDirCheck({ ok: false, message: "目录检查失败，请稍后重试" });
      if (!opts?.silent) setStatus("输出目录检查失败");
      return false;
    }
  }

  async function pickSplitbookOutputDir() {
    try {
      const picker = window.desktopApi?.pickSplitbookOutputDir;
      if (!picker) {
        setStatus("当前运行环境不支持目录选择");
        return;
      }
      const out = await picker();
      const nextPath = String(out?.path || "").trim();
      if (out?.canceled || !nextPath) {
        setStatus("已取消目录选择");
        return;
      }
      setSplitbookOutputDir(nextPath);
      try {
        window.localStorage.setItem("splitbook.outputDir", nextPath);
      } catch {}
      await verifySplitbookOutputDir(nextPath);
      setStatus(`拆书产物目录已设置：${nextPath}`);
    } catch (err) {
      setStatus(`选择输出目录失败：${formatAnyError(err)}`);
    }
  }

  function markSplitbookIngestMismatch() {
    const expected = String(splitbookIngestDialog?.expectedText || "导入").trim();
    setSplitbookIngestConfirmError(`输入不匹配，请输入“${expected}”`);
    setSplitbookIngestInputShake(true);
    if (splitbookIngestShakeTimerRef.current) {
      window.clearTimeout(splitbookIngestShakeTimerRef.current);
    }
    splitbookIngestShakeTimerRef.current = window.setTimeout(() => {
      setSplitbookIngestInputShake(false);
      splitbookIngestShakeTimerRef.current = null;
    }, 320);
    const el = splitbookIngestInputRef.current;
    if (el) {
      el.focus();
      el.select();
    }
  }

  function resolveSplitbookIngestConfirm(ok: boolean) {
    const resolver = splitbookIngestConfirmResolverRef.current;
    splitbookIngestConfirmResolverRef.current = null;
    if (resolver) resolver(ok);
  }

  function closeSplitbookIngestDialog(ok: boolean) {
    resolveSplitbookIngestConfirm(ok);
    setSplitbookIngestDialog(null);
    setSplitbookIngestConfirmError("");
    setSplitbookIngestInputShake(false);
  }

  async function confirmSplitbookIngestDialog() {
    if (!splitbookIngestDialog) return;
    const expected = String(splitbookIngestDialog.expectedText || "").trim();
    const typed = String(splitbookIngestDialog.typedText || "").trim();
    if (!expected || typed !== expected) {
      markSplitbookIngestMismatch();
      return;
    }
    closeSplitbookIngestDialog(true);
  }

  async function confirmSplitbookIngestAction(params: {
    action: "reuse" | "create" | "manual";
    splitbookName: string;
    sourcePath: string;
  }): Promise<boolean> {
    const actionText =
      params.action === "reuse"
        ? "将复用已有拆书并开始导入"
        : params.action === "create"
          ? "将新建拆书并开始导入"
          : "将对当前拆书执行导入";
    resolveSplitbookIngestConfirm(false);
    setSplitbookIngestDialog({
      actionText,
      splitbookName: String(params.splitbookName || "").trim(),
      sourcePath: String(params.sourcePath || "").trim(),
      expectedText: splitbookIngestConfirmKeyword,
      typedText: "",
    });
    setSplitbookIngestConfirmError("");
    setSplitbookIngestInputShake(false);
    return new Promise<boolean>((resolve) => {
      splitbookIngestConfirmResolverRef.current = resolve;
    });
  }

  function findSplitbookBySourcePath(sourcePathRaw: string, list: SplitbookItem[]) {
    const normalized = normalizeSplitbookPath(sourcePathRaw);
    if (!normalized) return null;
    return list.find((sb) => normalizeSplitbookPath(String(sb.source_path || "")) === normalized) || null;
  }

  async function createSplitbook(
    nameRaw: string,
    authorRaw: string,
    sourcePathRaw: string,
    options?: { reuseIfExists?: boolean }
  ) {
    const name = nameRaw.trim();
    if (!name) throw new Error("SPLITBOOK_NAME_REQUIRED");
    const sourcePath = sourcePathRaw.trim();
    if (sourcePath && options?.reuseIfExists) {
      const items = await loadSplitbooks();
      const existing = findSplitbookBySourcePath(sourcePath, items);
      if (existing) {
        setSelectedSplitbookId(existing.splitbook_id);
        return { row: existing, reused: true };
      }
    }
    const res = await fetch(`${baseUrl}/v1/splitbooks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, author: authorRaw.trim() || null, source_path: sourcePath || null }),
    });
    if (!res.ok) throw new Error(`SPLITBOOK_CREATE_FAILED:${res.status}`);
    const row = await res.json();
    setSelectedSplitbookId(row.splitbook_id);
    await loadSplitbooks();
    return { row, reused: false };
  }

  async function createSplitbookFromUi(): Promise<boolean> {
    if (!splitbookName.trim()) return false;
    const pathTrimmed = splitbookPath.trim();
    if (pathTrimmed) {
      const valid = await verifySplitbookPath(pathTrimmed, { silent: true });
      if (!valid) {
        setStatus("创建失败：本地路径校验未通过");
        return false;
      }
    }
    const result = await createSplitbook(splitbookName, splitbookAuthor, splitbookPath, { reuseIfExists: true });
    if (result.reused) {
      setStatus(`检测到同路径拆书，已复用：${result.row.name}`);
      return true;
    }
    setSplitbookName("");
    setSplitbookAuthor("");
    setStatus(`拆书已创建：${result.row.name}`);
    return true;
  }

  async function pickSplitbookLocalFile(): Promise<boolean> {
    try {
      const picker = window.desktopApi?.pickSplitbookLocalFile;
      if (!picker) {
        setStatus("当前运行环境不支持本地文件选择");
        return false;
      }
      const out = await picker();
      const nextPath = String(out?.path || "").trim();
      if (out?.canceled || !nextPath) {
        setStatus("已取消本地文件选择");
        return false;
      }
      const valid = await verifySplitbookPath(nextPath);
      if (!valid) {
        return false;
      }
      setSplitbookPath(nextPath);
      if (!splitbookOutputDir.trim()) {
        const inferredDir = inferDirectoryFromFilePath(nextPath);
        if (inferredDir) {
          setSplitbookOutputDir(inferredDir);
          try {
            window.localStorage.setItem("splitbook.outputDir", inferredDir);
          } catch {}
          void verifySplitbookOutputDir(inferredDir, { silent: true });
        }
      }
      const inferredName = splitbookName.trim() || inferSplitbookNameByPath(nextPath) || "本地文本拆书";
      setSplitbookName(inferredName);
      const items = await loadSplitbooks();
      const existing = findSplitbookBySourcePath(nextPath, items);
      const confirmOk = await confirmSplitbookIngestAction({
        action: existing ? "reuse" : "create",
        splitbookName: existing?.name || inferredName,
        sourcePath: nextPath,
      });
      if (!confirmOk) {
        setStatus("已取消导入");
        return false;
      }
      setStatus(`已选择本地文件：${nextPath}（编码：UTF-8）`);
      const result = await createSplitbook(inferredName, splitbookAuthor, nextPath, { reuseIfExists: true });
      const ingest = await triggerSplitbookJob("ingest", {
        splitbookId: String(result.row.splitbook_id),
        sourcePath: nextPath,
        confirmIngest: false,
      });
      const actionLabel = result.reused ? "已复用并开始导入" : "已创建并开始导入";
      setStatus(`${actionLabel}：${result.row.name}（任务：${String(ingest?.job_id || "-")}）`);
      return true;
    } catch (err) {
      setStatus(`本地文件选择失败：${formatAnyError(err)}`);
      return false;
    }
  }

  async function triggerSplitbookJob(
    kind: "ingest" | "embed" | "extract_structured" | "build_templates" | "build_profile",
    opts?: { splitbookId?: string; sourcePath?: string; confirmIngest?: boolean }
  ) {
    const splitbookId = String(opts?.splitbookId || selectedSplitbookId || "").trim();
    if (!splitbookId) return;
    const ingestPath = String(opts?.sourcePath ?? splitbookPath).trim();
    if (kind === "ingest") {
      const valid = await verifySplitbookPath(ingestPath, { silent: true });
      if (!valid) {
        setStatus("导入失败：本地路径校验未通过");
        return;
      }
      if (opts?.confirmIngest) {
        const targetSplitbook = splitbooks.find((sb) => sb.splitbook_id === splitbookId);
        const splitbookName = targetSplitbook?.name || `拆书 ${splitbookId.slice(0, 8)}`;
        const confirmOk = await confirmSplitbookIngestAction({
          action: "manual",
          splitbookName,
          sourcePath: ingestPath,
        });
        if (!confirmOk) {
          setStatus("已取消导入");
          return;
        }
      }
    }
    if (kind === "embed") {
      const latestSplitbooks = await loadSplitbooks().catch(() => splitbooks);
      const target = latestSplitbooks.find((sb) => sb.splitbook_id === splitbookId);
      if (String(target?.embed_status || "").toLowerCase() === "done") {
        setStatus("向量化已存在，已跳过。");
        return { skipped: true, reason: "already_embedded", splitbook_id: splitbookId };
      }
      const activeByStats = String((target?.stats as any)?.active_embed_job_status || "").trim().toLowerCase();
      const activeByJobs = splitbookRecentJobs.some((j) => {
        const cap = String(j.capability_id || "").trim().toLowerCase();
        const sid = String((j.payload as any)?.splitbook_id || "").trim();
        return cap === "splitbook.embed.v1" && sid === splitbookId && isActiveJobStatus(String(j.status || ""));
      });
      if (activeByStats === "queued" || activeByStats === "running" || activeByJobs) {
        setStatus("该拆书已有向量化任务在执行，请勿重复触发。");
        return { skipped: true, reason: "embed_active", splitbook_id: splitbookId };
      }
      const outputDir = String(splitbookOutputDir || "").trim();
      if (outputDir) {
        const outOk = await verifySplitbookOutputDir(outputDir, { silent: true });
        if (!outOk) {
          setStatus("向量化失败：拆书产物目录不可用，请先修正目录");
          return;
        }
      }
    }
    const body =
      kind === "ingest"
        ? {
            path: ingestPath,
            encoding: "utf-8",
            auto_optimize: true,
            chunk_size: splitbookChunkSize,
            overlap: splitbookOverlap,
          }
        : kind === "embed"
          ? {
              model: activeProviderConfig.embedding_model || "bge-m3:latest",
              batch: 64,
              auto_optimize: true,
              output_dir: String(splitbookOutputDir || "").trim() || undefined,
            }
          : kind === "extract_structured"
            ? { mode: "full" }
          : kind === "build_templates"
            ? { mode: "merge" }
            : { mode: "create", name: `参考风格-${selectedSplitbook?.name || "拆书(Splitbook)"}` };
    const res = await fetch(`${baseUrl}/v1/splitbooks/${splitbookId}/${kind}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const out = await res.json().catch(() => ({} as Record<string, any>));
      const detail = String(out?.detail_zh || out?.detail || out?.message || "").trim();
      const detailCode = String(out?.detail_code || out?.code || out?.detail || "").trim().toUpperCase();
      if (kind === "embed" && detailCode === "SPLITBOOK_EMBED_ALREADY_DONE") {
        setStatus("向量化已存在，已跳过。");
        return { skipped: true, reason: "already_embedded", splitbook_id: splitbookId };
      }
      throw new Error(detail || `SPLITBOOK_${kind.toUpperCase()}_FAILED:${res.status}`);
    }
    const out = await res.json();
    setStatus(`任务已入队：${kind} · ${out.job_id}`);
    if (showJobs) await pollJobs();
    return out;
  }

  async function waitJobTerminal(
    jobId: string,
    maxMs = 3 * 60 * 60 * 1000,
    opts?: {
      splitbookId?: string;
      kind?:
        | "ingest"
        | "embed"
        | "extract_structured"
        | "build_templates"
        | "build_profile"
        | "writeback_preview_batch"
        | "writeback_confirm_batch";
    }
  ) {
    const started = Date.now();
    const splitbookId = String(opts?.splitbookId || "").trim();
    const kind = opts?.kind || undefined;
    const tryRecoverBySplitbookStatus = async (): Promise<any | null> => {
      if (!splitbookId || !kind) return null;
      const latestSplitbooks = await loadSplitbooks().catch(() => splitbooks);
      const target = latestSplitbooks.find((sb) => String(sb.splitbook_id || "") === splitbookId);
      if (!target) return null;
      const ingestDone = String(target.ingest_status || "").toLowerCase() === "done";
      const embedDone = String(target.embed_status || "").toLowerCase() === "done";
      if (kind === "ingest" && ingestDone) {
        setStatus("导入任务超时，但拆书状态显示“导入已完成”，已自动继续。");
        return { job_id: jobId, status: "succeeded", recovered_by: "splitbook_ingest_status" };
      }
      if (kind === "embed" && embedDone) {
        setStatus("向量化任务超时，但拆书状态显示“向量化已完成”，已自动继续。");
        return { job_id: jobId, status: "succeeded", recovered_by: "splitbook_embed_status" };
      }
      return null;
    };
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
    const afterTimeoutRes = await fetch(`${baseUrl}/v1/jobs/${encodeURIComponent(jobId)}`).catch(() => null);
    if (afterTimeoutRes?.ok) {
      const finalOut = await afterTimeoutRes.json().catch(() => ({}));
      const finalStatus = String(finalOut?.status || "").toLowerCase();
      if (finalStatus === "succeeded" || finalStatus === "done") return finalOut;
    }
    const recovered = await tryRecoverBySplitbookStatus();
    if (recovered) return recovered;
    throw new Error(`JOB_TIMEOUT:${jobId}`);
  }

  async function runSplitbookPipeline() {
    if (!selectedSplitbookId) {
      setStatus("已跳过拆书流程：未选择拆书");
      return;
    }
    const ingest = await triggerSplitbookJob("ingest");
    if (ingest?.job_id) await waitJobTerminal(String(ingest.job_id), undefined, { splitbookId: selectedSplitbookId, kind: "ingest" });
    const embed = await triggerSplitbookJob("embed");
    if (embed?.job_id) await waitJobTerminal(String(embed.job_id), undefined, { splitbookId: selectedSplitbookId, kind: "embed" });
    const extract = await triggerSplitbookJob("extract_structured");
    if (extract?.job_id) await waitJobTerminal(String(extract.job_id), undefined, { splitbookId: selectedSplitbookId, kind: "extract_structured" });
    const tpl = await triggerSplitbookJob("build_templates");
    if (tpl?.job_id) await waitJobTerminal(String(tpl.job_id), undefined, { splitbookId: selectedSplitbookId, kind: "build_templates" });
    const profile = await triggerSplitbookJob("build_profile");
    if (profile?.job_id) await waitJobTerminal(String(profile.job_id), undefined, { splitbookId: selectedSplitbookId, kind: "build_profile" });
  }

  function formatSplitbookStepLabel(step: string) {
    const map: Record<string, string> = {
      idle: "待执行",
      ingest: "导入文本",
      embed: "向量化",
      extract_structured: "结构抽取",
      build_templates: "生成模板",
      build_profile: "生成画像",
      writeback_batch: "批量回写",
      done: "已完成",
      failed: "失败",
    };
    return map[step] || step;
  }

  function formatSplitbookManualStepState(state: "done" | "running" | "ready" | "blocked") {
    const map: Record<string, string> = {
      done: "已完成",
      running: "进行中",
      ready: "可执行",
      blocked: "未满足前置条件",
    };
    return map[state] || "待执行";
  }

  function formatDateTimeShort(raw: string) {
    const ts = Date.parse(String(raw || ""));
    if (!Number.isFinite(ts)) return "-";
    try {
      return new Date(ts).toLocaleString();
    } catch {
      return "-";
    }
  }

  function summarizeSplitbookStepLatestJob(job: JobItem | null) {
    if (!job) return "暂无执行记录";
    const status = formatJobStatusLabel(String(job.status || ""));
    const when = formatDateTimeShort(String(job.updated_at || job.created_at || ""));
    const errMsg = String((job.error as any)?.message || "").trim();
    const progressMsg = String((job.progress as any)?.message || "").trim();
    const resultMsg = String((job.result as any)?.message || (job.result as any)?.detail || "").trim();
    const detail = errMsg || progressMsg || resultMsg;
    const detailShort = detail ? ` · ${detail.slice(0, 42)}` : "";
    return `${status} · ${when}${detailShort}`;
  }

  async function runSplitbookQuickPipeline(): Promise<boolean> {
    if (!selectedSplitbookId) {
      setStatus("请先在左侧选择一个拆书条目");
      return false;
    }
    if (selectedSplitbookRunningCount > 0 || selectedSplitbookEmbedActiveByStats) {
      setStatus("当前拆书已有排队/运行中的任务，请等待完成或先中止后再执行。");
      return false;
    }
    const ingestPath = String(splitbookPath || selectedSplitbook?.source_path || "").trim();
    const valid = await verifySplitbookPath(ingestPath);
    if (!valid) {
      setStatus("拆书流程无法启动：本地路径校验未通过");
      return false;
    }
    setSplitbookPipelineBusy(true);
    setSplitbookPipelineStep("ingest");
    setSplitbookPipelineError("");
    try {
      const ingest = await triggerSplitbookJob("ingest", {
        splitbookId: selectedSplitbookId,
        sourcePath: ingestPath,
        confirmIngest: false,
      });
      if (ingest?.job_id) {
        await waitJobTerminal(String(ingest.job_id), undefined, { splitbookId: selectedSplitbookId, kind: "ingest" });
      }

      setSplitbookPipelineStep("embed");
      const embed = await triggerSplitbookJob("embed", { splitbookId: selectedSplitbookId });
      if (embed?.job_id) {
        await waitJobTerminal(String(embed.job_id), undefined, { splitbookId: selectedSplitbookId, kind: "embed" });
      }

      setSplitbookPipelineStep("extract_structured");
      const extract = await triggerSplitbookJob("extract_structured", { splitbookId: selectedSplitbookId });
      if (extract?.job_id) {
        await waitJobTerminal(String(extract.job_id), undefined, { splitbookId: selectedSplitbookId, kind: "extract_structured" });
      }

      setSplitbookPipelineStep("build_templates");
      const tpl = await triggerSplitbookJob("build_templates", { splitbookId: selectedSplitbookId });
      if (tpl?.job_id) {
        await waitJobTerminal(String(tpl.job_id), undefined, { splitbookId: selectedSplitbookId, kind: "build_templates" });
      }

      setSplitbookPipelineStep("build_profile");
      const profile = await triggerSplitbookJob("build_profile", { splitbookId: selectedSplitbookId });
      if (profile?.job_id) {
        await waitJobTerminal(String(profile.job_id), undefined, { splitbookId: selectedSplitbookId, kind: "build_profile" });
      }

      setSplitbookPipelineStep("done");
      setStatus("拆书全流程完成：导入 + 向量化 + 结构抽取 + 模板 + 画像");
      return true;
    } catch (e: any) {
      setSplitbookPipelineStep("failed");
      const msg = String(e?.message || e);
      setSplitbookPipelineError(msg);
      setStatus(`拆书流程失败：${msg}`);
      return false;
    } finally {
      await refreshSplitbookWorkspace({ silent: true }).catch(() => {});
      setSplitbookPipelineBusy(false);
    }
  }

  async function runSplitbookStep4ExtractAndRefresh(): Promise<boolean> {
    const targetSplitbookId = String(selectedSplitbookId || "").trim();
    if (!targetSplitbookId) {
      setStatus("请先选择拆书，再执行步骤 4。");
      return false;
    }
    if (splitbookStep4Busy || splitbookPipelineBusy) return false;
    if (selectedSplitbookRunningCount > 0 || selectedSplitbookEmbedActiveByStats) {
      setStatus("当前拆书仍有运行中的任务，请稍后再执行步骤 4。");
      return false;
    }
    if (selectedSplitbookEmbedStatus !== "done") {
      setStatus("步骤 4 需要先完成向量化（步骤 3.2）。");
      return false;
    }
    setSplitbookStep4Busy(true);
    try {
      const extract = await triggerSplitbookJob("extract_structured", { splitbookId: targetSplitbookId });
      let extractResult: Record<string, any> = {};
      if (extract?.job_id) {
        setStatus("步骤 4.1 已启动，正在等待结构抽取完成...");
        const done = await waitJobTerminal(String(extract.job_id), undefined, { splitbookId: targetSplitbookId, kind: "extract_structured" });
        extractResult = done?.result && typeof done.result === "object" ? (done.result as Record<string, any>) : {};
      }
      const ledgerOk = await loadSplitbookLedger(splitbookLedgerView, { splitbookId: targetSplitbookId, silent: true });
      const outlineOk = await loadSplitbookOutlinePreview({ splitbookId: targetSplitbookId, silent: true });
      const chapterPackOk = await loadSplitbookChapterPack(splitbookChapterNo, { splitbookId: targetSplitbookId, silent: true });
      const refreshFailures: string[] = [];
      if (!ledgerOk) refreshFailures.push("账本");
      if (!outlineOk) refreshFailures.push("大纲");
      if (!chapterPackOk) refreshFailures.push("章节包");
      if (refreshFailures.length) {
        throw new Error(`步骤 4 刷新失败：${refreshFailures.join(" / ")}（请重试 4.2~4.4 或检查任务日志）`);
      }
      const factTotal = Number(extractResult?.fact_total || 0);
      const growthRows = Number(extractResult?.growth_rows || 0);
      const sceneTotal = Number(extractResult?.scene_total || 0);
      if (factTotal <= 0 && growthRows <= 0 && sceneTotal <= 0) {
        setStatus("步骤 4 已完成，但抽取结果为空（facts/scenes/growth=0）。请检查源文本切分结果与任务日志。");
      } else {
        setStatus(`步骤 4 执行完成：账本 / 大纲 / 章节包已刷新（facts=${factTotal}，scenes=${sceneTotal}，growth=${growthRows}）。`);
      }
      return true;
    } catch (err) {
      setStatus(`步骤 4 执行失败：${formatAnyError(err)}`);
      return false;
    } finally {
      setSplitbookStep4Busy(false);
      await refreshSplitbookWorkspace({ silent: true }).catch(() => {});
    }
  }

  async function runSplitbookResegmentIngest(): Promise<boolean> {
    const splitbookId = String(selectedSplitbookId || "").trim();
    if (!splitbookId) {
      setStatus("请先选择拆书，再执行章节重切分。");
      return false;
    }
    if (splitbookResegmentBusy || splitbookPipelineBusy || splitbookStep4Busy) return false;
    if (selectedSplitbookRunningCount > 0 || selectedSplitbookEmbedActiveByStats) {
      setStatus("当前拆书仍有运行中的任务，请稍后再执行章节重切分。");
      return false;
    }
    const sourcePath = String(selectedSplitbook?.source_path || splitbookPath || "").trim();
    if (!sourcePath) {
      setStatus("未找到拆书源文件路径，无法重切分。");
      return false;
    }
    const validPath = await verifySplitbookPath(sourcePath, { silent: true });
    if (!validPath) {
      setStatus("章节重切分失败：源文件路径校验未通过。");
      return false;
    }
    setSplitbookResegmentBusy(true);
    try {
      setStatus("章节重切分已启动：正在重跑 3.1 导入切分...");
      const ingest = await triggerSplitbookJob("ingest", {
        splitbookId,
        sourcePath,
        confirmIngest: false,
      });
      if (!ingest?.job_id) {
        throw new Error("SPLITBOOK_RESEGMENT_JOB_NOT_CREATED");
      }
      await waitJobTerminal(String(ingest.job_id), undefined, { splitbookId, kind: "ingest" });
      const items = await loadSplitbooks({ sync: true });
      const current = items.find((x) => String(x.splitbook_id || "") === splitbookId) || null;
      const chapterTotal = Number(current?.stats?.chapter_total || 0);
      const chunkTotal = Number(current?.stats?.chunks_total || 0);
      setStatus(`章节重切分完成：检测章节 ${chapterTotal}，分块 ${chunkTotal}。请继续执行 3.2 向量化与步骤 4。`);
      return true;
    } catch (err) {
      setStatus(`章节重切分失败：${formatAnyError(err)}`);
      return false;
    } finally {
      setSplitbookResegmentBusy(false);
      await refreshSplitbookWorkspace({ silent: true }).catch(() => {});
    }
  }

  async function runUnifiedDesktopFlow() {
    if (flowBusy) return;
    if (!bookId || !chapterId || !quickVolumeId.trim()) {
      setStatus("统一流程需要 book_id + chapter_id + volume_id");
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
      setStatus(`统一流程完成（预检=${String(pf?.report?.summary?.overall || "未知")}）`);
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

  async function ensureChapterOutlineForGeneration(targetChapterId: string): Promise<boolean> {
    const chapterIdText = String(targetChapterId || "").trim();
    if (!chapterIdText) return false;
    try {
      const splitbookId = String(writingSplitbookRefId || selectedSplitbookId || "").trim();
      const structureHints = buildStructureHintsFromMaterialRefs(materialRefs);
      const res = await fetch(`${baseUrl}/v1/chapters/${chapterIdText}/outline_detail/auto_generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          force: false,
          splitbook_id: splitbookId || undefined,
          material_refs: materialRefs.slice(0, 30),
          structure_hints: structureHints || undefined,
        }),
      });
      if (!res.ok) throw new Error(`AUTO_OUTLINE_BEFORE_GENERATE_FAILED:${res.status}`);
      return true;
    } catch (err) {
      setStatus(`预生成章纲失败：${formatAnyError(err)}`);
      return false;
    }
  }

  async function runClosedLoopFlow(opts?: {
    chapterId?: string;
    intent?: string;
    evolveStyleOverride?: boolean;
    mode?: "single" | "batch";
    batchIndex?: number;
    batchTotal?: number;
    targetChapterNos?: number[];
  }): Promise<boolean> {
    if (closedLoopBusy) return false;
    let targetChapterId = String(opts?.chapterId || chapterId || "").trim();
    if (!targetChapterId) {
      const ready = await ensureStructureTargetsReady({ silent: true });
      targetChapterId = String(ready?.chapterId || "").trim();
      if (targetChapterId) setChapterId(targetChapterId);
    }
    if (!bookId || !targetChapterId) {
      setStatus("闭环执行需要 book_id + chapter_id");
      return false;
    }
    const mode = opts?.mode === "batch" ? "batch" : "single";
    const chapterNo = chapterNoById(targetChapterId);
    const targetNos = Array.isArray(opts?.targetChapterNos) ? opts?.targetChapterNos.filter((x) => Number(x) > 0) : [];
    const chapterLabel =
      mode === "batch"
        ? (targetNos.length ? `第${targetNos.join(" / 第")}章` : `第${chapterNo || 0}章`)
        : `第${chapterNo || 0}章`;
    const runDetail =
      mode === "batch" && Number(opts?.batchTotal || 0) > 0
        ? `批量进度 ${Number(opts?.batchIndex || 1)}/${Number(opts?.batchTotal || 1)}`
        : "单章生成";
    const outlineReady = await ensureChapterOutlineForGeneration(targetChapterId);
    if (!outlineReady) return false;
    updateChapterGenerationTrace({
      status: "running",
      mode,
      basis: buildChapterGenerationBasisText(),
      chapters: chapterLabel,
      chapterIds: [targetChapterId],
      detail: `执行中：${runDetail}`,
    });
    setClosedLoopBusy(true);
    setClosedLoopOutput(null);
    setClosedLoopSteps({
      draft: "running",
      writeback: "idle",
      preflight: "idle",
      rewrite: "idle",
      style_evolution: "idle",
    });
    try {
      const payload: any = {
        book_id: bookId,
        chapter_id: targetChapterId,
        intent_confirmed: String(opts?.intent || `闭环运行(${quickRunMode})`),
        dry_run: false,
        reuse_if_exists: false,
        force_stub_llm: false,
        do_writeback: closedLoopDoWriteback,
        run_preflight: closedLoopRunPreflight,
        fail_on_preflight_fail: closedLoopFailOnPreflightFail,
        evolve_style: typeof opts?.evolveStyleOverride === "boolean" ? opts.evolveStyleOverride : closedLoopEvolveStyle,
        style_evolution: {
          sample_limit: 24,
          min_sample_count: 6,
          alpha: 0.58,
          sync_book_settings: true,
        },
        rewrite: {
          enabled: closedLoopRewriteEnabled,
          level: "L1",
          auto_accept: closedLoopRewriteEnabled ? closedLoopRewriteAutoAccept : false,
        },
        min_chars: 3000,
      };
      if (quickVolumeId.trim()) payload.volume_id = quickVolumeId.trim();
      const res = await fetch(`${baseUrl}/v1/engine/closed_loop/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`CLOSED_LOOP_FAILED:${res.status}`);
      const out = await res.json();
      setClosedLoopOutput(out || {});

      const stageStatus = (stage: any, opts?: { required?: boolean }) => {
        if (!stage) return opts?.required ? "failed" : "idle";
        if (stage.skipped === true) return "idle";
        if (stage.ok === false) return "failed";
        return "ok";
      };
      setClosedLoopSteps({
        draft: stageStatus(out?.stages?.draft, { required: true }),
        writeback: stageStatus(out?.stages?.writeback),
        preflight: stageStatus(out?.stages?.preflight),
        rewrite: stageStatus(out?.stages?.rewrite),
        style_evolution: stageStatus(out?.stages?.style_evolution),
      });
      if (out?.stages?.style_evolution) {
        setStyleEvolutionOutput(out.stages.style_evolution);
      }
      if (bookId) void loadLatestStyleEvolution(bookId);
      if (out?.stages?.draft) setQuickDraftRunOut(out.stages.draft);
      const preflightOverall = String(out?.summary?.preflight_overall || "UNKNOWN");
      const textVerId = String(out?.stages?.draft?.output?.commit_result?.text_ver_id || "").trim();
      const chapterChars = Number(out?.summary?.chapter_chars || 0) || 0;
      updateChapterGenerationTrace({
        status: out?.ok ? "success" : "error",
        mode,
        basis: buildChapterGenerationBasisText(),
        chapters: chapterLabel,
        chapterIds: [targetChapterId],
        detail:
          `预检=${preflightOverall}` +
          (chapterChars > 0 ? `；正文长度≈${chapterChars} 字符` : "") +
          (textVerId ? `；版本=${textVerId.slice(0, 8)}...` : "") +
          (mode === "batch" && Number(opts?.batchTotal || 0) > 0
            ? `；批量 ${Number(opts?.batchIndex || 1)}/${Number(opts?.batchTotal || 1)}`
            : ""),
      });
      setStatus(`章节生成${out?.ok ? "完成" : "结束"}（预检=${preflightOverall}${chapterChars > 0 ? `；正文≈${chapterChars} 字符` : ""}）`);
      if (out?.ok) {
        const versionsOut = await quickLoadVersions({ silent: true });
        const preferDraftId =
          String(out?.stages?.draft?.output?.commit_result?.selected_draft_id || "").trim() ||
          String(out?.stages?.draft?.output?.commit_result?.active_draft_id || "").trim() ||
          String(out?.stages?.draft?.output?.commit_result?.draft_id || "").trim();
        await loadDraftPreviewById(preferDraftId, { silent: true, versionItems: versionsOut?.items });
      }
      void loadAiDebugInfo({ silent: true });
      return !!out?.ok;
    } catch (e: any) {
      const msg = String(e?.message || e);
      updateChapterGenerationTrace({
        status: "error",
        mode,
        basis: buildChapterGenerationBasisText(),
        chapters: chapterLabel,
        chapterIds: [targetChapterId],
        detail: toCleanSingleLine(msg, 120),
      });
      setClosedLoopSteps((m) => {
        const next = { ...m };
        for (const k of Object.keys(next)) {
          if (next[k] === "running") next[k] = "failed";
        }
        if (next.draft === "idle") next.draft = "failed";
        return next;
      });
      setStatus(`闭环执行失败：${msg}`);
      return false;
    } finally {
      setClosedLoopBusy(false);
    }
  }

  async function loadDraftPreviewById(
    draftIdInput?: string,
    opts?: { silent?: boolean; chapterId?: string; versionItems?: any[] }
  ) {
    const silent = !!opts?.silent;
    const chapterIdForPreview = String(opts?.chapterId || chapterId || "").trim();
    const loadLatestTextPreview = async (): Promise<boolean> => {
      if (!chapterIdForPreview) return false;
      const latestRes = await fetch(`${baseUrl}/v1/chapters/${encodeURIComponent(chapterIdForPreview)}/latest_text_preview`);
      if (!latestRes.ok) throw new Error(`LATEST_TEXT_PREVIEW_FAILED:${latestRes.status}`);
      const latest = await latestRes.json();
      const textValue = String(latest?.text || "").trim();
      if (!textValue) throw new Error("TEXT_PREVIEW_EMPTY");
      setChapterDraftPreviewText(textValue);
      setChapterDraftPreviewDraftId(String(latest?.draft_id || latest?.text_ver_id || ""));
      setChapterDraftPreviewSource(
        String(latest?.source || "").trim().toLowerCase() === "text_version" ? "text_version" : "draft"
      );
      const updatedAt = String(latest?.created_at || "").trim();
      setChapterDraftPreviewUpdatedAt(updatedAt);
      setChapterDraftPreviewDirty(false);
      if (!silent) setStatus(`章节正文已加载：${latest?.source === "text_version" ? "来自正文版本" : "来自草稿版本"}`);
      return true;
    };
    let draftId = String(draftIdInput || "").trim();
    if (!draftId) {
      const overrideItems = Array.isArray(opts?.versionItems) ? opts?.versionItems : [];
      const sourceItems = overrideItems.length
        ? overrideItems
        : Array.isArray(quickVersionsOut?.items)
          ? quickVersionsOut.items
          : [];
      const selectedFromList =
        sourceItems.find((it: any) => Boolean(it?.is_selected || it?.is_active)) ||
        sourceItems[0] ||
        null;
      draftId = String(selectedFromList?.draft_id || "").trim();
    }
    if (!draftId) {
      try {
        return await loadLatestTextPreview();
      } catch (err) {
        if (!silent) setStatus("未找到可预览的正文版本，请先执行 1.5 或加载草稿版本。");
        return false;
      }
    }
    setChapterDraftPreviewLoading(true);
    try {
      const res = await fetch(`${baseUrl}/v1/drafts/${encodeURIComponent(draftId)}`);
      if (res.ok) {
        const data = await res.json();
        const item = data?.item || {};
        const textValue = String(item?.text || "").trim();
        if (textValue) {
          setChapterDraftPreviewText(textValue);
          setChapterDraftPreviewDraftId(String(item?.draft_id || draftId));
          setChapterDraftPreviewSource("draft");
          const updatedAt = String(item?.created_at || "").trim();
          setChapterDraftPreviewUpdatedAt(updatedAt);
          setChapterDraftPreviewDirty(false);
          if (!silent) setStatus(`章节正文已加载：${String(item?.draft_id || draftId).slice(0, 8)}...`);
          return true;
        }
      }
      return await loadLatestTextPreview();
    } catch (err) {
      if (!silent) setStatus(`加载章节正文失败：${formatAnyError(err)}`);
      return false;
    } finally {
      setChapterDraftPreviewLoading(false);
    }
  }

  async function importManualChapterText() {
    const chapterIdText = String(chapterId || "").trim();
    const content = String(manualChapterImportText || "").trim();
    if (!chapterIdText) {
      setStatus("请先选择章节，再导入自写正文。");
      return;
    }
    if (!content) {
      setStatus("请先粘贴自写正文内容。");
      return;
    }
    setManualChapterImportBusy(true);
    try {
      const res = await fetch(`${baseUrl}/v1/chapters/${encodeURIComponent(chapterIdText)}/manual_import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content,
          note: String(manualChapterImportNote || "").trim() || "手动导入自写章节",
          selected_by: "user",
          source: "manual_import",
        }),
      });
      const out = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(String((out as any)?.detail || `HTTP_${res.status}`));
      setStatus(`已导入并激活：第${Number((out as any)?.chapter_no || 0)}章 · 草稿 ${(out as any)?.draft?.draft_id?.slice?.(0, 8) || ""}...`);
      setChapterDraftPreviewText(content);
      setChapterDraftPreviewDraftId(String((out as any)?.draft?.draft_id || (out as any)?.text_version?.text_ver_id || ""));
      setChapterDraftPreviewSource("draft");
      setChapterDraftPreviewUpdatedAt(String((out as any)?.draft?.created_at || (out as any)?.text_version?.created_at || ""));
      setChapterDraftPreviewDirty(false);
      void quickLoadVersions({ silent: true });
      void loadDraftConfirmations(bookId, { silent: true });
      void loadAiDebugInfo({ silent: true });
    } catch (err) {
      setStatus(`导入章节失败：${formatAnyError(err)}`);
    } finally {
      setManualChapterImportBusy(false);
    }
  }

  async function saveChapterDraftPreviewText() {
    const chapterIdText = String(chapterId || "").trim();
    const content = String(chapterDraftPreviewText || "").trim();
    if (!chapterIdText) {
      setStatus("请先选择章节，再保存正文。");
      return;
    }
    if (!content) {
      setStatus("正文为空，无法保存。");
      return;
    }
    setChapterDraftPreviewLoading(true);
    try {
      const res = await fetch(`${baseUrl}/v1/chapters/${encodeURIComponent(chapterIdText)}/manual_import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content,
          note: "章节正文预览窗口编辑保存",
          selected_by: "user",
          source: "manual_import_preview",
        }),
      });
      const out = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(String((out as any)?.detail || `HTTP_${res.status}`));
      const nextDraftId = String((out as any)?.draft?.draft_id || (out as any)?.text_version?.text_ver_id || "");
      const nextUpdatedAt = String((out as any)?.draft?.created_at || (out as any)?.text_version?.created_at || "");
      setChapterDraftPreviewDraftId(nextDraftId);
      setChapterDraftPreviewSource("draft");
      setChapterDraftPreviewUpdatedAt(nextUpdatedAt);
      setChapterDraftPreviewDirty(false);
      setManualChapterImportText(content);
      void quickLoadVersions({ silent: true });
      void loadDraftConfirmations(bookId, { silent: true });
      setStatus(`章节正文已保存并激活：${nextDraftId ? `${nextDraftId.slice(0, 8)}...` : "完成"}`);
    } catch (err) {
      setStatus(`保存章节正文失败：${formatAnyError(err)}`);
    } finally {
      setChapterDraftPreviewLoading(false);
    }
  }

  async function ensureBatchGenerationTargets(count: number, startChapterId: string): Promise<ChapterItem[]> {
    if (!bookId || !startChapterId) return [];
    let chapters = [...chapterItems];
    if (!chapters.length || !chapters.some((c) => String(c.chapter_id) === String(startChapterId))) {
      chapters = await loadChapters(bookId);
    }
    const sorted = [...chapters].sort((a, b) => Number(a.chapter_no || 0) - Number(b.chapter_no || 0));
    const start = sorted.find((x) => String(x.chapter_id || "") === String(startChapterId)) || null;
    if (!start) return [];
    const startNo = Math.max(1, Number(start.chapter_no || 1) || 1);
    const neededNos = Array.from({ length: count }).map((_, idx) => startNo + idx);
    const existingNoSet = new Set(sorted.map((x) => Number(x.chapter_no || 0)));
    let createdAny = false;
    for (const chNo of neededNos) {
      if (existingNoSet.has(chNo)) continue;
      const createRes = await fetch(`${baseUrl}/v1/books/${bookId}/chapters`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chapter_no: chNo, title: `第${chNo}章` }),
      });
      if (createRes.ok) {
        createdAny = true;
        existingNoSet.add(chNo);
        continue;
      }
      if (createRes.status === 409) {
        existingNoSet.add(chNo);
        continue;
      }
      throw new Error(`BATCH_CREATE_CHAPTER_FAILED:${createRes.status}`);
    }
    const latest = createdAny ? await loadChapters(bookId) : sorted;
    const latestSorted = [...latest].sort((a, b) => Number(a.chapter_no || 0) - Number(b.chapter_no || 0));
    const byNo = new Map<number, ChapterItem>();
    for (const row of latestSorted) {
      const n = Number(row.chapter_no || 0);
      if (n > 0 && !byNo.has(n)) byNo.set(n, row);
    }
    const targets = neededNos.map((no) => byNo.get(no)).filter(Boolean) as ChapterItem[];
    return targets;
  }

  async function runBatchClosedLoopGeneration() {
    if (batchGenerateBusy) return;
    if (!bookId || !chapterId) {
      setStatus("批量生成需要先选择书籍和起始章节。");
      return;
    }
    const count = Math.max(1, Math.min(5, Number(batchGenerateCount || 1) || 1));
    const targets = await ensureBatchGenerationTargets(count, chapterId);
    if (!targets.length) {
      setStatus("未找到可执行的目标章节。");
      return;
    }
    if (targets.length < count) {
      setStatus(`批量目标不足：请求 ${count} 章，实际可执行 ${targets.length} 章。`);
    }
    const targetChapterNos = targets.map((x) => Number(x.chapter_no || 0)).filter((x) => x > 0);
    updateChapterGenerationTrace({
      status: "running",
      mode: "batch",
      basis: buildChapterGenerationBasisText(),
      chapters: targetChapterNos.length ? `第${targetChapterNos.join(" / 第")}章` : "",
      chapterIds: targets.map((x) => String(x.chapter_id || "")).filter(Boolean),
      detail: `批量准备：共 ${targets.length} 章`,
    });
    setBatchGenerateBusy(true);
    try {
      let success = 0;
      let failed = 0;
      for (let i = 0; i < targets.length; i += 1) {
        const ch = targets[i];
        setChapterId(String(ch.chapter_id));
        const stepText = `[批量 ${i + 1}/${targets.length}] 第${Number(ch.chapter_no || 0)}章`;
        setStatus(`${stepText}：正在生成...`);
        const ok = await runClosedLoopFlow({
          chapterId: String(ch.chapter_id),
          intent: `批量章节生成 ${i + 1}/${targets.length}`,
          evolveStyleOverride: i === targets.length - 1 ? closedLoopEvolveStyle : false,
          mode: "batch",
          batchIndex: i + 1,
          batchTotal: targets.length,
          targetChapterNos,
        });
        if (!ok) {
          failed += 1;
          setStatus(`${stepText}：生成失败，继续处理后续章节。`);
          continue;
        }
        success += 1;
      }
      const requested = targets.length;
      updateChapterGenerationTrace({
        status: failed === 0 && success === requested ? "success" : "error",
        mode: "batch",
        basis: buildChapterGenerationBasisText(),
        chapters: targetChapterNos.length ? `第${targetChapterNos.join(" / 第")}章` : "",
        chapterIds: targets.map((x) => String(x.chapter_id || "")).filter(Boolean),
        detail: `批量完成：成功 ${success}/${requested} 章，失败 ${failed} 章`,
      });
      setStatus(`批量生成完成：成功 ${success}/${requested} 章，失败 ${failed} 章。`);
    } finally {
      setBatchGenerateBusy(false);
    }
  }

  async function loadLatestStyleEvolution(currentBookId = bookId) {
    if (!currentBookId) {
      setStyleEvolutionLatest(null);
      return null;
    }
    try {
      const res = await fetch(`${baseUrl}/v1/books/${currentBookId}/style/evolution/latest`);
      if (!res.ok) return null;
      const data = await res.json();
      setStyleEvolutionLatest(data?.item || null);
      return data?.item || null;
    } catch {
      return null;
    }
  }

  async function runStyleEvolutionNow(force = false): Promise<boolean> {
    if (styleEvolutionBusy) return false;
    if (!bookId) {
      setStatus("请先选择书籍，再执行风格进化");
      return false;
    }
    setStyleEvolutionBusy(true);
    try {
      const res = await fetch(`${baseUrl}/v1/books/${bookId}/style/evolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile_id: selectedBookProfileId || undefined,
          sample_limit: 24,
          min_sample_count: 6,
          alpha: 0.58,
          force,
          sync_book_settings: true,
        }),
      });
      if (!res.ok) throw new Error(`STYLE_EVOLVE_FAILED:${res.status}`);
      const out = await res.json();
      setStyleEvolutionOutput(out || {});
      if (out?.updated) {
        setStatus(`风格进化完成：画像版本 v${String(out.profile_version || "-")}`);
      } else if (out?.skipped) {
        setStatus(`风格进化跳过：${String(out.reason || "无需更新")}`);
      } else {
        setStatus("风格进化已执行");
      }
      await loadLatestStyleEvolution(bookId);
      await loadBooks();
      return true;
    } catch (e: any) {
      setStatus(`风格进化失败：${String(e?.message || e)}`);
      return false;
    } finally {
      setStyleEvolutionBusy(false);
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
    setStatus(`守卫开关(allow_guard)=${allowGuard}`);
  }

  async function deleteSplitbook(targetSplitbookId: string, opts?: { purgeAssets?: boolean }) {
    const sid = String(targetSplitbookId || "").trim();
    if (!sid || splitbookDeletingId) return;
    const row = splitbooks.find((x) => x.splitbook_id === sid);
    const name = row?.name || `拆书 ${sid.slice(0, 8)}`;
    const purgeAssets = !!opts?.purgeAssets;
    setSplitbookDeleteDialog({
      splitbookId: sid,
      name,
      purgeAssets,
      typedName: "",
    });
    setSplitbookDeleteError("");
  }

  function playDeleteMismatchBeep(level: "soft" | "strong") {
    try {
      const Ctx = (window as any).AudioContext || (window as any).webkitAudioContext;
      if (!Ctx) return;
      const ctx = new Ctx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "triangle";
      const isStrong = level === "strong";
      osc.frequency.value = isStrong ? 860 : 720;
      gain.gain.setValueAtTime(0.0001, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(isStrong ? 0.18 : 0.11, ctx.currentTime + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + (isStrong ? 0.24 : 0.16));
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + (isStrong ? 0.25 : 0.17));
      window.setTimeout(() => {
        void ctx.close().catch(() => {});
      }, isStrong ? 340 : 260);
    } catch {}
  }

  function markSplitbookDeleteMismatch() {
    setSplitbookDeleteError("输入名称不匹配，请按提示输入完整拆书名称。");
    setSplitbookDeleteInputShake(true);
    if (splitbookDeleteShakeTimerRef.current) {
      window.clearTimeout(splitbookDeleteShakeTimerRef.current);
    }
    splitbookDeleteShakeTimerRef.current = window.setTimeout(() => {
      setSplitbookDeleteInputShake(false);
      splitbookDeleteShakeTimerRef.current = null;
    }, 320);
    const el = splitbookDeleteInputRef.current;
    if (el) {
      el.focus();
      el.select();
    }
    if (deleteMismatchBeepEnabled) {
      playDeleteMismatchBeep(deleteMismatchBeepLevel);
    }
    setStatus("删除已取消：输入名称不匹配。");
  }

  async function confirmDeleteSplitbookDialog() {
    if (!splitbookDeleteDialog || splitbookDeletingId) return;
    const sid = String(splitbookDeleteDialog.splitbookId || "").trim();
    const name = String(splitbookDeleteDialog.name || "").trim();
    const purgeAssets = !!splitbookDeleteDialog.purgeAssets;
    if (!sid || !name) return;
    setSplitbookDeleteError("");
    setSplitbookDeletingId(sid);
    try {
      const res = await fetch(`${baseUrl}/v1/splitbooks/${sid}?purge_assets=${purgeAssets ? "true" : "false"}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const detail = await getApiErrorDetail(res);
        const detailNorm = String(detail || "").trim().toUpperCase();
        if (res.status === 409 && (detailNorm === "SPLITBOOK_JOB_RUNNING" || detail.includes("运行中的任务"))) {
          const errText = "该拆书仍有运行中的任务，请先等待任务完成。";
          setSplitbookDeleteError(errText);
          setStatus(`删除失败：${errText}`);
          return;
        }
        throw new Error(detail || `SPLITBOOK_DELETE_FAILED:${res.status}`);
      }
      const items = await loadSplitbooks();
      if (selectedSplitbookId === sid) {
        const next = items.find((x) => x.splitbook_id !== sid) || null;
        setSelectedSplitbookId(next?.splitbook_id || "");
      }
      setSplitbookLedgerRows([]);
      setSplitbookLedgerSummary(null);
      setSplitbookOutlinePreview(null);
      setSplitbookChapterPack(null);
      setSplitbookHealthReport(null);
      setSplitbookAntiCopyReport(null);
      setSplitbookDeleteDialog(null);
      setSplitbookDeleteError("");
      setStatus(`拆书已删除：${name}`);
    } catch (err) {
      const errText = formatAnyError(err);
      setSplitbookDeleteError(errText);
      setStatus(`删除拆书失败：${errText}`);
    } finally {
      setSplitbookDeletingId("");
    }
  }

  async function exportSplitbookDiagnose() {
    if (!selectedSplitbookId) return;
    const res = await fetch(`${baseUrl}/v1/splitbooks/${selectedSplitbookId}/diagnose_bundle?limit=50`);
    if (!res.ok) throw new Error(`SPLITBOOK_DIAGNOSE_FAILED:${res.status}`);
    const bundle = await res.json();
    const splitbookNamePrefix = sanitizeExportStem(String(selectedSplitbook?.name || splitbookName || selectedSplitbookId || "拆书"));
    const stem = `${splitbookNamePrefix}_诊断包_${new Date().toISOString().replace(/[:.]/g, "-")}`;
    const saved = await window.desktopApi.saveDiagnoseBundle(stem, bundle);
    const target = saved.zipPath || saved.directoryPath;
    setStatus(`诊断包已保存：${target}`);
    await window.desktopApi.openPath(target, true);
  }

  async function loadSplitbookLedger(
    view?: "chapter" | "character",
    opts?: { splitbookId?: string; silent?: boolean }
  ) {
    const sid = String(opts?.splitbookId || selectedSplitbookId || "").trim();
    if (!sid) return false;
    try {
      const nextView = view || splitbookLedgerView;
      const res = await fetch(`${baseUrl}/v1/splitbooks/${sid}/ledger?view=${nextView}&limit=800`);
      if (!res.ok) {
        const detail = await getApiErrorDetail(res);
        throw new Error(detail || `SPLITBOOK_LEDGER_FAILED:${res.status}`);
      }
      const out = await res.json();
      setSplitbookLedgerView(nextView);
      setSplitbookLedgerRows((out.rows || []) as any[]);
      setSplitbookLedgerSummary(out.summary || null);
      return true;
    } catch (err) {
      if (!opts?.silent) setStatus(`账本加载失败：${formatAnyError(err)}`);
      return false;
    }
  }

  async function loadSplitbookOutlinePreview(opts?: { splitbookId?: string; silent?: boolean }) {
    const sid = String(opts?.splitbookId || selectedSplitbookId || "").trim();
    if (!sid) return false;
    try {
      const res = await fetch(`${baseUrl}/v1/splitbooks/${sid}/outline`);
      if (!res.ok) {
        const detail = await getApiErrorDetail(res);
        throw new Error(detail || `SPLITBOOK_OUTLINE_FAILED:${res.status}`);
      }
      const out = await res.json();
      setSplitbookOutlinePreview(out);
      return true;
    } catch (err) {
      if (!opts?.silent) setStatus(`大纲加载失败：${formatAnyError(err)}`);
      return false;
    }
  }

  async function loadSplitbookChapterPack(
    chapterNo = splitbookChapterNo,
    opts?: { splitbookId?: string; silent?: boolean }
  ) {
    const sid = String(opts?.splitbookId || selectedSplitbookId || "").trim();
    if (!sid) return false;
    try {
      const res = await fetch(`${baseUrl}/v1/splitbooks/${sid}/chapter_pack?chapter_no=${encodeURIComponent(String(chapterNo))}`);
      if (!res.ok) {
        const detail = await getApiErrorDetail(res);
        throw new Error(detail || `SPLITBOOK_CHAPTER_PACK_FAILED:${res.status}`);
      }
      const out = await res.json();
      setSplitbookChapterPack(out);
      return true;
    } catch (err) {
      if (!opts?.silent) setStatus(`章节包生成失败：${formatAnyError(err)}`);
      return false;
    }
  }

  async function injectSplitbookStructureRefToWriting(opts?: {
    splitbookId?: string;
    scope?: "book" | "chapter";
    chapterNo?: number;
  }): Promise<boolean> {
    if (!chapterId) {
      setStatus("请先在写作工作台选择章节，再注入拆书结构。");
      return false;
    }
    const splitbookId = String(opts?.splitbookId || writingSplitbookRefId || selectedSplitbookId || "").trim();
    if (!splitbookId) {
      setStatus("请先选择拆书来源。");
      return false;
    }
    const scope = opts?.scope || writingSplitbookRefScope || "book";
    const chapterNoRaw = Number(opts?.chapterNo ?? writingSplitbookRefChapterNo ?? splitbookChapterNo ?? 1);
    const chapterNo = Number.isFinite(chapterNoRaw) ? Math.max(1, Math.round(chapterNoRaw)) : 1;
    const marker =
      scope === "chapter"
        ? `[拆书结构引用] source_splitbook_id=${splitbookId} scope=chapter chapter_no=${chapterNo}`
        : `[拆书结构引用] source_splitbook_id=${splitbookId} scope=book`;
    if (materialRefs.some((block) => String(block || "").includes(marker))) {
      setStatus(
        scope === "chapter"
          ? `该拆书结构引用已存在：${splitbookId} · 单章第${chapterNo}章`
          : `该拆书结构引用已存在：${splitbookId} · 全书结构`
      );
      return true;
    }
    setWritingSplitbookRefBusy(true);
    setStatus("正在提取拆书结构并注入写作引用...");
    try {
      const reqs: Promise<Response>[] = [
        fetch(`${baseUrl}/v1/splitbooks/${splitbookId}/outline`),
        fetch(`${baseUrl}/v1/splitbooks/${splitbookId}/ledger?view=chapter&limit=400`),
      ];
      if (scope === "chapter") {
        reqs.unshift(fetch(`${baseUrl}/v1/splitbooks/${splitbookId}/chapter_pack?chapter_no=${encodeURIComponent(String(chapterNo))}`));
      }
      const results = await Promise.all(reqs);
      let packOut: any = {};
      let outlineRes: Response;
      let ledgerRes: Response;
      if (scope === "chapter") {
        const packRes = results[0];
        outlineRes = results[1];
        ledgerRes = results[2];
        if (!packRes.ok) throw new Error(`SPLITBOOK_CHAPTER_PACK_FAILED:${packRes.status}`);
        packOut = await packRes.json();
      } else {
        outlineRes = results[0];
        ledgerRes = results[1];
      }
      const outlineOut = outlineRes.ok ? await outlineRes.json() : {};
      const ledgerOut = ledgerRes.ok ? await ledgerRes.json() : {};

      const splitbookRow = splitbooks.find((x) => x.splitbook_id === splitbookId);
      const splitbookName = String(splitbookRow?.name || splitbookId.slice(0, 8));
      const chapterRowsRaw = Array.isArray((ledgerOut as any)?.rows) ? ((ledgerOut as any).rows as unknown[]) : [];
      const chapterRowsAll: Record<string, unknown>[] = chapterRowsRaw.filter(
        (row): row is Record<string, unknown> => !!row && typeof row === "object"
      );
      const chapterRows: Record<string, unknown>[] =
        scope === "chapter"
          ? chapterRowsAll.filter((row) => Number(row.chapter_no || 0) === chapterNo).slice(0, 8)
          : chapterRowsAll.slice(0, 12);
      const chapterOutlines = Array.isArray((outlineOut as any)?.chapters) ? (((outlineOut as any).chapters as unknown[]) as Record<string, unknown>[]) : [];
      const chapterOutline = Array.isArray((outlineOut as any)?.chapters)
        ? (((outlineOut as any).chapters as unknown[])
            .find((row) => Number((row as Record<string, unknown>)?.chapter_no || 0) === chapterNo) as Record<string, unknown> | undefined)
        : undefined;

      const uniqTake = (arr: string[], limit = 8) => {
        const out: string[] = [];
        for (const item of arr) {
          const cleaned = toCleanSingleLine(item);
          if (!cleaned) continue;
          if (out.includes(cleaned)) continue;
          out.push(cleaned);
          if (out.length >= limit) break;
        }
        return out;
      };
      const chapterOutlineConflict = chapterOutlines.map((row) => toCleanSingleLine((row as any)?.summary?.conflict || "")).filter(Boolean);
      const chapterOutlineForeshadow = chapterOutlines.flatMap((row) => extractTextLines((row as any)?.beats?.foreshadow, 2));
      const chapterOutlinePayoff = chapterOutlines.flatMap((row) => extractTextLines((row as any)?.beats?.payoff, 2));
      const conflictLines =
        scope === "chapter"
          ? extractTextLines((packOut as any)?.key_conflicts, 6)
          : uniqTake(chapterOutlineConflict, 8);
      const foreshadowLines =
        scope === "chapter"
          ? extractTextLines((packOut as any)?.foreshadow, 6)
          : uniqTake(chapterOutlineForeshadow, 8);
      const payoffLines =
        scope === "chapter"
          ? extractTextLines((packOut as any)?.payoff, 6)
          : uniqTake(chapterOutlinePayoff, 8);
      const strategyLines =
        scope === "chapter"
          ? extractTextLines((packOut as any)?.strategy || (packOut as any)?.style_hints || (packOut as any)?.constraints, 5)
          : uniqTake(
              [
                `全书结构章节数：${Math.max(0, Number((outlineOut as any)?.chapter_total || 0))}`,
                "优先复用冲突升级顺序，不复述原文叙述。",
                "优先复用伏笔->回收节奏，不复用原句与原桥段。",
                "人物成长采用“压力->代价->收获”闭环推进。",
              ],
              5
            );
      const growthLines = chapterRows
        .map((row) => {
          const chapterPrefix =
            scope === "book" && Number(row.chapter_no || 0) > 0 ? `第${Number(row.chapter_no || 0)}章 · ` : "";
          const who = toCleanSingleLine(row.character_name || row.name || "角色");
          const stage = toCleanSingleLine(row.growth_stage || row.latest_stage || "阶段待补充");
          const pressure = toCleanSingleLine(row.pressure || row.latest_pressure || "压力待补充");
          const cost = toCleanSingleLine(row.cost || row.latest_cost || "代价待补充");
          const gain = toCleanSingleLine(row.gain || row.latest_gain || "收获待补充");
          return `${chapterPrefix}${who}: 阶段=${stage}；压力=${pressure}；代价=${cost}；收获=${gain}`;
        })
        .filter(Boolean)
        .slice(0, 6);

      const conflictText = (conflictLines.length ? conflictLines : ["（待补充冲突）"]).map((x) => `- ${x}`).join("\n");
      const foreshadowText = (foreshadowLines.length ? foreshadowLines : ["（待补充伏笔）"]).map((x) => `- ${x}`).join("\n");
      const payoffText = (payoffLines.length ? payoffLines : ["（待补充回收）"]).map((x) => `- ${x}`).join("\n");
      const growthText = (growthLines.length ? growthLines : ["- （待补充成长账本）"]).join("\n");
      const strategyText = (strategyLines.length ? strategyLines : ["（待补充节奏策略）"]).map((x) => `- ${x}`).join("\n");
      const outlineConflict = toCleanSingleLine((chapterOutline as any)?.summary?.conflict || (chapterOutline as any)?.chapter_title || "");
      const outlinePromise = toCleanSingleLine((chapterOutline as any)?.summary?.promise || (chapterOutline as any)?.summary?.goal || "");
      const block = [
        marker,
        `source_splitbook_name=${splitbookName}`,
        "usage_mode=structure_only",
        "usage_rule=仅允许借鉴结构与冲突机制；禁止复述原文；禁止沿用原叙事顺序；需重建人物动机/场景/因果链。",
        "",
        "【结构化约束输入】",
        scope === "chapter" ? `- 引用范围：单章结构（第${chapterNo}章）` : "- 引用范围：全书结构（跨章节聚合）",
        scope === "book" ? `- 覆盖章节数：${Math.max(0, Number((outlineOut as any)?.chapter_total || 0))}` : "",
        scope === "chapter" && outlineConflict ? `- 拆书章节冲突摘要：${outlineConflict}` : "",
        scope === "chapter" && outlinePromise ? `- 拆书章节承诺摘要：${outlinePromise}` : "",
        "",
        "【冲突驱动（可复用结构）】",
        conflictText,
        "",
        "【伏笔铺设（仅结构，不取原句）】",
        foreshadowText,
        "",
        "【回收节点（仅策略，不取原句）】",
        payoffText,
        "",
        "【角色成长维度（成长/代价/压力/收获）】",
        growthText,
        "",
        "【节奏与调参建议】",
        strategyText,
      ]
        .filter((line) => String(line || "").trim().length > 0)
        .join("\n");

      setMaterialRefs((prev) => [block, ...prev].slice(0, 20));
      setWritingSplitbookRefLast({
        splitbookId,
        splitbookName,
        scope,
        chapterNo: scope === "chapter" ? chapterNo : null,
        conflicts: conflictLines.length,
        foreshadow: foreshadowLines.length,
        payoff: payoffLines.length,
        injectedAt: new Date().toLocaleString(),
      });
      setStatus(
        scope === "chapter"
          ? `拆书结构引用已注入：${splitbookName} 第${chapterNo}章（结构模式，防抄袭）`
          : `拆书结构引用已注入：${splitbookName} 全书结构（结构模式，防抄袭）`
      );
      return true;
    } catch (err) {
      setStatus(`拆书结构注入失败：${formatAnyError(err)}`);
      return false;
    } finally {
      setWritingSplitbookRefBusy(false);
    }
  }

  function addQuickMaterialRefNote() {
    const text = String(writingMaterialQuickNote || "").trim();
    if (!text) {
      setStatus("请先输入素材备注。");
      return;
    }
    const block = `[创作素材备注]\n- 内容：${text}`;
    setMaterialRefs((prev) => [block, ...prev].slice(0, 40));
    setWritingMaterialQuickNote("");
    setStatus("素材备注已加入结构引用池。");
  }

  async function importMaterialsFromCurrentSplitbook() {
    if (writingMaterialImportBusy) return;
    if (!bookId) {
      setStatus("请先选择书籍。");
      return;
    }
    const splitbookId = String(writingSplitbookRefId || selectedSplitbookId || "").trim();
    if (!splitbookId) {
      setStatus("请先选择拆书来源（1.4.3）。");
      return;
    }
    setWritingMaterialImportBusy(true);
    try {
      const res = await fetch(`${baseUrl}/v1/books/${encodeURIComponent(bookId)}/materials/import_from_splitbook/${encodeURIComponent(splitbookId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          limit: 320,
          tag: "splitbook_structure",
          importance: 3,
          auto_embed: true,
        }),
      });
      if (!res.ok) throw new Error(`MATERIAL_IMPORT_FROM_SPLITBOOK_FAILED:${res.status}`);
      const out = await res.json();
      setStatus(
        `拆书素材已导入素材库：新增 ${Number(out?.created || 0)}，向量化 ${Number(out?.embedded || 0)}，失败 ${Number(out?.failed || 0)}`
      );
      openOptionalPanel("ref");
    } catch (err) {
      setStatus(`导入拆书素材失败：${formatAnyError(err)}`);
    } finally {
      setWritingMaterialImportBusy(false);
    }
  }

  function clearSplitbookStructureRefs() {
    setMaterialRefs((prev) => prev.filter((block) => !String(block || "").includes("[拆书结构引用]")));
    setWritingSplitbookRefLast(null);
    setStatus("已清空拆书结构引用。");
  }

  async function refreshSplitbookWorkspace(opts?: { silent?: boolean }) {
    if (splitbookRefreshBusy) return false;
    setSplitbookRefreshBusy(true);
    try {
      const items = await loadSplitbooks({ sync: true });
      await pollJobs();

      let sid = String(selectedSplitbookId || "").trim();
      if (sid && !items.some((x) => x.splitbook_id === sid)) sid = "";
      if (!sid && items.length) sid = String(items[0].splitbook_id || "");
      if (sid && sid !== selectedSplitbookId) {
        setSelectedSplitbookId(sid);
      }

      if (sid) {
        await loadSplitbookLedger(undefined, { splitbookId: sid, silent: true });
        await loadSplitbookOutlinePreview({ splitbookId: sid, silent: true });
        await loadSplitbookChapterPack(splitbookChapterNo, { splitbookId: sid, silent: true });
      } else {
        setSplitbookLedgerRows([]);
        setSplitbookLedgerSummary(null);
        setSplitbookOutlinePreview(null);
        setSplitbookChapterPack(null);
        setSplitbookHealthReport(null);
        setSplitbookAntiCopyReport(null);
      }

      if (!opts?.silent) {
        setStatus("刷新完成：已执行状态对账，拆书列表、任务状态、账本与章节包已同步。");
      }
      return true;
    } catch (err) {
      if (!opts?.silent) {
        setStatus(`刷新拆书状态失败：${formatAnyError(err)}`);
      }
      return false;
    } finally {
      setSplitbookRefreshBusy(false);
    }
  }

  async function runSplitbookWriteback() {
    if (!selectedSplitbookId) return;
    const content = String(splitbookWritebackText || "").trim();
    if (!content) {
      setStatus("请先粘贴要回写的章节正文");
      return;
    }
    try {
      const res = await fetch(`${baseUrl}/v1/splitbooks/${selectedSplitbookId}/writeback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chapter_no: Number(splitbookChapterNo),
          chapter_title: splitbookChapterPack?.chapter_title || `第${splitbookChapterNo}章`,
          content,
        }),
      });
      if (!res.ok) throw new Error(`SPLITBOOK_WRITEBACK_FAILED:${res.status}`);
      const out = await res.json();
      setStatus(`回写完成：facts=${out.facts_written || 0}，growth=${out.growth_written || 0}`);
      await loadSplitbookLedger().catch(() => {});
    } catch (err) {
      setStatus(`回写失败：${formatAnyError(err)}`);
    }
  }

  async function runSplitbookHealthReport() {
    if (!selectedSplitbookId) return;
    try {
      const res = await fetch(`${baseUrl}/v1/splitbooks/${selectedSplitbookId}/chapter_health`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chapter_no: Number(splitbookChapterNo),
          content: String(splitbookWritebackText || "").trim(),
        }),
      });
      if (!res.ok) throw new Error(`SPLITBOOK_HEALTH_FAILED:${res.status}`);
      const out = await res.json();
      setSplitbookHealthReport(out);
    } catch (err) {
      setStatus(`体检报告生成失败：${formatAnyError(err)}`);
    }
  }

  async function runSplitbookAntiCopyCheck() {
    if (!selectedSplitbookId) return;
    const content = String(splitbookWritebackText || "").trim();
    if (!content) {
      setStatus("请先粘贴章节正文，再执行反照抄检查");
      return;
    }
    try {
      const res = await fetch(`${baseUrl}/v1/splitbooks/${selectedSplitbookId}/anti_copy_check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chapter_no: Number(splitbookChapterNo),
          content,
          top_k: 200,
          ngram_size: 5,
        }),
      });
      if (!res.ok) throw new Error(`SPLITBOOK_ANTI_COPY_FAILED:${res.status}`);
      const out = await res.json();
      setSplitbookAntiCopyReport(out);
      setStatus(`反照抄检查完成：风险=${String(out?.risk_level || "-")}，得分=${String(out?.anti_copy_score ?? "-")}`);
    } catch (err) {
      setStatus(`反照抄检查失败：${formatAnyError(err)}`);
    }
  }

  async function runSplitbookBuildLibrary() {
    const inputIds = parseSplitbookIdsInput(splitbookLibraryIds);
    const ids = inputIds.length ? inputIds : splitbooks.map((x) => String(x.splitbook_id || "")).filter(Boolean);
    if (!ids.length) {
      setStatus("当前无可用拆书，无法构建跨书模板库");
      return;
    }
    try {
      const res = await fetch(`${baseUrl}/v1/splitbooks/library/build`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          splitbook_ids: ids,
          mode: "replace",
          max_splitbooks: 12,
        }),
      });
      if (!res.ok) throw new Error(`SPLITBOOK_LIBRARY_BUILD_FAILED:${res.status}`);
      const out = await res.json();
      setSplitbookLibraryResult(out);
      setStatus(`跨书模板库构建完成：新增 ${String(out?.created_count || 0)} 条模板`);
      void searchTemplateAssets().catch(() => {});
    } catch (err) {
      setStatus(`跨书模板库构建失败：${formatAnyError(err)}`);
    }
  }

  async function exportSplitbookArtifactsToPresetDir() {
    if (!selectedSplitbookId) {
      setStatus("请先选择拆书");
      return;
    }
    const outputDir = String(splitbookOutputDir || "").trim();
    const ok = await verifySplitbookOutputDir(outputDir, { silent: true });
    if (!ok) {
      setStatus("请先设置可用的拆书产物目录");
      return;
    }
    const saver = window.desktopApi?.saveTextAt;
    if (!saver) {
      setStatus("当前运行环境不支持定向保存");
      return;
    }
    try {
      const sid = selectedSplitbookId;
      const now = new Date();
      const ts = now.toISOString().replace(/[:.]/g, "-");
      const splitbookNamePrefix = sanitizeExportStem(String(selectedSplitbook?.name || splitbookName || sid || "拆书"));
      const chapterNo = Number(splitbookChapterNo) || 1;
      const ledgerChapterRes = await fetch(`${baseUrl}/v1/splitbooks/${sid}/ledger?view=chapter&limit=1200`);
      const ledgerCharacterRes = await fetch(`${baseUrl}/v1/splitbooks/${sid}/ledger?view=character&limit=1200`);
      const outlineRes = await fetch(`${baseUrl}/v1/splitbooks/${sid}/outline`);
      if (!ledgerChapterRes.ok || !ledgerCharacterRes.ok || !outlineRes.ok) {
        throw new Error("EXPORT_FETCH_FAILED");
      }
      const ledgerChapter = await ledgerChapterRes.json();
      const ledgerCharacter = await ledgerCharacterRes.json();
      const outline = await outlineRes.json();
      let chapterPack: any = null;
      const chapterPackRes = await fetch(`${baseUrl}/v1/splitbooks/${sid}/chapter_pack?chapter_no=${encodeURIComponent(String(chapterNo))}`);
      if (chapterPackRes.ok) {
        chapterPack = await chapterPackRes.json();
      }
      const healthPayload = {
        chapter_no: chapterNo,
        content: String(splitbookWritebackText || "").trim(),
      };
      const healthRes = await fetch(`${baseUrl}/v1/splitbooks/${sid}/chapter_health`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(healthPayload),
      });
      const health = healthRes.ok ? await healthRes.json() : null;

      const tasks = [
        saver(outputDir, `${splitbookNamePrefix}_结构账本-章节_${ts}`, JSON.stringify(ledgerChapter, null, 2), "json"),
        saver(outputDir, `${splitbookNamePrefix}_结构账本-角色_${ts}`, JSON.stringify(ledgerCharacter, null, 2), "json"),
        saver(outputDir, `${splitbookNamePrefix}_整卷大纲_${ts}`, JSON.stringify(outline, null, 2), "json"),
      ];
      if (chapterPack) {
        tasks.push(saver(outputDir, `${splitbookNamePrefix}_章节包-第${chapterNo}章_${ts}`, JSON.stringify(chapterPack, null, 2), "json"));
      }
      if (health) {
        tasks.push(saver(outputDir, `${splitbookNamePrefix}_章节体检-第${chapterNo}章_${ts}`, JSON.stringify(health, null, 2), "json"));
      }
      const saved = await Promise.all(tasks);
      setSplitbookLedgerRows((ledgerChapter.rows || []) as any[]);
      setSplitbookLedgerSummary(ledgerChapter.summary || null);
      setSplitbookOutlinePreview(outline || null);
      if (chapterPack) setSplitbookChapterPack(chapterPack);
      if (health) setSplitbookHealthReport(health);
      setStatus(`拆书产物已导出到预设目录，共 ${saved.length} 个文件`);
      await window.desktopApi.openPath(outputDir, true);
    } catch (err) {
      setStatus(`导出拆书产物失败：${formatAnyError(err)}`);
    }
  }

  async function loadChapters(currentBookId = bookId): Promise<ChapterItem[]> {
    if (!currentBookId) {
      setChapterItems([]);
      setChapterOutlineOverview([]);
      return [];
    }
    const q = encodeURIComponent(chapterQuery.trim());
    const res = await fetch(`${baseUrl}/v1/books/${currentBookId}/chapters?query=${q}&limit=200`);
    if (!res.ok) throw new Error(`CHAPTERS_LOAD_FAILED:${res.status}`);
    const data = await res.json();
    const items = (data.chapters || []) as ChapterItem[];
    setChapterItems(items);
    void loadChapterOutlineOverview(items, { silent: true });
    return items;
  }

  async function loadChapterOutlineOverview(
    chaptersInput?: ChapterItem[],
    opts?: { silent?: boolean }
  ) {
    const silent = !!opts?.silent;
    const itemsSource = Array.isArray(chaptersInput) ? chaptersInput : chapterItems;
    const items = [...itemsSource]
      .filter((c) => String(c?.chapter_id || "").trim())
      .sort((a, b) => Number(a.chapter_no || 0) - Number(b.chapter_no || 0));
    if (items.length === 0) {
      setChapterOutlineOverview([]);
      return;
    }
    setChapterOutlineOverviewLoading(true);
    try {
      const queue = [...items];
      const rows: ChapterOutlineOverviewItem[] = new Array(items.length);
      const indexById = new Map<string, number>();
      items.forEach((it, idx) => indexById.set(String(it.chapter_id), idx));
      const workerCount = Math.max(1, Math.min(6, items.length));
      await Promise.all(
        Array.from({ length: workerCount }).map(async () => {
          while (queue.length) {
            const ch = queue.shift();
            if (!ch) break;
            const chapterIdVal = String(ch.chapter_id || "");
            const row: ChapterOutlineOverviewItem = {
              chapterId: chapterIdVal,
              chapterNo: Number(ch.chapter_no || 0) || 0,
              title: String(ch.title || "").trim(),
              outlineVersion: 0,
              outlineNodes: 0,
              outlineSummary: "",
              updatedAt: "",
              loadError: "",
            };
            try {
              const verRes = await fetch(`${baseUrl}/v1/chapters/${chapterIdVal}/outline_detail/versions`);
              if (!verRes.ok) throw new Error(`OUTLINE_VERSIONS_LOAD_FAILED:${verRes.status}`);
              const verData = await verRes.json();
              const verItems = Array.isArray(verData?.items) ? verData.items : [];
              const latestVer = verItems.length ? verItems[0] : null;
              if (latestVer) {
                row.outlineVersion = Math.max(0, Number(latestVer.version || 0) || 0);
                row.updatedAt = String(latestVer.created_at || "");
                row.outlineSummary = toCleanSingleLine(String(latestVer.title || ""), 90);
              }
            } catch (err) {
              row.loadError = toCleanSingleLine(formatAnyError(err), 60);
            }
            const idx = indexById.get(chapterIdVal);
            if (typeof idx === "number") rows[idx] = row;
          }
        })
      );
      setChapterOutlineOverview(rows.filter(Boolean));
      if (!silent) {
        const doneCount = rows.filter((r) => r && r.outlineVersion > 0).length;
        setStatus(`章纲总览已刷新：${doneCount}/${rows.length} 章已有章纲。`);
      }
    } catch (err) {
      if (!silent) setStatus(`章纲总览刷新失败：${formatAnyError(err)}`);
    } finally {
      setChapterOutlineOverviewLoading(false);
    }
  }

  async function runSplitbookWritebackBatchPreview() {
    if (!selectedSplitbookId || splitbookWritebackBatchBusy) return;
    setSplitbookWritebackBatchBusy(true);
    setSplitbookWritebackBatchConfirm(null);
    try {
      const chapterNos = parseSplitbookChapterFilterInput(splitbookWritebackChapterFilter);
      const body: Record<string, unknown> = {
        force: !!splitbookWritebackBatchForce,
      };
      if (chapterNos.length) body.chapter_nos = chapterNos;
      const res = await fetch(`${baseUrl}/v1/splitbooks/${selectedSplitbookId}/writeback_preview_batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const out = await res.json().catch(() => ({} as Record<string, any>));
        const detail = String(out?.detail_zh || out?.detail || out?.message || "").trim();
        throw new Error(detail || `SPLITBOOK_WRITEBACK_BATCH_PREVIEW_FAILED:${res.status}`);
      }
      const queued = await res.json();
      const jobId = String(queued?.job_id || "");
      if (!jobId) throw new Error("SPLITBOOK_WRITEBACK_BATCH_PREVIEW_JOB_ID_MISSING");
      setStatus(`批量回写预览任务已入队：${jobId}`);
      if (showJobs) await pollJobs();
      const done = await waitJobTerminal(jobId, undefined, {
        splitbookId: selectedSplitbookId,
        kind: "writeback_preview_batch",
      });
      const result = done?.result && typeof done.result === "object" ? done.result : {};
      setSplitbookWritebackBatchPreview(result);
      const changedTotal = Number((result as any)?.changed_total || 0);
      const requestedTotal = Number((result as any)?.requested_total || 0);
      const maxChunkCount = Number((result as any)?.max_chunk_count || 0);
      const singleChapterWarning = !!(result as any)?.single_chapter_warning;
      if (changedTotal > 0) {
        if (singleChapterWarning) {
          setStatus(`批量预览完成：待回写 ${changedTotal}/${requestedTotal} 章；当前仅识别到单章且分块数 ${maxChunkCount}，回写增量可能有限。`);
        } else {
          setStatus(`批量预览完成：待回写 ${changedTotal}/${requestedTotal} 章`);
        }
      } else {
        setStatus(`批量预览完成：无变更章节（${requestedTotal} 章）。如需强制重算请勾选“强制重算”。`);
      }
    } catch (err) {
      setStatus(`批量回写预览失败：${formatAnyError(err)}`);
    } finally {
      setSplitbookWritebackBatchBusy(false);
    }
  }

  async function runSplitbookWritebackBatchConfirm() {
    if (!selectedSplitbookId || splitbookWritebackBatchBusy) return;
    const previewToken = String(splitbookWritebackBatchPreview?.preview_token || "").trim();
    if (!previewToken) {
      setStatus("请先执行批量回写预览，确认变更章节后再回写。");
      return;
    }
    setSplitbookWritebackBatchBusy(true);
    try {
      const chapterNos = parseSplitbookChapterFilterInput(splitbookWritebackChapterFilter);
      const body: Record<string, unknown> = {
        preview_token: previewToken,
        force: !!splitbookWritebackBatchForce,
        stop_on_error: false,
      };
      if (chapterNos.length) body.chapter_nos = chapterNos;
      const res = await fetch(`${baseUrl}/v1/splitbooks/${selectedSplitbookId}/writeback_confirm_batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const out = await res.json().catch(() => ({} as Record<string, any>));
        const detail = String(out?.detail_zh || out?.detail || out?.message || "").trim();
        throw new Error(detail || `SPLITBOOK_WRITEBACK_BATCH_CONFIRM_FAILED:${res.status}`);
      }
      const queued = await res.json();
      const jobId = String(queued?.job_id || "");
      if (!jobId) throw new Error("SPLITBOOK_WRITEBACK_BATCH_CONFIRM_JOB_ID_MISSING");
      setStatus(`批量回写确认任务已入队：${jobId}`);
      if (showJobs) await pollJobs();
      const done = await waitJobTerminal(jobId, undefined, {
        splitbookId: selectedSplitbookId,
        kind: "writeback_confirm_batch",
      });
      const result = done?.result && typeof done.result === "object" ? done.result : {};
      setSplitbookWritebackBatchConfirm(result);
      const appliedTotal = Number((result as any)?.applied_total || 0);
      const failedTotal = Number((result as any)?.failed_total || 0);
      const changedTotal = Number((result as any)?.changed_total || 0);
      const factsWrittenTotal =
        Number((result as any)?.facts_written_total || 0) ||
        ((Array.isArray((result as any)?.results) ? (result as any).results : []) as any[]).reduce(
          (acc, row) => acc + Number((row as any)?.facts_written || 0),
          0
        );
      const growthWrittenTotal =
        Number((result as any)?.growth_written_total || 0) ||
        ((Array.isArray((result as any)?.results) ? (result as any).results : []) as any[]).reduce(
          (acc, row) => acc + Number((row as any)?.growth_written || 0),
          0
        );
      if (appliedTotal > 0 && factsWrittenTotal === 0 && growthWrittenTotal === 0) {
        setStatus(`批量回写完成：已回写 ${appliedTotal}/${changedTotal} 章，失败 ${failedTotal} 章；但结构增量为 0（facts/growth 均为 0）。`);
      } else {
        setStatus(
          `批量回写完成：已回写 ${appliedTotal}/${changedTotal} 章，失败 ${failedTotal} 章，写入 facts=${factsWrittenTotal}，growth=${growthWrittenTotal}`
        );
      }
      await loadSplitbookLedger().catch(() => {});
      await loadSplitbookOutlinePreview().catch(() => {});
      await loadSplitbookChapterPack().catch(() => {});
      await loadSplitbooks().catch(() => {});
    } catch (err) {
      setStatus(`批量回写确认失败：${formatAnyError(err)}`);
    } finally {
      setSplitbookWritebackBatchBusy(false);
    }
  }

  async function loadChapterTextPreviewForDialog(chapterIdVal: string, opts?: { silent?: boolean }) {
    const chapterVal = String(chapterIdVal || "").trim();
    const silent = !!opts?.silent;
    if (!chapterVal) return false;
    setChapterOutlinePreviewTextLoading(true);
    try {
      const res = await fetch(`${baseUrl}/v1/chapters/${encodeURIComponent(chapterVal)}/latest_text_preview`);
      if (!res.ok) {
        const detail = await getApiErrorDetail(res);
        throw new Error(detail || `LATEST_TEXT_PREVIEW_FAILED:${res.status}`);
      }
      const latest = await res.json();
      const textValue = String(latest?.text || "");
      const draftId = String(latest?.draft_id || latest?.text_ver_id || "");
      const source =
        String(latest?.source || "").trim().toLowerCase() === "text_version" ? "text_version" : "draft";
      const updatedAt = String(latest?.created_at || "");
      setChapterOutlinePreviewText(textValue);
      setChapterOutlinePreviewTextDraftId(draftId);
      setChapterOutlinePreviewTextSource(textValue.trim() ? source : "");
      setChapterOutlinePreviewTextUpdatedAt(updatedAt);
      setChapterOutlinePreviewTextDirty(false);
      setChapterOutlinePreviewMatchInfo(null);
      if (!silent) {
        if (textValue.trim()) {
          setStatus(`章节正文已加载：${source === "text_version" ? "来自正文版本" : "来自草稿版本"}`);
        } else {
          setStatus("当前暂无可编辑正文，请先生成或导入正文。");
        }
      }
      return !!textValue.trim();
    } catch (err) {
      setChapterOutlinePreviewText("");
      setChapterOutlinePreviewTextDraftId("");
      setChapterOutlinePreviewTextSource("");
      setChapterOutlinePreviewTextUpdatedAt("");
      setChapterOutlinePreviewTextDirty(false);
      setChapterOutlinePreviewMatchInfo(null);
      if (!silent) setStatus(`加载章节正文失败：${formatAnyError(err)}`);
      return false;
    } finally {
      setChapterOutlinePreviewTextLoading(false);
    }
  }

  async function saveChapterTextFromOutlinePreview() {
    const dialog = chapterOutlinePreviewDialog;
    if (!dialog) return;
    const chapterIdVal = String(dialog.chapterId || "").trim();
    const content = String(chapterOutlinePreviewText || "").trim();
    if (!chapterIdVal) {
      setStatus("保存失败：缺少章节 ID。");
      return;
    }
    if (!content) {
      setStatus("请先输入章节正文内容再保存。");
      return;
    }
    setChapterOutlinePreviewTextSaving(true);
    try {
      const res = await fetch(`${baseUrl}/v1/chapters/${encodeURIComponent(chapterIdVal)}/manual_import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content,
          note: "章纲预览窗口编辑保存",
          selected_by: "user",
          source: "manual_import_preview",
        }),
      });
      const out = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(String((out as any)?.detail || `HTTP_${res.status}`));
      const nextDraftId = String((out as any)?.draft?.draft_id || (out as any)?.text_version?.text_ver_id || "");
      const nextUpdatedAt = String((out as any)?.draft?.created_at || (out as any)?.text_version?.created_at || "");
      setChapterOutlinePreviewTextDraftId(nextDraftId);
      setChapterOutlinePreviewTextSource("draft");
      setChapterOutlinePreviewTextUpdatedAt(nextUpdatedAt);
      setChapterOutlinePreviewTextDirty(false);
      setChapterDraftPreviewText(content);
      setChapterDraftPreviewDraftId(nextDraftId);
      setChapterDraftPreviewSource("draft");
      setChapterDraftPreviewUpdatedAt(nextUpdatedAt);
      setChapterDraftPreviewDirty(false);
      setManualChapterImportText(content);
      if (String(chapterId || "").trim() === chapterIdVal) {
        void quickLoadVersions({ silent: true });
      }
      setStatus(`第${dialog.chapterNo || "?"}章正文已保存并激活。`);
    } catch (err) {
      setStatus(`保存章节正文失败：${formatAnyError(err)}`);
    } finally {
      setChapterOutlinePreviewTextSaving(false);
    }
  }

  function jumpToOutlineNodeInPreview(node: unknown) {
    const nodeObj = node && typeof node === "object" ? (node as Record<string, unknown>) : null;
    const nodeId = String(nodeObj?.node_id || "").trim();
    if (nodeId) setChapterOutlinePreviewActiveNodeId(nodeId);
    const keywords = extractOutlineNodeKeywords(nodeObj);
    const match = findTextRangeByKeywords(chapterOutlinePreviewText, keywords);
    if (!match) {
      setChapterOutlinePreviewMatchInfo({
        nodeId,
        keyword: keywords[0] || "",
        start: -1,
        end: -1,
        matched: false,
      });
      return;
    }
    setChapterOutlinePreviewMatchInfo({
      nodeId,
      keyword: match.keyword,
      start: match.start,
      end: match.end,
      matched: true,
    });
    window.setTimeout(() => {
      focusTextareaRange(chapterOutlinePreviewTextRef, match.start, match.end);
    }, 0);
  }

  function jumpToSelectedOutlineNodeInDraftPreview() {
    if (!selectedNode) {
      setStatus("请先在章纲编辑区选中一个节点。");
      return;
    }
    if (!chapterDraftPreviewText.trim()) {
      setStatus("请先加载章节正文，再执行定位。");
      return;
    }
    const keywords = extractOutlineNodeKeywords(selectedNode);
    const match = findTextRangeByKeywords(chapterDraftPreviewText, keywords);
    if (!match) {
      setStatus("未命中正文片段：请补充节点摘要或手动查找。");
      return;
    }
    window.setTimeout(() => {
      focusTextareaRange(chapterDraftPreviewTextRef, match.start, match.end);
    }, 0);
    setStatus(`已定位正文片段：${toCleanSingleLine(match.keyword, 32)}`);
  }

  async function previewChapterOutlineFromOverview(item: ChapterOutlineOverviewItem) {
    const chapterIdVal = String(item.chapterId || "").trim();
    if (!chapterIdVal) return;
    setChapterOutlinePreviewBusyId(chapterIdVal);
    setChapterOutlinePreviewDialogLoading(true);
    setChapterOutlinePreviewActiveNodeId("");
    setChapterOutlinePreviewMatchInfo(null);
    setChapterOutlinePreviewText("");
    setChapterOutlinePreviewTextDraftId("");
    setChapterOutlinePreviewTextSource("");
    setChapterOutlinePreviewTextUpdatedAt("");
    setChapterOutlinePreviewTextDirty(false);
    try {
      const detailRes = await fetch(`${baseUrl}/v1/chapters/${chapterIdVal}/outline_detail?version=latest`);
      if (!detailRes.ok) throw new Error(`OUTLINE_LOAD_FAILED:${detailRes.status}`);
      const detail = await detailRes.json();
      const verRes = await fetch(`${baseUrl}/v1/chapters/${chapterIdVal}/outline_detail/versions`);
      let verItems: VersionItem[] = [];
      if (verRes.ok) {
        const data = await verRes.json();
        verItems = (Array.isArray(data?.items) ? data.items : []) as VersionItem[];
      }
      setChapterOutlinePreviewDialog({
        chapterId: chapterIdVal,
        chapterNo: Number(item.chapterNo || 0) || 0,
        title: String(item.title || "").trim(),
        selectedVersion: "latest",
        outlineVersion: Number(detail?.version || item.outlineVersion || 0) || 0,
        outline: (detail?.content || { nodes: [] }) as OutlineDetail,
        versions: verItems,
      });
      void loadChapterTextPreviewForDialog(chapterIdVal, { silent: true });
      setStatus(`已打开第${item.chapterNo || "?"}章章纲预览。`);
    } catch (err) {
      setStatus(`章纲预览失败：${formatAnyError(err)}`);
    } finally {
      setChapterOutlinePreviewBusyId("");
      setChapterOutlinePreviewDialogLoading(false);
    }
  }

  async function loadChapterOutlinePreviewVersion(version: string) {
    const dialog = chapterOutlinePreviewDialog;
    if (!dialog) return;
    const nextVersion = String(version || "latest").trim() || "latest";
    setChapterOutlinePreviewDialogLoading(true);
    try {
      const detailRes = await fetch(
        `${baseUrl}/v1/chapters/${dialog.chapterId}/outline_detail?version=${encodeURIComponent(nextVersion)}`
      );
      if (!detailRes.ok) throw new Error(`OUTLINE_LOAD_FAILED:${detailRes.status}`);
      const detail = await detailRes.json();
      setChapterOutlinePreviewDialog((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          selectedVersion: nextVersion,
          outlineVersion: Number(detail?.version || 0) || 0,
          outline: (detail?.content || { nodes: [] }) as OutlineDetail,
        };
      });
      setChapterOutlinePreviewActiveNodeId("");
      setChapterOutlinePreviewMatchInfo(null);
    } catch (err) {
      setStatus(`章纲版本切换失败：${formatAnyError(err)}`);
    } finally {
      setChapterOutlinePreviewDialogLoading(false);
    }
  }

  async function applyChapterOutlinePreviewToEditor() {
    const dialog = chapterOutlinePreviewDialog;
    if (!dialog) return;
    setChapterOutlinePreviewApplyBusy(true);
    try {
      const chapterIdVal = String(dialog.chapterId || "").trim();
      if (!chapterIdVal) throw new Error("CHAPTER_ID_REQUIRED");
      setChapterId(chapterIdVal);
      setOutline(dialog.outline || { nodes: [] });
      setSelectedNodeId((dialog.outline as any)?.nodes?.[0]?.node_id || null);
      setDirty(false);
      setVersions(dialog.versions || []);
      setSelectedVersion(dialog.selectedVersion || "latest");
      await refreshOutlineInjectionStatus(chapterIdVal);
      setStatus(`已将第${dialog.chapterNo || "?"}章章纲加载到编辑区。`);
      setChapterOutlinePreviewDialog(null);
      scrollToSection("section-outline-tools");
    } catch (err) {
      setStatus(`加载到编辑区失败：${formatAnyError(err)}`);
    } finally {
      setChapterOutlinePreviewApplyBusy(false);
    }
  }

  async function openCurrentChapterOutlinePreview() {
    const chapterIdVal = String(chapterId || "").trim();
    if (!chapterIdVal) {
      setStatus("请先选择章节，再预览章纲。");
      return;
    }
    const chapter = chapterItems.find((c) => String(c.chapter_id || "") === chapterIdVal) || null;
    const hit = chapterOutlineOverview.find((x) => String(x.chapterId || "") === chapterIdVal) || null;
    const fallback: ChapterOutlineOverviewItem = {
      chapterId: chapterIdVal,
      chapterNo: Number(chapter?.chapter_no || 0) || 0,
      title: String(chapter?.title || "未命名章节"),
      outlineVersion: Number(hit?.outlineVersion || 0) || 0,
      outlineNodes: Number(hit?.outlineNodes || 0) || 0,
      outlineSummary: String(hit?.outlineSummary || ""),
      updatedAt: String(hit?.updatedAt || ""),
      loadError: "",
    };
    await previewChapterOutlineFromOverview(hit || fallback);
  }

  async function deleteChapterOutlineFromOverview(item: ChapterOutlineOverviewItem) {
    const chapterIdVal = String(item.chapterId || "").trim();
    if (!chapterIdVal) return;
    if (Number(item.outlineVersion || 0) <= 0) {
      setStatus(`第${item.chapterNo || "?"}章暂无可删除章纲。`);
      return;
    }
    const chapterLabel = `第${item.chapterNo || "?"}章 · ${item.title || "未命名章节"}`;
    const ok = window.confirm(`确认删除 ${chapterLabel} 的最新章纲（v${item.outlineVersion}）吗？\n此操作会删除该章当前章纲版本。`);
    if (!ok) return;
    setChapterOutlineDeleteBusyId(chapterIdVal);
    try {
      const res = await fetch(`${baseUrl}/v1/chapters/${chapterIdVal}/outline_detail?version=latest`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const detail = await getApiErrorDetail(res);
        throw new Error(detail || `OUTLINE_DELETE_FAILED:${res.status}`);
      }
      if (String(chapterOutlinePreviewDialog?.chapterId || "") === chapterIdVal) {
        setChapterOutlinePreviewActiveNodeId("");
        setChapterOutlinePreviewMatchInfo(null);
        setChapterOutlinePreviewDialog(null);
      }
      await loadChapterOutlineOverview(undefined, { silent: true });
      if (String(chapterId || "").trim() === chapterIdVal) {
        await loadOutline("latest");
      }
      setStatus(`已删除 ${chapterLabel} 的最新章纲。`);
    } catch (err) {
      setStatus(`删除章纲失败：${formatAnyError(err)}`);
    } finally {
      setChapterOutlineDeleteBusyId("");
    }
  }

  async function loadDraftConfirmations(currentBookId = bookId, opts?: { silent?: boolean }) {
    const bid = String(currentBookId || "").trim();
    if (!bid) {
      setDraftConfirmTasks([]);
      setDraftConfirmSummary(null);
      return;
    }
    setDraftConfirmLoading(true);
    try {
      const res = await fetch(`${baseUrl}/v1/books/${encodeURIComponent(bid)}/draft_confirmations?limit=2000`);
      if (!res.ok) throw new Error(`DRAFT_CONFIRMATIONS_LOAD_FAILED:${res.status}`);
      const data = await res.json();
      const items = Array.isArray(data?.items) ? data.items : [];
      setDraftConfirmTasks(items);
      setDraftConfirmSummary({
        total: Number(data?.total || items.length || 0),
        confirmed: Number(data?.confirmed || 0),
        pending: Number(data?.pending || 0),
      });
    } catch (err) {
      if (!opts?.silent) setStatus(`章节确认状态加载失败：${formatAnyError(err)}`);
    } finally {
      setDraftConfirmLoading(false);
    }
  }

  async function loadVolumes(currentBookId = bookId) {
    if (!currentBookId) {
      setVolumeItems([]);
      setQuickVolumeId("");
      return [];
    }
    const res = await fetch(`${baseUrl}/v1/books/${currentBookId}/volumes`);
    if (!res.ok) throw new Error(`VOLUMES_LOAD_FAILED:${res.status}`);
    const data = await res.json();
    const items = (data.items || []) as any[];
    setVolumeItems(items);
    const currentVolumeId = String(quickVolumeId || "");
    const hasCurrent = items.some((it) => String(it?.volume_id || "") === currentVolumeId);
    if (!hasCurrent) {
      setQuickVolumeId(items.length ? String(items[0].volume_id || "") : "");
    }
    return items;
  }

  async function ensureStructureTargetsReady(opts?: { silent?: boolean }): Promise<{ chapterId: string; volumeId: string } | null> {
    const silent = !!opts?.silent;
    if (!bookId) {
      if (!silent) setStatus("请先选择书籍。");
      return null;
    }

    let chapters = chapterItems;
    if (!chapters.length || !chapters.some((x) => x.chapter_id === chapterId)) {
      const chRes = await fetch(`${baseUrl}/v1/books/${bookId}/chapters?query=&limit=200`);
      if (chRes.ok) {
        const chData = await chRes.json();
        chapters = (chData.chapters || []) as ChapterItem[];
      }
    }
    if (!chapters.length) {
      const createRes = await fetch(`${baseUrl}/v1/books/${bookId}/chapters`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chapter_no: 1, title: "第1章" }),
      });
      if (!createRes.ok) {
        if (!silent) setStatus("自动创建章节失败，请先手动创建章节。");
        return null;
      }
      const created = (await createRes.json()) as ChapterItem;
      chapters = [created];
      if (!silent) setStatus("已自动创建第1章，可继续结构生成。");
    }
    setChapterItems(chapters);
    void loadChapterOutlineOverview(chapters, { silent: true });
    let nextChapterId = String(chapterId || "").trim();
    if (!nextChapterId || !chapters.some((x) => x.chapter_id === nextChapterId)) {
      nextChapterId = String(chapters[0]?.chapter_id || "");
      setChapterId(nextChapterId);
    }
    if (!nextChapterId) {
      if (!silent) setStatus("未找到可用章节，请先创建章节。");
      return null;
    }

    let volumes = volumeItems;
    if (!volumes.length || !volumes.some((x) => String(x?.volume_id || "") === String(quickVolumeId || ""))) {
      const volRes = await fetch(`${baseUrl}/v1/books/${bookId}/volumes`);
      if (volRes.ok) {
        const volData = await volRes.json();
        volumes = (volData.items || []) as any[];
      }
    }
    if (!volumes.length) {
      const autoRes = await fetch(`${baseUrl}/v1/books/${bookId}/volumes/auto_create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chapters_per_volume: 30 }),
      });
      if (!autoRes.ok) {
        if (!silent) setStatus("自动创建卷失败，请先在卷面板创建或刷新卷。");
        return null;
      }
      const volRes = await fetch(`${baseUrl}/v1/books/${bookId}/volumes`);
      if (!volRes.ok) {
        if (!silent) setStatus("自动创建卷后读取失败，请刷新卷列表。");
        return null;
      }
      const volData = await volRes.json();
      volumes = (volData.items || []) as any[];
      if (!silent) setStatus("已自动创建卷，可继续结构生成。");
    }
    setVolumeItems(volumes);
    let nextVolumeId = String(quickVolumeId || "").trim();
    if (!nextVolumeId || !volumes.some((x) => String(x?.volume_id || "") === nextVolumeId)) {
      nextVolumeId = String(volumes[0]?.volume_id || "");
      setQuickVolumeId(nextVolumeId);
    }
    if (!nextVolumeId) {
      if (!silent) setStatus("未找到可用卷，请先创建或刷新卷。");
      return null;
    }

    return { chapterId: nextChapterId, volumeId: nextVolumeId };
  }

  async function loadBookWorkspace(currentBookId = bookId) {
    if (!currentBookId) {
      setNewBookWorkspacePath("");
      return;
    }
    try {
      const res = await fetch(`${baseUrl}/v1/books/${currentBookId}/workspace`);
      if (!res.ok) return;
      const data = await res.json();
      const pathValue = String(data?.workspace?.workspace_path || data?.workspace_path || "").trim();
      if (pathValue) setNewBookWorkspacePath(pathValue);
    } catch {}
  }

  async function saveWritingBrief(currentBookId = bookId) {
    if (!currentBookId) return;
    const getRes = await fetch(`${baseUrl}/v1/books/${currentBookId}/settings`);
    const existing = getRes.ok ? ((await getRes.json())?.settings || {}) : {};
    const writingBrief = {
      genre: storyGenre.trim(),
      theme: storyTheme.trim(),
      tone: storyTone.trim(),
      audience: storyAudience.trim(),
      idea: storyIdea.trim(),
      setting: storySetting.trim(),
      updated_at: new Date().toISOString(),
    };
    const nextSettings = {
      ...(existing || {}),
      writing_brief: writingBrief,
    };
    const saveRes = await fetch(`${baseUrl}/v1/books/${currentBookId}/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(nextSettings),
    });
    if (!saveRes.ok) throw new Error(`SAVE_BOOK_BRIEF_FAILED:${saveRes.status}`);
  }

  function normalizeMasterOutline(input: any) {
    if (!input || typeof input !== "object") return null;
    const planned = Math.max(0, Number((input as any).planned_chapters || 0) || 0);
    const summary = String((input as any).summary || "").trim();
    const phasesRaw = Array.isArray((input as any).phases) ? (input as any).phases : [];
    const phases = phasesRaw
      .filter((x: any) => x && typeof x === "object")
      .slice(0, 20)
      .map((x: any) => ({
        name: String(x.name || "").trim(),
        goal: String(x.goal || "").trim(),
        chapter_range: String(x.chapter_range || "").trim(),
      }));
    return {
      schema: "writing_master_outline_v1",
      summary,
      planned_chapters: planned,
      premise: String((input as any).premise || "").trim(),
      core_conflict: String((input as any).core_conflict || "").trim(),
      theme: String((input as any).theme || "").trim(),
      audience: String((input as any).audience || "").trim(),
      phases,
      constraints: (input as any).constraints && typeof (input as any).constraints === "object" ? (input as any).constraints : {},
      splitbook_hints_count: Math.max(0, Number((input as any).splitbook_hints_count || 0) || 0),
      updated_at: String((input as any).updated_at || new Date().toISOString()),
    };
  }

  function inferPlannedChaptersFromVolumes() {
    if (!Array.isArray(volumeItems) || volumeItems.length === 0) return 0;
    let sum = 0;
    for (const vol of volumeItems) {
      const planned = Number((vol as any)?.planned_chapters || 0);
      const startNo = Number((vol as any)?.start_chapter_no || 0);
      const endNo = Number((vol as any)?.end_chapter_no || 0);
      if (planned > 0) sum += planned;
      else if (startNo > 0 && endNo >= startNo) sum += endNo - startNo + 1;
    }
    return Math.max(0, Math.round(sum));
  }

  function buildMasterOutlineDraft() {
    const structureHints = buildStructureHintsFromMaterialRefs(materialRefs);
    const volumeBasedChapters = inferPlannedChaptersFromVolumes();
    const planned = Math.max(
      1,
      Number(masterOutlinePlannedChapters || 0) || 0,
      volumeBasedChapters,
      chapterItems.length || 0
    );
    const phases = Array.isArray(volumeItems)
      ? volumeItems
          .slice()
          .sort((a: any, b: any) => Number(a?.volume_no || 0) - Number(b?.volume_no || 0))
          .slice(0, 20)
          .map((vol: any) => ({
            name: String(vol?.title || `卷${String(vol?.volume_no || "")}`),
            goal: String(vol?.note || storyTheme || "推进主线与阶段冲突"),
            chapter_range:
              Number(vol?.start_chapter_no || 0) > 0 && Number(vol?.end_chapter_no || 0) >= Number(vol?.start_chapter_no || 0)
                ? `${Number(vol.start_chapter_no)}-${Number(vol.end_chapter_no)}`
                : "",
          }))
      : [];
    const summary = masterOutlineSummary.trim() || `${storyIdea.trim() || "推进主线冲突"}，并围绕“${storyTheme.trim() || "成长与代价"}”展开。`;
    return normalizeMasterOutline({
      summary,
      planned_chapters: planned,
      premise: storyIdea.trim(),
      core_conflict: storySetting.trim() || storyTheme.trim(),
      theme: storyTheme.trim(),
      audience: storyAudience.trim(),
      phases,
      constraints: {
        anti_copy: "仅可借结构，不可复述来源文本",
        continuity: "生成章节需保持总纲→卷纲→章纲一致",
      },
      splitbook_hints_count: structureHints?.total_lines || 0,
      updated_at: new Date().toISOString(),
    });
  }

  function formatMasterOutlineBasis(meta: any): string {
    const basis = Array.isArray(meta?.basis)
      ? meta.basis.map((x: any) => String(x || "").trim()).filter(Boolean)
      : [];
    if (!basis.length) return "创作简报 + 拆书结构（如已选择） + 卷信息";
    const map: Record<string, string> = {
      writing_brief: "创作简报",
      writing_brief_structured: "简报结构化字段",
      volume_items: "卷信息",
      book_db_context: "数据库上下文",
      chapter_items_db: "章节库数据",
      splitbook_selected: "拆书库选择",
      splitbook_outline_structure: "拆书大纲结构",
      splitbook_structure_hints: "拆书结构提示",
      manual_structure_hints: "手动结构提示",
      material_refs: "素材引用",
      material_guidance: "素材要点",
      material_library: "素材库",
      prompt_md_template: "大纲提示词模板(MD)",
    };
    return basis.map((x: string) => map[x] || x).join(" + ");
  }

  function toPrettyJsonText(value: any): string {
    if (value === null || value === undefined) return "";
    if (typeof value === "string") return value;
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }

  function summarizePromptPayload(value: any): string {
    if (!value || typeof value !== "object") return "未记录";
    const keys = Object.keys(value || {}).filter(Boolean);
    if (!keys.length) return "未记录";
    const top = keys.slice(0, 8).join(" / ");
    return keys.length > 8 ? `${top} 等 ${keys.length} 项` : top;
  }

  function formatStructureStepStatusLabel(status: StructureStepBasisState["status"]): string {
    if (status === "running") return "进行中";
    if (status === "success") return "已完成";
    if (status === "error") return "失败";
    return "待执行";
  }

  function updateStructureStepBasis(
    step: "1.3.1" | "1.3.2" | "1.4.1" | "1.4.2",
    patch: Partial<StructureStepBasisState>
  ) {
    setStructureStepBasis((prev) => ({
      ...prev,
      [step]: {
        ...prev[step],
        ...patch,
        updatedAt: new Date().toISOString(),
      },
    }));
  }

  function chapterNoById(targetChapterId: string): number {
    const hit = chapterItems.find((x) => String(x.chapter_id) === String(targetChapterId));
    return Number(hit?.chapter_no || 0) || 0;
  }

  function buildChapterGenerationBasisText(): string {
    const parts = [
      `总纲${masterOutlineReady ? "已保存" : "未保存"}`,
      `卷纲${volumePlanApplied ? "已应用" : "未应用"}`,
      `章纲${outlineInjectStatus.ready ? `已注入(v${outlineInjectStatus.version || 1})` : chapterOutlineSeed ? "已生成草案" : "未准备"}`,
      `结构引用${splitbookStructureRefCount}条`,
      `素材${materialRefs.length}条`,
    ];
    return parts.join(" + ");
  }

  function updateChapterGenerationTrace(patch: Partial<ChapterGenerationTraceState>) {
    setChapterGenerationTrace((prev) => ({
      ...prev,
      ...patch,
      updatedAt: new Date().toISOString(),
    }));
  }

  function isJobLinkedToChapterGenerationTrace(job: JobItem | null | undefined): boolean {
    if (!job || !chapterGenerationTrace.updatedAt) return false;
    const traceIds = Array.isArray(chapterGenerationTrace.chapterIds)
      ? chapterGenerationTrace.chapterIds.map((x) => String(x || "").trim()).filter(Boolean)
      : [];
    const jobChapterId = String((job as any)?.chapter_id || "").trim();
    if (jobChapterId && traceIds.includes(jobChapterId)) return true;
    const payloadChapterId = String(((job as any)?.payload || {})?.chapter_id || "").trim();
    if (payloadChapterId && traceIds.includes(payloadChapterId)) return true;
    return false;
  }

  function openWritingStudioForChapterGenerationTrace() {
    const traceIds = Array.isArray(chapterGenerationTrace.chapterIds)
      ? chapterGenerationTrace.chapterIds.map((x) => String(x || "").trim()).filter(Boolean)
      : [];
    const currentChapter = String(chapterId || "").trim();
    const targetChapterId =
      (currentChapter && traceIds.includes(currentChapter) ? currentChapter : "") ||
      traceIds[0] ||
      "";
    if (targetChapterId) setChapterId(targetChapterId);
    setWorkspaceMode("writing");
    setShowJobs(false);
    window.setTimeout(() => {
      scrollToSection("section-writing-studio");
    }, 80);
    if (targetChapterId) {
      const chNo = chapterNoById(targetChapterId);
      setStatus(`已定位到写作工作台（1.5 目标章节：第${chNo || "?"}章）`);
    } else {
      setStatus("已定位到写作工作台（未记录章节，已打开 1.5 区域）");
    }
  }

  async function saveMasterOutline(
    currentBookId = bookId,
    draftOutline?: any,
    options?: { meta?: any; suppressStatus?: boolean; useOuterBusy?: boolean }
  ) {
    if (!currentBookId) return false;
    const outlineObj = normalizeMasterOutline(draftOutline || buildMasterOutlineDraft());
    if (!outlineObj || !String(outlineObj.summary || "").trim()) {
      setStatus("请先填写总纲摘要，再保存。");
      return false;
    }
    if (!options?.useOuterBusy) setMasterOutlineBusy(true);
    try {
      const getRes = await fetch(`${baseUrl}/v1/books/${currentBookId}/settings`);
      const existing = getRes.ok ? ((await getRes.json())?.settings || {}) : {};
      const nextSettings = {
        ...(existing || {}),
        writing_master_outline: outlineObj,
      };
      if (options?.meta && typeof options.meta === "object") {
        (nextSettings as any).writing_master_outline_meta = options.meta;
      }
      const saveRes = await fetch(`${baseUrl}/v1/books/${currentBookId}/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(nextSettings),
      });
      if (!saveRes.ok) throw new Error(`SAVE_MASTER_OUTLINE_FAILED:${saveRes.status}`);
      setMasterOutline(outlineObj);
      setMasterOutlineSummary(String(outlineObj.summary || ""));
      setMasterOutlinePlannedChapters(Number(outlineObj.planned_chapters || 0) || 0);
      if (options?.meta && typeof options.meta === "object") setMasterOutlineAiMeta(options.meta);
      const hintCount = Number(outlineObj.splitbook_hints_count || 0) || 0;
      if (!options?.suppressStatus) {
        setStatus(
          `总纲已保存（计划章节 ${Number(outlineObj.planned_chapters || 0)} 章` +
            `${hintCount > 0 ? `，结构提示 ${hintCount} 条` : ""}）`
        );
      }
      return true;
    } catch (err) {
      setStatus(`保存总纲失败：${formatAnyError(err)}`);
      return false;
    } finally {
      if (!options?.useOuterBusy) setMasterOutlineBusy(false);
    }
  }

  async function generateMasterOutlineAuto() {
    if (!bookId) {
      setStatus("请先创建或选择书籍。");
      return false;
    }
    const structureHints = buildStructureHintsFromMaterialRefs(materialRefs);
    const splitbookId =
      writingSplitbookRefId.trim() ||
      String(writingSplitbookRefLast?.splitbookId || "").trim() ||
      String(selectedSplitbookId || "").trim() ||
      "";
    const plannedHint = Math.max(
      1,
      Number(masterOutlinePlannedChapters || 0) || 0,
      inferPlannedChaptersFromVolumes(),
      chapterItems.length || 0
    );
    const requestPayload: Record<string, any> = {
      genre: storyGenre.trim() || undefined,
      theme: storyTheme.trim() || undefined,
      tone: storyTone.trim() || undefined,
      audience: storyAudience.trim() || undefined,
      idea: storyIdea.trim() || undefined,
      setting: storySetting.trim() || undefined,
      planned_chapters: plannedHint,
      volume_items: (volumeItems || []).slice(0, 50).map((vol: any) => ({
        volume_no: Number(vol?.volume_no || 0) || undefined,
        title: String(vol?.title || "").trim() || undefined,
        note: String(vol?.note || "").trim() || undefined,
        start_chapter_no: Number(vol?.start_chapter_no || 0) || undefined,
        end_chapter_no: Number(vol?.end_chapter_no || 0) || undefined,
        planned_chapters: Number(vol?.planned_chapters || 0) || undefined,
      })),
      material_refs: (materialRefs || []).slice(0, 30),
    };
    if (structureHints) requestPayload.structure_hints = structureHints;
    if (splitbookId) requestPayload.splitbook_id = splitbookId;
    setMasterOutlineBusy(true);
    try {
      const res = await fetch(`${baseUrl}/v1/books/${bookId}/master_outline/auto_generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestPayload),
      });
      if (!res.ok) throw new Error(`MASTER_OUTLINE_AUTO_FAILED:${res.status}`);
      const data = await res.json();
      const outlineObj = normalizeMasterOutline(data?.outline);
      if (!outlineObj) throw new Error("MASTER_OUTLINE_EMPTY");
      const metaRaw = data?.meta && typeof data.meta === "object" ? data.meta : {};
      const meta = {
        ...(metaRaw || {}),
        provider: String(metaRaw.provider || "ollama"),
        model: String(metaRaw.model || ""),
        basis: Array.isArray(metaRaw.basis) ? metaRaw.basis.map((x: any) => String(x || "").trim()).filter(Boolean) : [],
        structure_hints_applied: Number(metaRaw.structure_hints_applied || 0) || 0,
        structure_hint_sources: Array.isArray(metaRaw.structure_hint_sources)
          ? metaRaw.structure_hint_sources.map((x: any) => String(x || "").trim()).filter(Boolean)
          : [],
        generated_at: String(metaRaw.generated_at || new Date().toISOString()),
      };
      const saved = await saveMasterOutline(bookId, outlineObj, {
        meta,
        suppressStatus: true,
        useOuterBusy: true,
      });
      if (!saved) return false;
      const basisText = formatMasterOutlineBasis(meta);
      const hintPart = meta.structure_hints_applied > 0 ? `，结构提示 ${meta.structure_hints_applied} 条` : "";
      const dbPart =
        Number(meta?.db_context?.chapter_count || 0) > 0 || Number(meta?.db_context?.volume_count || 0) > 0
          ? `，数据库上下文：章节 ${Number(meta?.db_context?.chapter_count || 0)} / 卷 ${Number(meta?.db_context?.volume_count || 0)}`
          : "";
      setStatus(`总纲已自动生成并保存（依据：${basisText}${hintPart}${dbPart}）。`);
      void loadAiDebugInfo({ silent: true });
      return true;
    } catch (err) {
      setStatus(`自动生成总纲失败：${formatAnyError(err)}`);
      return false;
    } finally {
      setMasterOutlineBusy(false);
    }
  }

  async function loadWritingBrief(currentBookId = bookId) {
    if (!currentBookId) return;
    const res = await fetch(`${baseUrl}/v1/books/${currentBookId}/settings`);
    if (!res.ok) return;
    const data = await res.json();
    const settings = (data?.settings || {});
    const brief = settings.writing_brief || {};
    setStoryGenre(String(brief.genre || ""));
    setStoryTheme(String(brief.theme || ""));
    setStoryTone(String(brief.tone || ""));
    setStoryAudience(String(brief.audience || ""));
    setStoryIdea(String(brief.idea || ""));
    setStorySetting(String(brief.setting || ""));
    const loadedOutline = normalizeMasterOutline(settings.writing_master_outline);
    setMasterOutline(loadedOutline);
    setMasterOutlineSummary(String(loadedOutline?.summary || ""));
    setMasterOutlinePlannedChapters(Number(loadedOutline?.planned_chapters || 0) || 0);
    const loadedMeta = settings.writing_master_outline_meta;
    setMasterOutlineAiMeta(loadedMeta && typeof loadedMeta === "object" ? loadedMeta : null);
  }

  async function loadAiDebugInfo(opts?: { silent?: boolean }) {
    if (!bookId) {
      if (!opts?.silent) setStatus("请先选择书籍，再查看 AI 调用明细。");
      return false;
    }
    setAiDebugBusy(true);
    setAiDebugError("");
    try {
      const params = new URLSearchParams();
      if (String(chapterId || "").trim()) params.set("chapter_id", String(chapterId).trim());
      const url = `${baseUrl}/v1/books/${bookId}/ai_debug${params.toString() ? `?${params.toString()}` : ""}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`LOAD_AI_DEBUG_FAILED:${res.status}`);
      const out = await res.json();
      setAiDebugData(out && typeof out === "object" ? out : null);
      if (!opts?.silent) {
        const runId = String(out?.draft_generation?.run?.run_id || "").trim();
        setStatus(`AI 调用明细已刷新${runId ? `（最近闭环 Run=${runId.slice(0, 8)}...）` : ""}`);
      }
      return true;
    } catch (err) {
      const msg = formatAnyError(err);
      setAiDebugError(msg);
      if (!opts?.silent) setStatus(`加载 AI 调用明细失败：${msg}`);
      return false;
    } finally {
      setAiDebugBusy(false);
    }
  }

  async function createBookProjectFromStudio() {
    const title = newBookName.trim();
    const workspacePath = newBookWorkspacePath.trim();
    if (!title) {
      setStatus("请先输入书名");
      return;
    }
    if (!workspacePath) {
      setStatus("请先设置书籍存储目录");
      return;
    }
    setWriterStudioBusy(true);
    try {
      const createRes = await fetch(`${baseUrl}/v1/books`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          author: newBookAuthor.trim() || null,
          language: newBookLanguage.trim() || "zh",
          notes: newBookNotes.trim() || null,
        }),
      });
      if (!createRes.ok) throw new Error(`BOOK_CREATE_FAILED:${createRes.status}`);
      const book = (await createRes.json()) as BookItem;
      const createdBookId = String(book.book_id);
      setBookId(createdBookId);

      const wsRes = await fetch(`${baseUrl}/v1/books/${createdBookId}/workspace`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workspace_path: workspacePath }),
      });
      if (!wsRes.ok) throw new Error(`BOOK_WORKSPACE_SET_FAILED:${wsRes.status}`);

      await saveWritingBrief(createdBookId);

      const chRes = await fetch(`${baseUrl}/v1/books/${createdBookId}/chapters`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chapter_no: 1,
          title: "第1章",
          arc_id: "vol-1",
          arc_index: 1,
        }),
      });
      if (chRes.ok) {
        const ch = (await chRes.json()) as ChapterItem;
        setChapterId(String(ch.chapter_id));
      }

      await fetch(`${baseUrl}/v1/books/${createdBookId}/volumes/auto_create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chapters_per_volume: 30 }),
      });
      const vols = await loadVolumes(createdBookId);
      if (vols.length) setQuickVolumeId(String(vols[0].volume_id || ""));

      await loadBooks();
      await loadChapters(createdBookId);
      setStatus(`创作项目已创建：${book.title}`);
    } catch (err) {
      setStatus(`创建创作项目失败：${formatAnyError(err)}`);
    } finally {
      setWriterStudioBusy(false);
    }
  }

  async function generateVolumePlanPreview(): Promise<boolean> {
    const ready = await ensureStructureTargetsReady({ silent: true });
    if (!bookId || !ready?.volumeId) {
      setStatus("请先准备书籍、卷与章节。");
      return false;
    }
    setWriterStudioBusy(true);
    try {
      const structureHints = buildStructureHintsFromMaterialRefs(materialRefs);
      const splitbookId = String(writingSplitbookRefId || selectedSplitbookId || "").trim();
      const volumeGoal = String(masterOutline?.summary || "").trim() || storyIdea.trim() || storyTheme.trim();
      const hintCount = Number(structureHints?.total_lines || 0) || 0;
      updateStructureStepBasis("1.3.1", {
        status: "running",
        basis: `总纲摘要 + 卷信息 + AI卷纲生成${hintCount > 0 ? ` + 拆书结构(${hintCount}条)` : ""}`,
        detail: "正在生成卷纲草案",
      });
      const res = await fetch(`${baseUrl}/v1/books/${bookId}/volumes/${ready.volumeId}/plan/preview_auto`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          volume_goal: volumeGoal,
          volume_theme: storyTheme.trim(),
          target_pacing: "mid",
          material_refs: structureHints ? splitbookStructureRefBlocks.slice(0, 20) : [],
          structure_hints: structureHints || undefined,
          structure_mode: structureHints ? "structure_only" : undefined,
          splitbook_id: splitbookId || undefined,
          use_ai_refine: true,
        }),
      });
      if (!res.ok) throw new Error(`VOLUME_PLAN_PREVIEW_FAILED:${res.status}`);
      const out = await res.json();
      setVolumePlanPreview(out);
      const appliedHintCount = Number(out?.structure_hints_applied || hintCount || 0) || 0;
      const hintSources = Array.isArray(out?.structure_hint_sources)
        ? out.structure_hint_sources.map((x: any) => String(x || "").trim()).filter(Boolean)
        : [];
      updateStructureStepBasis("1.3.1", {
        status: "success",
        basis: `总纲摘要 + 卷信息 + AI卷纲生成${appliedHintCount > 0 ? ` + 结构提示(${appliedHintCount}条)` : ""}`,
        detail: hintSources.length
          ? `来源：${hintSources.slice(0, 3).join(" / ")}`
          : `节奏：${String(out?.target_pacing || "mid")}`,
      });
      if (structureHints) {
        setStatus(`卷纲草案已生成（已融合拆书结构：${structureHints.sources.join(" / ") || "已注入来源"}）`);
      } else {
        setStatus("卷纲草案已生成");
      }
      return true;
    } catch (err) {
      updateStructureStepBasis("1.3.1", {
        status: "error",
        detail: toCleanSingleLine(formatAnyError(err), 120),
      });
      setStatus(`生成卷纲草案失败：${formatAnyError(err)}`);
      return false;
    } finally {
      setWriterStudioBusy(false);
    }
  }

  async function applyVolumePlanAuto(): Promise<boolean> {
    const ready = await ensureStructureTargetsReady({ silent: true });
    if (!bookId || !ready?.volumeId) {
      setStatus("请先准备书籍、卷与章节。");
      return false;
    }
    setWriterStudioBusy(true);
    try {
      const structureHints = buildStructureHintsFromMaterialRefs(materialRefs);
      const splitbookId = String(writingSplitbookRefId || selectedSplitbookId || "").trim();
      const volumeGoal = String(masterOutline?.summary || "").trim() || storyIdea.trim() || storyTheme.trim();
      const hintCount = Number(structureHints?.total_lines || 0) || 0;
      updateStructureStepBasis("1.3.2", {
        status: "running",
        basis: `卷纲草案应用 + AI优化${volumePlanPreview?.plan ? " + 草案预览" : ""}${hintCount > 0 ? ` + 拆书结构(${hintCount}条)` : ""}`,
        detail: "正在应用卷纲",
      });
      const res = await fetch(`${baseUrl}/v1/books/${bookId}/volumes/${ready.volumeId}/plan/apply_auto`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          volume_goal: volumeGoal,
          volume_theme: storyTheme.trim(),
          target_pacing: "mid",
          plan: volumePlanPreview?.plan || undefined,
          material_refs: structureHints ? splitbookStructureRefBlocks.slice(0, 20) : [],
          structure_hints: structureHints || undefined,
          structure_mode: structureHints ? "structure_only" : undefined,
          splitbook_id: splitbookId || undefined,
          use_ai_refine: true,
        }),
      });
      if (!res.ok) throw new Error(`VOLUME_PLAN_APPLY_FAILED:${res.status}`);
      const out = await res.json();
      setVolumePlanApplied(out);
      const appliedHintCount = Number(out?.structure_hints_applied || hintCount || 0) || 0;
      updateStructureStepBasis("1.3.2", {
        status: "success",
        basis: `卷纲草案应用 + AI优化${appliedHintCount > 0 ? ` + 结构提示(${appliedHintCount}条)` : ""}`,
        detail: `版本：${Number(out?.plan?.version || out?.version || 0) || 1}`,
      });
      if (structureHints) {
        setStatus(`卷纲已应用（已融合拆书结构 ${structureHints.total_lines} 条），可继续生成章纲`);
      } else {
        setStatus("卷纲已应用，可继续生成章纲");
      }
      return true;
    } catch (err) {
      updateStructureStepBasis("1.3.2", {
        status: "error",
        detail: toCleanSingleLine(formatAnyError(err), 120),
      });
      setStatus(`应用卷纲失败：${formatAnyError(err)}`);
      return false;
    } finally {
      setWriterStudioBusy(false);
    }
  }

  async function generateChapterOutlineSeed(opts?: { chapterId?: string }): Promise<boolean> {
    const ready = await ensureStructureTargetsReady({ silent: true });
    const targetChapterId = String(opts?.chapterId || ready?.chapterId || "").trim();
    if (!targetChapterId) {
      setStatus("请先准备可用章节。");
      return false;
    }
    if (String(chapterId || "").trim() !== targetChapterId) {
      setChapterId(targetChapterId);
    }
    const chapter = chapterItems.find((x) => x.chapter_id === targetChapterId);
    const chapterTitle = chapter?.title || `第${chapter?.chapter_no || 1}章`;
    const structureHints = buildStructureHintsFromMaterialRefs(materialRefs);
    const hintCount = Number(structureHints?.total_lines || 0) || 0;
    const splitbookId = String(writingSplitbookRefId || selectedSplitbookId || "").trim();
    updateStructureStepBasis("1.4.1", {
      status: "running",
      basis: `总纲 + 卷纲 + 章节信息 + AI章纲生成${hintCount > 0 ? ` + 拆书结构(${hintCount}条)` : ""}`,
      detail: "正在生成章纲草案（AI）",
    });
    setWriterStudioBusy(true);
    try {
      const saveRes = await fetch(`${baseUrl}/v1/chapters/${targetChapterId}/outline_detail/auto_generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          force: true,
          splitbook_id: splitbookId || undefined,
          material_refs: materialRefs.slice(0, 30),
          structure_hints: structureHints || undefined,
        }),
      });
      if (!saveRes.ok) throw new Error(`CHAPTER_OUTLINE_SEED_FAILED:${saveRes.status}`);
      const out = await saveRes.json();
      const outlineSeed = (out?.outline || out?.saved?.outline_detail || null) as OutlineDetail | null;
      if (outlineSeed && Array.isArray(outlineSeed.nodes)) {
        setChapterOutlineSeed(outlineSeed);
      }
      await loadOutline("latest");
      updateStructureStepBasis("1.4.1", {
        status: "success",
        basis: `总纲 + 卷纲 + 章节信息 + AI章纲生成${hintCount > 0 ? ` + 结构提示(${hintCount}条)` : ""}`,
        detail: `章节：${chapterTitle}${splitbookId ? "；已融合拆书结构" : ""}`,
      });
      if (structureHints) {
        setStatus(`章纲草案已生成（AI+结构融合 ${structureHints.total_lines} 条），请在下方节点编辑中微调`);
      } else {
        setStatus("章纲草案已生成（AI），请在下方节点编辑中微调");
      }
      void loadChapterOutlineOverview(undefined, { silent: true });
      void loadAiDebugInfo({ silent: true });
      return true;
    } catch (err) {
      updateStructureStepBasis("1.4.1", {
        status: "error",
        detail: toCleanSingleLine(formatAnyError(err), 120),
      });
      setStatus(`生成章纲草案失败：${formatAnyError(err)}`);
      return false;
    } finally {
      setWriterStudioBusy(false);
    }
  }

  async function runStructurePipelineOneClick() {
    if (structurePipelineBusy) return;
    if (!bookId) {
      setStatus("请先准备书籍、卷与章节，再执行结构一键流程。");
      return;
    }
    const ready = await ensureStructureTargetsReady({ silent: false });
    if (!ready?.chapterId || !ready?.volumeId) return;
    if (!masterOutlineReady) {
      setStatus("请先完成并保存总纲（步骤 1.2），再执行结构一键流程。");
      return;
    }
    setStructurePipelineBusy(true);
    setStructurePipelineError("");
    setStructurePipelineStep("volume_preview");
    try {
      setStatus("结构一键流程：正在执行 1.3.1 生成卷纲草案...");
      const ok1 = await generateVolumePlanPreview();
      if (!ok1) throw new Error("STRUCTURE_STEP_1_3_1_FAILED");

      setStructurePipelineStep("volume_apply");
      setStatus("结构一键流程：正在执行 1.3.2 应用卷纲...");
      const ok2 = await applyVolumePlanAuto();
      if (!ok2) throw new Error("STRUCTURE_STEP_1_3_2_FAILED");

      setStructurePipelineStep("chapter_seed");
      setStatus("结构一键流程：正在执行 1.4.1 生成章纲草案...");
      const ok3 = await generateChapterOutlineSeed();
      if (!ok3) throw new Error("STRUCTURE_STEP_1_4_1_FAILED");

      setStructurePipelineStep("control_plan");
      setStatus("结构一键流程：正在执行 1.4.2 控制计划细化...");
      const ok4 = await runControlPlan({
        source: "写作工作台 > 1.3/1.4 结构迭代 > 一键执行 1.3→1.4",
        entry: "writing.structure.one_click.step_1_4_2",
        mode: "one_click",
      }, { chapterId: ready.chapterId });
      if (!ok4) throw new Error("STRUCTURE_STEP_1_4_2_FAILED");

      setStructurePipelineStep("done");
      setStatus("结构一键流程完成：卷纲→应用→章纲→控制计划 已全部完成。");
    } catch (err) {
      setStructurePipelineStep("failed");
      setStructurePipelineError(formatAnyError(err));
      setStatus(`结构一键流程失败：${formatAnyError(err)}`);
    } finally {
      setStructurePipelineBusy(false);
    }
  }

  async function runStructurePipelineWithSplitbookFusion() {
    if (!bookId) {
      setStatus("请先准备书籍、卷与章节，再执行结构融合流程。");
      return;
    }
    const ready = await ensureStructureTargetsReady({ silent: false });
    if (!ready?.chapterId || !ready?.volumeId) return;
    if (!writingSplitbookRefId && !selectedSplitbookId) {
      setStatus("请先在 1.4.3 选择拆书来源，再执行结构融合流程。");
      return;
    }
    const okInject = await injectSplitbookStructureRefToWriting({
      splitbookId: writingSplitbookRefId || selectedSplitbookId,
      scope: writingSplitbookRefScope,
      chapterNo: writingSplitbookRefScope === "chapter" ? writingSplitbookRefChapterNo || splitbookChapterNo : undefined,
    });
    if (!okInject) return;
      setStatus("已注入拆书结构，开始执行 1.3→1.4 结构融合流程...");
    await runStructurePipelineOneClick();
  }

  async function createBookFromLibrary() {
    if (!newBookName.trim()) return;
    const res = await fetch(`${baseUrl}/v1/books`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: newBookName.trim(),
        author: newBookAuthor.trim() || null,
        language: newBookLanguage.trim() || "zh",
        notes: newBookNotes.trim() || null,
      }),
    });
    if (!res.ok) throw new Error(`BOOK_CREATE_FAILED:${res.status}`);
    const row = (await res.json()) as BookItem;
    setNewBookName("");
    setBookId(row.book_id);
    setStatus(`书籍已创建：${row.title}`);
    await loadBooks();
    await loadChapters(row.book_id);
    await loadVolumes(row.book_id);
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
    setStatus(`章节已创建：第${row.chapter_no}章`);
    await loadChapters(bookId);
  }

  function openDataDeleteDialog(kind: DataDeleteKind, id: string, name: string, message: string) {
    setDataDeleteError("");
    setDataDeleteInputShake(false);
    setDataDeleteDialog({
      kind,
      id,
      name,
      message,
      typedName: "",
    });
  }

  function markDataDeleteMismatch() {
    setDataDeleteError("输入名称与目标不一致，请核对后重试。");
    setDataDeleteInputShake(true);
    if (dataDeleteShakeTimerRef.current) {
      window.clearTimeout(dataDeleteShakeTimerRef.current);
      dataDeleteShakeTimerRef.current = null;
    }
    dataDeleteShakeTimerRef.current = window.setTimeout(() => {
      setDataDeleteInputShake(false);
      dataDeleteShakeTimerRef.current = null;
    }, 280);
    const el = dataDeleteInputRef.current;
    if (el) {
      el.focus();
      el.select();
    }
  }

  function isDataDeleteBusy(dialog: NonNullable<typeof dataDeleteDialog>): boolean {
    if (dialog.kind === "book") return bookDeleting;
    if (dialog.kind === "chapter") return chapterDeleting;
    if (dialog.kind === "profile") return profileDeleting;
    if (dialog.kind === "settings_preset") return presetDeletingId === dialog.id;
    if (dialog.kind === "jobs_cleanup") return jobCleanupBusy;
    if (dialog.kind === "structure_template") return structureTemplateDeletingId === dialog.id;
    return templateAssetDeletingId === dialog.id;
  }

  async function executeDeleteBook(bookIdToDelete: string, bookName: string): Promise<boolean> {
    setBookDeleting(true);
    try {
      const res = await fetch(`${baseUrl}/v1/books/${encodeURIComponent(bookIdToDelete)}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await getApiErrorDetail(res);
        throw new Error(detail || `BOOK_DELETE_FAILED:${res.status}`);
      }
      const out = await res.json().catch(() => ({} as any));
      const deleted = (out as any)?.deleted || {};
      const stats = ((deleted as any)?.deleted_stats || {}) as Record<string, unknown>;
      const deletedJobs = Number((deleted as any)?.deleted_jobs || 0) || 0;
      setBookId("");
      setChapterId("");
      setQuickVolumeId("");
      setChapterItems([]);
      setVolumeItems([]);
      await loadBooks();
      const summaryParts: string[] = [];
      const chapters = Number(stats.chapters || 0) || 0;
      const volumes = Number(stats.volumes || 0) || 0;
      const outlines = Number(stats.outlines || 0) || 0;
      const chunks = Number(stats.chunks || 0) || 0;
      const textVersions = Number(stats.text_versions || 0) || 0;
      if (chapters > 0) summaryParts.push(`章节 ${chapters}`);
      if (volumes > 0) summaryParts.push(`卷 ${volumes}`);
      if (outlines > 0) summaryParts.push(`大纲 ${outlines}`);
      if (chunks > 0) summaryParts.push(`分块 ${chunks}`);
      if (textVersions > 0) summaryParts.push(`正文版本 ${textVersions}`);
      if (deletedJobs > 0) summaryParts.push(`任务 ${deletedJobs}`);
      setStatus(
        `书籍已删除：${bookName}${summaryParts.length ? `（已清理：${summaryParts.join("，")}）` : ""}`
      );
      return true;
    } catch (err) {
      setStatus(`删除书籍失败：${formatAnyError(err)}`);
      setDataDeleteError(formatAnyError(err));
      return false;
    } finally {
      setBookDeleting(false);
    }
  }

  async function executeDeleteChapter(chapterIdToDelete: string, chapterLabel: string): Promise<boolean> {
    setChapterDeleting(true);
    try {
      const res = await fetch(`${baseUrl}/v1/chapters/${chapterIdToDelete}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await getApiErrorDetail(res);
        throw new Error(detail || `CHAPTER_DELETE_FAILED:${res.status}`);
      }
      const next = chapterItems.find((c) => c.chapter_id !== chapterIdToDelete) || null;
      setChapterId(next?.chapter_id || "");
      await loadChapters(bookId);
      setStatus(`章节已删除：${chapterLabel}`);
      return true;
    } catch (err) {
      setStatus(`删除章节失败：${formatAnyError(err)}`);
      setDataDeleteError(formatAnyError(err));
      return false;
    } finally {
      setChapterDeleting(false);
    }
  }

  async function executeDeleteProfile(profileIdToDelete: string, profileName: string): Promise<boolean> {
    setProfileDeleting(true);
    try {
      const res = await fetch(`${baseUrl}/v1/profiles/${profileIdToDelete}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await getApiErrorDetail(res);
        throw new Error(detail || `PROFILE_DELETE_FAILED:${res.status}`);
      }
      setSelectedBookProfileId("");
      setProfileVersions([]);
      setProfileActiveVersion(0);
      setProfileDiffResult(null);
      setProfileVersionSnapshot(null);
      await loadProfilesList();
      if (bookId) {
        await loadBooks();
        await loadBookProfilesMeta().catch(() => {});
      }
      setStatus(`画像已删除：${profileName}`);
      return true;
    } catch (err) {
      setStatus(`删除画像失败：${formatAnyError(err)}`);
      setDataDeleteError(formatAnyError(err));
      return false;
    } finally {
      setProfileDeleting(false);
    }
  }

  async function executeDeleteTemplateAsset(assetId: string, assetName: string): Promise<boolean> {
    setTemplateAssetDeletingId(assetId);
    try {
      const res = await fetch(`${baseUrl}/v1/templates/assets/${assetId}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await getApiErrorDetail(res);
        throw new Error(detail || `TEMPLATE_ASSET_DELETE_FAILED:${res.status}`);
      }
      setTemplateItems((prev) => prev.filter((x) => x.asset_id !== assetId));
      setTemplateSelected((prev) => (prev?.asset_id === assetId ? null : prev));
      setStatus(`模板资产已删除：${assetName}`);
      return true;
    } catch (err) {
      setStatus(`删除模板资产失败：${formatAnyError(err)}`);
      setDataDeleteError(formatAnyError(err));
      return false;
    } finally {
      setTemplateAssetDeletingId("");
    }
  }

  async function executeDeleteStructureTemplate(templateId: string, templateName: string): Promise<boolean> {
    setStructureTemplateDeletingId(templateId);
    try {
      const res = await fetch(`${baseUrl}/v1/templates/${templateId}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await getApiErrorDetail(res);
        throw new Error(detail || `TEMPLATE_DELETE_FAILED:${res.status}`);
      }
      setTemplateSelected((prev) => {
        if (!prev) return prev;
        const currentId = extractStructureTemplateId(prev);
        if (!currentId || currentId !== templateId) return prev;
        return { ...prev, source_span: { ...(prev.source_span || {}), template_id: "" } };
      });
      setStatus(`底层结构模板已删除：${templateName}`);
      return true;
    } catch (err) {
      setStatus(`删除底层结构模板失败：${formatAnyError(err)}`);
      setDataDeleteError(formatAnyError(err));
      return false;
    } finally {
      setStructureTemplateDeletingId("");
    }
  }

  async function executeDeleteSettingsPreset(presetId: string, presetName: string): Promise<boolean> {
    setPresetDeletingId(presetId);
    try {
      const res = await fetch(`${baseUrl}/v1/settings/presets/${presetId}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await getApiErrorDetail(res);
        throw new Error(detail || `PRESET_DELETE_FAILED:${res.status}`);
      }
      await loadSettingsPresets();
      setStatus(`预设已删除：${presetName}`);
      return true;
    } catch (err) {
      setStatus(`删除预设失败：${formatAnyError(err)}`);
      setDataDeleteError(formatAnyError(err));
      return false;
    } finally {
      setPresetDeletingId("");
    }
  }

  async function executeCleanupJobs(cleanupId: string, cleanupName: string): Promise<boolean> {
    setJobCleanupBusy(true);
    try {
      const encoded = String(cleanupId || "").trim();
      let query = "";
      if (encoded.startsWith("status:")) {
        query = `status=${encodeURIComponent(encoded.slice("status:".length))}`;
      } else if (encoded.startsWith("statuses:")) {
        query = `statuses=${encodeURIComponent(encoded.slice("statuses:".length))}`;
      }
      const path = `${baseUrl}/v1/jobs${query ? `?${query}` : ""}`;
      const res = await fetch(path, { method: "DELETE" });
      if (!res.ok) {
        const detail = await getApiErrorDetail(res);
        throw new Error(detail || `JOB_CLEANUP_FAILED:${res.status}`);
      }
      const out = await res.json();
      const deletedCount = Number(out?.deleted_count || 0);
      await pollJobs();
      setStatus(`${cleanupName}清理完成：已删除 ${deletedCount} 条任务记录`);
      return true;
    } catch (err) {
      setStatus(`清理任务失败：${formatAnyError(err)}`);
      setDataDeleteError(formatAnyError(err));
      return false;
    } finally {
      setJobCleanupBusy(false);
    }
  }

  async function confirmDataDeleteDialog() {
    if (!dataDeleteDialog) return;
    const expectedName = String(dataDeleteDialog.name || "").trim();

    let ok = false;
    if (dataDeleteDialog.kind === "book") {
      ok = await executeDeleteBook(dataDeleteDialog.id, expectedName);
    } else if (dataDeleteDialog.kind === "chapter") {
      ok = await executeDeleteChapter(dataDeleteDialog.id, expectedName);
    } else if (dataDeleteDialog.kind === "profile") {
      ok = await executeDeleteProfile(dataDeleteDialog.id, expectedName);
    } else if (dataDeleteDialog.kind === "settings_preset") {
      ok = await executeDeleteSettingsPreset(dataDeleteDialog.id, expectedName);
    } else if (dataDeleteDialog.kind === "jobs_cleanup") {
      ok = await executeCleanupJobs(dataDeleteDialog.id, expectedName);
    } else if (dataDeleteDialog.kind === "structure_template") {
      ok = await executeDeleteStructureTemplate(dataDeleteDialog.id, expectedName);
    } else {
      ok = await executeDeleteTemplateAsset(dataDeleteDialog.id, expectedName);
    }

    if (ok) {
      setDataDeleteError("");
      setDataDeleteInputShake(false);
      setDataDeleteDialog(null);
    }
  }

  function deleteCurrentBookFromLibrary() {
    if (!bookId) return;
    const currentBook = bookItems.find((b) => b.book_id === bookId) || null;
    const bookName = String(currentBook?.title || `book:${bookId}`).trim();
    openDataDeleteDialog("book", bookId, bookName, "将同步删除该书的章节、卷纲、事实层与相关运行数据。此操作不可撤销。");
  }

  function deleteCurrentChapterFromLibrary() {
    if (!chapterId) return;
    const currentChapter = chapterItems.find((c) => c.chapter_id === chapterId) || null;
    const chapterLabel = currentChapter ? `第${currentChapter.chapter_no}章 · ${currentChapter.title}` : chapterId;
    openDataDeleteDialog("chapter", chapterId, chapterLabel, "将删除本章节的正文版本、体检记录与相关任务引用。此操作不可撤销。");
  }

  function deleteCurrentProfile() {
    if (!selectedBookProfileId) return;
    const currentProfile = profiles.find((p) => p.profile_id === selectedBookProfileId) || null;
    const profileName = String(currentProfile?.name || selectedBookProfileId).trim();
    openDataDeleteDialog("profile", selectedBookProfileId, profileName, "该画像关联的模板与版本将被删除。书籍上的引用会自动清空。此操作不可撤销。");
  }

  function deleteTemplateAssetFromLibrary(assetId: string, assetName: string) {
    if (!assetId) return;
    const label = String(assetName || assetId).trim();
    openDataDeleteDialog("template_asset", assetId, label, "删除后将无法在引用中心继续检索与复用。");
  }

  function deleteStructureTemplateFromLibrary(templateId: string, templateName: string) {
    if (!templateId) return;
    const label = String(templateName || templateId).trim();
    openDataDeleteDialog("structure_template", templateId, label, "将删除该模板资产对应的底层结构模板，且不可撤销。");
  }

  function deletePresetFromSettings(presetId: string, presetName: string) {
    if (!presetId) return;
    const label = String(presetName || presetId).trim();
    openDataDeleteDialog("settings_preset", presetId, label, "将删除该设置预设，删除后无法恢复。");
  }

  function cleanupCurrentJobTabHistory() {
    if (jobTab === "running" || jobTab === "queued") {
      setStatus("排队中/运行中任务不支持直接清理，请先中止任务。");
      return;
    }
    const label = `任务历史（${formatJobStatusLabel(jobTab)}）`;
    openDataDeleteDialog("jobs_cleanup", `status:${jobTab}`, label, `将删除当前标签页下的${formatJobStatusLabel(jobTab)}任务记录。`);
  }

  function cleanupAllFinishedJobsHistory() {
    openDataDeleteDialog(
      "jobs_cleanup",
      "statuses:succeeded,failed,canceled",
      "全部已完成任务历史",
      "将删除成功/失败/已中止的任务记录，运行中任务会被保留。"
    );
  }

  async function saveOutline(note?: string) {
    if (!outline || !chapterId) return;
    setBusy(true);
      setStatus("大纲保存中...");
    try {
      const res = await fetch(`${baseUrl}/v1/chapters/${chapterId}/outline_detail/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ outline, note: note || "manual edit" })
      });
      if (!res.ok) throw new Error(`OUTLINE_SAVE_FAILED:${res.status}`);
      setDirty(false);
      await loadOutline("latest");
      setStatus("已保存新版本");
    } catch (err) {
      setStatus(formatAnyError(err));
    } finally {
      setBusy(false);
    }
  }

  async function runEval(triggerMeta?: TriggerMetaInput) {
    if (!chapterId) return;
    const meta = triggerMeta || {
      source: "写作工作台 > 章节操作 > 张力评估",
      entry: "writing.outline_tools.eval",
      mode: "manual",
    };
    setBusy(true);
    setStatus("正在创建评估任务...");
    try {
      const evalRes = await fetch(`${baseUrl}/v1/chapters/${chapterId}/tension/eval`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chapter_version_id: "00000000-0000-0000-0000-000000000000",
          input_mode: "outline",
          schema_ver: 1,
          profile_id: selectedBookProfileId || undefined,
          ...buildTriggerMeta(meta),
        })
      });
      if (!evalRes.ok) throw new Error(`EVAL_START_FAILED:${evalRes.status}`);
      const evalJob = (await evalRes.json()) as { job_id: string };

      await waitJobDone(baseUrl, evalJob.job_id, (job) => setStatus(`评估进度：${formatPhaseLabel(job.progress?.phase)} ${job.progress?.pct || 0}%`));

      const srRes = await fetch(`${baseUrl}/v1/skill_runs/latest?chapter_id=${encodeURIComponent(chapterId)}&skill_name=EVAL_CONFLICT_TENSION_V1`);
      if (!srRes.ok) throw new Error("EVAL_RESULT_NOT_FOUND");
      const sr: SkillRun = await srRes.json();
      setEvalRun(sr);
      setStatus("评估完成");
    } catch (err) {
      setStatus(formatAnyError(err));
    } finally {
      setBusy(false);
    }
  }

  async function runControlPlan(
    triggerMeta?: TriggerMetaInput,
    opts?: { chapterId?: string }
  ): Promise<boolean> {
    let targetChapterId = String(opts?.chapterId || chapterId || "").trim();
    if (!targetChapterId) {
      const ready = await ensureStructureTargetsReady({ silent: true });
      targetChapterId = String(ready?.chapterId || "").trim();
    }
    if (!targetChapterId) {
      setStatus("控制计划执行失败：未找到可用章节。");
      return false;
    }
    updateStructureStepBasis("1.4.2", {
      status: "running",
      basis: `章纲草案 + 张力目标 + 风格参数 + 素材引用(${materialRefs.length})`,
      detail: `章节ID：${targetChapterId.slice(0, 8)}...`,
    });
    const meta = triggerMeta || {
      source: "写作工作台 > 1.3/1.4 结构迭代 > 1.4.2 控制计划细化",
      entry: "writing.structure.step_1_4_2",
      mode: "manual",
    };
    setBusy(true);
    setStatus(`正在创建控制计划任务...（结构引用 ${splitbookStructureRefCount} 条）`);
    try {
      const res = await fetch(`${baseUrl}/v1/chapters/${targetChapterId}/tension/control_plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          targets,
          style,
          schema_ver: 1,
          material_refs: materialRefs,
          profile_id: selectedBookProfileId || undefined,
          ...buildTriggerMeta(meta),
        })
      });
      if (!res.ok) throw new Error(`CONTROL_PLAN_START_FAILED:${res.status}`);
      const job = (await res.json()) as { job_id: string };

      const doneJob = await waitJobDone(baseUrl, job.job_id, (j) =>
        setStatus(`控制计划进度：${formatPhaseLabel(j.progress?.phase)} ${j.progress?.pct || 0}%`)
      );

      let sr: SkillRun | null = null;
      const skillRunId = String(doneJob?.result?.skill_run_id || "").trim();
      if (skillRunId) {
        const srByIdRes = await fetch(`${baseUrl}/v1/skill_runs/${encodeURIComponent(skillRunId)}`);
        if (srByIdRes.ok) {
          sr = (await srByIdRes.json()) as SkillRun;
        }
      }
      if (!sr) {
        const srRes = await fetch(
          `${baseUrl}/v1/skill_runs/latest?chapter_id=${encodeURIComponent(targetChapterId)}&skill_name=TENSION_CONTROL_PLAN_V1`
        );
        if (srRes.ok) {
          sr = (await srRes.json()) as SkillRun;
        }
      }
      if (!sr) {
        const fallbackPatches = Math.max(0, Number(doneJob?.result?.patches || 0) || 0);
        setPlanRun(null);
        setSelectedPatches({});
        updateStructureStepBasis("1.4.2", {
          status: "success",
          basis: `章纲草案 + 张力目标 + 风格参数 + 素材引用(${materialRefs.length})`,
          detail: `任务已完成，补丁 ${fallbackPatches} 条；结果索引稍后可见`,
        });
        setStatus(`控制计划任务已完成（补丁 ${fallbackPatches} 条），正在等待结果索引同步。`);
        return true;
      }
      setPlanRun(sr);

      const patches = (((sr.output || {}).result || {}).patches || []) as any[];
      const selected: Record<string, boolean> = {};
      for (const p of patches) {
        if (p.patch_id) selected[p.patch_id] = true;
      }
      setSelectedPatches(selected);
      updateStructureStepBasis("1.4.2", {
        status: "success",
        basis: `章纲草案 + 张力目标 + 风格参数 + 素材引用(${materialRefs.length})`,
        detail: `补丁数：${patches.length}${splitbookStructureRefCount > 0 ? `；结构引用：${splitbookStructureRefCount}条` : ""}`,
      });
      setStatus(`控制计划已就绪：${patches.length} 条补丁（结构引用 ${splitbookStructureRefCount} 条）`);
      return true;
    } catch (err) {
      updateStructureStepBasis("1.4.2", {
        status: "error",
        detail: toCleanSingleLine(formatAnyError(err), 120),
      });
      setStatus(formatAnyError(err));
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function runBookTensionAnalyze() {
    if (!bookId) return;
    setBusy(true);
    setStatus("正在创建全书张力分析任务...");
    try {
      const res = await fetch(`${baseUrl}/v1/books/${bookId}/tension/analyze`, { method: "POST" });
      if (!res.ok) throw new Error(`BOOK_ANALYZE_START_FAILED:${res.status}`);
      const job = (await res.json()) as { job_id: string };
      await waitJobDone(baseUrl, job.job_id, (j) => setStatus(`全书分析进度：${formatPhaseLabel(j.progress?.phase)} ${j.progress?.pct || 0}%`));
      await loadBookTensionReport();
      setStatus("全书张力分析完成");
    } catch (err) {
      setStatus(formatAnyError(err));
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
    setStatus(`分卷目标已保存：${arcTargetForm.arc_id}`);
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
    setStatus(`报告已导出：${data.report_id || "无"}`);
  }

  async function exportChapterRevisionPdf() {
    const data = await requestChapterRevisionReport();
    if (!data?.html) throw new Error("REPORT_HTML_EMPTY");
    const stem = `chapter-revision-${chapterId || "report"}-v${compareFrom}-v${compareTo}`;
    const out = await window.desktopApi.exportPdf(data.html, stem);
    setReportHtml(data.html);
    setReportPdfPath(out.pdfPath);
    setStatus(`PDF 已导出：${out.pdfPath}`);
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
    setStatus(`已加载最新报告：${out.report_id || "-"}`);
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
    setStatus(`已打开画像 ${profileId} v${version}`);
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
      setStatus(`已在任务中心打开技能运行：${skillRunId}`);
      window.setTimeout(() => {
        const el = document.querySelector(`[data-job-id="${found.job_id}"]`) as HTMLElement | null;
        el?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 80);
    } else {
      setStatus(`最近成功任务中未找到 skill_run：${skillRunId}`);
    }
  }

  async function applyGlobalSearchItem(item: GlobalSearchItem | undefined) {
    if (!item) return;
    if (item.type === "book") {
      setBookId(item.id);
      setChapterId("");
      setStatus(`已选择书籍：${item.title}`);
      closeGlobalSearch();
      return;
    }
    if (item.type === "chapter") {
      if (item.book_id) setBookId(item.book_id);
      setChapterId(item.id);
      setStatus(`已打开章节：${item.title}`);
      closeGlobalSearch();
      return;
    }
    if (item.type === "material") {
      setStatus(`已选择素材：${item.title}`);
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
      setStatus(`已选择书籍：${item.title}`);
      return;
    }
    if (item.type === "chapter") {
      if (item.book_id) setBookId(item.book_id);
      setChapterId(item.id);
      setStatus(`已打开章节：${item.title}`);
      return;
    }
    if (item.type === "skill_run") {
      await openSkillRunInJobs(item.id);
      return;
    }
    setStatus(`已选择素材：${item.title}`);
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
      setStatus(`模板已加载：${items.length}`);
    } catch (err) {
      setStatus(formatAnyError(err));
    } finally {
      setTemplateLoading(false);
    }
  }

  async function addTemplateAssetToRefInbox(assetId: string, note?: string, name?: string) {
    if (!chapterId) {
      setStatus("请选择章节后再加入模板引用");
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
    setStatus(`模板引用已加入：${name || assetId}`);
  }

  async function addTemplateToRefInbox() {
    if (!templateSelected?.asset_id) return;
    await addTemplateAssetToRefInbox(templateSelected.asset_id, templateNote, templateSelected.name);
  }

  async function addMaterialCardToRefInbox(cardId: string, title?: string) {
    if (!chapterId) {
      setStatus("请选择章节后再加入素材引用");
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
    setStatus(`素材引用已加入：${title || cardId}`);
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
      setStatus(`引用检索完成：${merged.length}`);
    } catch (err) {
      setStatus(formatAnyError(err));
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
    await waitJobDone(baseUrl, job.job_id, (j) => setStatus(`模板演化进度：${formatPhaseLabel(j.progress?.phase)} ${j.progress?.pct || 0}%`));
    setStatus("模板演化完成");
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
    setStatus("正在创建修复方案任务...");
    try {
      const res = await fetch(`${baseUrl}/v1/books/${bookId}/tension/repair_plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ targets, style })
      });
      if (!res.ok) throw new Error(`REPAIR_PLAN_FAILED:${res.status}`);
      const data = await res.json();
      setStatus(`修复计划已创建：${data.jobs_created} 个任务`);
      if (showJobs) await pollJobs();
    } catch (err) {
      setStatus(formatAnyError(err));
    } finally {
      setBusy(false);
    }
  }

  async function applySelectedPatches() {
    if (!chapterId || !planRun) return;
    const patchIds = Object.entries(selectedPatches).filter(([, checked]) => checked).map(([id]) => id);
    if (!patchIds.length) return;

    setBusy(true);
    setStatus("正在应用所选补丁...");
    try {
      const res = await fetch(`${baseUrl}/v1/chapters/${chapterId}/outline_detail/apply_patches`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plan_skill_run_id: planRun.skill_run_id,
          selected_patch_ids: patchIds,
          auto_eval: true,
          targets,
          style,
          ...buildTriggerMeta({
            source: "写作工作台 > 章节操作 > 应用并评测",
            entry: "writing.outline_tools.apply_measure",
            mode: "manual",
          }),
        })
      });
      if (!res.ok) throw new Error(`APPLY_PATCHES_FAILED:${res.status}`);
      const created = await res.json();
      const applyJobId = created.apply_job_id as string;
      if (applyJobId) {
        await waitJobDone(baseUrl, applyJobId, (j) => setStatus(`应用+评测进度：${formatPhaseLabel(j.progress?.phase)} ${j.progress?.pct || 0}%`));
      }
      await loadOutline("latest");
      setStatus("已应用并评测，生成新大纲版本");
    } catch (err) {
      setStatus(formatAnyError(err));
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

    const queued = await fetchJobs("queued", 200);
    const running = await fetchJobs("running", 200);
    const succeeded = await fetchJobs("succeeded", 100);
    const failed = await fetchJobs("failed", 100);
    const canceled = await fetchJobs("canceled", 100);
    const mergedAll = [...queued, ...running, ...succeeded, ...failed, ...canceled];
    refreshEmbedTelemetry(mergedAll);
    const isSplitbookJob = (j: JobItem) =>
      String(j.capability_id || "").startsWith("splitbook.") ||
      String(j.job_type || "").toUpperCase().includes("SPLITBOOK");
    const splitbookAll = mergedAll
      .filter(isSplitbookJob)
      .sort((a, b) => {
        const ta = Date.parse(String(a.updated_at || a.created_at || ""));
        const tb = Date.parse(String(b.updated_at || b.created_at || ""));
        return (Number.isFinite(tb) ? tb : 0) - (Number.isFinite(ta) ? ta : 0);
      });
    const sbActive = splitbookAll.filter((j) => isActiveJobStatus(String(j.status || "")));
    setSplitbookRunningJobs(sbActive);
    setSplitbookRecentJobs(splitbookAll.slice(0, 50));
    if (showSplitbooks) {
      await loadSplitbooks({ sync: true }).catch(() => {});
    }

    const byTab: Record<string, JobItem[]> = {
      queued,
      running: [...queued, ...running],
      succeeded,
      failed,
      canceled,
    };
    const tabItemsRaw = byTab[jobTab] || running;
    const needle = jobSkillRunFilter.trim();
    const tabItems = needle
      ? tabItemsRaw.filter((j) => extractSkillRunId(j).toLowerCase().includes(needle.toLowerCase()))
      : tabItemsRaw;
    setJobs(tabItems);

    const currentSelectedJob = selectedJobRef.current;
    if (currentSelectedJob) {
      const next = mergedAll.find((j) => j.job_id === currentSelectedJob.job_id) || null;
      if (!next) {
        setSelectedJob(null);
      } else if (!jobInspectLockRef.current) {
        setSelectedJob(next);
      }
    }

    if (!pollInitializedRef.current) {
      for (const j of [...succeeded, ...failed, ...canceled]) {
        seenJobIdsRef.current.add(j.job_id);
      }
      pollInitializedRef.current = true;
      return queued.length > 0 || running.length > 0;
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
          setStatus(`评估完成：${runId}`);
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
          setStatus(`计划完成：${runId}`);
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
            setStatus(`应用完成：大纲 v${newVersion}`);
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
        setStatus(`拆书任务完成：${formatJobTypeLabel(job.job_type, job.capability_id)}`);
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
        setStatus(`任务失败：${formatJobTypeLabel(j.job_type, j.capability_id)} · ${formatJobErrorMessage(j.error)}`);
        setSelectedJob(j);
        if (String(j.capability_id || "").startsWith("splitbook.")) {
          await loadSplitbooks().catch(() => {});
        }
      }
    }

    return queued.length > 0 || running.length > 0;
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
        const base = Math.max(2000, Number(jobPollIntervalRef.current || 5000));
        const interval = hasRunning ? base : Math.min(15000, base + 3000);
        timerRef.current = window.setTimeout(tick, interval);
      } catch {
        timerRef.current = window.setTimeout(tick, Math.max(3000, Number(jobPollIntervalRef.current || 5000)));
      }
    };
    void tick();
  }

  async function retryJob(job: JobItem) {
    if (!job.capability_id || !job.payload) return;
    setStatus(`正在重试 ${formatJobTypeLabel(job.job_type, job.capability_id)}...`);
    await createJob(baseUrl, job.capability_id, job.payload as Record<string, unknown>);
    await pollJobs();
  }

  async function resumeJob(job: JobItem, opts?: { force?: boolean }) {
    const jid = String(job.job_id || "").trim();
    if (!jid) return;
    if (jobResumeBusyId === jid) return;
    setJobResumeBusyId(jid);
    setStatus(`正在继续任务：${formatJobTypeLabel(job.job_type, job.capability_id)}...`);
    try {
      const force = !!opts?.force;
      const res = await fetch(
        `${baseUrl}/v1/jobs/${encodeURIComponent(jid)}/resume?force=${force ? "true" : "false"}`,
        {
          method: "POST",
        }
      );
      if (!res.ok) {
        const detail = await getApiErrorDetail(res);
        throw new Error(detail || `JOB_RESUME_FAILED:${res.status}`);
      }
      const out = await res.json();
      setStatus(
        `任务已继续：${formatJobTypeLabel(job.job_type, job.capability_id)} → ${formatJobStatusLabel(
          String(out?.status || "queued")
        )}`
      );
      setJobTab("running");
      await pollJobs();
    } catch (err) {
      setStatus(`继续任务失败：${formatAnyError(err)}`);
    } finally {
      setJobResumeBusyId("");
    }
  }

  async function resumeStalledJobsInView() {
    if (jobResumeBatchBusy) return;
    const stalled = jobs.filter((j) => isJobLikelyStalled(j));
    if (!stalled.length) {
      setStatus("当前列表没有疑似中断任务。");
      return;
    }
    setJobResumeBatchBusy(true);
    try {
      let okCount = 0;
      for (const job of stalled) {
        const jid = String(job.job_id || "").trim();
        if (!jid) continue;
        const res = await fetch(`${baseUrl}/v1/jobs/${encodeURIComponent(jid)}/resume?force=true`, {
          method: "POST",
        });
        if (res.ok) okCount += 1;
      }
      await pollJobs();
      setStatus(`疑似中断任务继续完成：${okCount}/${stalled.length}`);
    } catch (err) {
      setStatus(`批量继续失败：${formatAnyError(err)}`);
    } finally {
      setJobResumeBatchBusy(false);
    }
  }

  async function cancelJob(job: JobItem) {
    if (!canCancelJob(job.status)) return;
    const res = await fetch(`${baseUrl}/v1/jobs/${encodeURIComponent(job.job_id)}/cancel`, {
      method: "POST",
    });
    if (!res.ok) {
      let detail = "";
      try {
        const out = await res.json();
        detail = String(out?.detail_zh || out?.detail || out?.message || "");
      } catch {
        detail = "";
      }
      const code = detail || `JOB_CANCEL_FAILED:${res.status}`;
      throw new Error(code);
    }
    const out = await res.json();
    setStatus(`任务已中止：${formatJobTypeLabel(job.job_type, job.capability_id)} → ${formatJobStatusLabel(String(out?.status || "canceled"))}`);
    await pollJobs();
  }

  async function deleteJobRecord(job: JobItem) {
    const jid = String(job.job_id || "").trim();
    if (!jid || !canDeleteJobRecord(job.status) || jobDeleteBusyId === jid) return;
    setJobDeleteBusyId(jid);
    try {
      const res = await fetch(`${baseUrl}/v1/jobs/${encodeURIComponent(jid)}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await getApiErrorDetail(res);
        throw new Error(detail || `JOB_DELETE_FAILED:${res.status}`);
      }
      setStatus(`任务记录已删除：${formatJobTypeLabel(job.job_type, job.capability_id)} · ${jid}`);
      if (selectedJob?.job_id === jid) setSelectedJob(null);
      await pollJobs();
    } catch (err) {
      setStatus(`删除任务记录失败：${formatAnyError(err)}`);
    } finally {
      setJobDeleteBusyId("");
    }
  }

  async function openJobInCenter(job: JobItem) {
    const s = String(job.status || "").toLowerCase();
    const tab: "queued" | "running" | "succeeded" | "failed" | "canceled" =
      s === "failed" ? "failed" : s === "succeeded" ? "succeeded" : s === "canceled" ? "canceled" : s === "queued" ? "queued" : "running";
    setShowJobs(true);
    setJobTab(tab);
    setJobSkillRunFilter("");
    await pollJobs();
    setSelectedJob(job);
    setStatus(`已在中心打开任务：${job.job_id}`);
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
    setStatus("设置已保存");
  }

  async function loadScopedSettings(scope: "global" | "book" | "chapter" = settingsScope) {
    let url = `${baseUrl}/v1/settings/global`;
    if (scope === "book") {
      if (!bookId) {
        setScopedSettingsText("{}");
        setStatus("请先选择 book_id 再加载书籍范围设置");
        return;
      }
      url = `${baseUrl}/v1/books/${bookId}/settings`;
    } else if (scope === "chapter") {
      if (!chapterId) {
        setScopedSettingsText("{}");
        setStatus("请先选择 chapter_id 再加载章节范围设置");
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
    setStatus(`分层设置已保存（${settingsScope}）`);
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
    setStatus("默认模板已加载（尚未保存）");
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
    setStatus(`预设已创建：${name}`);
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
    setStatus(`预设已应用到 ${settingsScope}`);
    await loadScopedSettings(settingsScope);
    if (chapterId) await loadEffectiveSettings();
  }

  function deletePreset(presetId: string, presetName: string) {
    deletePresetFromSettings(presetId, presetName);
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
    setStatus(`回滚成功：${auditId}`);
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
    setStatus(`${endpoint} 已完成`);
    await checkHealth();
  }

  async function quickStartSidecar() {
    try {
      const out = await window.desktopApi.sidecarStart();
      const b = String(out?.baseUrl || "").trim();
      if (b) setBaseUrl(b);
      const h = await window.desktopApi.sidecarHealth();
      if (h?.body && typeof h.body === "object") setHealth(h.body);
      setStatus(`Sidecar 已启动：${b || "-"}`);
    } catch (err: any) {
      setStatus(formatAnyError(err));
    }
  }

  async function quickDraftRun() {
    if (!bookId || !chapterId) {
      setStatus("快速草稿运行需要 book_id + chapter_id");
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
      setStatus(`快速草稿运行完成：${String(out?.run_id || "-")}`);
    } catch (err: any) {
      setStatus(formatAnyError(err));
    }
  }

  async function quickLoadVersions(opts?: { silent?: boolean }) {
    if (!chapterId) {
      if (!opts?.silent) setStatus("快速版本需要 chapter_id");
      return null;
    }
    try {
      const out = await window.desktopApi.draftListVersions({ chapter_id: chapterId });
      setQuickVersionsOut(out || {});
      const n = Array.isArray(out?.items) ? out.items.length : 0;
      if (!opts?.silent) setStatus(`快速版本已加载：${n}`);
      return out || {};
    } catch (err: any) {
      if (!opts?.silent) setStatus(formatAnyError(err));
      return null;
    }
  }

  async function quickSelectLatest(itemsOverride?: any[]) {
    if (!chapterId) {
      setStatus("快速选择需要 chapter_id");
      return false;
    }
    const items = Array.isArray(itemsOverride) ? itemsOverride : Array.isArray(quickVersionsOut?.items) ? quickVersionsOut.items : [];
    const first = items[0];
    const draftId = String(first?.draft_id || "").trim();
    if (!draftId) {
      setStatus("暂无可选择的草稿版本");
      return false;
    }
    try {
      const out = await window.desktopApi.draftSelect({
        chapter_id: chapterId,
        draft_id: draftId,
        selected_by: "user",
        reason: "quick select latest",
      });
      setQuickVersionsOut((m: any) => ({ ...(m || {}), selected: out || {} }));
      setQuickDraftConfirmAt(new Date().toLocaleString());
      if (showJobs && bookId) {
        void loadDraftConfirmations(bookId, { silent: true });
      }
      setStatus(`快速选择完成：${draftId}`);
      return true;
    } catch (err: any) {
      setStatus(formatAnyError(err));
      return false;
    }
  }

  async function quickConfirmLatestDraftFlow() {
    if (quickDraftConfirmBusy) return false;
    setQuickDraftConfirmBusy(true);
    try {
      const loaded = await quickLoadVersions();
      const items = Array.isArray(loaded?.items) ? loaded.items : [];
      if (!items.length) {
        setStatus("未找到可确认的草稿版本，请先执行正文生成。");
        return false;
      }
      return await quickSelectLatest(items);
    } finally {
      setQuickDraftConfirmBusy(false);
    }
  }

  async function quickPublishPack() {
    if (!bookId || !quickVolumeId.trim()) {
      setStatus("快速发布需要 book_id + volume_id");
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
      setStatus(`快速发布完成：${outputDir || "-"}`);
    } catch (err: any) {
      setStatus(formatAnyError(err));
    }
  }

  async function loadDraftVersionsWithRetry(targetChapterId: string, attempts = 6, delayMs = 700) {
    let lastOut: any = null;
    let lastErr: any = null;
    for (let i = 0; i < attempts; i += 1) {
      try {
        const out = await window.desktopApi.draftListVersions({ chapter_id: targetChapterId });
        lastOut = out || {};
        const items = Array.isArray(out?.items) ? out.items : [];
        if (items.length > 0) return out || {};
      } catch (err) {
        lastErr = err;
      }
      if (i < attempts - 1) {
        await new Promise((resolve) => window.setTimeout(resolve, delayMs));
      }
    }
    if (lastErr && !lastOut) throw lastErr;
    return lastOut || {};
  }

  async function quickRunAll() {
    if (quickPipelineBusy) return;
    if (!bookId || !chapterId || !quickVolumeId.trim()) {
      setStatus("一键流程需要 book_id + chapter_id + volume_id");
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
      const resolvedChapterId = String(draftOut?.output?.commit_result?.chapter_id || "").trim();
      const draftChapterId = resolvedChapterId || chapterId;
      if (resolvedChapterId && resolvedChapterId !== chapterId) setChapterId(resolvedChapterId);
      setQuickPipelineSteps((m) => ({ ...m, draft: "ok", versions: "running" }));

      const listOut = await loadDraftVersionsWithRetry(draftChapterId);
      setQuickVersionsOut(listOut || {});
      const versions = Array.isArray(listOut?.items) ? listOut.items : [];
      setQuickPipelineSteps((m) => ({ ...m, versions: "ok", select: "running" }));

      const latestDraftId = String(versions[0]?.draft_id || "").trim();
      if (!latestDraftId) throw new Error("ONECLICK_NO_DRAFT_VERSION");
      await window.desktopApi.draftSelect({
        chapter_id: draftChapterId,
        draft_id: latestDraftId,
        selected_by: "user",
        reason: "one-click select latest",
      });
      if (bookId) {
        void loadDraftConfirmations(bookId, { silent: true });
      }
      setQuickPipelineSteps((m) => ({ ...m, select: "ok", publish: "running" }));

      const packOut = await window.desktopApi.exportPublishPack({
        book_id: bookId,
        volume_id: quickVolumeId.trim(),
      });
      setQuickPublishOut(packOut || {});
      const outputDir = String(packOut?.output_dir || "").trim();
      if (outputDir) await window.desktopApi.openPath(outputDir, true);
      setQuickPipelineSteps((m) => ({ ...m, publish: "ok" }));
      setStatus("一键流程完成");
    } catch (err: any) {
      const msg = formatAnyError(err);
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
        setQuickPipelineError({ step: failedStep || "未知(unknown)", message: msg });
        return next;
      });
    } finally {
      setQuickPipelineBusy(false);
    }
  }

  async function quickRunSmart() {
    if (quickPipelineBusy) return;
    if (!bookId || !chapterId || !quickVolumeId.trim()) {
      setStatus("智能运行需要 book_id + chapter_id + volume_id");
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
      const resolvedChapterId = String(draftOut?.output?.commit_result?.chapter_id || "").trim();
      const draftChapterId = resolvedChapterId || chapterId;
      if (resolvedChapterId && resolvedChapterId !== chapterId) setChapterId(resolvedChapterId);
      if (quickRunMode === "manual_gate") {
        setQuickPipelineSteps((m) => ({ ...m, draft: "ok" }));
        setStatus("智能运行已完成到草稿。后续请人工执行版本/选稿/发布。");
        return;
      }

      setQuickPipelineSteps((m) => ({ ...m, draft: "ok", versions: "running" }));
      const listOut = await loadDraftVersionsWithRetry(draftChapterId);
      setQuickVersionsOut(listOut || {});
      setQuickPipelineSteps((m) => ({ ...m, versions: "ok", select: runAutoSelectLatest ? "running" : "ok" }));

      if (runAutoSelectLatest) {
        const versions = Array.isArray(listOut?.items) ? listOut.items : [];
        const latestDraftId = String(versions[0]?.draft_id || "").trim();
        if (!latestDraftId) throw new Error("SMARTRUN_NO_DRAFT_VERSION");
        await window.desktopApi.draftSelect({
          chapter_id: draftChapterId,
          draft_id: latestDraftId,
          selected_by: "user",
          reason: "smart-run select latest",
        });
        if (bookId) {
          void loadDraftConfirmations(bookId, { silent: true });
        }
      }

      if (!runAutoPublish) {
        setQuickPipelineSteps((m) => ({ ...m, select: "ok", publish: "idle" }));
        setStatus("智能运行已到选稿，发布留给人工。");
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
        setStatus("智能运行完成");
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
        setStatus("智能运行完成（自动修复后重试发布成功）");
      }
    } catch (err: any) {
      const msg = formatAnyError(err);
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
        setQuickPipelineError({ step: failedStep || "未知(unknown)", message: msg });
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

  function progressFromStepStatus(status: string): number {
    const s = String(status || "idle").toLowerCase();
    if (s === "ok" || s === "done" || s === "succeeded") return 1;
    if (s === "running") return 0.55;
    if (s === "failed" || s === "canceled" || s === "cancelled") return 0.15;
    return 0;
  }

  function progressFromStepMap(stepMap: Record<string, string>, order: string[]): number {
    if (!order.length) return 0;
    const total = order.reduce((acc, key) => acc + progressFromStepStatus(stepMap[key]), 0);
    return Math.max(0, Math.min(100, Math.round((total / order.length) * 100)));
  }

  function progressFromSplitbookPipelineStep(step: string): number {
    const s = String(step || "idle");
    const map: Record<string, number> = {
      idle: 0,
      ingest: 16,
      embed: 36,
      extract_structured: 58,
      build_templates: 78,
      build_profile: 92,
      writeback_batch: 96,
      done: 100,
      failed: 12,
    };
    return map[s] ?? 0;
  }

  function splitbookStepFromCapability(
    capabilityId: string
  ): "idle" | "ingest" | "embed" | "extract_structured" | "build_templates" | "build_profile" | "writeback_batch" {
    const cap = String(capabilityId || "").trim().toLowerCase();
    if (cap === "splitbook.ingest.v1") return "ingest";
    if (cap === "splitbook.embed.v1") return "embed";
    if (cap === "splitbook.extract_structured.v1") return "extract_structured";
    if (cap === "splitbook.build_templates.v1") return "build_templates";
    if (cap === "splitbook.build_profile.v1") return "build_profile";
    if (cap === "splitbook.writeback_batch.v1") return "writeback_batch";
    return "idle";
  }

  function progressFromSplitbookLiveJob(step: string, pct: number): number {
    const p = Math.max(0, Math.min(100, Math.round(Number(pct) || 0)));
    if (step === "ingest") return Math.max(6, Math.min(34, Math.round(6 + p * 0.28)));
    if (step === "embed") return Math.max(35, Math.min(57, Math.round(35 + p * 0.22)));
    if (step === "extract_structured") return Math.max(58, Math.min(77, Math.round(58 + p * 0.19)));
    if (step === "build_templates") return Math.max(78, Math.min(91, Math.round(78 + p * 0.13)));
    if (step === "build_profile") return Math.max(92, Math.min(99, Math.round(92 + p * 0.07)));
    if (step === "writeback_batch") return Math.max(94, Math.min(99, Math.round(94 + p * 0.05)));
    return progressFromSplitbookPipelineStep(step);
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
    setStatus(`未知失败步骤：${step}`);
  }

  async function quickFixwizardPlanForPublish() {
    if (!bookId || !quickVolumeId.trim()) {
      setStatus("修复向导需要 book_id + volume_id");
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
      setStatus(`修复方案已就绪：${n} 项`);
    } catch (err: any) {
      setStatus(formatAnyError(err));
    }
  }

  async function quickFixwizardExecuteTop(topN: number) {
    if (!bookId || !quickVolumeId.trim()) {
      setStatus("执行修复需要 book_id + volume_id");
      return;
    }
    const fixes = Array.isArray(quickFixPreview?.fixes) ? quickFixPreview.fixes : [];
    if (fixes.length === 0) {
      setStatus("暂无可执行修复。");
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
      setStatus(formatAnyError(err));
    }
  }

  async function quickFixwizardExecuteLowRisk(maxN: number) {
    if (!bookId || !quickVolumeId.trim()) {
      setStatus("执行修复需要 book_id + volume_id");
      return;
    }
    const fixes = Array.isArray(quickFixPreview?.fixes) ? quickFixPreview.fixes : [];
    const lowOnly = fixes.filter((x: any) => String(x?.risk || "").toLowerCase() === "low").slice(0, Math.max(1, maxN));
    if (lowOnly.length === 0) {
      setStatus("暂无低风险修复。");
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
      setStatus(formatAnyError(err));
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
    "ui.capability_chain.retry_max",
    "ui.capability_chain.retry_base_ms",
    "ui.delete_confirm.mismatch_beep",
    "ui.delete_confirm.mismatch_beep_level",
  ];

  function overrideScopedKey(keypath: string, value: any) {
    const updated = setPath(scopedSettingsObj || {}, keypath, value);
    setScopedSettingsObj(updated);
    setScopedSettingsText(JSON.stringify(updated, null, 2));
    setScopedSettingsParseError("");
    setStatus(`已覆盖 ${keypath} 到 ${settingsScope}（尚未保存）`);
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
    if (showJobs && jobAutoPauseOnInspect && jobInspectingDetail) {
      stopPolling();
      return;
    }
    void pollJobs();
    if (!jobAutoRefreshEnabled) {
      stopPolling();
      return;
    }
    startPolling();
    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showJobs, showSplitbooks, jobTab, baseUrl, jobSkillRunFilter, jobAutoRefreshEnabled, jobPollIntervalMs, jobAutoPauseOnInspect, jobInspectingDetail]);

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
    if (!showJobs) return;
    if (!bookId) {
      setDraftConfirmTasks([]);
      setDraftConfirmSummary(null);
      return;
    }
    void loadDraftConfirmations(bookId, { silent: true });
  }, [showJobs, bookId, baseUrl]);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem("splitbook.outputDir") || "";
      if (saved) {
        setSplitbookOutputDir(saved);
        void verifySplitbookOutputDir(saved, { silent: true });
      }
    } catch {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    setSplitbookPipelineStep("idle");
    setSplitbookPipelineError("");
    setSplitbookLedgerRows([]);
    setSplitbookLedgerSummary(null);
    setSplitbookOutlinePreview(null);
    setSplitbookChapterPack(null);
    setSplitbookHealthReport(null);
    setSplitbookAntiCopyReport(null);
    setSplitbookLibraryResult(null);
    if (selectedSplitbookId) {
      void loadSplitbookLedger().catch(() => {});
      void loadSplitbookOutlinePreview({ silent: true }).catch(() => {});
      void loadSplitbookChapterPack(undefined, { silent: true }).catch(() => {});
    }
  }, [selectedSplitbookId]);

  useEffect(() => {
    if (!splitbooks.length) {
      setWritingSplitbookRefId("");
      return;
    }
    if (writingSplitbookRefId && splitbooks.some((sb) => sb.splitbook_id === writingSplitbookRefId)) return;
    if (selectedSplitbookId && splitbooks.some((sb) => sb.splitbook_id === selectedSplitbookId)) {
      setWritingSplitbookRefId(selectedSplitbookId);
      return;
    }
    setWritingSplitbookRefId(splitbooks[0].splitbook_id);
  }, [splitbooks, selectedSplitbookId, writingSplitbookRefId]);

  useEffect(() => {
    const row = chapterItems.find((x) => x.chapter_id === chapterId);
    const chapterNo = Number(row?.chapter_no || 0);
    if (!Number.isFinite(chapterNo) || chapterNo <= 0) return;
    setWritingSplitbookRefChapterNo(chapterNo);
  }, [chapterItems, chapterId]);

  useEffect(() => {
    if (!splitbookIngestDialog) {
      setSplitbookIngestConfirmError("");
      setSplitbookIngestInputShake(false);
      return;
    }
    setSplitbookIngestConfirmError("");
    setSplitbookIngestInputShake(false);
    const timer = window.setTimeout(() => {
      const el = splitbookIngestInputRef.current;
      if (el) {
        el.focus();
        el.select();
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [splitbookIngestDialog]);

  useEffect(() => {
    if (!splitbookDeleteDialog) {
      setSplitbookDeleteError("");
      setSplitbookDeleteInputShake(false);
      return;
    }
    setSplitbookDeleteError("");
    setSplitbookDeleteInputShake(false);
    const timer = window.setTimeout(() => {
      const el = splitbookDeleteInputRef.current;
      if (el) {
        el.focus();
        el.select();
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [splitbookDeleteDialog]);

  useEffect(() => {
    if (!dataDeleteDialog) {
      setDataDeleteError("");
      setDataDeleteInputShake(false);
      return;
    }
    setDataDeleteError("");
    setDataDeleteInputShake(false);
    const timer = window.setTimeout(() => {
      const el = dataDeleteInputRef.current;
      if (el) {
        el.focus();
        el.select();
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [dataDeleteDialog]);

  useEffect(() => {
    return () => {
      resolveSplitbookIngestConfirm(false);
      if (splitbookIngestShakeTimerRef.current) {
        window.clearTimeout(splitbookIngestShakeTimerRef.current);
        splitbookIngestShakeTimerRef.current = null;
      }
      if (splitbookDeleteShakeTimerRef.current) {
        window.clearTimeout(splitbookDeleteShakeTimerRef.current);
        splitbookDeleteShakeTimerRef.current = null;
      }
      if (dataDeleteShakeTimerRef.current) {
        window.clearTimeout(dataDeleteShakeTimerRef.current);
        dataDeleteShakeTimerRef.current = null;
      }
    };
  }, []);

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
    if (!chapterId) {
      void refreshOutlineInjectionStatus("");
      return;
    }
    void loadOutline("latest");
    if (bookId) {
      void loadAiDebugInfo({ silent: true }).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapterId, bookId]);

  useEffect(() => {
    if (bookId) {
      void loadArcTargets().catch(() => {});
      void loadVariants().catch(() => {});
      void loadVolumes(bookId).catch(() => {});
      void loadBookWorkspace(bookId).catch(() => {});
      void loadWritingBrief(bookId).catch(() => {});
      void loadLatestStyleEvolution(bookId).catch(() => {});
      void loadAiDebugInfo({ silent: true }).catch(() => {});
    } else {
      setVolumeItems([]);
      setQuickVolumeId("");
      setVolumePlanPreview(null);
      setVolumePlanApplied(null);
      setChapterOutlineSeed(null);
      setAiDebugData(null);
      setAiDebugError("");
      setNewBookWorkspacePath("");
      setStoryGenre("");
      setStoryTheme("");
      setStoryTone("");
      setStoryAudience("");
        setStoryIdea("");
        setStorySetting("");
        setMasterOutline(null);
        setMasterOutlineAiMeta(null);
        setMasterOutlineSummary("");
        setMasterOutlinePlannedChapters(0);
        setStructureStepBasis({
          "1.3.1": { status: "idle", basis: "待执行", detail: "", updatedAt: "" },
          "1.3.2": { status: "idle", basis: "待执行", detail: "", updatedAt: "" },
          "1.4.1": { status: "idle", basis: "待执行", detail: "", updatedAt: "" },
          "1.4.2": { status: "idle", basis: "待执行", detail: "", updatedAt: "" },
        });
        setChapterGenerationTrace({
          status: "idle",
          mode: "single",
          basis: "待执行",
          chapters: "",
          chapterIds: [],
          detail: "",
          updatedAt: "",
        });
        setStyleEvolutionLatest(null);
        setStyleEvolutionOutput(null);
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
    void loadProfileVersions(selectedBookProfileId).catch((err) => setStatus(formatAnyError(err)));
  }, [showSettings, selectedBookProfileId]);

  useEffect(() => {
    if (!showSettings) return;
    if (!bookId) {
      setBookProfileMeta(null);
      return;
    }
    void loadBookProfilesMeta().catch((err) => setStatus(formatAnyError(err)));
  }, [showSettings, bookId]);

  useEffect(() => {
    if (!abBatchId) return;
    void loadAbBatch(abBatchId).catch((err) => setStatus(formatAnyError(err)));
    const t = window.setInterval(() => {
      void loadAbBatch(abBatchId).catch(() => {});
    }, 2000);
    return () => window.clearInterval(t);
  }, [abBatchId]);

  useEffect(() => {
    if (!showSettings || !chapterId) return;
    void loadChapterReports().catch((err) => setStatus(formatAnyError(err)));
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
    const controller = new AbortController();
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setSearchLoading(true);
      try {
        const res = await fetch(`${baseUrl}/v1/search?q=${encodeURIComponent(q)}&limit=20`, { signal: controller.signal });
        if (!res.ok) throw new Error(`SEARCH_FAILED:${res.status}`);
        const data = await res.json();
        if (cancelled) return;
        setSearchItems((data.items || []) as GlobalSearchItem[]);
        setSearchSelectedIndex(0);
      } catch (err: any) {
        if (cancelled || err?.name === "AbortError") return;
        setStatus(formatAnyError(err));
      } finally {
        if (!cancelled) setSearchLoading(false);
      }
    }, 250);
    return () => {
      cancelled = true;
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [searchOpen, searchQuery, baseUrl]);

  useEffect(() => {
    const q = librarySearchQuery.trim();
    if (!q) {
      setLibrarySearchItems([]);
      setLibrarySearchLoading(false);
      return;
    }
    const controller = new AbortController();
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setLibrarySearchLoading(true);
      try {
        const res = await fetch(`${baseUrl}/v1/search?q=${encodeURIComponent(q)}&limit=20`, { signal: controller.signal });
        if (!res.ok) throw new Error(`SEARCH_FAILED:${res.status}`);
        const data = await res.json();
        if (cancelled) return;
        setLibrarySearchItems((data.items || []) as GlobalSearchItem[]);
      } catch (err: any) {
        if (cancelled || err?.name === "AbortError") return;
        setStatus(formatAnyError(err));
      } finally {
        if (!cancelled) setLibrarySearchLoading(false);
      }
    }, 250);
    return () => {
      cancelled = true;
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [librarySearchQuery, baseUrl]);

  const patches = (((planRun?.output || {}).result || {}).patches || []) as any[];
  const issues = (((evalRun?.output || {}).result || {}).issues || []) as any[];
  const evalIssueViews = issues.map((it) => formatEvalIssueView(it));
  const splitbookStructureRefBlocks = materialRefs.filter((block) => String(block || "").includes("[拆书结构引用]"));
  const splitbookStructureRefCount = splitbookStructureRefBlocks.length;
  const splitbookStructureRefSourceList = (() => {
    const sourceSet = new Set<string>();
    for (const block of splitbookStructureRefBlocks) {
      const match = String(block || "").match(/source_splitbook_name=([^\n\r]+)/i);
      const name = toCleanSingleLine(match?.[1] || "", 36);
      if (name) sourceSet.add(name);
    }
    return Array.from(sourceSet).slice(0, 6);
  })();
  const splitbookStructureRefModeText = splitbookStructureRefCount > 0 ? "结构模式（防抄袭）已启用" : "未注入拆书结构引用";
  const report = bookTensionReport?.result || {};
  const fatigueZones = report?.book_trends?.fatigue_zones || [];
  const arcSummary = report?.arc_summary || [];
  const diagnosis = report?.diagnosis || [];
  const advanced = report?.advanced || {};
  const arcTargetAnalysis = report?.arc_targets || [];
  const activeProvider = ((settingsData?.ai_provider || "ollama") as ProviderId);
  const activeProviderConfig = getProviderConfig(settingsData, activeProvider);
  const selectedBookItem = bookItems.find((x) => x.book_id === bookId) || null;
  const selectedChapterItem = chapterItems.find((x) => x.chapter_id === chapterId) || null;
  const selectedVolumeItem = volumeItems.find((x) => String(x?.volume_id || "") === String(quickVolumeId || "")) || null;
  const latestStyleVersion = Number(
    (styleEvolutionLatest?.output || {})?.result?.profile_version_after
      ?? (styleEvolutionLatest?.output || {})?.result?.profile_version
      ?? 0
  );
  const latestStyleRunAt = String(styleEvolutionLatest?.created_at || styleEvolutionLatest?.output?.generated_at || "");
  const styleEvolutionStatusText = styleEvolutionBusy
    ? "进行中"
    : styleEvolutionLatest
      ? `已执行（v${latestStyleVersion || "-"}）`
      : "未执行";
  const showWritingWorkspace = workspaceMode !== "splitbook";
  const showSplitbookWorkspace = workspaceMode !== "writing";
  const writingBriefFilledCount = [storyGenre, storyTheme, storyTone, storyAudience, storyIdea, storySetting]
    .map((v) => String(v || "").trim())
    .filter(Boolean).length;
  const quickVersionItems = Array.isArray(quickVersionsOut?.items) ? quickVersionsOut.items : [];
  const quickSelectedDraftId = (() => {
    const selectedFromResult = String(quickVersionsOut?.selected?.selected_draft_id || "").trim();
    if (selectedFromResult) return selectedFromResult;
    const selectedFromList = quickVersionItems.find((it: any) => Boolean(it?.is_selected || it?.is_active));
    return String(selectedFromList?.draft_id || quickVersionsOut?.active_draft_id || "").trim();
  })();
  const quickSelectedDraftBranch = (() => {
    const branchFromResult = String(quickVersionsOut?.selected?.selected_branch || "").trim();
    if (branchFromResult) return branchFromResult;
    const selectedFromList = quickVersionItems.find((it: any) => String(it?.draft_id || "").trim() === quickSelectedDraftId);
    return String(selectedFromList?.branch || "").trim();
  })();
  const quickSelectedDraftAt = (() => {
    const selectedAt = String(quickVersionsOut?.selected?.selected_at || "").trim();
    if (selectedAt) return selectedAt;
    return quickDraftConfirmAt;
  })();
  const selectedSplitbook = splitbooks.find((x) => x.splitbook_id === selectedSplitbookId) || null;
  const selectedSplitbookChapterTotal = Number(selectedSplitbook?.stats?.chapter_total || 0);
  const selectedSplitbookChunkTotal = Number(selectedSplitbook?.stats?.chunks_total || 0);
  const splitbookSingleChapterLikely = selectedSplitbookChapterTotal <= 1 && selectedSplitbookChunkTotal >= 128;
  const splitbookWritebackPreviewToken = String(splitbookWritebackBatchPreview?.preview_token || "").trim();
  const splitbookWritebackPreviewChangedTotal = Number(splitbookWritebackBatchPreview?.changed_total || 0);
  const selectedSplitbookJobs = splitbookRecentJobs.filter((j) => {
    const sid = String((j.payload as any)?.splitbook_id || "");
    return sid && sid === selectedSplitbookId;
  });
  const splitbookLatestJobByCapability = (() => {
    const out: Record<string, JobItem> = {};
    const sorted = [...selectedSplitbookJobs].sort((a, b) => {
      const ta = Date.parse(String(a.updated_at || a.created_at || ""));
      const tb = Date.parse(String(b.updated_at || b.created_at || ""));
      return (Number.isFinite(tb) ? tb : 0) - (Number.isFinite(ta) ? ta : 0);
    });
    for (const job of sorted) {
      const cap = String(job.capability_id || "").toLowerCase();
      if (!cap || out[cap]) continue;
      out[cap] = job;
    }
    return out;
  })();
  const selectedSplitbookIngestStatus = String(selectedSplitbook?.ingest_status || "").trim().toLowerCase();
  const selectedSplitbookEmbedStatus = String(selectedSplitbook?.embed_status || "").trim().toLowerCase();
  const selectedSplitbookIngestActiveJobRaw =
    selectedSplitbookJobs.find(
      (j) =>
        String(j.capability_id || "").toLowerCase() === "splitbook.ingest.v1" && isActiveJobStatus(String(j.status || ""))
    ) || null;
  const selectedSplitbookEmbedActiveJobRaw =
    selectedSplitbookJobs.find(
      (j) =>
        String(j.capability_id || "").toLowerCase() === "splitbook.embed.v1" && isActiveJobStatus(String(j.status || ""))
    ) || null;
  const selectedSplitbookEmbedActiveByStatsRaw = (() => {
    const s = String(selectedSplitbook?.stats?.active_embed_job_status || "").trim().toLowerCase();
    return s === "queued" || s === "running";
  })();
  const splitbookIngestDoneActiveConflict = selectedSplitbookIngestStatus === "done" && !!selectedSplitbookIngestActiveJobRaw;
  const splitbookEmbedDoneActiveConflict =
    selectedSplitbookEmbedStatus === "done" && (!!selectedSplitbookEmbedActiveJobRaw || selectedSplitbookEmbedActiveByStatsRaw);
  const selectedSplitbookActiveJobs = selectedSplitbookJobs.filter((j) => {
    if (!isActiveJobStatus(String(j.status || ""))) return false;
    const cap = String(j.capability_id || "").trim().toLowerCase();
    if (cap === "splitbook.ingest.v1" && selectedSplitbookIngestStatus === "done") return false;
    if (cap === "splitbook.embed.v1" && selectedSplitbookEmbedStatus === "done") return false;
    return true;
  });
  const selectedSplitbookRunningCount = selectedSplitbookActiveJobs.length;
  const selectedSplitbookQueuedCount = selectedSplitbookActiveJobs.filter(
    (j) => String(j.status || "").toLowerCase() === "queued"
  ).length;
  const selectedSplitbookLatestActiveJob =
    selectedSplitbookActiveJobs
      .slice()
      .sort((a, b) => {
        const ta = Date.parse(String(a.updated_at || a.created_at || ""));
        const tb = Date.parse(String(b.updated_at || b.created_at || ""));
        return (Number.isFinite(tb) ? tb : 0) - (Number.isFinite(ta) ? ta : 0);
      })[0] || null;
  const selectedSplitbookEmbedActiveJob =
    selectedSplitbookActiveJobs.find((j) => String(j.capability_id || "").toLowerCase() === "splitbook.embed.v1") || null;
  const selectedSplitbookActiveCaps = new Set(
    selectedSplitbookActiveJobs.map((j) => String(j.capability_id || "").toLowerCase()).filter(Boolean)
  );
  const selectedSplitbookEmbedActiveByStats = (() => {
    if (selectedSplitbookEmbedStatus === "done") return false;
    return selectedSplitbookEmbedActiveByStatsRaw;
  })();
  const selectedSplitbookEmbedProgressPct = (() => {
    if (selectedSplitbookEmbedActiveJob) {
      const pctRaw = Number((selectedSplitbookEmbedActiveJob.progress as any)?.pct ?? (selectedSplitbookEmbedActiveJob.progress_value || 0) * 100);
      if (Number.isFinite(pctRaw)) return Math.max(0, Math.min(100, Math.round(pctRaw)));
    }
    const statsPct = Number(selectedSplitbook?.stats?.embed_progress_pct ?? NaN);
    if (Number.isFinite(statsPct)) return Math.max(0, Math.min(100, Math.round(statsPct)));
    const embedded = Number(selectedSplitbook?.stats?.embedded_total || 0);
    const chunks = Number(selectedSplitbook?.stats?.chunks_total || 0);
    if (chunks > 0) return Math.max(0, Math.min(100, Math.round((embedded / chunks) * 100)));
    return 0;
  })();
  const selectedSplitbookRecoverHint = String(selectedSplitbook?.stats?.recover_hint || "").trim().toLowerCase();
  const selectedSplitbookLiveStep = splitbookPipelineBusy
    ? splitbookPipelineStep
    : selectedSplitbookLatestActiveJob
      ? splitbookStepFromCapability(String(selectedSplitbookLatestActiveJob.capability_id || ""))
      : selectedSplitbookIngestStatus !== "done"
        ? "ingest"
        : selectedSplitbookEmbedStatus !== "done"
          ? "embed"
          : Number(selectedSplitbook?.stats?.fact_total || 0) > 0
            ? "build_templates"
            : "extract_structured";
  const selectedSplitbookLiveJobPct = selectedSplitbookLatestActiveJob
    ? Math.max(
        0,
        Math.min(
          100,
          Math.round(
            Number((selectedSplitbookLatestActiveJob.progress as any)?.pct ?? (selectedSplitbookLatestActiveJob.progress_value || 0) * 100)
          )
        )
      )
    : selectedSplitbookEmbedProgressPct;
  const selectedSplitbookLivePhase = selectedSplitbookLatestActiveJob
    ? String(
        (selectedSplitbookLatestActiveJob.progress as any)?.phase ||
          selectedSplitbookLatestActiveJob.stage ||
          selectedSplitbookLatestActiveJob.status ||
          ""
      )
    : "";
  const selectedSplitbookLiveProgressPctRaw = splitbookPipelineBusy
    ? progressFromSplitbookPipelineStep(splitbookPipelineStep)
    : selectedSplitbookLatestActiveJob
      ? progressFromSplitbookLiveJob(selectedSplitbookLiveStep, selectedSplitbookLiveJobPct)
      : null;
  const splitbookCanResumeEmbed =
    !!selectedSplitbook &&
    String(selectedSplitbook.ingest_status || "").toLowerCase() === "done" &&
    ["pending", "failed", "canceled"].includes(String(selectedSplitbook.embed_status || "").toLowerCase()) &&
    !selectedSplitbookEmbedActiveJob &&
    !selectedSplitbookEmbedActiveByStats;
  const selectedSplitbookSucceededCaps = new Set(
    selectedSplitbookJobs
      .filter((j) => {
        const st = String(j.status || "").toLowerCase();
        return st === "succeeded" || st === "done";
      })
      .map((j) => String(j.capability_id || ""))
      .filter(Boolean)
  );
  const splitbookTemplatesDone = selectedSplitbookSucceededCaps.has("splitbook.build_templates.v1");
  const splitbookProfileDone = selectedSplitbookSucceededCaps.has("splitbook.build_profile.v1");
  const splitbookStructuredDone =
    selectedSplitbookSucceededCaps.has("splitbook.extract_structured.v1") || Number(selectedSplitbook?.stats?.fact_total || 0) > 0;
  const splitbookPathReady = !!splitbookPathCheck?.ok;
  const splitbookCoreDone = selectedSplitbookIngestStatus === "done" && selectedSplitbookEmbedStatus === "done";
  const splitbookStep3BlockedByRunning = splitbookPipelineBusy || selectedSplitbookRunningCount > 0 || selectedSplitbookEmbedActiveByStats;
  const splitbookCanRunIngestStep = !!selectedSplitbookId && !!splitbookPathReady && !splitbookStep3BlockedByRunning;
  const splitbookCanRunEmbedStep =
    !!selectedSplitbookId &&
    selectedSplitbookIngestStatus === "done" &&
    selectedSplitbookEmbedStatus !== "done" &&
    !splitbookStep3BlockedByRunning;
  const splitbookCanRunExtractStep =
    !!selectedSplitbookId &&
    selectedSplitbookEmbedStatus === "done" &&
    !splitbookStep3BlockedByRunning;
  const splitbookCanRunBuildTemplatesStep = !!selectedSplitbookId && !!splitbookStructuredDone && !splitbookStep3BlockedByRunning;
  const splitbookCanRunBuildProfileStep = !!selectedSplitbookId && !!splitbookStructuredDone && !splitbookStep3BlockedByRunning;
  const splitbookStep3ManualRows = [
    {
      key: "ingest",
      label: "3.1 导入切分",
      done: selectedSplitbookIngestStatus === "done",
      running: selectedSplitbookActiveCaps.has("splitbook.ingest.v1") || (splitbookPipelineBusy && splitbookPipelineStep === "ingest"),
      canRun: splitbookCanRunIngestStep,
      action: () => triggerSplitbookJob("ingest", { confirmIngest: true }),
      buttonText: "执行 3.1",
      latestJob: splitbookLatestJobByCapability["splitbook.ingest.v1"] || null,
      latestSummary: summarizeSplitbookStepLatestJob(splitbookLatestJobByCapability["splitbook.ingest.v1"] || null),
    },
    {
      key: "embed",
      label: "3.2 向量化",
      done: selectedSplitbookEmbedStatus === "done",
      running:
        selectedSplitbookActiveCaps.has("splitbook.embed.v1") ||
        selectedSplitbookEmbedActiveByStats ||
        (splitbookPipelineBusy && splitbookPipelineStep === "embed"),
      canRun: splitbookCanRunEmbedStep,
      action: () => triggerSplitbookJob("embed"),
      buttonText: "执行 3.2",
      latestJob: splitbookLatestJobByCapability["splitbook.embed.v1"] || null,
      latestSummary: summarizeSplitbookStepLatestJob(splitbookLatestJobByCapability["splitbook.embed.v1"] || null),
    },
    {
      key: "extract_structured",
      label: "3.3 结构抽取",
      done: !!splitbookStructuredDone,
      running:
        selectedSplitbookActiveCaps.has("splitbook.extract_structured.v1") ||
        (splitbookPipelineBusy && splitbookPipelineStep === "extract_structured"),
      canRun: splitbookCanRunExtractStep,
      action: () => triggerSplitbookJob("extract_structured"),
      buttonText: "执行 3.3",
      latestJob: splitbookLatestJobByCapability["splitbook.extract_structured.v1"] || null,
      latestSummary: summarizeSplitbookStepLatestJob(splitbookLatestJobByCapability["splitbook.extract_structured.v1"] || null),
    },
    {
      key: "build_templates",
      label: "3.4 生成模板",
      done: !!splitbookTemplatesDone,
      running:
        selectedSplitbookActiveCaps.has("splitbook.build_templates.v1") ||
        (splitbookPipelineBusy && splitbookPipelineStep === "build_templates"),
      canRun: splitbookCanRunBuildTemplatesStep,
      action: () => triggerSplitbookJob("build_templates"),
      buttonText: "执行 3.4",
      latestJob: splitbookLatestJobByCapability["splitbook.build_templates.v1"] || null,
      latestSummary: summarizeSplitbookStepLatestJob(splitbookLatestJobByCapability["splitbook.build_templates.v1"] || null),
    },
    {
      key: "build_profile",
      label: "3.5 生成画像",
      done: !!splitbookProfileDone,
      running:
        selectedSplitbookActiveCaps.has("splitbook.build_profile.v1") ||
        (splitbookPipelineBusy && splitbookPipelineStep === "build_profile"),
      canRun: splitbookCanRunBuildProfileStep,
      action: () => triggerSplitbookJob("build_profile"),
      buttonText: "执行 3.5",
      latestJob: splitbookLatestJobByCapability["splitbook.build_profile.v1"] || null,
      latestSummary: summarizeSplitbookStepLatestJob(splitbookLatestJobByCapability["splitbook.build_profile.v1"] || null),
    },
  ] as const;
  const masterOutlineReady = !!String(masterOutline?.summary || masterOutlineSummary || "").trim();
  const masterOutlineChapterTotalRaw = Number(masterOutline?.planned_chapters || masterOutlinePlannedChapters || 0) || 0;
  const masterOutlineChapterTotal = Math.max(masterOutlineChapterTotalRaw, inferPlannedChaptersFromVolumes(), chapterItems.length || 0);
  const chapterOutlineDoneCount = chapterOutlineOverview.filter((x) => Number(x.outlineVersion || 0) > 0).length;
  const selectedChapterNo = Number(selectedChapterItem?.chapter_no || 0) || 0;
  const selectedVolumeChapterCount =
    Number(selectedVolumeItem?.start_chapter_no || 0) > 0 && Number(selectedVolumeItem?.end_chapter_no || 0) >= Number(selectedVolumeItem?.start_chapter_no || 0)
      ? Number(selectedVolumeItem.end_chapter_no) - Number(selectedVolumeItem.start_chapter_no) + 1
      : 0;
  const writingNextStep:
    | "book_or_brief"
    | "master_outline"
    | "volume_plan"
    | "outline_seed"
    | "closed_loop"
    | "draft_confirm"
    | "completed" = !bookId || writingBriefFilledCount < 4
    ? "book_or_brief"
    : !masterOutlineReady
      ? "master_outline"
      : !quickVolumeId || !volumePlanApplied
        ? "volume_plan"
        : !chapterId || !chapterOutlineSeed
          ? "outline_seed"
          : !closedLoopOutput?.ok
            ? "closed_loop"
            : !quickSelectedDraftId
              ? "draft_confirm"
              : "completed";
  const writingNextStepLabel =
    writingNextStep === "book_or_brief"
      ? "下一步：完成书籍与简报（1.1）"
      : writingNextStep === "master_outline"
        ? "下一步：生成并保存总纲（1.2）"
      : writingNextStep === "volume_plan"
        ? "下一步：生成并应用卷纲（1.3）"
        : writingNextStep === "outline_seed"
          ? "下一步：生成章纲草案（1.4）"
          : writingNextStep === "closed_loop"
            ? "下一步：执行章节生成（1.5）"
            : writingNextStep === "draft_confirm"
              ? "下一步：确认章节草稿（1.6）"
              : "主链路已完成：可继续执行风格进化（1.7）";
  const aiDebugMaster =
    aiDebugData?.master_outline?.ai_debug && typeof aiDebugData?.master_outline?.ai_debug === "object"
      ? aiDebugData.master_outline.ai_debug
      : masterOutlineAiMeta?.ai_debug && typeof masterOutlineAiMeta?.ai_debug === "object"
        ? masterOutlineAiMeta.ai_debug
        : null;
  const aiDebugChapter =
    aiDebugData?.chapter_outline?.ai_debug && typeof aiDebugData?.chapter_outline?.ai_debug === "object"
      ? aiDebugData.chapter_outline.ai_debug
      : null;
  const aiDebugDraft = aiDebugData?.draft_generation && typeof aiDebugData?.draft_generation === "object" ? aiDebugData.draft_generation : null;
  const aiDebugVolumePlan = aiDebugData?.volume_plan && typeof aiDebugData?.volume_plan === "object" ? aiDebugData.volume_plan : null;
  const aiCompliance =
    aiDebugData?.ai_compliance && typeof aiDebugData?.ai_compliance === "object" ? aiDebugData.ai_compliance : null;
  const splitbookNextStep:
    | "step1_file"
    | "step2_create"
    | "step3_ingest"
    | "step3_embed"
    | "step4_extract"
    | "step5_templates"
    | "step5_profile"
    | "step5_review" = !splitbookPathReady
    ? "step1_file"
    : !selectedSplitbookId
      ? "step2_create"
      : selectedSplitbookIngestStatus !== "done"
        ? "step3_ingest"
        : selectedSplitbookEmbedStatus !== "done"
          ? "step3_embed"
          : !splitbookStructuredDone
            ? "step4_extract"
            : !splitbookTemplatesDone
              ? "step5_templates"
              : !splitbookProfileDone
                ? "step5_profile"
                : "step5_review";
  const splitbookNextStepLabel =
    splitbookNextStep === "step1_file"
      ? "下一步：步骤 1 选择并校验本地文本"
      : splitbookNextStep === "step2_create"
        ? "下一步：步骤 2 创建/复用拆书"
        : splitbookNextStep === "step3_ingest"
          ? "下一步：步骤 3.1 导入切分"
          : splitbookNextStep === "step3_embed"
            ? "下一步：步骤 3.2 向量化"
            : splitbookNextStep === "step4_extract"
              ? "下一步：步骤 4.1~4.4 结构抽取与账本刷新"
              : splitbookNextStep === "step5_templates"
                ? "下一步：步骤 5.3 生成模板"
                : splitbookNextStep === "step5_profile"
                  ? "下一步：步骤 5.4 生成画像"
                  : "主链路已完成：可继续执行步骤 5 的导出/回写/体检";
  const structureStepStatusMap = {
    volume_preview:
      structureStepBasis["1.3.1"].status === "success"
        ? "ok"
        : structureStepBasis["1.3.1"].status === "error"
          ? "failed"
          : structurePipelineStep === "volume_preview" || structureStepBasis["1.3.1"].status === "running"
            ? "running"
            : "idle",
    volume_apply:
      structureStepBasis["1.3.2"].status === "success"
        ? "ok"
        : structureStepBasis["1.3.2"].status === "error"
          ? "failed"
          : structurePipelineStep === "volume_apply" || structureStepBasis["1.3.2"].status === "running"
            ? "running"
            : "idle",
    chapter_seed:
      structureStepBasis["1.4.1"].status === "success"
        ? "ok"
        : structureStepBasis["1.4.1"].status === "error"
          ? "failed"
          : structurePipelineStep === "chapter_seed" || structureStepBasis["1.4.1"].status === "running"
            ? "running"
            : "idle",
    control_plan:
      structureStepBasis["1.4.2"].status === "success"
        ? "ok"
        : structureStepBasis["1.4.2"].status === "error"
          ? "failed"
          : structurePipelineStep === "control_plan" || structureStepBasis["1.4.2"].status === "running"
            ? "running"
            : "idle",
  } as const;
  const structureDoneCount = Object.values(structureStepStatusMap).filter((x) => x === "ok").length;
  const structureProgressPct = Math.round((structureDoneCount / 4) * 100);
  const outlineInjectUpdatedText = outlineInjectStatus.updatedAt
    ? new Date(outlineInjectStatus.updatedAt).toLocaleTimeString("zh-CN", { hour12: false })
    : "-";
  const outlineInjectBadgeText = outlineInjectStatus.ready ? "已注入" : "未注入";
  const structureCurrentStepLabel =
    structurePipelineStep === "volume_preview"
      ? "1.3.1 生成卷纲草案"
      : structurePipelineStep === "volume_apply"
        ? "1.3.2 应用卷纲"
        : structurePipelineStep === "chapter_seed"
          ? "1.4.1 生成章纲草案"
          : structurePipelineStep === "control_plan"
            ? "1.4.2 控制计划细化"
            : structurePipelineStep === "done"
              ? "已完成"
              : structurePipelineStep === "failed"
                ? "执行失败"
                : "等待执行";
  const showSplitbookAdvanced = splitbookShowAdvanced;
  const capabilityRetryMax = (() => {
    const eff = Number(getPathValue(effectiveSettingsObj, "ui.capability_chain.retry_max", NaN));
    if (Number.isFinite(eff)) return Math.max(1, Math.min(8, Math.round(eff)));
    const scoped = Number(getPathValue(scopedSettingsObj || {}, "ui.capability_chain.retry_max", NaN));
    if (Number.isFinite(scoped)) return Math.max(1, Math.min(8, Math.round(scoped)));
    return 3;
  })();
  const capabilityRetryBaseMs = (() => {
    const eff = Number(getPathValue(effectiveSettingsObj, "ui.capability_chain.retry_base_ms", NaN));
    if (Number.isFinite(eff)) return Math.max(200, Math.min(5000, Math.round(eff)));
    const scoped = Number(getPathValue(scopedSettingsObj || {}, "ui.capability_chain.retry_base_ms", NaN));
    if (Number.isFinite(scoped)) return Math.max(200, Math.min(5000, Math.round(scoped)));
    return 600;
  })();
  const deleteMismatchBeepEnabled = (() => {
    const eff = getPathValue(effectiveSettingsObj, "ui.delete_confirm.mismatch_beep", undefined);
    if (typeof eff === "boolean") return eff;
    const scoped = getPathValue(scopedSettingsObj || {}, "ui.delete_confirm.mismatch_beep", undefined);
    if (typeof scoped === "boolean") return scoped;
    const local = getPathValue(settingsData || {}, "ui.delete_confirm.mismatch_beep", undefined);
    if (typeof local === "boolean") return local;
    return true;
  })();
  const deleteMismatchBeepLevel = (() => {
    const normalize = (raw: any) => {
      const v = String(raw || "").trim().toLowerCase();
      return v === "strong" ? "strong" : "soft";
    };
    const eff = getPathValue(effectiveSettingsObj, "ui.delete_confirm.mismatch_beep_level", undefined);
    if (eff !== undefined && eff !== null) return normalize(eff);
    const scoped = getPathValue(scopedSettingsObj || {}, "ui.delete_confirm.mismatch_beep_level", undefined);
    if (scoped !== undefined && scoped !== null) return normalize(scoped);
    const local = getPathValue(settingsData || {}, "ui.delete_confirm.mismatch_beep_level", undefined);
    if (local !== undefined && local !== null) return normalize(local);
    return "soft";
  })();
  const splitbookIngestConfirmKeyword = (() => {
    const normalize = (raw: any) => {
      const v = String(raw || "").replace(/\s+/g, "").slice(0, 16).trim();
      return v || "导入";
    };
    const eff = getPathValue(effectiveSettingsObj, "ui.ingest_confirm.keyword", undefined);
    if (eff !== undefined && eff !== null) return normalize(eff);
    const scoped = getPathValue(scopedSettingsObj || {}, "ui.ingest_confirm.keyword", undefined);
    if (scoped !== undefined && scoped !== null) return normalize(scoped);
    const local = getPathValue(settingsData || {}, "ui.ingest_confirm.keyword", undefined);
    if (local !== undefined && local !== null) return normalize(local);
    return "导入";
  })();
  const splitbookWizardSteps = [
    {
      key: "file",
      title: "文件",
      hint: splitbookPathReady ? "已就绪" : "待选择",
      done: splitbookPathReady,
    },
    {
      key: "create",
      title: "建档",
      hint: selectedSplitbookId ? "已选择" : "未建档",
      done: !!selectedSplitbookId,
    },
    {
      key: "core",
      title: "导入/向量化",
      hint: splitbookCoreDone ? "已完成" : "进行中",
      done: !!splitbookCoreDone,
    },
    {
      key: "extract",
      title: "结构账本",
      hint: splitbookStructuredDone ? "已完成" : "待执行",
      done: splitbookStructuredDone,
    },
    {
      key: "deliver",
      title: "模板/画像",
      hint: splitbookTemplatesDone && splitbookProfileDone ? "已完成" : "待完成",
      done: splitbookTemplatesDone && splitbookProfileDone,
    },
  ];
  const flowProgressPct = progressFromStepMap(flowSteps, ["splitbook", "smart", "preflight"]);
  const quickProgressPct = progressFromStepMap(quickPipelineSteps, ["sidecar", "draft", "versions", "select", "publish"]);
  const closedLoopProgressPct = progressFromStepMap(closedLoopSteps, ["draft", "writeback", "preflight", "rewrite", "style_evolution"]);
  const splitbookWizardProgressPct = Math.round(
    (splitbookWizardSteps.filter((x) => x.done).length / Math.max(1, splitbookWizardSteps.length)) * 100
  );
  const writingRecommendedDoneSteps =
    (bookId && writingBriefFilledCount >= 4 ? 1 : 0) +
    (bookId && writingBriefFilledCount >= 4 && masterOutlineReady ? 1 : 0) +
    (bookId && writingBriefFilledCount >= 4 && quickVolumeId && volumePlanApplied ? 1 : 0) +
    (bookId && writingBriefFilledCount >= 4 && quickVolumeId && volumePlanApplied && chapterId && chapterOutlineSeed ? 1 : 0) +
    (closedLoopOutput?.ok ? 1 : 0) +
    (quickSelectedDraftId ? 1 : 0);
  const writingRecommendedProgressPct = Math.round((writingRecommendedDoneSteps / 6) * 100);
  const splitbookRecommendedDoneSteps =
    (splitbookPathReady ? 1 : 0) +
    (selectedSplitbookId ? 1 : 0) +
    (selectedSplitbookIngestStatus === "done" ? 1 : 0) +
    (selectedSplitbookEmbedStatus === "done" ? 1 : 0) +
    (splitbookStructuredDone ? 1 : 0) +
    (splitbookTemplatesDone ? 1 : 0) +
    (splitbookProfileDone ? 1 : 0);
  const splitbookRecommendedProgressPct = Math.round((splitbookRecommendedDoneSteps / 7) * 100);
  const writingRecommendedDisplayPct = Math.max(
    0,
    Math.min(100, Math.round(recommendedWritingStatus.progressPct ?? writingRecommendedProgressPct))
  );
  const splitbookRecommendedDisplayPct = Math.max(
    0,
    Math.min(100, Math.round(recommendedSplitbookStatus.progressPct ?? splitbookRecommendedProgressPct))
  );
  const splitbookPipelineProgressPct =
    selectedSplitbookLiveProgressPctRaw === null ? splitbookWizardProgressPct : selectedSplitbookLiveProgressPctRaw;
  const writingRecommendedBusy = recommendedWritingStatus.state === "processing";
  const splitbookRecommendedBusy = recommendedSplitbookStatus.state === "processing";
  const recommendedGlobalBusy = writingRecommendedBusy || splitbookRecommendedBusy;
  const recommendedGlobalPct = writingRecommendedBusy
    ? writingRecommendedDisplayPct
    : splitbookRecommendedBusy
      ? splitbookRecommendedDisplayPct
      : 0;
  const recommendedGlobalLabel = writingRecommendedBusy
    ? "写作推荐执行中"
    : splitbookRecommendedBusy
      ? "拆书推荐执行中"
      : "";
  const recommendedGlobalText = writingRecommendedBusy
    ? (recommendedWritingStatus.progressText || recommendedWritingStatus.message)
    : splitbookRecommendedBusy
      ? (recommendedSplitbookStatus.progressText || recommendedSplitbookStatus.message)
      : "";
  const writingRecommendedDisabled =
    writingRecommendedBusy || writerStudioBusy || closedLoopBusy || quickPipelineBusy || styleEvolutionBusy;
  const splitbookRecommendedDisabled =
    splitbookRecommendedBusy ||
    splitbookPipelineBusy ||
    selectedSplitbookRunningCount > 0 ||
    selectedSplitbookEmbedActiveByStats;
  const libraryBookHits = librarySearchItems.filter((x) => x.type === "book");
  const libraryChapterHits = librarySearchItems.filter((x) => x.type === "chapter");
  const libraryMaterialHits = librarySearchItems.filter((x) => x.type === "material");
  const librarySkillRunHits = librarySearchItems.filter((x) => x.type === "skill_run");
  const draftConfirmSortedTasks = [...draftConfirmTasks].sort((a: any, b: any) => {
    const ap = String(a?.confirm_status || "") === "pending" ? 0 : 1;
    const bp = String(b?.confirm_status || "") === "pending" ? 0 : 1;
    if (ap !== bp) return ap - bp;
    return Number(a?.chapter_no || 0) - Number(b?.chapter_no || 0);
  });
  const draftConfirmPendingCount = Number(draftConfirmSummary?.pending || 0);
  const visiblePanelCount = [
    showAgentConsole,
    showVersionCenter,
    showRewriteCenter,
    showReleaseCenter,
    showTensionCenter,
    showHelpCenter,
    showJobs,
    showRefCenter,
    showSplitbooks,
    showSettings,
    showAssetCenter,
  ].filter(Boolean).length;

  function scrollToSection(sectionId: string) {
    const el = document.getElementById(sectionId);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function expandDetailsAndScroll(sectionId: string, mode: "all" | "key" = "all") {
    const el = document.getElementById(sectionId);
    if (!el) return;
    const detailsList = Array.from(el.querySelectorAll<HTMLDetailsElement>("details"));
    if (mode === "all") {
      for (const item of detailsList) item.open = true;
    } else {
      for (const item of detailsList) item.open = false;
      const keyDetails = Array.from(el.querySelectorAll<HTMLDetailsElement>('details[data-auto-expand-key="true"]'));
      if (keyDetails.length > 0) {
        for (const item of keyDetails) item.open = true;
      } else if (detailsList.length > 0) {
        detailsList[0].open = true;
      }
    }
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function openDetailsAndScroll(sectionId: string) {
    const el = document.getElementById(sectionId);
    if (!el) return;
    const parentDetails = el.closest("details");
    if (parentDetails) parentDetails.open = true;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function refreshWorkspaceAfterAssetRollback() {
    if (!bookId) return;
    try {
      await Promise.all([
        loadBooks(),
        loadChapters(bookId),
        loadVolumes(bookId),
        loadWritingBrief(bookId),
        loadProfilesList(),
        loadChapterOutlineOverview(undefined, { silent: true }),
      ]);
      if (chapterId) {
        await loadOutline("latest");
      }
      setStatus("已按快照回滚刷新写作上下文。");
    } catch (err) {
      setStatus(`回滚后刷新上下文失败：${formatAnyError(err)}`);
    }
  }

  function openOptionalPanel(target: "jobs" | "ref" | "splitbooks" | "settings" | "agent" | "versions" | "rewrite" | "release" | "tension" | "help" | "assets") {
    if (target === "jobs") setShowJobs(true);
    if (target === "ref") setShowRefCenter(true);
    if (target === "splitbooks") setShowSplitbooks(true);
    if (target === "settings") setShowSettings(true);
    if (target === "agent") setShowAgentConsole(true);
    if (target === "versions") setShowVersionCenter(true);
    if (target === "rewrite") setShowRewriteCenter(true);
    if (target === "release") setShowReleaseCenter(true);
    if (target === "tension") setShowTensionCenter(true);
    if (target === "help") setShowHelpCenter(true);
    if (target === "assets") setShowAssetCenter(true);
  }

  function renderTopPanel(title: string, onClose: () => void, children: ReactNode) {
    return (
      <div className="top-panel-overlay" onMouseDown={onClose}>
        <div className="top-panel-shell" onMouseDown={(e) => e.stopPropagation()}>
          <div className="top-panel-header">
            <strong>{title}</strong>
            <button onClick={onClose}>关闭</button>
          </div>
          <div className="top-panel-body">{children}</div>
        </div>
      </div>
    );
  }

  function applyBookSelection(nextBookId: string) {
    setBookId(nextBookId);
    const row = bookItems.find((b) => b.book_id === nextBookId);
    if (!row) return;
    setNewBookName(String(row.title || ""));
    setNewBookAuthor(String(row.author || ""));
    setNewBookLanguage(String(row.language || "zh"));
    setNewBookNotes(String(row.notes || ""));
  }

  function pushRecommendedRun(track: "writing" | "splitbook", step: string, detail: string) {
    const now = new Date();
    const item = {
      id: `${track}-${now.getTime()}`,
      ts: now.toLocaleTimeString(),
      track,
      step,
      detail,
    };
    setRecommendedRuns((prev) => [item, ...prev].slice(0, 5));
  }

  function setWritingRecommendedProgress(progressPct: number, message: string, progressText?: string) {
    setRecommendedWritingStatus({
      state: "processing",
      message,
      progressPct: Math.max(0, Math.min(99, Math.round(progressPct))),
      progressText,
    });
  }

  function setSplitbookRecommendedProgress(progressPct: number, message: string, progressText?: string) {
    setRecommendedSplitbookStatus({
      state: "processing",
      message,
      progressPct: Math.max(0, Math.min(99, Math.round(progressPct))),
      progressText,
    });
  }

  async function runRecommendedWritingStep() {
    if (recommendedWritingStatus.state === "processing") return;
    setWritingRecommendedProgress(writingRecommendedProgressPct, "处理中...", `写作链路进度：${writingRecommendedProgressPct}%`);
    try {
      if (writingNextStep === "book_or_brief") {
        setWritingRecommendedProgress(8, "正在定位写作工作台...", "步骤 1 / 6");
        pushRecommendedRun("writing", "1.1", writingNextStepLabel);
        scrollToSection("section-writing-studio");
        setRecommendedWritingStatus({ state: "success", message: "已定位到写作工作台，请先完成书籍与简报。", progressPct: writingRecommendedProgressPct });
        return;
      }
      if (writingNextStep === "master_outline") {
        setWritingRecommendedProgress(20, "准备生成并保存总纲...", "步骤 2 / 6");
        pushRecommendedRun("writing", "1.2", writingNextStepLabel);
        if (!bookId) {
          scrollToSection("section-writing-studio");
          setRecommendedWritingStatus({ state: "error", message: "缺少书籍，已定位到写作工作台。", progressPct: writingRecommendedProgressPct });
          return;
        }
        const ok = await generateMasterOutlineAuto();
        setRecommendedWritingStatus({
          state: ok ? "success" : "error",
          message: ok ? "总纲已生成并保存，可继续卷纲。" : "总纲生成失败，请查看状态栏。",
          progressPct: ok ? Math.max(writingRecommendedProgressPct, 30) : writingRecommendedProgressPct,
        });
        return;
      }
      if (writingNextStep === "volume_plan") {
        setWritingRecommendedProgress(35, "准备生成卷纲草案...", "步骤 3 / 6");
        pushRecommendedRun("writing", "1.3", writingNextStepLabel);
        if (!bookId) {
          scrollToSection("section-writing-studio");
          setRecommendedWritingStatus({ state: "error", message: "缺少书籍，已定位到写作工作台。", progressPct: writingRecommendedProgressPct });
          return;
        }
        setWritingRecommendedProgress(50, "卷纲草案生成中...", "步骤 3 / 6");
        const ok = await generateVolumePlanPreview();
        setRecommendedWritingStatus({
          state: ok ? "success" : "error",
          message: ok ? "卷纲草案生成完成，可继续应用卷纲。" : "卷纲草案生成失败，请查看状态栏。",
          progressPct: ok ? Math.max(writingRecommendedProgressPct, 55) : writingRecommendedProgressPct,
        });
        return;
      }
      if (writingNextStep === "outline_seed") {
        setWritingRecommendedProgress(60, "准备生成章纲草案...", "步骤 4 / 6");
        pushRecommendedRun("writing", "1.4", writingNextStepLabel);
        if (!bookId) {
          scrollToSection("section-writing-studio");
          setRecommendedWritingStatus({ state: "error", message: "缺少书籍，已定位到写作工作台。", progressPct: writingRecommendedProgressPct });
          return;
        }
        setWritingRecommendedProgress(72, "章纲草案生成中...", "步骤 4 / 6");
        const ok = await generateChapterOutlineSeed();
        setRecommendedWritingStatus({
          state: ok ? "success" : "error",
          message: ok ? "章纲草案生成完成，可继续闭环执行。" : "章纲草案生成失败，请查看状态栏。",
          progressPct: ok ? Math.max(writingRecommendedProgressPct, 75) : writingRecommendedProgressPct,
        });
        return;
      }
      if (writingNextStep === "closed_loop") {
        setWritingRecommendedProgress(80, "准备执行章节生成...", "步骤 5 / 6");
        pushRecommendedRun("writing", "1.5", writingNextStepLabel);
        const ready = await ensureStructureTargetsReady({ silent: true });
        if (!bookId || !ready?.chapterId) {
          scrollToSection("section-writing-studio");
          setRecommendedWritingStatus({ state: "error", message: "缺少书籍或章节，已定位到写作工作台。", progressPct: writingRecommendedProgressPct });
          return;
        }
        setWritingRecommendedProgress(90, "章节生成执行中（正文→回写→体检）...", "步骤 5 / 6");
        const ok = await runClosedLoopFlow();
        setRecommendedWritingStatus({
          state: ok ? "success" : "error",
          message: ok ? "章节生成执行完成。" : "章节生成失败，请查看状态栏。",
          progressPct: ok ? Math.max(writingRecommendedProgressPct, 80) : writingRecommendedProgressPct,
        });
        return;
      }
      if (writingNextStep === "draft_confirm") {
        setWritingRecommendedProgress(95, "正在确认章节草稿版本...", "步骤 6 / 6");
        pushRecommendedRun("writing", "1.6", writingNextStepLabel);
        const ready = await ensureStructureTargetsReady({ silent: true });
        if (!ready?.chapterId) {
          scrollToSection("section-writing-studio");
          setRecommendedWritingStatus({ state: "error", message: "缺少章节，已定位到写作工作台。", progressPct: writingRecommendedProgressPct });
          return;
        }
        const ok = await quickConfirmLatestDraftFlow();
        setRecommendedWritingStatus({
          state: ok ? "success" : "error",
          message: ok ? "章节草稿确认完成。" : "章节草稿确认失败，请先检查草稿是否生成。",
          progressPct: ok ? 100 : writingRecommendedProgressPct,
        });
        return;
      }
      if (writingNextStep === "completed" && closedLoopEvolveStyle) {
        setWritingRecommendedProgress(85, "准备执行风格进化...", "步骤 1.7（可选）");
        pushRecommendedRun("writing", "1.7", "下一步：执行风格进化（1.7）");
        setWritingRecommendedProgress(92, "风格进化执行中...", "步骤 1.7（可选）");
        const ok = await runStyleEvolutionNow(false);
        setRecommendedWritingStatus({
          state: ok ? "success" : "error",
          message: ok ? "风格进化执行完成。" : "风格进化执行失败，请查看状态栏。",
          progressPct: ok ? 100 : writingRecommendedProgressPct,
        });
        return;
      }
      setRecommendedWritingStatus({
        state: "success",
        message: "写作主链路已完成，可继续下一章或执行风格进化。",
        progressPct: 100,
      });
    } catch (err) {
      setRecommendedWritingStatus({ state: "error", message: `执行失败：${formatAnyError(err)}`, progressPct: writingRecommendedProgressPct });
    }
  }

  async function runRecommendedSplitbookStep() {
    if (recommendedSplitbookStatus.state === "processing") return;
    setSplitbookRecommendedProgress(splitbookRecommendedProgressPct, "处理中...", `拆书链路进度：${splitbookRecommendedProgressPct}%`);
    try {
      if (splitbookNextStep === "step1_file") {
        setSplitbookRecommendedProgress(8, "正在选择并校验本地文件...", "步骤 1 / 7");
        pushRecommendedRun("splitbook", "1", splitbookNextStepLabel);
        const ok = await pickSplitbookLocalFile();
        setRecommendedSplitbookStatus({
          state: ok ? "success" : "error",
          message: ok ? "本地文件已处理完成，可继续步骤 2。" : "本地文件处理未完成，请查看状态栏。",
          progressPct: ok ? Math.max(splitbookRecommendedProgressPct, 14) : splitbookRecommendedProgressPct,
        });
        return;
      }
      if (splitbookNextStep === "step2_create") {
        setSplitbookRecommendedProgress(20, "准备创建/复用拆书...", "步骤 2 / 7");
        pushRecommendedRun("splitbook", "2", splitbookNextStepLabel);
        if (!splitbookPathCheck?.ok || !splitbookName.trim()) {
          openOptionalPanel("splitbooks");
          setRecommendedSplitbookStatus({ state: "error", message: "拆书名称或路径未准备完成，已打开拆书面板。", progressPct: splitbookRecommendedProgressPct });
          return;
        }
        setSplitbookRecommendedProgress(28, "拆书创建中...", "步骤 2 / 7");
        const ok = await createSplitbookFromUi();
        setRecommendedSplitbookStatus({
          state: ok ? "success" : "error",
          message: ok ? "拆书创建/复用完成，可继续步骤 3.1。" : "拆书创建失败，请查看状态栏。",
          progressPct: ok ? Math.max(splitbookRecommendedProgressPct, 28) : splitbookRecommendedProgressPct,
        });
        return;
      }
      if (splitbookNextStep === "step3_ingest") {
        setSplitbookRecommendedProgress(34, "准备执行导入切分...", "步骤 3.1 / 7");
        pushRecommendedRun("splitbook", "3.1", splitbookNextStepLabel);
        if (!selectedSplitbookId || !splitbookPathCheck?.ok) {
          openOptionalPanel("splitbooks");
          setRecommendedSplitbookStatus({ state: "error", message: "未选中拆书或路径未校验，已打开拆书面板。", progressPct: splitbookRecommendedProgressPct });
          return;
        }
        setSplitbookRecommendedProgress(40, "导入切分执行中...", "步骤 3.1 / 7");
        const ingest = await triggerSplitbookJob("ingest", { splitbookId: selectedSplitbookId, confirmIngest: false });
        if (!ingest?.job_id) {
          setRecommendedSplitbookStatus({ state: "error", message: "步骤 3.1 未启动，请检查路径或拆书状态。", progressPct: splitbookRecommendedProgressPct });
          return;
        }
        await waitJobTerminal(String(ingest.job_id));
        await refreshSplitbookWorkspace({ silent: true }).catch(() => {});
        const ok = true;
        setRecommendedSplitbookStatus({
          state: ok ? "success" : "error",
          message: ok ? "步骤 3.1 导入切分完成，可继续步骤 3.2。" : "步骤 3.1 未完成，请查看任务中心。",
          progressPct: ok ? Math.max(splitbookRecommendedProgressPct, 42) : splitbookRecommendedProgressPct,
        });
        return;
      }
      if (splitbookNextStep === "step3_embed") {
        setSplitbookRecommendedProgress(48, "准备执行向量化...", "步骤 3.2 / 7");
        pushRecommendedRun("splitbook", "3.2", splitbookNextStepLabel);
        if (!selectedSplitbookId) {
          openOptionalPanel("splitbooks");
          setRecommendedSplitbookStatus({ state: "error", message: "未选中拆书，已打开拆书面板。", progressPct: splitbookRecommendedProgressPct });
          return;
        }
        setSplitbookRecommendedProgress(55, "向量化执行中...", "步骤 3.2 / 7");
        const out = await triggerSplitbookJob("embed", { splitbookId: selectedSplitbookId });
        if ((out as any)?.job_id) await waitJobTerminal(String((out as any).job_id));
        await refreshSplitbookWorkspace({ silent: true }).catch(() => {});
        const done = true;
        const skipped = Boolean((out as any)?.skipped);
        if (!(out as any)?.job_id && !skipped) {
          setRecommendedSplitbookStatus({ state: "error", message: "步骤 3.2 未启动，请检查向量化前置条件。", progressPct: splitbookRecommendedProgressPct });
          return;
        }
        setRecommendedSplitbookStatus({
          state: done || skipped ? "success" : "error",
          message: skipped ? "向量化已存在，自动跳过。" : done ? "步骤 3.2 向量化完成，可继续步骤 4。" : "步骤 3.2 未完成，请查看任务中心。",
          progressPct: done || skipped ? Math.max(splitbookRecommendedProgressPct, 58) : splitbookRecommendedProgressPct,
        });
        return;
      }
      if (splitbookNextStep === "step4_extract") {
        setSplitbookRecommendedProgress(64, "准备执行结构抽取与账本刷新...", "步骤 4 / 7");
        pushRecommendedRun("splitbook", "4", splitbookNextStepLabel);
        const ok = await runSplitbookStep4ExtractAndRefresh();
        setRecommendedSplitbookStatus({
          state: ok ? "success" : "error",
          message: ok ? "步骤 4 完成：账本/大纲/章节包已刷新。" : "步骤 4 失败，请查看状态栏。",
          progressPct: ok ? Math.max(splitbookRecommendedProgressPct, 72) : splitbookRecommendedProgressPct,
        });
        return;
      }
      if (splitbookNextStep === "step5_templates") {
        setSplitbookRecommendedProgress(78, "准备执行模板生成...", "步骤 5.3 / 7");
        pushRecommendedRun("splitbook", "5.3", splitbookNextStepLabel);
        if (!selectedSplitbookId) {
          openOptionalPanel("splitbooks");
          setRecommendedSplitbookStatus({ state: "error", message: "未选中拆书，已打开拆书面板。", progressPct: splitbookRecommendedProgressPct });
          return;
        }
        const out = await triggerSplitbookJob("build_templates", { splitbookId: selectedSplitbookId });
        if (!(out as any)?.job_id) {
          setRecommendedSplitbookStatus({ state: "error", message: "步骤 5.3 未启动，请先确认结构抽取已完成。", progressPct: splitbookRecommendedProgressPct });
          return;
        }
        await waitJobTerminal(String((out as any).job_id));
        await refreshSplitbookWorkspace({ silent: true }).catch(() => {});
        setRecommendedSplitbookStatus({
          state: true ? "success" : "error",
          message: "步骤 5.3 模板生成已完成。",
          progressPct: Math.max(splitbookRecommendedProgressPct, 86),
        });
        return;
      }
      if (splitbookNextStep === "step5_profile") {
        setSplitbookRecommendedProgress(90, "准备执行画像生成...", "步骤 5.4 / 7");
        pushRecommendedRun("splitbook", "5.4", splitbookNextStepLabel);
        if (!selectedSplitbookId) {
          openOptionalPanel("splitbooks");
          setRecommendedSplitbookStatus({ state: "error", message: "未选中拆书，已打开拆书面板。", progressPct: splitbookRecommendedProgressPct });
          return;
        }
        const out = await triggerSplitbookJob("build_profile", { splitbookId: selectedSplitbookId });
        if (!(out as any)?.job_id) {
          setRecommendedSplitbookStatus({ state: "error", message: "步骤 5.4 未启动，请先确认结构抽取已完成。", progressPct: splitbookRecommendedProgressPct });
          return;
        }
        await waitJobTerminal(String((out as any).job_id));
        await refreshSplitbookWorkspace({ silent: true }).catch(() => {});
        setRecommendedSplitbookStatus({
          state: "success",
          message: "步骤 5.4 画像生成已完成。",
          progressPct: Math.max(splitbookRecommendedProgressPct, 96),
        });
        return;
      }
      pushRecommendedRun("splitbook", "5.x", splitbookNextStepLabel);
      openOptionalPanel("splitbooks");
      setRecommendedSplitbookStatus({ state: "success", message: "拆书主链路已完成，可继续执行步骤 5 的导出/回写/体检。", progressPct: 100 });
    } catch (err) {
      setRecommendedSplitbookStatus({ state: "error", message: `执行失败：${formatAnyError(err)}`, progressPct: splitbookRecommendedProgressPct });
      if (
        splitbookNextStep === "step3_ingest" ||
        splitbookNextStep === "step3_embed" ||
        splitbookNextStep === "step4_extract" ||
        splitbookNextStep === "step5_templates" ||
        splitbookNextStep === "step5_profile"
      ) {
        openOptionalPanel("splitbooks");
      }
    }
  }

  return (
    <div className="wb-page">
      <header className="wb-header">
        <div className="wb-header-title">
          <h1>AI 写作引擎工作台</h1>
          <div className="small">先定义基调与设定，再生成卷纲/章纲并迭代，最后进入正文与体检闭环。</div>
        </div>
        <div className="wb-header-tools">
          <div className="row" style={{ gap: 6 }}>
            <button className={workspaceMode === "dual" ? "active" : ""} onClick={() => setWorkspaceMode("dual")}>双栏作业</button>
            <button className={workspaceMode === "writing" ? "active" : ""} onClick={() => setWorkspaceMode("writing")}>写作优先</button>
            <button className={workspaceMode === "splitbook" ? "active" : ""} onClick={() => setWorkspaceMode("splitbook")}>拆书优先</button>
          </div>
          <label className="small" style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input type="checkbox" checked={writerSimpleMode} onChange={(e) => setWriterSimpleMode(e.target.checked)} />
            简洁作业模式（当前：{writerSimpleMode ? "开启" : "关闭"}）
          </label>
          <button onClick={() => setSearchOpen(true)}>全局搜索 (Ctrl/Cmd+K)</button>
          <details className="header-panel-switcher">
            <summary>顶部面板列表</summary>
            <div className="row" style={{ marginTop: 8 }}>
              <button onClick={() => openOptionalPanel("jobs")}>① 任务中心{showJobs ? "（已显示）" : ""}</button>
              <button onClick={() => openOptionalPanel("settings")}>② 设置与健康{showSettings ? "（已显示）" : ""}</button>
              <button onClick={() => openOptionalPanel("ref")}>③ 引用中心{showRefCenter ? "（已显示）" : ""}</button>
              <button onClick={() => openOptionalPanel("splitbooks")}>④ 拆书库{showSplitbooks ? "（已显示）" : ""}</button>
              <button onClick={() => openOptionalPanel("agent")}>⑤ 智能体控制台{showAgentConsole ? "（已显示）" : ""}</button>
              <button onClick={() => openOptionalPanel("versions")}>⑥ 版本中心{showVersionCenter ? "（已显示）" : ""}</button>
              <button onClick={() => openOptionalPanel("rewrite")}>⑦ 改写中心{showRewriteCenter ? "（已显示）" : ""}</button>
              <button onClick={() => openOptionalPanel("release")}>⑧ 发布中心{showReleaseCenter ? "（已显示）" : ""}</button>
              <button onClick={() => openOptionalPanel("tension")}>⑨ 张力看板{showTensionCenter ? "（已显示）" : ""}</button>
              <button onClick={() => openOptionalPanel("assets")}>⑩ 资产沉淀{showAssetCenter ? "（已显示）" : ""}</button>
              <button onClick={() => openOptionalPanel("help")}>⑪ 帮助中心{showHelpCenter ? "（已显示）" : ""}</button>
            </div>
          </details>
          <div className="status">状态：{status}</div>
          {recommendedGlobalBusy ? (
            <div
              style={{
                minWidth: 260,
                maxWidth: 360,
                border: "1px solid #c7f9e6",
                borderRadius: 8,
                padding: "6px 8px",
                background: "#f0fdf7",
              }}
            >
              <div className="small" style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <strong>{recommendedGlobalLabel}</strong>
                <span>{recommendedGlobalPct}%</span>
              </div>
              <div className="pipeline-progress" style={{ marginTop: 4 }}>
                <span style={{ width: `${recommendedGlobalPct}%` }} />
              </div>
              <div className="small" style={{ marginTop: 4 }}>{recommendedGlobalText}</div>
            </div>
          ) : null}
        </div>
      </header>

      <section className="next-step-banner">
        {showWritingWorkspace ? (
          <div className="next-step-card">
            <div className="small">写作引擎下一步</div>
            <strong>{writingNextStepLabel}</strong>
            <button onClick={() => void runRecommendedWritingStep()} disabled={writingRecommendedDisabled}>
              {writingRecommendedBusy ? `处理中 ${writingRecommendedDisplayPct}%...` : "执行推荐步骤"}
            </button>
            <div className="small">进度：{writingRecommendedDisplayPct}%</div>
            <div className="pipeline-progress"><span style={{ width: `${writingRecommendedDisplayPct}%` }} /></div>
            {recommendedWritingStatus.progressText ? <div className="small">{recommendedWritingStatus.progressText}</div> : null}
            <div
              className={`small ${
                recommendedWritingStatus.state === "error"
                  ? "danger"
                  : recommendedWritingStatus.state === "success"
                    ? "ok"
                    : ""
              }`}
            >
              状态：{recommendedWritingStatus.message}
            </div>
          </div>
        ) : null}
        {showSplitbookWorkspace ? (
          <div className="next-step-card">
            <div className="small">拆书系统下一步</div>
            <strong>{splitbookNextStepLabel}</strong>
            <button onClick={() => void runRecommendedSplitbookStep()} disabled={splitbookRecommendedDisabled}>
              {splitbookRecommendedBusy ? `处理中 ${splitbookRecommendedDisplayPct}%...` : "执行推荐步骤"}
            </button>
            <div className="small">进度：{splitbookRecommendedDisplayPct}%</div>
            <div className="pipeline-progress"><span style={{ width: `${splitbookRecommendedDisplayPct}%` }} /></div>
            {recommendedSplitbookStatus.progressText ? <div className="small">{recommendedSplitbookStatus.progressText}</div> : null}
            <div
              className={`small ${
                recommendedSplitbookStatus.state === "error"
                  ? "danger"
                  : recommendedSplitbookStatus.state === "success"
                    ? "ok"
                    : ""
              }`}
            >
              状态：{recommendedSplitbookStatus.message}
            </div>
          </div>
        ) : null}
        <div className="next-step-card next-step-history">
          <div className="row" style={{ width: "100%" }}>
            <div>
              <div className="small">推荐步骤执行历史（最近 5 次）</div>
              <strong>{recommendedRuns.length ? "已记录" : "暂无记录"}</strong>
            </div>
            <button onClick={() => setRecommendedRuns([])} disabled={!recommendedRuns.length}>清空</button>
          </div>
          <div className="next-step-history-list">
            {recommendedRuns.length === 0 ? (
              <div className="small">执行上方“执行推荐步骤”后会自动记录。</div>
            ) : (
              recommendedRuns.map((item) => (
                <div key={item.id} className="next-step-history-item">
                  <span className="small">{item.ts}</span>
                  <strong>{item.track === "writing" ? "写作" : "拆书"} {item.step}</strong>
                  <span className="small">{item.detail}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      <section className="wb-shortcuts">
        {showWritingWorkspace ? (
          <>
            <button onClick={() => scrollToSection("section-writing-studio")}>写作工作台</button>
            <button onClick={() => scrollToSection("section-capability-clarity")}>能力观测总览</button>
            {!writerSimpleMode ? <button onClick={() => scrollToSection("section-quickstart")}>快速启动</button> : null}
            <button onClick={() => scrollToSection("section-outline-tools")}>章节操作</button>
            <button onClick={() => scrollToSection("section-main-editor")}>节点编辑</button>
          </>
        ) : null}
        {showSplitbookWorkspace ? (
          <button onClick={() => openOptionalPanel("splitbooks")}>拆书全量面板</button>
        ) : null}
        <button onClick={() => openOptionalPanel("help")}>帮助中心</button>
        <span className="small">更多功能请使用顶部“面板列表”</span>
        <span className="small">当前打开面板：{visiblePanelCount} 个</span>
      </section>

      {showWritingWorkspace ? (
      <section className="wb-panel" style={{ minHeight: "auto", marginBottom: 10 }}>
        <div className="row" style={{ marginBottom: 8 }}>
          <h3 style={{ margin: 0 }}>核心作业区</h3>
          <span className="small">聚焦拆书 + AI 写作，两条主链路按顺序执行。</span>
        </div>
        <div className="core-workspace-grid">
          {showWritingWorkspace ? (
            <div className="quickstart-card">
              <h4>① AI 写作引擎主链路</h4>
              <div className="small" style={{ marginBottom: 8, color: "#0a5f58" }}>{writingNextStepLabel}</div>
              <div className="core-step-list">
                <div className={`core-step ${writingNextStep === "book_or_brief" ? "active" : ""}`}><strong>1.1</strong><span>填写题材、基调、设定并保存简报</span></div>
                <div className={`core-step ${writingNextStep === "master_outline" ? "active" : ""}`}><strong>1.2</strong><span>生成/保存总纲（可注入拆书结构）</span></div>
                <div className={`core-step ${writingNextStep === "volume_plan" ? "active" : ""}`}><strong>1.3</strong><span>生成卷纲草案并应用（可注入拆书结构）</span></div>
                <div className={`core-step ${writingNextStep === "outline_seed" ? "active" : ""}`}><strong>1.4</strong><span>生成章纲草案并微调节点（可注入拆书结构）</span></div>
                <div className={`core-step ${writingNextStep === "closed_loop" ? "active" : ""}`}><strong>1.5</strong><span>按章纲生成章节（支持 1~5 章）</span></div>
                <div className={`core-step ${writingNextStep === "draft_confirm" ? "active" : ""}`}><strong>1.6</strong><span>确认章节草稿</span></div>
                <div className={`core-step ${closedLoopSteps.style_evolution === "running" ? "active" : ""}`}><strong>1.7</strong><span>风格进化：基于数据库样本自动迭代画像</span></div>
              </div>
              <div className="quick-status-grid" style={{ marginTop: 8 }}>
                <div className="summary-card">
                  <div className="k">书籍 / 章节</div>
                  <div className="v">
                    {selectedBookItem?.title || "未选择书籍"}
                    {selectedChapterItem ? ` · 第${selectedChapterItem.chapter_no}章` : " · 未选择章节"}
                  </div>
                </div>
                <div className="summary-card">
                  <div className="k">结构进度</div>
                  <div className="v">
                    总纲 {masterOutlineReady ? "已保存" : "未保存"} · 结构 {structureDoneCount}/4
                  </div>
                </div>
                <div className="summary-card">
                  <div className="k">章纲规模</div>
                  <div className="v">
                    {masterOutlineChapterTotal > 0 ? `计划 ${masterOutlineChapterTotal} 章` : "未设定"}
                    {chapterItems.length > 0 ? ` · 已建 ${chapterItems.length} 章` : ""}
                  </div>
                </div>
                <div className="summary-card">
                  <div className="k">确认 / 风格</div>
                  <div className="v">
                    草稿 {quickSelectedDraftId ? "已确认" : "未确认"} · 风格 {styleEvolutionStatusText}
                  </div>
                </div>
              </div>
              <div className="row" style={{ marginTop: 8, gap: 8, flexWrap: "wrap" }}>
                <button className={writingNextStep === "book_or_brief" ? "active" : ""} onClick={() => scrollToSection("section-writing-studio")}>执行 1.1</button>
                <button
                  className={writingNextStep === "master_outline" ? "active" : ""}
                  onClick={() => void generateMasterOutlineAuto()}
                  disabled={!bookId || masterOutlineBusy || writerStudioBusy}
                >
                  {masterOutlineBusy ? "执行中..." : "执行 1.2"}
                </button>
                <button
                  className={writingNextStep === "volume_plan" ? "active" : ""}
                  onClick={() => void generateVolumePlanPreview()}
                  disabled={!bookId}
                >
                  执行 1.3
                </button>
                <button
                  className={writingNextStep === "outline_seed" ? "active" : ""}
                  onClick={() => void generateChapterOutlineSeed()}
                  disabled={!bookId}
                >
                  执行 1.4
                </button>
                <button onClick={() => void runClosedLoopFlow()} disabled={closedLoopBusy || quickPipelineBusy || batchGenerateBusy || !bookId || !chapterId}>
                  {closedLoopBusy ? "章节生成中..." : "执行 1.5 生成"}
                </button>
                <label className="small" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  批量章数
                  <input
                    style={{ width: 66 }}
                    type="number"
                    min={1}
                    max={5}
                    value={batchGenerateCount}
                    onChange={(e) => setBatchGenerateCount(Math.max(1, Math.min(5, Number(e.target.value) || 1)))}
                    disabled={batchGenerateBusy || closedLoopBusy}
                  />
                </label>
                <button
                  onClick={() => void runBatchClosedLoopGeneration()}
                  disabled={batchGenerateBusy || closedLoopBusy || !bookId || !chapterId}
                >
                  {batchGenerateBusy ? "批量生成中..." : `批量生成 ${Math.max(1, Math.min(5, Number(batchGenerateCount || 1)))} 章`}
                </button>
                <button
                  className={writingNextStep === "draft_confirm" ? "active" : ""}
                  onClick={() => void quickConfirmLatestDraftFlow()}
                  disabled={quickDraftConfirmBusy || !chapterId}
                >
                  {quickDraftConfirmBusy ? "执行中..." : "执行 1.6 草稿确认"}
                </button>
                <button onClick={() => void runStyleEvolutionNow(false)} disabled={styleEvolutionBusy || !bookId}>
                  {styleEvolutionBusy ? "风格进化中..." : "执行 1.7 风格进化"}
                </button>
              </div>
            </div>
          ) : null}
          {showSplitbookWorkspace ? (
            <div className="quickstart-card">
              <h4>② 拆书主链路</h4>
              <div className="small" style={{ marginBottom: 8, color: "#0a5f58" }}>{splitbookNextStepLabel}</div>
              <div className="core-step-list">
                <div className={`core-step ${splitbookNextStep === "step1_file" ? "active" : ""}`}><strong>1</strong><span>选择本地 TXT/MD 文件并校验路径</span></div>
                <div className={`core-step ${splitbookNextStep === "step2_create" ? "active" : ""}`}><strong>2</strong><span>创建/复用拆书档案</span></div>
                <div className={`core-step ${splitbookNextStep === "step3_ingest" ? "active" : ""}`}><strong>3.1</strong><span>导入切分（Ingest）</span></div>
                <div className={`core-step ${splitbookNextStep === "step3_embed" ? "active" : ""}`}><strong>3.2</strong><span>向量化（Embed）</span></div>
                <div className={`core-step ${splitbookNextStep === "step4_extract" ? "active" : ""}`}><strong>4</strong><span>结构抽取 + 账本/大纲/章节包刷新</span></div>
                <div className={`core-step ${splitbookNextStep === "step5_templates" ? "active" : ""}`}><strong>5.3</strong><span>生成模板</span></div>
                <div className={`core-step ${splitbookNextStep === "step5_profile" ? "active" : ""}`}><strong>5.4</strong><span>生成画像</span></div>
              </div>
              <div className="quick-status-grid" style={{ marginTop: 8 }}>
                <div className="summary-card">
                  <div className="k">当前拆书</div>
                  <div className="v">{selectedSplitbook?.name || "未选择"}</div>
                </div>
                <div className="summary-card">
                  <div className="k">导入状态</div>
                  <div className="v">{selectedSplitbook ? formatPipelineStatus(selectedSplitbook.ingest_status) : "-"}</div>
                </div>
                <div className="summary-card">
                  <div className="k">向量化状态</div>
                  <div className="v">{selectedSplitbook ? formatPipelineStatus(selectedSplitbook.embed_status) : "-"}</div>
                </div>
                <div className="summary-card">
                  <div className="k">产物目录</div>
                  <div className="v">{splitbookOutputDir ? "已设置" : "未设置"}</div>
                </div>
              </div>
              <div className="row" style={{ marginTop: 8, gap: 8, flexWrap: "wrap" }}>
                <button className={splitbookNextStep === "step1_file" ? "active" : ""} onClick={() => void pickSplitbookLocalFile()}>执行 1</button>
                <button
                  className={splitbookNextStep === "step2_create" ? "active" : ""}
                  onClick={() => {
                    if (!splitbookName.trim()) {
                      openOptionalPanel("splitbooks");
                      return;
                    }
                    void createSplitbookFromUi();
                  }}
                  disabled={!splitbookPathCheck?.ok}
                >
                  执行 2
                </button>
                <button
                  className={splitbookNextStep === "step3_ingest" ? "active" : ""}
                  onClick={() => void triggerSplitbookJob("ingest", { confirmIngest: false })}
                  disabled={!splitbookCanRunIngestStep}
                >
                  执行 3.1
                </button>
                <button
                  className={splitbookNextStep === "step3_embed" ? "active" : ""}
                  onClick={() => void triggerSplitbookJob("embed")}
                  disabled={!splitbookCanRunEmbedStep && !splitbookCanResumeEmbed}
                >
                  执行 3.2
                </button>
                <button
                  className={splitbookNextStep === "step4_extract" ? "active" : ""}
                  onClick={() => void runSplitbookStep4ExtractAndRefresh()}
                  disabled={!selectedSplitbookId || selectedSplitbookEmbedStatus !== "done" || splitbookStep4Busy}
                >
                  执行 4
                </button>
                <button
                  className={splitbookNextStep === "step5_templates" ? "active" : ""}
                  onClick={() => void triggerSplitbookJob("build_templates")}
                  disabled={!splitbookCanRunBuildTemplatesStep}
                >
                  执行 5.3
                </button>
                <button
                  className={splitbookNextStep === "step5_profile" ? "active" : ""}
                  onClick={() => void triggerSplitbookJob("build_profile")}
                  disabled={!splitbookCanRunBuildProfileStep}
                >
                  执行 5.4
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>
      ) : null}

      {(showWritingWorkspace || showSplitbookWorkspace) ? (
      <CapabilityClarityPanel
        baseUrl={baseUrl}
        bookId={bookId}
        chapterId={chapterId}
        volumeId={quickVolumeId}
        splitbookId={selectedSplitbookId}
        retryMax={capabilityRetryMax}
        retryBaseMs={capabilityRetryBaseMs}
        antiCopyReport={splitbookAntiCopyReport}
        onStatus={setStatus}
        onRunRepairPlan={createRepairPlan}
        onRunTemplateEvolve={evolveTemplates}
        onRunAntiCopy={runSplitbookAntiCopyCheck}
      />
      ) : null}

      {showWritingWorkspace ? (
      <section id="section-writing-studio" className="wb-panel" style={{ minHeight: "auto", marginBottom: 10 }}>
        <div className="row" style={{ marginBottom: 8 }}>
          <h3 style={{ margin: 0 }}>写作引擎工作台</h3>
          <span className="small">流程：书籍项目 → 创作简报 → 总纲 → 卷纲 → 章纲 → 正文生成 → 风格进化</span>
        </div>
        <div className="quickstart-grid" style={writerSimpleMode ? { gridTemplateColumns: "1fr" } : undefined}>
          <div className="quickstart-card">
            <h4>1) 创建/选择书籍项目</h4>
            <div className="quick-form-grid">
              <label>
                书名
                <input value={newBookName} onChange={(e) => setNewBookName(e.target.value)} placeholder="例如：星港回声" />
              </label>
              <label>
                作者
                <input value={newBookAuthor} onChange={(e) => setNewBookAuthor(e.target.value)} placeholder="可选" />
              </label>
              <label>
                语言
                <select value={newBookLanguage} onChange={(e) => setNewBookLanguage(e.target.value)}>
                  <option value="zh">中文（zh）</option>
                  <option value="en">英文（en）</option>
                </select>
              </label>
              <label>
                已有书籍
                <select value={bookId} onChange={(e) => applyBookSelection(e.target.value)}>
                  <option value="">请选择</option>
                  {bookItems.map((b) => (
                    <option key={b.book_id} value={b.book_id}>
                      {b.title}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label style={{ marginTop: 8 }}>
              书籍备注
              <textarea rows={2} value={newBookNotes} onChange={(e) => setNewBookNotes(e.target.value)} placeholder="卖点、禁区、发布定位等（可选）" />
            </label>
            <label style={{ marginTop: 8 }}>
              存储目录（工作区）
              <input
                value={newBookWorkspacePath}
                onChange={(e) => setNewBookWorkspacePath(e.target.value)}
                placeholder="例如 D:\\NovelEngine\\books\\my-book"
              />
            </label>
            <div className="row" style={{ marginTop: 8 }}>
              <button onClick={() => void pickProjectWorkspaceDir()}>选择目录</button>
              <button onClick={() => void createBookProjectFromStudio()} disabled={writerStudioBusy}>
                {writerStudioBusy ? "创建中..." : "创建书籍项目"}
              </button>
              <button onClick={() => void loadBooks()}>刷新书籍</button>
              <button
                className="danger"
                onClick={() => void deleteCurrentBookFromLibrary()}
                disabled={!bookId || bookDeleting || writerStudioBusy}
              >
                {bookDeleting ? "删除中..." : "删除当前书籍"}
              </button>
            </div>
            <div className="small" style={{ marginTop: 8 }}>
              当前：{selectedBookItem ? `${selectedBookItem.title} (${selectedBookItem.book_id.slice(0, 8)}...)` : "未选择书籍"}
            </div>
            <div className="small danger" style={{ marginTop: 4 }}>
              删除会同步清理该书的章节、卷纲、事实层与关联任务数据，请谨慎操作。
            </div>
          </div>

          <div className="quickstart-card">
            <h4>2) 定义创作简报</h4>
            <div className="quick-form-grid">
              <label>
                题材
                <input value={storyGenre} onChange={(e) => setStoryGenre(e.target.value)} placeholder="玄幻 / 都市 / 科幻..." />
              </label>
              <label>
                受众
                <input value={storyAudience} onChange={(e) => setStoryAudience(e.target.value)} placeholder="例如：男频爽文读者" />
              </label>
              <label>
                主题命题
                <input value={storyTheme} onChange={(e) => setStoryTheme(e.target.value)} placeholder="成长、代价、选择..." />
              </label>
              <label>
                文风基调
                <input value={storyTone} onChange={(e) => setStoryTone(e.target.value)} placeholder="紧凑、冷峻、热血..." />
              </label>
            </div>
            <label style={{ marginTop: 8 }}>
              核心灵感/主线目标
              <textarea
                rows={3}
                value={storyIdea}
                onChange={(e) => setStoryIdea(e.target.value)}
                placeholder="主角目标、主线冲突、阶段承诺点"
              />
            </label>
            <label style={{ marginTop: 8 }}>
              世界观/关键设定
              <textarea
                rows={3}
                value={storySetting}
                onChange={(e) => setStorySetting(e.target.value)}
                placeholder="规则、组织、能力代价、限制条件"
              />
            </label>
            <div className="row" style={{ marginTop: 8 }}>
              <button onClick={() => void saveWritingBrief()} disabled={!bookId || writerStudioBusy}>
                保存简报
              </button>
              <button onClick={() => void loadWritingBrief()} disabled={!bookId || writerStudioBusy}>
                读取简报
              </button>
            </div>
            <div className="small" style={{ marginTop: 8 }}>
              简报会写入书籍设置，可用于后续卷纲/章纲自动生成。
            </div>
            <div className="splitbook-step-card" style={{ marginTop: 10 }}>
              <div className="row">
                <strong>1.2A) 素材库（可选增强）</strong>
                <span className="small">可手动添加素材，也可从拆书结构提取素材卡</span>
              </div>
              <div className="row" style={{ marginTop: 8, gap: 8, flexWrap: "wrap" }}>
                <button onClick={() => openOptionalPanel("ref")}>打开素材库/引用中心</button>
                <button
                  onClick={() => void importMaterialsFromCurrentSplitbook()}
                  disabled={!bookId || writingMaterialImportBusy || (!writingSplitbookRefId && !selectedSplitbookId)}
                >
                  {writingMaterialImportBusy ? "提取中..." : "从当前拆书提取素材"}
                </button>
              </div>
              <div className="row" style={{ marginTop: 8, gap: 8, flexWrap: "wrap" }}>
                <input
                  value={writingMaterialQuickNote}
                  onChange={(e) => setWritingMaterialQuickNote(e.target.value)}
                  placeholder="快速添加素材备注（例如：本卷反派动机是资源垄断）"
                />
                <button onClick={() => addQuickMaterialRefNote()} disabled={!writingMaterialQuickNote.trim()}>
                  加入本次生成素材
                </button>
              </div>
              <div className="small" style={{ marginTop: 6 }}>
                当前已注入素材引用：{materialRefs.length} 条
              </div>
            </div>
            <hr style={{ margin: "10px 0" }} />
            <h4 id="section-writing-step-1-2" style={{ margin: "0 0 8px" }}>1.2) 总纲（全书级）</h4>
            <label>
              总纲摘要
              <textarea
                rows={4}
                value={masterOutlineSummary}
                onChange={(e) => setMasterOutlineSummary(e.target.value)}
                placeholder="填写全书主线、终局承诺、阶段推进逻辑（可融合拆书结构但不引用原文）"
              />
            </label>
            <div className="quick-form-grid" style={{ marginTop: 8 }}>
              <label>
                计划章节总数
                <input
                  type="number"
                  min={1}
                  max={9999}
                  value={masterOutlinePlannedChapters || 0}
                  onChange={(e) => setMasterOutlinePlannedChapters(Math.max(0, Number(e.target.value) || 0))}
                />
              </label>
              <label>
                章纲统计（只读）
                <input value={masterOutlineChapterTotal > 0 ? `${masterOutlineChapterTotal} 章` : "未设定"} readOnly />
              </label>
            </div>
            <div className="small" style={{ marginTop: 6 }}>
              当前章节定位：{selectedChapterNo > 0 ? `第 ${selectedChapterNo} 章` : "未选择章节"}；已建章节：{chapterItems.length} 章
              </div>
              <div className="row" style={{ marginTop: 8, gap: 8, flexWrap: "wrap" }}>
                <button onClick={() => void generateMasterOutlineAuto()} disabled={!bookId || masterOutlineBusy || writerStudioBusy}>
                  {masterOutlineBusy ? "生成中..." : "AI 自动生成总纲（可融合拆书结构）"}
                </button>
                <button onClick={() => void saveMasterOutline()} disabled={!bookId || masterOutlineBusy || writerStudioBusy}>
                  {masterOutlineBusy ? "保存中..." : "保存总纲"}
                </button>
                <button onClick={() => void loadWritingBrief()} disabled={!bookId || masterOutlineBusy || writerStudioBusy}>
                  刷新总纲
                </button>
              </div>
              <div className="small" style={{ marginTop: 6 }}>
                状态：{masterOutlineReady ? `已就绪（计划 ${masterOutlineChapterTotal || 0} 章）` : "未就绪，请先保存总纲"}
              </div>
              <div className="small" style={{ marginTop: 4 }}>
                生成依据：
                {masterOutlineAiMeta
                  ? `${formatMasterOutlineBasis(masterOutlineAiMeta)}${
                      Number(masterOutlineAiMeta?.structure_hints_applied || 0) > 0
                        ? `（结构提示 ${Number(masterOutlineAiMeta?.structure_hints_applied || 0)} 条）`
                        : ""
                    }`
                  : "手动草案（可点击“AI 自动生成总纲”获得可追溯依据）"}
              </div>
              {masterOutlineAiMeta ? (
                <div className="small" style={{ marginTop: 4 }}>
                  模型：{String(masterOutlineAiMeta?.model || "未记录")}
                  {Array.isArray(masterOutlineAiMeta?.structure_hint_sources) && masterOutlineAiMeta.structure_hint_sources.length
                    ? ` · 提示来源：${masterOutlineAiMeta.structure_hint_sources.slice(0, 3).join(" / ")}`
                    : ""}
                  {masterOutlineAiMeta?.db_context
                    ? ` · 数据库上下文：章节 ${Number(masterOutlineAiMeta?.db_context?.chapter_count || 0)} / 卷 ${Number(masterOutlineAiMeta?.db_context?.volume_count || 0)}`
                    : ""}
                  {masterOutlineAiMeta?.splitbook_outline_reference
                    ? ` · 拆书结构参考：章节 ${Number(masterOutlineAiMeta?.splitbook_outline_reference?.chapter_total || 0)} / 阶段 ${Number(masterOutlineAiMeta?.splitbook_outline_reference?.phase_count || 0)}`
                    : ""}
                  {String(masterOutlineAiMeta?.prompt_template_source || "").trim()
                    ? ` · 提示词模板：${String(masterOutlineAiMeta?.prompt_template_source || "").trim()}`
                    : ""}
                  {String(masterOutlineAiMeta?.structure_hint_mode || "") === "tag_only" ? " · 结构输入：仅标签抽象（防照抄）" : ""}
                  {Number(masterOutlineAiMeta?.brief_protected_lines || 0) > 0
                    ? ` · 简报防复述行：${Number(masterOutlineAiMeta?.brief_protected_lines || 0)}`
                    : ""}
                  {Number(masterOutlineAiMeta?.material_guidance_count || 0) > 0
                    ? ` · 素材要点：${Number(masterOutlineAiMeta?.material_guidance_count || 0)}`
                    : ""}
                  {Number(masterOutlineAiMeta?.material_library_count || 0) > 0
                    ? ` · 素材库命中：${Number(masterOutlineAiMeta?.material_library_count || 0)}`
                    : ""}
                  {masterOutlineAiMeta?.anti_copy_guard_triggered
                    ? ` · 防抄袭保护已触发（${Array.isArray(masterOutlineAiMeta?.anti_copy_rewritten_fields) ? masterOutlineAiMeta.anti_copy_rewritten_fields.join(" / ") : "已重写"}）`
                    : ""}
                </div>
              ) : null}
            </div>

          <div id="section-writing-step-1-3-1-4" className="quickstart-card quickstart-actions">
            <h4>1.3) 卷纲 + 1.4) 章纲（结构迭代）</h4>
            <label>
              卷（Volume）
              <select value={quickVolumeId} onChange={(e) => setQuickVolumeId(e.target.value)} disabled={!bookId}>
                <option value="">请选择卷</option>
                {volumeItems.map((vol: any) => (
                  <option key={String(vol.volume_id)} value={String(vol.volume_id)}>
                    {String(vol.title || vol.volume_id)}
                  </option>
                ))}
              </select>
            </label>
            <div className="small" style={{ marginTop: 8 }}>
              主链路顺序：<strong>1.2 总纲</strong> → <strong>1.3 卷纲</strong> → <strong>1.4 章纲</strong> → <strong>1.5 章节生成</strong>
            </div>
            <div className="small" style={{ marginTop: 4 }}>
              你现在所在模块：<strong>1.3/1.4</strong>（执行 1.3.1~1.4.2 即完成卷纲与章纲迭代）
            </div>
            <div className="small" style={{ marginTop: 4 }}>
              子步骤：<strong>1.3.1 AI 生成卷纲草案</strong> → <strong>1.3.2 AI 优化并应用卷纲</strong> → <strong>1.4.1 AI 生成章纲草案</strong> → <strong>1.4.2 控制计划细化</strong>
            </div>
            <div className="small" style={{ marginTop: 4 }}>
              结构融合状态：{splitbookStructureRefCount > 0 ? `已启用（${splitbookStructureRefCount} 条拆书结构引用，将用于 1.3.1~1.4.2）` : "未启用（仅使用书籍简报）"}；卷纲/章纲会参考数据库中的拆书结构统计。
            </div>
            <div className="small" style={{ marginTop: 4 }}>
              章纲注入写作引擎：{outlineInjectStatus.message}
              {outlineInjectStatus.version > 0 ? `（v${outlineInjectStatus.version}，节点 ${outlineInjectStatus.nodeCount}）` : ""}
            </div>
            <div className="small" style={{ marginTop: 4 }}>
              章纲规模：计划 {masterOutlineChapterTotal > 0 ? masterOutlineChapterTotal : "-"} 章；当前已建 {chapterItems.length} 章。
            </div>
            <div className="row" style={{ gap: 8, marginTop: 8, flexWrap: "wrap" }}>
              <button
                onClick={() => void runStructurePipelineOneClick()}
                disabled={!bookId || !masterOutlineReady || structurePipelineBusy || writerStudioBusy || busy}
              >
                {structurePipelineBusy ? `结构一键执行中：${structureCurrentStepLabel}` : "一键执行 1.3 → 1.4"}
              </button>
              <button
                onClick={() => void runStructurePipelineWithSplitbookFusion()}
                disabled={!bookId || !masterOutlineReady || structurePipelineBusy || writerStudioBusy || busy}
              >
                {structurePipelineBusy ? "融合流程执行中..." : "一键结构融合（拆书→1.3~1.4）"}
              </button>
              <span className="small">进度：{structureProgressPct}% · 当前：{structureCurrentStepLabel}</span>
            </div>
            <div className="pipeline-progress" style={{ marginTop: 6 }}>
              <span style={{ width: `${structureProgressPct}%` }} />
            </div>
            {structurePipelineError ? <div className="small danger">一键执行异常：{structurePipelineError}</div> : null}
            <div className="core-step-list" style={{ marginTop: 8 }}>
              <div className={`core-step ${structureStepStatusMap.volume_preview === "running" ? "active" : ""}`}>
                <strong>1.3.1</strong>
                <span>生成卷纲草案</span>
                <span className="small">产出：卷纲预览（volumePlanPreview）</span>
                <span className="small">{formatPipelineStatus(structureStepStatusMap.volume_preview)}</span>
                <span className="small">
                  依据：{structureStepBasis["1.3.1"].basis} · {formatStructureStepStatusLabel(structureStepBasis["1.3.1"].status)}
                  {structureStepBasis["1.3.1"].updatedAt
                    ? `（${new Date(structureStepBasis["1.3.1"].updatedAt).toLocaleTimeString("zh-CN", { hour12: false })}）`
                    : ""}
                </span>
                {structureStepBasis["1.3.1"].detail ? <span className="small">结果：{structureStepBasis["1.3.1"].detail}</span> : null}
                <button
                  onClick={() => void generateVolumePlanPreview()}
                  disabled={!bookId || writerStudioBusy || structurePipelineBusy}
                >
                    执行 1.3.1
                </button>
              </div>
              <div className={`core-step ${structureStepStatusMap.volume_apply === "running" ? "active" : ""}`}>
                <strong>1.3.2</strong>
                <span>应用卷纲（将草案写入卷）</span>
                <span className="small">产出：卷纲应用结果（volumePlanApplied）</span>
                <span className="small">{formatPipelineStatus(structureStepStatusMap.volume_apply)}</span>
                <span className="small">
                  依据：{structureStepBasis["1.3.2"].basis} · {formatStructureStepStatusLabel(structureStepBasis["1.3.2"].status)}
                  {structureStepBasis["1.3.2"].updatedAt
                    ? `（${new Date(structureStepBasis["1.3.2"].updatedAt).toLocaleTimeString("zh-CN", { hour12: false })}）`
                    : ""}
                </span>
                {structureStepBasis["1.3.2"].detail ? <span className="small">结果：{structureStepBasis["1.3.2"].detail}</span> : null}
                <button
                  onClick={() => void applyVolumePlanAuto()}
                  disabled={!bookId || writerStudioBusy || structurePipelineBusy}
                >
                    执行 1.3.2
                </button>
              </div>
              <div className={`core-step ${structureStepStatusMap.chapter_seed === "running" ? "active" : ""}`}>
                <strong>1.4.1</strong>
                <span>生成章纲草案（写入当前章节）</span>
                <span className="small">产出：章节节点草案（chapterOutlineSeed）</span>
                <span className="small">{formatPipelineStatus(structureStepStatusMap.chapter_seed)}</span>
                <span className="small">
                  依据：{structureStepBasis["1.4.1"].basis} · {formatStructureStepStatusLabel(structureStepBasis["1.4.1"].status)}
                  {structureStepBasis["1.4.1"].updatedAt
                    ? `（${new Date(structureStepBasis["1.4.1"].updatedAt).toLocaleTimeString("zh-CN", { hour12: false })}）`
                    : ""}
                </span>
                {structureStepBasis["1.4.1"].detail ? <span className="small">结果：{structureStepBasis["1.4.1"].detail}</span> : null}
                <button
                  onClick={() => void generateChapterOutlineSeed()}
                  disabled={!bookId || writerStudioBusy || structurePipelineBusy}
                >
                    执行 1.4.1
                </button>
              </div>
              <div className={`core-step ${structureStepStatusMap.control_plan === "running" ? "active" : ""}`}>
                <strong>1.4.2</strong>
                <span>控制计划细化（生成补丁）</span>
                <span className="small">对应任务：张力修复规划（control_plan.tension.v1）</span>
                <span className="small">{formatPipelineStatus(structureStepStatusMap.control_plan)}</span>
                <span className="small">
                  依据：{structureStepBasis["1.4.2"].basis} · {formatStructureStepStatusLabel(structureStepBasis["1.4.2"].status)}
                  {structureStepBasis["1.4.2"].updatedAt
                    ? `（${new Date(structureStepBasis["1.4.2"].updatedAt).toLocaleTimeString("zh-CN", { hour12: false })}）`
                    : ""}
                </span>
                {structureStepBasis["1.4.2"].detail ? <span className="small">结果：{structureStepBasis["1.4.2"].detail}</span> : null}
                <button onClick={() => void runControlPlan()} disabled={busy || !outline || structurePipelineBusy}>
                  执行 1.4.2{splitbookStructureRefCount > 0 ? `（含结构引用 ${splitbookStructureRefCount}）` : ""}
                </button>
              </div>
            </div>
            <div className="splitbook-step-card" style={{ marginTop: 10 }}>
              <div className="row">
                <strong>结构修订工具（1.3/1.4）</strong>
                <span className="small">章纲调优 / 补丁应用 / 版本对比</span>
              </div>
              <div className="small" style={{ marginTop: 4 }}>
                说明：这里集中处理“评估 → 控制计划 → 应用补丁 → 对比”，避免与主链路按钮混在一起。
              </div>
              <div className="row" style={{ marginTop: 8, gap: 8, flexWrap: "wrap" }}>
                <button onClick={() => void runEval()} disabled={busy || !outline}>评估（Eval）</button>
                <button onClick={() => void runControlPlan()} disabled={busy || !outline}>控制计划（Control Plan）</button>
                <button onClick={applySelectedPatches} disabled={busy || !planRun}>应用已选补丁</button>
                <button
                  onClick={() => {
                    setCompareOpen(true);
                    setCompareUnread(false);
                  }}
                  disabled={!chapterId}
                  style={{ position: "relative" }}
                >
                  对比（Compare）
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
              </div>
            </div>
            <div className="splitbook-step-card" style={{ marginTop: 10 }}>
              <div className="row">
                <strong>1.4 章纲总览（逐章确认）</strong>
                <span className="small">
                  共 {chapterItems.length} 章 · 已生成章纲 {chapterOutlineDoneCount} 章
                </span>
              </div>
              <div className="small" style={{ marginTop: 4 }}>
                说明：这里按章节逐条展示章纲状态；支持定位、预览与删除最新章纲，并可直接执行 1.4.1（生成章纲草案）。
              </div>
              <div className="row" style={{ marginTop: 8, gap: 8, flexWrap: "wrap" }}>
                <button
                  onClick={() => void loadChapterOutlineOverview(undefined, { silent: false })}
                  disabled={!bookId || chapterOutlineOverviewLoading}
                >
                  {chapterOutlineOverviewLoading ? "章纲总览刷新中..." : "刷新章纲总览"}
                </button>
                <span className="small">
                  计划章节：{masterOutlineChapterTotal > 0 ? masterOutlineChapterTotal : "未设定"}；当前已建：{chapterItems.length}
                </span>
              </div>
              <div className="scroll" style={{ maxHeight: 260, marginTop: 8 }}>
                {chapterOutlineOverview.length === 0 ? (
                  <div className="small">暂无章节章纲数据，请先创建章节并点击“刷新章纲总览”。</div>
                ) : (
                  chapterOutlineOverview.map((item) => (
                    <div
                      key={`outline-overview-${item.chapterId}`}
                      className={`node-item ${String(chapterId || "") === String(item.chapterId) ? "active" : ""}`}
                      style={{ marginBottom: 6 }}
                    >
                      <div className="row" style={{ width: "100%", justifyContent: "space-between", gap: 10 }}>
                        <strong>第{item.chapterNo || "?"}章 · {item.title || "未命名章节"}</strong>
                        <code>{item.outlineVersion > 0 ? `章纲 v${item.outlineVersion}` : "未生成章纲"}</code>
                      </div>
                      <div className="small" style={{ marginTop: 4 }}>
                        {item.outlineVersion > 0
                          ? `${item.outlineNodes > 0 ? `节点 ${item.outlineNodes} · ` : ""}${item.outlineSummary || "已生成章纲（可进入节点编辑查看详情）"}`
                          : "当前章节还没有章纲草案。"}
                        {item.updatedAt
                          ? ` · 更新时间 ${new Date(item.updatedAt).toLocaleString("zh-CN", { hour12: false })}`
                          : ""}
                        {item.loadError ? ` · ${item.loadError}` : ""}
                      </div>
                      <div className="row" style={{ marginTop: 6, gap: 8, flexWrap: "wrap" }}>
                        <button
                          onClick={() => setChapterId(item.chapterId)}
                          disabled={!bookId}
                        >
                          定位本章
                        </button>
                        <button
                          onClick={() => void previewChapterOutlineFromOverview(item)}
                          disabled={
                            !bookId ||
                            chapterOutlinePreviewBusyId === item.chapterId ||
                            chapterOutlineDeleteBusyId === item.chapterId
                          }
                        >
                          {chapterOutlinePreviewBusyId === item.chapterId ? "预览中..." : "预览章纲"}
                        </button>
                        <button
                          onClick={() => void generateChapterOutlineSeed({ chapterId: item.chapterId })}
                          disabled={
                            !bookId ||
                            writerStudioBusy ||
                            structurePipelineBusy ||
                            chapterOutlineDeleteBusyId === item.chapterId
                          }
                        >
                          生成本章章纲（1.4.1）
                        </button>
                        <button
                          onClick={() => void deleteChapterOutlineFromOverview(item)}
                          disabled={
                            !bookId ||
                            Number(item.outlineVersion || 0) <= 0 ||
                            chapterOutlineDeleteBusyId === item.chapterId ||
                            chapterOutlinePreviewBusyId === item.chapterId
                          }
                        >
                          {chapterOutlineDeleteBusyId === item.chapterId ? "删除中..." : "删除章纲"}
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
            <div className="splitbook-step-card" style={{ marginTop: 10 }}>
              <div className="row">
                <strong>1.4.3 注入拆书结构（防抄袭）</strong>
                <span className="small">只注入结构/冲突/伏笔策略，不注入原文内容</span>
              </div>
              <div className="quick-form-grid" style={{ marginTop: 8 }}>
                <label>
                  来源拆书
                  <select
                    value={writingSplitbookRefId}
                    onChange={(e) => setWritingSplitbookRefId(e.target.value)}
                    disabled={writingSplitbookRefBusy}
                  >
                    <option value="">请选择拆书</option>
                    {splitbooks.map((sb) => (
                      <option key={`wsb-${sb.splitbook_id}`} value={sb.splitbook_id}>
                        {sb.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  引用范围
                  <select
                    value={writingSplitbookRefScope}
                    onChange={(e) => setWritingSplitbookRefScope((e.target.value as "book" | "chapter") || "book")}
                    disabled={writingSplitbookRefBusy}
                  >
                    <option value="book">全书结构（推荐）</option>
                    <option value="chapter">单章结构（可选）</option>
                  </select>
                </label>
                {writingSplitbookRefScope === "chapter" ? (
                  <label>
                    单章章节号
                    <input
                      type="number"
                      min={1}
                      value={writingSplitbookRefChapterNo}
                      onChange={(e) => setWritingSplitbookRefChapterNo(Math.max(1, Number(e.target.value) || 1))}
                      disabled={writingSplitbookRefBusy}
                    />
                  </label>
                ) : null}
              </div>
              <div className="small" style={{ marginTop: 6 }}>
                当前引用模式：<strong>{splitbookStructureRefModeText}</strong>
                {splitbookStructureRefSourceList.length ? ` · 来源：${splitbookStructureRefSourceList.join(" / ")}` : ""}
              </div>
              <div className="small">
                约束规则：仅可借结构机制；禁止复述原文；禁止沿用原叙事顺序；必须重建人物动机/场景/因果链。
              </div>
              <div className="row" style={{ marginTop: 8, gap: 8, flexWrap: "wrap" }}>
                <button
                  onClick={() => void injectSplitbookStructureRefToWriting()}
                  disabled={!bookId || !chapterId || !writingSplitbookRefId || writingSplitbookRefBusy}
                >
                  {writingSplitbookRefBusy ? "注入中..." : "执行 1.4.3 注入结构引用"}
                </button>
                <button onClick={() => clearSplitbookStructureRefs()} disabled={writingSplitbookRefBusy || splitbookStructureRefCount === 0}>
                  清空拆书结构引用
                </button>
                <button onClick={() => void loadSplitbooks({ sync: true })} disabled={writingSplitbookRefBusy}>
                  刷新拆书列表
                </button>
              </div>
              <div className="small" style={{ marginTop: 6 }}>
                已注入结构引用：{splitbookStructureRefCount} 条（这些内容会作为控制计划输入 `material_refs` 一并提交）
              </div>
              {writingSplitbookRefLast ? (
                <div className="small" style={{ marginTop: 4 }}>
                  最近注入：{writingSplitbookRefLast.splitbookName}{" "}
                  {writingSplitbookRefLast.scope === "chapter"
                    ? `单章第${Number(writingSplitbookRefLast.chapterNo || 0)}章`
                    : "全书结构"}{" "}
                  · 冲突 {writingSplitbookRefLast.conflicts} · 伏笔 {writingSplitbookRefLast.foreshadow} · 回收 {writingSplitbookRefLast.payoff} ·{" "}
                  {writingSplitbookRefLast.injectedAt}
                </div>
              ) : null}
            </div>
            <div className="small">
              当前章节：{selectedChapterItem ? `第${selectedChapterItem.chapter_no}章 · ${selectedChapterItem.title}` : "未选择"}
            </div>
            <div className="small">
              当前卷：{selectedVolumeItem ? String(selectedVolumeItem.title || selectedVolumeItem.volume_id) : "未选择"}
            </div>
            {!writerSimpleMode && volumePlanPreview ? (
              <details data-auto-expand-key="true">
                <summary>卷纲草案预览（调试）</summary>
                <pre>{JSON.stringify(volumePlanPreview, null, 2)}</pre>
              </details>
            ) : null}
            {!writerSimpleMode && volumePlanApplied ? (
              <details data-auto-expand-key="true">
                <summary>卷纲应用结果（调试）</summary>
                <pre>{JSON.stringify(volumePlanApplied, null, 2)}</pre>
              </details>
            ) : null}
            {!writerSimpleMode && chapterOutlineSeed ? (
              <details data-auto-expand-key="true">
                <summary>章纲草案预览（调试）</summary>
                <pre>{JSON.stringify(chapterOutlineSeed, null, 2)}</pre>
              </details>
            ) : null}
          </div>
          <div id="section-writing-step-1-5" className="quickstart-card">
            <h4>1.5) 章节生成（按章纲）</h4>
            <div className="small" style={{ marginBottom: 8 }}>
              作用：基于总纲+卷纲+章纲执行 AI 正文生成，支持单章或 1~5 章批量生成（目标不少于 3000 字符/章）。
            </div>
            <div className="quick-status-grid">
              <div className="summary-card">
                <div className="k">当前章节</div>
                <div className="v">{selectedChapterItem ? `第${selectedChapterItem.chapter_no}章` : "未选择"}</div>
              </div>
              <div className="summary-card">
                <div className="k">章节生成状态</div>
                <div className="v">{closedLoopBusy ? "执行中" : closedLoopOutput?.ok ? "最近一次成功" : "未执行/失败"}</div>
              </div>
              <div className="summary-card">
                <div className="k">可批量范围</div>
                <div className="v">1 ~ 5 章</div>
              </div>
              <div className="summary-card">
                <div className="k">本次生成模式</div>
                <div className="v">{chapterGenerationTrace.mode === "batch" ? "批量" : "单章"}</div>
              </div>
            </div>
            <div className="row" style={{ marginTop: 8, gap: 8, flexWrap: "wrap" }}>
              <button onClick={() => void runClosedLoopFlow()} disabled={closedLoopBusy || quickPipelineBusy || batchGenerateBusy || !bookId || !chapterId}>
                {closedLoopBusy ? "章节生成中..." : "执行 1.5 单章生成"}
              </button>
              <label className="small" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                批量章数
                <input
                  style={{ width: 66 }}
                  type="number"
                  min={1}
                  max={5}
                  value={batchGenerateCount}
                  onChange={(e) => setBatchGenerateCount(Math.max(1, Math.min(5, Number(e.target.value) || 1)))}
                  disabled={batchGenerateBusy || closedLoopBusy}
                />
              </label>
              <button
                onClick={() => void runBatchClosedLoopGeneration()}
                disabled={batchGenerateBusy || closedLoopBusy || !bookId || !chapterId}
              >
                {batchGenerateBusy ? "批量生成中..." : `执行 1.5 批量生成 ${Math.max(1, Math.min(5, Number(batchGenerateCount || 1)))} 章`}
              </button>
            </div>
            <div className="small" style={{ marginTop: 6 }}>
              生成依据：{chapterGenerationTrace.basis || "待执行"}
            </div>
            <div className="small" style={{ marginTop: 4 }}>
              目标章节：{chapterGenerationTrace.chapters || (selectedChapterItem ? `第${selectedChapterItem.chapter_no}章` : "未选择")}
            </div>
            <div className="small" style={{ marginTop: 4 }}>
              最近结果：{formatStructureStepStatusLabel(chapterGenerationTrace.status)}
              {chapterGenerationTrace.detail ? ` · ${chapterGenerationTrace.detail}` : ""}
              {chapterGenerationTrace.updatedAt
                ? ` · ${new Date(chapterGenerationTrace.updatedAt).toLocaleTimeString("zh-CN", { hour12: false })}`
                : ""}
            </div>
            <div className="small" style={{ marginTop: 6 }}>
              说明：生成时会自动参考总纲、卷纲、章纲与注入的结构约束（不引用拆书原文）。
            </div>
            <div className="splitbook-step-card" style={{ marginTop: 10 }}>
              <div className="row">
                <strong>自写章节导入（强覆盖）</strong>
                <span className="small">权限：导入后将直接成为当前章节的激活草稿 + 已选草稿 + 正文版本</span>
              </div>
              <div className="row" style={{ marginTop: 8, gap: 8, flexWrap: "wrap" }}>
                <input
                  value={manualChapterImportNote}
                  onChange={(e) => setManualChapterImportNote(e.target.value)}
                  placeholder="导入备注（可选）"
                  style={{ minWidth: 280 }}
                  disabled={manualChapterImportBusy}
                />
                <button
                  onClick={() => void importManualChapterText()}
                  disabled={manualChapterImportBusy || !chapterId || !String(manualChapterImportText || "").trim()}
                >
                  {manualChapterImportBusy ? "导入中..." : "导入并覆盖当前章节"}
                </button>
                <button
                  onClick={() => setManualChapterImportText("")}
                  disabled={manualChapterImportBusy || !manualChapterImportText}
                >
                  清空文本
                </button>
              </div>
              <textarea
                style={{ marginTop: 8 }}
                rows={8}
                value={manualChapterImportText}
                onChange={(e) => setManualChapterImportText(e.target.value)}
                placeholder="粘贴你的自写章节正文。导入后会直接替换当前章节的激活草稿与已选草稿。"
                disabled={manualChapterImportBusy}
              />
            </div>
            <div className="splitbook-step-card" style={{ marginTop: 10 }}>
              <div className="row">
                <strong>章节正文预览</strong>
                <span className="small">
                  {chapterDraftPreviewDraftId
                    ? `草稿 ${chapterDraftPreviewDraftId.slice(0, 8)}...`
                    : "未加载正文"}
                  {chapterDraftPreviewSource === "text_version" ? " · 来源：正文版本" : chapterDraftPreviewSource === "draft" ? " · 来源：草稿" : ""}
                  {chapterDraftPreviewDirty ? " · 未保存修改" : ""}
                  {chapterDraftPreviewUpdatedAt
                    ? ` · ${new Date(chapterDraftPreviewUpdatedAt).toLocaleString("zh-CN", { hour12: false })}`
                    : ""}
                </span>
              </div>
              <div className="row" style={{ marginTop: 8, gap: 8, flexWrap: "wrap" }}>
                <button
                  onClick={() => void loadDraftPreviewById("", { silent: false })}
                  disabled={chapterDraftPreviewLoading || !chapterId}
                >
                  {chapterDraftPreviewLoading ? "正文加载中..." : "查看最新章节正文"}
                </button>
                <button
                  onClick={() => void saveChapterDraftPreviewText()}
                  disabled={chapterDraftPreviewLoading || !chapterId || !chapterDraftPreviewText.trim() || !chapterDraftPreviewDirty}
                >
                  {chapterDraftPreviewLoading ? "保存中..." : chapterDraftPreviewDirty ? "保存正文并激活" : "正文已保存"}
                </button>
                <button
                  onClick={() => void openCurrentChapterOutlinePreview()}
                  disabled={chapterDraftPreviewLoading || !chapterId}
                >
                  同步预览本章章纲
                </button>
                <button
                  onClick={() => jumpToSelectedOutlineNodeInDraftPreview()}
                  disabled={chapterDraftPreviewLoading || !chapterDraftPreviewText || !selectedNode}
                >
                  按当前节点定位正文
                </button>
                <button
                  onClick={() => {
                    setChapterDraftPreviewText("");
                    setChapterDraftPreviewDraftId("");
                    setChapterDraftPreviewSource("");
                    setChapterDraftPreviewUpdatedAt("");
                    setChapterDraftPreviewDirty(false);
                  }}
                  disabled={chapterDraftPreviewLoading || !chapterDraftPreviewText}
                >
                  清空预览
                </button>
              </div>
              {chapterDraftPreviewText ? (
                <textarea
                  ref={chapterDraftPreviewTextRef}
                  style={{ marginTop: 8 }}
                  rows={12}
                  value={chapterDraftPreviewText}
                  onChange={(e) => {
                    setChapterDraftPreviewText(e.target.value);
                    setChapterDraftPreviewDirty(true);
                  }}
                />
              ) : (
                <div className="small" style={{ marginTop: 8 }}>
                  暂无正文内容。请先执行 1.5 生成，然后点击“查看最新章节正文”。
                </div>
              )}
            </div>
          </div>
          <div className="quickstart-card">
            <h4>AI 调用明细（调试）</h4>
            <div className="small" style={{ marginBottom: 8 }}>
              用于排查“AI 生成用了哪些数据、提示词是什么”，并确认 1.2~1.5 是否均由 AI 驱动。
            </div>
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <button onClick={() => void loadAiDebugInfo()} disabled={aiDebugBusy || !bookId}>
                {aiDebugBusy ? "刷新中..." : "刷新 AI 调用明细"}
              </button>
              <button
                onClick={() => {
                  setAiDebugData(null);
                  setAiDebugError("");
                }}
                disabled={aiDebugBusy || (!aiDebugData && !aiDebugError)}
              >
                清空明细
              </button>
            </div>
            {aiDebugError ? (
              <div className="small" style={{ marginTop: 6, color: "#7f1d1d" }}>
                加载失败：{aiDebugError}
              </div>
            ) : null}
            <details style={{ marginTop: 8 }} open>
              <summary>AI 达标审计（1.2~1.5）</summary>
              {aiCompliance?.stages && typeof aiCompliance.stages === "object" ? (
                <div style={{ marginTop: 6, display: "grid", gap: 6 }}>
                  {Object.entries(aiCompliance.stages as Record<string, any>).map(([step, item]) => (
                    <div key={step} className="small" style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: "6px 8px" }}>
                      <strong>{step} {String(item?.label || "")}</strong>
                      {" · "}
                      <span style={{ color: item?.ok ? "#065f46" : "#7f1d1d" }}>{item?.ok ? "已达标" : "未达标"}</span>
                      {" · "}
                      需 AI：{item?.required_ai ? "是" : "否"}
                      {!item?.ok && item?.reason ? (
                        <div style={{ marginTop: 4, color: "#7f1d1d" }}>原因：{String(item.reason)}</div>
                      ) : null}
                    </div>
                  ))}
                  <div className="small">
                    总体结论：<strong style={{ color: aiCompliance?.overall_ok ? "#065f46" : "#7f1d1d" }}>
                      {aiCompliance?.overall_ok ? "已达标" : "未达标"}
                    </strong>
                  </div>
                </div>
              ) : (
                <div className="small" style={{ marginTop: 6 }}>
                  暂无审计结果。请先执行 1.2~1.5 中至少一步后刷新。
                </div>
              )}
            </details>
            <details style={{ marginTop: 8 }}>
              <summary>1.2 总纲 AI 调用</summary>
              {aiDebugMaster ? (
                <>
                  <div className="small" style={{ marginTop: 6 }}>
                    模型：{String(aiDebugMaster?.model || "未记录")} · 数据键：{summarizePromptPayload(aiDebugMaster?.prompt_payload)} · 时间：
                    {String(aiDebugMaster?.generated_at || "未记录")}
                  </div>
                  <details style={{ marginTop: 6 }}>
                    <summary>查看 Prompt Payload(JSON)</summary>
                    <textarea rows={8} readOnly value={toPrettyJsonText(aiDebugMaster?.prompt_payload)} />
                  </details>
                  <details style={{ marginTop: 6 }}>
                    <summary>查看 System Prompt</summary>
                    <textarea rows={7} readOnly value={toPrettyJsonText(aiDebugMaster?.system_prompt)} />
                  </details>
                  <details style={{ marginTop: 6 }}>
                    <summary>查看 User Prompt</summary>
                    <textarea rows={8} readOnly value={toPrettyJsonText(aiDebugMaster?.user_prompt)} />
                  </details>
                </>
              ) : (
                <div className="small" style={{ marginTop: 6 }}>
                  暂无总纲 AI 调用记录。请先执行 1.2。
                </div>
              )}
            </details>
            <details style={{ marginTop: 8 }}>
              <summary>1.3 卷纲 AI 调用</summary>
              {aiDebugVolumePlan?.ai_refine && typeof aiDebugVolumePlan.ai_refine === "object" ? (
                <div className="small" style={{ marginTop: 6 }}>
                  卷：{String(aiDebugVolumePlan?.volume_no || "-")} {String(aiDebugVolumePlan?.title || "")} ·
                  AI refine：{aiDebugVolumePlan?.ai_refine?.enabled ? "已启用" : "未启用"} ·
                  采样条目：{Number(aiDebugVolumePlan?.ai_refine?.sample_size || 0)} ·
                  变更条目：{Number(aiDebugVolumePlan?.ai_refine?.changed_items || 0)}
                </div>
              ) : (
                <div className="small" style={{ marginTop: 6 }}>
                  暂无卷纲 AI 调用记录。请先执行 1.3。
                </div>
              )}
            </details>
            <details style={{ marginTop: 8 }}>
              <summary>1.4 章纲 AI 调用</summary>
              {aiDebugChapter ? (
                <>
                  <div className="small" style={{ marginTop: 6 }}>
                    模型：{String(aiDebugChapter?.model || "未记录")} · 数据键：{summarizePromptPayload(aiDebugChapter?.prompt_payload)} · 时间：
                    {String(aiDebugChapter?.generated_at || "未记录")}
                  </div>
                  <details style={{ marginTop: 6 }}>
                    <summary>查看 Prompt Payload(JSON)</summary>
                    <textarea rows={8} readOnly value={toPrettyJsonText(aiDebugChapter?.prompt_payload)} />
                  </details>
                  <details style={{ marginTop: 6 }}>
                    <summary>查看 System Prompt</summary>
                    <textarea rows={7} readOnly value={toPrettyJsonText(aiDebugChapter?.system_prompt)} />
                  </details>
                  <details style={{ marginTop: 6 }}>
                    <summary>查看 User Prompt</summary>
                    <textarea rows={8} readOnly value={toPrettyJsonText(aiDebugChapter?.user_prompt)} />
                  </details>
                </>
              ) : (
                <div className="small" style={{ marginTop: 6 }}>
                  暂无章纲 AI 调用记录。请先执行 1.4。
                </div>
              )}
            </details>
            <details style={{ marginTop: 8 }}>
              <summary>1.5 正文生成调用链</summary>
              {aiDebugDraft?.run ? (
                <>
                  <div className="small" style={{ marginTop: 6 }}>
                    Run：{String(aiDebugDraft?.run?.run_id || "未记录")} · 状态：{String(aiDebugDraft?.run?.status || "未知")} · 模型：
                    {String(aiDebugDraft?.llm_generate?.model || "未记录")} · 估算 Token：
                    {Number(aiDebugDraft?.llm_generate?.tokens_in_est || 0)} / {Number(aiDebugDraft?.llm_generate?.tokens_out_est || 0)}
                  </div>
                  <details style={{ marginTop: 6 }}>
                    <summary>查看 Compose Prompt（最终发送给正文生成的主提示词）</summary>
                    <textarea rows={10} readOnly value={toPrettyJsonText(aiDebugDraft?.compose_prompt?.prompt)} />
                  </details>
                  <details style={{ marginTop: 6 }}>
                    <summary>查看 Compose Prompt Blocks（结构化输入数据）</summary>
                    <textarea rows={10} readOnly value={toPrettyJsonText(aiDebugDraft?.compose_prompt?.prompt_blocks)} />
                  </details>
                  <details style={{ marginTop: 6 }}>
                    <summary>查看 LLM 节点输入参数</summary>
                    <textarea rows={6} readOnly value={toPrettyJsonText(aiDebugDraft?.llm_generate?.input)} />
                  </details>
                </>
              ) : (
                <div className="small" style={{ marginTop: 6 }}>
                  暂无 1.5 调用链记录。请先执行 1.5。
                </div>
              )}
            </details>
          </div>
          <div className="quickstart-card">
            <h4>1.6) 确认章节草稿</h4>
            <div className="small" style={{ marginBottom: 8 }}>
              作用：锁定当前章节发布候选稿，避免“生成成功但未确认”的状态。
            </div>
            <div className="quick-status-grid">
              <div className="summary-card">
                <div className="k">草稿版本数</div>
                <div className="v">{quickVersionItems.length}</div>
              </div>
              <div className="summary-card">
                <div className="k">确认状态</div>
                <div className="v">{quickSelectedDraftId ? "已确认" : "未确认"}</div>
              </div>
              <div className="summary-card">
                <div className="k">已确认稿件</div>
                <div className="v">
                  {quickSelectedDraftId
                    ? `${quickSelectedDraftId.slice(0, 8)}...${quickSelectedDraftBranch ? ` (${quickSelectedDraftBranch})` : ""}`
                    : "暂无"}
                </div>
              </div>
            </div>
            <div className="row" style={{ marginTop: 8, gap: 8, flexWrap: "wrap" }}>
              <button onClick={() => void quickLoadVersions()} disabled={!chapterId || quickDraftConfirmBusy}>
                执行 4.1 加载草稿版本
              </button>
              <button onClick={() => void quickSelectLatest()} disabled={!chapterId || quickVersionItems.length === 0 || quickDraftConfirmBusy}>
                执行 4.2 确认最新草稿
              </button>
              <button onClick={() => void quickConfirmLatestDraftFlow()} disabled={!chapterId || quickDraftConfirmBusy}>
                {quickDraftConfirmBusy ? "4.1→4.2 执行中..." : "一键执行 4.1 → 4.2"}
              </button>
            </div>
            <div className="small" style={{ marginTop: 8 }}>
              最近确认时间：{quickSelectedDraftAt || "暂无"}{quickSelectedDraftId ? ` · 稿件 ${quickSelectedDraftId.slice(0, 12)}...` : ""}
            </div>
          </div>
        </div>
      </section>
      ) : null}

      {showWritingWorkspace && !writerSimpleMode ? (
      <section id="section-quickstart" className="wb-panel" style={{ minHeight: "auto", marginBottom: 10 }}>
        <h3>快速启动</h3>
        <div className="quickstart-grid">
          <div className="quickstart-card">
            <h4>任务上下文</h4>
            <div className="quick-form-grid">
              <label>
                服务地址
                <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
              </label>
              <label>
                智能模式
                <select value={quickRunMode} onChange={(e) => setQuickRunMode(e.target.value as any)}>
                  <option value="safe_auto">安全自动（Safe Auto，自动执行低风险，失败自动修复）</option>
                  <option value="balanced_auto">均衡自动（Balanced，自动到发布，可选自动修复）</option>
                  <option value="manual_gate">手动闸门（Manual Gate，自动到草稿 Draft，其余人工）</option>
                </select>
              </label>
              <label>
                书籍 ID
                <input value={bookId} onChange={(e) => setBookId(e.target.value)} placeholder="书籍ID（UUID）" />
              </label>
              <label>
                章节 ID
                <input value={chapterId} onChange={(e) => setChapterId(e.target.value)} placeholder="章节ID（UUID）" />
              </label>
              <label>
                卷 ID
                <input value={quickVolumeId} onChange={(e) => setQuickVolumeId(e.target.value)} placeholder="卷ID（UUID）" />
              </label>
            </div>
          </div>
          {!writerSimpleMode ? (
            <div className="quickstart-card">
              <h4>自动化策略</h4>
              <div className="quick-option-grid">
                <label className="small">
                  <input type="checkbox" checked={quickAutoSelectLatest} onChange={(e) => setQuickAutoSelectLatest(e.target.checked)} />
                  自动选择最新稿
                </label>
                <label className="small">
                  <input type="checkbox" checked={quickAutoPublish} onChange={(e) => setQuickAutoPublish(e.target.checked)} />
                  自动发布
                </label>
                <label className="small">
                  <input type="checkbox" checked={quickAutoFixOnPublishFail} onChange={(e) => setQuickAutoFixOnPublishFail(e.target.checked)} />
                  发布失败自动低风险修复
                </label>
                <label className="small">
                  修复上限
                  <input
                    style={{ width: 80 }}
                    type="number"
                    min={1}
                    max={10}
                    value={quickAutoFixMax}
                    onChange={(e) => setQuickAutoFixMax(Math.max(1, Math.min(10, Number(e.target.value) || 1)))}
                  />
                </label>
                <label className="small">
                  <input type="checkbox" checked={quickAutoOpenFolder} onChange={(e) => setQuickAutoOpenFolder(e.target.checked)} />
                  自动打开导出目录
                </label>
                <label className="small">
                  <input type="checkbox" checked={flowAutoSplitbook} onChange={(e) => setFlowAutoSplitbook(e.target.checked)} />
                  统一流程前先执行拆书管线
                </label>
                <label className="small">
                  <input type="checkbox" checked={closedLoopDoWriteback} onChange={(e) => setClosedLoopDoWriteback(e.target.checked)} />
                  闭环：执行回写记忆
                </label>
                <label className="small">
                  <input type="checkbox" checked={closedLoopRunPreflight} onChange={(e) => setClosedLoopRunPreflight(e.target.checked)} />
                  闭环：执行章节体检
                </label>
                <label className="small">
                  <input type="checkbox" checked={closedLoopRewriteEnabled} onChange={(e) => setClosedLoopRewriteEnabled(e.target.checked)} />
                  闭环：启用去 AI 味
                </label>
                <label className="small">
                  <input
                    type="checkbox"
                    checked={closedLoopRewriteAutoAccept}
                    disabled={!closedLoopRewriteEnabled}
                    onChange={(e) => setClosedLoopRewriteAutoAccept(e.target.checked)}
                  />
                  闭环：自动采纳去 AI 味结果
                </label>
                <label className="small">
                  <input
                    type="checkbox"
                    checked={closedLoopFailOnPreflightFail}
                    onChange={(e) => setClosedLoopFailOnPreflightFail(e.target.checked)}
                  />
                  体检 FAIL 时整体标记失败
                </label>
                <label className="small">
                  <input
                    type="checkbox"
                    checked={closedLoopEvolveStyle}
                    onChange={(e) => setClosedLoopEvolveStyle(e.target.checked)}
                  />
                  闭环后自动风格进化
                </label>
              </div>
            </div>
          ) : null}
          <div className="quickstart-card quickstart-actions">
            <h4>执行区</h4>
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <button onClick={() => void runClosedLoopFlow()} disabled={closedLoopBusy || quickPipelineBusy}>
                {closedLoopBusy ? "闭环执行中..." : "一键闭环执行（推荐）"}
              </button>
              <button onClick={() => void runStyleEvolutionNow(false)} disabled={styleEvolutionBusy || !bookId}>
                {styleEvolutionBusy ? "风格进化中..." : "执行风格进化（1.6）"}
              </button>
              <button onClick={() => void quickRunSmart()} disabled={quickPipelineBusy}>
                {quickPipelineBusy ? "智能流程执行中..." : "一键智能运行（统一流）"}
              </button>
              <button onClick={() => void runUnifiedDesktopFlow()} disabled={flowBusy || quickPipelineBusy}>
                {flowBusy ? "统一流程执行中..." : "运行统一流程"}
              </button>
            </div>
            <div className="small" style={{ marginTop: 8 }}>
              最近风格进化：{latestStyleRunAt ? `${latestStyleRunAt}${latestStyleVersion ? ` · v${latestStyleVersion}` : ""}` : "暂无记录"}
            </div>
            <details open={!writerSimpleMode}>
              <summary>高级手动操作（按作业顺序）</summary>
              <div className="quick-form-grid" style={{ marginTop: 8 }}>
                <div className="summary-card">
                  <div className="k">01</div>
                  <div className="v">启动侧车（Sidecar）</div>
                  <div className="small">先拉起服务，确保后续步骤可执行。</div>
                  <button onClick={() => void quickStartSidecar()}>执行 01</button>
                </div>
                <div className="summary-card">
                  <div className="k">02</div>
                  <div className="v">健康检查</div>
                  <div className="small">确认接口与依赖状态正常。</div>
                  <button onClick={() => void checkHealth()}>执行 02</button>
                </div>
                <div className="summary-card">
                  <div className="k">03</div>
                  <div className="v">执行草稿</div>
                  <div className="small">触发草稿生成。</div>
                  <button onClick={() => void quickDraftRun()}>执行 03</button>
                </div>
                <div className="summary-card">
                  <div className="k">04</div>
                  <div className="v">加载版本</div>
                  <div className="small">读取本章版本列表。</div>
                  <button onClick={() => void quickLoadVersions()}>执行 04</button>
                </div>
                <div className="summary-card">
                  <div className="k">05</div>
                  <div className="v">选择最新版本</div>
                  <div className="small">将最新稿设为发布候选。</div>
                  <button onClick={() => void quickSelectLatest()}>执行 05</button>
                </div>
                <div className="summary-card">
                  <div className="k">06</div>
                  <div className="v">生成发布包</div>
                  <div className="small">产出可交付文件。</div>
                  <button onClick={() => void quickPublishPack()}>执行 06</button>
                </div>
                <div className="summary-card" style={{ gridColumn: "1 / -1" }}>
                  <div className="k">07</div>
                  <div className="v">传统一键流程（1→6 自动串行）</div>
                  <div className="small">若不想逐步点击，可直接执行完整顺序。</div>
                  <button onClick={() => void quickRunAll()} disabled={quickPipelineBusy}>
                    {quickPipelineBusy ? "07 执行中..." : "执行 07"}
                  </button>
                </div>
              </div>
            </details>
          </div>
        </div>
        <div className="quick-status-grid">
          <div className="quickstart-card">
            <div className="small" style={{ marginBottom: 4 }}>统一流程状态</div>
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              {(["splitbook", "smart", "preflight"] as const).map((k) => (
                <span key={k} className="small" style={{ color: stepColor(flowSteps[k]) }}>
                  {statusDot(flowSteps[k])} {flowStepLabel(k)}={formatPipelineStatus(flowSteps[k])}
                </span>
              ))}
            </div>
            <div className="small" style={{ marginTop: 6 }}>进度：{flowProgressPct}%</div>
            <div className="pipeline-progress"><span style={{ width: `${flowProgressPct}%` }} /></div>
          </div>
          <div className="quickstart-card">
            <div className="small" style={{ marginBottom: 4 }}>阶段状态</div>
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              {(["sidecar", "draft", "versions", "select", "publish"] as const).map((k) => (
                <span key={k} className="small" style={{ color: stepColor(quickPipelineSteps[k]) }}>
                  {statusDot(quickPipelineSteps[k])} {quickStepLabel(k)}={formatPipelineStatus(quickPipelineSteps[k])}
                </span>
              ))}
            </div>
            <div className="small" style={{ marginTop: 6 }}>进度：{quickProgressPct}%</div>
            <div className="pipeline-progress"><span style={{ width: `${quickProgressPct}%` }} /></div>
          </div>
          <div className="quickstart-card">
            <div className="small" style={{ marginBottom: 4 }}>闭环阶段状态</div>
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              {[
                { key: "draft", label: "草稿生成" },
                { key: "writeback", label: "回写记忆" },
                { key: "preflight", label: "章节体检" },
                { key: "rewrite", label: "去 AI 味" },
                { key: "style_evolution", label: "风格进化" },
              ].map((item) => (
                <span key={item.key} className="small" style={{ color: stepColor(closedLoopSteps[item.key]) }}>
                  {statusDot(closedLoopSteps[item.key])} {item.label}={formatPipelineStatus(closedLoopSteps[item.key])}
                </span>
              ))}
            </div>
            <div className="small" style={{ marginTop: 6 }}>进度：{closedLoopProgressPct}%</div>
            <div className="pipeline-progress"><span style={{ width: `${closedLoopProgressPct}%` }} /></div>
          </div>
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
            <strong>流水线失败（Pipeline）</strong>
            <div>步骤：{quickPipelineError.step ? quickStepLabel(quickPipelineError.step) : "-"}</div>
            <div style={{ whiteSpace: "pre-wrap" }}>{quickPipelineError.message}</div>
            <div className="row" style={{ gap: 8, marginTop: 8, flexWrap: "wrap" }}>
              <button onClick={() => void retryFailedStep()}>重试失败步骤</button>
              <button onClick={() => setShowAgentConsole(true)}>打开智能体控制台</button>
              {String(quickPipelineError.step || "") === "publish" ? (
                <button onClick={() => void quickFixwizardPlanForPublish()}>生成修复方案</button>
              ) : null}
              {String(quickPipelineError.step || "") === "publish" && Array.isArray(quickFixPreview?.fixes) && quickFixPreview.fixes.length > 0 ? (
                <>
                  <button onClick={() => void quickFixwizardExecuteLowRisk(3)}>执行低风险修复（最多 3 条）</button>
                  <button onClick={() => void quickFixwizardExecuteTop(1)}>执行 Top-1 修复</button>
                  <button onClick={() => void quickFixwizardExecuteTop(3)}>执行 Top-3 修复</button>
                </>
              ) : null}
            </div>
            {quickFixPreview ? (
              <details style={{ marginTop: 8 }}>
                <summary>快速修复预览</summary>
                <div className="scroll" style={{ maxHeight: 220, marginTop: 8 }}>
                  {!Array.isArray(quickFixPreview?.fixes) || quickFixPreview.fixes.length === 0 ? (
                    <div className="hint">暂无修复项。</div>
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
                            <span className="small">类型={String(fx?.type || "-")}</span>
                            <span className="small">目标={String(fx?.target || "-")}</span>
                          </div>
                          {String(fx?.reason || "").trim() ? (
                            <div className="small" style={{ marginTop: 4 }}>{String(fx?.reason || "")}</div>
                          ) : null}
                          {effects.length > 0 ? (
                            <div className="small" style={{ marginTop: 4 }}>
                              预期：{effects.slice(0, 3).join(" | ")}
                            </div>
                          ) : null}
                        </div>
                      );
                    })
                  )}
                </div>
                <details style={{ marginTop: 8 }}>
                  <summary className="small">修复预览原始 JSON</summary>
                  <pre>{JSON.stringify(quickFixPreview, null, 2)}</pre>
                </details>
              </details>
            ) : null}
            {quickFixExecuteOut ? (
              <details style={{ marginTop: 8 }}>
                <summary>快速修复执行结果</summary>
                <pre>{JSON.stringify(quickFixExecuteOut, null, 2)}</pre>
              </details>
            ) : null}
          </div>
        ) : null}
        {!writerSimpleMode ? (
          <div className="agent-grid" style={{ marginTop: 8 }}>
            <div className="agent-col">
              <div className="small">快速草稿执行</div>
              <pre>{JSON.stringify(quickDraftRunOut, null, 2)}</pre>
            </div>
            <div className="agent-col">
              <div className="small">快速版本结果</div>
              <pre>{JSON.stringify(quickVersionsOut, null, 2)}</pre>
            </div>
            <div className="agent-col">
              <div className="small">快速发布结果</div>
              <pre>{JSON.stringify(quickPublishOut, null, 2)}</pre>
            </div>
            <div className="agent-col">
              <div className="small">闭环执行结果</div>
              <pre>{JSON.stringify(closedLoopOutput, null, 2)}</pre>
            </div>
            <div className="agent-col">
              <div className="small">风格进化结果</div>
              <pre>{JSON.stringify(styleEvolutionOutput || styleEvolutionLatest, null, 2)}</pre>
            </div>
          </div>
        ) : null}
      </section>
      ) : null}

      {showAgentConsole
        ? renderTopPanel(
            "智能体控制台",
            () => setShowAgentConsole(false),
            <AgentConsolePanel
              selectedBookId={bookId}
              selectedChapterId={chapterId}
              onPickBookId={(id) => applyBookSelection(id)}
              onPickChapterId={(id) => setChapterId(id)}
            />
          )
        : null}

      {showVersionCenter
        ? renderTopPanel(
            "版本中心",
            () => setShowVersionCenter(false),
            <VersionsPanel
              bookId={bookId}
              chapterId={chapterId}
              onPickChapterId={(id) => setChapterId(id)}
              onStatus={(msg) => setStatus(msg)}
            />
          )
        : null}

      {showRewriteCenter
        ? renderTopPanel(
            "改写中心",
            () => setShowRewriteCenter(false),
            <RewritePanel
              bookId={bookId}
              chapterId={chapterId}
              onStatus={(msg) => setStatus(msg)}
            />
          )
        : null}

      {showReleaseCenter
        ? renderTopPanel(
            "发布中心",
            () => setShowReleaseCenter(false),
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
          )
        : null}

      {showHelpCenter
        ? renderTopPanel(
            "帮助中心",
            () => setShowHelpCenter(false),
            <HelpCenterPanel onOpenPanel={openOptionalPanel} onStatus={(msg) => setStatus(msg)} />
          )
        : null}

      {showAssetCenter
        ? renderTopPanel(
            "资产沉淀管理",
            () => setShowAssetCenter(false),
            <AssetCenterPanel
              baseUrl={baseUrl}
              bookId={bookId}
              onStatus={(msg) => setStatus(msg)}
              onAfterRollback={() => refreshWorkspaceAfterAssetRollback()}
            />
          )
        : null}

      <section className="wb-panel" style={{ minHeight: "auto", marginBottom: 10 }}>
        <div className="row" style={{ marginBottom: 8 }}>
          <h3 style={{ margin: 0 }}>资料库</h3>
          <span className="small">{writerSimpleMode ? "简洁模式：仅保留选择与查看" : "高级模式：支持检索、创建、全量查看"}</span>
        </div>
        {writerSimpleMode ? (
          <div className="outline-context" style={{ marginBottom: 10 }}>
            <div className="summary-card">
              <div className="k">当前书籍</div>
              <div className="v">{selectedBookItem?.title || "未选择"}</div>
            </div>
            <div className="summary-card">
              <div className="k">当前章节</div>
              <div className="v">{selectedChapterItem ? `第${selectedChapterItem.chapter_no}章` : "未选择"}</div>
            </div>
            <div className="summary-card">
              <div className="k">简报完成度</div>
              <div className="v">{writingBriefFilledCount}/6</div>
            </div>
          </div>
        ) : null}
        <div className="row" style={{ marginBottom: 8 }}>
          <input
            value={librarySearchQuery}
            onChange={(e) => setLibrarySearchQuery(e.target.value)}
            placeholder={writerSimpleMode ? "快速检索现有书籍/章节..." : "统一搜索：书籍 / 章节 / 素材 / 技能运行"}
          />
          <button onClick={() => setSearchOpen(true)}>打开全局搜索 (Ctrl/Cmd+K)</button>
          <button onClick={() => void loadBooks()}>刷新书籍</button>
          <button onClick={() => void loadChapters()} disabled={!bookId}>刷新章节</button>
        </div>
        {!writerSimpleMode && librarySearchQuery.trim() ? (
          <div className="wb-panel" style={{ minHeight: "auto", marginBottom: 10, padding: 10 }}>
            <div className="row" style={{ marginBottom: 6 }}>
              <strong>搜索结果</strong>
              <span className="small">{librarySearchLoading ? "搜索中..." : `${librarySearchItems.length} 条`}</span>
            </div>
            <div className="job-grid">
              <div>
                <div className="small" style={{ marginBottom: 6 }}>书籍</div>
                <div className="scroll" style={{ maxHeight: 160 }}>
                  {libraryBookHits.map((it) => (
                    <button key={`book_${it.id}`} className="node-item" onClick={() => void applyLibrarySearchItem(it)}>
                      <div style={{ width: "100%" }}>
                        <div className="row"><span><span className="badge">书籍</span> {it.title}</span><code>{Number(it.score || 0).toFixed(2)}</code></div>
                        <div className="small">{it.subtitle}</div>
                      </div>
                    </button>
                  ))}
                  {libraryBookHits.length === 0 ? <div className="hint">暂无书籍</div> : null}
                </div>
              </div>
              <div>
                <div className="small" style={{ marginBottom: 6 }}>章节</div>
                <div className="scroll" style={{ maxHeight: 160 }}>
                  {libraryChapterHits.map((it) => (
                    <button key={`chapter_${it.id}`} className="node-item" onClick={() => void applyLibrarySearchItem(it)}>
                      <div style={{ width: "100%" }}>
                        <div className="row"><span><span className="badge">章节</span> {it.title}</span><code>{Number(it.score || 0).toFixed(2)}</code></div>
                        <div className="small">{it.subtitle}</div>
                      </div>
                    </button>
                  ))}
                  {libraryChapterHits.length === 0 ? <div className="hint">暂无章节</div> : null}
                </div>
              </div>
            </div>
            <div className="job-grid" style={{ marginTop: 8 }}>
              <div>
                <div className="small" style={{ marginBottom: 6 }}>素材</div>
                <div className="scroll" style={{ maxHeight: 160 }}>
                  {libraryMaterialHits.map((it) => (
                    <button key={`material_${it.id}`} className="node-item" onClick={() => void applyLibrarySearchItem(it)}>
                      <div style={{ width: "100%" }}>
                        <div className="row"><span><span className="badge">素材</span> {it.title}</span><code>{Number(it.score || 0).toFixed(2)}</code></div>
                        <div className="small">{it.subtitle}</div>
                      </div>
                    </button>
                  ))}
                  {libraryMaterialHits.length === 0 ? <div className="hint">暂无素材</div> : null}
                </div>
              </div>
              <div>
                <div className="small" style={{ marginBottom: 6 }}>技能运行</div>
                <div className="scroll" style={{ maxHeight: 160 }}>
                  {librarySkillRunHits.map((it) => (
                    <button key={`skill_${it.id}`} className="node-item" onClick={() => void applyLibrarySearchItem(it)}>
                      <div style={{ width: "100%" }}>
                        <div className="row"><span><span className="badge">技能运行</span> {it.title}</span><code>{Number(it.score || 0).toFixed(2)}</code></div>
                        <div className="small">{it.subtitle}</div>
                      </div>
                    </button>
                  ))}
                  {librarySkillRunHits.length === 0 ? <div className="hint">暂无技能运行记录</div> : null}
                </div>
              </div>
            </div>
          </div>
        ) : null}
        <div className="job-grid">
          <div>
            <div className="row" style={{ marginBottom: 8 }}>
              <input value={bookQuery} onChange={(e) => setBookQuery(e.target.value)} placeholder="筛选书籍..." />
              <button onClick={() => void loadBooks()}>搜索</button>
              <button className="danger" onClick={() => void deleteCurrentBookFromLibrary()} disabled={!bookId || bookDeleting}>
                {bookDeleting ? "删除中..." : "删除当前书籍"}
              </button>
            </div>
            {!writerSimpleMode ? (
              <div className="row" style={{ marginBottom: 8 }}>
                <input value={newBookName} onChange={(e) => setNewBookName(e.target.value)} placeholder="新书名" />
                <button onClick={() => void createBookFromLibrary()}>创建书籍</button>
              </div>
            ) : null}
            <div className="scroll" style={{ maxHeight: 220 }}>
              {bookItems.map((b) => (
                <button
                  key={b.book_id}
                  className={`node-item ${bookId === b.book_id ? "active" : ""}`}
                  onClick={() => applyBookSelection(b.book_id)}
                >
                  <div style={{ width: "100%" }}>
                    <div className="row"><strong>{b.title}</strong><code>{b.language || "zh"}</code></div>
                    <div className="small">{b.book_id}</div>
                  </div>
                </button>
              ))}
              {bookItems.length === 0 ? <div className="hint">暂无书籍</div> : null}
            </div>
          </div>

          <div>
            <div className="row" style={{ marginBottom: 8 }}>
              <input value={chapterQuery} onChange={(e) => setChapterQuery(e.target.value)} placeholder="筛选章节..." disabled={!bookId} />
              <button onClick={() => void loadChapters()} disabled={!bookId}>搜索</button>
              <button className="danger" onClick={() => void deleteCurrentChapterFromLibrary()} disabled={!chapterId || chapterDeleting}>
                {chapterDeleting ? "删除中..." : "删除当前章节"}
              </button>
            </div>
            {!writerSimpleMode ? (
              <div className="row" style={{ marginBottom: 8, flexWrap: "wrap" }}>
                <input style={{ width: 96 }} type="number" value={newChapterNo} onChange={(e) => setNewChapterNo(Number(e.target.value))} placeholder="章序号（No.）" disabled={!bookId} />
                <input value={newChapterTitle} onChange={(e) => setNewChapterTitle(e.target.value)} placeholder="章节标题" disabled={!bookId} />
                <input style={{ width: 120 }} value={newChapterArcId} onChange={(e) => setNewChapterArcId(e.target.value)} placeholder="卷ID（arc_id）" disabled={!bookId} />
                <input style={{ width: 96 }} type="number" value={newChapterArcIndex} onChange={(e) => setNewChapterArcIndex(Number(e.target.value))} placeholder="卷内序号（arc_idx）" disabled={!bookId} />
                <button onClick={() => void createChapterFromLibrary()} disabled={!bookId}>创建章节</button>
              </div>
            ) : null}
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
              {bookId && chapterItems.length === 0 ? <div className="hint">暂无章节</div> : null}
            </div>
          </div>
        </div>
        {writerSimpleMode ? (
          <div className="quick-status-grid" style={{ marginTop: 10 }}>
            <div className="quickstart-card">
              <div className="small" style={{ marginBottom: 6 }}>当前书籍摘要</div>
              <div className="small">书名：{selectedBookItem?.title || "-"}</div>
              <div className="small">作者：{String(selectedBookItem?.author || "-")}</div>
              <div className="small">语言：{String(selectedBookItem?.language || "-")}</div>
              <div className="small">目录：<code>{newBookWorkspacePath || "-"}</code></div>
            </div>
            <div className="quickstart-card">
              <div className="small" style={{ marginBottom: 6 }}>当前章节摘要</div>
              <div className="small">章节：{selectedChapterItem ? `第${selectedChapterItem.chapter_no}章 · ${selectedChapterItem.title}` : "-"}</div>
              <div className="small">卷：{selectedVolumeItem ? String(selectedVolumeItem.title || selectedVolumeItem.volume_id) : "-"}</div>
              <div className="small">简报字段完成：{writingBriefFilledCount}/6</div>
              <div className="row" style={{ marginTop: 8, gap: 8 }}>
                <button onClick={() => void loadBookWorkspace()} disabled={!bookId}>刷新目录</button>
                <button onClick={() => void loadWritingBrief()} disabled={!bookId}>刷新简报</button>
                <button onClick={() => void loadVolumes()} disabled={!bookId}>刷新卷</button>
              </div>
            </div>
          </div>
        ) : null}
      </section>

      {showRefCenter
        ? renderTopPanel(
            "引用中心",
            () => setShowRefCenter(false),
            <section id="section-ref-center" className="wb-panel" style={{ minHeight: "auto", marginBottom: 0 }}>
          <div className="row" style={{ marginBottom: 8 }}>
            <h3 style={{ margin: 0 }}>引用中心</h3>
            <div className="row">
              <button className={refCenterTab === "material" ? "active" : ""} onClick={() => setRefCenterTab("material")}>素材</button>
              <button className={refCenterTab === "template" ? "active" : ""} onClick={() => setRefCenterTab("template")}>模板</button>
            </div>
          </div>
          <div className="row" style={{ marginBottom: 8, flexWrap: "wrap" }}>
            <input
              value={refUnifiedQuery}
              onChange={(e) => setRefUnifiedQuery(e.target.value)}
              placeholder="在引用中心统一检索（素材 + 模板）..."
            />
            <button onClick={() => void searchRefUnified()} disabled={!refUnifiedQuery.trim() || refUnifiedLoading}>
              {refUnifiedLoading ? "检索中..." : "检索引用"}
            </button>
          </div>
          {refUnifiedItems.length ? (
            <div className="scroll" style={{ maxHeight: 180, marginBottom: 10 }}>
              {refUnifiedItems.map((it) => (
                <div key={`${it.kind}:${it.id}`} className="issue-item">
                  <div className="row">
                    <span><span className="badge">{formatRefKindLabel(it.kind)}</span> {it.title}</span>
                    <code>{it.score.toFixed(2)}</code>
                  </div>
                  <div className="small" style={{ marginBottom: 6 }}>{it.subtitle}</div>
                  <div className="row">
                    <button
                      onClick={() => {
                        const promise = it.kind === "template"
                          ? addTemplateAssetToRefInbox(it.id, undefined, it.title)
                          : addMaterialCardToRefInbox(it.id, it.title);
                        void promise.catch((e) => setStatus(formatAnyError(e)));
                      }}
                      disabled={!chapterId}
                    >
                      加入引用
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
                    <option value="">（全部类型）</option>
                    <option value="structure">结构（structure）</option>
                    <option value="mechanic">机制（mechanic）</option>
                    <option value="style">风格（style）</option>
                    <option value="foreshadow">伏笔（foreshadow）</option>
                    <option value="payoff">回收（payoff）</option>
                  </select>
                  <input value={templateTag} onChange={(e) => setTemplateTag(e.target.value)} placeholder="标签（可选）" style={{ width: 180 }} />
                  <input value={templateQuery} onChange={(e) => setTemplateQuery(e.target.value)} placeholder="搜索模板..." />
                  <button onClick={() => void searchTemplateAssets()} disabled={templateLoading}>{templateLoading ? "加载中..." : "搜索"}</button>
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
                  {templateItems.length === 0 ? <div className="hint">暂无模板。</div> : null}
                </div>
              </div>
              <div>
                <div className="row" style={{ marginBottom: 8 }}>
                  <strong>模板详情</strong>
                  <div className="row">
                    <button
                      onClick={() => {
                        void addTemplateToRefInbox().catch((e) => setStatus(formatAnyError(e)));
                      }}
                      disabled={!templateSelected}
                    >
                      加入引用收件箱
                    </button>
                    <button
                      className="danger"
                      onClick={() => {
                        if (!templateSelected) return;
                        void deleteTemplateAssetFromLibrary(templateSelected.asset_id, templateSelected.name);
                      }}
                      disabled={!templateSelected || templateAssetDeletingId === templateSelected?.asset_id}
                    >
                      {templateSelected && templateAssetDeletingId === templateSelected.asset_id ? "删除中..." : "删除模板资产"}
                    </button>
                    <button
                      className="danger"
                      onClick={() => {
                        if (!selectedTemplateStructureId || !templateSelected) return;
                        deleteStructureTemplateFromLibrary(selectedTemplateStructureId, `${templateSelected.name}（结构模板）`);
                      }}
                      disabled={!selectedTemplateStructureId || structureTemplateDeletingId === selectedTemplateStructureId}
                      title={selectedTemplateStructureId ? "删除此模板资产关联的底层结构模板" : "当前模板资产未关联底层结构模板ID"}
                    >
                      {selectedTemplateStructureId && structureTemplateDeletingId === selectedTemplateStructureId ? "删除中..." : "删除底层模板"}
                    </button>
                  </div>
                </div>
                {templateSelected ? (
                  <>
                    <div className="small">类型：<code>{templateSelected.asset_type}</code></div>
                    <div className="small">素材ID：<code>{templateSelected.asset_id}</code></div>
                    <div className="small">底层模板ID：<code>{selectedTemplateStructureId || "-"}</code></div>
                    <div className="small">标签：{(templateSelected.tags || []).join(", ") || "-"}</div>
                    <label style={{ marginTop: 8 }}>
                      备注（可选）
                      <input value={templateNote} onChange={(e) => setTemplateNote(e.target.value)} placeholder="本章映射备注（可选）" />
                    </label>
                    <pre>{templateSelected.description}</pre>
                  </>
                ) : (
                  <div className="hint">请选择一个模板。</div>
                )}
              </div>
            </div>
          )}
          <div className="hint" style={{ marginTop: 8 }}>
            模板(Templates)加入后会进入当前章节引用收件箱(Ref Inbox)，并同步进入页面引用列表供控制计划(Control Plan)使用。
          </div>
            </section>
          )
        : null}

      {showSplitbooks
        ? renderTopPanel(
            "拆书库（Splitbooks）",
            () => setShowSplitbooks(false),
            <section id="section-splitbooks" className="wb-panel" style={{ minHeight: "auto", marginBottom: 0 }}>
          <div className="row" style={{ marginBottom: 8 }}>
            <h3 style={{ margin: 0 }}>拆书库（Splitbooks）</h3>
            <div className="row">
              <button onClick={() => void refreshSplitbookWorkspace()} disabled={splitbookRefreshBusy}>
                {splitbookRefreshBusy ? "刷新中..." : "刷新（含状态对账）"}
              </button>
            </div>
          </div>
          <div className="row" style={{ marginBottom: 10, gap: 14 }}>
            <label className="small" style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <input type="checkbox" checked={splitbookSimpleMode} onChange={(e) => setSplitbookSimpleMode(e.target.checked)} />
              简洁作业模式（当前：{splitbookSimpleMode ? "开启" : "关闭"}）
            </label>
            <label className="small" style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <input type="checkbox" checked={splitbookShowAdvanced} onChange={(e) => setSplitbookShowAdvanced(e.target.checked)} />
              高级参数区（当前：{splitbookShowAdvanced ? "显示" : "隐藏"}）
            </label>
          </div>
          <div className="job-grid">
            <div>
              <div className="splitbook-guide">
                <strong>拆书向导（5 步）</strong>
                <ol>
                  <li>先选本地 TXT/MD，再点“检查文件可用性”。</li>
                  <li>创建或复用拆书档案，确保选中目标拆书。</li>
                  <li>执行导入与向量化，确认状态变为“已完成”。</li>
                  <li>执行结构抽取，刷新结构账本/大纲/章节包。</li>
                  <li>生成模板与画像，最后导出诊断或回写新章节。</li>
                </ol>
              </div>

              <div className="splitbook-stepbar">
                {splitbookWizardSteps.map((step, idx) => (
                  <div key={step.key} className={`splitbook-step-pill ${step.done ? "done" : ""}`}>
                    <span className="idx">步骤 {idx + 1}</span>
                    <strong>{step.title}</strong>
                    <span className="small">{step.hint}</span>
                  </div>
                ))}
              </div>

              <div className="splitbook-step-card">
                <div className="row">
                  <strong>步骤 1：选择本地文件</strong>
                  <span className="small">支持 `.txt/.md/.jsonl`，默认 UTF-8（JSONL 视为预切分）</span>
                </div>
                <input
                  value={splitbookPath}
                  onChange={(e) => {
                    setSplitbookPath(e.target.value);
                    setSplitbookPathCheck(null);
                  }}
                  placeholder="本地文件路径，例如 D:\\books\\demo.txt"
                />
                <div className="row" style={{ marginTop: 8 }}>
                  <button onClick={() => void pickSplitbookLocalFile()}>选择本地文件</button>
                  <button onClick={() => void verifySplitbookPath(splitbookPath)}>检查文件可用性</button>
                </div>
                {splitbookPathCheck ? (
                  <div className={`small ${splitbookPathCheck.ok ? "ok" : "danger"}`}>文件检查：{splitbookPathCheck.message}</div>
                ) : null}
                <div className="row" style={{ marginTop: 10 }}>
                  <strong>拆书产物目录（可预设）</strong>
                  <span className="small">账本/大纲/章节包/体检报告导出到该目录</span>
                </div>
                <input
                  value={splitbookOutputDir}
                  onChange={(e) => {
                    setSplitbookOutputDir(e.target.value);
                    setSplitbookOutputDirCheck(null);
                  }}
                  placeholder="例如 D:\\NovelEngine\\splitbook_exports"
                />
                <div className="row" style={{ marginTop: 8 }}>
                  <button onClick={() => void pickSplitbookOutputDir()}>选择目录</button>
                  <button
                    onClick={() => {
                      const v = String(splitbookOutputDir || "").trim();
                      try {
                        if (v) window.localStorage.setItem("splitbook.outputDir", v);
                      } catch {}
                      void verifySplitbookOutputDir(v);
                    }}
                  >
                    保存为默认目录
                  </button>
                  <button onClick={() => void verifySplitbookOutputDir(splitbookOutputDir)}>检查目录可用性</button>
                </div>
                {splitbookOutputDirCheck ? (
                  <div className={`small ${splitbookOutputDirCheck.ok ? "ok" : "danger"}`}>目录检查：{splitbookOutputDirCheck.message}</div>
                ) : null}
              </div>

              <div className="splitbook-step-card">
                <div className="row">
                  <strong>步骤 2：创建或复用拆书</strong>
                  <span className="small">同路径自动复用，避免重复</span>
                </div>
                <div className="splitbook-form-grid">
                  <input value={splitbookName} onChange={(e) => setSplitbookName(e.target.value)} placeholder="拆书名称（必填）" />
                  <input value={splitbookAuthor} onChange={(e) => setSplitbookAuthor(e.target.value)} placeholder="作者（可选）" />
                </div>
                <div className="row" style={{ marginTop: 8 }}>
                  <button onClick={() => void createSplitbookFromUi()} disabled={!splitbookName.trim() || !splitbookPathReady}>
                    创建/复用拆书
                  </button>
                  <span className="small">当前：{selectedSplitbook?.name || "未选择拆书"}</span>
                </div>
              </div>

              <div className="splitbook-step-card">
                <div className="row">
                  <strong>步骤 3：导入与向量化</strong>
                  <span className="small">支持一键全流程，也支持分步骤手动执行（按 3.1 到 3.5）</span>
                </div>
                {showSplitbookAdvanced ? (
                  <div className="row" style={{ marginTop: 8, flexWrap: "wrap" }}>
                    <label style={{ width: 120 }}>
                      分块大小
                      <input type="number" value={splitbookChunkSize} onChange={(e) => setSplitbookChunkSize(Number(e.target.value))} />
                    </label>
                    <label style={{ width: 120 }}>
                      重叠大小
                      <input type="number" value={splitbookOverlap} onChange={(e) => setSplitbookOverlap(Number(e.target.value))} />
                    </label>
                  </div>
                ) : (
                  <div className="small" style={{ marginTop: 8 }}>
                    系统会按文本体量自动选择 chunk / overlap / 批次 / 并行数，默认优先质量与稳定性。
                  </div>
                )}
                <div className="row" style={{ marginTop: 8 }}>
                  <button
                    onClick={() => void runSplitbookQuickPipeline()}
                    disabled={!selectedSplitbookId || !splitbookPathReady || splitbookPipelineBusy || selectedSplitbookRunningCount > 0 || selectedSplitbookEmbedActiveByStats}
                  >
                    {splitbookPipelineBusy ? `执行中：${formatSplitbookStepLabel(selectedSplitbookLiveStep)}` : "一键执行全流程（3.1→3.5）"}
                  </button>
                  <button onClick={() => void triggerSplitbookJob("embed")} disabled={!splitbookCanResumeEmbed}>
                    继续向量化
                  </button>
                </div>
                <details
                  className="splitbook-substep-tree"
                  open={splitbookStep3TreeOpen}
                  onToggle={(e) => setSplitbookStep3TreeOpen((e.currentTarget as HTMLDetailsElement).open)}
                >
                  <summary>
                    步骤树（3.1~3.5，可折叠）
                    <span className="small"> · 可执行 {splitbookStep3ManualRows.filter((x) => x.canRun).length} / {splitbookStep3ManualRows.length}</span>
                  </summary>
                  <div className="splitbook-substep-list">
                    {splitbookStep3ManualRows.map((step) => {
                      const state: "done" | "running" | "ready" | "blocked" = step.done
                        ? "done"
                        : step.running
                          ? "running"
                          : step.canRun
                            ? "ready"
                            : "blocked";
                      return (
                        <div key={step.key} className={`splitbook-substep-row state-${state}`}>
                          <div className="splitbook-substep-main">
                            <strong>{step.label}</strong>
                            <span className="small">状态：{formatSplitbookManualStepState(state)}</span>
                            <div className="splitbook-substep-meta">
                              <span className="small">最近结果：{step.latestSummary}</span>
                              {step.latestJob ? (
                                <button className="splitbook-substep-link" onClick={() => void openJobInCenter(step.latestJob)}>
                                  查看任务详情
                                </button>
                              ) : null}
                            </div>
                          </div>
                          <button onClick={() => void step.action()} disabled={!step.canRun}>
                            {step.buttonText}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </details>
              </div>

              <details open={!splitbookSimpleMode} style={{ marginBottom: 8 }}>
                <summary>④ 结构化抽取与账本（按顺序作业）</summary>
                <div className="splitbook-step-card" style={{ marginTop: 8 }}>
                  <div className="row">
                    <strong>步骤 4：结构化抽取与账本</strong>
                    <span className="small">人物/时间线/设定 + 成长账本（可一键执行并自动刷新）</span>
                  </div>
                  <div className="row" style={{ marginTop: 8 }}>
                    <button
                      onClick={() => void runSplitbookStep4ExtractAndRefresh()}
                      disabled={!selectedSplitbookId || selectedSplitbookEmbedStatus !== "done" || splitbookStep4Busy}
                    >
                      {splitbookStep4Busy ? "步骤4执行中..." : "执行 4.1~4.4（推荐）"}
                    </button>
                    <button onClick={() => void triggerSplitbookJob("extract_structured")} disabled={!selectedSplitbookId || selectedSplitbookEmbedStatus !== "done" || splitbookStep4Busy}>
                      仅执行 4.1 结构抽取
                    </button>
                    <button onClick={() => void loadSplitbookLedger("chapter")} disabled={!selectedSplitbookId || splitbookStep4Busy}>
                      执行 4.2 刷新账本（章节）
                    </button>
                    <button onClick={() => void loadSplitbookLedger("character")} disabled={!selectedSplitbookId || splitbookStep4Busy}>
                      执行 4.3 刷新账本（角色）
                    </button>
                    <button onClick={() => void loadSplitbookOutlinePreview()} disabled={!selectedSplitbookId || splitbookStep4Busy}>
                      执行 4.4 刷新整卷大纲
                    </button>
                  </div>
                  <div className="small" style={{ marginTop: 8 }}>
                    提示：若账本仍为空，优先确认步骤 3.2 向量化已完成，再执行“执行 4.1~4.4（推荐）”。
                  </div>
                  {splitbookSingleChapterLikely ? (
                    <div className="small danger" style={{ marginTop: 6 }}>
                      检测到章节切分异常：当前仅 {selectedSplitbookChapterTotal} 章，但分块数 {selectedSplitbookChunkTotal}。建议先执行“章节重切分”再继续。
                    </div>
                  ) : null}
                  <div className="row" style={{ marginTop: 8 }}>
                    <button
                      onClick={() => void runSplitbookResegmentIngest()}
                      disabled={
                        !selectedSplitbookId ||
                        splitbookResegmentBusy ||
                        splitbookStep4Busy ||
                        splitbookPipelineBusy ||
                        selectedSplitbookRunningCount > 0 ||
                        selectedSplitbookEmbedActiveByStats
                      }
                    >
                      {splitbookResegmentBusy ? "章节重切分执行中..." : "章节重切分（重跑 3.1）"}
                    </button>
                    <span className="small">会重建 chunk 与章节号；完成后需重新执行 3.2 与 4.x。</span>
                  </div>
                </div>
              </details>

              <details open={!splitbookSimpleMode} style={{ marginBottom: 8 }}>
                <summary>⑤ 模板画像与闭环回写（按顺序作业）</summary>
                <div className="splitbook-step-card" style={{ marginTop: 8 }}>
                  <div className="row">
                    <strong>步骤 5：模板画像与闭环回写</strong>
                    <span className="small">章节包 / 回写 / 体检 / 反照抄 / 跨书模板库</span>
                  </div>
                  <div className="row" style={{ marginTop: 8, flexWrap: "wrap" }}>
                    <label style={{ width: 120 }}>
                      章节号
                      <input type="number" min={1} value={splitbookChapterNo} onChange={(e) => setSplitbookChapterNo(Number(e.target.value) || 1)} />
                    </label>
                    <button onClick={() => void loadSplitbookChapterPack()} disabled={!selectedSplitbookId}>
                      执行 5.1 生成章节包
                    </button>
                    <button onClick={() => void exportSplitbookArtifactsToPresetDir()} disabled={!selectedSplitbookId || !splitbookOutputDir.trim()}>
                      执行 5.2 导出拆书产物
                    </button>
                    {showSplitbookAdvanced ? (
                      <>
                        <button onClick={() => void triggerSplitbookJob("build_templates")} disabled={!selectedSplitbookId || !splitbookStructuredDone}>
                          执行 5.3 生成模板
                        </button>
                        <button onClick={() => void triggerSplitbookJob("build_profile")} disabled={!selectedSplitbookId || !splitbookStructuredDone}>
                          执行 5.4 生成画像
                        </button>
                        <button onClick={() => void exportSplitbookDiagnose()} disabled={!selectedSplitbookId}>
                          执行 5.5 导出诊断 JSON
                        </button>
                      </>
                    ) : null}
                  </div>
                  <div className="row" style={{ marginTop: 8, flexWrap: "wrap" }}>
                    <label style={{ minWidth: 320 }}>
                      批量章节过滤（可选）
                      <input
                        value={splitbookWritebackChapterFilter}
                        onChange={(e) => setSplitbookWritebackChapterFilter(e.target.value)}
                        placeholder="留空=全书；可填 1,2,5-10"
                      />
                    </label>
                    <label className="small" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <input
                        type="checkbox"
                        checked={splitbookWritebackBatchForce}
                        onChange={(e) => setSplitbookWritebackBatchForce(e.target.checked)}
                      />
                      强制重算（忽略章节哈希）
                    </label>
                    <button onClick={() => void runSplitbookWritebackBatchPreview()} disabled={!selectedSplitbookId || splitbookWritebackBatchBusy}>
                      {splitbookWritebackBatchBusy ? "5.6A 执行中..." : "执行 5.6A 批量回写预览"}
                    </button>
                    <button
                      onClick={() => void runSplitbookWritebackBatchConfirm()}
                      disabled={
                        !selectedSplitbookId ||
                        splitbookWritebackBatchBusy ||
                        !splitbookWritebackPreviewToken ||
                        splitbookWritebackPreviewChangedTotal <= 0
                      }
                    >
                      {splitbookWritebackBatchBusy ? "5.6B 执行中..." : "执行 5.6B 批量回写确认"}
                    </button>
                  </div>
                  {splitbookWritebackBatchPreview ? (
                    <div className="small" style={{ marginTop: 6 }}>
                      批量预览：待回写 {Number(splitbookWritebackBatchPreview.changed_total || 0)} / {Number(splitbookWritebackBatchPreview.requested_total || 0)} 章，
                      跳过 {Number(splitbookWritebackBatchPreview.unchanged_total || 0)} 章，
                      token={String(splitbookWritebackBatchPreview.preview_token || "-")}
                      {splitbookWritebackBatchPreview.single_chapter_warning
                        ? `；提示：仅识别到单章且分块数 ${Number(splitbookWritebackBatchPreview.max_chunk_count || 0)}，建议先检查章节切分`
                        : ""}
                    </div>
                  ) : null}
                  {splitbookWritebackBatchConfirm ? (
                    <div className="small" style={{ marginTop: 4 }}>
                      批量确认：已回写 {Number(splitbookWritebackBatchConfirm.applied_total || 0)} / {Number(splitbookWritebackBatchConfirm.changed_total || 0)} 章，
                      失败 {Number(splitbookWritebackBatchConfirm.failed_total || 0)} 章，
                      写入 facts=
                      {Number(splitbookWritebackBatchConfirm.facts_written_total || 0)}，
                      growth={Number(splitbookWritebackBatchConfirm.growth_written_total || 0)}
                    </div>
                  ) : null}
                  <textarea
                    style={{ marginTop: 8, minHeight: 110 }}
                    placeholder="可选：粘贴写作侧章节正文，用于单章回写/体检/反照抄。"
                    value={splitbookWritebackText}
                    onChange={(e) => setSplitbookWritebackText(e.target.value)}
                  />
                  <div className="row" style={{ marginTop: 8 }}>
                    <button onClick={() => void runSplitbookWriteback()} disabled={!selectedSplitbookId}>
                      执行 5.6C 单章正文回写
                    </button>
                    <button onClick={() => void runSplitbookHealthReport()} disabled={!selectedSplitbookId}>
                      执行 5.7 章节体检报告
                    </button>
                    <button onClick={() => void runSplitbookAntiCopyCheck()} disabled={!selectedSplitbookId || !splitbookWritebackText.trim()}>
                      执行 5.8 反照抄检查
                    </button>
                  </div>
                  <div className="row" style={{ marginTop: 8, flexWrap: "wrap" }}>
                    <button onClick={() => void runSplitbookBuildLibrary()} disabled={!splitbooks.length}>
                      执行 5.9 构建跨书模板库
                    </button>
                    {showSplitbookAdvanced ? (
                      <input
                        style={{ minWidth: 360 }}
                        value={splitbookLibraryIds}
                        onChange={(e) => setSplitbookLibraryIds(e.target.value)}
                        placeholder="跨书模板源拆书ID（可选，逗号分隔；留空=当前全部拆书）"
                      />
                    ) : null}
                  </div>
                  {splitbookAntiCopyReport ? (
                    <div className="small" style={{ marginTop: 6 }}>
                      反照抄：风险={String(splitbookAntiCopyReport.risk_level || "-")}，得分=
                      {String(splitbookAntiCopyReport.anti_copy_score ?? "-")}
                    </div>
                  ) : null}
                  {splitbookLibraryResult ? (
                    <div className="small" style={{ marginTop: 4 }}>
                      跨书模板库：来源 {Number((splitbookLibraryResult.source_splitbook_ids || []).length)} 本，新增
                      {String(splitbookLibraryResult.created_count || 0)} 条模板
                    </div>
                  ) : null}
                </div>
              </details>

              <div className="row" style={{ marginTop: 8, marginBottom: 6 }}>
                <strong>拆书列表</strong>
                <span className="small">点击任意条目可切换当前拆书</span>
              </div>
              <div className="scroll" style={{ maxHeight: 220 }}>
                {splitbooks.map((sb) => (
                  <div key={sb.splitbook_id} className="splitbook-list-item-row">
                    <button
                      className={`node-item ${selectedSplitbookId === sb.splitbook_id ? "active" : ""}`}
                      onClick={() => {
                        setSelectedSplitbookId(sb.splitbook_id);
                        if (sb.source_path) {
                          setSplitbookPath(sb.source_path);
                          void verifySplitbookPath(sb.source_path, { silent: true });
                        } else {
                          setSplitbookPathCheck(null);
                        }
                      }}
                    >
                      <div style={{ width: "100%" }}>
                        <div className="row">
                          <strong>{sb.name}</strong>
                          <code>{sb.allow_guard ? "保护：开（guard:on）" : "保护：关（guard:off）"}</code>
                        </div>
                        <div className="small">导入={formatPipelineStatus(sb.ingest_status)} · 向量化={formatPipelineStatus(sb.embed_status)}</div>
                        <div className="small">{sb.splitbook_id}</div>
                      </div>
                    </button>
                    <button
                      className="danger"
                      onClick={() => void deleteSplitbook(sb.splitbook_id)}
                      disabled={splitbookDeletingId === sb.splitbook_id}
                      title="删除该拆书（保留模板资产）"
                    >
                      {splitbookDeletingId === sb.splitbook_id ? "删除中..." : "删除"}
                    </button>
                    {showSplitbookAdvanced ? (
                      <button
                        className="danger"
                        onClick={() => void deleteSplitbook(sb.splitbook_id, { purgeAssets: true })}
                        disabled={splitbookDeletingId === sb.splitbook_id}
                        title="删除拆书并清理其模板资产"
                      >
                        彻底删除
                      </button>
                    ) : null}
                  </div>
                ))}
                {splitbooks.length === 0 ? <div className="hint">暂无拆书。</div> : null}
              </div>
            </div>
            <div>
              <div className="row" style={{ marginBottom: 8 }}>
                <strong>详情</strong>
              </div>
              {selectedSplitbook ? (
                <>
                  <div className="splitbook-status-grid" style={{ marginBottom: 8 }}>
                    <div className="summary-card">
                      <div className="k">导入状态</div>
                      <div className="v">{formatPipelineStatus(selectedSplitbook.ingest_status)}</div>
                    </div>
                    <div className="summary-card">
                      <div className="k">向量化状态</div>
                      <div className="v">{formatPipelineStatus(selectedSplitbook.embed_status)}</div>
                    </div>
                    <div className="summary-card">
                      <div className="k">向量化进度</div>
                      <div className="v">
                        {selectedSplitbookEmbedProgressPct}%
                        {selectedSplitbookEmbedActiveJob || selectedSplitbookEmbedActiveByStats
                          ? "（执行中）"
                          : splitbookCanResumeEmbed
                            ? "（待继续）"
                            : ""}
                      </div>
                    </div>
                    <div className="summary-card">
                      <div className="k">活跃任务</div>
                      <div className="v">
                        {selectedSplitbookRunningCount}
                        {selectedSplitbookQueuedCount > 0 ? `（排队 ${selectedSplitbookQueuedCount}）` : ""}
                      </div>
                    </div>
                    <div className="summary-card">
                      <div className="k">结构抽取</div>
                      <div className="v">{splitbookStructuredDone ? "已完成" : "待完成"}</div>
                    </div>
                    <div className="summary-card">
                      <div className="k">模板/画像</div>
                      <div className="v">
                        模板 {splitbookTemplatesDone ? "已完成" : "待完成"} · 画像 {splitbookProfileDone ? "已完成" : "待完成"}
                      </div>
                    </div>
                  </div>
                  {selectedSplitbookRecoverHint === "manual_resume_required" ? (
                    <div className="small danger">检测到异常中断：该拆书需手动“继续向量化”。</div>
                  ) : null}
                  <div className="splitbook-pipeline-strip">
                    <span>流程状态：{formatSplitbookStepLabel(selectedSplitbookLiveStep)}</span>
                    {selectedSplitbookLivePhase ? <span>阶段：{formatPhaseLabel(selectedSplitbookLivePhase)}</span> : null}
                    <span>进度：{splitbookPipelineProgressPct}%</span>
                    {splitbookPipelineError ? <span className="danger">最近错误：{splitbookPipelineError}</span> : null}
                  </div>
                  <div className="pipeline-progress" style={{ marginTop: 6 }}>
                    <span style={{ width: `${splitbookPipelineProgressPct}%` }} />
                  </div>
                  <details style={{ marginTop: 8 }}>
                    <summary className="small">更多状态与诊断</summary>
                    <div className="small">路径：<code>{selectedSplitbook.source_path || "-"}</code></div>
                    <div className="small">产物目录：<code>{splitbookOutputDir || "-"}</code></div>
                    <div className="small">分片数：<code>{Number(selectedSplitbook.stats?.chunks_total || 0)}</code></div>
                    <div className="small">已向量化：<code>{Number(selectedSplitbook.stats?.embedded_total || 0)}</code></div>
                    <div className="small">向量化报告：<code>{String(selectedSplitbook.stats?.embedding_report_path || "-")}</code></div>
                    {selectedSplitbook.stats?.embedding_report_error ? (
                      <div className="small danger">向量化报告错误：{String(selectedSplitbook.stats?.embedding_report_error)}</div>
                    ) : null}
                    {selectedSplitbook.stats?.last_error ? (
                      <div className="small danger">最近错误：{String(selectedSplitbook.stats?.last_error)}</div>
                    ) : null}
                    {splitbookIngestDoneActiveConflict || splitbookEmbedDoneActiveConflict ? (
                      <div className="small">
                        一致性保护已触发：
                        {splitbookIngestDoneActiveConflict ? " 导入已完成但存在旧活跃标记；" : ""}
                        {splitbookEmbedDoneActiveConflict ? " 向量化已完成但存在旧活跃标记；" : ""}
                        系统已自动忽略，不阻塞后续步骤。
                      </div>
                    ) : null}
                    {showSplitbookAdvanced ? (
                      <>
                        <div className="small">结构事实：<code>{Number(selectedSplitbook.stats?.fact_total || 0)}</code></div>
                        <div className="small">成长账本：<code>{Number(selectedSplitbook.stats?.growth_rows || 0)}</code></div>
                        <div className="small">关联任务总数：<code>{selectedSplitbookJobs.length}</code></div>
                      </>
                    ) : null}
                    {showSplitbookAdvanced && selectedSplitbookJobs.length ? (
                      <div className="scroll" style={{ maxHeight: 160, marginTop: 8 }}>
                        {selectedSplitbookJobs.map((j) => {
                          const pct = Math.max(0, Math.min(100, Math.round(Number((j.progress as any)?.pct ?? (j.progress_value || 0) * 100))));
                          return (
                            <div key={j.job_id} className="issue-item">
                              <div className="row">
                                <strong>{formatJobTypeLabel(j.job_type, j.capability_id)}</strong>
                                <code>{formatJobStatusLabel(j.status)} · {pct}%</code>
                              </div>
                              <div className="small">阶段：{formatPhaseLabel(j.stage)}</div>
                              {j.error ? <div className="small danger">错误：{formatJobErrorMessage(j.error)}</div> : null}
                              <div className="row" style={{ marginTop: 4 }}>
                                <button onClick={() => void openJobInCenter(j)}>在任务中心打开</button>
                                {canCancelJob(j.status) ? (
                                  <button className="danger" onClick={() => void cancelJob(j)}>中止任务</button>
                                ) : null}
                                {canResumeJob(j) ? (
                                  <button
                                    onClick={() => void resumeJob(j)}
                                    disabled={jobResumeBusyId === String(j.job_id || "")}
                                  >
                                    {jobResumeBusyId === String(j.job_id || "") ? "继续中..." : "继续任务"}
                                  </button>
                                ) : null}
                              </div>
                              <div style={{ height: 8, background: "#eee", borderRadius: 6, overflow: "hidden", marginTop: 4 }}>
                                <div style={{ width: `${pct}%`, height: "100%", background: "#2d7ef7" }} />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : null}
                  </details>
                  <div className="row" style={{ marginTop: 8, flexWrap: "wrap" }}>
                    <button onClick={() => void setSplitbookAllowGuard(!selectedSplitbook.allow_guard)}>
                      守卫开关(allow_guard)：{selectedSplitbook.allow_guard ? "开(ON)" : "关(OFF)"}
                    </button>
                    <button onClick={() => void refreshSplitbookWorkspace()} disabled={splitbookRefreshBusy}>
                      {splitbookRefreshBusy ? "刷新中..." : "刷新拆书状态"}
                    </button>
                    <button onClick={() => void triggerSplitbookJob("embed")} disabled={!splitbookCanResumeEmbed}>
                      继续向量化
                    </button>
                    <button
                      className="danger"
                      onClick={() => void deleteSplitbook(selectedSplitbook.splitbook_id)}
                      disabled={splitbookDeletingId === selectedSplitbook.splitbook_id}
                    >
                      {splitbookDeletingId === selectedSplitbook.splitbook_id ? "删除中..." : "删除当前拆书"}
                    </button>
                    {showSplitbookAdvanced ? (
                      <button
                        className="danger"
                        onClick={() => void deleteSplitbook(selectedSplitbook.splitbook_id, { purgeAssets: true })}
                        disabled={splitbookDeletingId === selectedSplitbook.splitbook_id}
                      >
                        彻底删除（含模板资产）
                      </button>
                    ) : null}
                  </div>
                  <div className="splitbook-step-card" style={{ marginTop: 10 }}>
                    <div className="row">
                      <strong>结构账本（表格视图）</strong>
                      <span className="small">视图：{splitbookLedgerView === "chapter" ? "章节" : "角色"}</span>
                    </div>
                    <div className="small">
                      账本统计：事实 {Number(splitbookLedgerSummary?.fact_rows || 0)} · 成长行 {Number(splitbookLedgerSummary?.growth_rows || 0)} · 角色 {Number(splitbookLedgerSummary?.character_rows || 0)}
                    </div>
                    <div className="scroll" style={{ maxHeight: 180, marginTop: 6 }}>
                      <table style={{ width: "100%", borderCollapse: "collapse" }}>
                        <thead>
                          <tr>
                            <th style={{ textAlign: "left" }}>章节</th>
                            <th style={{ textAlign: "left" }}>角色</th>
                            <th style={{ textAlign: "left" }}>阶段</th>
                            <th style={{ textAlign: "left" }}>压力</th>
                            <th style={{ textAlign: "left" }}>代价</th>
                            <th style={{ textAlign: "left" }}>收获</th>
                          </tr>
                        </thead>
                        <tbody>
                          {splitbookLedgerRows.slice(0, 60).map((row: any, idx: number) => (
                            <tr key={`${idx}-${row.chapter_no || "-"}-${row.character_name || "-"}`}>
                              <td>{row.chapter_no || "-"}</td>
                              <td>{row.character_name || "-"}</td>
                              <td>{row.growth_stage || row.latest_stage || "-"}</td>
                              <td>{row.pressure || row.latest_pressure || "-"}</td>
                              <td>{row.cost || row.latest_cost || "-"}</td>
                              <td>{row.gain || row.latest_gain || "-"}</td>
                            </tr>
                          ))}
                          {splitbookLedgerRows.length === 0 ? (
                            <tr>
                              <td colSpan={6} className="small">暂无账本数据，请先执行“结构抽取”。</td>
                            </tr>
                          ) : null}
                        </tbody>
                      </table>
                    </div>
                  </div>
                  <div className="splitbook-step-card" style={{ marginTop: 10 }}>
                    <div className="row">
                      <strong>大纲与章节包预览</strong>
                    </div>
                    <div className="small">大纲章节数：{Number(splitbookOutlinePreview?.chapter_total || 0)}</div>
                    <div className="scroll" style={{ maxHeight: 140, marginTop: 6 }}>
                      {(splitbookOutlinePreview?.chapters || []).slice(0, 20).map((c: any) => (
                        <div key={`outline-${c.chapter_no}`} className="small">
                          第{c.chapter_no}章 · {c.chapter_title} · 冲突：{c.summary?.conflict || "-"}
                        </div>
                      ))}
                    </div>
                    {splitbookChapterPack ? (
                      <div className="small" style={{ marginTop: 6 }}>
                        章节包：第{splitbookChapterPack.chapter_no}章，冲突 {Number((splitbookChapterPack.key_conflicts || []).length)}，
                        伏笔 {Number((splitbookChapterPack.foreshadow || []).length)}，回收 {Number((splitbookChapterPack.payoff || []).length)}
                        {splitbookChapterPack.fallback_used ? "（已自动回退到可用章节）" : ""}
                      </div>
                    ) : null}
                  </div>
                  {splitbookHealthReport ? (
                    <div className="splitbook-step-card" style={{ marginTop: 10 }}>
                      <div className="row">
                        <strong>章节体检报告</strong>
                        <span className="small">评分：{Number(splitbookHealthReport.score || 0)}</span>
                      </div>
                      {(splitbookHealthReport.checks || []).map((check: any, idx: number) => (
                        <div key={`check-${idx}`} className="small">
                          {check.name}：{check.status === "ok" ? "通过" : "预警"}
                        </div>
                      ))}
                      {(splitbookHealthReport.issues || []).map((issue: any, idx: number) => (
                        <div key={`issue-${idx}`} className="small danger">
                          [{issue.severity}] {issue.detail}
                        </div>
                      ))}
                    </div>
                  ) : null}
                  {splitbookAntiCopyReport ? (
                    <div className="splitbook-step-card" style={{ marginTop: 10 }}>
                      <div className="row">
                        <strong>反照抄检查报告</strong>
                        <span className="small">
                          风险：{String(splitbookAntiCopyReport.risk_level || "-")} · 得分：
                          {String(splitbookAntiCopyReport.anti_copy_score ?? "-")}
                        </span>
                      </div>
                      <div className="small">
                        max_overlap={String(splitbookAntiCopyReport?.metrics?.max_overlap_ratio ?? "-")} · max_lcs=
                        {String(splitbookAntiCopyReport?.metrics?.max_lcs_ratio ?? "-")} · 样本块=
                        {String(splitbookAntiCopyReport?.metrics?.sampled_chunks ?? "-")}
                      </div>
                      <div className="scroll" style={{ maxHeight: 120, marginTop: 6 }}>
                        {(splitbookAntiCopyReport.top_hits || []).map((hit: any, idx: number) => (
                          <div key={`copy-hit-${idx}`} className="small">
                            # {idx + 1} 章={String(hit.chapter_no || "-")} overlap={String(hit.overlap_ratio || "-")} lcs=
                            {String(hit.lcs_ratio || "-")}
                          </div>
                        ))}
                        {!(splitbookAntiCopyReport.top_hits || []).length ? (
                          <div className="small">未命中可疑重复片段。</div>
                        ) : null}
                      </div>
                      <div className="small" style={{ marginTop: 6 }}>
                        建议：{Array.isArray(splitbookAntiCopyReport.suggestions) ? splitbookAntiCopyReport.suggestions.join("；") : "-"}
                      </div>
                    </div>
                  ) : null}
                  {splitbookLibraryResult ? (
                    <div className="splitbook-step-card" style={{ marginTop: 10 }}>
                      <div className="row">
                        <strong>跨书模板库构建结果</strong>
                        <span className="small">新增：{String(splitbookLibraryResult.created_count || 0)}</span>
                      </div>
                      <div className="small">
                        来源拆书：{Number((splitbookLibraryResult.source_splitbook_ids || []).length)} 本 · 章节总数：
                        {String(splitbookLibraryResult?.summary?.chapters ?? "-")}
                      </div>
                      {(splitbookLibraryResult.created_items || []).map((it: any, idx: number) => (
                        <div key={`lib-item-${idx}`} className="small">
                          {String(it.asset_type || "-")} · {String(it.name || "-")}
                        </div>
                      ))}
                    </div>
                  ) : null}
                </>
              ) : (
                <div className="hint">请选择拆书。</div>
              )}
            </div>
          </div>
            </section>
          )
        : null}

      {showWritingWorkspace ? (
      <section id="section-outline-tools" className="wb-topbar wb-outline-toolbar">
        <div className="outline-context">
          <div className="summary-card">
            <div className="k">当前书籍 ID</div>
            <div className="v mono">{bookId || "-"}</div>
          </div>
          <div className="summary-card">
            <div className="k">当前章节 ID</div>
            <div className="v mono">{chapterId || "-"}</div>
          </div>
          <div className="summary-card">
            <div className="k">服务地址</div>
            <div className="v mono">{baseUrl || "-"}</div>
          </div>
          <div className="summary-card">
            <div className="k">章纲注入状态</div>
            <div className="v">
              {outlineInjectBadgeText}
              {outlineInjectStatus.version > 0 ? ` · v${outlineInjectStatus.version}` : ""}
              {outlineInjectStatus.nodeCount > 0 ? ` · 节点 ${outlineInjectStatus.nodeCount}` : ""}
            </div>
          </div>
        </div>
        <label>
          大纲版本（Version）
          <select value={selectedVersion} onChange={(e) => setSelectedVersion(e.target.value)}>
            <option value="latest">最新（latest）</option>
            {versions.map((v) => (
              <option key={v.outline_id} value={String(v.version)}>
                v{v.version}
              </option>
            ))}
          </select>
        </label>
        <div className="outline-action-row">
          <button onClick={() => loadOutline(selectedVersion)} disabled={busy}>加载大纲</button>
          <button onClick={() => saveOutline("manual edit")} disabled={busy || !dirty || !outline}>保存大纲</button>
        </div>
        <div className="small" style={{ gridColumn: "1 / -1", marginTop: 2 }}>
          Eval 提示：`chapter_version_id` 留空时，后端会自动使用该章节最新版本。
        </div>
        <div className="small" style={{ gridColumn: "1 / -1" }}>
          章纲自动注入：{outlineInjectStatus.message}（最近检测：{outlineInjectUpdatedText}）
        </div>
      </section>
      ) : null}

      {showWritingWorkspace && !writerSimpleMode ? (
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
      ) : null}

      {showWritingWorkspace ? (
      <main id="section-main-editor" className="wb-grid">
        <aside className="wb-panel node-list">
          <h3>节点</h3>
          <div className="scroll">
            {(outline?.nodes || []).map((n) => (
              <button key={n.node_id} className={`node-item ${selectedNodeId === n.node_id ? "active" : ""}`} onClick={() => setSelectedNodeId(n.node_id)}>
                <div>
                  <div className="row"><code>{n.node_id}</code><span className="badge">{n.type}</span></div>
                  <div className="summary-line">{(n.summary || "").split("\n")[0] || "(空)"}</div>
                </div>
              </button>
            ))}
          </div>
        </aside>

        <section className="wb-panel node-editor">
          <h3>节点编辑器</h3>
          {selectedNode ? (
            <>
              <div className="meta-row"><code>{selectedNode.node_id}</code><span className="badge">{selectedNode.type}</span></div>
              <textarea rows={12} value={selectedNode.summary || ""} onChange={(e) => updateNodeSummary(e.target.value)} />
              <div className="hint">编辑后点击“保存大纲”生成新版本</div>
            </>
          ) : (
            <div className="hint">选择一个节点开始编辑</div>
          )}

          <h4>评估问题</h4>
          <div className="issues">
            {evalIssueViews.length === 0 ? <div className="hint">暂无评估结果</div> : null}
            {evalIssueViews.map((it, idx) => (
              <div key={idx} className="issue-item">
                <strong>{it.typeZh}</strong>
                <span className="small">（严重度：{it.severityZh}）</span>
                <div className="small">位置：{it.where}</div>
                <div>{it.detailZh}</div>
                {it.typeRaw && it.typeRaw !== it.typeZh ? <div className="small">原始类型：{it.typeRaw}</div> : null}
              </div>
            ))}
          </div>
        </section>

        <aside className="wb-panel patch-panel">
          <h3>补丁</h3>
          <div className="scroll">
            {patches.length === 0 ? <div className="hint">请先执行控制计划（Control Plan）。</div> : null}
            {patches.map((p) => (
              <label key={p.patch_id || Math.random()} className="patch-item">
                <input type="checkbox" checked={Boolean(selectedPatches[p.patch_id])} onChange={(e) => setSelectedPatches({ ...selectedPatches, [p.patch_id]: e.target.checked })} />
                <div>
                  <div className="row"><strong>{p.patch_type}</strong><code>{p.patch_id || "无ID(no-id)"}</code></div>
                  <div className="small">位置：{JSON.stringify(p.where || {})}</div>
                  {p.change?.after ? <pre>{p.change.after}</pre> : null}
                  {p.insert?.node?.summary ? <pre>{p.insert.node.summary}</pre> : null}
                </div>
              </label>
            ))}
          </div>
        </aside>
      </main>
      ) : null}

      {showJobs
        ? renderTopPanel(
            "任务中心",
            () => setShowJobs(false),
            <section id="section-jobs" className="wb-panel" style={{ marginTop: 0 }}>
          <div className="row" style={{ marginBottom: 8 }}>
            <h3 style={{ margin: 0 }}>任务中心</h3>
            {(() => {
              const refresh = getJobRefreshIndicatorState();
              return (
                <span
                  className="small"
                  style={{
                    marginLeft: 10,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    borderRadius: 999,
                    padding: "2px 10px",
                    color: refresh.color,
                    background: refresh.bg,
                    border: `1px solid ${refresh.color}33`,
                    whiteSpace: "nowrap",
                  }}
                >
                  <span style={{ width: 8, height: 8, borderRadius: "50%", background: refresh.color, display: "inline-block" }} />
                  {refresh.text}
                </span>
              );
            })()}
            <div className="row">
              <button onClick={() => setJobTab("queued")} className={jobTab === "queued" ? "active" : ""}>排队中</button>
              <button onClick={() => setJobTab("running")} className={jobTab === "running" ? "active" : ""}>进行中（含排队）</button>
              <button onClick={() => setJobTab("succeeded")} className={jobTab === "succeeded" ? "active" : ""}>已完成</button>
              <button onClick={() => setJobTab("failed")} className={jobTab === "failed" ? "active" : ""}>失败</button>
              <button onClick={() => setJobTab("canceled")} className={jobTab === "canceled" ? "active" : ""}>已中止</button>
            </div>
          </div>
          <div className="row" style={{ marginBottom: 8, gap: 8, flexWrap: "wrap" }}>
            <button onClick={() => void pollJobs()} disabled={jobCleanupBusy}>刷新当前列表</button>
            <label className="small row" style={{ gap: 6 }}>
              <input
                type="checkbox"
                checked={jobAutoRefreshEnabled}
                onChange={(e) => setJobAutoRefreshEnabled(e.target.checked)}
              />
              自动刷新
            </label>
            <label className="small row" style={{ gap: 6 }}>
              刷新间隔
              <select
                value={String(jobPollIntervalMs)}
                onChange={(e) => setJobPollIntervalMs(Math.max(2000, Number(e.target.value) || 5000))}
                disabled={!jobAutoRefreshEnabled}
              >
                <option value="2000">2秒</option>
                <option value="5000">5秒</option>
                <option value="10000">10秒</option>
                <option value="15000">15秒</option>
              </select>
            </label>
            <label className="small row" style={{ gap: 6 }}>
              <input
                type="checkbox"
                checked={jobInspectLock}
                onChange={(e) => setJobInspectLock(e.target.checked)}
              />
              锁定右侧详情（查看时不跟随刷新）
            </label>
            <label className="small row" style={{ gap: 6 }}>
              <input
                type="checkbox"
                checked={jobAutoPauseOnInspect}
                onChange={(e) => setJobAutoPauseOnInspect(e.target.checked)}
                disabled={!jobAutoRefreshEnabled}
              />
              阅读详情时自动暂停刷新
            </label>
            <button
              onClick={() => void resumeStalledJobsInView()}
              disabled={jobResumeBatchBusy || !jobs.some((j) => isJobLikelyStalled(j))}
            >
              {jobResumeBatchBusy ? "继续中..." : "继续疑似中断任务"}
            </button>
            <button
              className="danger"
              onClick={() => cleanupCurrentJobTabHistory()}
              disabled={jobTab === "running" || jobTab === "queued" || jobCleanupBusy}
            >
              {jobCleanupBusy ? "清理中..." : `清理当前页（${formatJobStatusLabel(jobTab)}）`}
            </button>
            <button className="danger" onClick={() => cleanupAllFinishedJobsHistory()} disabled={jobCleanupBusy}>
              {jobCleanupBusy ? "清理中..." : "清理全部已完成"}
            </button>
          </div>
          {!jobAutoRefreshEnabled ? <div className="small" style={{ marginBottom: 8 }}>自动刷新已关闭，任务状态仅在手动刷新时更新。</div> : null}
          {jobAutoRefreshEnabled && jobAutoPauseOnInspect && jobInspectingDetail ? (
            <div className="small" style={{ marginBottom: 8 }}>自动刷新已暂停：正在查看任务详情/日志，离开右侧详情区后自动恢复。</div>
          ) : null}
          {chapterGenerationTrace.updatedAt ? (
            <div className="wb-panel" style={{ minHeight: "auto", marginBottom: 8, padding: 10 }}>
              <div className="row" style={{ marginBottom: 4 }}>
                <strong>最近 1.5 章节生成依据</strong>
                <code>{chapterGenerationTrace.mode === "batch" ? "批量" : "单章"}</code>
              </div>
              <div className="small">依据：{chapterGenerationTrace.basis || "待执行"}</div>
              <div className="small">目标章节：{chapterGenerationTrace.chapters || "未记录"}</div>
              <div className="small">
                结果：{formatStructureStepStatusLabel(chapterGenerationTrace.status)}
                {chapterGenerationTrace.detail ? ` · ${chapterGenerationTrace.detail}` : ""}
              </div>
              <div className="small">
                时间：{new Date(chapterGenerationTrace.updatedAt).toLocaleString("zh-CN")}
              </div>
              <div className="row" style={{ marginTop: 6, gap: 8, flexWrap: "wrap" }}>
                <button onClick={() => openWritingStudioForChapterGenerationTrace()}>定位到写作工作台（1.5）</button>
              </div>
            </div>
          ) : null}
          <div className="row" style={{ marginBottom: 8 }}>
            <label style={{ flex: 1 }}>
              技能运行筛选（skill_run_id）
              <input
                value={jobSkillRunFilter}
                onChange={(e) => setJobSkillRunFilter(e.target.value)}
                placeholder="粘贴技能运行 ID（skill_run_id）定位任务"
              />
            </label>
            <button onClick={() => setJobSkillRunFilter("")}>清除</button>
          </div>
          <div className="wb-panel" style={{ minHeight: "auto", marginBottom: 10, padding: 10 }}>
            <div className="row" style={{ marginBottom: 6 }}>
              <strong>章节确认任务（当前书）</strong>
              <span className="small">
                {bookId
                  ? `共 ${Number(draftConfirmSummary?.total || draftConfirmTasks.length || 0)} 章，已确认 ${
                      Number(draftConfirmSummary?.confirmed || 0)
                    } 章，待确认 ${draftConfirmPendingCount} 章`
                  : "请先选择书籍"}
              </span>
            </div>
            <div className="row" style={{ marginBottom: 8, gap: 8, flexWrap: "wrap" }}>
              <button onClick={() => void loadDraftConfirmations()} disabled={!bookId || draftConfirmLoading}>
                {draftConfirmLoading ? "刷新中..." : "刷新章节确认状态"}
              </button>
              <button onClick={() => openOptionalPanel("versions")} disabled={!chapterId}>
                打开版本中心
              </button>
              <button onClick={() => scrollToSection("section-writing-studio")} disabled={!bookId}>
                回到写作工作台
              </button>
            </div>
            {!bookId ? (
              <div className="small">未选择书籍，无法加载章节确认任务。</div>
            ) : (
              <div className="scroll" style={{ maxHeight: 200 }}>
                {draftConfirmSortedTasks.length === 0 ? (
                  <div className="small">暂无章节数据。</div>
                ) : (
                  draftConfirmSortedTasks.map((it: any) => {
                    const isPending = String(it?.confirm_status || "").toLowerCase() !== "confirmed";
                    const cid = String(it?.chapter_id || "");
                    const did = String(it?.selected_draft_id || "");
                    return (
                      <div key={`draft-confirm-${cid}`} className="node-item" style={{ cursor: "default" }}>
                        <div style={{ width: "100%" }}>
                          <div className="row" style={{ alignItems: "center" }}>
                            <strong>第{Number(it?.chapter_no || 0)}章 · {String(it?.chapter_title || "未命名章节")}</strong>
                            <code>{isPending ? "待确认" : "已确认"}</code>
                          </div>
                          <div className="small">
                            {isPending
                              ? "当前无已确认草稿，请先生成并确认版本（4.1→4.2）"
                              : `已确认稿件：${did.slice(0, 12)}... · 分支 ${String(it?.selected_branch || "-")} · ${
                                  String(it?.selected_at || "")
                                    ? `确认时间 ${String(it?.selected_at)}`
                                    : "已写入确认记录"
                                }`}
                          </div>
                          <div className="row" style={{ marginTop: 6, gap: 6, flexWrap: "wrap" }}>
                            <button
                              onClick={() => {
                                if (cid) setChapterId(cid);
                                scrollToSection("section-writing-studio");
                              }}
                            >
                              定位章节
                            </button>
                            {isPending ? (
                              <button
                                onClick={() => {
                                  if (cid) setChapterId(cid);
                                  scrollToSection("section-writing-studio");
                                  setStatus(`请在“4) 确认章节草稿”执行 4.1→4.2：第${Number(it?.chapter_no || 0)}章`);
                                }}
                              >
                                去确认
                              </button>
                            ) : null}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </div>
          <div className="job-grid">
            <div className="scroll">
              {jobs.map((j) => (
                <button data-job-id={j.job_id} key={j.job_id} className={`node-item ${selectedJob?.job_id === j.job_id ? "active" : ""}`} onClick={() => setSelectedJob(j)}>
                  <div style={{ width: "100%" }}>
                    <div className="row"><strong>{formatJobTypeLabel(j.job_type, j.capability_id)}</strong><code>{formatJobStatusLabel(String(j.status || ""))}</code></div>
                    <div className="small">书籍：{formatJobBookContext(j)}</div>
                    <div className="small">来源：{getJobSourceInfo(j).origin}</div>
                    {getJobTriggerMeta(j).mode ? <div className="small">触发方式：{formatTriggerModeLabel(getJobTriggerMeta(j).mode)}</div> : null}
                    {j.splitbook_id ? <div className="small">拆书ID：{String(j.splitbook_id)}</div> : null}
                    <div className="small">阶段：{formatPhaseLabel(j.stage)} · 进度：{Math.round((j.progress_value || 0) * 100)}%</div>
                    {isJobLinkedToChapterGenerationTrace(j) ? (
                      <div className="small">关联 1.5 章节生成：{chapterGenerationTrace.chapters || "章节未记录"} · {formatStructureStepStatusLabel(chapterGenerationTrace.status)}</div>
                    ) : null}
                    {getEmbedTelemetryText(j) ? <div className="small">{getEmbedTelemetryText(j)}</div> : null}
                    {isJobLikelyStalled(j) ? (
                      <div className="small danger">疑似中断：进度长时间未更新，可在右侧点“继续任务”。</div>
                    ) : isJobLongGapButExpected(j) ? (
                      <div className="small">大型拆书任务处理中：进度可能间歇更新，请稍候。</div>
                    ) : null}
                    {j.error ? <div className="small danger">错误：{formatJobErrorMessage(j.error)}</div> : null}
                    {extractSkillRunId(j) ? <div className="small">技能运行ID（skill_run）：{extractSkillRunId(j)}</div> : null}
                    <div className="small">{j.job_id}</div>
                  </div>
                </button>
              ))}
            </div>
            <div
              onMouseEnter={() => {
                if (showJobs && jobAutoPauseOnInspect) setJobInspectingDetail(true);
              }}
              onMouseLeave={() => {
                if (showJobs && jobAutoPauseOnInspect) setJobInspectingDetail(false);
              }}
              onFocusCapture={() => {
                if (showJobs && jobAutoPauseOnInspect) setJobInspectingDetail(true);
              }}
              onBlurCapture={(e) => {
                if (!showJobs || !jobAutoPauseOnInspect) return;
                const next = e.relatedTarget as Node | null;
                if (!next || !e.currentTarget.contains(next)) setJobInspectingDetail(false);
              }}
            >
              {selectedJob ? (
                <>
                  <h4>{formatJobTypeLabel(selectedJob.job_type, selectedJob.capability_id)}</h4>
                  <div className="small">关联书籍：<code>{formatJobBookContext(selectedJob)}</code></div>
                  <div className="small">来源功能：<code>{getJobSourceInfo(selectedJob).origin}</code></div>
                  {getJobTriggerMeta(selectedJob).mode ? <div className="small">触发方式：<code>{formatTriggerModeLabel(getJobTriggerMeta(selectedJob).mode)}</code></div> : null}
                  {getJobTriggerMeta(selectedJob).entry ? <div className="small">触发入口：<code>{getJobTriggerMeta(selectedJob).entry}</code></div> : null}
                  {selectedJob.book_id ? <div className="small">书籍ID：<code>{String(selectedJob.book_id)}</code></div> : null}
                  {selectedJob.chapter_id ? <div className="small">章节ID：<code>{String(selectedJob.chapter_id)}</code></div> : null}
                  {selectedJob.splitbook_id ? <div className="small">拆书ID：<code>{String(selectedJob.splitbook_id)}</code></div> : null}
                  {selectedJob.splitbook_name ? <div className="small">拆书名称：<code>{String(selectedJob.splitbook_name)}</code></div> : null}
                  {selectedJob.chapter_title ? <div className="small">章节标题：<code>{String(selectedJob.chapter_title)}</code></div> : null}
                  <div className="small">任务类型：<code>{selectedJob.job_type}</code></div>
                  <div className="small">能力标识：<code>{selectedJob.capability_id}</code></div>
                  <div className="small">阶段：{formatPhaseLabel(selectedJob.stage)}</div>
                  <div className="small">状态：{formatJobStatusLabel(String(selectedJob.status || ""))}</div>
                  {isJobLinkedToChapterGenerationTrace(selectedJob) ? (
                    <div className="wb-panel" style={{ minHeight: "auto", margin: "8px 0", padding: 8 }}>
                      <div className="small"><strong>1.5 章节生成依据（关联）</strong></div>
                      <div className="small">依据：{chapterGenerationTrace.basis || "待执行"}</div>
                      <div className="small">目标章节：{chapterGenerationTrace.chapters || "未记录"}</div>
                      <div className="small">结果：{formatStructureStepStatusLabel(chapterGenerationTrace.status)}{chapterGenerationTrace.detail ? ` · ${chapterGenerationTrace.detail}` : ""}</div>
                      <div className="small">
                        更新时间：{chapterGenerationTrace.updatedAt ? new Date(chapterGenerationTrace.updatedAt).toLocaleString("zh-CN") : "-"}
                      </div>
                      <div className="row" style={{ marginTop: 6, gap: 8 }}>
                        <button onClick={() => openWritingStudioForChapterGenerationTrace()}>定位到写作工作台（1.5）</button>
                      </div>
                    </div>
                  ) : null}
                  {getEmbedTelemetryText(selectedJob) ? <div className="small">{getEmbedTelemetryText(selectedJob)}</div> : null}
                  {isJobLikelyStalled(selectedJob) ? (
                    <div className="small danger">检测：该任务疑似因中断卡住，可点击“继续任务”恢复。</div>
                  ) : isJobLongGapButExpected(selectedJob) ? (
                    <div className="small">检测：该拆书任务仍在运行，进度可能间歇更新。</div>
                  ) : null}
                  <div className="small">请求参数：{JSON.stringify(selectedJob.payload || {}, null, 2)}</div>
                  <div className="small">结果：{JSON.stringify(selectedJob.result || {}, null, 2)}</div>
                  <div className="small">错误：{formatJobErrorMessage(selectedJob.error)}</div>
                  {selectedJob.error ? <div className="small">错误详情（原始）：{JSON.stringify(selectedJob.error || {}, null, 2)}</div> : null}
                  <h5>日志</h5>
                  <pre style={{ maxHeight: 220, overflow: "auto" }}>{(selectedJob.logs || []).join("\n") || "（无日志）"}</pre>
                  <div className="row" style={{ marginTop: 8, flexWrap: "wrap" }}>
                    <button onClick={() => navigateToJobSource(selectedJob)}>{getJobSourceInfo(selectedJob).actionLabel}</button>
                    {canCancelJob(selectedJob.status) ? (
                      <button className="danger" onClick={() => void cancelJob(selectedJob)}>中止任务</button>
                    ) : null}
                    {canResumeJob(selectedJob) ? (
                      <button
                        onClick={() => void resumeJob(selectedJob)}
                        disabled={jobResumeBusyId === String(selectedJob.job_id || "")}
                      >
                        {jobResumeBusyId === String(selectedJob.job_id || "") ? "继续中..." : "继续任务"}
                      </button>
                    ) : null}
                    {String(selectedJob.status || "").toLowerCase() === "failed" ? (
                      <button onClick={() => retryJob(selectedJob)}>重试任务</button>
                    ) : null}
                    {canDeleteJobRecord(selectedJob.status) ? (
                      <button
                        className="danger"
                        onClick={() => void deleteJobRecord(selectedJob)}
                        disabled={jobDeleteBusyId === String(selectedJob.job_id || "")}
                      >
                        {jobDeleteBusyId === String(selectedJob.job_id || "") ? "删除中..." : "删除记录"}
                      </button>
                    ) : null}
                  </div>
                </>
              ) : (
                <div className="hint">选择一个任务（job）查看详情</div>
              )}
            </div>
          </div>
            </section>
          )
        : null}

      {showTensionCenter
        ? renderTopPanel(
            "全书张力看板",
            () => setShowTensionCenter(false),
            <section className="wb-panel" style={{ marginTop: 0 }}>
              <h3>全书张力看板</h3>
              <div className="row" style={{ gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
                <button onClick={() => void runBookTensionAnalyze()} disabled={busy || !bookId}>分析全书</button>
                <button onClick={() => void loadBookTensionReport()} disabled={busy || !bookId}>加载报告</button>
                <button onClick={() => void loadLatestChapterReport()} disabled={busy || !chapterId}>加载章节报告</button>
                <button onClick={() => void createRepairPlan()} disabled={busy || !bookId}>修复方案</button>
              </div>
              <div className="small" style={{ marginBottom: 6 }}>
                说明：本区用于全书级诊断与修复策略，不属于主写作链路。
              </div>
              {!bookTensionReport ? <div className="hint">请先“分析全书”或“加载报告”。</div> : null}
              {bookTensionReport ? (
                <>
                  <div className="top-summary-grid">
                    <div className="summary-card">
                      <div className="k">覆盖率</div>
                      <div className="v">
                        {report.coverage?.chapters_with_metrics || 0} / {report.coverage?.chapters_total || 0}
                      </div>
                    </div>
                    <div className="summary-card">
                      <div className="k">峰值密度</div>
                      <div className="v">{report.peaks?.density_per_10 ?? 0} / 10章</div>
                    </div>
                    <div className="summary-card">
                      <div className="k">谷值密度</div>
                      <div className="v">{report.valleys?.density_per_10 ?? 0} / 10章</div>
                    </div>
                    <div className="summary-card">
                      <div className="k">疲劳区间</div>
                      <div className="v">{fatigueZones.length}</div>
                    </div>
                  </div>

                  <h4>趋势快照</h4>
                  <div className="trend-grid">
                    <div>
                      <div className="small">总体均线（overall_ma）</div>
                      <div className="trend-strip">
                        {(report.book_trends?.overall_ma || []).slice(-20).map((v: number, i: number) => (
                          <span key={i} style={{ height: `${Math.max(8, Math.round(v * 70))}px` }} />
                        ))}
                      </div>
                    </div>
                    <div>
                      <div className="small">代价均线（cost_ma）</div>
                      <div className="trend-strip">
                        {(report.book_trends?.cost_ma || []).slice(-20).map((v: number, i: number) => (
                          <span key={i} style={{ height: `${Math.max(8, Math.round(v * 70))}px` }} />
                        ))}
                      </div>
                    </div>
                    <div>
                      <div className="small">反转均线（reversal_ma）</div>
                      <div className="trend-strip">
                        {(report.book_trends?.reversal_ma || []).slice(-20).map((v: number, i: number) => (
                          <span key={i} style={{ height: `${Math.max(8, Math.round(v * 70))}px` }} />
                        ))}
                      </div>
                    </div>
                  </div>

                  <h4>疲劳区间</h4>
                  <div className="zone-list">
                    {fatigueZones.length === 0 ? <div className="hint">暂无疲劳区间。</div> : null}
                    {fatigueZones.map((z: any, idx: number) => (
                      <div key={idx} className="zone-item">
                        <div>
                          <strong>
                            {z.from} - {z.to}
                          </strong>
                          <div className="small">{z.reason}</div>
                        </div>
                        <div className="row">
                          <button onClick={() => setStatus(`跳转到第 ${z.from} 章`)}>跳转</button>
                          <button onClick={() => void fetch(`${baseUrl}/v1/books/${bookId}/tension/repair_plan`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ chapter_from: z.from, chapter_to: z.to, targets, style })
                          }).then(() => setStatus(`修复计划已创建：${z.from}-${z.to}`))}>
                            生成修复方案
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>

                  <h4>分卷概览</h4>
                  <div className="arc-table-wrap">
                    <table className="arc-table">
                      <thead>
                        <tr>
                          <th>卷（Arc）</th>
                          <th>章节数</th>
                          <th>总体</th>
                          <th>代价</th>
                          <th>反转</th>
                          <th>节奏</th>
                          <th>曲线形态</th>
                          <th>主要问题</th>
                          <th>机制占比</th>
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

                  <h4>高级预警</h4>
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

                  <h4>分卷目标设置</h4>
                  <div className="settings-grid">
                    <label>
                      卷 ID
                      <input value={arcTargetForm.arc_id} onChange={(e) => setArcTargetForm({ ...arcTargetForm, arc_id: e.target.value })} />
                    </label>
                    <label>
                      形态
                      <select
                        value={arcTargetForm.target_shape}
                        onChange={(e) => setArcTargetForm({ ...arcTargetForm, target_shape: e.target.value as ArcTarget["target_shape"] })}
                      >
                        <option value="ramp">线性上升（ramp）</option>
                        <option value="late_peak">后峰（late_peak）</option>
                        <option value="early_peak">前峰（early_peak）</option>
                        <option value="plateau">平台（plateau）</option>
                        <option value="sawtooth">锯齿（sawtooth）</option>
                      </select>
                    </label>
                    <label>
                      目标点（5）
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
                    <button onClick={() => void saveArcTarget()}>保存分卷目标</button>
                    <button onClick={() => void loadArcTargets()}>刷新分卷目标</button>
                    <button onClick={() => void evolveTemplates()}>演化模板</button>
                    <button onClick={() => void loadVariants()}>刷新变体</button>
                  </div>
                  <pre>{JSON.stringify({ advanced, arc_targets: arcTargetAnalysis, configured_targets: arcTargets }, null, 2)}</pre>

                  <h4>模板实验室</h4>
                  <div className="zone-list">
                    {variants.length === 0 ? <div className="hint">暂无变体，请先执行“演化模板”。</div> : null}
                    {variants.map((v) => (
                      <div key={v.variant_id} className="zone-item">
                        <div className="row">
                          <div>
                            <strong>{v.name}</strong>
                            <div className="small">启用：{String(v.enabled)} | 权重：{v.weight}</div>
                            <div className="small">范围：{JSON.stringify(v.scope)}</div>
                            <div className="small">统计：{JSON.stringify(v.stats)}</div>
                          </div>
                          <div className="row">
                            <button onClick={() => void setVariantEnabled(v.variant_id, true, Math.max(0.1, v.weight || 0.1))}>启用</button>
                            <button onClick={() => void setVariantEnabled(v.variant_id, false)}>停用</button>
                          </div>
                        </div>
                        <pre>{JSON.stringify(v.recipe, null, 2)}</pre>
                      </div>
                    ))}
                  </div>
                </>
              ) : null}
            </section>
          )
        : null}

      {showSettings
        ? renderTopPanel(
            "设置与健康",
            () => setShowSettings(false),
            <section id="section-settings" className="wb-panel" style={{ marginTop: 0 }}>
          <h3>设置与健康</h3>
          <div className="small" style={{ marginBottom: 8 }}>
            支持 Ollama / OpenAI / OpenAI-compatible（本地兼容网关）。当前 provider 会自动同步到运行时配置。
          </div>
          <details open={!writerSimpleMode} style={{ marginBottom: 10 }}>
            <summary>设置作业顺序（折叠导航）</summary>
            <div className="quick-form-grid" style={{ marginTop: 8 }}>
              <div className="summary-card">
                <div className="k">01</div>
                <div className="v">画像绑定与风格学习</div>
                <div className="small">先绑定书籍画像，再做学习和版本操作。</div>
                <button onClick={() => openDetailsAndScroll("settings-profile-panel")}>跳转 01</button>
              </div>
              <div className="summary-card">
                <div className="k">02</div>
                <div className="v">A/B 批次实验</div>
                <div className="small">批量评估画像差异，选优胜方案。</div>
                <button onClick={() => openDetailsAndScroll("settings-ab-panel")}>跳转 02</button>
              </div>
              <div className="summary-card">
                <div className="k">03</div>
                <div className="v">分层设置中心</div>
                <div className="small">按 global/book/chapter 维护配置与审计。</div>
                <button onClick={() => openDetailsAndScroll("settings-scoped-panel")}>跳转 03</button>
              </div>
              <div className="summary-card">
                <div className="k">04</div>
                <div className="v">Provider 与健康检查</div>
                <div className="small">最后保存运行配置并做健康验证。</div>
                <button onClick={() => openDetailsAndScroll("settings-provider-panel")}>跳转 04</button>
              </div>
            </div>
          </details>
          <details open={!writerSimpleMode} style={{ marginBottom: 10 }}>
            <summary>① 画像与风格学习 + ② A/B 批次（按顺序作业）</summary>
            <div id="settings-profile-panel" className="wb-panel" style={{ minHeight: "auto", marginBottom: 10, marginTop: 8 }}>
            <h4 style={{ marginTop: 0 }}>风格画像</h4>
            <div className="row" style={{ marginBottom: 8, flexWrap: "wrap" }}>
              <label style={{ minWidth: 320 }}>
                当前书籍
                <input value={bookId} onChange={(e) => setBookId(e.target.value)} placeholder="请在书库中选择（推荐）" />
              </label>
              <label style={{ minWidth: 320 }}>
                画像
                <select
                  value={selectedBookProfileId}
                  onChange={(e) => {
                    const next = e.target.value;
                    setSelectedBookProfileId(next);
                  }}
                >
                  <option value="">（无）</option>
                  {profiles.map((p) => (
                    <option key={p.profile_id} value={p.profile_id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="row" style={{ alignItems: "end" }}>
                <button onClick={() => void bindProfileToBook(selectedBookProfileId)} disabled={!bookId}>绑定画像</button>
                <button onClick={() => void bindProfileToBook("")} disabled={!bookId}>清除绑定</button>
                <button onClick={() => void loadProfilesList()} disabled={!showSettings}>刷新画像</button>
                <button onClick={() => void addExperimentProfile(selectedBookProfileId)} disabled={!bookId || !selectedBookProfileId}>
                  加入实验组
                </button>
                <button onClick={() => void learnProfileFromCurrentBook()} disabled={!bookId || !selectedBookProfileId || profileLearning}>
                  {profileLearning ? "学习中..." : "从书稿学习"}
                </button>
                <button className="danger" onClick={() => void deleteCurrentProfile()} disabled={!selectedBookProfileId || profileDeleting}>
                  {profileDeleting ? "删除中..." : "删除画像"}
                </button>
              </div>
            </div>
            <div className="small">
              当前 Eval/Control Plan 会自动注入该 profile_id；后端也会在未显式传入时回退到 book.profile_id。
            </div>
            <div className="row" style={{ gap: 10, marginTop: 10, alignItems: "stretch", flexWrap: "wrap" }}>
              <div style={{ flex: "1 1 360px", minWidth: 320 }}>
                <div className="small" style={{ marginBottom: 6 }}>
                  画像版本 · 当前 v{profileActiveVersion || "-"}
                </div>
                <div className="scroll" style={{ maxHeight: 220 }}>
                  {profileVersions.length === 0 ? <div className="hint">暂无版本。</div> : null}
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
                          <button onClick={() => void openProfileVersionSnapshot(selectedBookProfileId, Number(v.version))}>快照</button>
                          <button onClick={() => void setActiveProfileVersion(Number(v.version))} disabled={Number(v.version) === profileActiveVersion}>
                            设为当前
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div style={{ flex: "2 1 560px", minWidth: 360 }}>
                <div className="small">版本差异</div>
                <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "end" }}>
                  <label style={{ minWidth: 120 }}>
                    从
                    <select value={profileDiffFrom || 0} onChange={(e) => setProfileDiffFrom(Number(e.target.value) || 0)}>
                      {profileVersions.map((v) => (
                        <option key={`from-${v.version}`} value={v.version}>v{v.version}</option>
                      ))}
                    </select>
                  </label>
                  <label style={{ minWidth: 120 }}>
                    到
                    <select value={profileDiffTo || 0} onChange={(e) => setProfileDiffTo(Number(e.target.value) || 0)}>
                      {profileVersions.map((v) => (
                        <option key={`to-${v.version}`} value={v.version}>v{v.version}</option>
                      ))}
                    </select>
                  </label>
                  <button onClick={() => void runProfileVersionDiff()} disabled={!selectedBookProfileId || !profileDiffFrom || !profileDiffTo}>
                    执行对比
                  </button>
                </div>
                <pre style={{ maxHeight: 160, overflow: "auto" }}>{JSON.stringify(profileDiffResult || {}, null, 2)}</pre>
                <div className="small">快照预览</div>
                <pre style={{ maxHeight: 160, overflow: "auto" }}>{JSON.stringify(profileVersionSnapshot || {}, null, 2)}</pre>
              </div>
            </div>
            <div className="row" style={{ gap: 8, marginTop: 8, flexWrap: "wrap", alignItems: "end" }}>
              <label style={{ minWidth: 260 }}>
                克隆分支名称
                <input value={profileCloneName} onChange={(e) => setProfileCloneName(e.target.value)} placeholder="B-悬疑更冷" />
              </label>
              <button onClick={() => void cloneCurrentProfileBranch()} disabled={!selectedBookProfileId}>
                克隆画像分支
              </button>
            </div>
            {bookProfileMeta ? (
              <div className="small" style={{ marginTop: 8 }}>
                main={bookProfileMeta?.main?.profile_id || "-"} · experiments={(bookProfileMeta?.experiments || []).length}
              </div>
            ) : null}
            <div id="settings-ab-panel" className="hr" />
            <div className="h2">A/B 批次（步骤 02）</div>
            <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <label style={{ minWidth: 220 }}>
                Promote Strategy
                <select value={abPromoteStrategy} onChange={(e) => setAbPromoteStrategy(e.target.value as any)}>
                  <option value="profile">画像（profile）</option>
                  <option value="profile_plus_settings">画像+设置（profile_plus_settings）</option>
                  <option value="version">版本（version）</option>
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
                {abBatchLoading ? "启动中..." : "运行 A/B 批次"}
              </button>
              <button onClick={() => void loadAbBatch(abBatchId)} disabled={!abBatchId}>刷新批次</button>
              <button onClick={() => void retryAbBatchFailed(abBatchId)} disabled={!abBatchId}>重试失败</button>
              <button
                onClick={() => void promoteAbBatchWinner(abBatchId)}
                disabled={!abBatchId || !abBatchData?.ranking?.length || String(abBatchData?.status || "") !== "done"}
              >
                Promote Winner → Set as Main
              </button>
              <button onClick={() => void loadChapterReports()} disabled={!chapterId}>加载章节报告</button>
              <div className="small mono">批次ID（batch_id）={abBatchId || "-"}</div>
            </div>
            {abBatchData ? (
              <div style={{ marginTop: 8 }}>
                <div className="small">
                  状态：<span className="mono">{String(abBatchData.status || "-")}</span> · 条目数：{" "}
                  <span className="mono">{Array.isArray(abBatchData.items) ? abBatchData.items.length : 0}</span>
                  {" "}· 惩罚系数（penalty）：<span className="mono">{String((abBatchData.score_cfg || {}).penalty ?? "-")}</span>
                  {" "}· 胜出包（winner_bundle）：<span className="mono">{abBatchData.winner_bundle_id ? String(abBatchData.winner_bundle_id).slice(0, 8) : "-"}</span>
                </div>
                <div className="scroll" style={{ maxHeight: 180, marginTop: 6 }}>
                  {Array.isArray(abBatchData.items) && abBatchData.items.length > 0 ? (
                    <table className="compare-table">
                      <thead>
                        <tr>
                          <th>画像</th>
                          <th>变体</th>
                          <th>注入</th>
                          <th>版本</th>
                          <th>状态</th>
                          <th>评估</th>
                          <th>相似度</th>
                          <th>评分</th>
                          <th>注入包</th>
                          <th>注入次数</th>
                          <th>文本</th>
                          <th>追踪</th>
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
                    <div className="hint">暂无批次条目。</div>
                  )}
                </div>
              </div>
            ) : null}

            {abBatchData?.delta_ranking?.length ? (
              <div style={{ marginTop: 10 }}>
                <div className="h2">差值排名（实验 - 基线）</div>
                <div className="scroll" style={{ maxHeight: 180 }}>
                  <table className="compare-table">
                    <thead>
                      <tr>
                        <th>画像</th>
                        <th>基线</th>
                        <th>实验</th>
                        <th>差值</th>
                        <th>基线文本</th>
                        <th>实验文本</th>
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
                <div className="h2">组合差值（实验 - 组合基线）</div>
                <div className="scroll" style={{ maxHeight: 180 }}>
                  <table className="compare-table">
                    <thead>
                      <tr>
                        <th>画像</th>
                        <th>组合基线</th>
                        <th>实验</th>
                        <th>差值</th>
                        <th>组合文本</th>
                        <th>实验文本</th>
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
                <div className="h2">注入说明</div>
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
                  void viewAssetSelectionTrace(textVerId).catch((err) => setStatus(formatAnyError(err)));
                }}
              />
            ) : null}

            {bookId ? (
              <ComboLeaderboardPanel
                baseUrl={baseUrl}
                bookId={bookId}
                onStatus={setStatus}
                onOpenTrace={(textVerId) => {
                  void viewAssetSelectionTrace(textVerId).catch((err) => setStatus(formatAnyError(err)));
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
                  void viewAssetSelectionTrace(textVerId).catch((err) => setStatus(formatAnyError(err)));
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
              <div className="h2">A/B 对比（来自章节报告）</div>
              <div className="scroll" style={{ maxHeight: 220 }}>
                {chapterReports.length === 0 ? (
                  <div className="hint">暂无加载报告。</div>
                ) : (
                  Object.entries(
                    chapterReports.reduce((acc: Record<string, any[]>, it: any) => {
                      const key = String(it.profile_id_used || "未知(unknown)");
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
                            <span className="small">报告数={rows.length}</span>
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
          </details>
          <details open={!writerSimpleMode} style={{ marginBottom: 10 }}>
            <summary>② 分层设置中心（按顺序作业）</summary>
            <div id="settings-scoped-panel" className="wb-panel" style={{ minHeight: "auto", marginBottom: 10, marginTop: 8 }}>
            <h4 style={{ marginTop: 0 }}>分层设置中心</h4>
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
                  <option value="global">{formatScopeLabel("global")}</option>
                  <option value="book">{formatScopeLabel("book")}</option>
                  <option value="chapter">{formatScopeLabel("chapter")}</option>
                </select>
              </label>
              <label>
                book_id
                <input value={bookId} onChange={(e) => setBookId(e.target.value)} placeholder="书籍范围必填（book）" />
              </label>
              <label>
                chapter_id
                <input value={chapterId} onChange={(e) => setChapterId(e.target.value)} placeholder="章节/生效范围必填（chapter/effective）" />
              </label>
              <button onClick={() => void loadScopedSettings(settingsScope)}>加载分层设置</button>
              <button onClick={() => void saveScopedSettings()}>保存分层设置</button>
              <button onClick={() => void loadEffectiveSettings()}>加载生效配置</button>
              <button onClick={() => void restoreDefaultScopedTemplate()}>恢复默认模板（加载）</button>
            </div>
            <div className="row" style={{ gap: 8, marginTop: 8 }}>
              <button className={settingsEditorMode === "basic" ? "on" : ""} onClick={() => setSettingsEditorMode("basic")}>基础</button>
              <button className={settingsEditorMode === "advanced" ? "on" : ""} onClick={() => setSettingsEditorMode("advanced")}>高级</button>
              <span className="small" style={{ marginLeft: 8 }}>
                {scopedDirty ? "未保存更改" : "已保存"}
              </span>
              {scopedSettingsParseError ? <span className="small" style={{ color: "#b00020" }}>{scopedSettingsParseError}</span> : null}
            </div>
            <div className="row" style={{ gap: 10, marginTop: 10, alignItems: "stretch" }}>
              <div style={{ flex: 1 }}>
                <div className="small">分层 JSON</div>
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
                <div className="small">生效 JSON（含章节合并）</div>
                <textarea style={{ width: "100%", minHeight: 180 }} value={effectiveSettingsText} readOnly />
                <div className="small" style={{ marginTop: 8 }}>来源提示</div>
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
                      在当前范围覆盖（Override）
                    </button>
                    ) : null}
                    <button
                      style={{ width: "100%", textAlign: "left", marginTop: 4 }}
                      onClick={async () => {
                        try { await navigator.clipboard.writeText(traceMenu.key); } catch {}
                        setTraceMenu(null);
                      }}
                    >
                      复制键（Key）
                    </button>
                    <button
                      style={{ width: "100%", textAlign: "left", marginTop: 4 }}
                      onClick={async () => {
                        try { await navigator.clipboard.writeText(JSON.stringify(traceMenu.value ?? null, null, 2)); } catch {}
                        setTraceMenu(null);
                      }}
                    >
                      复制值（Value）
                    </button>
                  </div>
                ) : null}
                <div className="row" style={{ gap: 8, marginTop: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
                  <div style={{ minWidth: 220 }}>
                    <div className="label">对比范围</div>
                    <select className="input" value={settingsDiffPair} onChange={(e) => setSettingsDiffPair(e.target.value as any)}>
                      <option value="global_book">全局 ↔ 书籍（global ↔ book）</option>
                      <option value="book_chapter">书籍 ↔ 章节（book ↔ chapter）</option>
                      <option value="global_effective">全局 ↔ 生效（global ↔ effective）</option>
                    </select>
                  </div>
                  <button onClick={() => void computeSettingsDiff(settingsDiffPair)}>刷新差异</button>
                </div>
                <div style={{ marginTop: 10 }}>
                  <SettingsDiffPanel
                    title="设置差异"
                    changes={settingsDiffRows}
                    onOverrideBToScope={(k, v) => overrideScopedKey(k, v)}
                  />
                </div>
                <div className="card" style={{ marginTop: 10 }}>
                  <div className="h2">预设</div>
                  <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
                    <label style={{ minWidth: 180 }}>
                      名称（Name）
                      <input value={settingsPresetName} onChange={(e) => setSettingsPresetName(e.target.value)} placeholder="热血快节奏" />
                    </label>
                    <label style={{ minWidth: 220 }}>
                      描述（Description）
                      <input value={settingsPresetDesc} onChange={(e) => setSettingsPresetDesc(e.target.value)} placeholder="可选" />
                    </label>
                    <button onClick={() => void createSettingsPresetFromCurrent()}>保存当前为预设</button>
                    <button onClick={() => void loadSettingsPresets()}>刷新预设</button>
                  </div>
                  <div className="scroll" style={{ maxHeight: 220, marginTop: 10 }}>
                    {settingsPresets.length === 0 ? <div className="hint">暂无预设。</div> : null}
                    {settingsPresets.map((p) => (
                      <div key={p.preset_id} className="node-item" style={{ cursor: "default" }}>
                        <div style={{ width: "100%" }}>
                          <div className="row">
                            <strong>{p.name}</strong>
                            <span className="small">{p.description || ""}</span>
                          </div>
                          <div className="row" style={{ marginTop: 6 }}>
                            <button onClick={() => void applyPresetToCurrentScope(String(p.preset_id))}>应用到 {formatScopeLabel(settingsScope)}</button>
                            <button
                              className="danger"
                              onClick={() => deletePreset(String(p.preset_id), String(p.name || p.preset_id || ""))}
                              disabled={presetDeletingId === String(p.preset_id || "")}
                            >
                              {presetDeletingId === String(p.preset_id || "") ? "删除中..." : "删除"}
                            </button>
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
                    <div className="h2">回滚预览</div>
                    <div className="small mono">
                      audit_id={String(rollbackPreviewAudit.audit_id)} · action={String(rollbackPreviewAudit.action)}
                    </div>
                    <div style={{ marginTop: 10 }}>
                      <SettingsDiffPanel title="当前版本 → 回滚目标（Before）" changes={rollbackPreviewDiffRows} />
                    </div>
                    <div className="row" style={{ gap: 8, marginTop: 10 }}>
                      <button onClick={() => void confirmRollbackFromPreview()}>确认回滚</button>
                      <button onClick={() => { setRollbackPreviewAudit(null); setRollbackPreviewDiffRows([]); }}>取消</button>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
          </details>
          <details open={!writerSimpleMode} style={{ marginBottom: 10 }}>
            <summary>④ Provider 与健康检查（按顺序作业）</summary>
            <div id="settings-provider-panel" style={{ marginTop: 8 }}>
          <div className="settings-grid">
            <label>
              当前提供方
              <select
                value={activeProvider}
                onChange={(e) => {
                  const provider = e.target.value as ProviderId;
                  setSettingsData(syncLegacyOllama({ ...settingsData, ai_provider: provider }));
                }}
              >
                <option value="ollama">Ollama（本地）</option>
                <option value="openai">OpenAI（云/本地代理）</option>
                <option value="openai_compatible">OpenAI 兼容（本地）</option>
              </select>
            </label>
            <label>
              提供方预设
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
              <option value="">套用预设...</option>
              <option value="ollama_local">Ollama 本地（127.0.0.1:11434）</option>
              <option value="openai_default">OpenAI 官方</option>
              <option value="openai_local">OpenAI 兼容本地（127.0.0.1:8000/v1）</option>
            </select>
          </label>
          </div>
          <div className="settings-grid">
            <label>
              API 基础地址（API Base URL）
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
              API 密钥（API Key）
              <input
                type="password"
                placeholder="本地服务可留空"
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
              大模型（LLM Model）
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
              向量模型（Embedding Model）
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
              对话路径（Chat Path）
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
              向量路径（Embeddings Path）
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
            <button onClick={() => void saveSettings()}>保存设置</button>
            <button onClick={() => void checkHealth()}>健康检查</button>
            <button onClick={() => void runMaintenance("/v1/system/rebuild_fts")}>重建全文索引（FTS）</button>
            <button onClick={() => void runMaintenance("/v1/system/cleanup_jobs")}>清理任务</button>
          </div>
          <pre style={{ marginTop: 10 }}>{JSON.stringify(health, null, 2)}</pre>
            </div>
          </details>
            </section>
          )
        : null}

      {searchOpen ? (
        <div className="global-search-overlay" onMouseDown={closeGlobalSearch}>
          <div className="global-search-modal" onMouseDown={(e) => e.stopPropagation()}>
            <div className="row" style={{ marginBottom: 8 }}>
              <strong>统一搜索</strong>
              <span className="small">书籍 / 章节 / 素材 / 技能运行</span>
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
              placeholder="按标题或名称搜索..."
            />
            <div className="small" style={{ marginTop: 8 }}>
              {searchLoading ? "搜索中..." : `共 ${searchItems.length} 条结果`}
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
                        <span className="badge">{formatSearchTypeLabel(it.type)}</span> {it.title}
                      </span>
                      <code>{Number(it.score || 0).toFixed(2)}</code>
                    </div>
                    <div className="small">{it.subtitle}</div>
                  </div>
                </button>
              ))}
              {!searchLoading && searchItems.length === 0 ? <div className="hint">输入关键词开始搜索。</div> : null}
            </div>
            <div className="small" style={{ marginTop: 8 }}>
              ↑↓ 选择 · Enter 打开 · Esc 关闭
            </div>
          </div>
        </div>
      ) : null}

      <DeleteConfirmDialog
        open={!!splitbookIngestDialog}
        title="确认导入本地文本"
        requireInput={true}
        targetLabel={
          splitbookIngestDialog ? (
            <>
              动作：<strong>{splitbookIngestDialog.actionText}</strong>
              <br />
              拆书：<strong>{splitbookIngestDialog.splitbookName}</strong>
              <br />
              文件：<span className="mono">{splitbookIngestDialog.sourcePath}</span>
              <br />
              编码：UTF-8
            </>
          ) : null
        }
        warning="导入将开始写入拆书索引，耗时取决于文件体量，请确认路径与拆书名称无误。"
        expectedText={String(splitbookIngestDialog?.expectedText || "导入")}
        value={String(splitbookIngestDialog?.typedText || "")}
        promptLabel={
          <>
            请输入校验词 <span className="mono">{splitbookIngestDialog?.expectedText || "导入"}</span> 以开始导入
          </>
        }
        placeholder={String(splitbookIngestDialog?.expectedText || "导入")}
        error={splitbookIngestConfirmError}
        inputClassName={splitbookIngestInputShake ? "shake-once" : ""}
        inputRef={splitbookIngestInputRef}
        confirmLabel="开始导入"
        busyLabel="处理中..."
        onValueChange={(nextValue) => {
          setSplitbookIngestDialog((prev) => (prev ? { ...prev, typedText: nextValue } : prev));
          if (splitbookIngestConfirmError) setSplitbookIngestConfirmError("");
        }}
        onConfirm={() => void confirmSplitbookIngestDialog()}
        onCancel={() => closeSplitbookIngestDialog(false)}
        onMismatch={markSplitbookIngestMismatch}
      />

      <DeleteConfirmDialog
        open={!!splitbookDeleteDialog}
        title={splitbookDeleteDialog?.purgeAssets ? "彻底删除确认" : "删除拆书确认"}
        requireInput={false}
        targetLabel={splitbookDeleteDialog ? <>拆书：<strong>{splitbookDeleteDialog.name}</strong></> : null}
        warning={
          splitbookDeleteDialog?.purgeAssets
            ? "将删除拆书并清理其模板资产，操作不可撤销。"
            : "将删除拆书，但保留模板资产并解除来源关联。"
        }
        promptLabel="请输入拆书名称以确认删除"
        expectedText={String(splitbookDeleteDialog?.name || "")}
        value={String(splitbookDeleteDialog?.typedName || "")}
        placeholder={String(splitbookDeleteDialog?.name || "")}
        busy={!!splitbookDeletingId}
        error={splitbookDeleteError}
        inputRef={splitbookDeleteInputRef}
        inputClassName={splitbookDeleteInputShake ? "shake-once" : ""}
        confirmLabel={splitbookDeleteDialog?.purgeAssets ? "确认彻底删除" : "确认删除"}
        busyLabel="删除中..."
        onValueChange={(nextValue) => {
          setSplitbookDeleteDialog((prev) => (prev ? { ...prev, typedName: nextValue } : prev));
          if (splitbookDeleteError) setSplitbookDeleteError("");
          if (splitbookDeleteInputShake) setSplitbookDeleteInputShake(false);
        }}
        onConfirm={() => void confirmDeleteSplitbookDialog()}
        onCancel={() => {
          setSplitbookDeleteError("");
          setSplitbookDeleteInputShake(false);
          setSplitbookDeleteDialog(null);
        }}
        onMismatch={markSplitbookDeleteMismatch}
      />

      <DeleteConfirmDialog
        open={!!dataDeleteDialog}
        title="删除确认"
        requireInput={false}
        targetLabel={dataDeleteDialog ? <>目标：<strong>{dataDeleteDialog.name}</strong></> : null}
        warning={String(dataDeleteDialog?.message || "")}
        expectedText={String(dataDeleteDialog?.name || "")}
        value={String(dataDeleteDialog?.typedName || "")}
        placeholder={String(dataDeleteDialog?.name || "")}
        busy={dataDeleteDialog ? isDataDeleteBusy(dataDeleteDialog) : false}
        error={dataDeleteError}
        inputRef={dataDeleteInputRef}
        inputClassName={dataDeleteInputShake ? "shake-once" : ""}
        confirmLabel="确认删除"
        busyLabel="删除中..."
        onValueChange={(nextValue) => {
          setDataDeleteDialog((prev) => (prev ? { ...prev, typedName: nextValue } : prev));
          if (dataDeleteError) setDataDeleteError("");
          if (dataDeleteInputShake) setDataDeleteInputShake(false);
        }}
        onConfirm={() => void confirmDataDeleteDialog()}
        onCancel={() => {
          setDataDeleteError("");
          setDataDeleteInputShake(false);
          setDataDeleteDialog(null);
        }}
        onMismatch={markDataDeleteMismatch}
      />

      {chapterOutlinePreviewDialog ? (
        <div
          className="global-search-overlay"
          onMouseDown={() => {
            if (
              !chapterOutlinePreviewDialogLoading &&
              !chapterOutlinePreviewApplyBusy &&
              !chapterOutlinePreviewTextLoading &&
              !chapterOutlinePreviewTextSaving
            ) {
              setChapterOutlinePreviewDialog(null);
            }
          }}
        >
          <div
            className="global-search-modal"
            style={{ width: "min(980px, 94vw)" }}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="row" style={{ marginBottom: 8 }}>
              <strong>
                章纲预览：第{chapterOutlinePreviewDialog.chapterNo || "?"}章 · {chapterOutlinePreviewDialog.title || "未命名章节"}
              </strong>
              <button
                onClick={() => setChapterOutlinePreviewDialog(null)}
                disabled={
                  chapterOutlinePreviewDialogLoading ||
                  chapterOutlinePreviewApplyBusy ||
                  chapterOutlinePreviewTextLoading ||
                  chapterOutlinePreviewTextSaving
                }
              >
                关闭
              </button>
            </div>
            <div className="row" style={{ gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
              <label style={{ minWidth: 220 }}>
                预览版本
                <select
                  value={chapterOutlinePreviewDialog.selectedVersion || "latest"}
                  onChange={(e) => void loadChapterOutlinePreviewVersion(e.target.value)}
                  disabled={
                    chapterOutlinePreviewDialogLoading ||
                    chapterOutlinePreviewApplyBusy ||
                    chapterOutlinePreviewTextLoading ||
                    chapterOutlinePreviewTextSaving
                  }
                >
                  <option value="latest">latest（最新）</option>
                  {(chapterOutlinePreviewDialog.versions || []).map((v) => {
                    const ver = Number(v?.version || 0) || 0;
                    if (ver <= 0) return null;
                    return (
                      <option key={`preview-ver-${v?.outline_id || ver}`} value={String(ver)}>
                        v{ver} · {String(v?.title || "章纲版本")}
                      </option>
                    );
                  })}
                </select>
              </label>
              <span className="small">当前版本：v{chapterOutlinePreviewDialog.outlineVersion || 0}</span>
              <span className="small">
                节点数：{Array.isArray((chapterOutlinePreviewDialog.outline as any)?.nodes) ? (chapterOutlinePreviewDialog.outline as any).nodes.length : 0}
              </span>
              <span className="small">
                正文：{chapterOutlinePreviewTextDraftId ? chapterOutlinePreviewTextDraftId.slice(0, 8) : "未加载"}
                {chapterOutlinePreviewTextSource === "text_version" ? " · 来源正文版本" : chapterOutlinePreviewTextSource === "draft" ? " · 来源草稿" : ""}
                {chapterOutlinePreviewTextUpdatedAt
                  ? ` · ${new Date(chapterOutlinePreviewTextUpdatedAt).toLocaleString("zh-CN", { hour12: false })}`
                  : ""}
              </span>
            </div>
            {chapterOutlinePreviewDialogLoading ? <div className="small" style={{ marginTop: 6 }}>章纲加载中...</div> : null}
            {chapterOutlinePreviewTextLoading ? <div className="small" style={{ marginTop: 6 }}>正文加载中...</div> : null}
            <div className="job-grid" style={{ marginTop: 10 }}>
              <div className="wb-panel" style={{ minHeight: "auto", padding: 10 }}>
                <div className="row" style={{ marginBottom: 6 }}>
                  <strong>章纲节点预览</strong>
                  <span className="small">用于把握节奏与冲突推进</span>
                </div>
                <div className="scroll" style={{ maxHeight: 360 }}>
                  {Array.isArray((chapterOutlinePreviewDialog.outline as any)?.nodes) &&
                  (chapterOutlinePreviewDialog.outline as any).nodes.length > 0 ? (
                    ((chapterOutlinePreviewDialog.outline as any).nodes as any[]).map((node, idx) => (
                      <div
                        key={`preview-node-${String(node?.node_id || idx)}`}
                        className={`node-item ${chapterOutlinePreviewActiveNodeId === String(node?.node_id || "") ? "active" : ""}`}
                        style={{ marginBottom: 6, cursor: "pointer" }}
                        role="button"
                        tabIndex={0}
                        onClick={() => jumpToOutlineNodeInPreview(node)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            jumpToOutlineNodeInPreview(node);
                          }
                        }}
                      >
                        <div className="row" style={{ width: "100%", justifyContent: "space-between", gap: 8 }}>
                          <strong>
                            {idx + 1}. {String(node?.type || "节点")}
                          </strong>
                          <code>{String(node?.node_id || "")}</code>
                        </div>
                        <div className="small" style={{ marginTop: 4 }}>
                          {toCleanSingleLine(String(node?.summary || node?.goal || node?.note || ""), 220) || "（无摘要）"}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="small">该版本暂无可预览的章纲节点。</div>
                  )}
                </div>
              </div>
              <div className="wb-panel" style={{ minHeight: "auto", padding: 10 }}>
                <div className="row" style={{ marginBottom: 6 }}>
                  <strong>章节正文（可编辑）</strong>
                  <span className="small">
                    {chapterOutlinePreviewMatchInfo
                      ? chapterOutlinePreviewMatchInfo.matched
                        ? `已定位：${toCleanSingleLine(chapterOutlinePreviewMatchInfo.keyword, 24)}`
                        : "未命中正文，请补充节点摘要后再试"
                      : chapterOutlinePreviewTextDirty
                        ? "有未保存修改"
                        : "已同步"}
                  </span>
                </div>
                <div className="row" style={{ gap: 8, marginBottom: 6, flexWrap: "wrap" }}>
                  <button
                    onClick={() => void loadChapterTextPreviewForDialog(chapterOutlinePreviewDialog.chapterId)}
                    disabled={chapterOutlinePreviewTextLoading || chapterOutlinePreviewTextSaving}
                  >
                    {chapterOutlinePreviewTextLoading ? "加载中..." : "重新加载正文"}
                  </button>
                  <button
                    onClick={() => {
                      setChapterOutlinePreviewText("");
                      setChapterOutlinePreviewTextDraftId("");
                      setChapterOutlinePreviewTextSource("");
                      setChapterOutlinePreviewTextUpdatedAt("");
                      setChapterOutlinePreviewTextDirty(false);
                      setChapterOutlinePreviewMatchInfo(null);
                    }}
                    disabled={chapterOutlinePreviewTextLoading || chapterOutlinePreviewTextSaving || !chapterOutlinePreviewText}
                  >
                    清空正文
                  </button>
                </div>
                <textarea
                  ref={chapterOutlinePreviewTextRef}
                  rows={16}
                  value={chapterOutlinePreviewText}
                  onChange={(e) => {
                    setChapterOutlinePreviewText(e.target.value);
                    setChapterOutlinePreviewTextDirty(true);
                    setChapterOutlinePreviewMatchInfo(null);
                  }}
                  placeholder="在此编辑章节正文，然后点击“保存正文并激活”。"
                />
              </div>
            </div>
            <div className="row" style={{ gap: 8, marginTop: 10 }}>
              <button
                onClick={() => void saveChapterTextFromOutlinePreview()}
                disabled={
                  chapterOutlinePreviewDialogLoading ||
                  chapterOutlinePreviewApplyBusy ||
                  chapterOutlinePreviewTextLoading ||
                  chapterOutlinePreviewTextSaving ||
                  !chapterOutlinePreviewText.trim() ||
                  !chapterOutlinePreviewTextDirty
                }
              >
                {chapterOutlinePreviewTextSaving ? "保存中..." : chapterOutlinePreviewTextDirty ? "保存正文并激活" : "正文已保存"}
              </button>
              <button
                onClick={() => void applyChapterOutlinePreviewToEditor()}
                disabled={
                  chapterOutlinePreviewDialogLoading ||
                  chapterOutlinePreviewApplyBusy ||
                  chapterOutlinePreviewTextLoading ||
                  chapterOutlinePreviewTextSaving
                }
              >
                {chapterOutlinePreviewApplyBusy ? "加载中..." : "加载到编辑区"}
              </button>
              <button
                onClick={() => void generateChapterOutlineSeed({ chapterId: chapterOutlinePreviewDialog.chapterId })}
                disabled={
                  chapterOutlinePreviewDialogLoading ||
                  chapterOutlinePreviewApplyBusy ||
                  chapterOutlinePreviewTextLoading ||
                  chapterOutlinePreviewTextSaving ||
                  writerStudioBusy ||
                  structurePipelineBusy
                }
              >
                重新生成本章章纲（1.4.1）
              </button>
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

