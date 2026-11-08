"""共享工具层。

按职责分为：星火对话/语音、图像与视频理解、高德地图检索、
知识图谱 RAG、数字焕新（视觉识别 + 文生图）等。
"""

import _thread as thread
import base64
import hashlib
import hmac
import io
import ipaddress
import json
import logging
import os
import queue
import re
import ssl
import time
import uuid
from datetime import datetime
from time import mktime
from urllib.parse import urlencode, urlparse
from wsgiref.handlers import format_date_time

import requests
import websocket

from core.config import Config

logger = logging.getLogger(__name__)

# RAG 单例（懒加载；勿在模块顶层 import torch/HuggingFace，否则启动即占满页面文件）
_rag_instance = None


# ================================================================
# 1. 鉴权签名工具（讯飞通用）
# ================================================================

def create_auth_url(request_url, api_key, api_secret, path):
    """生成讯飞 WebSocket 接口的 HMAC-SHA256 鉴权 URL。"""
    url    = urlparse(request_url)
    date   = format_date_time(mktime(datetime.now().timetuple()))
    sig_origin = f'host: {url.netloc}\ndate: {date}\nGET {path} HTTP/1.1'
    sig_sha    = hmac.new(api_secret.encode('utf-8'), sig_origin.encode('utf-8'),
                          digestmod=hashlib.sha256).digest()
    sig_b64    = base64.b64encode(sig_sha).decode('utf-8')
    auth_origin = (f'api_key="{api_key}", algorithm="hmac-sha256", '
                   f'headers="host date request-line", signature="{sig_b64}"')
    authorization = base64.b64encode(auth_origin.encode('utf-8')).decode('utf-8')
    params = {'authorization': authorization, 'date': date, 'host': url.netloc}
    return request_url + '?' + urlencode(params)


# ================================================================
# 2. 语音转文字（IAT）—— 讯飞大模型中文语音识别 API
#    接口地址：wss://iat.xf-yun.com/v1
#    文档：https://www.xfyun.cn/doc/spark/spark_zh_iat.html
# ================================================================

def audio_to_text(audio_bytes):
    """
    调用讯飞「中英识别大模型」将 PCM/WAV 音频转为文字。
    接口要求：
      - URL:  wss://iat.xf-yun.com/v1
      - 音频: 16k 采样率、16bit、单声道、raw(PCM) 格式
      - 每帧: 1280 字节，间隔 40ms
      - domain 必须为 'slm'（大模型接口固定值）
      - payload.audio 中必须携带 channels / bit_depth / seq / status 字段
    """
    if not audio_bytes:
        return ''

    # WAV 文件头 44 字节，需跳过只取 PCM 数据
    pcm_bytes = audio_bytes[44:] if audio_bytes[:4] == b'RIFF' else audio_bytes

    state = {'text': '', 'error': None}

    def on_message(ws, message):
        try:
            msg = json.loads(message)
            header = msg.get('header') or {}
            code = header.get('code', -1)
            # 握手/会话类消息可能只有 code，无 status
            status = header.get('status')
            if code != 0:
                state['error'] = f"IAT 错误码 {code}: {header.get('message', '')}"
                logger.error('IAT 服务端报错: %s', state['error'])
                ws.close()
                return
            payload = msg.get('payload') or {}
            if payload.get('result'):
                raw_b64 = payload['result'].get('text') or ''
                if raw_b64:
                    text_data = json.loads(base64.b64decode(raw_b64).decode('utf-8'))
                    pgs = text_data.get('pgs', 'apd')
                    rg = text_data.get('rg', [])
                    seg = ''
                    for item in text_data.get('ws', []):
                        for cw in item.get('cw', []):
                            seg += cw.get('w', '')
                    if pgs == 'rpl' and len(rg) == 2:
                        pass
                    state['text'] += seg
            audio_st = (payload.get('audio') or {}).get('status')
            if status == 2 or audio_st == 2:
                ws.close()
        except Exception as e:
            logger.warning('IAT on_message 解析异常: %s | raw=%s', e, str(message)[:200])
            # 非致命格式差异时不主动关连接，避免整段识别失败
            if state['error'] is None and isinstance(message, str) and '"code":' in message:
                try:
                    hdr = json.loads(message).get('header') or {}
                    if hdr.get('code', 0) != 0:
                        state['error'] = hdr.get('message') or str(e)
                        ws.close()
                except Exception:
                    pass

    def on_error(ws, error):
        state['error'] = str(error)
        logger.error('IAT WebSocket 错误: %s', error)

    def on_close(ws, close_status_code, close_msg):
        logger.info('IAT WebSocket 关闭: %s %s', close_status_code, close_msg)

    def on_open(ws):
        def run():
            frame_size = 1280   # 官方规定 1280 字节/帧
            interval   = 0.04   # 官方规定 40ms 间隔
            seq        = 0      # 帧序号

            # 官方要求：parameter 只在第一帧发送
            iat_params = {
                'domain':   'slm',       # 大模型接口固定值
                'language': 'zh_cn',
                'accent':   'mandarin',
                'eos':      6000,        # 静音 6 秒后停止
                'result': {
                    'encoding': 'utf8',
                    'compress': 'raw',
                    'format':   'json'   # 官方 Demo 用 json，不是 plain
                }
            }

            fp     = io.BytesIO(pcm_bytes)
            status = 0  # 0=首帧 1=中间帧 2=末帧

            try:
                while True:
                    buf = fp.read(frame_size)
                    seq += 1

                    if not buf:
                        # 发末帧（空 audio）
                        frame = {
                            'header': {
                                'app_id': Config.SPARK_APPID,
                                'status': 2
                            },
                            'payload': {
                                'audio': {
                                    'encoding':    'raw',
                                    'sample_rate': 16000,
                                    'channels':    1,
                                    'bit_depth':   16,
                                    'seq':         seq,
                                    'status':      2,
                                    'audio':       ''
                                }
                            }
                        }
                        ws.send(json.dumps(frame))
                        break

                    audio_b64 = base64.b64encode(buf).decode('utf-8')

                    if status == 0:
                        # 首帧：携带 parameter
                        frame = {
                            'header': {
                                'app_id': Config.SPARK_APPID,
                                'status': 0
                            },
                            'parameter': {
                                'iat': iat_params
                            },
                            'payload': {
                                'audio': {
                                    'encoding':    'raw',
                                    'sample_rate': 16000,
                                    'channels':    1,
                                    'bit_depth':   16,
                                    'seq':         seq,
                                    'status':      0,
                                    'audio':       audio_b64
                                }
                            }
                        }
                        status = 1
                    else:
                        # 中间帧：不含 parameter
                        frame = {
                            'header': {
                                'app_id': Config.SPARK_APPID,
                                'status': 1
                            },
                            'payload': {
                                'audio': {
                                    'encoding':    'raw',
                                    'sample_rate': 16000,
                                    'channels':    1,
                                    'bit_depth':   16,
                                    'seq':         seq,
                                    'status':      1,
                                    'audio':       audio_b64
                                }
                            }
                        }

                    ws.send(json.dumps(frame))
                    time.sleep(interval)

            except Exception as e:
                logger.error('IAT 发送帧异常: %s', e)
                ws.close()

        thread.start_new_thread(run, ())

    # 官方新接口地址（大模型版）
    IAT_URL = 'wss://iat.xf-yun.com/v1'
    ws_url  = create_auth_url(
        IAT_URL,
        Config.SPARK_API_KEY,
        Config.SPARK_API_SECRET,
        urlparse(IAT_URL).path
    )

    logger.info('IAT 连接 URL: %s', ws_url[:80] + '...')
    ws = websocket.WebSocketApp(
        ws_url,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open,
    )
    ws.run_forever(sslopt={'cert_reqs': ssl.CERT_NONE}, ping_timeout=15)

    logger.info('IAT 完成，error=%s, text=%r', state["error"], state["text"])
    if state['error']:
        logger.error('IAT 最终失败: %s', state['error'])
        return ''

    return state['text'].strip()

# ================================================================
# 3. 星火大模型（统一 WebSocket + 用户可见错误文案）
# ================================================================

_LEGACY_SPARK_ERR_RE = re.compile(
    r'\[接口错误\s*\d+\][^\n]*|'
    r'\[连接错误\][^\n]*',
    re.IGNORECASE,
)


def format_spark_user_error(code=None, message=None) -> str:
    """将讯飞错误码转为用户可读提示，并附带原始 code/msg 便于排查。"""
    msg = (message or '').strip()
    code_i = None
    try:
        if code is not None and str(code).strip() != '':
            code_i = int(code)
    except (TypeError, ValueError):
        code_i = None

    detail = ''
    if code_i is not None or msg:
        detail = f'【原始错误】code={code_i if code_i is not None else "?"} msg={msg or "(空)"}'

    if code_i == 11200 or 'AppIdNoAuth' in msg:
        tip = (
            '星火大模型服务暂不可用（应用鉴权未通过）。'
            '请检查 backend_clean/.env 中的 SPARK_APPID、SPARK_API_KEY、SPARK_API_SECRET '
            '是否与讯飞控制台一致，并确认已开通与 generalv3 对应的模型服务。'
        )
    elif code_i in (10013, 10014, 10019) or 'licc' in msg.lower() or 'permission' in msg.lower():
        tip = '星火大模型服务暂不可用（应用未开通或已欠费），请在讯飞开放平台核对配额与权限。'
    elif code_i == 10004 or 'rate' in msg.lower() or 'limit' in msg.lower():
        tip = '星火大模型请求过于频繁，请稍后再试。'
    elif 'connect' in msg.lower() or 'timeout' in msg.lower():
        tip = '暂时无法连接星火大模型，请检查网络后重试。'
    else:
        tip = '星火大模型暂时无法生成文字说明，请稍后重试；其他功能（如地图、焕新）可能仍可使用。'

    return f'{tip}\n{detail}' if detail else tip


