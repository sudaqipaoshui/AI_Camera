# -*- coding: utf-8 -*-
"""结果落库: 把一次运行写进 test_run / case_result / metric。

三条硬规矩:
  1. **落库失败不影响测试结论** —— 调用方一律 try/except, 文件里也不主动抛;
  2. **结果表不在造数白名单里** —— 结果表刻意不带 ``is_fixture`` 列, 也不进
     ``db.ALLOWED_TABLES``, 因此 ``cleanup_fixture()`` 在物理上不可能删到真实结果,
     清历史只能按 run_id / 时间范围显式删;
  3. **同 run_id 重跑即覆盖** —— 先删该批次的明细再插, 避免重试导致数据翻倍。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import envloader  # noqa: E402

RESULT_TABLES = ("test_run", "case_result", "metric")

GIT_CANDIDATES = (
    r"D:\Git\cmd\git.EXE",
    r"C:\Program Files\Git\cmd\git.exe",
    "/usr/bin/git",
)


# --------------------------------------------------------------------------
# 环境信息
# --------------------------------------------------------------------------
def _git(*args: str) -> str:
    exe = envloader.get("AICAM_GIT") or shutil.which("git")
    if not exe:
        for c in GIT_CANDIDATES:
            if os.path.isfile(c):
                exe = c
                break
    if not exe:
        return ""
    try:
        r = subprocess.run([exe, "-C", str(PROJECT_ROOT), *args],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=20)
        return (r.stdout or "").strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def git_revision() -> tuple[str, int]:
    """返回 (commit, 是否有未提交改动)。取不到就返回空。"""
    commit = _git("rev-parse", "HEAD")
    if not commit:
        return "", 0
    dirty = 1 if _git("status", "--porcelain") else 0
    return commit, dirty


def active_device() -> dict:
    from aicamlab.runner import active_device as _ad
    try:
        return _ad()
    except Exception:
        return {}


def device_firmware(ip: str, token: str = "", timeout: int = 6) -> str:
    """问设备要固件版本。失败返回空串(不抛)。"""
    if not ip:
        return ""
    try:
        import requests
        r = requests.get(f"http://{ip}/control/getVersion",
                         headers={"x_token": token} if token else {}, timeout=timeout)
        j = r.json()
        return str(j.get("Version") or j.get("version") or "")
    except Exception:
        return ""


def _token() -> str:
    try:
        return envloader.get("YUNTIYU_X_TOKEN") or ""
    except Exception:
        return ""


# --------------------------------------------------------------------------
# 建表状态
# --------------------------------------------------------------------------
def missing_tables(client) -> list[str]:
    """返回缺失的结果表。表不存在时落库应给出可执行的提示而不是报错栈。"""
    try:
        rows = client.query("SHOW TABLES")
    except Exception:
        return list(RESULT_TABLES)
    have = set()
    for r in rows:
        have.add(next(iter(r.values())) if isinstance(r, dict) else r[0])
    return [t for t in RESULT_TABLES if t not in have]


# --------------------------------------------------------------------------
# 落库
# --------------------------------------------------------------------------
def record_summary(summary: dict, log_path: str | None = None,
                   report_path: str | None = None, env: str | None = None) -> bool:
    """写入一个批次及其用例明细。返回是否写成功(不抛异常)。"""
    from aicamlab.redact import scrub
    from pytest_helper.db import make_client

    client = make_client()
    try:
        client.connect()
    except Exception as exc:
        print(f"[recorder] 测试库不可用, 跳过落库: {exc}", file=sys.stderr)
        return False

    try:
        miss = missing_tables(client)
        if miss:
            print(f"[recorder] 缺结果表 {', '.join(miss)}, 跳过落库。"
                  f"请执行: python SQL/init_db.py 或 mysql < SQL/04_schema_runs.sql", file=sys.stderr)
            return False

        commit, dirty = git_revision()
        dev = active_device()
        ip = str(dev.get("ip") or "")
        fw = dev.get("firmware") or device_firmware(ip, _token())
        run_id = summary.get("run_id") or f"{datetime.now():%Y%m%d_%H%M%S}_{summary.get('target', 'run')}"
        counts = summary.get("counts") or {}

        run_row = {
            "run_id": run_id,
            "target": summary.get("target") or "",
            "env": env or envloader.get("AICAM_ENV") or "test",
            "device_key": str(dev.get("key") or dev.get("name") or ""),
            "device_ip": ip,
            "firmware": fw or "",
            "git_commit": commit,
            "git_dirty": dirty,
            "trigger_by": envloader.get("AICAM_TRIGGER_BY") or os.environ.get("USERNAME") or "",
            "tag": summary.get("tag") or "",
            "started_at": _dt(summary.get("started_at")),
            "finished_at": _dt(summary.get("finished_at")),
            "duration_sec": float(summary.get("duration_sec") or 0),
            "total": int(counts.get("total") or 0),
            "passed": int(counts.get("passed") or 0),
            "failed": int(counts.get("failed") or 0),
            "skipped": int(counts.get("skipped") or 0),
            "error": int(counts.get("error") or 0),
            "verdict": summary.get("verdict") or "UNKNOWN",
            "exit_code": int(summary.get("exit_code") or 0),
            "log_path": log_path or "",
            "report_path": report_path or "",
            "note": scrub(summary.get("note") or ""),
        }

        with client.transaction():
            cols = ", ".join(f"`{k}`" for k in run_row)
            ph = ", ".join(["%s"] * len(run_row))
            updates = ", ".join(f"`{k}`=VALUES(`{k}`)" for k in run_row if k != "run_id")
            client.execute(
                f"INSERT INTO `test_run` ({cols}) VALUES ({ph}) "
                f"ON DUPLICATE KEY UPDATE {updates}",
                tuple(run_row.values()),
            )
            client.execute("DELETE FROM `case_result` WHERE `run_id` = %s", (run_id,))
            cases = summary.get("cases") or []
            if cases:
                from aicamlab.failure import classify
                rows = []
                for c in cases:
                    status = c.get("status", "")
                    msg = scrub(c.get("message") or "")[:60000]
                    cls = classify(msg, c.get("nodeid", "")) if status in ("failed", "error") else None
                    rows.append((run_id, c.get("nodeid", ""), (c.get("name") or "")[:255],
                                 (c.get("module") or "")[:128], status, cls,
                                 float(c.get("duration_sec") or 0), msg))
                client.executemany(
                    "INSERT INTO `case_result` (run_id, nodeid, name, module, status, "
                    "failure_class, duration_sec, message) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    rows,
                )
        print(f"[recorder] 已落库: {run_id} ({run_row['verdict']}, "
              f"{run_row['total']} 用例, {run_row['duration_sec']}s)")
        return True
    except Exception as exc:
        print(f"[recorder] 落库失败(不影响测试结论): {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return False
    finally:
        client.close()


def record_metrics(run_id: str, metrics: list[dict]) -> int:
    """写入指标(准确率 / 极差 / inArea 等)。返回写入行数。

    单条 metric: ``{"name": "accuracy", "subject": "area3", "value": 101.2,
    "unit": "%", "extra": {...}}``
    """
    if not metrics:
        return 0
    from pytest_helper.db import make_client

    client = make_client()
    try:
        client.connect()
        if missing_tables(client):
            print("[recorder] 缺结果表, 跳过指标落库", file=sys.stderr)
            return 0
        rows = [(run_id, m.get("name", ""), (m.get("subject") or "")[:64],
                 m.get("value"), m.get("unit") or "",
                 json.dumps(m.get("extra"), ensure_ascii=False) if m.get("extra") else None)
                for m in metrics if m.get("value") is not None]
        with client.transaction():
            client.execute("DELETE FROM `metric` WHERE `run_id` = %s", (run_id,))
            client.executemany(
                "INSERT INTO `metric` (run_id, name, subject, value, unit, extra) "
                "VALUES (%s,%s,%s,%s,%s,%s)", rows)
        return len(rows)
    except Exception as exc:
        print(f"[recorder] 指标落库失败: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 0
    finally:
        client.close()


def _dt(value):
    """把 ISO 字符串或 datetime 规范成 MySQL 能收的 DATETIME。"""
    if not value:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    text = str(value).strip().replace("T", " ")
    return text[:19] if text else None


# --------------------------------------------------------------------------
# 查询(供 report / gate / web 用)
# --------------------------------------------------------------------------
def fetch_runs(target: str | None = None, tag: str | None = None,
               limit: int = 50) -> list[dict]:
    from pytest_helper.db import make_client

    where, params = [], []
    if target:
        where.append("`target` = %s")
        params.append(target)
    if tag:
        where.append("`tag` = %s")
        params.append(tag)
    sql = "SELECT * FROM `test_run`"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY `started_at` DESC, `id` DESC LIMIT %s"
    params.append(int(limit))

    client = make_client()
    try:
        client.connect()
        if missing_tables(client):
            return []
        return list(client.query(sql, tuple(params)))
    finally:
        client.close()


def fetch_cases(run_id: str, status: str | None = None,
                limit: int = 500, offset: int = 0) -> list[dict]:
    """取某批次的用例明细。status 可传 failed / passed / skipped / error。"""
    from pytest_helper.db import make_client

    client = make_client()
    try:
        client.connect()
        if missing_tables(client):
            return []
        sql = ("SELECT nodeid, name, module, status, failure_class, duration_sec, message "
               "FROM `case_result` WHERE `run_id` = %s")
        params: list = [run_id]
        if status:
            sql += " AND `status` = %s"
            params.append(status)
        sql += " ORDER BY (`status` IN ('failed','error')) DESC, `duration_sec` DESC LIMIT %s OFFSET %s"
        params += [int(limit), int(offset)]
        return list(client.query(sql, tuple(params)))
    finally:
        client.close()


def run_targets() -> list[str]:
    """结果库里出现过的目标名(给前端下拉用)。"""
    from pytest_helper.db import make_client

    client = make_client()
    try:
        client.connect()
        if missing_tables(client):
            return []
        rows = client.query("SELECT DISTINCT `target` t FROM `test_run` ORDER BY t")
        return [r["t"] for r in rows if r.get("t")]
    finally:
        client.close()


def fetch_metrics(run_ids: list[str] | None = None,
                  name: str | None = None, limit: int = 2000) -> list[dict]:
    from pytest_helper.db import make_client

    client = make_client()
    try:
        client.connect()
        if missing_tables(client):
            return []
        sql = "SELECT * FROM `metric` WHERE 1=1"
        params: list = []
        if run_ids:
            sql += " AND `run_id` IN (" + ",".join(["%s"] * len(run_ids)) + ")"
            params += list(run_ids)
        if name:
            sql += " AND `name` = %s"
            params.append(name)
        sql += " ORDER BY `id` DESC LIMIT %s"
        params.append(int(limit))
        return list(client.query(sql, tuple(params)))
    finally:
        client.close()


def latest_run(target: str | None = None) -> dict | None:
    runs = fetch_runs(target=target, limit=1)
    return runs[0] if runs else None


def purge_runs(run_ids: list[str]) -> dict[str, int]:
    """按 run_id 显式删除批次及其明细/指标。返回各表删除行数。

    这是结果表唯一的删除入口 —— 刻意不做"删全部"或"按时间清"的便捷开关,
    避免哪天一条手滑的调用把趋势数据抹掉。
    """
    if not run_ids:
        return {}
    from pytest_helper.db import make_client

    client = make_client()
    try:
        client.connect()
        if missing_tables(client):
            return {}
        ph = ",".join(["%s"] * len(run_ids))
        deleted: dict[str, int] = {}
        with client.transaction():
            for table in ("metric", "case_result", "test_run"):
                deleted[table] = client.execute(
                    f"DELETE FROM `{table}` WHERE `run_id` IN ({ph})", tuple(run_ids))
        return deleted
    finally:
        client.close()
