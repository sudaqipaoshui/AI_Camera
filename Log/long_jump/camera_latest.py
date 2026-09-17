import re
import matplotlib as mpl
import os
import matplotlib.pyplot as plt
import requests
import cv2
import numpy as np
import argparse
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUN_TIME = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
ROOT_SAVE_DIR = os.path.join(BASE_DIR, f"allure-report/long_jump/{RUN_TIME}")
# LOG_FILE = "1111.log"
POINT_ARRAY_KEEP_NUM = 4 # 取最后几个
SEPARATOR = "|"
SAVE_IMG_DIR = os.path.join(ROOT_SAVE_DIR, "track_img_output")  # 轨迹图保存路径
SAVE_IMG_DPI = 300
IMG_SAVE_FOLDER = os.path.join(ROOT_SAVE_DIR, "downloaded_imgs") # 下载图片保存路径
# BASE_IMG_URL = "http://192.168.3.175/img/"
BASE_IMG_URL = ""
SAVE_TXT_PATH = os.path.join(ROOT_SAVE_DIR, "final_result_拆分后分组数据.txt") # TXT文件目录
IMAGE_WIDTH = 640
IMAGE_HEIGHT = 360

# ====================== 第一步：图片匹配+下载======================
os.makedirs(IMG_SAVE_FOLDER, exist_ok=True)

def read_log_content():
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            log_str = f.read()
        print(f"第一步：成功读取日志文件，开始匹配图片链接段落...")
        return log_str
    except Exception as e:
        print(f"日志文件读取失败：{str(e)}")
        return ""


def draw_valid_score_on_img(img_path, valid_score):
    # 读取图片
    img = cv2.imread(img_path)
    if img is None:
        print(f"绘制validScore失败：图片{img_path}读取失败")
        return

    # 设置绘制参数
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.8
    if valid_score.lower() == "true":
        color = (0, 0, 255)  # 红色 BGR
    elif valid_score.lower() == "false":
        color = (0, 255, 0)  # 绿色 BGR
    else:
        color = (255, 0, 0)
    thickness = 2
    position = (10, 30)

    # 绘制文字
    # text = f"validScore: {valid_score}"
    text = f"{valid_score}"
    cv2.putText(img, text, position, font, font_scale, color, thickness)

    cv2.imwrite(img_path, img)
    print(f"已在图片{img_path}绘制validScore: {valid_score}")


def download_target_images():
    log_content = read_log_content()
    if not log_content:
        return

    # 正则匹配段落，非贪婪匹配，捕获图片名和validScore值
    pattern = r'save frame/userdata/image/((\d+)_(\d+)_last_(?:right|left)\.jpg).*?"validScore"\s*:\s*(\w+)'
    match_result = re.findall(pattern, log_content, re.DOTALL)

    if not match_result:
        print("日志中未匹配到符合规则的图片段落（包含validScore）")
        return

    print(f"第一步-筛选前：共匹配到 {len(match_result)} 个原始图片段落")

    # 筛选逻辑：第二个数值相等+第一个数值差值在100内 → 只保留最后一个（保留validScore信息）
    img_group_dict = {}
    for img_fullname, num1_str, num2_str, valid_score in match_result:
        num1 = int(num1_str)
        num2 = int(num2_str)
        if num2 not in img_group_dict:
            img_group_dict[num2] = []
        img_group_dict[num2].append((num1, img_fullname, valid_score))

    final_img_list = []
    for num2, img_item_list in img_group_dict.items():
        img_item_list_sorted = sorted(img_item_list, key=lambda x: x[0])
        if len(img_item_list_sorted) == 1:
            final_img_list.append(img_item_list_sorted[0])
        else:
            min_num1 = img_item_list_sorted[0][0]
            max_num1 = img_item_list_sorted[-1][0]
            if (max_num1 - min_num1) <= 100:
                final_img_list.append(img_item_list_sorted[-1])
            else:
                final_img_list.extend(img_item_list_sorted)

    final_download_list = [(img_name, valid_score) for (num1, img_name, valid_score) in final_img_list]
    print(f"第一步-筛选后：共保留 {len(final_download_list)} 张图片待下载 ↓↓↓")

    for num1, img_fullname, valid_score in final_img_list:
        frame_id = num1
        yuan_frame_id = num1 - 5
        download_url = BASE_IMG_URL + img_fullname
        final_save_path = os.path.join(IMG_SAVE_FOLDER, f"{yuan_frame_id}.jpg")

        try:
            res = requests.get(download_url, timeout=15)
            res.raise_for_status()
            with open(final_save_path, "wb") as f:
                f.write(res.content)
            print(f"下载成功 → {final_save_path} | frameId={frame_id}")

            draw_valid_score_on_img(final_save_path, valid_score)

        except requests.exceptions.RequestException as e:
            print(f"下载失败 [{download_url}] → 原因：{str(e)}")
        except Exception as e:
            print(f"保存失败 [{img_fullname}] → 原因：{str(e)}")
    print(f"第一步完成，图片均为纯frameId命名，且已绘制validScore值\n")


