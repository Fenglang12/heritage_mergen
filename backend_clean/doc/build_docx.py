"""直接生成三份答辩 Word 文档（内容与 heritage_mergen 代码库一致）。"""

from pathlib import Path

from docx import Document
from docx.enum.text import WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

DOC_DIR = Path(__file__).resolve().parent
FONT = "微软雅黑"
TEAL = RGBColor(0x2A, 0x70, 0x66)
GOLD = RGBColor(0xC9, 0xA8, 0x4C)


def _font(run, size=11, bold=False, color=None, name=None):
    run.font.name = name or FONT
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name or FONT)
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = color


def _para(doc, text, size=11, bold=False, color=None, space_after=6):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    p.paragraph_format.line_spacing = 1.25
    run = p.add_run(text)
    _font(run, size=size, bold=bold, color=color)
    return p


def _heading(doc, text, level=1):
    lv = 0 if level == 0 else level
    p = doc.add_heading(text, level=lv)
    sizes = {0: 22, 1: 16, 2: 13}
    for run in p.runs:
        _font(run, size=sizes.get(level, 13), bold=True, color=TEAL if level <= 1 else None)
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(6)


def _bullet(doc, text, size=11):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(3)
    run = p.add_run(text)
    _font(run, size=size)


def _table(doc, headers, rows, col_widths=None):
    t = doc.add_table(rows=1 + len(rows), cols=len(headers))
    t.style = "Table Grid"
    for j, h in enumerate(headers):
        c = t.rows[0].cells[j]
        c.text = ""
        run = c.paragraphs[0].add_run(h)
        _font(run, size=10, bold=True, color=TEAL)
    for ri, row in enumerate(rows):
        for j in range(len(headers)):
            val = row[j] if j < len(row) else ""
            c = t.rows[ri + 1].cells[j]
            c.text = ""
            run = c.paragraphs[0].add_run(val)
            _font(run, size=10)
    doc.add_paragraph()


