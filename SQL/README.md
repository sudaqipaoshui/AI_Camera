# 测试数据库（ai_camera_test）

本目录是 AICameraTestLab 的**测试库唯一定义处**：建库、建表、造数、清数、自检。
2026-09-17 之前，项目里只有 `config/test/*.yaml` 的 `mysql.uad_test` 配置，
**没有任何代码连接数据库**（`conftest.py` 的 `mysql` 是个 `return None` 的桩，
147 处用例挂着这个参数却从不使用）。本目录补上了这条断链。

## 库与账号

| 项 | 值 |
|---|---|
| 实例 | 本机 MySQL `127.0.0.1:3306`（`E:\MySQL\bin\mysqld.exe`，Windows 服务名 `MySQL`） |
| 库名 | `ai_camera_test`（utf8mb4 / utf8mb4_0900_ai_ci） |
| 专用账号 | `aicam_test_rw`，仅授权 `ai_camera_test.*`，口令随机生成写入 `.env` |
| 用途 | 造数 / 清数 / 跑用例查库校验 |

> 为什么另起一个库而不是沿用原配置的 `lifestyle_test`：
> 原实例 `swc-rds-uad-master-test.dsint.com:3306` 从本机 **TCP 超时**（实测 2026-09-16），
> 是死配置。本机这个 MySQL 是已有的空库，隔离性好、无需申请白名单，适合做自动化测试库。

## 文件

| 文件 | 作用 |
|---|---|
| `01_create_db_and_user.sql` | 建库 + 建专用账号 + 授权（幂等，可重跑） |
| `02_schema.sql` | 3 张最小表：`project` / `device` / `test_result` |
| `03_seed.sql` | 造基础字典数据（项目 + 两台主用设备） |
| `99_cleanup_fixture.sql` | 清数脚本，只删 `is_fixture = 1` |
| `init_db.py` | 一键初始化：执行上面全部 SQL + 生成账号口令写 `.env` + 权限复验 |
| `selfcheck.py` | 链路自检：连接 → 造数 → 查询 → 清数，10 项断言 |

连接代码在 `API/pytest_helper/db.py`，用例里直接用 `mysql` fixture 即可。

## 首次初始化 / 换库重建

```bash
E:\TestTools\venv\Scripts\python.exe SQL\init_db.py --root-password <本机MySQL的root口令>
```

脚本是**幂等**的：会 DROP 再 CREATE 表和账号，库名不变。已有 `AICAM_MYSQL_PASSWORD`
会被复用（不想复用就加 `--reset-password` 重新生成）。**注意：重建会清空表数据。**

跑完会往项目根 `.env` 写入：`AICAM_MYSQL_PASSWORD` / `LOCAL_MYSQL_ROOT_PASSWORD` /
`LOCAL_MYSQL_HOST|PORT|DATABASE|USER`。这些键都不入库。

## 验证可用

```bash
E:\TestTools\venv\Scripts\python.exe SQL\selfcheck.py
```

期望输出 `自检结果: 10/10 通过`。

## 在用例里怎么用

```python
def test_xxx(self, env, mysql, ...):
    mysql.cleanup_fixture()                                  # 清掉上次造的数据
    mysql.make_fixture('device', [{'device_name': 'X', 'device_serial': 'S'}])
    rows = mysql.query("SELECT score FROM test_result WHERE is_fixture = 1")
```

三个 fixture（都在根 `conftest.py`）：

| fixture | 行为 |
|---|---|
| `mysql`（原有） | 返回 `DbClient`。**惰性连接**，第一次 `query/execute` 才连 |
| `mysql_required` | 连不上直接 `fail` 并说明原因 |
| `mysql_optional` | 连不上 `skip`，适合本地无库也能跑的场合 |

## 设计约定

**1. `is_fixture` 标记是清数的唯一依据**

所有造数必须走 `make_fixture()`，它会强制写入 `is_fixture = 1`；
`cleanup_fixture()` 只删 `is_fixture = 1` 的行。人工在 Navicat 里录入的、
或设备真实上报的数据保持 `is_fixture = 0`，**永远不会被清掉**。
自检里专门有一条断言验证这件事。

**2. 表结构的取舍**

| 表 | 用途 | 备注 |
|---|---|---|
| `project` | 运动项目字典 | `item_id` 对应设备 `item.json` 的 `itemId`；`score_field` 对应 ReplayLab |
| `device` | 设备台账 | `device_serial` 对应设备 `deviceUnicode`；`bound_account` 记录绑定账号（如 yangyan 这类事故） |
| `test_result` | 成绩记录 | `raw_json` 存设备原始返回，排查用 |

**刻意不建外键约束**：造数/清数要能独立操作单表、顺序自由，一致性由测试代码保证。

**3. 其它**

- 时间统一 `DATETIME`，不用 `TIMESTAMP`（避开 2038 与时区问题）。
- 造数写入用事务（`client.transaction()`），避免半截数据。
- 造数表白名单在 `API/pytest_helper/db.py` 的 `ALLOWED_TABLES`，写错表会直接报错。

## 后续待办

- [ ] 表结构目前是**最小可用设计**，拿到测试环境真实 schema 后需增补字段/表。
      旧库连不上，可用 `mysqldump --no-defaults --no-data -h <host> -u <user> -p lifestyle_test > schema.sql`
      在能连库的机器上导出，再据此对齐。
- [ ] 本机 MySQL 监听在 `0.0.0.0:3306`（局域网可达）。若无局域网访问需求，
      建议改回只听 `127.0.0.1`。
- [ ] 若后续切到正式测试库：改 `config/test/*.yaml` 的 `mysql.uad_test` 四个字段
      （`host`/`port`/`user`/`database`）+ `.env` 的口令变量即可，**代码不用动**
      —— `config_from_env()` 会优先用 yaml 里的配置。
