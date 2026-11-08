"""会话级记忆与研学目标状态（可注入 Agent Prompt、可持久化）。"""

from __future__ import annotations

import json
import re
from datetime import datetime

from features.agent.parse import (
    extract_heritage_search_query,
    extract_place_search_args,
    extract_study_tour_args,
    should_hint_heritage_kb,
    should_hint_location,
    should_plan_study_tour,
)
from shared.utils import _POI_OPEN_INTENT_TOKENS

# 用户主动结束 / 切换
_END_GOAL_RE = re.compile(
    r'(不想|不要|结束|算了|换个主题|换主题|不做了|不做.{0,12}了|取消研学|先聊别的)',
)
_SWITCH_THEME_RE = re.compile(
    r'(改成|换成|改为|换成做|改做)([\u4e00-\u9fa5]{2,12})',
)

# 非地点类跑题（与地图 open 意图词表对齐后再并入）
_OFF_GOAL_EXTRA = (
    '好吃', '吃饭', '宵夜', '住宿', '天气', '机票', '车票', '快递',
)
_OFF_GOAL_TOKENS = tuple(dict.fromkeys(
    list(_POI_OPEN_INTENT_TOKENS) + list(_OFF_GOAL_EXTRA)
))

# 可向左扩展修饰语的锚点（抽「卤水火锅」而非只剩「火锅」）
_OPEN_EXPAND_ANCHORS = (
    '火锅', '烧烤', '肠粉', '鹅肉', '奶茶', '咖啡', '小吃',
    '餐厅', '饭店', '酒店', '宾馆', '民宿', '客栈',
)
_OPEN_LEAD_NOISE = (
    '附近的', '附近有没有', '附近有', '附近', '帮我找一下', '帮我找', '帮我',
    '我想吃', '我想要', '我想', '想吃', '我找', '找一下', '有没有',
    '哪里有', '哪里可以', '请给我', '给我', '找', '吃', '请', '的', '我',
)


def message_diverges_from_goal(user_msg: str, theme: str | None = None) -> bool:
    """本轮是否明确在问与研学主题无关的事。"""
    m = user_msg or ''
    theme = (theme or '').strip()
    if theme and theme in m:
        return False
    return any(tok in m for tok in _OFF_GOAL_TOKENS)


def message_continues_goal(user_msg: str, theme: str | None = None) -> bool:
    """含糊续问（附近还有吗）且未改话题 → 可沿用主题。"""
    m = user_msg or ''
    if message_diverges_from_goal(m, theme):
        return False
    theme = (theme or '').strip()
    if theme and theme in m:
        return True
    return any(
        k in m for k in (
            '附近还有', '相关的地方', '还有吗', '下一站', '怎么去', '路线',
            '继续安排', '继续', '场馆', '打卡', '研学',
        )
    )


def extract_open_place_keyword(user_msg: str) -> str:
    """
    从跑题问句抽地点检索词：优先具体品类短语（卤水火锅），
    勿一律截成「美食/火锅」。
    """
    m = (user_msg or '').strip()
    if not m:
        return ''

    # 1) 锚点向左扩展：潮汕卤水火锅 / 牛肉火锅
    for anchor in sorted(_OPEN_EXPAND_ANCHORS, key=len, reverse=True):
        idx = m.find(anchor)
        if idx < 0:
            continue
        start = idx
        while start > 0 and '\u4e00' <= m[start - 1] <= '\u9fff' and (idx - (start - 1)) <= 6:
            start -= 1
        span = m[start:idx + len(anchor)]
        changed = True
        while changed and span:
            changed = False
            for noise in _OPEN_LEAD_NOISE:
                if span.startswith(noise):
                    span = span[len(noise):]
                    changed = True
        if span:
            return span[:16]

    # 2) 整词命中 open 意图表（长词优先）
    for tok in sorted(_POI_OPEN_INTENT_TOKENS, key=len, reverse=True):
        if tok in m:
            return tok[:16]

    # 3) 口语 → 美食；其余 off-goal 原样返回（天气等）
    if any(t in m for t in ('好吃', '吃饭', '美食', '宵夜')):
        return '美食'
    for tok in _OFF_GOAL_EXTRA:
        if tok in m:
            return tok
    return ''


def empty_memory() -> dict:
    """返回一份空的会话记忆结构。"""
    return {
        'goal': None,           # 如「正在做英歌舞研学」
        'goal_status': 'idle',  # idle | active | done
        'theme': None,
        'city': None,
        'itinerary': [],        # [{name, address?, distance_m?}]
        'places': [],           # 本会话提到/检索到的地标名
        'asked': [],            # 近期用户问句摘要
        'notes': [],            # 短事实备忘
        'updated_at': None,
    }


