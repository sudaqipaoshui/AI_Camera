# -*- coding: utf-8 -*-
"""发布门禁: 按 gate.yaml 的阈值判定"这一批能不能放行"。

刻意区分三态:
  PASS  —— 所有 block 项都满足
  FAIL  —— 有 block 项不满足
  NO_DATA —— 连必需的批次都没有, 谈不上放行

门禁只读结果库, 不碰设备、不跑用例, 因此可以随时执行, 也适合放在 CI 的最后一步。
"""
from __future__ import annotations

import dataclasses
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import envloader  # noqa: E402

GATE_FILE = PROJECT_ROOT / "gate.yaml"

EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_NO_DATA = 3


@dataclasses.dataclass
class Finding:
    scope: str          # target 名 或 "global"
    rule: str
    severity: str       # block / warn
    ok: bool
    detail: str
    actual: object = None
    expected: object = None

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def load_gate(path: Path | None = None) -> dict:
    p = path or GATE_FILE
    if not p.exists():
        return {"defaults": {}, "targets": {}, "metrics": [], "required_targets": []}
    return envloader.load_yaml(str(p)) or {}


def _thresholds(cfg: dict, target: str) -> dict:
    merged = dict(cfg.get("defaults") or {})
    merged.update((cfg.get("targets") or {}).get(target) or {})
    return merged


def _age_hours(started_at) -> float | None:
    if not started_at:
        return None
    if isinstance(started_at, str):
        try:
            started_at = datetime.fromisoformat(started_at[:19].replace("T", " "))
        except ValueError:
            return None
    if not isinstance(started_at, datetime):
        return None
    return (datetime.now() - started_at).total_seconds() / 3600


