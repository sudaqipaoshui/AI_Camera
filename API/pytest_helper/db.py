# -*- coding: utf-8 -*-
"""测试库连接与造数/清数工具 —— 项目内访问 MySQL 的唯一入口。

背景
----
在此之前, 项目里虽然有 ``config/<env>/<config>.yaml`` 的 ``mysql.uad_test`` 配置,
但**没有任何代码连接它**: 全项目 ``def mysql`` 只出现在根 ``conftest.py``, 是个
``return None`` 的桩, 78 个 .py / 147 处用例签名挂着 ``mysql`` 参数却从不使用。
本模块补上这条断链。

配置来源
--------
优先读 ``env`` fixture 里的 ``mysql.uad_test``(即 yaml 配置, 也支持以后换成正式测试库);
读不到时回落到本机库的 ``LOCAL_MYSQL_*`` 环境变量(由 ``SQL/init_db.py`` 写入 .env)。
两条路都走 ``envloader``, 仓库里不放任何明文口令。

用法
----
在用例里直接用 ``mysql`` fixture(来自 conftest, 现在返回本模块的 DbClient)::

    def test_xxx(self, env, mysql, ...):
        mysql.execute("DELETE FROM test_result WHERE is_fixture = 1")
        rows = mysql.query("SELECT score FROM test_result WHERE device_id = %s", (1,))

造数与清数分别用 ``make_fixture()`` / ``cleanup_fixture()``, 两者都强制带
``is_fixture=1`` 标记, 保证清数不会误删人工录入的数据。
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterable, Mapping, Sequence

logger = logging.getLogger(__name__)

# yaml 里 mysql 配置所在的键路径
DEFAULT_PROFILE = "uad_test"

# 允许写入的表白名单, 防止造数脚本写错表
ALLOWED_TABLES = ("project", "device", "test_result")

FIXTURE_FLAG = "is_fixture"


class DbUnavailable(RuntimeError):
    """数据库不可用(未配置 / 连不上)。用例可选择 skip。"""


class DbClient:
    """薄封装的 pymysql 客户端, 提供 query / execute / executemany。

    刻意做薄: 不引入 ORM, 不缓存连接对象跨用例复用(测试库里连接泄漏比性能更昂贵)。
    """

    def __init__(self, config: Mapping[str, Any]) -> None:
        self.config = dict(config)
        # yaml 里写了 cursorclass: pymysql.cursors.DictCursor, 这里转成真实类
        self._cursor_class = self._resolve_cursor_class(self.config.get("cursorclass"))
        self._conn = None

    # ------------------------------------------------------------------
    # 连接
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_cursor_class(value: Any):
        if not isinstance(value, str) or not value:
            return None
        module_name, _, attr = value.rpartition(".")
        if not module_name:
            return None
        try:
            import importlib

            return getattr(importlib.import_module(module_name), attr)
        except Exception:  # 配置写错不该让整个用例崩在导入期
            logger.warning("无法解析 cursorclass=%s, 使用默认游标", value)
            return None

    def connect(self) -> None:
        if self._conn is not None and getattr(self._conn, "open", False):
            return
        try:
            import pymysql
        except ImportError as exc:  # pragma: no cover
            raise DbUnavailable("未安装 pymysql, 请用项目 venv 运行") from exc

        params = {
            "host": self.config.get("host"),
            "port": int(self.config.get("port") or 3306),
            "user": self.config.get("user"),
            "password": self.config.get("password"),
            "database": self.config.get("database"),
            "charset": self.config.get("charset") or "utf8mb4",
            "autocommit": bool(self.config.get("autocommit", True)),
            "connect_timeout": int(self.config.get("connect_timeout") or 6),
        }
        if self._cursor_class is not None:
            params["cursorclass"] = self._cursor_class
        missing = [k for k in ("host", "user", "database") if not params.get(k)]
        if missing:
            raise DbUnavailable(f"数据库配置缺少字段: {', '.join(missing)}")
        try:
            self._conn = pymysql.connect(**params)
        except Exception as exc:
            raise DbUnavailable(
                f"连接数据库失败 {params['host']}:{params['port']}/{params['database']} "
                f"-> {type(exc).__name__}: {exc}"
            ) from exc

    @property
    def conn(self):
        self.connect()
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def ping(self) -> bool:
        """探活: 能跑通 SELECT 1 就算可用。不抛异常, 便于 skip 判断。"""
        try:
            return self.query_one("SELECT 1 AS ok") is not None
        except Exception as exc:
            logger.warning("数据库探活失败: %s", exc)
            return False

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def query(self, sql: str, params: Sequence[Any] | Mapping[str, Any] | None = None) -> list[Any]:
        """执行 SELECT, 返回全部行(list[dict] 或 list[tuple])。"""
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())

    def query_one(self, sql: str, params: Sequence[Any] | Mapping[str, Any] | None = None):
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def query_scalar(self, sql: str, params: Sequence[Any] | Mapping[str, Any] | None = None):
        """取第一行第一列, 适合 COUNT(*)。"""
        row = self.query_one(sql, params)
        if row is None:
            return None
        if isinstance(row, Mapping):
            return next(iter(row.values()))
        return row[0]

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------
    def execute(self, sql: str, params: Sequence[Any] | Mapping[str, Any] | None = None) -> int:
        """执行单条写语句, 返回受影响行数。"""
        with self.conn.cursor() as cur:
            affected = cur.execute(sql, params)
        self._commit()
        return affected

    def executemany(self, sql: str, rows: Iterable[Sequence[Any]]) -> int:
        rows = list(rows)
        if not rows:
            return 0
        with self.conn.cursor() as cur:
            affected = cur.executemany(sql, rows)
        self._commit()
        return affected

    def _commit(self) -> None:
        if self._conn is not None and not self.config.get("autocommit", True):
            self._conn.commit()

    @contextmanager
    def transaction(self):
        """事务上下文: 造数要么全成要么全不成, 避免半截数据。"""
        self.connect()
        self._conn.begin()
        try:
            yield self
        except Exception:
            self._conn.rollback()
            raise
        else:
            self._conn.commit()

    # ------------------------------------------------------------------
    # 造数 / 清数
    # ------------------------------------------------------------------
    def make_fixture(self, table: str, rows: Sequence[Mapping[str, Any]]) -> int:
        """批量造数, 自动打 is_fixture=1 标记。

        例: mysql.make_fixture('device', [{'device_name': 'X', 'device_serial': 'S'}])
        """
        if table not in ALLOWED_TABLES:
            raise ValueError(f"表 {table} 不在造数白名单 {ALLOWED_TABLES} 内")
        if not rows:
            return 0
        prepared = []
        for row in rows:
            item = dict(row)
            item[FIXTURE_FLAG] = 1
            prepared.append(item)
        columns = list(prepared[0].keys())
        # 所有行必须同构, 否则占位符数量会对不上
        for item in prepared:
            if list(item.keys()) != columns:
                raise ValueError("make_fixture 要求所有行的字段完全一致")
        col_sql = ", ".join(f"`{c}`" for c in columns)
        placeholders = ", ".join(["%s"] * len(columns))
        sql = f"INSERT INTO `{table}` ({col_sql}) VALUES ({placeholders})"
        affected = self.executemany(sql, [tuple(r[c] for c in columns) for r in prepared])
        logger.info("造数 %s: %d 行", table, affected)
        return affected

    def cleanup_fixture(self, tables: Sequence[str] | None = None) -> dict[str, int]:
        """清数: 只删 is_fixture=1 的行, 按依赖倒序。返回各表删除行数。"""
        targets = list(tables or ("test_result", "device", "project"))
        deleted: dict[str, int] = {}
        for table in targets:
            if table not in ALLOWED_TABLES:
                raise ValueError(f"表 {table} 不在清数白名单 {ALLOWED_TABLES} 内")
            deleted[table] = self.execute(
                f"DELETE FROM `{table}` WHERE `{FIXTURE_FLAG}` = 1"
            )
        logger.info("清数完成: %s", deleted)
        return deleted

    def count_fixture(self) -> dict[str, int]:
        """看一眼各表待清理行数, 清数前先自查用。"""
        return {
            table: self.query_scalar(
                f"SELECT COUNT(*) FROM `{table}` WHERE `{FIXTURE_FLAG}` = 1"
            )
            for table in ALLOWED_TABLES
        }


# --------------------------------------------------------------------------
# 配置解析
# --------------------------------------------------------------------------
def config_from_env(env: Mapping[str, Any] | None, profile: str = DEFAULT_PROFILE) -> dict[str, Any]:
    """从 env fixture 的 mysql 配置取连接参数。"""
    if isinstance(env, Mapping):
        mysql_section = env.get("mysql") or {}
        candidate = mysql_section.get(profile) if isinstance(mysql_section, Mapping) else None
        if isinstance(candidate, Mapping):
            cfg = dict(candidate)
            if cfg.get("host") and cfg.get("user"):
                return cfg
            logger.info("env 里的 mysql.%s 缺少 host/user, 回落到本机库配置", profile)
    return config_from_local_env()


def config_from_local_env() -> dict[str, Any]:
    """回落到本机库: 读 SQL/init_db.py 写进 .env 的 LOCAL_MYSQL_* 变量。"""
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    import envloader

    return {
        "host": envloader.get("LOCAL_MYSQL_HOST", "127.0.0.1"),
        "port": int(envloader.get("LOCAL_MYSQL_PORT", "3306")),
        "user": envloader.get("LOCAL_MYSQL_USER", ""),
        "password": envloader.get("AICAM_MYSQL_PASSWORD", ""),
        "database": envloader.get("LOCAL_MYSQL_DATABASE", "ai_camera_test"),
        "charset": "utf8mb4",
        "autocommit": True,
        # 与 yaml 配置里的口径保持一致(都返回 dict)。
        # 否则"在 pytest 里拿到 dict、在 run.py/report 里拿到 tuple", 调用方得写两套取值逻辑。
        "cursorclass": "pymysql.cursors.DictCursor",
    }


def make_client(env: Mapping[str, Any] | None = None, profile: str = DEFAULT_PROFILE) -> DbClient:
    """按配置造一个 DbClient。"""
    return DbClient(config_from_env(env, profile))
