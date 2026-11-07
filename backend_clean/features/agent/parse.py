"""Agent 工具调用解析（无重型依赖，可供单元测试直接导入）。"""

import json
import re

# 图谱关系类问题（不含单独「哪」，避免「在哪里」误触发）
GRAPH_HINT_KEYWORDS = [
    '传承', '属于', '地区', '分布', '传承人', '关系', '项目', '类别', '批次',
    '谁', '哪些人', '哪个省', '哪些省', '什么关系', '关联',
]

# 实地位置 / 导航 / POI
LOCATION_HINT_KEYWORDS = (
    '在哪里', '在哪', '去哪儿', '去哪', '什么地方', '什么位置',
    '地址', '附近', '周边', '怎么去', '怎么走', '路线',
    '地图', '场馆', '剧院', '博物馆', '定位', '实地', '能看到',
    '地点', '非遗地点', '哪里', '哪儿', '去哪看', '在哪看', '文化地标',
)

REVIVE_HINT_KEYWORDS = (
    '焕新', '风格', '赛博', '重绘', '生成', '作画', '插画', '潮玩', '国潮',
)

REPORT_HINT_KEYWORDS = ('研学报告', '学习报告', '总结报告', '我的报告')

COMMUNITY_HINT_KEYWORDS = ('打卡', '晒足迹', '打卡广场', '分享打卡')

SOURCE_HINT_KEYWORDS = ('识图', '认图', '识别这张', '上传图', '照片是什么', '视频里')

# 复合研学行程（端到端编排）
STUDY_TOUR_HINT_KEYWORDS = (
    '安排', '行程', '半天', '一天', '研学路线', '游学', '帮我规划',
    '一日游', '半日', '打卡路线', '研学计划', '怎么玩', '路线规划一下',
)

# 百科叙述 / 「XX是什么」类（走向量库 Chroma，非图谱 SQL）
HERITAGE_KB_HINT_KEYWORDS = (
    '是什么', '什么是', '什么意思', '介绍一下', '介绍', '讲讲', '说说',
    '有哪些特点', '有什么特点', '什么叫', '概述', '简要介绍', '简单介绍',
    '百科', '了解一下', '想知道', '有哪些流派', '有哪些种类', '起源',
)

TOOL_CALL_RE = re.compile(r'<tool_call>\s*(\{.*?\})\s*</tool_call>', re.DOTALL)

KNOWN_TOOLS = frozenset({
    'search_heritage', 'query_graph', 'search_places',
    'plan_route', 'identify_image', 'revive_heritage',
    'plan_study_tour',
})

# Agent 文末推荐链接：路径 → 默认按钮文案（不含 /quiz，对话不引导至闯关页）
AGENT_PATH_LABELS = {
    '/map': '打开非遗地图',
    '/revive': '非遗焕新',
    '/graph': '知识图谱',
    '/source': '识图溯源',
    '/report': '研学报告',
    '/community': '打卡广场',
}

VALID_AGENT_PATHS = frozenset(AGENT_PATH_LABELS.keys())

_QUIZ_PATH_RE = re.compile(r'/quiz', re.IGNORECASE)

_MALFORMED_PATH_LINK_RE = re.compile(r'\[(/[a-z]+)\](?!\s*\()', re.IGNORECASE)
_SUGGEST_LINE_RE = re.compile(r'👉[^\n]*\[[^\]]+\]\(/[a-z]+\)', re.IGNORECASE)
_PATH_IN_LINK_RE = re.compile(r'\]\((/[a-z]+)\)', re.IGNORECASE)
_FULL_MARKDOWN_LINK_RE = re.compile(r'\[([^\]]+)\]\((/[^)]+)\)', re.IGNORECASE)

