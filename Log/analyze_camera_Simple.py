import re
from pathlib import Path
import argparse
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np
import csv

HAS_MATPLOTLIB = False
try:
    import matplotlib
    matplotlib.use('Agg')  # 使用非交互式后端
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    
    # 设置中文字体（统一风格）
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans', 'STHeiti']
    plt.rcParams['axes.unicode_minus'] = False
    HAS_MATPLOTLIB = True
except Exception as e:
    HAS_MATPLOTLIB = False

def parse_timestamp(line):
    """解析日志行的时间戳，返回字符串格式（保持原始格式）"""
    pattern = r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})'
    match = re.search(pattern, line)
    if match:
        return match.group(1)
    return None

def extract_running_persons(log_file_path, start_time=None, end_time=None):
    """
        提取格式：[{nameid: str, trackerid: str, timestamp: str, trackerTime: str, inAreaCount: str, sim: str, similerCount: str}, ...]
    """
    data = []
    # 正则表达式以匹配所有需要的字段
    pattern = r'识别出在跑人员:(\d+)\s*tracker id:(\d+)\s*trackerTime:(\d+)\s*inAreaCount:(\d+)\s*sim:([\d.]+)\s*similerCount:(\d+)'
    
    if not log_file_path.exists():
        print(f"⚠️  日志文件不存在: {log_file_path}")
        return data
    
    try:
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                if "识别出在跑人员" in line:
                    # 提取时间戳（字符串格式）
                    timestamp_str = parse_timestamp(line)
                    
                    # 时间过滤：如果需要过滤，将字符串转datetime比较
                    if timestamp_str:
                        try:
                            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                            # 检查是否在时间范围内
                            if (start_time and timestamp < start_time) or (end_time and timestamp > end_time):
                                continue
                        except:
                            print(f"⚠️  第{line_num}行时间戳格式异常: {timestamp_str}，跳过此条")
                            continue
                    else:
                        # 无时间戳的记录，保留并标记
                        print(f"⚠️  第{line_num}行无有效时间戳，保留此条记录")
                        timestamp_str = "无时间戳"
                    
                    # 提取所有字段
                    match = re.search(pattern, line)
                    if match:
                        nameid = match.group(1).strip()
                        trackerid = match.group(2).strip()
                        trackerTime = match.group(3).strip()
                        inAreaCount = match.group(4).strip()
                        sim = match.group(5).strip()
                        similerCount = match.group(6).strip()
                        data.append({
                            'nameid': nameid,
                            'trackerid': trackerid,
                            'timestamp': timestamp_str,
                            'trackerTime': trackerTime,
                            'inAreaCount': inAreaCount,
                            'sim': sim,
                            'similerCount': similerCount
                        })
                    else:
                        print(f"⚠️  在第{line_num}行找到关键字但格式不匹配: {line.strip()}")
    except Exception as e:
        print(f"⚠️  读取日志文件失败: {e}")
    
    return data

def split_by_time_window(records, time_threshold):
    """
    将同一nameid的记录按时间窗格分割（间隔大于指定阈值则分割）
    返回分割后的多个部分列表
    """
    if not records:
        return []
    
    # 按时间戳排序（无时间戳放最前）
    sorted_records = sorted(
        records,
        key=lambda x: datetime.strptime(x['timestamp'], '%Y-%m-%d %H:%M:%S') 
        if x['timestamp'] != "无时间戳" else datetime.min
    )
    
    groups = []
    current_group = [sorted_records[0]]
    
    for record in sorted_records[1:]:
        # 处理无时间戳的情况
        if current_group[-1]['timestamp'] == "无时间戳" or record['timestamp'] == "无时间戳":
            current_group.append(record)
            continue
            
        # 计算时间差
        prev_time = datetime.strptime(current_group[-1]['timestamp'], '%Y-%m-%d %H:%M:%S')
        curr_time = datetime.strptime(record['timestamp'], '%Y-%m-%d %H:%M:%S')
        time_diff = (curr_time - prev_time).total_seconds()
        
        if time_diff > time_threshold:  # 使用传入的阈值
            # 超过时间窗格，分割
            groups.append(current_group)
            current_group = [record]
        else:
            current_group.append(record)
    
    # 添加最后一组
    if current_group:
        groups.append(current_group)
        
    return groups

def count_unique_trackers(groups):
    """统计每个分组中不重复的trackerid数量"""
    return [len(set(record['trackerid'] for record in group)) for group in groups]

