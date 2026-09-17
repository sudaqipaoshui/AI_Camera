# -*- coding: utf-8 -*-
"""在本机 MySQL 上初始化 AICameraTestLab 测试库。

做的事(按顺序):
  1. 连 127.0.0.1:3306 (root)
  2. 建库 ai_camera_test + 专用账号 aicam_test_rw
  3. 建 3 张最小表 DROP/CREATE (幂等)
  4. 造基础数据(项目字典 + 两台主用设备)
  5. 用新建的 aicam_test_rw 连一次, 验证权限确实可用
  6. 把生成的账号口令写进项目根 .env

口令处理: 本脚本运行时随机生成 aicam_test_rw 的口令, 只写入 .env, 不打印全文,
          也不进 git。重复执行会重新生成(账号会被重建)。

用法:
    E:\\TestTools\\venv\\Scripts\\python.exe SQL\\init_db.py
    E:\\TestTools\\venv\\Scripts\\python.exe SQL\\init_db.py --root-password xxx
"""
from __future__ import annotations

import argparse
import os
import re
import secrets
import string
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = PROJECT_ROOT / "SQL"
ENV_FILE = PROJECT_ROOT / ".env"

DB_NAME = "ai_camera_test"
DB_USER = "aicam_test_rw"
DB_HOST = "127.0.0.1"
DB_PORT = 3306

ROOT_PWD_ENV = "LOCAL_MYSQL_ROOT_PASSWORD"
APP_PWD_ENV = "AICAM_MYSQL_PASSWORD"

SQL_FILES = ["01_create_db_and_user.sql", "02_schema.sql", "03_seed.sql",
             "04_schema_runs.sql"]


def gen_password(length: int = 24) -> str:
    """生成无歧义字符集的口令(去掉引号/反斜杠等易错字符)。"""
    alphabet = string.ascii_letters + string.digits + "!@#%^*_-+="
    return "".join(secrets.choice(alphabet) for _ in range(length))


def split_statements(sql_text: str) -> list[str]:
    """按分号切 SQL 语句, 跳过纯注释行。

    够用即可: 本项目 SQL 里没有存储过程/触发器这类含分号的复合语句。
    """
    lines = []
    for raw in sql_text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("--") or not stripped:
            continue
        lines.append(raw)
    cleaned = "\n".join(lines)
    return [s.strip() for s in cleaned.split(";") if s.strip()]


def exec_script(conn, path: Path, replacements: dict[str, str] | None = None) -> None:
    """执行一个 .sql 文件, 打印每条语句的结果。"""
    text = path.read_text(encoding="utf-8")
    for key, value in (replacements or {}).items():
        text = text.replace(key, value)
    statements = split_statements(text)
    print(f"\n=== {path.name} ({len(statements)} 条语句) ===")
    with conn.cursor() as cur:
        for stmt in statements:
            cur.execute(stmt)
            head = " ".join(stmt.split())[:70]
            if cur.description:  # 有结果集的语句(SELECT/自检)
                rows = cur.fetchall()
                print(f"  SELECT {head}...")
                for row in rows[:12]:
                    print("     ", row)
            else:
                print(f"  OK  {head}...")
    conn.commit()


def write_env(updates: dict[str, str]) -> None:
    """就地更新 .env 的指定键: 已存在则替换该行, 不存在则追加。不打印值。"""
    if ENV_FILE.is_file():
        text = ENV_FILE.read_text(encoding="utf-8")
    else:
        text = ""
    for key, value in updates.items():
        pattern = re.compile(rf"^{re.escape(key)}\s*=.*$", re.MULTILINE)
        line = f"{key}={value}"
        if pattern.search(text):
            text = pattern.sub(line, text)
        else:
            text = text.rstrip("\n") + "\n" + line + "\n"
    ENV_FILE.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root-password", default=None, help="本机 MySQL root 口令")
    parser.add_argument("--reset-password", action="store_true",
                        help="即使 .env 里已有 AICAM_MYSQL_PASSWORD 也重新生成")
    args = parser.parse_args()

    try:
        import pymysql
    except ImportError:
        print("缺少 pymysql, 请用项目 venv: E:\\TestTools\\venv\\Scripts\\python.exe")
        return 1

    # ---- root 口令: 命令行 > 环境变量/已有 .env ----
    sys.path.insert(0, str(PROJECT_ROOT))
    import envloader  # noqa: E402

    root_pwd = args.root_password or envloader.get(ROOT_PWD_ENV)
    if not root_pwd:
        print(f"缺少 root 口令。请加 --root-password, 或先在 .env 写 {ROOT_PWD_ENV}=...")
        return 1

    # ---- 应用账号口令: .env 已有就复用, 避免每次重跑都改密 ----
    app_pwd = None if args.reset_password else envloader.get(APP_PWD_ENV)
    app_pwd = app_pwd or gen_password()
    print(f"目标库   : {DB_NAME}")
    print(f"专用账号 : {DB_USER}@{DB_HOST}  (口令 {'复用 .env' if envloader.get(APP_PWD_ENV) and not args.reset_password else '本次新生成'}, 长度 {len(app_pwd)})")

    # ---- 建库 / 建账号 / 建表 / 造数 ----
    try:
        conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user="root",
                               password=root_pwd, connect_timeout=6,
                               autocommit=True, charset="utf8mb4")
    except Exception as exc:
        print(f"root 连接失败: {type(exc).__name__}: {exc}")
        return 1

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT VERSION()")
            print(f"已连接 MySQL {cur.fetchone()[0]}  ({DB_HOST}:{DB_PORT})")
        for name in SQL_FILES:
            exec_script(conn, SQL_DIR / name, {"__AICAM_PASSWORD__": app_pwd})
    finally:
        conn.close()

    # ---- 用新账号复验 ----
    print("\n=== 用专用账号复验 ===")
    try:
        c2 = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER,
                             password=app_pwd, database=DB_NAME,
                             connect_timeout=6, charset="utf8mb4")
        with c2.cursor() as cur:
            cur.execute("SELECT CURRENT_USER(), DATABASE()")
            print("  登录成功 ->", cur.fetchone())
            cur.execute("SHOW TABLES")
            print("  可见表  ->", [r[0] for r in cur.fetchall()])
            cur.execute("SELECT COUNT(*) FROM project")
            print("  project 行数 ->", cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM device")
            print("  device  行数 ->", cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM test_result")
            print("  test_result 行数 ->", cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM mysql.user")  # 应因无权限而失败
            print("  意外: 竟能读 mysql.user")
        c2.close()
        print("  权限验证通过(无法越权访问 mysql 库)")
    except pymysql.err.MySQLError as exc:
        if "denied" in str(exc).lower():
            print("  权限验证通过(越权访问被拒绝)")
        else:
            print(f"  复验失败: {type(exc).__name__}: {exc}")
            return 1

    # ---- 写 .env ----
    write_env({
        APP_PWD_ENV: app_pwd,
        ROOT_PWD_ENV: root_pwd,
        "LOCAL_MYSQL_HOST": DB_HOST,
        "LOCAL_MYSQL_PORT": str(DB_PORT),
        "LOCAL_MYSQL_DATABASE": DB_NAME,
        "LOCAL_MYSQL_USER": DB_USER,
    })
    print(f"\n已写入 {ENV_FILE.name}: {APP_PWD_ENV} / {ROOT_PWD_ENV} / LOCAL_MYSQL_* (值不打印)")
    print("完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
