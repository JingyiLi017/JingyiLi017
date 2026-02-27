# 项目能力矩阵（自动生成）

- 生成时间：2026-02-25 21:51:10
- 路由总数：256

## 一、模块能力总览

| 模块 | 路由数量 | 说明 |
| --- | ---: | --- |
| `books` | 65 | 书籍管理 |
| `chapters` | 34 | 章节管理 |
| `splitbooks` | 18 | 拆书系统 |
| `profiles` | 14 | 画像管理 |
| `settings` | 13 | 分层设置 |
| `templates` | 11 | 模板系统 |
| `agent` | 10 | 智能体协作 |
| `jobs` | 9 | 作业系统 |
| `materials` | 8 | 素材中心 |
| `system` | 7 | 系统维护 |
| `export` | 6 | 导出发布 |
| `fixwizard` | 6 | 修复向导 |
| `payoff_templates` | 5 | payoff_templates |
| `skillpacks` | 5 | 技能包 |
| `ab_batch` | 4 | A/B 批次 |
| `workflows` | 4 | 工作流引擎 |
| `draft` | 3 | 草稿流水线 |
| `skill_runs` | 3 | skill_runs |
| `asset_policy_proposals` | 2 | asset_policy_proposals |
| `ctx_tags` | 2 | ctx_tags |
| `drafts` | 2 | drafts |
| `extraction_runs` | 2 | 抽取运行 |
| `plan` | 2 | plan |
| `rewrite` | 2 | 去AI味改写 |
| `search` | 2 | 搜索检索 |
| `structure_combos` | 2 | 结构组合 |
| `structure_templates` | 2 | 结构模板 |
| `text_versions` | 2 | 文本版本 |
| `engine` | 1 | 引擎闭环 |
| `events` | 1 | SSE 事件流 |
| `foreshadow` | 1 | foreshadow |
| `growth` | 1 | growth |
| `health` | 1 | 系统健康 |
| `ingest` | 1 | 导入管线 |
| `ledger` | 1 | 账本写回 |
| `preflight` | 1 | 章节体检 |
| `prompt_templates` | 1 | 提示词模板 |
| `ref_inbox` | 1 | ref_inbox |
| `reports` | 1 | 报告与评估 |

## 二、核心工作流

### 1) AI 写作主链路
- `POST /v1/books` 创建书籍
- `POST /v1/books/{book_id}/settings` 保存创作简报/配置
- `POST /v1/books/{book_id}/volumes/{volume_id}/plan/preview_auto` 生成卷纲
- `POST /v1/draft/run` 生成草稿
- `POST /v1/engine/closed_loop/run` 闭环执行（正文→回写→体检→改写）
- `POST /v1/books/{book_id}/style/evolve` 风格进化

### 2) 拆书主链路
- `POST /v1/splitbooks` 创建拆书档案
- `POST /v1/splitbooks/{splitbook_id}/ingest` 导入切分
- `POST /v1/splitbooks/{splitbook_id}/embed` 向量化
- `POST /v1/splitbooks/{splitbook_id}/extract_structured` 结构化抽取
- `POST /v1/splitbooks/{splitbook_id}/build_templates` 模板沉淀
- `POST /v1/splitbooks/{splitbook_id}/build_profile` 画像生成

## 三、模块路由明细（每组最多展示 10 条）

### 书籍管理（`books`）
- `GET /v1/books/{book_id}/settings`
- `POST /v1/books/{book_id}/settings`
- `POST /v1/books/{book_id}/master_outline/auto_generate`
- `GET /v1/books/{book_id}/ai_debug`
- `POST /v1/books`
- `GET /v1/books`
- `DELETE /v1/books/{book_id}`
- `POST /v1/books/{book_id}/chapters`
- `GET /v1/books/{book_id}/chapters`
- `GET /v1/books/{book_id}/draft_confirmations`
- ... 其余 55 条

### 章节管理（`chapters`）
- `GET /v1/chapters/{chapter_id}/settings`
- `POST /v1/chapters/{chapter_id}/settings`
- `GET /v1/chapters/{chapter_id}/settings/effective`
- `DELETE /v1/chapters/{chapter_id}`
- `GET /v1/chapters/{chapter_id}/intent`
- `POST /v1/chapters/{chapter_id}/intent`
- `POST /v1/chapters/{chapter_id}/intent/suggest`
- `POST /v1/chapters/{chapter_id}/foreshadow/plan`
- `POST /v1/chapters/{chapter_id}/foreshadow/suggest_events`
- `POST /v1/chapters/{chapter_id}/foreshadow/confirm_events`
- ... 其余 24 条

