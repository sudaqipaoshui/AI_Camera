# -*- coding: utf-8 -*-
"""凭据脱敏: 把即将落库/落盘的文本里的口令遮掉。

为什么需要它
------------
pytest 的断言失败输出会把**整个 fixture 的 repr** 打出来, 本项目里最典型的是::

    env = {..., 'username': '<user>', 'password': '<secret>', ...}

也就是说: 只要有一条用例断言失败, 渲染后的凭据就会出现在
① 控制台 ② allure 报告 ③ pytest 日志文件 ④ 我们现在新增的结果库。

仓库里可以靠 .gitignore 挡住 ①②③, 但**结果库是要长期留存、要出趋势报告、
以后还要给网站查的** —— 凭据一旦进库就等于长期泄露。因此在写库前统一脱敏。

两道防线
--------
1. 按"键名"遮: password / token / secret / licence / ssh_pass ... 后面的值一律替换;
2. 按"字面值"遮: 从 envloader 取出真实凭据值, 文本里出现就替换。
   这一道能兜住"值被单独打印、没有键名陪着"的情况。
"""
from __future__ import annotations

import re
from typing import Any

MASK = "***"

# 键名 -> 值: 覆盖本项目 YAML/字典里出现过的全部敏感字段名
_KEY_PATTERN = (
    r"password|passwd|pwd|pass|token|x_token|authorization|auth|secret|"
    r"licence|license|encodePassword|encode_password|ssh_pass|api_key|apikey|"
    r"private_key|access_key"
)
_KEY_RE = re.compile(
    rf"(?P<key>[\"']?(?:{_KEY_PATTERN})[\"']?\s*[:=]\s*)(?P<q>[\"']?)(?P<val>[^\"'\s,}})\]&]{{2,}})",
    re.IGNORECASE,
)

# 形如 Bearer eyJ... 的 token
_BEARER_RE = re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]{16,}", re.IGNORECASE)

# 字面值替换的最小长度。
# ⚠️ 必须设阈值: 实测有个凭据变量的值恰好是 `root`(4 字符), 无阈值替换会把
# `ssh_user=root` / `/userdata/root` / `root@192.168.2.60` 这类正常文本一起打码,
# 把失败信息毁掉。密钥键名那条路仍然覆盖短口令, 所以这里放宽是安全的。
_MIN_LITERAL = 8

# 从 .env / 环境变量里取真实凭据值, 用于第二道防线
_SECRET_ENV_KEYS = (
    "YUNTIYU_ACCOUNT_PASSWORD",
    "YUNTIYU_ACCOUNT_ENCODE_PASSWORD",
    "YUNTIYU_X_TOKEN",
    "YUNTIYU_SECRET_ID",
    "YUNTIYU_SECRET_KEY",
    "CAMERA_SSH_PASSWORD",
    "X3_SSH_PASSWORD",
    "UAD_MYSQL_PASSWORD",
    "AICAM_MYSQL_PASSWORD",
    "LOCAL_MYSQL_ROOT_PASSWORD",
    "CAMERA_LICENCE",
)

_literals_cache: list[str] | None = None


def _literal_secrets() -> list[str]:
    """真实凭据值。惰性加载一次, 按长度倒序(先替长的, 避免短值把长值切碎)。"""
    global _literals_cache
    if _literals_cache is not None:
        return _literals_cache
    values: set[str] = set()
    try:
        import envloader
        for key in _SECRET_ENV_KEYS:
            val = envloader.get(key)
            if val and len(str(val)) >= _MIN_LITERAL:
                values.add(str(val))
    except Exception:
        pass
    # 值里可能带 - _ 等, 长值优先替换
    _literals_cache = sorted(values, key=len, reverse=True)
    return _literals_cache


def scrub(text: Any, extra_literals: list[str] | None = None) -> str:
    """返回脱敏后的文本。非字符串会被 str() 化。"""
    if text is None:
        return ""
    out = str(text)
    if not out:
        return out
    # 顺序要紧: Bearer 先做。否则 _KEY_RE 会先把 "Authorization: Bearer" 里的
    # Bearer 当成值遮掉, 后面就再没有 "Bearer <jwt>" 这个形状可匹配, JWT 会漏出来。
    out = _BEARER_RE.sub(rf"\g<1>{MASK}", out)
    out = _KEY_RE.sub(lambda m: f"{m.group('key')}{m.group('q')}{MASK}", out)
    for literal in (_literal_secrets() + list(extra_literals or [])):
        if literal and len(literal) >= _MIN_LITERAL and literal in out:
            out = out.replace(literal, MASK)
    return out


def scrub_mapping(data: dict) -> dict:
    """对 dict 里所有字符串值做脱敏(浅层, 够用)。"""
    return {k: (scrub(v) if isinstance(v, str) else v) for k, v in data.items()}