def evaluate(tag: str | None = None, log: bool = True) -> tuple[dict, int, str]:
    """返回 (判定详情, 退出码, 可读文本)。"""
    from aicamlab import recorder

    cfg = load_gate()
    findings: list[Finding] = []
    runs: dict[str, dict] = {}
    metrics: dict[str, dict[str, float]] = {}

    def note(msg: str) -> None:
        if log:
            print(msg)

    # ---- 1. 必需批次是否存在且新鲜 ----
    for target in cfg.get("required_targets") or []:
        run = recorder.latest_run(target=target)
        if not run:
            findings.append(Finding(target, "required", "block", False,
                                    f"没有 {target} 的批次记录", None, "至少一条"))
            continue
        if tag and run.get("tag") != tag:
            findings.append(Finding(target, "required", "block", False,
                                    f"{target} 最新批次标签是 {run.get('tag')!r}, 与要求的 {tag!r} 不符",
                                    run.get("tag"), tag))
            continue
        runs[target] = run

    if not runs:
        detail = {"verdict": "NO_DATA", "tag": tag, "findings": [f.to_dict() for f in findings]}
        text = ["", "门禁判定: NO_DATA —— 结果库里没有任何可用的批次记录",
                "", "  先跑一次:  python run.py api", ""]
        text += [f"  缺: {f.detail}" for f in findings]
        return detail, EXIT_NO_DATA, "\n".join(text)

    # ---- 2. 用例层面阈值 ----
    for target, run in runs.items():
        th = _thresholds(cfg, target)
        age = _age_hours(run.get("started_at"))
        if th.get("max_age_hours") is not None and age is not None:
            limit = float(th["max_age_hours"])
            findings.append(Finding(
                target, "批次新鲜度", "block", age <= limit,
                f"最新批次 {run['run_id']} 距今 {age:.1f} 小时(上限 {limit:.0f})",
                round(age, 1), limit))

        total = int(run.get("total") or 0)
        failed = int(run.get("failed") or 0) + int(run.get("error") or 0)
        skipped = int(run.get("skipped") or 0)

        if th.get("max_skipped_pct") is not None and total:
            pct = skipped / total * 100
            limit = float(th["max_skipped_pct"])
            findings.append(Finding(target, "跳过占比", "block", pct <= limit,
                                    f"{pct:.1f}%（{skipped}/{total},上限 {limit:.0f}%）",
                                    round(pct, 1), limit))

        # ---- 按失败类别判定(只阻塞 block_classes 里的类别) ----
        # 这是"只阻塞产品缺陷"口径的落地: env/case 类失败只 warn, 不卡流水线。
        if failed:
            from aicamlab.failure import CLASS_ENV, CLASS_CASE, CLASS_PRODUCT, CLASS_UNKNOWN
            cases = recorder.fetch_cases(run["run_id"], limit=10000)
            block_classes = set(th.get("block_classes") or [CLASS_PRODUCT])
            from aicamlab.failure import classify
            cls_counts: dict[str, int] = {}
            for c in cases:
                if (c.get("status") or "") in ("failed", "error"):
                    cls = c.get("failure_class") or classify(c.get("message"), c.get("nodeid", ""))
                    cls_counts[cls] = cls_counts.get(cls, 0) + 1
            # 每个类别各出一条 finding
            all_classes = (CLASS_ENV, CLASS_CASE, CLASS_PRODUCT, CLASS_UNKNOWN)
            for cls in all_classes:
                n = cls_counts.get(cls, 0)
                if n == 0:
                    continue
                is_blocked = cls in block_classes
                sev = "block" if is_blocked else "warn"
                label = {"env": "环境类失败", "case": "用例类失败",
                         "product": "产品缺陷", "unknown": "未归类失败"}[cls]
                findings.append(Finding(
                    target, label, sev, n == 0 or not is_blocked,
                    f"{n} 条{label}" + ("" if is_blocked else "（仅提示，不阻塞）"),
                    n, "0" if is_blocked else "不设限"))

        # 硬闸: 若配置里显式设了 max_failed(总失败数上限), 仍作为 block 项
        if th.get("max_failed") is not None:
            limit = int(th["max_failed"])
            findings.append(Finding(target, "失败用例数", "block", failed <= limit,
                                    f"{failed} 失败/错误(上限 {limit})", failed, limit))

        if run.get("verdict") != "PASS":
            # 批次本身已判失败。⚠️ 若失败全是 env/case 类, 不应因"结论 FAIL"就直接 block。
            # 这里改为 warn, 真正的 block 交给上面的分类判定。
            findings.append(Finding(target, "批次结论", "warn", False,
                                    f"批次 {run['run_id']} 结论为 {run.get('verdict')}",
                                    run.get("verdict"), "PASS"))

    # ---- 3. 指标阈值 ----
    for spec in cfg.get("metrics") or []:
        target = spec.get("target") or ""
        spec_tag = spec.get("tag")
        # ⚠️ 必须能按 tag 缩范围: 同一个 target(replay) 下混着多个运动项目,
        #    不区分就会拿开合跳的 area6 去判跳绳的 area6。见 gate.yaml 注释。
        if spec_tag:
            run = next((r for r in recorder.fetch_runs(target=target, tag=spec_tag, limit=1)), None)
        else:
            run = runs.get(target) or recorder.latest_run(target=target)
        if not run:
            findings.append(Finding(target, f"指标 {spec.get('name')}", "warn", False,
                                    f"没有 {target}"
                                    f"{'/' + spec_tag if spec_tag else ''} 的批次, 指标无法判定"))
            continue
        scope = target + (f"/{spec_tag}" if spec_tag else "")
        rows = recorder.fetch_metrics(run_ids=[run["run_id"]], name=spec.get("name"))
        subject = spec.get("subject")
        hit = None
        for r in rows:
            if (r.get("subject") or "") == (subject or ""):
                hit = r
                break
        label = f"指标 {spec.get('name')}" + (f"[{subject}]" if subject else "")
        if hit is None:
            findings.append(Finding(scope, label, spec.get("severity", "warn"), False,
                                    f"批次 {run['run_id']} 里没有这个指标"))
            continue
        value = float(hit["value"])
        metrics.setdefault(scope, {})[f"{spec.get('name')}[{subject}]"] = value
        sev = spec.get("severity", "warn")
        note = f"   [{spec['note']}]" if spec.get("note") else ""
        if spec.get("min") is not None:
            lo = float(spec["min"])
            findings.append(Finding(scope, label, sev, value >= lo,
                                    f"{value:g}{spec.get('unit') or ''}（下限 {lo:g}）{note}",
                                    value, f">={lo}"))
        elif spec.get("max") is not None:
            hi = float(spec["max"])
            findings.append(Finding(scope, label, sev, value <= hi,
                                    f"{value:g}{spec.get('unit') or ''}（上限 {hi:g}）{note}",
                                    value, f"<={hi}"))

    blocked = [f for f in findings if f.severity == "block" and not f.ok]
    verdict = "PASS" if not blocked else "FAIL"
    detail = {
        "verdict": verdict,
        "tag": tag,
        "runs": {t: r.get("run_id") for t, r in runs.items()},
        "metrics": metrics,
        "findings": [f.to_dict() for f in findings],
        "blocked": [f.rule for f in blocked],
    }

    lines = ["", "─" * 62, f"  门禁判定  {verdict}" + (f"   (tag={tag})" if tag else "")]
    for t, r in runs.items():
        lines.append(f"  {t:<12} {r['run_id']}  {r.get('verdict')}  "
                     f"{r.get('passed')}/{r.get('total')}  {r.get('firmware') or '-'}")
    lines.append("─" * 62)
    for f in findings:
        mark = "OK  " if f.ok else ("BLOCK" if f.severity == "block" else "warn ")
        lines.append(f"  {mark:<5} {f.scope:<10} {f.rule:<16} {f.detail}")
    if blocked:
        lines += ["", f"  ✗ {len(blocked)} 项被卡住, 不放行"]
    else:
        lines += ["", "  ✓ 全部 block 项通过"]
    lines.append("")

    return detail, (EXIT_OK if verdict == "PASS" else EXIT_BLOCKED), "\n".join(lines)


if __name__ == "__main__":
    as_json = "--json" in sys.argv
    d, code, text = evaluate(log=not as_json)
    print(json.dumps(d, ensure_ascii=False, indent=2, default=str) if as_json else text)
    sys.exit(code)
