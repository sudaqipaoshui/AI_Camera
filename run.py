#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AICameraTestLab 统一入口。

    python run.py <目标> [选项] [-- 透传给底层工具的参数]

设计目标是"CI 友好": 无交互、退出码固定、``--json`` 出机器可读摘要。
以后接 GitLab CI / GitHub Actions / Jenkins, 只需让流水线调用同一个命令。

退出码:  0=通过  1=用例失败  2=用法错误  3=前置条件不满足  4=危险目标未放行

例:
    python run.py list
    python run.py smoke
    python run.py api
    python run.py api -- -k ping -x
    python run.py replay -- --item rope --video E:/TestTools/rope8_4k.mp4
    python run.py gate --json
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aicamlab import runner  # noqa: E402


def split_passthrough(argv: list[str]) -> tuple[list[str], list[str]]:
    """把 '--' 之后的参数原样留给底层工具(pytest / run_test.py / 脚本)。"""
    if "--" in argv:
        i = argv.index("--")
        return argv[:i], argv[i + 1:]
    return argv, []


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run.py", add_help=True, formatter_class=argparse.RawDescriptionHelpFormatter,
        description="AICameraTestLab 统一入口。跑 `python run.py list` 看全部目标。",
    )
    p.add_argument("target", nargs="?", help="要执行的目标名, 见 `run.py list`")
    p.add_argument("--env", default=runner.DEFAULT_ENV, help="环境名 (默认 test)")
    p.add_argument("--config", default=runner.DEFAULT_CONFIG, help="配置文件名 (默认 camera.yaml)")
    p.add_argument("--tag", default=None, help="批次标签, 写进结果库, 如固件版本")
    p.add_argument("--run-id", default=None, help="自定义批次号 (默认按时间生成)")
    p.add_argument("--json", action="store_true", help="只输出机器可读 JSON (CI 用)")
    p.add_argument("--no-record", action="store_true", help="不把结果写入测试库")
    p.add_argument("--dry-run", action="store_true", help="只打印将要执行的命令")
    p.add_argument("--yes", action="store_true", help="放行长时/危险目标(如 24h 监控)")
    p.add_argument("-q", "--quiet", action="store_true", help="pytest 加 -q")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    own, passthrough = split_passthrough(argv)
    parser = build_parser()
    args = parser.parse_args(own)

    if not args.target or args.target in ("list", "help", "-h", "--help"):
        print(runner.list_targets())
        return runner.EXIT_OK

    target = runner.TARGETS.get(args.target)
    if target is None:
        print(f"未知目标: {args.target}\n", file=sys.stderr)
        print(runner.list_targets(), file=sys.stderr)
        return runner.EXIT_USAGE

    args.passthrough = list(passthrough)
    args.record = not args.no_record
    args.run_id = args.run_id or runner.new_run_id(target.key)

    if target.long_running and not args.yes:
        print(f"目标 {target.key} 是长时任务({target.extra_note or '需显式放行'})。"
              f"\n确认要跑就加 --yes:\n    python run.py {target.key} --yes",
              file=sys.stderr)
        return runner.EXIT_NEEDS_CONFIRM

    try:
        py = runner.resolve_python()
    except runner.PreconditionError as exc:
        print(f"前置条件不满足: {exc}", file=sys.stderr)
        return runner.EXIT_PRECONDITION

    # ---- 内置目标 ----
    if target.kind == "builtin":
        if target.key == "smoke":
            checks, code = runner.smoke(args, py)
            print(runner.render_checks(checks, args.json))
            if args.json:
                print(json.dumps({"run_id": args.run_id, "target": "smoke",
                                  "exit_code": code,
                                  "verdict": "PASS" if code == runner.EXIT_OK else "FAIL",
                                  "checks": [dataclasses.asdict(c) for c in checks]},
                                 ensure_ascii=False, indent=2))
            return code

        if target.key == "gate":
            from aicamlab import gating
            verdict, code, text = gating.evaluate(tag=args.tag, log=not args.json)
            if args.json:
                print(json.dumps(verdict, ensure_ascii=False, indent=2, default=str))
            else:
                print(text)
            return code

        if target.key == "report":
            from aicamlab import reporting
            path, code, text = reporting.build_report()
            if args.json:
                print(json.dumps({"report_path": str(path) if path else "",
                                  "exit_code": code}, ensure_ascii=False, indent=2))
            else:
                print(text)
            return code

    # ---- 前置条件 ----
    problems = runner.check_needs(target, args)
    if problems:
        msg = "\n".join(f"  - {p}" for p in problems)
        print(f"目标 {target.key} 的前置条件不满足:\n{msg}", file=sys.stderr)
        return runner.EXIT_PRECONDITION

    # ---- 执行 ----
    res = runner.execute(target, args, py)
    print(runner.render_result(res, args.json))

    # ---- 落库(pytest 目标由插件做, 脚本目标在这里补) ----
    if target.kind == "script" and args.record and not args.dry_run:
        try:
            from aicamlab import recorder
            recorder.record_summary(
                {"run_id": res.run_id, "target": target.key, "tag": args.tag,
                 "started_at": res.started_at, "finished_at": res.finished_at,
                 "duration_sec": res.duration_sec, "exit_code": res.exit_code,
                 "verdict": res.verdict, "counts": res.counts, "cases": []},
                log_path=res.log_path, env=args.env)
        except Exception as exc:
            print(f"[run] 落库失败(不影响结论): {type(exc).__name__}: {exc}", file=sys.stderr)

    return res.exit_code if res.exit_code in (0, 1) else runner.EXIT_TEST_FAILED


if __name__ == "__main__":
    sys.exit(main())
