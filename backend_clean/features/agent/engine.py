"""轻量多步 Agent：模型决策选工具 → 观察 → 再决策；启发式仅作软提示/降级兜底。"""

import json
import logging
import time

from core.config import Config
from features.agent.memory import (
    dump_memory_json,
    empty_memory,
    extract_open_place_keyword,
    format_session_memory_block,
    load_memory_json,
    memory_public_view,
    message_continues_goal,
    message_diverges_from_goal,
    update_memory_from_turn,
)
from features.agent.parse import (
    AGENT_ROUTE_RULES,
    append_grounding_block,
    build_grounded_places_answer,
    build_soft_prior_hint,
    enforce_suggest_path,
    extract_heritage_search_query,
    extract_place_search_args,
    extract_study_tour_args,
    format_suggest_path_hint,
    infer_suggest_path,
    normalize_agent_suggest_links,
    parse_tool_call_with_validation,
    should_hint_graph,
    should_hint_heritage_kb,
    should_hint_location,
    should_hint_revive,
    should_plan_study_tour,
    summarize_tool_result,
)
from features.agent.profile import build_user_profile, format_user_profile_block
from features.agent.schema import format_tool_catalog
from features.agent.tools import TOOL_REGISTRY, execute_tool, iter_revive_heritage, tool_label
from features.demo.service import get_demo_chat_reply
from features.revive.artwork import save_user_artwork
from shared.utils import (
    _query_search_intent,
    format_spark_user_error,
    strip_legacy_spark_error_text,
    sync_spark_call_meta,
)

logger = logging.getLogger(__name__)

MAX_ROUNDS = 6

_TOOL_USAGE_RULES = """
工具选用补充：
- 「XX是什么」「介绍一下XX」→ search_heritage；勿编造条目细节。
- 「在哪里」「附近」「场馆地址」→ search_places（有 GPS 时传 lng/lat；系统也会自动注入）。
- 「怎么去」「路线」「导航」且已有目标坐标 → plan_route（起点可省略，用用户 GPS）。
- 传承人/归属/关系 → query_graph；勿用图谱代替导航地址。
- 「安排半天/一日研学行程」→ plan_study_tour（并行地标+百科+图谱；有 GPS 会按距离排序并规划到首站）。
- 有用户图片且需认图 → identify_image；要作画 → revive_heritage。
- 已有工具结果且足够回答时，直接自然语言回复，勿重复同类工具。
"""

AGENT_SYSTEM = f"""你是「时空匠影」非遗研学工作站的多能力 Agent。
需要外部数据时，输出且仅输出一个工具调用块：
<tool_call>
{{"tool": "工具名", "args": {{ ... }}}}
</tool_call>

可用工具：
{format_tool_catalog()}

{_TOOL_USAGE_RULES}

规则：
1. 每次最多调用 1 个工具，等待结果后再决定下一步（plan_study_tour 内部可并行子检索）。
2. 信息足够时直接自然语言回答（不要输出 tool_call）。
3. 回答须依据工具数据；工具 ok:false 或未命中时要说明，勿编造。
4. 最终回答中用要点引用工具事实；系统会自动附「依据」块。
5. 文末 1 行主动推荐：👉 引导语？[链接文字](/路径)
6. 焕新成功后简述思路，并提示可在对话中查看图片。

{AGENT_ROUTE_RULES}"""


