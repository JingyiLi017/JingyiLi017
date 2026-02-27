import { ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import fs from "node:fs";
import fsp from "node:fs/promises";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { AgentDesktopSettings, setSettings } from "./store/settingsStore";

export type SidecarLogFn = (line: string) => void;

export class SidecarManager {
  private proc: ChildProcessWithoutNullStreams | null = null;
  private attachedExternal = false;
  private attachedPid: number | null = null;
  private attachedPidVerified = false;
  private readonly pidFilePath = path.join(os.tmpdir(), "writerbook-desktop-sidecar.json");
  private log: SidecarLogFn;
  public port = 17777;
  public baseUrl = "http://127.0.0.1:17777";

  constructor(logFn: SidecarLogFn) {
    this.log = logFn;
  }

  isRunning() {
    return !!this.proc || this.attachedExternal;
  }

  async start(cfg: AgentDesktopSettings): Promise<{ ok: boolean; baseUrl: string; port: number }> {
    if (this.proc) {
      return { ok: true, baseUrl: this.baseUrl, port: this.port };
    }
    if (this.attachedExternal) {
      const h = await this.health(String(cfg.agentToken || ""));
      if (h?.ok) {
        return { ok: true, baseUrl: this.baseUrl, port: this.port };
      }
      this.attachedExternal = false;
      this.attachedPid = null;
      this.attachedPidVerified = false;
    }

    const preferred = Number(cfg.sidecarPreferredPort || 17777);
    const reused = await this.tryAttachExisting(cfg, preferred);
    if (reused) {
      return reused;
    }

    await this.ensureInfraReady(cfg);
    this.port = await this.pickPort(preferred);
    this.baseUrl = `http://127.0.0.1:${this.port}`;
    const cwdRaw = String(cfg.sidecarCwd || "").trim();
    const resolvedCwd = cwdRaw ? path.resolve(cwdRaw) : "";
    const defaultCwd = process.resourcesPath
      ? path.join(process.resourcesPath, "bin", "sidecar")
      : path.resolve(process.cwd(), "engine");

    const cwd = resolvedCwd && fs.existsSync(resolvedCwd) ? resolvedCwd : defaultCwd;
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
        this.attachedExternal = false;
        this.attachedPid = null;
        this.attachedPidVerified = false;
        await this.clearPidFile();
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
        this.attachedExternal = false;
        this.attachedPid = null;
        this.attachedPidVerified = false;
        await this.clearPidFile();
      }
    }
    throw new Error(`SIDECAR_START_FAILED:${String(lastErr?.message || lastErr || "unknown")}`);
  }

  private async tryAttachExisting(
    cfg: AgentDesktopSettings,
    preferredPort: number
  ): Promise<{ ok: boolean; baseUrl: string; port: number } | null> {
    const token = String(cfg.agentToken || "");
    const fromPidFile = await this.tryAttachFromPidFile(token);
    if (fromPidFile) {
      return fromPidFile;
    }
    const listenerPid = await this.getListeningPidByPort(preferredPort);
    if (!listenerPid || listenerPid <= 0) {
      return null;
    }
    const signatureOk = await this.isLikelySidecarProcess(listenerPid);
    if (!signatureOk) {
      this.log(`[sidecar] port=${preferredPort} pid=${listenerPid} is not sidecar, skip attach`);
      return null;
    }
    const existingHealthy = await this.healthAtPort(preferredPort, token);
    if (existingHealthy.ok) {
      this.port = preferredPort;
      this.baseUrl = `http://127.0.0.1:${preferredPort}`;
      this.attachedExternal = true;
      this.attachedPid = listenerPid;
      this.attachedPidVerified = true;
      this.log(`[sidecar] reuse existing sidecar at ${this.baseUrl}, pid=${listenerPid}`);
      return { ok: true, baseUrl: this.baseUrl, port: this.port };
    }
    return null;
  }

  private async tryAttachFromPidFile(
    agentToken: string
  ): Promise<{ ok: boolean; baseUrl: string; port: number } | null> {
    const info = await this.readPidFile();
    if (!info) return null;
    const pid = Number(info.pid || 0);
    const port = Number(info.port || 0);
    if (pid <= 0 || port <= 0) {
      await this.clearPidFile();
      return null;
    }
    if (!this.isPidAlive(pid)) {
      await this.clearPidFile();
      return null;
    }
    const verified = await this.isLikelySidecarProcess(pid);
    if (!verified) {
      this.log(`[sidecar] pid file points to non-sidecar process pid=${pid}, ignore and clear`);
      await this.clearPidFile();
      return null;
    }
    const h = await this.healthAtPort(port, agentToken);
    if (!h.ok) {
      await this.clearPidFile();
      return null;
    }
    this.port = port;
    this.baseUrl = `http://127.0.0.1:${port}`;
    this.attachedExternal = true;
    this.attachedPid = pid;
    this.attachedPidVerified = true;
    this.log(`[sidecar] reuse existing pid=${pid} at ${this.baseUrl}`);
    return { ok: true, baseUrl: this.baseUrl, port: this.port };
  }

  private async startExecutableOnce(exePath: string, cwd: string, cfg: AgentDesktopSettings): Promise<void> {
    const env: Record<string, string | undefined> = {
      ...process.env,
      PORT: String(this.port),
      DATABASE_URL: String(cfg.databaseUrl || "").trim() || undefined,
    };
    if (String(cfg.agentToken || "").trim()) env["AGENT_TOKEN"] = String(cfg.agentToken || "");
    this.log(`[sidecar] spawn ${exePath} --host 127.0.0.1 --port ${this.port} (cwd=${cwd})`);
    const actualCwd = fs.existsSync(cwd) ? cwd : path.dirname(exePath);
    this.log(`[sidecar] resolved cwd=${actualCwd} (configured=${cwd})`);
    this.proc = spawn(exePath, ["--host", "127.0.0.1", "--port", String(this.port)], { cwd: actualCwd, env });
    await this.awaitSpawn();
    this.attachedExternal = false;
    this.attachedPid = this.proc.pid ?? null;
    this.attachedPidVerified = true;
    await this.writePidFile(this.proc.pid ?? null, this.port);
    this.proc.stdout.on("data", (d) => this.log(`[sidecar:stdout] ${String(d).trimEnd()}`));
    this.proc.stderr.on("data", (d) => this.log(`[sidecar:stderr] ${String(d).trimEnd()}`));
    this.proc.on("exit", (code) => {
      this.log(`[sidecar] exited code=${String(code)}`);
      this.proc = null;
      this.attachedPid = null;
      this.attachedExternal = false;
      this.attachedPidVerified = false;
      void this.clearPidFile();
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
    this.attachedExternal = false;
    this.attachedPid = this.proc.pid ?? null;
    this.attachedPidVerified = true;
    await this.writePidFile(this.proc.pid ?? null, this.port);
    this.proc.stdout.on("data", (d) => this.log(`[sidecar:stdout] ${String(d).trimEnd()}`));
    this.proc.stderr.on("data", (d) => this.log(`[sidecar:stderr] ${String(d).trimEnd()}`));
    this.proc.on("exit", (code) => {
      this.log(`[sidecar] exited code=${String(code)}`);
      this.proc = null;
      this.attachedPid = null;
      this.attachedExternal = false;
      this.attachedPidVerified = false;
      void this.clearPidFile();
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
      push(path.join(bundledBase, "bin", "sidecar", exeName));
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
    if (this.proc) {
      const pid = this.proc.pid ?? null;
      this.log(`[sidecar] stopping managed process pid=${String(pid ?? "-")}`);
      if (pid && pid > 0) {
        await this.terminateProcess(pid, "managed");
      } else {
        try {
          this.proc.kill("SIGTERM");
        } catch {}
      }
      this.proc = null;
      this.attachedPid = null;
      this.attachedExternal = false;
      this.attachedPidVerified = false;
      await this.clearPidFile();
      return { ok: true };
    }
    if (this.attachedExternal && this.attachedPid && this.isPidAlive(this.attachedPid)) {
      const verified = this.attachedPidVerified || (await this.isLikelySidecarProcess(this.attachedPid));
      if (verified) {
        await this.terminateProcess(this.attachedPid, "attached");
      } else {
        this.log(`[sidecar] skip stopping attached pid=${this.attachedPid} because signature is not sidecar`);
      }
    }
    this.attachedExternal = false;
    this.attachedPid = null;
    this.attachedPidVerified = false;
    await this.clearPidFile();
    return { ok: true };
  }

  private async terminateProcess(pid: number, source: "managed" | "attached"): Promise<void> {
    if (!this.isPidAlive(pid)) return;
    this.log(`[sidecar] stopping ${source} process pid=${pid}`);
    if (process.platform === "win32") {
      const out = await this.runCmd("taskkill", ["/PID", String(pid), "/T", "/F"]);
      if (!out.ok) {
        this.log(`[sidecar] taskkill failed pid=${pid} code=${out.code}`);
      }
    } else {
      try {
        process.kill(pid, "SIGTERM");
      } catch {}
    }
    let exited = await this.waitPidExit(pid, 5000);
    if (!exited && process.platform !== "win32") {
      try {
        process.kill(pid, "SIGKILL");
      } catch {}
      exited = await this.waitPidExit(pid, 2000);
    }
    if (!exited) {
      this.log(`[sidecar] process still alive after stop pid=${pid}`);
    }
  }

  private async waitPidExit(pid: number, timeoutMs: number): Promise<boolean> {
    const started = Date.now();
    while (Date.now() - started < timeoutMs) {
      if (!this.isPidAlive(pid)) return true;
      await new Promise((r) => setTimeout(r, 120));
    }
    return !this.isPidAlive(pid);
  }

  private isPidAlive(pid: number): boolean {
    if (!Number.isFinite(pid) || pid <= 0) return false;
    try {
      process.kill(pid, 0);
      return true;
    } catch {
      return false;
    }
  }

  private async getProcessSignature(pid: number): Promise<string> {
    if (!Number.isFinite(pid) || pid <= 0) return "";
    if (process.platform === "win32") {
      const cmd = `$p=Get-CimInstance Win32_Process -Filter "ProcessId = ${pid}" | Select-Object -First 1 ExecutablePath,CommandLine; if ($null -eq $p) { exit 3 }; Write-Output (($p.ExecutablePath -as [string]) + '||' + ($p.CommandLine -as [string]))`;
      const out = await this.runCmdCapture("powershell.exe", ["-NoProfile", "-Command", cmd]);
      if (!out.ok) return "";
      return String(out.stdout || "").trim();
    }
    try {
      const raw = await fsp.readFile(`/proc/${pid}/cmdline`, "utf-8");
      if (raw) return raw.replace(/\u0000/g, " ").trim();
    } catch {}
    const out = await this.runCmdCapture("ps", ["-p", String(pid), "-o", "command="]);
    if (!out.ok) return "";
    return String(out.stdout || "").trim();
  }

  private async isLikelySidecarProcess(pid: number): Promise<boolean> {
    const sig = (await this.getProcessSignature(pid)).toLowerCase();
    if (!sig) return false;
    if (sig.includes("sidecar.exe")) return true;
    if (/[\\/](sidecar)(\s|$)/.test(sig)) return true;
    if (sig.includes("uvicorn") && sig.includes("app.main:app")) return true;
    return false;
  }

  private async getListeningPidByPort(port: number): Promise<number | null> {
    if (!Number.isFinite(port) || port <= 0) return null;
    if (process.platform === "win32") {
      const cmd = `$p=Get-NetTCPConnection -State Listen -LocalPort ${port} -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess; if ($null -eq $p) { exit 3 }; Write-Output $p`;
      const out = await this.runCmdCapture("powershell.exe", ["-NoProfile", "-Command", cmd]);
      if (out.ok) {
        const pid = Number(String(out.stdout || "").trim());
        if (Number.isFinite(pid) && pid > 0) return pid;
      }
      const netstatOut = await this.runCmdCapture("cmd.exe", ["/c", "netstat -ano -p tcp"]);
      if (netstatOut.ok) {
        const lines = String(netstatOut.stdout || "").split(/\r?\n/);
        for (const raw of lines) {
          const line = String(raw || "").trim();
          if (!line) continue;
          const cols = line.split(/\s+/);
          if (cols.length < 5) continue;
          const proto = String(cols[0] || "").toUpperCase();
          const localAddress = String(cols[1] || "");
          const state = String(cols[3] || "").toUpperCase();
          const pid = Number(cols[4]);
          if (proto !== "TCP") continue;
          if (state !== "LISTENING") continue;
          if (!localAddress.endsWith(`:${port}`)) continue;
          if (Number.isFinite(pid) && pid > 0) return pid;
        }
      }
      return null;
    }
    const lsofOut = await this.runCmdCapture("lsof", ["-iTCP:" + String(port), "-sTCP:LISTEN", "-n", "-P", "-t"]);
    if (lsofOut.ok) {
      const line = String(lsofOut.stdout || "").split(/\r?\n/).find((x) => String(x || "").trim().length > 0) || "";
      const pid = Number(line.trim());
      if (Number.isFinite(pid) && pid > 0) return pid;
    }
    return null;
  }

  private async writePidFile(pid: number | null, port: number): Promise<void> {
    if (!pid || pid <= 0) return;
    const payload = {
      pid,
      port,
      updated_at: new Date().toISOString(),
    };
    try {
      await fsp.writeFile(this.pidFilePath, JSON.stringify(payload, null, 2), "utf-8");
    } catch {}
  }

  private async readPidFile(): Promise<{ pid: number; port: number } | null> {
    try {
      const raw = await fsp.readFile(this.pidFilePath, "utf-8");
      const parsed = JSON.parse(raw || "{}");
      return {
        pid: Number(parsed?.pid || 0),
        port: Number(parsed?.port || 0),
      };
    } catch {
      return null;
    }
  }

  private async clearPidFile(): Promise<void> {
    try {
      await fsp.unlink(this.pidFilePath);
    } catch {}
  }

  private async healthAtPort(port: number, agentToken: string): Promise<{ ok: boolean; status: number }> {
    if (!Number.isFinite(port) || port <= 0) return { ok: false, status: 0 };
    try {
      const res = await fetch(`http://127.0.0.1:${port}/v1/health`, {
        method: "GET",
        headers: {
          ...(agentToken ? { Authorization: `Bearer ${agentToken}` } : {}),
        },
      });
      return { ok: res.ok, status: res.status };
    } catch {
      return { ok: false, status: 0 };
    }
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

  private async runCmdCapture(
    cmd: string,
    args: string[],
    cwd?: string
  ): Promise<{ ok: boolean; code: number; stdout: string; stderr: string }> {
    return await new Promise((resolve) => {
      let stdout = "";
      let stderr = "";
      const p = spawn(cmd, args, { cwd, stdio: ["ignore", "pipe", "pipe"] });
      p.stdout.on("data", (d) => {
        const text = String(d);
        stdout += text;
      });
      p.stderr.on("data", (d) => {
        const text = String(d);
        stderr += text;
      });
      p.once("error", () => resolve({ ok: false, code: -1, stdout, stderr }));
      p.once("close", (code) => resolve({ ok: code === 0, code: Number(code ?? -1), stdout, stderr }));
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
    const provider = String(cfg.infraProvider || "docker");
    if (provider === "none") {
      throw new Error("INFRA_DISABLED_DB_NOT_REACHABLE");
    }
    if (provider === "local_pg") {
      await this.startLocalPostgres(cfg, hp.port);
    } else {
      await this.startDockerPostgres(cfg);
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

  private async startDockerPostgres(cfg: AgentDesktopSettings): Promise<void> {
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
  }

  private guessInitDbPathFromPgCtl(pgCtlPath: string): string {
    if (!pgCtlPath) return "";
    const dir = path.dirname(pgCtlPath);
    return path.join(dir, process.platform === "win32" ? "initdb.exe" : "initdb");
  }

  private guessPgCtlPathFromInitDb(initdbPath: string): string {
    if (!initdbPath) return "";
    const dir = path.dirname(initdbPath);
    return path.join(dir, process.platform === "win32" ? "pg_ctl.exe" : "pg_ctl");
  }

  private async startLocalPostgres(cfg: AgentDesktopSettings, port: number): Promise<void> {
    const pgCtl = String(cfg.localPgCtlPath || "").trim() || this.guessPgCtlPathFromInitDb(String(cfg.localPgInitDbPath || "").trim());
    const initdb = String(cfg.localPgInitDbPath || "").trim() || this.guessInitDbPathFromPgCtl(pgCtl);
    const dataDir = String(cfg.localPgDataDir || "").trim();
    if (!pgCtl || !fs.existsSync(pgCtl)) {
      throw new Error(`LOCAL_PG_CTL_NOT_FOUND:${pgCtl || "(empty)"}`);
    }
    if (!dataDir) {
      throw new Error("LOCAL_PG_DATA_DIR_EMPTY");
    }
    await fsp.mkdir(dataDir, { recursive: true });
    const pgVersionFile = path.join(dataDir, "PG_VERSION");
    if (!fs.existsSync(pgVersionFile)) {
      if (!initdb || !fs.existsSync(initdb)) {
        throw new Error(`LOCAL_INITDB_NOT_FOUND:${initdb || "(empty)"}`);
      }
      this.log(`[infra] local_pg initdb: ${dataDir}`);
      const initRes = await this.runCmd(initdb, ["-D", dataDir, "-U", "postgres", "-A", "trust", "-E", "UTF8"]);
      if (!initRes.ok) {
        throw new Error("LOCAL_INITDB_FAILED");
      }
    }
    const logFile = path.join(dataDir, "postgres.log");
    this.log(`[infra] local_pg pg_ctl start: ${dataDir} port=${port}`);
    const out = await this.runCmd(pgCtl, [
      "-D",
      dataDir,
      "-l",
      logFile,
      "-o",
      `-p ${port}`,
      "start",
      "-w",
      "-t",
      "30",
    ]);
    if (!out.ok) {
      throw new Error("LOCAL_PG_START_FAILED");
    }
  }
}
