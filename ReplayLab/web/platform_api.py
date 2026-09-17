# -*- coding: utf-8 -*-
"""平台视图接口: 把结果库(test_run / case_result / metric)暴露给 ReplayLab 网站。

为什么放在这里
--------------
ReplayLab 的网站本来只看得到"本地 reports/ 目录里的 md 文件" —— 那是模块级视图。
加了这一层之后, 同一个界面就能回答"这版固件比上版好还是差", 不用再翻一个个孤立的报告。

设计原则: **库不可用不能让页面崩**。所有接口在数据库缺失/连不上时
返回 ``{"ok": false, "error": "..."}`` 且 HTTP 200, 由前端展示成一句人话。
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

bp = Blueprint("platform", __name__)

REPORTS_DIR = PROJECT_ROOT / "reports"


def _norm(value):
    """把 DB 取出来的值规范化成前端好用的类型。

    ⚠️ 不能直接把行丢给 jsonify: Flask 会把 datetime 序列化成 HTTP 日期
    (``"Thu, 17 Sep 2026 11:36:34 GMT"``), 前端按 ``YYYY-MM-DD HH:MM`` 切片会切出乱码;
    DECIMAL 则会变成字符串 ``"0.00"``, 参与比较/相减时出错。
    """
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", "replace")
    return value


def _rows(rows):
    return [{k: _norm(v) for k, v in dict(r).items()} for r in (rows or [])]


def _fail(exc: Exception) -> dict:
    return {"ok": False, "error": f"{type(exc).__name__}: {exc}",
            "hint": "检查测试库是否可用(python SQL/selfcheck.py), "
                    "以及结果表是否已建(python SQL/init_db.py)"}


def _limited(limit: int, default: int = 50, cap: int = 500) -> int:
    try:
        return max(1, min(int(limit), cap))
    except (TypeError, ValueError):
        return default


@bp.get("/api/platform/status")
def api_status():
    """结果库连通性与规模, 前端据此决定显示数据还是显示提示。"""
    try:
        from aicamlab import recorder
        latest = recorder.fetch_runs(limit=1)
        all_runs = recorder.fetch_runs(limit=500)
        return jsonify({"ok": True, "total_runs": len(all_runs),
                        "targets": recorder.run_targets(),
                        "latest": _rows(latest)[0] if latest else None})
    except Exception as exc:
        return jsonify(_fail(exc))


@bp.get("/api/runs")
def api_runs():
    try:
        from aicamlab import recorder
        runs = recorder.fetch_runs(
            target=request.args.get("target") or None,
            tag=request.args.get("tag") or None,
            limit=_limited(request.args.get("limit", 50), 50, 500),
        )
        return jsonify({"ok": True, "runs": _rows(runs),
                        "targets": recorder.run_targets()})
    except Exception as exc:
        return jsonify(_fail(exc))


@bp.get("/api/run/<run_id>")
def api_run_detail(run_id):
    try:
        from aicamlab import recorder
        runs = [r for r in recorder.fetch_runs(limit=500) if r.get("run_id") == run_id]
        if not runs:
            return jsonify({"ok": False, "error": f"没有批次 {run_id}"}), 404
        status = request.args.get("status") or None
        cases = recorder.fetch_cases(run_id, status=status,
                                     limit=_limited(request.args.get("limit", 300), 300, 2000))
        metrics = recorder.fetch_metrics(run_ids=[run_id])
        return jsonify({"ok": True, "run": _rows(runs)[0],
                        "cases": _rows(cases), "metrics": _rows(metrics)})
    except Exception as exc:
        return jsonify(_fail(exc))


@bp.get("/api/trend")
def api_trend():
    """按目标给出趋势: 每批次的通过率 / 失败数 / 耗时, 以及指标序列。"""
    try:
        from aicamlab import reporting
        data = reporting.collect(limit=_limited(request.args.get("limit", 60), 60, 300))
        out_targets = {}
        for target, items in data["by_target"].items():
            out_targets[target] = [{
                "run_id": r.get("run_id"),
                "started_at": _norm(r.get("started_at")) or "",
                "passed": r.get("passed"), "total": r.get("total"),
                "failed": r.get("failed"), "skipped": r.get("skipped"),
                "duration_sec": float(r.get("duration_sec") or 0),
                "verdict": r.get("verdict"),
                "firmware": r.get("firmware"), "tag": r.get("tag"),
                "pass_rate": round((r.get("passed") or 0) / (r.get("total") or 1) * 100, 1),
            } for r in items]
        series = {f"{name}[{subject}]" if subject else name: [
            {"run_id": rid, "value": float(val)} for rid, val in vals]
            for (name, subject), vals in data["metric_series"].items()}
        return jsonify({"ok": True, "targets": out_targets, "metrics": series,
                        "total_runs": len(data["runs"])})
    except Exception as exc:
        return jsonify(_fail(exc))


@bp.post("/api/platform/trend-report")
@bp.get("/api/platform/trend-report")
def api_trend_report():
    """现生成一份趋势报告(md + html), 返回可打开的地址。"""
    try:
        from aicamlab import reporting
        path, code, text = reporting.build_report()
        if not path:
            return jsonify({"ok": False, "error": text.strip()})
        return jsonify({"ok": True, "path": str(path), "url": "/platform/trend"})
    except Exception as exc:
        return jsonify(_fail(exc))


@bp.get("/platform/trend")
def platform_trend():
    """打开最近一次生成的趋势报告 HTML。"""
    latest = REPORTS_DIR / "latest.html"
    if not latest.is_file():
        return ("<meta charset='utf-8'><p style='font-family:sans-serif;padding:32px'>"
                "还没有生成过趋势报告。回到平台页签点「生成趋势报告」。</p>"), 404
    return send_file(str(latest), mimetype="text/html")


@bp.get("/api/platform/log")
def api_platform_log():
    """取某个批次的原始日志尾部(便于从网站直接看失败上下文)。"""
    run_id = (request.args.get("run_id") or "").strip()
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        return jsonify({"ok": False, "error": "run_id 非法"}), 400
    log_path = PROJECT_ROOT / "Log" / f"_{run_id}.log"
    if not log_path.is_file():
        return jsonify({"ok": False, "error": "日志文件不存在(可能已被清理)"})
    try:
        tail = int(request.args.get("tail", 20000))
    except (TypeError, ValueError):
        tail = 20000
    text = log_path.read_text(encoding="utf-8", errors="replace")
    return jsonify({"ok": True, "size": len(text), "text": text[-max(1000, tail):]})
