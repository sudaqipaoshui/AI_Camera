#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
@Time: 2024-09-12 11:26:07
@Author: ying.chen
@Update: Token刷新 by ran.xu&sonic.gao
@Description: 跟微服务相关的业务处理类
@Prd:
@Showdoc:
"""
import json
import time
import requests
import yaml
import logging
from pytest_helper.http_client import DateEncoder, request_with_sign
# from pytest_helper.signature import moatkeeper_signature
import traceback
from pytest_helper.encryption import sha3256, get_encryption2, rsa

c_app_ids = {1000004, 1000003, 1000027}

# TODO 重构

def get_encryption2_eu(host, env, app_id=10000):
    """
    获取key_id/key
    每次要用到密码的时候，先调用本接口，获取key和key_id
    把密码使用rsa加密,BASE64, 再传输，并带上本次的key_id,规则见新版密码规则
    """

    params= {
        'hash_type':  'sha256'
    }
    
    app_schema = (app_id,env['secret'][int(app_id)])
    url = f'{host}/acc/2/in/get_encryption' if int(app_id) not in c_app_ids else f'{host}/acc/2/get_encryption'
    
    response = request_with_sign(url, app_schema, m="GET",params=params).json()
    return response['data']['key_id'], response['data']['key']

def get_login_token(cfg):
    requestBody = {'username': 'qingle.liu.o', 'password': 'Hk6/HNowekbWClv7rvQB2yA9YYE01AaV9PNNRTUQoF3AOcboxPgqiN173ISC+KYl3kjcNR9JqUOG2QAvT8Ep4wqdStEuFi1RH5wmrW71dkkbJCUrdRdbaljtVdFAE822cocnFithRWx2U19GB5ugp9kpFe87WXHP3F3b5lC5hI0=', 'dealerCode': '999999', 'isSSO': 'false'}
    loginToken = requests.request(url='https://scms-sit.dshome.com/api/v1/login-service/common/login', method='POST',
                                  json=requestBody)
    import json
    tokenJson = json.loads(loginToken.text)
    token = "Bearer " + tokenJson['TOKEN']
    # with open(f"{config_path}", 'r', encoding='UTF-8') as configfile:
    #     cfg = yaml.load(configfile)
    cfg['maintenance_token']['loginToken'] = token
    save_yaml(cfg)
    return token


def get_bro_token(cfg):
    requestParam = {'appId': '123456'}
    broToken = requests.request(url='https://artemis-api.dsint.com/api/v1/som-bro-service/token/get', method='POST',
                                data=requestParam)
    broToken = str(broToken.content, encoding='utf-8')
    token = "Bearer " + broToken
    # with open(f"{config_path}", 'r', encoding='UTF-8') as configfile:
    #     cfg = yaml.load(configfile)
    cfg['maintenance_token']['broToken'] = token
    save_yaml(cfg)
    return token


def scms_pad_login_token(cfg):
    requestBody = {'username': 'baojun.xu.o', 'password': 'IVBoiFGJE2yojqjScwaNf6UI/L8iYwGJ5+1BXwFEEIpFcu+d7Bh/Vq4HQV2EAHSdjZZ4mNCgAgwU/fZS8Ttc0V/NFr43hbld2CXpejFfUhmLdFDry/Ne2MjvCZ/elpq3EUoymSk7rBAR7nm8IZO61rQYN3m9EijE2T1PVQslNyI=', 'dealerCode': 'BEJB001'}
    SpaaloginToken = requests.request(url='https://scms-test.ds.com/api/v1/login-service/common/login', method='POST',
                                      json=requestBody)
    tokenJson = json.loads(SpaaloginToken.text)
    scms_pad_token = "Bearer " + tokenJson['TOKEN']
    # with open(f"{config_path}", 'r', encoding='UTF-8') as configfile:
    #     cfg = yaml.load(configfile)
    cfg['maintenance_token']['scmspadToken'] = scms_pad_token
    save_yaml(cfg)

def spaa_login_token(cfg):
    requestBody = {'username': 'qingle.liu.o', 'password': '123456', 'dealerCode': '999999', 'isSSO': 'false'}
    SpaaloginToken = requests.request(url='https://artemis-api-sit.ds.com/api/v1/spaa-login-service/common/login',
                                      method='POST',
                                      data=requestBody)
    tokenJson = json.loads(SpaaloginToken.text)
    spaatoken = "Bearer " + tokenJson['TOKEN']
    # with open(f"{config_path}", 'r', encoding='UTF-8') as configfile:
    #     cfg = yaml.load(configfile)
    cfg['maintenance_token']['spaaloginToken'] = spaatoken
    save_yaml(cfg)


def get_maintenancece_token(env):
    """
    获取maintenancece token
    :param config_path:
    :return:
    """
    if "maintenance_token" in env:
        get_login_token(env)
        get_bro_token(env)
        scms_pad_login_token(env)
        spaa_login_token(env)


def get_account_token(cfg):
    """
     1.验证token是否过期
     2.过期则刷新；不过期不刷新
    :param cfg:
    :return:
    """
    refreshToken = cfg.get("refresh_token")
    if refreshToken == 1 or refreshToken == "ds":
        refreshToken = "ds"
        app_secrets = cfg.get("secret")
        environment = cfg["environment"]
        for user in cfg["users"]:
            account_id = user["account_id"]
            if isinstance(user["tokens"], dict) and user["tokens"]:
                appids = user["tokens"].keys()
                for appid in appids:
                    token_value = user["tokens"][appid]
                    check = check_token(
                        environment, app_secrets, token_value, appid, refreshToken
                    )
                    if check != "success":
                        status = refresh_token(
                            account_id,
                            app_secrets,
                            refreshToken,
                            environment,
                            app_id=appid,
                        )
                        if status != "fail":
                            user["tokens"][appid] = status

            else:
                appid = cfg.get("app_id")
                token_value = user["tokens"]
                check = check_token(
                    environment, app_secrets, token_value, appid, refreshToken
                )
                if check != "success":
                    status = refresh_token(
                        account_id, app_secrets, refreshToken, environment, app_id=appid
                    )
                    if status != "fail":
                        user["tokens"] = status

        save_yaml(cfg)

    elif refreshToken == "eu":
        app_secrets = cfg.get("secret")
        environment = cfg["environment"]
        for user in cfg["users"]:
            email = user["email"]
            password = user["password"]
            if isinstance(user["tokens"], dict) and user["tokens"]:
                for appid in user["tokens"]:
                    validation = check_token(
                        environment,
                        app_secrets,
                        user["tokens"][appid],
                        appid,
                        refreshToken,
                    )
                    if validation != "success":
                        token = login_eu(email, password, cfg, appid)
                        if token != "fail":
                            user["tokens"][appid] = token

            else:
                appid = cfg.get("app_id")
                validation = check_token(
                    environment, app_secrets, user["tokens"], appid, refreshToken
                )
                if validation != "success":
                    token = login_eu(email, password, cfg, appid)
                    if token != "fail":
                        user["tokens"] = token
        save_yaml(cfg)

    elif refreshToken == "alps":
        app_secrets = cfg.get("secret")
        environment = cfg["environment"]
        for user in cfg["users"]:
            account_id = user["account_id"]
            if isinstance(user["tokens"], dict) and user["tokens"]:
                appids = user["tokens"].keys()
                for appid in appids:
                    token_value = user["tokens"][appid]
                    check = check_token(
                        environment, app_secrets, token_value, appid, refreshToken
                    )
                    if check != "success":
                        status = refresh_token(
                            account_id,
                            app_secrets,
                            refreshToken,
                            environment,
                            app_id=appid,
                        )
                        if status != "fail":
                            user["tokens"][appid] = status

            else:
                appid = cfg.get("app_id")
                token_value = user["tokens"]
                check = check_token(
                    environment, app_secrets, token_value, appid, refreshToken
                )
                if check != "success":
                    status = refresh_token(
                        account_id, app_secrets, refreshToken, environment, app_id=appid
                    )
                    if status != "fail":
                        user["tokens"] = status

        save_yaml(cfg)

    elif refreshToken == "fy":
        app_secrets = cfg.get("secret")
        environment = cfg["environment"]
        for user in cfg["users"]:
            account_id = user["account_id"]
            if isinstance(user["tokens"], dict) and user["tokens"]:
                appids = user["tokens"].keys()
                for appid in appids:
                    token_value = user["tokens"][appid]
                    check = check_token(
                        environment, app_secrets, token_value, appid, refreshToken
                    )
                    if check != "success":
                        status = refresh_token(
                            account_id,
                            app_secrets,
                            refreshToken,
                            environment,
                            app_id=appid,
                        )
                        if status != "fail":
                            user["tokens"][appid] = status

            else:
                appid = cfg.get("app_id")
                token_value = user["tokens"]
                check = check_token(
                    environment, app_secrets, token_value, appid, refreshToken
                )
                if check != "success":
                    status = refresh_token(
                        account_id, app_secrets, refreshToken, environment, app_id=appid
                    )
                    if status != "fail":
                        user["tokens"] = status

        save_yaml(cfg)


def save_yaml(cfg):
    with open(f"{cfg['config_path']}", mode='w', encoding='UTF-8') as configfile:
        yaml.dump(cfg, configfile, default_flow_style=False, allow_unicode=True, sort_keys=False)

def check_token(environment, app_secrets, token, refreshToken, app_id=10000):
    """
    校验token是否过期
    :param environment:
    :param app_secrets:
    :param token:
    :param app_id:
    :return:
    """
    try:
        if not token or len(str(token)) < 13 or 'Bearer' not in token:
            return 'failed'
        if refreshToken == 'ds':
            host = 'https://app-{environment}.dsint.com'.format(environment=environment)
        elif refreshToken == 'eu':
            host = 'https://app-{}-eu.dsint.com'.format(environment)
        elif refreshToken == 'alps':
            host = 'https://tsp-alps-{}.dsint.com'.format(environment)
        elif refreshToken == 'fy':
            host = 'https://tsp-fy-{}.dsint.com'.format(environment)
        inputs = {
            "host": host,
            "method": "POST",
            "path": "/acc/2/in/token/verify_access",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 7.0; BLN-AL20 Build/HONORBLN-AL20)/2.9.5-Lifestyle-Android",
            },
            "params": {
                "region": "cn",
                "lang": "zh-cn",
                "app_id": app_id,
                "sign": "",
                "nonce": str(int(time.time() * 1000)),
            },
            "data": {"access_token": token.split(" ")[1], "action": "comment_content"},
        }
        if refreshToken != 'ds':
            inputs['params'].update({'hash_type': 'sha256'})
        headers = inputs.get('headers')
        token = None
        if headers:
            token = headers.get('Authorization')
        sign = moatkeeper_signature(
            inputs.get("method"),
            inputs.get("path"),
            inputs.get("params"),
            inputs.get("data"),
            inputs.get("json"),
            app_secrets[int(app_id)],
            token,
        )
        inputs['params']["sign"] = sign
        res = requests.request(inputs.pop("method"),
                               url=inputs.pop("host") + inputs.pop("path"),
                               **inputs)
        response = res.json()
        if res.status_code == 200:
            return response['result_code']
        else:
            print("校验token失败:{}".format(response))
            return 'fail'
    except Exception as e:
        traceback.print_exc()
        return 'fail'


def refresh_token(account_id, app_secrets, refreshToken, environment, app_id):
    """    
     刷新已过期token
    :param account_id:
    :param app_secrets:
    :param environment:
    :param app_id:
    :return:
    """
    if refreshToken == 'ds':
        host = 'https://app-{environment}.dsint.com'.format(environment=environment)
    elif refreshToken == 'alps':
        host = 'https://tsp-alps-{}.dsint.com'.format(environment)
    elif refreshToken == 'fy':
        host = 'https://tsp-fy-{}.dsint.com'.format(environment)
    try:
        inputs = {
            "host": host,
            "method": "POST",
            "path": "/acc/2/in/token/create_for_other",
            "headers": {
                'Content-Type': 'application/x-www-form-urlencoded',
                "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 7.0; BLN-AL20 Build/HONORBLN-AL20)/2.9.5-Lifestyle-Android"

            },
            "params": {
                "region": "cn",
                "lang": "zh-cn",
                "app_id": 10000,
                "sign": "",
                'nonce': str(int(time.time() * 1000))
            },
            "data": {
                "access_token_ttl_in_days": 90,
                "account_id": account_id,
                'device_id': '982518078',
                'terminal': '{"name":"我的华为手机","model":"HUAWEI P30 Pro"}',
                'remote_ip': '10.110.93.76',
                'dst_app_id': app_id

            }

        }
        headers = inputs.get('headers')
        if refreshToken != 'ds':
            inputs['params'].update({'hash_type': 'sha256'})
        token = None
        if headers:
            token = headers.get('Authorization')
        sign = moatkeeper_signature(
            inputs.get("method"),
            inputs.get("path"),
            inputs.get("params"),
            inputs.get("data"),
            inputs.get("json"),
            app_secrets[int(10000)],
            token,
        )
        inputs['params']["sign"] = sign
        res = requests.request(inputs.pop("method"),
                               url=inputs.pop("host") + inputs.pop("path"),
                               **inputs)
        response = res.json()
        if response.get('result_code') == 'success':
            real_token = 'Bearer ' + response['data']['access_token']
            # print("real token:{}".format(real_token))
            return real_token
        else:
            print("刷新token失败:{}".format(response))
            return 'fail'
    except Exception as e:
        traceback.print_exc()
        return 'fail'

def login_eu(email, password, env, app_id=10000):
    """
    """
    try:
        app_schema = (app_id, env['secret'][int(app_id)])
        host = f'https://app-{env["environment"]}-eu.dsint.com' if int(app_id) not in c_app_ids else f'https://app-{env["environment"]}.eu.ds.com'
        key_id, key = get_encryption2_eu(host, env, app_id)
        pwd = rsa(sha3256(password), key).decode('utf-8')
        payload = {
            'email': email,
            'password_e': pwd,
            'key_id': key_id,
            'device_id': 'local',
            'terminal': '{"name":"我的华为手机","model":"HUAWEI P30 Pro"}',
            'remote_ip': '10.110.93.76',
        }
        url = f'{host}/acc/3/in/app_email/login' if int(app_id) not in c_app_ids else f'{host}/a/account/login'
        inputs = {
            "params": {
                'hash_type':'sha256',
                "region": "cn",
                "lang": "zh-cn",
                'nonce': str(int(time.time() * 1000))
            },
            'data': payload
        }
        response = request_with_sign(url,app_schema,m='POST',**inputs).json()
        return response['data']['token_type'] + ' ' + response['data']['access_token']
    except Exception as e:
        traceback.print_exc()
        logging.error('please make sure that your app id has access to app account service!')
        return 'fail'
