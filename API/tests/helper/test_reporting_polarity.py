# -*- coding: utf-8 -*-
"""reporting 指标极性(_delta / _is_lower_better)的回归测试(纯函数, 不需设备/库)。

守护一个真实发生过的 bug: 指标趋势的环比方向判断默认"越高越好",
导致 spread(极差)/invalid_areas(无效路) 这类"越低越好"的指标方向标反
(极差从 28 降到 1 却被标成"变差")。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aicamlab.reporting import _delta, _is_lower_better


def test_accuracy_is_higher_better():
    assert not _is_lower_better("accuracy")
    assert not _is_lower_better("in_area")
    # 越高越好: 上升=改善, 下降=变差
    assert "改善" in _delta(101, 96)          # ↑5 改善
    assert "变差" in _delta(96, 101)          # ↓5 变差


def test_spread_is_lower_better():
    assert _is_lower_better("spread")
    assert _is_lower_better("spread_max")
    assert _is_lower_better("spread_mean")
    # 越低越好: 下降=改善
    assert "改善" in _delta(1, 28, lower_is_better=True)
    assert "变差" in _delta(28, 1, lower_is_better=True)


def test_invalid_areas_is_lower_better():
    assert _is_lower_better("invalid_areas")


def test_delta_flat_is_持平():
    assert _delta(5, 5) == "持平"


def test_delta_none_prev_is_dash():
    assert _delta(5, None) == "—"
