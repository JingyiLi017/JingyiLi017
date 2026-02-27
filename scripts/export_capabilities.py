from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN_PY = ROOT / "engine" / "app" / "main.py"
OUT_MD = ROOT / "docs" / "PROJECT_CAPABILITY_MATRIX.md"

ROUTE_RE = re.compile(r'@app\.(get|post|put|patch|delete)\("([^"]+)"')


def group_name(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        return "misc"
    if parts[0] == "v1" and len(parts) >= 2:
        return parts[1]
    return parts[0]


def title(name: str) -> str:
    return {
        "health": "系统健康",
        "system": "系统维护",
        "settings": "分层设置",
        "books": "书籍管理",
        "chapters": "章节管理",
        "profiles": "画像管理",
        "splitbooks": "拆书系统",
        "jobs": "作业系统",
        "events": "SSE 事件流",
        "search": "搜索检索",
        "materials": "素材中心",
        "templates": "模板系统",
        "reports": "报告与评估",
        "agent": "智能体协作",
        "rewrite": "去AI味改写",
        "draft": "草稿流水线",
        "engine": "引擎闭环",
        "export": "导出发布",
        "preflight": "章节体检",
        "fixwizard": "修复向导",
        "workflows": "工作流引擎",
        "ab_batch": "A/B 批次",
        "extraction_runs": "抽取运行",
        "structure_templates": "结构模板",
        "structure_combos": "结构组合",
        "prompt_templates": "提示词模板",
        "skillpacks": "技能包",
        "ledger": "账本写回",
        "text_versions": "文本版本",
        "ingest": "导入管线",
    }.get(name, name)


def build_markdown(routes: list[tuple[str, str]]) -> str:
    by_group: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for method, path in routes:
        by_group[group_name(path)].append((method.upper(), path))

    groups = sorted(by_group.keys(), key=lambda key: (-len(by_group[key]), key))
    lines: list[str] = []
    lines.append("# 项目能力矩阵（自动生成）")
    lines.append("")
    lines.append(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 路由总数：{len(routes)}")
    lines.append("")
    lines.append("## 一、模块能力总览")
    lines.append("")
    lines.append("| 模块 | 路由数量 | 说明 |")
    lines.append("| --- | ---: | --- |")
    for key in groups:
        lines.append(f"| `{key}` | {len(by_group[key])} | {title(key)} |")
    lines.append("")
    lines.append("## 二、核心工作流")
    lines.append("")
    lines.append("### 1) AI 写作主链路")
    lines.append("- `POST /v1/books` 创建书籍")
    lines.append("- `POST /v1/books/{book_id}/settings` 保存创作简报/配置")
    lines.append("- `POST /v1/books/{book_id}/volumes/{volume_id}/plan/preview_auto` 生成卷纲")
    lines.append("- `POST /v1/draft/run` 生成草稿")
    lines.append("- `POST /v1/engine/closed_loop/run` 闭环执行（正文→回写→体检→改写）")
    lines.append("- `POST /v1/books/{book_id}/style/evolve` 风格进化")
    lines.append("")
    lines.append("### 2) 拆书主链路")
    lines.append("- `POST /v1/splitbooks` 创建拆书档案")
    lines.append("- `POST /v1/splitbooks/{splitbook_id}/ingest` 导入切分")
    lines.append("- `POST /v1/splitbooks/{splitbook_id}/embed` 向量化")
    lines.append("- `POST /v1/splitbooks/{splitbook_id}/extract_structured` 结构化抽取")
    lines.append("- `POST /v1/splitbooks/{splitbook_id}/build_templates` 模板沉淀")
    lines.append("- `POST /v1/splitbooks/{splitbook_id}/build_profile` 画像生成")
    lines.append("")
    lines.append("## 三、模块路由明细（每组最多展示 10 条）")
    lines.append("")
    for key in groups:
        lines.append(f"### {title(key)}（`{key}`）")
        preview = by_group[key][:10]
        for method, path in preview:
            lines.append(f"- `{method} {path}`")
        left = len(by_group[key]) - len(preview)
        if left > 0:
            lines.append(f"- ... 其余 {left} 条")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    content = MAIN_PY.read_text(encoding="utf-8")
    routes = ROUTE_RE.findall(content)
    md = build_markdown(routes)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"[ok] capability matrix written: {OUT_MD}")
    print(f"[ok] total routes: {len(routes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

