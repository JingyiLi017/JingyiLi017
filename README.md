# WriterBook Desktop + Engine

AI写作引擎 + 拆书系统，升级为“双层架构”：
- 桌面端：Electron + React + TypeScript
- 本地引擎：FastAPI + Postgres/pgvector（Jobs + SSE + Ingest + Search）

## 当前能力
- 桌面端写作/拆书工作流与结果导出
- 引擎侧 `system/info`、`db/init`、`books`、`jobs`、`events`、`search/chunks`
- 账本侧 `skill_runs` + `ledger/apply`（staging 到正式账本）
- 结构模板库 `profiles/templates` + `extract.structure_beats.v1`
- Docker 一键启动 pgvector 数据库

## 能力统筹与验证（新增）
- 自动能力矩阵：`docs/PROJECT_CAPABILITY_MATRIX.md`
- 核心验证报告：`docs/reports/core-verify-latest.md`
- 一键验证命令：
```powershell
cmd /c npm run verify:core
```
- 拆书状态一致性回归（中断/中止/继续/删除）：
```powershell
cmd /c npm run verify:splitbook-state
```
- API 契约回归（pytest）：
```powershell
cmd /c npm run verify:api-contract
```
- 质量门禁（一键跑完核心验证 + 状态一致性 + API 契约回归 + 桌面端智能流水线烟测）：
```powershell
cmd /c npm run verify:quality
```
- 质量门禁报告：
  - `docs/reports/quality-gate-latest.md`
  - `docs/reports/quality-gate-latest.json`

## 快速开始（Ubuntu）
1. 启动数据库：
```bash
docker compose -f infra/docker-compose.yml up -d
```
2. 启动引擎：
```bash
bash dev-engine.sh
```
3. 启动桌面端：
```bash
npm install
npm run dev
```

## 快速开始（Windows）
1. 启动数据库（Docker Desktop）
```powershell
docker compose -f .\infra\docker-compose.yml up -d
```
2. 启动引擎
```powershell
.\dev-engine.ps1
```
3. 启动桌面端
```powershell
cmd /c npm run dev
```

## 一键封装发布（Windows）
目标：安装包内自带 sidecar，可直接桌面端一键启动使用（无需用户本机 Python）。

1. 构建 sidecar 可执行文件（PyInstaller）并打包桌面应用：
```powershell
cmd /c npm run dist
```

说明：`dist` 脚本默认启用镜像下载（可减少 Electron 下载失败）：
- `ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/`
- `ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/`

如需自定义镜像，可先设置环境变量再执行：
```powershell
$env:ELECTRON_MIRROR = "你的镜像地址"
$env:ELECTRON_BUILDER_BINARIES_MIRROR = "你的镜像地址"
cmd /c npm run dist
```

2. 产物目录：
- 安装包：`release/`
- sidecar 可执行文件：`engine/dist/sidecar/sidecar.exe`

3. 运行逻辑（已内置）：
- 桌面应用优先启动安装包内 `resources/sidecar/sidecar.exe`
- 若不存在则回退到 `engine/.venv` 或系统 Python
- 默认自动启动 sidecar，可在 UI 关闭 `auto_start`
- 默认自动拉起本地数据库基础设施（`docker compose up -d postgres`），可在 UI 关闭 `auto_start_infra`
- 可在 UI 修改 `database_url` 与 `infra_compose`，实现本地/远端数据库切换

4. 首次使用建议：
- 安装并启动 Docker Desktop
- 打开应用后点击 `One-Click Ready`
- 若成功，`sidecar health` 与 `health` 均为 `ok`

## 无 Docker 模式（local_pg）
当你不希望使用 Docker，可在桌面端 Settings 配置：
- `infra_provider = local_pg`
- `local_pg_ctl = C:\Program Files\PostgreSQL\16\bin\pg_ctl.exe`
- `local_initdb = C:\Program Files\PostgreSQL\16\bin\initdb.exe`（可留空自动推断）
- `local_pg_data = <一个可写目录>`（首次会自动 initdb）
- `database_url` 指向 `127.0.0.1:<port>`

