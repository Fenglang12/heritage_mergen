# -*- coding: utf-8 -*-
"""生成比赛答辩三份 Word 文档"""
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

OUT_DIR = Path(__file__).resolve().parent.parent / "docs"
OUT_DIR.mkdir(exist_ok=True)


def set_doc_style(doc):
    style = doc.styles["Normal"]
    style.font.name = "微软雅黑"
    style._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
    style.font.size = Pt(11)


def h1(doc, text):
    p = doc.add_heading(text, level=0)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return p


def h2(doc, text):
    return doc.add_heading(text, level=1)


def h3(doc, text):
    return doc.add_heading(text, level=2)


def h4(doc, text):
    return doc.add_heading(text, level=3)


def para(doc, text, bold=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = bold
    return p


def bullet(doc, text):
    return doc.add_paragraph(text, style="List Bullet")


def table(doc, headers, rows):
    t = doc.add_table(rows=1 + len(rows), cols=len(headers))
    t.style = "Table Grid"
    for i, h in enumerate(headers):
        t.rows[0].cells[i].text = h
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            t.rows[ri + 1].cells[ci].text = str(val)
    doc.add_paragraph()
    return t


def qa_block(doc, q, a, future=None):
    para(doc, f"问：{q}", bold=True)
    para(doc, f"答：{a}")
    if future:
        para(doc, f"拓展方向：{future}")
    doc.add_paragraph()


# ─────────────────────────────────────────────────────────────
# 文档 1：答辩项目介绍（精炼）
# ─────────────────────────────────────────────────────────────
def build_doc1():
    doc = Document()
    set_doc_style(doc)
    h1(doc, "时空匠影")
    para(doc, "非遗文化数字研学工作站 · AI Agent 赛道答辩材料", bold=True)
    para(doc, "项目名称：时空匠影（Heritage Digital Studio）")
    doc.add_paragraph()

    h2(doc, "一、项目一句话")
    para(doc, "以「多模态 AI Agent + 知识图谱 RAG + 空间智能」为核心，打造可感知地理位置、可对话、可识图、可创作、可研学的非遗文化数字平台。")

    h2(doc, "二、痛点与价值")
    table(doc, ["痛点", "我们的方案"], [
        ["非遗知识分散、难检索", "MySQL 知识图谱 + Text2SQL RAG + D3 可视化"],
        ["线下研学缺乏智能导览", "IP/GPS 定位 + 高德 POI + 多模式路线规划"],
        ["年轻用户参与感弱", "AI 闯关答题、打卡社区、数字焕新创作"],
        ["图文视频理解门槛高", "讯飞星火多模态 + 阿里云百炼视频理解"],
    ])

    h2(doc, "三、核心功能（用户视角）")
    bullets = [
        "周边非遗地图：按访问者 IP 定位城市，自动标记文化馆/博物馆/非遗点位",
        "星火向导：流式多轮对话，支持语音输入与 TTS 播报，结合图谱 RAG",
        "识图溯源：上传图片/视频，AI 识别非遗元素并跳转地图高亮",
        "数字焕新：文生图异步创作非遗主题艺术图",
        "知识图谱透视：力导向图探索项目、传承人、地区关系",
        "AI 闯关：基于图谱随机出题 + 排行榜",
        "打卡广场：UGC 打卡、评论、管理员审核与热力图",
    ]
    for b in bullets:
        bullet(doc, b)

    h2(doc, "四、技术亮点（评委 30 秒版）")
    table(doc, ["维度", "技术选型"], [
        ["Agent 能力", "对话 / 视觉 / 创作 / 教育 / 空间 五类能力协同"],
        ["大模型", "讯飞星火 v3.1 WebSocket 流式；百炼 Qwen-VL 视频"],
        ["知识增强", "ChromaDB 向量召回 + MySQL Text2SQL 双路 RAG"],
        ["前端", "Vue 3 + Vite + Element Plus + 高德 + D3"],
        ["后端", "Flask 蓝图拆分 + Session 鉴权 + SSE"],
    ])

    h2(doc, "五、演示建议（5–8 分钟）")
    steps = [
        "登录 → 地图自动定位到当前城市，展示周边非遗点",
        "星火向导：提问「某某非遗传承人是谁」展示 RAG 回答",
        "识图溯源：上传非遗图片 → 地图高亮关联地标",
        "数字焕新：输入提示词生成艺术图",
        "知识图谱：拖拽节点查看关系",
        "闯关答题 + 排行榜（可选）",
        "管理员：打卡审核 / 热力图（若有时间）",
    ]
    for i, s in enumerate(steps, 1):
        bullet(doc, f"{i}. {s}")

    h2(doc, "六、Agent 赛道定调（答辩必背）")
    para(doc, "定调一句话：时空匠影 = 面向非遗研学的多模态 Tool-Augmented Agent 工作站，在统一账号下完成「问—看—找—走—学—创—分享」闭环。", bold=True)
    table(doc, ["维度", "结论"], [
        ["能否报 AI Agent 赛道？", "可以。垂直场景的多能力智能体工作站，叙事成立。"],
        ["作品类型", "场景型 / 工具增强型 Agent（非通用 AutoGPT）"],
        ["核心差异", "感知-推理-行动闭环 + 图谱 RAG + 空间智能 + 讯飞全链路"],
    ])
    h3(doc, "30 秒开场白（可背诵）")
    para(doc, "各位评委好。我们是「时空匠影」——非遗数字研学工作站。用户到达一座城市，系统通过 IP 感知位置，在地图上标出周边非遗场馆；可语音向星火向导提问，背后有知识图谱与向量双路 RAG；拍照识图可溯源文化地标；还能 AI 规划研学路线、闯关学习、数字创作与社区打卡。我们把对话、视觉、空间、教育、创作五类 Agent 能力串成一条研学闭环，而不是单一聊天机器人。谢谢。")

    h2(doc, "七、团队与总结")
    para(doc, "代码已提交、以答辩呈现为主。强调可演示闭环与讯飞生态契合；诚实说明当前为「多能力工作流编排」，演进方向是统一 Agent Orchestrator。")

    path = OUT_DIR / "1_时空匠影_比赛答辩项目介绍.docx"
    doc.save(path)
    return path


# ─────────────────────────────────────────────────────────────
# 文档 2：前后端模块与代码说明（详尽）
# ─────────────────────────────────────────────────────────────
def build_doc2():
    doc = Document()
    set_doc_style(doc)
    h1(doc, "时空匠影 · 前后端技术架构与模块说明")
    para(doc, "本文档面向开发与答辩技术质询，说明整体框架、各文件职责、技术栈与数据流。")

    h2(doc, "第一部分 · 整体架构")
    h3(doc, "1.1 系统分层")
    para(doc, "项目采用经典前后端分离：浏览器运行 Vue 3 SPA，通过 HTTP/SSE 调用 Flask REST API；后端聚合讯飞、高德、百炼等第三方能力，业务数据与知识图谱存 MySQL，语义检索使用 ChromaDB。")
    table(doc, ["层级", "技术", "职责"], [
        ["展示层", "Vue 3 + Element Plus + 高德 JS API + D3.js", "页面交互、地图、图谱可视化、流式 UI"],
        ["网关/代理", "Vite dev proxy / Nginx", "API 转发、Cookie、SSE 不缓冲、IP 头转发"],
        ["应用层", "Flask 3 + 蓝图", "路由、鉴权、业务编排"],
        ["AI 服务层", "utils.py + mysql_rag_engine.py", "大模型、RAG、TTS/ASR、图像/视频"],
        ["数据层", "MySQL + ChromaDB", "用户/社区/图谱/向量"],
        ["外部 API", "讯飞星火、百炼、高德", "对话、多模态、地图"],
    ])

    h3(doc, "1.2 请求链路（典型对话）")
    flow = [
        "用户在 ChatView 输入问题 → fetch POST /api/chat（SSE）",
        "routes.chat：校验 session_id，若有 audio 则 utils.audio_to_text",
        "utils.get_retrieved_context：ChromaDB 相似度检索 + MySQLGraphRAG.query",
        "utils.stream_chat_with_llm：WebSocket 连接讯飞星火，流式 yield token",
        "同时写入 ChatHistory；前端 ReadableStream 逐字渲染",
    ]
    for f in flow:
        bullet(doc, f)

    h2(doc, "第二部分 · 后端模块详解（backend_clean/）")

    backend_modules = [
        ("app.py", "Flask 应用工厂", "Flask, Flask-CORS, SQLAlchemy",
         "create_app()：加载 Config、注册 api_bp / community_bp / quiz_bp、db.create_all()、初始化 admin 账号；CORS 允许 5173 与 X-Client-Public-IP 头。"),
        ("config.py", "配置中心", "python-dotenv",
         "从 .env 读取 SECRET_KEY、MySQL、讯飞 APPID/KEY、高德 Key、百炼 Key；无硬编码生产密钥。"),
        ("exts.py", "扩展单例", "Flask-SQLAlchemy",
         "db 全局实例，避免 models 与 app 循环导入。"),
        ("models.py", "ORM 模型", "SQLAlchemy",
         "9 张表：User、ChatSession、ChatHistory、Feedback、Checkin、CheckinComment、QuizScore、图谱相关；role/is_banned 支持管理员与封号。"),
        ("routes.py", "核心 API 蓝图", "Flask, PyMySQL, PIL, threading",
         "认证；default_local/get_location IP 定位；会话 CRUD；/chat SSE；analyze_source 图/视频；generate_art 异步绘画；graph_data；direction/route_plan 高德路线；image_tasks 清理线程。"),
        ("routes_community.py", "社区蓝图", "Flask",
         "前缀 /api：反馈提交/我的反馈；打卡提交/列表/地图钉/评论；管理员用户/反馈/打卡审核。"),
        ("routes_quiz.py", "答题蓝图", "Flask, PyMySQL, 讯飞",
         "/quiz/generate AI 出题；/quiz/submit 判分入库；/quiz/leaderboard；/admin/heatmap 非遗与打卡热力数据。"),
        ("utils.py", "AI 与地图工具库", "websocket-client, requests, langchain, openai 兼容",
         "讯飞鉴权 WSS；stream_chat_with_llm；audio_to_text(IAT)；get_tts_audio；understand_image/video；execute_xf_art_generation；get_markers_from_amap；resolve_amap_ip_location；get_client_ip_from_request。"),
        ("mysql_rag_engine.py", "图谱 Text2SQL RAG", "PyMySQL, 讯飞",
         "自然语言 → SQL 查询 graph_nodes/graph_edges；结果注入 Prompt；与向量检索互补。"),
        ("build_rag_db.py", "向量库构建", "ChromaDB, HuggingFaceEmbeddings",
         "将图谱文本切片写入 chroma_db/，供 get_retrieved_context 语义召回。"),
        ("data_cleaner.py / import_to_mysql.py", "数据准备脚本", "pandas/csv",
         "清洗 nodes.csv、relationships.csv → JSON/SQL 导入 heritage_db。"),
    ]
    for idx, (file, role, tech, desc) in enumerate(backend_modules, 1):
        h3(doc, f"2.{idx} {file}")
        table(doc, ["项", "内容"], [["角色", role], ["技术", tech], ["说明", desc]])

    h3(doc, "2.12 后端核心 API 清单")
    apis = [
        ("POST", "/api/register, /login", "注册登录，Session Cookie"),
        ("GET", "/api/default_local", "用户 IP → 城市 + 周边非遗 markers"),
        ("GET", "/api/get_location", "返回 city/lng/lat/citycode"),
        ("POST", "/api/chat", "SSE 流式问答，支持 message 或 audio"),
        ("POST", "/api/analyze_source", "图片 Base64 识图 → 地标列表"),
        ("POST", "/api/analyze_source_video", "视频 → 百炼理解"),
        ("POST", "/api/generate_art", "异步文生图 task_id"),
        ("GET", "/api/graph_data", "图谱 nodes+edges JSON"),
        ("POST", "/api/direction", "单段路线 steps+polyline"),
        ("POST", "/api/route_plan", "多站研学路线 + AI 总结"),
        ("GET", "/api/quiz/generate", "AI 生成 5 道题"),
        ("POST", "/api/checkin/submit", "用户打卡（待审核）"),
        ("GET", "/api/admin/heatmap/*", "管理员热力图数据"),
    ]
    table(doc, ["方法", "路径", "说明"], apis)

    h3(doc, "2.13 IP 定位实现要点")
    bullets = [
        "get_client_ip_from_request：X-Forwarded-For > X-Real-IP > X-Client-Public-IP（本地）",
        "resolve_amap_ip_location(client_ip)：调用高德 v3/ip?ip=公网IP",
        "港澳台 city 为空时用 province 映射为「香港」等",
        "get_markers_from_amap(city)：高德 place/text 搜索非遗/博物馆关键词",
    ]
    for b in bullets:
        bullet(doc, b)

    h2(doc, "第三部分 · 前端模块详解（vue-ep-frontend/）")

    fe_modules = [
        ("main.js", "入口", "Vue 3, Pinia, Element Plus", "创建 app，注册路由、状态、UI 库。"),
        ("App.vue", "根组件", "Vue Router", "仅 <RouterView>。"),
        ("router/index.js", "路由", "Vue Router 4", "懒加载；meta.auth/guest/admin 守卫；普通用户落地 /map，管理员 /admin/users。"),
        ("stores/auth.js", "认证状态", "Pinia", "username/role 与 localStorage 同步；login/logout。"),
        ("stores/mapStore.js", "地图跨页", "Pinia", "识图结果 pendingMarkers → MapView 消费。"),
        ("api/index.js", "接口层", "Axios, Fetch", "46+ 接口；401 跳转登录；IP 定位请求附带 X-Client-Public-IP；SSE/TTS 用 fetch。"),
        ("utils/clientIp.js", "公网 IP", "fetch ipinfo/ipify", "本地开发浏览器查 IP 供后端高德定位；支持 force 刷新。"),
        ("views/LoginView.vue", "登录注册", "Element Plus", "账号密码；成功后按 role 跳转。"),
        ("views/LayoutView.vue", "主布局", "Element Plus Menu", "侧边栏角色菜单 + RouterView。"),
        ("views/MapView.vue", "非遗地图", "高德 AMap 3D, Fetch TTS", "IP 定城市+markers；GPS 定路线起点；单点/多站 direction；InfoWindow 弹窗。"),
        ("views/SourceView.vue", "识图溯源", "Axios 上传", "图/视频分析 → mapStore → 跳转地图。"),
        ("views/ReviveView.vue", "数字焕新", "轮询", "generate_art + query_art 每 3s。"),
        ("views/ChatView.vue", "星火向导", "SSE, MediaRecorder, Web Audio", "多会话；流式气泡；语音录 PCM；TTS 播放。"),
        ("views/GraphView.vue", "知识图谱", "D3 forceSimulation", "加载 graph_data，分类着色，拖拽缩放。"),
        ("views/QuizView.vue", "闯关", "Axios 长超时", "generate 90s；答题计时；leaderboard Top20。"),
        ("views/CommunityView.vue", "打卡广场", "高德 + 表单", "审核通过钉图；打卡提交；评论；IP 降级定位。"),
        ("views/FeedbackView.vue", "反馈", "Axios", "用户提交与查看我的反馈。"),
        ("views/Admin*.vue", "管理端", "Element Table", "用户封号、反馈回复、打卡审核、热力图 AMap.Heatmap。"),
        ("assets/global.css", "设计系统", "CSS Variables", "国风暗黑主题；覆盖 Element Plus 主色。"),
        ("vite.config.js", "构建", "Vite 5", "端口 5173；/api 代理 5000；Element 按需插件。"),
    ]
    for i, (file, role, tech, desc) in enumerate(fe_modules, 1):
        h3(doc, f"3.{i} {file}")
        table(doc, ["项", "内容"], [["角色", role], ["技术", tech], ["说明", desc]])

    h2(doc, "第四部分 · 数据库与 AI 数据流")
    h3(doc, "4.1 MySQL 主要表")
    table(doc, ["表名", "用途"], [
        ["users", "账号、角色、封号"],
        ["chat_sessions / chat_histories", "对话会话与消息"],
        ["graph_nodes / graph_edges", "非遗知识图谱"],
        ["checkins / checkin_comments", "打卡与评论"],
        ["feedbacks", "用户反馈"],
        ["quiz_scores", "答题成绩排行"],
    ])

    h3(doc, "4.2 RAG 双路检索")
    para(doc, "用户提问后：① ChromaDB 对问题做 embedding 相似检索，取 Top-K 文本片段；② MySQLGraphRAG 将问题转 SQL 查图谱实体与关系；③ 合并 context 注入星火 Prompt。降低幻觉并保证可溯源。")

    h2(doc, "第五部分 · 技术栈总表")
    table(doc, ["端", "类别", "技术"], [
        ["后端", "Web", "Flask 3, Flask-CORS, Flask-SQLAlchemy"],
        ["后端", "DB", "MySQL 8, PyMySQL, ChromaDB"],
        ["后端", "AI", "讯飞星火/IAT/TTS/绘画, 百炼 Qwen-VL, LangChain"],
        ["后端", "其他", "requests, websocket-client, Pillow, python-dotenv"],
        ["前端", "框架", "Vue 3, Vite 5, Vue Router 4, Pinia 2"],
        ["前端", "UI", "Element Plus, @element-plus/icons-vue"],
        ["前端", "地图/图", "高德 JS API 2.0, D3.js"],
        ["前端", "通信", "Axios, Fetch SSE, Web Audio API, MediaRecorder"],
    ])

    path = OUT_DIR / "2_时空匠影_前后端技术模块与代码说明.docx"
    doc.save(path)
    return path


# ─────────────────────────────────────────────────────────────
# 文档 3：专家答辩模拟 Q&A
# ─────────────────────────────────────────────────────────────
def build_doc3_preamble(doc):
    """答辩定调与赛道合规性（代码不改，仅答辩用）"""
    h2(doc, "〇、答辩定调与开场（必读）")
    para(doc, "本项目代码已提交，以下内容为答辩话术与评委应答策略，不涉及改代码。")

    h3(doc, "0.1 三句话结论")
    table(doc, ["问题", "结论"], [
        ["能报 AI Agent 赛道吗？", "能。非遗研学场景下的多模态 Tool-Augmented Agent 工作站。"],
        ["是严格意义的自主 Agent 吗？", "尚不完整：更像「大模型 + 多工具 + 固定工作流」；自主规划、统一编排偏弱。"],
        ["作为参赛作品合格吗？", "合格。应用型/场景型 Agent 符合赛道；若评委按 AutoGPT 标准会吃亏，需用正确叙事。"],
    ])

    h3(doc, "0.2 30 秒开场白")
    para(doc, "各位评委好。我们是「时空匠影」——非遗数字研学工作站。用户到达一座城市，系统通过 IP 感知位置，在地图上标出周边非遗场馆；可语音向星火向导提问，背后有知识图谱与向量双路 RAG；拍照识图可溯源文化地标；还能 AI 规划研学路线、闯关学习、数字创作与社区打卡。我们把对话、视觉、空间、教育、创作五类 Agent 能力串成一条研学闭环，而不是单一聊天机器人。谢谢。")

    h3(doc, "0.3 答辩定调金句（背一句即可）")
    bullet(doc, "时空匠影 = 面向非遗研学的多模态 Tool-Augmented Agent 工作站。")
    bullet(doc, "不是静态网站，也不是 Chatbot，而是「问—看—找—走—学—创—分享」闭环。")
    bullet(doc, "演进方向：统一意图路由 + Function Calling + 可观测 Agent 链路（诚实说规划，不夸大现状）。")

    h3(doc, "0.4 五类 Agent 能力矩阵（对照表）")
    table(doc, ["能力块", "Agent 特征", "在本项目中的体现"], [
        ["对话 Agent", "记忆 + 检索 + 生成", "多会话、ChromaDB + Text2SQL RAG、SSE 流式、语音 IAT/TTS"],
        ["空间 Agent", "感知位置 + 调地图工具", "IP/GPS 定位、高德 POI、单点/多站路线、route_plan 流水线"],
        ["视觉 Agent", "多模态理解 + 下游动作", "识图/视频理解 → mapStore → 地图高亮"],
        ["创作 Agent", "目标驱动生成", "讯飞绘画异步任务、轮询结果"],
        ["教育 Agent", "结构化任务输出", "AI 出题、判分、排行榜"],
    ])

    h3(doc, "0.5 感知—推理—行动闭环（讲解用）")
    flow = [
        "感知：IP/GPS 定位、图片/视频上传、语音 PCM",
        "推理：星火大模型 + 双路 RAG（向量 + 图谱 SQL）+ 路线规划 LLM 排序",
        "行动：流式回答、地图标点、路线折线、生图、出题、打卡入库",
    ]
    for f in flow:
        bullet(doc, f)

    h3(doc, "0.6 答辩时「建议说 / 避免说」")
    table(doc, ["建议说", "避免说"], [
        ["多模态 Tool-Augmented Agent、研学工作流闭环", "我们是全球首个全自动超级 Agent"],
        ["路线规划是多步工具链：POI 检索 → LLM 编排 → 高德算路", "系统完全自主任意任务"],
        ["当前用关键词触发图谱检索，下一步做 Function Calling", "已经实现 ReAct 自主规划（未实现）"],
        ["场景型 Agent，垂直非遗 + 空间 + 图谱", "和 ChatGPT 一样通用"],
    ])


def build_doc3():
    doc = Document()
    set_doc_style(doc)
    h1(doc, "时空匠影 · AI Agent 赛道专家答辩模拟")
    para(doc, "模拟评委/领域专家提问，附参考答案、拓展方向与赛道合规性专章。建议答辩前通读，用自己的话复述。")

    build_doc3_preamble(doc)

    sections = [
        ("一、项目定位与 Agent 内涵", [
            ("你们的项目和普通非遗网站或聊天机器人有什么区别？",
             "我们不是静态展示站，而是多能力 Agent 编排：对话 Agent（RAG+语音）、视觉 Agent（识图/视频）、创作 Agent（文生图）、教育 Agent（AI 出题）、空间 Agent（IP/GPS+路线）。各能力通过统一账号、会话、地图状态串联，形成「研学工作流」而非单点工具。",
             "引入 LangGraph/CrewAI 做多 Agent 协作；定义 Agent 间 handoff 协议（如识图 Agent 自动调用地图 Agent）。"),
            ("为什么适合 AI Agent 赛道而不是纯应用开发？",
             "核心在于「感知-推理-行动」闭环：感知（IP/GPS/图像/视频）、推理（大模型+RAG）、行动（生成回答/标点/路线/图片/题目）。且具备工具调用形态（高德 API、SQL、TTS 等）与流式交互体验。",
             "将工具封装为 MCP Server，支持外部 Agent 框架接入；增加可观测性（链路追踪、每步 tool call 日志）。"),
            ("目标用户是谁？解决了什么真实场景？",
             "中小学生/亲子研学、非遗爱好者、文化馆线下导览辅助。场景：到陌生城市想知道附近有什么非遗可逛；看到工艺品想知道渊源；计划一日研学路线；边逛边问星火向导。",
             "与校方/博物馆 B 端合作，定制垂类知识库与专属 Agent 人设。"),
        ]),
        ("二、技术架构与工程化", [
            ("前后端为什么这样拆分？",
             "Flask 专注 API 与 AI 调度，Vue 专注交互与地图渲染；SSE/WebSocket 长连接不适合模板渲染。蓝图拆分 routes / community / quiz 便于权限边界与维护。",
             "微服务化 AI 网关；前端 SSR 仅在有 SEO 需求时考虑。"),
            ("Session Cookie 鉴权是否够用？",
             "当前比赛/校内场景足够：HttpOnly Cookie + CORS 白名单 + 管理员 role 校验。生产应 HTTPS、SameSite=None、防 CSRF（SameSite=Lax 已部分防护）。",
             "JWT + Refresh Token；OAuth 微信登录。"),
            ("流式对话如何实现？为什么不用 Axios？",
             "后端 stream_with_context + text/event-stream；前端 fetch ReadableStream 按 chunk 解析。Axios 对 SSE 支持不便，故 TTS/对话均用原生 fetch。",
             "统一 SSE 客户端库；支持断线重连与 message id。"),
            ("image_tasks 内存任务如何防泄漏？",
             "routes.py 后台线程定期清理超过 TTL（10 分钟）的绘画任务字典条目，避免 generate_art 轮询堆积。",
             "改用 Redis + Celery 持久化任务队列。"),
        ]),
        ("三、RAG 与知识图谱", [
            ("为什么同时用 ChromaDB 和 MySQL Text2SQL？",
             "向量检索擅长模糊语义与同义表达；Text2SQL 擅长精确实体关系（传承人-项目-地区）。双路合并提高召回率与可解释性，符合图谱场景。",
             "GraphRAG 社区摘要；对 edges 做 embedding；引入 rerank 模型。"),
            ("Text2SQL 如何防止 SQL 注入？",
             "mysql_rag_engine 限制仅允许 SELECT、白名单表名，并由 LLM 生成后做关键字过滤/校验；不拼接用户原始输入。",
             "使用参数化查询模板 + slot filling，而非自由 SQL。"),
            ("图谱数据从哪来？质量如何保证？",
             "nodes.csv / relationships.csv 经 data_cleaner 清洗为 clean_nodes/edges.json，再 import_to_mysql。可人工抽检节点类型与关系谓词。",
             "对接官方非遗名录 API；增量更新与版本管理。"),
            ("若 RAG 检索为空，对话会怎样？",
             "仍调用大模型，但 Prompt 注明「未检索到图谱上下文，请基于通用知识并提示用户」。避免编造具体传承人姓名。",
             "检索为空时主动触发联网搜索工具（需合规）。"),
        ]),
        ("四、多模态与讯飞/百炼", [
            ("为什么对话用讯飞、视频用百炼？",
             "讯飞星火对比赛生态与语音链路（IAT/TTS）集成成熟；视频理解用百炼 Qwen-VL 接口简单、效果稳定。属于「按能力选模型」的工程策略。",
             "抽象 ModelProvider 接口，热切换模型；统一计费监控。"),
            ("识图溯源的技术路径？",
             "图片 Base64 → understand_image（星火多模态）→ 解析非遗名/地区 → get_markers_from_amap 精确 POI 搜索 → 返回 markers 与 city 给前端 mapStore。",
             "增加 OCR + 文物检测小模型；链接百科/非遗百科 URL。"),
            ("绘画任务是同步还是异步？",
             "异步：/generate_art 返回 task_id，前端轮询 /query_art；后端线程执行 WebSocket 绘画，结果存 image_tasks。",
             "WebSocket 推送完成事件；结果存 OSS 而非内存。"),
        ]),
        ("五、地图与 IP 定位", [
            ("本地开发如何做到按用户 IP 定位？",
             "Vite 代理下后端只见 127.0.0.1。前端 clientIp.js 通过 ipinfo/ipify 获取浏览器公网 IP，请求头 X-Client-Public-IP 传给 Flask，再调高德 v3/ip?ip=...。",
             "生产用 Nginx 传 X-Forwarded-For，无需浏览器上报。"),
            ("开 VPN 为什么曾经总显示广州？",
             "① 高德对香港 IP 常返回 city 为空，旧逻辑直接 fallback 广州；② 浏览器未走 VPN 查 IP 时仍用大陆出口。已修复 province 映射与 IP 刷新。",
             "支持用户手动选城市；显示当前检测 IP 便于调试。"),
            ("GPS 和 IP 定位分别用于什么？",
             "IP：初始城市与周边非遗 POI；GPS：路线规划起点精确定位。二者分工避免混淆。",
             "融合 WiFi/基站辅助定位；室内展馆蓝牙 beacon。"),
        ]),
        ("六、社区、安全与运营", [
            ("打卡为什么要审核？",
             "UGC 防 spam、涉政涉黄风险；管理员 AdminCheckins 通过/拒绝并记录原因。",
             "AI 预审 + 人工复审；敏感词与图片鉴黄 API。"),
            ("管理员权限如何控制？",
             "User.role==1；路由 meta.admin + 后端 @admin_required 双校验。",
             "RBAC 细粒度权限；操作审计日志。"),
            ("封号机制？",
             "is_banned + banned_reason；登录时校验并拒绝。",
             "限时封禁；申诉流程。"),
        ]),
        ("七、性能、成本与可靠性", [
            ("并发高时瓶颈在哪？",
             "讯飞 WebSocket 连接数、MySQL 连接池、Chroma 单实例。当前面向演示与小规模用户。",
             "连接池、队列削峰、读写分离、CDN 静态资源。"),
            ("大模型调用如何控制成本？",
             "答题/识图/路线总结限制调用频率；会话级缓存；RAG 减少无效 token。",
             "按用户配额；小模型做意图分类再调大模型。"),
            ("若高德或讯飞 API 失败？",
             "IP 定位 fallback 广州；路线返回 error JSON；对话 SSE 发送错误事件；前端 ElMessage 提示。",
             "熔断降级与健康检查面板。"),
        ]),
        ("八、创新点、不足与未来规划", [
            ("你认为最大的创新点是什么？",
             "「空间智能 + 知识图谱 RAG + 多模态」三位一体，且在同一工作站 UI 内完成研学闭环，而非孤立 Demo。",
             "申报专利/软著；开源 RAG 评测数据集。"),
            ("当前不足？",
             "Agent 编排仍偏硬编码路由，非自主 tool planning；无统一 memory 跨模块；评测指标未系统化。",
             "见下方三年路线图。"),
            ("若给你 3 个月还会做什么？",
             "① Agent Orchestrator（意图识别→工具选择）；② 研学行程一键规划 Agent；③ 评测集与自动化回归；④ 部署 Docker Compose + 监控。",
             "MCP 工具市场；数字人讲解；AR 识物。"),
            ("如何体现「讯飞」生态？",
             "星火对话/识图/绘画/语音全链路；可进一步对接讯飞开放平台最新 Agent SDK 与星火 Ultra。",
             "深度集成讯飞虚拟人；比赛官方组件替换自研 WSS 封装。"),
        ]),
        ("九、赛道合规性：这是合格的 AI Agent 吗？（专章）", [
            ("从评委角度，你们到底算不算 AI Agent？",
             "算，但要准确定义：我们是「非遗研学场景下的多模态 Tool-Augmented Agent 工作站」。具备感知（IP/GPS/图/音）、推理（大模型+RAG）、行动（回答/标点/路线/生图/出题）；多条链路调用外部工具（高德、MySQL、TTS）。符合赛道对「Agent 应用」的常见期待，但不是单一自主体的 AutoGPT。",
             "若评委认可场景 Agent，强调闭环演示；若偏学术，主动承认编排方式并给出演进路线。"),
            ("你们和 Chatbot 的本质区别是什么？",
             "Chatbot 只有对话；我们有空间智能（地图+路线）、视觉溯源、创作、教育、UGC 社区，且识图结果经 mapStore 驱动地图行动，route_plan 是 POI→LLM→高德 的多步工具链，不是一轮文本回复。",
             "答辩演示顺序体现「行动」而不只聊天。"),
            ("自主性体现在哪里？有没有「Agent 循环」？",
             "完整 ReAct 循环尚未实现；自主性体现在：① 对话侧自动双路检索再生成；② 识图后自动搜 POI 并推送地图；③ route_plan 自动排序站点并算路。属于「工作流级自主」，可诚实说明下一步做统一 Orchestrator。",
             "答辩可展示 route_plan 与识图→地图的联动，最有说服力。"),
            ("为什么用关键词触发图谱检索，而不是模型选工具？",
             "工程上可控、延迟低、易调试；比赛周期内优先保证演示稳定。我们清楚这是与「标准 Agent」的差距，规划用星火 Function Calling 做意图→工具选择，作为二期而非本次提交范围。",
             "把「关键词路由」说成「可解释的轻量意图路由」，避免被理解为不会 Agent。"),
            ("若评委说「这只是大模型套壳」怎么回应？",
             "套壳只有对话；我们叠加了：自有非遗知识图谱与 Text2SQL、Chroma 向量库、高德空间工具链、异步绘画任务、社区审核与热力图——这些是领域知识与工程系统，不是 Prompt  alone。RAG 降低幻觉，地图与路线可验证。",
             "准备 1 分钟 live demo：问一个图谱关系 + 地图标点 + 识图跳转。"),
            ("和 Copilot、通义、文心等通用助手比优势？",
             "通用助手无非遗垂类图谱、无「到某地自动标非遗点」的空间闭环、无研学打卡与闯关。我们是垂直研学 Agent，深度 > 广度。",
             "不正面硬刚通用模型，强调垂类数据与场景闭环。"),
            ("记忆（Memory）有没有？",
             "会话级 ChatHistory 支持多轮对话；跨模块通过 mapStore 传递识图地标、session 绑定用户。尚无统一 Agent Memory 写回所有模块，这是已知边界，可在 Q&A 中主动说出显得专业。",
             "未来：用户偏好城市、浏览过的非遗类型写入长期记忆。"),
            ("讯飞杯 AI Agent 赛道，评委最可能看重什么？",
             "① 大模型是否解决真实场景；② 是否有工具/多模态/Agent 形态；③ 讯飞能力使用深度；④ 可演示、可理解。我们四条都能对应，答辩用闭环演示覆盖。",
             "突出星火 + IAT/TTS + 图像/绘画全链路。"),
            ("代码不能改了，答辩还能怎么加分？",
             "① 用正确 Agent 叙事与能力矩阵图；② 演示「感知→行动」最短路径（登录→地图→问 RAG→识图→地图）；③ 诚实讲不足与演进；④ 准备评委追问表（本文档第九、十节）。",
             "PPT 加一张「与传统应用对比」表即可。"),
        ]),
    ]

    for sec_title, qas in sections:
        h2(doc, sec_title)
        for i, (q, a, fut) in enumerate(qas, 1):
            h3(doc, f"Q{i}")
            qa_block(doc, q, a, fut)

    h2(doc, "十、评委高频追问速答卡（一句话版）")
    quick = [
        ("数据隐私？", "图片/视频 Base64 传输，会话存自有 MySQL；告知用户数据用于研学分析，生产需隐私政策。"),
        ("能离线吗？", "核心依赖在线 API，离线仅可缓存已加载地图瓦片与历史会话。"),
        ("竞品对比？", "相比通用地图：有非遗图谱与 AI；相比纯 Chatbot：有空间与 UGC 闭环。"),
        ("是 Agent 还是 Chatbot？", "Chatbot 只是能力之一；五类 Agent 能力 + 研学工作流闭环。"),
        ("自主性在哪？", "RAG 自动检索、识图联动地图、route_plan 多步工具链；非全自动规划。"),
        ("最大不足？", "缺统一 Orchestrator 与模型自主选工具；跨模块 Memory 未统一——已规划演进。"),
        ("为什么选 Agent 赛道？", "感知-推理-行动 + 工具调用 + 垂类闭环，符合场景型 Agent 作品定义。"),
    ]
    table(doc, ["问题", "一句话答"], quick)

    h2(doc, "附录 A：与「严格 Agent」的差距对照（诚实陈述用）")
    table(doc, ["严格 Agent 特征", "本项目现状", "答辩怎么说"], [
        ["模型自主选工具", "多为路由/固定 API 调用", "已实现工具调用形态，选型由工作流保证稳定"],
        ["ReAct 思考-行动循环", "未实现完整循环", "路线规划等已有多步链，下一步统一 Orchestrator"],
        ["统一 Agent 大脑", "多页面多入口", "产品是工作站，五类 Agent 能力协同"],
        ["跨任务长期记忆", "会话级 + mapStore", "满足研学单次行程，长期记忆在 roadmap"],
    ])

    h2(doc, "附录 B：推荐演示顺序（5–8 分钟，突出 Agent）")
    demo = [
        "登录 → 地图 IP 定位（空间 Agent·感知+行动）",
        "星火向导：图谱关系问题（对话 Agent·RAG）",
        "识图上传 → 跳转地图高亮（视觉 Agent→空间 Agent）",
        "可选：路线规划或数字焕新（规划/创作 Agent）",
        "可选：闯关或打卡社区（教育/UGC）",
        "收尾：一句话定调 + 演进路线图（口播，可不写代码）",
    ]
    for i, d in enumerate(demo, 1):
        bullet(doc, f"{i}. {d}")

    path = OUT_DIR / "3_时空匠影_AI_Agent赛道专家答辩模拟问答.docx"
    doc.save(path)
    return path


if __name__ == "__main__":
    p1 = build_doc1()
    p2 = build_doc2()
    p3 = build_doc3()
    print("已生成：")
    print(p1)
    print(p2)
    print(p3)
