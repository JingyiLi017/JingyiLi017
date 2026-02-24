import { app, BrowserWindow, ipcMain, shell } from "electron";
import path from "node:path";
import os from "node:os";
import fs from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { runBookDeconstruction, runWritingWorkflow } from "./services/workflows";
import { AppConfig, BookTaskInput, WritingTaskInput } from "./services/types";
import { exportHtmlToPdf } from "./pdf";
import { registerAgentIpcHandlers } from "./ipc/handlers";
import { SidecarManager } from "./sidecarManager";
import { getSettings } from "./store/settingsStore";

const isDev = !app.isPackaged;
const execFileAsync = promisify(execFile);

function safeName(input: string) {
  return String(input || "diagnose")
    .replace(/[\\/:*?"<>|]/g, "_")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 120);
}

function psQuote(input: string) {
  return `'${String(input).replace(/'/g, "''")}'`;
}

function createWindow() {
  // 建议将 preload 路径提取出来调试
  const preloadPath = app.isPackaged
    ? path.join(__dirname, 'preload.js') // 打包后通常在同级
    : path.join(__dirname, 'preload.js'); 

  console.log("Preload loading from:", preloadPath);

  const win = new BrowserWindow({
    width: 1200,
    height: 820,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false, // 💡 重要：如果是散装 JS 引用，关闭沙盒可以提高模块兼容性
    }
  });

  win.webContents.on("did-fail-load", (_event, errorCode, errorDescription, validatedURL) => {
    const msg = `[ui] did-fail-load code=${errorCode} url=${validatedURL} desc=${errorDescription}`;
    // eslint-disable-next-line no-console
    console.error(msg);
    win.webContents.send("log:append", msg);
  });

  if (isDev) {
    win.loadURL("http://localhost:5173");
    win.webContents.openDevTools({ mode: "detach" });
  } else {
    win.loadFile(path.join(__dirname, "../dist/index.html"));
  }
}

app.whenReady().then(async () => {
  const sidecar = new SidecarManager((line: string) => {
    for (const w of BrowserWindow.getAllWindows()) {
      w.webContents.send("log:append", line);
    }
  });
  registerAgentIpcHandlers(sidecar);

  ipcMain.handle("workflow:writing", async (_, input: WritingTaskInput, config: AppConfig) => {
    return runWritingWorkflow(input, config);
  });

  ipcMain.handle("workflow:book", async (_, input: BookTaskInput, config: AppConfig) => {
    return runBookDeconstruction(input, config);
  });

  ipcMain.handle("report:export-pdf", async (_, args: { html: string; fileStem: string }) => {
    const pdfPath = await exportHtmlToPdf(args);
    return { pdfPath };
  });

  ipcMain.handle("report:open-path", async (_, args: { path: string; reveal?: boolean }) => {
    const targetPath = String(args?.path || "");
    if (!targetPath) {
      throw new Error("EMPTY_PATH");
    }
    if (args?.reveal) {
      shell.showItemInFolder(targetPath);
      return { ok: true };
    }
    const err = await shell.openPath(targetPath);
    return { ok: err.length === 0, error: err || null };
  });

  ipcMain.handle("report:path-exists", async (_, args: { path: string }) => {
    const targetPath = String(args?.path || "").trim();
    if (!targetPath) return { ok: true, exists: false };
    try {
      await fs.access(targetPath);
      return { ok: true, exists: true };
    } catch {
      return { ok: true, exists: false };
    }
  });

  ipcMain.handle("report:save-json", async (_, args: { fileStem: string; content: string }) => {
    const outDir = path.join(os.homedir(), "NovelEngine", "Diagnose");
    await fs.mkdir(outDir, { recursive: true });
    const fileName = `${safeName(args?.fileStem || "splitbook_diagnose")}.json`;
    const outputPath = path.join(outDir, fileName);
    await fs.writeFile(outputPath, String(args?.content || ""), "utf-8");
    return { path: outputPath };
  });

  ipcMain.handle("report:save-text", async (_, args: { fileStem: string; content: string; ext?: string }) => {
    const outDir = path.join(os.homedir(), "NovelEngine", "Diagnose");
    await fs.mkdir(outDir, { recursive: true });
    const extRaw = String(args?.ext || "txt").trim().toLowerCase();
    const ext = extRaw === "md" ? "md" : "txt";
    const fileName = `${safeName(args?.fileStem || "draft_diff")}.${ext}`;
    const outputPath = path.join(outDir, fileName);
    await fs.writeFile(outputPath, String(args?.content || ""), "utf-8");
    return { path: outputPath };
  });

  ipcMain.handle(
    "report:save-text-at",
    async (_, args: { directory: string; fileStem: string; content: string; ext?: string }) => {
      const targetDir = String(args?.directory || "").trim();
      if (!targetDir) throw new Error("EMPTY_DIRECTORY");
      await fs.mkdir(targetDir, { recursive: true });
      const extRaw = String(args?.ext || "txt").trim().toLowerCase();
      const ext = extRaw === "md" ? "md" : "txt";
      const fileName = `${safeName(args?.fileStem || "draft_diff")}.${ext}`;
      const outputPath = path.join(targetDir, fileName);
      await fs.writeFile(outputPath, String(args?.content || ""), "utf-8");
      return { path: outputPath };
    }
  );

  ipcMain.handle("report:save-diagnose-bundle", async (_, args: { fileStem: string; bundle: any }) => {
    const stem = safeName(args?.fileStem || "diagnose_bundle");
    const rootDir = path.join(os.homedir(), "NovelEngine", "Diagnose");
    const bundleDir = path.join(rootDir, stem);
    await fs.mkdir(bundleDir, { recursive: true });

    const bundle = args?.bundle || {};
    const writeJson = async (name: string, data: any) => {
      await fs.writeFile(path.join(bundleDir, `${safeName(name)}.json`), JSON.stringify(data ?? null, null, 2), "utf-8");
    };

    await writeJson("summary", bundle?.summary || {});
    await writeJson("health", bundle?.health || {});
    await writeJson("splitbook", bundle?.splitbook || {});
    await writeJson("jobs_failed_recent", bundle?.jobs_failed_recent || []);
    await writeJson("jobs_running_recent", bundle?.jobs_running_recent || []);
    await writeJson("jobs_done_recent", bundle?.jobs_done_recent || []);
    await writeJson("template_assets", bundle?.template_assets || []);
    await writeJson("related_profiles", bundle?.related_profiles || []);
    await fs.writeFile(
      path.join(bundleDir, "bundle_full.json"),
      JSON.stringify(bundle, null, 2),
      "utf-8"
    );

    const zipPath = path.join(rootDir, `${stem}.zip`);
    let zipped = false;
    if (process.platform === "win32") {
      const psCmd = `Compress-Archive -Path ${psQuote(path.join(bundleDir, "*"))} -DestinationPath ${psQuote(zipPath)} -Force`;
      try {
        await execFileAsync("powershell.exe", ["-NoProfile", "-Command", psCmd]);
        zipped = true;
      } catch {
        zipped = false;
      }
    }

    return { directoryPath: bundleDir, zipPath: zipped ? zipPath : null };
  });

  createWindow();

  try {
    const cfg = await getSettings();
    if (cfg.autoStartSidecar !== false) {
      sidecar
        .start(cfg)
        .then((ret) => {
          const msg = `[sidecar] auto-start ready: ${ret.baseUrl}`;
          for (const w of BrowserWindow.getAllWindows()) w.webContents.send("log:append", msg);
        })
        .catch((e: any) => {
          const msg = `[sidecar] auto-start failed: ${String(e?.message || e)} (you can start manually in Settings/Health)`;
          for (const w of BrowserWindow.getAllWindows()) w.webContents.send("log:append", msg);
        });
    } else {
      const msg = "[sidecar] auto-start disabled by settings";
      for (const w of BrowserWindow.getAllWindows()) w.webContents.send("log:append", msg);
    }
  } catch (e: any) {
    const msg = `[sidecar] bootstrap settings failed: ${String(e?.message || e)}`;
    for (const w of BrowserWindow.getAllWindows()) w.webContents.send("log:append", msg);
  }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
