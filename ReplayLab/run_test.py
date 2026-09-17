# -*- coding: utf-8 -*-
"""ReplayLab 一期: 一键视频注入测试流水线
用法:
  python run_test.py --item kaihetiao --video E:\\TestTools\\kaihetiao_8grid_12m.mp4
  python run_test.py --item kaihetiao --video E:\\TestTools\\kaihetiao_4k_20m.mp4 --grid8 --duration 800
  python run_test.py --item kaihetiao --video ... --dry-run     # 只打印计划不动设备
流程: 视频准备(可选grid8拼贴) -> 部署(上传/点位/切流/重启) -> 等待就位 -> 采集 -> 分析 -> 报告归档
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # 项目根, envloader.py 所在
sys.path.insert(0, os.path.join(ROOT, "E2E"))
sys.path.insert(0, ROOT)
import paramiko
import requests
import websocket
import x3_pb2 as pb2
import envloader  # 统一凭据加载器

KB = json.load(open(os.path.join(HERE, "items.json"), encoding="utf-8"))
# 多设备: devices[active] 的设备级字段 覆盖 _env 全局字段, 合并出当前有效环境(扁平)。
# 旧版扁平 _env(无 devices)时 _dev={}, ENV 即原 _env, 完全向后兼容。
_raw_env = KB["_env"]
_devs = _raw_env.get("devices") or {}
_active = _raw_env.get("active")
_dev = _devs.get(_active, {}) if _active else {}
ENV = {**{k: v for k, v in _raw_env.items() if k not in ("devices", "active")}, **_dev}
IP = ENV["ip"]
BASE = f"http://{IP}"
DEV_NAME = _dev.get("name") or IP
DEV_MODEL = _dev.get("model", "")

# items.json 是入库文件, 刻意不写口令; 口令统一从 .env 取。
if not ENV.get("ssh_pass"):
    ENV["ssh_pass"] = envloader.require("CAMERA_SSH_PASSWORD")

# token: 优先当前设备在 items.json 里配的 token, 否则回退 .env 的 YUNTIYU_X_TOKEN
TOKEN = ENV.get("token") or envloader.require("YUNTIYU_X_TOKEN")
H_JSON = {"x_token": TOKEN, "Content-Type": "application/json"}

REPORTS = os.path.join(HERE, "reports")
os.makedirs(REPORTS, exist_ok=True)
# 跑前设备配置快照(不入库), 供跑完还原
STATE_DIR = os.path.join(HERE, "_state")

ap = argparse.ArgumentParser(description="ReplayLab 一键视频注入测试")
ap.add_argument("--item", required=True, help="项目key(items.json), 如 kaihetiao/rope")
ap.add_argument("--video", required=True, help="源视频本地路径")
ap.add_argument("--grid8", action="store_true", help="先做8格拼贴(需items.json有grid8配置)")
ap.add_argument("--duration", type=int, default=800, help="采集时长秒")
ap.add_argument("--skip-deploy", action="store_true", help="跳过部署(设备已在跑该视频)")
ap.add_argument("--dry-run", action="store_true", help="只打印计划, 不动设备")
ap.add_argument("--analyze-only", default="", help="只重分析已有jsonl(不部署不采集), 配合--item")
ap.add_argument("--no-restore", action="store_true",
                help="跑完不还原设备配置(默认会还原; 仅手工调试注入态时才用)")
ap.add_argument("--keep-video", action="store_true",
                help="还原时保留已上传到设备的视频(默认删掉以回收空间)")
ARGS = ap.parse_args()

if ARGS.item not in KB or ARGS.item.startswith("_"):
    print(f"[FATAL] items.json 无项目 '{ARGS.item}', 可选: {[k for k in KB if not k.startswith('_')]}")
    sys.exit(1)
CFG = KB[ARGS.item]
ITEM_ID = CFG["itemId"]
SCORE_FIELD = CFG["score_field"]

print(f"=== ReplayLab ===\n项目={CFG['name']}(id={ITEM_ID}) 计数字段={SCORE_FIELD} "
      f"timer={CFG['timer']} grid8={ARGS.grid8} duration={ARGS.duration}s dry_run={ARGS.dry_run}", flush=True)
print(f"设备={DEV_NAME}({DEV_MODEL}@{IP})", flush=True)


# ---------- 视频准备 ----------
def md5_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(4 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def make_grid8(src):
    """单人视频 -> 8格拼贴4K。输出到源视频同目录, 文件名加 _8grid 后缀。"""
    g = CFG.get("grid8")
    if not g:
        print("[FATAL] 该项目 items.json 无 grid8 配置")
        sys.exit(1)
    out = os.path.splitext(src)[0] + "_8grid.mp4"
    if os.path.exists(out):
        print(f"[grid8] 已存在, 复用: {out}")
        return out
    w, h = g["cell"]
    ov = ";".join(
        (f"[{('base' if i == 0 else 't%d' % (i - 1))}][s{i}]overlay={x}:{y}:shortest=1"
         + (f"[t{i}]" if i < 7 else "[out]"))
        for i, (x, y) in enumerate(g["layouts"]))
    fc = (f"[0:v]crop={g['crop']},scale={g['scale']}:flags=lanczos,fps=30,"
          f"split=8{''.join('[s%d]' % i for i in range(8))};"
          f"color=black:size={g['canvas']}:rate=30[base];" + ov)
    cmd = [ENV["ffmpeg"], "-hide_banner", "-y", "-i", src, "-filter_complex", fc,
           "-map", "[out]", "-c:v", "libx264", "-preset", "veryfast",
           "-b:v", "18M", "-maxrate", "20M", "-bufsize", "40M", "-pix_fmt", "yuv420p", "-an", out]
    print(f"[grid8] 生成中 -> {out}", flush=True)
    subprocess.run(cmd, check=True)
    return out


def polys8():
    """从 grid8.cell + inset_px 生成8个归一化点位矩形(右上->右下->左下->左上)。

    ⚠️ 必须与 make_grid8() 的贴图坐标保持一致:
       make_grid8 用 layouts 数组贴图, 而 layouts = [c*cw + ox, r*ch + oy],
       即贴图时叠加了 origin 偏移。本函数若不加同样的 origin,
       下发给设备的点位就会比实际画面偏 (ox-ins, oy-ins) 个像素
       —— 遮挡场景下会把仅剩的可见人体切到框外, 导致该路彻底不出成绩。
    """
    g = CFG["grid8"]
    cw, ch = g["cell"]
    ins = g["inset_px"]
    W, H = map(int, g["canvas"].split("x"))
    ox, oy = g.get("origin", [0, 0])
    out = []
    for r in range(2):
        for c in range(4):
            x0, x1 = c * cw + ox + ins, (c + 1) * cw + ox - ins
            y0, y1 = r * ch + oy + ins, (r + 1) * ch + oy - ins
            # 夹紧到画布内, 防止第2行因 origin 溢出导致点位越界
            x0, x1 = max(0, x0), min(W, x1)
            y0, y1 = max(0, y0), min(H, y1)
            out.append([x1 / W, y0 / H, x1 / W, y1 / H, x0 / W, y1 / H, x0 / W, y0 / H])
    return out


VIDEO = ARGS.video if ARGS.dry_run else (make_grid8(ARGS.video) if ARGS.grid8 else ARGS.video)
if not os.path.exists(VIDEO):
    print(f"[FATAL] 视频不存在: {VIDEO}")
    sys.exit(1)
VNAME = os.path.basename(VIDEO)
print(f"[视频] {VIDEO} ({os.path.getsize(VIDEO)/1e6:.0f}MB)", flush=True)


# ---------- 部署 ----------
REMOTE = f"{ENV['video_dir_device']}/{VNAME}"
ITEM_KEY = f"item{ITEM_ID}"


def ssh_conn():
    s = paramiko.SSHClient()
    s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    s.connect(IP, 22, ENV["ssh_user"], ENV["ssh_pass"], timeout=8)
    return s


def deploy():
    ssh = ssh_conn()
    _, so, _ = ssh.exec_command("df -h /userdata | tail -1", timeout=10)
    print("[部署] 磁盘:", so.read().decode().strip(), flush=True)

    lm = md5_file(VIDEO)
    print(f"[部署] local md5={lm}", flush=True)
    url = f"http://{ENV['http_host']}:{ENV['http_port']}/{VNAME}"
    _, so, _ = ssh.exec_command(f"rm -f {REMOTE}; wget -q {url} -O {REMOTE} && echo WGET_OK || echo WGET_FAIL", timeout=1800)
    r = so.read().decode().strip()
    print(f"[部署] wget: {r}", flush=True)
    if "WGET_OK" not in r:
        print("[FATAL] 上传失败, 确认 http.server 已启动: python -m http.server 8000 --directory E:\\TestTools")
        ssh.close(); sys.exit(1)

    _, so, _ = ssh.exec_command(f"md5sum {REMOTE}", timeout=600)
    rm = so.read().decode().split()[0]
    assert rm == lm, f"MD5 不一致 local={lm} remote={rm}"
    print("[部署] MD5 一致 ✓", flush=True)

    if CFG.get("grid8"):
        sftp = ssh.open_sftp()
        tmp_loc = os.path.join(HERE, "_item_tmp.json")
        sftp.get(ENV["item_json"], tmp_loc)
        raw = open(tmp_loc, encoding="utf-8").read()
        d, end = json.JSONDecoder().raw_decode(raw)
        tail = raw[end:]
        old = d[ITEM_KEY]["init_area"]
        print(f"[部署] 改前 {ITEM_KEY}.init_area 数量={len(old)} (==8 即固件已同步)", flush=True)
        d[ITEM_KEY]["init_area"] = polys8()
        open(tmp_loc, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=4) + tail)
        sftp.put(tmp_loc, ENV["item_json"] + ".new")
        sftp.close()
        _, so, se = ssh.exec_command(
            f"cp -p {ENV['item_json']} {ENV['item_json']}.bak_replay && "
            f"mv {ENV['item_json']}.new {ENV['item_json']} && echo REPLACED", timeout=15)
        print("[部署] item.json:", so.read().decode().strip(), se.read().decode().strip(), flush=True)

    # 注入参数: 必须 3 个字段一起置位。
    # 出厂态设备是 is_rtsp_in=false / rtsp_camera_type=1, 只改 video_url 不会生效
    # (设备仍走 sensor 采集), 这是本流程早期只在 .30 上手改过注入参数才会"看起来能用"的坑。
    cfgp = ENV["rtsp_config"]
    orig_stat = ""
    _, so, _ = ssh.exec_command(f"stat -c '%a %u:%g' {cfgp}", timeout=10)
    orig_stat = so.read().decode().strip()
    sftp = ssh.open_sftp()
    tmp_cfg = os.path.join(HERE, "_rtsp_tmp.json")
    sftp.get(cfgp, tmp_cfg)
    sftp.close()
    cfg = json.load(open(tmp_cfg, encoding="utf-8"))
    src = cfg.setdefault("source_rtsp_in", {})
    ch0 = src.setdefault("rtsp_link_info", {}).setdefault("channel0", {})
    before = (src.get("is_rtsp_in"), src.get("rtsp_camera_type"), ch0.get("video_url"))
    src["is_rtsp_in"] = True
    src["rtsp_camera_type"] = 3
    ch0["video_url"] = REMOTE
    open(tmp_cfg, "w", encoding="utf-8").write(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    sftp = ssh.open_sftp()
    sftp.put(tmp_cfg, cfgp + ".new")
    sftp.close()
    fix = f"chmod {orig_stat.split()[0]} {cfgp} && chown {orig_stat.split()[1]} {cfgp}" if orig_stat else "true"
    _, so, se = ssh.exec_command(
        f"cp -p {cfgp} {cfgp}.bak_replay && mv {cfgp}.new {cfgp} && {fix} && "
        f"grep -E '\"is_rtsp_in\"|\"rtsp_camera_type\"|\"video_url\"' {cfgp} | grep -v '@'", timeout=20)
    print(f"[部署] 注入参数: is_rtsp_in={before[0]} type={before[1]} -> 开/3/{os.path.basename(REMOTE)}", flush=True)
    print("[部署] 回读:", so.read().decode().strip(), se.read().decode().strip(), flush=True)

    print("[部署] reboot...", flush=True)
    ssh.exec_command("reboot", timeout=5)
    ssh.close()
    time.sleep(3)


# ---------- 跑前快照 / 跑后还原 ----------
# 背景: 本流程会改设备两处状态 —— rtsp_config.json 的注入参数, 以及(启用 grid8 时)
# item.json 里 item{ID}.init_area 的 8 格点位。改完要 reboot, 而设备不会自己恢复。
# 早期版本跑完就把设备留在"注入模式"(192.168.2.30 就是这么被留在绳8视频上的),
# 所以这里统一做"跑前快照、跑完还原", 用 try/finally 兜住异常与 Ctrl-C。
def wait_http(timeout=300):
    """等设备 HTTP 回来, 返回是否成功(不退出进程, 还原阶段要能继续)。"""
    t = time.time()
    while time.time() - t < timeout:
        try:
            if requests.get(BASE + "/camera/deviceInfo", timeout=3).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


def snapshot_state():
    """跑前把设备配置原文拉回本地(含属主/权限), 返回快照 dict。"""
    ssh = ssh_conn()
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    d = os.path.join(STATE_DIR, f"{DEV_NAME}_{ts}")
    os.makedirs(d, exist_ok=True)
    snap = {"dir": d, "ts": ts, "items": {}}
    sftp = ssh.open_sftp()
    for key, remote in (("rtsp_config", ENV["rtsp_config"]), ("item_json", ENV["item_json"])):
        local = os.path.join(d, key + os.path.splitext(remote)[1])
        try:
            sftp.get(remote, local)
            _, so, _ = ssh.exec_command(f"stat -c '%a %u:%g' {remote}", timeout=10)
            snap["items"][key] = {"remote": remote, "local": local,
                                  "stat": so.read().decode().strip()}
            print(f"[快照] {remote} -> {local} ({os.path.getsize(local)}B, "
                  f"{snap['items'][key]['stat']})", flush=True)
        except Exception as e:
            print(f"[快照] {remote} 失败: {type(e).__name__}: {e}", flush=True)
    sftp.close()
    ssh.close()
    return snap


def restore_state(snap, video_remote=None):
    """把快照写回设备并 reboot, 让设备回到跑前状态。返回是否成功。"""
    if not snap or not snap.get("items"):
        print("[还原] 无可用快照, 跳过", flush=True)
        return False
    ssh = ssh_conn()
    sftp = ssh.open_sftp()
    for key, info in snap["items"].items():
        sftp.put(info["local"], info["remote"] + ".restoring")
    sftp.close()
    for key, info in snap["items"].items():
        fix = ""
        st = info.get("stat") or ""
        if len(st.split()) == 2:
            fix = f" && chmod {st.split()[0]} {info['remote']} && chown {st.split()[1]} {info['remote']}"
        _, so, _ = ssh.exec_command(
            f"mv {info['remote']}.restoring {info['remote']}{fix} && "
            f"stat -c '%a %u:%g %s' {info['remote']}", timeout=20)
        print(f"[还原] {info['remote']} -> {so.read().decode().strip()}", flush=True)
    if video_remote:
        if ARGS.keep_video:
            print(f"[还原] 保留上传的视频(--keep-video): {video_remote}", flush=True)
        else:
            _, so, _ = ssh.exec_command(f"rm -f {video_remote} && echo REMOVED", timeout=30)
            print(f"[还原] 清理上传的视频 {video_remote}: {so.read().decode().strip()}", flush=True)
    print("[还原] reboot ...", flush=True)
    ssh.exec_command("reboot", timeout=5)
    ssh.close()
    time.sleep(3)
    ok = wait_http()
    print(f"[还原] 设备 HTTP {'已恢复' if ok else '300s 未恢复'}", flush=True)
    return ok


# ---------- 等待就位 + join ----------
latest = {"n": 0, "areas": {}}
stop = {"flag": False}
CAP = []
t0 = time.time()


def on_message(ws, message):
    try:
        pbm = pb2.FrameMessage(); pbm.ParseFromString(message)
    except Exception:
        return
    for attr in pbm.Statistics_msg_.attributes_:
        if attr.type_ == "sportInfos":
            try:
                infos = json.loads(attr.value_string_)
            except Exception:
                continue
            CAP.append({"t": round(time.time() - t0, 2), "si": [
                {"a": i.get("areaIndex"), "s": i.get(SCORE_FIELD), "in": i.get("inArea"),
                 "st": i.get("status"), "tm": i.get("timer"), "tid": i.get("trackId")} for i in infos]})
            latest["n"] = len(infos)
            latest["areas"] = {i.get("areaIndex"): (i.get(SCORE_FIELD), i.get("inArea"), i.get("status")) for i in infos}


def ws_loop():
    while not stop["flag"]:
        try:
            websocket.WebSocketApp(f"ws://{IP}:8080", on_message=on_message,
                                   on_error=lambda w, e: None).run_forever()
        except Exception:
            pass
        time.sleep(2)


FW_VERSION = ""  # 当前设备固件版本(wait_ready后读取, 写入报告)


def get_firmware():
    """读设备固件版本(GET /control/getVersion), 失败返回 ''。"""
    try:
        r = requests.get(BASE + "/control/getVersion", headers=H_JSON, timeout=8)
        j = r.json()
        return str(j.get("Version") or j.get("version") or "")
    except Exception:
        return ""


def wait_ready():
    print("[就位] 等设备 HTTP...", flush=True)
    for _ in range(120):
        try:
            if requests.get(BASE + "/camera/deviceInfo", timeout=3).status_code == 200:
                break
        except Exception:
            pass
        time.sleep(2)
    else:
        print("[FATAL] HTTP 240s 未恢复"); sys.exit(1)
    print(f"[就位] HTTP 恢复 @ t={time.time()-t0:.0f}", flush=True)

    ssh = ssh_conn()
    log = ENV["log_glob"]

    def cur_frame():
        _, so, _ = ssh.exec_command(f"grep 'decoder Input ok' {log} | tail -1", timeout=10)
        m = re.search(r"frame_idx=(\d+)", so.read().decode(errors="replace"))
        return int(m.group(1)) if m else -1

    print("[就位] 等解码器...", flush=True)
    for _ in range(60):
        f1 = cur_frame(); time.sleep(2); f2 = cur_frame()
        if f1 >= 0 and f2 > f1:
            print(f"[就位] 解码器运行中 frame_idx={f2} @ t={time.time()-t0:.0f}", flush=True)
            break
        time.sleep(2)
    else:
        print("[FATAL] 解码器 240s 未出帧"); sys.exit(1)
    return ssh


def join_flow():
    n_testers = CFG["join"]["testers"]
    if CFG.get("visitor_auto_session") and latest["n"] >= n_testers:
        print(f"[join] visitor 持久化已就位 n={latest['n']}, 跳过 joinSport", flush=True)
        return
    requests.post(BASE + "/camera/guestMode", json={"visitor": True}, headers=H_JSON, timeout=10)
    if CFG.get("need_start_sport"):
        ss = CFG["start_sport"]
        r = requests.post(BASE + "/camera/startSport",
                          json={"time": ss["time"], "delayTime": ss["delayTime"]},
                          headers=H_JSON, timeout=10)
        print(f"[join] startSport: {r.text[:80]!r}", flush=True)
        time.sleep(2)
    r = requests.post(BASE + "/camera/joinSport",
                      json={"data": {"testers": [{"testerId": i, "name": ""} for i in range(n_testers)],
                                     "itemId": ITEM_ID}}, headers=H_JSON, timeout=15)
    print(f"[join] joinSport({n_testers}人,item{ITEM_ID}): {r.text[:100]!r}", flush=True)


# ---------- 采集 ----------
FR = []


def capture(ssh, jsonl_path):
    fstop = {"flag": False}
    log = ENV["log_glob"]

    def frame_probe():
        while not fstop["flag"]:
            try:
                _, so, _ = ssh.exec_command(f"grep 'decoder Input ok' {log} | tail -1", timeout=10)
                m = re.search(r"frame_idx=(\d+)", so.read().decode(errors="replace"))
                if m:
                    FR.append({"t": round(time.time() - t0, 2), "f": int(m.group(1))})
            except Exception:
                pass
            time.sleep(1.5)

    threading.Thread(target=frame_probe, daemon=True).start()
    print(f"[采集] {ARGS.duration}s ...", flush=True)
    tend = time.time() + ARGS.duration
    lp = {"t": -10.0}
    while time.time() < tend:
        el = time.time() - t0
        if el - lp["t"] >= 5:
            lp["t"] = el
            brief = {a: v for a, v in latest["areas"].items()}
            print(f"  t={el:6.1f} n={latest['n']} {brief}", flush=True)
        time.sleep(1)
    fstop["flag"] = True
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in CAP:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        for r in FR:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[采集] 写 {jsonl_path} (si={len(CAP)} frame={len(FR)})", flush=True)


# ---------- 分析 ----------
def analyze():
    G = CFG["golden"]
    GTYPE = G.get("type", "piecewise")
    GSCORES = G.get("scores") or []  # final模式: per-area最终成绩基准(计时计数项目)
    GBASE = int(G.get("area_base", 0) or 0)  # final模式: 设备areaIndex起始值, scores[i]对应area(GBASE+i)
    GP = [(p[0], p[1]) for p in G.get("points", [])]
    LOOP = G.get("loop_frames") or 0
    TOTAL = G.get("total_per_loop") or (GP[-1][1] if GP else 0)

    def golden(vt):
        if not GP:
            return None
        if vt <= GP[0][0]:
            return float(GP[0][1])
        if vt >= GP[-1][0]:
            return float(TOTAL)
        for (t1, g1), (t2, g2) in zip(GP, GP[1:]):
            if t1 <= vt <= t2:
                return g1 + (g2 - g1) * (vt - t1) / (t2 - t1)
        return float(TOTAL)

    def frame_at(t):
        if not FR:
            return None
        best = min(FR, key=lambda r: abs(r["t"] - t))
        return best["f"] if abs(best["t"] - t) < 3 else None

    def win_golden(ta, tb):
        f0, f1 = frame_at(ta), frame_at(tb)
        if f0 is None or f1 is None or not LOOP:
            return None, "-"
        v0, v1 = (f0 % LOOP) / 30.0, (f1 % LOOP) / 30.0
        if v1 > v0:
            return golden(v1) - golden(v0), f"[{v0:.1f},{v1:.1f}]"
        return (TOTAL - golden(v0)) + golden(v1), f"[{v0:.1f},..]+[0,{v1:.1f}]"

    per_area = {}
    for r in CAP:
        for x in r["si"]:
            a = x.get("a")
            if a is None:
                continue
            per_area.setdefault(a, []).append((r["t"], x.get("s") or 0, x.get("st") or "", bool(x.get("in"))))

    area_rounds = {}
    for a, rows in per_area.items():
        if GTYPE == "final":
            _idx = (a - GBASE) if isinstance(a, int) else -1
            if not (0 <= _idx < len(GSCORES)):
                continue  # final模式: 跳过基准外area(如残留的area0)
        rounds, cur, prev_s = [], None, None
        for (t, s, st, inn) in rows:
            if prev_s is not None and s <= 3 and prev_s > 50 and cur is not None:
                rounds.append(cur); cur = None
            if cur is None:
                cur = {"t0": t, "t1": t, "sp0": None, "sp1": None, "smax": 0, "in_n": 0, "in_true": 0}
            cur["t1"] = t
            if st == "SPORTING":
                if cur["sp0"] is None:
                    cur["sp0"] = t
                cur["sp1"] = t
            cur["smax"] = max(cur["smax"], s)
            cur["in_n"] += 1
            cur["in_true"] += 1 if inn else 0
            prev_s = s
        if cur:
            rounds.append(cur)
        area_rounds[a] = rounds

    # ---- 判定某路在某轮是否"有效" ----
    # 背景: 人物遮挡会让设备认为"区域内有人"(in=true) 但永不进入 SPORTING, 成绩恒为 0。
    # 这种 0 不是"算法算错", 而是"该路数据不可用"。若计入极差, 会把
    # 真实的一致性指标从 28 虚高到 136 (见 rope area6 案例)。
    #
    # 但要注意区分两种"没进 SPORTING":
    #   (a) 真·无数据 —— 该轮有大量采样点, 却全程没进过 SPORTING (如 rope area6, 6858 点) → 疑似遮挡
    #   (b) 尾部残轮 —— 采集停止后残留的零星点, 本身不构成一轮 (如开合跳轮11 仅 82 点) → 不是异常
    # 判据: 该轮采样点数是否达到一个"最小成轮规模"。正常一轮是全场 8 路共约 2000 个采样点。
    MIN_ROUND_SAMPLES = 200

    def is_valid(rd):
        """该轮该路是否产出可用数据: 必须真正进入过 SPORTING。"""
        return rd["sp0"] is not None

    def is_tail_noise(rd):
        """尾部残轮: 点数太少, 不构成完整一轮。"""
        return rd["in_n"] < MIN_ROUND_SAMPLES

    lines = [f"各路轮数: { {a: len(v) for a, v in sorted(area_rounds.items())} }"]
    n_rounds = max((len(v) for v in area_rounds.values()), default=0)
    acc_map, in_map, invalid_map, noise_map = {}, {}, {}, {}
    lines.append("\n=== 逐轮 ===")
    for ri in range(n_rounds):
        scores, accs, invalid = {}, {}, {}
        for a in sorted(area_rounds):
            rds = area_rounds[a]
            if ri >= len(rds):
                continue
            rd = rds[ri]
            ii = in_map.setdefault(a, [0, 0]); ii[0] += rd["in_true"]; ii[1] += rd["in_n"]
            if not is_valid(rd):
                if is_tail_noise(rd):
                    # 尾部残轮, 不算异常, 也不计极差
                    noise_map.setdefault(a, 0); noise_map[a] += 1
                else:
                    # 该路数据不可用: 单独列出并标注原因
                    invalid[a] = rd["smax"]
                    invalid_map.setdefault(a, 0)
                    invalid_map[a] += 1
                continue
            scores[a] = rd["smax"]
            g = None
            if GTYPE == "final":
                # 计时计数项目(跳绳等): 该轮最终成绩smax 对比该路基准 scores[areaIndex-GBASE]
                idx = (a - GBASE) if isinstance(a, int) else -1
                if 0 <= idx < len(GSCORES) and GSCORES[idx]:
                    g = float(GSCORES[idx])
            elif rd["sp0"] is not None and rd["sp1"] is not None and rd["sp1"] - rd["sp0"] > 20:
                g, _ = win_golden(rd["sp0"], rd["sp1"])
            if g and g > 0:
                accs[a] = round(rd["smax"] / g * 100, 1)
                acc_map.setdefault(a, []).append(rd["smax"] / g * 100)
        if not scores and not invalid:
            continue
        vals = list(scores.values())
        sstr = ",".join(f"{a}:{s}" for a, s in scores.items())
        astr = ",".join(f"{a}:{v}" for a, v in accs.items())
        # 极差/均值只取有效路; 无有效路时明确标注而不是显示 0
        if vals:
            spread = f"极差={max(vals)-min(vals)} 均值={sum(vals)/len(vals):.1f}"
        else:
            spread = "极差=-- 均值=-- (本轮无有效路)"
        inv = ""
        if invalid:
            inv = " | 无效路(未进SPORTING,疑遮挡): " + ",".join(f"{a}:{s}" for a, s in invalid.items())
        lines.append(f"轮{ri:>2}: {sstr}{' | ' if sstr else ''}{spread} | 准确率%: {astr}{inv}")

    lines.append("\n=== 各路汇总 ===")
    for a in sorted(in_map):
        accs = acc_map.get(a) or []
        inr = in_map[a][0] / in_map[a][1] * 100 if in_map[a][1] else 0
        if accs:
            lines.append(f"area{a}: 有效轮={len(accs)} 准确率 min={min(accs):.1f}% max={max(accs):.1f}% "
                         f"avg={sum(accs)/len(accs):.1f}% | inArea={inr:.0f}%")
        else:
            nbad = invalid_map.get(a, 0)
            why = f" | 无效轮={nbad} (未进入SPORTING, 疑似人物遮挡/点位问题)" if nbad else ""
            lines.append(f"area{a}: 无有效轮{why} | inArea={inr:.0f}%")

    # 数据完整性提示: 若存在无效路, 在报告里显式说明, 避免把"无数据"误读成"算法全错"
    if invalid_map:
        lines.append("\n=== 数据完整性 ===")
        lines.append("以下路未产出可用数据(全程未进入 SPORTING), 其成绩 0 不代表算法错误:")
        for a in sorted(invalid_map):
            lines.append(f"  area{a}: 无效轮数={invalid_map[a]}")
        lines.append("排查建议: 1) 该格是否被前方人物遮挡; 2) 贴图坐标与下发点位是否错位"
                     "(见 run_test.py polys8 与 make_grid8 的 origin 处理)")
    if noise_map:
        lines.append(f"注: 另有尾部残轮(采样点<{MIN_ROUND_SAMPLES}, 采集结束后残留) 已自动忽略: "
                     + ",".join(f"area{a}×{n}" for a, n in sorted(noise_map.items())))
    out = "\n".join(lines)
    print(out, flush=True)
    return out


# ---------- 报告 ----------
def write_report(md_path, jsonl_path, analysis):
    md = f"""# ReplayLab 报告: {CFG['name']}

