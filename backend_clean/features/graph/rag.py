"""非遗知识图谱 RAG：自然语言 → Text2SQL → MySQL → LLM 总结。"""

import json
import logging

import pymysql

from core.config import Config
from features.graph.nodes import extract_node_ids

logger = logging.getLogger(__name__)


class MySQLGraphRAG:
    def __init__(self, llm_func):
        """
        初始化图谱 RAG 引擎。
        llm_func: 传入 utils.py 的 sync_spark_call，用于 Text2SQL 和最终总结
        """
        self.llm_call  = llm_func
        self.db_config = {
            'host':        Config.DB_HOST,
            'user':        Config.DB_USER,
            'password':    Config.DB_PASS,
            'database':    Config.DB_NAME,
            'charset':     'utf8mb4',
            'cursorclass': pymysql.cursors.DictCursor
        }

    # ── 执行 SQL ─────────────────────────────────────────────────

    def execute_sql(self, sql):
        """执行 SQL 并返回结果列表，出错时返回错误描述字符串"""
        conn = None
        try:
            conn = pymysql.connect(**self.db_config)
            with conn.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
                logger.debug('图谱查询结果（%d 行）: %s', len(rows), rows)
                return rows
        except Exception as e:
            logger.error('图谱 SQL 执行失败: %s | SQL: %s', e, sql)
            return f'SQL Error: {e}'
        finally:
            if conn:
                conn.close()

    # ── Text2SQL ─────────────────────────────────────────────────

    def text_to_sql(self, user_question):
        """使用少样本提示（Few-Shot Prompt）将用户自然语言转化为 SQL"""
        prompt = f"""
你是一个精通 MySQL 图谱查询的专家。请将用户的非遗提问转化为精确查询数据库的 SQL 语句。

【数据库真实结构与规则】
使用两张表模拟图谱结构：

1. `graph_nodes` (id, label, properties)
   - `id`：项目编号（如 'Ⅰ-6'、'01-0001'），绝对不是中文名称！
   - `label`：枚举 '非遗项目'、'传承人'、'地区'、'类别'、'批次'
   - `properties`：JSON 格式，非遗项目包含字段：
     {{"id":"Ⅰ-6","name":"白蛇传传说","type":"新增项目","batch":"2006(第一批)",
       "region":"浙江省杭州市","category":"民间文学","protection_unit":"杭州市文化馆"}}

2. `graph_edges` (id, source, target, relationship)
   - `source`：源节点编号（对应 graph_nodes.id）
   - `target`：目标节点标识
   - `relationship`：连线关系（如 '属于'、'公布于'）

【查询铁律（必须遵守）】
1. 名称模糊匹配：用 `properties->>'$.name' LIKE '%核心词%'`，禁止用 `id = '中文名'`
2. 优先查 Properties：地区/类别/保护单位直接用 `SELECT properties->>'$.字段名'`，禁止不必要的 JOIN
3. 模糊词宽泛化：用户说"白蛇传说"，SQL 写 LIKE '%白蛇%'

【正确 SQL 示例】
- 问：白蛇传说的发源地？
  答：SELECT properties->>'$.region' AS 地区 FROM graph_nodes WHERE label='非遗项目' AND properties->>'$.name' LIKE '%白蛇%';
- 问：白蛇传说属于什么类别？
  答：SELECT properties->>'$.category' AS 类别 FROM graph_nodes WHERE label='非遗项目' AND properties->>'$.name' LIKE '%白蛇%';
- 问：王安江是哪个民族？
  答：SELECT properties->>'$.ethnicity' AS 民族 FROM graph_nodes WHERE label='传承人' AND properties->>'$.name' LIKE '%王安江%';

用户问题：{user_question}
请仅输出纯 SQL 语句，不要有任何 Markdown 标记或额外说明文字。
        """
        raw = self.llm_call(prompt).strip()
        logger.debug('星火生成原始 SQL: %s', raw)

        # 清洗 Markdown 代码块标记
        sql = raw.replace('```sql', '').replace('```', '').replace('\n', ' ').strip()

        if 'SELECT' in sql.upper():
            start = sql.upper().find('SELECT')
            sql   = sql[start:]
            if ';' in sql:
                sql = sql[:sql.find(';') + 1]
            return sql
        return ''

    # ── 对外查询接口 ─────────────────────────────────────────────

    def query_structured(self, user_question: str) -> dict:
        """
        结构化查询：返回答案、节点 ID 列表与原始行，供 Agent 与图谱页高亮使用。
        """
        sql = self.text_to_sql(user_question)
        if not sql:
            return {
                'ok': False,
                'answer': '抱歉，未能理解该问题的逻辑，请换个更明确的问法。',
                'node_ids': [],
                'sql': '',
            }

        logger.info('图谱 SQL: %s', sql)
        data = self.execute_sql(sql)
        if not data or (isinstance(data, str) and 'Error' in str(data)):
            return {
                'ok': False,
                'answer': f'在图谱数据库中没找到关于「{user_question}」的数据。',
                'node_ids': [],
                'sql': sql,
            }

        node_ids = extract_node_ids(data)
        context = json.dumps(data, ensure_ascii=False)
        final_prompt = f"""基于以下图谱查询结果，用亲切的语气回答用户。
查询结果: {context}
用户问题: {user_question}
专家回答："""
        answer = (self.llm_call(final_prompt) or '').strip()
        if not answer:
            answer = '图谱总结服务暂时不可用，请稍后重试或检查星火配置。'
        return {
            'ok': True,
            'answer': answer,
            'node_ids': node_ids,
            'sql': sql,
            'raw_rows': data,
        }

    def query(self, user_question):
        """兼容旧接口：仅返回自然语言答案。"""
        result = self.query_structured(user_question)
        return result.get('answer', '查询失败')
