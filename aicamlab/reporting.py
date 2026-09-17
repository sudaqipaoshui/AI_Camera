# -*- coding: utf-8 -*-
"""趋势报告: 从结果库生成跨批次、跨固件的对比报告(Markdown + HTML)。

这是"平台化"的关键一环 —— 在此之前每个批次都是一座孤岛(allure 一套、
Stability 一套 txt、ReplayLab 一套 md), 没人能回答"这版比上版好了还是差了"。
"""
from __future__ import annotations

import html
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

OUT_DIR = PROJECT_ROOT / "reports"

EXIT_OK = 0
EXIT_NO_DATA = 3


def _pct(part, whole) -> str:
    try:
        return f"{int(part) / int(whole) * 100:.1f}%" if int(whole) else "—"
    except Exception:
        return "—"


def _delta(cur, prev, unit: str = "", lower_is_better: bool = False) -> str:
    if cur is None or prev is None:
        return "—"
    try:
        d = float(cur) - float(prev)
    except (TypeError, ValueError):
        return "—"
    if abs(d) < 1e-9:
        return "持平"
    arrow = "↑" if d > 0 else "↓"
    good = (d < 0) if lower_is_better else (d > 0)
    return f"{arrow}{abs(d):g}{unit} {'改善' if good else '变差'}"


