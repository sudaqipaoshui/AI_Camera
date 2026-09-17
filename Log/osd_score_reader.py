# -*- coding: utf-8 -*-
"""摄像头 OSD 成绩基准工具（golden 数据管理）

用途：为回放测试素材建立「成绩基准文件」（golden），供 E2E 用例断言比对。

主流程（半自动，推荐）：
    # 1. 提取指定时刻的 OSD 条带放大图（人工读数用）
    python Log/osd_score_reader.py 视频路径 --extract --time 57
    # 2. 人工读图后固化 golden（8路成绩 + 总计）
    python Log/osd_score_reader.py 视频路径 --set "125,138,102,115,127,153,139,138" --total 1726
    # golden 存至 Log/golden/<视频名>.json

作为库使用（E2E 用例断言基准）：
    from Log.osd_score_reader import load_golden
    golden = load_golden("双脚跳绳")   # -> {"scores": [...], "total": 1726, ...}

附：--ocr 为实验性自动识别（模板匹配）。720p 低码率 + 6px 小字号下
识别不可靠，仅作参考，不作为断言依据；高清无 OSD 压缩素材可重新评估。
"""
import argparse
import datetime
import json
import os

import cv2
import numpy as np

# OSD 条带相对位置（相对帧高，适配不同分辨率）
STRIP_Y_START = 0.958

GOLDEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden")
CROP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "osd_crops")


def read_frame_at(video_path: str, t_sec: float = None) -> np.ndarray:
    """读取指定秒的帧；t_sec=None 读倒数第 2 秒"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if t_sec is None:
        t_sec = max(0.0, total / fps - 2.0)
    idx = min(total - 1, int(t_sec * fps))
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"读取帧失败: t={t_sec}s")
    return frame


def video_meta(video_path: str) -> dict:
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return {"fps": round(fps, 3), "frames": total,
            "duration_sec": round(total / fps, 2), "resolution": f"{w}x{h}"}


def extract_osd_image(video_path: str, t_sec: float = None,
                      scale: int = 3) -> str:
    """提取 OSD 条带并放大保存，返回图片路径（供人工读数）"""
    frame = read_frame_at(video_path, t_sec)
    strip = frame[int(frame.shape[0] * STRIP_Y_START):, :]
    enlarged = cv2.resize(strip, None, fx=scale, fy=scale,
                          interpolation=cv2.INTER_CUBIC)
    os.makedirs(CROP_DIR, exist_ok=True)
    name = os.path.splitext(os.path.basename(video_path))[0]
    t_tag = "end" if t_sec is None else f"{int(t_sec)}s"
    out = os.path.join(CROP_DIR, f"{name}_osd_{t_tag}.png")
    cv2.imwrite(out, enlarged)
    return out


def _golden_path(video_name: str) -> str:
    return os.path.join(GOLDEN_DIR, f"{video_name}.json")


def save_golden(video_path: str, scores: list, total: int,
                t_sec: float = None, note: str = "") -> str:
    """固化成绩基准到 golden JSON"""
    assert len(scores) == 8, "必须为 8 路成绩"
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    name = os.path.splitext(os.path.basename(video_path))[0]
    data = {
        "video": os.path.basename(video_path),
        "scores": scores,          # 8 路点位成绩（与画面中点位顺序一致）
        "total": total,            # OSD 总计
        "source": "人工读数(OSD)",  # 基准来源
        "osd_time_sec": t_sec,     # 读数时刻（视频内秒）
        "note": note,
        "meta": video_meta(video_path),
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    path = _golden_path(name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def load_golden(video_name: str) -> dict:
    """加载成绩基准（供 E2E 用例断言）"""
    path = _golden_path(video_name)
    if not os.path.exists(path):
        raise RuntimeError(f"golden 不存在: {path}，请先 --extract 读数并 --set 固化")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser(description="摄像头OSD成绩基准工具")
    ap.add_argument("video", help="视频文件路径")
    ap.add_argument("--extract", action="store_true",
                    help="提取 OSD 条带放大图（人工读数用）")
    ap.add_argument("--time", type=float, default=None, help="视频内时刻(秒)")
    ap.add_argument("--set", dest="scores", default=None,
                    help="固化 golden：8 路成绩，逗号分隔，如 '125,138,102,115,127,153,139,138'")
    ap.add_argument("--total", type=int, default=None, help="OSD 总计数")
    ap.add_argument("--note", default="", help="备注（写入 golden）")
    args = ap.parse_args()

    if args.extract:
        out = extract_osd_image(args.video, args.time)
        print(f"OSD 放大图已保存: {out}")
        print("请查看图片读数，然后执行:")
        print(f'  python Log/osd_score_reader.py "{args.video}" '
              f'--set "路1,路2,...,路8" --total 总计')
        return

    if args.scores:
        scores = [int(s) for s in args.scores.split(",")]
        path = save_golden(args.video, scores, args.total, args.time, args.note)
        print(f"golden 已固化: {path}")
        print(open(path, encoding="utf-8").read())
        return

    ap.print_help()


if __name__ == "__main__":
    main()
