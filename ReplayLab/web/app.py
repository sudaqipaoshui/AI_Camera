# -*- coding: utf-8 -*-
"""ReplayLab Web 后端 (二期 MVP)
复用一期 run_test.py 命令行流水线(subprocess 异步执行), 提供:
  视频库 / 上传 / 一键发起测试 / 任务实时日志 / 报告中心
前后端同源(Flask 同时 serve static), 无需 CORS。单设备全局只允许一个测试在跑。
"""
import copy
import hashlib
import json
import os
import re
import requests
import shutil
import subprocess
import sys
import threading
import time
import uuid

from flask import Flask, jsonify, request, send_file, send_from_directory

HERE = os.path.dirname(os.path.abspath(__file__))          # web/
ROOT = os.path.dirname(HERE)                                # ReplayLab/
PROJECT_ROOT = os.path.dirname(ROOT)                        # 项目根, envloader.py 所在
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
import envloader  # noqa: E402  统一凭据加载器

ITEMS_PATH = os.path.join(ROOT, "items.json")
REPORTS = os.path.join(ROOT, "reports")
STATIC = os.path.join(HERE, "static")
# 跑 run_test.py 用的解释器: 优先环境变量, 其次当前解释器, 最后回落到已知 venv。
# 不再写死绝对路径, 换机器/换 venv 时不必改代码。
VENV_PY = (envloader.get("REPLAYLAB_PYTHON")
           or sys.executable
           or r"E:\TestTools\venv\Scripts\python.exe")
RUN_TEST = os.path.join(ROOT, "run_test.py")

KB = json.load(open(ITEMS_PATH, encoding="utf-8"))
SERVE_DIR = KB["_env"]["serve_dir"]                         # E:/TestTools
FFMPEG = KB["_env"]["ffmpeg"]
FFPROBE = os.path.join(os.path.dirname(FFMPEG), "ffprobe.exe")
FRAMES_DIR = os.path.join(REPORTS, "_frames")
os.makedirs(FRAMES_DIR, exist_ok=True)

app = Flask(__name__, static_folder=STATIC, static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = None                     # 允许大视频上传
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0                 # 静态资源不缓存, 前端更新即生效
app.json.ensure_ascii = False                               # 中文不转义(Flask3写法, JSON_AS_ASCII已废弃)

# 平台视图: 把测试结果库(test_run / case_result / metric)接到同一个界面上。
# 独立成 blueprint, 库不可用时只让那几个接口返回 ok=false, 不影响本页原有的
# 视频库/发起测试/报告中心等功能。
if HERE not in sys.path:
    sys.path.insert(0, HERE)
try:
    from platform_api import bp as _platform_bp
    app.register_blueprint(_platform_bp)
except Exception as _exc:  # pragma: no cover
    print(f"[warn] 平台视图接口未加载: {type(_exc).__name__}: {_exc}")

TASKS = {}
TLOCK = threading.Lock()


# ---------------- 页面 ----------------
@app.route("/")
def index():
    r = send_from_directory(STATIC, "index.html")
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return r


# ---------------- 项目 ----------------
@app.route("/api/items")
def api_items():
    out = []
    for k, v in _load_kb().items():
        if k.startswith("_"):
            continue
        out.append({
            "key": k, "name": v.get("name"), "itemId": v.get("itemId"),
            "score_field": v.get("score_field"), "timer": v.get("timer"),
            "need_start_sport": v.get("need_start_sport"),
            "has_grid8": bool(v.get("grid8")),
            "has_golden": bool(v.get("golden", {}).get("points") or v.get("golden", {}).get("scores")),
        })
    return jsonify(out)


# ---------------- 视频库 ----------------
def _scan_videos():
    vids = []
    for dirpath, _, files in os.walk(SERVE_DIR):
        for fn in files:
            if not fn.lower().endswith(".mp4"):
                continue
            fp = os.path.join(dirpath, fn)
            try:
                st = os.stat(fp)
            except OSError:
                continue
            vids.append({
                "name": fn,
                "rel": os.path.relpath(fp, SERVE_DIR).replace("\\", "/"),
                "size": st.st_size,
                "mtime": st.st_mtime,
            })
    vids.sort(key=lambda x: x["mtime"], reverse=True)
    return vids


@app.route("/api/videos")
def api_videos():
    return jsonify(_scan_videos())


@app.route("/api/upload", methods=["POST"])
def api_upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "未选择文件"}), 400
    name = os.path.basename(f.filename.replace("\\", "/")).strip()
    if ".." in name or not name.lower().endswith(".mp4"):
        return jsonify({"error": "仅支持 .mp4 且文件名非法"}), 400
    dst = os.path.join(SERVE_DIR, name)
    f.save(dst)  # werkzeug 流式落盘, 大文件不进内存
    return jsonify({"ok": True, "name": name, "size": os.path.getsize(dst)})


