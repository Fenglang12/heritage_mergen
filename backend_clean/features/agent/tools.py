"""Agent 可调用的业务能力封装，复用 utils / 图谱 / 路线等既有实现。"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.config import Config
from features.map.direction import plan_direction
from shared.utils import (
    _poi_is_noise_for_theme,
    apply_marker_intros,
    execute_zhipu_art_generation,
    get_amap_location,
    get_client_ip_from_request,
    get_retrieved_context,
    collect_markers_for_entries,
    get_markers_from_amap,
    get_markers_near_lnglat,
    iter_zhipu_art_generation,
    normalize_art_result_url,
    resolve_geo_from_lnglat,
    understand_image,
)

logger = logging.getLogger(__name__)

# 由 routes 在启动时注入，避免循环导入
_graph_engine = None
_normalize_city = None


def init_agent_tools(graph_engine, normalize_city_fn):
    """注册图谱引擎与地名规范化函数（来自 routes 模块）。"""
    global _graph_engine, _normalize_city
    _graph_engine = graph_engine
    _normalize_city = normalize_city_fn


def tool_search_heritage(query: str, top_k: int = 3) -> dict:
    """向量检索非遗百科上下文。"""
    text = get_retrieved_context(query)
    return {'ok': bool(text), 'context': text or '未检索到相关百科内容。'}


def tool_query_graph(question: str) -> dict:
    """知识图谱 Text2SQL 查询，返回自然语言答案与节点 ID。"""
    if _graph_engine is None:
        return {'ok': False, 'answer': '图谱引擎未初始化', 'node_ids': []}
    result = _graph_engine.query_structured(question)
    return result


def _resolve_search_city(city: str) -> str:
    """有城市名则规范化；否则按当前请求 IP 定位，再不行才用配置兜底。"""
    city = (city or '').strip()
    if city:
        return (_normalize_city(city) if _normalize_city else city) or city
    try:
        from flask import has_request_context, request
        client_ip = get_client_ip_from_request(request) if has_request_context() else None
        located = (get_amap_location(client_ip) or '').strip()
        if located:
            return located
    except Exception as exc:
        logger.warning('search_places IP 定位失败: %s', exc)
    return Config.DEFAULT_MAP_CITY


def _coerce_coord(value):
    if value is None or value == '':
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def tool_search_places(
    city: str = '',
    keyword: str = None,
    lng=None,
    lat=None,
    radius: int = 5000,
) -> dict:
    """
    搜索非遗相关文化地标。
    有 lng/lat 时优先高德周边检索（按距离排序），否则按城市关键词检索。
    """
    kw = (keyword or '').strip()[:10] or None
    notes = []
    markers = []
    mode = ''
    loc_source = 'city'
    lng_f, lat_f = _coerce_coord(lng), _coerce_coord(lat)
    resolved_city = (city or '').strip()

    if lng_f is not None and lat_f is not None:
        geo = resolve_geo_from_lnglat(lng_f, lat_f)
        if geo.get('city'):
            resolved_city = geo['city']
        try:
            radius_i = int(radius or 5000)
        except (TypeError, ValueError):
            radius_i = 5000
        markers = get_markers_near_lnglat(lng_f, lat_f, kw, radius=radius_i)
        loc_source = 'gps_around'
        if markers:
            mode = markers[0].get('match_mode') or 'around'
            notes.append(f'已按当前位置周边约 {radius_i}m 检索与主题相关地点，按距离排序')
        else:
            # 附近无果 → 同城主题检索（仍拒绝 fallback_generic 胡凑）
            resolved_city = _resolve_search_city(resolved_city)
            markers = get_markers_from_amap(resolved_city, kw)
            markers = [
                m for m in markers
                if (m.get('match_mode') or '') not in ('fallback_generic',)
            ]
            loc_source = 'gps_city_fallback'
            if markers:
                notes.append('周边未命中主题场馆，已回退同城「主题名」检索')
            mode = (markers[0].get('match_mode') if markers else '') or ''
    else:
        resolved_city = _resolve_search_city(resolved_city)
        markers = get_markers_from_amap(resolved_city, kw)
        if kw:
            markers = [
                m for m in markers
                if (m.get('match_mode') or '') not in ('fallback_generic',)
            ]
        mode = (markers[0].get('match_mode') if markers else '') or ''

    apply_marker_intros(markers, city=resolved_city)
    for m in markers:
        note = (m.get('search_note') or '').strip()
        if note and note not in notes:
            notes.append(note)

    if not markers:
        return {
            'ok': False,
            'city': resolved_city,
            'keyword': kw or '',
            'count': 0,
            'markers': [],
            'lng': lng_f,
            'lat': lat_f,
            'loc_source': loc_source,
            'error': (
                f'在【{resolved_city or "当前位置"}】未检索到与「{kw or "非遗"}」相关的高德地标；'
                f'请换城市/关键词，或检查 AMAP_API_KEY / 定位权限。'
            ),
        }
    return {
        'ok': True,
        'city': resolved_city,
        'keyword': kw or '',
        'count': len(markers),
        'markers': markers[:12],
        'match_mode': mode,
        'search_notes': notes,
        'lng': lng_f,
        'lat': lat_f,
        'loc_source': loc_source,
        'radius_m': int(radius or 5000) if lng_f is not None else None,
    }


def tool_plan_route(origin_lng, origin_lat, dest_lng, dest_lat, mode='driving', citycode='010') -> dict:
    """调用高德路线规划，统一 ok 字段便于 Agent / Grounding。"""
    # schema 里可能是 bicycling，底层 direction 用 cycling
    mode_map = {'bicycling': 'cycling', 'bike': 'cycling', 'cycle': 'cycling'}
    mode = mode_map.get((mode or 'driving').lower(), (mode or 'driving').lower())
    raw = plan_direction(origin_lng, origin_lat, dest_lng, dest_lat, mode, citycode)
    if raw.get('status') == 'success':
        dist = int(raw.get('distance') or 0)
        dur = int(raw.get('duration') or 0)
        return {
            'ok': True,
            'mode': mode,
            'distance_m': dist,
            'distance_km': round(dist / 1000.0, 2),
            'duration_s': dur,
            'duration_min': max(1, int(round(dur / 60.0))) if dur else None,
            'cost': raw.get('cost'),
            'steps': (raw.get('steps') or [])[:8],
            'polyline': raw.get('polyline') or [],
            'summary': (
                f'{mode} 约 {round(dist / 1000.0, 2)} km'
                + (f' / {max(1, int(round(dur / 60.0)))} 分钟' if dur else '')
            ),
        }
    return {
        'ok': False,
        'error': raw.get('msg') or '路线规划失败',
        'mode': mode,
    }


def tool_identify_image(image_b64: str) -> dict:
    """识图溯源：视觉模型解析 + 高德 POI 聚合。"""
    raw = image_b64.split(',', 1)[1] if ',' in image_b64 else image_b64
    prompt = (
        '请识别图片中的地点和非遗内容。\n'
        '每项一行，格式：【非遗条目】：XX省XX市 | 非遗项目名称\n'
        '最后一行用一句话描述图片非遗特色。'
    )
    ai_analysis = understand_image(raw, prompt) or ''
    if ai_analysis.startswith('【识图失败】'):
        return {
            'ok': False,
            'error': ai_analysis,
            'ai_text': ai_analysis,
            'city': '',
            'markers': [],
        }

    entries = []
    for line in ai_analysis.split('\n'):
        line = line.strip()
        if '【非遗条目】：' not in line:
            continue
        body = line.replace('【非遗条目】：', '').strip()
        if '|' in body:
            city_raw, kw_raw = body.split('|', 1)
        else:
            city_raw, kw_raw = body, ''
        city = _normalize_city(city_raw) if _normalize_city else city_raw
        entries.append((city, (kw_raw.strip()[:10] or None)))

    if not entries:
        return {
            'ok': False,
            'error': (
                '识图未解析出【非遗条目】城市/项目格式，未使用默认城市以免标错地点。'
                f'模型原文：{(ai_analysis or "（空）")[:300]}'
            ),
            'ai_text': ai_analysis,
            'city': '',
            'markers': [],
        }

    markers = collect_markers_for_entries(entries)
    apply_marker_intros(markers, city=entries[0][0] if entries else None)

    return {
        'ok': True,
        'ai_text': ai_analysis,
        'city': entries[0][0],
        'markers': markers,
    }


def tool_revive_heritage(prompt: str, image_b64: str = None, on_progress=None) -> dict:
    """非遗数字焕新：GLM-4V 分析参考图 + CogView-4 生成。"""
    prompt = (prompt or '').strip()
    if not prompt:
        return {'ok': False, 'error': '缺少创作描述 prompt，请说明想要的风格或效果'}

    raw_b64 = None
    if image_b64:
        raw_b64 = image_b64.split(',', 1)[1] if ',' in image_b64 else image_b64

    def _progress(stage, text, detail=None):
        if on_progress:
            on_progress(stage, text, detail)

    result = execute_zhipu_art_generation(prompt, raw_b64, on_progress=_progress)
    if not result.get('success'):
        return {
            'ok': False,
            'error': result.get('msg') or '焕新生成失败',
            'suggestion': '可前往「非遗数字焕新」页面重试，或简化/调整创意描述后再次生成。',
        }

    url = normalize_art_result_url(result.get('data') or '')
    return {
        'ok': True,
        'url': url,
        'analysis': result.get('analysis') or '',
        'prompt': prompt,
    }


def iter_revive_heritage(prompt: str, image_b64: str = None):
    """焕新工具流式事件（供 Agent SSE）。"""
    prompt = (prompt or '').strip()
    if not prompt:
        yield {'type': 'result', 'ok': False, 'error': '缺少创作描述 prompt'}
        return

    raw_b64 = None
    if image_b64:
        raw_b64 = image_b64.split(',', 1)[1] if ',' in image_b64 else image_b64

    for event in iter_zhipu_art_generation(prompt, raw_b64):
        if event['type'] == 'progress':
            yield {'type': 'progress', 'stage': event.get('stage'), 'text': event.get('text', '')}
        elif event['type'] == 'result':
            if not event.get('success'):
                yield {
                    'type': 'result',
                    'ok': False,
                    'error': event.get('msg') or '焕新生成失败',
                    'suggestion': '可前往「非遗数字焕新」页面重试，或调整创意描述。',
                }
                return
            url = normalize_art_result_url(event.get('data') or '')
            yield {
                'type': 'result',
                'ok': True,
                'url': url,
                'analysis': event.get('analysis') or '',
                'prompt': prompt,
            }


def _marker_as_poi(marker: dict) -> dict:
    return {
        'name': (marker.get('base_name') or marker.get('name') or ''),
        'type': marker.get('type') or marker.get('category') or '',
        'address': marker.get('address') or '',
    }


def filter_study_tour_markers(markers: list, theme: str) -> list:
    """
    研学行程站点筛选：名称沾主题，且复用意图噪声门控
   （挡「英歌舞主题火锅」等蹭词，与地图过滤一致）。
    """
    theme = (theme or '').strip()
    if not markers:
        return []
    if not theme or theme == '非遗':
        return [m for m in markers if isinstance(m, dict)]

    def _name(m: dict) -> str:
        return (m.get('base_name') or '') + (m.get('name') or '')

    def _ok(m: dict) -> bool:
        return isinstance(m, dict) and not _poi_is_noise_for_theme(_marker_as_poi(m), theme)

    theme_hit = [m for m in markers if _ok(m) and theme in _name(m)]
    if theme_hit:
        return theme_hit
    if len(theme) >= 2:
        soft = [m for m in markers if _ok(m) and theme[:-1] in _name(m)]
        if soft:
            return soft
    return []


def tool_plan_study_tour(
    city: str = '',
    theme: str = '非遗',
    hours: float = 4,
    lng=None,
    lat=None,
    radius: int = 8000,
) -> dict:
    """
    复合研学任务：并行拉地标 + 百科 + 图谱，组装可讲解的结构化行程。
    有 GPS 时按距离排序站点，并规划到第一站的路线。
    """
    city = (city or '').strip()
    theme = ((theme or '').strip() or '非遗')[:40]
    lng_f, lat_f = _coerce_coord(lng), _coerce_coord(lat)
    try:
        hours = float(hours or 4)
    except (TypeError, ValueError):
        hours = 4.0
    hours = max(2.0, min(hours, 10.0))

    places_r, heritage_r, graph_r = {}, {}, {}

    def _places():
        return tool_search_places(
            city,
            theme if theme != '非遗' else None,
            lng=lng_f,
            lat=lat_f,
            radius=radius or 8000,
        )

    def _heritage():
        return tool_search_heritage(theme)

    def _graph():
        return tool_query_graph(f'{theme}有哪些传承人或地区分布？')

    with ThreadPoolExecutor(max_workers=3) as pool:
        futs = {
            pool.submit(_places): 'places',
            pool.submit(_heritage): 'heritage',
            pool.submit(_graph): 'graph',
        }
        for fut in as_completed(futs):
            key = futs[fut]
            try:
                val = fut.result()
            except Exception as exc:
                logger.warning('plan_study_tour 子任务 %s 失败: %s', key, exc)
                val = {'ok': False, 'error': str(exc)}
            if key == 'places':
                places_r = val
            elif key == 'heritage':
                heritage_r = val
            else:
                graph_r = val

    resolved_city = places_r.get('city') or city or Config.DEFAULT_MAP_CITY
    markers = places_r.get('markers') or [] if places_r.get('ok') else []
    # 主题研学：名称含主题 + 意图噪声门控；不够则如实少排
    markers = filter_study_tour_markers(markers, theme)
    # 有距离则按近到远；站点数量随命中数，不做「至少 2 站」硬凑
    if any(isinstance(m, dict) and m.get('distance_m') is not None for m in markers):
        markers = sorted(
            markers,
            key=lambda m: m.get('distance_m') if isinstance(m, dict) and m.get('distance_m') is not None else 1e12,
        )
    n_stops = min(len(markers), max(1, min(5, int(round(hours / 1.5)))))
    picked = markers[:n_stops] if n_stops else []
    slot = hours / max(len(picked), 1)
    itinerary = []
    t = 9.0  # 默认上午 9 点起
    for i, m in enumerate(picked):
        if not isinstance(m, dict):
            continue
        name = m.get('base_name') or m.get('name') or f'站点{i + 1}'
        hh = int(t)
        mm = 0 if (t - hh) < 0.5 else 30
        itinerary.append({
            'order': i + 1,
            'time': f'{hh:02d}:{mm:02d}',
            'duration_h': round(slot, 1),
            'name': name,
            'address': m.get('address') or '',
            'lng': m.get('lng') or m.get('longitude'),
            'lat': m.get('lat') or m.get('latitude'),
            'distance_m': m.get('distance_m'),
            'ai_intro': (m.get('ai_intro') or '')[:160],
        })
        t += slot

    route_first = None
    if itinerary and lng_f is not None and lat_f is not None:
        dest = itinerary[0]
        if dest.get('lng') is not None and dest.get('lat') is not None:
            route_first = tool_plan_route(
                lng_f, lat_f, dest['lng'], dest['lat'], mode='walking',
            )
            if not route_first.get('ok'):
                route_first = tool_plan_route(
                    lng_f, lat_f, dest['lng'], dest['lat'], mode='driving',
                )

    grounding = []
    if itinerary:
        grounding.append(
            f'地标（{resolved_city}）：' + '、'.join(x['name'] for x in itinerary)
        )
    if places_r.get('loc_source'):
        grounding.append(f'空间检索：{places_r.get("loc_source")}')
    if route_first and route_first.get('ok'):
        grounding.append(f'到第一站路线：{route_first.get("summary")}')
    ctx = (heritage_r.get('context') or '').strip() if heritage_r.get('ok') else ''
    if ctx:
        grounding.append('百科：' + ctx.replace('\n', ' ')[:120] + ('…' if len(ctx) > 120 else ''))
    else:
        grounding.append('百科：未命中有效片段')
    if graph_r.get('ok') and (graph_r.get('answer') or '').strip():
        grounding.append('图谱：' + (graph_r.get('answer') or '').strip()[:100])
    elif graph_r.get('ok') is False:
        grounding.append('图谱：查询未成功')

    ok = bool(itinerary) or bool(ctx) or bool(graph_r.get('ok'))
    summary_bits = [
        f'主题「{theme}」·约 {hours:g} 小时·城市【{resolved_city}】',
    ]
    if itinerary:
        summary_bits.append(f'安排 {len(itinerary)} 站（仅保留与主题相关地点）')
    else:
        summary_bits.append(
            f'附近/同城暂无名称含「{theme}」的可靠场馆，未用无关景点凑行程'
        )
        grounding.append(f'行程：主题「{theme}」相关 POI 不足，已拒绝泛非遗凑数')
    if route_first and route_first.get('ok'):
        summary_bits.append(f'当前位置→首站：{route_first.get("summary")}')
    return {
        'ok': ok,
        'city': resolved_city,
        'theme': theme,
        'hours': hours,
        'itinerary': itinerary,
        'markers': picked,
        'route_to_first': route_first,
        'user_lng': lng_f,
        'user_lat': lat_f,
        'loc_source': places_r.get('loc_source'),
        'heritage_ok': bool(heritage_r.get('ok') and ctx),
        'graph_ok': bool(graph_r.get('ok')),
        'heritage_excerpt': ctx[:500] if ctx else '',
        'graph_answer': (graph_r.get('answer') or '')[:400] if graph_r.get('ok') else '',
        'grounding': grounding,
        'summary': '；'.join(summary_bits),
        'error': None if ok else (
            places_r.get('error')
            or f'未能拼出「{theme}」主题行程：附近缺少相关场馆，请换主题/扩大范围或先打开地图定位'
        ),
    }


TOOL_REGISTRY = {
    'search_heritage': {
        'fn': lambda args: tool_search_heritage(args.get('query', '')),
        'label': '检索非遗百科',
    },
    'query_graph': {
        'fn': lambda args: tool_query_graph(args.get('question', '')),
        'label': '查询知识图谱',
    },
    'search_places': {
        'fn': lambda args: tool_search_places(
            args.get('city', ''),
            args.get('keyword'),
            lng=args.get('lng'),
            lat=args.get('lat'),
            radius=args.get('radius', 5000),
        ),
        'label': '搜索文化地标',
    },
    'plan_route': {
        'fn': lambda args: tool_plan_route(
            args.get('origin_lng'), args.get('origin_lat'),
            args.get('dest_lng'), args.get('dest_lat'),
            args.get('mode', 'driving'), args.get('citycode', '010'),
        ),
        'label': '规划出行路线',
    },
    'identify_image': {
        'fn': lambda args: tool_identify_image(args.get('image_b64', '')),
        'label': '识别图片非遗元素',
    },
    'revive_heritage': {
        'fn': lambda args: tool_revive_heritage(
            args.get('prompt', ''),
            args.get('image_b64'),
        ),
        'label': '非遗数字焕新（GLM-4V + CogView-4）',
    },
    'plan_study_tour': {
        'fn': lambda args: tool_plan_study_tour(
            args.get('city', ''),
            args.get('theme', '非遗'),
            args.get('hours', 4),
            lng=args.get('lng'),
            lat=args.get('lat'),
            radius=args.get('radius', 8000),
        ),
        'label': '编排研学行程',
    },
}


def execute_tool(tool_name: str, args: dict) -> dict:
    """执行已注册工具，未知工具返回错误说明。"""
    entry = TOOL_REGISTRY.get(tool_name)
    if not entry:
        return {'ok': False, 'error': f'未知工具: {tool_name}'}
    try:
        return entry['fn'](args or {})
    except Exception as exc:
        logger.exception('工具 %s 执行失败', tool_name)
        return {'ok': False, 'error': str(exc)}


def tool_label(tool_name: str) -> str:
    return TOOL_REGISTRY.get(tool_name, {}).get('label', tool_name)
