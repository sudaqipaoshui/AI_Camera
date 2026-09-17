import copy
import inspect
import json
import os
import sys
import time
import pytest
import yaml
import logging

# allure 仅用于报告装饰/附加, 属"尽力而为"能力。CI 云 runner 的纯函数回归不装 allure-pytest,
# 因此这里做成可选导入: 缺失时置 None, 下方使用处已有 try/except 兜底。
try:
    import allure
except ImportError:  # pragma: no cover - 仅在不装 allure 的环境触发
    allure = None
from pathlib import Path
from hashlib import md5

# 把项目根目录(envloader.py 所在)加入 sys.path, 保证从任意工作目录启动都能导入。
_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
import envloader  # noqa: E402  统一凭据加载器, 负责展开配置里的 ${VAR}
# from pytest_helper.websocket_client import ShortWebSocetClient
from pytest_helper.http_client import DateEncoder, TSPRequest
from pytest_helper.common import render, merge
# 已移除 _pytest.assertion.util.assertrepr_compare 的导入: pytest 9 改变了它的签名,
# 不再由本插件直接调用, 差异渲染交给 pytest 自身处理。
from pytest_helper.server import get_account_token, get_maintenancece_token

pre_input_list, post_input_list = [], []


def pytest_addoption(parser):
    """
    在session开始之前，添加命令行参数，参数会保存在config对象的option属性中。
    """
    parser.addoption("--env",
                     action="store",
                     dest="environment",
                     default="test",
                     help="environment: test or stg")
    parser.addoption("--runslow", action="store_true",
                     help="run slow tests")
    parser.addoption("--runmanual", action="store_true",
                     help="run manual tests")
    parser.addoption("--config",
                     action="store",
                     dest="configuration",
                     default="config.yaml",
                     help="configuration of testing project")
    parser.addoption("--proxy", action="store_true",
                     help="need proxy or not")

# ---------------------------------------------------------------------------
# env 的返回值会被 pytest 打进断言失败输出(assertion rewriting 会把局部变量
# 连同 repr 一起打印)。而本项目 env 里含展开后的明文凭据, 于是**只要有一条用例
# 断言失败**, 口令就会进入: ① 控制台 ② allure 报告 ③ pytest 日志 ④ 结果库。
# 让 env 返回一个 repr 已脱敏的 dict 子类, 从源头把这条路堵死。
# 行为与 dict 完全一致(dict 子类), 用例代码无需改动。
# ---------------------------------------------------------------------------
try:
    from aicamlab.redact import scrub as _scrub
except Exception:  # 只把 API 目录单独拿出来跑时可能取不到, 退化为内置最小实现
    import re as _re

    _SECRET_KEY_RE = _re.compile(
        r"([\"']?(?:password|passwd|token|x_token|authorization|secret|licence|"
        r"ssh_pass|encodePassword)[\"']?\s*[:=]\s*)([\"']?)([^\"'\s,})]{2,})", _re.I)

    def _scrub(text):
        return _SECRET_KEY_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}***", str(text))


class SafeEnv(dict):
    """与 dict 行为一致, 只是 repr / str 会把凭据遮掉。"""

    __slots__ = ()

    def __repr__(self):
        return _scrub(dict.__repr__(self))

    __str__ = __repr__


