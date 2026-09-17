#!/usr/bin/env python
# -*- coding:utf-8 -*-

"""
@Time: 2025-09-25 18:07:49
@Author: pytest generator
@Doc: https://yapi.dream-sports.cn/project/423/interface/api/17384
"""

import logging
from pprint import pprint
import allure
import pytest
from pytest_helper.assertions import free_compare, soft_assert, result_compare


class TestCameraStartsport(object):

    @pytest.fixture(scope="class", autouse=True)
    def prepare(self, request, env, mysql, requests):
        with allure.step("测试数据准备:"):
            pass

        @allure.step("测试数据清理:")
        def fin():
            pass
        request.addfinalizer(fin)
        return 

    @allure.title("起点摄像头——开始运动")
    @allure.link("https://yapi.dream-sports.cn/project/423/interface/api/17384")
    @pytest.mark.author('pytest.generator')
    @pytest.mark.datafile('API/data/items/test_camera_startsport.yaml')
    def test_camera_startsport(self, env, inputs, requests, expectation, case):
        with allure.step(case):
            response = requests.request(env, inputs)

        with allure.step("校验结果"):
            assert response['code'] == expectation['response']['code']
            free_compare(response, expectation)


