#!/usr/bin/env python
# -*- coding:utf-8 -*-
import difflib
import pprint
import re
import inspect
import codecs
import copy
import json
import jsonpath
from pytest_helper.errors import NonJsonForCheck
"""
result_compare方法为返回包自动全匹配方法，只需要将返回包按照json的层级结构转成yaml的格式，放到断言的yaml文件中，即可自动解析所有层级的字段并与真实返回包进行匹配
建议使用方法: assert result_compare(response, expectation["response"]["data"]) == True
yaml文件配置示例:
tests:
  - case: 1.查询上海罗锦路服务中心INDEX页面各个节点数量
    input:
      host: "{{$.host.scmsserver}}" # value是{{开头时，要用双引号括起来
      method: GET
      path: "/pad/util/queryutil/queryNodeCount"
      headers:
        Authorization: "{{$.maintenance_token.scmspadToken}}"
      params: # url参数
        dealerCode: SHHB002
      json:
    expectation:
      response:
        data:
          balanceCount: 221
          balanceInCount: 135
          balanceSettleCount: 915
          balanceUnCount: 86
真实返回包为：
{
  "balanceCount": 221,
  "balanceInCount": 135,
  "balanceSettleCount": 915,
  "balanceUnCount": 86
}
使用注意事项：
1、如果每次请求返回内容都不一样的内容不建议作为固定的断言写入expectation中，例如requestId、responseTime等
2、一定要保证yaml中个字段的层级结构与真实返回的json保持一致，否则会校验失败
3、可以登录http://www.json2yaml.com/ 对json格式的返回包进行转换，不需要的字段可以直接删除，不影响结果校验
4、如果仅需要校验字段的值不为空，不需要精确校验字段的内容，可以将断言中该字段的值设置为 NotNull，系统会自动识别并对返回包中该字段做非空校验
"""


def _require_mapping(response, where):
    """jsonpath 只能作用于 dict/list。

    拿到 bytes / None 时直接给出明确原因 —— 否则 jsonpath 会静默返回 False，
    最终报出 `check_key: xxx`，让人误以为是业务字段缺失，
    而真实原因往往是连接层故障返回了非 JSON 文本。
    """
    if isinstance(response, (dict, list)):
        return
    raise NonJsonForCheck(response, where=where)


def _brief(value, limit=200):
    """把断言里期望/实际值压成一行，避免超长对象淹没失败信息。"""
    text = repr(value)
    return text if len(text) <= limit else text[:limit] + '...'


def result_compare(response, expected):
    _require_mapping(response, 'result_compare')
    expected_list = list()
    for i in expected.keys():
        expected_list.append(i)
    response_list = list()
    for i in response.keys():
        response_list.append(i)
    len_expected = len(expected_list)
    result = True
    for i in range(0, len_expected):
        k = expected_list[i]

        if k in response_list:
            if expected[k] == "NotNull":
                if response[k] != None:
                    i += 1
                else:
                    result = False
                    print(f"失败原因: 字段{k}的值不匹配,返回包中字段{k}的值为空")
                    break
            elif isinstance(expected[k], dict):
                if result_compare(response[k], expected[k]) == False:
                    result = False
                    print(f"失败原因: 字段{k}的值不匹配")
                    break
                else:
                    i += 1
            elif isinstance(expected[k], list):
                if len(response[k]) < len(expected[k]):
                    result = False
                    print(f"失败原因: 字段{k}的值不匹配")
                    break
                elif len(expected[k]) == 0:
                    if len(response[k]) != 0:
                        result = False
                        print(f"失败原因: 字段{k}的值不匹配")
                        break
                    else:
                        pass
                else:
                    for j in range(len(expected[k])):
                        if isinstance(expected[k][j], dict):
                            result = result_compare(response[k][j], expected[k][j])
                            if result == False:
                                break
                            else:
                                pass
                        else:
                            if expected[k][j] in response[k]:
                                pass
                            else:
                                result = False
                                print(f"失败原因: 字段{k}的值不匹配")
                                break
            elif response[k] == expected[k]:
                i += 1
            else:
                result = False
                print(f"失败原因: 字段{k}的值不匹配")
                break
        else:
            print(f"失败原因: 当前返回包没有断言中的字段{k}")
            result = False
            break
    return result


