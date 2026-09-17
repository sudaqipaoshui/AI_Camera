#!/usr/bin/python3
# -*- coding:utf-8 -*-  
""" 
@author: gaoyuhang@dreamsports.ai
@time: 2025/09/08 15:56
@file: yapi_to_.py
@description: 通过Yapi的OpenAPI获取接口文档信息,转化成需要的脚本
"""


import os
import string
import time
import jsonpath
import pypinyin
import requests
import json
import yaml
import traceback

host = 'https://yapi.dream-sports.cn'

class Yapi(object):

    def __init__(self, host, project_token, cat_id=None):
        """连接yapi初始化信息
        :param yapi_host: yapi对应域名
        :param project_token: 每个项目都有唯一的标识token，用户可以使用这个token值来请求项目 openapi.
        """
        self.token = project_token
        self.url = host
        self.cat_id = cat_id

    def get_project(self) -> dict:
        """
        获取项目配置信息，重点是需要里面的basepath属性。
        :return: dict
        """
        resp = {}
        try:
            resp = requests.request("GET",
                                    self.url + "/api/project/get",
                                    headers={"Content-Type": "application/json"},
                                    params={"token": self.token}).json()
            # 仅当data存在时设置class_name，避免NoneType错误
            if isinstance(resp, dict) and isinstance(resp.get('data'), dict):
                resp["class_name"] = Yapi._get_class_name(resp['data'].get('name', ''))
            # print(json.dumps(resp, indent=2, ensure_ascii=False))
            # project_id = resp['data']['_id']
        except Exception as e:
            print("调用/api/project/get失败：", e)
        return resp

    def get_interfaces_by_project_id(self, page=1, limit=1000) -> list:
        """获取项目下的所有接口id组成的列表
        :param limit:
        :param page:
        :param project_id:
        """
        interfaces = []
        try:
            resp = requests.request("GET",
                                    self.url + "/api/interface/list",
                                    headers={"Content-Type": "application/json"},
                                    params={"project_id": self.get_project()['data']['_id'],
                                            "page": page,
                                            "limit": limit,
                                            "token": self.token}).json()
            # print(json.dumps(resp, indent=2, ensure_ascii=False))
            interfaces = jsonpath.jsonpath(resp, "$.._id")
        except Exception as e:
            print("调用/api/interface/list失败：", e)
        return interfaces

    def get_interfaces_by_cat_id(self, cat_id, page=1, limit=1000) -> list:
        """获取项目下的分类所有接口id组成的列表
        :param cat_id:
        :param project_id:
        """
        interfaces = []
        try:
            resp = requests.request("GET",
                                    self.url + "/api/interface/list_cat",
                                    headers={"Content-Type": "application/json"},
                                    params={"catid": cat_id,
                                            "project_id": self.get_project()['data']['_id'],
                                            "page": page,
                                            "limit": limit,
                                            "token": self.token}).json()

            # print(json.dumps(resp, indent=2, ensure_ascii=False))
            interfaces = jsonpath.jsonpath(resp, "$.._id")
        except Exception as e:
            print("调用/api/interface/list失败：", e)
        return interfaces

    def get_detail_by_id(self, interface_id) -> list:
        """根据interface_id获取接口的详细信息
        :param interface_id: 接口的id
        """
        detail = {"method": "",
                  "path": "",
                  "headers": None,
                  "params": None,
                  "data": None,
                  "json": None,
                  "files": None}
        resp = None
        try:
            resp = requests.request("GET",
                                    self.url + "/api/interface/get",
                                    headers={"Content-Type": "application/json"},
                                    params={"id": interface_id, "token": self.token}).json()
            # print(json.dumps(resp, indent=2, ensure_ascii=False))
        except Exception as e:
            print("请求/api/interface/get异常：", e)

        # 项目信息
        project_info = self.get_project() or {}
        # detail['project']["project_id"] = project_info.get('_id')
        # detail['project']["class_name"] = project_info.get('class_name')
        # detail['project']['create_time'] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        # 接口信息
        data = (resp or {}).get('data') or {}
        if not data:
            print("获取接口详情失败，接口ID: {}，响应无data".format(interface_id))
            return None

        basepath = ((project_info or {}).get('data') or {}).get('basepath', '') or ''
        detail['api_title'] = data.get('title')
        detail['project_id'] = data.get('project_id')
        detail['api_id'] = data.get('_id')
        detail['method'] = data.get('method')
        detail["path"] = basepath + (data.get('path') or '')
        detail['api_name'] = data.get('method', '').lower() + "_" + (data.get('path') or '').lstrip('/').replace(
            "/", "_").lower().replace("{", "").replace(
            "}", "").replace("-", "_").replace(":", "")

        # 处理header
        detail['headers'] = {}
        for header in (data.get('req_headers') or []):
            detail['headers'][header['name']] = header.get("value") or header.get("example", "")

        # 处理params
        # detail['params'] = {"sign": "", "app_id": ""}
        detail['params'] = {}
        for query in (data.get('req_query') or []):
            detail['params'][query['name']] = query.get("value") or query.get("example", "")

        # 处理data
        req_body_type = data.get('req_body_type')

        if req_body_type == 'json':
            detail['json'] = {}
            req_body = data.get('req_body_other')
            if req_body:
                parsed = Yapi._safe_json_loads(req_body)
                if parsed is not None:
                    detail['json'] = Yapi._json_format(parsed)

        if req_body_type == 'raw':
            detail['data'] = {}
            req_body = data.get('req_body_other')
            if req_body:
                parsed = Yapi._safe_json_loads(req_body)
                if parsed is not None:
                    detail['data'] = parsed

        if req_body_type == 'form':
            detail['data'] = {}
            req_body = data.get('req_body_form') or []
            for body in req_body:
                detail['data'][body['name']] = body.get("value") or body.get("example", "")

        # 处理response
        res_body_type = data.get('res_body_type')
        
        if res_body_type == 'json':
            detail['response'] = {}
            res_body = data.get('res_body')
            if res_body:
                parsed = Yapi._safe_json_loads(res_body)
                if parsed is not None:
                    detail['response'] = Yapi._json_format(parsed)

        detail['request_template'] = "{" + Template.request_template.format(**detail) + "}"

        return detail

    def get_project_categories(self) -> list:
        """
        get_project_categories:获取项目下的所有分类组成的列表
        Returns:
            list: categories apilist
        """
        categories = []
        try:
            resp = requests.request("GET",
                                    self.url + "/api/interface/getCatMenu",
                                    headers={"Content-Type": "application/json"},
                                    params={"project_id": self.get_project()['data']['_id'],
                                            "token": self.token}).json()

            # print(json.dumps(resp, indent=2, ensure_ascii=False))
            categories = jsonpath.jsonpath(resp, "$.._id")
        except Exception as e:
            print("调用/api/interface/getCatMenu失败：", e)
        return categories

    def get_all_api_details(self) -> list:
        """获取项目或目录下的所有api详情
        """
        # 获取目录下的API详情
        # api_list = self.get_interfaces_by_cat_id(cat_id=279531)
        
        # 获取项目下的API详情
        api_list = self.get_interfaces_by_project_id()
                
        all_api_details = []
        
        for api in api_list:
            api_detail = self.get_detail_by_id(api)
            print("当前正在获取接口: {}".format(api))
            if api_detail:
                all_api_details.append(api_detail)
            else:
                print("获取接口失败")
            
        return all_api_details

    def get_cat_api_details(self, cat_id) -> list:
        """获取目录下的所有api详情
        """
        api_list = self.get_interfaces_by_cat_id(cat_id)

        # 获取项目下的API详情
        all_api_details = []
        
        for api in api_list:
            api_detail = self.get_detail_by_id(api)
            print("当前正在获取接口: {}".format(api))
            if api_detail:
                all_api_details.append(api_detail)
            
        return all_api_details

    def get_one_api_details(self, api_id) -> list:
        """获取单个api详情
        """
        api_list = [api_id]
                
        all_api_details = []
        
        for api in api_list:
            api_detail = self.get_detail_by_id(api)
            print("当前正在获取接口: {}".format(api))
            if api_detail:
                all_api_details.append(api_detail)
            else:
                print("获取接口失败")
            
        return all_api_details

    @staticmethod
    def _json_format(json_data) -> dict:
        """
        解析yapi中的json数据
        :param json_data:
        :return: dict
        """
        if not isinstance(json_data, dict):
            return json_data
            
        temp = {}
        json_type = json_data.get("type")
        if json_type == "array":
            items = json_data.get('items', {})
            temp = [Yapi._json_format(items)]
        elif json_type == "object":
            properties = json_data.get('properties', {})
            for k, v in properties.items():
                temp[k] = Yapi._json_format(v)
        elif json_type in ["string", "text"]:
            temp = ''
        elif json_type == "boolean":
            temp = False
        elif json_type in ["integer", "number"]:
            temp = 0
        else:
            # 如果没有type字段，直接返回原始数据或空字典
            temp = json_data

        return temp

    @staticmethod
    def _safe_json_loads(text: str):
        """尝试宽松解析JSON，失败返回None。"""
        try:
            return json.loads(text)
        except Exception:
            try:
                return yaml.safe_load(text)
            except Exception:
                print("JSON解析失败，内容:", (text[:120] + '...') if isinstance(text, str) and len(text) > 120 else text)
                return None

    @staticmethod
    def _get_class_name(name: str):
        class_name = ""
        for letter in name.capitalize():
            if letter not in string.punctuation:
                if '\u4e00' <= letter <= '\u9fa5':  # 中文
                    s = ''
                    for i in pypinyin.pinyin(letter, style=pypinyin.NORMAL):
                        s += ''.join(i)
                    class_name += s.capitalize()
                else:
                    class_name += letter
        return class_name