def strip_legacy_spark_error_text(text: str) -> str:
    """移除旧版写入回答正文的 [接口错误 …] 片段。"""
    if not text:
        return ''
    cleaned = _LEGACY_SPARK_ERR_RE.sub('', text)
    return re.sub(r'\n{3,}', '\n\n', cleaned).strip()


def _spark_chat_once(prompt, *, temperature=0.5, max_tokens=2048, uid=None):
    """
    单次星火对话。返回 (content, error)。
    error 为 None 表示成功；否则为 {'code', 'message', 'kind'}，kind 为 api|connect。
    """
    path = urlparse(Config.SPARK_URL).path
    auth_url = create_auth_url(
        Config.SPARK_URL, Config.SPARK_API_KEY, Config.SPARK_API_SECRET, path,
    )
    result_text = []
    error = None

    def on_message(ws, message):
        nonlocal error
        msg_dict = json.loads(message)
        if msg_dict['header']['code'] == 0:
            content = msg_dict['payload']['choices']['text'][0]['content']
            result_text.append(content)
            if msg_dict['payload']['choices']['status'] == 2:
                ws.close()
        else:
            error = {
                'code': msg_dict['header']['code'],
                'message': msg_dict['header'].get('message', ''),
                'kind': 'api',
            }
            logger.error(
                '讯飞接口报错 code=%s msg=%s',
                error['code'], error['message'],
            )
            ws.close()

    def on_error(ws, ws_error):
        nonlocal error
        if error is None:
            error = {'code': None, 'message': str(ws_error), 'kind': 'connect'}
            logger.error('WebSocket 报错: %s', ws_error)

    def on_open(ws):
        data = {
            'header': {'app_id': Config.SPARK_APPID, 'uid': uid or str(uuid.uuid4())},
            'parameter': {
                'chat': {
                    'domain': Config.SPARK_DOMAIN,
                    'temperature': temperature,
                    'max_tokens': max_tokens,
                },
            },
            'payload': {'message': {'text': [{'role': 'user', 'content': prompt}]}},
        }
        ws.send(json.dumps(data))

    ws = websocket.WebSocketApp(
        auth_url, on_message=on_message, on_error=on_error, on_open=on_open,
    )
    ws.run_forever(sslopt={'cert_reqs': ssl.CERT_NONE})
    return ''.join(result_text), error


def sync_spark_call_meta(prompt, *, temperature=0.1, max_tokens=1024):
    """返回 (正文, 用户提示)。成功时用户提示为 None。"""
    text, err = _spark_chat_once(
        prompt, temperature=temperature, max_tokens=max_tokens, uid='1234',
    )
    if err:
        return '', format_spark_user_error(err.get('code'), err.get('message'))
    return (text or '').strip(), None


def sync_spark_call(prompt):
    """同步调用星火；失败时返回空字符串（详情见日志，由调用方聚合提示）。"""
    text, user_err = sync_spark_call_meta(prompt)
    if user_err:
        logger.debug('sync_spark_call 失败: %s', user_err[:120])
    return text


def stream_chat_with_llm(context):
    """流式打字机输出；星火失败时不写入原始错误码，由调用方决定兜底文案。"""
    text, err = _spark_chat_once(context, temperature=0.5, max_tokens=2048)
    if err:
        return
    yield from (text or '')


# ================================================================
# 4-b. 地图标点简介（默认讯飞星火批量生成，可选百炼 Qwen）
# ================================================================

def _minimal_intro_fallback(marker: dict) -> str:
    name = marker.get('base_name') or '文化地标'
    addr = (marker.get('address') or '').strip()
    if addr:
        return f'{name}，地址：{addr}。'
    return f'{name}。'


def _dashscope_api_key() -> str:
    """有效百炼 Key；空或占位符视为未配置。"""
    key = (Config.DASHSCOPE_API_KEY or '').strip()
    if not key or key.lower().startswith('your-'):
        return ''
    return key


def _build_marker_intro_prompt(markers: list, city: str = None, for_spark: bool = False) -> str:
    lines = []
    for i, m in enumerate(markers, 1):
        lines.append(
            f'{i}. id={m.get("id")} 名称={m.get("base_name")} '
            f'类型={m.get("type") or "未知"} 地址={m.get("address") or "无"} '
            f'商圈={m.get("biz_area") or "无"}'
        )
    city_hint = f'城市：{city}\n' if city else ''
    if for_spark:
        return (
            f'{city_hint}'
            '你是非遗文化导览员。为下列文化地标各写一句简介（40~60字，中文）。\n'
            '要求：写清该点与非遗或传统文化的关系；可提地址；不要编造电话或开放时间；少用套话。\n'
            '只输出多行，每行格式为：高德id|简介。'
        '「高德id」必须与下列每行 id= 后的编码完全一致（如 B0FFxxx），禁止用馆名代替 id；不要序号、不要 markdown。\n\n'
            + '\n'.join(lines)
        )
    return (
        f'{city_hint}'
        '你是非遗文化导览员。请为下列文化地标各写一句简介（40~60字，中文）。\n'
        '要求：写清该点与非遗或传统文化的关系；可提地址；不要编造电话或开放时间；少用套话；不要列表序号。\n'
        '严格只输出 JSON 数组，每项格式：{"id":"与输入一致","intro":"简介文字"}\n\n'
        + '\n'.join(lines)
    )


def _parse_marker_intros_json(raw: str, markers: list) -> dict:
    """从模型输出解析 id -> intro 映射（仅当输出含 JSON 数组时尝试）。"""
    text = (raw or '').strip()
    if not text or '[' not in text:
        return {}

    payload = text
    if not text.startswith('['):
        m = re.search(r'\[[\s\S]*\]', text)
        if not m:
            return {}
        payload = m.group(0)

    try:
        items = json.loads(payload)
    except json.JSONDecodeError:
        logger.debug('标点简介非 JSON 格式，已跳过 JSON 解析')
        return {}

    id_set = {str(m.get('id')) for m in markers if m.get('id')}
    result = {}
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            mid = str(item.get('id', '')).strip()
            intro = (item.get('intro') or item.get('ai_intro') or '').strip()
            if mid and intro and mid in id_set:
                result[mid] = _sanitize_intro_text(intro, mid)
    return result


def _extract_id_intro_from_line(line: str, id_set: set) -> tuple:
    """
    从单行提取 (poi_id, intro)。
    支持：B0xxx|简介、id|B0xxx|简介、1. id|B0xxx|简介
    """
    line = line.strip().strip('`')
    if not line or '|' not in line:
        return None, None
    line = re.sub(r'^\d+[\.\)、]\s*', '', line)

    parts = [p.strip() for p in line.split('|') if p.strip()]
    if len(parts) < 2:
        return None, None

    mid, intro = None, None
    if parts[0].lower() == 'id' and len(parts) >= 3 and parts[1] in id_set:
        mid, intro = parts[1], '|'.join(parts[2:])
    elif parts[0].lower() == 'id' and len(parts) >= 2:
        # 星火常输出 id|馆名+简介…，未带 B0xxx，交由按序解析
        return None, None
    elif parts[0].lower().startswith('id='):
        token = parts[0][3:].strip()
        if token in id_set:
            mid, intro = token, '|'.join(parts[1:])
        elif len(parts) >= 2 and parts[1] in id_set:
            mid, intro = parts[1], '|'.join(parts[2:])
    elif parts[0] in id_set:
        mid, intro = parts[0], '|'.join(parts[1:])

    if not mid or not intro:
        return None, None
    intro = intro.strip().strip('"').strip("'")
    if intro.lower() in ('id', 'id='):
        return None, None
    return mid, intro


def _sanitize_intro_text(intro: str, poi_id: str = None) -> str:
    """去掉误写入简介开头的 POI id 前缀。"""
    intro = (intro or '').strip()
    if not intro:
        return intro
    if poi_id and intro.startswith(poi_id + '|'):
        intro = intro[len(poi_id) + 1:].strip()
    m = re.match(r'^[A-Z0-9]{8,}\|', intro)
    if m:
        intro = intro[m.end():].strip()
    return intro[:120]


def _parse_marker_intros_lines(raw: str, markers: list) -> dict:
    """解析 id|简介 行格式（适配讯飞星火输出）。"""
    id_set = {str(m.get('id')) for m in markers if m.get('id')}
    result = {}
    for line in (raw or '').split('\n'):
        mid, intro = _extract_id_intro_from_line(line, id_set)
        if mid and intro and mid not in result:
            result[mid] = _sanitize_intro_text(intro, mid)
    return result


def _extract_intro_from_spark_plain_line(line: str) -> str:
    """解析星火常见的「1. id|馆名与简介…」行，返回 id| 之后的整段文字。"""
    line = line.strip().strip('`')
    if not line:
        return ''
    line = re.sub(r'^\d+[\.\)、]\s*', '', line)
    if line.lower().startswith('id|'):
        return line[3:].strip()
    # 模型常直接输出「店名 - 品类」未带高德 id：按序兜底时当作简介正文
    if '|' not in line and len(line) >= 6:
        return line[:120]
    return ''


