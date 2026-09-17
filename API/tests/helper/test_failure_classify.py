# -*- coding: utf-8 -*-
"""failure.classify 归因口径的回归测试(纯函数, 不需设备)。

这些断言锁死"什么失败算 env / case / product / unknown",
是"门禁只阻塞产品缺陷"这一口径的基础 —— 归因错一条, 门禁就判错一次。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aicamlab.failure import classify, classify_many


def test_env_nonjson():
    assert classify("响应不是 JSON，无法按 jsonpath 校验") == "env"


def test_env_unreachable():
    assert classify("目标不可达: 192.168.3.29") == "env"
    assert classify("MaxRetryError: Connection refused") == "env"


def test_env_gateway():
    assert classify("502 Bad Gateway ... upstream connect failed") == "env"
    assert classify("connection timed out") == "env"


def test_case_check_key():
    assert classify("AssertionError: check_key: code") == "case"
    assert classify("KeyError: 'code'") == "case"


def test_case_type_error():
    assert classify("TypeError: byte indices must be integers") == "case"


def test_product_code_minus_one():
    assert classify("assert -1 == 0") == "product"
    assert classify("assert 0 == 405") == "product"


def test_unknown_empty():
    assert classify("") == "unknown"
    assert classify("一段完全看不懂的神秘报错") == "unknown"


def test_env_priority_over_assert():
    # 环境类失败即使文本里带 assert 也要优先判 env(连接层故障会伪装成断言)
    assert classify("响应不是 JSON ... assert 0 == 0") == "env"


def test_classify_many():
    cases = [
        {"status": "failed", "message": "响应不是 JSON", "nodeid": "t1"},
        {"status": "failed", "message": "check_key: code", "nodeid": "t2"},
        {"status": "failed", "message": "assert -1 == 0", "nodeid": "t3"},
        {"status": "failed", "message": "", "nodeid": "t4"},
        {"status": "passed", "message": "", "nodeid": "t5"},  # 通过的不计
    ]
    got = classify_many(cases)
    assert got == {"env": 1, "case": 1, "product": 1, "unknown": 1}
