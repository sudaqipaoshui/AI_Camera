import re
import csv
from pathlib import Path
import argparse
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np

HAS_MATPLOTLIB = False
try:
    import matplotlib
    matplotlib.use('Agg')  # 使用非交互式后端
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    
    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans', 'STHeiti']
    plt.rcParams['axes.unicode_minus'] = False
    HAS_MATPLOTLIB = True
except Exception:
    HAS_MATPLOTLIB = False

def parse_time(time_str):
    try:
        return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"时间格式错误: {time_str}，正确格式为 'YYYY-MM-DD HH:MM:SS'"
        )

def parse_name_testerid_mapping(log_file_path, target_names, app_start=None, app_end=None):
    """
    确保每个唯一name对应唯一testerId
    """
    name_testerid_map = {}  
    
    if not log_file_path.exists():
        return name_testerid_map
    
    try:
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # 提取日志时间戳
                time_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})', line)
                if not time_match:
                    continue
                
                try:
                    log_time = datetime.strptime(time_match.group(1), '%Y-%m-%d %H:%M:%S.%f')
                except:
                    continue
                
                # 时间范围判断（仅当起止时间都提供时才过滤）
                if app_start is not None and app_end is not None:
                    if not (app_start <= log_time <= app_end):
                        continue
                
                # 匹配name和testerId的映射关系
                match = re.search(r'testerId=(\d+),\s*name=([^,]+)', line)
                if match:
                    tester_id = match.group(1).strip()
                    name = match.group(2).strip()
                    # 仅保留目标name列表中的记录，且同一name仅建立一次映射
                    if name in target_names and name not in name_testerid_map:
                        name_testerid_map[name] = tester_id
    
    except Exception as e:
        print(f"建立name-testerId映射时出错: {str(e)}")
    
    return name_testerid_map

def parse_app_log(app_log_path, app_start=None, app_end=None):
    """
    最终person_ids数量与去重后的唯一name数量一致
    """
    name_set = set()  # 用set自动去重，确保每个name唯一
    name_details = []  # 保存去重后的name及首次出现的行号，用于日志输出
    start_time = None
    base_time = None
    
    # 正则表达式定义
    tester_pattern = r'testerListToSportList recordId=.*name=([\u4e00-\u9fa5a-zA-Z0-9_]+)'
    start_pattern = r'SportParallelFragmentViewModel: onAssistTestModeSportStarted'  # 匹配基准时间行
    
    if not app_log_path.exists():
        print(f"错误：APP日志文件不存在 - {app_log_path}")
        return [], None, None
    
    try:
        # 第一步：遍历日志，提取所有`testerListToSportList`行的name（自动去重）和基准时间
        # 注意：testerListToSportList 行通常在时间范围之前出现，所以需要扩大搜索范围
        with open(app_log_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):  # 记录行号，方便排查问题
                # 提取日志时间戳
                time_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})', line)
                if not time_match:
                    continue
                
                try:
                    log_time = datetime.strptime(time_match.group(1), '%Y-%m-%d %H:%M:%S.%f')
                except:
                    continue
                
                # 提取name（testerListToSportList 行通常在时间范围之前，所以不严格限制时间范围）
                tester_match = re.search(tester_pattern, line)
                if tester_match:
                    # 对于 testerListToSportList 行，如果提供了时间范围，允许在开始时间前30分钟内查找
                    if app_start is not None and app_end is not None:
                        # 允许在开始时间前30分钟到结束时间之间查找
                        search_start = app_start - timedelta(minutes=30)
                        if not (search_start <= log_time <= app_end):
                            continue
                    name = tester_match.group(1).strip()
                    if name not in name_set:
                        name_set.add(name)
                        name_details.append({
                            'name': name,
                            'first_line': line_num  # 记录首次出现的行号
                        })
                        print(f"从第{line_num}行首次提取到name: {name} (时间: {log_time.strftime('%Y-%m-%d %H:%M:%S.%f')})")
                    else:
                        print(f"第{line_num}行重复出现name: {name}（已去重）")
                
                # 提取基准时间（允许在开始时间前查找，因为基准时间通常在测试开始时记录）
                if not start_time and re.search(start_pattern, line):
                    # 基准时间行允许在开始时间前5分钟到结束时间之间查找
                    if app_start is not None and app_end is not None:
                        search_start = app_start - timedelta(minutes=5)
                        if not (search_start <= log_time <= app_end):
                            continue
                    try:
                        start_time = datetime.strptime(time_match.group(1), '%Y-%m-%d %H:%M:%S.%f')
                        base_time = start_time - timedelta(hours=8)
                        print(f"提取到基准时间: {base_time.strftime('%Y-%m-%d %H:%M:%S')} (原始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S.%f')})")
                    except:
                        print("警告：未能解析基准时间")
    
    except Exception as e:
        print(f"提取name和基准时间时出错: {str(e)}")
        return [], None, None
    
    # 检查是否提取到有效name
    if not name_set:
        print("错误：未从日志中提取到任何`testerListToSportList recordId=`行的有效name")
        return [], None, None
    
    # 第二步：建立name-testerId映射（基于去重后的唯一name列表）
    target_names = list(name_set)
    name_testerid_map = parse_name_testerid_mapping(
        app_log_path,
        target_names=target_names,
        app_start=app_start,
        app_end=app_end
    )
    
    # 第三步：生成person_ids（去重后按name字典序排序，确保结果稳定）
    person_ids = []
    missing_mapping = []  # 记录未找到映射的name
    # 按name字典序排序（汉字按Unicode排序，英文按字母序）
    sorted_name_details = sorted(name_details, key=lambda x: x['name'])
    
    for item in sorted_name_details:
        name = item['name']
        first_line = item['first_line']
        if name in name_testerid_map:
            tester_id = name_testerid_map[name]
            person_ids.append(tester_id)
        else:
            # 未找到映射时，添加占位符
            person_ids.append(f"未知-{name}")
            missing_mapping.append(f"name={name}（首次出现第{first_line}行）")
    
    # 输出关键统计信息
    print("\n" + "="*60)
    print(f"原始`testerListToSportList recordId=`行总数：{len(name_details)}（已去重）")
    print(f"去重后唯一name数量：{len(name_set)}")
    print(f"成功映射testerId的数量：{len(person_ids) - len(missing_mapping)}")
    print(f"未找到testerId的数量：{len(missing_mapping)}")
    if missing_mapping:
        print(f"未找到映射的记录：{', '.join(missing_mapping)}")
    
    print("\nname与testerId映射关系（去重后）：")
    for name, tid in sorted(name_testerid_map.items(), key=lambda x: x[0]):
        print(f"  name: {name} → testerId: {tid}")
    
    print(f"\n最终person_ids列表（长度：{len(person_ids)}，已排序）：")
    print(f"  {person_ids}")
    print("="*60 + "\n")
    
    # 若所有name都未找到映射，返回失败
    if len(missing_mapping) == len(name_set):
        print("错误：所有提取到的name都未找到对应的testerId，分析终止")
        return [], None, None
    
    return person_ids, base_time, name_testerid_map

