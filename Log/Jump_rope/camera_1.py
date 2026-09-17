import re
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from ast import literal_eval
import matplotlib as mpl
import os
import math
import argparse
from datetime import datetime

# ---------------------- 配置matplotlib支持中文 ----------------------
def setup_matplotlib_chinese():
    mpl.rcParams['font.sans-serif'] = ['DejaVu Sans', 'SimHei', 'WenQuanYi Micro Hei', 'Heiti TC']
    mpl.rcParams['axes.unicode_minus'] = False

    if os.name == 'posix' and 'Darwin' in os.uname().sysname:
        try:
            mpl.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC', 'Arial Unicode MS'] + mpl.rcParams[
                'font.sans-serif']
        except:
            pass
    elif os.name == 'nt':
        mpl.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei'] + mpl.rcParams['font.sans-serif']


setup_matplotlib_chinese()


# ---------------------- 第一步：提取data1 ----------------------
def extract_data1_by_keyword(log_file_path):
    data1 = []
    keyword = "frame_info_"
    # 定义需要替换的字符串
    target_str = "pointArraynull"
    replace_str = "pointArray[[0.0,0.0],[0.0,0.0],[0.0,0.0],[0.0,0.0],[0.0,0.0]]"
    replace_count = 0
    try:
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if keyword in line and line:
                    if target_str in line:
                        line = line.replace(target_str, replace_str)
                        replace_count += 1
                    data1.append({
                        "line_num": line_num,
                        "log_content": line
                    })
        print(f"=== 第一步完成 ===")
        print(f"匹配到包含'frame_info_'的日志行数（data1长度）：{len(data1)}")
        print(f"成功替换 'pointArraynull' 为指定数组的行数：{replace_count}")
        return data1
    except FileNotFoundError:
        print(f"致命错误：未找到日志文件！路径：{log_file_path}")
        return []


# ---------------------- 第二步：提取data2----------------------
def process_data2_and_csv(data1, csv_output):
    log_pattern = re.compile(
        r'.*?frame_info_(\d+)_(\d+)_([^_]+)_(-?\d+)_(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})_score(\d+)_pointArray(\[\[.*?\]\])',
        re.DOTALL
    )

    data2_list = []
    for item in data1:
        line = item["log_content"]
        line_num = item["line_num"]

        match = log_pattern.search(line)
        if not match:
            print(f"第{line_num}行：日志格式不匹配，跳过 | 日志片段：{line[:100]}...")
            continue

        try:
            frameid = match.group(1)
            dianwei = match.group(2)
            name = match.group(3)
            testid = match.group(4)
            time = match.group(5)
            score = match.group(6)
            pointArray_str = match.group(7)

            score = int(score) if score.strip().isdigit() else 0

            pointArray = literal_eval(pointArray_str)
            if len(pointArray) < 5:
                pointArray += [[0.0, 0.0]] * (5 - len(pointArray))
            elif len(pointArray) > 5:
                pointArray = pointArray[:5]

            data2_list.append({
                "frameid": int(frameid),
                "dianwei": dianwei,
                "name": name,
                "testid": testid,
                "time": time,
                "score": score,
                "pointArray": pointArray
            })
        except Exception as e:
            print(f"第{line_num}行：字段提取失败，跳过 | 错误：{e} | 日志片段：{line[:100]}...")
            continue

    if not data2_list:
        print("警告：未提取到任何有效data2数据！")
        df_data2 = pd.DataFrame(columns=["frameid", "dianwei", "name", "testid", "time", "pointArray"])
        df_csv = pd.DataFrame(columns=["dianwei", "testid"])
        df_csv.to_csv(csv_output, index=False, encoding='utf-8-sig')
        return df_data2, df_csv

    df_data2 = pd.DataFrame(data2_list)
    df_data2['time'] = pd.to_datetime(df_data2['time'])
    print(f"\n=== 第二步：提取data2完成 ===")
    print(f"原始data2数据条数（无去重）：{len(df_data2)}")

    df_csv = df_data2[["dianwei", "testid"]].drop_duplicates(subset=["dianwei", "testid"])
    df_csv.to_csv(csv_output, index=False, encoding='utf-8-sig')

    print(f"第二步：生成CSV完成 ===")
    print(f"CSV（dianwei+testid去重）数据条数：{len(df_csv)}")
    print(f"CSV文件路径：{csv_output}")

    return df_data2, df_csv


