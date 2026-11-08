"""Agent 引擎单元测试（不依赖讯飞 API）。"""

import unittest

from features.agent.engine import HeritageAgent
from features.agent.memory import empty_memory
from features.agent.parse import (
    AGENT_PATH_LABELS,
    append_grounding_block,
    build_grounded_places_answer,
    build_soft_prior_hint,
    enforce_suggest_path,
    extract_heritage_search_query,
    extract_place_search_args,
    extract_study_tour_args,
    infer_suggest_path,
    normalize_agent_suggest_links,
    parse_tool_call,
    parse_tool_call_with_validation,
    should_hint_graph,
    should_hint_heritage_kb,
    should_hint_location,
    should_plan_study_tour,
    summarize_tool_result,
)
from features.agent.schema import format_tool_catalog, validate_tool_args


class TestParseToolCall(unittest.TestCase):
    def test_valid_tool_call(self):
        text = (
            '正在查询。\n<tool_call>\n'
            '{"tool": "query_graph", "args": {"question": "白蛇传说类别"}}\n'
            '</tool_call>'
        )
        parsed = parse_tool_call(text)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed[0], 'query_graph')
        self.assertEqual(parsed[1]['question'], '白蛇传说类别')

    def test_revive_heritage_tool_call(self):
        text = (
            '<tool_call>\n'
            '{"tool": "revive_heritage", "args": {"prompt": "赛博朋克风格剪纸"}}\n'
            '</tool_call>'
        )
        parsed = parse_tool_call(text)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed[0], 'revive_heritage')

    def test_no_tool_call_returns_none(self):
        self.assertIsNone(parse_tool_call('直接回答用户。'))

    def test_invalid_json_returns_none(self):
        text = '<tool_call>{not json}</tool_call>'
        self.assertIsNone(parse_tool_call(text))

    def test_repair_trailing_comma(self):
        text = (
            '<tool_call>\n'
            '{"tool": "search_heritage", "args": {"query": "粤剧",}}\n'
            '</tool_call>'
        )
        parsed = parse_tool_call(text)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed[0], 'search_heritage')

    def test_validate_missing_required(self):
        text = '<tool_call>{"tool": "search_heritage", "args": {}}</tool_call>'
        v = parse_tool_call_with_validation(text)
        self.assertFalse(v['ok'])
        self.assertEqual(v['tool'], 'search_heritage')
        self.assertIn('query', v['error'])

    def test_validate_ok(self):
        text = '<tool_call>{"tool": "search_heritage", "args": {"query": "粤剧"}}</tool_call>'
        v = parse_tool_call_with_validation(text)
        self.assertTrue(v['ok'])
        self.assertEqual(v['args']['query'], '粤剧')


class TestSoftPriorAndStudyTour(unittest.TestCase):
    def test_soft_prior_not_empty_for_kb(self):
        hint = build_soft_prior_hint('粤剧是什么')
        self.assertIn('软提示', hint)
        self.assertIn('search_heritage', hint)

    def test_study_tour_detect(self):
        self.assertTrue(should_plan_study_tour('帮我安排汕头半天英歌舞研学'))
        self.assertFalse(should_plan_study_tour('安排一下晚饭'))  # 无非遗语境
        args = extract_study_tour_args('帮我安排广州半天粤剧研学')
        self.assertIn('广州', args['city'])
        self.assertEqual(args['hours'], 4.0)

    def test_study_tour_suggest_map(self):
        pad = [{'tool': 'plan_study_tour', 'result': {'ok': True, 'itinerary': []}}]
        self.assertEqual(infer_suggest_path('安排行程', pad), '/map')

    def test_schema_catalog_has_study_tour(self):
        cat = format_tool_catalog()
        self.assertIn('plan_study_tour', cat)
        self.assertIn('lng', cat)  # 空间 Agent：search_places / plan_study_tour 含坐标

    def test_plan_route_schema_dest_required_origin_optional(self):
        ok, args, err = validate_tool_args(
            'plan_route',
            {'dest_lng': 116.7, 'dest_lat': 23.3, 'mode': 'walking'},
        )
        self.assertTrue(ok, err)
        self.assertEqual(args['dest_lng'], 116.7)

    def test_validate_hours_coerce(self):
        ok, args, err = validate_tool_args('plan_study_tour', {'hours': '4', 'theme': '英歌舞'})
        self.assertTrue(ok)
        self.assertEqual(args['hours'], 4.0)
        self.assertEqual(err, '')


