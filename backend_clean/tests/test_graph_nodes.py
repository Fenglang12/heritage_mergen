"""图谱节点 ID 提取测试。"""

import json
import unittest

from features.graph.nodes import extract_node_ids


class TestExtractNodeIds(unittest.TestCase):
    def test_from_row_id(self):
        rows = [{'id': 'Ⅰ-6', 'label': '非遗项目'}]
        self.assertEqual(extract_node_ids(rows), ['Ⅰ-6'])

    def test_from_properties_name(self):
        props = json.dumps({'name': '白蛇传传说', 'category': '民间文学'})
        rows = [{'properties': props}]
        self.assertIn('白蛇传传说', extract_node_ids(rows))

    def test_deduplicate(self):
        rows = [
            {'id': 'Ⅰ-6', 'properties': '{"name": "白蛇传传说"}'},
        ]
        ids = extract_node_ids(rows)
        self.assertEqual(len(ids), len(set(ids)))

    def test_non_list_returns_empty(self):
        self.assertEqual(extract_node_ids('SQL Error'), [])


if __name__ == '__main__':
    unittest.main()
