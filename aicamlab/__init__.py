# -*- coding: utf-8 -*-
"""AICameraTestLab 平台工具箱。

分层:
  runner      —— 统一入口的执行层(目标注册表 + 子进程执行 + 结果汇总)
  pytest_plugin —— 挂在 pytest 上的采集插件(输出 JSON 摘要 + 落库)
  recorder    —— 结果落库(批次 / 用例 / 指标)
  reporting   —— 跨批次趋势报告
  gating      —— 发布门禁判定

对外只暴露 run.py 一个命令行入口, 本包不直接给用例使用。
"""
from pathlib import Path
import sys

__all__ = ["PROJECT_ROOT", "API_DIR", "SQL_DIR", "LOG_DIR", "REPORTS_DIR"]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_DIR = PROJECT_ROOT / "API"
SQL_DIR = PROJECT_ROOT / "SQL"
LOG_DIR = PROJECT_ROOT / "Log"
REPORTS_DIR = PROJECT_ROOT / "reports"

# 项目约定: `pytest_helper` 住在 API/ 下(根 conftest.py 也是这么做的)。
# 这里补一次, 让 run.py / recorder 这类"不在 pytest 里跑"的入口也能 import 到它。
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))