class TestGrounding(unittest.TestCase):
    def test_append_grounding_from_heritage(self):
        pad = [{
            'tool': 'search_heritage',
            'result': {'ok': True, 'context': '【非遗项目科普】粤剧是广东传统戏曲'},
        }]
        out = append_grounding_block('粤剧历史悠久。', pad)
        self.assertIn('**依据**', out)
        self.assertIn('百科检索', out)

    def test_grounded_places_uses_tool_markers_only(self):
        pad = [{
            'tool': 'search_places',
            'result': {
                'ok': True,
                'city': '汕头市',
                'keyword': '美食',
                'loc_source': 'gps_around',
                'markers': [
                    {'base_name': '单元测试店甲', 'type': '餐饮服务', 'address': '路1', 'distance_m': 50},
                    {'base_name': '单元测试店乙', 'type': '餐饮服务', 'address': '路2', 'distance_m': 80},
                ],
            },
        }]
        out = build_grounded_places_answer(pad)
        self.assertIn('单元测试店甲', out)
        self.assertIn('单元测试店乙', out)
        self.assertIn('高德', out)


class TestGraphHint(unittest.TestCase):
    def test_hint_keywords(self):
        self.assertTrue(should_hint_graph('白蛇传说属于什么类别？'))
        self.assertFalse(should_hint_graph('今天天气怎么样'))

    def test_location_question_not_graph(self):
        self.assertFalse(should_hint_graph('皮影戏在哪里？'))
        self.assertTrue(should_hint_location('皮影戏在哪里？'))


class TestPlaceSearchArgs(unittest.TestCase):
    def test_extract_shadow_puppet(self):
        args = extract_place_search_args('皮影戏在哪里？')
        self.assertEqual(args['keyword'], '皮影戏')
        self.assertEqual(args['city'], '')

    def test_extract_with_city(self):
        args = extract_place_search_args('广州的英歌舞在哪里看')
        self.assertIn('广州', args['city'])


class TestHeritageKbHint(unittest.TestCase):
    def test_what_is_triggers_kb(self):
        self.assertTrue(should_hint_heritage_kb('粤剧是什么'))
        self.assertFalse(should_hint_heritage_kb('粤剧在哪里'))

    def test_extract_query(self):
        self.assertEqual(extract_heritage_search_query('粤剧是什么'), '粤剧')

    def test_graph_question_not_kb(self):
        self.assertFalse(should_hint_heritage_kb('皮影戏有哪些传承人？'))


class TestInferSuggestPath(unittest.TestCase):
    def test_location_question_maps_to_map(self):
        self.assertEqual(infer_suggest_path('皮影戏在哪里？'), '/map')

    def test_heritage_place_keyword(self):
        self.assertTrue(should_hint_location('我想了解皮影戏的非遗地点'))
        args = extract_place_search_args('我想了解皮影戏的非遗地点')
        self.assertEqual(args['keyword'], '皮影戏')

    def test_heritage_kb_maps_to_graph(self):
        self.assertEqual(infer_suggest_path('粤剧是什么'), '/graph')

    def test_search_heritage_scratchpad_maps_to_graph(self):
        pad = [{'tool': 'search_heritage', 'result': {'ok': True, 'context': '【非遗项目科普】粤剧'}}]
        self.assertEqual(infer_suggest_path('粤剧是什么', pad), '/graph')

    def test_revive_with_identify_maps_to_revive_not_map(self):
        pad = [
            {'tool': 'identify_image', 'result': {'ok': True, 'markers': [{'id': '1'}]}},
            {'tool': 'revive_heritage', 'result': {'ok': True, 'url': 'data:image/png;base64,x'}},
        ]
        msg = '请按国潮插画风格焕新我上传的图片'
        self.assertEqual(infer_suggest_path(msg, pad), '/revive')

    def test_search_places_scratchpad_maps_to_map(self):
        pad = [{'tool': 'search_places', 'result': {'ok': True, 'markers': []}}]
        self.assertEqual(infer_suggest_path('介绍一下', pad), '/map')

    def test_quiz_intent_not_recommended(self):
        self.assertNotEqual(infer_suggest_path('出几道题考考我'), '/quiz')
        self.assertNotIn('/quiz', AGENT_PATH_LABELS)

    def test_graph_intent(self):
        self.assertEqual(infer_suggest_path('皮影戏有哪些传承人？'), '/graph')


