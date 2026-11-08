"""星火错误文案与清洗（不调用真实 API）。"""

import unittest

from shared.utils import (
    _filter_pois_for_theme,
    _poi_is_noise_for_theme,
    _poi_matches_keyword,
    _query_search_intent,
    format_spark_user_error,
    strip_legacy_spark_error_text,
)


class TestSparkUserErrors(unittest.TestCase):
    def test_app_id_no_auth_includes_raw(self):
        msg = format_spark_user_error(11200, 'AppIdNoAuthError')
        self.assertIn('SPARK_APPID', msg)
        self.assertIn('11200', msg)
        self.assertIn('AppIdNoAuthError', msg)
        self.assertIn('【原始错误】', msg)

    def test_strip_legacy_error_line(self):
        raw = '你好\n\n[接口错误 11200]: AppIdNoAuthError\n\n👉 [打开非遗地图](/map)'
        cleaned = strip_legacy_spark_error_text(raw)
        self.assertNotIn('接口错误', cleaned)
        self.assertIn('你好', cleaned)


class TestPoiMatch(unittest.TestCase):
    def test_match_shadow_puppet(self):
        poi = {'name': '中国皮影艺术博物馆', 'address': '成都市', 'type': '科教文化'}
        self.assertTrue(_poi_matches_keyword(poi, '皮影戏'))
        self.assertFalse(_poi_matches_keyword(poi, '粤剧'))


class TestPoiNoiseFilter(unittest.TestCase):
    def test_intent_open_vs_browse(self):
        self.assertEqual(_query_search_intent('卤水火锅'), 'open')
        self.assertEqual(_query_search_intent('英歌舞'), 'heritage')
        self.assertEqual(_query_search_intent(''), 'browse')

    def test_browse_drops_food_and_insect(self):
        noisy = [
            {'name': '潮澎派·非遗卤水火锅', 'type': '餐饮', 'address': ''},
            {'name': '肠粉博物馆', 'type': '餐饮', 'address': ''},
            {'name': '虫鸣探秘活体自然博物馆', 'type': '科教文化', 'address': ''},
            {'name': '魔法厨房&玩具博物馆', 'type': '休闲娱乐', 'address': ''},
        ]
        for p in noisy:
            self.assertTrue(_poi_is_noise_for_theme(p, ''), p['name'])

    def test_user_asks_hotpot_keeps_hotpot(self):
        poi = {'name': '潮澎派·非遗卤水火锅', 'type': '餐饮', 'address': ''}
        self.assertFalse(_poi_is_noise_for_theme(poi, '卤水火锅'))
        kept, mode = _filter_pois_for_theme([poi], '卤水火锅')
        self.assertEqual(mode, 'around_open')
        self.assertEqual(len(kept), 1)

    def test_generic_keeps_heritage(self):
        good = {'name': '信德缘非遗金包银', 'type': '购物服务', 'address': '长平路'}
        self.assertFalse(_poi_is_noise_for_theme(good, ''))
        self.assertTrue(_filter_pois_for_theme([good], '')[0])

    def test_theme_rejects_food_hijack(self):
        poi = {'name': '英歌舞主题火锅店', 'type': '餐饮', 'address': ''}
        self.assertTrue(_poi_is_noise_for_theme(poi, '英歌舞'))


if __name__ == '__main__':
    unittest.main()
