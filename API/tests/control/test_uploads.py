#!/usr/bin/env python
# -*- coding:utf-8 -*-

"""
@Time: 2025-09-25 18:07:49
@Author: pytest generator
@Doc: https://yapi.dream-sports.cn/project/423/interface/api/17315
"""

import logging
from pprint import pprint
import allure
import pytest
from pytest_helper.assertions import free_compare, soft_assert, result_compare


class TestUploads(object):

    @pytest.fixture(scope="class", autouse=True)
    def prepare(self, request, env, mysql, requests):
        with allure.step("测试数据准备:"):
            pass

        @allure.step("测试数据清理:")
        def fin():
            pass              
        request.addfinalizer(fin)
        return 

    @allure.title("{case}")
    @allure.link("https://yapi.dream-sports.cn/project/423/interface/api/17315")
    @pytest.mark.author('pytest.generator')
    @pytest.mark.datafile('API/data/control/test_uploads.yaml')
    def test_uploads(self, env, inputs, requests, expectation, case):
        with allure.step(case):
            response = requests.request(env, inputs)

        with allure.step("校验结果"):
            assert response['code'] == expectation['response']['code']
            free_compare(response, expectation)



