#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""pytest_helper 的显式异常类型。

存在意义
--------
让"失败"在**源头**就带上可读原因，而不是等到断言层拿着一个 bytes 去跑
jsonpath，最后抛出 `check_key: code` 这种与真实原因无关的信息。

典型场景：设备/网关不可达时，响应体是纯文本::

    b'upstream connect failed: connection timed out\\n'

过去 `http_client.TSPRequest.request()` 会把非 JSON 响应原样返回 bytes，
于是测试里 `response['code']` 抛::

    TypeError: byte indices must be integers or slices, not str

或让 jsonpath 返回 False 从而报::

    AssertionError: check_key: code

—— 连接层故障被伪装成业务断言失败。这正是"跑完不知道结论可不可信"的机制本身。

`failure_class` 供 aicamlab 平台侧归因使用（env / case / product / unknown）。
"""

BODY_EXCERPT_LIMIT = 600

#: 失败归因分类（与 aicamlab.failure 共享口径）
CLASS_ENV = "env"          # 环境/基础设施：目标不可达、网关、非 JSON 传输响应
CLASS_CASE = "case"        # 用例自身：数据文件串用、期望值过期
CLASS_PRODUCT = "product"  # 产品缺陷：业务 code 非 0
CLASS_UNKNOWN = "unknown"  # 待定


def _as_text(body) -> str:
    if body is None:
        return ""
    if isinstance(body, bytes):
        return body.decode("utf-8", errors="replace")
    return str(body)


class NonJsonResponse(Exception):
    """响应体不是 JSON —— 通常是连接层/网关故障，而不是业务返回。

    携带 URL / 状态码 / Content-Type / 原文截断，让失败信息自解释。
    """

    failure_class = CLASS_ENV

    def __init__(self, url, status_code=None, content_type=None, body=None,
                 method=None, expect_json=True):
        self.url = url
        self.status_code = status_code
        self.content_type = content_type
        self.body = _as_text(body)
        self.method = method
        self.expect_json = expect_json
        super().__init__(self.render())

    @property
    def excerpt(self) -> str:
        text = self.body.strip()
        if not text:
            return "(空响应体)"
        if len(text) > BODY_EXCERPT_LIMIT:
            return (text[:BODY_EXCERPT_LIMIT]
                    + f"\n... (已截断, 原文共 {len(text)} 字符)")
        return text

    @property
    def hint(self) -> str:
        """按状态码与原文内容给一句人话原因，便于快速判断归属。"""
        low = self.body.lower()
        if any(k in low for k in ("connect failed", "connection timed out",
                                  "timed out", "timeout", "unreachable")):
            return "目标不可达 / 连接超时 —— 多半是设备或网关没起来，不是接口逻辑问题"
        if "upstream" in low:
            return "上游(upstream)异常 —— 网关后面的服务不可用"
        if "proxy" in low:
            return "代理层返回了非 JSON 内容"
        if "no such file" in low or "not found" in low:
            return "返回了『不存在』类文本 —— 可能路径写错或资源未部署"
        if self.status_code is not None:
            if self.status_code >= 500:
                return f"HTTP {self.status_code} 服务端错误"
            if self.status_code == 404:
                return "HTTP 404 —— 路由不存在，检查 path 或目标 host 是否搞错"
            if self.status_code in (301, 302, 307, 308):
                return f"HTTP {self.status_code} 重定向 —— 实际打到了错误的服务"
        if self.content_type and "html" in self.content_type.lower():
            return "返回了 HTML 页面 —— 请求多半打到了 Web 服务而非接口"
        if not self.body.strip():
            return "响应体为空 —— 连接被中断或服务直接断开"
        return "响应体不是 JSON，无法按 jsonpath 校验"

    def render(self) -> str:
        head = (f"响应不是 JSON，无法按 jsonpath 校验"
                f"（期望 JSON，实际 {len(self.body)} 字符文本）")
        lines = [head, ""]
        req = f"  {self.method} {self.url}" if self.method else f"  {self.url}"
        lines.append(f"请求:{req}")
        if self.status_code is not None:
            lines.append(f"状态码: {self.status_code}")
        if self.content_type:
            lines.append(f"Content-Type: {self.content_type}")
        lines.append(f"判断: {self.hint}")
        lines.append("")
        lines.append("响应原文（截断）:")
        lines.append("  " + self.excerpt.replace("\n", "\n  "))
        lines.append("")
        lines.append("提示: 响应层故障会伪装成业务断言失败。"
                     "先确认目标设备/网关可达，再怀疑接口逻辑。")
        return "\n".join(lines)


class NonJsonForCheck(NonJsonResponse):
    """由断言层抛出：拿到的对象不是 dict/list，jsonpath 无法工作。

    与 NonJsonResponse 的区别是这里只有"手上这个东西"，
    没有 HTTP 上下文（状态码 / Content-Type）。
    """

    def __init__(self, response, where=None):
        self.where = where
        self.actual_type = type(response).__name__
        raw = _as_text(response)
        super().__init__(url=f"(断言处{(' ' + where) if where else ''})",
                         status_code=None, content_type=None, body=raw)

    def render(self) -> str:
        lines = [
            f"断言目标不是可解析的 JSON 对象：实际类型 {self.actual_type}",
            "",
            f"位置: {self.where or '未知'}",
        ]
        if self.actual_type == "bytes":
            lines.append("判断: 响应被当作 bytes 传下来了 —— "
                         "多半是连接层/网关返回了非 JSON 文本")
        elif self.actual_type in ("NoneType",):
            lines.append("判断: 响应为 None —— 请求可能根本没发出去")
        else:
            lines.append("判断: jsonpath 只能作用于 dict/list")
        lines.append("")
        lines.append("对象原文（截断）:")
        lines.append("  " + self.excerpt.replace("\n", "\n  "))
        return "\n".join(lines)


class DeviceUnreachable(NonJsonResponse):
    """目标设备/TCP 层不可达（连接被拒绝、超时）。"""

    failure_class = CLASS_ENV

    def __init__(self, target, reason=None):
        self.target = target
        self.reason = reason
        super().__init__(url=str(target), body=reason or "", expect_json=False)

    def render(self) -> str:
        return (f"目标不可达: {self.target}\n"
                f"原因: {self.reason or '连接失败/超时'}\n"
                f"判断: 环境问题 —— 该地址的设备或服务没起来，或 IP 已失效")