def _parse_marker_intros_by_order(raw: str, markers: list) -> dict:
    """按顺序兜底：每行一条简介，与 markers 按下标一一对应（允许条数不足）。"""
    id_set = {str(m.get('id')) for m in markers if m.get('id')}
    lines = []
    for line in (raw or '').split('\n'):
        intro = _extract_intro_from_spark_plain_line(line)
        if not intro or len(intro) < 8:
            _, intro = _extract_id_intro_from_line(line, id_set)
        if intro and len(intro) >= 8:
            lines.append(_sanitize_intro_text(intro))
    if not lines:
        return {}
    result = {}
    for m, intro in zip(markers, lines):
        mid = str(m.get('id', ''))
        if mid:
            result[mid] = intro
    return result


def _merge_intro_results(markers: list, *maps: dict) -> dict:
    out = {}
    for m in markers:
        mid = str(m.get('id', ''))
        for mp in maps:
            if mid and mp.get(mid):
                out[mid] = mp[mid]
                break
    return out


def _generate_marker_intros_qwen(prompt: str, markers: list) -> dict:
    """百炼 Qwen3 Max（需有效 DASHSCOPE_API_KEY）。"""
    api_key = _dashscope_api_key()
    if not api_key:
        return {}

    try:
        from openai import OpenAI
    except ImportError:
        logger.error('openai 包未安装，无法调用 Qwen 标点简介')
        return {}

    max_tokens = min(2048, 80 * len(markers) + 128)
    client = OpenAI(api_key=api_key, base_url=Config.DASHSCOPE_BASE_URL)

    completion = client.chat.completions.create(
        model=Config.QWEN_INTRO_MODEL,
        messages=[{'role': 'user', 'content': prompt}],
        temperature=0.4,
        max_tokens=max_tokens,
    )
    raw = completion.choices[0].message.content or ''
    return _parse_marker_intros_json(raw, markers)


def _generate_marker_intros_spark(markers: list, city: str = None) -> dict:
    """讯飞星火生成标点简介（默认通道，使用 .env 中 SPARK_*）。"""
    prompt = _build_marker_intro_prompt(markers, city, for_spark=True)
    try:
        raw = (sync_spark_call(prompt) or '').strip()
        if not raw:
            logger.warning('星火标点简介返回为空')
            return {}

        parsed = _merge_intro_results(
            markers,
            _parse_marker_intros_lines(raw, markers),
            _parse_marker_intros_by_order(raw, markers),
            _parse_marker_intros_json(raw, markers),
        )
        if parsed:
            logger.info('标点简介已由讯飞星火生成（%d/%d 条）', len(parsed), len(markers))
        else:
            logger.warning('星火简介解析失败，原始输出: %s', raw[:400])
        return parsed
    except Exception as e:
        logger.error('星火标点简介失败: %s', e)
        return {}


def generate_marker_intros_batch(markers: list, city: str = None) -> dict:
    """
    批量生成标点简介。
    MARKER_INTRO_PROVIDER=spark（默认）| qwen
    返回 {poi_id: intro_text}。
    """
    if not markers:
        return {}

    provider = (getattr(Config, 'MARKER_INTRO_PROVIDER', None) or 'spark').lower()

    if provider == 'qwen' and _dashscope_api_key():
        prompt = _build_marker_intro_prompt(markers, city, for_spark=False)
        try:
            parsed = _generate_marker_intros_qwen(prompt, markers)
            if parsed:
                return parsed
            logger.warning('Qwen 标点简介无有效结果，改用讯飞星火')
        except Exception as e:
            logger.warning('Qwen 标点简介失败，改用讯飞星火: %s', e)

    return _generate_marker_intros_spark(markers, city)


def apply_marker_intros(markers: list, city: str = None) -> None:
    """就地写入 markers[].ai_intro（已有 ai_intro 的条目跳过，如演示数据）。"""
    if not markers:
        return

    pending = [m for m in markers if not (m.get('ai_intro') or '').strip()]
    if not pending:
        return

    # 美食等周边直搜：不做「非遗导览」星火简介，避免格式解析失败与胡编文化套话
    heritage_pending = []
    for m in pending:
        if (m.get('match_mode') or '') == 'around_open':
            m['ai_intro'] = _minimal_intro_fallback(m)
        else:
            heritage_pending.append(m)

    if not heritage_pending:
        return

    intro_map = generate_marker_intros_batch(heritage_pending, city=city)
    for m in heritage_pending:
        mid = str(m.get('id', ''))
        raw_intro = intro_map.get(mid)
        m['ai_intro'] = (
            _sanitize_intro_text(raw_intro, mid) if raw_intro else _minimal_intro_fallback(m)
        )


# ================================================================
# 5. 图像识别（带自定义 Prompt）
# ================================================================

