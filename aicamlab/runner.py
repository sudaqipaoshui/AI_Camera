# -*- coding: utf-8 -*-
"""统一入口的执行层: 目标注册表 + 子进程执行 + 结果汇总。

设计约束(为了以后能直接接 CI):
  * 无任何交互式提问 —— 需要人确认的目标用 ``--yes`` 显式放行, 否则直接拒绝执行;
  * 退出码固定且有意义(见 ``EXIT_*``), CI 只需看退出码;
  * ``--json`` 输出机器可读摘要, 摘要里带 log_path, 原始输出落文件而非混进 stdout;
  * 解释器统一用项目 venv, 不再依赖 PATH 上碰巧存在的 python3。

本模块不含业务逻辑, 只是"把散落的脚本收成一张表, 按同一套规矩执行"。
"""
from __future__ import annotations

import dataclasses
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import envloader  # noqa: E402

# ---- 退出码: CI 直接据此判成败 -------------------------------------------
EXIT_OK = 0            # 全部通过
EXIT_TEST_FAILED = 1   # 有用例失败 / 脚本非零退出
EXIT_USAGE = 2         # 用法错误(未知目标、缺参数)
EXIT_PRECONDITION = 3  # 前置条件不满足(缺依赖、库不可用、设备不可达)
EXIT_NEEDS_CONFIRM = 4 # 危险/长时目标未显式放行

LOG_DIR = PROJECT_ROOT / "Log"

# 项目 venv 的候选位置(按优先级), 可用 .env 的 AICAM_PYTHON 覆盖
KNOWN_PYTHONS = (
    PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
    PROJECT_ROOT / ".venv" / "bin" / "python",
    PROJECT_ROOT / "venv" / "Scripts" / "python.exe",
    Path(r"E:\TestTools\venv\Scripts\python.exe"),
)

DEFAULT_ENV = "test"
DEFAULT_CONFIG = "camera.yaml"


# ==========================================================================
# 解释器
# ==========================================================================
def _probe_python(exe: str, timeout: int = 40) -> bool:
    """能否 import 齐跑测试所需的依赖。"""
    try:
        r = subprocess.run(
            [exe, "-c", "import pytest, yaml, pymysql, requests"],
            capture_output=True, timeout=timeout,
        )
        return r.returncode == 0
    except Exception:
        return False


def resolve_python() -> str:
    """挑一个装了依赖的解释器。顺序: .env 指定 > 当前 > 已知 venv。"""
    candidates: list[str] = []
    override = envloader.get("AICAM_PYTHON")
    if override:
        candidates.append(override)
    candidates.append(sys.executable)
    candidates.extend(str(p) for p in KNOWN_PYTHONS if p.exists())

    seen: set[str] = set()
    for exe in candidates:
        if not exe or exe in seen:
            continue
        seen.add(exe)
        if os.path.isfile(exe) and _probe_python(exe):
            return exe
    raise PreconditionError(
        "找不到装了依赖的解释器。请在 .env 里设 AICAM_PYTHON=<venv python 绝对路径>, "
        f"或确认以下任一存在: {', '.join(str(p) for p in KNOWN_PYTHONS)}"
    )


# ==========================================================================
# 异常
# ==========================================================================
class UsageError(RuntimeError):
    """用法错误。"""


class PreconditionError(RuntimeError):
    """前置条件不满足。"""


class NeedsConfirm(RuntimeError):
    """需要显式放行才能执行。"""


# ==========================================================================
# 目标注册表
# ==========================================================================
@dataclasses.dataclass(frozen=True)
class Target:
    key: str
    desc: str
    kind: str = "pytest"                 # pytest | script | builtin
    paths: tuple[str, ...] = ()
    expr: str | None = None              # pytest -m 表达式
    script: str | None = None
    script_args: tuple[str, ...] = ()
    needs: tuple[str, ...] = ()          # device / ssh / adb
    long_running: bool = False           # 需 --yes 显式放行
    extra_note: str = ""