def free_compare(response, expectation, all=False, sort=True):
    _require_mapping(response, 'free_compare')

    for jpath in expectation['response'].keys():
        if jpath[:6] == '_keys_':
            '''
            校验key是否存在，yaml文件中key样例：
            以_keys_开头，后边跟jsonpath
            根节点：  _keys_$
            二级及以上节点：_keys_data.member_in_group_info
            '''
            expect_checkDic = {}
            actual_checkDic = {}
            check_key_jpath = jpath[6:]
            if check_key_jpath == '$':
                check_keys = response.keys()
            else:
                check_keys = jsonpath.jsonpath(response, check_key_jpath)[0]
            expect_keys = expectation['response'][jpath]
            for expect_key in expect_keys:
                expect_checkDic[expect_key] = True
                if expect_key in check_keys:
                    actual_checkDic[expect_key] = True
                else:
                    actual_checkDic[expect_key] = False
            assert actual_checkDic == expect_checkDic, 'check_key: ' + jpath
        else:
            '''
            校验response中指定值
            '''
            actual = jsonpath.jsonpath(response, jpath)
            expect = expectation['response'][jpath]
            if all == False:
                if actual == False:
                    # jsonpath 未命中 -> 响应里根本没有这个路径。
                    # 明确区分「路径不存在」与「值不符」，否则两者都报 check_key，无法归因。
                    assert actual == expect, (
                        f'check_key: {jpath} —— jsonpath 未命中该路径(响应中不存在), '
                        f'期望 {_brief(expect)}'
                    )
                else:
                    assert actual[0] == expect, (
                        f'check_key: {jpath} —— 值不符, '
                        f'期望 {_brief(expect)}, 实际 {_brief(actual[0])}'
                    )
            else:
                if sort == True:
                    assert sorted(actual) == sorted(expect), (
                        f'check_key: {jpath} —— 集合不符, '
                        f'期望 {_brief(expect)}, 实际 {_brief(actual)}'
                    )
                else:
                    assert actual == expect, (
                        f'check_key: {jpath} —— 值不符, '
                        f'期望 {_brief(expect)}, 实际 {_brief(actual)}'
                    )
def show_json(json_obj):
    obj = copy.deepcopy(json_obj)
    _convert_obj(obj)

    json_dump_str = json.dumps(obj, indent=2, ensure_ascii=False)
    return json_dump_str


def _convert_obj(obj):
    # Convert obj to make it can be json dumped. Now we just handle the bytes value
    if isinstance(obj, dict):

        for k, v in obj.items():
            if isinstance(v, bytes):
                obj[k] = codecs.encode(obj[k], 'hex').decode('ascii').upper()
            _convert_obj(v)

    elif isinstance(obj, list):
        for item in obj:
            _convert_obj(item)

    else:
        return obj


def assert_equal(actual, expected, actual_name='actual', expected_name='expected'):
    """
    Compare two objects. Must put two object in one line.
    It support int, str, list, dict type, but not support set type
    :param actual: actual result
    :param expected: expected result
    :return:
    """
    assert type(actual) is type(expected), "TypeError: type not same!"

    if not actual_name and not expected_name:
        previous_frame = inspect.currentframe().f_back
        (filename, line_number, function_name, lines, index) = inspect.getframeinfo(previous_frame, context=2)
        if 'assert_equal' in lines[1]:
            func_with_param = lines[1].strip()
        else:
            func_with_param = ''.join([x.strip() for x in lines])



        p1 = re.compile(r"assert_equal[(](.*)[)]", re.S)
        left, right = re.findall(p1, func_with_param)[0].split(',')
    else:
        left, right = actual_name, expected_name

    # print("{0} is\n {1}".format(left, show_json(actual)))
    # print("{0} is\n {1}".format(right, show_json(expected)))

    try:
        assert actual == expected
    except AssertionError as e:
        # Here we try to make pycharm's 'click to see difference' works and also we want to display full diff
        explanation = []
        if isinstance(actual, int):
            actual = "\"\"" + f'(int {left})  {actual}' + "\"\""
            expected = "\"\"" + f'(int {right})  {expected}' + "\"\""
            explanation.append("assert " + actual + " == " + expected)
            explanation.append('Differing items:')
            explanation.append("\"\"" + actual + " != " + expected)

        elif isinstance(actual, str):
            actual = "\"\"" + f'(str {left})  {actual}' + "\"\""
            expected = "\"\"" + f'(str {right})  {expected}' + "\"\""
            explanation.append("assert " + actual + " == " + expected)
            explanation.append('Differing items:')
            explanation.append("\"\"" + actual + " != " + expected)
        else:
            if isinstance(actual, dict):
                actual['__name__'] = left
                expected['__name__'] = right

            explanation.append("assert " + str(actual) + " == " + str(expected))
            explanation.append('Differing items:')
            explanation.append(str(actual) + " != " + str(expected))
            try:
                left_formatting = pprint.pformat(actual).splitlines()
                right_formatting = pprint.pformat(expected).splitlines()
                explanation.extend(['Full diff:'])
            except Exception:
                left_formatting = sorted(repr(x) for x in left)
                right_formatting = sorted(repr(x) for x in right)
                explanation = ['Full diff (fallback to calling repr on each item):']

            explanation.extend(line.strip() for line in difflib.ndiff(left_formatting, right_formatting))

        raise AssertionError('\n'.join(explanation))

def soft_assert(response, expectation):
    '''
    只断言预期json 对象中指定的key，包括子孙对象也只断言指定key，
    list必须断言与实际列表长度一致
    '''
    if isinstance(expectation, list):
        response = {'list': response}
        expectation = {'list': expectation}
    for key, value in expectation.items():
        if isinstance(value, list):
            assert len(response.get(key, [])) == len(value), f'实际返回:{key} 的列表{response.get(key, "无此字段")} 长度与预期不一致'
            for i in range(len(value)):
                soft_assert(response[key][i], value[i])
        elif isinstance(value, dict):
            soft_assert(response[key], value)
        elif value == 'not null':
            response.get(key), f'{key}返回的值:\"{response.get(key, "无此字段")}\"与预期不为空不一致'
        else:
            assert response.get(key) == value, f'{key}返回的值:\"{response.get(key, "无此字段")}\"与预期:\"{value}\"不一致'

