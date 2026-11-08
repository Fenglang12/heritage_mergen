# 时空匠影 · 后端服务（`backend_clean`）

> Flask 纯 API —— 讯飞星火、图谱 Text2SQL、轻量 Agent、社区与研学报告  
> 深圳理工大学 AI Agent 大赛 · 非遗研学工作站

---

## 目录

- [技术架构](#技术架构)
- [目录结构（按功能归类）](#目录结构按功能归类)
- [快速启动](#快速启动)
- [环境变量](#环境变量)
- [MySQL 数据表](#mysql-数据表)
- [API 接口一览](#api-接口一览)
- [Agent 与 SSE 协议](#agent-与-sse-协议)
- [非遗焕新（双模型）](#非遗焕新双模型)
- [演示模式与缓存](#演示模式与缓存)
- [单元测试](#单元测试)
- [注意事项](#注意事项)

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────────┐
│  app.py — 注册蓝图、db.create_all()、user_artworks / study_reports 升级 │
├─────────────────────────────────────────────────────────────────┤
│  api/routes.py          认证 / 地图 / Agent / 识图 / 焕新 / 图谱   │
│  features/*/routes.py   答题 / 报告 / 社区（独立 Blueprint）       │
├─────────────────────────────────────────────────────────────────┤
│  features/agent         Prompt + tool_call 多步 Agent             │
│  shared/utils.py        讯飞 IAT/TTS/Spark、智谱、RAG、高德        │
│  features/graph         图谱 Text2SQL                             │
│  features/revive        焕新作品入库（研学报告创作集）              │
│  features/demo          DEMO_MODE、识图结果缓存                    │
├─────────────────────────────────────────────────────────────────┤
│  MySQL 8（业务 + graph_*）    ChromaDB（向量百科，可选）            │
└─────────────────────────────────────────────────────────────────┘
```

**请求链路（对话）：** 前端 Cookie → `@auth_required` → `HeritageAgent` → `features/agent/tools` → SSE 流式返回 → 写入 `chat_histories`。

---

## 目录结构（按功能归类）

```
backend_clean/
├── app.py                      # 应用入口
├── requirements.txt
├── .env / .env.example
│
├── core/                       # 基础设施
│   ├── config.py               # 环境变量（含 DEMO_MODE）
│   ├── exts.py                 # SQLAlchemy
│   ├── models.py               # ORM（含 UserArtwork，image_data 为 LONGTEXT）
│   └── auth_utils.py           # 鉴权装饰器
│
├── api/                        # 主 API 蓝图
│   └── routes.py               # 认证、地图、/chat、识图、焕新、图谱、TTS、/asr
│
├── features/
│   ├── agent/                  # 星火向导 Agent
│   │   ├── engine.py           # 多步循环、演示模式降级、用户画像
│   │   ├── tools.py            # search_heritage / query_graph / revive_heritage 等
│   │   ├── parse.py            # tool_call、推荐链接 normalize / infer / enforce
│   │   └── profile.py          # 打卡/答题/对话 → 用户画像
│   ├── graph/
│   │   ├── rag.py              # MySQLGraphRAG（Text2SQL）
│   │   └── nodes.py            # 图谱节点 ID 提取
│   ├── map/
│   │   └── direction.py        # 高德路线
│   ├── revive/
│   │   └── artwork.py          # user_artworks 入库、LONGTEXT 自动升级、入库压缩
│   ├── demo/
│   │   ├── service.py          # 预置识图/焕新/对话、识图缓存
│   │   └── data/demo_data.json
│   ├── quiz/                   # routes.py + service.py
│   ├── report/                 # 报告聚合；content_json LONGTEXT；入库 strip / 读出 hydrate
│   └── community/              # 打卡、反馈、管理员
│
├── shared/
│   └── utils.py                # 讯飞 / 智谱 / RAG、标点简介、识图地标聚合等
│
├── scripts/
│   ├── build_rag_db.py
│   ├── import_to_mysql.py
│   ├── data_cleaner.py
│   └── migrate_user_artworks_longtext.sql   # 手动升级 image_data 列（可选）
│
├── tests/                      # parse、graph nodes、agent 推荐路径等
├── doc/                        # 答辩文档（Markdown 为主，见 doc/README.md）
├── chroma_db/                  # 预构建向量库（约 51MB，已纳入 Git，克隆即用）
└── clean_nodes.json / clean_edges.json
```

> **向量库：** `chroma_db/` 随仓库推送，克隆后 Agent 百科检索（`search_heritage`）可直接使用。仅在你修改了图谱文本或嵌入模型时才需重新执行 `python scripts/build_rag_db.py`。

### 功能与代码目录对照

| 功能 | 主要代码位置 | 关键 API |
|------|----------------|----------|
| 登录注册 | `core` + `api/routes.py` | `POST /api/login` `register` |
| 语音转写 | `shared/utils` + `api/routes.py` | `POST /api/asr` |
| 星火 Agent | `features/agent` | `POST /api/chat`（SSE）；推荐路径 `infer` / `enforce` |
| 非遗识图 | `api/routes.py` + `shared/utils` | `POST /api/analyze_source` |
| 数字焕新 | `api/routes.py` + `shared/utils` + `features/revive` | `POST /api/generate_art` `generate_art/stream` |
| 知识图谱 | `features/graph` + `api/routes.py` | `GET /api/graph_data` `POST /api/graph/query` |
| 地图路线 | `features/map` + `api/routes.py` + `shared/utils` | `/api/default_local` `direction` `route_plan`；标点 `ai_intro` 批量生成 |
| 对话会话 | `api/routes.py` | 标题自动命名 + `PATCH /api/session/<id>` |
| 识图上限 | `shared/utils.collect_markers_for_entries` | 合并地标 ≤ `SOURCE_TRACE_MAX_MARKERS` |
| 闯关答题 | `features/quiz` | `/api/quiz/*` |
| 研学报告 | `features/report` + `features/revive/artwork` | `/api/report/*`；`content_json` LONGTEXT |
| 社区管理 | `features/community` | `/api/checkin/*` `/api/admin/*` |
| 演示降级 | `features/demo` + `core.config` | `DEMO_MODE=true` |

---

## 快速启动

```bash
cd backend_clean
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env：MySQL、讯飞 Spark、智谱 ZHIPU_*、高德 AMAP_API_KEY
python app.py
# http://localhost:5000
```

代码规范检查（开发可选）：

```bash
cd backend_clean
pip install -r requirements-dev.txt
ruff check .
```

**数据准备（首次）：**

```bash
python scripts/import_to_mysql.py
python scripts/build_rag_db.py   # 仅重建向量库时需要（仓库已含 chroma_db/）
```

**开发热重载：**

```bash
set FLASK_DEBUG=true
python app.py
```

前端开发服务器默认将 `/api` 代理到 `localhost:5000`（见 `vue-ep-frontend/README.md`）。

---

## 环境变量

见 `.env.example`。复制为 `.env` 后填入真实密钥（勿提交 Git）。

| 变量组 | 用途 |
|--------|------|
| `SECRET_KEY` | Flask Session |
| `DB_*` | MySQL（默认库名 `heritage_db`） |
| `SPARK_*` | 讯飞星火对话 / Text2SQL / 出题 / 报告 |
| `XFYUN_*` | 语音识别 IAT、语音合成 TTS（若已配置） |
| `ZHIPU_API_KEY` | **焕新/视频识图必填**：GLM-4.1V-Thinking-Flash 识图 + CogView-3-Flash 生图（当前免费） |
| `ZHIPU_IMAGE_MODEL` | 推荐 `cogview-3-flash`（免费） |
| `ZHIPU_VISION_MODEL` | 推荐 `glm-4.1v-thinking-flash`（免费，支持图片/视频） |
| `AMAP_API_KEY` | IP 定位、POI、路线 |
| `VIDEO_BASE_URL` | 视频识图通道地址（当前 `https://open.bigmodel.cn/api/paas/v4`；留空回落到百炼） |
| `VIDEO_API_KEY` | 视频识图通道密钥（当前复用智谱 Key；留空回落到 `DASHSCOPE_API_KEY`） |
| `VIDEO_MODEL` | 视频理解模型，当前默认 `glm-4.1v-thinking-flash` |
| `DASHSCOPE_API_KEY` | 百炼备用视频通道；`MARKER_INTRO_PROVIDER=qwen` 时用于地图标点简介 |
| `DASHSCOPE_BASE_URL` | 百炼兼容接口，默认 `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `QWEN_INTRO_MODEL` | 标点简介用 Qwen 模型，默认 `qwen3-max` |
| `MARKER_INTRO_PROVIDER` | `spark`（默认，复用 `SPARK_*`）或 `qwen` |
| `SOURCE_TRACE_MAX_MARKERS` | 识图 / 视频溯源返回地标数上限，默认 `10` |
| `DEMO_MODE` | `true` / `1` / `yes`：焕新、识图、Agent 对话走预置数据 |
| `FLASK_DEBUG` | 开发模式；`true` 时可用查询参数 `client_ip` 联调定位 |

---

## 对话会话与标题

| 行为 | 说明 |
|------|------|
| 新建会话 | `POST /api/session/create` → 默认标题 **「新对话」** |
| 自动命名 | 用户在该会话发送**第一条**文字消息后，若标题仍为占位符，取消息**前 8 个字**写入 `chat_sessions.title` |
| 手动重命名 | `PATCH /api/session/<sid>`，body：`{ "title": "自定义标题" }`（最长 100 字） |
| 占位标题集合 | `新对话`、`新的对话`、`关于非遗的新探索`（旧数据兼容，仍会触发自动命名） |

语音首条消息使用 ASR 转写后的文本参与截断；纯图片消息为 `[发送了一张图片]` 时保持「新对话」。

---

## 地图标点简介（`ai_intro`）

`GET /api/default_local`、识图合并地标、`Agent search_places` 等会为每个 marker 写入 `ai_intro` 字段，供前端地图弹窗展示。

| 项目 | 说明 |
|------|------|
| 实现 | `shared/utils.apply_marker_intros()`，默认 **一次批量** 调用讯飞星火 |
| 配置 | `MARKER_INTRO_PROVIDER=spark`（默认）或 `qwen`（需有效 `DASHSCOPE_API_KEY`） |
| 失败兜底 | 仅显示 `【名称】，地址` 简短文案 |

---

## 识图溯源地标数量

`POST /api/analyze_source` / `analyze_source_video` 按星火识别的多条「非遗条目」分别查高德 POI，按 `id` 去重后**最多保留** `SOURCE_TRACE_MAX_MARKERS` 条（默认 10，可在 `.env` 调整）。

---

## MySQL 数据表

`db.create_all()` 在启动时自动建表。**不会修改已有表的列类型**，仅创建缺失表。

### `user_artworks`（焕新作品 · 研学报告创作集）

| 列 | 类型 | 说明 |
|----|------|------|
| `id` | INT PK | 自增 |
| `user_id` | INT FK | 用户 |
| `prompt` | VARCHAR(500) | 创意描述 |
| `image_data` | **LONGTEXT** | base64 data URL（入库前会压缩为 JPEG 预览图） |
| `analysis` | LONGTEXT | 视觉模型分析摘要 |
| `source` | VARCHAR(20) | `revive` / `agent` |
| `created_at` | DATETIME | 创建时间 |

**重要：** 若表是早期自动创建的 `TEXT` 类型（约 64KB 上限），生图成功但入库会报 `Data too long for column 'image_data'`。

**处理方式（二选一）：**

1. **推荐**：重启 `python app.py`，启动时会执行 `ensure_user_artworks_schema()` 自动 `ALTER` 为 LONGTEXT。  
2. **手动**：执行 `scripts/migrate_user_artworks_longtext.sql`。

### `study_reports`（研学报告）

| 列 | 类型 | 说明 |
|----|------|------|
| `content_json` | **LONGTEXT** | 结构化报告 JSON |

**启动时** `ensure_study_reports_schema()` 会将早期 `TEXT` 列自动 `ALTER` 为 LONGTEXT。

**入库策略：** 流式生成完整 JSON 先 SSE 推前端；写入 DB 前 `strip_report_for_storage()` 剥离创作集 base64，仅保留作品 `id` 等元数据。读取 `GET /api/report/latest` 时 `hydrate_report_artworks()` 从 `user_artworks` 回填图片。

### 其它业务表

`users`、`chat_sessions`、`chat_histories`、`checkins`、`quiz_scores`、`feedbacks` 等 —— 见 `core/models.py`。

---

## API 接口一览

前缀均为 `/api`。除注明外需登录（`@auth_required`）。

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/register` | 注册 |
| POST | `/login` | 登录，写 Session |
| GET | `/logout` | 登出 |

### 语音

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/asr` | 独立语音转文字（讯飞 IAT；返回 JSON 安全解析 `header.status`） |
| GET/POST | `/stream_voice` | TTS，返回 PCM |

### 对话 Agent（SSE）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/chat` | Agent 多步工具 + 流式回答 |

请求体：`message`、`session_id`；可选 `audio`（Base64 WAV）、`image`（Base64，触发识图工具）。

### 会话

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/sessions` | 会话列表（含 `title`、`time`） |
| POST | `/session/create` | 新建会话，默认标题「新对话」 |
| PATCH | `/session/<sid>` | 修改会话标题 `{ "title": "..." }` |
| GET | `/history/<sid>` | 历史消息 |
| POST | `/clear` | 删除会话（body：`session_id`） |

### 识图与焕新

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/analyze_source` | 图片识图；可选 `voice_hint`；`markers` 最多 `SOURCE_TRACE_MAX_MARKERS` 条 |
| POST | `/analyze_source_video` | 视频识图（默认智谱 GLM-4.1V-Thinking-Flash，可切百炼）；地标数量同上 |
| POST | `/generate_art` | 异步生图，返回 `task_id` |
| POST | `/generate_art/stream` | **SSE** 推送视觉识别 → 图像生成阶段进度 |
| GET | `/query_art/<task_id>` | 轮询异步生图结果 |

### 图谱与地图

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/graph_data` | 全量图谱节点与边 |
| POST | `/graph/query` | 图谱问答 + `related_nodes` |
| GET | `/default_local` | IP 定位 + 同城非遗 POI |
| GET | `/get_location` | IP → 城市/经纬度 |
| POST | `/direction` | 单段路线 |
| POST | `/route_plan` | 多站游览路线 |

### 答题 / 报告 / 社区

见 `features/quiz/routes.py`、`features/report/routes.py`、`features/community/routes.py`。

| 模块 | 前缀示例 |
|------|----------|
| 答题 | `/quiz/generate` `/quiz/generate/stream` `/quiz/submit` |
| 报告 | `/report/latest` `/report/generate/stream` |
| 社区 | `/checkin/*` `/feedback/*` `/admin/*` |

---

## Agent 与 SSE 协议

### 设计原则

- 不引入 LangGraph / CrewAI；Prompt + `<tool_call>` JSON 驱动工具
- 工具实现在 `features/agent/tools.py`，复用 `shared/utils` 等既有能力
- 图谱类问题可自动预调 `query_graph`（关键词启发）
- 文末推荐链接：`infer_suggest_path` + `enforce_suggest_path`（`features/agent/parse.py`）

### 可用工具

| 工具名 | 说明 |
|--------|------|
| `search_heritage` | Chroma 向量百科 |
| `query_graph` | 图谱 Text2SQL，返回 `node_ids` |
| `search_places` | 高德 POI |
| `plan_route` | 路线规划 |
| `identify_image` | 图片识图（请求带 `image` 时） |
| `revive_heritage` | GLM-4.1V-Thinking-Flash + CogView-3-Flash 焕新（对话内出图） |

### `POST /api/chat` SSE 事件

每行：`data: {JSON}\n\n`

| type | 说明 |
|------|------|
| `asr` | 语音转写 `{ "text" }` |
| `thinking` | 分析中 |
| `tool_call` | `{ "tool", "label", "args" }` |
| `tool_result` | `{ "tool", "summary" }` |
| `revive_progress` | 焕新阶段 `{ "stage", "text" }` |
| `art_image` | 焕新完成 `{ "url", "prompt" }` |
| `text` | 回答片段 `{ "text" }` |
| `error` | 错误 |
| `done` | 结束 |

回答末尾 Agent 会按 Prompt 输出主动推荐，格式必须为 Markdown 链接：

```text
👉 想挑战英歌舞知识吗？[开始答题](/quiz)
```

可用路径：`/map`、`/source`、`/graph`、`/quiz`、`/revive`、`/report`、`/community`。

| 用户意图（示例） | 推荐路径 |
|------------------|----------|
| 在哪里、怎么去、附近、地址 | `/map` |
| 识图、认图、上传图 | `/source` |
| 传承人、关系、分布（非导航） | `/graph` |
| 出题、考我、闯关 | `/quiz` |
| 焕新、重绘 | `/revive` |
| 研学报告 | `/report` |
| 打卡广场 | `/community` |

**前后端修正：** 畸形链接 `[/quiz]` → `normalize_agent_suggest_links`；若模型推荐路径与意图不符 → `enforce_suggest_path`（`engine.py` 与 `api/routes.py` 入库前）。前端 `suggestLinks.js` 同步规范化。

---

## 非遗焕新（双模型）

```
用户上传参考图 + Prompt
        │
   ┌────┴────┐
   │ 有参考图？│
   └────┬────┘
    YES │     NO
        ▼     ▼
   GLM-4.1V-Thinking-Flash 分析 ──→ CogView-3-Flash 文生图
        │
        ▼
   外链转 data URL（normalize_art_result_url）
        │
        ▼
   可选写入 user_artworks（供研学报告创作集）
```

实现入口：`shared/utils.py` 的 `iter_zhipu_art_generation()`；路由在 `api/routes.py`。图像模型请求体含 `watermark_enabled: false`（需在智谱开放平台签署去水印免责声明）。

### 焕新 SSE（`/api/generate_art/stream`）

| type | 说明 |
|------|------|
| `progress` | `{ "stage", "text" }` — 如 glm_start / glm_done / cogview_start / done |
| `done` | `{ "url", "analysis" }` |
| `error` | `{ "msg" }` |

入库失败**不会**中断 SSE（已捕获异常，图片仍返回前端）。

---

## 演示模式与缓存

| 机制 | 说明 |
|------|------|
| `DEMO_MODE=true` | 不调智谱/识图 API，使用 `features/demo/data/demo_data.json` 预置结果 |
| 焕新 `_art_cache` | 相同 prompt+图 hash 命中内存缓存，加速二次演示 |
| 识图 `_source_cache` | 相同图片 hash 直接返回上次识图结果 |

---

## 单元测试与代码规范

单元测试不依赖讯飞/智谱外网：

```bash
cd backend_clean
python -m unittest discover -s tests -t . -v
```

代码规范检查（ruff，配置见 `backend_clean/pyproject.toml`）：

```bash
cd backend_clean
pip install -r requirements-dev.txt
ruff check .
```

覆盖：`features/agent/parse.py`（含 `normalize_agent_suggest_links`、`infer_suggest_path`、`enforce_suggest_path`）、`features/graph/nodes.py`、`tests/test_agent_engine.py`（推荐路径场景）。

---

## 智谱 API 常见问题

焕新或视觉模型报 **「IP 地址没有接口访问权限」** 时，请在 [智谱开放平台](https://open.bigmodel.cn/) 检查 API Key 的 **IP 白名单**，或关闭 IP 限制 / 更换网络。答辩现场可设 `DEMO_MODE=true` 使用预置焕新图。

---

## 注意事项

1. 所有 Python 命令请在 **`backend_clean` 根目录**执行。
2. 管理员默认账号：首次启动若无 `admin` 会自动创建（见 `app.py`），请及时改密。
3. 生图异步任务：`image_tasks` 内存字典，TTL 10 分钟。
4. 生产部署：Nginx 对 `/api/chat`、`/generate_art/stream` 等须 `proxy_buffering off`。
5. 前端登录页为青金深色 `LoginView.vue`，约定不随 Agent 批量改 UI（见 `.cursor/rules/protect-login-ui.mdc`）。
6. 答辩 Word 文档见 **`doc/`** 下三份 `.docx`（由 `doc/build_docx.py` 生成，见 `doc/README.md`）。

更完整的仓库级说明可参考根目录 `README.md`。