def filter_by_time(df_data2, start_time=None, end_time=None):
    """根据时间范围筛选数据"""
    if start_time is None and end_time is None:
        return df_data2  # 无时间筛选条件，返回原始数据

    # 转换输入时间为datetime类型
    try:
        if start_time:
            start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
        if end_time:
            end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
    except ValueError as e:
        print(f"时间格式错误：{e}，请使用'YYYY-MM-DD HH:MM:SS'格式")
        return df_data2

    # 应用筛选条件
    mask = pd.Series([True] * len(df_data2))
    if start_time:
        mask &= df_data2['time'] >= start_dt
    if end_time:
        mask &= df_data2['time'] <= end_dt

    filtered_df = df_data2[mask].copy()
    print(f"\n=== 时间筛选完成 ===")
    print(f"筛选前数据条数：{len(df_data2)}")
    print(f"筛选后数据条数：{len(filtered_df)}")
    if len(filtered_df) == 0:
        print("警告：筛选后无数据，请检查时间范围是否合适")

    return filtered_df


# ---------------------- 第三步：处理data3----------------------
def process_data3(df_data2):

    if len(df_data2) == 0:
        print("=== 第三步：处理data3 ===")
        print("跳过处理data3：原始data2无有效数据")
        return []
    required_cols = ["testid", "frameid", "pointArray"]
    if not all(col in df_data2.columns for col in required_cols):
        print("=== 第三步：处理data3 ===")
        print("跳过处理data3：data2缺失必需字段")
        return []

    unique_testids = df_data2["testid"].unique()
    print(f"\n=== 第三步：开始处理data3 ===")
    print(f"共有{len(unique_testids)}个唯一的testid需要处理")

    data3_list = []

    for tid in unique_testids:
        # 按frameid排序
        tid_data = df_data2[df_data2["testid"] == tid].sort_values(by='frameid').reset_index(drop=True)
        if len(tid_data) < 2:
            print(f"testid={tid}：数据点不足（{len(tid_data)}条），跳过处理")
            continue

        data3 = {
            "testid": tid,
            "total_records": len(tid_data),
            "frameid_range": f"{tid_data['frameid'].min()} ~ {tid_data['frameid'].max()}",
            "points_data": []  # 每个元素对应一个坐标点的完整数据
        }

        for point_idx in range(5):
            # 提取该坐标点的所有(x,y)对 + frameid
            coords_list = [row["pointArray"][point_idx] for _, row in tid_data.iterrows()]
            frameids = tid_data['frameid'].tolist()

            # 计算每个(x,y)点到原点的欧氏距离（用于绘制波浪线）
            distance_list = [math.hypot(x, y) for x, y in coords_list]

            point_data = {
                "point_index": point_idx + 1,
                "frameids": frameids,  # X轴：帧序号
                "coords_list": coords_list,  # 原始(x,y)坐标对
                "distance_list": distance_list  # 波浪线Y轴：欧氏距离
            }
            data3["points_data"].append(point_data)

        data3_list.append(data3)

        # # 打印校验信息
        # print(f"\n---------- testid={tid} 的data3信息 ----------")
        # print(f"总记录数：{data3['total_records']}")
        # print(f"FrameID范围：{data3['frameid_range']}")
        # for i, point_data in enumerate(data3["points_data"]):
        #     print(f"  坐标点 {point_data['point_index']}:")
        #     print(f"    FrameID示例（前5个）：{point_data['frameids'][:5]}")
        #     print(f"    完整坐标点示例（前5个）：{point_data['coords_list'][:5]}")
        #     print(f"    欧氏距离示例（前5个）：{[round(d, 2) for d in point_data['distance_list'][:5]]}")
        #     print(f"    距离范围：{min(point_data['distance_list']):.2f} ~ {max(point_data['distance_list']):.2f}")

    print(f"\n=== 第三步：处理data3完成 ===")
    print(f"成功生成data3的testid数量：{len(data3_list)}")
    print(f"每个testid包含5个坐标点的完整数据（未拆分XY）")

    return data3_list