### 拆书系统（`splitbooks`）
- `GET /v1/splitbooks`
- `GET /v1/splitbooks/compare`
- `POST /v1/splitbooks`
- `DELETE /v1/splitbooks/{splitbook_id}`
- `POST /v1/splitbooks/{splitbook_id}/allow_guard`
- `POST /v1/splitbooks/{splitbook_id}/ingest`
- `POST /v1/splitbooks/{splitbook_id}/embed`
- `POST /v1/splitbooks/{splitbook_id}/build_templates`
- `POST /v1/splitbooks/{splitbook_id}/extract_structured`
- `POST /v1/splitbooks/{splitbook_id}/build_profile`
- ... 其余 8 条

### 画像管理（`profiles`）
- `POST /v1/profiles`
- `GET /v1/profiles`
- `GET /v1/profiles/{profile_id}`
- `DELETE /v1/profiles/{profile_id}`
- `POST /v1/profiles/{profile_id}`
- `GET /v1/profiles/{profile_id}/versions`
- `GET /v1/profiles/{profile_id}/versions/{version}`
- `POST /v1/profiles/{profile_id}/active_version`
- `POST /v1/profiles/{profile_id}/diff`
- `POST /v1/profiles/{profile_id}/clone`
- ... 其余 4 条

### 分层设置（`settings`）
- `GET /v1/settings`
- `POST /v1/settings`
- `GET /v1/settings/global`
- `POST /v1/settings/global`
- `GET /v1/settings/default_template`
- `POST /v1/settings/diff`
- `GET /v1/settings/presets`
- `POST /v1/settings/presets`
- `POST /v1/settings/presets/{preset_id}`
- `DELETE /v1/settings/presets/{preset_id}`
- ... 其余 3 条

### 模板系统（`templates`）
- `GET /v1/templates`
- `GET /v1/templates/assets/{asset_id}`
- `DELETE /v1/templates/assets/{asset_id}`
- `DELETE /v1/templates/{template_id}`
- `POST /v1/templates/evolve`
- `GET /v1/templates/variants`
- `GET /v1/templates/variants/{variant_id}`
- `POST /v1/templates/variants/{variant_id}/enable`
- `POST /v1/templates/variants/{variant_id}/disable`
- `POST /v1/templates/effect_samples`
- ... 其余 1 条

### 智能体协作（`agent`）
- `GET /v1/agent/diagnose`
- `POST /v1/agent/orchestrate/plan`
- `POST /v1/agent/orchestrate/step`
- `POST /v1/agent/orchestrate/run`
- `POST /v1/agent/propose`
- `POST /v1/agent/apply`
- `POST /v1/agent/audits/list`
- `POST /v1/agent/combo_injections/list`
- `POST /v1/agent/combo_injections/cleanup`
- `POST /v1/agent/rollback`

### 作业系统（`jobs`）
- `POST /v1/jobs`
- `GET /v1/jobs`
- `DELETE /v1/jobs`
- `DELETE /v1/jobs/{job_id}`
- `GET /v1/jobs/examples`
- `GET /v1/jobs/examples/{job_type}`
- `POST /v1/jobs/{job_id}/cancel`
- `POST /v1/jobs/{job_id}/resume`
- `GET /v1/jobs/{job_id}`

### 素材中心（`materials`）
- `GET /v1/materials`
- `POST /v1/materials`
- `GET /v1/materials/{card_id}`
- `DELETE /v1/materials/{card_id}`
- `POST /v1/materials/{card_id}/embed`
- `POST /v1/materials/knn`
- `POST /v1/materials/import_from_chunks`
- `POST /v1/materials/{card_id}/policy`

### 系统维护（`system`）
- `GET /v1/system/info`
- `POST /v1/system/db/init`
- `POST /v1/system/init`
- `POST /v1/system/db/verify`
- `POST /v1/system/rebuild_fts`
- `POST /v1/system/cleanup_jobs`
- `POST /v1/system/rebuild_embeddings`

### 导出发布（`export`）
- `POST /v1/export/chapter`
- `POST /v1/export/volume`
- `POST /v1/export/publish_pack`
- `POST /v1/export/logs`
- `POST /v1/export/logs/cleanup_missing`
- `POST /v1/export/rebuild`