def build_doc1():
    doc = Document()
    _heading(doc, "时空匠影 · 比赛答辩项目介绍", 0)
    _para(doc, "深圳理工大学 AI Agent 大赛 · 非遗研学工作站决赛作品", size=10, color=GOLD, space_after=12)

    _heading(doc, "一、项目概述", 1)
    _para(
        doc,
        "「时空匠影」面向非遗研学：国风暗黑 UI（青金配色），包含非遗地图、识图溯源、知识图谱、"
        "星火向导、数字焕新、闯关答题、研学报告与社区打卡。",
    )

    _heading(doc, "二、用户痛点与解决方案", 1)
    _table(
        doc,
        ["痛点", "本产品方案"],
        [
            ["非遗点位分散，实地难找", "高德 POI + IP 定位；地图弹窗展示 ai_intro 简介；路线规划"],
            ["传承关系复杂难懂", "MySQL 知识图谱 + 星火 Text2SQL；Three.js 3D 力导向可视化"],
            ["学习缺少智能引导", "讯飞星火轻量 Agent（Prompt + tool_call 多步工具）"],
            ["传统技艺难以现代表达", "智谱 GLM-4V 理解参考图 + CogView-4 数字焕新"],
            ["研学过程无法总结", "聚合对话/答题/打卡/创作 → 星火生成研学报告（含数字创作集）"],
        ],
    )

    _heading(doc, "三、八大功能模块", 1)
    modules = [
        ("非遗地图 /map", "同城非遗 POI、标点简介、多站路线；Agent/识图结果经 mapStore 联动高亮"),
        ("识图溯源 /source", "图片/视频识别非遗条目，合并高德地标（SOURCE_TRACE_MAX_MARKERS 可配）"),
        ("知识图谱 /graph", "自然语言查传承人/地区/项目关系；前端搜索节点并相机聚焦"),
        ("星火向导 /chat", "多会话 SSE 对话；六类工具；文末推荐站内页面一键跳转"),
        ("数字焕新 /revive", "参考图+文案；SSE 推送 GLM-4V→CogView-4 阶段；作品入 user_artworks"),
        ("闯关答题 /quiz", "SSE 流式出题、提交得分、排行榜"),
        ("研学报告 /report", "24h 缓存；content_json LONGTEXT；创作集大图入库剥离、读出回填"),
        ("社区打卡 /community", "打卡广场、意见反馈；管理员审核/封号/热力图"),
    ]
    for title, desc in modules:
        _bullet(doc, f"{title}：{desc}")

    _heading(doc, "四、技术亮点（答辩强调）", 1)
    highlights = [
        "轻量 Agent：不依赖 LangGraph；工具复用 shared/utils；parse.py 可单测",
        "推荐链接三层治理：Prompt 规则 + normalize 畸形链接 + infer/enforce 按意图纠错",
        "双模型焕新管线：有图先视觉分析再生图；对话与焕新页共用 iter_zhipu_art_generation",
        "工程化存储：user_artworks.image_data、study_reports.content_json 启动自动升级 LONGTEXT",
        "演示模式 DEMO_MODE：识图/焕新/对话走预置数据，适合答辩现场弱网",
    ]
    for h in highlights:
        _bullet(doc, h)

    _heading(doc, "五、登录与界面", 1)
    _para(
        doc,
        "登录入口 /login：青金深色双栏布局（左：品牌、数据条、功能卡片、非遗时间轴与跑马灯；"
        "右：登录/注册表单、「登堂入室」按钮）。认证逻辑封装于 features/auth/composables/useAuthForm.js。"
        "全局 global.css 统一 Element Plus 深色主题与 heritage-dialog 弹窗样式。",
    )

    _heading(doc, "六、角色与部署", 1)
    _table(
        doc,
        ["角色", "能力"],
        [
            ["普通用户", "地图、对话、识图、焕新、答题、报告、打卡、反馈"],
            ["管理员 role=1", "用户管理、打卡审核、反馈处理、访问热力图"],
        ],
    )
    _para(doc, "后端 backend_clean → http://localhost:5000；前端 vue-ep-frontend → http://localhost:5173（/api 代理）。")
    _para(doc, "环境变量见 backend_clean/.env.example（Spark、智谱、高德、XFYUN、DEMO_MODE 等）。")

    doc.save(DOC_DIR / "1_时空匠影_比赛答辩项目介绍.docx")
    print("OK: 1_时空匠影_比赛答辩项目介绍.docx")


