# 时空匠影 · Agent 优化路线图（10 点）

> 来源：2026-11-06 指导老师视角评审（结合现阶段 AI Agent 前沿）。  
> 用途：后续迭代与答辩备稿对照；Cursor 规则会引用本文件。  
> 状态：推进中（完成一项把 `[ ]` 改为 `[x]` 并注明日期）。  
> 成熟度快照：[`11_项目成熟度快照_2026-11-06.md`](11_项目成熟度快照_2026-11-06.md)（备份：`backups/heritage_mergen_snapshot_2026-11-06_1509.zip`）

**一句话目标：** 从「能调工具的非遗平台」升格为「可规划、可引用、可评测、能跨模块闭环」的 Agent。

**优先原则：** P0 做透再堆页面；Demo 只 mock 慢/贵链路，决策与检索尽量真跑。

---

## P0（答辩叙事与 Agent 定义）

### 1. [x] 弱化前置启发式，强化模型选工具（2026-11-06）
- **现状：** ~~`should_hint_*` 抢先调工具~~ → 主路径改为模型决策；启发式仅 `build_soft_prior_hint` 软提示 + 星火降级时 `_run_degraded_tools` 兜底。
- **关键文件：** `features/agent/engine.py`、`parse.py`

### 2. [x] 工具协议升级（Schema / 校验 / 纠错 / Trajectory）（2026-11-06）
- **已做：** `schema.py` 工具目录与参数校验；非法调用注入 `_pending_repair` 自愈一轮；SSE/`logger` 输出 `trajectory` 事件。
- **关键文件：** `schema.py`、`parse.py`、`engine.py`、`tools.py`

### 3. [x] 复合「研学任务」一条端到端轨迹（2026-11-06）
- **已做：** 新工具 `plan_study_tour`（并行地标+百科+图谱 → 结构化行程）；前端可将 markers 推到地图。
- **关键文件：** `tools.py`、`engine.py`、`ChatView.vue`

### 4. [x] 回答强制 Grounding（可引用依据）（2026-11-06）
- **已做：** `append_grounding_block` / `collect_grounding_lines`；最终回答自动附 **依据** 列表。
- **关键文件：** `parse.py`、`engine.py`

---

## P1（深度与可证明性）

### 5. [x] 任务分解 + 多工具协作（含并行）（2026-11-06 · 首版）
- **已做：** `plan_study_tour` 内 `ThreadPoolExecutor` 并行三路检索；外层仍单工具/轮（符合星火文本协议）。
- **后续可增强：** 外层多 tool_call 并行、更细 Planner。

### 6. [x] 会话记忆与目标状态（超越浅画像）（2026-11-06）
- **已做：**
  - `features/agent/memory.py`：研学目标 / 主题 / 站点 / 近期问句；行程或地点工具可激活「正在做英歌舞研学」
  - 持久化 `chat_sessions.memory_json`；注入 Agent Prompt；续问自动补主题
  - SSE `session_memory` + 对话页顶部目标条；说「不做了」可结束目标
- **关键文件：** `memory.py`、`session_schema.py`、`engine.py`、`routes.py`、`models.py`、`ChatView.vue`

### 7. [x] 空间 Agent 化（坐标进工具、附近检索、真用路线）（2026-11-06）
- **已做：**
  - 高德 `place/around` 周边检索 + 距离排序（`get_markers_near_lnglat`）
  - 对话请求可传 `lng/lat`；Agent 自动注入 `search_places` / `plan_study_tour` / `plan_route` 起点
  - `plan_study_tour` 按距离排站点并规划到第一站；`plan_route` 统一 `ok` + summary
  - 前端 Chat 带 GPS（优先地图页缓存）；Map 定位写入 `mapStore.lastGps`
  - **相关性收紧（2026-11-06 下午）：** 禁止「非遗|博物馆」OR 凑数；主题行程只保留名称含主题词的站点（防虫鸣馆/麻糍店进英歌舞研学）
  - **噪声再收紧（2026-11-07）：** 无主题词周边也过滤餐饮/虫鸣/玩具等；正向非遗信号优先；拆开检索词避免「博物馆」OR 刷脏
  - **意图门控（2026-11-07）：** 参考高德「意图→召回→过滤」、美团相关性：先判 `open/heritage/browse`；用户显式搜「卤水火锅」走 open 不过滤餐饮；搜「英歌舞」仍挡主题火锅蹭词；噪声词随 query 失效（query 里已有的词不当噪声）
  - **开放意图贯通（2026-11-07）：** `_OFF_GOAL` 与地图 open 词表对齐；`extract_open_place_keyword` 抽具体品类；跑题注入不再 `len>6` 覆盖；`plan_study_tour` 复用 `_poi_is_noise_for_theme`
- **关键文件：** `shared/utils.py`、`tools.py`、`engine.py`、`routes.py`、`ChatView.vue`、`mapStore.js`、`MapView.vue`

### 8. [x] 评测集与成功率表（2026-11-06 · 扩到 24 条 + 离线成功率表）
- **已做：**
  - `tests/eval_agent_cases.json`（24 条：百科/地点/图谱/行程/焕新/美食跑题/记忆暂停与结束/Schema）
  - `scripts/eval_agent_offline.py`：离线跑分，门禁 ≥20 条且成功率 ≥85%；报告 `tests/eval_agent_report.md`
  - 覆盖近期修复：美食 `diverge/pause`、Grounded POI 列表、结束目标「不做…了」
- **本轮实测：** 24/24（100%），离线不调星火/外网。
- **后续：** 接真链路（星火+高德）跑成功率表；扩到 30～50 条。

---

## P2（加分与工程）

### 9. [x] Demo 与真实能力边界清晰（2026-11-06 · 收紧）
- **已做：** Agent 主循环不再一上来用 Demo 短接决策；仅在星火降级时用预置文案润色**已执行工具**结果。慢/贵链路仍可走 demo 工具层。
- **关键文件：** `features/agent/engine.py`、`features/demo/`

### 10. [x] 交付冒烟与稳定性门禁（2026-11-06 · 起步）
- **已做：** `scripts/smoke_agent_offline.py`（Schema/解析/软提示/Grounding/评测用例≥20）；可串联 `eval_agent_offline.py`。
- **后续：** 登录→地图→对话一问的端到端脚本；前端 build 门禁。

---

## 答辩追问备稿（对应上述点）

1. 去掉抢跑 hint 后谁选工具？→ 模型主路径；软提示 prior；降级才启发式。  
2. 「帮我安排半天非遗」？→ `plan_study_tour` 输出行程站点，并可落到地图。  
3. 依据从哪来？→ 文末 **依据** 块对应百科/图谱/地标工具结果。

---

## 刻意不做（避免名词堆砌）

- 为炫技再堆无关页面  
- 未做透 P0 就上完整 Multi-Agent / MCP 名词包装  
- 用 Demo 预置回复冒充 Agent 决策能力  
