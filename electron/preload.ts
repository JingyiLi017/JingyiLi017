import { contextBridge, ipcRenderer } from "electron";
import type { AppConfig, BookTaskInput, BookTaskOutput, WritingTaskInput, WritingTaskOutput } from "./services/types";

const IPC = {
  SETTINGS_GET: "settings:get",
  SETTINGS_SET: "settings:set",

  AGENT_HEALTH: "agent:health",
  AGENT_DIAGNOSE: "agent:diagnose",
  AGENT_PROPOSE: "agent:propose",
  AGENT_APPLY: "agent:apply",
  AGENT_ORCHESTRATE_PLAN: "agent:orchestrate:plan",
  AGENT_ORCHESTRATE_STEP: "agent:orchestrate:step",
  AGENT_ORCHESTRATE_RUN: "agent:orchestrate:run",
  AGENT_ROLLBACK: "agent:rollback",
  AGENT_AUDITS_LIST: "agent:audits:list",
  AGENT_COMBO_INJECTIONS_LIST: "agent:combo-injections:list",
  AGENT_COMBO_INJECTIONS_CLEANUP: "agent:combo-injections:cleanup",
  PLAN_AUTOBUILD: "plan:autobuild",

  DIAGNOSE_ENGINE: "diag:engine",
  SPLITBOOK_PICK_LOCAL_FILE: "splitbook:pick-local-file",
  SPLITBOOK_PICK_OUTPUT_DIR: "splitbook:pick-output-dir",

  WORKFLOW_DEFINITION: "workflow:definition",
  WORKFLOW_RUN: "workflow:run",
  WORKFLOW_GET_RUN: "workflow:get-run",
  WORKFLOW_ROLLBACK_RUN: "workflow:rollback-run",
  DRAFT_RUN: "draft:run",
  DRAFT_GET: "draft:get",
  DRAFT_DELETE: "draft:delete",
  REWRITE_RUN: "rewrite:run",
  REWRITE_ACCEPT: "rewrite:accept",
  CHAPTER_DRAFTS: "chapter:drafts",
  CHAPTER_DRAFT_ACTIVATE: "chapter:draft:activate",
  DRAFT_LIST_VERSIONS: "draft:list-versions",
  DRAFT_SELECT: "draft:select",
  LEDGER_PROMOTE_SELECTED: "ledger:promote-selected",
  BOOK_WORKSPACE_GET: "book:workspace:get",
  BOOK_WORKSPACE_SET: "book:workspace:set",
  EXPORT_CHAPTER: "export:chapter",
  EXPORT_VOLUME: "export:volume",
  EXPORT_PUBLISH_PACK: "export:publish-pack",
  PREFLIGHT_RUN: "preflight:run",
  EXPORT_LOGS: "export:logs",
  EXPORT_CLEANUP_MISSING: "export:cleanup-missing",
  EXPORT_REBUILD: "export:rebuild",
  FIXWIZARD_PLAN: "fixwizard:plan",
  FIXWIZARD_EXECUTE: "fixwizard:execute",
  FIXWIZARD_RECHECK: "fixwizard:recheck",
  FIXWIZARD_ROLLBACK_LAST: "fixwizard:rollback-last",
  FIXWIZARD_ROLLBACK_CHAIN: "fixwizard:rollback-chain",
  FIXWIZARD_CHAINS: "fixwizard:chains",
  SKILLPACKS_CATALOG: "skillpacks:catalog",
  SKILLPACKS_PRESETS: "skillpacks:presets",
  SKILLPACKS_BIND_GET: "skillpacks:bind:get",
  SKILLPACKS_BIND_SET: "skillpacks:bind:set",
  SKILLPACKS_AUTO_RUN: "skillpacks:auto-run",
  HTTP_PROXY_REQUEST: "http:proxy-request",
  SIDECAR_START: "sidecar:start",
  SIDECAR_STOP: "sidecar:stop",
  SIDECAR_HEALTH: "sidecar:health",
} as const;


