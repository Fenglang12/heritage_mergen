"""构建本地 Chroma 向量库（首次运行会自动下载嵌入模型）。"""

import re

from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings


def clean_and_transform_data(file_path):
    """提取乱码CSV中的关键信息，并转化为自然语言大白话"""
    print(f"正在清洗数据: {file_path} ...")

    # 【核心修复】：双重编码解析，专治各种 Windows Excel 导出的乱码 CSV
    content = ""
    try:
        # 先尝试带有 BOM 头的 UTF-8 编码读取
        with open(file_path, encoding='utf-8-sig') as f:
            content = f.read()
    except UnicodeDecodeError:
        # 如果报错，说明是 Windows 默认的 GBK/ANSI 编码
        with open(file_path, encoding='gbk', errors='ignore') as f:
            content = f.read()

    documents = []
    # 提取非遗项目节点信息
    # 匹配格式如: name: 苗族古歌（簪汪传）, batch: 2021(第五批), ...
    project_pattern = r'\{([^}]+name:\s*([^,]+)[^}]+)\}'
    matches = re.findall(project_pattern, content)

    for match_full, name in matches:
        # 将属性字符串转为字典方便取值
        props = {}
        for item in match_full.split(','):
            if ':' in item:
                k, v = item.split(':', 1)
                props[k.strip().replace('"', '')] = v.strip().replace('"', '')

        # 判断是项目还是传承人
        if 'category' in props:  # 这是一个非遗项目
            text = f"【非遗项目科普】{props.get('name', '未知项目')} 属于 {props.get('category', '未知')} 类别的非物质文化遗产。该项目主要分布在 {props.get('region', '未知地区')}，由 {props.get('protection_unit', '相关单位')} 负责保护，于 {props.get('batch', '未知批次')} 正式入选非遗名录。此项目类型为 {props.get('type', '常规项目')}。"
            documents.append(Document(page_content=text, metadata={"source": "非遗项目库", "name": props.get('name')}))

        elif 'ethnicity' in props and 'gender' in props:  # 这是一个传承人
            text = f"【传承人档案】{props.get('name', '未知')}，性别{props.get('gender', '未知')}，{props.get('ethnicity', '未知族')}，是非物质文化遗产的重要传承人。其所属的工作或申报单位是：{props.get('work_unit', '未知')}。编号为 {props.get('id', '无')}。"
            documents.append(Document(page_content=text, metadata={"source": "传承人库", "name": props.get('name')}))

    return documents


def build_vector_db():
    print("1. 开始读取并转化数据...")
    docs1 = clean_and_transform_data('nodes.csv')
    docs2 = clean_and_transform_data('relationships.csv')
    all_docs = docs1 + docs2

    # 去重
    unique_docs = {doc.page_content: doc for doc in all_docs}.values()
    final_docs = list(unique_docs)

    print(f"成功提取并生成了 {len(final_docs)} 条自然语言知识百科！")
    print("样本预览:", final_docs[0].page_content)

    print("\n2. 正在加载本地 Embedding 模型 (首次运行会自动下载模型文件，请耐心等待)...")
    # 使用轻量级的高质量中文向量模型
    embeddings = HuggingFaceEmbeddings(model_name="shibing624/text2vec-base-chinese")

    print("\n3. 正在构建本地 ChromaDB 向量数据库...")
    # 持久化目录设为项目下的 chroma_db 文件夹
    persist_directory = "./chroma_db"

    # 构建并持久化数据库（from_documents 会写入 persist_directory）
    Chroma.from_documents(
        documents=final_docs,
        embedding=embeddings,
        persist_directory=persist_directory,
    )

    print(f"\n✅ 数据库构建完成！所有知识已永久保存在 {persist_directory} 目录中。")


if __name__ == "__main__":
    build_vector_db()