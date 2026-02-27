import { getSettings } from "../store/settingsStore";

async function fetchJson(path: string, body?: any) {
  const cfg = await getSettings();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), Math.max(3000, Number(cfg.timeoutMs || 20000)));
  try {
    const base = String(cfg.baseUrl || "").replace(/\/+$/, "");
    const url = `${base}${path}`;
    const res = await fetch(url, {
      method: body ? "POST" : "GET",
      headers: {
        "Content-Type": "application/json",
        ...(cfg.agentToken ? { Authorization: `Bearer ${cfg.agentToken}` } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    const text = await res.text();
    let data: any = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { raw: text };
    }
    if (!res.ok) {
      const err = new Error(`HTTP_${res.status}`);
      (err as any).status = res.status;
      (err as any).payload = data;
      throw err;
    }
    return data;
  } finally {
    clearTimeout(timeout);
  }
}

async function deleteJson(path: string) {
  const cfg = await getSettings();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), Math.max(3000, Number(cfg.timeoutMs || 20000)));
  try {
    const base = String(cfg.baseUrl || "").replace(/\/+$/, "");
    const url = `${base}${path}`;
    const res = await fetch(url, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
        ...(cfg.agentToken ? { Authorization: `Bearer ${cfg.agentToken}` } : {}),
      },
      signal: controller.signal,
    });
    const text = await res.text();
    let data: any = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { raw: text };
    }
    if (!res.ok) {
      const err = new Error(`HTTP_${res.status}`);
      (err as any).status = res.status;
      (err as any).payload = data;
      throw err;
    }
    return data;
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchRaw(req: { path: string; method?: string; body?: any; headers?: Record<string, string> }) {
  const cfg = await getSettings();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), Math.max(3000, Number(cfg.timeoutMs || 20000)));
  try {
    const base = String(cfg.baseUrl || "").replace(/\/+$/, "");
    const rawPath = String(req?.path || "").trim();
    if (!rawPath) throw new Error("EMPTY_PATH");
    const url = /^https?:\/\//i.test(rawPath) ? rawPath : `${base}${rawPath.startsWith("/") ? "" : "/"}${rawPath}`;
    const method = String(req?.method || "GET").toUpperCase();
    const headers: Record<string, string> = {};
    for (const [k, v] of Object.entries(req?.headers || {})) {
      if (typeof v === "string" && v.length) headers[k] = v;
    }
    if (cfg.agentToken && !Object.keys(headers).some((k) => k.toLowerCase() === "authorization")) {
      headers.Authorization = `Bearer ${cfg.agentToken}`;
    }
    let body: any = undefined;
    const hasBody = method !== "GET" && method !== "HEAD" && req?.body !== undefined && req?.body !== null;
    if (hasBody) {
      if (typeof req.body === "string") {
        body = req.body;
      } else {
        body = JSON.stringify(req.body);
        if (!Object.keys(headers).some((k) => k.toLowerCase() === "content-type")) {
          headers["Content-Type"] = "application/json";
        }
      }
    }
    const res = await fetch(url, { method, headers, body, signal: controller.signal });
    const text = await res.text();
    return {
      ok: res.ok,
      status: res.status,
      statusText: res.statusText,
      headers: Object.fromEntries(res.headers.entries()),
      text,
    };
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchJsonOrDefault(path: string, body: any, fallback: any) {
  try {
    return await fetchJson(path, body);
  } catch (e: any) {
    const status = Number(e?.status || 0);
    if (status === 404 || status === 405) {
      return fallback;
    }
    throw e;
  }
}

export const agentClient = {
  httpProxyRequest: (req: { path: string; method?: string; body?: any; headers?: Record<string, string> }) => fetchRaw(req),
  health: () => fetchJson("/v1/health"),
  diagnose: (req: any) => {
    const q = `book_id=${encodeURIComponent(String(req?.book_id || ""))}${req?.chapter_id ? `&chapter_id=${encodeURIComponent(String(req.chapter_id))}` : ""}`;
    return fetchJson(`/v1/agent/diagnose?${q}`);
  },
  propose: (req: any) => fetchJson("/v1/agent/propose", req),
  apply: (req: any) => fetchJson("/v1/agent/apply", req),
  orchestratePlan: (req: any) => fetchJson("/v1/agent/orchestrate/plan", req),
  orchestrateStep: (req: any) => fetchJson("/v1/agent/orchestrate/step", req),
  orchestrateRun: (req: any) => fetchJson("/v1/agent/orchestrate/run", req),
  rollback: (req: any) => fetchJsonOrDefault("/v1/agent/rollback", req, { ok: false, unsupported: true }),
  auditsList: (req: any) => fetchJsonOrDefault("/v1/agent/audits/list", req, { audits: [], unsupported: true }),
  comboInjectionsList: (req: any) => fetchJson("/v1/agent/combo_injections/list", req),
  comboInjectionsCleanup: (req: any) => fetchJson("/v1/agent/combo_injections/cleanup", req),
  planAutobuild: (req: any) => fetchJson("/v1/plan/autobuild", req),
  workflowDefinition: (workflowId: string) =>
    fetchJsonOrDefault(`/v1/workflows/definitions/${encodeURIComponent(String(workflowId || "draft_runner_v1"))}`, undefined, { unsupported: true }),
  workflowRun: (req: any) => fetchJson("/v1/workflows/run", req),
  workflowGetRun: (runId: string) => fetchJson(`/v1/workflows/runs/${encodeURIComponent(String(runId || ""))}`),
  workflowRollbackRun: (runId: string, req: any) =>
    fetchJsonOrDefault(`/v1/workflows/runs/${encodeURIComponent(String(runId || ""))}/rollback`, req, { ok: false, unsupported: true }),
  rewriteRun: (req: any) => fetchJson("/v1/rewrite/run", req),
  rewriteAccept: (req: any) => fetchJson("/v1/rewrite/accept", req),
  draftRun: (req: any) => fetchJson("/v1/draft/run", req),
  draftGet: (draftId: string) => fetchJson(`/v1/drafts/${encodeURIComponent(String(draftId || ""))}`),
  draftDelete: (draftId: string) => deleteJson(`/v1/drafts/${encodeURIComponent(String(draftId || ""))}`),
  chapterDrafts: (chapterId: string) => fetchJson(`/v1/chapters/${encodeURIComponent(String(chapterId || ""))}/drafts`),
  chapterActivateDraft: (chapterId: string, draftId: string) =>
    fetchJson(`/v1/chapters/${encodeURIComponent(String(chapterId || ""))}/drafts/${encodeURIComponent(String(draftId || ""))}/activate`, {}),
  draftListVersions: (req: any) => fetchJson("/v1/draft/list_versions", req),
  draftSelect: (req: any) => fetchJson("/v1/draft/select", req),
  ledgerPromoteSelected: (req: any) => fetchJson("/v1/ledger/promote_selected", req),
  bookWorkspaceGet: (bookId: string) => fetchJson(`/v1/books/${encodeURIComponent(String(bookId || ""))}/workspace`),
  bookWorkspaceSet: (bookId: string, req: any) =>
    fetchJson(`/v1/books/${encodeURIComponent(String(bookId || ""))}/workspace`, req),
  exportChapter: (req: any) => fetchJson("/v1/export/chapter", req),
  exportVolume: (req: any) => fetchJson("/v1/export/volume", req),
  exportPublishPack: (req: any) => fetchJson("/v1/export/publish_pack", req),
  preflightRun: (req: any) => fetchJson("/v1/preflight/run", req),
  exportLogs: (req: any) => fetchJson("/v1/export/logs", req),
  exportCleanupMissing: (req: any) => fetchJson("/v1/export/logs/cleanup_missing", req),
  exportRebuild: (req: any) => fetchJson("/v1/export/rebuild", req),
  fixwizardPlan: (req: any) => fetchJson("/v1/fixwizard/plan", req),
  fixwizardExecute: (req: any) => fetchJson("/v1/fixwizard/execute", req),
  fixwizardRecheck: (req: any) => fetchJson("/v1/fixwizard/recheck", req),
  fixwizardRollbackLast: (req: any) => fetchJson("/v1/fixwizard/rollback_last", req),
  fixwizardRollbackChain: (req: any) => fetchJson("/v1/fixwizard/rollback_chain", req),
  fixwizardChains: (req: any) => fetchJson("/v1/fixwizard/chains", req),
  skillpacksCatalog: () => fetchJson("/v1/skillpacks/catalog"),
  skillpacksPresets: () => fetchJson("/v1/skillpacks/presets"),
  skillpacksBindGet: (bookId: string) => fetchJson(`/v1/skillpacks/bindings/${encodeURIComponent(String(bookId || ""))}`),
  skillpacksBindSet: (req: any) => fetchJson("/v1/skillpacks/bind", req),
  skillpacksAutoRun: (req: any) => fetchJson("/v1/skillpacks/auto_run", req),
};
