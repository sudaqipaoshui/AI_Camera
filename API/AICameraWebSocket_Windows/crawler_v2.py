import websocket
import x3_pb2 as pb2
import os
import json
import datetime
import cv2
import numpy as np
import logging
from pathlib import Path

# Target {
#  string type_;             // "person"
#  uint64 track_id_;         // track_id
#  repeated Box boxes_ = [{
#    string type_;           //  "body"、"head" 或 "face"，分别表示人脸框、人头框、人体框
#    Point top_left_;        // 框左上点坐标
#    Point bottom_right_;    // 框右下点坐标
#    float score;
#  }];
#  repeated Points points_ = [Points {
#    string type_;           // "body_landmarks"，表示人体骨骼点集合
#    repeated Point points_;
#  }];
#  repeated Attributes attributes_ = [{
#    string type_;           // "age"、"gender"、"face_mask", 分别表示年龄、性别、口罩
#                            // "fall"、"raise_hand"、"stand"、"squat", 分别表示摔倒、举手、站立和蹲下
#                            // "action"表示体感游戏
#
#    float value_;           // 属性对应的值
#    string value_string_;   // reserved
#    float score_;           // 置信度
#  }];
# }

import yaml
from pathlib import Path

# 从配置文件读取IP地址
ip = "192.168.3.175"  # 默认值

# 关键点索引定义
LShoulder = 5
RShoulder = 6
LHand = 9
RHand = 10
LAnk = 15
RAnk = 16

# 全局变量
img_w = 640
img_h = 360
frameid = 0
start_time = None
area_data = []
video_pose_data = {}

# 数据检查统计
check_stats = {
    'total_frames': 0,
    'valid_frames': 0,
    'invalid_frames': 0,
    'errors': {
        'image_decode_failed': 0,
        'no_targets': 0,
        'no_pose_data': 0,
        'invalid_pose_count': 0,
        'protobuf_parse_failed': 0,
        'invalid_timestamp': 0,
        'message_too_large': 0,
        'invalid_box_coordinates': 0,
    },
    'warnings': {
        'empty_targets': 0,
        'pose_keypoints_missing': 0,
        'low_confidence': 0,
        'frame_drop': 0,
        'high_latency': 0,
        'unstable_fps': 0,
        'track_id_discontinuous': 0,
        'invalid_box_size': 0,
        'keypoint_out_of_range': 0,
        'duplicate_track_id': 0,
        'missing_areas': 0,
        'missing_sportInfos': 0,
    }
}

# 性能监控
performance_stats = {
    'frame_timestamps': [],  # 记录每帧的时间戳
    'frame_sizes': [],  # 记录每帧消息大小
    'last_timestamp': None,
    'track_ids': set(),  # 记录所有track_id
    'fps_history': [],  # FPS历史记录
}

# 温度监控 (从WebSocket消息中提取)
temperature_stats = {
    'temperatures': [],  # 温度历史记录
    'timestamps': [],  # 温度采集时间戳
}

# 日志和报告设置
reports_dir = 'allure-report/websocket'
if not os.path.exists(reports_dir):
    os.makedirs(reports_dir, exist_ok=True)  # 使用 makedirs 创建多级目录

# 保存设置
save_type = 'video'  # 'image' 或 'video'
write_video_file = None
write_json_file = None
out = None  # VideoWriter 将在收到第一帧时初始化

# 按日期分类的目录结构
session_date = datetime.datetime.now().strftime("%Y%m%d")
session_dir = os.path.join(reports_dir, session_date)
if not os.path.exists(session_dir):
    os.makedirs(session_dir, exist_ok=True)

# 视频保存目录（按日期分类）
videos_dir = os.path.join(session_dir, 'videos')
if not os.path.exists(videos_dir):
    os.makedirs(videos_dir, exist_ok=True)

# 日志保存目录（按日期分类）
logs_dir = os.path.join(session_dir, 'logs')
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir, exist_ok=True)

# 初始化日志
log_file = os.path.join(logs_dir, datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + '.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()  # 同时输出到控制台
    ]
)
logger = logging.getLogger(__name__)

# 报告数据
report_data = {
    'start_time': datetime.datetime.now(),
    'end_time': None,
    'frames': [],
    'errors': [],
    'warnings': [],
    'summary': {}
}


def _json_loads_list(s) -> list:
    """
    安全解析为 list；失败或类型不符时返回 []。
    """
    try:
        if s is None or s == '':
            return []
        v = json.loads(s)
        return v if isinstance(v, list) else []
    except Exception:
        return []


def _json_loads_dict(s) -> dict:
    """
    安全解析为 dict；失败或类型不符时返回 {}。
    """
    try:
        if s is None or s == '':
            return {}
        v = json.loads(s)
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def _normalize_epoch_seconds(raw_ts) -> float:
    """
    将各种单位（秒/毫秒/微秒/纳秒）时间戳规范为秒（float）。
    根据时间戳的数量级自动判断单位。
    """
    try:
        ts = float(raw_ts)
    except Exception:
        # 无法转换，返回当前时间
        return datetime.datetime.now().timestamp()
    
    # 检查是否为合理值
    if ts <= 0:
        return datetime.datetime.now().timestamp()
    
    # 粗略按数量级判断：
    # > 1e18: 纳秒 (很少见)
    # > 1e14: 微秒 (1970-01-01 以来的微秒数)
    # > 1e11: 毫秒 (1970-01-01 以来的毫秒数)
    # 否则: 秒
    if ts > 1e18:
        return ts / 1e9
    elif ts > 1e14:
        return ts / 1e6
    elif ts > 1e11:
        return ts / 1e3
    else:
        return ts


