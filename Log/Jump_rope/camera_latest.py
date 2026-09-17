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
# 设置中文字体
def setup_matplotlib_chinese():
    """根据操作系统自动配置matplotlib中文字体"""
    mpl.rcParams['font.sans-serif'] = ['DejaVu Sans', 'SimHei', 'WenQuanYi Micro Hei', 'Heiti TC']
    mpl.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

    # 根据操作系统类型调整字体优先级
    if os.name == 'posix':
        try:
            if 'Darwin' in os.uname().sysname:
                mpl.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC', 'Arial Unicode MS'] + mpl.rcParams['font.sans-serif']
            else:
                mpl.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'WenQuanYi Micro Hei'] + mpl.rcParams['font.sans-serif']
        except:
            pass
    elif os.name == 'nt':
        mpl.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei'] + mpl.rcParams['font.sans-serif']


setup_matplotlib_chinese()


# ---------------------- 第一步：提取data1 ----------------------
def extract_data1_by_keyword(log_file_path):
    data1 = []
    keyword = "frame_info_"
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

    if data2_list:
        # 判断所有testid是否都为"-1"
        # all_testid_is_minus1 = all(item["testid"] == "-1" for item in data2_list)
        # if all_testid_is_minus1:
        #     print("检测到所有testid均为-1，将dianwei的值赋值给testid")
        # 判断所有testid是否都不为"0"
        all_testid_is_minus1 = all(item["testid"] != "0" for item in data2_list)
        if all_testid_is_minus1:
            # print("检测到所有testid均为-1，将dianwei的值赋值给testid")
            print("检测到所有testid均不为0，将dianwei的值赋值给testid")
            # 遍历替换testid为dianwei的值
            for item in data2_list:
                item["testid"] = item["dianwei"]
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

    try:
        if start_time:
            start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
        if end_time:
            end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
    except ValueError as e:
        print(f"时间格式错误：{e}，请使用'YYYY-MM-DD HH:MM:SS'格式")
        return df_data2

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
# def filter_by_time(df_data2, start_time=None, end_time=None):
#     """根据时间范围筛选数据"""
#     if start_time is None and end_time is None:
#         # # 无时间筛选条件，先检查是否需要替换testid
#         # if not df_data2.empty:
#         #     # 判断所有testid是否都为"-1"
#         #     all_testid_is_minus1 = all(str(item) == "-1" for item in df_data2['testid'])
#         #     if all_testid_is_minus1:
#         #         print("检测到所有testid均为-1，将dianwei的值赋值给testid")
#         #         df_data2['testid'] = df_data2['dianwei']
#         return df_data2  # 无时间筛选条件，返回原始数据
#
#     # 转换输入时间为datetime类型
#     try:
#         if start_time:
#             start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
#         if end_time:
#             end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
#     except ValueError as e:
#         print(f"时间格式错误：{e}，请使用'YYYY-MM-DD HH:MM:SS'格式")
#         # 格式错误时也检查并替换testid
#         if not df_data2.empty:
#             all_testid_is_minus1 = all(str(item) == "-1" for item in df_data2['testid'])
#             if all_testid_is_minus1:
#                 print("检测到所有testid均为-1，将dianwei的值赋值给testid")
#                 df_data2['testid'] = df_data2['dianwei']
#         return df_data2
#
#     # 应用筛选条件
#     mask = pd.Series([True] * len(df_data2))
#     if start_time:
#         mask &= df_data2['time'] >= start_dt
#     if end_time:
#         mask &= df_data2['time'] <= end_dt
#
#     filtered_df = df_data2[mask].copy()
#
#     # 筛选后应用testid替换逻辑
#     if not filtered_df.empty:
#         # 判断筛选后的数据中所有testid是否都为"-1"
#         all_testid_is_minus1 = all(str(item) == "-1" for item in filtered_df['testid'])
#         if all_testid_is_minus1:
#             print("时间筛选后检测到所有testid均为-1，将dianwei的值赋值给testid")
#             filtered_df['testid'] = filtered_df['dianwei']
#
#     print(f"\n=== 时间筛选完成 ===")
#     print(f"筛选前数据条数：{len(df_data2)}")
#     print(f"筛选后数据条数：{len(filtered_df)}")
#     if len(filtered_df) == 0:
#         print("警告：筛选后无数据，请检查时间范围是否合适")
#
#     return filtered_df


