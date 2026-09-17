#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解析 result2.log 文件，生成统计表格
"""

import re
import csv
from collections import defaultdict
from pathlib import Path

def parse_log_line(line):
    """解析日志行，提取关键信息"""
    # 匹配格式: testerId=1998863780, name=49, crossTime=1762942487052, crossCount=1, score=00:34, lastScore=00:00
    pattern = r'testerId=(\d+),\s*name=([^,]+),\s*startTime=\d+,\s*crossTime=(\d+),\s*crossCount=(\d+),\s*score=([^,]+),\s*lastScore=([^\s]+)'
    match = re.search(pattern, line)
    
    if match:
        tester_id = match.group(1)
        name = match.group(2)
        cross_time = int(match.group(3))
        cross_count = int(match.group(4))
        score = match.group(5)
        last_score = match.group(6)
        
        return {
            'testerId': tester_id,
            'name': name,
            'crossTime': cross_time,
            'crossCount': cross_count,
            'score': score,
            'lastScore': last_score,
            'raw_line': line.strip()
        }
    return None

def parse_log_file(log_file_path):
    """解析日志文件"""
    data = defaultdict(lambda: {
        'name': '',
        'testerId': '',
        'circles': {},
        'logs': []
    })
    
    with open(log_file_path, 'r', encoding='utf-8') as f:
        for line in f:
            parsed = parse_log_line(line)
            if parsed:
                tester_id = parsed['testerId']
                name = parsed['name']
                cross_count = parsed['crossCount']
                
                # 初始化
                if not data[tester_id]['name']:
                    data[tester_id]['name'] = name
                    data[tester_id]['testerId'] = tester_id
                
                # 记录每一圈的信息
                circle_key = f'第{cross_count}圈'
                if circle_key not in data[tester_id]['circles']:
                    data[tester_id]['circles'][circle_key] = {
                        'score': parsed['score'],
                        'lastScore': parsed['lastScore'],
                        'crossTime': parsed['crossTime']
                    }
                
                # 记录日志
                data[tester_id]['logs'].append(parsed['raw_line'])
    
    return data

def generate_table(data, output_csv=None, output_md=None):
    """生成统计表格"""
    # 准备CSV数据
    csv_rows = []
    
    # 表头
    headers = ['name', 'id', '第一圈（crossCount=1）', '第二圈', '第三圈', '第四圈', '日志信息']
    csv_rows.append(headers)
    
    # 按testerId排序
    sorted_items = sorted(data.items(), key=lambda x: int(x[0]))
    
    for tester_id, info in sorted_items:
        # 格式化日志信息：显示所有日志，用换行符分隔
        log_info = '\n'.join(info['logs']) if info['logs'] else ''
        # 如果日志太长，可以截断并添加省略号
        if len(log_info) > 500:
            log_info = '\n'.join(info['logs'][:2]) + '\n... (共{}条日志)'.format(len(info['logs']))
        
        row = [
            info['name'],
            info['testerId'],
            info['circles'].get('第1圈', {}).get('score', ''),
            info['circles'].get('第2圈', {}).get('score', ''),
            info['circles'].get('第3圈', {}).get('score', ''),
            info['circles'].get('第4圈', {}).get('score', ''),
            log_info
        ]
        csv_rows.append(row)
    
    # 保存CSV
    if output_csv:
        with open(output_csv, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(csv_rows)
        print(f"✅ CSV表格已保存: {output_csv}")
    
    # 生成Markdown表格
    if output_md:
        md_content = "# 长跑统计表格\n\n"
        md_content += "| " + " | ".join(headers) + " |\n"
        md_content += "| " + " | ".join(['---'] * len(headers)) + " |\n"
        
        for tester_id, info in sorted_items:
            row = [
                info['name'],
                info['testerId'],
                info['circles'].get('第1圈', {}).get('score', '-'),
                info['circles'].get('第2圈', {}).get('score', '-'),
                info['circles'].get('第3圈', {}).get('score', '-'),
                info['circles'].get('第4圈', {}).get('score', '-'),
                f"共{len(info['logs'])}条日志" if info['logs'] else '-'
            ]
            md_content += "| " + " | ".join(str(cell) for cell in row) + " |\n"
        
        with open(output_md, 'w', encoding='utf-8') as f:
            f.write(md_content)
        print(f"✅ Markdown表格已保存: {output_md}")
    
    # 打印到控制台
    print("\n" + "="*100)
    print("统计表格预览:")
    print("="*100)
    print(f"{'name':<10} {'id':<15} {'第一圈':<12} {'第二圈':<12} {'第三圈':<12} {'第四圈':<12} {'日志数':<10}")
    print("-"*100)
    
    for tester_id, info in sorted_items:
        circle_1 = info['circles'].get('第1圈', {}).get('score', '-')
        circle_2 = info['circles'].get('第2圈', {}).get('score', '-')
        circle_3 = info['circles'].get('第3圈', {}).get('score', '-')
        circle_4 = info['circles'].get('第4圈', {}).get('score', '-')
        log_count = len(info['logs'])
        
        print(f"{info['name']:<10} {info['testerId']:<15} {circle_1:<12} {circle_2:<12} {circle_3:<12} {circle_4:<12} {log_count:<10}")
    
    print("="*100)
    print(f"\n总计: {len(data)} 人")

def main():
    # 日志文件路径
    log_file = Path('/Users/sonic/Downloads/result2.log')
    
    if not log_file.exists():
        print(f"❌ 文件不存在: {log_file}")
        return
    
    print(f"📖 正在解析日志文件: {log_file}")
    
    # 解析日志
    data = parse_log_file(log_file)
    
    # 输出目录
    output_dir = Path(__file__).parent.parent / 'docs'
    output_dir.mkdir(exist_ok=True)
    
    # 生成表格
    csv_file = output_dir / 'result2_statistics.csv'
    md_file = output_dir / 'result2_statistics.md'
    
    generate_table(data, output_csv=csv_file, output_md=md_file)

if __name__ == '__main__':
    main()

