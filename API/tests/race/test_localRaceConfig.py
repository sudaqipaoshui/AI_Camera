#!/usr/bin/env python 
# coding:utf-8
"""
@Time: 2025-09-05 10:10
@Author: gaoyuhang
@Description:
@Prd:https:
@Showdoc:
@case:
@doc: https://hsuhdec6va.feishu.cn/wiki/ZMEhw0l7giqUvNkH3cDcGUgUnmT
"""
from pprint import pprint

import allure
import curlify
import pytest
from pytest_helper.assertions import free_compare
import copy
import json
import datetime

@allure.feature('camera-localRaceConfig')
@allure.story('localRaceConfig')
# @pytest.mark.flaky(reruns=2, reruns_delay=5)
class TestLocalRaceConfig(object):
    @pytest.fixture(scope="class", autouse=True)
    def prepare(self, request, env, mysql, requests):
        pass

    @allure.title("{case}")
    @pytest.mark.datafile('API/data/race/test_localRaceConfig.yaml')
    def test_localRaceConfig(self, env, inputs, requests, expectation, case, mysql):

        with allure.step(case):
            response = requests.request(env, inputs)
        with allure.step("校验结果"):
            free_compare(response, expectation)
