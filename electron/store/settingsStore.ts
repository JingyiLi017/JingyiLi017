import { app } from "electron";
import fs from "node:fs/promises";
import path from "node:path";

export type AgentDesktopSettings = {
  baseUrl: string;
  agentToken: string;
  timeoutMs: number;
  databaseUrl: string;
  infraProvider: "docker" | "local_pg" | "none";
  sidecarPythonPath: string;
  sidecarExecutablePath: string;
  sidecarCwd: string;
  sidecarPreferredPort: number;
  autoStartSidecar: boolean;
  autoStartInfra: boolean;
  infraComposePath: string;
  localPgCtlPath: string;
  localPgInitDbPath: string;
  localPgDataDir: string;
};

function resolveDefaults(): AgentDesktopSettings {
  const appRoot = app.getAppPath();
  const projectRoot = path.resolve(appRoot, "..");
  const engineDir = path.resolve(projectRoot, "engine");
  const devCompose = path.resolve(projectRoot, "infra", "docker-compose.yml");
  const packagedCompose = path.resolve(process.resourcesPath || "", "infra", "docker-compose.yml");
  const infraComposePath = app.isPackaged ? packagedCompose : devCompose;
  const winVenvPython = path.resolve(engineDir, ".venv", "Scripts", "python.exe");
  const unixVenvPython = path.resolve(engineDir, ".venv", "bin", "python");
  return {
    baseUrl: "http://127.0.0.1:17777",
    agentToken: "",
    timeoutMs: 20000,
    databaseUrl: "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/novel_db",
    infraProvider: "docker",
    sidecarPythonPath: process.platform === "win32" ? winVenvPython : unixVenvPython,
    sidecarExecutablePath: "",
    sidecarCwd: engineDir,
    sidecarPreferredPort: 17777,
    autoStartSidecar: true,
    autoStartInfra: true,
    infraComposePath,
    localPgCtlPath: "",
    localPgInitDbPath: "",
    localPgDataDir: path.resolve(app.getPath("userData"), "pgdata"),
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
      databaseUrl: String(json?.databaseUrl || defaults.databaseUrl),
      infraProvider: (json?.infraProvider === "local_pg" || json?.infraProvider === "none" ? json.infraProvider : "docker"),
      sidecarPythonPath: String(json?.sidecarPythonPath || defaults.sidecarPythonPath),
      sidecarExecutablePath: String(json?.sidecarExecutablePath || defaults.sidecarExecutablePath),
      sidecarCwd: String(json?.sidecarCwd || defaults.sidecarCwd),
      sidecarPreferredPort: Number(json?.sidecarPreferredPort || defaults.sidecarPreferredPort),
      autoStartSidecar: Boolean(json?.autoStartSidecar ?? defaults.autoStartSidecar),
      autoStartInfra: Boolean(json?.autoStartInfra ?? defaults.autoStartInfra),
      infraComposePath: String(json?.infraComposePath || defaults.infraComposePath),
      localPgCtlPath: String(json?.localPgCtlPath || defaults.localPgCtlPath),
      localPgInitDbPath: String(json?.localPgInitDbPath || defaults.localPgInitDbPath),
      localPgDataDir: String(json?.localPgDataDir || defaults.localPgDataDir),
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
    databaseUrl: String(patch.databaseUrl ?? curr.databaseUrl ?? defaults.databaseUrl),
    infraProvider: (patch.infraProvider ?? curr.infraProvider ?? defaults.infraProvider) as AgentDesktopSettings["infraProvider"],
    sidecarPythonPath: String(patch.sidecarPythonPath ?? curr.sidecarPythonPath ?? defaults.sidecarPythonPath),
    sidecarExecutablePath: String(
      patch.sidecarExecutablePath ?? curr.sidecarExecutablePath ?? defaults.sidecarExecutablePath
    ),
    sidecarCwd: String(patch.sidecarCwd ?? curr.sidecarCwd ?? defaults.sidecarCwd),
    sidecarPreferredPort: Number(patch.sidecarPreferredPort ?? curr.sidecarPreferredPort ?? defaults.sidecarPreferredPort),
    autoStartSidecar: Boolean(patch.autoStartSidecar ?? curr.autoStartSidecar ?? defaults.autoStartSidecar),
    autoStartInfra: Boolean(patch.autoStartInfra ?? curr.autoStartInfra ?? defaults.autoStartInfra),
    infraComposePath: String(patch.infraComposePath ?? curr.infraComposePath ?? defaults.infraComposePath),
    localPgCtlPath: String(patch.localPgCtlPath ?? curr.localPgCtlPath ?? defaults.localPgCtlPath),
    localPgInitDbPath: String(patch.localPgInitDbPath ?? curr.localPgInitDbPath ?? defaults.localPgInitDbPath),
    localPgDataDir: String(patch.localPgDataDir ?? curr.localPgDataDir ?? defaults.localPgDataDir),
  };
  await fs.mkdir(path.dirname(settingsPath()), { recursive: true });
  await fs.writeFile(settingsPath(), JSON.stringify(next, null, 2), "utf-8");
  return next;
}