### 修复向导（`fixwizard`）
- `POST /v1/fixwizard/plan`
- `POST /v1/fixwizard/execute`
- `POST /v1/fixwizard/rollback_chain`
- `POST /v1/fixwizard/rollback_last`
- `POST /v1/fixwizard/chains`
- `POST /v1/fixwizard/recheck`

### payoff_templates（`payoff_templates`）
- `GET /v1/payoff_templates`
- `GET /v1/payoff_templates/hits`
- `GET /v1/payoff_templates/stats`
- `POST /v1/payoff_templates`
- `DELETE /v1/payoff_templates/{template_id}`

### 技能包（`skillpacks`）
- `GET /v1/skillpacks/presets`
- `GET /v1/skillpacks/catalog`
- `GET /v1/skillpacks/bindings/{book_id}`
- `POST /v1/skillpacks/bind`
- `POST /v1/skillpacks/auto_run`

### A/B 批次（`ab_batch`）
- `GET /v1/ab_batch/{batch_id}`
- `POST /v1/ab_batch/{batch_id}/retry_failed`
- `POST /v1/ab_batch/{batch_id}/promote`
- `POST /v1/ab_batch/{batch_id}/promote_winner`

### 工作流引擎（`workflows`）
- `GET /v1/workflows/definitions/{workflow_id}`
- `POST /v1/workflows/run`
- `GET /v1/workflows/runs/{run_id}`
- `POST /v1/workflows/runs/{run_id}/rollback`

### 草稿流水线（`draft`）
- `POST /v1/draft/list_versions`
- `POST /v1/draft/run`
- `POST /v1/draft/select`

### skill_runs（`skill_runs`）
- `GET /v1/skill_runs/{skill_run_id}`
- `GET /v1/skill_runs/latest`
- `POST /v1/skill_runs`

### asset_policy_proposals（`asset_policy_proposals`）
- `POST /v1/asset_policy_proposals/{proposal_id}/accept`
- `POST /v1/asset_policy_proposals/{proposal_id}/reject`

### ctx_tags（`ctx_tags`）
- `GET /v1/ctx_tags/dictionary`
- `POST /v1/ctx_tags/dictionary`

### drafts（`drafts`）
- `GET /v1/drafts/{draft_id}`
- `DELETE /v1/drafts/{draft_id}`

### 抽取运行（`extraction_runs`）
- `GET /v1/extraction_runs/{run_id}`
- `POST /v1/extraction_runs/{run_id}/retry`

### plan（`plan`）
- `POST /v1/plan/autobuild`
- `GET /v1/plan/items/{item_id}/execution_trace`

### 去AI味改写（`rewrite`）
- `POST /v1/rewrite/run`
- `POST /v1/rewrite/accept`

### 搜索检索（`search`）
- `GET /v1/search/chunks`
- `GET /v1/search`

### 结构组合（`structure_combos`）
- `GET /v1/structure_combos`
- `POST /v1/structure_combos/{combo_id}/policy`

### 结构模板（`structure_templates`）
- `GET /v1/structure_templates`
- `POST /v1/structure_templates/{template_id}/policy`

### 文本版本（`text_versions`）
- `POST /v1/text_versions/{text_ver_id}/extract_assets`
- `GET /v1/text_versions/{text_ver_id}/asset_selection_trace/latest`

### 引擎闭环（`engine`）
- `POST /v1/engine/closed_loop/run`

### SSE 事件流（`events`）
- `GET /v1/events`

### foreshadow（`foreshadow`）
- `POST /v1/foreshadow/{foreshadow_id}/event`

### growth（`growth`）
- `POST /v1/growth/milestones/{milestone_id}/event`

### 系统健康（`health`）
- `GET /v1/health`

### 导入管线（`ingest`）
- `POST /v1/ingest/structure_templates`

### 账本写回（`ledger`）
- `POST /v1/ledger/promote_selected`

### 章节体检（`preflight`）
- `POST /v1/preflight/run`

### 提示词模板（`prompt_templates`）
- `POST /v1/prompt_templates/{template_id}/policy`

### ref_inbox（`ref_inbox`）
- `POST /v1/ref_inbox/{ref_id}/status`

### 报告与评估（`reports`）
- `POST /v1/reports/chapter_revision`
