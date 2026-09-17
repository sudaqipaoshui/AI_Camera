#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""失败信息的可读性回归测试（纯函数，不需要设备）。

守护两个曾经真实发生的问题：

1. 非 JSON 响应被静默当作 bytes 传下去，导致失败信息与真实原因无关
   （`TypeError: byte indices...` / `AssertionError: check_key: code`），
   掩盖了连接层故障。

2. **假通过**：jsonpath 作用于 bytes 时返回 `False`，而旧代码写的是
   `assert actual == expect`；当期望值是 `0`（最常见的"成功"码）时，
   `False == 0` 在 Python 里为真 —— 设备不可达却判定用例通过。
   这条断言锁死该路径，防止回归。
"""
import pytest

from pytest_helper.assertions import free_compare, _require_mapping
from pytest_helper.errors import NonJsonForCheck, NonJsonResponse

# 设备/网关不可达时真实出现过的响应体
DEAD_BODY = b'upstream connect failed: connection timed out\n'


def test_non_json_response_message_is_self_explanatory():
    """NonJsonResponse 必须带上 URL、状态码与原文，并给出人话判断。"""
    exc = NonJsonResponse(url='http://192.168.1.245/camera/login',
                          status_code=502, content_type='text/plain',
                          body=DEAD_BODY, method='POST')
    text = str(exc)
    assert 'http://192.168.1.245/camera/login' in text
    assert '502' in text
    assert 'upstream connect failed' in text
    assert '不是 JSON' in text
    assert exc.failure_class == 'env'


def test_bytes_body_raises_instead_of_silently_failing():
    """断言层拿到 bytes 必须显式报错，而不是让 jsonpath 静默返回 False。"""
    with pytest.raises(NonJsonForCheck) as ei:
        free_compare(DEAD_BODY, {'response': {'code': 0}})
    assert 'bytes' in str(ei.value)


def test_none_body_raises():
    with pytest.raises(NonJsonForCheck):
        _require_mapping(None, 'free_compare')


def test_false_pass_path_is_closed():
    """核心回归：期望 code=0 时，不可达响应绝不能再被判为通过。

    旧行为：jsonpath(bytes,'code') -> False，且 False == 0 -> 断言通过。
    现在必须在进入断言前就抛 NonJsonForCheck。
    """
    for expect in (0, False, 0.0):
        with pytest.raises(NonJsonForCheck):
            free_compare(DEAD_BODY, {'response': {'code': expect}})


def test_jsonpath_miss_message_says_path_missing():
    """jsonpath 未命中要与"值不符"区分开，否则无法归因。"""
    with pytest.raises(AssertionError) as ei:
        free_compare({'data': {'item_id': 7}}, {'response': {'data.nope': 1}})
    assert '未命中' in str(ei.value)


def test_value_mismatch_message_shows_actual():
    with pytest.raises(AssertionError) as ei:
        free_compare({'data': {'item_id': 7}}, {'response': {'data.item_id': 9}})
    msg = str(ei.value)
    assert '值不符' in msg and '7' in msg


def test_valid_assertions_still_pass():
    """回归：正常断言不能被误伤。"""
    free_compare({'data': {'item_id': 7}}, {'response': {'data.item_id': 7}})
    free_compare({'code': 0, 'layer': 3}, {'response': {'code': 0}})
    free_compare({'code': 0, 'msg': 'ok'}, {'response': {'_keys_$': ['code', 'msg']}})
    # all=True 是全匹配，jsonpath 返回"命中的列表"，故期望也是嵌套列表
    free_compare({'a': {'b': [1, 2]}}, {'response': {'a.b': [[1, 2]]}}, all=True)
