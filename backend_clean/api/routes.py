"""核心 API 路由：认证、对话 Agent、识图、地图、图谱等。"""

import base64
import io
import json
import logging
import re
import threading
import time
import uuid

import pymysql
from flask import Blueprint, Response, current_app, jsonify, request, session, stream_with_context
from PIL import Image
from werkzeug.security import check_password_hash, generate_password_hash

from core.auth_utils import auth_required, get_current_user_id
from core.config import Config
from core.exts import db
from core.models import ChatHistory, ChatSession, User
from features.agent.engine import HeritageAgent
from features.agent.parse import (
    enforce_suggest_path,
    infer_suggest_path,
    normalize_agent_suggest_links,
)
from features.agent.tools import init_agent_tools
from features.graph.graph_payload import build_graph_payload
from features.graph.rag import MySQLGraphRAG
from features.map.direction import plan_direction
from features.revive.artwork import save_user_artwork
from shared.utils import (
    apply_marker_intros,
    audio_to_text,
    collect_markers_for_entries,
    execute_zhipu_art_generation,
    get_amap_location,
    get_client_ip_from_request,
    get_markers_from_amap,
    get_markers_near_lnglat,
    get_tts_audio,
    iter_zhipu_art_generation,
    normalize_art_result_url,
    resolve_geo_from_lnglat,
    strip_legacy_spark_error_text,
    sync_spark_call,
    understand_image,
    understand_video,
)

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api')

# ── 生图任务内存存储（含过期清理）────────────────────────────────
# 结构：{ task_id: { status, url/msg, created_at } }

# 省级 → 省会城市，用于模型只输出省名时的兜底
_PROVINCE_CAPITAL = {
    '北京': '北京市', '天津': '天津市', '上海': '上海市', '重庆': '重庆市',
    '河北': '石家庄市', '山西': '太原市', '辽宁': '沈阳市', '吉林': '长春市',
    '黑龙江': '哈尔滨市', '江苏': '南京市', '浙江': '杭州市', '安徽': '合肥市',
    '福建': '福州市', '江西': '南昌市', '山东': '济南市', '河南': '郑州市',
    '湖北': '武汉市', '湖南': '长沙市', '广东': '广州市', '海南': '海口市',
    '四川': '成都市', '贵州': '贵阳市', '云南': '昆明市', '陕西': '西安市',
    '甘肃': '兰州市', '青海': '西宁市', '内蒙古': '呼和浩特市',
    '广西': '南宁市', '西藏': '拉萨市', '宁夏': '银川市', '新疆': '乌鲁木齐市',
}

def _normalize_city(raw: str) -> str:
    """
    将模型输出的地名规范化为高德可用的市级名称。
    - "广东省广州市" → "广州市"
    - "广东省"       → "广州市"（省会兜底）
    - "广东"         → "广州市"
    - "北京市"       → "北京市"
    """
    import re as _re
    s = raw.strip()
    # 去掉自治区/特别行政区后缀，统一处理
    s = _re.sub(r'^(.+?)(省|自治区|特别行政区)', lambda m: m.group(1) + '|', s, count=1)
    if '|' in s:
        province, rest = s.split('|', 1)
        rest = rest.strip()
        if rest:
            return rest  # 有市名，直接返回
        # 只有省名，查省会
        return _PROVINCE_CAPITAL.get(province.strip(), province.strip() + '市')
    # 没有省份分隔符，直接当城市名用（如"北京市"、"广州市"）
    return s if s else '北京市'

image_tasks: dict = {}
IMAGE_TASK_TTL = 600  # 任务保留 10 分钟后自动清理


def _cleanup_tasks():
    """后台线程：每 5 分钟清理过期任务，防止内存泄漏"""
    while True:
        time.sleep(300)
        now = time.time()
        expired = [k for k, v in list(image_tasks.items())
                   if now - v.get('created_at', 0) > IMAGE_TASK_TTL]
        for k in expired:
            image_tasks.pop(k, None)
        if expired:
            logger.info('已清理 %d 个过期生图任务', len(expired))


threading.Thread(target=_cleanup_tasks, daemon=True).start()

# ── 全局 RAG 引擎（启动时初始化一次）──────────────────────────────
graph_engine = MySQLGraphRAG(sync_spark_call)