def load_memory_json(raw: str | None) -> dict:
    """从数据库 JSON 文本恢复会话记忆；内容损坏时回退为空结构。"""
    mem = empty_memory()
    if not (raw or '').strip():
        return mem
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return mem
    if not isinstance(data, dict):
        return mem
    mem.update({k: data.get(k, mem[k]) for k in mem})
    if not isinstance(mem.get('itinerary'), list):
        mem['itinerary'] = []
    if not isinstance(mem.get('places'), list):
        mem['places'] = []
    if not isinstance(mem.get('asked'), list):
        mem['asked'] = []
    if not isinstance(mem.get('notes'), list):
        mem['notes'] = []
    return mem


def dump_memory_json(mem: dict) -> str:
    """序列化会话记忆，并刷新 updated_at 时间戳。"""
    payload = empty_memory()
    payload.update(mem or {})
    payload['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return json.dumps(payload, ensure_ascii=False)


def memory_public_view(mem: dict | None) -> dict | None:
    """给前端的轻量视图；paused 时不展示强目标条，避免误导。"""
    mem = mem or {}
    if mem.get('goal_status') != 'active' or not mem.get('goal'):
        return None
    stops = [
        (s.get('name') if isinstance(s, dict) else None)
        for s in (mem.get('itinerary') or [])[:5]
    ]
    stops = [n for n in stops if n]
    return {
        'goal': mem.get('goal'),
        'theme': mem.get('theme'),
        'city': mem.get('city'),
        'stops': stops,
        'status': mem.get('goal_status'),
    }


def format_session_memory_block(mem: dict | None, user_msg: str = '') -> str:
    """注入决策 Prompt：让模型接住研学目标，但允许明确跑题。"""
    mem = mem or {}
    diverge = message_diverges_from_goal(user_msg, mem.get('theme'))

    if mem.get('goal_status') == 'paused' or diverge:
        lines = ['【本会话记忆】']
        if mem.get('goal'):
            lines.append(f"- 先前研学目标（已让路）：{mem.get('goal')}")
        lines.append(
            '- 用户本轮明确在问其它事（如美食/吃饭）。'
            '必须按新意图回答：用 search_places 检索对应关键词（如「美食」），'
            '禁止再推英歌/研学场馆，除非用户又提起该主题。'
        )
        return '\n' + '\n'.join(lines) + '\n'

    if mem.get('goal_status') != 'active' or not mem.get('goal'):
        asked = mem.get('asked') or []
        places = mem.get('places') or []
        if not asked and not places:
            return ''
        lines = ['【本会话记忆】']
        if asked:
            lines.append('- 近期问过：' + '；'.join(asked[:3]))
        if places:
            lines.append('- 提过的地标：' + '、'.join(places[:6]))
        lines.append('回答时可自然承接上文，勿假装用户没提过。')
        return '\n' + '\n'.join(lines) + '\n'

    lines = [
        '【本会话记忆·研学目标】',
        f"- 当前目标：{mem.get('goal')}（含糊续问时可承接；用户改问美食等则必须改答）",
    ]
    if mem.get('theme'):
        lines.append(f"- 主题：{mem['theme']}")
    if mem.get('city'):
        lines.append(f"- 城市：{mem['city']}")
    stops = [
        s.get('name') for s in (mem.get('itinerary') or [])
        if isinstance(s, dict) and s.get('name')
    ]
    if stops:
        lines.append('- 已安排站点：' + ' → '.join(stops[:5]))
    places = mem.get('places') or []
    if places:
        lines.append('- 已检索地标：' + '、'.join(places[:8]))
    asked = mem.get('asked') or []
    if asked:
        lines.append('- 用户近期问过：' + '；'.join(asked[:3]))
    lines.append(
        '含糊问「附近还有吗」时可围绕上述主题；'
        '一旦出现美食/吃饭等明确新意图，立即切换，勿强行拉回研学场馆。'
    )
    return '\n' + '\n'.join(lines) + '\n'


def _push_unique(lst: list, item: str, limit: int = 12):
    item = (item or '').strip()
    if not item:
        return
    if item in lst:
        lst.remove(item)
    lst.insert(0, item)
    del lst[limit:]


def _set_active_goal(mem: dict, theme: str, city: str = ''):
    theme = (theme or '').strip() or '非遗'
    theme = re.sub(r'^我+', '', theme).strip() or '非遗'
    city = (city or '').strip()
    mem['theme'] = theme
    if city:
        mem['city'] = city
    mem['goal'] = f'正在做{theme}研学'
    mem['goal_status'] = 'active'


def update_memory_from_turn(
    mem: dict,
    user_msg: str,
    scratchpad: list | None = None,
) -> dict:
    """
    根据本轮用户话 + 工具结果更新会话记忆。
    规则可解释：行程工具 / 研学意图 → 激活目标；结束话术 → 收束。
    """
    mem = load_memory_json(dump_memory_json(mem))  # normalize
    msg = (user_msg or '').strip()
    scratchpad = scratchpad or []

    if msg and not msg.startswith('['):
        _push_unique(mem['asked'], msg[:60], limit=5)

    # 明确跑题（美食等）：暂停研学目标，避免工具层继续注入旧主题
    if msg and message_diverges_from_goal(msg, mem.get('theme')):
        if mem.get('goal_status') == 'active':
            mem['goal_status'] = 'paused'
            _push_unique(mem['notes'], f"暂离研学，改问：{msg[:40]}", limit=6)
        open_kw = extract_open_place_keyword(msg)
        if open_kw:
            _push_unique(mem['notes'], f'临时关注：{open_kw}', limit=6)
        # 不 return：仍可吸收本轮工具结果
    elif msg and mem.get('goal_status') == 'paused' and message_continues_goal(msg, mem.get('theme')):
        # 又聊回研学主题 → 恢复
        mem['goal_status'] = 'active'

    # 结束目标
    if msg and _END_GOAL_RE.search(msg):
        if mem.get('goal_status') in ('active', 'paused'):
            mem['goal_status'] = 'done'
            mem['notes'] = (mem.get('notes') or [])[:4]
            _push_unique(mem['notes'], f"用户结束目标：{mem.get('goal') or ''}", limit=6)
        return mem

    # 显式换主题
    if msg:
        sw = _SWITCH_THEME_RE.search(msg)
        if sw:
            theme = sw.group(2).strip()
            for noise in ('研学', '行程', '的', '一下'):
                theme = theme.replace(noise, '')
            if theme:
                _set_active_goal(mem, theme, mem.get('city') or '')
                mem['itinerary'] = []

    # 工具结果优先
    for s in scratchpad:
        tool = s.get('tool')
        res = s.get('result') if isinstance(s.get('result'), dict) else {}
        if tool == 'plan_study_tour' and res.get('ok'):
            theme = (res.get('theme') or extract_study_tour_args(msg).get('theme') or '非遗')
            city = res.get('city') or ''
            if not message_diverges_from_goal(msg, theme):
                _set_active_goal(mem, theme, city)
            itin = []
            for stop in res.get('itinerary') or []:
                if not isinstance(stop, dict) or not stop.get('name'):
                    continue
                itin.append({
                    'name': stop['name'],
                    'address': stop.get('address') or '',
                    'distance_m': stop.get('distance_m'),
                })
                _push_unique(mem['places'], stop['name'], limit=12)
            if itin:
                mem['itinerary'] = itin
            if res.get('summary'):
                _push_unique(mem['notes'], (res.get('summary') or '')[:80], limit=6)
        elif tool == 'search_places' and res.get('ok'):
            kw = (res.get('keyword') or '').strip()
            city = (res.get('city') or '').strip()
            if city:
                mem['city'] = city
            for m in (res.get('markers') or [])[:8]:
                if isinstance(m, dict) and m.get('base_name'):
                    _push_unique(mem['places'], m['base_name'], limit=12)
            # 美食等临时检索不升级成「正在做美食研学」
            if kw and kw != '非遗' and kw not in _OFF_GOAL_TOKENS and '美食' not in kw:
                if mem.get('goal_status') not in ('active', 'paused'):
                    _set_active_goal(mem, kw, city)
                elif mem.get('goal_status') == 'active' and not mem.get('theme'):
                    mem['theme'] = kw
        elif tool == 'search_heritage' and res.get('ok'):
            args = s.get('args') if isinstance(s.get('args'), dict) else {}
            q = (args.get('query') or '').strip()
            if q and mem.get('goal_status') not in ('active', 'paused') and not message_diverges_from_goal(msg, q):
                _set_active_goal(mem, q[:20], mem.get('city') or '')
            elif q and mem.get('goal_status') == 'active':
                _push_unique(mem['notes'], f'检索过百科：{q}', limit=6)

    # 无工具但话术像研学 → 预激活目标（下一轮工具可对齐）
    # 美食等跑题不预激活，避免「正在做找的美食研学」
    if (
        mem.get('goal_status') != 'active'
        and msg
        and not message_diverges_from_goal(msg, mem.get('theme'))
    ):
        if should_plan_study_tour(msg):
            args = extract_study_tour_args(msg)
            _set_active_goal(mem, args.get('theme') or '非遗', args.get('city') or '')
        elif should_hint_location(msg):
            args = extract_place_search_args(msg)
            kw = (args.get('keyword') or '').strip()
            if (
                kw
                and kw not in ('非遗', '安排', '行程')
                and kw not in _OFF_GOAL_TOKENS
                and '美食' not in kw
            ):
                _set_active_goal(mem, kw, args.get('city') or '')
        elif should_hint_heritage_kb(msg):
            q = extract_heritage_search_query(msg)
            if q and q != '非遗':
                # 百科问答：记为关注主题，但不强行写「正在做X研学」除非已有行程语境
                if '研学' in msg or '行程' in msg:
                    _set_active_goal(mem, q, mem.get('city') or '')
                else:
                    mem['theme'] = mem.get('theme') or q
                    _push_unique(mem['notes'], f'关注：{q}', limit=6)

    return mem