# ---------------------- 第四步：绘图（每个子图一个波浪线） ----------------------
def plot_data3(data3_list, output_dir):

    print(f"\n=== 第四步：开始绘图 ===")
    if len(data3_list) == 0:
        print("跳过绘图：data3列表为空")
        return

    os.makedirs(output_dir, exist_ok=True)

    for data3 in data3_list:
        tid = data3["testid"]
        points_data = data3["points_data"]

        # 创建5个子图
        fig, axes = plt.subplots(5, 1, figsize=(12, 20), sharex=True)
        fig.suptitle(f"testid: {tid} 的5个坐标点波浪变化（欧氏距离）", fontsize=16, fontweight='bold', y=0.92)

        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']

        for i, point_data in enumerate(points_data):
            ax = axes[i]
            point_idx = point_data["point_index"]

            # 绘制核心波浪线：FrameID → 欧氏距离（单一曲线，呈现波浪）
            ax.plot(point_data["frameids"], point_data["distance_list"],
                    color=colors[i], label=f'坐标点{point_idx} 欧氏距离',
                    linewidth=2, marker='.', markersize=3)

            # 叠加原始X/Y坐标的散点
            # x_coords = [x for x, y in point_data["coords_list"]]
            # y_coords = [y for x, y in point_data["coords_list"]]
            # ax.scatter(point_data["frameids"], x_coords, color=colors[i], s=5, alpha=0.5, label='X坐标')
            # ax.scatter(point_data["frameids"], y_coords, color='red', s=5, alpha=0.5, label='Y坐标')

            # 子图样式设置
            ax.set_title(f'坐标点 {point_idx}', fontsize=14)
            ax.set_ylabel('欧氏距离', fontsize=12)
            ax.legend(loc='upper right')
            ax.grid(alpha=0.3)

        # 统一设置X轴
        axes[-1].set_xlabel('FrameID（帧序号）', fontsize=12)

        plt.tight_layout()

        # 保存图片
        output_path = f"{output_dir}/testid_{tid}_waveforms_by_distance.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"已保存testid={tid}的波形图至：{output_path}")
        plt.close()

    print(f"\n=== 第四步：绘图完成 ===")
    print(f"共生成{len(data3_list)}张波形图，保存至目录：{output_dir}")


# ---------------------- 第五步：处理data4_list（提取Y坐标） ----------------------
def process_data4(data3_list):
    if not data3_list:
        print("=== 处理data4 ===")
        print("跳过处理data4：data3_list为空")
        return []

    print(f"\n=== 开始处理data4 ===")
    data4_list = []

    for data3 in data3_list:
        tid = data3["testid"]
        # 构建data4的基本信息
        data4 = {
            "testid": tid,
            "total_records": data3["total_records"],
            "frameid_range": data3["frameid_range"],
            "points_data": []  # 每个元素对应一个坐标点的Y坐标数据
        }

        for point_data in data3["points_data"]:
            point_idx = point_data["point_index"]
            frameids = point_data["frameids"]
            # 提取每个坐标对中的Y值
            y_coords_list = [y for x, y in point_data["coords_list"]]

            # 构建该点的data4数据
            data4_point = {
                "point_index": point_idx,
                "frameids": frameids,
                "y_coords_list": y_coords_list  # 仅保留Y坐标列表
            }
            data4["points_data"].append(data4_point)

        data4_list.append(data4)
        print(f"已处理testid={tid}的data4数据")

        # print(f"\n---------- testid={tid} 的data4信息 ----------")
        # print(f"总记录数：{data4['total_records']}")
        # print(f"FrameID范围：{data4['frameid_range']}")
        # for i, point_data in enumerate(data4["points_data"]):
        #     print(f"  坐标点 {point_data['point_index']}:")
        #     print(f"    FrameID示例（前5个）：{point_data['frameids'][:5]}")
        #     print(f"    Y坐标值示例（前5个）：{[round(y, 2) for y in point_data['y_coords_list'][:5]]}")  # 保留2位小数更整洁
        #     print(f"    Y坐标范围：{min(point_data['y_coords_list']):.2f} ~ {max(point_data['y_coords_list']):.2f}")

    print(f"\n=== 处理data4完成 ===")
    print(f"成功生成data4的testid数量：{len(data4_list)}")
    return data4_list


