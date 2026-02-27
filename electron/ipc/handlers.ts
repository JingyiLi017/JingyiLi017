import { app, BrowserWindow, dialog, ipcMain } from "electron";
import { IPC } from "./channels";
import { agentClient } from "../api/agentClient";
import { getSettings, setSettings } from "../store/settingsStore";
import { SidecarManager } from "../sidecarManager";

import fs from "node:fs";
import path from "node:path";

function _exists(p: string) {
  try { return fs.existsSync(p); } catch { return false; }
}

ipcMain.handle(IPC.DIAGNOSE_ENGINE, async () => {
  const cfg = await getSettings();

  const resourcesPath = process.resourcesPath || "";
  const exeName = process.platform === "win32" ? "sidecar.exe" : "sidecar";

  const candidates = [
    cfg.sidecarExecutablePath ? String(cfg.sidecarExecutablePath) : "",
    resourcesPath ? path.join(resourcesPath, "bin", "sidecar", exeName) : "",
    resourcesPath ? path.join(resourcesPath, "sidecar", exeName) : "",
    resourcesPath ? path.join(resourcesPath, exeName) : "",
    // dev fallback（可选）
    path.resolve(process.cwd(), "engine", "dist", exeName),
  ].filter(Boolean);

  const exeCandidates = candidates.map((p) => ({ path: p, exists: _exists(p) }));

  const composeFile = String(cfg.infraComposePath || "").trim();
  const composeExists = composeFile ? _exists(composeFile) : false;

  const lastStartError = String((globalThis as any).__lastSidecarStartError || "");

  return {
    appPath: app.getAppPath(),
    userData: app.getPath("userData"),
    resourcesPath,
    cwd: process.cwd(),

    autoStartSidecar: cfg.autoStartSidecar,
    autoStartInfra: cfg.autoStartInfra,
    infraProvider: cfg.infraProvider,

    baseUrl: String(cfg.baseUrl || ""),
    sidecarPreferredPort: Number(cfg.sidecarPreferredPort || 17777),

    databaseUrl: String(cfg.databaseUrl || ""),

    infra: {
      infraComposePath: composeFile,
      composeExists,
    },

    exeCandidates,
    lastStartError,
  };
});

ipcMain.handle(IPC.SPLITBOOK_PICK_LOCAL_FILE, async () => {
  const owner = BrowserWindow.getFocusedWindow() ?? BrowserWindow.getAllWindows()[0];
  const result = await dialog.showOpenDialog(owner ?? undefined, {
    title: "选择拆书文本文件",
    properties: ["openFile"],
    filters: [
      { name: "文本文件 (TXT/MD/JSONL)", extensions: ["txt", "md", "jsonl"] },
      { name: "全部文件", extensions: ["*"] },
    ],
  });
  const picked = String(result.filePaths?.[0] || "").trim();
  if (result.canceled || !picked) return { canceled: true, path: "" };
  return { canceled: false, path: picked };
});

ipcMain.handle(IPC.SPLITBOOK_PICK_OUTPUT_DIR, async () => {
  const owner = BrowserWindow.getFocusedWindow() ?? BrowserWindow.getAllWindows()[0];
  const result = await dialog.showOpenDialog(owner ?? undefined, {
    title: "选择拆书产物存储目录",
    properties: ["openDirectory", "createDirectory"],
  });
  const picked = String(result.filePaths?.[0] || "").trim();
  if (result.canceled || !picked) return { canceled: true, path: "" };
  return { canceled: false, path: picked };
});


