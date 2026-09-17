#!/usr/bin/env python  
# -*- coding:utf-8 -*-  
""" 
@author:sonic.gao 
@time: 2025/07/22 15:17
@contact: gaoyuhang@dreamsports.ai
@description: 脚本描述【必填】
"""
import datetime
import decimal
import json
import logging
import re
import jsonpath
import time
import requests


class DateEncoder(json.JSONEncoder):
    """
    格式化json内特殊类型字段
    """

    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        else:
            try:
                return json.JSONEncoder.default(self, obj)
            except TypeError as e:
                logging.debug('JSONEncoder  error')
                logging.debug(e.args)
                return str(obj)


def render(env, inputs):
    """
    用env中的数据替换测试数据中{{}}中间的内容，{{}}中间采用jsonpath语法
    """

    input_str = json.dumps(inputs, indent=2, ensure_ascii=False, cls=DateEncoder)
    pattern = re.compile(r"{{([^{].*?)}}")
    matches = re.findall(pattern, input_str)
    for m in matches:
        if jsonpath.jsonpath(env, m):
            try:
                value = jsonpath.jsonpath(env, m)[0]
                input_str = input_str.replace("{{" + m + "}}", str(value))
            except Exception as e:
                logging.error(f'Render Error  m:{m} value:{value} error_msg:{e}')
                raise
        else:
            pass
    # logging.info(input_str)
    return json.loads(input_str)


def now_to_date(format_string="%Y-%m-%d %H:%M:%S"):
    """
    将当前时间转换为时间字符串，默认为2017-10-01 13:37:04格式
    :param format_string:
    :return:
    """
    time_stamp = int(time.time())
    time_array = time.localtime(time_stamp)
    str_date = time.strftime(format_string, time_array)
    return str_date


def bj_to_date():
    """
    获取北京时间，默认为2017-10-01 13:37:04格式
    :param format_string:
    :return:
    """
    data = requests.get(url='http://quan.suning.com/getSysTime.do').json()
    str_date = data['sysTime2']
    return str_date
    
def merge(defaults, override):
    """
    merge字典
    """
    if defaults is None:
        defaults = dict()
    for k, v in override.items():
        if k in defaults:
            if isinstance(v, dict):
                defaults[k] = merge(defaults[k], v)
        else:
            defaults[k] = v
    return defaults