contextBridge.exposeInMainWorld("desktopApi", {
  runWritingTask: (input: WritingTaskInput, config: AppConfig): Promise<WritingTaskOutput> =>
    ipcRenderer.invoke("workflow:writing", input, config),
  runBookTask: (input: BookTaskInput, config: AppConfig): Promise<BookTaskOutput> =>
    ipcRenderer.invoke("workflow:book", input, config),
  exportPdf: (html: string, fileStem: string): Promise<{ pdfPath: string }> =>
    ipcRenderer.invoke("report:export-pdf", { html, fileStem }),
  saveJson: (fileStem: string, content: string): Promise<{ path: string }> =>
    ipcRenderer.invoke("report:save-json", { fileStem, content }),
  saveText: (fileStem: string, content: string, ext = "txt"): Promise<{ path: string }> =>
    ipcRenderer.invoke("report:save-text", { fileStem, content, ext }),
  saveTextAt: (directory: string, fileStem: string, content: string, ext = "txt"): Promise<{ path: string }> =>
    ipcRenderer.invoke("report:save-text-at", { directory, fileStem, content, ext }),
  saveDiagnoseBundle: (fileStem: string, bundle: any): Promise<{ directoryPath: string; zipPath: string | null }> =>
    ipcRenderer.invoke("report:save-diagnose-bundle", { fileStem, bundle }),
  openPath: (path: string, reveal = false): Promise<{ ok: boolean; error?: string | null }> =>
    ipcRenderer.invoke("report:open-path", { path, reveal }),
  pathExists: (path: string): Promise<{ ok: boolean; exists: boolean }> =>
    ipcRenderer.invoke("report:path-exists", { path }),

  settingsGet: (): Promise<any> => ipcRenderer.invoke(IPC.SETTINGS_GET),
  settingsSet: (patch: any): Promise<any> => ipcRenderer.invoke(IPC.SETTINGS_SET, patch),
  pickSplitbookLocalFile: (): Promise<{ canceled: boolean; path: string }> =>
    ipcRenderer.invoke(IPC.SPLITBOOK_PICK_LOCAL_FILE),
  pickSplitbookOutputDir: (): Promise<{ canceled: boolean; path: string }> =>
    ipcRenderer.invoke(IPC.SPLITBOOK_PICK_OUTPUT_DIR),
  diagnoseEngine: (): Promise<any> => ipcRenderer.invoke(IPC.DIAGNOSE_ENGINE),

  agentHealth: (): Promise<any> => ipcRenderer.invoke(IPC.AGENT_HEALTH),
  agentDiagnose: (req: any): Promise<any> => ipcRenderer.invoke(IPC.AGENT_DIAGNOSE, req),
  agentPropose: (req: any): Promise<any> => ipcRenderer.invoke(IPC.AGENT_PROPOSE, req),
  agentApply: (req: any): Promise<any> => ipcRenderer.invoke(IPC.AGENT_APPLY, req),
  agentOrchestratePlan: (req: any): Promise<any> => ipcRenderer.invoke(IPC.AGENT_ORCHESTRATE_PLAN, req),
  agentOrchestrateStep: (req: any): Promise<any> => ipcRenderer.invoke(IPC.AGENT_ORCHESTRATE_STEP, req),
  agentOrchestrateRun: (req: any): Promise<any> => ipcRenderer.invoke(IPC.AGENT_ORCHESTRATE_RUN, req),
  agentRollback: (req: any): Promise<any> => ipcRenderer.invoke(IPC.AGENT_ROLLBACK, req),
  agentAuditsList: (req: any): Promise<any> => ipcRenderer.invoke(IPC.AGENT_AUDITS_LIST, req),
  agentComboInjectionsList: (req: any): Promise<any> => ipcRenderer.invoke(IPC.AGENT_COMBO_INJECTIONS_LIST, req),
  agentComboInjectionsCleanup: (req: any): Promise<any> => ipcRenderer.invoke(IPC.AGENT_COMBO_INJECTIONS_CLEANUP, req),
  planAutobuild: (req: any): Promise<any> => ipcRenderer.invoke(IPC.PLAN_AUTOBUILD, req),

  workflowDefinition: (req: any): Promise<any> => ipcRenderer.invoke(IPC.WORKFLOW_DEFINITION, req),
  workflowRun: (req: any): Promise<any> => ipcRenderer.invoke(IPC.WORKFLOW_RUN, req),
  workflowGetRun: (req: any): Promise<any> => ipcRenderer.invoke(IPC.WORKFLOW_GET_RUN, req),
  workflowRollbackRun: (req: any): Promise<any> => ipcRenderer.invoke(IPC.WORKFLOW_ROLLBACK_RUN, req),
  draftRun: (req: any): Promise<any> => ipcRenderer.invoke(IPC.DRAFT_RUN, req),
  draftGet: (req: any): Promise<any> => ipcRenderer.invoke(IPC.DRAFT_GET, req),
  draftDelete: (req: any): Promise<any> => ipcRenderer.invoke(IPC.DRAFT_DELETE, req),
  rewriteRun: (req: any): Promise<any> => ipcRenderer.invoke(IPC.REWRITE_RUN, req),
  rewriteAccept: (req: any): Promise<any> => ipcRenderer.invoke(IPC.REWRITE_ACCEPT, req),
  chapterDrafts: (req: any): Promise<any> => ipcRenderer.invoke(IPC.CHAPTER_DRAFTS, req),
  chapterActivateDraft: (req: any): Promise<any> => ipcRenderer.invoke(IPC.CHAPTER_DRAFT_ACTIVATE, req),
  draftListVersions: (req: any): Promise<any> => ipcRenderer.invoke(IPC.DRAFT_LIST_VERSIONS, req),
  draftSelect: (req: any): Promise<any> => ipcRenderer.invoke(IPC.DRAFT_SELECT, req),
  ledgerPromoteSelected: (req: any): Promise<any> => ipcRenderer.invoke(IPC.LEDGER_PROMOTE_SELECTED, req),
  bookWorkspaceGet: (req: any): Promise<any> => ipcRenderer.invoke(IPC.BOOK_WORKSPACE_GET, req),
  bookWorkspaceSet: (req: any): Promise<any> => ipcRenderer.invoke(IPC.BOOK_WORKSPACE_SET, req),
  exportChapter: (req: any): Promise<any> => ipcRenderer.invoke(IPC.EXPORT_CHAPTER, req),
  exportVolume: (req: any): Promise<any> => ipcRenderer.invoke(IPC.EXPORT_VOLUME, req),
  exportPublishPack: (req: any): Promise<any> => ipcRenderer.invoke(IPC.EXPORT_PUBLISH_PACK, req),
  preflightRun: (req: any): Promise<any> => ipcRenderer.invoke(IPC.PREFLIGHT_RUN, req),
  exportLogs: (req: any): Promise<any> => ipcRenderer.invoke(IPC.EXPORT_LOGS, req),
  exportCleanupMissing: (req: any): Promise<any> => ipcRenderer.invoke(IPC.EXPORT_CLEANUP_MISSING, req),
  exportRebuild: (req: any): Promise<any> => ipcRenderer.invoke(IPC.EXPORT_REBUILD, req),
  fixwizardPlan: (req: any): Promise<any> => ipcRenderer.invoke(IPC.FIXWIZARD_PLAN, req),
  fixwizardExecute: (req: any): Promise<any> => ipcRenderer.invoke(IPC.FIXWIZARD_EXECUTE, req),
  fixwizardRecheck: (req: any): Promise<any> => ipcRenderer.invoke(IPC.FIXWIZARD_RECHECK, req),
  fixwizardRollbackLast: (req: any): Promise<any> => ipcRenderer.invoke(IPC.FIXWIZARD_ROLLBACK_LAST, req),
  fixwizardRollbackChain: (req: any): Promise<any> => ipcRenderer.invoke(IPC.FIXWIZARD_ROLLBACK_CHAIN, req),
  fixwizardChains: (req: any): Promise<any> => ipcRenderer.invoke(IPC.FIXWIZARD_CHAINS, req),
  skillpacksCatalog: (): Promise<any> => ipcRenderer.invoke(IPC.SKILLPACKS_CATALOG),
  skillpacksPresets: (): Promise<any> => ipcRenderer.invoke(IPC.SKILLPACKS_PRESETS),
  skillpacksBindGet: (req: any): Promise<any> => ipcRenderer.invoke(IPC.SKILLPACKS_BIND_GET, req),
  skillpacksBindSet: (req: any): Promise<any> => ipcRenderer.invoke(IPC.SKILLPACKS_BIND_SET, req),
  skillpacksAutoRun: (req: any): Promise<any> => ipcRenderer.invoke(IPC.SKILLPACKS_AUTO_RUN, req),
  httpRequest: (req: any): Promise<any> => ipcRenderer.invoke(IPC.HTTP_PROXY_REQUEST, req),
  sidecarStart: (): Promise<any> => ipcRenderer.invoke(IPC.SIDECAR_START),
  sidecarStop: (): Promise<any> => ipcRenderer.invoke(IPC.SIDECAR_STOP),
  sidecarHealth: (): Promise<any> => ipcRenderer.invoke(IPC.SIDECAR_HEALTH),
  onLog: (cb: (line: string) => void) => {
    ipcRenderer.removeAllListeners("log:append");
    ipcRenderer.on("log:append", (_e, line) => cb(String(line || "")));
  },
});
