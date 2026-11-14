"""闯关答题：抽题上下文构建与 LLM 出题（供 REST / SSE 复用）。"""

import json
import logging
import re

import pymysql

from core.config import Config
from shared.utils import sync_llm_call

logger = logging.getLogger(__name__)


def _get_db_conn():
    return pymysql.connect(
        host=Config.DB_HOST, user=Config.DB_USER,
        password=Config.DB_PASS, database=Config.DB_NAME,
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor,
    )


def _parse_props(node):
    props = node.get('properties') or {}
    if isinstance(props, str):
        try:
            props = json.loads(props)
        except json.JSONDecodeError:
            props = {}
    return props


def _fetch_quiz_nodes():
    """从图谱库抽取非遗项目与传承人节点文本。"""
    conn = _get_db_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, label, properties FROM graph_nodes
                WHERE label = '非遗项目' ORDER BY RAND() LIMIT 6
            """)
            heritage_nodes = cursor.fetchall()
            cursor.execute("""
                SELECT id, label, properties FROM graph_nodes
                WHERE label = '传承人' ORDER BY RAND() LIMIT 4
            """)
            inheritor_nodes = cursor.fetchall()
    finally:
        conn.close()

    heritage_texts, inheritor_texts = [], []
    for n in heritage_nodes:
        props = _parse_props(n)
        name = (props.get('name') or '').strip()
        if not name:
            continue
        parts = [f'· 项目名称：{name}']
        for key, label in (
            ('category', '类别'), ('region', '所在地区'),
            ('batch', '入选批次'), ('protection_unit', '保护单位'),
        ):
            if props.get(key):
                parts.append(f'{label}：{props[key]}')
        heritage_texts.append('，'.join(parts))

    for n in inheritor_nodes:
        props = _parse_props(n)
        name = (props.get('name') or '').strip()
        if not name:
            continue
        parts = [f'· 传承人姓名：{name}']
        for key, label in (('gender', '性别'), ('ethnicity', '民族'), ('work_unit', '工作单位')):
            val = props.get(key)
            if val and str(val).strip():
                parts.append(f'{label}：{val}')
        inheritor_texts.append('，'.join(parts))

    return heritage_texts, inheritor_texts


def generate_quiz_questions():
    """
    生成 5 道选择题。
    返回 (questions_list, error_msg)；成功时 error_msg 为 None。
    """
    heritage_texts, inheritor_texts = _fetch_quiz_nodes()
    if len(heritage_texts) < 3 or len(inheritor_texts) < 2:
        return None, '知识库内容不足，请先完善非遗数据'

    heritage_info = '\n'.join(heritage_texts[:3])
    inheritor_info = '\n'.join(inheritor_texts[:2])

    prompt = f"""你是非遗文化出题专家。请根据下方数据，严格出5道单选题，直接输出JSON数组，不要输出任何其他内容。

【非遗项目数据】（用于第1、2、3题）：
{heritage_info}

【传承人数据】（用于第4、5题）：
{inheritor_info}

输出格式为JSON数组，共5个元素，每个元素包含：
- id: 题号（1-5）
- question: 完整的疑问句
- options: ["A. 内容", "B. 内容", "C. 内容", "D. 内容"]
- answer: 正确选项字母，如 "A"
- explanation: 不超过50字的解析

出题要求：
1. 第1~3题对应前3条非遗项目，第4~5题对应前2条传承人
2. 每题只用对应那一条数据，禁止混用
3. 错误选项用同类型真实信息，不能捏造
"""
    raw = sync_llm_call(prompt, temperature=0.2, max_tokens=2500) or ''
    try:
        cleaned = raw.strip()
        if not cleaned:
            raise ValueError('模型未返回内容，请检查智谱 API Key 与额度')
        if '```' in cleaned:
            cleaned = re.sub(r'```(?:json)?', '', cleaned).strip('` \n')
        # 容错：截取首个 JSON 数组
        if not cleaned.startswith('['):
            m = re.search(r'\[[\s\S]*\]', cleaned)
            if m:
                cleaned = m.group(0)
        questions = json.loads(cleaned)
        if not isinstance(questions, list) or not questions:
            raise ValueError('返回题目为空')
        return questions, None
    except Exception as exc:
        logger.error('出题解析失败: %s\nraw=%s', exc, (raw or '')[:500])
        return None, f'AI出题失败，请重试（{exc}）'
