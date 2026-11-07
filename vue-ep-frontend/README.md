# 时空匠影 · 前端应用

> Vue 3 + Vite + Element Plus —— 国风暗黑主题的非遗文化数字研学工作站前端

---

## 目录

- [技术架构](#技术架构)
- [目录结构（按功能归类）](#目录结构按功能归类)
- [技术栈](#技术栈)
- [快速启动](#快速启动)
- [环境配置与代理](#环境配置与代理)
- [API 与 SSE](#api-与-sse)
- [页面功能说明](#页面功能说明)
- [路由设计](#路由设计)
- [开发规范](#开发规范)
- [与后端对应关系](#与后端对应关系)

---

## 技术架构

```
┌────────────────────────────────────────────────────────────┐
│  main.js → App.vue → core/router → LayoutView + 功能页      │
├────────────────────────────────────────────────────────────┤
│  api/index.js        Axios REST + fetch SSE / TTS           │
│  features/*/views    各业务页面（按功能分目录）                 │
│  features/shared     VoiceInputBar、useVoiceInput             │
│  Pinia               features/auth/auth.js                  │
├────────────────────────────────────────────────────────────┤
│  Vite 代理 /api → localhost:5000    高德地图 JS API          │
└────────────────────────────────────────────────────────────┘
```

---

## 目录结构（按功能归类）

```
vue-ep-frontend/
├── index.html
├── vite.config.js              # @ → src、/api 代理
├── package.json
└── src/
    ├── main.js
    ├── App.vue
    ├── assets/
    │   ├── global.css          # 主题变量 + Element Plus 深色覆盖
    │   └── page-common.css     # 页面通用布局
    │
    ├── core/                   # 应用骨架（非业务功能）
    │   ├── router/index.js     # 路由守卫、懒加载
    │   └── views/LayoutView.vue
    │
    ├── api/
    │   └── index.js            # 全部后端接口（按功能分块注释）
    │
    ├── public/
    │   ├── favicon.ico
    │   └── favicon.svg
    └── features/
        ├── auth/
        │   ├── views/LoginView.vue         # 青金深色登录（左品牌右表单）
        │   ├── composables/useAuthForm.js  # 登录/注册逻辑
        │   └── auth.js                     # Pinia：isLoggedIn / isAdmin
        ├── map/
        │   ├── views/MapView.vue
        │   ├── stores/mapStore.js     # 识图结果 → 地图高亮
        │   └── utils/clientIp.js      # 公网 IP → X-Client-Public-IP
        ├── source/
        │   └── views/SourceView.vue   # 识图 + 语音补充描述
        ├── revive/
        │   └── views/ReviveView.vue   # 焕新 SSE 进度 + 双阶段动画
        ├── chat/
        │   ├── views/ChatView.vue     # Agent、会话标题、图片/语音、推荐链接跳转
        │   ├── stores/mapStore.js     # 识图/对话地标 → 地图页高亮
        │   └── utils/
        │       ├── chatStream.js      # /api/chat SSE 解析
        │       └── suggestLinks.js    # 推荐链接规范化 + router.push
        ├── graph/
        │   └── views/GraphView.vue    # Three.js 力导向 3D、搜索定位、相机聚焦
        ├── quiz/
        │   ├── views/QuizView.vue     # SSE 出题、连击、朗读题目
        │   └── utils/quizStream.js
        ├── report/
        │   └── views/ReportView.vue   # 报告 SSE + 数字创作集图集
        ├── community/
        │   └── views/CommunityView.vue
        ├── feedback/
        │   └── views/FeedbackView.vue
        ├── admin/
        │   └── views/Admin*.vue
        └── shared/
            ├── components/VoiceInputBar.vue
            └── composables/useVoiceInput.js   # → POST /api/asr
```

### 路径别名

`vite.config.js` 中 `@` 指向 `src/`。跨功能引用示例：

```javascript
import { streamChat } from '@/api'
import { useAuthStore } from '@/features/auth/auth'
import VoiceInputBar from '@/features/shared/components/VoiceInputBar.vue'
```

---

## 技术栈

| 类别 | 技术 |
|------|------|
| 框架 | Vue 3（Composition API + `<script setup>`） |
| 构建 | Vite 5 |
| UI | Element Plus（深色主题覆盖见 `assets/global.css`） |
| 状态 | Pinia（`features/auth/auth.js`） |
| 路由 | Vue Router 4（History + 懒加载） |
| HTTP | Axios（REST）+ fetch（SSE、TTS PCM） |
| 3D 图谱 | Three.js |
| 地图 | 高德地图 JS API v2.0 |

---

## 快速启动

### 前置条件

- Node.js 18+
- 后端已在 `http://localhost:5000` 运行（见 `backend_clean/README.md`）

### 安装与开发

```bash
cd vue-ep-frontend
npm install
npm run dev
# http://localhost:5173
```

### 生产构建

```bash
npm run build
# 产物：dist/
```

---

## 环境配置与代理

`vite.config.js` 已将 `/api` 代理到 `http://localhost:5000`，并转发 `changeOrigin`。

后端需配置 CORS 允许请求头 `X-Client-Public-IP`（地图 IP 定位用）。本地开发时由 `features/map/utils/clientIp.js` 获取公网 IP 并写入该头。

**焕新相关：** 前端默认调用 `POST /api/generate_art/stream`（SSE），无需轮询即可看到 GLM-4V / CogView-4 阶段提示。需保证后端 `.env` 中 `ZHIPU_API_KEY` 有效；现场答辩可设后端 `DEMO_MODE=true`。

---

## API 与 SSE

统一封装在 `src/api/index.js`。

### REST 分组

| 分块 | 主要方法 |
|------|----------|
| 认证 | `login` `register` `logout` |
| 地图 | `getDefaultLocal` `getIpLocation` |
| 识图 | `analyzeSource`（支持 `voice_hint`）`analyzeSourceVideo` |
| 焕新 | `generateArt` `generateArtStream` `queryArtTask` |
| 会话 | `getSessions` `createSession` `updateSessionTitle` `getSessionHistory` `clearSession` |
| Agent | `streamChat` `streamChatAudio` `streamChatImage` |
| TTS | `fetchTtsPcm` |
| 语音 | `transcribeAudio` → `/api/asr` |
| 图谱 | `queryGraph` `getGraphData` |
| 答题 | `streamGenerateQuiz` `submitQuiz` `getLeaderboard` |
| 报告 | `getLatestReport` `generateReportStream` |
| 社区/管理 | `submitCheckin`、`admin*` 等 |

### SSE 解析

| 场景 | 工具 | 消费页面 |
|------|------|----------|
| Agent 对话 | `features/chat/utils/chatStream.js` | `ChatView.vue` |
| 焕新生图 | 同上 `readChatStream` | `ReviveView.vue` |
| 答题出题 | `features/quiz/utils/quizStream.js` | `QuizView.vue` |
| 研学报告 | `readChatStream` | `ReportView.vue` |

### Agent 对话事件 → UI（`ChatView.vue`）

| type | UI 行为 |
|------|---------|
| `thinking` | 「正在分析…」 |
| `tool_call` / `tool_result` | 工具步骤条 |
| `revive_progress` | 焕新阶段文案更新 |
| `art_image` | 气泡内展示焕新图 |
| `text` | 流式回答 |
| `asr` | 更新用户语音气泡文字 |
| `error` | 错误提示 |
| `done` | 结束并写入历史 |

Agent 回答中的 Markdown 链接（如 `[打开非遗地图](/map)`）经 `suggestLinks.js` 规范化后渲染为可点击 `<a>`（`router.push`）。错误格式 `[/quiz]` 会补全为默认文案。后端 `infer_suggest_path` / `enforce_suggest_path` 会按用户意图纠正推荐路径（地点 → `/map`，关系 → `/graph`，出题 → `/quiz` 等）。

**可跳转站内路径：** `/map`、`/source`、`/graph`、`/quiz`、`/revive`、`/report`、`/community`。

### 会话标题（`ChatView.vue`）

| 行为 | 说明 |
|------|------|
| 新建 | 后端默认「新对话」 |
| 自动 | 首条用户消息后，后端用消息前 8 字更新标题（占位标题时） |
| 手动 | 侧栏双击标题或点编辑图标 → 失焦 / Enter 调用 `updateSessionTitle` |

### 焕新 SSE 事件（`ReviveView.vue`）

| type | UI 行为 |
|------|---------|
| `progress` | 进度文案 + 阶段日志列表 |
| `done` | 展示 `url` 作品图 |
| `error` | `ElMessage` 提示 |

---

## 页面功能说明

| 路由 | 目录 | 要点 |
|------|------|------|
| `/login` | `features/auth` | 青金深色登录/注册（品牌区：数据条、功能卡片、非遗时间轴、跑马灯；表单区：渐变描边 + 「匠」印）；逻辑见 `useAuthForm.js` |
| `/map` | `features/map` | IP 定位非遗 POI、弹窗展示后端 `ai_intro`、路线规划；`mapStore` 消费识图结果 |
| `/source` | `features/source` | 图片/视频识图、`VoiceInputBar` 补充描述 |
| `/revive` | `features/revive` | 参考图 + Prompt；SSE 双阶段（🔍 GLM / 🖌️ CogView） |
| `/chat` | `features/chat` | 多会话与标题编辑、语音、**图片上传**、Agent 焕新工具、推荐链接跳转；`mapStore` 联动地图 |
| `/graph` | `features/graph` | 3D 力导向图谱；`el-autocomplete` 搜索节点并相机聚焦；图谱问答高亮相关节点 |
| `/quiz` | `features/quiz` | SSE 逐题预览、连击徽章、朗读题目 |
| `/report` | `features/report` | 分模块 SSE 报告、**数字创作集**缩略图 |
| `/community` | `features/community` | 打卡广场 |
| `/feedback` | `features/feedback` | 意见反馈 |
| `/admin/*` | `features/admin` | 用户/审核/反馈/热力图 |

---

## 路由设计

```
/login                         LoginView（guest）
/                              LayoutView（auth）
├── /map                       MapView
├── /source                    SourceView
├── /revive                    ReviveView
├── /chat                      ChatView
├── /graph                     GraphView
├── /quiz                      QuizView
├── /report                    ReportView
├── /community                 CommunityView
├── /feedback                  FeedbackView
├── /admin/users|checkins|feedbacks|heatmap
└── /admin → /admin/users
```

守卫：`meta.auth` 需登录；`meta.admin` 需管理员；`meta.guest` 已登录跳转首页。

---

## 开发规范

1. **新功能**放在 `src/features/<功能名>/`，不要新增根级 `views/`、`stores/`。
2. **跨模块**使用 `@/` 别名，避免深层 `../../../`。
3. **LoginView.vue**：正式登录页 UI，**禁止**为 Agent 等功能批量改 template/style（见 `.cursor/rules/protect-login-ui.mdc`）；逻辑可抽至 `useAuthForm.js`。
4. **全局弹窗**优先使用 `heritage-dialog`（定义于 `assets/global.css`，管理端 `heritage-dialog--form`）。
5. **颜色**使用 `assets/global.css` 中的 CSS 变量（含 `el-input__count` 深色、 `el-message-box` 深色）。
6. **弹窗 / teleport** 若页面级覆盖，可用无 scoped 的 `<style>` 块；能走全局类则不要重复写。
7. **REST** 走 `api/index.js`；**SSE** 用 `fetch` + `chatStream` / `quizStream`。

---

## 与后端对应关系

| 主题 | 前端 | 后端 |
|------|------|------|
| 目录结构 | 本文 | `backend_clean/README.md` |
| Agent / SSE | `features/chat` | `features/agent` |
| 焕新双模型 | `features/revive` | `shared/utils.py` + `api/routes.py` |
| 创作集入库 | `features/report` | `features/revive/artwork.py` → `user_artworks` |
| 演示模式 | — | `DEMO_MODE` + `features/demo` |
| 语音 | `features/shared` | `POST /api/asr` |
| 图谱 | `features/graph` | `features/graph/rag.py` + `GET /graph_data` |
| 会话标题 | `ChatView` + `updateSessionTitle` | `PATCH /api/session/<id>`、首条消息自动命名 |
| 推荐链接 | `suggestLinks.js` | `normalize` + `infer_suggest_path` / `enforce_suggest_path` |
| 地图联动 | `features/chat/stores/mapStore.js` | Agent `search_places` 等地标结果 |
| IP 定位 | `features/map/utils/clientIp.js` | `utils.get_client_ip_from_request` |
| 语音 ASR | `useVoiceInput.js` | `POST /api/asr`（录音时长校验、IAT 安全解析） |

---

## 知识图谱页（`GraphView.vue`）

| 能力 | 说明 |
|------|------|
| 渲染 | Three.js：彩色球体按 `label` 着色，边为线段；**100 次**力导向迭代后静态展示（无 emoji 贴图） |
| 搜索 | `el-autocomplete` 匹配节点 `name` / `label`，最多 20 条；选中后相机飞向节点（`FOCUS_RADIUS`）、放大高亮，其余半透明 |
| 取消定位 | 「取消定位」恢复默认相机与全部节点透明度 |
| 问答 | `POST /api/graph/query` 返回 `related_nodes` 时，自动聚焦第一个相关节点 |

---

### 部署提示（Nginx）

```nginx
location /api {
    proxy_pass http://127.0.0.1:5000;
    proxy_buffering off;
    proxy_read_timeout 120s;
}
location / {
    root .../dist;
    try_files $uri $uri/ /index.html;
}
```

---

## 常见问题

**焕新页面一直 loading 后报错？**  
先确认后端 `ZHIPU_API_KEY`；若日志出现 `Data too long for column 'image_data'`，重启后端以升级 `user_artworks` 表为 LONGTEXT（见后端 README）。

**Agent 对话无图但焕新页正常？**  
对话内需带图或描述焕新意图，触发 `revive_heritage` 工具；也可直接去 `/revive`。

**地图定位不准？**  
开发环境依赖 `X-Client-Public-IP`；换网络后可在地图页点刷新重新取 IP。

**地图瓦片 `ERR_CACHE_READ_FAILURE`？**  
多为浏览器对高德 CDN 的磁盘缓存异常（304 响应），可无痕模式或清理站点缓存；与业务接口无关。

**图谱搜索选节点后画面没动？**  
确认节点已在 `graph_data` 中加载；聚焦动画约 0.8s，期间可点「取消定位」复位。

**控制台 favicon 404？**  
确认 `public/favicon.ico` 与 `index.html` 中 `<link rel="icon">` 存在；开发服务器需能访问 `/favicon.ico`。

**焕新页语音报 400？**  
检查录音是否过短；后端 IAT 需有效 `XFYUN_*`；见后端 README「语音」与 `shared/utils` IAT 解析说明。

**答辩/技术文档？**  
见 `backend_clean/doc/`（Markdown 与 Word 备份索引）。