def _sse_event(payload: dict) -> str:
    """将事件序列化为 SSE data 行。"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# ================================================================
# 用户认证
# ================================================================

@api_bp.route('/register', methods=['POST'])
def register():
    data     = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    if not username or not password:
        return jsonify({'status': 'error', 'msg': '账号和密码不能为空'})

    # 修复：增加密码最小长度校验
    if len(password) < 6:
        return jsonify({'status': 'error', 'msg': '密码至少需要6位'})

    if len(username) > 30:
        return jsonify({'status': 'error', 'msg': '雅号不能超过30个字符'})

    if User.query.filter_by(username=username).first():
        return jsonify({'status': 'error', 'msg': '此雅号已被抢占，请换一个'})

    new_user = User(username=username, password_hash=generate_password_hash(password, method='pbkdf2:sha256'))
    db.session.add(new_user)
    db.session.commit()
    logger.info('新用户注册：%s', username)
    return jsonify({'status': 'success', 'msg': '注册成功，请登录'})


@api_bp.route('/login', methods=['POST'])
def login():
    data     = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'status': 'error', 'msg': '雅号或暗令不匹配'})

    if user.is_banned:
        return jsonify({'status': 'error', 'msg': f'账号已被封禁：{user.banned_reason or "违反社区规范"}'}), 403

    session['user_id']  = user.id
    session['username'] = user.username
    logger.info('用户登录：%s (role=%d)', username, user.role)
    return jsonify({'status': 'success', 'username': user.username, 'role': user.role})


@api_bp.route('/logout')
def logout():
    session.clear()
    return jsonify({'status': 'success'})


# ================================================================
# 2. 地图初始定位
# ================================================================

init_agent_tools(graph_engine, _normalize_city)


@api_bp.route('/map/search', methods=['GET'])
@auth_required
def map_search():
    """按城市 + 关键词搜索 POI（对话跳转地图、带 query 时使用）。"""
    city = (request.args.get('city') or '').strip()
    keyword = (request.args.get('keyword') or '').strip()
    if not keyword:
        return jsonify({'status': 'error', 'msg': '缺少 keyword 参数'}), 400
    if city:
        city = _normalize_city(city)
    else:
        city = get_amap_location(get_client_ip_from_request(request))
    markers = get_markers_from_amap(city, keyword[:10])
    apply_marker_intros(markers, city=city)
    count = len(markers)
    return jsonify({
        'status': 'success',
        'city': city,
        'keyword': keyword,
        'markers': markers,
        'ai_text': (
            f'已在【{city}】标注与「{keyword}」相关的 {count} 处地标，点击标点可看详情。'
            if count else f'【{city}】未找到与「{keyword}」直接相关的地标，已改用默认定标。'
        ),
    })


@api_bp.route('/default_local', methods=['GET'])
@auth_required
def default_local():
    """
    默认地图：浏览器 GPS → 逆地理得城市 → 以坐标为圆心周边检索文化地标。
    周边无结果时才回退同城文本检索。IP 定位已停用。
    """
    client_ip = get_client_ip_from_request(request)
    gps_lng = request.args.get('lng')
    gps_lat = request.args.get('lat')
    try:
        radius = int(request.args.get('radius') or 8000)
    except (TypeError, ValueError):
        radius = 8000
    radius = max(1000, min(radius, 30000))

    if gps_lng is None or gps_lat is None or not str(gps_lng).strip() or not str(gps_lat).strip():
        logger.warning('default_local ✗ 缺少 lng/lat，拒绝 IP 定位')
        return jsonify({
            'status':     'error',
            'city':       '',
            'markers':    [],
            'ai_text':    '请授权浏览器定位后重试（仅支持精确位置，已关闭网络 IP 定位）。',
            'loc_source': '',
            'loc_error':  '缺少浏览器坐标 lng/lat',
            'client_ip':  client_ip,
        }), 400

    logger.warning('default_local ✓ 浏览器坐标 lng=%s lat=%s radius=%s', gps_lng, gps_lat, radius)
    geo = resolve_geo_from_lnglat(gps_lng, gps_lat)
    if geo.get('status') != 'success' or not geo.get('city'):
        loc_error = geo.get('loc_error') or 'GPS 逆地理失败'
        logger.warning('default_local 逆地理失败: %s', loc_error)
        return jsonify({
            'status':     'error',
            'city':       '',
            'lng':        geo.get('lng'),
            'lat':        geo.get('lat'),
            'markers':    [],
            'ai_text':    f'精确定位失败：{loc_error}',
            'loc_source': 'gps',
            'loc_error':  loc_error,
            'client_ip':  client_ip,
        }), 400

    loc = geo.get('city') or ''
    search_mode = 'around'
    used_radius = radius
    markers = get_markers_near_lnglat(geo.get('lng'), geo.get('lat'), radius=radius)

    # 近处没有时放大半径再试一次
    if not markers and radius < 20000:
        used_radius = min(25000, max(radius * 2, 15000))
        markers = get_markers_near_lnglat(geo.get('lng'), geo.get('lat'), radius=used_radius)
        if markers:
            search_mode = 'around_wide'

    # 仍没有：回退同城文本检索（全市），并标明不是「身边」
    if not markers and loc:
        markers = get_markers_from_amap(loc)
        search_mode = 'city_fallback' if markers else 'empty'

    apply_marker_intros(markers, city=loc)

    count = len(markers)
    if search_mode.startswith('around'):
        msg = (
            f'已按浏览器定位到【{loc}】，在约 {used_radius // 1000}km 内标出 '
            f'{count} 处文化地标（由近到远）。'
        )
        if search_mode == 'around_wide':
            msg += '近处较少，已自动扩大检索范围。'
    elif search_mode == 'city_fallback':
        msg = (
            f'已定位到【{loc}】，附近 {radius // 1000}km 内暂无合适文化点，'
            f'已改为展示同城 {count} 处地标供参考。'
        )
    else:
        msg = f'已定位到【{loc}】，附近暂未检索到文化地标，可稍后刷新或换个开阔位置再试。'

    return jsonify({
        'status':        'success',
        'city':          loc,
        'lng':           geo.get('lng'),
        'lat':           geo.get('lat'),
        'citycode':      geo.get('citycode', ''),
        'markers':       markers,
        'ai_text':       msg,
        'ip_used':       None,
        'client_ip':     client_ip,
        'loc_status':    geo.get('status'),
        'loc_source':    geo.get('loc_source') or 'gps+regeo',
        'search_mode':   search_mode,
        'search_radius': used_radius if search_mode.startswith('around') else None,
        'loc_error':     None,
        'loc_warnings':  [],
        'formatted_address': geo.get('formatted_address') or '',
    })


# ================================================================
# 3. 会话管理模块
# ================================================================

DEFAULT_SESSION_TITLES = frozenset({'新对话', '新的对话', '关于非遗的新探索'})


def _auto_title_from_message(msg: str) -> str:
    """取用户首条问题前 8 个字作为会话标题。"""
    text = re.sub(r'\s+', ' ', (msg or '').strip())
    if not text or text.startswith('['):
        return '新对话'
    return text[:8]


def _maybe_auto_rename_session(sess, msg: str) -> None:
    """首条用户消息后，若仍为占位标题则自动命名。"""
    if (sess.title or '').strip() not in DEFAULT_SESSION_TITLES:
        return
    user_count = ChatHistory.query.filter_by(session_id=sess.id, role='user').count()
    if user_count != 1:
        return
    sess.title = _auto_title_from_message(msg)
    db.session.commit()


@api_bp.route('/sessions', methods=['GET'])
@auth_required
def get_sessions():
    user_id = get_current_user_id()
    rows = (ChatSession.query
            .filter_by(user_id=user_id)
            .order_by(ChatSession.created_at.desc())
            .all())
    from features.agent.memory import load_memory_json, memory_public_view
    data = []
    for s in rows:
        mem = memory_public_view(load_memory_json(getattr(s, 'memory_json', None)))
        data.append({
            'id': s.id,
            'title': s.title,
            'time': s.created_at.strftime('%m-%d %H:%M'),
            'memory': mem,
        })
    return jsonify({'status': 'success', 'sessions': data})


@api_bp.route('/session/create', methods=['POST'])
@auth_required
def create_session():
    user_id = get_current_user_id()
    new_sess = ChatSession(user_id=user_id, title='新对话')
    db.session.add(new_sess)
    db.session.commit()
    return jsonify({'session_id': new_sess.id, 'title': new_sess.title})


@api_bp.route('/session/<int:sid>', methods=['PATCH'])
@auth_required
def update_session(sid):
    """用户自定义修改会话标题。"""
    user_id = get_current_user_id()
    sess = ChatSession.query.get(sid)
    if not sess or sess.user_id != user_id:
        return jsonify({'status': 'error', 'msg': '越权访问！'}), 403

    data  = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'status': 'error', 'msg': '标题不能为空'}), 400
    sess.title = title[:100]
    db.session.commit()
    return jsonify({'status': 'success', 'title': sess.title})


@api_bp.route('/history/<int:sid>', methods=['GET'])
@auth_required
def get_session_history(sid):
    user_id = get_current_user_id()
    sess = ChatSession.query.get(sid)
    if not sess or sess.user_id != user_id:
        return jsonify({'status': 'error', 'msg': '越权访问！'}), 403

    from features.agent.memory import load_memory_json, memory_public_view
    messages = (ChatHistory.query
                .filter_by(session_id=sid)
                .order_by(ChatHistory.timestamp.asc())
                .all())
    mem = memory_public_view(load_memory_json(getattr(sess, 'memory_json', None)))
    return jsonify({
        'status': 'success',
        'data': [{'role': m.role, 'content': m.content} for m in messages],
        'memory': mem,
    })


@api_bp.route('/clear', methods=['POST'])
@auth_required
def clear_memory():
    user_id    = get_current_user_id()
    data       = request.get_json(silent=True) or {}
    session_id = data.get('session_id')
    if session_id:
        sess = ChatSession.query.get(session_id)
        if sess and sess.user_id == user_id:
            db.session.delete(sess)
            db.session.commit()
    return jsonify({'status': 'success'})


# ================================================================
# 语音转文字（全站复用）
# ================================================================

@api_bp.route('/asr', methods=['POST'])
@auth_required
def asr_transcribe():
    data = request.get_json(silent=True) or {}
    audio_b64 = data.get('audio', '')
    if not audio_b64:
        return jsonify({'status': 'error', 'msg': '缺少 audio 参数'}), 400
    try:
        encoded = audio_b64.split(',', 1)[1] if ',' in audio_b64 else audio_b64
        text = audio_to_text(base64.b64decode(encoded))
        if not text or not text.strip():
            return jsonify({'status': 'error', 'msg': '语音识别结果为空'}), 400
        return jsonify({'status': 'success', 'text': text.strip()})
    except Exception as exc:
        logger.error('ASR 失败: %s', exc)
        return jsonify({'status': 'error', 'msg': f'语音识别失败：{exc}'}), 500


# ================================================================
# 向导问答（Agent 多步工具 + SSE）
# ================================================================

@api_bp.route('/chat', methods=['POST'])
@auth_required
def chat():
    user_id = get_current_user_id()
    data = request.get_json(silent=True) or {}
    msg = (data.get('message') or '').strip()
    audio_b64 = data.get('audio')
    image_b64 = data.get('image')
    session_id = data.get('session_id')

    asr_text = None
    if audio_b64 and not msg:
        try:
            encoded = audio_b64.split(',', 1)[1] if ',' in audio_b64 else audio_b64
            asr_result = audio_to_text(base64.b64decode(encoded))
            if not asr_result or not asr_result.strip():
                def err_gen():
                    yield _sse_event({'type': 'error', 'text': '语音识别结果为空，请重新录音'})
                return Response(stream_with_context(err_gen()), mimetype='text/event-stream')
            msg = asr_result.strip()
            asr_text = msg
        except Exception as exc:
            logger.error('语音转文字失败: %s', exc, exc_info=True)
            error_text = f'语音识别失败：{exc}'
            def err_gen():
                yield _sse_event({'type': 'error', 'text': error_text})
            return Response(stream_with_context(err_gen()), mimetype='text/event-stream')

    if not msg and not image_b64:
        return jsonify({'error': '消息内容为空'}), 400
    if not session_id:
        return jsonify({'error': '缺少 session_id'}), 400

    sess = ChatSession.query.get(session_id)
    if not sess or sess.user_id != user_id:
        return jsonify({'error': '无效的 session_id'}), 403

    user_content = msg or '[发送了一张图片]'
    db.session.add(ChatHistory(session_id=session_id, role='user', content=user_content))
    db.session.commit()
    _maybe_auto_rename_session(sess, msg or user_content)

    history_rows = (
        ChatHistory.query.filter_by(session_id=session_id)
        .order_by(ChatHistory.id.desc())
        .limit(12)
        .all()
    )
    history = [{'role': h.role, 'content': h.content} for h in reversed(history_rows)]

    # 浏览器 GPS（前端可选传入）；优先于 IP，供空间 Agent 附近检索 / 路线
    user_lng = data.get('lng', data.get('longitude'))
    user_lat = data.get('lat', data.get('latitude'))
    user_city = (data.get('city') or '').strip() or None
    user_citycode = (data.get('citycode') or '').strip() or None
    from features.agent.memory import dump_memory_json, load_memory_json
    from features.agent.session_schema import ensure_chat_session_memory_schema
    try:
        ensure_chat_session_memory_schema()
    except Exception:
        pass
    session_memory = load_memory_json(getattr(sess, 'memory_json', None))
    agent = HeritageAgent(
        image_b64=image_b64,
        user_id=user_id,
        user_lng=user_lng,
        user_lat=user_lat,
        user_city=user_city,
        user_citycode=user_citycode,
        session_memory=session_memory,
    )
    app_ctx = current_app._get_current_object()

    def generate():
        if asr_text:
            yield _sse_event({'type': 'asr', 'text': asr_text})

        full_response = ''
        for event in agent.run(msg or '请分析这张图片中的非遗内容', history=history):
            etype = event.get('type')
            if etype == 'text':
                full_response += event.get('text', '')
            yield _sse_event(event)
            if etype == 'done':
                break

        with app_ctx.app_context():
            raw = strip_legacy_spark_error_text(full_response or '') or '（无文本回复）'
            preferred = infer_suggest_path(msg or user_content, agent._scratchpad)
            normalized = normalize_agent_suggest_links(
                enforce_suggest_path(raw, preferred),
                preferred_path=preferred,
            )
            db.session.add(ChatHistory(
                session_id=session_id,
                role='assistant',
                content=normalized,
            ))
            # 持久化会话记忆（研学目标等）
            try:
                s2 = ChatSession.query.get(session_id)
                if s2 and s2.user_id == user_id:
                    s2.memory_json = dump_memory_json(agent.session_memory)
            except Exception as exc:
                logger.warning('保存会话记忆失败: %s', exc)
            db.session.commit()

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


# ================================================================
# 5. 非遗识图
# ================================================================

@api_bp.route('/analyze_source', methods=['POST'])
@auth_required
def analyze_source():
    user_id = get_current_user_id()
    data    = request.get_json(silent=True) or {}

    img_raw = data.get('image', '')
    if not img_raw:
        return jsonify({'status': 'error', 'msg': '未收到图片数据'}), 400

    # 兼容 data:image/...;base64,XXX 格式
    img_b64 = img_raw.split(',')[1] if ',' in img_raw else img_raw

    from features.demo.service import (
        apply_simulate_delay,
        get_cached_source,
        get_demo_analyze_result,
        set_cached_source,
    )

    if Config.DEMO_MODE:
        from features.demo.service import demo_simulate_working
        demo_simulate_working()
        ai_analysis, markers, target_city = get_demo_analyze_result(img_b64)
        payload = {'status': 'success', 'ai_text': ai_analysis, 'markers': markers, 'city': target_city}
        session_id = data.get('session_id')
        if session_id:
            sess = ChatSession.query.get(session_id)
            if sess and sess.user_id == user_id:
                db.session.add(ChatHistory(session_id=session_id, role='user', content='[发送了一张图片用于溯源]'))
                db.session.add(ChatHistory(session_id=session_id, role='assistant',
                                           content=f'【图片分析结果】\n{ai_analysis}'))
                db.session.commit()
        return jsonify(payload)

    cached = get_cached_source(img_b64)
    if cached:
        apply_simulate_delay()
        if cached.get('markers'):
            cached = {
                **cached,
                'markers': cached['markers'][:Config.SOURCE_TRACE_MAX_MARKERS],
            }
        return jsonify(cached)

    voice_hint = (data.get('voice_hint') or '').strip()
    prompt = (
        '请识别图片中的地点和非遗内容。\n'
        '图片可能涉及多个城市、多个非遗项目，请逐一列出，每项占一行，格式如下：\n'
        '【非遗条目】：XX省XX市 | 非遗项目名称\n'
        '注意：城市必须精确到市级，若无法确定具体市请写该省省会城市。\n'
        '例如广东非遗应区分：粤剧→广州市，英歌舞→汕头市，醒狮→佛山市\n'
        '示例输出（仅供参考格式）：\n'
        '【非遗条目】：广州市 | 粤剧\n'
        '【非遗条目】：汕头市 | 英歌舞\n'
        '【非遗条目】：苏州市 | 苏绣\n'
        '最后一行：用一句话生动描述该图片所呈现的非遗文化特色。\n'
        '注意：只输出上述格式，不要多余文字。'
    )
    if voice_hint:
        prompt += f'\n用户语音补充说明：{voice_hint}'
    ai_analysis = understand_image(img_b64, prompt) or ''
    if ai_analysis.startswith('【识图失败】'):
        return jsonify({
            'status': 'error',
            'msg': ai_analysis,
            'ai_text': ai_analysis,
            'markers': [],
            'city': '',
        }), 502

    entries = []
    for line in ai_analysis.split('\n'):
        line = line.strip()
        if '【非遗条目】：' in line:
            body = line.replace('【非遗条目】：', '').strip()
            if '|' in body:
                city_raw, kw_raw = body.split('|', 1)
            else:
                city_raw, kw_raw = body, ''
            city = _normalize_city(city_raw)
            kw   = kw_raw.strip()[:10] or None
            entries.append((city, kw))

    if not entries:
        return jsonify({
            'status': 'error',
            'msg': (
                '识图未解析出【非遗条目】城市/项目，已取消默认北京以免地点错误。'
                f'模型原文：{ai_analysis[:400] or "（空）"}'
            ),
            'ai_text': ai_analysis,
            'markers': [],
            'city': '',
        }), 422

    markers = collect_markers_for_entries(entries)
    target_city = entries[0][0]
    apply_marker_intros(markers, city=target_city)

    # 写入聊天记录（校验会话归属）
    session_id = data.get('session_id')
    if session_id:
        sess = ChatSession.query.get(session_id)
        if sess and sess.user_id == user_id:
            db.session.add(ChatHistory(session_id=session_id, role='user', content='[发送了一张图片用于溯源]'))
            db.session.add(ChatHistory(session_id=session_id, role='assistant',
                                       content=f'【图片分析结果】\n{ai_analysis}'))
            db.session.commit()

    payload = {'status': 'success', 'ai_text': ai_analysis, 'markers': markers, 'city': target_city}
    set_cached_source(img_b64, payload)
    return jsonify(payload)


# ================================================================
# 5-b. 非遗识别溯源（视频版）
# ================================================================

@api_bp.route('/analyze_source_video', methods=['POST'])
@auth_required
def analyze_source_video():
    user_id = get_current_user_id()
    data    = request.get_json(silent=True) or {}

    video_raw = data.get('video', '')
    if not video_raw:
        return jsonify({'status': 'error', 'msg': '未收到视频数据'}), 400

    # 去掉 data:video/...;base64, 前缀
    if ',' in video_raw:
        mime_part, video_b64 = video_raw.split(',', 1)
        # 提取 MIME 类型，如 video/mp4
        mime_type = mime_part.replace('data:', '').replace(';base64', '') or 'video/mp4'
    else:
        video_b64 = video_raw
        mime_type = 'video/mp4'

    # 视频文件大小限制：base64 字符数 / 1.333 ≈ 原始字节，限制约 50MB
    MAX_B64_LEN = 50 * 1024 * 1024 * 4 // 3
    if len(video_b64) > MAX_B64_LEN:
        return jsonify({'status': 'error', 'msg': '视频文件过大，请上传 50MB 以内的视频'}), 400

    if Config.DEMO_MODE:
        from features.demo.service import demo_simulate_working, get_demo_analyze_result
        demo_simulate_working()
        ai_analysis, markers, target_city = get_demo_analyze_result()
        return jsonify({'status': 'success', 'ai_text': ai_analysis, 'markers': markers, 'city': target_city})

    prompt = (
        '请识别视频中出现的所有地点和非遗内容。\n'
        '视频可能涉及多个城市、多个非遗项目，请逐一列出，每项占一行，格式如下：\n'
        '【非遗条目】：XX省XX市 | 非遗项目名称\n'
        '注意：城市必须精确到市级，若无法确定具体市请写该省省会城市。\n'
        '例如：\n'
        '【非遗条目】：广东省广州市 | 粤剧\n'
        '【非遗条目】：广东省汕头市 | 英歌舞\n'
        '最后一行：用一句话生动描述该视频所呈现的非遗文化特色。\n'
        '注意：只输出上述格式，不要多余文字。'
    )

    ai_analysis, video_err = understand_video(video_b64, prompt, mime_type)

    if not ai_analysis:
        return jsonify({
            'status': 'error',
            'msg': video_err or '视频理解失败，请检查 VIDEO_API_KEY（或 DASHSCOPE_API_KEY）配置或重试',
        }), 500

    # 解析多条【非遗条目】，每条独立查高德，最终合并去重
    entries = []   # [(city, keyword), ...]
    for line in ai_analysis.split('\n'):
        line = line.strip()
        if '【非遗条目】：' in line:
            body = line.replace('【非遗条目】：', '').strip()
            if '|' in body:
                city_raw, kw_raw = body.split('|', 1)
            else:
                city_raw, kw_raw = body, ''
            city = _normalize_city(city_raw)
            kw   = kw_raw.strip()[:10] or None
            entries.append((city, kw))

    # 兜底：模型没输出条目时，用通用词搜一次
    if not entries:
        entries = [('广州市', None)]

    markers = collect_markers_for_entries(entries)
    # 返回给前端展示的代表城市（取第一条）
    target_city = entries[0][0] if entries else '广州市'
    apply_marker_intros(markers, city=target_city)

    # 写入聊天记录
    session_id = data.get('session_id')
    if session_id:
        sess = ChatSession.query.get(session_id)
        if sess and sess.user_id == user_id:
            db.session.add(ChatHistory(session_id=session_id, role='user', content='[发送了一段视频用于溯源]'))
            db.session.add(ChatHistory(session_id=session_id, role='assistant',
                                       content=f'【视频分析结果】\n{ai_analysis}'))
            db.session.commit()

    return jsonify({'status': 'success', 'ai_text': ai_analysis, 'markers': markers, 'city': target_city})

@api_bp.route('/generate_art', methods=['POST'])
@auth_required
def generate_art():
    user_id = get_current_user_id()
    req     = request.get_json(silent=True) or {}

    user_prompt       = req.get('prompt', '将此图片转换为具有现代美感的风格')
    frontend_image_b64 = req.get('image', None)
    session_id        = req.get('session_id')

    image_b64 = None
    if frontend_image_b64:
        try:
            raw = frontend_image_b64.split(',')[1] if ',' in frontend_image_b64 else frontend_image_b64
            img = Image.open(io.BytesIO(base64.b64decode(raw)))
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.thumbnail((512, 512))  # 与 TTI 接口一致，减小上传体积、降低 status=4 失败率
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=80)
            image_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        except Exception as e:
            logger.error('图片解析失败: %s', e)
            return jsonify({'status': 'error', 'msg': '图片解析失败，请换一张图片试试。'})

    task_id = str(uuid.uuid4())
    image_tasks[task_id] = {'status': 'processing', 'created_at': time.time()}

    def run_task(tid, prompt, b64_img, sid, uid):
        try:
            result = execute_zhipu_art_generation(prompt, b64_img)
            if result.get('success'):
                img_data  = result['data']
                if isinstance(img_data, list):
                    img_data = img_data[0] if img_data else ''
                final_url = normalize_art_result_url(img_data)
                image_tasks[tid] = {'status': 'success', 'url': final_url, 'created_at': time.time()}
                app_obj = current_app._get_current_object()
                with app_obj.app_context():
                    save_user_artwork(uid, prompt, final_url, result.get('analysis', ''), 'revive')
                    if sid:
                        sess = ChatSession.query.get(sid)
                        if sess and sess.user_id == uid:
                            note = f'【系统提示：您刚刚使用非遗焕新功能，将非遗元素重构为了：{prompt}】'
                            db.session.add(ChatHistory(session_id=sid, role='assistant', content=note))
                            db.session.commit()
            else:
                image_tasks[tid] = {'status': 'error', 'msg': result.get('msg', '生成失败'),
                                    'created_at': time.time()}
        except Exception as e:
            logger.error('生图任务异常: %s', e)
            image_tasks[tid] = {'status': 'error', 'msg': f'系统内部异常: {e}', 'created_at': time.time()}

    threading.Thread(target=run_task, args=(task_id, user_prompt, image_b64, session_id, user_id),
                     daemon=True).start()

    return jsonify({'status': 'accepted', 'task_id': task_id})


@api_bp.route('/generate_art/stream', methods=['POST'])
@auth_required
def generate_art_stream():
    """非遗焕新 SSE：推送 GLM-4V 分析 → CogView-4 生成各阶段进度。"""
    req = request.get_json(silent=True) or {}
    user_prompt = req.get('prompt', '将此图片转换为具有现代美感的风格')
    frontend_image_b64 = req.get('image')

    image_b64 = None
    if frontend_image_b64:
        try:
            raw = frontend_image_b64.split(',')[1] if ',' in frontend_image_b64 else frontend_image_b64
            img = Image.open(io.BytesIO(base64.b64decode(raw)))
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.thumbnail((512, 512))
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=80)
            image_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        except Exception as e:
            logger.error('图片解析失败: %s', e)
            def err_gen():
                yield _sse_event({'type': 'error', 'msg': '图片解析失败，请换一张图片试试。'})
            return Response(stream_with_context(err_gen()), mimetype='text/event-stream')

    uid = get_current_user_id()

    def generate():
        final_url = None
        analysis = ''
        for event in iter_zhipu_art_generation(user_prompt, image_b64):
            if event['type'] == 'progress':
                yield _sse_event({
                    'type': 'progress',
                    'stage': event.get('stage'),
                    'text': event.get('text', ''),
                })
            elif event['type'] == 'result':
                if not event.get('success'):
                    yield _sse_event({'type': 'error', 'msg': event.get('msg', '生成失败')})
                    return
                final_url = normalize_art_result_url(event.get('data') or '')
                analysis = event.get('analysis') or ''
                try:
                    save_user_artwork(uid, user_prompt, final_url, analysis, 'revive')
                except Exception as exc:
                    logger.warning('焕新作品入库失败（不影响返回图片）: %s', exc)
                yield _sse_event({
                    'type': 'done',
                    'url': final_url,
                    'analysis': analysis,
                })
        if not final_url:
            yield _sse_event({'type': 'error', 'msg': '生图流程异常结束'})

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@api_bp.route('/query_art/<task_id>', methods=['GET'])
@auth_required
def query_art(task_id):
    task = image_tasks.get(task_id)
    if not task:
        return jsonify({'status': 'error', 'msg': '任务不存在或已过期'}), 404
    return jsonify(task)


# ================================================================
# 7. 语音合成（TTS）
# ================================================================

@api_bp.route('/stream_voice', methods=['GET', 'POST'])
@auth_required
def stream_voice():
    # 优先取 POST JSON body，兼容旧版 GET 参数
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        text = data.get('text', '').strip()
    else:
        text = request.args.get('text', '').strip()

    if not text:
        return jsonify({'error': '缺少 text 参数'}), 400
    # 讯飞 TTS 单次上限约 8000 字节，汉字约 2600 字，截断保护
    if len(text.encode('utf-8')) > 7800:
        text = text.encode('utf-8')[:7800].decode('utf-8', errors='ignore')

    # aue=raw 返回 16k 16bit 单声道 PCM，前端用 AudioContext 解码播放
    return Response(
        stream_with_context(get_tts_audio(text)),
        mimetype='audio/pcm',
        headers={
            'X-Sample-Rate': '16000',
            'X-Bit-Depth': '16',
            'X-Channels': '1',
        }
    )


# ================================================================
# 8. 知识图谱数据
# ================================================================

@api_bp.route('/graph_data')
@auth_required   # 修复：补充鉴权，防止未登录访问
def get_graph_data():
    conn = pymysql.connect(
        host=Config.DB_HOST, user=Config.DB_USER,
        password=Config.DB_PASS, database=Config.DB_NAME,
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with conn.cursor() as cursor:
            nodes, edges = build_graph_payload(cursor)
    finally:
        conn.close()

    return jsonify({'nodes': nodes, 'edges': edges})


@api_bp.route('/graph/query', methods=['POST'])
@auth_required
def graph_query():
    """图谱专项问答：返回答案与可高亮节点 ID 列表。"""
    data = request.get_json(silent=True) or {}
    question = (data.get('question') or '').strip()
    if not question:
        return jsonify({'status': 'error', 'msg': '问题不能为空'}), 400

    result = graph_engine.query_structured(question)
    return jsonify({
        'status': 'success' if result.get('ok') else 'error',
        'answer': result.get('answer', ''),
        'related_nodes': result.get('node_ids', []),
        'sql': result.get('sql', ''),
    })


# ================================================================
# AI 非遗游览路线规划
# ================================================================

def _get_amap_driving_route(origin_lng, origin_lat, waypoints, dest_lng, dest_lat):
    """高德驾车路径规划 v3（strategy=0 最快）。"""
    import requests as _req
    origin      = f'{origin_lng},{origin_lat}'
    destination = f'{dest_lng},{dest_lat}'
    wp_str      = ';'.join([f'{p[0]},{p[1]}' for p in waypoints]) if waypoints else ''
    params = {
        'key':         Config.AMAP_API_KEY,
        'origin':      origin,
        'destination': destination,
        'strategy':    0,
        'output':      'json',
    }
    if wp_str:
        params['waypoints'] = wp_str
    try:
        res = _req.get('https://restapi.amap.com/v3/direction/driving',
                       params=params, timeout=8).json()
        if res.get('status') == '1' and res.get('route', {}).get('paths'):
            path     = res['route']['paths'][0]
            duration = int(path.get('duration', 0))
            distance = int(path.get('distance', 0))
            polyline_pts = []
            for step in path.get('steps', []):
                for pt in step.get('polyline', '').split(';'):
                    parts = pt.split(',')
                    if len(parts) == 2:
                        try:
                            polyline_pts.append([float(parts[0]), float(parts[1])])
                        except ValueError:
                            pass
            return {'duration': duration, 'distance': distance, 'polyline': polyline_pts}
    except Exception as exc:
        logger.error('高德驾车路径失败: %s', exc)
    return None


def _get_amap_transit_route(origin_lng, origin_lat, dest_lng, dest_lat, city):
    """高德公共交通路径规划 v3（strategy=0 最快）。"""
    import requests as _req
    params = {
        'key':         Config.AMAP_API_KEY,
        'origin':      f'{origin_lng},{origin_lat}',
        'destination': f'{dest_lng},{dest_lat}',
        'city':        city,
        'strategy':    0,
        'output':      'json',
    }
    try:
        res = _req.get('https://restapi.amap.com/v3/direction/transit/integrated',
                       params=params, timeout=8).json()
        if res.get('status') == '1' and res.get('route', {}).get('transits'):
            best = res['route']['transits'][0]
            return {
                'duration':         int(best.get('duration', 0)),
                'distance':         int(res['route'].get('distance', 0)),
                'walking_distance': int(best.get('walking_distance', 0)),
            }
    except Exception as exc:
        logger.error('高德公交路径失败: %s', exc)
    return None


@api_bp.route('/route_plan', methods=['POST'])
@auth_required
def route_plan():
    """
    AI 非遗路线规划。
    请求 JSON:
      city        目标城市（如 "苏州市"）
      preference  偏好描述（如 "想了解刺绣类"）
      origin_lng  用户当前经度（来自前端 IP 定位）
      origin_lat  用户当前纬度
    返回 JSON:
      status      success / error
      stops       [{id, name, lng, lat, address, ai_intro, tts_text}, ...]
      ai_summary  AI 生成的路线总结（一段话）
      driving     {duration, distance, polyline}  驾车最快路线
      transit     {duration, distance, walking_distance} 或 null
    """
    data       = request.get_json(silent=True) or {}
    city       = (data.get('city') or '').strip()
    preference = (data.get('preference') or '').strip()
    origin_lng = data.get('origin_lng')
    origin_lat = data.get('origin_lat')

    if not city:
        city = get_amap_location(get_client_ip_from_request(request))

    # ── Step1: 高德搜索候选地点 ──────────────────────────────
    import re as _re
    pref_keyword = None
    if preference:
        m = _re.search(r'[\u4e00-\u9fa5]{2,6}', preference)
        if m:
            pref_keyword = m.group(0)

    markers = get_markers_from_amap(city, pref_keyword)
    if not markers:
        markers = get_markers_from_amap(city)
    if not markers:
        return jsonify({'status': 'error', 'msg': f'未找到{city}的非遗地点，请尝试其他城市'})

    # 最多取 5 个地点做路线
    candidates = markers[:5]
    apply_marker_intros(candidates, city=city)

    # ── Step2: LLM 按偏好排序 + 生成讲解文本 ─────────────────
    cand_desc = '\n'.join(
        [f'{i+1}. {c["base_name"]}（{c.get("address","无地址")}）'
         for i, c in enumerate(candidates)]
    )
    pref_hint = f'用户偏好：{preference}' if preference else '用户希望综合参观'
    llm_prompt = f"""你是非遗游览路线规划专家。请根据以下信息完成任务。