# ---------------------- 第三步：处理data3----------------------
def process_data3(df_data2):
    if len(df_data2) == 0:
        print("=== 第三步：处理data3 ===")
        print("跳过处理data3：原始data2无有效数据")
        return []
    required_cols = ["testid", "frameid", "pointArray", "score"]
    if not all(col in df_data2.columns for col in required_cols):
        print("=== 第三步：处理data3 ===")
        print("跳过处理data3：data2缺失必需字段")
        return []

    unique_testids = df_data2["testid"].unique()
    print(f"\n=== 第三步：开始处理data3 ===")
    print(f"共有{len(unique_testids)}个唯一的testid需要处理")

    data3_list = []

    for tid in unique_testids:
        tid_data = df_data2[df_data2["testid"] == tid].sort_values(by='frameid').reset_index(drop=True)
        if len(tid_data) < 2:
            print(f"testid={tid}：数据点不足（{len(tid_data)}条），跳过处理")
            continue

        data3 = {
            "testid": tid,
            "total_records": len(tid_data),
            "frameid_range": f"{tid_data['frameid'].min()} ~ {tid_data['frameid'].max()}",
            "points_data": [],  # 每个元素对应一个坐标点的完整数据
            "score_list": tid_data['score'].tolist(),
            "frameids_full": tid_data['frameid'].tolist()
        }

        for point_idx in range(5):
            coords_list = [row["pointArray"][point_idx] for _, row in tid_data.iterrows()]
            frameids = tid_data['frameid'].tolist()

            distance_list = [math.hypot(x, y) for x, y in coords_list]

            point_data = {
                "point_index": point_idx + 1,
                "frameids": frameids,
                "coords_list": coords_list,
                "distance_list": distance_list
            }
            data3["points_data"].append(point_data)

        data3_list.append(data3)

    print(f"\n=== 第三步：处理data3完成 ===")
    print(f"成功生成data3的testid数量：{len(data3_list)}")
    print(f"每个testid包含5个坐标点的完整数据（未拆分XY）+ score列表")

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

            ax.plot(point_data["frameids"], point_data["distance_list"],
                    color=colors[i], label=f'坐标点{point_idx} 欧氏距离',
                    linewidth=2, marker='.', markersize=3)

            ax.set_title(f'坐标点 {point_idx}', fontsize=14)
            ax.set_ylabel('欧氏距离', fontsize=12)
            ax.legend(loc='upper right')
            ax.grid(alpha=0.3)

        axes[-1].set_xlabel('FrameID（帧序号）', fontsize=12)

        plt.tight_layout()

        # 保存图片
        output_path = f"{output_dir}/testid_{tid}_waveforms_by_distance.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"已保存testid={tid}的波形图至：{output_path}")
        plt.close()

    print(f"\n=== 第四步：绘图完成 ===")
    print(f"共生成{len(data3_list)}张波形图，保存至目录：{output_dir}")


# ---------------------- 第五步：处理data4_list（提取Y坐标 + 关联score变化帧ID） ----------------------
def process_data4(data3_list, data5_list):

    if not data3_list:
        print("=== 处理data4 ===")
        print("跳过处理data4：data3_list为空")
        return []

    score_change_frame_map = {}
    for data5 in data5_list:
        score_change_frame_map[data5["testid"]] = data5["score_change_frameids"]

    print(f"\n=== 开始处理data4 ===")
    data4_list = []

    for data3 in data3_list:
        tid = data3["testid"]
        data4 = {
            "testid": tid,
            "total_records": data3["total_records"],
            "frameid_range": data3["frameid_range"],
            "score_change_frameids": score_change_frame_map.get(tid, []),
            "points_data": []
        }

        for point_data in data3["points_data"]:
            point_idx = point_data["point_index"]
            frameids = point_data["frameids"]
            y_coords_list = [y for x, y in point_data["coords_list"]]

            data4_point = {
                "point_index": point_idx,
                "frameids": frameids,
                "y_coords_list": y_coords_list
            }
            data4["points_data"].append(data4_point)

        data4_list.append(data4)
        print(f"已处理testid={tid}的data4数据（关联{len(data4['score_change_frameids'])}个score变化帧ID）")

    print(f"\n=== 处理data4完成 ===")
    print(f"成功生成data4的testid数量：{len(data4_list)}")
    return data4_list