@pytest.fixture(scope="session")
def env(request, pytestconfig):
    """
    load environment condig file, return {} if path is invalid.
    """
    # pytestconfig.cache = {}  # 注释掉这行，解决AttributeError: 'dict' object has no attribute 'set'问题
    # 计算项目根目录：从 pytest rootdir 向上查找（通常是 API 目录，需要向上一级到项目根目录）
    # 或者在 conftest.py 中已经定义了 PROJECT_ROOT，这里尝试使用它
    rootdir = getattr(request.config, 'rootdir', None)
    if rootdir:
        rootdir_path = Path(str(rootdir))
        # 如果 rootdir 是 API 目录，向上查找项目根目录
        # 检查是否存在上一级的 config 目录
        project_root = rootdir_path.parent if (rootdir_path.parent / "config").exists() else rootdir_path
    else:
        # fallback: 使用当前文件位置向上查找
        project_root = Path(__file__).resolve().parents[2]
    
    config_path = os.path.join(str(project_root),
                               "config",
                               request.config.getoption("environment"),
                               request.config.getoption("configuration")
                               )
    # 配置里的凭据以 ${VAR} 占位符书写, 由 envloader 从 .env / 真实环境变量展开。
    # 缺变量会直接抛错, 这是刻意设计: 不允许静默回落到硬编码默认口令。
    env_config = envloader.load_yaml(config_path)
    env_config.update({
        'environment': request.config.getoption("environment"),
        'rootdir': request.config.rootdir.strpath,
        'config_path': config_path,
        'proxy': request.config.getoption("proxy"),
        # 'pytestconfig': pytestconfig.cache
    })
    # 设备身份(ip / ssh 账号)从 config/devices.yaml 注入 —— 单一来源, 见该文件顶部说明。
    # 这么做的原因: 设备 IP 曾同时写在 camera.yaml 与 items.json 里且不一致,
    # 其中 camera.yaml 指着早已离线的旧机器, 让 22 条真的连设备的用例必然失败。
    # 注入后 env['ssh_host'] 等键的用法不变, 只是值不再由本文件决定。
    try:
        from aicamlab.inventory import apply_to_env
        env_config = apply_to_env(env_config)
    except Exception:
        pass
    return SafeEnv(env_config)


@pytest.fixture(scope='session', autouse=True)
def refresh_token(env):
    # 刷新token
    get_account_token(env)
    # 刷新maintenance token
    get_maintenancece_token(env)


def pytest_assertion_pass(item, lineno, orig, expl):
    """
    Hook called whenever an assertion passes.
    需要显示声明enable_assertion_pass_hook=true
    """
    pass


def pytest_assertrepr_compare(config, op, left, right):
    """
    断言失败时执行: 记录日志, 并把左右值附加到 Allure 报告。

    这里刻意不自行渲染差异说明。pytest 9 起 _pytest.assertion.util.assertrepr_compare
    的签名已改为 (op, left, right, *, verbose, highlighter, assertion_text_diff_style),
    且返回生成器; 老代码按 (config, op, left, right) 调用会抛 TypeError,
    结果每一次断言失败都变成 TypeError, 真实差异被完全掩盖。
    返回 None 表示"不提供自定义说明", 由 pytest 自身逻辑输出标准差异。
    """
    try:
        left_name, right_name = inspect.stack()[7].code_context[0].lstrip().lstrip(
            'assert').rstrip('\n').split(op)
    except Exception:
        left_name, right_name = left, right
    logging.info("断言失败: %s %s %s", left_name, op, right_name)
    logging.debug("%s is %s", left_name, left)
    logging.debug("%s is %s", right_name, right)
    try:
        if allure is not None:
            with allure.step("断言{}{}{}".format(left_name, op, right_name)):
                allure.attach(json.dumps(left, indent=2,
                                         ensure_ascii=False, cls=DateEncoder), str(left_name))
                allure.attach(json.dumps(right, indent=2,
                                         ensure_ascii=False, cls=DateEncoder), str(right_name))
    except Exception:
        logging.debug("附加断言信息到 allure 失败, 已忽略")
    return None


def pytest_runtest_setup(item):
    if 'slow' in item.keywords and not item.config.getvalue("runslow"):
        pytest.skip("need --runslow option to run")
    if 'manual' in item.keywords and not item.config.getvalue("runmanual"):
        pytest.skip("need --runmanual option to run")


def pytest_configure(config):
    """
    解析命令行参数，初始化插件、conftest.py、配置和读取pytest.ini配置文件等，创建session。
    :param config:
    """
    config.addinivalue_line(
        "markers", "cool_marker: this one is for cool tests.")
    config.addinivalue_line(
        "markers", "mark_with(arg, arg2): this marker takes arguments."
    )