TARGETS: dict[str, Target] = {t.key: t for t in (
    Target("api", "接口用例(默认集合, 无需真机)", paths=("API/tests",)),
    Target("security", "安全用例(越权/鉴权/加密/隐私)", paths=("Security",)),
    Target("stability", "稳定性短时用例(不含 24h 长跑)", paths=("Stability",),
           expr="not longrunning", needs=("ssh",)),
    Target("performance", "AI 模型性能测试", kind="script",
           script="Performance/test_all_models_performance.py"),
    Target("benchmark", "X5 芯片基准测试", kind="script",
           script="Benchmark/test_x5_benchmark_standalone.py"),
    Target("e2e", "端到端用例(真机 + adb + airtest)", paths=("E2E/tests",),
           needs=("device", "adb")),
    Target("replay", "ReplayLab 视频注入测试", kind="script",
           script="ReplayLab/run_test.py", needs=("device",)),
    Target("smoke", "30 秒自检: 依赖 / 配置 / 测试库 / 收集 / 设备",
           kind="builtin"),
    Target("gate", "按 gate.yaml 阈值判定上一批次是否放行", kind="builtin"),
    Target("report", "从结果库生成跨批次趋势报告", kind="builtin"),
    Target("long", "全部离线用例(排除长跑)", paths=("Stability", "Performance",
           "Benchmark", "Security", "API/tests"), expr="not longrunning"),
    Target("stability-24h", "X5 24 小时 SSH 稳定性监控", paths=("Stability",),
           expr="x5_ssh_24h_monitoring", needs=("ssh",), long_running=True,
           extra_note="真实运行 24 小时, 需 --yes 放行"),
)}


def list_targets() -> str:
    lines = ["可用目标:", ""]
    width = max(len(k) for k in TARGETS)
    for t in TARGETS.values():
        mark = " [长时]" if t.long_running else ""
        need = f"  需要: {'/'.join(t.needs)}" if t.needs else ""
        lines.append(f"  {t.key.ljust(width)}  {t.desc}{mark}{need}")
    lines += ["", "例:  python run.py api", "     python run.py gate --json",
              "     python run.py api -- -k ping      # -- 之后透传给 pytest", ""]
    return "\n".join(lines)


# ==========================================================================
# 执行
# ==========================================================================
@dataclasses.dataclass
class RunResult:
    run_id: str
    target: str
    cmd: list[str]
    started_at: str
    finished_at: str
    duration_sec: float
    exit_code: int
    counts: dict
    verdict: str
    log_path: str
    note: str = ""

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def new_run_id(target: str) -> str:
    return f"{datetime.now():%Y%m%d_%H%M%S}_{target}"


_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_SUMMARY_RE = re.compile(
    r"(?P<n>\d+)\s+(?P<kind>passed|failed|error|errors|skipped|xfailed|xpassed|deselected|warning|warnings)"
)


def _parse_pytest_counts(lines: list[str]) -> dict:
    """从 pytest 汇总行抠计数(插件没写出 JSON 时的兜底)。"""
    counts: dict[str, int] = {}
    for line in reversed(lines[-40:]):
        clean = _ANSI.sub("", line)
        if " passed" not in clean and " failed" not in clean and " error" not in clean:
            continue
        for m in _SUMMARY_RE.finditer(clean):
            kind = m.group("kind").rstrip("s") if m.group("kind").startswith("error") else m.group("kind")
            kind = {"error": "error", "warning": "warning"}.get(kind, kind)
            counts[kind] = counts.get(kind, 0) + int(m.group("n"))
        if counts:
            break
    return counts


def _verdict(exit_code: int, counts: dict) -> str:
    if exit_code == 0:
        return "PASS"
    if counts.get("failed") or counts.get("error"):
        return "FAIL"
    return "ERROR"


def _pytest_cmd(py: str, t: Target, args) -> list[str]:
    cmd = [py, "-m", "pytest", *t.paths]
    if t.expr:
        cmd += ["-m", t.expr]
    cmd += ["--env", args.env, "--config", args.config]
    # 本项目自带的采集插件: 输出 JSON 摘要, 需要时落库
    cmd += ["-p", "aicamlab.pytest_plugin"]
    json_path = str(LOG_DIR / f"_{args.run_id}.json")
    cmd += [f"--aicamlab-json={json_path}", f"--aicamlab-run-id={args.run_id}",
            f"--aicamlab-target={t.key}"]
    if args.tag:
        cmd += [f"--aicamlab-tag={args.tag}"]
    if args.record:
        cmd += ["--aicamlab-record-run"]
    if args.quiet:
        cmd += ["-q"]
    cmd += list(args.passthrough)
    return cmd


