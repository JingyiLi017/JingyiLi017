import { ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import { AgentDesktopSettings, setSettings } from "./store/settingsStore";

export type SidecarLogFn = (line: string) => void;

export class SidecarManager {
  private proc: ChildProcessWithoutNullStreams | null = null;
  private log: SidecarLogFn;
  public port = 17777;
  public baseUrl = "http://127.0.0.1:17777";

  constructor(logFn: SidecarLogFn) {
    this.log = logFn;
  }

  isRunning() {
    return !!this.proc;
  }

  async start(cfg: AgentDesktopSettings): Promise<{ ok: boolean; baseUrl: string; port: number }> {
    if (this.proc) {
      return { ok: true, baseUrl: this.baseUrl, port: this.port };
    }
    await this.ensureInfraReady(cfg);
    const preferred = Number(cfg.sidecarPreferredPort || 17777);
    this.port = await this.pickPort(preferred);
    this.baseUrl = `http://127.0.0.1:${this.port}`;
    const cwdRaw = String(cfg.sidecarCwd || "").trim();
    const cwd = cwdRaw ? path.resolve(cwdRaw) : path.resolve(process.cwd(), "engine");
    let lastErr: any = null;
    const executableCandidates = this.resolveExecutableCandidates(cfg, cwd);
    for (const exePath of executableCandidates) {
      try {
        await this.startExecutableOnce(exePath, cwd, cfg);
        await this.waitHealthy(String(cfg.agentToken || ""), 30000);
        await setSettings({ baseUrl: this.baseUrl, sidecarExecutablePath: exePath, sidecarCwd: cwd });
        return { ok: true, baseUrl: this.baseUrl, port: this.port };
      } catch (e: any) {
        lastErr = e;
        this.log(`[sidecar] executable start failed with ${exePath}: ${String(e?.message || e)}`);
        const p = this.proc as ChildProcessWithoutNullStreams | null;
        if (p) {
          try {
            p.kill("SIGTERM");
          } catch {}
          this.proc = null;
        }
      }
    }

    const candidates = this.resolvePythonCandidates(cfg, cwd);
    for (const pythonPath of candidates) {
      try {
        await this.startOnce(pythonPath, cwd, cfg);
        await this.waitHealthy(String(cfg.agentToken || ""), 30000);
        await setSettings({ baseUrl: this.baseUrl, sidecarPythonPath: pythonPath, sidecarCwd: cwd });
        return { ok: true, baseUrl: this.baseUrl, port: this.port };
      } catch (e: any) {
        lastErr = e;
        this.log(`[sidecar] start failed with ${pythonPath}: ${String(e?.message || e)}`);
        const p = this.proc as ChildProcessWithoutNullStreams | null;
        if (p) {
          try {
            p.kill("SIGTERM");
          } catch {}
          this.proc = null;
        }
      }
    }
    throw new Error(`SIDECAR_START_FAILED:${String(lastErr?.message || lastErr || "unknown")}`);
  }

  private async startExecutableOnce(exePath: string, cwd: string, cfg: AgentDesktopSettings): Promise<void> {
    const env: Record<string, string | undefined> = {
      ...process.env,
      PORT: String(this.port),
      DATABASE_URL: String(cfg.databaseUrl || "").trim() || undefined,
    };
    if (String(cfg.agentToken || "").trim()) env["AGENT_TOKEN"] = String(cfg.agentToken || "");
    this.log(`[sidecar] spawn ${exePath} --host 127.0.0.1 --port ${this.port} (cwd=${cwd})`);
    this.proc = spawn(exePath, ["--host", "127.0.0.1", "--port", String(this.port)], { cwd, env });
    await this.awaitSpawn();
    this.proc.stdout.on("data", (d) => this.log(`[sidecar:stdout] ${String(d).trimEnd()}`));
    this.proc.stderr.on("data", (d) => this.log(`[sidecar:stderr] ${String(d).trimEnd()}`));
    this.proc.on("exit", (code) => {
      this.log(`[sidecar] exited code=${String(code)}`);
      this.proc = null;
    });
  }

  private async startOnce(pythonPath: string, cwd: string, cfg: AgentDesktopSettings): Promise<void> {
    const env: Record<string, string | undefined> = {
      ...process.env,
      PORT: String(this.port),
      DATABASE_URL: String(cfg.databaseUrl || "").trim() || undefined,
    };
    if (String(cfg.agentToken || "").trim()) env["AGENT_TOKEN"] = String(cfg.agentToken || "");
    this.log(`[sidecar] spawn ${pythonPath} -m uvicorn app.main:app --host 127.0.0.1 --port ${this.port} (cwd=${cwd})`);
    this.proc = spawn(pythonPath, ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(this.port)], {
      cwd,
      env,
    });
    await this.awaitSpawn();
    this.proc.stdout.on("data", (d) => this.log(`[sidecar:stdout] ${String(d).trimEnd()}`));
    this.proc.stderr.on("data", (d) => this.log(`[sidecar:stderr] ${String(d).trimEnd()}`));
    this.proc.on("exit", (code) => {
      this.log(`[sidecar] exited code=${String(code)}`);
      this.proc = null;
    });
  }

  private async awaitSpawn(): Promise<void> {
    await new Promise<void>((resolve, reject) => {
      const proc = this.proc;
      if (!proc) return reject(new Error("PROC_NOT_CREATED"));
      const onError = (err: any) => {
        cleanup();
        reject(err || new Error("SPAWN_ERROR"));
      };
      const onExit = (code: number | null) => {
        if (code !== null && code !== 0) {
          cleanup();
          reject(new Error(`EXIT_${code}`));
        }
      };
      const onSpawn = () => {
        cleanup();
        resolve();
      };
      const cleanup = () => {
        proc.off("error", onError);
        proc.off("exit", onExit);
        proc.off("spawn", onSpawn);
      };
      proc.once("error", onError);
      proc.once("exit", onExit);
      proc.once("spawn", onSpawn);
    });
  }

  private resolveExecutableCandidates(cfg: AgentDesktopSettings, cwd: string): string[] {
    const picks: string[] = [];
    const push = (p: string) => {
      const s = String(p || "").trim();
      if (!s) return;
      if (!picks.includes(s)) picks.push(s);
    };
    push(String(cfg.sidecarExecutablePath || ""));
    const bundledBase = process.resourcesPath || "";
    if (bundledBase) {
      const exeName = process.platform === "win32" ? "sidecar.exe" : "sidecar";
      push(path.join(bundledBase, "sidecar", exeName));
      push(path.join(bundledBase, exeName));
    }
    push(path.join(cwd, "dist", process.platform === "win32" ? "sidecar.exe" : "sidecar"));
    return picks.filter((p) => fs.existsSync(p));
  }

  private resolvePythonCandidates(cfg: AgentDesktopSettings, cwd: string): string[] {
    const picks: string[] = [];
    const push = (p: string) => {
      const s = String(p || "").trim();
      if (!s) return;
      if (!picks.includes(s)) picks.push(s);
    };
    push(String(cfg.sidecarPythonPath || ""));
    const winVenv = path.join(cwd, ".venv", "Scripts", "python.exe");
    const unixVenv = path.join(cwd, ".venv", "bin", "python");
    if (fs.existsSync(winVenv)) push(winVenv);
    if (fs.existsSync(unixVenv)) push(unixVenv);
    push("python");
    if (process.platform === "win32") push("py");
    return picks;
  }

  async stop(): Promise<{ ok: boolean }> {
    if (!this.proc) return { ok: true };
    this.log("[sidecar] stopping");
    this.proc.kill("SIGTERM");
    this.proc = null;
    return { ok: true };
  }

  async health(agentToken: string): Promise<any> {
    try {
      const res = await fetch(`${this.baseUrl}/v1/health`, {
        method: "GET",
        headers: {
          ...(agentToken ? { Authorization: `Bearer ${agentToken}` } : {}),
        },
      });
      const text = await res.text();
      let json: any = null;
      try {
        json = text ? JSON.parse(text) : null;
      } catch {
        json = { raw: text };
      }
      return { ok: res.ok, status: res.status, body: json };
    } catch (e: any) {
      return { ok: false, status: 0, error: String(e?.message || e) };
    }
  }

  private async waitHealthy(agentToken: string, timeoutMs: number): Promise<void> {
    const started = Date.now();
    while (Date.now() - started < timeoutMs) {
      const h = await this.health(agentToken);
      if (h?.ok) return;
      await new Promise((r) => setTimeout(r, 300));
    }
    throw new Error("SIDECAR_HEALTH_TIMEOUT");
  }

  private pickPort(preferred: number): Promise<number> {
    const tryPort = (p: number): Promise<number> =>
      new Promise((resolve) => {
        const server = net.createServer();
        server.once("error", () => resolve(-1));
        server.once("listening", () => server.close(() => resolve(p)));
        server.listen(p, "127.0.0.1");
      });
    return (async () => {
      for (let p = preferred; p < preferred + 50; p++) {
        const ok = await tryPort(p);
        if (ok > 0) return ok;
      }
      throw new Error("NO_FREE_PORT");
    })();
  }

  private parseDbHostPort(databaseUrl: string): { host: string; port: number } | null {
    const raw = String(databaseUrl || "").trim();
    if (!raw) return null;
    let normalized = raw;
    if (normalized.startsWith("postgresql+")) normalized = normalized.replace("postgresql+", "postgresql");
    if (normalized.startsWith("postgres+")) normalized = normalized.replace("postgres+", "postgresql+");
    try {
      const u = new URL(normalized);
      const host = String(u.hostname || "").trim();
      const port = Number(u.port || "5432");
      if (!host || !Number.isFinite(port)) return null;
      return { host, port };
    } catch {
      return null;
    }
  }

  private isLocalHost(host: string): boolean {
    const h = String(host || "").trim().toLowerCase();
    return h === "127.0.0.1" || h === "localhost";
  }

  private async isTcpReachable(host: string, port: number, timeoutMs = 800): Promise<boolean> {
    return await new Promise<boolean>((resolve) => {
      const socket = new net.Socket();
      let done = false;
      const finish = (ok: boolean) => {
        if (done) return;
        done = true;
        try {
          socket.destroy();
        } catch {}
        resolve(ok);
      };
      socket.setTimeout(timeoutMs);
      socket.once("connect", () => finish(true));
      socket.once("timeout", () => finish(false));
      socket.once("error", () => finish(false));
      socket.connect(port, host);
    });
  }

  private async runCmd(cmd: string, args: string[], cwd?: string): Promise<{ ok: boolean; code: number }> {
    return await new Promise((resolve) => {
      const p = spawn(cmd, args, { cwd, stdio: ["ignore", "pipe", "pipe"] });
      p.stdout.on("data", (d) => this.log(`[infra:${cmd}:stdout] ${String(d).trimEnd()}`));
      p.stderr.on("data", (d) => this.log(`[infra:${cmd}:stderr] ${String(d).trimEnd()}`));
      p.once("error", () => resolve({ ok: false, code: -1 }));
      p.once("close", (code) => resolve({ ok: code === 0, code: Number(code ?? -1) }));
    });
  }

  private async ensureInfraReady(cfg: AgentDesktopSettings): Promise<void> {
    if (cfg.autoStartInfra === false) return;
    const hp = this.parseDbHostPort(String(cfg.databaseUrl || ""));
    if (!hp || !this.isLocalHost(hp.host)) return;
    const ready = await this.isTcpReachable(hp.host, hp.port);
    if (ready) {
      this.log(`[infra] database reachable at ${hp.host}:${hp.port}`);
      return;
    }
    const composeFile = String(cfg.infraComposePath || "").trim();
    if (!composeFile || !fs.existsSync(composeFile)) {
      throw new Error(`INFRA_COMPOSE_NOT_FOUND:${composeFile || "(empty)"}`);
    }
    this.log(`[infra] database not reachable, attempting docker compose up: ${composeFile}`);
    const composeDir = path.dirname(composeFile);
    let out = await this.runCmd("docker", ["compose", "-f", composeFile, "up", "-d", "postgres"], composeDir);
    if (!out.ok) {
      out = await this.runCmd("docker-compose", ["-f", composeFile, "up", "-d", "postgres"], composeDir);
    }
    if (!out.ok) {
      throw new Error("INFRA_DOCKER_START_FAILED");
    }
    for (let i = 0; i < 50; i++) {
      const ok = await this.isTcpReachable(hp.host, hp.port, 1200);
      if (ok) {
        this.log(`[infra] database ready at ${hp.host}:${hp.port}`);
        return;
      }
      await new Promise((r) => setTimeout(r, 600));
    }
    throw new Error("INFRA_DB_TIMEOUT");
  }
}