@pytest.fixture(scope='session', autouse=False)
def faker():
    """
    知名的构造测试数据的faker
    """
    from faker import Factory
    return Factory.create('zh_CN')


def pytest_generate_tests(metafunc):
    """
    参数化测试函数
    :param metafunc:
    :return:
    """
    ids, inputs, expectation, connect, data = [], [], [], [], []
    markers = metafunc.definition.own_markers
    for marker in markers:
        if marker.name == 'datafile':
            test_data_path = os.path.join(metafunc.config.rootdir, marker.args[0]) if marker.args \
                else str(metafunc.definition.fspath).replace('tests', 'data').replace('.py', '.yaml')
            with open(test_data_path, encoding='utf-8') as f:
                ext = os.path.splitext(test_data_path)[-1]
                if ext in ['.yaml', '.yml']:
                    test_data = yaml.safe_load(f)
                elif ext == '.json':
                    test_data = json.load(f)
                else:
                    raise TypeError(
                        'datafile must be yaml or json，root must be tests')
            common_inputs = test_data.get('common_inputs', 0)
            if "pre_inputs" in metafunc.fixturenames:
                dt = test_data['pre'][0]
                pre_input_list.append(dt['pre_input'])
            if "post_inputs" in metafunc.fixturenames:
                dt = test_data['post'][0]
                post_input_list.append(dt['post_input'])
            if "inputs" in metafunc.fixturenames and "expectation" in metafunc.fixturenames:
                single_group_flag = True if isinstance(test_data['tests'], dict) and test_data['tests'].get(
                    'group', False) else False  # group flag
                cases = test_data['tests']['group'] if single_group_flag else test_data['tests']
                for case in cases:
                    if 'group' in case:
                        sub_inputs, sub_expectation, sub_ids = [], [], []
                        for item in case['group']:
                            sub_ids.append(f'{item["case"]}')
                            sub_inputs.append(
                                merge(item['input'], common_inputs) if common_inputs else item['input'])
                            sub_expectation.append(item['expectation'])  # 替换测试数据
                        inputs.append(sub_inputs)
                        expectation.append(sub_expectation)
                        ids.append(str(sub_ids))
                    else:
                        ids.append(case['case'])
                        inputs.append(
                            merge(case['input'], common_inputs) if common_inputs else case['input'])
                        expectation.append(case['expectation'])
                # 注意: 必须显式 list()。pytest 10 起不再接受非集合的可迭代对象,
                # 直接传 zip() 会触发 PytestRemovedIn10Warning 并在未来报错。
                argvalues = ([(inputs, expectation, ids)] if single_group_flag
                             else list(zip(inputs, expectation, ids)))
                metafunc.parametrize("inputs, expectation, case", argvalues,
                                     ids=['组合场景'] if single_group_flag else ids,
                                     scope="function")
            if "connect" in metafunc.fixturenames and "data" in metafunc.fixturenames and "expectation" in metafunc.fixturenames:
                for d in test_data['tests']:
                    ids.append(d['case'])
                    connect.append(
                        merge(d['connect'], common_inputs) if common_inputs else d['connect'])
                    data.append(merge(d['data'], common_inputs)
                                if common_inputs else d['data'])
                    expectation.append(d['expectation'])


def pytest_report_teststatus(report, config):
    """
    获取当前测试函数的测试结果，并做相应处理
    test outcome, always one of "passed", "failed", "skipped".
    """
    if report.outcome == 'passed':
        pass
    elif report.outcome == "failed":
        pass
    else:
        pass


@pytest.fixture(scope="session", autouse=False)
def requests():
    """
    用于发送http请求，如果有代理通过--proxies
    """
    return TSPRequest()


@pytest.fixture(scope="function")
def http():
    """
    Backward-compatible alias for TSPRequest.request expected by generated tests.
    Provides a callable with signature: request(env, inputs) -> response
    """
    class _HttpWrapper:
        @staticmethod
        def request(env, inputs):
            return TSPRequest.request(env, inputs)

    return _HttpWrapper()


