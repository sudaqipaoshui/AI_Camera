# -*- coding: utf-8 -*-
"""失败归因: 把一条失败用例的 message 归到 failure_class。

口径与 ``API/pytest_helper/errors.py`` 里的 ``CLASS_*`` 常量**共享**:
  env      —— 环境/基础设施: 目标不可达、网关异常、非 JSON 传输响应
  case     —— 用例自身: 数据文件串用、期望值过期、参数化错误
  product  —— 产品缺陷: 业务 code 非 0、断言值不符
  unknown  —— 无法归因, 待人工看

为什么需要一个独立模块而不是只读异常类型:
  1. 结果库里存的是**文本 message**, 异常类型在序列化时已经丢了;
  2. 有些失败(历史批次、ReplayLab 落库的)根本没有走 errors.py 的异常;
  3. 归因必须对"纯字符串"可判定, 才能覆盖任何来源的失败。

设计: 纯函数, 不依赖 pytest, 可用单元测试锁定。
"""

from __future__ import annotations

import re

#: 与 errors.py 保持一致
CLASS_ENV = "env"
CLASS_CASE = "case"
CLASS_PRODUCT = "product"
CLASS_UNKNOWN = "unknown"

# --------------------------------------------------------------------------
# 环境类 (env) —— 连接层/网关/传输层故障, 与业务逻辑无关
# --------------------------------------------------------------------------
_ENV_PATTERNS = (
    # 显式异常类型 (errors.py) 的文案
    "响应不是 JSON",
    "目标不可达",
    "断言目标不是可解析的 JSON",
    "上游(upstream)异常",
    "代理层返回了非 JSON",
    # requests / urllib 连接异常
    "ConnectTimeout",
    "ReadTimeout",
    "ConnectionError",
    "MaxRetryError",
    "Connection refused",
    "connection timed out",
    "Connection reset",
    "Remote end closed connection",
    # 网关层文本
    "upstream connect failed",
    "connection timed out",
    "no route to host",
    "Name or service not known",
    "Temporary failure in name resolution",
    "502 Bad Gateway",
    "503 Service Unavailable",
    "504 Gateway Timeout",
    # TCP/套接字
    "timed out",
    "Errno 10060",
    "Errno 10061",
    "Errno 110",
    "Errno 111",
)

# --------------------------------------------------------------------------
# 用例类 (case) —— 用例/数据文件自身问题, 不是产品逻辑
# --------------------------------------------------------------------------
_CASE_PATTERNS = (
    # 数据文件串用 / 期望值缺失
    "check_key",
    "KeyError",
    "没有这个键",
    "路径不存在",
    # 参数化错误
    "byte indices must be integers",
    "not subscriptable",
    # pytest 收集/装配
    "fixture",
    "TypeError",
    "AttributeError",
    "IndexError",
)

# --------------------------------------------------------------------------
# 产品类 (product) —— 业务返回非预期, 才是"产品缺陷"信号
# --------------------------------------------------------------------------
_PRODUCT_PATTERNS = (
    "assert -1 ==",          # code:-1 业务失败
    "code:-1",
    "assert 0 ==",           # 期望成功码 0, 实际非 0
    "assert",                 # 兜底: 显式断言失败, 优先视为产品侧
)


def _match(text: str, patterns: tuple[str, ...]) -> bool:
    return any(p in text for p in patterns)


def classify(message: str | None, nodeid: str = "") -> str:
    """把一条失败 message 归到 env/case/product/unknown。

    判定顺序刻意如此:
      1. 环境类优先 —— 连接层故障会伪装成各种断言错误, 必须先判;
      2. 用例类次之 —— check_key / KeyError 等是数据文件问题;
      3. 产品类 —— 剩下的显式 assert 失败才归产品;
      4. 都匹配不上 → unknown。
    """
    text = (message or "").strip()
    if not text:
        return CLASS_UNKNOWN

    if _match(text, _ENV_PATTERNS):
        return CLASS_ENV
    if _match(text, _CASE_PATTERNS):
        return CLASS_CASE
    if _match(text, _PRODUCT_PATTERNS):
        return CLASS_PRODUCT
    return CLASS_UNKNOWN


def classify_many(cases: list[dict]) -> dict[str, int]:
    """对一批用例明细计数各类别。cases 形如 recorder.fetch_cases 的返回。"""
    counts = {CLASS_ENV: 0, CLASS_CASE: 0, CLASS_PRODUCT: 0, CLASS_UNKNOWN: 0}
    for c in cases:
        if (c.get("status") or "") in ("failed", "error"):
            cls = c.get("failure_class") or classify(c.get("message"), c.get("nodeid", ""))
            counts[cls] = counts.get(cls, 0) + 1
    return counts