class Template(object):
    """Template"""

    py_service_template = """
#!/usr/bin/env python
# -*- coding:utf-8 -*-

\"""
@Time: {time}
@Author: yapi2service generator
@doc: {host}/project/{project_id}/interface/api
\"""

import copy
from pytest_http.http_client import HttpRequest


class {class_name}Service(object):

    def __init__(self, env):
        self.env = env

    @staticmethod
    def render_template(template, inputs):
        \"""使用实际参数替换template中的参数\"""
        template_copy = copy.deepcopy(template)
        if inputs.get('host'):
            template_copy["host"] = inputs.get('host')
        if inputs.get('path'):
            template_copy["path"] = inputs.get('path')
        if inputs.get('headers'):
            template_copy["headers"] = {class_name}Service._replace(template["headers"], inputs.get('headers'))
        if inputs.get('params'):
            template_copy["params"] = {class_name}Service._replace(template["params"], inputs.get('params'))
        if inputs.get('data'):
            template_copy["data"] = {class_name}Service._replace(template["data"], inputs.get('data'))
        if inputs.get('json'):
            template_copy["json"] = {class_name}Service._replace(template["json"], inputs.get('json'))
        if inputs.get('files'):
            template_copy["files"] = inputs.get('files')
        if inputs.get('verify'):
            template_copy["verify"] = inputs.get('verify')
        if inputs.get('cert'):
            template_copy["cert"] = inputs.get('cert')
    
        return template_copy
    
    @staticmethod
    def _replace(template, inputs):
        \"""
        用inputs渲染template
        对于 template 和 inputs 都有的 key，合成规则为： 用inputs的值覆盖template的值。
        对于 只有 template 或者 只有inputs 有的 key，将 template 和 inputs 合成一个新的字典。
        \"""
        if isinstance(template, dict) and isinstance(inputs, dict):
            new_dict = dict()
            inputs_keys = list(inputs.keys())
            for d1k in template.keys():
                if d1k in inputs_keys:  # template, inputs都有。去往深层比对
                    inputs_keys.remove(d1k)
                    new_dict[d1k] = {class_name}Service._replace(template.get(d1k), inputs.get(d1k))
                else:  # template有, inputs没有的key
                    new_dict[d1k] = template.get(d1k)
            for d2k in inputs_keys:  # inputs有, template没有的key
                new_dict[d2k] = inputs.get(d2k)
            return new_dict
        else:
            return inputs or template  # 看谁不是None或者''
"""

    # 注意缩进
    api_template = """
    def {api_name}(self, inputs: dict):
        \"""
        @doc_title: {api_title}
        @doc: https://apidoc.dsint.com/project/{project_id}/interface/api/{api_id}
        \"""
        template = {request_template}
        template = self.render_template(template, inputs)
        response = HttpRequest.request(self.env, template)
        return response
        """

    request_template = """
                     "method": "{method}",
                     "path": "{path}",
                     "headers": {headers},
                     "params": {params},
                     "json": {json},
                     "data": {data},
                     "files": {files},  # [optional] Content-Type=multipart/form-data时需要，相对路径
                     "verify": False,  # [optional]双向认证接口需要，验证服务端的ca，相对路径
                     "cert": [  # [optional]双向认证接口需要，验证客户端的证书，相对路径
                        "",  # tls_cert
                        ""  # tls_private_key
                     ]
                     """

    py_case_template = """#!/usr/bin/env python
# -*- coding:utf-8 -*-

\"""
@Time: {time}
@Author: pytest generator
@Doc: {host}/project/{project_id}/interface/api/{api_id}
\"""

import logging
from pprint import pprint
import allure
import pytest
from pytest_helper.assertions import free_compare, soft_assert, result_compare

@allure.feature('{class_name}')
@allure.story('{class_name}{case}')
class {class_name}(object):

    @pytest.fixture(scope="class", autouse=True)
    def prepare(self, request, env, mysql, requests):
        with allure.step("测试数据准备:"):
            pass

        @allure.step("测试数据清理:")
        def fin():
            pass
        request.addfinalizer(fin)
        return 

    @allure.title({case})
    @allure.link("{host}/project/{project_id}/interface/api/{api_id}")
    @pytest.mark.author('pytest.generator')
    @pytest.mark.datafile('{data_file}')
    def {function_name}(self, env, inputs, requests, expectation, case):
        with allure.step(case):
            response = requests.request(env, inputs)

        with allure.step("校验结果"):
            assert response['code'] == expectation['response']['code']
            free_compare(response, expectation)



"""

