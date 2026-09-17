#!/usr/bin/env python
# coding: utf-8
"""
跳远日志分析 Runner（参考长跑 test_runner.py 模式）
配置 log_file_path 与可选时间范围后，执行跳远分析，输出 testid、name、成绩；
同时将结果 CSV 生成到 allure-report/log_analysis/<日期>/ 目录。
"""
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 配置：日志文件路径（相对项目根或绝对路径）
log_file_path = "Log/20260204/app/111927970_2026-02-04_14-02-06.log"
# 可选：只分析该时间段内的成绩
fallback_start_time = None  # 例如 '2026-02-04 13:49:00'
fallback_end_time = None    # 例如 '2026-02-04 14:00:00'
# 是否输出 CSV 到 allure 目录（默认 True）
output_csv_to_allure = True
# 自定义 CSV 路径（若设置则优先于 allure 目录）
output_csv = None  # 例如 'allure-report/log_analysis/20260204/longjump_results.csv'


def _allure_longjump_csv_path(project_root: Path, log_path: Path) -> Path:
    """根据日志路径或当前日期，生成 allure 目录下的 CSV 路径。"""
    date_str = datetime.now().strftime("%Y%m%d")
    # 尝试从日志文件名提取日期，如 111927970_2026-02-04_14-02-06.log -> 20260204
    match = re.search(r"_(\d{4})-(\d{2})-(\d{2})_", log_path.name)
    if match:
        date_str = f"{match.group(1)}{match.group(2)}{match.group(3)}"
    csv_dir = project_root / "allure-report" / "log_analysis" / date_str
    csv_dir.mkdir(parents=True, exist_ok=True)
    return csv_dir / "longjump_results.csv"


class TestLongjumpLog(object):
    """跳远日志分析用例"""

    def test_analyze_longjump_log(self, project_root):
        """分析跳远 APP 日志，输出 testid、name、成绩（cm），并生成 CSV 到 allure 目录"""
        log_file = (
            project_root / log_file_path
            if not Path(log_file_path).is_absolute()
            else Path(log_file_path)
        )
        if not log_file.exists():
            raise FileNotFoundError(f"日志文件不存在: {log_file}")

        analyze_script = project_root / "Log" / "analyze_longjump_log.py"
        if not analyze_script.exists():
            raise FileNotFoundError(f"分析脚本不存在: {analyze_script}")

        cmd = [sys.executable, str(analyze_script.resolve()), str(log_file.resolve())]
        if fallback_start_time:
            cmd.extend(["--start-time", fallback_start_time])
        if fallback_end_time:
            cmd.extend(["--end-time", fallback_end_time])

        # 确定 CSV 输出路径：自定义 > 固定输出到 allure
        if output_csv:
            out_csv = project_root / output_csv if not Path(output_csv).is_absolute() else Path(output_csv)
        elif output_csv_to_allure:
            out_csv = _allure_longjump_csv_path(project_root, log_file)
        else:
            out_csv = None
        if out_csv:
            out_csv.parent.mkdir(parents=True, exist_ok=True)
            cmd.extend(["--csv", str(out_csv.resolve())])

        result = subprocess.run(cmd, cwd=str(project_root.resolve()))
        assert result.returncode == 0, f"跳远日志分析脚本退出码: {result.returncode}"