def _script_cmd(py: str, t: Target, args) -> list[str]:
    cmd = [py, t.script]
    if t.key == "replay":
        # run_test.py 自己解析 --item/--video, 这里不替它编参数, 全部由 -- 透传
        cmd += list(args.passthrough)
    else:
        cmd += list(t.script_args) + list(args.passthrough)
    return cmd


def check_needs(t: Target, args) -> list[str]:
    """返回未满足的前置条件描述(空列表=都满足)。"""
    problems: list[str] = []
    if not t.needs:
        return problems
    dev = active_device()
    if "device" in t.needs:
        if not dev.get("ip"):
            problems.append("没有激活设备(config/devices.yaml 或 items.json 的 _env.active)")
        elif not _tcp_alive(dev["ip"], 80, 2.0) and not _tcp_alive(dev["ip"], 22, 2.0):
            problems.append(f"设备 {dev['ip']} 不可达(80/22 端口都连不上)")
    if "ssh" in t.needs:
        if not dev.get("ip"):
            problems.append("没有激活设备, 无法走 SSH")
        if not envloader.get("CAMERA_SSH_PASSWORD"):
            problems.append("缺少 CAMERA_SSH_PASSWORD(在 .env 里配)")
    if "adb" in t.needs and not shutil.which("adb"):
        problems.append("PATH 上没有 adb")
    return problems