def extract_temperature_from_message(pbm):
    """从WebSocket消息中提取温度数据"""
    global temperature_stats

    try:
        if not pbm.HasField('Statistics_msg_'):
            return None

        # 遍历Statistics消息的attributes，查找温度数据
        for attr in pbm.Statistics_msg_.attributes_:
            # 可能的温度字段：temperature, temp, device_temp等
            if attr.type_ in ['temperature', 'temp', 'device_temp', 'cpu_temp', 'soc_temp']:
                temp_value = None

                # 尝试从value_获取（浮点数）
                if hasattr(attr, 'value_') and attr.value_ > 0:
                    temp_value = attr.value_
                    # 如果值太大，可能是毫摄氏度，需要除以1000
                    if temp_value > 150:
                        temp_value = temp_value / 1000

                # 尝试从value_string_获取（字符串）
                elif hasattr(attr, 'value_string_') and attr.value_string_:
                    try:
                        temp_str = attr.value_string_.strip()
                        # 移除可能的单位符号
                        temp_str = temp_str.replace('°C', '').replace('℃', '').replace('C', '').strip()
                        temp_value = float(temp_str)

                        # 如果值太大（>150），可能是毫摄氏度或其他单位
                        if temp_value > 150:
                            temp_value = temp_value / 1000
                    except:
                        pass

                # 验证温度范围是否合理（0-150°C）
                if temp_value and 0 < temp_value < 150:
                    current_time = datetime.datetime.now()
                    temperature_stats['temperatures'].append(temp_value)
                    temperature_stats['timestamps'].append(current_time)
                    logger.info(f"🌡️  温度采集 [{attr.type_}]: {temp_value:.1f}°C")
                    return temp_value

        return None
    except Exception as e:
        logger.debug(f"温度提取失败: {e}")
        return None