# ---------------------- 第六步：绘制data4波形图（Y坐标 + 标记score变化帧ID虚线） ----------------------
def plot_data4(data4_list, output_dir):
    print(f"\n=== 开始绘制data4波形图 ===")
    if len(data4_list) == 0:
        print("跳过绘图：data4_list为空")
        return

    os.makedirs(output_dir, exist_ok=True)

    for data4 in data4_list:
        tid = data4["testid"]
        points_data = data4["points_data"]
        score_change_frameids = data4["score_change_frameids"]  # 获取score变化的帧ID

        # 创建5个子图（每个坐标点一个子图）
        fig, axes = plt.subplots(5, 1, figsize=(12, 20), sharex=True)
        fig.suptitle(f"testid: {tid} 的5个坐标点Y坐标变化（Score变化帧ID标记）", fontsize=16, fontweight='bold', y=0.92)

        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#8c564b', '#9467bd']

        for i, point_data in enumerate(points_data):
            ax = axes[i]
            point_idx = point_data["point_index"]

            ax.plot(point_data["frameids"], point_data["y_coords_list"],
                    color=colors[i], label=f'坐标点{point_idx} Y坐标',
                    linewidth=0.6, marker='.', markersize=0.9)

            # # 绘制score变化帧ID的垂直虚线
            # for frame_id in score_change_frameids:
            #     ax.axvline(x=frame_id, color='red', linestyle='--', linewidth=1.5, alpha=0.7,
            #                label='Score变化帧' if i == 0 else "")
            for idx, frame_id in enumerate(score_change_frameids):
                label_text = 'Score变化帧' if (i == 0 and idx == 0) else ""
                ax.axvline(x=frame_id, color='red', linestyle='--', linewidth=0.5, alpha=0.5, label=label_text)

            ax.set_title(f'坐标点 {point_idx}', fontsize=14)
            ax.set_ylabel('Y坐标值', fontsize=12)
            if i == 0:
                ax.legend(loc='upper right')
            else:
                ax.legend().remove()
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