# ====================== 第二步：正则匹配、去重、分组排序 ======================
def extract_and_process_data():
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            log_content = f.read()
        print(f"日志读取成功，文件大小: {len(log_content) / 1024:.2f} KB")
    except Exception as e:
        print(f"日志读取失败：{e}")
        return None

    pattern = r'"frameId"\s*:\s*(\d+)\s*,?\s*"frontFaceFrame"\s*:\s*(\d+)\s*,?\s*"gender"\s*:\s*"([^"]+)"\s*,?\s*"grade"\s*:\s*"([^"]+)"\s*,?\s*"inArea"\s*:\s*(\w+)\s*,?\s*"inintTrackId"\s*:\s*(\d+)\s*,?\s*"initArea"\s*:\s*\[(.*?)\]\s*,?\s*"isRealAreaIndex"\s*:\s*(\w+)\s*,?\s*"joinSuccess"\s*:\s*(\-?\d+)\s*,?\s*"mark"\s*:\s*"([^"]+)"\s*,?\s*"name"\s*:\s*"([^"]+)"\s*,?\s*"pointArray"\s*:\s*\[(.*?)\]\s*,?\s*"readyTimer"\s*:\s*(\d+)\s*,?\s*"score"\s*:\s*(\d+)\s*,?\s*"sendFail"\s*:\s*(\w+)\s*,?\s*"sn"\s*:\s*"([^"]+)"\s*,?\s*"soundState"\s*:\s*(\d+)\s*,?\s*"startReady"\s*:\s*(\w+)\s*,?\s*"status"\s*:\s*"([^"]+)"\s*,?\s*"testId"\s*:\s*"([^"]+)"\s*,?\s*"timer"\s*:\s*(\d+)\s*,?\s*"trackId"\s*:\s*(\d+)\s*,?\s*(?:\"validScore\"\s*:\s*(\w+)\s*,?)?\s*'
    matches = re.findall(pattern, log_content, re.DOTALL | re.VERBOSE | re.MULTILINE)
    print(f"匹配到 {len(matches)} 条原始有效数据，开始去重排序处理")

    result_set = set()
    for match in matches:
        frame_id = f"frameId:{match[0]}"
        raw_point_array = re.sub(r'\s+', '', match[11])
        point_list = raw_point_array.split(',') if raw_point_array else []
        keep_point = point_list[-POINT_ARRAY_KEEP_NUM:]
        point_array = f"pointArray:[{','.join(keep_point)}]"
        status = f"status:{match[18]}"
        test_id = f"testId:{match[19]}"
        track_id = f"trackId:{match[21]}"
        result_line = SEPARATOR.join([frame_id, point_array, status, test_id, track_id])
        result_set.add(result_line)

    final_result = sorted(list(result_set),
                          key=lambda x: int(re.search(r'frameId:(\d+)', x).group(1)) if re.search(r'frameId:(\d+)',
                                                                                                  x) else 0)

    print(f"数据去重排序完成，共 {len(final_result)} 条有效数据\n")

    testid_groups = {}
    for line in final_result:
        current_testid = re.search(r'testId:([^|]+)', line).group(1) if re.search(r'testId:([^|]+)',
                                                                                  line) else "unknown"
        if current_testid not in testid_groups:
            testid_groups[current_testid] = []
        testid_groups[current_testid].append(line)

    return testid_groups

# ====================== 第三步：testId内数据拆分 ======================
def split_testid_data(data_lines):
    if not data_lines:
        return []

    segments = []
    current_segment = []
    VALID_STATUSES = {"FACE_RECOGNITED", "SPORTING"}

    for line in data_lines:
        curr_status_match = re.search(r'status:([^|]+)', line)
        curr_status = curr_status_match.group(1) if curr_status_match else None

        if curr_status not in VALID_STATUSES:
            if current_segment:
                segments.append(current_segment)
                current_segment = []
            continue

        if not current_segment:
            if curr_status == "FACE_RECOGNITED":
                current_segment = [line]
        else:
            has_sporting = any(re.search(r'status:SPORTING', l) for l in current_segment)
            if has_sporting and curr_status == "FACE_RECOGNITED":
                segments.append(current_segment)
                current_segment = [line]
            else:
                current_segment.append(line)

    if current_segment:
        segments.append(current_segment)

    return segments


