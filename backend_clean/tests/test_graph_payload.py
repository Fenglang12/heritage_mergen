"""图谱数据构建单元测试（不依赖 MySQL）。"""

import unittest

from features.graph.graph_payload import _region_tokens_from_work_unit


class TestRegionTokens(unittest.TestCase):
    def test_hubei_theatre(self):
        tokens = _region_tokens_from_work_unit('湖北省京剧院')
        self.assertIn('湖北省', tokens)
        self.assertIn('湖北', tokens)

    def test_gansu_county(self):
        tokens = _region_tokens_from_work_unit('甘肃省肃南裕固族自治县')
        self.assertTrue(any('甘肃' in t for t in tokens))

    def test_empty(self):
        self.assertEqual(_region_tokens_from_work_unit(''), [])


if __name__ == '__main__':
    unittest.main()
