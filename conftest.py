from pathlib import Path
import sys
import pytest

# Ensure project root is on sys.path so imports like `pytest_helper` work
PROJECT_ROOT = Path(__file__).resolve().parent
project_root_str = str(PROJECT_ROOT)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

# Add API directory to path for pytest_helper
API_DIR = PROJECT_ROOT / "API"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

# Auto-load custom plugin providing fixtures and parametrization
pytest_plugins = [
    "pytest_helper.plugin",
    "pytest_helper.e2e_helper",  # E2E测试辅助插件
]

# mysql fixture: 项目内访问测试库的唯一入口 (实现见 API/pytest_helper/db.py)
#
# 历史背景: 这里原本是 `return None` 的桩。78 个 .py / 147 处用例签名挂着 mysql 参数,
# 函数体却从不使用它, 因此换成真连接不会影响任何既有用例的行为 —— 只有真正开始
# 用 mysql 的用例才会感知到这个变化。
#
# 刻意采用 session scope 且**不**自动连接: 用例数量多, 每条都建连接没必要;
# 真正要用时第一次 query/execute 会自动 connect, 用完由 pytest 统一 close。
@pytest.fixture(scope="session")
def mysql(request):
    from pytest_helper.db import make_client

    # env fixture 若可用, 优先用 yaml 里的 mysql 配置; 否则回落到本机库的 .env 变量。
    # 用 try 而不是直接依赖, 是为了让 mysql 在 env 不可用的场景下也能单独使用。
    try:
        env = request.getfixturevalue("env")
    except Exception:
        env = None

    client = make_client(env)
    yield client
    client.close()


@pytest.fixture(scope="session")
def mysql_required(mysql):
    """要用库、且库必须可用时用这个: 连不上直接 fail 并给出原因, 不静默跳过。"""
    try:
        from pytest_helper.db import DbUnavailable

        mysql.connect()
    except DbUnavailable as exc:
        pytest.fail(str(exc), pytrace=False)
    return mysql


@pytest.fixture(scope="session")
def mysql_optional(mysql):
    """要用库、但库不可用时可接受跳过时用这个。"""
    from pytest_helper.db import DbUnavailable

    try:
        mysql.connect()
    except DbUnavailable as exc:
        pytest.skip(f"测试库不可用, 跳过: {exc}")
    return mysql

# Override plugin's refresh_token to avoid network calls during local tests
@pytest.fixture(scope='session', autouse=True)
def refresh_token():
    pass