def strip_thinking_text(text: str) -> str:
    """移除视觉/推理模型输出中的 <think> 思考段与 <answer> 包装标签。"""
    if not text:
        return ''
    cleaned = re.sub(r'<think\b[^>]*>.*?</think\s*>', '', text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<think\b[^>]*>.*$', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'</?answer\b[^>]*>', '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def understand_image(img_b64, prompt):
    """讯飞图像理解。成功返回文本；失败返回带【原始错误】前缀的说明（便于前端/日志排查）。"""
    result = {'text': '', 'error': None}

    def on_message(ws, message):
        data = json.loads(message)
        code = data.get('header', {}).get('code', -1)
        if code != 0:
            err = data.get('header', {}).get('message', '')
            result['error'] = f'code={code} msg={err}'
            logger.error('讯飞识图报错 %s', result['error'])
            ws.close()
            return
        content = data['payload']['choices']['text'][0]['content']
        result['text'] += content
        if data['payload']['choices']['status'] == 2:
            ws.close()

    def on_error(ws, error):
        result['error'] = f'WebSocket: {error}'
        logger.error('讯飞识图连接错误: %s', error)

    def on_open(ws):
        data = {
            'header':    {'app_id': Config.SPARK_APPID, 'uid': str(uuid.uuid4())},
            'parameter': {'chat': {'domain': 'general', 'temperature': 0.5, 'max_tokens': 2048}},
            'payload':   {'message': {'text': [
                {'role': 'user', 'content': img_b64, 'content_type': 'image'},
                {'role': 'user', 'content': prompt}
            ]}}
        }
        ws.send(json.dumps(data))

    ws_url = create_auth_url(Config.IMAGE_URL, Config.SPARK_API_KEY, Config.SPARK_API_SECRET,
                             urlparse(Config.IMAGE_URL).path)
    ws = websocket.WebSocketApp(
        ws_url, on_message=on_message, on_error=on_error, on_open=on_open,
    )
    ws.run_forever(sslopt={'cert_reqs': ssl.CERT_NONE})
    if result['error'] and not result['text']:
        return f'【识图失败】【原始错误】{result["error"]}'
    return strip_thinking_text(result['text'])


def understand_video(video_b64: str, prompt: str, mime_type: str = 'video/mp4') -> tuple[str, str]:
    """
    调用阿里云百炼视频理解接口。

    :return: (分析文本, 错误信息)；成功时错误信息为空字符串
    """
    try:
        from openai import OpenAI
    except ImportError:
        logger.error('openai 包未安装，请执行 pip install openai')
        return '', '服务端未安装 openai 依赖，请执行 pip install openai'

    api_key = (Config.VIDEO_API_KEY or _dashscope_api_key()).strip()
    if not api_key:
        logger.error('VIDEO_API_KEY / DASHSCOPE_API_KEY 未配置或无效')
        return '', (
            '视频理解 API Key 未配置。请在 backend_clean/.env 中设置 VIDEO_API_KEY'
            '（或 DASHSCOPE_API_KEY）'
        )

    base_url = (Config.VIDEO_BASE_URL or Config.DASHSCOPE_BASE_URL).strip()
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    try:
        video_part = {
            'type': 'video_url',
            'video_url': {'url': f'data:{mime_type};base64,{video_b64}'},
        }
        # fps 是百炼 Qwen-VL 的采样参数；智谱等 OpenAI 兼容服务不需要
        if 'dashscope' in base_url:
            video_part['fps'] = 2

        completion = client.chat.completions.create(
            model=Config.VIDEO_MODEL,
            messages=[
                {
                    'role': 'user',
                    'content': [video_part, {'type': 'text', 'text': prompt}],
                }
            ],
        )
        text = strip_thinking_text(completion.choices[0].message.content or '')
        if not text:
            return '', '模型返回内容为空，请换较短视频重试'
        return text, ''
    except Exception as e:
        logger.error('understand_video 调用失败: %s', e)
        err = str(e)
        if '401' in err or 'invalid_api_key' in err.lower() or 'Incorrect API key' in err:
            return '', (
                '视频理解 API Key 无效（401）。请确认 backend_clean/.env 中的 '
                'VIDEO_API_KEY（或 DASHSCOPE_API_KEY）是否启用、复制完整。'
            )
        if '429' in err:
            return '', '视频理解请求过于频繁（429），请稍后再试'
        return '', f'视频理解调用失败：{err[:240]}'


# ================================================================
# 6. 高德地图打点
# ================================================================

def collect_markers_for_entries(entries, max_count=None):
    """
    按 (城市, 非遗关键词) 列表聚合高德 POI，去重并限制总数。
    entries: [(city, keyword_or_None), ...]
    """
    limit = max_count if max_count is not None else Config.SOURCE_TRACE_MAX_MARKERS
    seen_ids = set()
    all_markers = []
    for city, kw in entries:
        if len(all_markers) >= limit:
            break
        for m in get_markers_from_amap(city, kw):
            if m['id'] not in seen_ids:
                seen_ids.add(m['id'])
                all_markers.append(m)
                if len(all_markers) >= limit:
                    break
    return all_markers


def _amap_poi_to_marker(poi: dict) -> dict:
    loc = (poi.get('location') or ',').split(',')
    return {
        'id':        poi.get('id', ''),
        'base_name': poi.get('name', ''),
        'lng':       loc[0] if len(loc) > 0 else '',
        'lat':       loc[1] if len(loc) > 1 else '',
        'type':      poi.get('type', ''),
        'address':   poi.get('address', ''),
        'tel':       poi.get('tel', ''),
        'biz_area':  poi.get('business_area', ''),
    }


def _poi_matches_keyword(poi: dict, keyword: str) -> bool:
    """名称/地址/类型是否与非遗关键词相关（避免 OR 出无关文化馆）。"""
    kw = (keyword or '').strip()
    if not kw:
        return True
    blob = ''.join([
        str(poi.get('name') or ''),
        str(poi.get('address') or ''),
        str(poi.get('type') or ''),
    ])
    # 关键词过短时要求完整包含；常见项目名直接匹配
    if kw in blob:
        return True
    # 「皮影戏」等：允许「皮影」子串命中「皮影艺术博物馆」
    if len(kw) >= 2 and kw[:-1] in blob:
        return True
    return False


# 默认「研学/非遗」场景下的噪声词（意图门控：用户明确搜餐饮时不启用）
# 参考：高德/美团「先意图、再过滤」；Google Places type filter 也随 query 开关
_POI_NOISE_TOKENS = (
    '麻糍', '小吃', '餐饮', '火锅', '卤水', '烧烤', '肠粉', '鹅肉', '饭店', '餐厅',
    '奶茶', '咖啡', '超市', '酒店', '宾馆', '客栈', '民宿',
    '虫鸣', '昆虫', '活体', '动物园', '水族', '海洋馆', '自然博物馆',
    '玩具', '魔法厨房', '剧本杀', '密室', 'KTV', '网吧', '美容', '美发',
    '停车', '停车场', '地铁站', '公交站',
)

# 生活服务意图词：用户 query 命中则走开放检索，不做非遗噪声过滤
_POI_OPEN_INTENT_TOKENS = (
    '美食', '餐厅', '小吃', '火锅', '卤水', '烧烤', '肠粉', '鹅肉', '饭店',
    '奶茶', '咖啡', '酒店', '宾馆', '民宿', '客栈', '超市',
)

# 无主题词时的正向信号：更像非遗/研学场馆
_POI_HERITAGE_SIGNALS = (
    '非遗', '文化遗产', '传习', '传承', '民俗', '民艺', '手作', '手工', '工坊',
    '剪纸', '皮影', '刺绣', '陶瓷', '嵌瓷', '金包银', '英歌', '潮剧', '粤剧',
    '昆曲', '古琴', '太极', '武术', '戏曲', '戏院', '剧院', '文化馆', '文化站',
    '文化广场', '博物馆', '美术馆', '纪念馆', '陈列馆', '展览馆', '艺术馆',
)

# 蹭主题的餐饮/娱乐词：仅在「研学主题意图」下，名称含主题仍可判定为噪声
_POI_THEME_HIJACK_TOKENS = (
    '火锅', '卤水', '小吃', '餐厅', '饭店', '肠粉', '鹅肉', '奶茶', '咖啡',
    '酒店', '宾馆', '玩具', '虫鸣', '活体', '魔法厨房',
)


def _poi_blob(poi: dict) -> str:
    return ''.join([
        str(poi.get('name') or ''),
        str(poi.get('type') or ''),
        str(poi.get('address') or ''),
    ])


def _query_search_intent(keyword: str) -> str:
    """
    查询意图（轻量版 query 分析）。
    - open: 用户明确要美食/住宿等生活服务 → 不过滤餐饮噪声
    - heritage: 有主题词且非 open → 按研学相关过滤蹭词
    - browse: 无关键词（地图默认周边）→ 偏非遗浏览过滤
    """
    kw = (keyword or '').strip()
    if not kw:
        return 'browse'
    if any(tok in kw for tok in _POI_OPEN_INTENT_TOKENS):
        return 'open'
    return 'heritage'


def _active_noise_tokens(keyword: str) -> tuple:
    """
    噪声词随意图变化：用户 query 里已出现的词不再当噪声
    （搜「卤水火锅」时，「卤水」「火锅」不能用来杀结果）。
    """
    kw = (keyword or '').strip()
    if not kw:
        return _POI_NOISE_TOKENS
    return tuple(tok for tok in _POI_NOISE_TOKENS if tok not in kw)


def _poi_has_noise(poi: dict, keyword: str = '') -> bool:
    tokens = _active_noise_tokens(keyword)
    return any(tok in _poi_blob(poi) for tok in tokens)


def _poi_has_heritage_signal(poi: dict) -> bool:
    return any(tok in _poi_blob(poi) for tok in _POI_HERITAGE_SIGNALS)


def _poi_is_noise_for_theme(poi: dict, keyword: str) -> bool:
    """
    意图门控的噪声判定（不是永久黑名单）。
    - open 意图：不过滤
    - browse：命中噪声即丢
    - heritage：主题命中但名称明显是餐饮蹭词仍丢；否则按噪声词丢
    """
    intent = _query_search_intent(keyword)
    if intent == 'open':
        return False

    kw = (keyword or '').strip()
    name = str(poi.get('name') or '')
    noisy = _poi_has_noise(poi, keyword)

    if intent == 'browse':
        return noisy

    # heritage
    if kw in name or (len(kw) >= 2 and kw[:-1] in name):
        if noisy and any(tok in name for tok in _POI_THEME_HIJACK_TOKENS if tok not in kw):
            return True
        return False
    return noisy


def _filter_pois_for_theme(pois: list, keyword: str) -> tuple[list, str]:
    """
    按查询意图过滤。返回 (pois, match_mode)。
    - around_open: 生活服务意图，保留文本匹配结果
    - around_precise / around_generic: 研学相关
    """
    kw = (keyword or '').strip()
    intent = _query_search_intent(kw)

    if intent == 'open':
        matched = [p for p in pois if _poi_matches_keyword(p, kw)] if kw else list(pois)
        if not matched and kw:
            matched = list(pois)  # 开放意图下放宽：关键词已用于召回
        return (matched[:], 'around_open') if matched else ([], 'none')

    if intent == 'browse':
        cleaned = [p for p in pois if not _poi_is_noise_for_theme(p, '')]
        preferred = [p for p in cleaned if _poi_has_heritage_signal(p)]
        if preferred:
            return preferred, 'around_generic'
        soft = [
            p for p in cleaned
            if any(t in str(p.get('name') or '') for t in ('馆', '院', '广场', '传习所', '工坊'))
        ]
        return soft, 'around_generic' if soft else 'none'

    matched = [
        p for p in pois
        if _poi_matches_keyword(p, kw) and not _poi_is_noise_for_theme(p, kw)
    ]
    if matched:
        return matched, 'around_precise'
    return [], 'none'


def _amap_text_search(city: str, keywords: str, offset: int = 10) -> tuple[list, str]:
    """
    高德关键字检索。返回 (pois, error_msg)。
    error_msg 为空表示请求成功（pois 可为 []）。
    """
    url = 'https://restapi.amap.com/v3/place/text'
    params = {
        'key': Config.AMAP_API_KEY,
        'keywords': keywords,
        'city': city,
        'citylimit': 'true',
        'offset': offset,
        'page': 1,
    }
    try:
        res = requests.get(url, params=params, timeout=5).json()
        status = str(res.get('status', ''))
        if status == '1':
            return list(res.get('pois') or []), ''
        info = res.get('info') or res.get('infocode') or 'unknown'
        return [], f'高德 POI 失败 status={status} info={info} keywords={keywords!r} city={city!r}'
    except Exception as e:
        return [], f'高德 POI 请求异常: {e}'


def _amap_around_search(lng, lat, keywords: str, radius: int = 5000, offset: int = 12) -> tuple[list, str]:
    """高德周边检索（按距离排序）。返回 (pois, error_msg)。"""
    url = 'https://restapi.amap.com/v3/place/around'
    params = {
        'key': Config.AMAP_API_KEY,
        'location': f'{float(lng):.6f},{float(lat):.6f}',
        'keywords': keywords or '非遗|博物馆|文化馆',
        'radius': max(500, min(int(radius or 5000), 50000)),
        'offset': offset,
        'page': 1,
        'sortrule': 'distance',
    }
    try:
        res = requests.get(url, params=params, timeout=6).json()
        status = str(res.get('status', ''))
        if status == '1':
            return list(res.get('pois') or []), ''
        info = res.get('info') or res.get('infocode') or 'unknown'
        return [], f'高德周边检索失败 status={status} info={info}'
    except Exception as e:
        return [], f'高德周边检索异常: {e}'


def _haversine_m(lng1, lat1, lng2, lat2) -> float:
    """两点球面距离（米）。"""
    from math import asin, cos, radians, sin, sqrt
    try:
        lon1, la1, lon2, la2 = map(float, (lng1, lat1, lng2, lat2))
    except (TypeError, ValueError):
        return 1e12
    r = 6371000.0
    dlon, dlat = radians(lon2 - lon1), radians(la2 - la1)
    a = sin(dlat / 2) ** 2 + cos(radians(la1)) * cos(radians(la2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(min(1.0, sqrt(a)))


def get_markers_near_lnglat(lng, lat, heritage_keyword=None, radius=5000):
    """
    以浏览器 GPS 为圆心做周边非遗/文化 POI 检索，按距离排序。
    无结果时返回 []（由调用方决定是否回退同城文本检索）。
    """
    try:
        lng_f, lat_f = float(lng), float(lat)
    except (TypeError, ValueError):
        return []

    kw = (heritage_keyword or '').strip()[:16] or None
    radius = max(500, min(int(radius or 5000), 50000))
    errors = []

    def _to_markers(pois, match_mode: str):
        out = []
        for poi in pois:
            m = _amap_poi_to_marker(poi)
            m['match_mode'] = match_mode
            try:
                dist = poi.get('distance')
                if dist is not None and str(dist).strip() != '':
                    m['distance_m'] = int(float(dist))
                else:
                    m['distance_m'] = int(_haversine_m(
                        lng_f, lat_f, m.get('lng') or m.get('longitude'), m.get('lat') or m.get('latitude'),
                    ))
            except (TypeError, ValueError):
                m['distance_m'] = None
            out.append(m)
        out.sort(key=lambda x: x.get('distance_m') if x.get('distance_m') is not None else 1e12)
        return out

    intent = _query_search_intent(kw or '')

    # 生活服务意图：直搜用户词，跳过研学噪声过滤（用户要卤水火锅就给火锅）
    if intent == 'open' and kw:
        pois, err = _amap_around_search(lng_f, lat_f, kw, radius=radius, offset=15)
        if err:
            errors.append(err)
        elif pois:
            filtered, mode = _filter_pois_for_theme(pois, kw)
            return _to_markers((filtered or pois)[:10], mode or 'around_open')

    # heritage：主题变体；browse：拆开文化向检索词
    if intent == 'heritage' and kw:
        attempts = [kw, f'{kw}体验', f'{kw}博物馆', f'{kw}非遗']
    else:
        attempts = [
            '非遗',
            '文化馆|传习所|民俗',
            '纪念馆|美术馆|陈列馆',
            '剧院|戏院|手工作坊',
        ]

    merged = []
    seen_ids = set()
    last_mode = 'around_generic'

    for attempt_kw in attempts:
        if not attempt_kw:
            continue
        pois, err = _amap_around_search(lng_f, lat_f, attempt_kw, radius=radius, offset=15)
        if err:
            errors.append(err)
            continue
        if not pois:
            continue
        filtered, mode = _filter_pois_for_theme(pois, kw or '')
        if not filtered:
            continue
        last_mode = mode
        if kw:
            # 主题词：命中即返回（由近到远）
            return _to_markers(filtered[:10], mode)
        for p in filtered:
            pid = p.get('id') or f"{p.get('name')}|{p.get('location')}"
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            merged.append(p)
        if len(merged) >= 10:
            break

    if not kw and merged:
        return _to_markers(merged[:10], last_mode)

    # 放大半径再试主题词（仍不做泛非遗凑数）
    if kw and radius < 20000:
        wide = min(25000, max(radius * 3, 15000))
        pois, err = _amap_around_search(lng_f, lat_f, kw, radius=wide, offset=20)
        if not err and pois:
            filtered, mode = _filter_pois_for_theme(pois, kw)
            if filtered:
                markers = _to_markers(filtered[:10], mode)
                for m in markers:
                    m['search_note'] = f'已扩大至约 {wide}m 检索与「{kw}」相关地点'
                return markers

    if errors:
        logger.warning('AMap 周边检索失败 lng=%s lat=%s kw=%s errs=%s', lng_f, lat_f, kw, errors)
    return []


def get_markers_from_amap(city, heritage_keyword=None):
    """
    根据城市和可选的非遗关键词从高德搜索 POI 打点。

    :param city: 城市名，如 "北京市"
    :param heritage_keyword: 具体非遗项目名（如「皮影戏」）。优先精确搜，
                             再按名称过滤；无相关结果时才弱兜底通用文化类 POI。
    """
    if not city or city == '全国':
        return []

    search_city = _city_for_amap_search(city)
    kw = (heritage_keyword or '').strip()[:16] or None
    errors = []

    def _to_markers(pois, match_mode: str):
        out = []
        for poi in pois:
            m = _amap_poi_to_marker(poi)
            m['match_mode'] = match_mode
            out.append(m)
        return out

    intent = _query_search_intent(kw or '')

    # 生活服务意图：城市直搜用户词，不做研学噪声过滤
    if intent == 'open' and kw:
        pois, err = _amap_text_search(search_city, kw, offset=12)
        if err:
            logger.error(err)
            return []
        filtered, mode = _filter_pois_for_theme(pois, kw)
        if not filtered:
            return []
        return _to_markers(filtered[:8], mode if mode != 'none' else 'keyword')

    # 1) 精确：只用项目名（不要 OR 文化馆，否则高德会刷无关场馆）
    if intent == 'heritage' and kw:
        for attempt_kw in (kw, f'{kw}博物馆', f'{kw}非遗', f'{kw}|{kw}剧场|{kw}展馆'):
            pois, err = _amap_text_search(search_city, attempt_kw, offset=12)
            if err:
                errors.append(err)
                continue
            filtered, mode = _filter_pois_for_theme(pois, kw)
            if filtered:
                return _to_markers(filtered[:8], 'precise' if mode == 'around_precise' else mode)
            if pois and attempt_kw == kw:
                # 名称不完全含关键词，但仍是该词检索结果；仍过意图噪声门
                soft = [p for p in pois if not _poi_is_noise_for_theme(p, kw)]
                if soft:
                    return _to_markers(soft[:5], 'keyword')

        # 2) 弱兜底：通用词，但尽量留下与关键词沾边的；否则带提示字段
        pois, err = _amap_text_search(search_city, '非遗|博物馆|民俗|戏曲|剧院', offset=10)
        if err:
            errors.append(err)
        else:
            related, _ = _filter_pois_for_theme(pois, kw)
            cleaned_browse, _ = _filter_pois_for_theme(pois, '')
            picked = related[:5] if related else cleaned_browse[:3]
            markers = _to_markers(picked, 'fallback_generic' if not related else 'fallback_related')
            if markers and not related:
                for m in markers:
                    m['search_note'] = (
                        f'未找到与「{kw}」名称直接相关的场馆，已列出【{city}】内通用文化类地点供参考'
                    )
            if markers:
                return markers
        if errors:
            logger.warning('AMap 精确检索无结果且兜底失败 city=%s kw=%s errs=%s', city, kw, errors)
        return []

    # browse：同城文化地标（过滤餐饮/娱乐噪声）
    pois, err = _amap_text_search(search_city, '非遗|文化馆|传习|纪念馆|手工作坊', offset=12)
    if err:
        logger.error(err)
        return []
    filtered, mode = _filter_pois_for_theme(pois, '')
    if not filtered:
        return []
    return _to_markers(filtered[:8], mode if mode != 'none' else 'generic')


# ================================================================
# 7. IP 定位（按访问者公网 IP，非服务器出口 IP）
# ================================================================

def _is_public_ip(ip_str):
    if not ip_str:
        return False
    try:
        ip = ipaddress.ip_address(ip_str.strip())
        return not (ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local)
    except ValueError:
        return False


def get_client_ip_from_request(req):
    """
    解析用户公网 IP：优先反向代理头；本地开发时可用前端 X-Client-Public-IP。
    生产环境需在 Nginx 配置 X-Real-IP / X-Forwarded-For。
    """
    if not req:
        return None

    if os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes'):
        debug_ip = (req.args.get('client_ip') or '').strip()
        if debug_ip and _is_public_ip(debug_ip):
            return debug_ip

    xff = req.headers.get('X-Forwarded-For')
    if xff:
        for part in reversed([p.strip() for p in xff.split(',') if p.strip()]):
            if _is_public_ip(part):
                return part

    xri = (req.headers.get('X-Real-IP') or '').strip()
    if _is_public_ip(xri):
        return xri

    rip = (req.remote_addr or '').strip()
    reported = (req.headers.get('X-Client-Public-IP') or '').strip()

    # 本地 Vite：优先浏览器上报 IP（开 VPN 后才是香港/海外公网 IP）
    if reported and _is_public_ip(reported):
        if not _is_public_ip(rip) or rip in ('127.0.0.1', '::1'):
            return reported

    if _is_public_ip(rip):
        return rip

    if reported and _is_public_ip(reported):
        return reported

    if xff:
        first = xff.split(',')[0].strip()
        if first:
            return first
    return rip or None


def _amap_str_field(val):
    if isinstance(val, list):
        val = val[0] if val else ''
    if not isinstance(val, str):
        return ''
    val = val.strip()
    return val if val and val != '[]' else ''


def _rect_is_empty(rect):
    if not rect:
        return True
    if isinstance(rect, list):
        return len(rect) == 0
    if isinstance(rect, str):
        return not rect.strip() or rect.strip() == '[]'
    return True


def _parse_amap_rectangle(rect):
    if _rect_is_empty(rect):
        return None, None
    if isinstance(rect, list):
        rect = rect[0] if rect else ''
    if not isinstance(rect, str) or ';' not in rect:
        return None, None
    try:
        p1, p2 = rect.split(';', 1)
        x1, y1 = map(float, p1.split(','))
        x2, y2 = map(float, p2.split(','))
        return round((x1 + x2) / 2, 6), round((y1 + y2) / 2, 6)
    except (ValueError, TypeError):
        return None, None


# ipinfo 国家码 → 展示/检索用城市名（高德 v3/ip 对港澳台常返回空列表）
_IPINFO_REGION_MAP = {
    'HK': '香港',
    'MO': '澳门',
    'TW': '台湾',
}

# ipinfo 英文城市 → 高德可用中文市级名（否则会把 Guangzhou 当城市去搜 POI，结果错乱）
_IPINFO_CITY_CN = {
    'beijing': '北京市', 'shanghai': '上海市', 'tianjin': '天津市', 'chongqing': '重庆市',
    'guangzhou': '广州市', 'shenzhen': '深圳市', 'dongguan': '东莞市', 'foshan': '佛山市',
    'zhuhai': '珠海市', 'zhongshan': '中山市', 'huizhou': '惠州市', 'shantou': '汕头市',
    'hangzhou': '杭州市', 'ningbo': '宁波市', 'wenzhou': '温州市', 'nanjing': '南京市',
    'suzhou': '苏州市', 'wuxi': '无锡市', 'hefei': '合肥市', 'fuzhou': '福州市',
    'xiamen': '厦门市', 'nanchang': '南昌市', 'jinan': '济南市', 'qingdao': '青岛市',
    'zhengzhou': '郑州市', 'wuhan': '武汉市', 'changsha': '长沙市', 'chengdu': '成都市',
    'kunming': '昆明市', 'guiyang': '贵阳市', 'xi\'an': '西安市', 'xian': '西安市',
    'lanzhou': '兰州市', 'xining': '西宁市', 'yinchuan': '银川市', 'urumqi': '乌鲁木齐市',
    'harbin': '哈尔滨市', 'changchun': '长春市', 'shenyang': '沈阳市', 'dalian': '大连市',
    'taiyuan': '太原市', 'shijiazhuang': '石家庄市', 'nanning': '南宁市', 'haikou': '海口市',
    'sanya': '三亚市', 'lhasa': '拉萨市', 'hohhot': '呼和浩特市',
}


def _ensure_cn_city_name(name: str) -> str:
    """尽量补成「XX市」，便于高德 city 检索。"""
    name = (name or '').strip()
    if not name:
        return ''
    if name in ('香港', '澳门', '台湾'):
        return name
    if name.endswith(('市', '省', '地区', '盟', '州', '县', '区')):
        return name
    if name in ('北京', '上海', '天津', '重庆'):
        return name + '市'
    # 已是中文短名
    if re.search(r'[\u4e00-\u9fa5]', name) and len(name) <= 6:
        return name + '市'
    return name


def _amap_regeo_city(lng, lat) -> dict | None:
    """用高德逆地理把经纬度转成中文城市（校正 ipinfo 英文名）。"""
    if lng is None or lat is None:
        return None
    try:
        res = requests.get(
            'https://restapi.amap.com/v3/geocode/regeo',
            params={
                'key': Config.AMAP_API_KEY,
                'location': f'{lng},{lat}',
                'extensions': 'base',
            },
            timeout=5,
        ).json()
        if str(res.get('status')) != '1':
            info = res.get('info') or res.get('infocode') or ''
            logger.warning('高德逆地理失败 status=%s info=%s', res.get('status'), info)
            return None
        addr = (res.get('regeocode') or {}).get('addressComponent') or {}
        city = _amap_str_field(addr.get('city'))
        province = _amap_str_field(addr.get('province'))
        # 直辖市 city 常为空，用 province
        display = city or province
        display = _CITY_DISPLAY_ALIAS.get(display, display)
        display = _ensure_cn_city_name(display)
        if not display:
            return None
        return {
            'city': display,
            'citycode': _amap_str_field(addr.get('citycode')),
            'adcode': _amap_str_field(addr.get('adcode')),
            'formatted': _amap_str_field((res.get('regeocode') or {}).get('formatted_address')),
        }
    except Exception as e:
        logger.warning('高德逆地理异常: %s', e)
        return None


def _geo_from_ipinfo(client_ip):
    """
    高德 IP 接口对部分出口 IP 常返回 province/city/rectangle 均为 []。
    使用 ipinfo 补经纬度，再尽量转成中文城市名。
    """
    if not client_ip or not _is_public_ip(client_ip):
        return None
    try:
        r = requests.get(f'https://ipinfo.io/{client_ip}/json', timeout=5).json()
        country = (r.get('country') or '').upper()
        city_en = (r.get('city') or '').strip()
        region  = (r.get('region') or '').strip()
        lng, lat = None, None
        loc = (r.get('loc') or '').strip()
        if loc and ',' in loc:
            lat_s, lng_s = loc.split(',', 1)
            lat = round(float(lat_s.strip()), 6)
            lng = round(float(lng_s.strip()), 6)

        display = _IPINFO_REGION_MAP.get(country)
        if not display:
            blob = f'{city_en} {region}'.lower()
            if 'hong kong' in blob or country == 'HK':
                display = '香港'
            elif 'macau' in blob or 'macao' in blob or country == 'MO':
                display = '澳门'
            elif country == 'TW' or 'taiwan' in blob:
                display = '台湾'
            elif country == 'CN':
                key = city_en.lower().replace(' ', '')
                display = _IPINFO_CITY_CN.get(key) or _IPINFO_CITY_CN.get(city_en.lower())
                if not display and re.search(r'[\u4e00-\u9fa5]', city_en):
                    display = _ensure_cn_city_name(city_en)
            else:
                display = city_en or region

        citycode, adcode = '', ''
        # 有坐标时用高德逆地理拿标准中文市名（最准）
        if lng is not None and lat is not None:
            regeo = _amap_regeo_city(lng, lat)
            if regeo and regeo.get('city'):
                display = regeo['city']
                citycode = regeo.get('citycode') or ''
                adcode = regeo.get('adcode') or ''

        if not display:
            return None

        display = _ensure_cn_city_name(display)
        return {
            'status':     'success',
            'city':       display,
            'lng':        lng,
            'lat':        lat,
            'citycode':   citycode,
            'adcode':     adcode,
            'ip_used':    client_ip,
            'loc_source': 'ipinfo+regeo' if citycode or adcode else 'ipinfo',
            'amap_raw':   {'ipinfo_country': country, 'ipinfo_city': city_en},
        }
    except Exception as e:
        logger.warning('ipinfo 定位失败 ip=%s: %s', client_ip, e)
        return None


# 高德对港澳台 IP 常返回 city=[]，需用 province 或别名
_CITY_DISPLAY_ALIAS = {
    '香港特别行政区': '香港',
    '澳门特别行政区': '澳门',
    '台湾省':         '台湾',
}
_CITY_SEARCH_ALIAS = {
    '香港':           '香港特别行政区',
    '香港特别行政区': '香港特别行政区',
    '澳门':           '澳门特别行政区',
    '澳门特别行政区': '澳门特别行政区',
    '台湾':           '台湾省',
    '台湾省':         '台湾省',
}


def _amap_display_city(res):
    city = _amap_str_field(res.get('city'))
    province = _amap_str_field(res.get('province'))
    if city in _CITY_DISPLAY_ALIAS:
        return _CITY_DISPLAY_ALIAS[city]
    if city:
        return city
    if province in _CITY_DISPLAY_ALIAS:
        return _CITY_DISPLAY_ALIAS[province]
    if province:
        return province
    return ''


def _city_for_amap_search(display_city):
    return _CITY_SEARCH_ALIAS.get(display_city, display_city)


def _fixed_city_location(city: str, status: str = 'fixed'):
    """固定城市坐标（仅 IP 定位全部失败时的兜底）。"""
    from core.config import Config

    city = (city or Config.DEFAULT_MAP_CITY).strip() or Config.DEFAULT_MAP_CITY
    preset = _CITY_GEO_PRESETS.get(city) or _CITY_GEO_PRESETS.get(Config.DEFAULT_MAP_CITY)
    if not preset:
        preset = _CITY_GEO_PRESETS['广州市']
    return {
        'status':     status,
        'city':       city,
        'lng':        preset['lng'],
        'lat':        preset['lat'],
        'citycode':   preset['citycode'],
        'adcode':     preset['adcode'],
        'ip_used':    None,
        'loc_source': 'fixed',
    }


_CITY_GEO_PRESETS = {
    '广州市': {'lng': 113.264385, 'lat': 23.129112, 'citycode': '020', 'adcode': '440100'},
    '深圳市': {'lng': 114.057868, 'lat': 22.543099, 'citycode': '0755', 'adcode': '440300'},
    '北京市': {'lng': 116.407394, 'lat': 39.904211, 'citycode': '010', 'adcode': '110000'},
}


def _fallback_ip_location():
    from core.config import Config
    return _fixed_city_location(Config.DEFAULT_MAP_CITY, status='fallback')


def resolve_geo_from_lnglat(lng, lat):
    """浏览器 GPS 精炼：逆地理得到当前城市。"""
    try:
        lng_f, lat_f = float(lng), float(lat)
    except (TypeError, ValueError):
        return {
            'status': 'error',
            'city': '',
            'loc_source': 'gps',
            'loc_error': f'无效坐标 lng={lng!r} lat={lat!r}',
        }
    regeo = _amap_regeo_city(lng_f, lat_f)
    if not regeo:
        return {
            'status': 'error',
            'city': '',
            'lng': lng_f,
            'lat': lat_f,
            'loc_source': 'gps',
            'loc_error': '高德逆地理未返回城市，请检查 AMAP_API_KEY 或坐标是否在境内',
        }
    return {
        'status': 'success',
        'city': regeo['city'],
        'lng': lng_f,
        'lat': lat_f,
        'citycode': regeo.get('citycode', ''),
        'adcode': regeo.get('adcode', ''),
        'ip_used': None,
        'loc_source': 'gps+regeo',
        'formatted_address': regeo.get('formatted') or '',
    }


def resolve_amap_ip_location(client_ip=None):
    """
    调用高德 IP 定位。client_ip 为公网 IP 时传入 ip 参数，否则由高德解析调用方出口 IP。
    策略：高德 IP →（空/失败）ipinfo+逆地理 → 兜底城市，并写入 loc_error 便于前端展示。
    """
    from core.config import Config

    params = {'key': Config.AMAP_API_KEY}
    ip_used = None
    errors = []
    if client_ip and _is_public_ip(client_ip):
        params['ip'] = client_ip
        ip_used = client_ip
    elif client_ip:
        logger.info('客户端 IP 非公网(%s)，高德将使用服务器出口 IP 解析', client_ip)
        errors.append(f'客户端 IP 非公网({client_ip})，将用服务器出口 IP')

    amap_city = ''
    try:
        res = requests.get('https://restapi.amap.com/v3/ip', params=params, timeout=4).json()
        display_city = _ensure_cn_city_name(_amap_display_city(res))
        if res.get('status') == '1' and display_city:
            # 仅省级（如「广东省」）精度不够，继续用 ipinfo 细化到市
            if display_city.endswith('省') and client_ip and _is_public_ip(client_ip):
                errors.append(f'高德仅返回省级「{display_city}」，尝试 ipinfo 细化到市')
                amap_city = display_city
            else:
                lng, lat = _parse_amap_rectangle(res.get('rectangle'))
                return {
                    'status':     'success',
                    'city':       display_city,
                    'lng':        lng,
                    'lat':        lat,
                    'citycode':   _amap_str_field(res.get('citycode')),
                    'adcode':     _amap_str_field(res.get('adcode')),
                    'ip_used':    ip_used,
                    'loc_source': 'amap',
                    'amap_raw': {
                        'city': res.get('city'),
                        'province': res.get('province'),
                    },
                }
        else:
            info = res.get('info') or res.get('infocode') or ''
            errors.append(
                f'高德 IP 无有效城市 status={res.get("status")} info={info} '
                f'raw_city={res.get("city")!r} province={res.get("province")!r}'
            )
            logger.warning('高德 IP 定位无有效城市 client_ip=%s resp=%s', client_ip, res)
    except Exception as e:
        errors.append(f'高德 IP 请求异常: {e}')
        logger.error('高德 IP 定位失败 client_ip=%s: %s', client_ip, e)

    if client_ip and _is_public_ip(client_ip):
        alt = _geo_from_ipinfo(client_ip)
        if alt:
            if amap_city and alt.get('city') and alt['city'].endswith('市'):
                alt['loc_detail'] = f'高德省级「{amap_city}」已用 ipinfo/逆地理细化为「{alt["city"]}」'
            if errors:
                alt['loc_warnings'] = errors
            logger.info(
                'IP 定位采用 %s ip=%s -> %s',
                alt.get('loc_source'), client_ip, alt.get('city'),
            )
            return alt
        errors.append('ipinfo 未能解析该公网 IP 的城市')

    fb = _fallback_ip_location()
    fb['loc_error'] = '；'.join(errors) if errors else 'IP 定位失败，已使用兜底城市'
    fb['loc_warnings'] = errors
    fb['ip_used'] = ip_used
    return fb


def get_amap_location(client_ip=None):
    """兼容旧接口：仅返回 IP 定位得到的城市名。"""
    return resolve_amap_ip_location(client_ip)['city']


# ================================================================
# 8. 语音合成（TTS，流式）
# ================================================================

def get_tts_audio(text):
    """调用讯飞 TTS 合成语音，返回音频字节数据。"""
    print(f'[TTS] 开始合成，文本长度={len(text)}，前50字: {text[:50]}', flush=True)
    q = queue.Queue()
    done = [False]

    def on_message(ws, message):
        try:
            msg = json.loads(message)
            code = msg.get('code', -1)
            print(f'[TTS] 收到消息 code={code} sid={msg.get("sid","")}', flush=True)
            if code != 0:
                print(f'[TTS] 错误: {code} {msg.get("message","")}', flush=True)
                q.put(None)
                ws.close()
                return
            audio_data = msg.get('data', {}).get('audio', '')
            status = msg.get('data', {}).get('status', -1)
            if audio_data:
                chunk = base64.b64decode(audio_data)
                print(f'[TTS] 音频块 {len(chunk)} bytes, status={status}', flush=True)
                q.put(chunk)
            if status == 2:
                print('[TTS] 合成完成', flush=True)
                done[0] = True
                q.put(None)
                ws.close()
        except Exception as e:
            print(f'[TTS] on_message 异常: {e}', flush=True)
            q.put(None)
            ws.close()

    def on_error(ws, error):
        print(f'[TTS] WebSocket 错误: {error}', flush=True)
        q.put(None)

    def on_close(ws, code, msg):
        print(f'[TTS] WebSocket 关闭 code={code}', flush=True)
        if not done[0]:
            q.put(None)

    def on_open(ws):
        print('[TTS] WebSocket 已连接，发送请求', flush=True)
        data = {
            'common':   {'app_id': Config.SPARK_APPID},
            # 官方 demo: aue=raw, auf=audio/L16;rate=16000, vcn=x4_yezi, tte=utf8
            'business': {'aue': 'raw', 'auf': 'audio/L16;rate=16000',
                         'vcn': 'x4_yezi', 'tte': 'utf8',
                         'speed': 50, 'volume': 50, 'pitch': 50},
            'data':     {'status': 2, 'text': base64.b64encode(text.encode('utf-8')).decode('utf-8')}
        }
        ws.send(json.dumps(data))

    # 官方 demo 签名时 host 固定为 ws-api.xfyun.cn，不是 tts-api.xfyun.cn
    # 参见：tts_ws_python3_demo.py create_url() 方法
    TTS_WS_URL  = 'wss://tts-api.xfyun.cn/v2/tts'
    SIGN_HOST   = 'ws-api.xfyun.cn'
    SIGN_PATH   = '/v2/tts'
    date        = format_date_time(mktime(datetime.now().timetuple()))
    sig_origin  = f'host: {SIGN_HOST}\ndate: {date}\nGET {SIGN_PATH} HTTP/1.1'
    sig_sha     = hmac.new(Config.SPARK_API_SECRET.encode('utf-8'),
                           sig_origin.encode('utf-8'), digestmod=hashlib.sha256).digest()
    sig_b64     = base64.b64encode(sig_sha).decode('utf-8')
    auth_origin = (f'api_key="{Config.SPARK_API_KEY}", algorithm="hmac-sha256", '
                   f'headers="host date request-line", signature="{sig_b64}"')
    authorization = base64.b64encode(auth_origin.encode('utf-8')).decode('utf-8')
    params  = {'authorization': authorization, 'date': date, 'host': SIGN_HOST}
    ws_url  = TTS_WS_URL + '?' + urlencode(params)
    print(f'[TTS] 连接URL前80字: {ws_url[:80]}', flush=True)
    ws = websocket.WebSocketApp(ws_url, on_message=on_message, on_error=on_error,
                                on_close=on_close, on_open=on_open)
    thread.start_new_thread(ws.run_forever, (), {'sslopt': {'cert_reqs': ssl.CERT_NONE}})

    while True:
        try:
            chunk = q.get(timeout=30)  # 30秒超时防止永久阻塞
        except queue.Empty:
            print('[TTS] 等待超时', flush=True)
            break
        if chunk is None:
            break
        yield chunk
    print('[TTS] generator 结束', flush=True)


# ================================================================
# 9. 非遗焕新（AI 文生图 / 图生图）
# ================================================================

# ── 智谱 AI：图生文（GLM-4V）+ 文生图（CogView-4）双模型串联 ──
ZHIPU_CHAT_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
ZHIPU_GEN_URL  = "https://open.bigmodel.cn/api/paas/v4/images/generations"


def _zhipu_describe_image(b64_img):
    """
    GLM-4V 图像理解：分析参考图中的非遗文化元素、视觉特征与构图。
    返回一段可用于文生图的详细描述文本。
    """
    api_key = Config.ZHIPU_API_KEY
    if not api_key:
        logger.warning("智谱 API Key 未配置，跳过参考图分析")
        return ""

    # 确保去除 data URL 前缀，仅保留纯 base64
    raw_b64 = b64_img.split(",")[1] if "," in b64_img else b64_img

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    body = {
        "model": Config.ZHIPU_VISION_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": (
                    "请以精炼的中文描述这张非遗文化图片，重点关注："
                    "1) 核心文化元素（图案、纹样、器物、人物造型等）；"
                    "2) 色彩体系（主色调、配色风格）；"
                    "3) 构图特征（对称、留白、层次等）；"
                    "4) 材质与质感。"
                    "控制在200字以内，用于后续AI文生图的参考描述。"
                )},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{raw_b64}"}}
            ]
        }],
        "temperature": 0.3,
        "max_tokens": 2048
    }

    try:
        resp = requests.post(ZHIPU_CHAT_URL, json=body, headers=headers, timeout=30)
        resp_json = resp.json()
        if resp.status_code != 200:
            err_msg = resp_json.get("error", {}).get("message", str(resp_json))
            logger.error("GLM-4V 图像分析失败: %s", err_msg)
            return ""
        content = resp_json.get("choices", [{}])[0].get("message", {}).get("content", "")
        content = strip_thinking_text(content)
        logger.info("视觉模型参考图分析完成，长度 %d", len(content))
        return content
    except Exception as e:
        logger.warning("GLM-4V 图像分析异常: %s", e)
        return ""