def point_in_polygon(point_x, point_y, polygon):
    """
    判断点是否在多边形内部
    :param point: (x, y) 元组，表示点的坐标
    :param polygon: 顶点坐标组成的列表，例如 [x1, y1, x2, y2, x3, y3]
    :return: True or False
    """
    n = int(len(polygon) / 2)

    inside = False
    p1x = polygon[0]
    p1y = polygon[1]
    for i in range(1, n):
        p2x = polygon[i * 2]
        p2y = polygon[i * 2 + 1]
        if min(p1y, p2y) < point_y <= max(p1y, p2y) and point_x <= max(p1x, p2x):
            if p1y != p2y:
                xinters = (point_y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                if p1x == p2x or point_x <= xinters:
                    inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def match_position(top_left, bottom_right, area_data):
    bm_point_x = (top_left.x_ + bottom_right.x_) / 2
    bm_point_y = bottom_right.y_
    for i in range(len(area_data)):
        if len(area_data[i]) == 0:
            continue
        if point_in_polygon(bm_point_x, bm_point_y, area_data[i]):
            return i
    return -1


def check_message_data(pbm, message_size=0):
    """
    检查消息数据的完整性和有效性
    返回: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []

    # 0. 检查消息大小
    if message_size > 10 * 1024 * 1024:  # 10MB
        errors.append(f"消息过大: {message_size / 1024 / 1024:.2f}MB")
        check_stats['errors']['message_too_large'] += 1
    elif message_size > 5 * 1024 * 1024:  # 5MB
        warnings.append(f"消息较大: {message_size / 1024 / 1024:.2f}MB")

    # 1. 检查图像数据
    if not pbm.HasField('img_'):
        errors.append("缺少图像数据 (img_)")
    elif pbm.img_.width_ <= 0 or pbm.img_.height_ <= 0:
        errors.append(f"图像尺寸无效: {pbm.img_.width_}x{pbm.img_.height_}")
    elif len(pbm.img_.buf_) == 0:
        errors.append("图像缓冲区为空")
    elif pbm.img_.width_ > 10000 or pbm.img_.height_ > 10000:
        warnings.append(f"图像尺寸异常大: {pbm.img_.width_}x{pbm.img_.height_}")

    # 2. 检查智能消息
    if not pbm.HasField('smart_msg_'):
        errors.append("缺少智能消息 (smart_msg_)")
    else:
        # 检查时间戳 - 使用归一化后的秒级时间戳
        raw_timestamp = pbm.smart_msg_.timestamp_
        current_timestamp = _normalize_epoch_seconds(raw_timestamp)
        
        if raw_timestamp == 0:
            errors.append("时间戳为0")
            check_stats['errors']['invalid_timestamp'] += 1
        elif performance_stats['last_timestamp'] is not None:
            # 检查时间戳是否倒退
            if current_timestamp < performance_stats['last_timestamp']:
                warnings.append(f"时间戳倒退: {current_timestamp} < {performance_stats['last_timestamp']}")

            # 检查帧间隔（延迟）- current_timestamp 已经是秒
            time_diff = current_timestamp - performance_stats['last_timestamp']
            if time_diff > 1.0:  # 超过1秒
                warnings.append(f"帧间隔过长: {time_diff:.2f}秒")
                check_stats['warnings']['high_latency'] += 1
            elif time_diff < 0.01:  # 小于10ms，可能有问题
                warnings.append(f"帧间隔过短: {time_diff * 1000:.2f}ms")

            # 计算FPS
            if time_diff > 0:
                fps = 1.0 / time_diff
                performance_stats['fps_history'].append(fps)
                if len(performance_stats['fps_history']) > 100:
                    performance_stats['fps_history'].pop(0)

                # 检查FPS稳定性
                if len(performance_stats['fps_history']) >= 10:
                    avg_fps = sum(performance_stats['fps_history']) / len(performance_stats['fps_history'])
                    if fps < avg_fps * 0.7 or fps > avg_fps * 1.3:
                        warnings.append(f"FPS不稳定: 当前{fps:.1f}fps, 平均{avg_fps:.1f}fps")
                        check_stats['warnings']['unstable_fps'] += 1

        performance_stats['last_timestamp'] = current_timestamp
        performance_stats['frame_timestamps'].append(current_timestamp)

        # 检查错误码
        if pbm.smart_msg_.error_code_ != 0:
            errors.append(f"智能消息错误码: {pbm.smart_msg_.error_code_}")

        # 检查目标数量
        if len(pbm.smart_msg_.targets_) == 0:
            warnings.append("未检测到任何目标")
            check_stats['warnings']['empty_targets'] += 1

        # 检查每个目标
        current_track_ids = set()
        for i, target in enumerate(pbm.smart_msg_.targets_):
            if target.type_ == 'person':
                # 检查track_id
                if target.track_id_ > 0:
                    current_track_ids.add(target.track_id_)
                    if target.track_id_ in performance_stats['track_ids']:
                        # track_id已存在，检查是否合理（可能是同一目标在不同帧）
                        pass
                    else:
                        performance_stats['track_ids'].add(target.track_id_)

                # 检查是否有检测框
                if len(target.boxes_) == 0:
                    warnings.append(f"目标 {i} (track_id: {target.track_id_}) 没有检测框")
                else:
                    # 检查每个检测框
                    for j, box in enumerate(target.boxes_):
                        # 检查坐标有效性
                        if box.top_left_.x_ >= box.bottom_right_.x_ or box.top_left_.y_ >= box.bottom_right_.y_:
                            errors.append(
                                f"目标 {i} 检测框 {j} 坐标无效: ({box.top_left_.x_}, {box.top_left_.y_}) -> ({box.bottom_right_.x_}, {box.bottom_right_.y_})")
                            check_stats['errors']['invalid_box_coordinates'] += 1

                        # 检查检测框大小
                        box_width = box.bottom_right_.x_ - box.top_left_.x_
                        box_height = box.bottom_right_.y_ - box.top_left_.y_
                        if box_width < 10 or box_height < 10:
                            warnings.append(f"目标 {i} 检测框 {j} 尺寸过小: {box_width}x{box_height}")
                            check_stats['warnings']['invalid_box_size'] += 1
                        elif box_width > img_w or box_height > img_h:
                            warnings.append(f"目标 {i} 检测框 {j} 超出图像范围: {box_width}x{box_height}")
                            check_stats['warnings']['invalid_box_size'] += 1

                        # 检查宽高比（人体检测框通常不会太宽或太高）
                        aspect_ratio = box_width / box_height if box_height > 0 else 0
                        if aspect_ratio > 3.0 or aspect_ratio < 0.2:
                            warnings.append(f"目标 {i} 检测框 {j} 宽高比异常: {aspect_ratio:.2f}")

                # 检查是否有姿态关键点
                has_pose = False
                for points in target.points_:
                    if points.type_ == 'body_landmarks':
                        has_pose = True
                        if len(points.points_) < 17:
                            errors.append(f"目标 {i} 关键点数量不足: {len(points.points_)}/17")
                            check_stats['errors']['invalid_pose_count'] += 1
                        else:
                            # 检查关键点坐标范围
                            out_of_range_count = 0
                            for kp_idx, kp in enumerate(points.points_):
                                if kp.x_ < 0 or kp.x_ > img_w or kp.y_ < 0 or kp.y_ > img_h:
                                    out_of_range_count += 1
                            if out_of_range_count > len(points.points_) * 0.3:  # 超过30%的关键点超出范围
                                warnings.append(f"目标 {i} 关键点超出范围: {out_of_range_count}/{len(points.points_)}")
                                check_stats['warnings']['keypoint_out_of_range'] += 1
                        break

                if not has_pose:
                    warnings.append(f"目标 {i} 没有姿态关键点")
                    check_stats['warnings']['pose_keypoints_missing'] += 1

    # 3. 检查统计消息
    if not pbm.HasField('Statistics_msg_'):
        warnings.append("缺少统计消息 (Statistics_msg_)")
    else:
        has_areas = False
        has_sportInfos = False
        has_temperature = False
        for attr in pbm.Statistics_msg_.attributes_:
            if attr.type_ == 'areas':
                has_areas = True
            if attr.type_ == 'sportInfos':
                has_sportInfos = True
            if attr.type_ in ['temperature', 'temp', 'device_temp', 'cpu_temp', 'soc_temp']:
                has_temperature = True

        if not has_areas:
            warnings.append("缺少区域数据 (areas)")
            check_stats['warnings']['missing_areas'] += 1

        # 温度数据是可选的，只记录信息不作为警告
        if has_temperature:
            logger.debug("✓ 消息包含温度数据")
        if not has_sportInfos:
            warnings.append("缺少运动信息 (sportInfos)")
            check_stats['warnings']['missing_sportInfos'] += 1

    # 4. 检查检测框置信度
    for target in pbm.smart_msg_.targets_:
        for box in target.boxes_:
            if box.score < 0.5:
                warnings.append(f"检测框置信度较低: {box.score:.2f}")
                check_stats['warnings']['low_confidence'] += 1
            elif box.score > 1.0:
                errors.append(f"检测框置信度异常: {box.score:.2f} (应 <= 1.0)")

    # 5. 检查抓拍消息（如果存在）
    if pbm.HasField('capture_msg_'):
        if len(pbm.capture_msg_.targets_) > 0:
            # 检查抓拍目标数量是否合理
            if len(pbm.capture_msg_.targets_) > 100:
                warnings.append(f"抓拍目标数量过多: {len(pbm.capture_msg_.targets_)}")

    # 6. 检查消息大小记录
    performance_stats['frame_sizes'].append(message_size)
    if len(performance_stats['frame_sizes']) > 100:
        performance_stats['frame_sizes'].pop(0)

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def check_pose_data(pose_points, key_name=""):
    """
    检查姿态关键点数据的有效性
    """
    errors = []
    warnings = []

    if len(pose_points) < 17:
        errors.append(f"{key_name}: 关键点数量不足 ({len(pose_points)}/17)")
        return False, errors, warnings

    # 检查关键点是否在合理范围内（假设图像尺寸已知）
    valid_points = 0
    for i, point in enumerate(pose_points):
        if point.x_ < 0 or point.y_ < 0:
            warnings.append(f"{key_name}: 关键点 {i} 坐标异常 ({point.x_}, {point.y_})")
        elif point.x_ > img_w or point.y_ > img_h:
            warnings.append(f"{key_name}: 关键点 {i} 超出图像范围 ({point.x_}, {point.y_})")
        else:
            valid_points += 1

    if valid_points < len(pose_points) * 0.8:
        warnings.append(f"{key_name}: 有效关键点比例较低 ({valid_points}/{len(pose_points)})")

    return True, errors, warnings


def print_check_summary():
    """打印检查统计摘要"""
    print("\n" + "=" * 60)
    print("📊 数据检查统计摘要")
    print("=" * 60)
    print(f"总帧数: {check_stats['total_frames']}")
    print(f"有效帧数: {check_stats['valid_frames']}")
    print(f"无效帧数: {check_stats['invalid_frames']}")

    if check_stats['errors']:
        print("\n❌ 错误统计:")
        for error_type, count in check_stats['errors'].items():
            if count > 0:
                print(f"  - {error_type}: {count}")

    if check_stats['warnings']:
        print("\n⚠️  警告统计:")
        for warning_type, count in check_stats['warnings'].items():
            if count > 0:
                print(f"  - {warning_type}: {count}")

    if check_stats['total_frames'] > 0:
        valid_rate = (check_stats['valid_frames'] / check_stats['total_frames']) * 100
        print(f"\n✅ 数据有效率: {valid_rate:.2f}%")
    print("=" * 60 + "\n")

    # 记录到日志
    logger.info("=" * 60)
    logger.info("数据检查统计摘要")
    logger.info(f"总帧数: {check_stats['total_frames']}")
    logger.info(f"有效帧数: {check_stats['valid_frames']}")
    logger.info(f"无效帧数: {check_stats['invalid_frames']}")
    if check_stats['total_frames'] > 0:
        valid_rate = (check_stats['valid_frames'] / check_stats['total_frames']) * 100
        logger.info(f"数据有效率: {valid_rate:.2f}%")

    # 性能统计
    if len(performance_stats['fps_history']) > 0:
        avg_fps = sum(performance_stats['fps_history']) / len(performance_stats['fps_history'])
        min_fps = min(performance_stats['fps_history'])
        max_fps = max(performance_stats['fps_history'])
        logger.info(f"FPS统计: 平均={avg_fps:.2f}, 最小={min_fps:.2f}, 最大={max_fps:.2f}")

    # 温度统计
    if len(temperature_stats['temperatures']) > 0:
        avg_temp = sum(temperature_stats['temperatures']) / len(temperature_stats['temperatures'])
        min_temp = min(temperature_stats['temperatures'])
        max_temp = max(temperature_stats['temperatures'])
        logger.info(
            f"温度统计: 平均={avg_temp:.1f}°C, 最小={min_temp:.1f}°C, 最大={max_temp:.1f}°C, 采样数={len(temperature_stats['temperatures'])}")
        print(f"📊 FPS统计: 平均={avg_fps:.2f}fps, 最小={min_fps:.2f}fps, 最大={max_fps:.2f}fps")

    if len(performance_stats['frame_sizes']) > 0:
        avg_size = sum(performance_stats['frame_sizes']) / len(performance_stats['frame_sizes'])
        max_size = max(performance_stats['frame_sizes'])
        logger.info(f"消息大小: 平均={avg_size / 1024:.2f}KB, 最大={max_size / 1024:.2f}KB")
        print(f"📊 消息大小: 平均={avg_size / 1024:.2f}KB, 最大={max_size / 1024:.2f}KB")

    if len(performance_stats['track_ids']) > 0:
        logger.info(f"检测到的track_id数量: {len(performance_stats['track_ids'])}")
        print(f"📊 检测到的track_id数量: {len(performance_stats['track_ids'])}")


def generate_html_report():
    """生成HTML格式的报告"""
    global report_data, check_stats

    report_data['end_time'] = datetime.datetime.now()
    duration = report_data['end_time'] - report_data['start_time']

    report_data['summary'] = {
        'total_frames': check_stats['total_frames'],
        'valid_frames': check_stats['valid_frames'],
        'invalid_frames': check_stats['invalid_frames'],
        'duration_seconds': duration.total_seconds(),
        'valid_rate': (check_stats['valid_frames'] / check_stats['total_frames'] * 100) if check_stats[
                                                                                               'total_frames'] > 0 else 0,
        'errors': check_stats['errors'],
        'warnings': check_stats['warnings']
    }

    # 报告文件保存到日期目录
    report_date_dir = os.path.join(reports_dir, session_date)
    if not os.path.exists(report_date_dir):
        os.makedirs(report_date_dir, exist_ok=True)
    report_file = os.path.join(report_date_dir, datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + '_report.html')

    html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WebSocket 数据采集报告</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .summary-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .summary-card h3 {{
            margin: 0 0 10px 0;
            font-size: 14px;
            opacity: 0.9;
        }}
        .summary-card .value {{
            font-size: 32px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .section {{
            margin: 30px 0;
        }}
        .section h2 {{
            color: #555;
            border-left: 4px solid #4CAF50;
            padding-left: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .error {{
            color: #f44336;
            font-weight: bold;
        }}
        .warning {{
            color: #ff9800;
        }}
        .success {{
            color: #4CAF50;
        }}
        .info {{
            background-color: #e3f2fd;
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
        }}
        .progress-bar {{
            width: 100%;
            height: 30px;
            background-color: #e0e0e0;
            border-radius: 15px;
            overflow: hidden;
            margin: 10px 0;
        }}
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #4CAF50, #8BC34A);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            transition: width 0.3s;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 WebSocket 数据采集报告</h1>

        <div class="info">
            <strong>采集时间:</strong> {report_data['start_time'].strftime('%Y-%m-%d %H:%M:%S')} - {report_data['end_time'].strftime('%Y-%m-%d %H:%M:%S')}<br>
            <strong>持续时间:</strong> {duration.total_seconds():.2f} 秒 ({duration})<br>
            <strong>连接地址:</strong> ws://{ip}:8080<br>
            <strong>日志文件:</strong> {log_file}
        </div>

        <div class="section">
            <h2>📈 总体统计</h2>
            <div class="summary">
                <div class="summary-card">
                    <h3>总帧数</h3>
                    <div class="value">{check_stats['total_frames']}</div>
                </div>
                <div class="summary-card">
                    <h3>有效帧数</h3>
                    <div class="value">{check_stats['valid_frames']}</div>
                </div>
                <div class="summary-card">
                    <h3>无效帧数</h3>
                    <div class="value">{check_stats['invalid_frames']}</div>
                </div>
                <div class="summary-card">
                    <h3>数据有效率</h3>
                    <div class="value">{report_data['summary']['valid_rate']:.2f}%</div>
                </div>
            </div>

            <div class="progress-bar">
                <div class="progress-fill" style="width: {report_data['summary']['valid_rate']}%">
                    {report_data['summary']['valid_rate']:.2f}%
                </div>
            </div>
        </div>

        <div class="section">
            <h2>🌡️ 温度监控</h2>
            <div class="summary">
"""

    # 添加温度统计卡片
    if len(temperature_stats['temperatures']) > 0:
        avg_temp = sum(temperature_stats['temperatures']) / len(temperature_stats['temperatures'])
        min_temp = min(temperature_stats['temperatures'])
        max_temp = max(temperature_stats['temperatures'])
        temp_count = len(temperature_stats['temperatures'])

        html_content += f"""
                <div class="summary-card">
                    <h3>平均温度</h3>
                    <div class="value">{avg_temp:.1f}°C</div>
                </div>
                <div class="summary-card">
                    <h3>最低温度</h3>
                    <div class="value">{min_temp:.1f}°C</div>
                </div>
                <div class="summary-card">
                    <h3>最高温度</h3>
                    <div class="value">{max_temp:.1f}°C</div>
                </div>
                <div class="summary-card">
                    <h3>采样次数</h3>
                    <div class="value">{temp_count}</div>
                </div>
"""
    else:
        html_content += """
                <div class="info">
                    <strong>⚠️ 未采集到温度数据</strong><br>
                    可能原因：WebSocket消息中不包含温度信息
                </div>
"""

    html_content += """
            </div>
        </div>

        <div class="section">
            <h2>❌ 错误统计</h2>
            <table>
                <thead>
                    <tr>
                        <th>错误类型</th>
                        <th>数量</th>
                        <th>占比</th>
                    </tr>
                </thead>
                <tbody>
"""

    total_errors = sum(check_stats['errors'].values())
    for error_type, count in check_stats['errors'].items():
        if count > 0:
            percentage = (count / check_stats['total_frames'] * 100) if check_stats['total_frames'] > 0 else 0
            html_content += f"""
                    <tr>
                        <td>{error_type}</td>
                        <td class="error">{count}</td>
                        <td>{percentage:.2f}%</td>
                    </tr>
"""

    html_content += """
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>⚠️ 警告统计</h2>
            <table>
                <thead>
                    <tr>
                        <th>警告类型</th>
                        <th>数量</th>
                        <th>占比</th>
                    </tr>
                </thead>
                <tbody>
"""

    for warning_type, count in check_stats['warnings'].items():
        if count > 0:
            percentage = (count / check_stats['total_frames'] * 100) if check_stats['total_frames'] > 0 else 0
            html_content += f"""
                    <tr>
                        <td>{warning_type}</td>
                        <td class="warning">{count}</td>
                        <td>{percentage:.2f}%</td>
                    </tr>
"""

    html_content += f"""
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>📝 详细信息</h2>
            <p>详细的错误和警告信息请查看日志文件: <code>{log_file}</code></p>
        </div>

        <div class="info">
            <strong>报告生成时间:</strong> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>
"""

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    logger.info(f"HTML报告已生成: {report_file}")
    print(f"✅ HTML报告已生成: {report_file}")
    return report_file


def generate_json_report():
    """生成JSON格式的报告"""
    global report_data, check_stats

    report_data['end_time'] = datetime.datetime.now()
    duration = report_data['end_time'] - report_data['start_time']

    json_report = {
        'metadata': {
            'start_time': report_data['start_time'].isoformat(),
            'end_time': report_data['end_time'].isoformat(),
            'duration_seconds': duration.total_seconds(),
            'ip': ip,
            'log_file': log_file
        },
        'statistics': {
            'total_frames': check_stats['total_frames'],
            'valid_frames': check_stats['valid_frames'],
            'invalid_frames': check_stats['invalid_frames'],
            'valid_rate': (check_stats['valid_frames'] / check_stats['total_frames'] * 100) if check_stats[
                                                                                                   'total_frames'] > 0 else 0
        },
        'performance': {
            'avg_fps': sum(performance_stats['fps_history']) / len(performance_stats['fps_history']) if len(
                performance_stats['fps_history']) > 0 else 0,
            'min_fps': min(performance_stats['fps_history']) if len(performance_stats['fps_history']) > 0 else 0,
            'max_fps': max(performance_stats['fps_history']) if len(performance_stats['fps_history']) > 0 else 0,
            'avg_message_size_kb': sum(performance_stats['frame_sizes']) / len(
                performance_stats['frame_sizes']) / 1024 if len(performance_stats['frame_sizes']) > 0 else 0,
            'max_message_size_kb': max(performance_stats['frame_sizes']) / 1024 if len(
                performance_stats['frame_sizes']) > 0 else 0,
            'unique_track_ids': len(performance_stats['track_ids'])
        },
        'temperature': {
            'avg_temp': sum(temperature_stats['temperatures']) / len(temperature_stats['temperatures']) if len(
                temperature_stats['temperatures']) > 0 else 0,
            'min_temp': min(temperature_stats['temperatures']) if len(temperature_stats['temperatures']) > 0 else 0,
            'max_temp': max(temperature_stats['temperatures']) if len(temperature_stats['temperatures']) > 0 else 0,
            'sample_count': len(temperature_stats['temperatures'])
        },
        'errors': {k: v for k, v in check_stats['errors'].items() if v > 0},
        'warnings': {k: v for k, v in check_stats['warnings'].items() if v > 0},
        'error_details': report_data['errors'],
        'warning_details': report_data['warnings']
    }

    # 报告文件保存到日期目录
    report_date_dir = os.path.join(reports_dir, session_date)
    if not os.path.exists(report_date_dir):
        os.makedirs(report_date_dir, exist_ok=True)
    report_file = os.path.join(report_date_dir, datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + '_report.json')

    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(json_report, f, ensure_ascii=False, indent=2)

    logger.info(f"JSON报告已生成: {report_file}")
    print(f"✅ JSON报告已生成: {report_file}")
    return report_file


def on_message(ws, message):
    global data_path, area_data, frameid, start_time, img_w, img_h, video_pose_data, out, write_video_file, write_json_file
    tester_data = {}

    try:
        global check_stats

        print("**************** message *******************")
        print(f"消息类型: {type(message)}, 消息长度: {len(message) if hasattr(message, '__len__') else 'N/A'}")

        # 确保 message 是 bytes 类型
        if isinstance(message, str):
            print("警告: 收到字符串类型消息，尝试转换为 bytes")
            message = message.encode('latin-1')  # 使用 latin-1 保留原始字节
        elif not isinstance(message, bytes):
            error_msg = f"未知的消息类型: {type(message)}"
            print(f"❌ {error_msg}")
            logger.error(error_msg)
            check_stats['errors']['protobuf_parse_failed'] += 1
            check_stats['total_frames'] += 1
            check_stats['invalid_frames'] += 1
            return
        
        # 检查消息是否为空
        if len(message) == 0:
            error_msg = "收到空消息"
            print(f"❌ {error_msg}")
            logger.error(error_msg)
            check_stats['errors']['protobuf_parse_failed'] += 1
            check_stats['total_frames'] += 1
            check_stats['invalid_frames'] += 1
            return
        
        # 检查是否为 JSON 消息（通常以 '{' 开头）
        try:
            if message[0:1] == b'{':
                # 尝试解析为 JSON
                json_str = message.decode('utf-8')
                json_data = json.loads(json_str)
                msg_type = json_data.get('type', 'unknown')
                print(f"ℹ️  收到 JSON 消息，类型: {msg_type}")
                logger.info(f"收到 JSON 消息: {msg_type}")
                # JSON 消息不是帧数据，直接跳过不计入统计
                return
        except Exception:
            pass  # 不是 JSON，继续尝试 Protobuf 解析
        
        # 记录消息大小
        message_size = len(message)
        
        # 解析protobuf消息
        try:
            pbm = pb2.FrameMessage()
            pbm.ParseFromString(message)
            print("✓ Protobuf 解析成功")
            
        except Exception as e:
            import traceback
            error_msg = f"Protobuf解析失败: {e}"
            print(f"❌ {error_msg}")
            print(f"详细错误: {traceback.format_exc()}")
            print(f"消息长度: {len(message) if hasattr(message, '__len__') else 'N/A'}")
            if hasattr(message, '__len__') and len(message) > 0:
                try:
                    print(f"消息前100字节 (hex): {message[:100].hex()}")
                    print(f"消息前100字节 (repr): {repr(message[:100])}")
                except Exception:
                    pass
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            check_stats['errors']['protobuf_parse_failed'] += 1
            check_stats['total_frames'] += 1
            check_stats['invalid_frames'] += 1
            return

        # 数据检查
        check_stats['total_frames'] += 1
        is_valid, errors, warnings = check_message_data(pbm, message_size)

        if is_valid:
            check_stats['valid_frames'] += 1
        else:
            check_stats['invalid_frames'] += 1
            print(f"❌ 数据检查失败:")
            logger.warning(f"数据检查失败 (帧 {check_stats['total_frames']})")
            for error in errors:
                print(f"   - {error}")
                logger.error(f"  - {error}")
                # 记录到报告数据
                report_data['errors'].append({
                    'frame': check_stats['total_frames'],
                    'time': datetime.datetime.now().isoformat(),
                    'error': error
                })
                # 更新错误统计
                if 'image' in error.lower() or 'decode' in error.lower():
                    check_stats['errors']['image_decode_failed'] += 1
                elif 'target' in error.lower():
                    check_stats['errors']['no_targets'] += 1
                elif 'pose' in error.lower() or '关键点' in error:
                    check_stats['errors']['no_pose_data'] += 1

        if warnings:
            print(f"⚠️  警告:")
            for warning in warnings:
                print(f"   - {warning}")
                logger.warning(f"  - {warning}")
                # 记录到报告数据
                report_data['warnings'].append({
                    'frame': check_stats['total_frames'],
                    'time': datetime.datetime.now().isoformat(),
                    'warning': warning
                })

        # 记录帧信息到报告
        report_data['frames'].append({
            'frame_id': check_stats['total_frames'],
            'time': datetime.datetime.now().isoformat(),
            'is_valid': is_valid,
            'errors': errors,
            'warnings': warnings
        })

        print(f"Statistics attributes: {len(pbm.Statistics_msg_.attributes_)} items")
        print("**************** Statistics message *******************")

        is_Testing = False
        
        # 安全获取图像宽高
        try:
            img_w = pbm.img_.width_ if pbm.HasField('img_') else img_w
            img_h = pbm.img_.height_ if pbm.HasField('img_') else img_h
        except Exception as e:
            error_msg = f"获取图像尺寸失败: {e}"
            print(f"❌ {error_msg}")
            logger.error(error_msg)
            check_stats['errors']['image_decode_failed'] += 1
            return

        # 解码图像
        # 添加调试信息
        buf_len = len(pbm.img_.buf_) if pbm.HasField('img_') else 0
        img_type = pbm.img_.type_ if (pbm.HasField('img_') and pbm.img_.type_) else "unknown"
        if frameid < 3:  # 只打印前3帧的详细信息
            print(f"🔍 图像信息: 尺寸={img_w}x{img_h}, 类型={img_type}, 缓冲区大小={buf_len}字节")
        
        # 根据图像类型进行解码
        img = None
        try:
            if img_type.upper() in ['JPEG', 'JPG', 'PNG']:
                # 压缩格式，使用imdecode
                img = cv2.imdecode(np.frombuffer(pbm.img_.buf_, dtype=np.uint8), cv2.IMREAD_COLOR)
            elif img_type.upper() == 'BGR':
                # BGR原始格式
                img_array = np.frombuffer(pbm.img_.buf_, dtype=np.uint8)
                if len(img_array) == img_w * img_h * 3:
                    img = img_array.reshape((img_h, img_w, 3))
                else:
                    print(f"⚠️  BGR数据大小不匹配: 期望{img_w * img_h * 3}, 实际{len(img_array)}")
            elif img_type.upper() in ['NV12', 'NV21']:
                # YUV格式
                yuv_data = np.frombuffer(pbm.img_.buf_, dtype=np.uint8)
                if img_type.upper() == 'NV12':
                    img = cv2.cvtColor(yuv_data.reshape((img_h * 3 // 2, img_w)), cv2.COLOR_YUV2BGR_NV12)
                else:  # NV21
                    img = cv2.cvtColor(yuv_data.reshape((img_h * 3 // 2, img_w)), cv2.COLOR_YUV2BGR_NV21)
            elif img_type.upper() == 'YUV420':
                # YUV420格式
                yuv_data = np.frombuffer(pbm.img_.buf_, dtype=np.uint8)
                img = cv2.cvtColor(yuv_data.reshape((img_h * 3 // 2, img_w)), cv2.COLOR_YUV2BGR_I420)
            else:
                # 未知格式，尝试用imdecode
                img = cv2.imdecode(np.frombuffer(pbm.img_.buf_, dtype=np.uint8), cv2.IMREAD_COLOR)
        except Exception as e:
            print(f"⚠️  图像解码异常: {e}")
            logger.error(f"图像解码异常: {e}")
            
        if img is None:
            error_msg = f"图像解码失败，跳过该帧 (尺寸={img_w}x{img_h}, 类型={img_type}, buf_len={buf_len})"
            print(f"❌ {error_msg}")
            logger.error(error_msg)
            check_stats['errors']['image_decode_failed'] += 1
            return

        # 从消息中提取温度数据
        extract_temperature_from_message(pbm)

        # 🔍 调试：打印所有Statistics字段（只打印第一帧）
        if frameid == 0:
            print("\n" + "=" * 60)
            print("🔍 Statistics_msg_ 所有字段:")
            print("=" * 60)
            for attr in pbm.Statistics_msg_.attributes_:
                value_info = ""
                if hasattr(attr, 'value_') and attr.value_ != 0:
                    value_info = f" (value_={attr.value_})"
                if hasattr(attr, 'value_string_') and attr.value_string_:
                    value_info += f" (value_string_='{attr.value_string_[:100]}')"
                print(f"  - {attr.type_}{value_info}")
            print("=" * 60 + "\n")

        for attr in pbm.Statistics_msg_.attributes_:
            # print(attr.type_,':',attr.value_string_)
            if attr.type_ == 'areas':
                data = _json_loads_list(getattr(attr, 'value_string_', ''))
                if data:  # 只在数据有效时处理
                    area_data = [[] for _ in range(len(data))]
                    for i in range(len(data)):
                        for j in range(len(data[i])):
                            wh = img_w if j % 2 == 0 else img_h
                            area_data[i].append(data[i][j] * wh)
            if attr.type_ == 'sportInfos':
                data = _json_loads_list(getattr(attr, 'value_string_', ''))
                if data:  # 只在数据有效时处理
                    for i in range(len(data)):
                        key = 'item' + str(i)
                        if key not in tester_data:
                            tester_data[key] = {}
                        # print(str(i+1)+'号'+' 姓名:',data[i]['name'],' 测试ID:','无' if data[i]['testId']=='' else data[i]['testId'])
                        tester_data[key]['name'] = data[i].get('name', '')
                        tester_data[key]['testId'] = data[i].get('testId', '')
                        if data[i].get('testId', '') != '':
                            is_Testing = True

        print(f'图像尺寸: {img_w} x {img_h}')
        print(f'区域数据: {area_data}')

        print("**************** smart message *******************")
        # print(pbm.smart_msg_)
        pid = -1
        for target in pbm.smart_msg_.targets_:
            if target.type_ == 'person':
                for box in target.boxes_:
                    if box.type_ == 'body':
                        # pid+=1
                        # img=cv2.circle(img,(int((box.top_left_.x_+box.bottom_right_.x_)/2),int(box.bottom_right_.y_)),2,(0,255,0))
                        pos_index = match_position(box.top_left_, box.bottom_right_, area_data)
                        print(
                            f'pos_index: {pos_index}, box: ({box.top_left_.x_}, {box.top_left_.y_}) -> ({box.bottom_right_.x_}, {box.bottom_right_.y_})')
                        # pos_index=pid
                        
                        # 只有在匹配到区域时才处理
                        if pos_index > -1:
                            key = 'item' + str(pos_index)
                            if key not in tester_data:
                                tester_data[key] = {}
                            
                            for points in target.points_:
                                if points.type_ == 'body_landmarks':
                                    # 检查姿态数据
                                    pose_valid, pose_errors, pose_warnings = check_pose_data(
                                        points.points_, f"item{pos_index}"
                                    )
                                    if pose_errors:
                                        for err in pose_errors:
                                            print(f"❌ {err}")
                                    if pose_warnings:
                                        for warn in pose_warnings:
                                            print(f"⚠️  {warn}")

                                    tester_data[key]['pose'] = points.points_
        print(f'人员数据: {tester_data}')

        # 每10帧打印一次统计摘要
        if frameid > 0 and frameid % 10 == 0:
            print_check_summary()

        # print("**************** capture message *******************")
        # print(pbm.capture_msg_)

        # Initialize new keys in video_pose_data if needed
        for key in tester_data:
            if key not in video_pose_data:
                video_pose_data[key] = {'LShoulder': [], 'LAnk': [], 'LHand': [], 'RShoulder': [], 'RAnk': [],
                                        'RHand': []}

        # 处理帧计数和视频保存
        if is_Testing or True:  # 始终处理
            frameid += 1
            print(f"Processing frame {frameid}")
            
            # 安全地转换时间戳
            try:
                ts_sec = _normalize_epoch_seconds(pbm.smart_msg_.timestamp_)
                d = datetime.datetime.fromtimestamp(ts_sec)
            except Exception as e:
                # 时间戳转换失败，使用当前时间
                logger.warning(f"时间戳转换失败 (timestamp={pbm.smart_msg_.timestamp_}): {e}")
                d = datetime.datetime.now()

            # 只保存视频，不保存单独的JSON和图像文件
            if save_type == 'video':
                # 保存视频模式
                # 初始化 VideoWriter（在收到第一帧时）
                if out is None:
                    # 使用时间戳作为文件名
                    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    write_video_file = os.path.join(videos_dir, timestamp_str + '.avi')
                    write_json_file = os.path.join(videos_dir, timestamp_str + '.json')
                    fourcc = cv2.VideoWriter_fourcc(*'XVID')
                    fps = 30
                    write_size = (img_w, img_h)
                    out = cv2.VideoWriter(write_video_file, fourcc, fps, write_size)
                    if not out.isOpened():
                        print(f"❌ 无法创建视频文件: {write_video_file}")
                        return
                    print(f"✅ 创建视频文件: {write_video_file}")

                # 在图像上绘制信息
                img = cv2.rectangle(img, (0, 0), (img_w, 20), (0, 0, 0), -1)
                if frameid == 1:
                    start_time = d
                diff = d - start_time
                label = f'StartTime: {d.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]}  |  Frames: {str(frameid).zfill(4)}  |  Duration: {diff.total_seconds():.2f}s'
                # 可选：在图像上显示标签
                # img = cv2.putText(img, label, (3, 15), cv2.FONT_HERSHEY_SIMPLEX,
                #                   0.5, (255, 255, 255), 1)

                out.write(img)

                # 可选：绘制区域边界（调试用）
                # for i in range(len(area_data)):
                #     if len(area_data[i]) >= 4:
                #         print((area_data[i][0], area_data[i][1]), (area_data[i][-2], area_data[i][-1]))
                #         img = cv2.line(img, (int(area_data[i][0]), int(area_data[i][1])),
                #                        (int(area_data[i][-2]), int(area_data[i][-1])), (255, 0, 0), 2)
                #         img = cv2.putText(img, str(i+1), (int(area_data[i][-1])+15, int(area_data[-1][1])-15),
                #                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255))
                #         for j in range(int(len(area_data[i])/2)-1):
                #             cv2.line(img, (int(area_data[i][j*2]), int(area_data[i][j*2+1])),
                #                      (int(area_data[i][j*2+2]), int(area_data[i][j*2+3])), (255, 0, 0), 2)

                # 显示图像（可选）
                cv2.imshow('AI Camera', img)
                cv2.waitKey(1)

                # 记录姿态数据
                for key in tester_data:
                    if 'pose' in tester_data[key]:
                        pose = tester_data[key]['pose']
                        if len(pose) > max(LShoulder, RShoulder, LHand, RHand, LAnk, RAnk):
                            video_pose_data[key]['LShoulder'].append(pose[LShoulder].y_)
                            video_pose_data[key]['RShoulder'].append(pose[RShoulder].y_)
                            video_pose_data[key]['LHand'].append(pose[LHand].y_)
                            video_pose_data[key]['RHand'].append(pose[RHand].y_)
                            video_pose_data[key]['LAnk'].append(pose[LAnk].y_)
                            video_pose_data[key]['RAnk'].append(pose[RAnk].y_)
                        else:
                            # 关键点数量不足
                            video_pose_data[key]['LShoulder'].append(-1)
                            video_pose_data[key]['RShoulder'].append(-1)
                            video_pose_data[key]['LHand'].append(-1)
                            video_pose_data[key]['RHand'].append(-1)
                            video_pose_data[key]['LAnk'].append(-1)
                            video_pose_data[key]['RAnk'].append(-1)
                    else:
                        # 没有姿态数据
                        video_pose_data[key]['LShoulder'].append(-1)
                        video_pose_data[key]['RShoulder'].append(-1)
                        video_pose_data[key]['LHand'].append(-1)
                        video_pose_data[key]['RHand'].append(-1)
                        video_pose_data[key]['LAnk'].append(-1)
                        video_pose_data[key]['RAnk'].append(-1)
        else:
            print("not Testing")

    except Exception as e:
        print(f"❌ 处理消息时出错: {e}")
        import traceback
        traceback.print_exc()


def cleanup_resources():
    """清理资源：释放视频写入器和保存JSON数据"""
    global out, write_video_file, write_json_file, frameid, video_pose_data

    if out is not None:
        out.release()
        out = None
        print("✅ 视频写入器已释放")

    if frameid > 0 and write_json_file is not None:
        try:
            with open(write_json_file, 'w', encoding='utf-8') as f:
                json.dump(video_pose_data, f, ensure_ascii=False, indent=2)
            print(f"✅ 姿态数据已保存: {write_json_file}")
        except Exception as e:
            print(f"❌ 保存JSON数据失败: {e}")
    elif write_video_file is not None and os.path.isfile(write_video_file):
        # 如果没有帧数据，删除空视频文件
        try:
            os.remove(write_video_file)
            print(f"🗑️  删除空视频文件: {write_video_file}")
        except Exception as e:
            print(f"❌ 删除文件失败: {e}")


def on_error(ws, error):
    print(f"❌ WebSocket 错误: {error}")
    print(f"WebSocket 对象: {ws}")
    cleanup_resources()
    exit(1)


def on_close(ws, close_status_code, close_msg):
    print("### WebSocket 连接已关闭 ###")
    logger.info("WebSocket 连接已关闭")
    # 打印最终统计摘要
    print_check_summary()
    # 生成报告
    try:
        html_report = generate_html_report()
        json_report = generate_json_report()
        print(f"\n📄 报告文件:")
        print(f"   - HTML: {html_report}")
        print(f"   - JSON: {json_report}")
    except Exception as e:
        logger.error(f"生成报告失败: {e}")
        print(f"❌ 生成报告失败: {e}")
    cleanup_resources()
    cv2.destroyAllWindows()


# 数据保存路径（已禁用，不再需要额外的数据目录）
data_path = ip.replace('.', '_') + '_data'
# if not os.path.exists(data_path):
#     os.mkdir(data_path)

print("=" * 60)
print("🚀 WebSocket 摄像头数据采集工具")
print("=" * 60)
print(f"📡 连接地址: ws://{ip}:8080")
# print(f"💾 数据保存路径: {data_path}")
print(f"🎬 视频保存路径: {videos_dir}")
print(f"📝 保存模式: {save_type}")
print(f"📋 日志文件: {log_file}")
print(f"📊 报告目录: {reports_dir}")
print(f"📅 会话日期: {session_date}")
print("=" * 60)
print("按 Ctrl+C 停止采集并查看统计摘要\n")

logger.info("=" * 60)
logger.info("WebSocket 摄像头数据采集工具启动")
logger.info(f"连接地址: ws://{ip}:8080")
# logger.info(f"数据保存路径: {data_path}")
logger.info(f"视频保存路径: {videos_dir}")
logger.info(f"日志文件: {log_file}")
logger.info(f"报告目录: {reports_dir}")
logger.info(f"会话日期: {session_date}")
logger.info("=" * 60)

websocket.enableTrace(False)
ws = websocket.WebSocketApp("ws://" + ip + ":8080",
                            on_message=on_message,
                            on_error=on_error,
                            on_close=on_close)

try:
    ws.run_forever()
except KeyboardInterrupt:
    print("\n\n⚠️  用户中断")
    logger.info("用户中断程序")
    print_check_summary()
    # 生成报告
    try:
        html_report = generate_html_report()
        json_report = generate_json_report()
        print(f"\n📄 报告文件:")
        print(f"   - HTML: {html_report}")
        print(f"   - JSON: {json_report}")
    except Exception as e:
        logger.error(f"生成报告失败: {e}")
        print(f"❌ 生成报告失败: {e}")
    cleanup_resources()
    cv2.destroyAllWindows()