# ---------------- 发起测试 ----------------
def _reader(task):
    proc = task["proc"]
    try:
        for line in iter(proc.stdout.readline, ""):
            with TLOCK:
                task["log"].append(line.rstrip("\n"))
        proc.wait()
        with TLOCK:
            task["status"] = "done" if proc.returncode == 0 else "failed"
            task["returncode"] = proc.returncode
    except Exception as e:
        with TLOCK:
            task["log"].append(f"[reader异常] {e}")
            task["status"] = "failed"
    with TLOCK:
        task["end_time"] = time.time()


@app.route("/api/run", methods=["POST"])
def api_run():
    data = request.get_json(force=True)
    item = data.get("item")
    rel = data.get("video")
    duration = int(data.get("duration", 800))
    grid8 = bool(data.get("grid8"))
    skip_deploy = bool(data.get("skip_deploy"))

    if item not in _load_kb() or item.startswith("_"):
        return jsonify({"error": f"未知项目 {item}"}), 400
    video = os.path.join(SERVE_DIR, rel) if rel else None
    if not video or not os.path.isfile(video):
        return jsonify({"error": f"视频不存在 {rel}"}), 400

    with TLOCK:
        for t in TASKS.values():
            if t["status"] == "running":
                return jsonify({"error": f"已有测试在跑(task {t['id'][:8]}), 单设备不可并发"}), 409

    cmd = [VENV_PY, RUN_TEST, "--item", item, "--video", video, "--duration", str(duration)]
    if grid8:
        cmd.append("--grid8")
    if skip_deploy:
        cmd.append("--skip-deploy")

    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", bufsize=1)
    tid = uuid.uuid4().hex
    task = {"id": tid, "item": item, "video": rel, "duration": duration,
            "grid8": grid8, "skip_deploy": skip_deploy, "cmd": " ".join(cmd),
            "status": "running", "log": [], "start_time": time.time(),
            "proc": proc, "returncode": None, "end_time": None}
    with TLOCK:
        TASKS[tid] = task
    threading.Thread(target=_reader, args=(task,), daemon=True).start()
    return jsonify({"ok": True, "task_id": tid})


@app.route("/api/tasks")
def api_tasks():
    with TLOCK:
        out = [{"id": t["id"], "item": t["item"], "video": t["video"],
                "status": t["status"], "start_time": t["start_time"],
                "end_time": t["end_time"], "returncode": t["returncode"],
                "log_lines": len(t["log"])} for t in TASKS.values()]
    out.sort(key=lambda x: x["start_time"], reverse=True)
    return jsonify(out)


@app.route("/api/task/<tid>")
def api_task(tid):
    since = int(request.args.get("since", 0))
    with TLOCK:
        t = TASKS.get(tid)
        if not t:
            return jsonify({"error": "无此任务"}), 404
        log = t["log"][since:]
        return jsonify({"id": tid, "status": t["status"], "log": log,
                        "total": len(t["log"]), "returncode": t["returncode"],
                        "item": t["item"], "video": t["video"],
                        "start_time": t["start_time"], "end_time": t["end_time"]})