def normalize_art_result_url(img_data: str) -> str:
    """智谱外链转 data URL，避免过期与整页跳转。"""
    raw = str(img_data or '').strip()
    if not raw:
        return ''
    if raw.startswith('data:image'):
        return raw
    if raw.startswith(('http://', 'https://')):
        try:
            resp = requests.get(raw, timeout=60)
            resp.raise_for_status()
            content_type = (resp.headers.get('Content-Type') or 'image/jpeg').split(';')[0]
            if not content_type.startswith('image/'):
                content_type = 'image/jpeg'
            encoded = base64.b64encode(resp.content).decode('utf-8')
            logger.info('焕新图外链已转存，大小 %d bytes', len(resp.content))
            return f'data:{content_type};base64,{encoded}'
        except Exception as exc:
            logger.warning('焕新图外链转存失败，仍返回原 URL: %s', exc)
            return raw
    return f'data:image/jpeg;base64,{raw}'


# 焕新生图结果缓存（prompt + 图 hash → data URL），演示加速
_art_cache: dict = {}
_ART_CACHE_MAX = 64

_DEMO_ART_DATA_URL = (
    'data:image/svg+xml;base64,'
    'PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI1MTIiIGhlaWdodD0iNTEyIj48cmVjdCBmaWxsPSIjMWExZjI3IiB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PXNhbnMtc2VyaWYgZm9udC1zaXplPSIyMCIgZmlsbD0iIzNkOWU4YyIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPuaXoOazleiDveWKoOi9ve+8gOivt+axgjwvdGV4dD48L3N2Zz4='
)


