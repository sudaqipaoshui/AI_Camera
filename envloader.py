# -*- coding: utf-8 -*-
"""统一凭据加载器 —— 全项目唯一入口。

设计原则
--------
1. 仓库里不出现任何明文凭据。配置文件只写 ``${VAR}`` 占位符。
2. 取值优先级: 真实环境变量 > 项目根 ``.env`` > 显式传入的 default。
   真实环境变量优先, 是为了让 CI / 容器可以直接注入而不用落盘 .env。
3. 零第三方依赖。不引入 python-dotenv, 避免影响既有 venv 的可运行性。
4. 缺变量就报错, 不给"兜底默认密码"。历史上代码里写死的默认口令
   正是凭据泄露的根源, 这里刻意 fail-fast。

用法
----
    from envloader import get, require, load_yaml

    pwd  = require("CAMERA_SSH_PASSWORD")      # 缺了就抛 RuntimeError
    port = get("CAMERA_SSH_PORT", "22")        # 有默认值
    cfg  = load_yaml("config/test/camera.yaml")  # 自动展开 ${VAR}
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"

# ${VAR} 与 $VAR 两种写法都支持
_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

_loaded_files: set[Path] = set()


# --------------------------------------------------------------------------
# .env 解析
# --------------------------------------------------------------------------
def _parse_env_file(path: Path) -> dict[str, str]:
    """解析 .env。支持: # 注释 / 空行 / export 前缀 / 单双引号包裹 / 值内 = 号。"""
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        # 去掉成对的引号, 保留值内的空格与特殊字符
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if not key:
            continue
        result[key] = value
    return result


def load_env(path: str | Path | None = None, force: bool = False) -> None:
    """把 .env 灌进 os.environ。已存在的真实环境变量不会被覆盖。"""
    env_path = Path(path) if path else DEFAULT_ENV_FILE
    env_path = env_path if env_path.is_absolute() else PROJECT_ROOT / env_path
    if env_path in _loaded_files and not force:
        return
    _loaded_files.add(env_path)
    for key, value in _parse_env_file(env_path).items():
        os.environ.setdefault(key, value)


# --------------------------------------------------------------------------
# 取值
# --------------------------------------------------------------------------
def get(key: str, default: Any = None) -> Any:
    """取环境变量。空字符串视为未设置(避免 .env 里写了 KEY= 造成假阳性)。"""
    load_env()
    value = os.environ.get(key)
    if value is None or value == "":
        return default
    return value


def require(key: str) -> str:
    """取必填环境变量, 缺失直接失败并提示怎么补。"""
    value = get(key)
    if value is None:
        raise RuntimeError(
            f"缺少必需的环境变量 {key}。\n"
            f"  请确认项目根存在 .env (可从 .env.example 复制), 或直接注入真实环境变量:\n"
            f"      cp .env.example .env      # 然后填入真实值\n"
            f"  期望位置: {DEFAULT_ENV_FILE}"
        )
    return str(value)


def has(key: str) -> bool:
    return get(key) is not None


# --------------------------------------------------------------------------
# ${VAR} 展开
# --------------------------------------------------------------------------
def expand_str(text: str) -> str:
    """把字符串里的 ${VAR} 换成实际值。变量缺失时抛错, 不静默留下占位符。"""
    load_env()

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        value = os.environ.get(name)
        if value is None or value == "":
            raise RuntimeError(
                f"配置里引用了 ${{{name}}}, 但该环境变量未设置。\n"
                f"  请在 .env 中补上 {name}=<真实值>, 或参照 .env.example 说明。"
            )
        return value

    return _PLACEHOLDER.sub(_replace, text)


def expand(obj: Any) -> Any:
    """递归展开 dict / list / str 里的占位符, 其它类型原样返回。"""
    if isinstance(obj, str):
        return expand_str(obj)
    if isinstance(obj, dict):
        return {key: expand(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [expand(item) for item in obj]
    return obj


# --------------------------------------------------------------------------
# YAML 加载
# --------------------------------------------------------------------------
def load_yaml(path: str | Path) -> Any:
    """读 YAML 并展开其中的 ${VAR}。path 可为绝对路径或相对项目根。

    PyYAML 在这里才导入, 让本模块的 get/require 不依赖第三方库。
    """
    import yaml  # 局部导入: 仅 load_yaml 需要

    yaml_path = Path(path)
    if not yaml_path.is_absolute():
        yaml_path = PROJECT_ROOT / yaml_path
    if not yaml_path.is_file():
        raise FileNotFoundError(f"配置文件不存在: {yaml_path}")
    with open(yaml_path, encoding="utf-8") as handle:
        data = yaml.load(handle.read(), Loader=yaml.SafeLoader)
    return expand(data)


if __name__ == "__main__":  # 自检: python envloader.py
    load_env(force=True)
    print(f"项目根      : {PROJECT_ROOT}")
    print(f".env 文件   : {DEFAULT_ENV_FILE} ({'存在' if DEFAULT_ENV_FILE.is_file() else '不存在'})")
    print(f"已加载变量数: {len(os.environ)}")
    for probe in ("CAMERA_SSH_PASSWORD", "YUNTIYU_X_TOKEN", "UAD_MYSQL_PASSWORD"):
        print(f"  {probe:<24} {'已设置' if has(probe) else '未设置'}")
