"""知识图谱全量数据构建：基础子图 + 随机传承人扩展子图。"""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

INHERITOR_SAMPLE_COUNT = 8
PROJECTS_PER_INHERITOR = 2
BASE_EDGE_LIMIT = 2000


def _parse_properties(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def _normalize_node_row(row: dict) -> dict:
    return {
        'id': row['id'].strip(),
        'label': row.get('label') or '未知',
        'properties': _parse_properties(row.get('properties')),
    }


def _infer_virtual_label(target_id: str) -> str:
    if any(k in target_id for k in ('省', '市', '县', '区', '自治')):
        return '地区'
    if '批' in target_id or re.match(r'[0-9]{4}', target_id):
        return '批次'
    return '类别'


def _ensure_virtual_node(nodes_by_id: dict, target_id: str) -> None:
    if target_id in nodes_by_id:
        return
    nodes_by_id[target_id] = {
        'id': target_id,
        'label': _infer_virtual_label(target_id),
        'properties': {'name': target_id},
    }


def _region_tokens_from_work_unit(work_unit: str) -> list[str]:
    """从工作单位提取省/市/县等 token，用于匹配非遗项目 region。"""
    text = (work_unit or '').strip()
    if not text:
        return []
    tokens: list[str] = []
    for pattern in (
        r'([\u4e00-\u9fa5]{2,12}?省)',
        r'([\u4e00-\u9fa5]{2,12}?市)',
        r'([\u4e00-\u9fa5]{2,12}?自治区)',
        r'([\u4e00-\u9fa5]{2,12}?县)',
    ):
        m = re.search(pattern, text)
        if m:
            full = m.group(1)
            tokens.append(full)
            if full.endswith('省'):
                tokens.append(full[:-1])
            elif full.endswith('市'):
                tokens.append(full[:-1])
    # 去重保序
    seen = set()
    out = []
    for t in tokens:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _fetch_random_inheritors(cursor, limit: int = INHERITOR_SAMPLE_COUNT) -> list[dict]:
    cursor.execute(
        """
        SELECT id, label, properties FROM graph_nodes
        WHERE label = '传承人'
        ORDER BY RAND()
        LIMIT %s
        """,
        (limit,),
    )
    return [_normalize_node_row(r) for r in cursor.fetchall()]


def _fetch_projects_for_inheritor(cursor, inheritor: dict, limit: int = PROJECTS_PER_INHERITOR) -> list[dict]:
    props = inheritor.get('properties') or {}
    work_unit = props.get('work_unit') or ''
    tokens = _region_tokens_from_work_unit(work_unit)

    if tokens:
        conds = []
        params: list[Any] = []
        for t in tokens:
            like = f'%{t}%'
            conds.append(
                "(properties->>'$.region' LIKE %s "
                "OR properties->>'$.protection_unit' LIKE %s)"
            )
            params.extend([like, like])
        where = ' OR '.join(conds)
        cursor.execute(
            f"""
            SELECT id, label, properties FROM graph_nodes
            WHERE label = '非遗项目' AND ({where})
            ORDER BY RAND()
            LIMIT %s
            """,
            (*params, limit),
        )
        rows = cursor.fetchall()
        if rows:
            return [_normalize_node_row(r) for r in rows]

    # 无地区命中时随机关联非遗项目，保证有扩展边
    cursor.execute(
        """
        SELECT id, label, properties FROM graph_nodes
        WHERE label = '非遗项目'
        ORDER BY RAND()
        LIMIT %s
        """,
        (limit,),
    )
    return [_normalize_node_row(r) for r in cursor.fetchall()]


def _fetch_edges_for_sources(cursor, source_ids: list[str]) -> list[dict]:
    if not source_ids:
        return []
    fmt = ','.join(['%s'] * len(source_ids))
    cursor.execute(
        f"""
        SELECT source, target, relationship FROM graph_edges
        WHERE source IN ({fmt})
        """,
        tuple(source_ids),
    )
    return [
        {
            'source': e['source'].strip(),
            'target': e['target'].strip(),
            'relationship': e['relationship'],
        }
        for e in cursor.fetchall()
    ]


def _append_inheritor_expansion(cursor, nodes_by_id: dict, edges: list[dict]) -> None:
    """随机 8 位传承人 + 按地区关联非遗项目 + 项目原有属于/位于边。"""
    inheritors = _fetch_random_inheritors(cursor, INHERITOR_SAMPLE_COUNT)
    if not inheritors:
        return

    edge_keys = {(e['source'], e['target'], e['relationship']) for e in edges}
    project_ids: list[str] = []

    for inh in inheritors:
        nodes_by_id[inh['id']] = inh
        projects = _fetch_projects_for_inheritor(cursor, inh, PROJECTS_PER_INHERITOR)
        for proj in projects:
            pid, iid = proj['id'], inh['id']
            nodes_by_id[pid] = proj
            project_ids.append(pid)
            key = (pid, iid, '传承人')
            if key not in edge_keys:
                edges.append({
                    'source': pid,
                    'target': iid,
                    'relationship': '传承人',
                })
                edge_keys.add(key)

    for pe in _fetch_edges_for_sources(cursor, list(set(project_ids))):
        key = (pe['source'], pe['target'], pe['relationship'])
        if key not in edge_keys:
            edges.append(pe)
            edge_keys.add(key)
        _ensure_virtual_node(nodes_by_id, pe['target'])

    logger.info(
        '图谱传承人扩展：%d 人，关联项目 %d 个，当前边 %d 条',
        len(inheritors),
        len(set(project_ids)),
        len(edges),
    )


def build_graph_payload(cursor) -> tuple[list[dict], list[dict]]:
    """构建前端 3D 图谱所需的 nodes / edges。"""
    cursor.execute(
        'SELECT source, target, relationship FROM graph_edges LIMIT %s',
        (BASE_EDGE_LIMIT,),
    )
    edges = [
        {
            'source': e['source'].strip(),
            'target': e['target'].strip(),
            'relationship': e['relationship'],
        }
        for e in cursor.fetchall()
    ]

    source_ids = {e['source'] for e in edges}
    nodes_by_id: dict[str, dict] = {}

    if source_ids:
        fmt = ','.join(['%s'] * len(source_ids))
        cursor.execute(
            f'SELECT id, label, properties FROM graph_nodes WHERE id IN ({fmt})',
            tuple(source_ids),
        )
        for row in cursor.fetchall():
            n = _normalize_node_row(row)
            nodes_by_id[n['id']] = n

    for e in edges:
        _ensure_virtual_node(nodes_by_id, e['target'])

    connected_ids = {e['source'] for e in edges} | {e['target'] for e in edges}
    nodes_by_id = {nid: n for nid, n in nodes_by_id.items() if nid in connected_ids}

    # 随机传承人扩展（合并进同一图）
    _append_inheritor_expansion(cursor, nodes_by_id, edges)

    connected_ids = {e['source'] for e in edges} | {e['target'] for e in edges}
    nodes = [n for n in nodes_by_id.values() if n['id'] in connected_ids]

    return nodes, edges
