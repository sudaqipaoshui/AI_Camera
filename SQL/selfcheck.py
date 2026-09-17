# -*- coding: utf-8 -*-
"""测试库自检: 验证「连接 → 造数 → 查询校验 → 清数」整条链路可用。

这是一个**只读 + 自带清理**的自检, 跑完把造的数据全删掉, 不留痕迹。
可以在每次改动数据库相关代码后执行, 也适合放进 CI 做前置检查。

用法:
    E:\\TestTools\\venv\\Scripts\\python.exe SQL\\selfcheck.py
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for path in (str(PROJECT_ROOT), str(PROJECT_ROOT / "API")):
    if path not in sys.path:
        sys.path.insert(0, path)

from pytest_helper.db import DbUnavailable, make_client  # noqa: E402

PASS, FAIL = "[PASS]", "[FAIL]"
_results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    _results.append((name, ok, detail))
    print(f"{PASS if ok else FAIL}  {name}{('  -> ' + detail) if detail else ''}")
    return ok


def main() -> int:
    client = make_client()

    print("=" * 68)
    print("步骤 1/6  连接测试库")
    print("=" * 68)
    try:
        client.connect()
    except DbUnavailable as exc:
        check("连接", False, str(exc))
        return 1
    cfg = client.config
    check("连接", True, f"{cfg['user']}@{cfg['host']}:{cfg['port']}/{cfg['database']}")

    print("\n" + "=" * 68)
    print("步骤 2/6  表结构就位")
    print("=" * 68)
    rows = client.query(
        "SELECT TABLE_NAME, TABLE_COMMENT FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME",
        (cfg["database"],),
    )
    tables = []
    for row in rows:
        name, comment = (list(row.values()) if isinstance(row, dict) else row)
        tables.append(name)
        print(f"       - {name:<14} {comment}")
    check("3 张表齐全", set(tables) >= {"project", "device", "test_result"}, str(tables))

    print("\n" + "=" * 68)
    print("步骤 3/6  先清掉历史造数, 保证起点干净")
    print("=" * 68)
    before = client.count_fixture()
    print(f"       清理前待清理行数: {before}")
    deleted = client.cleanup_fixture()
    print(f"       已删除: {deleted}")
    check("清理后无残留", all(v == 0 for v in client.count_fixture().values()))

    print("\n" + "=" * 68)
    print("步骤 4/6  造数(全部带 is_fixture=1 标记)")
    print("=" * 68)
    n_proj = client.make_fixture("project", [
        {"item_id": 9001, "item_name": "自检-跳绳", "score_unit": "个", "score_field": "count"},
        {"item_id": 9002, "item_name": "自检-跳远", "score_unit": "米", "score_field": "distance"},
    ])
    n_dev = client.make_fixture("device", [
        {"device_name": "自检设备A", "device_serial": "SELFCHECK-A", "model": "X5", "ip": "127.0.0.1"},
        {"device_name": "自检设备B", "device_serial": "SELFCHECK-B", "model": "X5", "ip": "127.0.0.2"},
    ])
    print(f"       project 写入 {n_proj} 行, device 写入 {n_dev} 行")
    pid = client.query_scalar("SELECT id FROM project WHERE item_id = 9001")
    did = client.query_scalar("SELECT id FROM device WHERE device_serial = 'SELFCHECK-A'")
    n_res = client.make_fixture("test_result", [
        {"device_id": did, "project_id": pid, "tester_no": "T001", "tester_name": "自检员1",
         "round_no": 1, "score": 176.0, "occurred_at": "2026-09-17 09:00:00", "source": "selfcheck"},
        {"device_id": did, "project_id": pid, "tester_no": "T001", "tester_name": "自检员1",
         "round_no": 2, "score": 184.0, "occurred_at": "2026-09-17 09:05:00", "source": "selfcheck"},
        {"device_id": did, "project_id": pid, "tester_no": "T002", "tester_name": "自检员2",
         "round_no": 1, "score": 181.0, "occurred_at": "2026-09-17 09:10:00", "source": "selfcheck"},
    ])
    print(f"       test_result 写入 {n_res} 行")
    check("造数成功", (n_proj, n_dev, n_res) == (2, 2, 3))

    print("\n" + "=" * 68)
    print("步骤 5/6  查询校验(模拟真实用例的查库断言)")
    print("=" * 68)
    top = client.query_one(
        "SELECT tester_no, MAX(score) AS best FROM test_result "
        "WHERE is_fixture = 1 GROUP BY tester_no ORDER BY best DESC LIMIT 1"
    )
    print(f"       最高分查询: {top}")
    best = (top.get("best") if isinstance(top, dict) else top[1]) if top else None
    check("最高分 = 184", str(best).startswith("184"), str(best))

    total = client.query_scalar("SELECT COUNT(*) FROM test_result WHERE is_fixture = 1")
    check("成绩行数 = 3", int(total) == 3, str(total))

    joined = client.query_one(
        "SELECT r.tester_no, r.score, d.device_name, p.item_name "
        "FROM test_result r JOIN device d ON d.id = r.device_id "
        "JOIN project p ON p.id = r.project_id WHERE r.is_fixture = 1 ORDER BY r.id LIMIT 1"
    )
    print(f"       三表联查: {joined}")
    check("三表联查可用", joined is not None)

    print("\n" + "=" * 68)
    print("步骤 6/6  清数, 验证只清 is_fixture=1")
    print("=" * 68)
    # 先插一行"人工数据"(is_fixture=0), 验证清数不会误删
    client.execute(
        "INSERT INTO project (item_id, item_name, score_unit, score_field, is_fixture) "
        "VALUES (9003, '人工录入-不该被删', '个', 'count', 0)"
    )
    deleted = client.cleanup_fixture()
    print(f"       已删除: {deleted}")
    manual = client.query_scalar("SELECT COUNT(*) FROM project WHERE item_id = 9003")
    check("人工数据(is_fixture=0)被保留", int(manual) == 1, f"剩 {manual} 行(应为 1)")
    left = client.count_fixture()
    check("造数数据已清净", all(v == 0 for v in left.values()), str(left))

    # 收尾: 把验证用的人工数据也删掉
    client.execute("DELETE FROM project WHERE item_id = 9003")
    check("收尾清理完成", client.query_scalar("SELECT COUNT(*) FROM project WHERE item_id = 9003") == 0)

    client.close()

    passed = sum(1 for _, ok, _ in _results if ok)
    total_n = len(_results)
    print("\n" + "=" * 68)
    print(f"自检结果: {passed}/{total_n} 通过")
    if passed != total_n:
        print("未通过项:")
        for name, ok, detail in _results:
            if not ok:
                print(f"   {FAIL} {name}  {detail}")
    print("=" * 68)
    return 0 if passed == total_n else 1


if __name__ == "__main__":
    sys.exit(main())
