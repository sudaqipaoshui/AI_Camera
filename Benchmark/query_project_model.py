#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目和模型关系查询工具

用法:
    python tools/query_project_model.py                    # 列出所有项目类型
    python tools/query_project_model.py --models            # 列出所有模型
    python tools/query_project_model.py --project face      # 查询特定项目
    python tools/query_project_model.py --model yolov8      # 查询包含特定关键词的模型
"""

import json
import sys
import argparse
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAPPING_FILE = PROJECT_ROOT / "docs" / "project_model_mapping.json"
DEPLOY_PATH = Path("/Users/sonic/DreamSports/X5/deploy")

def load_mapping():
    """加载项目-模型映射"""
    if MAPPING_FILE.exists():
        with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def list_projects():
    """列出所有项目类型"""
    mapping = load_mapping()
    if not mapping:
        print("❌ 映射文件不存在，请先运行文档生成脚本")
        return
    
    print("=" * 80)
    print("项目类型列表")
    print("=" * 80)
    for i, project in enumerate(mapping['projects'], 1):
        print(f"{i:2d}. {project['type']:30s} ({project['config_dir']})")
    print(f"\n总计: {mapping['total_projects']} 个项目类型")

def list_models():
    """列出所有模型"""
    mapping = load_mapping()
    if not mapping:
        print("❌ 映射文件不存在，请先运行文档生成脚本")
        return
    
    print("=" * 80)
    print("模型文件列表")
    print("=" * 80)
    for i, model in enumerate(mapping['models'], 1):
        print(f"{i:2d}. {model['name']:50s} ({model['type']})")
    print(f"\n总计: {mapping['total_models']} 个模型文件")

def search_project(keyword):
    """搜索项目"""
    mapping = load_mapping()
    if not mapping:
        print("❌ 映射文件不存在，请先运行文档生成脚本")
        return
    
    keyword = keyword.lower()
    matches = [p for p in mapping['projects'] if keyword in p['type'].lower()]
    
    if not matches:
        print(f"❌ 未找到包含 '{keyword}' 的项目")
        return
    
    print("=" * 80)
    print(f"搜索结果: '{keyword}'")
    print("=" * 80)
    for i, project in enumerate(matches, 1):
        print(f"{i}. {project['type']}")
        print(f"   配置目录: {project['config_dir']}")
        print(f"   路径: {project['path']}")
        print()

def search_model(keyword):
    """搜索模型"""
    mapping = load_mapping()
    if not mapping:
        print("❌ 映射文件不存在，请先运行文档生成脚本")
        return
    
    keyword = keyword.lower()
    matches = [m for m in mapping['models'] if keyword in m['name'].lower()]
    
    if not matches:
        print(f"❌ 未找到包含 '{keyword}' 的模型")
        return
    
    print("=" * 80)
    print(f"搜索结果: '{keyword}'")
    print("=" * 80)
    for i, model in enumerate(matches, 1):
        print(f"{i}. {model['name']}")
        print(f"   类型: {model['type']}")
        print(f"   路径: {model['path']}")
        print()

def show_summary():
    """显示摘要信息"""
    mapping = load_mapping()
    if not mapping:
        print("❌ 映射文件不存在，请先运行文档生成脚本")
        return
    
    print("=" * 80)
    print("项目-模型关系摘要")
    print("=" * 80)
    print(f"项目类型数量: {mapping['total_projects']}")
    print(f"模型文件数量: {mapping['total_models']}")
    print()
    print("项目类型:")
    for project in mapping['projects']:
        print(f"  - {project['type']}")
    print()
    print("模型类型分布:")
    model_types = {}
    for model in mapping['models']:
        model_type = model['type']
        model_types[model_type] = model_types.get(model_type, 0) + 1
    for model_type, count in sorted(model_types.items()):
        print(f"  - {model_type}: {count} 个")

def main():
    parser = argparse.ArgumentParser(description='项目和模型关系查询工具')
    parser.add_argument('--projects', action='store_true', help='列出所有项目类型')
    parser.add_argument('--models', action='store_true', help='列出所有模型')
    parser.add_argument('--project', type=str, help='搜索项目（支持关键词）')
    parser.add_argument('--model', type=str, help='搜索模型（支持关键词）')
    parser.add_argument('--summary', action='store_true', help='显示摘要信息')
    
    args = parser.parse_args()
    
    if args.projects:
        list_projects()
    elif args.models:
        list_models()
    elif args.project:
        search_project(args.project)
    elif args.model:
        search_model(args.model)
    elif args.summary:
        show_summary()
    else:
        # 默认显示摘要
        show_summary()
        print()
        print("使用 --help 查看所有选项")

if __name__ == '__main__':
    main()

