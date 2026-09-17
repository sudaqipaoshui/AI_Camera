#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志分析工具
功能：
1. 提取日志信息，支持指定时间段
2. 统计并生成CSV
3. 生成图表
"""

import re
import csv
import argparse
from datetime import datetime
from collections import defaultdict
from pathlib import Path
# 尝试导入matplotlib（可选）
HAS_MATPLOTLIB = False
try:
    # 先尝试导入numpy，如果版本不兼容，先降级处理提示
    import numpy as np
    # 检查numpy版本
    if hasattr(np, '__version__'):
        np_version = np.__version__.split('.')[0]
        if int(np_version) >= 2:
            # numpy 2.x 可能与旧版matplotlib不兼容
            # 尝试导入matplotlib，如果失败会给出提示
            pass
    
    import matplotlib
    matplotlib.use('Agg')  # 使用非交互式后端，避免GUI依赖
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np
    
    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans', 'STHeiti']
    plt.rcParams['axes.unicode_minus'] = False
    HAS_MATPLOTLIB = True
except Exception as e:
    HAS_MATPLOTLIB = False
    # 静默失败，在generate_charts中会提示

def parse_timestamp(line):
    """解析日志行的时间戳"""
    # 格式: 2025-11-12 18:08:39.827
    pattern = r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})'
    match = re.search(pattern, line)
    if match:
        try:
            return datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S.%f')
        except:
            return None
    return None

def parse_circle_data(line):
    """解析长跑圈数数据"""
    # 匹配格式: testerId=1998863780, name=49, crossTime=1762942487052, crossCount=1, score=00:34, lastScore=00:00
    pattern = r'testerId=(\d+),\s*name=([^,]+),\s*startTime=\d+,\s*crossTime=(\d+),\s*crossCount=(\d+),\s*score=([^,]+),\s*lastScore=([^\s,]+)'
    match = re.search(pattern, line)
    
    if match:
        return {
            'testerId': match.group(1),
            'name': match.group(2),
            'crossTime': int(match.group(3)),
            'crossCount': int(match.group(4)),
            'score': match.group(5),
            'lastScore': match.group(6),
            'timestamp': parse_timestamp(line),
            'raw_line': line.strip()
        }
    return None

def filter_by_time_range(lines, start_time=None, end_time=None):
    """根据时间段过滤日志"""
    if not start_time and not end_time:
        return lines
    
    filtered = []
    skipped_before = 0
    skipped_after = 0
    included = 0
    
    for line in lines:
        timestamp = parse_timestamp(line)
        if timestamp:
            if start_time and timestamp < start_time:
                skipped_before += 1
                continue
            if end_time and timestamp > end_time:
                skipped_after += 1
                continue
            included += 1
        filtered.append(line)
    
    if start_time or end_time:
        print(f"📅 时间段过滤详情:")
        if start_time:
            print(f"   开始时间: {start_time}")
        if end_time:
            print(f"   结束时间: {end_time}")
        print(f"   过滤前日志行数: {len(lines)}")
        print(f"   过滤后日志行数: {len(filtered)}")
        print(f"   包含的日志行数: {included}")
        print(f"   跳过（开始时间之前）: {skipped_before}")
        print(f"   跳过（结束时间之后）: {skipped_after}")
    
    return filtered

def parse_log_file(log_file_path, start_time=None, end_time=None):
    """解析日志文件"""
    data = defaultdict(lambda: {
        'name': '',
        'testerId': '',
        'circles': {},
        'logs': [],
        'timestamps': []
    })
    
    with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # 过滤时间段
    if start_time or end_time:
        lines = filter_by_time_range(lines, start_time, end_time)
        print(f"📅 时间段过滤: {start_time} ~ {end_time}")
        print(f"   过滤后日志行数: {len(lines)}")
    
    for line in lines:
        parsed = parse_circle_data(line)
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
                    'crossTime': parsed['crossTime'],
                    'timestamp': parsed['timestamp']
                }
            
            # 记录日志和时间戳
            data[tester_id]['logs'].append(parsed['raw_line'])
            if parsed['timestamp']:
                data[tester_id]['timestamps'].append(parsed['timestamp'])
    
    return data

def generate_csv(data, output_csv, expected_circles=4):
    """生成CSV统计表格"""
    # 根据expected_circles动态生成表头
    headers = ['name', 'id']
    for i in range(1, expected_circles + 1):
        if i == 1:
            headers.append(f'第一圈（crossCount=1）')
        else:
            headers.append(f'第{i}圈')
    headers.extend(['日志数量', '日志信息'])
    csv_rows = [headers]
    
    # 按testerId排序
    sorted_items = sorted(data.items(), key=lambda x: int(x[0]))
    
    for tester_id, info in sorted_items:
        log_info = '\n'.join(info['logs'][:3]) if info['logs'] else ''
        if len(log_info) > 500:
            log_info = '\n'.join(info['logs'][:2]) + '\n... (共{}条日志)'.format(len(info['logs']))
        
        row = [info['name'], info['testerId']]
        # 根据expected_circles动态添加圈数数据
        for i in range(1, expected_circles + 1):
            row.append(info['circles'].get(f'第{i}圈', {}).get('score', ''))
        row.extend([len(info['logs']), log_info])
        csv_rows.append(row)
    
    # 确保输出目录存在（按日期）
    output_csv = Path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    
    # 保存CSV
    with open(output_csv, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(csv_rows)
    
    print(f"✅ CSV表格已保存: {output_csv}")
    return csv_rows

def parse_face_recognition_status(log_file_path):
    """解析日志中的人脸识别状态"""
    face_recognition_data = {}
    recordid_to_testerid = {}  # recordId到testerId的映射
    
    if not log_file_path.exists():
        return face_recognition_data
    
    try:
        # 第一遍：建立recordId到testerId的映射（从多个来源）
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # 从addCircle中提取recordId和testerId的对应关系
                match = re.search(r'addCircle.*?recordId=([^,]+).*?testerId=(\d+)', line)
                if match:
                    record_id = match.group(1).strip()
                    tester_id = match.group(2)
                    if record_id not in recordid_to_testerid:
                        recordid_to_testerid[record_id] = tester_id
                
                # 从addVideoToSportItem中提取recordId和testerId的对应关系
                match = re.search(r'addVideoToSportItem.*?recordId=([^,]+).*?testerId=(\d+)', line)
                if match:
                    record_id = match.group(1).strip()
                    tester_id = match.group(2)
                    if record_id not in recordid_to_testerid:
                        recordid_to_testerid[record_id] = tester_id
                
                # 从onSportStart中提取recordId和testerId的对应关系
                match = re.search(r'onSportStart.*?recordId=([^,]+).*?testerId=(\d+)', line)
                if match:
                    record_id = match.group(1).strip()
                    tester_id = match.group(2)
                    if record_id not in recordid_to_testerid:
                        recordid_to_testerid[record_id] = tester_id
        
        # 第二遍：解析人脸识别状态，并使用recordId关联testerId
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # 匹配格式: testerListToSportList recordId=..., name=57, status=FACE_RECOGNITED
                pattern = r'testerListToSportList.*?recordId=([^,]+).*?name=(\d+),\s*status=(\w+)'
                match = re.search(pattern, line)
                if match:
                    record_id = match.group(1).strip()
                    name = match.group(2)
                    status = match.group(3)
                    # 通过recordId查找testerId
                    tester_id = recordid_to_testerid.get(record_id, None)
                    if name not in face_recognition_data:
                        face_recognition_data[name] = []
                    face_recognition_data[name].append({
                        'status': status,
                        'timestamp': parse_timestamp(line),
                        'testerId': tester_id
                    })
                
                # 也从confirmTester和addCircle中提取人员信息（包括中文名字）
                # confirmTester格式: confirmTester ip=..., testerId=1998864602, name=邓
                confirm_pattern = r'confirmTester.*?testerId=(\d+).*?name=([^,\s]+)'
                confirm_match = re.search(confirm_pattern, line)
                if confirm_match:
                    tester_id = confirm_match.group(1)
                    name = confirm_match.group(2).strip()
                    # 如果name是数字，添加到face_recognition_data
                    if name.isdigit():
                        if name not in face_recognition_data:
                            face_recognition_data[name] = []
                        face_recognition_data[name].append({
                            'status': 'CONFIRMED',
                            'timestamp': parse_timestamp(line),
                            'testerId': tester_id
                        })
                
                # addCircle格式: addCircle ... testerId=1998864602, name=邓
                addcircle_pattern = r'addCircle.*?testerId=(\d+).*?name=([^,]+)'
                addcircle_match = re.search(addcircle_pattern, line)
                if addcircle_match:
                    tester_id = addcircle_match.group(1)
                    name = addcircle_match.group(2).strip()
                    # 如果name是数字，添加到face_recognition_data
                    if name.isdigit():
                        if name not in face_recognition_data:
                            face_recognition_data[name] = []
                        face_recognition_data[name].append({
                            'status': 'CIRCLE_COMPLETED',
                            'timestamp': parse_timestamp(line),
                            'testerId': tester_id
                    })
    except Exception as e:
        print(f"⚠️  读取人脸识别状态失败: {e}")
    
    return face_recognition_data

def generate_charts(data, output_dir, log_file_path=None, expected_circles=4, timestamp=None, start_time=None, end_time=None):
    """生成图表
    
    Args:
        data: 解析后的日志数据（已经过时间过滤）
        output_dir: 输出目录
        log_file_path: 日志文件路径（可选）
        expected_circles: 期望完成的圈数，默认4圈
        timestamp: 时间戳字符串（格式：YYYY-MM-DD_HH-MM-SS），用于文件名（Windows 兼容，不包含冒号和空格）
        start_time: 开始时间（用于时间过滤，如果提供则只统计在时间范围内的人员）
        end_time: 结束时间（用于时间过滤，如果提供则只统计在时间范围内的人员）
    """
    # 确保 timestamp 不包含 Windows 不允许的字符（冒号）
    # 格式：YYYY-MM-DD HH_MM_SS（日期和时间之间有空格，冒号替换为下划线）
    if timestamp:
        original_timestamp = timestamp
        # 替换冒号为下划线（保留日期和时间之间的空格，Windows 文件名兼容）
        timestamp = timestamp.replace(':', '_')
        # 移除微秒部分（如果有）
        if '.' in timestamp:
            parts = timestamp.split('.')
            timestamp = parts[0]  # 只保留日期和时间部分，去掉微秒
        # print(f"🔧 清理后的时间戳: {timestamp} (原始: {original_timestamp})")  # 注释掉调试信息
    if not HAS_MATPLOTLIB:
        print("⚠️  跳过图表生成（matplotlib不可用）")
        print("   提示: 如果遇到numpy兼容性问题，请运行: pip install 'numpy<2'")
        return
    
    output_dir = Path(output_dir)
    # 按日期创建子目录
    date_str = datetime.now().strftime("%Y%m%d")
    output_dir = output_dir / date_str
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. 圈数完成情况统计（基于人脸识别的人员）
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # 获取所有人脸识别到的人员（包括数字编号和中文名字），并保存testerId信息用于排序
    # 如果提供了时间范围，只统计在时间范围内的人员
    all_recognized_names = []
    all_tester_ids_with_names = {}
    name_to_testerid_map = {}  # name到testerId的映射，用于排序
    
    if log_file_path:
        # 如果提供了时间范围，只从过滤后的日志中提取人员
        if start_time or end_time:
            # 时间过滤模式：只统计在时间范围内的人员
            # 从 data 中获取所有人员（这些人员已经在时间范围内）
            all_tester_ids_in_range = set(data.keys())
            
            # 从 data 中获取人员信息
            for tester_id, info in data.items():
                all_tester_ids_in_range.add(tester_id)
                if info['name']:
                    all_tester_ids_with_names[tester_id] = info['name']
                    if info['name'] not in name_to_testerid_map:
                        name_to_testerid_map[info['name']] = tester_id
            
            # 时间过滤模式：以该时间段内的 testerListToSportList 为主
            # 首先从时间范围内的 testerListToSportList 提取人员
            try:
                # 首先建立 recordId 到 testerId 的映射（从整个日志文件）
                recordid_to_testerid = {}
                with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        # 从addCircle中提取recordId和testerId的对应关系
                        match = re.search(r'addCircle.*?recordId=([^,]+).*?testerId=(\d+)', line)
                        if match:
                            record_id = match.group(1).strip()
                            tester_id = match.group(2)
                            if record_id not in recordid_to_testerid:
                                recordid_to_testerid[record_id] = tester_id
                        # 从addVideoToSportItem中提取recordId和testerId的对应关系
                        match = re.search(r'addVideoToSportItem.*?recordId=([^,]+).*?testerId=(\d+)', line)
                        if match:
                            record_id = match.group(1).strip()
                            tester_id = match.group(2)
                            if record_id not in recordid_to_testerid:
                                recordid_to_testerid[record_id] = tester_id
                        # 从onSportStart中提取recordId和testerId的对应关系
                        match = re.search(r'onSportStart.*?recordId=([^,]+).*?testerId=(\d+)', line)
                        if match:
                            record_id = match.group(1).strip()
                            tester_id = match.group(2)
                            if record_id not in recordid_to_testerid:
                                recordid_to_testerid[record_id] = tester_id
                
                # 从时间范围内的 testerListToSportList 提取人员（只统计时间范围内的人员）
                testerlist_tester_ids = set()  # 在时间范围内的 testerListToSportList 中的人员
                with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        # 检查时间戳，只处理时间范围内的记录
                        line_timestamp = parse_timestamp(line)
                        if line_timestamp and start_time <= line_timestamp <= end_time:
                            # 匹配格式: testerListToSportList recordId=..., name=..., status=...
                            match = re.search(r'testerListToSportList.*?recordId=([^,]+).*?name=([^,]+)', line)
                            if match:
                                record_id = match.group(1).strip()
                                name = match.group(2).strip()
                                # 通过 recordId 查找 testerId
                                tester_id = recordid_to_testerid.get(record_id)
                                if tester_id:
                                    testerlist_tester_ids.add(tester_id)
                                    all_tester_ids_in_range.add(tester_id)
                                    if tester_id not in all_tester_ids_with_names:
                                        all_tester_ids_with_names[tester_id] = name
                                    if name not in name_to_testerid_map:
                                        name_to_testerid_map[name] = tester_id
                                else:
                                    person_key = 'r:' + record_id
                                    testerlist_tester_ids.add(person_key)
                                    all_tester_ids_in_range.add(person_key)
                                    if person_key not in all_tester_ids_with_names:
                                        all_tester_ids_with_names[person_key] = name
                                    if name not in name_to_testerid_map:
                                        name_to_testerid_map[name] = person_key
                
                # 运动总人数以时间范围内的 testerListToSportList 为准（仅统计姓名唯一出现的）
                # 并补充有圈数数据的人员（可能不在列表中但有成绩，避免漏计）
                all_tester_ids_in_range = testerlist_tester_ids.copy()
                for tester_id in data.keys():
                    all_tester_ids_in_range.add(tester_id)
            except Exception as e:
                print(f"⚠️  提取 testerListToSportList 时出错: {e}")
                import traceback
                traceback.print_exc()
            
            # 使用在时间范围内的人员（支持 testerId 与 无 testerId 时的 recordId 标识 r:xxx）
            def _sort_person_key(x):
                if x.isdigit():
                    return (0, int(x))
                return (1, x)
            all_recognized_names = [all_tester_ids_with_names.get(tid, str(tid)) for tid in sorted(all_tester_ids_in_range, key=_sort_person_key)]
        else:
            # 无时间过滤模式：从整个日志文件中提取所有人员（原有逻辑）
            # 从testerListToSportList获取数字编号
            face_recognition_data = parse_face_recognition_status(log_file_path)
            if face_recognition_data:
                all_recognized_names = sorted(face_recognition_data.keys(), key=lambda x: int(x) if x.isdigit() else 0)
            
            # 从addCircle和confirmTester获取所有人员（包括中文名字）
            try:
                with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        # 从addCircle中提取
                        match = re.search(r'addCircle.*?testerId=(\d+).*?name=([^,]+)', line)
                        if match:
                            tid = match.group(1)
                            name = match.group(2).strip()
                            if tid not in all_tester_ids_with_names:
                                all_tester_ids_with_names[tid] = name
                            # 保存name到testerId的映射
                            if name not in name_to_testerid_map:
                                name_to_testerid_map[name] = tid
                        # 从confirmTester中提取
                        match = re.search(r'confirmTester.*?testerId=(\d+).*?name=([^,]+)', line)
                        if match:
                            tid = match.group(1)
                            name = match.group(2).strip()
                            if tid not in all_tester_ids_with_names:
                                all_tester_ids_with_names[tid] = name
                            # 保存name到testerId的映射（如果还没有）
                            if name not in name_to_testerid_map:
                                name_to_testerid_map[name] = tid
            except:
                pass
            
            # 合并所有人员：数字编号 + 中文名字
            # 数字编号已经在all_recognized_names中
            # 添加中文名字的人员（如果不在数字编号中）
            for tid, name in all_tester_ids_with_names.items():
                if not name.isdigit() and name not in all_recognized_names:
                    all_recognized_names.append(name)
                    if name not in name_to_testerid_map:
                        name_to_testerid_map[name] = tid
    
    # 如果没有人脸识别数据，使用成绩数据中的人员
    if not all_recognized_names:
        all_recognized_names = [info['name'] for info in sorted(data.values(), key=lambda x: int(x['testerId']))]
        for info in data.values():
            if info['name'] not in name_to_testerid_map:
                name_to_testerid_map[info['name']] = info['testerId']
    
    # 从data中补充name到testerId的映射（用于有成绩数据的人员，包括数字编号）
    for info in data.values():
        if info['name'] not in name_to_testerid_map:
            name_to_testerid_map[info['name']] = info['testerId']
    
    # 从face_recognition_data中补充testerId（通过recordId关联）
    if log_file_path:
        face_recognition_data = parse_face_recognition_status(log_file_path)
        for name, records in face_recognition_data.items():
            if name not in name_to_testerid_map:
                # 查找有testerId的记录
                for record in records:
                    if record.get('testerId'):
                        name_to_testerid_map[name] = record['testerId']
                        break
    
    # 按照testerId排序所有人员
    # 构建(name, testerId)元组列表用于排序
    name_tid_pairs = []
    for name in all_recognized_names:
        tid = name_to_testerid_map.get(name, "0")
        name_tid_pairs.append((name, tid))
    
    # 按照testerId排序（将testerId转换为整数进行排序）
    name_tid_pairs.sort(key=lambda x: int(x[1]) if x[1] and x[1].isdigit() else 0)
    all_recognized_names = [name for name, tid in name_tid_pairs]
    
    # 统计每个人的完成圈数（包括0圈）
    circle_counts = defaultdict(int)
    name_to_info_map = {info['name']: info for info in data.values()}
    
    for name in all_recognized_names:
        if name in name_to_info_map:
            # 有成绩数据，统计完成的圈数
            info = name_to_info_map[name]
            max_circle = max([int(k[1]) for k in info['circles'].keys()] + [0])
            circle_counts[max_circle] += 1
        else:
            # 没有成绩数据，计为0圈
            circle_counts[0] += 1
    
    # 确保0到expected_circles圈都有数据（即使为0）
    for circle_num in range(0, expected_circles + 1):
        if circle_num not in circle_counts:
            circle_counts[circle_num] = 0
    
    circles = sorted(circle_counts.keys())
    counts = [circle_counts[c] for c in circles]
    labels = [f'{c}圈' for c in circles]
    
    ax.bar(labels, counts, color='skyblue', edgecolor='navy', alpha=0.7)
    ax.set_xlabel('完成圈数', fontsize=12)
    ax.set_ylabel('人数', fontsize=12)
    ax.set_title('圈数完成情况统计', fontsize=14, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)
    
    # 添加数值标签
    for i, v in enumerate(counts):
        ax.text(i, v + 0.1, str(v), ha='center', va='bottom')
    
    plt.tight_layout()
    # 生成带时间戳的文件名（圈数完成情况统计图）
    if timestamp:
        chart1_filename = f'circle_completion_stats_{timestamp}.png'
        # print(f"🔧 [第一个图表] 使用时间戳: {timestamp}, 文件名: {chart1_filename}")  # 注释掉调试信息
    else:
        chart1_filename = 'circle_completion_stats.png'
    chart1_path = output_dir / chart1_filename
    plt.savefig(chart1_path, dpi=300, bbox_inches='tight')
    print(f"✅ 圈数完成情况统计图已保存: {chart1_path}")
    plt.close()
    
    # 2. 收集每个人的所有圈数数据（用于分组柱状图）
    people_data = {}
    for tester_id, info in sorted(data.items(), key=lambda x: int(x[0])):
        person_name = f"{info['name']}({info['testerId']})"
        circle_times = []
        circle_labels = []
        
        for circle_num in range(1, expected_circles + 1):
            circle_key = f'第{circle_num}圈'
            circle_data = info['circles'].get(circle_key, {})
            if circle_data.get('score'):
                time_str = circle_data['score']
                try:
                    parts = time_str.split(':')
                    if len(parts) == 2:
                        minutes = int(parts[0])
                        seconds = int(parts[1])
                        total_seconds = minutes * 60 + seconds
                        circle_times.append(total_seconds)
                        circle_labels.append(circle_num)
                except:
                    pass
        
        if len(circle_times) > 0:
            people_data[person_name] = {
                'times': circle_times,
                'circles': circle_labels,
                'name': info['name'],
                'testerId': tester_id
            }
    
    # 3. 每个人在不同圈数的成绩对比（分组柱状图）
    fig, ax = plt.subplots(figsize=(24, 12))
    
    # 获取人脸识别状态数据（如果可用）- 这决定了横坐标的所有人员
    face_status_info = {}
    all_recognized_names = []  # 所有人脸识别到的人员（作为横坐标基准）
    all_tester_ids_with_names_chart = {}
    
    if log_file_path:
        # 如果提供了时间范围，只从过滤后的日志中提取人员
        if start_time or end_time:
            # 时间过滤模式：以该时间段内的 testerListToSportList 为主（与主统计逻辑保持一致）
            all_tester_ids_in_range_chart = set()
            
            try:
                # 首先建立 recordId 到 testerId 的映射（从整个日志文件）
                recordid_to_testerid = {}
                with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        # 从addCircle中提取recordId和testerId的对应关系
                        match = re.search(r'addCircle.*?recordId=([^,]+).*?testerId=(\d+)', line)
                        if match:
                            record_id = match.group(1).strip()
                            tester_id = match.group(2)
                            if record_id not in recordid_to_testerid:
                                recordid_to_testerid[record_id] = tester_id
                        # 从addVideoToSportItem中提取recordId和testerId的对应关系
                        match = re.search(r'addVideoToSportItem.*?recordId=([^,]+).*?testerId=(\d+)', line)
                        if match:
                            record_id = match.group(1).strip()
                            tester_id = match.group(2)
                            if record_id not in recordid_to_testerid:
                                recordid_to_testerid[record_id] = tester_id
                        # 从onSportStart中提取recordId和testerId的对应关系
                        match = re.search(r'onSportStart.*?recordId=([^,]+).*?testerId=(\d+)', line)
                        if match:
                            record_id = match.group(1).strip()
                            tester_id = match.group(2)
                            if record_id not in recordid_to_testerid:
                                recordid_to_testerid[record_id] = tester_id
                
                # 与主统计一致：只保留在 testerListToSportList 中姓名仅出现一次的人员
                name_count_chart = defaultdict(int)
                with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line_timestamp = parse_timestamp(line)
                        if line_timestamp and start_time <= line_timestamp <= end_time:
                            match = re.search(r'testerListToSportList.*?recordId=([^,]+).*?name=([^,]+)', line)
                            if match:
                                name_count_chart[match.group(2).strip()] += 1
                valid_names_chart = {name for name, cnt in name_count_chart.items() if cnt == 1}
                testerlist_tester_ids_chart = set()
                with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line_timestamp = parse_timestamp(line)
                        if line_timestamp and start_time <= line_timestamp <= end_time:
                            match = re.search(r'testerListToSportList.*?recordId=([^,]+).*?name=([^,]+)', line)
                            if match:
                                record_id = match.group(1).strip()
                                name = match.group(2).strip()
                                if name not in valid_names_chart:
                                    continue
                                tester_id = recordid_to_testerid.get(record_id)
                                if tester_id:
                                    testerlist_tester_ids_chart.add(tester_id)
                                    all_tester_ids_in_range_chart.add(tester_id)
                                    if tester_id not in all_tester_ids_with_names_chart:
                                        all_tester_ids_with_names_chart[tester_id] = name
                                else:
                                    person_key = 'r:' + record_id
                                    testerlist_tester_ids_chart.add(person_key)
                                    all_tester_ids_in_range_chart.add(person_key)
                                    if person_key not in all_tester_ids_with_names_chart:
                                        all_tester_ids_with_names_chart[person_key] = name
                
                # 只统计在时间范围内的 testerListToSportList 中的人员
                # 不再统计那些只在时间范围内有 confirmTester 但不在 testerListToSportList 中的人员
                # 但保留有圈数数据的人员（即使不在 testerListToSportList 中，也可能有圈数数据）
                all_tester_ids_in_range_chart = testerlist_tester_ids_chart.copy()
                # 添加有圈数数据的人员（这些人员可能不在 testerListToSportList 中，但有实际成绩）
                for tester_id in data.keys():
                    all_tester_ids_in_range_chart.add(tester_id)
                    # 从 data 中获取人员信息
                    if tester_id in data and data[tester_id].get('name'):
                        if tester_id not in all_tester_ids_with_names_chart:
                            all_tester_ids_with_names_chart[tester_id] = data[tester_id]['name']
            except:
                pass
            
            # 使用在时间范围内的人员（与主统计逻辑保持一致，支持 r: 前缀 key）
            all_recognized_names = [all_tester_ids_with_names_chart.get(tid, str(tid)) for tid in sorted(all_tester_ids_in_range_chart, key=_sort_person_key)]
        else:
            # 无时间过滤模式：从整个日志文件中提取所有人员（原有逻辑）
            # 从testerListToSportList获取数字编号
            face_recognition_data = parse_face_recognition_status(log_file_path)
            if face_recognition_data:
                # 按name排序，获取所有人
                all_recognized_names = sorted(face_recognition_data.keys(), key=lambda x: int(x) if x.isdigit() else 0)
                for name, records in face_recognition_data.items():
                    # 获取最新的状态
                    if records:
                        latest_status = records[-1]['status']
                        face_status_info[name] = latest_status
            
            # 从addCircle和confirmTester获取所有人员（包括中文名字）
            try:
                with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        # 从addCircle中提取
                        match = re.search(r'addCircle.*?testerId=(\d+).*?name=([^,]+)', line)
                        if match:
                            tid = match.group(1)
                            name = match.group(2).strip()
                            if tid not in all_tester_ids_with_names_chart:
                                all_tester_ids_with_names_chart[tid] = name
                        # 从confirmTester中提取
                        match = re.search(r'confirmTester.*?testerId=(\d+).*?name=([^,]+)', line)
                        if match:
                            tid = match.group(1)
                            name = match.group(2).strip()
                            if tid not in all_tester_ids_with_names_chart:
                                all_tester_ids_with_names_chart[tid] = name
            except:
                pass
            
            # 合并所有人员：数字编号 + 中文名字
            for tid, name in all_tester_ids_with_names_chart.items():
                if not name.isdigit() and name not in all_recognized_names:
                    all_recognized_names.append(name)
    
    # 如果没有人脸识别数据，使用成绩数据中的人员
    if not all_recognized_names:
        all_recognized_names = [info['name'] for info in sorted(data.values(), key=lambda x: int(x['testerId']))]
    
    # 构建完整的人员列表（包含testerId信息）
    # 首先从日志中提取name到testerId的映射（用于没有成绩数据的人，包括中文名字和数字编号）
    name_to_testerid_from_log = {}
    if log_file_path:
        try:
            # 如果提供了时间范围，只从过滤后的日志中提取
            if start_time or end_time:
                with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    filtered_lines = filter_by_time_range(f.readlines(), start_time, end_time)
                    for line in filtered_lines:
                        # 从addCircle日志中提取name和testerId的对应关系（包括数字和中文名字）
                        pattern = r'(addCircle|confirmTester).*?testerId=(\d+).*?name=([^,]+)'
                        match = re.search(pattern, line)
                        if match:
                            tester_id = match.group(2)
                            name = match.group(3).strip()
                            # 如果name不在映射中，或者需要更新（优先使用addCircle的数据）
                            if name not in name_to_testerid_from_log or 'addCircle' in match.group(0):
                                name_to_testerid_from_log[name] = tester_id
            else:
                # 无时间过滤模式：从整个日志文件中提取
                with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        # 从addCircle日志中提取name和testerId的对应关系（包括数字和中文名字）
                        pattern = r'(addCircle|confirmTester).*?testerId=(\d+).*?name=([^,]+)'
                        match = re.search(pattern, line)
                        if match:
                            tester_id = match.group(2)
                            name = match.group(3).strip()
                            # 如果name不在映射中，或者需要更新（优先使用addCircle的数据）
                            if name not in name_to_testerid_from_log or 'addCircle' in match.group(0):
                                name_to_testerid_from_log[name] = tester_id
        except:
            pass
    
    # 从data中补充name到testerId的映射（用于有成绩数据的人员）
    for info in data.values():
        if info['name'] not in name_to_testerid_from_log:
            name_to_testerid_from_log[info['name']] = info['testerId']
    
    # 从face_recognition_data中补充testerId（通过recordId关联，用于没有addCircle/confirmTester记录的人员）
    if log_file_path:
        face_recognition_data = parse_face_recognition_status(log_file_path)
        for name, records in face_recognition_data.items():
            if name not in name_to_testerid_from_log:
                # 查找有testerId的记录
                for record in records:
                    if record.get('testerId'):
                        name_to_testerid_from_log[name] = record['testerId']
                        break
    
    # 构建人员列表，包含(name, testerId, first_detection_time)元组，用于按检测时间排序
    person_list_with_info = []
    name_to_person_map = {info['name']: (info['name'], info['testerId']) for info in data.values()}
    name_to_first_time_chart = {}
    
    # 获取每个人的第一次检测时间
    # 优先使用confirmTester（实际确认时间），然后是addCircle（第一次完成圈数），最后是testerListToSportList
    if log_file_path:
        try:
            # 如果提供了时间范围，只从过滤后的日志中提取
            if start_time or end_time:
                with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    filtered_lines = filter_by_time_range(f.readlines(), start_time, end_time)
                
                # 第一遍：从confirmTester获取首次检测时间（最准确）
                for line in filtered_lines:
                    match = re.search(r'confirmTester.*?name=([^,\s]+)', line)
                    if match:
                        name = match.group(1).strip()
                        line_timestamp = parse_timestamp(line)  # 使用 line_timestamp 避免覆盖函数参数
                        if line_timestamp and (name not in name_to_first_time_chart or line_timestamp < name_to_first_time_chart[name]):
                            name_to_first_time_chart[name] = line_timestamp
                
                # 第二遍：从addCircle获取第一次完成圈数的时间（只添加没有confirmTester记录的人员）
                for line in filtered_lines:
                    match = re.search(r'addCircle.*?name=([^,]+).*?crossCount=1', line)
                    if match:
                        name = match.group(1).strip()
                        if name not in name_to_first_time_chart:  # 只添加没有confirmTester记录的人员
                            line_timestamp = parse_timestamp(line)  # 使用 line_timestamp 避免覆盖函数参数
                            if line_timestamp:
                                name_to_first_time_chart[name] = line_timestamp
                
                # 第三遍：从testerListToSportList获取（只添加没有前面记录的人员）
                for line in filtered_lines:
                    match = re.search(r'testerListToSportList.*?name=([^,]+)', line)
                    if match:
                        name = match.group(1).strip()
                        if name not in name_to_first_time_chart:  # 只添加没有前面记录的人员
                            line_timestamp = parse_timestamp(line)  # 使用 line_timestamp 避免覆盖函数参数
                            if line_timestamp:
                                name_to_first_time_chart[name] = line_timestamp
            else:
                # 无时间过滤模式：从整个日志文件中提取
                # 第一遍：从confirmTester获取首次检测时间（最准确）
                with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        match = re.search(r'confirmTester.*?name=([^,\s]+)', line)
                        if match:
                            name = match.group(1).strip()
                            line_timestamp = parse_timestamp(line)  # 使用 line_timestamp 避免覆盖函数参数
                            if line_timestamp and (name not in name_to_first_time_chart or line_timestamp < name_to_first_time_chart[name]):
                                name_to_first_time_chart[name] = line_timestamp
                
                # 第二遍：从addCircle获取第一次完成圈数的时间（只添加没有confirmTester记录的人员）
                with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        match = re.search(r'addCircle.*?name=([^,]+).*?crossCount=1', line)
                        if match:
                            name = match.group(1).strip()
                            if name not in name_to_first_time_chart:  # 只添加没有confirmTester记录的人员
                                line_timestamp = parse_timestamp(line)  # 使用 line_timestamp 避免覆盖函数参数
                                if line_timestamp:
                                    name_to_first_time_chart[name] = line_timestamp
                
                # 第三遍：从testerListToSportList获取（只添加没有前面记录的人员）
                with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        match = re.search(r'testerListToSportList.*?name=([^,]+)', line)
                        if match:
                            name = match.group(1).strip()
                            if name not in name_to_first_time_chart:  # 只添加没有前面记录的人员
                                line_timestamp = parse_timestamp(line)  # 使用 line_timestamp 避免覆盖函数参数
                                if line_timestamp:
                                    name_to_first_time_chart[name] = line_timestamp
        except:
            pass
    
    for name in all_recognized_names:
        # 优先从data中获取testerId（有成绩数据）
        if name in name_to_person_map:
            person_name, tester_id = name_to_person_map[name]
            first_time = name_to_first_time_chart.get(name, datetime.max)
            person_list_with_info.append((person_name, tester_id, first_time, f"{person_name}({tester_id})"))
        elif name in name_to_testerid_from_log:
            # 从日志中找到了testerId，但没有成绩数据
            tester_id = name_to_testerid_from_log[name]
            first_time = name_to_first_time_chart.get(name, datetime.max)
            person_list_with_info.append((name, tester_id, first_time, f"{name}({tester_id})"))
        else:
            # 如果只有人脸识别数据，没有成绩数据，使用name作为标识
            first_time = name_to_first_time_chart.get(name, datetime.max)
            person_list_with_info.append((name, "0", first_time, f"{name}(?)"))
    
    # 按照testerId排序
    person_list_with_info.sort(key=lambda x: int(x[1]) if x[1] and x[1].isdigit() else 0)
    
    # 提取排序后的显示名称
    all_person_list = [item[3] for item in person_list_with_info]
    
    # 准备数据 - 使用所有人作为横坐标
    x = np.arange(len(all_person_list))
    width = 0.2  # 柱状图宽度
    
    # 为每一圈准备数据（包含所有人员，没有成绩的为0）
    circle_data_list = [[] for _ in range(expected_circles)]  # expected_circles个圈的数据
    
    for person_label in all_person_list:
        # 从person_label中提取name（支持数字和中文名字）
        # 格式可能是: "56(1998874198)" 或 "邓(1998864602)" 或 "王老师(1998864600)"
        name_match = re.search(r'^([^(]+)\(', person_label)
        person_name = None
        
        if name_match:
            name = name_match.group(1).strip()
            # 在people_data中查找对应的数据
            for pn, pdata in people_data.items():
                if pdata['name'] == name:
                    person_name = pn
                    break
        
        if person_name and person_name in people_data:
            data_dict = people_data[person_name]
            for circle_num in range(1, expected_circles + 1):
                if circle_num in data_dict['circles']:
                    idx = data_dict['circles'].index(circle_num)
                    circle_data_list[circle_num - 1].append(data_dict['times'][idx])
                else:
                    circle_data_list[circle_num - 1].append(0)  # 无数据用0表示
        else:
            # 没有成绩数据的人，所有圈数都是0
            for circle_num in range(1, expected_circles + 1):
                circle_data_list[circle_num - 1].append(0)
    
    # 绘制分组柱状图
    colors_bar = ['lightcoral', 'lightblue', 'lightgreen', 'lightyellow', 'lightpink', 'lightcyan', 'lightgray']
    labels_bar = [f'第{i+1}圈' for i in range(expected_circles)]
    
    for i in range(expected_circles):
        bars = ax.bar(x + i * width, circle_data_list[i], width, 
                     label=labels_bar[i], color=colors_bar[i], 
                     edgecolor='navy', alpha=0.7)
        # 添加数值标签（只显示有成绩的）
        for j, bar in enumerate(bars):
            height = bar.get_height()
            if height > 0:
                minutes = int(height // 60)
                seconds = int(height % 60)
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{minutes:02d}:{seconds:02d}',
                       ha='center', va='bottom', fontsize=8, rotation=90)
            # 如果高度为0且该人员没有成绩数据，可以显示"无数据"（可选）
            # elif height == 0 and all_person_list[j] not in [pn for pn in people_data.keys()]:
            #     ax.text(bar.get_x() + bar.get_width()/2., 5,
            #            '无数据',
            #            ha='center', va='bottom', fontsize=5, color='gray', style='italic')
    
    ax.set_ylabel('用时（秒）', fontsize=16, fontweight='bold')
    ax.set_title('每个人在不同圈数的成绩对比（分组柱状图）', fontsize=18, fontweight='bold')
    ax.set_xticks(x + width * 1.5)
    
    # 构建横坐标标签（去掉状态标识，检查是否完整4圈）
    x_labels = []
    incomplete_person_indices = []  # 记录未完成expected_circles圈的人员索引
    
    for idx, person_label in enumerate(all_person_list):
        # 从person_label中提取name（格式: "49(3780)" 或 "42(?)" 或 "邓(1998864602)" 或 "王老师(1998864600)"）
        name_match = re.search(r'^([^(]+)\(', person_label)
        if name_match:
            name = name_match.group(1).strip()
            # 检查是否完成4圈
            person_name = None
            for pn, pdata in people_data.items():
                if pdata['name'] == name:
                    person_name = pn
                    break
            
            if person_name and person_name in people_data:
                data_dict = people_data[person_name]
                # 检查是否完成expected_circles圈
                if expected_circles not in data_dict['circles']:
                    # 未完成expected_circles圈，标记为"漏圈"
                    x_labels.append(f"{person_label}\n漏圈")
                    incomplete_person_indices.append(idx)
                else:
                    # 完成expected_circles圈，只显示姓名
                    x_labels.append(person_label)
            else:
                # 没有成绩数据，标记为"漏圈"
                x_labels.append(f"{person_label}\n漏圈")
                incomplete_person_indices.append(idx)
        else:
            # 没有匹配到name（可能是中文名字或其他格式），尝试直接匹配
            # 检查是否在people_data中
            person_name = None
            for pn, pdata in people_data.items():
                if pn == person_label or pdata['name'] in person_label:
                    person_name = pn
                    break
            
            if person_name and person_name in people_data:
                data_dict = people_data[person_name]
                if expected_circles not in data_dict['circles']:
                    x_labels.append(f"{person_label}\n漏圈")
                    incomplete_person_indices.append(idx)
                else:
                    x_labels.append(person_label)
            else:
                # 没有找到person_name，直接显示标签
                x_labels.append(person_label)
    
    ax.set_xticklabels(x_labels, rotation=45, ha='right', fontsize=12)
    
    # 高亮显示未完成expected_circles圈的人员标签
    for idx in incomplete_person_indices:
        label = ax.get_xticklabels()[idx]
        label.set_color('red')
        label.set_fontweight('bold')
    ax.legend(fontsize=14)
    ax.grid(axis='y', alpha=0.3)
    
    # 在图表底部显示完成数（没有漏圈的人数）
    total_people = len(all_person_list)
    # 计算完成expected_circles圈的人数（没有漏圈的人数，支持中文名字）
    completed_people = 0
    for person_label in all_person_list:
        name_match = re.search(r'^([^(]+)\(', person_label)
        if name_match:
            name = name_match.group(1).strip()
            person_name = None
            for pn, pdata in people_data.items():
                if pdata['name'] == name:
                    person_name = pn
                    break
            
            if person_name and person_name in people_data:
                data_dict = people_data[person_name]
                if expected_circles in data_dict['circles']:
                    completed_people += 1
    
    ax.text(0.5, -0.12, f'完成数: {completed_people}/{total_people}', 
           transform=ax.transAxes, ha='center', va='top',
           fontsize=16, fontweight='bold', 
           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # 添加Y轴时间标签
    y_ticks = ax.get_yticks()
    y_labels = []
    for tick in y_ticks:
        if tick >= 0:
            minutes = int(tick // 60)
            seconds = int(tick % 60)
            y_labels.append(f'{minutes:02d}:{seconds:02d}')
        else:
            y_labels.append('')
    ax.set_yticklabels(y_labels)
    
    plt.tight_layout(rect=[0, 0.05, 1, 0.98])  # 为底部总人数留出空间
    # 生成带时间戳的文件名
    if timestamp:
        chart_bar_filename = f'person_circle_relationship_bar_{timestamp}.png'
        # print(f"🔧 [第二个图表] 使用时间戳: {timestamp}, 文件名: {chart_bar_filename}")  # 注释掉调试信息
    else:
        chart_bar_filename = 'person_circle_relationship_bar.png'
    chart_bar_path = output_dir / chart_bar_filename
    plt.savefig(chart_bar_path, dpi=300, bbox_inches='tight')
    print(f"✅ 圈数-人关系柱状图已保存: {chart_bar_path}")
    plt.close()

def main():
    parser = argparse.ArgumentParser(description='日志分析工具')
    parser.add_argument('log_file', type=str, help='日志文件路径')
    parser.add_argument('--start-time', type=str, help='开始时间 (格式: 2025-11-12 18:08:39)')
    parser.add_argument('--end-time', type=str, help='结束时间 (格式: 2025-11-12 18:22:45)')
    parser.add_argument('--output-dir', type=str, default='allure-report/log_analysis', help='输出目录 (默认: allure-report/log_analysis)')
    parser.add_argument('--circles', '--r', type=int, default=4, dest='expected_circles', help='期望完成的圈数，默认4圈')
    
    args = parser.parse_args()
    
    # 解析时间参数
    start_time = None
    end_time = None
    if args.start_time:
        try:
            # 清理可能的引号和多余空格
            start_time_str = args.start_time.strip().strip('"').strip("'")
            start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S')
            print(f"✅ 开始时间: {start_time}")
        except ValueError as e:
            print(f"⚠️  开始时间格式错误: '{args.start_time}'")
            print(f"   期望格式: YYYY-MM-DD HH:MM:SS (例如: 2025-12-16 10:20:30)")
            print(f"   错误详情: {e}")
            print(f"   将不使用时间过滤")
        except Exception as e:
            print(f"⚠️  解析开始时间时出错: {e}")
            print(f"   将不使用时间过滤")
    if args.end_time:
        try:
            # 清理可能的引号和多余空格
            end_time_str = args.end_time.strip().strip('"').strip("'")
            end_time = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S')
            print(f"✅ 结束时间: {end_time}")
        except ValueError as e:
            print(f"⚠️  结束时间格式错误: '{args.end_time}'")
            print(f"   期望格式: YYYY-MM-DD HH:MM:SS (例如: 2025-12-16 10:36:10)")
            print(f"   错误详情: {e}")
            print(f"   将不使用时间过滤")
        except Exception as e:
            print(f"⚠️  解析结束时间时出错: {e}")
            print(f"   将不使用时间过滤")
    
    # 验证时间范围
    if start_time and end_time:
        if start_time >= end_time:
            print(f"⚠️  警告: 开始时间 ({start_time}) 不能晚于或等于结束时间 ({end_time})")
            print(f"   将不使用时间过滤")
            start_time = None
            end_time = None
        else:
            print(f"📅 时间过滤范围: {start_time} ~ {end_time}")
    elif start_time or end_time:
        print(f"⚠️  警告: 只提供了开始时间或结束时间之一，将不使用时间过滤")
        print(f"   提示: 需要同时提供 --start-time 和 --end-time 才会启用时间过滤")
        start_time = None
        end_time = None
    
    log_file = Path(args.log_file)
    if not log_file.exists():
        print(f"❌ 文件不存在: {log_file}")
        return
    
    print(f"📖 正在解析日志文件: {log_file}")
    
    # 解析日志
    data = parse_log_file(log_file, start_time, end_time)
    
    if not data:
        print("⚠️  未找到有效数据")
        return
    
    # 输出目录（按日期）
    base_output_dir = Path(args.output_dir)
    date_str = datetime.now().strftime("%Y%m%d")
    output_dir = base_output_dir / date_str
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 获取期望圈数参数
    expected_circles = args.expected_circles
    
    # 生成时间戳（用于图片文件名）
    # 如果提供了时间范围，使用 start_time 作为时间戳；否则使用当前时间
    # Windows 文件名不能包含冒号，所以将冒号替换为下划线
    # 格式：YYYY-MM-DD HH_MM_SS（日期和时间之间有空格，冒号替换为下划线）
    if start_time:
        # 使用 start_time 作为时间戳，格式：YYYY-MM-DD HH_MM_SS（Windows 兼容）
        timestamp_str = start_time.strftime('%Y-%m-%d %H_%M_%S')
        # print(f"🔧 生成的时间戳: {timestamp_str}")  # 注释掉调试信息
    else:
        # 使用当前时间作为时间戳
        timestamp_str = datetime.now().strftime('%Y-%m-%d %H_%M_%S')
        # print(f"🔧 生成的时间戳（当前时间）: {timestamp_str}")  # 注释掉调试信息
    
    # 生成CSV
    csv_file = output_dir / f'{log_file.stem}_statistics.csv'
    csv_rows = generate_csv(data, csv_file, expected_circles)
    
    # 生成图表（传入基础目录，函数内部会创建日期子目录）
    # 两个图表使用相同的时间戳，确保命名规则一致
    generate_charts(data, base_output_dir, log_file, expected_circles, timestamp=timestamp_str, start_time=start_time, end_time=end_time)
    
    # 如果指定了时间范围，只统计在时间范围内的人员
    # 否则统计整个日志文件中的所有人员
    if start_time or end_time:
        # 时间过滤模式：只统计在时间范围内的人员
        # 时间过滤模式：以该时间段内的 testerListToSportList 为主
        # 首先从时间范围内的 testerListToSportList 提取人员
        all_tester_ids_in_range = set()
        testerid_to_name = {}
        
        try:
            # 首先建立 recordId 到 testerId 的映射（从整个日志文件）
            recordid_to_testerid = {}
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    # 从addCircle中提取recordId和testerId的对应关系
                    match = re.search(r'addCircle.*?recordId=([^,]+).*?testerId=(\d+)', line)
                    if match:
                        record_id = match.group(1).strip()
                        tester_id = match.group(2)
                        if record_id not in recordid_to_testerid:
                            recordid_to_testerid[record_id] = tester_id
                    # 从addVideoToSportItem中提取recordId和testerId的对应关系
                    match = re.search(r'addVideoToSportItem.*?recordId=([^,]+).*?testerId=(\d+)', line)
                    if match:
                        record_id = match.group(1).strip()
                        tester_id = match.group(2)
                        if record_id not in recordid_to_testerid:
                            recordid_to_testerid[record_id] = tester_id
                    # 从onSportStart中提取recordId和testerId的对应关系
                    match = re.search(r'onSportStart.*?recordId=([^,]+).*?testerId=(\d+)', line)
                    if match:
                        record_id = match.group(1).strip()
                        tester_id = match.group(2)
                        if record_id not in recordid_to_testerid:
                            recordid_to_testerid[record_id] = tester_id
            
            # 从时间范围内的 testerListToSportList 提取人员（只统计时间范围内的人员）
            testerlist_tester_ids = set()  # 在时间范围内的 testerListToSportList 中的人员
            testerlist_count = 0
            testerlist_matched = 0
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    # 检查时间戳，只处理时间范围内的记录
                    line_timestamp = parse_timestamp(line)
                    if line_timestamp and start_time <= line_timestamp <= end_time:
                        # 匹配格式: testerListToSportList recordId=..., name=..., status=...
                        match = re.search(r'testerListToSportList.*?recordId=([^,]+).*?name=([^,]+)', line)
                        if match:
                            testerlist_count += 1
                            record_id = match.group(1).strip()
                            name = match.group(2).strip()
                            # 通过 recordId 查找 testerId（若日志无 testerId 则用 recordId 作为唯一标识）
                            tester_id = recordid_to_testerid.get(record_id)
                            if tester_id:
                                testerlist_matched += 1
                                testerlist_tester_ids.add(tester_id)
                                all_tester_ids_in_range.add(tester_id)
                                if tester_id not in testerid_to_name:
                                    testerid_to_name[tester_id] = name
                            else:
                                if name in testerid_to_name.values():
                                    continue
                                person_key = 'r:' + record_id
                                testerlist_tester_ids.add(person_key)
                                all_tester_ids_in_range.add(person_key)
                                if person_key not in testerid_to_name:
                                    testerid_to_name[person_key] = name
            
            # 只统计在时间范围内的 testerListToSportList 中的人员
            # 不再统计那些只在时间范围内有 confirmTester 但不在 testerListToSportList 中的人员
            # 但保留有圈数数据的人员（即使不在 testerListToSportList 中，也可能有圈数数据）
            all_tester_ids_in_range = testerlist_tester_ids.copy()
            # 添加有圈数数据的人员（这些人员可能不在 testerListToSportList 中，但有实际成绩）
            for tester_id in data.keys():
                all_tester_ids_in_range.add(tester_id)
                # 从 data 中获取人员信息
                if tester_id in data and data[tester_id].get('name'):
                    if tester_id not in testerid_to_name:
                        testerid_to_name[tester_id] = data[tester_id]['name']
            
            # 总是打印调试信息，即使 count 为 0
            print(f"   - 从 testerListToSportList 提取的记录数: {testerlist_count}")
            print(f"   - 能关联到 testerId 的记录数: {testerlist_matched}")
        except Exception as e:
            print(f"⚠️  提取 testerListToSportList 时出错: {e}")
            import traceback
            traceback.print_exc()
        
        # 统计总人数：以时间范围内的 testerListToSportList 为主
        # 1) 在时间范围内的 testerListToSportList 中的人员
        # 2) 在时间范围内有圈数数据的人员（即使不在 testerListToSportList 中，也可能有实际成绩）
        total_people = len(all_tester_ids_in_range)
        print(f"📊 时间过滤模式：以该时间段内的 testerListToSportList 为主")
        print(f"   在时间范围内的 testerListToSportList 中的人员数: {total_people}")
        print(f"   - 有圈数数据的人员: {len(data)}")
        print(f"   - 在 testerListToSportList 中但没有圈数数据的人员: {total_people - len(data)}")
    else:
        # 无时间过滤模式：统计整个日志文件中的所有人员（原有逻辑）
        # 获取所有人脸识别到的人员（包括没有完成圈数的）
        face_recognition_data = parse_face_recognition_status(log_file)
        all_recognized_names = []
        if face_recognition_data:
            all_recognized_names = sorted(face_recognition_data.keys(), key=lambda x: int(x) if x.isdigit() else 0)
        
        # 也从addCircle和confirmTester中提取所有人员（包括中文名字）
        all_tester_ids = set()
        testerid_to_name = {}
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    # 从addCircle中提取testerId和name
                    match = re.search(r'addCircle.*?testerId=(\d+).*?name=([^,]+)', line)
                    if match:
                        tid = match.group(1)
                        name = match.group(2).strip()
                        all_tester_ids.add(tid)
                        if tid not in testerid_to_name:
                            testerid_to_name[tid] = name
                    # 从confirmTester中提取testerId和name
                    match = re.search(r'confirmTester.*?testerId=(\d+).*?name=([^,]+)', line)
                    if match:
                        tid = match.group(1)
                        name = match.group(2).strip()
                        all_tester_ids.add(tid)
                        if tid not in testerid_to_name:
                            testerid_to_name[tid] = name
        except Exception as e:
            pass
        
        # 统计总人数：
        # 1. testerListToSportList中的数字编号人员
        # 2. addCircle/confirmTester中的testerId（包括中文名字的人员如"邓"和"王老师"）
        # 合并统计，确保包含所有人员
        
        # 从testerListToSportList获取的数字编号人员
        total_from_testerlist = len(all_recognized_names) if all_recognized_names else 0
        
        # 从addCircle/confirmTester获取的testerId人员（包括中文名字）
        total_from_addcircle = len(all_tester_ids)
        
        # 检查addCircle/confirmTester中的testerId对应的name是否是数字编号
        # 如果是数字编号，说明已经在testerListToSportList中统计了
        # 如果是中文名字（如"邓"、"王老师"），需要单独统计
        testerid_with_chinese_name = set()
        for tid in all_tester_ids:
            name = testerid_to_name.get(tid, '')
            # 如果name不是纯数字，说明是中文名字，需要单独统计
            if name and not name.isdigit():
                testerid_with_chinese_name.add(tid)
        
        # 统计总人数：
        # - testerListToSportList中的数字编号人员数（20个）
        # - 加上addCircle/confirmTester中中文名字的人员（如"邓"、"王老师"）
        # 注意：如果"王老师"对应数字编号56，它已经在testerListToSportList中，不应该重复计算
        # 但"邓"可能没有对应的数字编号，需要单独计算
        total_people = total_from_testerlist + len(testerid_with_chinese_name)
        
        # 确保至少包含data中的人员数（有成绩数据的人员）
        total_people = max(total_people, len(data))
    
    # 创建name到data的映射
    name_to_data = {info['name']: info for info in data.values()}
    
    # 打印统计摘要
    print("\n" + "="*80)
    print("统计摘要:")
    print("="*80)
    print(f"期望完成圈数: {expected_circles}圈")
    print(f"总人数: {total_people}")
    
    # 统计完成expected_circles圈的人数
    completed_circles_key = f'第{expected_circles}圈'
    completed_count = sum(1 for info in data.values() if completed_circles_key in info['circles'])
    print(f"完成{expected_circles}圈: {completed_count} 人")
    
    # 统计漏圈情况（从expected_circles-1圈开始，逐级递减）
    missing_stats = {}  # {漏圈数: 人数}
    for missing_count in range(1, expected_circles):
        completed_circle = expected_circles - missing_count
        next_circle = completed_circle + 1
        completed_key = f'第{completed_circle}圈'
        next_key = f'第{next_circle}圈'
        missing_people = sum(1 for info in data.values() 
                             if completed_key in info['circles'] and next_key not in info['circles'])
        missing_stats[missing_count] = missing_people
        print(f"漏{missing_count}圈: {missing_people} 人")
    
    # 统计完全没有成绩数据的人数
    missing_stats[expected_circles] = 0
    if total_people > len(data):
        missing_stats[expected_circles] = total_people - len(data)
        print(f"漏{expected_circles}圈: {missing_stats[expected_circles]} 人")
    
    # 计算漏圈率
    total_missing_circles = 0
    for missing_count, missing_people in missing_stats.items():
        total_missing_circles += missing_people * missing_count
    
    if total_people > 0:
        total_expected_circles = total_people * expected_circles
        missing_rate = (total_missing_circles / total_expected_circles) * 100 if total_expected_circles > 0 else 0
        print(f"\n漏圈率: {missing_rate:.2f}%")
        print(f"计算方式: 漏总圈数({total_missing_circles}) / (总人数({total_people}) × 期望圈数({expected_circles})) = {total_expected_circles}")
        print(f"漏总圈数: {total_missing_circles} 圈")
        print(f"总期望圈数: {total_expected_circles} 圈")
    else:
        print("\n⚠️  无法计算漏圈率：总人数为0")
    
    print("="*80)

if __name__ == '__main__':
    main()