# ---------------------- 第六步：绘制data4波形图（Y坐标） ----------------------
def plot_data4(data4_list, output_dir):
    print(f"\n=== 开始绘制data4波形图 ===")
    if len(data4_list) == 0:
        print("跳过绘图：data4_list为空")
        return

    os.makedirs(output_dir, exist_ok=True)

    for data4 in data4_list:
        tid = data4["testid"]
        points_data = data4["points_data"]

        # 创建5个子图（每个坐标点一个子图）
        fig, axes = plt.subplots(5, 1, figsize=(12, 20), sharex=True)
        fig.suptitle(f"testid: {tid} 的5个坐标点Y坐标变化", fontsize=16, fontweight='bold', y=0.92)

        # 为每个子图分配不同颜色
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']

        for i, point_data in enumerate(points_data):
            ax = axes[i]
            point_idx = point_data["point_index"]

            # 绘制核心曲线：FrameID → Y坐标
            ax.plot(point_data["frameids"], point_data["y_coords_list"],
                    color=colors[i], label=f'坐标点{point_idx} Y坐标',
                    linewidth=2, marker='.', markersize=3)

            # 子图样式设置
            ax.set_title(f'坐标点 {point_idx}', fontsize=14)
            ax.set_ylabel('Y坐标值', fontsize=12)
            ax.legend(loc='upper right')
            ax.grid(alpha=0.3)

        # 统一设置X轴
        axes[-1].set_xlabel('FrameID（帧序号）', fontsize=12)

        plt.tight_layout()

        # 保存图片
        output_path = f"{output_dir}/testid_{tid}_waveforms_by_y.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"已保存testid={tid}的Y坐标波形图至：{output_path}")
        plt.close()

    print(f"\n=== 绘制data4波形图完成 ===")
    print(f"共生成{len(data4_list)}张Y坐标波形图，保存至目录：{output_dir}")

# ---------------------- 第七步：处理data5_list（提取score） ----------------------
def process_data5(df_data2_filtered):
    if len(df_data2_filtered) == 0:
        print("=== 处理data5 ===")
        print("跳过处理data5：过滤后的data2无有效数据")
        return []

    print(f"\n=== 开始处理data5 ===")
    data5_list = []

    # 获取所有唯一testid
    unique_testids = df_data2_filtered["testid"].unique()

    for tid in unique_testids:
        # 按frameid排序当前testid的所有数据
        tid_data = df_data2_filtered[df_data2_filtered["testid"] == tid].sort_values(by='frameid').reset_index(drop=True)
        if len(tid_data) < 1:
            print(f"testid={tid}：无有效score数据，跳过")
            continue

        # 构建data5的核心信息
        data5 = {
            "testid": tid,
            "total_records": len(tid_data),
            "frameid_range": f"{tid_data['frameid'].min()} ~ {tid_data['frameid'].max()}",
            "score_data": {
                "frameids": tid_data['frameid'].tolist(),
                "score_list": tid_data['score'].tolist()  # 已转为数值型的score列表
            }
        }
        data5_list.append(data5)
        print(f"已处理testid={tid}的data5数据（总记录数：{len(tid_data)}）")

    print(f"\n=== 处理data5完成 ===")
    print(f"成功生成data5的testid数量：{len(data5_list)}")
    return data5_list


