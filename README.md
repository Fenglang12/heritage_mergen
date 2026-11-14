# 时空匠影 · 非遗研学工作站




---

## 项目简介

国风非遗研学平台，主要能力：

- **星火 Agent**：多步工具对话（识图 / 图谱 / 地图 / 焕新 / 百科检索）
- **知识图谱**：Text2SQL + Three.js 3D 可视化
- **非遗识图溯源**：图片 / 视频，地标数量可配置
- **数字焕新**：智谱 GLM-4.1V-Thinking-Flash + CogView-3-Flash（免费）
- **地图路线**：浏览器定位、POI 标点简介、全程规划
- **闯关答题**、**研学报告**、**社区打卡**与管理后台

---

## 仓库结构

```
heritage_mergen/
├── backend_clean/          # Flask 后端（详见 backend_clean/README.md）
│   ├── chroma_db/          # 预构建 Chroma 向量库（约 51MB，已纳入 Git）
│   ├── clean_nodes.json    # 清洗后图谱节点
│   ├── clean_edges.json    # 清洗后图谱边
│   └── features/           # Agent / 图谱 / 焕新 / 答题 / 报告 / 社区
├── vue-ep-frontend/        # Vue 3 前端（详见 vue-ep-frontend/README.md）
├── scripts/                # 辅助脚本
└── .cursor/rules/          # 开发约定（登录页保护等）
```

---

## 快速开始

### 1. 克隆仓库

```bash
git clone <你的仓库地址>
cd heritage_mergen
```

克隆后 **已包含** `backend_clean/chroma_db/`，一般**无需**再执行 `build_rag_db.py`（除非你要重建向量库）。

### 2. 后端

```bash
cd backend_clean
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env：MySQL、讯飞 Spark、智谱、高德等（见下方环境变量）
python app.py
# http://localhost:5000
```

**MySQL 图谱数据（首次）：**

```bash
python scripts/import_to_mysql.py
```

### 3. 前端

```bash
cd vue-ep-frontend
npm install
npm run dev
# http://localhost:5173  （/api 代理到 5000）
```

### 4. 默认管理员

首次启动若无 `admin` 用户会自动创建，请登录后立即修改密码。

---

## 环境变量要点

| 变量 | 用途 |
|------|------|
| `DB_*` | MySQL |
| `SPARK_*` | 讯飞星火（Agent / 图谱 Text2SQL / 出题 / 报告 / 地图标点简介默认通道） |
| `ZHIPU_API_KEY` | 非遗焕新 / 视频识图：GLM-4.1V-Thinking-Flash + CogView-3-Flash（当前免费） |
| `AMAP_API_KEY` | 地图定位、POI、路线 |
| `MARKER_INTRO_PROVIDER` | 地图标点弹窗简介：`spark`（默认）或 `qwen`（需 `DASHSCOPE_API_KEY`） |
| `SOURCE_TRACE_MAX_MARKERS` | 识图 / 视频溯源合并地标上限（默认 `10`） |
| `VIDEO_*` | 视频识图通道（当前默认智谱 `glm-4.1v-thinking-flash`；留空回落到百炼） |
| `DASHSCOPE_*` | 百炼备用通道；标点简介走 `qwen` 时必填 |
| `DEMO_MODE=true` | 答辩演示：焕新 / 识图 / Agent 走预置数据 |

完整说明见 [`backend_clean/.env.example`](backend_clean/.env.example)。

---

## 近期功能摘要

| 模块 | 说明 |
|------|------|
| 登录页 | 青金深色双栏 UI（`/login`）；逻辑 `useAuthForm.js` |
| 对话会话 | 新建默认为「新对话」；首条用户消息自动取前 8 字为标题；支持 `PATCH /api/session/<id>` 重命名 |
| 地图标点 | 弹窗 `ai_intro` 由星火批量生成（可改 `MARKER_INTRO_PROVIDER=qwen`）；对话 `mapStore` 可联动高亮 |
| 识图溯源 | 多条目 POI 去重后最多返回 `SOURCE_TRACE_MAX_MARKERS` 个地标 |
| Agent 推荐 | 按意图推荐 `/map` `/graph` `/quiz` 等；`infer` + `enforce` + 前端 `suggestLinks` |
| 研学报告 | `content_json` LONGTEXT；入库剥离创作集大图、读出 hydrate |
| 知识图谱 | 彩色球体 3D 力导向布局；搜索下拉选节点后相机飞向目标并高亮 |

---

## 提交到 GitHub 说明

### 应提交

| 路径 | 说明 |
|------|------|
| `backend_clean/` 源码与 `chroma_db/` | 向量库约 51MB |
| `clean_nodes.json` `clean_edges.json` | 图谱清洗数据 |
| `backend_clean/.env.example` | 环境变量模板 |
| `vue-ep-frontend/src/` 等源码 | 不含 `node_modules/`、`dist/` |

### 禁止提交

| 路径 | 原因 |
|------|------|
| `backend_clean/.env` | 含 API Key |
| `vue-ep-frontend/node_modules/` | 可 `npm install` 恢复 |
| `.venv/` `.idea/` | 本地环境 |

> GitHub 单文件上限 100MB；`chroma.sqlite3` 约 30MB，可正常推送。超大向量库可考虑 [Git LFS](https://git-lfs.github.com/)。

---

## 详细文档

- [后端 API / Agent / 焕新 / 图谱](backend_clean/README.md)
- [前端页面 / SSE / 路由](vue-ep-frontend/README.md)
- [答辩 Word 文档（doc 目录三份 .docx）](backend_clean/doc/README.md)

---

## 许可证与声明

本项目为竞赛决赛作品。第三方 API（讯飞、智谱、高德、百炼等）须自行申请密钥。
