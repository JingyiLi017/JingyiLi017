import { contextBridge, ipcRenderer } from "electron";
import { AppConfig, BookTaskInput, BookTaskOutput, WritingTaskInput, WritingTaskOutput } from "./services/types";
import { IPC } from "./ipc/channels";

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

  agentHealth: (): Promise<any> => ipcRenderer.invoke(IPC.AGENT_HEALTH),
  agentDiagnose: (req: any): Promise<any> => ipcRenderer.invoke(IPC.AGENT_DIAGNOSE, req),
  agentPropose: (req: any): Promise<any> => ipcRenderer.invoke(IPC.AGENT_PROPOSE, req),
  agentApply: (req: any): Promise<any> => ipcRenderer.invoke(IPC.AGENT_APPLY, req),
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
