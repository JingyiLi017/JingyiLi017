import type { AppConfig, BookTaskInput, BookTaskOutput, WritingTaskInput, WritingTaskOutput } from "../../electron/services/types";

declare global {
  interface Window {
    desktopApi: {
      runWritingTask: (input: WritingTaskInput, config: AppConfig) => Promise<WritingTaskOutput>;
      runBookTask: (input: BookTaskInput, config: AppConfig) => Promise<BookTaskOutput>;
      exportPdf: (html: string, fileStem: string) => Promise<{ pdfPath: string }>;
      saveJson: (fileStem: string, content: string) => Promise<{ path: string }>;
      saveText: (fileStem: string, content: string, ext?: string) => Promise<{ path: string }>;
      saveTextAt: (directory: string, fileStem: string, content: string, ext?: string) => Promise<{ path: string }>;
      saveDiagnoseBundle: (fileStem: string, bundle: any) => Promise<{ directoryPath: string; zipPath: string | null }>;
      openPath: (path: string, reveal?: boolean) => Promise<{ ok: boolean; error?: string | null }>;
      pathExists: (path: string) => Promise<{ ok: boolean; exists: boolean }>;
      settingsGet: () => Promise<any>;
      settingsSet: (patch: any) => Promise<any>;
      pickSplitbookLocalFile: () => Promise<{ canceled: boolean; path: string }>;
      pickSplitbookOutputDir: () => Promise<{ canceled: boolean; path: string }>;
      diagnoseEngine: () => Promise<any>;
      agentHealth: () => Promise<any>;
      agentDiagnose: (req: any) => Promise<any>;
      agentPropose: (req: any) => Promise<any>;
      agentApply: (req: any) => Promise<any>;
      agentOrchestratePlan: (req: any) => Promise<any>;
      agentOrchestrateStep: (req: any) => Promise<any>;
      agentOrchestrateRun: (req: any) => Promise<any>;
      agentRollback: (req: any) => Promise<any>;
      agentAuditsList: (req: any) => Promise<any>;
      agentComboInjectionsList: (req: any) => Promise<any>;
      agentComboInjectionsCleanup: (req: any) => Promise<any>;
      planAutobuild: (req: any) => Promise<any>;
      workflowDefinition: (req: any) => Promise<any>;
      workflowRun: (req: any) => Promise<any>;
      workflowGetRun: (req: any) => Promise<any>;
      workflowRollbackRun: (req: any) => Promise<any>;
      draftRun: (req: any) => Promise<any>;
      draftGet: (req: any) => Promise<any>;
      draftDelete: (req: any) => Promise<any>;
      rewriteRun: (req: any) => Promise<any>;
      rewriteAccept: (req: any) => Promise<any>;
      chapterDrafts: (req: any) => Promise<any>;
      chapterActivateDraft: (req: any) => Promise<any>;
      draftListVersions: (req: any) => Promise<any>;
      draftSelect: (req: any) => Promise<any>;
      ledgerPromoteSelected: (req: any) => Promise<any>;
      bookWorkspaceGet: (req: any) => Promise<any>;
      bookWorkspaceSet: (req: any) => Promise<any>;
      exportChapter: (req: any) => Promise<any>;
      exportVolume: (req: any) => Promise<any>;
      exportPublishPack: (req: any) => Promise<any>;
      preflightRun: (req: any) => Promise<any>;
      exportLogs: (req: any) => Promise<any>;
      exportCleanupMissing: (req: any) => Promise<any>;
      exportRebuild: (req: any) => Promise<any>;
      fixwizardPlan: (req: any) => Promise<any>;
      fixwizardExecute: (req: any) => Promise<any>;
      fixwizardRecheck: (req: any) => Promise<any>;
      fixwizardRollbackLast: (req: any) => Promise<any>;
      fixwizardRollbackChain: (req: any) => Promise<any>;
      fixwizardChains: (req: any) => Promise<any>;
      skillpacksCatalog: () => Promise<any>;
      skillpacksPresets: () => Promise<any>;
      skillpacksBindGet: (req: any) => Promise<any>;
      skillpacksBindSet: (req: any) => Promise<any>;
      skillpacksAutoRun: (req: any) => Promise<any>;
      httpRequest: (req: any) => Promise<any>;
      sidecarStart: () => Promise<any>;
      sidecarStop: () => Promise<any>;
      sidecarHealth: () => Promise<any>;
      onLog: (cb: (line: string) => void) => void;
    };
  }
}

export {};