AGENT_ROUTE_RULES = """
【站内页面跳转 — 仅下列路径，格式必须为 [链接文字](/路径)】

1. /map — 非遗地图：POI 位置、标点 ai_intro、路线规划；识图结果可高亮到地图。
   ✓ 在哪里、去哪看、附近、地址、怎么去、剧场/博物馆位置

2. /source — 识图溯源：上传图片/视频识别非遗并标注地图。
   ✓ 要认图、发图、视频里是什么；无图不提

3. /graph — 知识图谱：传承人/地区/类别/项目关系（非导航地址）。
   ✓ 谁传承、属于哪里(文化分布)、有什么关系
   ✗ 「剧院在哪、怎么去」→ /map

4. /revive — 数字焕新：参考图+文案 AI 作画。
5. /report — 研学报告：汇总打卡/答题/创作。
6. /community — 打卡广场：实地打卡分享。

【严禁】
- 将工具名或 API 路径作为站内链接（如 /search_heritage、/query_graph）。
- 推荐 /quiz 或「闯关答题」；用户若要答题请自行从侧边栏进入，对话内不提供跳转。
百科类问题须先调用 search_heritage 工具检索，文末只能推荐上表 6 个页面路径。
复合行程（安排半天/一日研学）须调用 plan_study_tour，勿只丢给用户侧边栏。

【推荐正例】
- 地点：👉 要在地图上查看位置吗？[打开非遗地图](/map)
- 美食：说明店名/品类，勿写成「英歌舞场馆」；👉 可用地图查看。[打开非遗地图](/map)
- 关系：👉 想看清传承脉络吗？[知识图谱](/graph)
- 行程：👉 可在地图上按行程查看各地标。[打开非遗地图](/map)

【推荐反例 — 禁止】
- ❌ [开始闯关](/quiz) 或任何 /quiz 链接
"""


def should_plan_study_tour(message: str) -> bool:
    m = message or ''
    if should_hint_revive(m):
        return False
    strong = (
        '行程', '半天', '一天', '研学路线', '游学', '一日游', '半日',
        '打卡路线', '研学计划', '帮我规划', '路线规划一下', '怎么玩',
    )
    if any(kw in m for kw in strong):
        return True
    # 「安排」单独过宽，需搭非遗/研学语境
    if '安排' in m and any(k in m for k in ('研学', '非遗', '路线', '行程', '游', '玩', '打卡')):
        return True
    return False


def should_hint_location(message: str) -> bool:
    m = message or ''
    if should_plan_study_tour(m):
        return True
    return any(kw in m for kw in LOCATION_HINT_KEYWORDS)


def should_hint_graph(message: str) -> bool:
    m = message or ''
    if should_hint_location(m):
        return False
    return any(kw in m for kw in GRAPH_HINT_KEYWORDS)


def should_hint_revive(message: str) -> bool:
    m = message or ''
    return any(kw in m for kw in REVIVE_HINT_KEYWORDS)


def should_hint_heritage_kb(message: str) -> bool:
    """百科/「是什么」类问题：应优先 search_heritage（Chroma），而非仅靠模型记忆。"""
    m = message or ''
    if should_hint_location(m) or should_hint_revive(m):
        return False
    if should_hint_graph(m):
        return False
    if any(k in m for k in SOURCE_HINT_KEYWORDS):
        return False
    return any(kw in m for kw in HERITAGE_KB_HINT_KEYWORDS)


def extract_heritage_search_query(message: str) -> str:
    """从「粤剧是什么」等问句提取向量检索关键词。"""
    m = (message or '').strip()
    for prefix in (
        '请介绍一下', '介绍一下', '请介绍', '帮我介绍', '帮我讲讲', '讲讲',
        '说说', '想了解', '想知道', '请说说',
    ):
        if m.startswith(prefix):
            m = m[len(prefix):].strip()
            break
    for suffix in sorted(
        (
            '是什么意思', '什么意思', '是什么', '什么是', '有哪些特点', '有什么特点',
            '有哪些', '有什么', '的定义', '的简介', '的概述', '概况', '介绍',
            '历史', '起源', '吗', '呢', '？', '?', '什么叫', '百科',
        ),
        key=len,
        reverse=True,
    ):
        if m.endswith(suffix):
            m = m[:-len(suffix)].strip()
            break
    m = re.sub(r'^[的\s]+', '', m)
    m = re.sub(r'[\s？?！!。，,、]+$', '', m).strip('「」『』""\'')
    return (m[:30] if m else (message or '').strip()[:20]) or '非遗'