# ---------------------- 第八步：绘制data5波形图（score分数） ----------------------
def plot_data5(data5_list, output_dir):
    print(f"\n=== 开始绘制data5波形图 ===")
    if len(data5_list) == 0:
        print("跳过绘图：data5_list为空")
        return

    os.makedirs(output_dir, exist_ok=True)

    for data5 in data5_list:
        tid = data5["testid"]
        score_data = data5["score_data"]

        # 创建单个子图（score是单维度，无需5个子图）
        fig, ax = plt.subplots(1, 1, figsize=(12, 6))
        fig.suptitle(f"testid: {tid} 的Score分数变化", fontsize=16, fontweight='bold', y=0.95)

        # 绘制核心曲线：FrameID → Score分数
        ax.plot(score_data["frameids"], score_data["score_list"],
                color='#ff4500', label=f'testid={tid} Score',
                linewidth=2, marker='.', markersize=4)

        # 样式设置
        ax.set_xlabel('FrameID（帧序号）', fontsize=12)
        ax.set_ylabel('Score分数值', fontsize=12)
        ax.legend(loc='upper right')
        ax.grid(alpha=0.3)
        ax.set_ylim(bottom=0)  # Score通常非负，限定Y轴下限

        plt.tight_layout()

        # 保存图片
        output_path = f"{output_dir}/testid_{tid}_waveforms_by_score.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"已保存testid={tid}的Score波形图至：{output_path}")
        plt.close()

    print(f"\n=== 绘制data5波形图完成 ===")
    print(f"共生成{len(data5_list)}张Score波形图，保存至目录：{output_dir}")



# ---------------------- 主函数 ----------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="处理跳绳相机日志文件")
    parser.add_argument('app_log', type=str, help='APP日志文件路径（例如：1.log、./logs/2.log）')
    parser.add_argument('--start_time', type=str, nargs='?',
                        help='开始时间，格式：YYYY-MM-DD HH:MM:SS（可选）')
    parser.add_argument('--end_time', type=str, nargs='?',
                        help='结束时间，格式：YYYY-MM-DD HH:MM:SS（可选）')
    args = parser.parse_args()
    #输入
    LOG_FILE = args.app_log
    start_time = args.start_time
    end_time = args.end_time
    #输出
    current_time = datetime.now().strftime("%Y_%m_%d_%H.%M")
    # BASE_OUTPUT_DIR = "./allure-report/log_analysis/waveform_plots"
    # OUTPUT_DIR = os.path.join(BASE_OUTPUT_DIR, current_time)
    # os.makedirs(OUTPUT_DIR, exist_ok=True)
    # CSV_OUTPUT = os.path.join(OUTPUT_DIR, "dianwei_testid.csv")
    # IMG_OUTPUT_DIR = OUTPUT_DIR
    current_script_path = os.path.abspath(__file__)
    current_script_dir = os.path.dirname(current_script_path)
    log_dir = os.path.dirname(current_script_dir)
    project_root_dir = os.path.dirname(log_dir)
    BASE_OUTPUT_DIR = os.path.join(
        project_root_dir,
        "allure-report",
        "log_analysis",
        "waveform_plots"
    )
    OUTPUT_DIR = os.path.join(BASE_OUTPUT_DIR, current_time)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    CSV_OUTPUT = os.path.join(OUTPUT_DIR, "dianwei_testid.csv")
    IMG_OUTPUT_DIR = OUTPUT_DIR
    #侏罗纪
    data1 = extract_data1_by_keyword(LOG_FILE)
    if not data1:
        print("无匹配的日志行，程序结束")
        exit()
    df_data2, df_csv = process_data2_and_csv(data1, CSV_OUTPUT)
    df_data2_filtered = filter_by_time(df_data2, start_time, end_time)

    data3_list = process_data3(df_data2_filtered)
    # plot_data3(data3_list, IMG_OUTPUT_DIR)
    data4_list = process_data4(data3_list)
    plot_data4(data4_list, IMG_OUTPUT_DIR)
    data5_list = process_data5(df_data2_filtered)
    plot_data5(data5_list, IMG_OUTPUT_DIR)
