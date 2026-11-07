"""会话记忆单元测试（不依赖外网）。"""

import unittest

from features.agent.memory import (
    empty_memory,
    extract_open_place_keyword,
    format_session_memory_block,
    memory_public_view,
    message_diverges_from_goal,
    update_memory_from_turn,
)
from features.agent.tools import filter_study_tour_markers


class TestSessionMemory(unittest.TestCase):
    def test_plan_study_tour_sets_goal(self):
        mem = empty_memory()
        pad = [{
            'tool': 'plan_study_tour',
            'result': {
                'ok': True,
                'theme': '英歌舞',
                'city': '汕头市',
                'summary': '安排 3 站',
                'itinerary': [
                    {'name': '潮博馆潮汕英歌舞', 'address': '汕头'},
                    {'name': '英歌舞体验馆', 'address': ''},
                ],
            },
        }]
        mem = update_memory_from_turn(mem, '帮我安排半天英歌舞研学', pad)
        self.assertEqual(mem['goal_status'], 'active')
        self.assertEqual(mem['goal'], '正在做英歌舞研学')
        self.assertEqual(mem['theme'], '英歌舞')
        self.assertEqual(len(mem['itinerary']), 2)
        pub = memory_public_view(mem)
        self.assertEqual(pub['goal'], '正在做英歌舞研学')
        block = format_session_memory_block(mem)
        self.assertIn('正在做英歌舞研学', block)
        self.assertIn('潮博馆潮汕英歌舞', block)

    def test_end_goal(self):
        mem = empty_memory()
        mem = update_memory_from_turn(
            mem,
            '帮我安排英歌舞研学',
            [{'tool': 'plan_study_tour', 'result': {
                'ok': True, 'theme': '英歌舞', 'city': '汕头市',
                'itinerary': [{'name': 'A'}],
            }}],
        )
        mem = update_memory_from_turn(mem, '先不做了换个主题', [])
        self.assertEqual(mem['goal_status'], 'done')

    def test_location_activates_theme(self):
        mem = empty_memory()
        mem = update_memory_from_turn(
            mem,
            '附近有什么英歌舞相关的地方？',
            [{'tool': 'search_places', 'result': {
                'ok': True, 'keyword': '英歌舞', 'city': '汕头市',
                'markers': [{'base_name': '英歌舞体验馆'}],
            }}],
        )
        self.assertEqual(mem['goal'], '正在做英歌舞研学')
        self.assertIn('英歌舞体验馆', mem['places'])

    def test_food_pauses_goal(self):
        self.assertTrue(message_diverges_from_goal('帮我找美食', '英歌舞'))
        mem = empty_memory()
        mem = update_memory_from_turn(
            mem,
            '帮我安排英歌舞研学',
            [{'tool': 'plan_study_tour', 'result': {
                'ok': True, 'theme': '英歌舞', 'city': '汕头市',
                'itinerary': [{'name': 'A'}],
            }}],
        )
        mem = update_memory_from_turn(mem, '我的意思是让你帮我找美食', [])
        self.assertEqual(mem['goal_status'], 'paused')
        self.assertEqual(mem.get('theme'), '英歌舞')
        block = format_session_memory_block(mem, '帮我找美食')
        self.assertIn('美食', block)
        self.assertIn('禁止再推', block)

    def test_food_alone_does_not_become_study_goal(self):
        mem = empty_memory()
        mem = update_memory_from_turn(mem, '帮我找附近的美食', [])
        self.assertNotEqual(mem.get('goal_status'), 'active')
        self.assertNotIn('美食', (mem.get('goal') or ''))

    def test_extract_open_prefers_specific_dish(self):
        self.assertEqual(extract_open_place_keyword('帮我找潮州卤水火锅'), '潮州卤水火锅')
        self.assertEqual(extract_open_place_keyword('我想吃卤水火锅'), '卤水火锅')
        self.assertEqual(extract_open_place_keyword('附近有美食吗'), '美食')
        self.assertEqual(extract_open_place_keyword('有没有烧烤'), '烧烤')

    def test_study_tour_drops_theme_food_hijack(self):
        markers = [
            {'base_name': '英歌舞体验馆', 'type': '科教文化服务', 'address': ''},
            {'base_name': '英歌舞主题火锅店', 'type': '餐饮服务', 'address': ''},
        ]
        kept = filter_study_tour_markers(markers, '英歌舞')
        names = [m['base_name'] for m in kept]
        self.assertIn('英歌舞体验馆', names)
        self.assertNotIn('英歌舞主题火锅店', names)


if __name__ == '__main__':
    unittest.main()