def process_group_records(group):
    """
    处理单个分组内的记录：
    1. 相邻记录trackerid相同 → 保留后一条，删除前一条
    2. 相邻记录trackerid不同且前一条>后一条 → 标记为需要凸显（添加特殊标识）
    返回处理后的带标记记录列表
    """
    if not group:
        return []
    
    # 第一步：去重
    deduplicated = [group[0]]
    for record in group[1:]:
        prev_record = deduplicated[-1]
        try:
            # 转为整数比较trackerid（兼容字符串格式的数字）
            prev_tracker = int(prev_record['trackerid'])
            curr_tracker = int(record['trackerid'])
        except ValueError:
            # trackerid非数字格式，不处理去重
            deduplicated.append(record)
            continue
        
        if prev_tracker == curr_tracker:
            # 保留最新的
            deduplicated[-1] = record
        else:
            deduplicated.append(record)
    
    # 第二步：标记需要凸显的记录
    marked_records = []
    for i in range(len(deduplicated)):
        record = deduplicated[i].copy()
        # 标记字段：默认空字符串，需要凸显则设为特殊符号
        record['highlight_mark'] = ""
        
        # 只检查当前记录与下一条的关系（最后一条无下一条，不标记）
        if i < len(deduplicated) - 1:
            try:
                curr_tracker = int(record['trackerid'])
                next_tracker = int(deduplicated[i+1]['trackerid'])
            except ValueError:
                # trackerid非数字，不标记
                marked_records.append(record)
                continue
            
            # 前一条trackerid大于后一条 → 用特殊符号凸显（⚠️+异常标识）
            if curr_tracker > next_tracker:
                record['highlight_mark'] = "⚠️ 异常：trackerid下降"
        
        marked_records.append(record)
    
    return marked_records

def export_processed_csv(nameid_data, output_dir):
    """
    导出处理后的记录到CSV文件：
    - 列：nameid、时间戳、分组号、trackerid、trackerTime、sim、标记
    - 凸显方式：需要关注的记录在"标记"列显示"⚠️ 异常：trackerid下降"
    - 规则1：相邻trackerid相同 → 保留后一条
    - 规则2：相邻trackerid不同且前一条>后一条 → "标记"列显示特殊标识
    - 规则3：nameid切换时插入空行分割
    """
    # 创建输出目录（按日期组织）
    date_str = datetime.now().strftime("%Y%m%d")
    output_path = Path(output_dir) / date_str
    output_path.mkdir(parents=True, exist_ok=True)
    csv_path = output_path / "processed_running_log.csv"
    
    # 定义CSV字段
    fieldnames = ['nameid', '时间戳', '分组号', 'trackerid', 'trackerTime', 'sim', '标记']
    
    try:
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            current_row = 2  # 用于记录当前行号（仅作逻辑判断）
            # 按nameid数值升序排序（确保输出有序）
            sorted_nameids = sorted(
                nameid_data.keys(),
                key=lambda x: int(x) if x.isdigit() else float('inf')  # 非数字nameid放最后
            )
            
            # 遍历每个nameid的数据
            for nameid_idx, nameid in enumerate(sorted_nameids):
                nameid_info = nameid_data[nameid]
                
                # 遍历每个分组（带分组号）
                for group_idx, group in enumerate(nameid_info['groups'], 1):
                    # 处理当前分组的记录（去重+标记凸显）
                    processed_records = process_group_records(group)
                    
                    # 写入当前分组的所有处理后记录
                    for record in processed_records:
                        writer.writerow({
                            'nameid': nameid,
                            '时间戳': record['timestamp'],
                            '分组号': group_idx,
                            'trackerid': record['trackerid'],
                            'trackerTime': record['trackerTime'],
                            'sim': record['sim'],
                            '标记': record['highlight_mark']
                        })
                        current_row += 1
                
                # 规则3：nameid切换时插入空行（最后一个nameid后不插）
                if nameid_idx < len(sorted_nameids) - 1:
                    # 写入空行（所有字段为空字符串）
                    writer.writerow({field: '' for field in fieldnames})
                    current_row += 1
        
        print(f"✅ 处理后的CSV文件已保存至：{csv_path}")
    except Exception as e:
        print(f"⚠️  导出CSV失败：{e}")

