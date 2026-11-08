"""将清洗后的图谱节点/关系导入 MySQL。"""

import json

import pymysql

from core.config import Config


def init_mysql_graph():
    print("⏳ 连接 MySQL 数据库...")
    conn = pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASS,
        database=Config.DB_NAME,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    cursor = conn.cursor()

    # 1. 创建图谱专用表
    print("⏳ 正在建立图谱关系表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS graph_nodes (
            id VARCHAR(100) PRIMARY KEY,
            label VARCHAR(50),
            properties JSON
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS graph_edges (
            id INT AUTO_INCREMENT PRIMARY KEY,
            source VARCHAR(100),
            target VARCHAR(100),
            relationship VARCHAR(50),
            INDEX (source),
            INDEX (target)
        )
    """)

    # 清空旧数据（防止重复运行）
    cursor.execute("TRUNCATE TABLE graph_nodes")
    cursor.execute("TRUNCATE TABLE graph_edges")

    # 2. 导入节点数据
    print("⏳ 开始导入节点数据...")
    with open('clean_nodes.json', encoding='utf-8') as f:
        nodes = json.load(f)
        for node in nodes:
            cursor.execute(
                "INSERT INTO graph_nodes (id, label, properties) VALUES (%s, %s, %s)",
                (node['id'], node['label'], json.dumps(node['properties'], ensure_ascii=False))
            )

    # 3. 导入关系（边）数据
    print("⏳ 开始导入关系数据...")
    with open('clean_edges.json', encoding='utf-8') as f:
        edges = json.load(f)
        for edge in edges:
            cursor.execute(
                "INSERT INTO graph_edges (source, target, relationship) VALUES (%s, %s, %s)",
                (edge['source'], edge['target'], edge['relationship'])
            )

    conn.commit()
    cursor.close()
    conn.close()
    print(f"✅ 成功导入 {len(nodes)} 个节点和 {len(edges)} 条关系到 MySQL！")


if __name__ == "__main__":
    init_mysql_graph()