# ---------------- 项目管理 ----------------
def _load_kb():
    """每次从磁盘读最新 items.json, 避免全局缓存与磁盘(命令行/编辑器改动)不一致。"""
    with open(ITEMS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save_kb(kb):
    """原子写 items.json + 备份。传入读自磁盘并合入修改后的 kb。"""
    shutil.copy2(ITEMS_PATH, ITEMS_PATH + ".bak")
    tmp = ITEMS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(kb, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ITEMS_PATH)


@app.route("/api/item/<key>")
def api_item_detail(key):
    kb = _load_kb()
    if key not in kb or key.startswith("_"):
        return jsonify({"error": f"未知项目 {key}"}), 404
    return jsonify({"key": key, "config": kb[key]})


@app.route("/api/item/save", methods=["POST"])
def api_item_save():
    data = request.get_json(force=True)
    key = data.get("key")
    cfg = data.get("config")
    kb = _load_kb()
    if key not in kb or key.startswith("_"):
        return jsonify({"error": f"未知项目 {key}"}), 404
    if not isinstance(cfg, dict) or "itemId" not in cfg or "golden" not in cfg:
        return jsonify({"error": "config 非法(需含 itemId/golden)"}), 400
    kb[key] = cfg
    _save_kb(kb)
    return jsonify({"ok": True, "key": key})


@app.route("/api/item/create", methods=["POST"])
def api_item_create():
    data = request.get_json(force=True)
    key = (data.get("key") or "").strip()
    kb = _load_kb()
    if not key or key in kb or key.startswith("_") or not key.replace("_", "").isalnum():
        return jsonify({"error": "key 非法或已存在(仅限字母数字下划线)"}), 400
    cfg = copy.deepcopy(kb["_template"])
    cfg["name"] = data.get("name") or key
    cfg["itemId"] = int(data.get("itemId") or 0)
    cfg["score_field"] = data.get("score_field") or "score"
    cfg["timer"] = data.get("timer")            # int 秒 或 null
    cfg["need_start_sport"] = bool(data.get("need_start_sport"))
    cfg["golden"] = {"type": data.get("golden_type") or "final",
                     "scores": [], "points": [], "loop_frames": 0,
                     "fps": 30, "total_per_loop": 0, "round_sec": cfg["timer"]}
    kb[key] = cfg
    _save_kb(kb)
    return jsonify({"ok": True, "key": key})


# ---------------- 设备管理(多设备切换) ----------------
def _default_device():
    """新建设备的默认字段(X5 路径模板, 接 X3 时按型号再调)。"""
    return {"name": "", "model": "X5", "ip": "", "ssh_user": "root", "ssh_pass": "",
            "video_dir_device": "/userdata/video",
            "rtsp_config": "/userdata/camera_config/rtsp_config.json",
            "item_json": "/userdata/item.json",
            "log_glob": "/userdata/deploy/log/logger_$(date +%Y-%m-%d_%H).log",
            "token": ""}


@app.route("/api/devices")
def api_devices():
    env = _load_kb()["_env"]
    devs = env.get("devices") or {}
    active = env.get("active")
    out = [{"key": k, "name": d.get("name"), "model": d.get("model", ""),
            "ip": d.get("ip"), "ssh_user": d.get("ssh_user", "root"),
            "active": (k == active)} for k, d in devs.items()]
    return jsonify({"active": active, "devices": out})


@app.route("/api/device/select", methods=["POST"])
def api_device_select():
    key = (request.get_json(force=True).get("key") or "").strip()
    kb = _load_kb()
    env = kb["_env"]
    if key not in (env.get("devices") or {}):
        return jsonify({"error": "无此设备"}), 404
    env["active"] = key
    _save_kb(kb)
    return jsonify({"ok": True, "active": key})


@app.route("/api/device/save", methods=["POST"])
def api_device_save():
    d = request.get_json(force=True)
    kb = _load_kb()
    env = kb["_env"]
    devs = env.setdefault("devices", {})
    key = (d.get("key") or "").strip()            # 原 key(编辑时传); 空=新建
    name = (d.get("name") or "").strip()
    ip = (d.get("ip") or "").strip()
    if not name or not ip:
        return jsonify({"error": "名称/IP 必填"}), 400
    new_key = (d.get("new_key") or "").strip() or key
    if not new_key:
        new_key = re.sub(r"[^A-Za-z0-9_]", "_", f"{d.get('model', 'dev')}_{ip.replace('.', '_')}")
    base = dict(devs.get(key) or _default_device())   # 编辑保留原字段, 新建用模板
    base.update({"name": name, "model": d.get("model", "X5"), "ip": ip,
                 "ssh_user": d.get("ssh_user") or "root",
                 "ssh_pass": d.get("ssh_pass", base.get("ssh_pass", "")),
                 "token": d.get("token", base.get("token", ""))})
    if key and key != new_key and key in devs:
        del devs[key]
        if env.get("active") == key:
            env["active"] = new_key
    devs[new_key] = base
    if not env.get("active"):
        env["active"] = new_key
    _save_kb(kb)
    return jsonify({"ok": True, "key": new_key})


@app.route("/api/device/delete", methods=["POST"])
def api_device_delete():
    key = (request.get_json(force=True).get("key") or "").strip()
    kb = _load_kb()
    env = kb["_env"]
    devs = env.get("devices") or {}
    if key not in devs:
        return jsonify({"error": "无此设备"}), 404
    if env.get("active") == key:
        return jsonify({"error": "不能删除当前激活设备, 请先切换到别的设备"}), 400
    del devs[key]
    _save_kb(kb)
    return jsonify({"ok": True})


def _get_token(dev):
    """设备 token 优先(items.json 的 devices[].token), 空则取 .env 的 YUNTIYU_X_TOKEN。"""
    if dev.get("token"):
        return dev["token"]
    try:
        return envloader.require("YUNTIYU_X_TOKEN")
    except Exception:
        return ""


@app.route("/api/device/firmware")
def api_device_firmware():
    kb = _load_kb()
    env = kb["_env"]
    dev = (env.get("devices") or {}).get(env.get("active")) or {}
    ip = dev.get("ip")
    if not ip:
        return jsonify({"ok": False, "error": "无激活设备"}), 400
    try:
        r = requests.get(f"http://{ip}/control/getVersion",
                         headers={"x_token": _get_token(dev)}, timeout=6)
        j = r.json()
        return jsonify({"ok": True, "version": j.get("Version") or j.get("version") or "",
                        "ip": ip, "model": dev.get("model", "")})
    except Exception as e:
        return jsonify({"ok": False, "error": f"设备离线或读取失败: {e}"})


FW_DIR = os.path.join(SERVE_DIR, "firmware")  # 固件库(8000端口共享, 摄像头经HTTP从此下载)


def _md5(fp):
    h = hashlib.md5()
    with open(fp, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@app.route("/api/firmware/list")
def api_firmware_list():
    """列固件库, 按型号分组 {x3:[...], x5:[...]}。"""
    kb = _load_kb(); env = kb["_env"]
    out = {}
    for model in ("x3", "x5"):
        d = os.path.join(FW_DIR, model)
        pkgs = []
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                fp = os.path.join(d, f)
                if os.path.isfile(fp) and not f.startswith("."):
                    pkgs.append({"name": f, "size": os.path.getsize(fp)})
        out[model] = pkgs
    return jsonify({"ok": True, "fw": out,
                    "http_base": f"http://{env['http_host']}:{env['http_port']}"})


@app.route("/api/firmware/flash", methods=["POST"])
def api_firmware_flash():
    """固件OTA刷机: 型号强校验(固件必须在对应型号目录, 防刷错变砖) → 设备HTTP下载 → 触发更新。
    流程: codeDownload{md5,downloadUrl} → update{md5,increment=0全量}。校验设备返回码, 拒绝时透传真实原因。
    实测结论: 本批X5设备整固件OTA是"云端下发升级码"驱动 —— 需先 getCodePackageInfo?code=云端升级码 建任务,
    无云端任务时 codeDownload 返回 code=500 'please call GetCodePackageInfo', 本地直刷不被设备接受。"""
    d = request.get_json(force=True)
    key = (d.get("key") or "").strip()
    fname = (d.get("file") or "").strip()
    kb = _load_kb(); env = kb["_env"]; devs = env.get("devices") or {}
    if key not in devs:
        return jsonify({"ok": False, "error": "设备不存在"}), 404
    dev = devs[key]
    model = (dev.get("model") or "").lower()
    if model not in ("x3", "x5"):
        return jsonify({"ok": False, "error": f"设备型号未知: {dev.get('model')}"}), 400
    # 型号强校验: 固件必须在 firmware/{型号}/ 下
    fp = os.path.join(FW_DIR, model, fname)
    if not fname or not os.path.isfile(fp):
        return jsonify({"ok": False, "error": f"firmware/{model}/ 下无此固件: {fname}"}), 404
    md5 = _md5(fp)
    url = f"http://{env['http_host']}:{env['http_port']}/firmware/{model}/{fname}"
    ip = dev["ip"]; token = _get_token(dev)
    # 1) codeDownload: 校验设备返回码(设备拒绝必须报错透传, 不能"假成功")
    try:
        r1 = requests.post(f"http://{ip}/control/codeDownload", json={"md5": md5, "downloadUrl": url},
                           headers={"x_token": token}, timeout=600)
        j1 = r1.json()
    except Exception as e:
        return jsonify({"ok": False, "error": f"codeDownload 请求失败(设备离线?): {e}"})
    c1 = j1.get("code", j1.get("Code", r1.status_code))
    if c1 != 200:
        tip = "本设备整固件OTA需云端下发升级码(先getCodePackageInfo建任务), 本地直刷不被接受" if c1 == 500 else ""
        return jsonify({"ok": False, "error": f"设备拒绝下载(code={c1}): {j1.get('message') or j1.get('Message') or j1}", "tip": tip})
    # 2) update: 校验 Code(成功为0)
    try:
        r2 = requests.post(f"http://{ip}/control/update", json={"md5": md5, "increment": 0},
                           headers={"x_token": token}, timeout=60)
        j2 = r2.json()
    except Exception as e:
        return jsonify({"ok": False, "error": f"update 触发失败: {e}", "download": j1})
    c2 = j2.get("Code", j2.get("code", 0))
    if c2 not in (0, 200):
        return jsonify({"ok": False, "error": f"设备拒绝更新(Code={c2}): {j2.get('Messages') or j2.get('message') or j2}", "download": j1})
    return jsonify({"ok": True, "md5": md5, "url": url, "download": j1, "update": j2})


# ---------------- 视频工具(框点位/元信息) ----------------
def _video_abs(rel):
    """rel(相对serve_dir) -> 绝对路径, 防目录穿越。"""
    ap = os.path.abspath(os.path.join(SERVE_DIR, rel or ""))
    if not ap.startswith(os.path.abspath(SERVE_DIR)) or not os.path.isfile(ap):
        return None
    return ap


@app.route("/api/videometa")
def api_videometa():
    ap = _video_abs(request.args.get("video"))
    if not ap:
        return jsonify({"error": "视频不存在"}), 400
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
             "-show_entries", "format=duration", "-of", "json", ap],
            capture_output=True, text=True, timeout=60).stdout
        j = json.loads(out)
        st = j["streams"][0]
        num, den = st.get("r_frame_rate", "30/1").split("/")
        fps = float(num) / float(den) if float(den) else 30.0
        return jsonify({"width": st.get("width"), "height": st.get("height"),
                        "fps": round(fps, 3),
                        "frames": int(st.get("nb_frames") or 0),
                        "duration": round(float(j["format"].get("duration", 0)), 2)})
    except Exception as e:
        return jsonify({"error": f"ffprobe失败: {e}"}), 500


