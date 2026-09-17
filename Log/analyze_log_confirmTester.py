#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志分析工具
功能：
1. 提取日志信息，支持指定时间段
2. 统计并生成CSV
3. 生成图表（分组柱状+多颜色区分）
"""

import re
import csv
import argparse
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
# 尝试导入matplotlib（可选）
HAS_MATPLOTLIB = False
try:
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')  # 使用非交互式后端，避免GUI依赖
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    
    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans', 'STHeiti']
    plt.rcParams['axes.unicode_minus'] = False
    HAS_MATPLOTLIB = True
except Exception as e:
    HAS_MATPLOTLIB = False

def parse_face_recognition_status(log_file_path):
    """解析日志中的人脸识别状态 返回仅包含name值的列表"""
    face_names = set()
    
    if not log_file_path.exists():
        return list(face_names)
    
    try:
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # 匹配格式: testerListToSportList recordId=..., name=57, status=FACE_RECOGNITED
                pattern = r'testerListToSportList.*?name=(\d+),\s*status=(\w+)'
                match = re.search(pattern, line)
                if match:
                    name = match.group(1).strip()  # 格式化：去除空格
                    face_names.add(name)
    except Exception as e:
        print(f"⚠️  读取人脸识别状态失败: {e}")

    return sorted(face_names, key=lambda x: int(x))  # 按数字升序

def parse_name_testerid_mapping(log_file_path):
    """
    提取 name 与 testerId 的映射
    """
    name_testerid_map = {}  # 确保一个name对应唯一testerId
    target_pattern = r'onSportDataChange updated, ip=[\d.]+, index=\d+, testerId=(\d+),\s*name=(\d+)'
    
    if not log_file_path.exists():
        print("⚠️  日志文件不存在，无法提取name-testerId映射")
        return name_testerid_map
    
    try:
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                match = re.search(target_pattern, line)
                if match:
                    tester_id = match.group(1).strip()  # 提取testerId
                    name = match.group(2).strip()        # 提取对应的name
                    # 去重：如果name已存在，不覆盖（保留第一个testerId）
                    if name not in name_testerid_map:
                        name_testerid_map[name] = tester_id
    except Exception as e:
        print(f"⚠️  提取name-testerId映射失败: {e}")
    
    print(f"✅ 从日志提取到 {len(name_testerid_map)} 组name-testerId映射")
    
    print("📋 按 testerId 升序排序后的映射详情：")
    sorted_items = sorted(name_testerid_map.items(), key=lambda x: int(x[1]))
    for name, tester_id in sorted_items:
        print(f"name: {name} → testerId: {tester_id}")
    return name_testerid_map

def parse_timestamp(line):
    """解析日志行的时间戳"""
    pattern = r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})'
    match = re.search(pattern, line)
    if match:
        try:
            return datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S.%f')
        except:
            return None
    return None

def parse_confirm_tester_data(line):
    """解析confirmTester日志数据"""
    pattern = r'confirmTester ip=([^,]+),\s*testerId=(\d+),\s*name=([^,]+)'
    match = re.search(pattern, line)
    
    if match:
        return {
            'ip': match.group(1),
            'testerId': match.group(2),
            'name': match.group(3).strip(),  # 格式化：去除空格
            'timestamp': parse_timestamp(line),
            'raw_line': line.strip()
        }
    return None

def filter_by_time_range(lines, start_time=None, end_time=None):
    """根据时间段过滤日志"""
    if not start_time and not end_time:
        return lines
    
    filtered = []
    for line in lines:
        timestamp = parse_timestamp(line)
        if timestamp:
            if start_time and timestamp < start_time:
                continue
            if end_time and timestamp > end_time:
                continue
        filtered.append(line)
    
    return filtered

def filter_logs_by_window(timestamps, logs, window_seconds=25):
    """按时间窗口过滤日志(25秒窗口)"""
    if not timestamps or len(timestamps) != len(logs):
        return [], []
    
    # 确保数据按时间排序
    combined = sorted(zip(timestamps, logs), key=lambda x: x[0])
    sorted_timestamps, sorted_logs = zip(*combined) if combined else ([], [])
    
    filtered_ts = []
    filtered_logs = []
    n = len(sorted_timestamps)
    start_idx = 0
    
    while start_idx < n:
        window_start = sorted_timestamps[start_idx]
        window_end = window_start + timedelta(seconds=window_seconds)
        end_idx = start_idx
        while end_idx < n and sorted_timestamps[end_idx] <= window_end:
            end_idx += 1
        last_in_window_idx = end_idx - 1
        
        filtered_ts.append(sorted_timestamps[last_in_window_idx])
        filtered_logs.append(sorted_logs[last_in_window_idx])
        start_idx = end_idx
    
    return filtered_ts, filtered_logs

def filter_by_5s_interval(timestamps, logs):
    """过滤相邻日志间隔小于等于5秒的日志：保留后一个，删除前一个"""
    if len(timestamps) < 2:
        return timestamps, logs
    
    filtered_ts = [timestamps[-1]]
    filtered_logs = [logs[-1]]
    
    for i in range(len(timestamps)-2, -1, -1):
        current_ts = timestamps[i]
        next_ts = filtered_ts[-1]
        time_diff = (next_ts - current_ts).total_seconds()
        
        if time_diff > 5:
            filtered_ts.append(current_ts)
            filtered_logs.append(logs[i])
    
    filtered_ts.reverse()
    filtered_logs.reverse()
    
    return filtered_ts, filtered_logs

def parse_log_file(log_file_path, start_time=None, end_time=None):
    """解析日志文件，同时提取基准时间和终止时间"""
    data = defaultdict(lambda: {
        'name': '',
        'testerId': '',
        'ip': '',
        'logs': [],
        'timestamps': []
    })
    base_start_time = None
    base_end_time = None
    target_start_keyword = "SportParallelFragmentViewModel: onAssistTestModeSportStarted"
    target_end_keyword = "SportFragmentViewModel: onSportDone test model all finish, sportStep="
    
    with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    if start_time or end_time:
        lines = filter_by_time_range(lines, start_time, end_time)
    
    for line in lines:
        if not base_start_time and target_start_keyword in line:
            base_start_time = parse_timestamp(line)
        
        if not base_end_time and target_end_keyword in line:
            base_end_time = parse_timestamp(line)
        
        parsed = parse_confirm_tester_data(line)
        if parsed:
            tester_id = parsed['testerId']
            name = parsed['name']
            
            if not data[tester_id]['name']:
                data[tester_id]['name'] = name
                data[tester_id]['testerId'] = tester_id
                data[tester_id]['ip'] = parsed['ip']
            
            data[tester_id]['logs'].append(parsed['raw_line'])
            if parsed['timestamp']:
                data[tester_id]['timestamps'].append(parsed['timestamp'])
    
    # 按基准时间和终止时间过滤日志
    for tester_id in data:
        timestamps = data[tester_id]['timestamps']
        logs = data[tester_id]['logs']
        filtered_ts = []
        filtered_logs = []
        
        for ts, log in zip(timestamps, logs):
            if ts is None:
                continue
            
            valid = True
            if base_start_time is not None and ts <= base_start_time:
                valid = False
            if base_end_time is not None and ts >= base_end_time:
                valid = False
                
            if valid:
                filtered_ts.append(ts)
                filtered_logs.append(log)
        
        data[tester_id]['timestamps'] = filtered_ts
        data[tester_id]['logs'] = filtered_logs
    
    # 应用25秒窗口和5秒间隔过滤
    for tester_id in data:
        filtered_ts, filtered_logs = filter_logs_by_window(
            data[tester_id]['timestamps'], 
            data[tester_id]['logs']
        )
        data[tester_id]['timestamps'] = filtered_ts
        data[tester_id]['logs'] = filtered_logs
        
        filtered_5s_ts, filtered_5s_logs = filter_by_5s_interval(
            data[tester_id]['timestamps'],
            data[tester_id]['logs']
        )
        data[tester_id]['timestamps'] = filtered_5s_ts
        data[tester_id]['logs'] = filtered_5s_logs
    
    return data, base_start_time, base_end_time

def generate_csv(data, output_csv):
    """生成CSV统计表格"""
    headers = ['name', 'id', 'ip', '日志数量', '日志信息']
    csv_rows = [headers]
    
    sorted_items = sorted(data.items(), key=lambda x: int(x[0]))
    
    for tester_id, info in sorted_items:
        log_info = '\n'.join(info['logs'][:7]) if info['logs'] else ''
        if len(log_info) > 800:
            log_info = '\n'.join(info['logs'][:6]) + '\n... (共{}条日志)'.format(len(info['logs']))
        
        row = [
            info['name'],
            info['testerId'],
            info['ip'],
            len(info['logs']),
            log_info
        ]
        csv_rows.append(row)
    
    output_csv = Path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_csv, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(csv_rows)
    
    print(f"✅ CSV表格已保存: {output_csv}")
    return csv_rows

def generate_charts(data, output_dir, base_start_time):
    """生成图表（分组柱状+多颜色区分）"""
    if not HAS_MATPLOTLIB:
        print("⚠️  跳过图表生成（matplotlib不可用）")
        return
    total_people = len(data)
    output_dir = Path(output_dir)
    date_str = datetime.now().strftime("%Y%m%d")
    output_dir = output_dir / date_str
    output_dir.mkdir(parents=True, exist_ok=True)
    
    def seconds_to_mmss(seconds):
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"
    
    # 1. 人员日志数量统计
    num_people = len(data)
    fig_width = max(10, min(num_people * 0.8, 200))
    fig, ax = plt.subplots(figsize=(fig_width, 6))
    
    names = []
    log_counts = []
    for tester_id, info in sorted(data.items(), key=lambda x: int(x[0])):
        names.append(info['name'])
        log_counts.append(len(info['logs']))
    
    ax.bar(names, log_counts, width=0.6, color='skyblue', edgecolor='navy', alpha=0.7)
    ax.set_xlabel(f'姓名（总人数：{total_people}）', fontsize=12)
    ax.set_ylabel('日志数量', fontsize=12)
    ax.set_title('人员日志数量统计（30间隔）', fontsize=14, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)
    
    for i, v in enumerate(log_counts):
        ax.text(i, v + 0.1, str(v), ha='center', va='bottom')
    
    plt.xticks(rotation=45, ha='right', fontsize=10)
    plt.tight_layout()
    chart1_path = output_dir / 'log_count_stats.png'
    plt.savefig(chart1_path, dpi=300, bbox_inches='tight')
    print(f"✅ 人员日志数量统计图已保存: {chart1_path}")
    plt.close()
    
    # 2. 每个人的日志时间对比
    people_data = {}
    max_timestamps = 0
    
    for tester_id, info in sorted(data.items(), key=lambda x: int(x[0])):
        person_name = f"{info['name']}（{tester_id}）"
        time_diffs = []
        
        if info['timestamps'] and base_start_time:
            for ts in info['timestamps']:
                diff = (ts - base_start_time).total_seconds()
                time_diffs.append(diff)
        
        people_data[person_name] = {
            'diffs': time_diffs,
            'name': info['name'],
            'testerId': tester_id
        }
        
        if len(time_diffs) > max_timestamps:
            max_timestamps = len(time_diffs)
    
    all_persons = list(people_data.keys())
    num_persons = len(all_persons)
    
    if num_persons == 0:
        return
    
    fig_width = max(12, min(num_persons * 1.2, 200))
    fig, ax = plt.subplots(figsize=(fig_width, 8))
    
    bar_width = 0.15 if max_timestamps <= 5 else 0.1
    x = np.arange(num_persons)
    color_cycle = plt.cm.tab10.colors
    labels = [f'时间点 {i+1}' for i in range(max_timestamps)]
    
    timepoint_data = [[] for _ in range(max_timestamps)]
    for person in all_persons:
        diffs = people_data[person]['diffs']
        for i in range(max_timestamps):
            timepoint_data[i].append(diffs[i] if i < len(diffs) else 0)
    
    for i in range(max_timestamps):
        ax.bar(
            x + i * bar_width, 
            timepoint_data[i], 
            width=bar_width,
            label=labels[i],
            color=color_cycle[i % len(color_cycle)],
            edgecolor='navy',
            alpha=0.7
        )
    
    label_fontsize = 6 if num_persons > 30 else 7 if num_persons > 15 else 8
    for i in range(max_timestamps):
        for j, val in enumerate(timepoint_data[i]):
            if val > 0:
                x_pos = x[j] + i * bar_width
                ax.text(
                    x_pos, val + max([max(tpd) for tpd in timepoint_data]) * 0.01,
                    seconds_to_mmss(val),
                    ha='center', va='bottom',
                    fontsize=label_fontsize,
                    rotation=90
                )
    
    ax.set_xlabel(f'人员（总人数：{total_people}）', fontsize=12)
    ax.set_ylabel('与发令时间的差值（分:秒）', fontsize=12)
    ax.set_title('每个人的日志时间对比（30秒间隔）', fontsize=14, fontweight='bold')
    ax.set_xticks(x + bar_width * (max_timestamps - 1) / 2)
    rotation = 90 if num_persons > 10 else 45
    ax.set_xticklabels(all_persons, rotation=rotation, ha='right',
                      fontsize=6 if num_persons > 30 else 7 if num_persons > 15 else 9)
    
    def format_mmss(x, pos):
        minutes = int(x // 60)
        seconds = int(x % 60)
        return f"{minutes:02d}:{seconds:02d}"
    ax.yaxis.set_major_formatter(FuncFormatter(format_mmss))
    
    ax.legend(fontsize=10, title='日志时间点')
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    chart2_path = output_dir / 'person_time_comparison.png'
    plt.savefig(chart2_path, dpi=300, bbox_inches='tight')
    print(f"✅ 人员日志时间对比图已保存: {chart2_path}")
    plt.close()

def main():
    parser = argparse.ArgumentParser(description='日志分析工具')
    parser.add_argument('log_file', type=str, help='日志文件路径')
    parser.add_argument('--start-time', type=str, help='开始时间 (格式: 2025-11-12 18:08:39)')
    parser.add_argument('--end-time', type=str, help='结束时间 (格式: 2025-11-12 18:22:45)')
    parser.add_argument('--output-dir', type=str, default='allure-report/log_analysis', help='输出目录')
    
    args = parser.parse_args()
    
    start_time = None
    end_time = None
    if args.start_time:
        try:
            start_time = datetime.strptime(args.start_time, '%Y-%m-%d %H:%M:%S')
        except:
            print(f"⚠️  开始时间格式错误，使用默认值")
    if args.end_time:
        try:
            end_time = datetime.strptime(args.end_time, '%Y-%m-%d %H:%M:%S')
        except:
            print(f"⚠️  结束时间格式错误，使用默认值")
    
    log_file = Path(args.log_file)
    if not log_file.exists():
        print(f"❌ 文件不存在: {log_file}")
        return
    
    print(f"📖 正在解析日志文件: {log_file}")
    
    # 1. 解析原有日志数据
    data, base_start_time, base_end_time = parse_log_file(log_file, start_time, end_time)
    
    # 2. 获取人脸识别的name列表（格式化后）
    face_names = parse_face_recognition_status(log_file)
    
    # 3. 新增：提取name-testerId映射（从目标关键字）
    name_testerid_map = parse_name_testerid_mapping(log_file)
    
    # 4. 格式化现有data中的name，避免匹配误差
    existing_names = {str(info['name']).strip() for info in data.values() if info['name']}
    
    # 5. 确定需要添加的name（仅data中没有的）
    names_to_add = [name for name in face_names if name.strip() not in existing_names]
    print(f"🔍 需要新增的name数量: {len(names_to_add)} (人脸识别有但data中没有)")
    
    # 6. 核心修改：仅新增数据，用真实testerId（从映射中匹配）
    added_count = 0  # 统计实际成功新增的数量
    for name in names_to_add:
        name_clean = name.strip()
        # 从映射中获取对应的真实testerId
        tester_id = name_testerid_map.get(name_clean)
        
        # 处理：如果没有找到对应的testerId，提示并跳过（确保只添加有真实testerId的数据）
        if not tester_id:
            print(f"⚠️  name={name_clean} 未找到对应的testerId，跳过添加")
            continue
        
        # 确保只添加（不覆盖原有数据）：如果testerId已存在，跳过
        if tester_id in data:
            print(f"⚠️  testerId={tester_id} (对应name={name_clean}) 已存在于data中，跳过添加")
            continue
        
        # 按data结构新增条目（仅添加，不修改原有）
        data[tester_id] = {
            'name': name_clean,
            'testerId': tester_id,  # 使用真实提取的testerId
            'ip': '',  # 无ip信息，留空
            'logs': [],  # 无日志，留空
            'timestamps': []  # 无时间戳，留空
        }
        added_count += 1
    
    if not data:
        print("⚠️  未找到有效数据")
        return
    
    # 基准时间处理
    if not base_start_time:
        print("⚠️  未找到基准时间关键字，使用备选时间")
        base_start_time = datetime.strptime("18:13:51.475", "%H:%M:%S.%f")
    else:
        print(f"✅ 提取到基准时间: {base_start_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
    
    if not base_end_time:
        print("⚠️  未找到终止时间关键字，未应用终止时间过滤")
    else:
        print(f"✅ 提取到终止时间: {base_end_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
    
    # 生成CSV和图表
    base_output_dir = Path(args.output_dir)
    date_str = datetime.now().strftime("%Y%m%d")
    output_dir = base_output_dir / date_str
    output_dir.mkdir(parents=True, exist_ok=True)
    
    csv_file = output_dir / f'{log_file.stem}_statistics.csv'
    csv_rows = generate_csv(data, csv_file)
    
    generate_charts(data, base_output_dir, base_start_time)
    
    # 统计摘要（更新实际新增数量）
    print("\n" + "="*80)
    print("统计摘要:")
    print("="*80)
    print(f"parse_face_recognition_status获取的name总数: {len(face_names)}")
    print(f"遍历data后总人数: {len(data)}")
    print(f"计划新增人数: {len(names_to_add)}")
    print(f"实际新增人数: {added_count}")  # 显示实际成功新增的数量
    print(f"过滤后总日志数: {sum(len(info['logs']) for info in data.values())}")
    print(f"基准时间: {base_start_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
    print(f"终止时间: {base_end_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}") if base_end_time else print("终止时间: 未设置")
    print("="*80)

if __name__ == '__main__':
    main()