def write_split_data_to_txt(all_split_data, mode='a', encoding='utf-8'):
    with open(SAVE_TXT_PATH, mode, encoding=encoding, newline='') as f:
        for test_id, seg_data in all_split_data.items():
            f.write("=" * 120 + "\n")
            f.write(f"【TESTID 独立分组】 testId = {test_id} | 共拆分为 {len(seg_data)} 个数据段 \n")
            f.write("=" * 120 + "\n\n")

            for seg_idx, single_segment in enumerate(seg_data, start=1):
                f.write("-" * 80 + "\n")
                f.write(
                    f"第 {seg_idx} 段数据 | 该段共 {len(single_segment)} 条数据 | 状态范围[FACE_RECOGNITED → SPORTING]\n")
                f.write("-" * 80 + "\n")

                for line_num, data_line in enumerate(single_segment, start=1):
                    f.write(f"     {line_num}. {data_line}\n")

                f.write("\n")
        f.write("\n" + "=" * 120 + "\n")
        f.write(f"数据统计：共处理 {len(all_split_data)} 个独立testId | 输出文件：{SAVE_TXT_PATH}\n")
        f.write("=" * 120 + "\n")


# ====================== 第四步：每组数据过滤（保留最后3个FACE + 全部SPORTING）======================
def filter_segment_data(segment_lines):
    if not segment_lines:
        return []

    face_lines = []
    sporting_lines = []
    for line in segment_lines:
        status_match = re.search(r'status:([^|]+)', line)
        if status_match:
            status = status_match.group(1)
            if status == "FACE_RECOGNITED":
                face_lines.append(line)
            elif status == "SPORTING":
                sporting_lines.append(line)

    filtered_face = face_lines[-3:] if len(face_lines) >= 3 else face_lines
    filtered_all = filtered_face + sporting_lines

    filtered_all_sorted = sorted(filtered_all,
                                 key=lambda x: int(re.search(r'frameId:(\d+)', x).group(1)) if re.search(
                                     r'frameId:(\d+)', x) else 0)

    return filtered_all_sorted


# ====================== 第五步：绘图 ======================

COLOR_CONFIG = {
    "P1_TRACK": "#E53E3E",  # 左脚踝轨迹-红色
    "P2_TRACK": "#3182CE",  # 右脚踝轨迹-蓝色
    "P1_P2_LINE": "#FFC0CB",  # 同帧两点连线-粉色
    "STATUS_FACE": "#F87171",  # FACE状态点-浅红
    "STATUS_OTHER": "#60A5FA"  # SPORTING状态点-浅蓝
}
UNIFIED_MARKER = "o"
POINT_SIZE = 3


def setup_matplotlib_chinese():
    mpl.rcParams['font.sans-serif'] = ['DejaVu Sans', 'SimHei', 'Microsoft YaHei', 'PingFang SC']
    mpl.rcParams['axes.unicode_minus'] = False
    if os.name == 'posix':
        try:
            mpl.rcParams['font.sans-serif'] = ['PingFang SC', 'Arial Unicode MS'] + mpl.rcParams['font.sans-serif']
        except:
            pass