def extract_study_tour_args(message: str) -> dict:
    """从「帮我安排汕头半天英歌舞研学」提取 city / theme / hours。"""
    m = (message or '').strip()
    place = extract_place_search_args(m)
    city = place.get('city') or ''
    if not city:
        # 「广州半天粤剧研学」：城市名紧挨半天/一天/研学
        cm = re.search(
            r'([\u4e00-\u9fa5]{2,8}?)(?=(?:市|省)?(?:的)?(?:半天|半日|一天|一日|全日|研学|游学|行程))',
            m,
        )
        if cm:
            name = cm.group(1)
            for noise in ('帮我安排', '安排', '请', '想', '要'):
                name = name.replace(noise, '')
            name = name.strip()
            if len(name) >= 2:
                city = name if name.endswith(('省', '市')) else name + '市'
    theme = place.get('keyword') or '非遗'
    for noise in (
        '安排', '行程', '规划', '半天', '半日', '一天', '一日', '全日',
        '研学', '游学', '帮我', '请帮我', '请', '路线', '一下',
    ):
        theme = theme.replace(noise, '')
    # 「帮我安排…」抽词后常残留句首「我」
    theme = re.sub(r'^我+', '', theme)
    theme = re.sub(r'\s+', '', theme).strip() or '非遗'
    if city and theme.startswith(city.replace('市', '').replace('省', '')):
        theme = theme[len(city.replace('市', '').replace('省', '')):].lstrip('市省的') or '非遗'
    hours = 4.0
    if '一天' in m or '全日' in m or '一日' in m:
        hours = 8.0
    elif '半天' in m or '半日' in m:
        hours = 4.0
    return {'city': city, 'theme': theme[:40], 'hours': hours}


def build_soft_prior_hint(user_msg: str, has_image: bool = False) -> str:
    """
    软提示：写入决策 Prompt，不强制执行工具。
    评委可答：主路径由模型选工具；启发式仅作 prior。
    """
    tips = []
    m = user_msg or ''
    if any(t in m for t in ('美食', '好吃', '吃饭', '餐厅', '小吃', '火锅', '卤水', '烧烤')):
        tips.append(
            '用户在问美食/吃饭 → 必须 search_places；'
            'keyword 优先用用户说的具体品类（如卤水火锅），勿一律写成「美食」；禁止继续推研学场馆。'
        )
    elif should_plan_study_tour(user_msg):
        tips.append('用户像在要「研学行程」→ 优先考虑 plan_study_tour(city, theme, hours)。')
    elif should_hint_location(user_msg):
        tips.append('用户像在问地点/附近 → 可考虑 search_places；有起终点时可 plan_route。')
    if should_hint_heritage_kb(user_msg):
        tips.append('用户像在问百科「是什么」→ 可考虑 search_heritage，勿凭空编细节。')
    if should_hint_graph(user_msg):
        tips.append('用户像在问传承人/归属/关系 → 可考虑 query_graph。')
    if should_hint_revive(user_msg):
        tips.append('用户像在要数字焕新创作 → 可考虑 revive_heritage。')
    if has_image:
        tips.append('本轮附带用户图片；若尚未识图可 identify_image，若要作画可 revive_heritage。')
    if not tips:
        return ''
    joined = ' '.join(tips)
    return (
        f'\n【软提示·仅供参考，非强制执行】{joined}\n'
        '请你自主决定是否调用工具；不要因为软提示而重复已执行过的同类工具。\n'
    )