def extract_camera_data(camera_log_path, target_ids, camera_start=None, camera_end=None):
    """提取Camera日志中指定testerId的记录"""
    # 初始化字典，确保包含所有target_ids，即使没有记录也保留空列表
    data = {pid: [] for pid in target_ids}
    
    db_pattern = r'db top one id:(\d+)tracker id:(\d+)trackerTime:(\d+)inAreaCount:(\d+)sim:([\d.]+)similerCount:(\d+)'
    new_pattern = r'new feature top one id:(\d+)tracker id:(\d+)trackerTime:(\d+)inAreaCount:(\d+)sim:([\d.]+)similerCount:(\d+)'
    
    if not camera_log_path.exists():
        return data  # 返回包含所有target_ids的空字典
    
    try:
        with open(camera_log_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # 提取原始时间戳字符串
                time_match = re.search(r'time:(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', line)
                if not time_match:
                    continue
                time_str = time_match.group(1)  # 保存原始时间戳字符串
                
                # 解析为datetime对象
                try:
                    timestamp = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                except:
                    continue
                
                # 时间范围判断（仅当起止时间都提供时才过滤）
                if camera_start is not None and camera_end is not None:
                    if not (camera_start <= timestamp <= camera_end):
                        continue
                
                # 匹配db类型
                db_match = re.search(db_pattern, line)
                if db_match:
                    id_str = db_match.group(1)
                    # 仅处理target_ids中存在的id
                    if id_str in data:
                        try:
                            data[id_str].append({
                                'id': id_str,
                                'trackerid': db_match.group(2).strip(),
                                'timestamp': timestamp,  # 解析后的datetime对象
                                'time_str': time_str,    # 原始时间戳字符串
                                'trackerTime': db_match.group(3).strip(),
                                'inAreaCount': db_match.group(4).strip(),
                                'sim': db_match.group(5).strip(),
                                'similerCount': db_match.group(6).strip(),
                                'type': 'db'
                            })
                        except:
                            pass
                    continue
                
                # 匹配new类型
                new_match = re.search(new_pattern, line)
                if new_match:
                    id_str = new_match.group(1)
                    # 仅处理target_ids中存在的id
                    if id_str in data:
                        try:
                            data[id_str].append({
                                'id': id_str,
                                'trackerid': new_match.group(2).strip(),
                                'timestamp': timestamp,  # 解析后的datetime对象
                                'time_str': time_str,    # 原始时间戳字符串
                                'trackerTime': new_match.group(3).strip(),
                                'inAreaCount': new_match.group(4).strip(),
                                'sim': new_match.group(5).strip(),
                                'similerCount': new_match.group(6).strip(),
                                'type': 'new'
                            })
                        except:
                            pass
                    continue
    except Exception as e:
        print(f"解析Camera日志出错: {str(e)}")
    
    return data

def filter_by_sim(data):
    """过滤每个id对应的记录中sim值>=0.75的记录，保持原字典结构"""
    filtered_data = {}
    # 遍历每个id及其对应的记录列表
    for pid, records in data.items():
        filtered_records = []
        for record in records:
            try:
                # 尝试将sim转换为浮点数，判断
                if float(record['sim']) >= 0.75:
                    filtered_records.append(record)
            except (ValueError, KeyError):
                # 跳过sim值无效或不存在的记录
                continue
        # 保留当前id，值为过滤后的记录列表（可能为空）
        filtered_data[pid] = filtered_records
    return filtered_data

def split_by_type(sim_data):
    # 初始化两个新字典，确保包含与sim_data相同的所有id
    db_sim_data = {pid: [] for pid in sim_data.keys()}
    new_sim_data = {pid: [] for pid in sim_data.keys()}
    
    # 遍历每个id的记录，按类型分类
    for pid, records in sim_data.items():
        for record in records:
            if record['type'] == 'db':
                db_sim_data[pid].append(record)
            elif record['type'] == 'new':
                new_sim_data[pid].append(record)
    
    return db_sim_data, new_sim_data

def seconds_to_mmss(seconds):
    """将秒数转换为 分:秒 格式"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"

def validate_distance(distance):
    """验证跑步距离，返回对应的时间阈值"""
    distance_thresholds = {100: 10, 200: 21, 400: 49}
    if distance not in distance_thresholds:
        return None, f"不支持的距离: {distance}米，仅支持100/200/400米"
    return distance_thresholds[distance], None

"""按时间窗口逻辑分割记录"""
def split_by_time_window(records, time_threshold):
    
    if not records:
        return []  
    
    # 按时间戳升序排序
    sorted_records = sorted(records, key=lambda x: x['timestamp'])
    result = []
    
    # 遍历所有记录
    for i in range(len(sorted_records)):
        current = sorted_records[i]
        
        # 判断是否为最后一条记录
        if i < len(sorted_records) - 1:

            next_record = sorted_records[i + 1]
            time_diff = (next_record['timestamp'] - current['timestamp']).total_seconds()
            
            if time_diff > time_threshold:
                result.append(current)
        else:

            result.append(current)
    
    return result  

"""按时间窗口过滤db和new类型的数据："""
def filter_by_time_window(db_sim_data, new_sim_data, time_threshold):
    # 初始化结果字典，确保保留所有原始ID
    s_db_sim_data = {pid: [] for pid in db_sim_data.keys()}
    s_new_sim_data = {pid: [] for pid in new_sim_data.keys()}
    
    # 处理db类型数据：对每个id的记录列表应用时间窗口过滤
    for pid in db_sim_data.keys():
        pid_records = db_sim_data[pid]
        # 应用时间窗口过滤逻辑，仅保留每个窗口的最后一条记录
        filtered_records = split_by_time_window(pid_records, time_threshold)
        s_db_sim_data[pid] = filtered_records
    
    # 处理new类型数据：对每个id的记录列表应用时间窗口过滤
    for pid in new_sim_data.keys():
        pid_records = new_sim_data[pid]
        filtered_records = split_by_time_window(pid_records, time_threshold)
        s_new_sim_data[pid] = filtered_records
    
    return s_db_sim_data, s_new_sim_data

"""生成db类型柱状图"""
def plot_db_time_diff_chart(db_data, base_time, output_dir, person_info):
    """生成db类型柱状图，包含所有ID即使记录为空"""
    if not HAS_MATPLOTLIB or not base_time or not db_data:
        return
    
    # 准备绘图数据：确保包含所有ID，即使记录为空
    plot_data = defaultdict(list)
    # 遍历所有ID（包括记录为空的）
    for pid in db_data.keys():
        records = db_data[pid]  # 可能为空列表
        for record in records:
            time_diff = (record['timestamp'] - base_time).total_seconds()
            plot_data[pid].append(round(time_diff, 2))
        # 关键：即使没有记录，也要确保ID存在于plot_data中（值为空列表）
        if pid not in plot_data:
            plot_data[pid] = []
    
    # 所有ID必须从原始db_data的键中获取，确保不丢失任何ID
    def sort_key(x):
        if x.startswith('未知-'):
            suffix = x.replace('未知-', '')
            return int(suffix) if suffix.isdigit() else float('inf')
        else:
            return int(x) if x.isdigit() else float('inf')
    all_ids = sorted(db_data.keys(), key=sort_key)
    # 生成人员列表，确保所有ID都有对应条目（即使没有person_info）
    all_persons = []
    for pid in all_ids:
        if pid in person_info and 'name' in person_info[pid]:
            all_persons.append(f"{person_info[pid]['name']}（{pid}）")
        else:
            all_persons.append(f"未知（{pid}）")  # 处理无人员信息的情况
    total_people = len(all_persons)  # 等于原始ID总数
    
    # 创建输出目录
    date_str = datetime.now().strftime("%Y%m%d")
    output_path = Path(output_dir) / date_str
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 生成时间戳（用于文件名）
    timestamp_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    
    # 图表配置：计算最大时间点数量（包含空记录ID的0）
    max_timestamps = 0
    for pid in all_ids:
        if len(plot_data[pid]) > max_timestamps:
            max_timestamps = len(plot_data[pid])
    max_timestamps = max_timestamps if max_timestamps > 0 else 1  # 至少1个时间点
    
    bar_width = 0.15 if max_timestamps <= 5 else 0.1
    x_positions = np.arange(len(all_persons))
    color_cycle = plt.cm.tab10.colors
    labels = [f'时间点 {i+1}' for i in range(max_timestamps)]
    
    # 整理时间点数据：为空记录ID填充0
    timepoint_data = [[] for _ in range(max_timestamps)]
    for idx, pid in enumerate(all_ids):
        diffs = plot_data[pid]
        for i in range(max_timestamps):
            # 为空记录或不足的时间点填充0
            timepoint_data[i].append(diffs[i] if i < len(diffs) else 0)
    
    # 设置图表大小
    fig_width = max(12, min(total_people * 1.2, 200))
    fig, ax = plt.subplots(figsize=(fig_width, 8))
    
    # 设置标题
    ax.set_title(
        f'db top one 类型 - 人员时间差分布（总人数：{total_people}）\n（基准时间: {base_time.strftime("%Y-%m-%d %H:%M:%S")}）',
        fontsize=14, fontweight='bold'
    )
    
    # 绘制柱状图（空记录ID会显示高度为0的柱子）
    for i in range(max_timestamps):
        ax.bar(
            x_positions + i * bar_width,
            timepoint_data[i],
            width=bar_width,
            label=labels[i],
            color=color_cycle[i % len(color_cycle)],
            edgecolor='navy',
            alpha=0.7
        )
    
    # 添加数据标签：仅为有值的条目添加
    label_fontsize = 6 if total_people > 30 else 7 if total_people > 15 else 8
    for i in range(max_timestamps):
        for j, val in enumerate(timepoint_data[i]):
            if val > 0:  # 只显示正值标签（0值不显示）
                x_pos = x_positions[j] + i * bar_width
                ax.text(
                    x_pos, val + max([max(tpd) for tpd in timepoint_data]) * 0.01,
                    seconds_to_mmss(val),
                    ha='center', va='bottom',
                    fontsize=label_fontsize,
                    rotation=90
                )
    
    # 设置坐标轴
    ax.set_xlabel(f'人员（总人数：{total_people}）', fontsize=12)
    ax.set_ylabel('与发令时间的差值（分:秒）', fontsize=12)
    
    ax.set_xticks(x_positions + bar_width * (max_timestamps - 1) / 2)
    rotation = 90 if total_people > 10 else 45
    ax.set_xticklabels(all_persons, rotation=rotation, ha='right',
                      fontsize=6 if total_people > 30 else 7 if total_people > 15 else 9)
    
    # Y轴格式化
    def format_mmss(x, pos):
        minutes = int(x // 60)
        seconds = int(x % 60)
        return f"{minutes:02d}:{seconds:02d}"
    ax.yaxis.set_major_formatter(FuncFormatter(format_mmss))
    
    # 添加图例和网格
    ax.legend(fontsize=10, title='日志时间点')
    ax.grid(axis='y', alpha=0.3)
    
    # 调整布局并保存
    plt.tight_layout()
    chart_filename = f'db_time_diff_analysis_{timestamp_str}.png'
    chart_path = output_path / chart_filename
    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
    print(f"✅ db类型时间差分析图已保存: {chart_path}")
    plt.close()

"""生成new类型柱状图"""
def plot_new_time_diff_chart(new_data, base_time, output_dir, person_info):
    """生成new类型柱状图，包含所有ID即使记录为空"""
    if not HAS_MATPLOTLIB or not base_time or not new_data:
        return
    
    # 准备绘图数据：确保包含所有ID，即使记录为空
    plot_data = defaultdict(list)
    # 遍历所有ID（包括记录为空的）
    for pid in new_data.keys():
        records = new_data[pid]  # 可能为空列表
        for record in records:
            time_diff = (record['timestamp'] - base_time).total_seconds()
            plot_data[pid].append(round(time_diff, 2))
        # 关键：即使没有记录，也要确保ID存在于plot_data中
        if pid not in plot_data:
            plot_data[pid] = []
    
    # 所有ID必须从原始new_data的键中获取，确保不丢失任何ID
    def sort_key(x):
        if x.startswith('未知-'):
            suffix = x.replace('未知-', '')
            return int(suffix) if suffix.isdigit() else float('inf')
        else:
            return int(x) if x.isdigit() else float('inf')
    all_ids = sorted(new_data.keys(), key=sort_key)
    # 生成人员列表，确保所有ID都有对应条目
    all_persons = []
    for pid in all_ids:
        if pid in person_info and 'name' in person_info[pid]:
            all_persons.append(f"{person_info[pid]['name']}（{pid}）")
        else:
            all_persons.append(f"未知（{pid}）")  # 处理无人员信息的情况
    total_people = len(all_persons)  # 等于原始ID总数
    
    # 创建输出目录
    date_str = datetime.now().strftime("%Y%m%d")
    output_path = Path(output_dir) / date_str
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 生成时间戳（用于文件名）
    timestamp_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    
    # 图表配置：计算最大时间点数量
    max_timestamps = 0
    for pid in all_ids:
        if len(plot_data[pid]) > max_timestamps:
            max_timestamps = len(plot_data[pid])
    max_timestamps = max_timestamps if max_timestamps > 0 else 1  # 至少1个时间点
    
    bar_width = 0.15 if max_timestamps <= 5 else 0.1
    x_positions = np.arange(len(all_persons))
    color_cycle = plt.cm.tab10.colors
    labels = [f'时间点 {i+1}' for i in range(max_timestamps)]
    
    # 整理时间点数据：为空记录ID填充0
    timepoint_data = [[] for _ in range(max_timestamps)]
    for idx, pid in enumerate(all_ids):
        diffs = plot_data[pid]
        for i in range(max_timestamps):
            timepoint_data[i].append(diffs[i] if i < len(diffs) else 0)
    
    # 设置图表大小
    fig_width = max(12, min(total_people * 1.2, 200))
    fig, ax = plt.subplots(figsize=(fig_width, 8))
    
    # 设置标题
    ax.set_title(
        f'new feature top one 类型 - 人员时间差分布（总人数：{total_people}）\n（基准时间: {base_time.strftime("%Y-%m-%d %H:%M:%S")}）',
        fontsize=14, fontweight='bold'
    )
    
    # 绘制柱状图（空记录ID会显示高度为0的柱子）
    for i in range(max_timestamps):
        ax.bar(
            x_positions + i * bar_width,
            timepoint_data[i],
            width=bar_width,
            label=labels[i],
            color=color_cycle[i % len(color_cycle)],
            edgecolor='navy',
            alpha=0.7
        )
    
    # 添加数据标签：仅为有值的条目添加
    label_fontsize = 6 if total_people > 30 else 7 if total_people > 15 else 8
    for i in range(max_timestamps):
        for j, val in enumerate(timepoint_data[i]):
            if val > 0:  # 只显示正值标签
                x_pos = x_positions[j] + i * bar_width
                ax.text(
                    x_pos, val + max([max(tpd) for tpd in timepoint_data]) * 0.01,
                    seconds_to_mmss(val),
                    ha='center', va='bottom',
                    fontsize=label_fontsize,
                    rotation=90
                )
    
    # 设置坐标轴
    ax.set_xlabel(f'人员（总人数：{total_people}）', fontsize=12)
    ax.set_ylabel('与发令时间的差值（分:秒）', fontsize=12)
    
    ax.set_xticks(x_positions + bar_width * (max_timestamps - 1) / 2)
    rotation = 90 if total_people > 10 else 45
    ax.set_xticklabels(all_persons, rotation=rotation, ha='right',
                      fontsize=6 if total_people > 30 else 7 if total_people > 15 else 9)
    
    # Y轴格式化
    def format_mmss(x, pos):
        minutes = int(x // 60)
        seconds = int(x % 60)
        return f"{minutes:02d}:{seconds:02d}"
    ax.yaxis.set_major_formatter(FuncFormatter(format_mmss))
    
    # 添加图例和网格
    ax.legend(fontsize=10, title='日志时间点')
    ax.grid(axis='y', alpha=0.3)
    
    # 调整布局并保存
    plt.tight_layout()
    chart_filename = f'new_time_diff_analysis_{timestamp_str}.png'
    chart_path = output_path / chart_filename
    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
    print(f"✅ new类型时间差分析图已保存: {chart_path}")
    plt.close()

"""生成db/new类型漏圈csv"""
def generate_time_interval_csv(data, output_dir, data_type):
    # 第一步：收集所有数据数量>=4的id的前4个时间戳
    position_timestamps = {1: [], 2: [], 3: [], 4: []}  # 存储每个位置的时间戳
    
    for pid, records in data.items():
        if len(records) >= 4:
            # 按时间戳排序并取前4个
            sorted_records = sorted(records, key=lambda x: x['timestamp'])[:4]
            # 记录每个位置的时间戳
            for i, record in enumerate(sorted_records, 1):
                position_timestamps[i].append(record['timestamp'])
    
    # 如果没有足够的合格数据，无法生成有效区间
    if not any(position_timestamps.values()):
        print(f"警告：没有数据数量>=4的id，无法生成{data_type}类型的时间区间CSV")
        return
    
    # 第二步：计算每个位置的平均时间和区间
    intervals = {}
    for pos in range(1, 5):
        timestamps = position_timestamps[pos]
        if not timestamps:
            intervals[pos] = (None, None)
            continue
        
        # 计算平均时间
        total_seconds = sum((ts - timestamps[0]).total_seconds() for ts in timestamps)
        avg_seconds = total_seconds / len(timestamps)
        avg_time = timestamps[0] + timedelta(seconds=avg_seconds)
        
        # 生成上下10秒的区间
        interval_start = avg_time - timedelta(seconds=10)
        interval_end = avg_time + timedelta(seconds=10)
        intervals[pos] = (interval_start, interval_end)
    
    # 第三步：处理所有id，检查每个时间戳属于哪个区间
    results = []
    for pid, records in data.items():
        # 对记录按时间戳排序
        sorted_records = sorted(records, key=lambda x: x['timestamp'])
        
        # 记录每个区间的匹配情况
        interval_matches = [None] * 4
        
        for record in sorted_records:
            ts = record['timestamp']
            # 检查属于哪个区间
            for pos in range(1, 5):
                start, end = intervals[pos]
                if start and end and start <= ts <= end and interval_matches[pos-1] is None:
                    interval_matches[pos-1] = ts.strftime('%Y-%m-%d %H:%M:%S')
                    break
        
        # 对于未匹配的区间，标记为"空（漏圈）"
        has_missing = False
        for i in range(4):
            if interval_matches[i] is None:
                interval_matches[i] = "空（漏圈）"
                has_missing = True  # 标记存在漏圈
        
        # 新增：只有存在漏圈时才保留该行数据
        if has_missing:
            results.append([pid] + interval_matches)
    # 按ID升序排列（处理ID为数字字符串和包含"未知-"前缀的情况）
    def sort_key(row):
        pid = row[0]
        # 处理包含"未知-"前缀的ID
        if isinstance(pid, str) and pid.startswith('未知-'):
            suffix = pid.replace('未知-', '')
            if suffix.isdigit():
                return (1, int(suffix))  # 使用元组，第一个元素表示类型（1=未知-前缀）
            else:
                return (2, pid)  # 非数字的未知-ID排在最后
        else:
            # 尝试将ID转为整数排序
            try:
                return (0, int(pid))  # 使用元组，第一个元素表示类型（0=普通数字）
            except (ValueError, TypeError):
                return (2, str(pid))  # 非数字ID排在最后
    
    results.sort(key=sort_key)
    # 第四步：生成CSV文件
    date_str = datetime.now().strftime("%Y%m%d")
    output_path = Path(output_dir) / date_str
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 生成时间戳（用于文件名）
    timestamp_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    csv_file = output_path / f'{data_type}_time_interval_analysis_{timestamp_str}.csv'
    with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        # 写入表头
        writer.writerow(['id', '第一个数据时间段', '第二个数据时间段', '第三个数据时间段', '第四个数据时间段'])
        # 写入数据
        for row in results:
            writer.writerow(row)
    
    print(f"✅ {data_type}类型时间区间分析CSV已保存: {csv_file}")
    print(f"📊 共保留 {len(results)} 条存在漏圈的记录")

def print_id_statistics(data, sim_data, db_sim_data, new_sim_data, s_db_sim_data, s_new_sim_data):
    """打印各数据结构中id的数量总数、具体值及每个ID对应的记录数量（针对字典类型）"""
    print("\n" + "="*80)
    print("ID统计信息：")
    
    # 处理data（字典）：打印ID总数、具体ID及每个ID对应的记录数量
    print(f"\n【data】")
    data_ids = list(data.keys())
    print(f"  ID总数: {len(data_ids)}")
    print(f"  所有ID: {data_ids}")
    print(f"  各ID对应的记录数量：")
    # 定义排序函数：处理包含"未知-"前缀的ID
    def sort_key(x):
        if x.startswith('未知-'):
            # 去掉"未知-"前缀后检查是否是数字
            suffix = x.replace('未知-', '')
            if suffix.isdigit():
                return int(suffix)
            else:
                return float('inf')
        else:
            # 直接检查是否是数字
            if x.isdigit():
                return int(x)
            else:
                return float('inf')
    
    for pid in sorted(data_ids, key=sort_key):
        record_count = len(data[pid])
        print(f"    - ID: {pid} → 记录数量: {record_count}")
    
    # 处理sim_data（字典）：打印ID总数、具体ID及每个ID对应的记录数量
    print(f"\n【sim_data】")
    sim_data_ids = list(sim_data.keys())
    print(f"  ID总数: {len(sim_data_ids)}")
    print(f"  所有ID: {sim_data_ids}")
    print(f"  各ID对应的记录数量（sim >= 0.75）：")
    for pid in sorted(sim_data_ids, key=sort_key):
        record_count = len(sim_data[pid])
        print(f"    - ID: {pid} → 有效记录数量: {record_count}")
    
     # 处理db_sim_data（字典）：打印ID总数、具体ID及每个ID对应的记录数量
    print(f"\n【db_sim_data】")
    db_sim_ids = list(db_sim_data.keys())
    print(f"  ID总数: {len(db_sim_ids)}")
    print(f"  所有ID: {db_sim_ids}")
    print(f"  各ID对应的db类型记录数量：")
    for pid in sorted(db_sim_ids, key=sort_key):
        record_count = len(db_sim_data[pid])
        print(f"    - ID: {pid} → db记录数量: {record_count}")
    
    # 处理new_sim_data（字典）：打印ID总数、具体ID及每个ID对应的记录数量
    print(f"\n【new_sim_data】")
    new_sim_ids = list(new_sim_data.keys())
    print(f"  ID总数: {len(new_sim_ids)}")
    print(f"  所有ID: {new_sim_ids}")
    print(f"  各ID对应的new类型记录数量：")
    for pid in sorted(new_sim_ids, key=sort_key):
        record_count = len(new_sim_data[pid])
        print(f"    - ID: {pid} → new记录数量: {record_count}")
    
    # 处理s_db_sim_data（字典）：与db_sim_data格式一致（时间窗口过滤后）
    print(f"\n【s_db_sim_data】（时间窗口过滤后）")
    s_db_sim_ids = list(s_db_sim_data.keys())
    print(f"  ID总数: {len(s_db_sim_ids)}")
    print(f"  所有ID: {s_db_sim_ids}")
    print(f"  各ID对应的db类型过滤后记录数量：")
    for pid in sorted(s_db_sim_ids, key=sort_key):
        record_count = len(s_db_sim_data[pid])
        print(f"    - ID: {pid} → 过滤后db记录数量: {record_count}")
    # 总记录数：所有id的记录数之和
    total_s_db = sum(len(records) for records in s_db_sim_data.values())
    print(f"  总记录数: {total_s_db}")
    
    # 处理s_new_sim_data（字典）：与new_sim_data格式一致（时间窗口过滤后）
    print(f"\n【s_new_sim_data】（时间窗口过滤后）")
    s_new_sim_ids = list(s_new_sim_data.keys())
    print(f"  ID总数: {len(s_new_sim_ids)}")
    print(f"  所有ID: {s_new_sim_ids}")
    print(f"  各ID对应的new类型过滤后记录数量：")
    for pid in sorted(s_new_sim_ids, key=sort_key):
        record_count = len(s_new_sim_data[pid])
        print(f"    - ID: {pid} → 过滤后new记录数量: {record_count}")
    # 总记录数：所有id的记录数之和
    total_s_new = sum(len(records) for records in s_new_sim_data.values())
    print(f"  总记录数: {total_s_new}")
    
    print("\n" + "="*80)

def main():
    parser = argparse.ArgumentParser(description='APP+Camera日志联动分析工具')
    parser.add_argument('app_log', type=str, help='APP日志文件路径')
    parser.add_argument('camera_log', type=str, help='Camera日志文件路径')
    parser.add_argument('distance', type=int, help='跑步距离（100/200/400米）')
    parser.add_argument('--app-start', type=parse_time, 
                        help='APP日志开始时间（格式：YYYY-MM-DD HH:MM:SS，不提供则使用全部日志）')
    parser.add_argument('--app-end', type=parse_time,
                        help='APP日志结束时间（格式：YYYY-MM-DD HH:MM:SS，不提供则使用全部日志）')
    parser.add_argument('--camera-start', type=parse_time,
                        help='Camera日志开始时间（格式：YYYY-MM-DD HH:MM:SS，不提供则使用全部日志）')
    parser.add_argument('--camera-end', type=parse_time,
                        help='Camera日志结束时间（格式：YYYY-MM-DD HH:MM:SS，不提供则使用全部日志）')

    parser.add_argument('--output-dir', type=str, default='allure-report/log_analysis',
                        help='输出目录（默认：allure-report/log_analysis）')
    
    args = parser.parse_args()
    
    # 验证APP时间范围（仅当两者都提供时）
    if args.app_start is not None and args.app_end is not None:
        if args.app_start >= args.app_end:
            print("错误：APP日志开始时间不能晚于结束时间")
            return
    
    # 验证Camera时间范围（仅当两者都提供时）
    if args.camera_start is not None and args.camera_end is not None:
        if args.camera_start >= args.camera_end:
            print("错误：Camera日志开始时间不能晚于结束时间")
            return
    
    # 解析APP日志获取人员信息和基准时间
    person_ids, base_time, name_tid_map = parse_app_log(
        Path(args.app_log),
        app_start=args.app_start,
        app_end=args.app_end
    )
    if not person_ids or not base_time:
        print("错误：缺少有效人员ID或基准时间，分析终止")
        return
    
    # 验证跑步距离
    time_threshold, err = validate_distance(args.distance)
    if err:
        print(f"错误：{err}，分析终止")
        return
    
    # 提取Camera日志数据
    data = extract_camera_data(
        Path(args.camera_log), 
        target_ids=person_ids,
        camera_start=args.camera_start,
        camera_end=args.camera_end
    )
    if not data:
        print("无匹配的Camera日志数据，分析终止")
        return
    
    # 按sim值过滤
    sim_data = filter_by_sim(data)
    if not any(sim_data.values()):  # 检查是否所有id的记录都为空
        print("无有效sim数据（sim >= 0.75），分析终止")
        return
    
    # 按类型分割（从字典的所有记录中收集db和new类型）
    db_sim_data, new_sim_data = split_by_type(sim_data)
    # 按时间窗口过滤
    s_db_sim_data, s_new_sim_data = filter_by_time_window(db_sim_data, new_sim_data, time_threshold)
    print_id_statistics(data, sim_data, db_sim_data, new_sim_data, s_db_sim_data, s_new_sim_data)
    # 生成图表
    testerid_name_map = {v: {'name': k} for k, v in name_tid_map.items()}
    plot_db_time_diff_chart(s_db_sim_data, base_time, args.output_dir, testerid_name_map)
    plot_new_time_diff_chart(s_new_sim_data, base_time, args.output_dir, testerid_name_map)
    #生成CSV
    generate_time_interval_csv(s_db_sim_data, args.output_dir, "db")
    generate_time_interval_csv(s_new_sim_data, args.output_dir, "new")

    print("日志分析完成！")

if __name__ == '__main__':
    main()