class TestEnforceSuggestPath(unittest.TestCase):
    def test_replace_wrong_quiz_with_map(self):
        raw = '广州有皮影剧场。\n\n👉 想挑战皮影戏知识吗？[开始闯关](/quiz)'
        fixed = enforce_suggest_path(raw, '/map')
        self.assertIn('(/map)', fixed)
        self.assertNotIn('(/quiz)', fixed)

    def test_append_map_when_missing(self):
        raw = '广州有皮影剧场。'
        fixed = enforce_suggest_path(raw, '/map')
        self.assertIn('[打开非遗地图](/map)', fixed)


class TestSummarize(unittest.TestCase):
    def test_long_string_truncated(self):
        s = summarize_tool_result('x' * 500)
        self.assertLessEqual(len(s), 403)

    def test_dict_summary(self):
        s = summarize_tool_result({'status': 'success', 'markers': [1, 2]})
        self.assertIn('success', s)

    def test_failed_tool_summary(self):
        s = summarize_tool_result({'ok': False, 'error': 'API 限流', 'suggestion': '稍后重试'})
        self.assertIn('失败', s)
        self.assertIn('稍后重试', s)

    def test_heritage_context_summary(self):
        s = summarize_tool_result({'ok': True, 'context': '【非遗项目科普】粤剧属于戏曲类别'})
        self.assertIn('粤剧', s)


class TestNormalizeSuggestLinks(unittest.TestCase):
    def test_fix_malformed_quiz_link_to_graph(self):
        raw = '👉 了解更多关于英歌舞的信息？[/quiz]'
        fixed = normalize_agent_suggest_links(raw)
        self.assertIn('[知识图谱](/graph)', fixed)
        self.assertNotIn('(/quiz)', fixed)
        self.assertNotIn('？[/quiz]', fixed)

    def test_fix_invalid_search_heritage_link(self):
        raw = '👉 想了解更多？[非遗百科](/search_heritage?query=粤剧)'
        fixed = normalize_agent_suggest_links(raw, preferred_path='/graph')
        self.assertIn('[知识图谱](/graph)', fixed)
        self.assertNotIn('search_heritage', fixed)

    def test_keep_valid_markdown_link(self):
        raw = '👉 想查看关系吗？[知识图谱](/graph)'
        self.assertEqual(normalize_agent_suggest_links(raw), raw)

    def test_path_labels_no_quiz(self):
        self.assertIn('/map', AGENT_PATH_LABELS)
        self.assertNotIn('/quiz', AGENT_PATH_LABELS)


class TestDivergeKeywordInject(unittest.TestCase):
    def _agent_with_theme(self, msg: str):
        mem = empty_memory()
        mem['theme'] = '英歌舞'
        mem['goal'] = '正在做英歌舞研学'
        mem['goal_status'] = 'active'
        mem['city'] = '汕头市'
        agent = HeritageAgent(session_memory=mem)
        agent._current_user_msg = msg
        return agent

    def test_keeps_specific_model_keyword(self):
        agent = self._agent_with_theme('帮我找潮州卤水火锅')
        out = agent._inject_user_geo('search_places', {'keyword': '潮州卤水火锅'})
        self.assertEqual(out['keyword'], '潮州卤水火锅')

    def test_upgrades_short_hotpot_to_phrase(self):
        agent = self._agent_with_theme('帮我找卤水火锅')
        out = agent._inject_user_geo('search_places', {'keyword': '火锅'})
        self.assertEqual(out['keyword'], '卤水火锅')

    def test_strips_theme_pollution(self):
        agent = self._agent_with_theme('帮我找美食')
        out = agent._inject_user_geo('search_places', {'keyword': '英歌舞'})
        self.assertEqual(out['keyword'], '美食')


if __name__ == '__main__':
    unittest.main()
