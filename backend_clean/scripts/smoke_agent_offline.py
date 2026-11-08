#!/usr/bin/env python3
"""离线冒烟：Schema / 解析 / 软提示 / Grounding（不调用星火与外网）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from features.agent.parse import (
    append_grounding_block,
    build_soft_prior_hint,
    parse_tool_call_with_validation,
    should_plan_study_tour,
)
from features.agent.schema import TOOL_SCHEMAS, format_tool_catalog


def main() -> int:
    errors = []
    if 'plan_study_tour' not in TOOL_SCHEMAS:
        errors.append('missing plan_study_tour schema')
    if 'plan_study_tour' not in format_tool_catalog():
        errors.append('catalog missing plan_study_tour')

    v = parse_tool_call_with_validation(
        '<tool_call>{"tool":"search_heritage","args":{"query":"粤剧"}}</tool_call>'
    )
    if not v.get('ok'):
        errors.append(f'search_heritage validate failed: {v}')

    bad = parse_tool_call_with_validation(
        '<tool_call>{"tool":"search_heritage","args":{}}</tool_call>'
    )
    if bad.get('ok'):
        errors.append('expected missing query to fail')

    if not should_plan_study_tour('帮我安排半天非遗研学'):
        errors.append('study tour detect failed')

    if '软提示' not in build_soft_prior_hint('粤剧是什么'):
        errors.append('soft prior empty')

    grounded = append_grounding_block(
        '正文',
        [{'tool': 'search_heritage', 'result': {'ok': True, 'context': '粤剧简介'}}],
    )
    if '**依据**' not in grounded:
        errors.append('grounding missing')

    cases_path = ROOT / 'tests' / 'eval_agent_cases.json'
    cases = json.loads(cases_path.read_text(encoding='utf-8'))
    n_cases = len(cases.get('cases') or [])
    if n_cases < 20:
        errors.append(f'eval cases too few ({n_cases}<20)')

    if errors:
        print('SMOKE FAIL:')
        for e in errors:
            print(' -', e)
        return 1
    print(f'SMOKE OK: schema/parse/soft-prior/grounding/eval-cases({n_cases})')
    print('Hint: python scripts/eval_agent_offline.py  # 成功率表')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