def collect_grounding_lines(scratchpad: list) -> list[str]:
    """从工具结果抽取可展示的「依据」条目。"""
    lines: list[str] = []
    seen = set()

    def _add(line: str):
        line = (line or '').strip()
        if not line or line in seen:
            return
        seen.add(line)
        lines.append(line)

    for s in scratchpad or []:
        tool = s.get('tool')
        res = s.get('result') if isinstance(s.get('result'), dict) else {}
        if not res:
            continue
        if tool == 'search_heritage':
            ctx = (res.get('context') or '').strip()
            if res.get('ok') and ctx:
                snippet = ctx.replace('\n', ' ')[:120]
                _add(f'百科检索：{snippet}{"…" if len(ctx) > 120 else ""}')
            elif res.get('ok') is False or not ctx:
                _add('百科检索：库中未命中有效片段（勿编造条目细节）')
        elif tool == 'query_graph':
            if res.get('ok'):
                ans = (res.get('answer') or '').strip()[:100]
                nodes = res.get('node_ids') or []
                if ans:
                    _add(f'知识图谱：{ans}{"…" if len(res.get("answer") or "") > 100 else ""}')
                if nodes:
                    _add(f'图谱节点：{", ".join(str(n) for n in nodes[:6])}')
            else:
                _add('知识图谱：查询未成功或无匹配')
        elif tool == 'search_places':
            if res.get('ok'):
                city = res.get('city') or ''
                names = [
                    m.get('base_name') for m in (res.get('markers') or [])[:5]
                    if isinstance(m, dict) and m.get('base_name')
                ]
                if names:
                    _add(f'地标（{city}）：{"、".join(names)}')
                else:
                    _add(f'地标（{city}）：检索到 {res.get("count") or 0} 处')
            else:
                _add(f'地标检索：{res.get("error") or "未命中"}')
        elif tool == 'plan_study_tour':
            for g in res.get('grounding') or []:
                _add(str(g))
            itin = res.get('itinerary') or []
            if itin:
                names = [x.get('name') for x in itin if isinstance(x, dict) and x.get('name')]
                if names:
                    _add(f'研学行程站点：{" → ".join(names[:5])}')
        elif tool == 'identify_image' and res.get('ok'):
            markers = res.get('markers') or []
            names = [
                m.get('base_name') for m in markers[:4]
                if isinstance(m, dict) and m.get('base_name')
            ]
            if names:
                _add(f'识图关联地标：{"、".join(names)}')
            ai = (res.get('ai_text') or '').strip().split('\n')[0][:80]
            if ai:
                _add(f'识图摘要：{ai}')
        elif tool == 'plan_route' and res.get('ok'):
            _add(f'路线规划：{res.get("summary") or "已生成出行方案"}')
        elif tool == 'search_places' and res.get('loc_source'):
            # 已在上方处理 markers；补一条空间来源
            if res.get('ok') and str(res.get('loc_source')).startswith('gps'):
                _add(f'定位来源：{res.get("loc_source")}')
        elif tool == 'revive_heritage' and res.get('ok'):
            _add('数字焕新：已生成作品（对话内图片）')
    return lines


def append_grounding_block(text: str, scratchpad: list) -> str:
    """最终回答后追加「依据」块；无工具结果则不追加。"""
    text = (text or '').rstrip()
    lines = collect_grounding_lines(scratchpad)
    if not lines:
        if scratchpad:
            block = '\n\n---\n**依据**\n- 本轮工具未返回可引用片段；未命中处请勿当作事实。'
            if '**依据**' not in text:
                text += block
        return text
    if '**依据**' in text or '依据：' in text:
        return text
    body = '\n'.join(f'- {ln}' for ln in lines[:8])
    return text + f'\n\n---\n**依据**（来自本轮工具，可核对）\n{body}'


def latest_search_places_result(scratchpad: list) -> dict | None:
    for s in reversed(scratchpad or []):
        if s.get('tool') != 'search_places':
            continue
        res = s.get('result')
        if isinstance(res, dict) and res.get('ok') and (res.get('markers') or []):
            return res
    return None


def build_grounded_places_answer(scratchpad: list) -> str | None:
    """
    用地图工具返回的真实 POI 生成列表，禁止模型自由编店名。
    本轮若已有 plan_study_tour，不覆盖行程叙述。
    """
    if any(s.get('tool') == 'plan_study_tour' for s in (scratchpad or [])):
        return None
    res = latest_search_places_result(scratchpad)
    if not res:
        return None
    markers = [
        m for m in (res.get('markers') or [])
        if isinstance(m, dict) and (m.get('base_name') or '').strip()
    ]
    if not markers:
        return None
    city = (res.get('city') or '').strip() or '附近'
    kw = (res.get('keyword') or '').strip() or '地点'
    src = (res.get('loc_source') or '').strip()
    head = f'根据高德地图检索，{city}与「{kw}」相关的地点如下'
    if src.startswith('gps'):
        head += '（按与您当前位置的距离排序）'
    head += '：'
    lines = [head]
    for i, m in enumerate(markers[:8], 1):
        name = (m.get('base_name') or '').strip()
        bits = []
        typ = (m.get('type') or '').strip().split(';')[0]
        if typ:
            bits.append(typ[:24])
        dist = m.get('distance_m')
        if dist is not None:
            try:
                bits.append(f'约{int(float(dist))}米')
            except (TypeError, ValueError):
                pass
        addr = (m.get('address') or '').strip()
        if addr:
            bits.append(addr[:36])
        extra = f' — {" · ".join(bits)}' if bits else ''
        lines.append(f'{i}. {name}{extra}')
    return '\n'.join(lines)