def plot_bar_chart(nameid_data, output_dir):
    """绘制柱状图，展示每个nameid不同时间窗格的不重复trackerid数量"""
    if not HAS_MATPLOTLIB:
        print("⚠️  跳过图表生成（matplotlib不可用）")
        return
    
    nameids = list(nameid_data.keys())
    # 按nameid数值排序
    nameids.sort(key=lambda x: int(x) if x.isdigit() else float('inf'))
    total_count = len(nameids)
    # 准备数据
    all_counts = []
    for nameid in nameids:
        all_counts.append(nameid_data[nameid]['counts'])
    
    # 创建输出目录（按日期组织）
    date_str = datetime.now().strftime("%Y%m%d")
    output_path = Path(output_dir) / date_str
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 设置图表大小（自适应数据量）
    num_nameids = len(nameids)
    fig_width = max(10, min(num_nameids * 0.8, 200))
    fig, ax = plt.subplots(figsize=(fig_width, 6))
    
    # 设置柱状图样式
    width = 0.8 / max(len(counts) for counts in all_counts) if all_counts else 0.8
    color_cycle = plt.cm.tab10.colors  # 使用颜色循环
    
    for i, counts in enumerate(all_counts):
        for j, count in enumerate(counts):
            ax.bar(
                x=i - 0.4 + width*(j + 0.5),
                height=count,
                width=width,
                label=f'分段{j+1}' if i == 0 else "",
                color=color_cycle[j % len(color_cycle)],
                edgecolor='navy',
                alpha=0.7
            )
            # 添加数值标签
            ax.text(
                x=i - 0.4 + width*(j + 0.5),
                y=count + max(max(c) for c in all_counts) * 0.01,
                s=str(count),
                ha='center',
                va='bottom',
                fontsize=8
            )
    
    # 设置图表属性（统一风格）
    ax.set_xlabel(f'NameID（总人数：{total_count}）', fontsize=12)
    ax.set_ylabel('不重复TrackerID数量', fontsize=12)
    ax.set_title('各NameID不同时间窗格的不重复TrackerID数量', fontsize=14, fontweight='bold')
    ax.set_xticks(range(len(nameids)))
    ax.set_xticklabels(nameids, rotation=45, ha='right', fontsize=10)
    ax.legend(fontsize=10)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    # 保存图表而不是显示
    chart_path = output_path / 'tracker_count_stats.png'
    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
    print(f"✅ 柱状图已保存: {chart_path}")
    plt.close()

def validate_distance(distance):
    """验证距离参数并返回对应的时间阈值"""
    distance_thresholds = {100: 10, 200: 21, 400: 49}
    if distance not in distance_thresholds:
        return None, f"不支持的距离: {distance}米，仅支持100/200/400米"
    return distance_thresholds[distance], None

def parse_time_param(time_str):
    """解析时间字符串为datetime对象"""
    if not time_str:
        return None, None
    try:
        return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S'), None
    except ValueError:
        return None, "时间格式错误，请使用: YYYY-MM-DD HH:MM:SS"

def process_running_data(log_file, start_time, end_time, time_threshold):
    """处理跑步数据：提取、分组、分割时间窗格并统计"""
    running_persons_data = extract_running_persons(log_file, start_time, end_time)
    
    # 按nameid分组
    nameid_groups = defaultdict(list)
    for item in running_persons_data:
        nameid_groups[item['nameid']].append(item)
    
    # 处理每个nameid，按时间窗格分割并统计
    nameid_data = {}
    for nameid, records in nameid_groups.items():
        split_groups = split_by_time_window(records, time_threshold)
        tracker_counts = count_unique_trackers(split_groups)
        nameid_data[nameid] = {
            'groups': split_groups,
            'counts': tracker_counts
        }
    return nameid_data

def main():
    parser = argparse.ArgumentParser(description='日志分析工具（按nameid分组+时间窗格分割+数据清洗）')
    parser.add_argument('log_file', type=str, help='日志文件路径')
    parser.add_argument('distance', type=int, help='跑步距离（100/200/400米）')
    parser.add_argument('--start-time', type=str, help='开始时间 (格式: 2025-11-12 18:08:39)')
    parser.add_argument('--end-time', type=str, help='结束时间 (格式: 2025-11-12 18:22:45)')
    parser.add_argument('--output-dir', type=str, default='allure-report/log_analysis', help='输出目录')
    args = parser.parse_args()
    
    # 验证距离参数
    time_threshold, err = validate_distance(args.distance)
    if err:
        print(f"⚠️  {err}")
        return
    print(f"ℹ️  检测到{args.distance}米，使用时间阈值: {time_threshold}秒")
    
    # 解析时间参数
    start_time, err = parse_time_param(args.start_time)
    if err:
        print(f"⚠️  开始{err}")
        return
    end_time, err = parse_time_param(args.end_time)
    if err:
        print(f"⚠️  结束{err}")
        return
    
    # 处理数据
    log_file = Path(args.log_file)
    nameid_data = process_running_data(log_file, start_time, end_time, time_threshold)
    
    # 导出结果（仅CSV和可选图表）
    if nameid_data:
        export_processed_csv(nameid_data, args.output_dir)
        plot_bar_chart(nameid_data, args.output_dir)
    else:
        print("\nℹ️  没有有效数据可处理")

if __name__ == '__main__':
    main()