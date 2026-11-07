"""从图谱 SQL 查询结果中提取可用于前端高亮的节点标识。"""

import json
import logging

logger = logging.getLogger(__name__)


def _parse_properties(raw):
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def extract_node_ids(rows) -> list:
    """
    从 graph_nodes 查询行中提取节点 id 与名称。
    返回去重后的列表，供 D3 图谱高亮使用。
    """
    if not isinstance(rows, list):
        return []

    ids = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        node_id = row.get('id')
        if node_id:
            ids.append(str(node_id).strip())
        props = _parse_properties(row.get('properties'))
        name = props.get('name')
        if name:
            ids.append(str(name).strip())

    seen = set()
    unique = []
    for item in ids:
        if item and item not in seen:
            seen.add(item)
            unique.append(item)
    return unique