# ---------------------- 第七步：处理data5_list（提取score + 识别score变化的帧ID） ----------------------
def process_data5(df_data2_filtered):
    if len(df_data2_filtered) == 0:
        print("=== 处理data5 ===")
        print("跳过处理data5：过滤后的data2无有效数据")
        return []

    print(f"\n=== 开始处理data5 ===")
    data5_list = []

    unique_testids = df_data2_filtered["testid"].unique()

    for tid in unique_testids:
        tid_data = df_data2_filtered[df_data2_filtered["testid"] == tid].sort_values(by='frameid').reset_index(
            drop=True)
        if len(tid_data) < 1:
            print(f"testid={tid}：无有效score数据，跳过")
            continue

        score_list = tid_data['score'].tolist()
        frameids_list = tid_data['frameid'].tolist()
        score_change_frameids = []

        for i in range(1, len(score_list)):
            if score_list[i] != score_list[i - 1]:
                score_change_frameids.append(frameids_list[i])  # 记录变化帧的ID

        data5 = {
            "testid": tid,
            "total_records": len(tid_data),
            "frameid_range": f"{tid_data['frameid'].min()} ~ {tid_data['frameid'].max()}",
            "score_data": {
                "frameids": frameids_list,
                "score_list": score_list  # 已转为数值型的score列表
            },
            "score_change_frameids": score_change_frameids
        }
        data5_list.append(data5)
        print(f"已处理testid={tid}的data5数据（总记录数：{len(tid_data)}，score变化帧ID数量：{len(score_change_frameids)}）")

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
        score_change_frameids = data5["score_change_frameids"]
        frameids = score_data["frameids"]
        score_list = score_data["score_list"]

        max_segments = []
        current_segment_scores = []
        current_segment_frameids = []

        for idx, (score, fid) in enumerate(zip(score_list, frameids)):
            if score == 0:
                # 处理当前分段
                if current_segment_scores:
                    max_score = max(current_segment_scores)
                    max_idx = current_segment_scores.index(max_score)
                    max_fid = current_segment_frameids[max_idx]
                    max_segments.append({"max_score": max_score, "max_fid": max_fid})
                    # 重置分段
                    current_segment_scores = []
                    current_segment_frameids = []
            else:
                current_segment_scores.append(score)
                current_segment_frameids.append(fid)

        if current_segment_scores:
            max_score = max(current_segment_scores)
            max_idx = current_segment_scores.index(max_score)
            max_fid = current_segment_frameids[max_idx]
            max_segments.append({"max_score": max_score, "max_fid": max_fid})

        fig, ax = plt.subplots(1, 1, figsize=(12, 6))
        fig.suptitle(f"testid: {tid} 的Score分数变化", fontsize=16, fontweight='bold', y=0.95)

        ax.plot(score_data["frameids"], score_data["score_list"],
                color='#ff4500', label=f'testid={tid} Score',
                linewidth=2, marker='.', markersize=4)

        for idx, seg in enumerate(max_segments):
            max_score = seg["max_score"]
            max_fid = seg["max_fid"]

            ax.scatter(max_fid, max_score, color='red', s=50, zorder=5,
                       label=f'第{idx + 1}段最大值' if idx == 0 else "")

            ax.text(max_fid, max_score + (max_score * 0.05 if max_score != 0 else 1),
                    f'最大值: {max_score}\n帧ID: {max_fid}',
                    fontsize=10, ha='center', va='bottom',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))

        # # 标记score变化的帧ID
        # for frame_id in score_change_frameids:
        #     ax.axvline(x=frame_id, color='red', linestyle='--', linewidth=1.5, alpha=0.7,
        #                label='Score变化帧' if frame_id == score_change_frameids[0] else "")

        # 样式设置
        ax.set_xlabel('FrameID（帧序号）', fontsize=12)
        ax.set_ylabel('Score分数值', fontsize=12)
        handles, labels = ax.get_legend_handles_labels()
        # ax.legend(loc='upper right')
        ax.legend(handles, labels, loc='upper right')
        ax.grid(alpha=0.3)
        ax.set_ylim(bottom=0)  # Score非负，限定Y轴下限

        plt.tight_layout()

        output_path = f"{output_dir}/testid_{tid}_waveforms_by_score.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"已保存testid={tid}的Score波形图至：{output_path}")
        plt.close()

    print(f"\n=== 绘制data5波形图完成 ===")
    print(f"共生成{len(data5_list)}张Score波形图，保存至目录：{output_dir}")


# ---------------------- 第九步：生成交互式网页展示（汇总大图+虚线标记帧ID+5独立图+加宽+工具栏放大+固定Y轴0-5000） ----------------------
def process_web_data(data4_list, data5_list):
    """整理网页展示所需的结构化数据"""
    if not data4_list or not data5_list:
        print("=== 处理网页展示数据 ===")
        print("跳过处理网页数据：data4_list或data5_list为空")
        return {}

    web_data = {}
    data5_map = {item["testid"]: item for item in data5_list}

    for data4 in data4_list:
        tid = data4["testid"]
        if tid not in data5_map:
            print(f"警告：testid={tid} 无对应的score数据，跳过")
            continue


        y_points_data = []
        for point_data in data4["points_data"]:
            y_points_data.append({
                "point_index": point_data["point_index"],
                "frameids": point_data["frameids"],
                "y_coords": point_data["y_coords_list"]
            })

        data5 = data5_map[tid]
        score_data = {
            "frameids": data5["score_data"]["frameids"],
            "score_list": data5["score_data"]["score_list"],
            "score_change_frameids": data5["score_change_frameids"],
            "max_segments": []
        }

        score_list = data5["score_data"]["score_list"]
        frameids_list = data5["score_data"]["frameids"]
        current_segment_scores = []
        current_segment_frameids = []
        for idx, (score, fid) in enumerate(zip(score_list, frameids_list)):
            if score == 0:
                if current_segment_scores:
                    max_score = max(current_segment_scores)
                    max_idx = current_segment_scores.index(max_score)
                    max_fid = current_segment_frameids[max_idx]
                    score_data["max_segments"].append({
                        "max_score": max_score,
                        "max_fid": max_fid
                    })
                    current_segment_scores = []
                    current_segment_frameids = []
            else:
                current_segment_scores.append(score)
                current_segment_frameids.append(fid)
        if current_segment_scores:
            max_score = max(current_segment_scores)
            max_idx = current_segment_scores.index(max_score)
            max_fid = current_segment_frameids[max_idx]
            score_data["max_segments"].append({
                "max_score": max_score,
                "max_fid": max_fid
            })

        web_data[tid] = {
            "testid": tid,
            "total_records": data4["total_records"],
            "frameid_range": data4["frameid_range"],
            "y_points_data": y_points_data,
            "score_data": score_data
        }

    print(f"\n=== 处理网页展示数据完成 ===")
    print(f"可展示的testid数量：{len(web_data)}")
    return web_data