def _create_service_file(filename, project):
    """
    内部接口。将project更新template，并写到py文件中
    :param filename:
    :param project:  项目信息
    :return:
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(Template.py_service_template.format(project_id=project.get('_id'),
                                                        host=host,
                                                        class_name=project.get('class_name'),
                                                        time=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())))
    except Exception as e:
        print(e)

def api2service(filename, token, api_id):
    """
    外部接口。将一个接口写入service文件
    :param filename:
    :param token:
    :param project_id:
    :param api_id:
    :return:
    """
    yapi = Yapi(host, token)
    if not os.path.exists(filename):
        project = yapi.get_project()
        _create_service_file(filename, project)
    try:
        detail = yapi.get_detail_by_id(api_id)
        with open(filename, "a", encoding="utf-8") as f:
            f.write(Template.api_template.format(**detail))
    except Exception as e:
        print(e)

def project2service(filename, token):
    """
    外部接口。将一个项目的所有接口写入service文件
    :param filename:
    :param token:
    :param project_id:
    :return:
    """
    yapi = Yapi(host, token)
    interfaces = yapi.get_interfaces_by_project_id()
    for i in range(len(interfaces)):
        print("进度：{}/{}".format(i + 1, len(interfaces)), "当前处理的接口是{}".format(interfaces[i]))
        api2service(filename, token, interfaces[i])

def yapi2service(filename, token, api_id=None):
    if api_id:
        api2service(filename, token, api_id)
    else:
        project2service(filename, token)

def underline2hump(text):
    """
    下划线转驼峰
    :param text:
    :return:
    """
    arr = filter(None, text.lower().split("_"))
    res = ''
    for i in arr:
        res = res + i[0].upper() + i[1:]
    return res

def _json_format(json_data):
    """
    解析yapi中的json数据
    :param json_data:
    :return:
    """
    temp = {}
    for p in json_data['properties']:
        if json_data['properties'][p]['type'] == "array":
            data = json_data['properties'][p]['items']
            temp[p] = []
            if 'properties' in data:
                temp[p].append(_json_format(data))
        elif json_data['properties'][p]['type'] == "object":
            data = json_data['properties'][p]
            temp[p] = _json_format(data)

        else:
            temp[p] = None
    return temp

def hump2underline(text):
    lst = []
    for index, char in enumerate(text):
        if char.isupper() and index != 0:
            lst.append("_")
        lst.append(char)

    return "".join(lst).lower()

def yapi2yaml_and_py(token: str, api_id: int = None, cat_id:int = None) -> None:
    """
    项目下的接口文档转化成 yaml 和 py。
    如果传入分类目录cat_id，只转化该分类下的接口
    
    :param token: Yapi项目token
    :param cat_id: Yapi项目下的分类目录id
    :return: None
    """
    yapi = Yapi(host, token, cat_id)
    project_resp = yapi.get_project() or {}
    project_data = project_resp.get('data') or {}
    project_id = project_data.get('_id') or ''
    project_name = project_data.get('name') or 'project'
    
    if cat_id is None and api_id is None:
        all_api_details = yapi.get_all_api_details()
    elif api_id is not None:
        all_api_details = yapi.get_one_api_details(api_id)
    elif cat_id is not None:
        all_api_details = yapi.get_cat_api_details(cat_id)

    if project_id != '':
        
        # 在当前目录下生成一个API/data/project_name目录
        file_path_yaml = "data" + "/" + project_name + "/"
        # 在当前目录下生成一个test/project_name目录
        file_path_py =  "tests" + "/" + project_name + "/"
        os.makedirs(f"{file_path_yaml}", exist_ok=True)
        # 生成py
        os.makedirs(f"{file_path_py}", exist_ok=True)

    else:
        file_path_yaml = ''
        file_path_py = ''

    for api_detail in all_api_details:
        try:
            path = api_detail["path"]
            method = api_detail["method"]
            headers = api_detail["headers"]
            params = api_detail["params"]
            data = api_detail["data"]
            json_data = api_detail["json"]
            response = api_detail["response"]
            api_id = api_detail["api_id"]

            cases = {
                "common_inputs":{
                    "host": "{{$.host.app}}",
                    "method": method,
                    "path": path,
                    "params": {
                    },
                    "headers": headers
                    },
                "tests": [{
                    "case": path,
                        "input": {
                        "params": 
                            params,
                            "data": data,
                            "json": json_data,
                            "files": None,
                            "verify": None,
                            "cert": None
                        },
                        "expectation": {
                            "response": response
                    }
                }]
            }

            # 转成yaml格式
            fmt_case = yaml.dump(
                cases, default_flow_style=False, allow_unicode=True, sort_keys=False)

            dst = "test" + path.replace("/", "_").lower()
            with open(f"{file_path_yaml}{dst}.yaml", "w", encoding="utf-8") as f:
                f.write(fmt_case)
            
            with open(f"{file_path_py}{dst}.py", "w", encoding="utf-8") as f:
                code = Template.py_case_template.format(
                    host=host,
                    class_name=underline2hump(dst),
                    data_file=f'{file_path_yaml}{dst}.yaml',
                    project_id=project_id,
                    api_id=api_id,
                    case='"{case}"',
                    time=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                    function_name=hump2underline(dst)
                )
                f.write(code)

        except Exception as e:
            print('api_id:{}导出失败，请查看报错信息！'.format(api_detail.get('api_id')))
            traceback.print_exc()