然后点击 `One-Click Ready`，应用会自动执行本机 PostgreSQL 初始化/启动。

## CI 打包（Windows）
已提供 GitHub Actions 工作流：`.github/workflows/windows-package.yml`

触发方式：
- 手动触发（workflow_dispatch）
- 推送到 `main/master` 且命中桌面/引擎相关路径

手动触发支持参数：
- `package_target=dir`：仅产出 `win-unpacked`
- `package_target=installer`：仅产出安装包（NSIS）
- `package_target=both`：同时产出 `win-unpacked + 安装包`
- 若手动触发未传 `package_target`：默认按 `both` 执行
- `push` 自动触发时默认按 `dir` 执行（仅 `win-unpacked`）

产物：
- `win-unpacked`（可直接运行验证）
- `win-installer`（安装包与更新元数据）
- `sidecar-exe`（独立 sidecar 可执行文件）

兼容触发（无 inputs 的客户端）：
- 使用 `.github/workflows/windows-package-compat.yml`
- 仅支持手动触发（workflow_dispatch）
- 固定产出：`win-unpacked + win-installer + sidecar-exe`

## 关键目录
- `engine/app/main.py`: FastAPI 入口
- `engine/app/services/jobs.py`: Job 队列与任务执行
- `engine/app/services/ingest.py`: 拆书导入处理
- `engine/app/services/event_bus.py`: SSE 事件总线
- `infra/docker-compose.yml`: pgvector 数据库
- `docs/落地手册-桌面应用.md`: 分段式手册

## 一键闭环接口（规划→生成→回写→体检→可选去 AI 味）

已新增：`POST /v1/engine/closed_loop/run`

最小请求示例：
```json
{
  "book_id": "BOOK_UUID",
  "chapter_id": "CHAPTER_UUID",
  "intent_confirmed": "本章推进主线并留钩子",
  "do_writeback": true,
  "run_preflight": true,
  "rewrite": {
    "enabled": false,
    "level": "L1",
    "auto_accept": false
  }
}
```

可选参数：
- `dry_run`：仅跑生成工作流，不做回写/落库副作用
- `reuse_if_exists`：复用同幂等键已执行结果
- `fail_on_preflight_fail`：当体检 `overall=FAIL` 时将整体 `ok` 置为 `false`
- `writeback`：可单独开关 `extract_facts / extract_growth / extract_timeline / extract_new_materials / run_eval`

## 拆书增强接口（反照抄 + 跨书模板库）

- 反照抄检查：`POST /v1/splitbooks/{splitbook_id}/anti_copy_check`  
  输入 `chapter_no + content`，输出 `anti_copy_score / risk_level / top_hits / suggestions`。
- 跨书模板库构建：`POST /v1/splitbooks/library/build`  
  输入 `splitbook_ids[]`（可空，空时自动取最近拆书），输出抽象模板资产并入库 `template_asset`。

补充：`EMBED` 阶段的向量默认写入数据库表 `splitbook_chunk_embedding`，不是直接写文本文件。  
若在请求体传入 `output_dir`，会额外输出一份向量化报告 JSON 到该目录（用于落盘审计）。

默认已启用自动优化（无需人工调参）：
- Ingest：按文本体量自动调整 `chunk_size / overlap / batch_insert`
- Embed：按分块数量自动调整 `batch / worker_count`（并行嵌入，不改变模型与向量质量）

## 大文件预切分脚本

超大 TXT（百万字）建议先预切分成 JSONL，再导入拆书：

```powershell
engine\.venv\Scripts\python engine\scripts\splitbook_prechunk.py --input D:\books\demo.txt --output D:\books\demo.prechunk.jsonl --chunk-size 1200 --overlap 180
```

## 详细落地手册
查看 `docs/落地手册-桌面应用.md`。