def generate_web_page(web_data, output_dir):
    """生成交互式网页文件（HTML+JS）- 汇总大图带虚线+5独立图+Y轴0-5000固定"""
    if not web_data:
        print("跳过生成网页：无可用的web展示数据")
        return

    html_template = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>跳绳相机日志分析 - 交互式波形图</title>
    <script src="https://cdn.plot.ly/plotly-2.20.0.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
        }
        body {
            display: flex;
            height: 100vh;
            overflow: hidden;
        }
        /* 左侧testid导航栏 */
        .testid-sidebar {
            width: 280px;
            background: #f5f5f5;
            border-right: 1px solid #ddd;
            padding: 20px;
            overflow-y: auto;
        }
        .testid-sidebar h2 {
            font-size: 18px;
            margin-bottom: 20px;
            color: #333;
            border-bottom: 1px solid #ddd;
            padding-bottom: 10px;
        }
        .testid-item {
            padding: 10px 15px;
            margin-bottom: 8px;
            background: white;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s;
            border-left: 3px solid #ccc;
        }
        .testid-item:hover {
            background: #e8f4f8;
            border-left-color: #4299e1;
        }
        .testid-item.active {
            background: #4299e1;
            color: white;
            border-left-color: #2563eb;
        }
        /* 右侧图表区域 */
        .chart-container {
            flex: 1;
            padding: 20px;
            display: flex;
            flex-direction: column;
            overflow-y: auto;
            background: #fff;
            width: calc(100% - 280px) !important;
        }
        .chart-tabs {
            margin-bottom: 20px;
            display: flex;
            gap: 10px;
        }
        .chart-tab {
            padding: 10px 20px;
            background: #f5f5f5;
            border: 1px solid #ddd;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .chart-tab.active {
            background: #4299e1;
            color: white;
            border-color: #4299e1;
        }
        .chart-wrapper {
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 20px;
            padding: 10px;
            width: 100% !important;
        }
        /* 图表容器样式 统一 */
        .single-chart-card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            background: white;
            width: 100% !important;
            min-height: 400px !important;
            margin: 0 auto !important;
        }
        /* 汇总大图和Score图专属尺寸（两者完全一致） */
        .big-chart-card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            background: white;
            width: 100% !important;
            min-height: 600px !important;
            margin: 0 auto !important;
        }
        .testid-info {
            margin-bottom: 15px;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 6px;
            font-size: 14px;
            color: #333;
        }
        /* 核心：图表宽高调整（加宽） */
        .plotly-graph-div {
            height: 380px !important;
            width: 100% !important;
            min-width: 900px !important;
        }
        /* 汇总大图/Score图 专属高度（两者尺寸完全一致） */
        .big-plot-div {
            height: 580px !important;
            width: 100% !important;
            min-width: 900px !important;
        }
        /* ========== Plotly工具栏放大样式 ========== */
        .modebar {
            height: 46px !important;
            padding: 0 8px !important;
        }
        .modebar-btn {
            width: 42px !important;
            height: 42px !important;
            font-size: 20px !important;
            margin: 0 4px !important;
        }
        .modebar-btn svg {
            width: 22px !important;
            height: 22px !important;
            margin: auto !important;
        }
        .modebar-btn:hover {
            background-color: #e1e5ea !important;
            border-radius: 6px !important;
        }
        /* 图表字体优化 */
        .plotly .xtick, .plotly .ytick {
            font-size: 13px !important;
        }
        .plotly .gtitle, .plotly .xaxis-title, .plotly .yaxis-title {
            font-size: 14px !important;
        }
    </style>