@pytest.fixture(scope="function", autouse=False)
def ws(env, connect):
    """
    用于发送websocket请求
    """
    return ShortWebSocetClient(env, connect)


@pytest.fixture(scope="class", autouse=False)
def pre_inputs(env):
    pre_input = render(env, copy.deepcopy(pre_input_list.pop(0)))
    return pre_input


@pytest.fixture(scope="class", autouse=False)
def post_inputs(env):
    post_input = render(env, copy.deepcopy(post_input_list.pop(0)))
    return post_input


@pytest.fixture(scope='function', autouse=True)
def render_inputs(request):
    """
    替换inputs数据

    惰性获取 env: 只有用例真正声明了 inputs 参数才需要 env 与渲染。
    否则(如纯函数回归)不碰 env —— 避免 autouse 让 env/配置/凭据成为
    所有测试的隐式依赖, 拖累 CI 云 runner 上无凭据的单元测试。
    """
    if 'inputs' not in request.fixturenames:
        return
    env = request.getfixturevalue('env')
    inputs = request.getfixturevalue('inputs')
    render_result = render(env, inputs)
    if isinstance(inputs, dict):
        inputs.update(render_result)
    elif isinstance(inputs, list):
        del inputs[:]
        inputs += render_result


@pytest.fixture(scope='function', autouse=True)
def render_expectation(request):
    """
    替换expectation数据

    同上: 惰性获取 env, 纯函数测试不触发配置加载。
    """
    if 'expectation' not in request.fixturenames:
        return
    env = request.getfixturevalue('env')
    expectation = request.getfixturevalue('expectation')
    render_result = render(env, expectation)
    if isinstance(expectation, dict):
        expectation.update(render_result)
    elif isinstance(expectation, list):
        del expectation[:]
        expectation += render_result


@pytest.fixture(scope='session')
def get_token(env):
    """
    get odin token
    """
    try:
        host = env['host']['vom_order']
        schema = env['vom']['schema']
        print('type of schema ', type(schema))
        url = host + '/api/v1/createtoken'
        app_secret = schema['app_secret']
        current_stamp = str(int(time.time()))
        payload = {
            'timestamp': current_stamp,
        }
        payload.update(schema)
        gen_list = [k + '=' + v for k, v in payload.items()]
        gen_list.sort()
        query = '&'.join(gen_list) + app_secret
        sign_str = md5(bytes(query, encoding='utf-8')).hexdigest()
        logging.info(query + ': ' + sign_str)
        payload['digest'] = sign_str
        res = requests.get(url, params=payload).json()
        logging.info(res)
        print('本次token是：', res['resultData'])
        return res['resultData']
    except KeyError as e:
        logging.warning('not need  get odin token!')


@pytest.fixture(scope='session')
def get_vomadmin_token(env):
    """
    get vom admin _sid
    """
    try:

        host = env['host']['vom_admin'] + '/app/loginForAdmAndPw'
        vomaccount = env['vom']['vomaccount']
        response = requests.post(url=host, data=vomaccount)
        return response.json()['resultData']['_sid']
    except KeyError as e:
        logging.warning('not need  get vom admin _sid!')


@pytest.fixture(scope='function', autouse=False)
def make_muse_sign(env, inputs):
    s = f'{env["secret"][inputs["params"]["appid"]]}0appid={inputs["params"]["appid"]}1deviceid={inputs["params"]["deviceid"]}2os={inputs["params"]["os"]}3packagename={inputs["params"]["packagename"]}{env["secret"][inputs["params"]["appid"]]}'
    sign = md5(s.encode(encoding="utf-8")).hexdigest()
    inputs['params']['sign'] = sign


@pytest.hookimpl(optionalhook=True)
def pytest_json_modifyreport(json_report):
    if hasattr(pytest, "path_coverage"):
        covered_uri_path=pytest.path_coverage
        json_report["covered_uri_path"]=list(set(covered_uri_path))
    else:
        pass