def draw_track_for_segment(test_id, seg_idx, seg_lines):
    """
    1. 按分组frameId范围匹配downloaded_imgs下的纯frameId.jpg作为背景，无匹配则无背景
    2. 图像尺寸640×360，坐标点是归一化值(已除以宽高)，画布刻度固定0→1永不变化
    3. 图像左上角为原点
    4. frameId不连续断线、粉色虚线50%透明度、特征点/起止点标记
    5. pointArray = 左脚踝(x1,y1)+右脚踝(x2,y2) 归一化坐标
    """
    # 解析当前分组的轨迹数据+提取分组内frameId范围
    frame_info = []
    seg_frame_ids = []
    for line in seg_lines:
        f_id_match = re.search(r'frameId:(\d+)', line)
        p_arr_match = re.search(r'pointArray:\[(.*?)\]', line)
        sta_match = re.search(r'status:([^|]+)', line)
        # 新增：提取track_id
        track_id_match = re.search(r'trackId:(\d+)', line)

        if f_id_match and p_arr_match and sta_match and track_id_match:
            frame_id = int(f_id_match.group(1))
            seg_frame_ids.append(frame_id)
            point_arr = p_arr_match.group(1).split(',')
            # 新增：获取track_id值
            track_id = track_id_match.group(1)
            if len(point_arr) == 4:
                x1, y1, x2, y2 = [float(i) for i in point_arr]
                status = sta_match.group(1)
                mark_status = "FACE_RECOGNITED" if status == "FACE_RECOGNITED" else "SPORTING"
                # 新增：将track_id加入frame_info元组
                frame_info.append((frame_id, x1, y1, x2, y2, mark_status, track_id))

    if not frame_info:
        print(f"  → testId {test_id} 第 {seg_idx} 段无有效轨迹数据，跳过绘图")
        return
    # 匹配背景图
    bg_img_path = None
    if seg_frame_ids:
        min_fid = min(seg_frame_ids)
        max_fid = max(seg_frame_ids)
        for fid in range(min_fid, max_fid + 1):
            temp_img_path = os.path.join(IMG_SAVE_FOLDER, f"{fid}.jpg")
            if os.path.exists(temp_img_path):
                bg_img_path = temp_img_path
                break

    plt.figure(figsize=(8, 4.5), dpi=100)  # 8:4.5 严格对应640:360
    ax = plt.gca()
    ax.set_xlim(0, 1)  # X轴固定0到1
    ax.set_ylim(0, 1)  # Y轴固定0到1
    ax.set_xlabel('归一化X坐标', fontsize=12)
    ax.set_ylabel('归一化Y坐标', fontsize=12)
    ax.set_title(
        f'testId = {test_id} (第 {seg_idx} 段)\nframeId范围:{min(seg_frame_ids)}-{max(seg_frame_ids)}',
        fontsize=14, pad=20)

    if bg_img_path:
        try:
            bg_img = cv2.imread(bg_img_path)
            bg_img = cv2.cvtColor(bg_img, cv2.COLOR_BGR2RGB)  # BGR转RGB适配matplotlib
            ax.imshow(bg_img, extent=[0, 1, 1, 0], aspect='auto')  # 铺满0-1坐标区域
            print(f"  → 匹配到背景图：{bg_img_path}")
        except Exception as e:
            print(f"  → 背景图加载失败：{e}，使用纯白画布")

    # frameId不连续则自动断线
    temp_p1_x, temp_p1_y = [], []
    temp_p2_x, temp_p2_y = [], []
    prev_frame_id = frame_info[0][0]

    for i in range(len(frame_info)):
        # 调整：适配新增的track_id字段
        curr_frame_id, x1, y1, x2, y2, _, _ = frame_info[i]

        if curr_frame_id - prev_frame_id != 1:
            if temp_p1_x and temp_p1_y:
                ax.plot(temp_p1_x, temp_p1_y, color=COLOR_CONFIG["P1_TRACK"], linewidth=0.8, alpha=0.8)
                ax.plot(temp_p2_x, temp_p2_y, color=COLOR_CONFIG["P2_TRACK"], linewidth=0.8, alpha=0.8)
            temp_p1_x, temp_p1_y = [], []
            temp_p2_x, temp_p2_y = [], []

        temp_p1_x.append(x1)
        temp_p1_y.append(y1)
        temp_p2_x.append(x2)
        temp_p2_y.append(y2)
        prev_frame_id = curr_frame_id

        ax.plot([x1, x2], [y1, y2], color=COLOR_CONFIG["P1_P2_LINE"],
                linewidth=0.5, alpha=0.5, linestyle='--', label='同帧左右脚踝连线' if i == 0 else "")

    # 绘制最后一段轨迹线
    if temp_p1_x and temp_p1_y:
        ax.plot(temp_p1_x, temp_p1_y, color=COLOR_CONFIG["P1_TRACK"], linewidth=0.8, alpha=0.8, label='左脚踝 轨迹线')
        ax.plot(temp_p2_x, temp_p2_y, color=COLOR_CONFIG["P2_TRACK"], linewidth=0.8, alpha=0.8, label='右脚踝 轨迹线')

    # 绘制特征点+起止点标记
    p1_x = [info[1] for info in frame_info]
    p1_y = [info[2] for info in frame_info]
    p2_x = [info[3] for info in frame_info]
    p2_y = [info[4] for info in frame_info]
    status_list = [info[5] for info in frame_info]

    for i in range(len(frame_info)):
        curr_status = status_list[i]
        point_color = COLOR_CONFIG["STATUS_FACE"] if curr_status == "FACE_RECOGNITED" else COLOR_CONFIG["STATUS_OTHER"]
        ax.scatter(p1_x[i], p1_y[i], color=point_color, marker=UNIFIED_MARKER, s=POINT_SIZE, alpha=0.9, zorder=5)
        ax.scatter(p2_x[i], p2_y[i], color=point_color, marker=UNIFIED_MARKER, s=POINT_SIZE, alpha=0.9, zorder=5)

    # 起止点标记
    ax.scatter(p1_x[0], p1_y[0], color='#6366F1', s=5, zorder=6, label='轨迹起点')
    ax.scatter(p2_x[0], p2_y[0], color='#6366F1', s=5, zorder=6)
    ax.scatter(p1_x[-1], p1_y[-1], color='#F97316', s=5, zorder=6, label='轨迹终点')
    ax.scatter(p2_x[-1], p2_y[-1], color='#F97316', s=5, zorder=6)

    # 新增：提取起点和终点的track_id
    start_track_id = frame_info[0][6]
    end_track_id = frame_info[-1][6]

    # 图例信息
    legend_elements = [
        plt.Line2D([], [], color=COLOR_CONFIG["P1_TRACK"], linewidth=1.5),
        plt.Line2D([], [], color=COLOR_CONFIG["P2_TRACK"], linewidth=1.5),
        plt.Line2D([], [], color=COLOR_CONFIG["P1_P2_LINE"], linewidth=1.35, linestyle='--', alpha=0.5),
        plt.Line2D([], [], color='#6366F1', marker='o', linestyle='None', markersize=7.5),
        plt.Line2D([], [], color='#F97316', marker='o', linestyle='None', markersize=7.5),
        plt.Line2D([], [], color='#a8df64', marker='o', linestyle='None', markersize=2)
    ]
    legend_labels = [
        '左脚踝 轨迹线',
        '右脚踝 轨迹线',
        '同帧左右脚踝连线',
        # 修改：添加track_id到图例标签
        f'轨迹起点_trackid:{start_track_id}',
        f'轨迹终点_trackid:{end_track_id}',
        '落地点脚跟'
    ]
    ax.legend(handles=legend_elements, labels=legend_labels, loc='best', fontsize=7.5)
    ax.invert_yaxis()
    ax.grid(True, alpha=0.4, linestyle='--')
    plt.tight_layout()

    # 保存轨迹图
    os.makedirs(SAVE_IMG_DIR, exist_ok=True)
    save_filename = f"testId_{test_id}_轨迹图_第{seg_idx}段.png"
    save_path = os.path.join(SAVE_IMG_DIR, save_filename)
    plt.savefig(save_path, dpi=SAVE_IMG_DPI, bbox_inches='tight', facecolor='white', edgecolor='none')
    print(f"  → 已导出轨迹图 → {save_path}")
    plt.close()