def _art_cache_key(prompt: str, b64_img=None) -> str:
    img_part = ''
    if b64_img:
        raw = b64_img.split(',', 1)[1] if ',' in b64_img else b64_img
        img_part = hashlib.md5(raw[:4096].encode('utf-8', errors='ignore')).hexdigest()[:16]
    return hashlib.md5(f'{prompt}|{img_part}'.encode()).hexdigest()


def iter_zhipu_art_generation(prompt, b64_img=None):
    """
    智谱双模型串联生图（生成器）：yield progress 事件，最后 yield result 事件。
    progress: {"type": "progress", "stage": str, "text": str, "detail": optional}
    result:   {"type": "result", "success": bool, "data": url|None, "msg": str, "analysis": str}
    """
    if Config.DEMO_MODE:
        from features.demo.service import get_demo_art, iter_art_simulate_progress

        demo_img, demo_analysis = get_demo_art(prompt)
        for event in iter_art_simulate_progress(b64_img):
            yield event
        yield {
            'type': 'result',
            'success': True,
            'data': demo_img or _DEMO_ART_DATA_URL,
            'msg': '',
            'analysis': demo_analysis or '剪纸纹样、朱砂红配色、对称构图',
        }
        return

    cache_key = _art_cache_key(prompt, b64_img)
    cached = _art_cache.get(cache_key)
    if cached:
        from features.demo.service import iter_art_simulate_progress

        for event in iter_art_simulate_progress(b64_img):
            yield event
        yield {'type': 'result', 'success': True, 'data': cached, 'msg': '', 'analysis': ''}
        return

    api_key = Config.ZHIPU_API_KEY
    if not api_key:
        yield {
            'type': 'result',
            'success': False,
            'data': None,
            'msg': '智谱 API Key 未配置，请在 .env 中设置 ZHIPU_API_KEY',
            'analysis': '',
        }
        return

    img_desc = ''
    combined_prompt = prompt

    if b64_img:
        yield {'type': 'progress', 'stage': 'glm_start', 'text': '视觉模型正在分析参考图中的非遗文化元素…'}
        logger.info('检测到参考图，调用视觉模型分析图像特征...')
        img_desc = _zhipu_describe_image(b64_img)
        if img_desc:
            excerpt = img_desc if len(img_desc) <= 100 else img_desc[:100] + '…'
            yield {
                'type': 'progress',
                'stage': 'glm_done',
                'text': f'识别到：{excerpt}',
                'detail': img_desc,
            }
            combined_prompt = (
                f'【参考图核心特征】{img_desc}\n'
                f'【创作要求】{prompt}\n'
                f'请基于参考图的非遗文化特征，按创作要求重新生成数字艺术品。'
                f'保留文化内核，融入现代视觉表达，画面精致，光影高级。'
            )
        else:
            yield {'type': 'progress', 'stage': 'glm_skip', 'text': '参考图分析未完成，将仅按文字创意生成'}
    else:
        yield {'type': 'progress', 'stage': 'text_only', 'text': '未提供参考图，图像模型将按文字创意直接生成'}

    yield {'type': 'progress', 'stage': 'cogview_start', 'text': '图像模型正在绘制焕新艺术品…'}

    model = Config.ZHIPU_IMAGE_MODEL
    quality = 'hd' if len(combined_prompt.strip()) > 60 else 'standard'
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    body = {
        'model': model,
        'prompt': combined_prompt,
        'size': '1024x1024',
        'quality': quality,
        'watermark_enabled': False,
    }

    try:
        resp = requests.post(ZHIPU_GEN_URL, json=body, headers=headers, timeout=120)
        resp_json = resp.json()
        if resp.status_code != 200:
            err_msg = resp_json.get('error', {}).get('message', resp_json.get('message', str(resp_json)))
            yield {'type': 'result', 'success': False, 'data': None, 'msg': f'智谱 API 错误: {err_msg}', 'analysis': img_desc}
            return
    except requests.exceptions.Timeout:
        yield {'type': 'result', 'success': False, 'data': None, 'msg': '智谱生图超时（120s），请重试或简化提示词', 'analysis': img_desc}
        return
    except Exception as e:
        yield {'type': 'result', 'success': False, 'data': None, 'msg': f'智谱生图请求异常: {e}', 'analysis': img_desc}
        return

    data_list = resp_json.get('data', [])
    if not data_list or not data_list[0].get('url'):
        content_filter = resp_json.get('content_filter', [])
        if content_filter:
            reason = content_filter[0] if isinstance(content_filter[0], str) else content_filter[0].get('role', '安全拦截')
            yield {'type': 'result', 'success': False, 'data': None, 'msg': f'图片被安全策略拦截（{reason}），请修改提示词', 'analysis': img_desc}
            return
        yield {'type': 'result', 'success': False, 'data': None, 'msg': '未返回图片数据，请重试', 'analysis': img_desc}
        return

    img_url = data_list[0]['url']
    final_url = normalize_art_result_url(img_url)
    if len(_art_cache) >= _ART_CACHE_MAX:
        _art_cache.pop(next(iter(_art_cache)))
    _art_cache[cache_key] = final_url

    yield {'type': 'progress', 'stage': 'done', 'text': '焕新作品生成完成'}
    yield {'type': 'result', 'success': True, 'data': final_url, 'msg': '', 'analysis': img_desc}