</head>
<body>
    <!-- 左侧testid导航 -->
    <div class="testid-sidebar">
        <h2>TestID 列表</h2>
        <div id="testid-list">
            <!-- JS动态生成testid项 -->
        </div>
    </div>

    <!-- 右侧图表区域 -->
    <div class="chart-container">
        <div class="testid-info" id="testid-info">
            请选择左侧的TestID查看波形图
        </div>
        <div class="chart-tabs">
            <div class="chart-tab active" data-tab="y-coord">Y坐标波形图</div>
            <div class="chart-tab" data-tab="score">Score波形图</div>
        </div>
        <div class="chart-wrapper" id="chart-wrapper">
            <!-- Plotly图表容器：动态生成汇总大图 + 5个独立Y坐标图 / 1个Score图 -->
        </div>
    </div>

    <script>
        // 网页展示数据（由Python传入）
        const webData = {web_data_json};
        const testids = Object.keys(webData);
        let currentTestID = testids[0] || "";
        let currentTab = "y-coord"; // 默认显示Y坐标
        const colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd'];//颜色统一，一一对应

        // 初始化左侧testid列表
        function initTestIDList() {
            const testidListEl = document.getElementById("testid-list");
            if (!testidListEl || testids.length === 0) return;

            testids.forEach(tid => {
                const itemEl = document.createElement("div");
                itemEl.className = "testid-item" + (tid === currentTestID ? " active" : "");
                itemEl.textContent = `TestID: ${tid}`;
                itemEl.dataset.testid = tid;
                itemEl.onclick = () => switchTestID(tid);
                testidListEl.appendChild(itemEl);
            });
        }

        // 切换testid
        function switchTestID(tid) {
            document.querySelectorAll(".testid-item").forEach(el => {
                el.classList.remove("active");
                if (el.dataset.testid === tid) el.classList.add("active");
            });
            currentTestID = tid;
            updateTestIDInfo();
            renderChart();
        }

        // 切换图表标签（Y坐标/Score）
        function switchChartTab(tab) {
            document.querySelectorAll(".chart-tab").forEach(el => {
                el.classList.remove("active");
                if (el.dataset.tab === tab) el.classList.add("active");
            });
            currentTab = tab;
            renderChart();
        }

        // 更新testid基本信息
        function updateTestIDInfo() {
            const infoEl = document.getElementById("testid-info");
            if (!currentTestID || !webData[currentTestID]) {
                infoEl.textContent = "无可用数据";
                return;
            }
            const data = webData[currentTestID];
            infoEl.innerHTML = `
                <strong>TestID:</strong> ${data.testid} <br>
                <strong>总记录数:</strong> ${data.total_records} <br>
                <strong>帧ID范围:</strong> ${data.frameid_range}
            `;
        }

        // ========== 核心修改：Y坐标波形图 - 顶部汇总大图(带score帧ID虚线) + 下方5个独立图 ==========
        function renderYCoordChart() {
            if (!currentTestID || !webData[currentTestID]) return;
            const data = webData[currentTestID];
            const yPointsData = data.y_points_data;
            // 获取需要标记的score变化帧ID集合
            const scoreChangeFrameIds = data.score_data.score_change_frameids;
            const chartWrapper = document.getElementById("chart-wrapper");
            chartWrapper.innerHTML = ""; // 清空容器

            // ------ 第一步：先创建【汇总大图】- 含5个坐标点+score变化帧ID红色垂直虚线 ------
            const bigChartCard = document.createElement("div");
            bigChartCard.className = "big-chart-card";
            bigChartCard.id = "y-chart-big";
            chartWrapper.appendChild(bigChartCard);
            // 汇总大图：5个坐标点全部绘制在同一张图，颜色一一对应
            const bigTraces = [];
            yPointsData.forEach((point, idx) => {
                bigTraces.push({
                    x: point.frameids,
                    y: point.y_coords,
                    type: "scatter",
                    mode: "lines+markers",
                    marker: { size: 4 },
                    line: { width: 2, color: colors[idx] },
                    name: `坐标点${point.point_index}`
                });
            });

            // ========== 生成所有score_change_frameids的【红色垂直虚线】 ==========
            const dashLineShapes = [];
            scoreChangeFrameIds.forEach(fid => {
                dashLineShapes.push({
                    type: 'line',
                    x0: fid,
                    y0: 0,
                    x1: fid,
                    y1: 5000,
                    line: {
                        color: 'rgba(255, 0, 0, 0.6)', // 红色半透明，醒目不遮挡
                        width: 1.5, // 数值越大线越粗，1.2刚好
                        dash: 'dot' // 点虚线样式，和Score图一致，dot=点虚线  dash=短横线虚线  solid=实线
                    },
                    layer: 'below' // 虚线在波形下方，不遮挡曲线
                });
            });

            // 汇总大图布局：尺寸和Score一致+Y轴固定0-5000+红色虚线+所有属性匹配
            const bigLayout = {
                title: {
                    text: `所有5个坐标点 - Y值变化汇总波形图 (红色虚线=Score变化帧ID)`,
                    font: { size: 16, weight: "bold" },
                    pad: { t: 10, b: 10 }
                },
                height: 580,
                margin: { l: 60, r: 20, t: 40, b: 60 },
                xaxis: {
                    title: "FrameID（帧序号）",
                    showgrid: true,
                    gridcolor: "#eee",
                    autorange: true
                },
                yaxis: {
                    title: "Y坐标数值",
                    showgrid: true,
                    gridcolor: "#eee",
                    range: [0, 5000], // Y轴固定0-5000，和下方一致
                    fixedrange: true   // 锁定Y轴缩放，只允许缩放帧ID
                },
                hovermode: "x unified",
                showlegend: true,
                legend: { orientation: 'h', y: -0.15 },
                shapes: dashLineShapes 
            };
            // 绘制汇总大图
            Plotly.newPlot("y-chart-big", bigTraces, bigLayout, {responsive: true});

            // ------ 第二步：生成【5个独立Y坐标图】，依次排列在大图下方 ------
            yPointsData.forEach((point, idx) => {
                const chartCard = document.createElement("div");
                chartCard.className = "single-chart-card";
                chartCard.id = `y-chart-${idx}`;
                chartWrapper.appendChild(chartCard);

                const trace = {
                    x: point.frameids,
                    y: point.y_coords,
                    type: "scatter",
                    mode: "lines+markers",
                    marker: { size: 4 },
                    line: { width: 2, color: colors[idx] },
                    name: `坐标点${point.point_index}`
                };

                const layout = {
                    title: {
                        text: `坐标点 ${point.point_index} - Y值变化波形图`,
                        font: { size: 14, weight: "bold" },
                        pad: { t: 10, b: 10 }
                    },
                    height: 380,
                    margin: { l: 50, r: 20, t: 40, b: 60 },
                    xaxis: {
                        title: "FrameID（帧序号）",
                        showgrid: true,
                        gridcolor: "#eee",
                        autorange: true
                    },
                    yaxis: {
                        title: "Y坐标数值",
                        showgrid: true,
                        gridcolor: "#eee",
                        range: [0, 5000],
                        fixedrange: true
                    },
                    hovermode: "x unified",
                    showlegend: true
                };

                Plotly.newPlot(`y-chart-${idx}`, [trace], layout, {responsive: true});
            });
        }

        // Score波形图
        function renderScoreChart() {
            if (!currentTestID || !webData[currentTestID]) return;
            const data = webData[currentTestID];
            const scoreData = data.score_data;
            const chartWrapper = document.getElementById("chart-wrapper");
            chartWrapper.innerHTML = "";

            const chartCard = document.createElement("div");
            chartCard.className = "big-chart-card";
            chartWrapper.appendChild(chartCard);

            const traceScore = {
                x: scoreData.frameids,
                y: scoreData.score_list,
                type: "scatter",
                mode: "lines+markers",
                marker: { size: 5, color: "#ff4500" },
                line: { width: 2.5, color: "#ff4500" },
                name: "Score分数"
            };

            const maxMarkers = {
                x: scoreData.max_segments.map(seg => seg.max_fid),
                y: scoreData.max_segments.map(seg => seg.max_score),
                type: "scatter",
                mode: "markers+text",
                marker: { size: 12, color: "red", symbol: "star" },
                text: scoreData.max_segments.map((seg, idx) => 
                    `第${idx+1}段最大值: ${seg.max_score}<br>帧ID: ${seg.max_fid}`
                ),
                textposition: "top center",
                name: "分段最大值"
            };

            const layout = {
                title: {
                    text: `TestID: ${currentTestID} - Score分数变化`,
                    font: { size: 16, weight: "bold" }
                },
                height: 580,
                margin: { l: 60, r: 20, t: 40, b: 60 },
                xaxis: {
                    title: "FrameID（帧序号）",
                    showgrid: true,
                    gridcolor: "#eee"
                },
                yaxis: {
                    title: "Score分数值",
                    showgrid: true,
                    gridcolor: "#eee",
                    range: [0, Math.max(...scoreData.score_list) * 1.1]
                },
                hovermode: "x unified",
                showlegend: true
            };

            Plotly.newPlot(chartCard, [traceScore, maxMarkers], layout, {responsive: true});
        }

        // 渲染当前选中的图表
        function renderChart() {
            if (currentTab === "y-coord") {
                renderYCoordChart();
            } else if (currentTab === "score") {
                renderScoreChart();
            }
        }

        // 初始化页面
        window.onload = function() {
            document.querySelectorAll(".chart-tab").forEach(tab => {
                tab.onclick = () => switchChartTab(tab.dataset.tab);
            });
            initTestIDList();
            updateTestIDInfo();
            renderChart();
        };
    </script>