# ====================== 主函数 ======================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('app_log', type=str, help='camera日志文件路径（例如：1.log、./logs/2.log）')
    # parser.add_argument('img_ip',
    #                     type=str,
    #                     nargs='?',
    #                     default='192.168.3.175',
    #                     help='图片服务器的IP地址（默认：192.168.3.175）')
    parser.add_argument('img_ip',
                        type=str,
                        help='图片服务器的IP地址（必填，无默认值）')
    args = parser.parse_args()
    LOG_FILE = args.app_log
    BASE_IMG_URL = f"http://{args.img_ip}/img/"

    download_target_images()
    testid_groups = extract_and_process_data()
    if not testid_groups:
        print("数据处理失败，退出程序")
        exit(1)

    setup_matplotlib_chinese()
    total_testid_count = len(testid_groups)
    print("=" * 60)
    print(f"数据统计结果 → 本次共处理【{total_testid_count}个】独立的testId")
    print("=" * 60)

    all_split_result = {}
    for test_id, data_lines in testid_groups.items():
        segments = split_testid_data(data_lines)
        all_split_result[test_id] = segments

        group_count = len(segments)
        print(f"\n testId: {test_id} → 共拆分为【{group_count}个】有效分组")
        write_split_data_to_txt(all_split_result, mode='w')

        for seg_idx, seg_lines in enumerate(segments, 1):
            filtered_lines = filter_segment_data(seg_lines)
            if not filtered_lines:
                print(f"  → testId {test_id} 第 {seg_idx} 段过滤后无数据，跳过绘图")
                continue
            draw_track_for_segment(test_id, seg_idx, filtered_lines)

    print(f"\n 所有拆分后的数据已完整写入 → {SAVE_TXT_PATH}")
    print(" \n 所有testId的轨迹图绘制完成！")