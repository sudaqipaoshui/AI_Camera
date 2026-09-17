# -*- coding: utf-8 -*-
"""设备清单: 全项目唯一的"是哪台设备"来源。

读 ``config/devices.yaml``。历史上设备 IP 散在 camera.yaml / items.json /
deploy_camera.sh 三处且不一致(其中一处指向早已离线的旧机器, 导致 22 条 API 用例
必然失败), 这里收敛成一处。

用法::

    from aicamlab.inventory import active_device, apply_to_env

    dev = active_device()          # {"key": "X5_192_168_2_60", "ip": "192.168.2.60", ...}
    env = apply_to_env(env_config) # 把设备身份合并进 env fixture 的字典
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import envloader  # noqa: E402

DEVICES_FILE = PROJECT_ROOT / "config" / "devices.yaml"

# ReplayLab 知识库的兜底位置: 清单文件缺失时仍能拿到一台设备, 不至于直接崩
FALLBACK_KB = PROJECT_ROOT / "ReplayLab" / "items.json"

_cache: dict | None = None


def load_inventory(path: str | Path | None = None, use_cache: bool = True) -> dict:
    """读设备清单。返回 ``{"active": key, "devices": {...}}``; 读不到返回空结构。"""
    global _cache
    if use_cache and _cache is not None and path is None:
        return _cache

    target = Path(path) if path else DEVICES_FILE
    data: dict = {}
    if target.is_file():
        try:
            data = envloader.load_yaml(str(target)) or {}
        except Exception as exc:  # 占位符没配齐 / YAML 写坏
            print(f"[inventory] 读 {target} 失败: {type(exc).__name__}: {exc}", file=sys.stderr)
            data = {}

    if not data.get("devices"):
        data = _from_replaylab_kb()

    if path is None:
        _cache = data
    return data


def _from_replaylab_kb() -> dict:
    """兜底: 从 ReplayLab/items.json 的 _env.devices 取(仅取身份字段)。"""
    import json

    if not FALLBACK_KB.is_file():
        return {}
    try:
        kb = json.loads(FALLBACK_KB.read_text(encoding="utf-8"))
    except Exception:
        return {}
    env = (kb or {}).get("_env") or {}
    devices = env.get("devices") or {}
    identity = {k: {f: v.get(f) for f in ("name", "model", "ip", "ssh_user", "ssh_pass", "token")}
                for k, v in devices.items()}
    return {"active": env.get("active"), "devices": identity, "_source": str(FALLBACK_KB)}


def device_keys() -> list[str]:
    return list((load_inventory().get("devices") or {}).keys())


def get_device(key: str, use_cache: bool = True) -> dict:
    inv = load_inventory(use_cache=use_cache)
    dev = (inv.get("devices") or {}).get(key) or {}
    return dict(dev, key=key) if dev else {}


def active_device(use_cache: bool = True) -> dict:
    """当前激活设备。active 指向不存在的设备时返回空 dict, 由调用方给出明确提示。"""
    inv = load_inventory(use_cache=use_cache)
    key = inv.get("active")
    devices = inv.get("devices") or {}
    if key not in devices:
        # active 为空但恰好只有一台设备时, 就用它
        if not key and len(devices) == 1:
            key = next(iter(devices))
        else:
            return {}
    return dict(devices[key], key=key)


def apply_to_env(env: dict) -> dict:
    """把激活设备的身份合并进 env 字典(就地), 让旧代码的 env['ssh_host'] 继续可用。

    合并的键:
      ssh_host / ssh_username / ssh_password  —— SSH 类用例
      host.camera                            —— 接口类用例的测试目标(数据文件里的 {{$.host.camera}})
      device / device_key / device_model     —— 结构化访问

    清单读不到时原样返回 —— 此时仍沿用环境配置里可能存在的旧值。
    """
    dev = active_device()
    if not dev:
        return env
    ip = dev.get("ip")
    if ip:
        env["ssh_host"] = ip
        # 关键: 70 个数据文件用 {{$.host.camera}} 决定"测哪台设备"。
        # 它和 ssh_host 指向同一台机器, 必须一起跟着清单走, 否则会
        # "SSH 连 A、HTTP 打 B" —— 主题里的 22 条用例失败就是这么来的。
        hosts = env.get("host")
        if isinstance(hosts, dict):
            hosts["camera"] = f"http://{ip}"
    if dev.get("ssh_user"):
        env["ssh_username"] = dev["ssh_user"]
    if dev.get("ssh_pass"):
        env["ssh_password"] = dev["ssh_pass"]
    if dev.get("token"):
        env["device_token"] = dev["token"]
    env["device"] = {k: v for k, v in dev.items() if k != "ssh_pass"}
    env["device_key"] = dev.get("key", "")
    env["device_model"] = dev.get("model", "")
    return env


def describe() -> str:
    inv = load_inventory()
    devices = inv.get("devices") or {}
    if not devices:
        return "设备清单为空(检查 config/devices.yaml)"
    active = inv.get("active")
    lines = [f"设备清单 {DEVICES_FILE.relative_to(PROJECT_ROOT)}  (active = {active})", ""]
    for key, d in devices.items():
        mark = "  <-- 当前" if key == active else ("  (!) active 未指向任何设备" if not active else "")
        lines.append(f"  {key:<22} {d.get('model') or '?':<4} {d.get('ip') or '?':<16} "
                     f"{d.get('name') or ''}{mark}")
    if active not in devices:
        lines.append(f"  ⚠️ active={active!r} 不在清单里, 请修正")
    return "\n".join(lines)