- 时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 项目: {CFG['name']} (itemId={ITEM_ID}, 计数字段={SCORE_FIELD})
- 设备: {DEV_NAME}({DEV_MODEL}@{IP}) 固件版本: {FW_VERSION or '未获取'}
- 视频: `{VNAME}`
- grid8: {ARGS.grid8} | 采集时长: {ARGS.duration}s
- 跑后设备还原: {RESTORE_NOTE}
- 原始数据: `{os.path.basename(jsonl_path)}`

## 分析

```
{analysis}
```
"""
    open(md_path, "w", encoding="utf-8").write(md)


# ---------- main ----------
def main():
    global FW_VERSION, RESTORE_NOTE
    if ARGS.dry_run:
        print("\n=== DRY-RUN 计划 ===", flush=True)
        print(f"项目={CFG['name']}(id={ITEM_ID}) 视频={VIDEO}", flush=True)
        print(f"将部署到 {REMOTE}{' (8格点位)' if CFG.get('grid8') else ''}, 切 video_url 后 reboot", flush=True)
        print(f"join: visitors={CFG['join']['testers']} need_start_sport={CFG['need_start_sport']}", flush=True)
        print(f"采集 {ARGS.duration}s -> golden对齐分析 -> 报告到 {REPORTS}", flush=True)
        return
    if ARGS.analyze_only:  # 离线重分析已有采集数据(不碰设备)
        RESTORE_NOTE = "未涉及(本次仅离线重分析, 未接触设备)"
        with open(ARGS.analyze_only, encoding="utf-8") as f:
            for ln in f:
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                (CAP if "si" in r else FR).append(r)
        mdr = os.path.join(REPORTS, f"{ARGS.item}_re_{datetime.datetime.now().strftime('%H%M%S')}.md")
        write_report(mdr, ARGS.analyze_only, analyze())
        print(f"[重分析] 报告: {mdr}", flush=True)
        return
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    jsonl_path = os.path.join(REPORTS, f"{ARGS.item}_{ts}.jsonl")
    md_path = os.path.join(REPORTS, f"{ARGS.item}_{ts}.md")
    snap = None
    try:
        if not ARGS.skip_deploy:
            snap = snapshot_state()
            deploy()
        else:
            print("[skip-deploy] 跳过部署", flush=True)
        ssh = wait_ready()
        FW_VERSION = get_firmware()
        print(f"[固件] {DEV_NAME}({DEV_MODEL}@{IP}) 版本={FW_VERSION or '未获取'}", flush=True)
        threading.Thread(target=ws_loop, daemon=True).start()
        time.sleep(4)
        print(f"[join前] n={latest['n']} areas={latest['areas']}", flush=True)
        join_flow()
        time.sleep(3)
        capture(ssh, jsonl_path)
        stop["flag"] = True
        ssh.close()
    finally:
        # 无论成功、报错还是 Ctrl-C, 都要把设备还原回去, 不留注入态
        if ARGS.skip_deploy:
            RESTORE_NOTE = "未执行(本次 --skip-deploy)"
        elif ARGS.no_restore:
            RESTORE_NOTE = "未还原(--no-restore), 设备仍处注入模式"
            print("[还原] 已按 --no-restore 跳过, 设备保持在注入模式", flush=True)
        else:
            try:
                ok = restore_state(snap, REMOTE)
                RESTORE_NOTE = "已还原跑前配置并重启" if ok else "已写回配置, 但 HTTP 未按时恢复, 需人工确认"
            except Exception as e:
                RESTORE_NOTE = f"还原失败: {type(e).__name__}: {e}"
                print(f"[还原] 失败: {type(e).__name__}: {e}", flush=True)
            print(f"[还原] {RESTORE_NOTE}", flush=True)
    analysis = analyze()
    write_report(md_path, jsonl_path, analysis)
    print(f"[完成] 报告: {md_path}", flush=True)


main()