def collect(limit: int = 60) -> dict:
    from aicamlab import recorder

    runs = recorder.fetch_runs(limit=limit)
    by_target: dict[str, list[dict]] = {}
    for r in runs:
        by_target.setdefault(r.get("target") or "?", []).append(r)
    # fetch_runs 是倒序, 趋势要正序
    for v in by_target.values():
        v.sort(key=lambda r: (str(r.get("started_at") or ""), r.get("id") or 0))

    run_ids = [r["run_id"] for r in runs]
    metrics = recorder.fetch_metrics(run_ids=run_ids) if run_ids else []
    metric_series: dict[tuple[str, str], list[tuple[str, float]]] = {}
    run_index = {r["run_id"]: r for r in runs}
    for m in metrics:
        key = (m.get("name") or "", m.get("subject") or "")
        metric_series.setdefault(key, []).append(
            (m["run_id"], float(m["value"]))) 
    for v in metric_series.values():
        v.sort(key=lambda t: str(run_index.get(t[0], {}).get("started_at") or ""))
    return {"runs": runs, "by_target": by_target, "metric_series": metric_series,
            "run_index": run_index}


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------
def to_markdown(data: dict) -> str:
    runs = data["runs"]
    if not runs:
        return ("# 测试趋势报告\n\n_结果库里还没有任何批次。先跑一次: `python run.py api`_\n")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# 测试趋势报告", "", f"- 生成时间：{now}",
             f"- 数据来源：本机测试库 `test_run` / `case_result` / `metric`",
             f"- 批次总数：{len(runs)}", ""]

    # 总览
    lines += ["## 最近批次", "",
              "| 批次 | 目标 | 开始 | 耗时 | 通过/总数 | 失败 | 跳过 | 结论 | 固件 | 标签 |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for r in runs[:25]:
        lines.append(
            f"| {r.get('run_id')} | {r.get('target')} | {str(r.get('started_at') or '')[:16]} "
            f"| {r.get('duration_sec')}s | {r.get('passed')}/{r.get('total')} "
            f"| {r.get('failed')} | {r.get('skipped')} | {r.get('verdict')} "
            f"| {r.get('firmware') or '—'} | {r.get('tag') or '—'} |")
    lines.append("")

    # 各目标
    lines += ["## 各目标最新一批", ""]
    for target, items in sorted(data["by_target"].items()):
        cur, prev = items[-1], (items[-2] if len(items) > 1 else None)
        lines += [f"### {target}", "",
                  f"- 最新：`{cur.get('run_id')}`  **{cur.get('verdict')}**  "
                  f"{cur.get('passed')}/{cur.get('total')} 通过  "
                  f"（失败 {cur.get('failed')}，跳过 {cur.get('skipped')}）",
                  f"- 固件：`{cur.get('firmware') or '未记录'}`   标签：`{cur.get('tag') or '—'}`"]
        if prev:
            # 注意: 不能在 f-string 的 {} 里换行(Python 3.11 还不支持), 先算好再拼
            d_rate = _delta((cur.get("passed") or 0) / (cur.get("total") or 1),
                            (prev.get("passed") or 0) / (prev.get("total") or 1))
            d_fail = _delta(cur.get("failed"), prev.get("failed"), lower_is_better=True)
            d_cost = _delta(cur.get("duration_sec"), prev.get("duration_sec"), "s", True)
            lines.append(f"- vs 上一批：通过率 {d_rate}   失败数 {d_fail}   耗时 {d_cost}")
        lines.append("")

        # 通过率小趋势
        trend = items[-12:]
        if len(trend) > 1:
            lines += ["| 批次 | 通过率 | 失败 | 耗时(s) | 结论 |", "|---|---|---|---|---|"]
            for r in trend:
                lines.append(f"| {r.get('run_id')} | "
                             f"{_pct(r.get('passed'), r.get('total'))} | {r.get('failed')} "
                             f"| {r.get('duration_sec')} | {r.get('verdict')} |")
            lines.append("")

    # 指标趋势
    if data["metric_series"]:
        lines += ["## 指标趋势", ""]
        for (name, subject), series in sorted(data["metric_series"].items()):
            label = name + (f"[{subject}]" if subject else "")
            vals = [v for _, v in series]
            if not vals:
                continue
            head = f"### {label}"
            lines += [head, "",
                      f"- 最新 **{vals[-1]:g}**   首次 {vals[0]:g}   "
                      f"最小 {min(vals):g}   最大 {max(vals):g}   样本 {len(vals)}",
                      f"- 相对上一批：{_delta(vals[-1], vals[-2] if len(vals) > 1 else None)}", "",
                      "| 批次 | 值 |", "|---|---|"]
            for run_id, val in series[-12:]:
                lines.append(f"| {run_id} | {val:g} |")
            lines.append("")

    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------
CSS = """
body{font-family:-apple-system,'Segoe UI','Microsoft YaHei',sans-serif;background:#fff;
color:#2C2C2A;margin:0;padding:32px 40px;line-height:1.6}
h1{font-size:22px;font-weight:500;margin:0 0 4px}
h2{font-size:16px;font-weight:500;margin:28px 0 10px;padding-bottom:6px;
border-bottom:1px solid #D3D1C7}
h3{font-size:14px;font-weight:500;margin:18px 0 8px;color:#444441}
.meta{color:#5F5E5A;font-size:13px;margin-bottom:20px}
table{border-collapse:collapse;font-size:13px;margin:8px 0 16px;width:100%}
th,td{border:1px solid #D3D1C7;padding:5px 10px;text-align:left}
th{background:#F1EFE8;font-weight:500}
td.num{text-align:right}
.pass{color:#3B6D11;font-weight:500}
.fail{color:#A32D2D;font-weight:500}
.warnc{color:#854F0B;font-weight:500}
.bar{display:inline-block;height:9px;background:#C0DD97;vertical-align:middle;border-radius:2px}
.bar.bad{background:#F09595}
.empty{color:#888780;font-size:13px}
"""


def to_html(data: dict) -> str:
    runs = data["runs"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    esc = html.escape
    out = [f"<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>",
           f"<title>测试趋势报告</title><style>{CSS}</style></head><body>",
           "<h1>测试趋势报告</h1>",
           f"<div class='meta'>生成时间 {now} · 批次总数 {len(runs)} · "
           f"数据来自本机测试库 test_run / case_result / metric</div>"]

    if not runs:
        out.append("<p class='empty'>结果库里还没有任何批次。先跑一次 "
                   "<code>python run.py api</code>。</p></body></html>")
        return "\n".join(out)

    out.append("<h2>最近批次</h2><table><tr>"
               "<th>批次</th><th>目标</th><th>开始</th><th>耗时</th>"
               "<th>通过/总数</th><th>失败</th><th>跳过</th><th>结论</th>"
               "<th>固件</th><th>标签</th></tr>")
    for r in runs[:25]:
        cls = "pass" if r.get("verdict") == "PASS" else "fail"
        out.append(
            f"<tr><td>{esc(str(r.get('run_id')))}</td><td>{esc(str(r.get('target')))}</td>"
            f"<td>{esc(str(r.get('started_at') or '')[:16])}</td>"
            f"<td class='num'>{r.get('duration_sec')}</td>"
            f"<td class='num'>{r.get('passed')}/{r.get('total')}</td>"
            f"<td class='num'>{r.get('failed')}</td><td class='num'>{r.get('skipped')}</td>"
            f"<td class='{cls}'>{esc(str(r.get('verdict')))}</td>"
            f"<td>{esc(str(r.get('firmware') or '—'))}</td>"
            f"<td>{esc(str(r.get('tag') or '—'))}</td></tr>")
    out.append("</table>")

    out.append("<h2>各目标最新一批</h2>")
    for target, items in sorted(data["by_target"].items()):
        cur, prev = items[-1], (items[-2] if len(items) > 1 else None)
        cls = "pass" if cur.get("verdict") == "PASS" else "fail"
        out.append(f"<h3>{esc(target)}</h3>")
        out.append(f"<div>最新 <code>{esc(str(cur.get('run_id')))}</code> · "
                   f"<span class='{cls}'>{esc(str(cur.get('verdict')))}</span> · "
                   f"{cur.get('passed')}/{cur.get('total')} 通过 · "
                   f"固件 <code>{esc(str(cur.get('firmware') or '未记录'))}</code></div>")
        if prev:
            d_rate = _delta((cur.get("passed") or 0) / (cur.get("total") or 1),
                            (prev.get("passed") or 0) / (prev.get("total") or 1))
            d_fail = _delta(cur.get("failed"), prev.get("failed"), lower_is_better=True)
            d_cost = _delta(cur.get("duration_sec"), prev.get("duration_sec"), "s", True)
            out.append(f"<div class='meta'>vs 上一批：通过率 {esc(d_rate)} · "
                       f"失败数 {esc(d_fail)} · 耗时 {esc(d_cost)}</div>")
        rows = items[-12:]
        if len(rows) > 1:
            out.append("<table><tr><th>批次</th><th>通过率</th><th></th>"
                       "<th>失败</th><th>耗时(s)</th><th>结论</th></tr>")
            for r in rows:
                total = r.get("total") or 0
                pct = (r.get("passed") or 0) / total * 100 if total else 0
                bad = "bad" if pct < 95 else ""
                out.append(
                    f"<tr><td>{esc(str(r.get('run_id')))}</td>"
                    f"<td class='num'>{pct:.1f}%</td>"
                    f"<td><span class='bar {bad}' style='width:{max(2, pct):.0f}px'></span></td>"
                    f"<td class='num'>{r.get('failed')}</td>"
                    f"<td class='num'>{r.get('duration_sec')}</td>"
                    f"<td>{esc(str(r.get('verdict')))}</td></tr>")
            out.append("</table>")

    if data["metric_series"]:
        out.append("<h2>指标趋势</h2><table><tr><th>指标</th><th>最新</th>"
                   "<th>首次</th><th>最小</th><th>最大</th><th>样本</th><th>环比</th></tr>")
        for (name, subject), series in sorted(data["metric_series"].items()):
            vals = [v for _, v in series]
            if not vals:
                continue
            label = name + (f"[{subject}]" if subject else "")
            out.append(
                f"<tr><td>{esc(label)}</td><td class='num'>{vals[-1]:g}</td>"
                f"<td class='num'>{vals[0]:g}</td><td class='num'>{min(vals):g}</td>"
                f"<td class='num'>{max(vals):g}</td><td class='num'>{len(vals)}</td>"
                f"<td>{esc(_delta(vals[-1], vals[-2] if len(vals) > 1 else None))}</td></tr>")
        out.append("</table>")

    out.append("</body></html>")
    return "\n".join(out)


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------
def build_report(limit: int = 60) -> tuple[Path | None, int, str]:
    from aicamlab import recorder

    try:
        data = collect(limit=limit)
    except Exception as exc:
        return None, EXIT_NO_DATA, f"读取结果库失败: {type(exc).__name__}: {exc}"

    if not data["runs"]:
        text = ("\n结果库里还没有任何批次。\n\n"
                "  先跑一次:  python run.py api\n"
                "  或在不落库的模式下先把表建好:  python SQL/init_db.py\n")
        return None, EXIT_NO_DATA, text

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = OUT_DIR / f"趋势报告_{ts}.md"
    html_path = OUT_DIR / f"趋势报告_{ts}.html"
    md_path.write_text(to_markdown(data), encoding="utf-8")
    html_path.write_text(to_html(data), encoding="utf-8")
    (OUT_DIR / "latest.md").write_text(to_markdown(data), encoding="utf-8")
    (OUT_DIR / "latest.html").write_text(to_html(data), encoding="utf-8")

    text = (f"\n趋势报告已生成:\n  {md_path}\n  {html_path}\n"
            f"  (同时更新 {OUT_DIR / 'latest.html'})\n  "
            f"覆盖 {len(data['runs'])} 个批次, {len(data['by_target'])} 个目标, "
            f"{len(data['metric_series'])} 个指标序列\n")
    return html_path, EXIT_OK, text


if __name__ == "__main__":
    path, code, text = build_report()
    print(text)
    sys.exit(code)