export function registerAgentIpcHandlers(sidecar: SidecarManager) {
  ipcMain.handle(IPC.SETTINGS_GET, async () => getSettings());
  ipcMain.handle(IPC.SETTINGS_SET, async (_e, patch: any) => setSettings(patch || {}));
  ipcMain.handle(IPC.SIDECAR_START, async () => sidecar.start(await getSettings()));
  ipcMain.handle(IPC.SIDECAR_STOP, async () => sidecar.stop());
  ipcMain.handle(IPC.SIDECAR_HEALTH, async () => {
    const s = await getSettings();
    return sidecar.health(String(s.agentToken || ""));
  });

  ipcMain.handle(IPC.AGENT_HEALTH, async () => agentClient.health());
  ipcMain.handle(IPC.AGENT_DIAGNOSE, async (_e, req: any) => agentClient.diagnose(req || {}));
  ipcMain.handle(IPC.AGENT_PROPOSE, async (_e, req: any) => agentClient.propose(req || {}));
  ipcMain.handle(IPC.AGENT_APPLY, async (_e, req: any) => agentClient.apply(req || {}));
  ipcMain.handle(IPC.AGENT_ORCHESTRATE_PLAN, async (_e, req: any) => agentClient.orchestratePlan(req || {}));
  ipcMain.handle(IPC.AGENT_ORCHESTRATE_STEP, async (_e, req: any) => agentClient.orchestrateStep(req || {}));
  ipcMain.handle(IPC.AGENT_ORCHESTRATE_RUN, async (_e, req: any) => agentClient.orchestrateRun(req || {}));
  ipcMain.handle(IPC.AGENT_ROLLBACK, async (_e, req: any) => agentClient.rollback(req || {}));
  ipcMain.handle(IPC.AGENT_AUDITS_LIST, async (_e, req: any) => agentClient.auditsList(req || {}));
  ipcMain.handle(IPC.AGENT_COMBO_INJECTIONS_LIST, async (_e, req: any) => agentClient.comboInjectionsList(req || {}));
  ipcMain.handle(IPC.AGENT_COMBO_INJECTIONS_CLEANUP, async (_e, req: any) => agentClient.comboInjectionsCleanup(req || {}));
  ipcMain.handle(IPC.PLAN_AUTOBUILD, async (_e, req: any) => agentClient.planAutobuild(req || {}));
  ipcMain.handle(IPC.WORKFLOW_DEFINITION, async (_e, req: any) => agentClient.workflowDefinition(String(req?.workflow_id || "draft_runner_v1")));
  ipcMain.handle(IPC.WORKFLOW_RUN, async (_e, req: any) => agentClient.workflowRun(req || {}));
  ipcMain.handle(IPC.WORKFLOW_GET_RUN, async (_e, req: any) => agentClient.workflowGetRun(String(req?.run_id || "")));
  ipcMain.handle(IPC.WORKFLOW_ROLLBACK_RUN, async (_e, req: any) =>
    agentClient.workflowRollbackRun(String(req?.run_id || ""), req?.body || {})
  );
  ipcMain.handle(IPC.DRAFT_RUN, async (_e, req: any) => agentClient.draftRun(req || {}));
  ipcMain.handle(IPC.DRAFT_GET, async (_e, req: any) => agentClient.draftGet(String(req?.draft_id || "")));
  ipcMain.handle(IPC.DRAFT_DELETE, async (_e, req: any) => agentClient.draftDelete(String(req?.draft_id || "")));
  ipcMain.handle(IPC.REWRITE_RUN, async (_e, req: any) => agentClient.rewriteRun(req || {}));
  ipcMain.handle(IPC.REWRITE_ACCEPT, async (_e, req: any) => agentClient.rewriteAccept(req || {}));
  ipcMain.handle(IPC.CHAPTER_DRAFTS, async (_e, req: any) => agentClient.chapterDrafts(String(req?.chapter_id || "")));
  ipcMain.handle(IPC.CHAPTER_DRAFT_ACTIVATE, async (_e, req: any) =>
    agentClient.chapterActivateDraft(String(req?.chapter_id || ""), String(req?.draft_id || ""))
  );
  ipcMain.handle(IPC.DRAFT_LIST_VERSIONS, async (_e, req: any) => agentClient.draftListVersions(req || {}));
  ipcMain.handle(IPC.DRAFT_SELECT, async (_e, req: any) => agentClient.draftSelect(req || {}));
  ipcMain.handle(IPC.LEDGER_PROMOTE_SELECTED, async (_e, req: any) => agentClient.ledgerPromoteSelected(req || {}));
  ipcMain.handle(IPC.BOOK_WORKSPACE_GET, async (_e, req: any) => agentClient.bookWorkspaceGet(String(req?.book_id || "")));
  ipcMain.handle(IPC.BOOK_WORKSPACE_SET, async (_e, req: any) =>
    agentClient.bookWorkspaceSet(String(req?.book_id || ""), req?.body || {})
  );
  ipcMain.handle(IPC.EXPORT_CHAPTER, async (_e, req: any) => agentClient.exportChapter(req || {}));
  ipcMain.handle(IPC.EXPORT_VOLUME, async (_e, req: any) => agentClient.exportVolume(req || {}));
  ipcMain.handle(IPC.EXPORT_PUBLISH_PACK, async (_e, req: any) => agentClient.exportPublishPack(req || {}));
  ipcMain.handle(IPC.PREFLIGHT_RUN, async (_e, req: any) => agentClient.preflightRun(req || {}));
  ipcMain.handle(IPC.EXPORT_LOGS, async (_e, req: any) => agentClient.exportLogs(req || {}));
  ipcMain.handle(IPC.EXPORT_CLEANUP_MISSING, async (_e, req: any) => agentClient.exportCleanupMissing(req || {}));
  ipcMain.handle(IPC.EXPORT_REBUILD, async (_e, req: any) => agentClient.exportRebuild(req || {}));
  ipcMain.handle(IPC.FIXWIZARD_PLAN, async (_e, req: any) => agentClient.fixwizardPlan(req || {}));
  ipcMain.handle(IPC.FIXWIZARD_EXECUTE, async (_e, req: any) => agentClient.fixwizardExecute(req || {}));
  ipcMain.handle(IPC.FIXWIZARD_RECHECK, async (_e, req: any) => agentClient.fixwizardRecheck(req || {}));
  ipcMain.handle(IPC.FIXWIZARD_ROLLBACK_LAST, async (_e, req: any) => agentClient.fixwizardRollbackLast(req || {}));
  ipcMain.handle(IPC.FIXWIZARD_ROLLBACK_CHAIN, async (_e, req: any) => agentClient.fixwizardRollbackChain(req || {}));
  ipcMain.handle(IPC.FIXWIZARD_CHAINS, async (_e, req: any) => agentClient.fixwizardChains(req || {}));
  ipcMain.handle(IPC.SKILLPACKS_CATALOG, async () => agentClient.skillpacksCatalog());
  ipcMain.handle(IPC.SKILLPACKS_PRESETS, async () => agentClient.skillpacksPresets());
  ipcMain.handle(IPC.SKILLPACKS_BIND_GET, async (_e, req: any) => agentClient.skillpacksBindGet(String(req?.book_id || "")));
  ipcMain.handle(IPC.SKILLPACKS_BIND_SET, async (_e, req: any) => agentClient.skillpacksBindSet(req || {}));
  ipcMain.handle(IPC.SKILLPACKS_AUTO_RUN, async (_e, req: any) => agentClient.skillpacksAutoRun(req || {}));
  ipcMain.handle(IPC.HTTP_PROXY_REQUEST, async (_e, req: any) => agentClient.httpProxyRequest(req || {}));
}
