#!/usr/bin/env python
# coding:utf-8
"""
8点位1分钟跳绳·黄金素材回放测试（多人并发识别基准用例）

素材：双脚跳绳.mp4（真实现场 8 点位同测，1280x720@30fps，60.4s）
基准：Log/golden/双脚跳绳.json（OSD 当次成绩 125/138/102/115/127/153/139/138 -> 1726）

流程：配置回放时间段 → 清日志 → 重启摄像头 → APP发令 → 采日志 → 成绩比对 golden
前置：
  1. 视频已上传 replay 服务器（host.replay）
  2. 摄像头已切跳绳项目并配好 8 点位（setArea / APP 端完成）
  3. adb 仅连接测试模拟器 emulator-5554（勿裸连，防止误操作用户设备）
"""
import datetime
from pathlib import Path
from time import sleep

import allure
import pytest
from pytest_helper.assertions import free_compare

from Log.osd_score_reader import load_golden

# ---- 素材时间轴（视频内 OSD 时间，北京时间；UTC 时间轴需换算，见 YAML 注释）----
ITEM = 'rope'
GOLDEN_VIDEO = '双脚跳绳'
T_SPORT = 60                    # 项目时长：1 分钟
startTime = '20260910t095624z'      # 视频起点
startsportTime = '20260910t095625z'  # 发令点（OSD 计数起点）
endTime = '20260910t095726z'        # 视频终点

# 成绩比对容差：每路 ±2 个
TOLERANCE = 2

# 教学屏 APP（仅连接测试模拟器，遵守 adb 设备约束）
DEVICE_URI = "Android:///emulator-5554"
APP_PACKAGE = "com.dreamsport.aicamera.client"


@allure.feature('跳绳8点位回放测试')
@allure.story('黄金素材-多人并发识别')
class TestRope8Golden(object):

    logStartTime = None
    logEndTime = None
    time_interval = None
    time_interval_2 = None
    t2 = None

    @allure.title("{case}, 配置摄像头rtsp回放时间段(8点位跳绳黄金素材)")
    @pytest.mark.datafile('E2E/data/test_updateRtspSettings_rope8_20260910.yaml')
    def test_updateRtspSettings(self, env, inputs, requests, expectation, case,
                                e2e_time_helper):
        with allure.step("计算时间间隔"):
            time_info = e2e_time_helper.calculate_time_intervals(
                startTime, startsportTime, endTime)
            TestRope8Golden.t2 = time_info['t2']
            TestRope8Golden.time_interval = time_info['time_interval']
            TestRope8Golden.time_interval_2 = time_info['time_interval_2']
            TestRope8Golden.logStartTime = time_info['logStartTime']
            TestRope8Golden.logEndTime = time_info['logEndTime']

        with allure.step(case):
            inputs['json']['startTime'] = startTime
            inputs['json']['endTime'] = endTime
            response = requests.request(env, inputs)
        with allure.step("校验结果"):
            free_compare(response, expectation)

    @allure.title("清理设备上的日志文件")
    def test_delete_logs(self, env, e2e_log_manager):
        e2e_log_manager.delete_adb_logs(env)
        camera_ip = env['ssh_host']
        e2e_log_manager.delete_ssh_logs(env, remote_host=camera_ip)

    @allure.title("通过SSH重启摄像头")
    def test_ssh_reboot(self, env, e2e_device_manager):
        e2e_device_manager.ssh_reboot(env, [env['ssh_host']])

    @allure.title("加载成绩基准(golden)")
    def test_load_golden(self):
        golden = load_golden(GOLDEN_VIDEO)
        assert len(golden['scores']) == 8, "golden 必须为 8 路成绩"
        allure.attach(str(golden), "OSD当次成绩基准",
                      allure.attachment_type.TEXT)
        TestRope8Golden.golden = golden

    @allure.title("APP操作｜发令并等待运动结束")
    def test_click_start_button(self, e2e_device_manager, project_root):
        # 等待视频播到发令点（重启耗时 t0 + 视频头到发令 t1）
        if TestRope8Golden.time_interval:
            sleep(TestRope8Golden.time_interval)

        from airtest.core.api import connect_device, start_app, touch, snapshot
        with allure.step(f"连接测试设备 {DEVICE_URI}"):
            # 显式指定 emulator-5554，禁止裸连（多设备在线会误操作用户设备）
            dev = connect_device(DEVICE_URI)
            width, height = dev.get_current_resolution()
            start_app(APP_PACKAGE)
            sleep(1)

        with allure.step("点击发令按钮"):
            # 右上角进入 + 底部中央发令（与现网 APP 交互一致）
            touch((width - 50, 50))
            sleep(0.5)
            touch((width // 2 - 50, height - 50))

        with allure.step("等待运动结束"):
            wait_time = TestRope8Golden.t2 or (T_SPORT + 3)
            sleep(wait_time)

        with allure.step("结束画面截图"):
            date_str = datetime.datetime.now().strftime("%Y%m%d")
            shot_dir = Path(project_root) / "allure-report" / "screenshot" / date_str
            shot_dir.mkdir(parents=True, exist_ok=True)
            snapshot(str(shot_dir / f"rope8_golden_{datetime.datetime.now():%Y%m%d%H%M%S}.png"))

    @allure.title("获取日志｜APP和摄像头")
    def test_get_log(self, env, e2e_log_manager, project_root):
        e2e_log_manager.get_adb_logs(env, project_root)
        e2e_log_manager.get_ssh_logs(env, project_root, remote_host=env['ssh_host'])

    @allure.title("成绩比对｜回放识别成绩 vs golden基准")
    def test_compare_scores(self, env, project_root):
        """比对口径：
        - golden.scores：素材录制当次摄像头 OSD 的 8 路成绩（基准）
        - 回放新成绩：从本次摄像头日志解析（TODO: 接入 Log/ 解析工具，
          参考 Log/analyze_camera_Latest.py 的成绩提取逻辑，按点位/人员归组）
        - 断言：每路 |新成绩 - 基准| <= TOLERANCE；同时应安排一次人工看视频
          数出 8 人真实成绩写入 golden.ground_truth，做三方比对定精度
        """
        golden = TestRope8Golden.golden
        # TODO: 日志解析出本次回放的 8 路成绩 replay_scores
        # replay_scores = parse_rope_scores_from_log(log_dir, logStartTime, logEndTime)
        # for i, (got, base) in enumerate(zip(replay_scores, golden['scores'])):
        #     assert abs(got - base) <= TOLERANCE, \
        #         f"点位{i+1}: 回放成绩{got} 与基准{base} 偏差超±{TOLERANCE}"
        pytest.skip("日志成绩解析待接入后启用比对；golden 基准已就绪: "
                    + str(golden['scores']))