城市：{city}
{pref_hint}

候选地点列表（按编号）：
{cand_desc}

请完成以下两项任务，严格按格式输出，不要多余文字：

【任务1】推荐游览顺序（从候选列表中选3~5个，按参观顺序排列，每行一个编号）：
ORDER:编号1,编号2,编号3,...

【任务2】为每个入选地点写一句30字以内的语音讲解词（格式：编号|讲解词）：
TTS:1|讲解词
TTS:2|讲解词
...

【任务3】用一句60字以内的话总结本次路线亮点：
SUMMARY:总结内容"""

    llm_result = sync_spark_call(llm_prompt)
    logger.info('LLM 路线规划结果: %s', llm_result)

    # ── Step3: 解析 LLM 输出 ──────────────────────────────────
    order_ids   = []
    tts_map     = {}
    ai_summary  = f'已规划【{city}】非遗相关游览路线，共多处地标。'

    for line in llm_result.split('\n'):
        line = line.strip()
        if line.startswith('ORDER:'):
            raw = line.replace('ORDER:', '').strip()
            for tok in _re.split(r'[,，、\s]+', raw):
                tok = tok.strip()
                if tok.isdigit():
                    order_ids.append(int(tok))
        elif line.startswith('TTS:'):
            raw = line.replace('TTS:', '').strip()
            parts = raw.split('|', 1)
            if len(parts) == 2 and parts[0].strip().isdigit():
                tts_map[int(parts[0].strip())] = parts[1].strip()
        elif line.startswith('SUMMARY:'):
            s = line.replace('SUMMARY:', '').strip()
            if s:
                ai_summary = s

    # fallback：若 LLM 没有输出 ORDER，按原始顺序取全部
    if not order_ids:
        order_ids = list(range(1, len(candidates) + 1))

    # 去重、过滤越界
    seen = set()
    order_ids_clean = []
    for oid in order_ids:
        if 1 <= oid <= len(candidates) and oid not in seen:
            order_ids_clean.append(oid)
            seen.add(oid)
    if not order_ids_clean:
        order_ids_clean = list(range(1, min(4, len(candidates) + 1)))

    # 构建站点列表
    stops = []
    for oid in order_ids_clean:
        c = candidates[oid - 1]
        tts_text = tts_map.get(oid, c.get('ai_intro') or c['base_name'])
        stops.append({
            'id':       c['id'],
            'name':     c['base_name'],
            'lng':      c['lng'],
            'lat':      c['lat'],
            'address':  c.get('address', ''),
            'ai_intro': c.get('ai_intro', ''),
            'tts_text': tts_text,
        })

    if not stops:
        return jsonify({'status': 'error', 'msg': 'AI 规划失败，请重试'})

    # ── Step4: 高德路径规划（起点 → 各站点 → 终点）────────────
    # 用用户 IP 经纬度作为起点；若拿不到，用第一站作为起点
    if origin_lng and origin_lat:
        o_lng, o_lat = float(origin_lng), float(origin_lat)
    else:
        o_lng, o_lat = float(stops[0]['lng']), float(stops[0]['lat'])

    dest = stops[-1]
    d_lng, d_lat = float(dest['lng']), float(dest['lat'])

    waypoints = [(float(s['lng']), float(s['lat'])) for s in stops[:-1]]
    # 去掉起点（避免起点==第一途径点时重复）
    if waypoints and abs(waypoints[0][0] - o_lng) < 0.001 and abs(waypoints[0][1] - o_lat) < 0.001:
        waypoints = waypoints[1:]

    driving_info = _get_amap_driving_route(o_lng, o_lat, waypoints, d_lng, d_lat)
    transit_info = _get_amap_transit_route(o_lng, o_lat, d_lng, d_lat, city)

    return jsonify({
        'status':     'success',
        'city':       city,
        'stops':      stops,
        'ai_summary': ai_summary,
        'driving':    driving_info,
        'transit':    transit_info,
    })


# ================================================================
# 新增：IP 定位接口（代理高德，返回城市 + 经纬度）
# ================================================================

@api_bp.route('/get_location', methods=['GET'])
@auth_required
def get_location():
    """
    定位：仅 ?lng=&lat=（浏览器精确位置 + 逆地理）。IP 定位已停用。
    """
    gps_lng = request.args.get('lng')
    gps_lat = request.args.get('lat')
    if gps_lng is None or gps_lat is None or not str(gps_lng).strip() or not str(gps_lat).strip():
        return jsonify({
            'status': 'error',
            'loc_error': '缺少浏览器坐标 lng/lat（已关闭 IP 定位）',
            'loc_source': '',
        }), 400
    geo = resolve_geo_from_lnglat(gps_lng, gps_lat)
    if geo.get('status') == 'success' and geo.get('city'):
        return jsonify(geo)
    # GPS 失败不再回退 IP
    return jsonify(geo), 400


# ================================================================
# 新增：单目的地路线规划（4种方式），前端点击非遗地点后调用
# ================================================================

@api_bp.route('/direction', methods=['POST'])
@auth_required
def direction():
    """四种交通方式的单段路线规划，逻辑委托 direction_service。"""
    data = request.get_json(silent=True) or {}
    result = plan_direction(
        data.get('origin_lng'),
        data.get('origin_lat'),
        data.get('dest_lng'),
        data.get('dest_lat'),
        (data.get('mode') or 'driving').lower(),
        data.get('citycode', '010'),
    )
    if result.get('status') == 'error':
        code = 400 if '不支持' in result.get('msg', '') else 500
        return jsonify(result), code
    return jsonify(result)