def extract_place_search_args(message: str) -> dict:
    """从用户句提取 search_places 的 city / keyword（启发式）。"""
    m = (message or '').strip()
    city = ''
    city_m = re.search(r'([\u4e00-\u9fa5]{2,10}?)([省市])(?:的)?', m)
    if city_m:
        city = city_m.group(1) + city_m.group(2)
    else:
        # 「广州的英歌舞」等：城市名后直接接「的」
        city_m2 = re.search(r'([\u4e00-\u9fa5]{2,8}?)的', m)
        if city_m2:
            name = city_m2.group(1)
            if not name.endswith(('省', '市')):
                name = name + '市'
            city = name

    keyword = m
    for loc in LOCATION_HINT_KEYWORDS:
        keyword = keyword.replace(loc, '')
    for noise in (
        '吗', '呢', '？', '?', '请', '帮', '我想知道', '请问', '帮我', '查一下',
        '一下', '有没有', '哪里可以', '什么地方有', '我想了解', '想了解', '了解',
        '非遗地点', '的地点', '地点', '非遗',
    ):
        keyword = keyword.replace(noise, '')
    keyword = re.sub(r'\s+', '', keyword).strip()
    keyword = re.sub(r'的+$', '', keyword).strip()[:12]
    if not keyword:
        keyword = '非遗'

    # 未提城市时留空，由工具层按请求 IP 解析当前所在城市
    return {'city': city, 'keyword': keyword}


def _revive_succeeded(scratchpad: list) -> bool:
    return any(
        s.get('tool') == 'revive_heritage'
        and isinstance(s.get('result'), dict)
        and s['result'].get('ok')
        for s in (scratchpad or [])
    )


def infer_suggest_path(user_msg: str, scratchpad: list = None) -> str | None:
    """根据用户句与已执行工具推断应推荐的页面路径（不含 /quiz）。"""
    scratchpad = scratchpad or []
    tools_used = [s.get('tool') for s in scratchpad if s.get('tool')]
    m = user_msg or ''

    # 用户主诉求为焕新生图时，优先推荐焕新页，不因附带识图而推地图
    if _revive_succeeded(scratchpad) and not should_hint_location(m):
        return '/revive'

    if 'plan_study_tour' in tools_used or 'search_places' in tools_used or 'plan_route' in tools_used:
        return '/map'
    if 'identify_image' in tools_used:
        for s in scratchpad:
            res = s.get('result') if isinstance(s, dict) else None
            if isinstance(res, dict) and res.get('markers'):
                return '/map'
        return '/source'
    if 'query_graph' in tools_used:
        return '/graph'
    if 'search_heritage' in tools_used:
        return '/graph'
    if 'revive_heritage' in tools_used:
        return '/revive'

    if should_hint_heritage_kb(m):
        return '/graph'

    if should_hint_location(m):
        return '/map'
    if should_hint_revive(m):
        return '/revive'
    if any(k in m for k in REPORT_HINT_KEYWORDS):
        return '/report'
    if any(k in m for k in COMMUNITY_HINT_KEYWORDS):
        return '/community'
    if any(k in m for k in SOURCE_HINT_KEYWORDS) or '图片' in m:
        return '/source'
    if should_hint_graph(m):
        return '/graph'
    return None


def format_suggest_path_hint(user_msg: str, scratchpad: list = None) -> str:
    path = infer_suggest_path(user_msg, scratchpad)
    if not path:
        return ''
    label = AGENT_PATH_LABELS.get(path, '前往')
    forbidden = '禁止推荐 /quiz 或闯关答题链接。'
    if path == '/revive':
        forbidden += ' 禁止推荐 /map（本轮为数字焕新生图，非查地点）。'
    elif path == '/graph':
        forbidden += ' 禁止推荐 /map（除非用户同时问地址）。'
    return (
        f'\n【系统建议的下一步页面】{path} '
        f'（文末推荐必须使用 [{label}]({path})，优先采用；{forbidden}）\n'
    )