</body>
</html>
    """

    # 将web_data转为JSON字符串（兼容Python数据类型）
    import json
    web_data_json = json.dumps(web_data, ensure_ascii=False, indent=2)
    html_content = html_template.replace("{web_data_json}", web_data_json)

    # 生成网页文件
    web_file_path = os.path.join(output_dir, "rope_skip_analysis.html")
    with open(web_file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n=== 生成交互式网页完成 ===")
    print(f"网页文件路径：{web_file_path}")
    # print(f"使用说明：")
    # print(f"  1. Y坐标波形图：顶部汇总大图含【5个坐标点+红色虚线(Score变化帧ID)】，下方为5个独立图")
    # print(f"  2. 汇总大图尺寸和Score图一致，Y轴固定0~5000，虚线跟随帧ID缩放平移")
    # print(f"  3. 左侧切换TestID，右侧切换Y坐标/Score波形图，工具栏已放大，图表已加宽")

# ---------------------- 主函数 ----------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="处理跳绳相机日志文件")
    parser.add_argument('app_log', type=str, help='APP日志文件路径（例如：1.log、./logs/2.log）')
    parser.add_argument('--start_time', type=str, nargs='?',
                        help='开始时间，格式：YYYY-MM-DD HH:MM:SS（可选）')
    parser.add_argument('--end_time', type=str, nargs='?',
                        help='结束时间，格式：YYYY-MM-DD HH:MM:SS（可选）')
    args = parser.parse_args()
    # 输入
    LOG_FILE = args.app_log
    start_time = args.start_time
    end_time = args.end_time
    # 输出
    current_time = datetime.now().strftime("%Y_%m_%d_%H.%M")
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


    data1 = extract_data1_by_keyword(LOG_FILE)
    if not data1:
        print("无匹配的日志行，程序结束")
        exit()
    df_data2, df_csv = process_data2_and_csv(data1, CSV_OUTPUT)
    df_data2_filtered = filter_by_time(df_data2, start_time, end_time)
    data3_list = process_data3(df_data2_filtered)

    data5_list = process_data5(df_data2_filtered)

    data4_list = process_data4(data3_list, data5_list)
    # plot_data4(data4_list, IMG_OUTPUT_DIR)
    # plot_data5(data5_list, IMG_OUTPUT_DIR)

    web_data = process_web_data(data4_list, data5_list)
    generate_web_page(web_data, IMG_OUTPUT_DIR)