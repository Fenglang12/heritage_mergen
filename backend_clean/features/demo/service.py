"""演示模式预置数据、识图缓存、对话降级回复。"""

import hashlib
import json
import logging
import time
from pathlib import Path

from core.config import Config

logger = logging.getLogger(__name__)

_DATA = None
_source_cache: dict = {}
_SOURCE_CACHE_MAX = 32


def _load_data() -> dict:
    global _DATA
    if _DATA is None:
        path = Path(__file__).parent / 'data' / 'demo_data.json'
        with open(path, encoding='utf-8') as f:
            _DATA = json.load(f)
    return _DATA


def _image_hash(img_b64: str) -> str:
    raw = img_b64.split(',', 1)[1] if img_b64 and ',' in img_b64 else (img_b64 or '')
    return hashlib.md5(raw[:8192].encode('utf-8', errors='ignore')).hexdigest()


def simulate_delay_sec() -> float:
    return float(getattr(Config, 'DEMO_SIMULATE_DELAY_SEC', 0) or 0)


def apply_simulate_delay():
    """缓存命中等场景：按 DEMO_SIMULATE_DELAY_SEC 等待，与 DEMO_MODE 无关。"""
    sec = simulate_delay_sec()
    if sec > 0:
        time.sleep(sec)


def demo_simulate_working():
    """DEMO_MODE 下短暂等待，使前端加载态与真机体验一致（无额外用户可见文案）。"""
    if not Config.DEMO_MODE:
        return
    apply_simulate_delay()


def iter_art_simulate_progress(b64_img=None):
    """焕新演示/缓存命中：输出与真机一致的进度事件并分段等待。"""
    delay = simulate_delay_sec()
    if b64_img:
        yield {
            'type': 'progress',
            'stage': 'glm_start',
            'text': 'GLM-4V 正在分析参考图中的非遗文化元素…',
        }
    else:
        yield {
            'type': 'progress',
            'stage': 'text_only',
            'text': '未提供参考图，CogView-4 将按文字创意直接生成',
        }
    if delay > 0:
        time.sleep(delay * 0.45)
    if b64_img:
        yield {
            'type': 'progress',
            'stage': 'glm_done',
            'text': '已提取非遗纹样与色彩特征',
        }
    yield {'type': 'progress', 'stage': 'cogview_start', 'text': 'CogView-4 正在绘制焕新艺术品…'}
    if delay > 0:
        time.sleep(delay * 0.55)


def _normalize_demo_markers(markers: list) -> list:
    """与高德 POI 结构对齐，确保前端能显示 base_name。"""
    out = []
    for raw in markers or []:
        if not isinstance(raw, dict):
            continue
        m = dict(raw)
        if not (m.get('base_name') or '').strip():
            m['base_name'] = (m.get('name') or '文化地标').strip()
        out.append(m)
    return out


def get_demo_analyze_result(img_b64: str = None) -> tuple:
    """返回 (ai_text, markers, city)。"""
    presets = _load_data().get('analyze_presets') or []
    if not presets:
        return '识图分析完成。', [], '广州市'
    idx = int(_image_hash(img_b64 or 'default'), 16) % len(presets)
    p = presets[idx]
    return (
        p.get('ai_text', ''),
        _normalize_demo_markers(p.get('markers') or []),
        p.get('city', '广州市'),
    )


def get_demo_art(prompt: str) -> tuple:
    """按 prompt 关键词匹配预置焕新图，返回 (image_data, analysis)。"""
    presets = _load_data().get('art_presets') or []
    prompt = prompt or ''
    for p in presets:
        kws = p.get('keywords') or []
        if kws and any(k in prompt for k in kws):
            return p.get('image_data', ''), p.get('analysis', '')
    fallback = presets[-1] if presets else {}
    return fallback.get('image_data', ''), fallback.get('analysis', '')


def get_demo_chat_reply(user_msg: str, tool_summary: str = '') -> str:
    """演示模式下 Agent 最终回答（不调星火）。"""
    msg = (user_msg or '').strip()
    for item in _load_data().get('chat_replies') or []:
        if any(k in msg for k in item.get('keywords') or []):
            base = item.get('text', '')
            if tool_summary and '（尚无工具结果）' not in tool_summary:
                return f'{base}\n\n{tool_summary[:200]}'
            return base
    default = _load_data().get('chat_default', '')
    if tool_summary and '焕新作品已生成' in tool_summary:
        return f'非遗数字焕新已完成。{tool_summary[:120]}\n\n{default}'
    return default


def get_cached_source(img_b64: str):
    key = _image_hash(img_b64)
    return _source_cache.get(key)


def set_cached_source(img_b64: str, payload: dict):
    if len(_source_cache) >= _SOURCE_CACHE_MAX:
        _source_cache.pop(next(iter(_source_cache)))
    _source_cache[_image_hash(img_b64)] = payload