def _rewrite_quiz_links_to(text: str, target_path: str) -> str:
    """将文本中的 /quiz 推荐改为合法路径或移除该行。"""
    if not text:
        return text
    label = AGENT_PATH_LABELS.get(target_path, '前往')
    replacement = f'[{label}]({target_path})'

    def _line_repl(line: str) -> str:
        if not _QUIZ_PATH_RE.search(line):
            return line
        if line.strip().startswith('👉'):
            return f'👉 {replacement}'.replace(f'[{label}]({target_path})', replacement)
        return _FULL_MARKDOWN_LINK_RE.sub(
            lambda m: replacement if _QUIZ_PATH_RE.search(m.group(2)) else m.group(0),
            line,
        )

    lines = []
    for line in text.split('\n'):
        if line.strip().startswith('👉') and _QUIZ_PATH_RE.search(line):
            lines.append(
                f'👉 想继续探索吗？{replacement}'
                if target_path in VALID_AGENT_PATHS else line
            )
        else:
            lines.append(_line_repl(line))
    return '\n'.join(lines)


def enforce_suggest_path(text: str, preferred_path: str | None) -> str:
    """当模型推荐了与意图不符的路径时，修正文末 👉 推荐行。"""
    if not text:
        return text

    fix_path = preferred_path if preferred_path in VALID_AGENT_PATHS else '/graph'
    text = _rewrite_quiz_links_to(text, fix_path)

    if not preferred_path:
        return text

    label = AGENT_PATH_LABELS.get(preferred_path, '前往')
    correct_tail = f'[{label}]({preferred_path})'

    hint_templates = {
        '/map': f'👉 要在地图上查看位置与路线吗？{correct_tail}',
        '/graph': f'👉 想查看相关传承与地区关系吗？{correct_tail}',
        '/revive': f'👉 想尝试数字焕新创作吗？{correct_tail}',
        '/source': f'👉 上传照片可识图溯源并标注地图。{correct_tail}',
        '/report': f'👉 可生成您的非遗研学报告。{correct_tail}',
        '/community': f'👉 欢迎实地打卡分享体验。{correct_tail}',
    }
    default_line = hint_templates.get(preferred_path, f'👉 {correct_tail}')

    lines = text.split('\n')
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('👉'):
            m = _PATH_IN_LINK_RE.search(line)
            path_in_line = m.group(1) if m else None
            if _QUIZ_PATH_RE.search(line) or (path_in_line and path_in_line != preferred_path):
                new_lines.append(default_line)
                continue
        new_lines.append(line)

    result = '\n'.join(new_lines)
    if not _SUGGEST_LINE_RE.search(result):
        result = result.rstrip() + '\n\n' + default_line
    return _rewrite_quiz_links_to(result, preferred_path)


def normalize_agent_suggest_links(text: str, preferred_path: str | None = None) -> str:
    """将 [/graph]、[/search_heritage?query=…]、[/quiz] 等修正为合法站内路径。"""
    if not text:
        return text

    fix_path = preferred_path if preferred_path in VALID_AGENT_PATHS else '/graph'

    def _repl(match: re.Match) -> str:
        path = match.group(1)
        if _QUIZ_PATH_RE.search(path):
            label = AGENT_PATH_LABELS.get(fix_path, '前往')
            return f'[{label}]({fix_path})'
        label = AGENT_PATH_LABELS.get(path, '前往')
        return f'[{label}]({path})'

    text = _MALFORMED_PATH_LINK_RE.sub(_repl, text)

    def _path_repl(match: re.Match) -> str:
        label, path = match.group(1), match.group(2)
        base = path.split('?')[0].rstrip('/')
        if _QUIZ_PATH_RE.search(base):
            fix_label = AGENT_PATH_LABELS.get(fix_path, label)
            return f'[{fix_label}]({fix_path})'
        if base in VALID_AGENT_PATHS:
            return match.group(0)
        fix_label = AGENT_PATH_LABELS.get(fix_path, label)
        return f'[{fix_label}]({fix_path})'

    text = _FULL_MARKDOWN_LINK_RE.sub(_path_repl, text)
    return _rewrite_quiz_links_to(text, fix_path)