def build_doc2():
    doc = Document()
    _heading(doc, "时空匠影 · 前后端技术模块与代码说明", 0)
    _para(doc, "仓库：heritage_mergen · backend_clean + vue-ep-frontend", size=10, color=GOLD)

    _heading(doc, "一、技术栈", 1)
    _table(
        doc,
        ["层级", "技术选型"],
        [
            ["前端", "Vue 3、Vite 5、Element Plus、Pinia、Vue Router、Three.js、高德 JS API v2"],
            ["后端", "Flask、SQLAlchemy、MySQL 8、ChromaDB（向量百科，仓库含 chroma_db/）"],
            ["对话/图谱", "讯飞星火 Spark（Agent、Text2SQL、出题、报告、标点简介默认通道）"],
            ["视觉/生图", "智谱 GLM-4V + CogView-4；百炼可选（视频识图、标点 qwen 通道）"],
            ["地图", "高德 Web 服务（IP、POI、direction、route_plan）"],
            ["语音", "讯飞 IAT（/api/asr）、TTS（/api/stream_voice）"],
        ],
    )

    _heading(doc, "二、后端目录（backend_clean）", 1)
    _para(doc, "app.py：注册蓝图、db.create_all()、ensure_user_artworks_schema、ensure_study_reports_schema")
    backend_rows = [
        ("api/routes.py", "login/register、地图、POST /chat SSE、识图、焕新、图谱、asr、TTS"),
        ("features/agent/engine.py", "HeritageAgent 多步循环、演示降级、用户画像注入"),
        ("features/agent/tools.py", "六工具 execute_tool；revive 支持 on_progress"),
        ("features/agent/parse.py", "tool_call 解析、推荐链接 normalize/infer/enforce"),
        ("features/graph/rag.py", "MySQLGraphRAG Text2SQL"),
        ("features/revive/artwork.py", "user_artworks 入库、LONGTEXT、JPEG 压缩"),
        ("features/report/service.py", "行为聚合、报告生成、strip/hydrate 创作集"),
        ("features/quiz、community", "独立 Blueprint"),
        ("features/demo", "DEMO_MODE 预置数据与识图/焕新缓存"),
        ("shared/utils.py", "讯飞/智谱/RAG/标点简介/IAT 安全解析"),
    ]
    _table(doc, ["路径", "职责"], backend_rows)

    _heading(doc, "三、前端目录（vue-ep-frontend/src）", 1)
    frontend_rows = [
        ("core/router/index.js", "路由守卫 auth/guest/admin；管理员默认 /admin/users"),
        ("api/index.js", "全部 REST + streamChat 等 SSE 入口"),
        ("features/auth/LoginView.vue", "正式登录页 UI；useAuthForm.js 登录注册"),
        ("features/chat/ChatView.vue", "Agent 对话、会话标题、图片/语音、推荐链接"),
        ("features/chat/stores/mapStore.js", "对话/识图地标 → 地图高亮"),
        ("features/chat/utils/suggestLinks.js", "推荐链接规范化、router.push"),
        ("features/chat/utils/chatStream.js", "解析 /api/chat SSE 事件"),
        ("features/map/MapView.vue", "POI、clientIp → X-Client-Public-IP"),
        ("features/graph/GraphView.vue", "Three.js 力导向、搜索聚焦"),
        ("features/revive/ReviveView.vue", "焕新 SSE 双阶段进度"),
        ("features/report/ReportView.vue", "报告 SSE、数字创作集"),
        ("assets/global.css", "主题变量、heritage-dialog、深色 el-input 计数"),
    ]
    _table(doc, ["路径", "职责"], frontend_rows)

    _heading(doc, "四、路由与页面对照", 1)
    _table(
        doc,
        ["路由", "页面", "后端主要接口"],
        [
            ["/login", "LoginView", "POST /api/login、register"],
            ["/map", "MapView", "GET default_local、POST direction/route_plan"],
            ["/source", "SourceView", "POST analyze_source、analyze_source_video、asr"],
            ["/chat", "ChatView", "POST /api/chat、sessions、PATCH session 标题"],
            ["/graph", "GraphView", "GET graph_data、POST graph/query"],
            ["/revive", "ReviveView", "POST generate_art/stream、asr"],
            ["/quiz", "QuizView", "POST quiz/generate/stream、submit"],
            ["/report", "ReportView", "GET report/latest、POST report/generate/stream"],
            ["/community", "CommunityView", "checkin、feedback"],
            ["/admin/*", "Admin 四页", "admin/users、checkins、feedbacks、heatmap"],
        ],
    )

    _heading(doc, "五、核心数据流", 1)
    _heading(doc, "5.1 Agent 对话", 2)
    _para(
        doc,
        "ChatView → POST /api/chat（body: message、session_id；可选 audio、image）"
        " → HeritageAgent 循环解析 <tool_call> → execute_tool → scratchpad"
        " → 流式 text + tool_call/tool_result/revive_progress/art_image"
        " → infer_suggest_path + enforce_suggest_path 修正文末推荐"
        " → normalize_agent_suggest_links 后写入 chat_histories。",
    )
    _heading(doc, "5.2 数字焕新", 2)
    _para(
        doc,
        "ReviveView 或 Agent revive_heritage → iter_zhipu_art_generation（glm 分析 → cogview 生图）"
        " → normalize_art_result_url → 可选写入 user_artworks（source=revive/agent）。",
    )
    _heading(doc, "5.3 研学报告", 2)
    _para(
        doc,
        "聚合近 10 会话、答题、打卡、list_user_artworks → Spark 生成 JSON"
        " → SSE 推送完整内容 → strip_report_for_storage 去掉创作集 base64 再入库"
        " → GET latest 时 hydrate_report_artworks 按 id 回填图片。",
    )

    _heading(doc, "六、Agent 推荐路径规则", 1)
    _table(
        doc,
        ["用户意图示例", "推荐路径", "默认按钮文案"],
        [
            ["在哪里、怎么去、附近、地址", "/map", "打开非遗地图"],
            ["识图、认图、上传图片", "/source", "识图溯源"],
            ["传承人、关系、分布（非导航）", "/graph", "知识图谱"],
            ["出题、考我、闯关", "/quiz", "开始闯关"],
            ["焕新、重绘、国潮", "/revive", "非遗焕新"],
            ["研学报告、总结", "/report", "研学报告"],
            ["打卡、晒足迹", "/community", "打卡广场"],
        ],
    )
    _para(doc, "禁止：用户仅问地点时推荐 /quiz。实现见 features/agent/parse.py，单测 tests/test_agent_engine.py。")

    _heading(doc, "七、SSE 事件类型", 1)
    _table(
        doc,
        ["接口", "事件 type", "说明"],
        [
            ["POST /api/chat", "asr / thinking / tool_call / tool_result", "语音转写、工具步骤"],
            ["POST /api/chat", "revive_progress / art_image", "对话内焕新进度与成图"],
            ["POST /api/chat", "text / error / done", "回答流、结束"],
            ["POST /api/generate_art/stream", "progress / done / error", "焕新页阶段进度"],
            ["POST /api/report/generate/stream", "text / done", "报告流式生成"],
            ["POST /api/quiz/generate/stream", "question / done", "逐题出题"],
        ],
    )

    _heading(doc, "八、数据库要点", 1)
    _table(
        doc,
        ["表名", "说明"],
        [
            ["users", "账号、role（0 用户 1 管理员）"],
            ["chat_sessions / chat_histories", "多会话；首条消息自动标题；PATCH 重命名"],
            ["user_artworks", "焕新作品；image_data LONGTEXT；入库 JPEG 压缩"],
            ["study_reports", "content_json LONGTEXT；strip/hydrate 创作集"],
            ["checkins / quiz_scores / feedbacks", "打卡、答题、反馈"],
            ["graph 相关表", "scripts/import_to_mysql.py 导入节点边"],
        ],
    )

    _heading(doc, "九、测试与演示", 1)
    _para(doc, "cd backend_clean && python -m unittest discover -s tests -v")
    _para(doc, "DEMO_MODE=true：识图、焕新、Agent 使用 features/demo/data/demo_data.json。")

    doc.save(DOC_DIR / "2_时空匠影_前后端技术模块与代码说明.docx")
    print("OK: 2_时空匠影_前后端技术模块与代码说明.docx")


