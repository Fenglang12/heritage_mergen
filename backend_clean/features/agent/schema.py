"""Agent 工具 Schema：校验、纠错提示、Prompt 目录。"""

from __future__ import annotations

import copy
from typing import Any

# 轻量 JSON-Schema 子集（不引入 jsonschema 依赖，便于答辩环境）
TOOL_SCHEMAS: dict[str, dict] = {
    'search_heritage': {
        'description': '向量检索非遗百科（「XX是什么」类问题优先）',
        'required': ['query'],
        'properties': {
            'query': {'type': 'string', 'minLength': 1, 'maxLength': 80},
        },
    },
    'query_graph': {
        'description': '知识图谱 Text2SQL：传承人/地区/类别关系（非导航地址）',
        'required': ['question'],
        'properties': {
            'question': {'type': 'string', 'minLength': 2, 'maxLength': 200},
        },
    },
    'search_places': {
        'description': (
            '检索非遗相关文化地标；有用户 GPS 时应传 lng/lat 做周边检索，'
            '否则传 city 做同城关键词检索'
        ),
        'required': [],
        'properties': {
            'city': {'type': 'string', 'maxLength': 40},
            'keyword': {'type': 'string', 'maxLength': 20},
            'lng': {'type': 'number'},
            'lat': {'type': 'number'},
            'radius': {'type': 'number'},
        },
    },
    'plan_route': {
        'description': (
            '高德路线规划；起点可省略（系统会注入用户 GPS）。'
            '问「怎么去」「路线」且已有目标坐标时调用'
        ),
        'required': ['dest_lng', 'dest_lat'],
        'properties': {
            'origin_lng': {'type': 'number'},
            'origin_lat': {'type': 'number'},
            'dest_lng': {'type': 'number'},
            'dest_lat': {'type': 'number'},
            'mode': {'type': 'string', 'enum': ['driving', 'walking', 'transit', 'bicycling']},
            'citycode': {'type': 'string'},
        },
    },
    'identify_image': {
        'description': '图片识图溯源（仅当本轮已有用户图片时可调）',
        'required': ['image_b64'],
        'properties': {
            'image_b64': {'type': 'string', 'minLength': 8},
        },
    },
    'revive_heritage': {
        'description': '非遗数字焕新：文案/参考图生成艺术品',
        'required': ['prompt'],
        'properties': {
            'prompt': {'type': 'string', 'minLength': 2, 'maxLength': 500},
            'image_b64': {'type': 'string'},
        },
    },
    'plan_study_tour': {
        'description': (
            '复合研学任务：一次编排地标检索 + 百科背景 + 图谱关系，'
            '输出半天/一日结构化行程；有 GPS 时按距离排序并规划到第一站'
        ),
        'required': [],
        'properties': {
            'city': {'type': 'string', 'maxLength': 40},
            'theme': {'type': 'string', 'maxLength': 40},
            'hours': {'type': 'number'},
            'lng': {'type': 'number'},
            'lat': {'type': 'number'},
            'radius': {'type': 'number'},
        },
    },
}


def format_tool_catalog() -> str:
    """生成给模型看的工具目录（含参数说明）。"""
    lines = []
    for name, schema in TOOL_SCHEMAS.items():
        props = schema.get('properties') or {}
        req = set(schema.get('required') or [])
        arg_bits = []
        for key, meta in props.items():
            mark = '*' if key in req else ''
            typ = meta.get('type', 'any')
            arg_bits.append(f'{key}{mark}:{typ}')
        args_s = ', '.join(arg_bits) if arg_bits else '—'
        lines.append(f'- {name}({args_s}) — {schema.get("description", "")}')
    return '\n'.join(lines)


def _coerce_number(value: Any):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def validate_tool_args(tool: str, args: dict | None) -> tuple[bool, dict, str]:
    """
    校验并轻度纠错参数。
    返回 (ok, fixed_args, error_message)；ok=False 时 error 供模型下一轮自愈。
    """
    schema = TOOL_SCHEMAS.get(tool)
    if not schema:
        return False, {}, f'未知工具: {tool}'
    args = copy.deepcopy(args or {})
    props = schema.get('properties') or {}
    required = schema.get('required') or []

    # 丢掉未声明字段（保留扩展安全）
    unknown = [k for k in list(args.keys()) if k not in props]
    for k in unknown:
        args.pop(k, None)

    for key, meta in props.items():
        if key not in args or args[key] is None:
            continue
        typ = meta.get('type')
        val = args[key]
        if typ == 'string':
            if not isinstance(val, str):
                args[key] = str(val)
            s = args[key].strip()
            mx = meta.get('maxLength')
            mn = meta.get('minLength')
            if mx is not None:
                s = s[: int(mx)]
            args[key] = s
            if mn is not None and len(s) < int(mn):
                return False, args, f'参数 {key} 过短（至少 {mn} 字）'
            enum = meta.get('enum')
            if enum and s and s not in enum:
                return False, args, f'参数 {key} 必须是 {enum} 之一，收到「{s}」'
        elif typ == 'number':
            num = _coerce_number(val)
            if num is None:
                return False, args, f'参数 {key} 应为数字'
            args[key] = num

    for key in required:
        val = args.get(key)
        if val is None or (isinstance(val, str) and not val.strip()):
            return False, args, f'缺少必填参数: {key}'

    return True, args, ''
