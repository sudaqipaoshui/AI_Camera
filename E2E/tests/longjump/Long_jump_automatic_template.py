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
import subprocess
import sys
import os
import time
import datetime
import traceback
from pathlib import Path
from time import sleep

import allure
import pytest
from pytest_helper.assertions import free_compare
from airtest.core.api import *

# 跳远
count = 24
item = 'long jump'
startTime =       '20260109_165600'
startsportTime =  '20260109_165600'
endTime =         '20260109_171000'


@allure.feature('跳远全流程自动化测试')
@allure.story('立定跳远')
class TestUpdateRtspSettings(object):
    # 时间相关类变量（由test_updateRtspSettings设置）
    logStartTime = None
    logEndTime = None
    time_interval = None
    time_interval_2 = None
    t2 = None
 
    @pytest.fixture(scope="class", autouse=True)
    def prepare(self):
        pass

    @allure.title("{case}, 配置起点和终点摄像头的rtsp回放时间段")
    @pytest.mark.datafile('E2E/data/test_updateRtspSettings_ry_175.yaml')
    def test_updateRtspSettings(self, env, inputs, requests, expectation, case, e2e_time_helper):
        """配置RTSP设置并计算时间间隔"""
        with allure.step("计算时间间隔"):
            time_info = e2e_time_helper.calculate_time_intervals(startTime, startsportTime, endTime)
            # 设置类变量
            TestUpdateRtspSettings.t2 = time_info['t2']
            TestUpdateRtspSettings.time_interval = time_info['time_interval']
            TestUpdateRtspSettings.time_interval_2 = time_info['time_interval_2']
            TestUpdateRtspSettings.logStartTime = time_info['logStartTime']
            TestUpdateRtspSettings.logEndTime = time_info['logEndTime']

        with allure.step(case):
            # inputs['json']['host'] = '192.168.3.65'
            # inputs['json']['play_channel'] = 5
            inputs['json']['startTime'] = startTime
            inputs['json']['endTime'] = endTime
            response = requests.request(env, inputs)
        with allure.step("校验结果"):
            free_compare(response, expectation)

    @allure.title("清理设备上的日志文件")
    def test_delete_logs(self, env, e2e_log_manager):
        """使用插件删除设备日志"""
        e2e_log_manager.delete_adb_logs(env)
        e2e_log_manager.delete_ssh_logs(env)

    @allure.title("通过SSH重启摄像头")
    def test_ssh_reboot(self, env, e2e_device_manager):
        """使用插件重启设备"""
        devices = ['192.168.3.29']
        e2e_device_manager.ssh_reboot(env, devices)     

    @allure.title("APP操作｜等待检录完成 > 发令 > 结束测试")
    def test_click_start_button(self, e2e_device_manager, project_root):
        """通过Airtest自动化点击发令按钮（使用插件）"""
        e2e_device_manager.run_sport_test(
            project_root=project_root,
            app_package="com.dreamsport.aicamera.client",
            time_interval=TestUpdateRtspSettings.time_interval,
            t2=TestUpdateRtspSettings.t2,
            time_interval_2=TestUpdateRtspSettings.time_interval_2
        )

    @allure.title("获取日志｜APP和摄像头")
    def test_get_log(self, env, e2e_log_manager, project_root):

        from E2E.pytest_helper.e2e_helper import E2ELogManager
        E2ELogManager.get_adb_logs(env, project_root)
        camera_ip = '192.168.3.29'
        E2ELogManager.get_ssh_logs(env, project_root, remote_host=camera_ip)

    @allure.title("分析日志")
    def test_analyze_log(self, env, e2e_log_manager, project_root):
        try:
            # 动态获取项目根目录（根据实际目录层级调整parents[n]）
            project_root = Path(__file__).resolve().parents[3]
            allure.attach(f"项目根目录：{project_root}", "基础路径信息")

            # 分析脚本路径
            analyze_script = project_root / "Log" / "long_jump" / "camera_latest.py"
            if not analyze_script.exists():
                raise FileNotFoundError(f"分析脚本不存在: {analyze_script}")
            allure.attach(f"分析脚本路径：{analyze_script}", "基础路径信息")

            # 日志目录（当日日期格式：YYYYMMDD）
            date_str = datetime.datetime.now().strftime("%Y%m%d")
            log_root_dir = project_root / "Log" / date_str
            allure.attach(f"当日日志根目录：{log_root_dir}", "基础路径信息")

            # 查找相机日志目录
            camera_log_dir = log_root_dir / "camera"
            if not camera_log_dir.exists() or not camera_log_dir.is_dir():
                raise FileNotFoundError(
                    f"相机日志目录不存在: {camera_log_dir}，请先运行 test_get_log 获取日志"
                )

            # 查找最新相机日志文件（.log）
            camera_log_files = list(camera_log_dir.glob("*.log"))
            if not camera_log_files:
                raise FileNotFoundError(f"在 {camera_log_dir} 目录下未找到相机日志文件")

            # 按修改时间排序，取最新的日志文件
            camera_log_file = max(camera_log_files, key=lambda f: f.stat().st_mtime)
            log_info = f"✅ 找到最新相机日志文件: {camera_log_file}"
            print(log_info)
            allure.attach(log_info, "日志文件定位结果")

            # ========== 执行分析脚本核心逻辑 ==========
            with allure.step("构造并执行日志分析命令"):
                cmd = [
                    "python3",
                    str(analyze_script),
                    str(camera_log_file),
                    #env需要修改为纯IP
                    env
                ]
                cmd_str = " ".join(cmd)
                print(f"执行命令：{cmd_str}")
                allure.attach(cmd_str, "执行命令", allure.attachment_type.TEXT)

                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    encoding="utf-8",
                    timeout=300,
                )

            # ========== 校验执行结果并记录 ==========
            with allure.step("校验分析脚本执行结果"):
                allure.attach(result.stdout, "脚本标准输出", allure.attachment_type.TEXT)
                allure.attach(result.stderr, "脚本标准错误", allure.attachment_type.TEXT)
                allure.attach(f"返回码：{result.returncode}", "执行状态")

                print("\n=== 脚本执行输出 ===")
                print(f"标准输出：\n{result.stdout}")
                if result.stderr:
                    print(f"标准错误：\n{result.stderr}")

                if result.returncode != 0:
                    raise RuntimeError(
                        f"日志分析脚本执行失败！返回码：{result.returncode}，错误信息：{result.stderr}"
                    )
                print("✅ 日志分析脚本执行成功！")

        # ==========异常捕获与处理 ==========
        except subprocess.TimeoutExpired:
            error_msg = "日志分析脚本执行超时（超过300秒）"
            print(error_msg)
            allure.attach(error_msg, "执行异常", allure.attachment_type.TEXT)
            raise RuntimeError(error_msg)

        except FileNotFoundError as e:
            error_msg = f"文件不存在异常：{str(e)}"
            print(error_msg)
            allure.attach(error_msg, "执行异常", allure.attachment_type.TEXT)
            raise

        except RuntimeError as e:
            error_msg = f"执行失败：{str(e)}"
            print(error_msg)
            allure.attach(error_msg, "执行异常", allure.attachment_type.TEXT)
            raise

        except Exception as e:
            # 捕获所有异常，记录完整堆栈信息
            error_msg = f"未知异常：{str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            allure.attach(error_msg, "未知异常详情", allure.attachment_type.TEXT)
            raise