def build_doc3():
    doc = Document()
    _heading(doc, "时空匠影 · AI Agent 赛道专家答辩模拟问答", 0)
    _para(doc, "共 12 题 · 与 backend_clean/features/agent 及前端 chat 模块一致", size=10, color=GOLD)

    qa = [
        (
            "Q1：为什么不用 LangChain / LangGraph？",
            "采用 Prompt + <tool_call> JSON 轻量架构。工具在 features/agent/tools.py，"
            "直接调用 Chroma、MySQLGraphRAG、高德、智谱焕新等既有能力。"
            "parse.py 可单元测试，依赖少、链路透明，适合竞赛周期交付。",
        ),
        (
            "Q2：Agent 有哪些工具？如何选择？",
            "共六种：search_heritage（向量百科）、query_graph（图谱 SQL）、search_places（POI）、"
            "plan_route（路线）、identify_image（请求带 image 时）、revive_heritage（对话内焕新）。"
            "模型输出 <tool_call>{name,args}</tool_call>，engine 解析后 execute_tool，结果写入 scratchpad 进入下一轮。"
            "图谱类问题还可关键词预调 query_graph。",
        ),
        (
            "Q3：用户问「皮影戏在哪里」为何不能跳答题页？",
            "三层保障：① Prompt 中 AGENT_ROUTE_RULES 明确地点→/map 禁止 /quiz；"
            "② infer_suggest_path 检测 LOCATION_HINT_KEYWORDS；"
            "③ enforce_suggest_path 替换文末 👉 行为 [打开非遗地图](/map)。"
            "若模型输出 [/quiz]，normalize_agent_suggest_links 补全 Markdown。"
            "前端 suggestLinks.js 同步处理，router.push 跳转。",
        ),
        (
            "Q4：对话内焕新和 /revive 页面有何区别？",
            "共用 shared/utils.iter_zhipu_art_generation。对话内由 revive_heritage 触发，"
            "SSE 推送 revive_progress、art_image 事件在 ChatView 展示。"
            "/revive 为专用工作流：参考图+Prompt+双阶段进度条。"
            "成功作品写入 user_artworks，研学报告数字创作集可展示。",
        ),
        (
            "Q5：语音输入如何实现？400 错误如何排查？",
            "前端 useVoiceInput 录制 WAV → POST /api/asr → 讯飞 IAT WebSocket。"
            "shared/utils 对返回 JSON 做 header.status 安全解析，避免 KeyError。"
            "过短录音前端拦截；需配置有效 XFYUN_*；焕新页与对话页共用同一接口。",
        ),
        (
            "Q6：知识图谱用 RAG 还是数据库？",
            "图谱问答是 MySQL + Text2SQL（features/graph/rag.py），返回 related_nodes 供前端高亮。"
            "百科常识才用 Chroma search_heritage。"
            "前端 Three.js 读取 GET /api/graph_data，力导向布局，autocomplete 搜索后相机聚焦。",
        ),
        (
            "Q7：研学报告会不会因图片过大入库失败？",
            "会。故采用：流式先返回完整 JSON；入库前 strip_report_for_storage 剥离创作集 base64，"
            "仅保留作品 id；study_reports.content_json 启动时 ensure_study_reports_schema 升级 LONGTEXT；"
            "读取 latest 时 hydrate_report_artworks 从 user_artworks 回填。user_artworks.image_data 同为 LONGTEXT。",
        ),
        (
            "Q8：答辩现场网络不稳怎么办？",
            "设置 DEMO_MODE=true，识图、焕新、Agent 走 features/demo 预置数据。"
            "焕新有内存 hash 缓存。智谱需检查 API Key IP 白名单或关闭限制。",
        ),
        (
            "Q9：如何体现「非遗研学」而非通用聊天？",
            "使用顺序：地图实地→识图→图谱关系→Agent 讲解→焕新创作→答题→报告→社区打卡。"
            "工具与 Prompt 围绕非遗 POI、条目、传承人设计；profile.py 注入打卡/答题画像。",
        ),
        (
            "Q10：会话标题如何管理？",
            "POST /api/session/create 默认「新对话」。首条用户文字消息后，若标题为占位符，"
            "取消息前 8 字自动命名。PATCH /api/session/<id> 手动重命名（最长 100 字）。"
            "前端 ChatView 侧栏双击或编辑图标调用 updateSessionTitle。",
        ),
        (
            "Q11：地图标点简介 ai_intro 如何生成？",
            "shared/utils.apply_marker_intros 默认批量调用星火；"
            "MARKER_INTRO_PROVIDER=spark（默认）或 qwen（需 DASHSCOPE_API_KEY）。"
            "用于 default_local、识图合并地标、Agent search_places 结果。",
        ),
        (
            "Q12：如何自测推荐链接逻辑？",
            "cd backend_clean && python -m unittest discover -s tests -v。"
            "test_agent_engine 含 infer_suggest_path（如「皮影戏在哪里」→/map）、"
            "enforce_suggest_path 场景。前端可对 Agent 回复点击推荐链接验证跳转。",
        ),
    ]
    for q, a in qa:
        _heading(doc, q, 2)
        _para(doc, f"答：{a}")

    _heading(doc, "附录：推荐链接规范", 1)
    _para(doc, "正确格式示例：")
    _para(doc, "👉 要在地图上查看位置与路线吗？[打开非遗地图](/map)", size=10)
    _para(doc, "合法路径：/map、/source、/graph、/quiz、/revive、/report、/community", size=10, bold=True)

    doc.save(DOC_DIR / "3_时空匠影_AI_Agent赛道专家答辩模拟问答.docx")
    print("OK: 3_时空匠影_AI_Agent赛道专家答辩模拟问答.docx")


def main():
    build_doc1()
    build_doc2()
    build_doc3()


if __name__ == "__main__":
    main()