def _tcp_alive(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def active_device() -> dict:
    """当前激活设备。实现见 aicamlab/inventory.py(config/devices.yaml 是唯一来源)。"""
    from aicamlab.inventory import active_device as _active

    try:
        return _active()
    except Exception:
        return {}


def execute(t: Target, args, py: str) -> RunResult:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now()
    t0 = time.time()

    if t.kind == "pytest":
        cmd = _pytest_cmd(py, t, args)
    else:
        cmd = _script_cmd(py, t, args)
    cmd = [c for c in cmd if c != ""]

    if args.dry_run:
        return RunResult(args.run_id, t.key, cmd, started.isoformat(timespec="seconds"),
                         started.isoformat(timespec="seconds"), 0.0, EXIT_OK,
                         {}, "DRY-RUN", "", note="--dry-run, 未真正执行")

    child_env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    log_path = LOG_DIR / f"_{args.run_id}.log"
    collected: list[str] = []
    with open(log_path, "w", encoding="utf-8", errors="replace") as logf:
        proc = subprocess.Popen(
            cmd, cwd=str(PROJECT_ROOT), env=child_env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            logf.write(line)
            logf.flush()
            collected.append(line)
            if not args.json:
                sys.stdout.write(line)
                sys.stdout.flush()
        exit_code = proc.wait()

    counts: dict = {}
    summary_file = LOG_DIR / f"_{args.run_id}.json"
    if summary_file.exists():
        try:
            counts = json.loads(summary_file.read_text(encoding="utf-8")).get("counts") or {}
        except Exception:
            counts = {}
    if not counts:
        counts = _parse_pytest_counts(collected)

    verdict = _verdict(exit_code, counts) if t.kind == "pytest" else (
        "PASS" if exit_code == 0 else "FAIL")

    return RunResult(
        run_id=args.run_id, target=t.key, cmd=cmd,
        started_at=started.isoformat(timespec="seconds"),
        finished_at=datetime.now().isoformat(timespec="seconds"),
        duration_sec=round(time.time() - t0, 2),
        exit_code=exit_code, counts=counts, verdict=verdict,
        log_path=str(log_path),
    )


# ==========================================================================
# 自检
# ==========================================================================
@dataclasses.dataclass
class Check:
    name: str
    ok: bool
    detail: str


def smoke(args, py: str) -> tuple[list[Check], int]:
    """30 秒自检。任一项失败即返回非零, 让 CI 在跑用例前就拦住环境问题。"""
    checks: list[Check] = []

    checks.append(Check("解释器", True, py))

    # 配置可加载
    cfg_path = PROJECT_ROOT / "config" / args.env / args.config
    if cfg_path.exists():
        try:
            data = envloader.load_yaml(str(cfg_path)) or {}
            users = data.get("users") or [{}]
            checks.append(Check("配置加载", True,
                                f"{cfg_path.relative_to(PROJECT_ROOT)} 已渲染, "
                                f"{len(data)} 个顶层键"))
        except Exception as exc:
            checks.append(Check("配置加载", False, f"{type(exc).__name__}: {exc}"))
    else:
        checks.append(Check("配置加载", False, f"缺少 {cfg_path}"))

    # 凭据是否齐(只报缺哪些, 不打印值)
    required = ("YUNTIYU_ACCOUNT_USERNAME", "YUNTIYU_ACCOUNT_PASSWORD",
                "YUNTIYU_X_TOKEN", "CAMERA_SSH_PASSWORD")
    missing = [k for k in required if not envloader.get(k)]
    checks.append(Check("凭据", not missing,
                        "齐全" if not missing else f"缺 {', '.join(missing)}"))

    # 测试库
    try:
        from pytest_helper.db import make_client
        client = make_client()
        if client.ping():
            db = client.config.get("database")
            row = client.query_scalar("SELECT COUNT(*) FROM information_schema.tables "
                                      "WHERE table_schema = %s", (db,))
            checks.append(Check("测试库", True, f"{db} 可达, {row} 张表"))
        else:
            checks.append(Check("测试库", False, "ping 失败"))
        client.close()
    except Exception as exc:
        checks.append(Check("测试库", False, f"{type(exc).__name__}: {exc}"))

    # 结果表是否就位
    try:
        from pytest_helper.db import make_client
        client = make_client()
        have = set()
        for r in client.query("SHOW TABLES"):
            have.add(next(iter(r.values())) if isinstance(r, dict) else r[0])
        need = {"test_run", "case_result", "metric"}
        miss = need - have
        checks.append(Check("结果表", not miss,
                            "就位" if not miss else f"缺 {', '.join(sorted(miss))} (跑 SQL/04_schema_runs.sql)"))
        client.close()
    except Exception as exc:
        checks.append(Check("结果表", False, f"{type(exc).__name__}: {exc}"))

    # 用例收集
    try:
        r = subprocess.run([py, "-m", "pytest", "--collect-only", "-q"],
                           cwd=str(PROJECT_ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=180)
        tail = (r.stdout or "").strip().splitlines()[-1:] or [""]
        m = re.search(r"(\d+)\s+tests? collected", tail[0])
        n = int(m.group(1)) if m else 0
        err = "error" in tail[0].lower()
        checks.append(Check("用例收集", (not err) and n > 0,
                            tail[0][:120] if tail[0] else "无输出"))
    except Exception as exc:
        checks.append(Check("用例收集", False, f"{type(exc).__name__}: {exc}"))

    # 激活设备
    dev = active_device()
    if dev.get("ip"):
        alive = _tcp_alive(dev["ip"], 22, 2.0) or _tcp_alive(dev["ip"], 80, 2.0)
        checks.append(Check("激活设备", alive,
                            f"{dev.get('key') or dev.get('name')} {dev['ip']} "
                            f"{'可达' if alive else '不可达(离线不影响离线用例)'}"))
    else:
        checks.append(Check("激活设备", False, "未配置(离线用例不受影响)"))

    failed = [c for c in checks if not c.ok]
    return checks, (EXIT_OK if not failed else EXIT_PRECONDITION)


def render_checks(checks: list[Check], as_json: bool) -> str:
    if as_json:
        return json.dumps([dataclasses.asdict(c) for c in checks], ensure_ascii=False, indent=2)
    lines = []
    for c in checks:
        lines.append(f"  {'OK  ' if c.ok else 'FAIL'}  {c.name:<8} {c.detail}")
    return "\n".join(lines)


def render_result(res: RunResult, as_json: bool) -> str:
    if as_json:
        return json.dumps(res.to_dict(), ensure_ascii=False, indent=2)
    counts = res.counts or {}
    cnt = " ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "—"
    lines = [""]
    if res.verdict == "DRY-RUN":
        lines += ["  将要执行:", f"    {subprocess.list2cmdline(res.cmd)}", ""]
    lines += [
        "─" * 62,
        f"  目标     {res.target}",
        f"  批次     {res.run_id}",
        f"  耗时     {res.duration_sec}s",
        f"  计数     {cnt}",
        f"  结论     {res.verdict}   (exit={res.exit_code})",
    ]
    if res.log_path:
        lines.append(f"  日志     {res.log_path}")
    if res.note:
        lines.append(f"  说明     {res.note}")
    lines.append("─" * 62)
    return "\n".join(lines)
