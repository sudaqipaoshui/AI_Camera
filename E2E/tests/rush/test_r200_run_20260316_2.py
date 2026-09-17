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
import allure
import pytest
from pytest_helper.assertions import free_compare

r = 4
d = 800
count = 39

startTime =       '20260316t135600z'
startsportTime =  '20260316t130000z'
endTime =         '20260316t141700z'

@allure.feature('长跑全流程自动化测试')
@allure.story(f'{d}米 {r}圈')
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
    @pytest.mark.datafile('E2E/data/test_updateRtspSettings_200_channel1-2.yaml')
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
        devices = ['192.168.3.30', '192.168.3.29']
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
        """获取APP日志（通过ADB）和摄像头日志（通过SCP）- 使用插件"""
        e2e_log_manager.get_all_logs(env, project_root)
   
    @allure.title("分析日志｜APP&Camera")
    def test_analyze_log(self, e2e_log_analyzer, project_root):
        """统一分析APP和Camera日志 - 使用插件"""
        result = e2e_log_analyzer.analyze_all_logs(
            project_root=project_root,
            app_start_time=TestUpdateRtspSettings.logStartTime,
            app_end_time=TestUpdateRtspSettings.logEndTime,
            expected_circles=r,
            distance=d,
            circles=r
            # fallback_start_time='2026-02-06 13:16:00',
            # fallback_end_time='2026-02-06 14:34:40'
        )
        if result.get('app_result') and 'stats' in result['app_result']:
            stats = result['app_result']['stats']
            print(f"\n📊 漏圈率统计:")
            print(f"   总人数: {stats['total_people']}")
            print(f"   完成{r}圈: {stats['completed_count']} 人")
            print(f"   漏圈率: {stats['missing_rate']:.2f}%")