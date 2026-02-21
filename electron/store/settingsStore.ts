import { app } from "electron";
import fs from "node:fs/promises";
import path from "node:path";

export type AgentDesktopSettings = {
  baseUrl: string;
  agentToken: string;
  timeoutMs: number;
  sidecarPythonPath: string;
  sidecarExecutablePath: string;
  sidecarCwd: string;
  sidecarPreferredPort: number;
  autoStartSidecar: boolean;
};

function resolveDefaults(): AgentDesktopSettings {
  const appRoot = app.getAppPath();
  const projectRoot = path.resolve(appRoot, "..");
  const engineDir = path.resolve(projectRoot, "engine");
  const winVenvPython = path.resolve(engineDir, ".venv", "Scripts", "python.exe");
  const unixVenvPython = path.resolve(engineDir, ".venv", "bin", "python");
  return {
    baseUrl: "http://127.0.0.1:17777",
    agentToken: "",
    timeoutMs: 20000,
    sidecarPythonPath: process.platform === "win32" ? winVenvPython : unixVenvPython,
    sidecarExecutablePath: "",
    sidecarCwd: engineDir,
    sidecarPreferredPort: 17777,
    autoStartSidecar: true,
  };
}

function settingsPath() {
  return path.join(app.getPath("userData"), "agent-settings.json");
}

export async function getSettings(): Promise<AgentDesktopSettings> {
  const defaults = resolveDefaults();
  try {
    const p = settingsPath();
    const raw = await fs.readFile(p, "utf-8");
    const json = JSON.parse(raw);
    return {
      baseUrl: String(json?.baseUrl || defaults.baseUrl),
      agentToken: String(json?.agentToken || ""),
      timeoutMs: Number(json?.timeoutMs || defaults.timeoutMs),
      sidecarPythonPath: String(json?.sidecarPythonPath || defaults.sidecarPythonPath),
      sidecarExecutablePath: String(json?.sidecarExecutablePath || defaults.sidecarExecutablePath),
      sidecarCwd: String(json?.sidecarCwd || defaults.sidecarCwd),
      sidecarPreferredPort: Number(json?.sidecarPreferredPort || defaults.sidecarPreferredPort),
      autoStartSidecar: Boolean(json?.autoStartSidecar ?? defaults.autoStartSidecar),
    };
  } catch {
    return { ...defaults };
  }
}

export async function setSettings(patch: Partial<AgentDesktopSettings>): Promise<AgentDesktopSettings> {
  const defaults = resolveDefaults();
  const curr = await getSettings();
  const next: AgentDesktopSettings = {
    baseUrl: String(patch.baseUrl ?? curr.baseUrl ?? defaults.baseUrl),
    agentToken: String(patch.agentToken ?? curr.agentToken ?? ""),
    timeoutMs: Number(patch.timeoutMs ?? curr.timeoutMs ?? defaults.timeoutMs),
    sidecarPythonPath: String(patch.sidecarPythonPath ?? curr.sidecarPythonPath ?? defaults.sidecarPythonPath),
    sidecarExecutablePath: String(
      patch.sidecarExecutablePath ?? curr.sidecarExecutablePath ?? defaults.sidecarExecutablePath
    ),
    sidecarCwd: String(patch.sidecarCwd ?? curr.sidecarCwd ?? defaults.sidecarCwd),
    sidecarPreferredPort: Number(patch.sidecarPreferredPort ?? curr.sidecarPreferredPort ?? defaults.sidecarPreferredPort),
    autoStartSidecar: Boolean(patch.autoStartSidecar ?? curr.autoStartSidecar ?? defaults.autoStartSidecar),
  };
  await fs.mkdir(path.dirname(settingsPath()), { recursive: true });
  await fs.writeFile(settingsPath(), JSON.stringify(next, null, 2), "utf-8");
  return next;
}
