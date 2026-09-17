#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
@author:sonic.gao
@time: 2025/06/16 16:38
@contact: gaoyuhang@dreamsports.ai
@description: 发起http请求的客户端，封装了requests，根据业务场景增加了变量替换、自动签名、证书查找、自动代理等功能
"""
import json
import logging
import os
from json import JSONDecodeError

import allure
import curlify
import requests

from pytest_helper.common import render, DateEncoder
from pytest_helper.encryption import rsa, sha3256, des3_encrypt, get_encryption2
from pytest_helper.errors import NonJsonResponse
# from pytest_helper.signature import moatkeeper_signature, uds_sig, vbom_sign, do_admin_sign, bd_sign
import copy
from urllib.parse import urlparse
import hashlib
import time


class TSPRequest(object):
    @staticmethod
    def request(env, inputs):
        inputs = render(env, inputs)
        encode_password(env, inputs)

        # # 3. 计算签名，并添加到params,如果是musesapi，则不重复计算签名
        # if inputs.get('params', False) and 'musesapi' not in inputs.get('host'):
        #     if 'sign' in inputs.get('params'):
        #         headers = inputs.get('headers')
        #         token = None
        #         if headers:
        #             token = headers.get('Authorization')
        #         sign = moatkeeper_signature(inputs.get('method'),
        #                                     inputs.get('path'),
        #                                     inputs.get('params'),
        #                                     inputs.get('data'),
        #                                     inputs.get('json'),
        #                                     env['secret'][int(inputs["params"]["app_id"])],
        #                                     token)
        #         inputs['params']["sign"] = sign
        #     # 增加uds sig签名
        #     elif 'sig' in inputs.get('params'):
        #         sig = uds_sig(inputs.get('params'),
        #                       inputs.get('data'),
        #                       env['secret'][int(inputs["params"]["app_id"])])
        #         inputs['params']["sig"] = sig
        #     # 计算字节火山签名，在url里传签名和参数
        #     elif 'Sign' in inputs.get('params'):
        #         sign = bd_sign(inputs.get('params'),
        #                        inputs.get('data'),
        #                        inputs.get('json'),
        #                        env['secret']['accountSecret'])
        #         inputs['params']["Sign"] = sign
        # elif inputs.get('params', False) and 'musesapi' in inputs.get('host'):
        #     if 'sign' in inputs['params']:
        #         s = f'{env["secret"][inputs["params"]["appid"]]}0appid={inputs["params"]["appid"]}1deviceid={inputs["params"]["deviceid"]}2os={inputs["params"]["os"]}3packagename={inputs["params"]["packagename"]}{env["secret"][inputs["params"]["appid"]]}'
        #         sign = hashlib.md5(s.encode(encoding="utf-8")).hexdigest()
        #         inputs['params']['sign'] = sign

        # # 3. 计算签名，并添加到data
        # if inputs.get('data', False):
        #     # 增加vinbom sign签名
        #     d = inputs.get('data')
        #     if 'vbom_sign' in d:
        #         # support esb sign
        #         application = d.get('application', 0)
        #         app_secret = None
        #         if env.get('secret', 0) and application in env.get('secret', 0):
        #             app_secret = env['secret'][application]
        #         else:
        #             app_secret = None if inputs['data']['vbom_sign'] == "" else inputs['data']['vbom_sign']
        #         sign = vbom_sign(inputs.get('params'),
        #                          inputs.get('data'), app_secret)
        #         inputs['data']["sign"] = sign

        # # 字节火山签名，在json body里传签名和参数
        # if inputs.get('json', False):
        #     if 'Sign' in inputs.get('json'):
        #         sign = bd_sign(inputs.get('params'),
        #                        inputs.get('data'),
        #                        inputs.get('json'),
        #                        env['secret']['accountSecret'])
        #         inputs["json"]['Sign'] = sign

        # # 3. do admin接口签名字段在headers里，计算签名并更新在headers里
        # headers = inputs.get("headers")
        # if headers and 'do_admin_sign' in headers:
        #     public_key = headers.get('publicKey', 0)
        #     private_key = None
        #     if env.get('secret', 0) and public_key in env.get('secret', 0):
        #         private_key = env['secret'][public_key]
        #     sign = do_admin_sign(headers, inputs["json"], private_key)
        #     headers["sign"] = sign

        # # 4. 设置代理，命令行如何设置代理的话，就走代理
        # if env.get('proxy'):
        #     inputs['proxies'] = env.get('proxies')
        # # 5. 处理files
        # check_form_upload(env, inputs)

        # 6. 发送请求
        logging.info("请求对象\n" + json.dumps(inputs, indent=2, ensure_ascii=False, cls=DateEncoder))
        with allure.step("发起请求{}{}".format(inputs.get("method"), inputs.get("host") + inputs.get("path"))):
            allure.attach(json.dumps(inputs, indent=2, ensure_ascii=False, cls=DateEncoder), '请求对象')
            requests_inputs = copy.copy(inputs)
            r = requests.request(requests_inputs.pop('method'),
                                 url=requests_inputs.pop('host') + requests_inputs.pop('path'),
                                 **requests_inputs)
            curl_print(r.request, inputs)
            r.encoding = 'utf-8'
            try:
                response = r.json()
            except (JSONDecodeError, requests.exceptions.JSONDecodeError):
                # 非 JSON 响应：**不要**静默返回 bytes。
                #
                # 历史行为是 `response = r.content`，结果连接层故障
                # （例如设备/网关不可达时返回 b'upstream connect failed: ...'）
                # 会被伪装成业务断言失败：
                #   - 测试里 response['code'] -> TypeError: byte indices must be integers...
                #   - 断言层 jsonpath 返回 False -> AssertionError: check_key: code
                # 两种信息都与真实原因无关，导致"跑完不知道结论可不可信"。
                # 现在在源头抛带上下文的显式异常，失败信息自解释。
                raw_text = r.text
                allure.attach(raw_text or "(空响应体)", '响应结果(非 JSON)')
                logging.error("响应不是 JSON:\n" + (raw_text or "(空响应体)"))
                raise NonJsonResponse(
                    url=inputs.get('host', '') + inputs.get('path', ''),
                    status_code=r.status_code,
                    content_type=r.headers.get('Content-Type'),
                    body=raw_text,
                    method=inputs.get('method'),
                ) from None
            response_txt = json.dumps(response, indent=2, ensure_ascii=False, cls=DateEncoder)
            allure.attach(response_txt, '响应结果')
            logging.info("响应结果\n" + response_txt)
            return response


def check_form_upload(env, inputs):
    files = []
    if inputs.get("files", []):
        if len(inputs.get("files")) > 0:
            for i in inputs.get("files"):
                file_json = i.get("file", {})
                if file_json.get("path"):
                    # if not file_json["path"].startswith('/'):
                    file_real_path = os.path.join(env['rootdir'] + "/res/", file_json["path"])
                    # else:
                    #     file_real_path = file_json["path"]
                param_name = file_json.get("name", "file")
                file_type = file_json.get("type", "text/plain")
                file_name = file_json.get("file_name", os.path.basename(file_json["path"]))
                file = (param_name, (file_name, open(file_real_path, 'rb'), file_type))
                files.append(file)
        inputs['files'] = files


def curl_print(req: requests.request, inputs):
    try:
        curl_str = curlify.to_curl(req)

        if 'cert' in inputs and inputs['cert'] is not None:
            curl_str += f" --tlsv1.2 --cert {inputs['cert'][0]} --key {inputs['cert'][1]}"
            curl_str += f" --cacert {inputs['verify']}" if 'verify' in inputs else " -k"

        logging.info(curl_str)
    except UnicodeDecodeError as e:
        _get_curl_request(inputs)


def encode_pincode(env, inputs):
    if inputs.get('data', False) and 'pin_code' in inputs['data']:
        key_id, key = get_encryption2(env.get('host').get('app_in'), inputs['params']['app_id'])
        inputs['data']['pin_code'] = rsa(sha3256(inputs.get('data').get('pin_code')), key).decode("utf-8")
        if 'pin_code_key_id' in inputs.get('data'):
            inputs['data']['pin_code_key_id'] = key_id
        if 'key_id' in inputs.get('data') and inputs['data']['key_id'] is None:
            inputs['data']['key_id'] = key_id

    if inputs.get('params', False) and 'pin_code' in inputs['params']:
        key_id, key = get_encryption2(env.get('host').get('app_in'), inputs['params']['app_id'])
        inputs['params']['pin_code'] = rsa(sha3256(inputs.get('params').get('pin_code')), key).decode("utf-8")
        if 'pin_code_key_id' in inputs.get('params'):
            inputs['params']['pin_code_key_id'] = key_id
        if 'key_id' in inputs.get('params') and inputs['data']['key_id'] is None:
            inputs['params']['key_id'] = key_id


def encode_password(env, inputs):
    if inputs.get('data', False) and 'password_e' in inputs['data']:
        if 'encryption' in inputs and inputs['encryption']['type'] == '3DES':
            inputs['data']['password_e'] = des3_encrypt(inputs['data']['password_e'], inputs['encryption']['key'])
            del (inputs['encryption'])
        elif inputs.get('path', False) == '/c/user/register':
            key_id, key = get_encryption2(env.get('host').get('app_in'), inputs['params']['app_id'])
            inputs['data']['password_e'] = rsa(inputs.get('data').get('password_e'), key).decode("utf-8")
            inputs['data']['key_id'] = key_id
            inputs['data']['key'] = key
        else:
            key_id, key = get_encryption2(env.get('host').get('app_in'), inputs['params']['app_id'])
            inputs['data']['password_e'] = rsa(sha3256(inputs.get('data').get('password_e')), key).decode("utf-8")
            inputs['data']['key_id'] = key_id
            inputs['data']['key'] = key

    if inputs.get('params', False) and 'password_e' in inputs['params']:
        key_id, key = get_encryption2(env.get('host').get('app_in'), inputs['params']['app_id'])
        inputs['params']['password_e'] = rsa(sha3256(inputs.get('params').get('password_e')), key).decode("utf-8")
        inputs['params']['key_id'] = key_id
        inputs['params']['key'] = key


def _get_curl_request(input):
    """
    :return:
    """
    urls = input.get('url', '')
    if input.get('params'):
        urls += "?" + _dict_to_url_param(input['params'])
    curl_str = "curl -X {method} \'{url}\'".format(method=input.get('method', 'GET').upper(), url=urls)

    if input.get('headers'):
        for k, v in input['headers'].items():
            curl_str += " -H \'{key}:{value}\'".format(key=k, value=v)
    if input.get('data'):
        if isinstance(input['data'], dict):
            curl_str = curl_str + " -d \'{data_str}\'".format(data_str=_dict_to_url_param(input['data']))
        elif isinstance(input['data'], str):
            curl_str = curl_str + " -d \'{data_str}\'".format(data_str=input['data'])
    if input.get("cert"):
        curl_str = curl_str + " --tlsv1.2 --cert {cert} --key {key}".format(cert=input.get("cert")[0],
                                                                            key=input.get("cert")[1])
        if input.get("verify"):
            curl_str = curl_str + " --cacert {cacert}".format(cacert=input.get("verify"))
        else:
            curl_str = curl_str + " -k"
    curl = curl_str + ' -v | json_pp'
    logging.info('Requester curl is :\n{}'.format(curl))


def _dict_to_url_param(diction):
    param_str = ''
    for k, v in diction.items():
        param_str += '&' + str(k) + '=' + str(v)
    return param_str[1:]


def request_with_sign(url, app_schema, m='get', params=None, data=None, json=None, headers=None,
                      **kwargs):
    import json as js
    # generate sign param
    o = urlparse(url)
    now = int(time.time())
    sign_str = ''
    sign_list = ['timestamp={}'.format(now), 'app_id={}'.format(app_schema[0])]
    params = {} if params is None else params
    if o.query:
        sign_list += o.query.split('&')
    if params:
        sign_list += [k + '=' + str(v) for k, v in params.items()]
    if data:
        for k, v in data.items():
            sign_list += [k + '=' + str(i) for i in v] if isinstance(v, list) else [k + '=' + str(v)]
    if json:
        sign_list.append('jsonBody={}'.format(js.dumps(json)))
    sign_list.sort()
    sign_str = m.upper() + o.path + '?' + '&'.join(sign_list) + app_schema[1]
    if headers and 'Authorization' in headers:
        sign_str += headers['Authorization']
    sign = hashlib.sha256(bytes(sign_str, encoding='utf-8')).hexdigest() if params.get('hash_type', 0) else hashlib.md5(
        bytes(sign_str, encoding='utf-8')).hexdigest()
    params.update({
        'timestamp': now,
        'app_id': app_schema[0],
        'sign': sign
    })
    inputs = {

    }
    response = requests.request(m, url, params=params, data=data, json=json, headers=headers, **kwargs)
    curl_print(response.request, {})
    return response
