"""清洗图谱原始 CSV，输出 clean_nodes.json / clean_edges.json。"""

import json
import os
import re

# ================= 配置区 =================
INPUT_NODES = 'nodes.csv'
INPUT_RELS = 'relationships.csv'
OUTPUT_NODES = 'clean_nodes.json'
OUTPUT_EDGES = 'clean_edges.json'


def read_dirty_file(file_path):
    """双重编码容错读取，专治各类乱码"""
    if not os.path.exists(file_path):
        print(f"❌ 找不到文件: {file_path}")
        return []
    try:
        with open(file_path, encoding='utf-8-sig') as f:
            return f.readlines()
    except UnicodeDecodeError:
        with open(file_path, encoding='gbk', errors='ignore') as f:
            return f.readlines()


def parse_properties(prop_str):
    """
    智能解析属性字符串。
    应对极度恶劣的数据：比如正常的 'name: 民间文学' 和 畸形的 'name, 民间文学'
    以及被 Excel 截断产生的孤立逗号 ',work_unit: '
    """
    properties = {}
    # 清理各种乱入的引号
    prop_str = prop_str.replace('"', '').strip()

    # 按照逗号分割属性对，但需要过滤掉空字符串和无意义的断点
    raw_pairs = [p.strip() for p in prop_str.split(',') if p.strip()]

    for pair in raw_pairs:
        # 处理正常格式 key: value
        if ':' in pair:
            k, v = pair.split(':', 1)
            properties[k.strip()] = v.strip()
        # 处理畸形格式 key, value (由于前面用逗号split了，这里可能变成没有冒号的单字符串，需启发式修复)
        elif ' ' in pair:
            k, v = pair.split(' ', 1)
            properties[k.strip()] = v.strip()

    return properties


def clean_nodes(lines):
    """提取标准化节点数据"""
    print("⏳ 开始清洗节点数据...")
    nodes = []
    # 匹配模式：兼容 (:标签 {属性}) 以及畸形的 (,标签 {属性})
    # 正则解释：找括号，忽略冒号或逗号，抓取标签名，找大括号内的属性
    pattern = re.compile(r'\(\s*[:|,]?\s*([^\s{]+)\s*\{([^}]+)\}\s*\)')

    for line in lines:
        line = line.replace('"', '')  # 暴力去除所有CSV造成的乱码引号
        matches = pattern.findall(line)
        for label, prop_str in matches:
            props = parse_properties(prop_str)
            if props:
                # 确定唯一标识符（优先用 ID，没有 ID 用 Name）
                node_id = props.get('id', props.get('name', 'unknown'))
                nodes.append({
                    "id": node_id,
                    "label": label.strip(),
                    "properties": props
                })

    # 去重
    unique_nodes = {n['id']: n for n in nodes}.values()
    return list(unique_nodes)


def clean_edges(lines):
    """提取标准化关系（边）数据"""
    print("⏳ 开始清洗关系数据...")
    edges = []

    # 匹配模式：(源节点)-[:关系]->(目标节点)
    # 正则极其宽容，适应里面的乱码
    pattern = re.compile(r'\((.*?)\)\s*-\s*\[\s*:([^\s\]]+)\s*\]\s*->\s*\((.*?)\)')
    # 用于从节点字符串中抠出核心属性的正则
    prop_pattern = re.compile(r'\{([^}]+)\}')

    for line in lines:
        # 暴力清理换行符、多余引号和异常逗号拼装
        line = line.replace('"', '').replace('\n', '')

        matches = pattern.findall(line)
        for source_str, rel_type, target_str in matches:
            # 提取 Source 和 Target 的属性
            src_prop_match = prop_pattern.search(source_str)
            tgt_prop_match = prop_pattern.search(target_str)

            if src_prop_match and tgt_prop_match:
                src_props = parse_properties(src_prop_match.group(1))
                tgt_props = parse_properties(tgt_prop_match.group(1))

                # 寻找关联的键值对（通过 id 或 name 连线）
                src_id = src_props.get('id', src_props.get('name'))
                tgt_id = tgt_props.get('id', tgt_props.get('name'))

                if src_id and tgt_id:
                    edges.append({
                        "source": src_id,
                        "target": tgt_id,
                        "relationship": rel_type.strip()
                    })

    # 边去重（源、目标、关系完全一致的视为重复）
    unique_edges = []
    seen = set()
    for e in edges:
        identifier = f"{e['source']}-{e['relationship']}-{e['target']}"
        if identifier not in seen:
            seen.add(identifier)
            unique_edges.append(e)

    return unique_edges


def main():
    print("🚀 开始执行降维清洗任务...")

    # 1. 读取原始脏数据
    node_lines = read_dirty_file(INPUT_NODES)
    edge_lines = read_dirty_file(INPUT_RELS)

    # 2. 清洗与提取
    clean_n = clean_nodes(node_lines)
    clean_e = clean_edges(edge_lines)

    # 3. 导出为高贵、纯洁的 JSON 格式
    with open(OUTPUT_NODES, 'w', encoding='utf-8') as f:
        json.dump(clean_n, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_EDGES, 'w', encoding='utf-8') as f:
        json.dump(clean_e, f, ensure_ascii=False, indent=2)

    print("\n✅ 清洗完成！")
    print(f"📊 成功提取有效节点 (Nodes): {len(clean_n)} 个")
    print(f"🔗 成功提取有效关系 (Edges): {len(clean_e)} 条")
    print(f"📂 成果已保存至 '{OUTPUT_NODES}' 和 '{OUTPUT_EDGES}'")


if __name__ == "__main__":
    main()