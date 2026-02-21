import { useEffect, useMemo, useState } from "react";
import { DiffViewer } from "./DiffViewer";

type Props = {
  bookId: string;
  chapterId: string;
  onPickChapterId: (id: string) => void;
  onStatus?: (msg: string) => void;
};

export function VersionsPanel({ bookId, chapterId, onPickChapterId, onStatus }: Props) {
  const [versions, setVersions] = useState<any[]>([]);
  const [selectedDraftId, setSelectedDraftId] = useState("");
  const [leftDraftId, setLeftDraftId] = useState("");
  const [rightDraftId, setRightDraftId] = useState("");
  const [leftText, setLeftText] = useState("");
  const [rightText, setRightText] = useState("");
  const [collapsedById, setCollapsedById] = useState<Record<string, boolean>>({});
  const [branchFilter, setBranchFilter] = useState("all");
  const [onlySelectedChain, setOnlySelectedChain] = useState(false);
  const [sortBy, setSortBy] = useState<"created_at" | "text_length">("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [lastExportPath, setLastExportPath] = useState("");
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem("versions_panel_prefs");
      if (!raw) return;
      const p = JSON.parse(raw);
      if (typeof p?.branchFilter === "string") setBranchFilter(p.branchFilter);
      if (typeof p?.onlySelectedChain === "boolean") setOnlySelectedChain(p.onlySelectedChain);
      if (p?.sortBy === "created_at" || p?.sortBy === "text_length") setSortBy(p.sortBy);
      if (p?.sortDir === "asc" || p?.sortDir === "desc") setSortDir(p.sortDir);
    } catch {
      // ignore corrupted local prefs
    }
  }, []);
  useEffect(() => {
    try {
      window.localStorage.setItem(
        "versions_panel_prefs",
        JSON.stringify({ branchFilter, onlySelectedChain, sortBy, sortDir })
      );
    } catch {
      // ignore storage errors
    }
  }, [branchFilter, onlySelectedChain, sortBy, sortDir]);

  const sortedDesc = useMemo(() => {
    const arr = [...versions];
    if (sortBy === "text_length") {
      arr.sort((a, b) => Number(a?.text_length || 0) - Number(b?.text_length || 0));
    } else {
      arr.sort((a, b) => String(a?.created_at || "").localeCompare(String(b?.created_at || "")));
    }
    return sortDir === "desc" ? arr.reverse() : arr;
  }, [versions, sortBy, sortDir]);
  const versionById = useMemo(() => {
    const m = new Map<string, any>();
    for (const v of versions) {
      const id = String(v?.draft_id || "").trim();
      if (id) m.set(id, v);
    }
    return m;
  }, [versions]);
  const childrenByParent = useMemo(() => {
    const m = new Map<string, any[]>();
    for (const v of versions) {
      const pid = String(v?.parent_draft_id || "").trim();
      if (!pid) continue;
      const arr = m.get(pid) || [];
      arr.push(v);
      m.set(pid, arr);
    }
    return m;
  }, [versions]);
  const branchOptions = useMemo(() => {
    const set = new Set<string>();
    for (const v of versions) {
      const b = String(v?.branch || "").trim();
      if (b) set.add(b);
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [versions]);
  const selectedChainSet = useMemo(() => {
    const out = new Set<string>();
    const anchor = String(selectedDraftId || rightDraftId || leftDraftId || "").trim();
    if (!anchor) return out;
    const visited = new Set<string>();
    const walkUp = (id: string) => {
      let cur = id;
      while (cur && !visited.has(cur)) {
        visited.add(cur);
        out.add(cur);
        const node = versionById.get(cur);
        const parent = String(node?.parent_draft_id || "").trim();
        cur = parent;
      }
    };
    const walkDown = (id: string) => {
      const queue = [id];
      while (queue.length) {
        const cur = queue.shift() || "";
        if (!cur || visited.has(`d:${cur}`)) continue;
        visited.add(`d:${cur}`);
        out.add(cur);
        const kids = childrenByParent.get(cur) || [];
        for (const k of kids) {
          const kid = String(k?.draft_id || "").trim();
          if (kid) queue.push(kid);
        }
      }
    };
    walkUp(anchor);
    walkDown(anchor);
    return out;
  }, [selectedDraftId, rightDraftId, leftDraftId, versionById, childrenByParent]);

  const treeRows = useMemo(() => {
    const roots: any[] = [];
    for (const v of versions) {
      const pid = String(v?.parent_draft_id || "").trim();
      if (!pid) {
        roots.push(v);
      }
    }
    const sortAsc = (arr: any[]) =>
      [...arr].sort((a, b) => String(a.created_at || "").localeCompare(String(b.created_at || "")));
    const out: Array<{ item: any; depth: number; hasChildren: boolean }> = [];
    const walk = (node: any, depth: number) => {
      const did = String(node?.draft_id || "");
      const kids = sortAsc(childrenByParent.get(did) || []);
      out.push({ item: node, depth, hasChildren: kids.length > 0 });
      if (collapsedById[did]) return;
      for (const k of kids) walk(k, depth + 1);
    };
    for (const r of sortAsc(roots)) walk(r, 0);
    return out;
  }, [versions, childrenByParent, collapsedById]);
  const filteredRows = useMemo(() => {
    return treeRows.filter(({ item }) => {
      const did = String(item?.draft_id || "").trim();
      const br = String(item?.branch || "").trim();
      if (branchFilter !== "all" && br !== branchFilter) return false;
      if (onlySelectedChain && !selectedChainSet.has(did)) return false;
      return true;
    });
  }, [treeRows, branchFilter, onlySelectedChain, selectedChainSet]);

  async function loadPairTexts(leftId: string, rightId: string) {
    if (!leftId || !rightId) return;
    setBusy("text:pair");
    setErr("");
    try {
      const [leftOut, rightOut] = await Promise.all([
        window.desktopApi.draftGet({ draft_id: leftId }),
        window.desktopApi.draftGet({ draft_id: rightId }),
      ]);
      setLeftText(String(leftOut?.item?.text || ""));
      setRightText(String(rightOut?.item?.text || ""));
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function loadVersions() {
    if (!chapterId) return;
    setBusy("load");
    setErr("");
    try {
      const out = await window.desktopApi.draftListVersions({ chapter_id: chapterId });
      const items = Array.isArray(out?.items) ? out.items : [];
      setVersions(items);
      const active = items.find((x: any) => Boolean(x?.is_active || x?.is_selected));
      if (active?.draft_id) {
        const ad = String(active.draft_id);
        setSelectedDraftId(ad);
        if (!leftDraftId) setLeftDraftId(ad);
      }
      if (items.length >= 2 && (!leftDraftId || !rightDraftId)) {
        const latest = String(items[0]?.draft_id || "");
        const prev = String(items[1]?.draft_id || "");
        if (latest && prev) {
          setRightDraftId(latest);
          setLeftDraftId(prev);
          void loadPairTexts(prev, latest);
        }
      }
      onStatus?.(`Loaded ${Array.isArray(out?.items) ? out.items.length : 0} versions`);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function selectDraft(draftId: string) {
    if (!chapterId || !draftId) return;
    setBusy("select");
    setErr("");
    try {
      await window.desktopApi.draftSelect({
        chapter_id: chapterId,
        draft_id: draftId,
        selected_by: "user",
        reason: "manual select from versions panel",
      });
      setSelectedDraftId(draftId);
      await loadVersions();
      onStatus?.(`Selected draft ${draftId}`);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function loadDraftText(draftId: string, side: "left" | "right") {
    if (!draftId) return;
    setBusy(`text:${side}`);
    setErr("");
    try {
      const out = await window.desktopApi.draftGet({ draft_id: draftId });
      const text = String(out?.item?.text || "");
      if (side === "left") {
        setLeftText(text);
      } else {
        setRightText(text);
      }
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function compareWithParent(draftId: string) {
    const cur = versionById.get(String(draftId || "").trim());
    const parentId = String(cur?.parent_draft_id || "").trim();
    if (!cur || !parentId) {
      setErr("Parent draft not found for selected node.");
      return;
    }
    setLeftDraftId(parentId);
    setRightDraftId(String(cur?.draft_id || ""));
    await loadPairTexts(parentId, String(cur?.draft_id || ""));
    onStatus?.(`Compared parent ${parentId} -> child ${String(cur?.draft_id || "")}`);
  }

  function buildDiffMarkdown(): string {
    const now = new Date().toISOString();
    return [
      "# Draft Diff",
      `- chapter_id: ${chapterId || "-"}`,
      `- left_draft_id: ${leftDraftId || "-"}`,
      `- right_draft_id: ${rightDraftId || "-"}`,
      `- exported_at: ${now}`,
      "",
      "## Left",
      "",
      leftText || "(empty)",
      "",
      "## Right",
      "",
      rightText || "(empty)",
      "",
    ].join("\n");
  }

  function buildDiffText(): string {
    const now = new Date().toISOString();
    return [
      "DRAFT_DIFF",
      `chapter_id=${chapterId || "-"}`,
      `left_draft_id=${leftDraftId || "-"}`,
      `right_draft_id=${rightDraftId || "-"}`,
      `exported_at=${now}`,
      "",
      "[LEFT]",
      leftText || "(empty)",
      "",
      "[RIGHT]",
      rightText || "(empty)",
      "",
    ].join("\n");
  }

  function joinPath(...parts: string[]): string {
    const cleaned = parts
      .map((p) => String(p || "").trim())
      .filter(Boolean)
      .map((p) => p.replace(/[\\/]+$/g, "").replace(/^[\\/]+/g, ""));
    if (!cleaned.length) return "";
    const first = String(parts[0] || "").trim().replace(/[\\/]+$/g, "");
    return [first, ...cleaned.slice(1)].join("\\");
  }

  async function exportDiff(ext: "md" | "txt") {
    if (!leftText && !rightText) {
      setErr("No diff text loaded.");
      return;
    }
    setBusy(`export:${ext}`);
    setErr("");
    try {
      const stem = `draft_diff_${(chapterId || "chapter").slice(0, 12)}_${Date.now()}`;
      const content = ext === "md" ? buildDiffMarkdown() : buildDiffText();
      let out: { path: string } | null = null;
      if (bookId) {
        try {
          const ws = await window.desktopApi.bookWorkspaceGet({ book_id: bookId });
          const workspacePath = String(ws?.workspace_path || "").trim();
          const bookSlug = String(ws?.book_slug || "").trim();
          if (workspacePath && bookSlug) {
            const targetDir = joinPath(workspacePath, "books", bookSlug, "exports", "diffs");
            out = await window.desktopApi.saveTextAt(targetDir, stem, content, ext);
          }
        } catch {
          // fallback below
        }
      }
      if (!out) {
        out = await window.desktopApi.saveText(stem, content, ext);
      }
      const p = String(out?.path || "");
      setLastExportPath(p);
      onStatus?.(`Diff exported: ${p}`);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function openExportFolder() {
    const p = String(lastExportPath || "").trim();
    if (!p) return;
    await window.desktopApi.openPath(p, false);
  }

  return (
    <section className="wb-panel" style={{ minHeight: "auto", marginBottom: 10 }}>
      <h3>Versions</h3>
      <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
        <label>
          chapter_id
          <input value={chapterId} onChange={(e) => onPickChapterId(e.target.value)} placeholder="uuid" />
        </label>
        <button onClick={() => void loadVersions()} disabled={!chapterId || !!busy}>
          {busy === "load" ? "Loading..." : "Load Versions"}
        </button>
        <label>
          branch
          <select value={branchFilter} onChange={(e) => setBranchFilter(e.target.value)}>
            <option value="all">all</option>
            {branchOptions.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
        </label>
        <label className="row" style={{ gap: 6, alignItems: "center" }}>
          <input
            type="checkbox"
            checked={onlySelectedChain}
            onChange={(e) => setOnlySelectedChain(e.target.checked)}
          />
          only selected chain
        </label>
        <label>
          sort by
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value as any)}>
            <option value="created_at">created_at</option>
            <option value="text_length">text_length</option>
          </select>
        </label>
        <label>
          dir
          <select value={sortDir} onChange={(e) => setSortDir(e.target.value as any)}>
            <option value="desc">desc</option>
            <option value="asc">asc</option>
          </select>
        </label>
      </div>
      {err ? <div className="hint" style={{ color: "#7f1d1d", marginTop: 8 }}>{err}</div> : null}
      <div className="scroll" style={{ maxHeight: 260, marginTop: 8 }}>
        <table className="table" style={{ width: "100%" }}>
          <thead>
            <tr>
              <th>variant</th>
              <th>branch</th>
              <th>draft_id</th>
              <th>parent</th>
              <th>len</th>
              <th>selected</th>
              <th>action</th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map(({ item: d, depth, hasChildren }) => {
              const did = String(d?.draft_id || "");
              const active = Boolean(d?.is_active || d?.is_selected || selectedDraftId === did);
              const hasParent = Boolean(String(d?.parent_draft_id || "").trim());
              return (
                <tr key={did}>
                  <td>
                    {hasChildren ? (
                      <button
                        className="small"
                        style={{ marginRight: 6, padding: "0 6px" }}
                        onClick={() => setCollapsedById((m) => ({ ...m, [did]: !m[did] }))}
                        title={collapsedById[did] ? "Expand children" : "Collapse children"}
                      >
                        {collapsedById[did] ? "+" : "-"}
                      </button>
                    ) : (
                      <span style={{ display: "inline-block", width: 20 }} />
                    )}
                    <span className="mono" style={{ opacity: 0.55 }}>
                      {depth > 0 ? `${"│ ".repeat(Math.max(0, depth - 1))}└─ ` : ""}
                    </span>
                    {String(d?.variant || "-")}
                  </td>
                  <td>{String(d?.branch || "-")}</td>
                  <td className="mono">{did}</td>
                  <td className="mono">{String(d?.parent_draft_id || "-")}</td>
                  <td>{Number(d?.text_length || 0)}</td>
                  <td>{active ? "yes" : "no"}</td>
                  <td>
                    <button onClick={() => void selectDraft(did)} disabled={!!busy || active}>
                      {active ? "Selected" : "Select"}
                    </button>
                    <button onClick={() => setLeftDraftId(did)} style={{ marginLeft: 6 }} disabled={leftDraftId === did}>
                      L
                    </button>
                    <button onClick={() => setRightDraftId(did)} style={{ marginLeft: 6 }} disabled={rightDraftId === did}>
                      R
                    </button>
                    <button
                      onClick={() => void compareWithParent(did)}
                      style={{ marginLeft: 6 }}
                      disabled={!!busy || !hasParent}
                      title={hasParent ? "Load parent->current for diff" : "No parent"}
                    >
                      Parent
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {sortedDesc.length === 0 ? <div className="hint">No versions loaded.</div> : null}
        {sortedDesc.length > 0 && filteredRows.length === 0 ? <div className="hint">No rows match current filters.</div> : null}
      </div>
      <div className="job-grid" style={{ marginTop: 8 }}>
        <div>
          <div className="row" style={{ gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <strong>Left</strong>
            <code className="small">{leftDraftId || "-"}</code>
            <button onClick={() => void loadDraftText(leftDraftId, "left")} disabled={!leftDraftId || !!busy}>
              Load Left Text
            </button>
          </div>
        </div>
        <div>
          <div className="row" style={{ gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <strong>Right</strong>
            <code className="small">{rightDraftId || "-"}</code>
            <button onClick={() => void loadDraftText(rightDraftId, "right")} disabled={!rightDraftId || !!busy}>
              Load Right Text
            </button>
          </div>
        </div>
      </div>
      <div className="row" style={{ gap: 8, marginTop: 8, flexWrap: "wrap" }}>
        <button
          onClick={() => void loadPairTexts(leftDraftId, rightDraftId)}
          disabled={!leftDraftId || !rightDraftId || !!busy}
        >
          Load Left/Right Pair
        </button>
        <button onClick={() => void exportDiff("md")} disabled={(!leftText && !rightText) || !!busy}>
          Export Diff .md
        </button>
        <button onClick={() => void exportDiff("txt")} disabled={(!leftText && !rightText) || !!busy}>
          Export Diff .txt
        </button>
        <button onClick={() => void openExportFolder()} disabled={!lastExportPath}>
          Open Export File
        </button>
        <button
          onClick={() => void compareWithParent(rightDraftId || selectedDraftId)}
          disabled={!(rightDraftId || selectedDraftId) || !!busy}
        >
          Compare Selected/Right With Parent
        </button>
      </div>
      {lastExportPath ? (
        <div className="small mono" style={{ marginTop: 6 }}>
          exported: {lastExportPath}
        </div>
      ) : null}
      {(leftText || rightText) ? (
        <div style={{ marginTop: 8 }}>
          <DiffViewer before={leftText} after={rightText} />
        </div>
      ) : null}
      <details style={{ marginTop: 8 }}>
        <summary>raw versions json</summary>
        <pre>{JSON.stringify(sortedDesc, null, 2)}</pre>
      </details>
    </section>
  );
}
