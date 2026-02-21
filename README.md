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

## CI 打包（Windows）
已提供 GitHub Actions 工作流：`.github/workflows/windows-package.yml`

触发方式：
- 手动触发（workflow_dispatch）
- 推送到 `main/master` 且命中桌面/引擎相关路径

产物：
- `win-unpacked`（可直接运行验证）
- `sidecar-exe`（独立 sidecar 可执行文件）

## 关键目录
- `engine/app/main.py`: FastAPI 入口
- `engine/app/services/jobs.py`: Job 队列与任务执行
- `engine/app/services/ingest.py`: 拆书导入处理
- `engine/app/services/event_bus.py`: SSE 事件总线
- `infra/docker-compose.yml`: pgvector 数据库
- `docs/落地手册-桌面应用.md`: 分段式手册

## 详细落地手册
查看 `docs/落地手册-桌面应用.md`。
