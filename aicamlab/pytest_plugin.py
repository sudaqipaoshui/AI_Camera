# -*- coding: utf-8 -*-
"""pytest 采集插件: 输出 JSON 摘要, 并把结果落到测试库。

只由 run.py 通过 ``-p aicamlab.pytest_plugin`` 显式挂载 —— 裸跑 pytest 不会加载它,
因此不会改变任何既有用例的行为。

落库失败**绝不**影响测试结论: 所有数据库相关动作都包在 try/except 里,
失败只打警告。原因很实在 —— 测试库挂了不代表被测固件有问题。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_MESSAGE_LIMIT = 6000


def _truncate_middle(text: str, limit: int = _MESSAGE_LIMIT) -> str:
    """超长时**掐中间、保两头**。

    不能只留头部: pytest 的 longrepr 前面是一大坨请求/响应 dump, 真正的报错行
    (``E   assert -1 == 0``) 在**最后**。只留头部会把唯一有价值的信息切掉 ——
    实测 22 条失败里有 15 条因此变成"无消息"。
    """
    if len(text) <= limit:
        return text
    head = limit // 3
    tail = limit - head - 40
    return f"{text[:head]}\n... [中间省略 {len(text) - head - tail} 字符] ...\n{text[-tail:]}"


def pytest_addoption(parser):
    group = parser.getgroup("aicamlab", "AICameraTestLab 采集")
    group.addoption("--aicamlab-json", action="store", default=None,
                    help="把本次运行的 JSON 摘要写到该路径")
    group.addoption("--aicamlab-run-id", action="store", default=None,
                    help="批次号(由 run.py 生成)")
    group.addoption("--aicamlab-target", action="store", default=None,
                    help="目标名, 如 api / e2e / replay")
    group.addoption("--aicamlab-tag", action="store", default=None,
                    help="批次标签, 如固件版本或里程碑")
    group.addoption("--aicamlab-record-run", action="store_true", default=False,
                    help="把结果写入测试库(库不可用时只警告)")
    group.addoption("--aicamlab-no-record", action="store_true", default=False,
                    help="显式关闭落库")


class Collector:
    """把 pytest 的报告事件整理成批次 + 用例级结果。"""

    WORST = {"passed": 0, "skipped": 1, "failed": 2, "error": 3}

    def __init__(self):
        self.cases: dict[str, dict] = {}
        self.started_at = datetime.now().isoformat(timespec="seconds")

    def on_report(self, report) -> None:
        if report.when == "call":
            status = report.outcome if report.outcome in ("passed", "failed") else "skipped"
            if report.outcome == "skipped":
                status = "skipped"
        elif report.when == "setup":
            if report.failed:
                status = "error"
            elif report.skipped:
                status = "skipped"
            else:
                return
        elif report.when == "teardown":
            if report.failed:
                status = "error"
            else:
                return
        else:
            return

        item = self.cases.setdefault(report.nodeid, {
            "nodeid": report.nodeid,
            "name": report.nodeid.rsplit("::", 1)[-1],
            "module": report.nodeid.split("::", 1)[0].replace("/", ".").removesuffix(".py"),
            "status": "passed",
            "duration_sec": 0.0,
            "message": "",
        })
        if self.WORST.get(status, 0) >= self.WORST.get(item["status"], 0):
            item["status"] = status
        item["duration_sec"] = round(item["duration_sec"] + float(report.duration or 0), 3)
        if report.failed or (report.skipped and not item["message"]):
            text = getattr(report, "longreprtext", "") or ""
            if text:
                # ⚠️ 断言失败输出里会带整个 fixture 的 repr, 本项目 env fixture 含明文凭据。
                # 落库前必须脱敏, 否则口令会长期留在结果库里(见 aicamlab/redact.py 的说明)。
                from aicamlab.redact import scrub
                item["message"] = _truncate_middle(scrub(text))

    def counts(self) -> dict:
        out = {"total": len(self.cases), "passed": 0, "failed": 0,
               "error": 0, "skipped": 0}
        for c in self.cases.values():
            out[c["status"]] = out.get(c["status"], 0) + 1
        return out


# pytest 9 的 TestReport 上没有 .config 属性, 因此状态放模块级而不是挂在 config 上
_COLLECTOR: Collector | None = None
_STARTED: datetime | None = None


def pytest_configure(config):
    global _COLLECTOR, _STARTED
    if config.getoption("--aicamlab-no-record"):
        return
    _COLLECTOR = Collector()
    _STARTED = datetime.now()


def pytest_runtest_logreport(report):
    if _COLLECTOR is not None:
        _COLLECTOR.on_report(report)


def pytest_sessionfinish(session, exitstatus):
    collector = _COLLECTOR
    if collector is None:
        return

    finished = datetime.now()
    started = _STARTED or finished
    counts = collector.counts()
    exit_code = int(exitstatus)
    verdict = "PASS" if exit_code == 0 else ("FAIL" if counts["failed"] or counts["error"] else "ERROR")

    summary = {
        "run_id": session.config.getoption("--aicamlab-run-id"),
        "target": session.config.getoption("--aicamlab-target"),
        "tag": session.config.getoption("--aicamlab-tag"),
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": finished.isoformat(timespec="seconds"),
        "duration_sec": round((finished - started).total_seconds(), 2),
        "exit_code": exit_code,
        "verdict": verdict,
        "counts": counts,
        "cases": list(collector.cases.values()),
    }

    out = session.config.getoption("--aicamlab-json")
    if out:
        try:
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            Path(out).write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        except Exception as exc:
            print(f"[aicamlab] 写摘要失败: {exc}", file=sys.stderr)

    if session.config.getoption("--aicamlab-record-run"):
        try:
            from aicamlab import recorder
            recorder.record_summary(summary, log_path=None)
        except Exception as exc:
            print(f"[aicamlab] 落库失败(不影响测试结论): {type(exc).__name__}: {exc}",
                  file=sys.stderr)