@app.route("/api/frame")
def api_frame():
    ap = _video_abs(request.args.get("video"))
    if not ap:
        return jsonify({"error": "视频不存在"}), 400
    t = float(request.args.get("t", 5))
    w = int(request.args.get("w", 960))          # 缩略宽度, 画布显示用
    out = os.path.join(FRAMES_DIR, f"f_{uuid.uuid4().hex[:10]}.jpg")
    try:
        subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error",
                        "-ss", str(t), "-i", ap, "-frames:v", "1",
                        "-vf", f"scale={w}:-1", "-q:v", "3", "-y", out],
                       check=True, timeout=120)
        return send_file(out, mimetype="image/jpeg")
    except Exception as e:
        return jsonify({"error": f"抽帧失败: {e}"}), 500


# ---------------- 报告 ----------------
def _scan_reports():
    reps = []
    for fn in os.listdir(REPORTS):
        if not fn.endswith(".md"):
            continue
        fp = os.path.join(REPORTS, fn)
        st = os.stat(fp)
        base = fn[:-3]
        reps.append({"name": fn, "base": base, "size": st.st_size, "mtime": st.st_mtime,
                     "has_jsonl": os.path.exists(os.path.join(REPORTS, base + ".jsonl"))})
    reps.sort(key=lambda x: x["mtime"], reverse=True)
    return reps


@app.route("/api/reports")
def api_reports():
    return jsonify(_scan_reports())


@app.route("/api/report/<name>")
def api_report(name):
    if ".." in name or not name.endswith(".md"):
        return jsonify({"error": "非法"}), 400
    fp = os.path.join(REPORTS, name)
    if not os.path.isfile(fp):
        return jsonify({"error": "报告不存在"}), 404
    return jsonify({"name": name, "content": open(fp, encoding="utf-8").read()})


@app.route("/api/report/raw/<name>")
def api_report_raw(name):
    if ".." in name:
        return jsonify({"error": "非法"}), 400
    return send_from_directory(REPORTS, name, as_attachment=True)


if __name__ == "__main__":
    os.makedirs(REPORTS, exist_ok=True)
    print(f"视频库目录: {SERVE_DIR}")
    print(f"报告目录: {REPORTS}")
    print("ReplayLab Web: http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, threaded=True)