class HeritageAgent:
    """非遗研学 Agent：模型主导工具循环 + 软提示 + 降级兜底 + 轨迹。"""

    def __init__(
        self,
        graph_engine=None,
        image_b64: str = None,
        user_id: int = None,
        user_lng=None,
        user_lat=None,
        user_city: str = None,
        user_citycode: str = None,
        session_memory: dict = None,
    ):
        self.image_b64 = image_b64
        self.user_id = user_id
        try:
            self.user_lng = float(user_lng) if user_lng is not None and user_lng != '' else None
            self.user_lat = float(user_lat) if user_lat is not None and user_lat != '' else None
        except (TypeError, ValueError):
            self.user_lng, self.user_lat = None, None
        self.user_city = (user_city or '').strip() or None
        self.user_citycode = (user_citycode or '').strip() or None
        if self.user_lng is not None and self.user_lat is not None and not self.user_city:
            try:
                from shared.utils import resolve_geo_from_lnglat
                geo = resolve_geo_from_lnglat(self.user_lng, self.user_lat)
                if geo.get('city'):
                    self.user_city = geo['city']
                if geo.get('citycode'):
                    self.user_citycode = geo.get('citycode') or self.user_citycode
            except Exception as exc:
                logger.warning('用户坐标逆地理失败: %s', exc)
        self._scratchpad = []
        self._trajectory = []
        if isinstance(session_memory, dict):
            self._memory = load_memory_json(dump_memory_json(session_memory))
        else:
            self._memory = empty_memory()
        self._profile_block = format_user_profile_block(build_user_profile(user_id))
        self._spark_degraded = False
        self._spark_error_detail = ''
        self._pending_repair = ''  # 上一轮参数错误，注入下一轮决策

    @property
    def session_memory(self) -> dict:
        return self._memory

    def run(self, user_msg: str, history: list = None, stream: bool = True):
        """
        生成器事件：
        thinking | tool_call | tool_result | trajectory | text | done | session_memory …
        """
        history = history or []
        self._current_user_msg = user_msg or ''
        # 开场先按本轮话更新「是否跑题」，避免美食仍被注成英歌
        self._memory = update_memory_from_turn(self._memory, user_msg, [])
        yield {'type': 'thinking', 'text': '正在分析您的问题…'}
        pub0 = memory_public_view(self._memory)
        if pub0:
            yield {'type': 'session_memory', 'memory': pub0}
        elif self._memory.get('goal_status') == 'paused':
            yield {'type': 'session_memory', 'memory': None}
        yield from self._emit_traj(
            'start',
            message=(user_msg or '')[:120],
            goal=(self._memory.get('goal') if self._memory else None),
        )

        # 多模态输入绑定：有图则先识图（非启发式抢跑，而是用户附件上下文）
        if self.image_b64 and not any(s.get('tool') == 'identify_image' for s in self._scratchpad):
            yield from self._run_tool('identify_image', {'image_b64': self.image_b64})

        spark_fail_streak = 0
        for _ in range(MAX_ROUNDS):
            decision = self._decide(user_msg, history)
            validated = parse_tool_call_with_validation(
                decision, frozenset(TOOL_REGISTRY.keys()),
            )

            if validated.get('tool') and not validated.get('ok'):
                # Schema 失败：不执行，注入纠错信息再决策一轮
                self._pending_repair = (
                    f'工具 {validated["tool"]} 参数无效：{validated.get("error")}。'
                    f'请修正 args 后重新输出 <tool_call>，或改为直接回答。'
                )
                yield from self._emit_traj(
                    'tool_validate_error',
                    tool=validated.get('tool'),
                    error=validated.get('error', ''),
                )
                spark_fail_streak = 0
                continue

            if validated.get('ok') and validated.get('tool'):
                self._pending_repair = ''
                spark_fail_streak = 0
                yield from self._run_tool(validated['tool'], validated['args'])
                continue

            if decision and '<tool_call>' not in decision:
                self._pending_repair = ''
                # 研学行程类：模型若空答不调工具，补跑编排后再总结（保证主题闭环可演示）
                if (
                    should_plan_study_tour(user_msg)
                    and not any(s.get('tool') == 'plan_study_tour' for s in self._scratchpad)
                ):
                    yield from self._emit_traj('enforce_study_tour')
                    yield from self._run_tool(
                        'plan_study_tour', extract_study_tour_args(user_msg),
                    )
                    continue
                yield from self._emit_text_chunks(decision.strip(), user_msg)
                return

            # 星火空响应 / 解析失败
            if not (decision or '').strip():
                spark_fail_streak += 1
                yield from self._emit_traj('spark_empty', streak=spark_fail_streak)
                if spark_fail_streak >= 1:
                    yield from self._run_degraded_tools(user_msg)
                if self._scratchpad:
                    # Demo：仅在星火不可用时用预置文案润色工具结果，不替代工具决策
                    if Config.DEMO_MODE and self._spark_degraded:
                        yield from self._emit_demo_final(user_msg)
                        return
                    yield from self._emit_text_chunks(
                        self._fallback_reply_from_tools(user_msg), user_msg,
                    )
                    return
                if spark_fail_streak >= 2:
                    break
            else:
                # 有文本但夹了坏 tool_call
                self._pending_repair = (
                    '未能解析合法 <tool_call>。请只输出一个合法工具块，或直接回答用户。'
                )
                yield from self._emit_traj('parse_miss', preview=(decision or '')[:160])

        yield from self._run_degraded_tools(user_msg)
        yield from self._stream_final(user_msg, history)

    def _emit_traj(self, step: str, **payload):
        entry = {
            'ts': round(time.time(), 3),
            'step': step,
            **{k: v for k, v in payload.items() if v is not None},
        }
        self._trajectory.append(entry)
        try:
            logger.info('agent_traj %s', json.dumps(entry, ensure_ascii=False)[:600])
        except Exception:
            logger.info('agent_traj %s', step)
        yield {'type': 'trajectory', 'step': entry}

    def _run_degraded_tools(self, user_msg: str):
        """仅当星火降级或轮次耗尽时，用启发式补齐关键工具（兜底，非主路径）。"""
        used = {s.get('tool') for s in self._scratchpad}
        if should_plan_study_tour(user_msg) and 'plan_study_tour' not in used:
            yield from self._emit_traj('degraded_hint', tool='plan_study_tour')
            args = extract_study_tour_args(user_msg)
            yield from self._run_tool('plan_study_tour', args)
            return
        if should_hint_location(user_msg) and 'search_places' not in used and 'plan_study_tour' not in used:
            yield from self._emit_traj('degraded_hint', tool='search_places')
            yield from self._run_tool('search_places', extract_place_search_args(user_msg))
        if should_hint_heritage_kb(user_msg) and 'search_heritage' not in used:
            yield from self._emit_traj('degraded_hint', tool='search_heritage')
            yield from self._run_tool(
                'search_heritage',
                {'query': extract_heritage_search_query(user_msg)},
            )
        if should_hint_graph(user_msg) and 'query_graph' not in used:
            yield from self._emit_traj('degraded_hint', tool='query_graph')
            yield from self._run_tool('query_graph', {'question': user_msg})
        if should_hint_revive(user_msg) and 'revive_heritage' not in used:
            yield from self._emit_traj('degraded_hint', tool='revive_heritage')
            yield from self._run_tool(
                'revive_heritage',
                {'prompt': user_msg or '非遗国潮焕新'},
            )

    def _inject_user_geo(self, tool: str, args: dict) -> dict:
        """把浏览器 GPS + 会话目标主题注入空间类工具（模型未传时）。"""
        args = dict(args or {})
        if tool == 'revive_heritage' and not args.get('image_b64') and self.image_b64:
            args['image_b64'] = self.image_b64
        if tool == 'identify_image' and not args.get('image_b64') and self.image_b64:
            args['image_b64'] = self.image_b64

        msg = getattr(self, '_current_user_msg', '') or ''
        theme = (self._memory.get('theme') or '').strip() if self._memory else ''
        mem_city = (self._memory.get('city') or '').strip() if self._memory else ''
        diverge = message_diverges_from_goal(msg, theme)
        paused = (self._memory.get('goal_status') == 'paused') if self._memory else False
        continue_goal = message_continues_goal(msg, theme) and not diverge and not paused

        # 跑题：禁止注入研学主题；生活类 keyword 优先具体品类，勿用 len 粗暴覆盖
        if diverge and tool == 'search_places':
            open_kw = extract_open_place_keyword(msg)
            kw = (args.get('keyword') or '').strip()
            generic = not kw or kw in ('非遗', '附近', '周边')
            theme_polluted = bool(theme) and theme in kw
            model_open = bool(kw) and _query_search_intent(kw) == 'open'
            if open_kw:
                if generic or theme_polluted:
                    args['keyword'] = open_kw
                elif model_open and len(open_kw) > len(kw) and (
                    open_kw.endswith(kw) or kw in open_kw
                ):
                    # 模型给「火锅」、句中可抽「卤水火锅」→ 升级；勿用带动词杂质的长串覆盖
                    args['keyword'] = open_kw
                # 否则保留模型已给出的具体 open keyword
            if not (args.get('city') or '').strip() and mem_city:
                args['city'] = mem_city
        elif continue_goal:
            # 仅「含糊续问」才补研学主题
            if tool == 'plan_study_tour' and theme:
                t = (args.get('theme') or '').strip()
                if not t or t in ('非遗', '安排', '行程', '规划'):
                    args['theme'] = theme
                if not (args.get('city') or '').strip() and mem_city:
                    args['city'] = mem_city
            if tool == 'search_places' and theme:
                kw = (args.get('keyword') or '').strip()
                if not kw or kw in ('非遗', '附近', '周边'):
                    args['keyword'] = theme
                if not (args.get('city') or '').strip() and mem_city:
                    args['city'] = mem_city
            if tool == 'search_heritage' and theme:
                q = (args.get('query') or '').strip()
                if not q or q in ('非遗',):
                    args['query'] = theme

        if self.user_lng is None or self.user_lat is None:
            return args
        if tool in ('search_places', 'plan_study_tour'):
            if args.get('lng') is None:
                args['lng'] = float(self.user_lng)
            if args.get('lat') is None:
                args['lat'] = float(self.user_lat)
            if not (args.get('city') or '').strip() and self.user_city:
                args['city'] = self.user_city
        if tool == 'plan_route':
            if args.get('origin_lng') is None:
                args['origin_lng'] = float(self.user_lng)
            if args.get('origin_lat') is None:
                args['origin_lat'] = float(self.user_lat)
            if not (args.get('citycode') or '').strip() and self.user_citycode:
                args['citycode'] = self.user_citycode
        return args

    def _refresh_memory(self, user_msg: str):
        self._memory = update_memory_from_turn(self._memory, user_msg, self._scratchpad)
        return memory_public_view(self._memory)

    def _geo_prompt_block(self) -> str:
        if self.user_lng is None or self.user_lat is None:
            return (
                '\n【用户位置】本轮未提供浏览器 GPS；search_places 将按城市/IP 检索，'
                '无法做「附近」排序。可提示用户允许定位或先打开地图页定位。\n'
            )
        city = self.user_city or '未知城市'
        return (
            f'\n【用户位置·浏览器 GPS】城市约【{city}】，'
            f'坐标 lng={float(self.user_lng):.6f}, lat={float(self.user_lat):.6f}。'
            '问附近/行程/怎么去时务必使用坐标（系统也会自动注入工具参数）。\n'
        )

    def _run_tool(self, tool: str, args: dict):
        args = self._inject_user_geo(tool, args)

        yield from self._emit_traj('tool_call', tool=tool)
        yield {
            'type': 'tool_call',
            'tool': tool,
            'label': tool_label(tool),
            'args': {k: v for k, v in (args or {}).items() if k != 'image_b64'},
        }

        if tool == 'revive_heritage':
            result = None
            for evt in iter_revive_heritage(args.get('prompt', ''), args.get('image_b64')):
                if evt['type'] == 'progress':
                    yield {
                        'type': 'revive_progress',
                        'stage': evt.get('stage'),
                        'text': evt.get('text', ''),
                    }
                elif evt['type'] == 'result':
                    result = evt
            if result is None:
                result = {'ok': False, 'error': '焕新流程异常结束'}
        else:
            result = execute_tool(tool, args)

        summary = summarize_tool_result(result)
        self._scratchpad.append({
            'tool': tool, 'args': args, 'result': result, 'summary': summary,
        })
        yield from self._emit_traj(
            'tool_result',
            tool=tool,
            ok=(result.get('ok') if isinstance(result, dict) else None),
            summary=(summary or '')[:200],
        )
        yield {'type': 'tool_result', 'tool': tool, 'summary': summary, 'data': result}
        if tool == 'revive_heritage' and isinstance(result, dict) and result.get('ok') and result.get('url'):
            if self.user_id:
                save_user_artwork(
                    self.user_id,
                    result.get('prompt', args.get('prompt', '')),
                    result['url'],
                    result.get('analysis', ''),
                    'agent',
                )
            yield {'type': 'art_image', 'url': result['url'], 'prompt': result.get('prompt', '')}

    def _finalize_response_text(self, text: str, user_msg: str) -> str:
        text = strip_legacy_spark_error_text(text or '')
        # 地点类回答：正文只用工具返回的高德 POI 名，不让模型另编店名
        grounded = build_grounded_places_answer(self._scratchpad)
        if grounded:
            suggest_lines = [
                ln for ln in (text or '').split('\n')
                if ln.strip().startswith('👉')
            ]
            text = grounded
            if suggest_lines:
                text = text + '\n\n' + suggest_lines[-1]
        preferred = infer_suggest_path(user_msg, self._scratchpad)
        text = enforce_suggest_path(text, preferred)
        text = normalize_agent_suggest_links(text, preferred_path=preferred)
        text = append_grounding_block(text, self._scratchpad)
        return text

    def _fallback_reply_from_tools(self, user_msg: str) -> str:
        """星火不可用时，根据已执行工具结果生成简短说明。"""
        from features.agent.parse import _revive_succeeded

        revive_done = _revive_succeeded(self._scratchpad)
        parts = []
        for s in self._scratchpad:
            tool = s.get('tool')
            res = s.get('result') if isinstance(s.get('result'), dict) else {}
            if tool == 'plan_study_tour':
                if res.get('ok'):
                    parts.append(res.get('summary') or '已生成研学行程草案。')
                    for stop in (res.get('itinerary') or [])[:5]:
                        if isinstance(stop, dict) and stop.get('name'):
                            parts.append(
                                f"{stop.get('time', '')} {stop['name']}"
                                + (f"（{stop['address']}）" if stop.get('address') else '')
                            )
                    if res.get('heritage_excerpt'):
                        parts.append((res.get('heritage_excerpt') or '')[:280])
                    if res.get('graph_answer'):
                        parts.append((res.get('graph_answer') or '')[:200])
                else:
                    parts.append(res.get('error') or '研学行程编排失败。')
            elif tool == 'revive_heritage' and res.get('ok'):
                parts.append('已按您的描述完成非遗数字焕新，请在对话中查看上方生成图片。')
                analysis = (res.get('analysis') or '').strip()
                if analysis:
                    parts.append(analysis[:280])
            elif tool == 'identify_image' and res.get('ok') and not revive_done:
                parts.append('已完成图片识图溯源，可在地图中查看标注的文化地标。')
            elif tool == 'identify_image' and res.get('ok') and revive_done and should_hint_location(user_msg):
                parts.append('识图结果已关联地图标点，可在非遗地图中查看位置。')
            elif tool == 'search_places':
                if res.get('ok'):
                    cnt = res.get('count') or len(res.get('markers') or [])
                    city = res.get('city') or ''
                    kw = res.get('keyword') or ''
                    markers = res.get('markers') or []
                    names = [
                        m.get('base_name') for m in markers[:6]
                        if isinstance(m, dict) and m.get('base_name')
                    ]
                    if kw:
                        line = f'已在【{city}】检索与「{kw}」相关的地标 {cnt} 处'
                    else:
                        line = f'已在【{city}】检索到周边文化地标 {cnt} 处'
                    if names:
                        line += '：' + '、'.join(names) + '。'
                    else:
                        line += '。'
                    for note in (res.get('search_notes') or []):
                        line += f'\n（{note}）'
                    mode = res.get('match_mode') or ''
                    if mode.startswith('fallback'):
                        line += '\n（说明：精确匹配不足，结果含通用文化类地点，请以名称是否含关键词为准。）'
                    parts.append(line)
                else:
                    parts.append(res.get('error') or '地图地点检索失败。')
            elif tool == 'query_graph' and res.get('ok'):
                ans = (res.get('answer') or '').strip()
                if ans:
                    parts.append(ans[:400])
            elif tool == 'search_heritage' and res.get('context'):
                ctx = (res.get('context') or '').strip()
                if ctx:
                    parts.append(ctx[:400])

        if not parts:
            if should_hint_location(user_msg):
                parts.append(
                    '地图检索已完成，但星火文字总结暂不可用；请点击文末链接在非遗地图中查看标点详情。'
                )
            else:
                parts.append(
                    '相关功能已执行，但星火文字总结暂不可用，请稍后在侧边栏继续使用地图、图谱或焕新等功能。',
                )
        body = '\n\n'.join(parts)
        if self._spark_degraded and body:
            detail = self._spark_error_detail or format_spark_user_error()
            body += f'\n\n（文字总结不可用，以上为工具直接结果。）\n{detail}'
        return self._finalize_response_text(body, user_msg)

    def _decide(self, user_msg: str, history: list) -> str:
        history_text = '\n'.join(
            f"{h.get('role', 'user')}: {h.get('content', '')[:200]}"
            for h in (history or [])[-6:]
        )
        tool_notes = '\n'.join(
            f"- {s['tool']}: {s['summary']}" for s in self._scratchpad
        ) or '（尚无工具结果）'

        profile = f'\n\n{self._profile_block}' if self._profile_block else ''
        mem_block = format_session_memory_block(self._memory, user_msg)
        suggest_hint = format_suggest_path_hint(user_msg, self._scratchpad)
        soft = build_soft_prior_hint(user_msg, has_image=bool(self.image_b64))
        geo = self._geo_prompt_block()
        repair = ''
        if self._pending_repair:
            repair = f'\n【上轮工具调用需修正】{self._pending_repair}\n'

        prompt = f"""{AGENT_SYSTEM}{profile}{mem_block}{suggest_hint}{geo}{soft}{repair}

【对话摘要】
{history_text}

【已执行工具】
{tool_notes}

【用户问题】
{user_msg}

请决定：输出 <tool_call> 或给出可直接回复用户的完整答案（含与意图一致的单行主动推荐）。"""
        text, user_err = sync_spark_call_meta(prompt)
        if user_err:
            self._spark_error_detail = user_err
            if not self._spark_degraded:
                logger.warning('星火不可用，将尽量仅用工具结果回答: %s', user_err[:200])
                self._spark_degraded = True
            return ''
        return text

    def _emit_demo_final(self, user_msg: str):
        from features.demo.service import demo_simulate_working
        demo_simulate_working()
        tool_block = '\n'.join(s['summary'] for s in self._scratchpad) or ''
        text = get_demo_chat_reply(user_msg, tool_block)
        yield from self._emit_text_chunks(text, user_msg)

    def _emit_text_chunks(self, text: str, user_msg: str = ''):
        """将同步决策结果按字切片推送，保留打字机效果且避免二次调用 LLM。"""
        text = strip_legacy_spark_error_text(text or '')
        pub = self._refresh_memory(user_msg)
        if pub:
            yield {'type': 'session_memory', 'memory': pub}
        if not text.strip():
            yield from self._emit_traj('done_empty')
            yield {'type': 'done'}
            return
        text = self._finalize_response_text(text, user_msg)
        yield from self._emit_traj(
            'answer',
            chars=len(text),
            tools=len(self._scratchpad),
            goal=(self._memory.get('goal') if self._memory else None),
        )
        step = 8
        for i in range(0, len(text), step):
            yield {'type': 'text', 'text': text[i:i + step]}
        yield {'type': 'done'}

    def _stream_final(self, user_msg: str, history: list):
        """达到最大轮次后，基于全部工具结果流式生成最终回答。"""
        if Config.DEMO_MODE and self._spark_degraded:
            yield from self._emit_demo_final(user_msg)
            return
        tool_block = '\n\n'.join(
            f"【{s['tool']}】\n{s['summary']}" for s in self._scratchpad
        ) or '无'
        history_text = '\n'.join(
            f"{h.get('role')}: {h.get('content', '')[:300]}"
            for h in (history or [])[-8:]
        )
        profile = f'\n\n{self._profile_block}' if self._profile_block else ''
        mem_block = format_session_memory_block(self._memory, user_msg)
        suggest_hint = format_suggest_path_hint(user_msg, self._scratchpad)
        prompt = f"""你是时空匠影非遗向导。请结合工具检索结果，专业、准确地回答用户。
若某工具失败或未命中，说明原因，勿编造数据。
地点/美食列表只能使用【工具检索结果】里出现的店名与地址，禁止编造未出现的店名。
回答正文中点明关键地名/传承关系等事实；系统会附加「依据」列表。
有研学记忆时可承接；若用户明确改问美食等，必须按新意图答，禁止复读场馆模板。
回答末尾用 1 行 👉 主动推荐，须与用户意图一致；链接格式 [链接文字](/路径)。

{AGENT_ROUTE_RULES}
{suggest_hint}{profile}{mem_block}

【工具检索结果】
{tool_block}

【近期对话】
{history_text}

【用户问题】
{user_msg}
"""
        text, user_err = sync_spark_call_meta(
            prompt, temperature=0.5, max_tokens=2048,
        )
        text = strip_legacy_spark_error_text(text)
        if user_err or not text.strip():
            yield from self._run_degraded_tools(user_msg)
            if self._scratchpad:
                if Config.DEMO_MODE:
                    yield from self._emit_demo_final(user_msg)
                else:
                    yield from self._emit_text_chunks(
                        self._fallback_reply_from_tools(user_msg), user_msg,
                    )
            else:
                yield from self._emit_text_chunks(
                    user_err or format_spark_user_error(), user_msg,
                )
            return
        yield from self._emit_text_chunks(text, user_msg)