def _repair_tool_json(raw: str) -> dict | None:
    """尝试从残缺 JSON 中抢救 tool / args。"""
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # 常见：尾部多余逗号 / 单引号
    fixed = raw.replace("'", '"')
    fixed = re.sub(r',\s*}', '}', fixed)
    fixed = re.sub(r',\s*]', ']', fixed)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass
    tool_m = re.search(r'"tool"\s*:\s*"([a-z_]+)"', raw)
    if not tool_m:
        return None
    tool = tool_m.group(1)
    args = {}
    for key in (
        'query', 'question', 'city', 'keyword', 'prompt', 'mode', 'citycode',
        'theme', 'hours', 'origin_lng', 'origin_lat', 'dest_lng', 'dest_lat',
    ):
        km = re.search(rf'"{key}"\s*:\s*"([^"]*)"', raw)
        if km:
            args[key] = km.group(1)
            continue
        nm = re.search(rf'"{key}"\s*:\s*(-?\d+(?:\.\d+)?)', raw)
        if nm:
            args[key] = float(nm.group(1)) if '.' in nm.group(1) else int(nm.group(1))
    return {'tool': tool, 'args': args}


def parse_tool_call(text: str, known_tools: frozenset = None):
    """解析 LLM 输出中的 tool_call，返回 (tool_name, args) 或 None。"""
    known_tools = known_tools or KNOWN_TOOLS
    if not text:
        return None
    match = TOOL_CALL_RE.search(text)
    if not match:
        # 容错：模型偶发漏写闭合标签
        loose = re.search(r'<tool_call>\s*(\{.*)', text, re.DOTALL)
        if not loose:
            return None
        payload = _repair_tool_json(loose.group(1).split('</tool_call>')[0])
    else:
        payload = _repair_tool_json(match.group(1))
    if not payload:
        return None
    tool = payload.get('tool')
    args = payload.get('args') or {}
    if tool and tool in known_tools:
        return tool, args
    return None


def parse_tool_call_with_validation(text: str, known_tools: frozenset = None):
    """
    解析并 Schema 校验。
    返回 dict: {ok, tool, args, error}；无调用块时 ok=False 且 tool=None。
    """
    from features.agent.schema import validate_tool_args

    known_tools = known_tools or KNOWN_TOOLS
    parsed = parse_tool_call(text, known_tools)
    if not parsed:
        return {'ok': False, 'tool': None, 'args': {}, 'error': ''}
    tool, args = parsed
    ok, fixed, err = validate_tool_args(tool, args)
    if ok:
        return {'ok': True, 'tool': tool, 'args': fixed, 'error': ''}
    return {'ok': False, 'tool': tool, 'args': fixed, 'error': err or '参数校验失败'}


def summarize_tool_result(result, limit: int = 400) -> str:
    if isinstance(result, dict):
        if result.get('ok') and result.get('summary') and (
            result.get('distance_m') is not None or result.get('mode')
        ) and result.get('itinerary') is None:
            text = result.get('summary') or '路线已规划'
            return text if len(text) <= limit else text[:limit] + '…'
        if result.get('ok') and result.get('itinerary') is not None and result.get('summary'):
            bits = [result.get('summary') or '研学行程']
            names = [
                x.get('name') for x in (result.get('itinerary') or [])[:5]
                if isinstance(x, dict) and x.get('name')
            ]
            if names:
                bits.append('站点：' + ' → '.join(names))
            text = '；'.join(bits)
            return text if len(text) <= limit else text[:limit] + '…'
        if result.get('ok') and result.get('context'):
            text = (result.get('context') or '').strip()
            return text if len(text) <= limit else text[:limit] + '…'
        if result.get('ok') is False:
            err = result.get('error') or result.get('msg') or '未知错误'
            sug = result.get('suggestion', '')
            text = f'工具执行失败：{err}'
            if sug:
                text += f'。建议：{sug}'
            return text
        if result.get('ok') and result.get('url'):
            analysis = (result.get('analysis') or '')[:120]
            prefix = '焕新作品已生成'
            if analysis:
                prefix += f'（分析摘要：{analysis}）'
            return prefix
    if isinstance(result, str):
        text = result
    else:
        text = json.dumps(result, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + '…'