def execute_zhipu_art_generation(prompt, b64_img=None, on_progress=None):
    """
    智谱双模型串联生图（同步封装）。
    on_progress(stage, text, detail=None) 可选，用于 Agent / SSE 推送中间态。
    """
    result = None
    for event in iter_zhipu_art_generation(prompt, b64_img):
        if event['type'] == 'progress' and on_progress:
            on_progress(event.get('stage', ''), event.get('text', ''), event.get('detail'))
        elif event['type'] == 'result':
            result = event
    if not result:
        return {'success': False, 'data': None, 'msg': '生图流程异常结束'}
    return {
        'success': result['success'],
        'data': result.get('data'),
        'msg': result.get('msg', ''),
        'analysis': result.get('analysis', ''),
    }


# 10. 向量 RAG 检索
# ================================================================

def get_retrieved_context(query):
    """向量 RAG 检索：返回与 query 相关的非遗百科上下文文本。"""
    global _rag_instance
    try:
        if _rag_instance is None:
            # 延迟导入：避免 import utils 时拉起 torch/CUDA（WinError 1455）
            from langchain_chroma import Chroma
            from langchain_huggingface import HuggingFaceEmbeddings

            embeddings = HuggingFaceEmbeddings(model_name='shibing624/text2vec-base-chinese')
            _rag_instance = Chroma(
                persist_directory='./chroma_db',
                embedding_function=embeddings,
            )
        docs = _rag_instance.similarity_search(query, k=5)
        return '\n'.join([d.page_content for d in docs])
    except Exception as e:
        logger.error('RAG 检索失败: %s', e)
        return ''
