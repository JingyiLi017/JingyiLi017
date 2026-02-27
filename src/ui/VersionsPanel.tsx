import { useEffect, useMemo, useRef, useState } from "react";
import { DiffViewer } from "./DiffViewer";
import { DeleteConfirmDialog } from "./DeleteConfirmDialog";

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
  const [draftDeletingId, setDraftDeletingId] = useState("");
  const [deleteDialog, setDeleteDialog] = useState<{
    draftId: string;
    token: string;
    typedToken: string;
  } | null>(null);
  const [deleteError, setDeleteError] = useState("");
  const [deleteInputShake, setDeleteInputShake] = useState(false);
  const deleteInputRef = useRef<HTMLInputElement | null>(null);
  const deleteShakeTimerRef = useRef<number | null>(null);

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

  useEffect(() => {
    if (!deleteDialog) {
      setDeleteError("");
      setDeleteInputShake(false);
      return;
    }
    const timer = window.setTimeout(() => {
      const el = deleteInputRef.current;
      if (el) {
        el.focus();
        el.select();
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [deleteDialog]);

  useEffect(() => {
    return () => {
      if (deleteShakeTimerRef.current) {
        window.clearTimeout(deleteShakeTimerRef.current);
        deleteShakeTimerRef.current = null;
      }
    };
  }, []);

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

  function formatDeleteError(err: any): string {
    const payload = err?.payload || {};
    const detailCode = String(payload?.detail_code || payload?.detail || "").trim().toUpperCase();
    const detailZh = String(payload?.detail_zh || "").trim();
    if (detailZh) return detailZh;
    if (detailCode === "DRAFT_DELETE_LAST_FORBIDDEN") return "当前章节仅剩一个版本，不能删除。";
    if (detailCode === "DRAFT_DELETE_NO_REPLACEMENT") return "删除失败：没有可切换的替代版本。";
    if (detailCode === "DRAFT_NOT_FOUND") return "版本不存在或已被删除。";
    if (detailCode === "DRAFT_NOT_FOUND_FOR_CHAPTER") return "版本不属于当前章节。";
    const status = Number(err?.status || 0);
    if (status) return `删除失败（HTTP ${status}）`;
    return String(err?.message || err || "删除失败");
  }

  function openDeleteDialog(draftId: string) {
    const id = String(draftId || "").trim();
    if (!id) return;
    const token = id.slice(0, 8);
    setDeleteError("");
    setDeleteInputShake(false);
    setDeleteDialog({ draftId: id, token, typedToken: "" });
  }

  function markDeleteMismatch() {
    setDeleteError("输入校验码不一致，请核对后重试。");
    setDeleteInputShake(true);
    if (deleteShakeTimerRef.current) {
      window.clearTimeout(deleteShakeTimerRef.current);
      deleteShakeTimerRef.current = null;
    }
    deleteShakeTimerRef.current = window.setTimeout(() => {
      setDeleteInputShake(false);
      deleteShakeTimerRef.current = null;
    }, 280);
    const el = deleteInputRef.current;
    if (el) {
      el.focus();
      el.select();
    }
  }

  async function confirmDeleteDraftDialog() {
    if (!deleteDialog) return;
    setDraftDeletingId(deleteDialog.draftId);
    setDeleteError("");
    try {
      const out = await window.desktopApi.draftDelete({ draft_id: deleteDialog.draftId });
      const replacementId = String(out?.replacement_draft_id || "");
      const switched = Boolean(out?.switched);
      setDeleteDialog(null);
      await loadVersions();
      if (leftDraftId === deleteDialog.draftId) setLeftDraftId(replacementId || "");
      if (rightDraftId === deleteDialog.draftId) setRightDraftId(replacementId || "");
      if (selectedDraftId === deleteDialog.draftId) setSelectedDraftId(replacementId || "");
      onStatus?.(
        switched && replacementId
          ? `版本已删除，并自动切换到替代版本：${replacementId}`
          : `版本已删除：${deleteDialog.draftId}`
      );
    } catch (e: any) {
      setDeleteError(formatDeleteError(e));
    } finally {
      setDraftDeletingId("");
    }
  }

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
      onStatus?.(`已加载 ${Array.isArray(out?.items) ? out.items.length : 0} 个版本`);
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
      onStatus?.(`已选草稿 ${draftId}`);
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
      setErr("未找到所选节点的父草稿。");
      return;
    }
    setLeftDraftId(parentId);
    setRightDraftId(String(cur?.draft_id || ""));
    await loadPairTexts(parentId, String(cur?.draft_id || ""));
    onStatus?.(`已对比父节点 ${parentId} -> 子节点 ${String(cur?.draft_id || "")}`);
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
      setErr("未加载差异文本。");
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
      onStatus?.(`差异已导出：${p}`);
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
      <h3>版本</h3>
      <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
        <label>
          章节ID（chapter_id）
          <input value={chapterId} onChange={(e) => onPickChapterId(e.target.value)} placeholder="章节ID（UUID）" />
        </label>
        <button onClick={() => void loadVersions()} disabled={!chapterId || !!busy}>
          {busy === "load" ? "加载中..." : "加载版本"}
        </button>
        <label>
          分支
          <select value={branchFilter} onChange={(e) => setBranchFilter(e.target.value)}>
            <option value="all">全部</option>
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
          仅显示所选链路
        </label>
        <label>
          排序字段
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value as any)}>
            <option value="created_at">创建时间（created_at）</option>
            <option value="text_length">文本长度（text_length）</option>
          </select>
        </label>
        <label>
          方向
          <select value={sortDir} onChange={(e) => setSortDir(e.target.value as any)}>
            <option value="desc">降序（desc）</option>
            <option value="asc">升序（asc）</option>
          </select>
        </label>
      </div>
      {err ? <div className="hint" style={{ color: "#7f1d1d", marginTop: 8 }}>{err}</div> : null}
      {deleteError && !deleteDialog ? <div className="hint" style={{ color: "#7f1d1d", marginTop: 8 }}>{deleteError}</div> : null}
      <div className="scroll" style={{ maxHeight: 260, marginTop: 8 }}>
        <table className="table" style={{ width: "100%" }}>
          <thead>
            <tr>
              <th>变体</th>
              <th>分支</th>
              <th>草稿ID</th>
              <th>父节点</th>
              <th>长度</th>
              <th>已选</th>
              <th>操作</th>
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
                        title={collapsedById[did] ? "展开子节点" : "折叠子节点"}
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
                  <td>{active ? "是" : "否"}</td>
                  <td>
                    <button onClick={() => void selectDraft(did)} disabled={!!busy || active}>
                      {active ? "已选中" : "选中"}
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
                      title={hasParent ? "加载父节点对比" : "无父节点"}
                    >
                      父节点
                    </button>
                    <button
                      className="danger"
                      onClick={() => openDeleteDialog(did)}
                      style={{ marginLeft: 6 }}
                      disabled={!!busy || draftDeletingId === did}
                    >
                      {draftDeletingId === did ? "删除中..." : "删除"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {sortedDesc.length === 0 ? <div className="hint">暂无版本。</div> : null}
        {sortedDesc.length > 0 && filteredRows.length === 0 ? <div className="hint">当前筛选无结果。</div> : null}
      </div>
      <div className="job-grid" style={{ marginTop: 8 }}>
        <div>
          <div className="row" style={{ gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <strong>左侧</strong>
            <code className="small">{leftDraftId || "-"}</code>
            <button onClick={() => void loadDraftText(leftDraftId, "left")} disabled={!leftDraftId || !!busy}>
              加载左侧文本
            </button>
          </div>
        </div>
        <div>
          <div className="row" style={{ gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <strong>右侧</strong>
            <code className="small">{rightDraftId || "-"}</code>
            <button onClick={() => void loadDraftText(rightDraftId, "right")} disabled={!rightDraftId || !!busy}>
              加载右侧文本
            </button>
          </div>
        </div>
      </div>
      <div className="row" style={{ gap: 8, marginTop: 8, flexWrap: "wrap" }}>
        <button
          onClick={() => void loadPairTexts(leftDraftId, rightDraftId)}
          disabled={!leftDraftId || !rightDraftId || !!busy}
        >
          加载左右对
        </button>
        <button onClick={() => void exportDiff("md")} disabled={(!leftText && !rightText) || !!busy}>
          导出差异 .md
        </button>
        <button onClick={() => void exportDiff("txt")} disabled={(!leftText && !rightText) || !!busy}>
          导出差异 .txt
        </button>
        <button onClick={() => void openExportFolder()} disabled={!lastExportPath}>
          打开导出文件
        </button>
        <button
          onClick={() => void compareWithParent(rightDraftId || selectedDraftId)}
          disabled={!(rightDraftId || selectedDraftId) || !!busy}
        >
          与父节点对比（已选/右侧）
        </button>
      </div>
      {lastExportPath ? (
        <div className="small mono" style={{ marginTop: 6 }}>
          导出文件：{lastExportPath}
        </div>
      ) : null}
      {(leftText || rightText) ? (
        <div style={{ marginTop: 8 }}>
          <DiffViewer before={leftText} after={rightText} />
        </div>
      ) : null}
      <details style={{ marginTop: 8 }}>
        <summary>原始版本 JSON</summary>
        <pre>{JSON.stringify(sortedDesc, null, 2)}</pre>
      </details>

      <DeleteConfirmDialog
        open={!!deleteDialog}
        title="删除版本确认"
        requireInput={false}
        targetLabel={deleteDialog ? <>草稿ID：<code>{deleteDialog.draftId}</code></> : null}
        warning="如果删除的是当前选中/激活版本，系统会自动切换到其他版本后再删除。"
        promptLabel={deleteDialog ? <>请输入校验码 <strong>{deleteDialog.token}</strong> 以确认删除</> : "请输入校验码以确认删除"}
        expectedText={String(deleteDialog?.token || "")}
        value={String(deleteDialog?.typedToken || "")}
        placeholder={String(deleteDialog?.token || "")}
        busy={!!draftDeletingId}
        error={deleteError}
        inputRef={deleteInputRef}
        inputClassName={deleteInputShake ? "shake-once" : ""}
        confirmLabel="确认删除"
        busyLabel="删除中..."
        onValueChange={(nextValue) => {
          setDeleteDialog((prev) => (prev ? { ...prev, typedToken: nextValue } : prev));
          if (deleteError) setDeleteError("");
          if (deleteInputShake) setDeleteInputShake(false);
        }}
        onConfirm={() => void confirmDeleteDraftDialog()}
        onCancel={() => {
          setDeleteError("");
          setDeleteInputShake(false);
          setDeleteDialog(null);
        }}
        onMismatch={markDeleteMismatch}
      />
    </section>
  );
}
