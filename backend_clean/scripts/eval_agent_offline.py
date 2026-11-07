#!/usr/bin/env python3
"""
离线评测跑分（路线图 #8）：不调星火/外网。
对 eval_agent_cases.json 做启发式工具先验、记忆跑题、Schema、推荐路径、Grounding 检查，
输出成功率表（stdout + tests/eval_agent_report.md）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from features.agent.memory import (  # noqa: E402
    empty_memory,
    extract_open_place_keyword,
    message_continues_goal,
    message_diverges_from_goal,
    update_memory_from_turn,
)
from features.agent.parse import (  # noqa: E402
    append_grounding_block,
    build_grounded_places_answer,
    build_soft_prior_hint,
    enforce_suggest_path,
    infer_suggest_path,
    should_hint_graph,
    should_hint_heritage_kb,
    should_hint_location,
    should_hint_revive,
    should_plan_study_tour,
)
from features.agent.schema import validate_tool_args  # noqa: E402


def predict_tools(message: str) -> list[str]:
    """离线代理：与 soft prior / 降级兜底同序的工具倾向。"""
    m = message or ''
    if any(t in m for t in ('美食', '好吃', '吃饭', '餐厅', '小吃', '火锅', '卤水', '烧烤')):
        return ['search_places']
    if should_hint_revive(m):
        return ['revive_heritage']
    if should_plan_study_tour(m):
        return ['plan_study_tour']
    if should_hint_location(m):
        tools = ['search_places']
        if any(k in m for k in ('怎么去', '路线', '导航', '怎么走')):
            tools.append('plan_route')
        return tools
    if should_hint_graph(m):
        return ['query_graph']
    if should_hint_heritage_kb(m):
        return ['search_heritage']
    return []


def _mock_scratchpad_for_path(case: dict, predicted: list[str]) -> list:
    if case.get('mock_markers') is not None:
        return [{
            'tool': 'search_places',
            'result': {
                'ok': True,
                'city': '汕头市',
                'keyword': '美食',
                'loc_source': 'gps_around',
                'markers': case['mock_markers'],
            },
        }]
    expect = case.get('expect_tools_any') or predicted
    tool = (expect[0] if expect else (predicted[0] if predicted else None))
    if not tool:
        return []
    if tool == 'search_heritage':
        return [{'tool': tool, 'result': {'ok': True, 'context': '百科片段占位'}}]
    if tool == 'query_graph':
        return [{'tool': tool, 'result': {'ok': True, 'answer': '图谱答案占位', 'node_ids': ['n1']}}]
    if tool == 'search_places':
        return [{'tool': tool, 'result': {'ok': True, 'city': '汕头', 'markers': [
            {'base_name': '占位场馆'},
        ], 'count': 1}}]
    if tool == 'plan_study_tour':
        return [{'tool': tool, 'result': {
            'ok': True, 'theme': '英歌舞', 'city': '汕头市',
            'itinerary': [{'name': '站A'}], 'summary': '行程占位',
            'grounding': ['地标占位'],
        }}]
    if tool == 'revive_heritage':
        return [{'tool': tool, 'result': {'ok': True, 'url': 'http://x/y.png'}}]
    if tool == 'plan_route':
        return [{'tool': tool, 'result': {'ok': True, 'summary': '步行约1km'}}]
    return [{'tool': tool, 'result': {'ok': True}}]


def eval_case(case: dict) -> tuple[bool, list[str]]:
    fails: list[str] = []
    msg = case.get('message') or ''

    # Schema-only cases
    if 'schema_tool' in case:
        ok, _, err = validate_tool_args(case['schema_tool'], case.get('schema_args') or {})
        want = bool(case.get('schema_ok'))
        if ok != want:
            fails.append(f'schema ok={ok} want={want} err={err}')
        return (not fails), fails

    predicted = predict_tools(msg)
    expect_any = case.get('expect_tools_any') or []
    if expect_any and not any(t in predicted for t in expect_any):
        # soft prior 文字也可作弱证据
        soft = build_soft_prior_hint(msg)
        soft_hit = any(t in soft for t in expect_any)
        if not soft_hit:
            fails.append(f'tools predict={predicted} expect_any={expect_any}')

    for t in case.get('forbid_tools') or []:
        if t in predicted:
            fails.append(f'forbid tool predicted: {t}')

    theme = case.get('theme_prior')
    if case.get('expect_diverge') is True and not message_diverges_from_goal(msg, theme):
        fails.append('expect diverge')
    if case.get('expect_continue_goal') is True and not message_continues_goal(msg, theme):
        fails.append('expect continue_goal')

    open_kw = case.get('expect_open_keyword')
    if open_kw and extract_open_place_keyword(msg) != open_kw:
        fails.append(
            f'open_kw={extract_open_place_keyword(msg)!r} want={open_kw!r}'
        )

    if case.get('expect_memory_pause') or case.get('forbid_goal_activation') or case.get('expect_goal_done'):
        mem = empty_memory()
        if case.get('goal_prior_active') or case.get('theme_prior'):
            mem = update_memory_from_turn(
                mem,
                f"帮我安排{(theme or '非遗')}研学",
                [{'tool': 'plan_study_tour', 'result': {
                    'ok': True, 'theme': theme or '非遗', 'city': '汕头市',
                    'itinerary': [{'name': 'A'}],
                }}],
            )
        mem = update_memory_from_turn(mem, msg, [])
        if case.get('expect_memory_pause') and mem.get('goal_status') != 'paused':
            fails.append(f'memory status={mem.get("goal_status")} want=paused')
        if case.get('forbid_goal_activation') and mem.get('goal_status') == 'active':
            if '美食' in (mem.get('goal') or '') or '美食' in (mem.get('theme') or ''):
                fails.append('food activated as study goal')
        if case.get('expect_goal_done') and mem.get('goal_status') != 'done':
            fails.append(f'memory status={mem.get("goal_status")} want=done')

    pad = _mock_scratchpad_for_path(case, predicted)
    path = infer_suggest_path(msg, pad)
    if case.get('expect_path') and path != case['expect_path']:
        fails.append(f'path={path} want={case["expect_path"]}')

    if case.get('forbid_paths'):
        text = enforce_suggest_path('介绍一下。👉 [开始闯关](/quiz)', path or '/graph')
        for fp in case['forbid_paths']:
            if fp in text:
                fails.append(f'forbid path still present: {fp}')

    if case.get('need_grounding'):
        body = append_grounding_block('回答正文。', pad)
        if '**依据**' not in body:
            fails.append('grounding missing')

    if case.get('expect_grounded_places'):
        ans = build_grounded_places_answer(pad)
        if not ans or '高德' not in ans:
            fails.append('grounded places missing')
        for m in case.get('mock_markers') or []:
            name = m.get('base_name')
            if name and name not in (ans or ''):
                fails.append(f'missing marker {name}')

    return (not fails), fails


def main() -> int:
    cases_path = ROOT / 'tests' / 'eval_agent_cases.json'
    data = json.loads(cases_path.read_text(encoding='utf-8'))
    cases = data.get('cases') or []
    rows = []
    passed = 0
    for case in cases:
        ok, fails = eval_case(case)
        if ok:
            passed += 1
        rows.append({
            'id': case.get('id'),
            'ok': ok,
            'fails': fails,
            'message': (case.get('message') or '')[:40],
        })

    total = len(rows)
    rate = (passed / total * 100) if total else 0.0

    lines = [
        '# Agent 离线评测成功率表',
        '',
        f'- 用例数：{total}',
        f'- 通过：{passed}',
        f'- 成功率：**{rate:.1f}%**',
        f'- 脚本：`scripts/eval_agent_offline.py`（不调星火/外网）',
        '',
        '| ID | 结果 | 说明 |',
        '|---|---|---|',
    ]
    for r in rows:
        mark = 'PASS' if r['ok'] else 'FAIL'
        note = '—' if r['ok'] else '; '.join(r['fails'])[:80]
        lines.append(f"| `{r['id']}` | {mark} | {note} |")
    lines.append('')

    report = ROOT / 'tests' / 'eval_agent_report.md'
    report.write_text('\n'.join(lines), encoding='utf-8')

    print(f'EVAL {passed}/{total} ({rate:.1f}%)')
    for r in rows:
        flag = 'OK' if r['ok'] else 'FAIL'
        extra = '' if r['ok'] else f" :: {'; '.join(r['fails'])}"
        print(f"  [{flag}] {r['id']}{extra}")
    print(f'Report: {report}')

    # 门禁：起步集至少 20 条且成功率 ≥ 85%
    if total < 20:
        print('GATE FAIL: need >= 20 cases')
        return 1
    if rate < 85.0:
        print('GATE FAIL: success rate < 85%')
        return 1
    print('GATE OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
