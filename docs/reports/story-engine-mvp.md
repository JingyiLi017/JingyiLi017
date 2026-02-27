# AI 写作引擎增强（Story Engine MVP）

## 一、已落地接口（按作业顺序）

1. `GET /v1/books/{book_id}/engine/dashboard`  
   查看全局覆盖率：章包覆盖、体检覆盖、待审提案、过期伏笔。

2. `GET /v1/books/{book_id}/story_bible`  
   拉取 Story Bible 快照（人物/时间线/设定/成长里程碑/伏笔/提案）。

3. `POST /v1/books/{book_id}/story_bible/proposals`  
   提交“新设定/新人物/时间线/成长/伏笔”提案（先提案再写入事实层）。

4. `POST /v1/books/{book_id}/story_bible/proposals/{proposal_id}/review`  
   审核提案（`approved/rejected`，可 `auto_apply=true` 自动写入事实层）。

5. `POST /v1/books/{book_id}/engine/chapter_pack`  
   生成章节包（冲突卡 + 场景卡 + 输入证据包 + 强制检查清单）。

6. `POST /v1/books/{book_id}/engine/chapter_audit`  
   章节体检打分（6 维、总分 30、默认阈值 22）。

7. `POST /v1/books/{book_id}/engine/chapter_repair_plan`  
   基于最新/指定体检结果，产出定向修订方案（只改弱项）。

---

## 二、章节包示例（chapter_pack）

请求体关键字段：

- `chapter_id` / `chapter_no`
- `volume_goal`、`arc_goal`、`chapter_goal`
- `conflict_type`（可选，不传会自动避开最近 3 章重复类型）
- `scene_count`（3~8）
- `suspense_type`

输出包含：

- `conflict_card`：目标/阻力/升级/爽点/悬念/代价锚点
- `scene_cards`：每场主功能与预期输出
- `checklist`：推进>=1、兑现>=1、悬念>=1
- `input_package`：最近章节摘要 + Story Bible 证据

---

## 三、体检维度（chapter_audit）

- 因果链（causal_chain）
- 人设一致（character_consistency）
- 设定一致（setting_consistency）
- 节奏兑现（rhythm_payoff）
- 悬念质量（suspense_quality）
- 伏笔管理（foreshadow_management）

低于阈值时会返回 `needs_rework`，并附带 `repair_plan.actions`。

---

## 四、与 300W 字闭环目标对齐

- 分形结构：章节包输出“卷/篇/章目标 + 场景卡”
- 事实层约束：Story Bible 快照 + 提案审核入库
- 冲突驱动：冲突模板自动轮换（避免连续重复）
- 体检回炉：打分 + 定向修复
- 可观测：仪表盘实时显示覆盖率与风险项
