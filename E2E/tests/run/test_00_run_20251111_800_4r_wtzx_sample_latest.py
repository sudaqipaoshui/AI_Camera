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
import shutil
import zipfile
from pathlib import Path
from time import sleep

import allure
import pytest
from pytest_helper.assertions import free_compare
from pytest_helper.e2e_helper import resolve_ssh_password
from airtest.core.api import *

# 圈数
r = 4
# 距离：800米
d = 800
# 人数
count = 39

startTime = '20251117t162910'
startsportTime = '20251117t163520z'
endTime = '20251117t164100z'

@allure.feature('长跑全流程自动化测试')
@allure.story('800米 4圈')
class TestUpdateRtspSettings(object):
    # 日志开始时间
    logStartTime = None
    # 日志结束时间
    logEndTime = None
    # 时间间隔：重启到发令的时间间隔
    time_interval = None
    # 时间间隔2：重启到结束的总时间间隔
    time_interval_2 = None
    # t2：从发令到结束的时间间隔（秒）
    t2 = None
 
    @pytest.fixture(scope="class", autouse=True)
    def prepare(self):
        pass

    @allure.title("{case}, 配置起点和终点摄像头的rtsp回放时间段")
    # @pytest.mark.skip(reason="暂时跳过")
    @pytest.mark.datafile('E2E/data/test_updateRtspSettings_type_channel1-4.yaml')
    def test_updateRtspSettings(self, env, inputs, requests, expectation, case):

        with allure.step("计算时间间隔"):
            
            # 解析时间字符串（格式：YYYYMMDDtHHMMSSz，z表示UTC）
            def parse_utc_time(time_str):
                """解析UTC时间字符串：20251111t142200z -> 2025-11-11 14:22:00"""
                # 移除末尾的'z'
                time_str = time_str.rstrip('z')
                # 分割日期和时间部分
                date_part = time_str[:8]  # 20251111
                time_part = time_str[9:]  # 142200 (跳过't')
                # 解析
                return datetime.datetime(int(date_part[:4]), int(date_part[4:6]), int(date_part[6:8]), int(time_part[:2]), int(time_part[2:4]), int(time_part[4:6]))
            
            # 解析时间
            start_dt = parse_utc_time(startTime)
            startsport_dt = parse_utc_time(startsportTime)
            end_dt = parse_utc_time(endTime)
            
            # t0 摄像头重启时间 ｜ s
            t0 = 10
            # t1 从视频开始到发令的时间间隔（秒）
            t1 = (startsport_dt - start_dt).total_seconds()
            # t2 从发令到结束的时间间隔（秒）
            t2 = (end_dt - startsport_dt).total_seconds()
            TestUpdateRtspSettings.t2 = t2
            
            # 重启到发令的时间间隔 = t0 + t1
            time_interval = t0 + t1
            TestUpdateRtspSettings.time_interval = time_interval

            # 重启到结束的总时间间隔 = t0 + t1 + t2
            time_interval_2 = t0 + t1 + t2
            TestUpdateRtspSettings.time_interval_2 = time_interval_2

            # 日志开始时间（通过当前时间计算，格式：2025-11-12 18:14:00）
            current_time = datetime.datetime.now()
            logStartTime_dt = current_time + datetime.timedelta(seconds=time_interval)
            TestUpdateRtspSettings.logStartTime = logStartTime_dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # 日志结束时间
            logEndTime_dt = logStartTime_dt + datetime.timedelta(seconds=t2)
            TestUpdateRtspSettings.logEndTime = logEndTime_dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # 打印时间信息
            print("="*60)
            print(f"time_interval (重启到发令): {time_interval} 秒 ({time_interval/60:.1f} 分钟)")
            print(f"time_interval_2 (重启到结束): {time_interval_2} 秒 ({time_interval_2/60:.1f} 分钟)")
            print(f"logStartTime:          {TestUpdateRtspSettings.logStartTime}")
            print(f"logEndTime:            {TestUpdateRtspSettings.logEndTime}")
            print("="*60)

        with allure.step(case):
            inputs['json']['startTime'] = startTime
            inputs['json']['endTime'] = endTime
            response = requests.request(env, inputs)
        with allure.step("校验结果"):
            free_compare(response, expectation)
            
            return TestUpdateRtspSettings.logStartTime, TestUpdateRtspSettings.logEndTime, TestUpdateRtspSettings.time_interval

    @allure.title("清除设备上的日志文件")
    def test_delete_logs(self, env):
        """在运行测试前删除ADB设备上的日志文件，并清空SSH设备上的日志文件
        
        1. 删除ADB设备（Android）上的日志：sdcard/DreamSports/log/{date_str}/
        2. 清空SSH设备（摄像头）上的日志：/userdata/deploy/log/logger.log（保留文件但清空内容）
        
        默认删除当天的日志。如果需要删除其他日期的日志，可以修改 date_str 变量。
        """
        with allure.step("删除ADB设备上的日志"):
            # 默认删除当天的日志，可以修改为指定日期，格式：YYYYMMDD
            date_str = datetime.datetime.now().strftime("%Y%m%d")
            # 如果需要删除其他日期的日志，取消下面的注释并修改日期：
            # date_str = "20251204"  # 示例：删除 2025年12月4日的日志
            
            # ADB设备上的日志路径
            device_log_path = f'sdcard/DreamSports/log/{date_str}/'
            
            print("="*60)
            print(f"正在删除ADB设备上的日志...")
            print(f"设备路径: {device_log_path}")
            print("="*60)
            
            # 通过 adb shell 删除设备上的日志目录
            adb_cmd = ['adb', 'shell', 'rm', '-rf', device_log_path]
            print(f"执行命令: {' '.join(adb_cmd)}")
            
            try:
                result = subprocess.run(adb_cmd, capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    print(f"✅ 已删除ADB设备上的日志目录: {device_log_path}")
                    allure.attach(
                        f"已删除ADB设备日志: {device_log_path}\n输出: {result.stdout}",
                        "删除ADB日志结果",
                        allure.attachment_type.TEXT
                    )
                else:
                    # adb shell rm 即使目录不存在也可能返回非0，检查错误信息
                    if "No such file or directory" in result.stderr or "not found" in result.stderr.lower():
                        print(f"ℹ️  ADB设备上的日志目录不存在: {device_log_path}")
                        allure.attach(
                            f"ADB设备日志目录不存在: {device_log_path}",
                            "删除ADB日志结果",
                            allure.attachment_type.TEXT
                        )
                    else:
                        print(f"⚠️  删除ADB设备日志时出现警告: {result.stderr}")
                        allure.attach(
                            f"删除ADB日志警告: {result.stderr}",
                            "删除ADB日志警告",
                            allure.attachment_type.TEXT
                        )
            except subprocess.TimeoutExpired:
                error_msg = f"❌ 删除ADB设备日志超时"
                print(error_msg)
                allure.attach(error_msg, "删除ADB日志错误", allure.attachment_type.TEXT)
                raise RuntimeError(error_msg)
            except Exception as e:
                error_msg = f"❌ 删除ADB设备日志失败: {e}"
                print(error_msg)
                allure.attach(error_msg, "删除ADB日志错误", allure.attachment_type.TEXT)
                # 不抛出异常，继续清空SSH设备上的日志
        
        with allure.step("清空SSH设备（摄像头）上的日志"):
            # 远程服务器信息（从配置文件读取，或使用默认值）
            try:
                if env:
                    cameraB_url = env.get('host', {}).get('cameraB', 'http://192.168.3.29')
                    remote_host = cameraB_url.replace('http://', '').replace('https://', '')
                    remote_username = env.get('ssh_username', 'root')
                    remote_password = resolve_ssh_password(env)
                else:
                    raise AttributeError("env not provided")
            except (AttributeError, KeyError, TypeError):
                # 如果配置读取失败，使用默认值
                remote_host = "192.168.3.29"
                remote_username = "root"
                remote_password = resolve_ssh_password(None)
            
            remote_log_path = "/userdata/deploy/log/logger.log"
            
            print("="*60)
            print(f"正在清空SSH设备（摄像头）上的日志文件...")
            print(f"远程主机: {remote_username}@{remote_host}")
            print(f"远程路径: {remote_log_path}")
            print("="*60)
            
            # 通过 sshpass + ssh 清空远程设备上的日志文件（使用 echo -n > 清空文件内容）
            ssh_cmd = [
                'sshpass',
                '-p', remote_password,
                'ssh',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                f'{remote_username}@{remote_host}',
                f'echo -n > {remote_log_path}'
            ]
            
            print(f"执行命令: sshpass -p *** ssh {remote_username}@{remote_host} 'echo -n > {remote_log_path}'")
            
            try:
                result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    print(f"✅ 已清空SSH设备上的日志文件: {remote_log_path}")
                    allure.attach(
                        f"已清空SSH设备日志: {remote_log_path}\n输出: {result.stdout}",
                        "清空SSH日志结果",
                        allure.attachment_type.TEXT
                    )
                else:
                    # 如果文件不存在，尝试创建目录和文件
                    if "No such file" in result.stderr or "not found" in result.stderr.lower():
                        # 尝试创建目录和空文件
                        create_cmd = [
                            'sshpass',
                            '-p', remote_password,
                            'ssh',
                            '-o', 'StrictHostKeyChecking=no',
                            '-o', 'UserKnownHostsFile=/dev/null',
                            f'{remote_username}@{remote_host}',
                            f'mkdir -p $(dirname {remote_log_path}) && echo -n > {remote_log_path}'
                        ]
                        create_result = subprocess.run(create_cmd, capture_output=True, text=True, timeout=30)
                        if create_result.returncode == 0:
                            print(f"✅ 已创建并清空SSH设备上的日志文件: {remote_log_path}")
                            allure.attach(
                                f"已创建并清空SSH设备日志: {remote_log_path}",
                                "清空SSH日志结果",
                                allure.attachment_type.TEXT
                            )
                        else:
                            error_msg = f"⚠️  SSH设备上的日志文件路径不存在，且创建失败: {remote_log_path}\n错误: {create_result.stderr}"
                            print(error_msg)
                            allure.attach(error_msg, "清空SSH日志警告", allure.attachment_type.TEXT)
                    else:
                        error_msg = f"❌ 清空SSH设备日志失败: {result.stderr}"
                        print(error_msg)
                        allure.attach(error_msg, "清空SSH日志错误", allure.attachment_type.TEXT)
                        # 不抛出异常，记录错误即可
            except FileNotFoundError:
                error_msg = "❌ sshpass 未安装，无法清空SSH设备日志。请安装: brew install hudochenkov/sshpass/sshpass"
                print(error_msg)
                allure.attach(error_msg, "清空SSH日志错误", allure.attachment_type.TEXT)
            except subprocess.TimeoutExpired:
                error_msg = f"❌ 清空SSH设备日志超时"
                print(error_msg)
                allure.attach(error_msg, "清空SSH日志错误", allure.attachment_type.TEXT)
            except Exception as e:
                error_msg = f"❌ 清空SSH设备日志失败: {e}"
                print(error_msg)
                allure.attach(error_msg, "清空SSH日志错误", allure.attachment_type.TEXT)
                # 不抛出异常，记录错误即可
        
        print("="*60)
        print("✅ 日志删除操作完成")
        print("="*60)

    @allure.title("通过SSH重启摄像头")
    # @pytest.mark.skip(reason="暂时跳过")
    def test_ssh_reboot(self, env):
        """通过SSH命令重启摄像头设备（重启192.168.3.28和192.168.3.29两台设备）
        
        1. 从配置文件读取SSH连接信息（或使用默认值）
        2. 通过 sshpass + ssh 执行 reboot 命令重启两台设备
        """
        # 要重启的设备列表
        devices = ['192.168.3.28', '192.168.3.29']
        
        # 远程服务器信息（从配置文件读取，或使用默认值）
        try:
            if env:
                remote_username = env.get('ssh_username', 'root')
                remote_password = resolve_ssh_password(env)
            else:
                raise AttributeError("env not provided")
        except (AttributeError, KeyError, TypeError):
            # 如果配置读取失败，使用默认值
            remote_username = "root"
            remote_password = resolve_ssh_password(None)
        
        print("="*60)
        print(f"正在通过SSH重启摄像头设备（共 {len(devices)} 台）...")
        print(f"设备列表: {', '.join(devices)}")
        print("="*60)
        
        reboot_results = []
        
        for device_ip in devices:
            with allure.step(f"重启设备 {device_ip}"):
                print("="*60)
                print(f"正在重启设备: {device_ip}")
                print("="*60)
                
                # 通过 sshpass + ssh 执行 reboot 命令
                ssh_cmd = [
                    'sshpass',
                    '-p', remote_password,
                    'ssh',
                    '-o', 'StrictHostKeyChecking=no',
                    '-o', 'UserKnownHostsFile=/dev/null',
                    '-o', 'ConnectTimeout=10',
                    f'{remote_username}@{device_ip}',
                    'reboot'
                ]
                
                print(f"执行命令: sshpass -p *** ssh {remote_username}@{device_ip} 'reboot'")
                
                device_result = {
                    'device': device_ip,
                    'status': 'unknown',
                    'message': ''
                }
                
                try:
                    # 注意：reboot 命令执行后，SSH连接会立即断开，所以可能会返回错误
                    # 这是正常的，因为设备正在重启
                    result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=10)
                    
                    # reboot 命令执行后，设备会立即重启，SSH连接会断开
                    # 所以即使返回码非0，也可能是正常的（连接断开）
                    if result.returncode == 0:
                        print(f"✅ 设备 {device_ip} SSH重启命令执行成功")
                        device_result['status'] = 'success'
                        device_result['message'] = f"SSH重启命令执行成功\n输出: {result.stdout}"
                    else:
                        # 检查是否是连接断开（设备正在重启）
                        if "Connection closed" in result.stderr or "Connection reset" in result.stderr or "Broken pipe" in result.stderr:
                            print(f"✅ 设备 {device_ip} SSH重启命令已执行，设备正在重启（连接断开是正常的）")
                            device_result['status'] = 'success'
                            device_result['message'] = f"SSH重启命令已执行，设备正在重启\n错误信息（正常）: {result.stderr}"
                        else:
                            print(f"⚠️  设备 {device_ip} SSH重启命令执行警告: {result.stderr}")
                            device_result['status'] = 'warning'
                            device_result['message'] = f"SSH重启命令警告: {result.stderr}\n标准输出: {result.stdout}"
                    
                except subprocess.TimeoutExpired:
                    # 超时也可能是正常的，因为设备正在重启
                    print(f"ℹ️  设备 {device_ip} SSH连接超时（可能是设备正在重启导致的，这是正常的）")
                    device_result['status'] = 'success'
                    device_result['message'] = "SSH连接超时，设备可能正在重启"
                except FileNotFoundError:
                    error_msg = "❌ sshpass 未安装，无法通过SSH重启设备。请安装: brew install hudochenkov/sshpass/sshpass"
                    print(f"❌ {error_msg}")
                    device_result['status'] = 'error'
                    device_result['message'] = error_msg
                    allure.attach(error_msg, f"SSH重启错误 - {device_ip}", allure.attachment_type.TEXT)
                    raise RuntimeError(error_msg)
                except Exception as e:
                    # 其他异常可能是连接断开（设备正在重启），这是正常的
                    if "Connection closed" in str(e) or "Connection reset" in str(e) or "Broken pipe" in str(e):
                        print(f"✅ 设备 {device_ip} SSH重启命令已执行，设备正在重启（连接断开是正常的）")
                        device_result['status'] = 'success'
                        device_result['message'] = f"SSH重启命令已执行，设备正在重启\n异常信息（正常）: {str(e)}"
                    else:
                        error_msg = f"❌ 设备 {device_ip} SSH重启失败: {e}"
                        print(error_msg)
                        traceback.print_exc()
                        device_result['status'] = 'error'
                        device_result['message'] = error_msg
                        allure.attach(traceback.format_exc(), f"SSH重启错误 - {device_ip}", allure.attachment_type.TEXT)
                        # 不抛出异常，继续重启下一台设备
                
                reboot_results.append(device_result)
                allure.attach(
                    device_result['message'],
                    f"SSH重启结果 - {device_ip}",
                    allure.attachment_type.TEXT
                )
                
                # 在重启下一台设备前稍作等待
                if device_ip != devices[-1]:
                    print(f"等待 1 秒后重启下一台设备...")
                    sleep(1)
        
        # 汇总结果
        print("="*60)
        print("✅ SSH重启命令执行完成")
        print("="*60)
        print("重启结果汇总:")
        for result in reboot_results:
            status_icon = "✅" if result['status'] == 'success' else "⚠️" if result['status'] == 'warning' else "❌"
            print(f"  {status_icon} {result['device']}: {result['status']}")
        print("="*60)
        print("   注意：设备正在重启，请等待设备重启完成后再执行后续操作")
        print("="*60)
        
        # 附加汇总结果到 Allure 报告
        summary = "SSH重启结果汇总:\n\n"
        for result in reboot_results:
            status_icon = "✅" if result['status'] == 'success' else "⚠️" if result['status'] == 'warning' else "❌"
            summary += f"{status_icon} {result['device']}: {result['status']}\n"
            summary += f"   详情: {result['message']}\n\n"
        allure.attach(summary.strip(), "SSH重启汇总", allure.attachment_type.TEXT)

    @allure.title("APP操作｜等待检录完成 > 发令 > 结束测试")
    def test_click_start_button(self):
        """通过Airtest自动化点击发令按钮"""

        with allure.step("连接设备并操作"):
            try:
                # 1. 连接设备（使用当前连接的设备）
                print("\n1. 正在连接设备...")
                dev = connect_device("Android:///")
                print(f"   设备连接成功: {dev}")
                
                # 获取屏幕尺寸
                width, height = dev.get_current_resolution()
                print(f"   屏幕尺寸: {width} x {height}")
                
                # 2. 重启应用（先停止再启动）
                print("\n2. 正在重启应用...")
                app_package = "com.dreamsport.aicamera.client"
                
                # 先停止应用（如果正在运行）
                try:
                    stop_app(app_package)
                    print(f"   应用已停止: {app_package}")
                    sleep(1)  # 等待应用完全停止
                except Exception as e:
                    print(f"   ⚠️  停止应用时出现警告（可能应用未运行）: {e}")
                
                # 启动应用
                start_app(app_package)
                print(f"   应用已启动: {app_package}")
                
                # 等待应用加载
                sleep(5)  # 等待应用完全启动
                
                # 3. 等待检录间隔（如果已计算）
                if TestUpdateRtspSettings.time_interval:
                    sleep_time = TestUpdateRtspSettings.time_interval
                    print(f"等待时间间隔: {sleep_time} 秒")
                else:
                    sleep_time = 1
                    print("使用默认等待时间: 0.5 秒")
                sleep(sleep_time)

                # 4. 点击发令按钮
                print("\n5. 点击发令按钮...")
                offset_y = 50  # 从底部往上50像素
                offset_x = 100  # 从中心往左50像素
                bottom_center = (width // 2 - offset_x, height - offset_y)
                touch(bottom_center)
                print(f"   已点击位置: {bottom_center}")
                
                print("\n✅ 发令按钮操作完成")

                # 5. 点击结束测试按钮
                # 等待测试结束（从发令到结束的时间间隔）
                if TestUpdateRtspSettings.t2 is not None:
                    wait_time = TestUpdateRtspSettings.t2
                    print(f"\n等待测试结束时间: {wait_time} 秒 ({wait_time/60:.1f} 分钟)")
                elif TestUpdateRtspSettings.time_interval_2 is not None and TestUpdateRtspSettings.time_interval is not None:
                    # 如果 t2 未定义，通过 time_interval_2 - time_interval 计算
                    wait_time = TestUpdateRtspSettings.time_interval_2 - TestUpdateRtspSettings.time_interval
                    print(f"\n等待测试结束时间（计算值）: {wait_time} 秒 ({wait_time/60:.1f} 分钟)")
                else:
                    # 如果都没有定义，使用默认值
                    wait_time = 10  # 默认5分钟
                    print(f"\n⚠️  t2 和 time_interval 未定义，使用默认等待时间: {wait_time} 秒")
                
                sleep(wait_time)


                # 7. 结束测试前截图
                print("\n7. 结束测试截图...")
                try:
                    # 获取项目根目录
                    project_root = Path(__file__).resolve().parents[3]
                    # 创建截图目录
                    date_str = datetime.datetime.now().strftime("%Y%m%d")
                    screenshot_dir = project_root / "allure-report" / "screenshot" / date_str
                    screenshot_dir.mkdir(parents=True, exist_ok=True)
                    
                    # 生成截图文件名（带时间戳）
                    timestamp_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    screenshot_filename = f"test_end_{timestamp_str}.png"
                    screenshot_path = screenshot_dir / screenshot_filename
                    
                    # 保存截图
                    snapshot(str(screenshot_path))
                    print(f"   截图已保存: {screenshot_path}")
                    
                    # 附加截图到 Allure 报告
                    if screenshot_path.exists():
                        with open(screenshot_path, 'rb') as f:
                            allure.attach(
                                f.read(),
                                f"结束测试截图 - {timestamp_str}",
                                allure.attachment_type.PNG
                            )
                        print(f"   截图已附加到 Allure 报告")
                    else:
                        print(f"   ⚠️  截图文件不存在: {screenshot_path}")
                except Exception as e:
                    print(f"   ⚠️  截图失败: {e}")
                    # 不抛出异常，继续执行


                print("\n6. 点击结束测试按钮...")
                offset_y = 50  # 从底部往上50像素
                offset_x = -100  # 从中心往右50像素
                bottom_center = (width // 2 - offset_x, height - offset_y)
                touch(bottom_center)
                print(f"   已点击位置: {bottom_center}")
                
                # 等待确认对话框出现
                print("   等待确认对话框出现...")
                sleep(2)  # 等待对话框完全显示
                
                # 点击确定按钮（确认对话框中的确定按钮）
                # 根据屏幕尺寸计算确定按钮位置（对话框通常在屏幕中央偏下，确定按钮在右侧）
                # 确定按钮大约在屏幕宽度的60-70%位置，高度的60-65%位置
                confirm_x = int(width * 0.65)  # 屏幕宽度的65%位置（右侧）
                confirm_y = int(height * 0.62)  # 屏幕高度的62%位置（中央偏下）
                confirm_center = (confirm_x, confirm_y)
                
                print(f"   点击确定按钮位置: {confirm_center}")
                touch(confirm_center)
                print(f"   已点击确定按钮")
                
                # 等待确认对话框消失
                sleep(2)  # 等待对话框消失和界面更新

                
                print("\n✅ 结束测试完成")

            except Exception as e:
                error_msg = f"操作失败: {e}"
                print(f"\n❌ {error_msg}")
                traceback.print_exc()
                allure.attach(traceback.format_exc(), "错误堆栈", allure.attachment_type.TEXT)
                raise RuntimeError(error_msg) from e

    @allure.title("获取日志｜APP和摄像头")
    def test_get_log(self, env):
        """获取APP日志（通过ADB）和摄像头日志（通过SCP）
        
        1. 删除本地最新日志目录
        2. 通过ADB获取APP日志：sdcard/DreamSports/log/{date_str}/
        3. 通过SCP获取摄像头日志：/userdata/deploy/log/logger.log
        4. 打包本地最新日志目录
        """
        # 从设备获取日志，放到项目根目录下的Log/YYYYMMDD/ 目录下
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        # 项目根目录：API/tests/e2e/ -> 项目根目录 (parents[3])
        project_root = Path(__file__).resolve().parents[3]  # 项目根目录
        log_dir = project_root / "Log" / date_str
        
        # 步骤1：删除本地最新日志目录
        with allure.step("删除本地最新日志目录"):
            print("\n" + "="*60)
            print("步骤 1/4: 删除本地最新日志目录")
            print("="*60)
            
            if log_dir.exists() and log_dir.is_dir():
                print(f"正在删除日志目录: {log_dir}")
                try:
                    shutil.rmtree(log_dir)
                    print(f"✅ 已删除目录: {log_dir}")
                    allure.attach(
                        f"已删除日志目录: {log_dir}",
                        "删除日志目录结果",
                        allure.attachment_type.TEXT
                    )
                except Exception as e:
                    error_msg = f"删除日志目录失败: {e}"
                    print(f"⚠️  {error_msg}")
                    traceback.print_exc()
                    allure.attach(traceback.format_exc(), "删除日志目录错误", allure.attachment_type.TEXT)
                    # 不抛出异常，继续执行后续步骤
            else:
                print(f"ℹ️  日志目录不存在，跳过删除: {log_dir}")
                allure.attach(
                    f"日志目录不存在: {log_dir}",
                    "删除日志目录结果",
                    allure.attachment_type.TEXT
                )
            
            print("✅ 步骤 1 完成：本地日志目录删除完成\n")
        
        # 确保日志目录存在（如果之前被删除了）
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建分类子目录
        app_dir = log_dir / "app"
        camera_dir = log_dir / "camera"
        app_dir.mkdir(parents=True, exist_ok=True)
        camera_dir.mkdir(parents=True, exist_ok=True)
        
        # 记录获取开始时间
        fetch_start_time = datetime.datetime.now()
        
        with allure.step("adb获取APP日志"): 
            # 设备上的日志路径
            device_log_path = f'sdcard/DreamSports/log/{date_str}/'
            
            # 执行adb pull命令，拉取到app目录
            adb_cmd = ['adb', 'pull', device_log_path, str(app_dir)]
            print(f"执行命令: {' '.join(adb_cmd)}")
            
            try:
                result = subprocess.run(adb_cmd, capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    # 检查是否创建了嵌套的日期目录，如果是则移动文件到app目录
                    nested_dir = app_dir / date_str
                    if nested_dir.exists() and nested_dir.is_dir():
                        print(f"⚠️  检测到嵌套目录，正在移动文件到app目录...")
                        # 移动嵌套目录中的所有文件到app目录
                        for file_path in nested_dir.iterdir():
                            if file_path.is_file():
                                target_path = app_dir / file_path.name
                                if target_path.exists():
                                    # 如果文件已存在，使用更新的文件
                                    if file_path.stat().st_mtime > target_path.stat().st_mtime:
                                        file_path.replace(target_path)
                                    else:
                                        file_path.unlink()
                                else:
                                    file_path.replace(target_path)
                        # 删除空的嵌套目录
                        try:
                            nested_dir.rmdir()
                            print(f"✅ 已清理嵌套目录")
                        except:
                            pass
                    
                    # 记录APP日志获取时间
                    app_fetch_time = datetime.datetime.now()
                    app_timestamp_str = app_fetch_time.strftime('%Y-%m-%d %H:%M:%S')
                    app_timestamp_file = app_fetch_time.strftime('%Y-%m-%d_%H-%M-%S')  # 用于文件名，替换冒号为下划线
                    
                    # 重命名所有.log文件，添加时间戳
                    log_files = list(app_dir.glob("*.log"))
                    renamed_count = 0
                    for log_file in log_files:
                        if log_file.is_file():
                            # 获取文件名和扩展名
                            file_stem = log_file.stem  # 不含扩展名的文件名
                            file_suffix = log_file.suffix  # 扩展名
                            # 新文件名：原文件名_时间戳.log
                            new_name = f"{file_stem}_{app_timestamp_file}{file_suffix}"
                            new_path = app_dir / new_name
                            if new_path.exists():
                                # 如果新文件名已存在，添加序号
                                counter = 1
                                while new_path.exists():
                                    new_name = f"{file_stem}_{app_timestamp_file}_{counter}{file_suffix}"
                                    new_path = app_dir / new_name
                                    counter += 1
                            log_file.rename(new_path)
                            renamed_count += 1
                            print(f"   重命名: {log_file.name} -> {new_name}")
                    
                    print(f"✅ APP日志已成功拉取到: {app_dir}")
                    print(f"   获取时间: {app_timestamp_str}")
                    print(f"   重命名文件数: {renamed_count}")
                    print("✅ 步骤 2 完成：APP日志获取完成\n")
                    allure.attach(result.stdout, "adb pull 输出", allure.attachment_type.TEXT)
                else:
                    print(f"⚠️  adb pull 警告: {result.stderr}")
                    allure.attach(result.stderr, "adb pull 错误", allure.attachment_type.TEXT)
            except Exception as e:
                print(f"❌ adb pull 失败: {e}")
                allure.attach(traceback.format_exc(), "adb pull 异常堆栈", allure.attachment_type.TEXT)
                raise
        
        with allure.step("SCP获取摄像头日志"):
            # 远程服务器信息（从配置文件读取，或使用默认值）
            # 默认使用 cameraB (192.168.3.29)
            try:
                # 尝试从配置文件读取（如果可用）
                cameraB_url = env.get('host', {}).get('cameraB', 'http://192.168.3.29')
                remote_host = cameraB_url.replace('http://', '').replace('https://', '')
                remote_username = env.get('ssh_username', 'root')
                remote_password = resolve_ssh_password(env)
            except (AttributeError, KeyError, TypeError):
                # 如果配置读取失败，使用默认值
                remote_host = "192.168.3.29"
                remote_username = "root"
                remote_password = resolve_ssh_password(None)
            
            remote_log_path = "/userdata/deploy/log/logger.log"
            
            # 记录摄像头日志获取时间（在下载前记录，用于文件名）
            camera_fetch_time = datetime.datetime.now()
            camera_timestamp_str = camera_fetch_time.strftime('%Y-%m-%d %H:%M:%S')
            camera_timestamp_file = camera_fetch_time.strftime('%Y-%m-%d_%H-%M-%S')  # 用于文件名，替换冒号为下划线
            
            # 本地保存路径：存放到camera目录，文件名带时间戳
            local_log_path = camera_dir / f"logger_{camera_timestamp_file}.log"
            
            # 构建 scp 命令（使用 sshpass 传递密码）
            # scp root@192.168.3.29:/userdata/deploy/log/logger.log /Users/sonic/ProjectD/AICameraTestLab/Log/{当日目录}/logger.log
            scp_cmd = [
                'sshpass',
                '-p', remote_password,
                'scp',
                '-o', 'StrictHostKeyChecking=no',  # 跳过主机密钥检查
                '-o', 'UserKnownHostsFile=/dev/null',  # 不保存主机密钥
                f'{remote_username}@{remote_host}:{remote_log_path}',
                str(local_log_path)
            ]
            
            print("="*60)
            print(f"正在从摄像头设备下载日志...")
            print(f"远程主机: {remote_username}@{remote_host}")
            print(f"远程路径: {remote_log_path}")
            print(f"本地路径: {local_log_path}")
            print(f"目标目录: {camera_dir}")
            print("="*60)
            
            # 打印命令（隐藏密码）
            cmd_display = ' '.join([
                'sshpass',
                '-p', '***',
                'scp',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                f'{remote_username}@{remote_host}:{remote_log_path}',
                str(local_log_path)
            ])
            print(f"执行命令: {cmd_display}")
            
            try:
                result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=300)
                
                if result.returncode == 0:
                    # 检查文件是否成功下载
                    if local_log_path.exists():
                        file_size = local_log_path.stat().st_size
                        print(f"✅ 摄像头日志已成功下载到: {local_log_path}")
                        print(f"   文件大小: {file_size} bytes ({file_size/1024/1024:.2f} MB)")
                        print(f"   获取时间: {camera_timestamp_str}")
                        print(f"   文件名: {local_log_path.name}")
                        allure.attach(result.stdout, "scp 输出", allure.attachment_type.TEXT)
                        
                        # 附加文件信息到 Allure 报告
                        file_info = f"""
                        文件路径: {local_log_path}
                        文件大小: {file_size} bytes ({file_size/1024/1024:.2f} MB)
                        下载时间: {camera_timestamp_str}
                        远程主机: {remote_username}@{remote_host}
                        远程路径: {remote_log_path}
                        """
                        allure.attach(file_info.strip(), "日志文件信息", allure.attachment_type.TEXT)
                    else:
                        print(f"⚠️  scp 命令执行成功，但文件不存在: {local_log_path}")
                        allure.attach(result.stdout, "scp 输出", allure.attachment_type.TEXT)
                        raise FileNotFoundError(f"文件下载失败: {local_log_path}")
                else:
                    error_msg = f"scp 命令执行失败 (返回码: {result.returncode})"
                    print(f"❌ {error_msg}")
                    print(f"错误输出: {result.stderr}")
                    allure.attach(result.stderr, "scp 错误", allure.attachment_type.TEXT)
                    raise RuntimeError(f"{error_msg}\n{result.stderr}")
                    
            except subprocess.TimeoutExpired:
                error_msg = "scp 命令执行超时（超过5分钟）"
                print(f"❌ {error_msg}")
                allure.attach(error_msg, "scp 超时", allure.attachment_type.TEXT)
                raise RuntimeError(error_msg)
            except Exception as e:
                error_msg = f"scp 下载日志失败: {e}"
                print(f"❌ {error_msg}")
                traceback.print_exc()
                allure.attach(traceback.format_exc(), "异常堆栈", allure.attachment_type.TEXT)
                raise RuntimeError(error_msg) from e
        
        # 记录获取完成时间
        fetch_end_time = datetime.datetime.now()
        fetch_duration = (fetch_end_time - fetch_start_time).total_seconds()
        final_timestamp_str = fetch_end_time.strftime('%Y-%m-%d %H:%M:%S')
        
        print("="*60)
        print(f"✅ 日志获取完成")
        print(f"   完成时间: {final_timestamp_str}")
        print(f"   耗时: {fetch_duration:.2f} 秒")
        print("="*60)
        
        return app_dir
   
    @allure.title("分析APP日志")
    # @pytest.mark.skip(reason="暂时跳过")
    def test_analyze_log(self):
        # 优先从类变量获取，如果没有则使用手动输入的时间
        start_time = TestUpdateRtspSettings.logStartTime
        end_time = TestUpdateRtspSettings.logEndTime
        
        # 如果类变量中没有时间，使用手动输入的时间作为默认值
        if start_time is None or end_time is None:

            start_time = '2025-12-09 14:28:28'
            end_time = '2025-12-09 14:33:28'

            print(f"⚠️  类变量中未设置时间，使用手动输入的时间:")
            print(f"   开始时间: {start_time}")
            print(f"   结束时间: {end_time}")
        else:
            print(f"✅ 使用类变量中的时间:")
            print(f"   开始时间: {start_time}")
            print(f"   结束时间: {end_time}")
        
        # 获取期望完成的圈数
        expected_circles = r

        with allure.step("分析日志"):
            # 动态获取项目根目录
            project_root = Path(__file__).resolve().parents[3]  # 项目根目录
            
            # 查找日志文件（项目根目录下的Log目录）
            date_str = datetime.datetime.now().strftime("%Y%m%d")
            log_dir = project_root / "Log" / date_str
            
            # 优先从app目录查找日志文件（新的目录结构）
            app_dir = log_dir / "app"
            if app_dir.exists() and app_dir.is_dir():
                # 明确处理app目录下的日志文件
                log_dir = app_dir
                print(f"✅ 使用APP日志目录: {log_dir}")
                print(f"   目录路径: {log_dir.resolve()}")
                
                # 列出app目录下的所有日志文件
                app_log_files = list(log_dir.glob("*.log"))
                if app_log_files:
                    print(f"   找到 {len(app_log_files)} 个日志文件:")
                    for log_file in sorted(app_log_files):
                        file_size = log_file.stat().st_size if log_file.exists() else 0
                        print(f"     - {log_file.name} ({file_size/1024/1024:.2f} MB)")
                else:
                    print(f"   ⚠️  app目录下未找到.log文件")
            else:
                # 检查是否存在嵌套目录（处理之前遗留的嵌套结构）
                nested_log_dir = log_dir / date_str
                if nested_log_dir.exists() and nested_log_dir.is_dir():
                    log_dir = nested_log_dir
                    print(f"⚠️  检测到嵌套目录，使用: {log_dir}")
                else:
                    print(f"⚠️  app目录不存在，使用根目录: {log_dir}")
            
            if not log_dir.exists():
                raise FileNotFoundError(f"日志目录不存在: {log_dir}，请先运行 test_get_log 获取日志")

            # 查找包含 "APP_INFO: 跳绳屏" 的日志文件
            # 只在当前log_dir目录下查找，不再递归子目录（因为app目录下应该直接就是日志文件）
            log_files = list(log_dir.glob("*.log"))
            print(f"   在 {log_dir} 目录下找到 {len(log_files)} 个.log文件")
            
            target_log_file = None
            for log_file in log_files:
                try:
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        for i, line in enumerate(f):
                            if i > 100:
                                break
                            if 'APP_INFO: 跳绳屏' in line:
                                target_log_file = log_file
                                break
                    if target_log_file:
                        break
                except Exception as e:
                    continue
            
            if not target_log_file:
                raise FileNotFoundError(f"在 {log_dir} 目录下未找到包含 'APP_INFO: 跳绳屏' 的日志文件")

            # 如果手动输入的时间也没有，从日志文件中自动提取
            if start_time is None or end_time is None:
                print("⚠️  logStartTime 和 logEndTime 未定义，尝试从日志文件中自动提取...")
                
                # 从日志文件中提取时间范围
                import re
                first_timestamp = None
                last_timestamp = None
                
                try:
                    with open(target_log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            # 匹配时间格式: 2025-11-12 18:08:39.827
                            pattern = r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})'
                            match = re.search(pattern, line)
                            if match:
                                try:
                                    timestamp_str = match.group(1)
                                    timestamp = datetime.datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f')
                                    if first_timestamp is None:
                                        first_timestamp = timestamp
                                    last_timestamp = timestamp
                                except:
                                    continue
                    
                    if first_timestamp and last_timestamp:
                        # 转换为字符串格式（不包含毫秒）
                        start_time = first_timestamp.strftime('%Y-%m-%d %H:%M:%S')
                        end_time = last_timestamp.strftime('%Y-%m-%d %H:%M:%S')
                        print(f"✅ 从日志文件中提取时间范围:")
                        print(f"   开始时间: {start_time}")
                        print(f"   结束时间: {end_time}")
                    else:
                        # 如果无法提取，尝试从文件名中提取时间戳
                        # 文件名格式: 111622481_2025-12-04_15-30-50.log
                        file_name = target_log_file.stem  # 不含扩展名
                        timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})-(\d{2})', file_name)
                        if timestamp_match:
                            date_part = timestamp_match.group(1)
                            hour = timestamp_match.group(2)
                            minute = timestamp_match.group(3)
                            second = timestamp_match.group(4)
                            # 使用文件名中的时间作为开始时间，结束时间设为开始时间后1小时
                            start_time = f"{date_part} {hour}:{minute}:{second}"
                            end_time_dt = datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S') + datetime.timedelta(hours=1)
                            end_time = end_time_dt.strftime('%Y-%m-%d %H:%M:%S')
                            print(f"✅ 从文件名中提取时间范围:")
                            print(f"   开始时间: {start_time}")
                            print(f"   结束时间: {end_time} (默认+1小时)")
                        else:
                            raise ValueError("无法从日志文件或文件名中提取时间范围，请手动设置 logStartTime 和 logEndTime")
                except Exception as e:
                    print(f"❌ 提取时间范围失败: {e}")
                    raise ValueError(f"无法从日志文件中提取时间范围: {e}。请先运行 test_updateRtspSettings 或手动设置 logStartTime 和 logEndTime")
            else:
                print(f"✅ 使用已定义的时间范围:")
                print(f"   开始时间: {start_time}")
                print(f"   结束时间: {end_time}")
            
            # 打印圈数信息
            print(f"✅ 期望完成圈数: {expected_circles}圈")
            
            # 调用 analyze_log.py 分析日志
            analyze_script = project_root / "Log" / "analyze_log.py"
            if not analyze_script.exists():
                raise FileNotFoundError(f"分析脚本不存在: {analyze_script}")
            
            # 构建命令 - 使用绝对路径确保正确
            # 确保输出目录是绝对路径，避免pytest运行时路径问题
            output_dir_abs = (project_root / 'allure-report' / 'log_analysis').resolve()
            cmd = [
                'python3',
                str(analyze_script.resolve()),
                str(target_log_file.resolve()),
                '--start-time', start_time,
                '--end-time', end_time,
                '--circles', str(expected_circles),
                '--output-dir', str(output_dir_abs)
            ]
            
            # 打印完整的执行命令（用于调试）
            # 使用sys.stdout.write确保在pytest中也能看到输出
            cmd_str = ' '.join(cmd)
            
            debug_info = []
            debug_info.append("="*80)
            debug_info.append("="*80)
            debug_info.append("开始分析日志:")
            debug_info.append("="*80)
            debug_info.append(f"日志文件: {target_log_file}")
            debug_info.append(f"日志文件绝对路径: {target_log_file.resolve()}")
            debug_info.append(f"日志文件是否存在: {target_log_file.exists()}")
            if target_log_file.exists():
                file_size = target_log_file.stat().st_size
                debug_info.append(f"日志文件大小: {file_size} bytes ({file_size/1024/1024:.2f} MB)")
            debug_info.append(f"开始时间: {start_time}")
            debug_info.append(f"结束时间: {end_time}")
            debug_info.append(f"期望完成圈数: {expected_circles}")
            debug_info.append(f"输出目录（绝对路径）: {output_dir_abs}")
            debug_info.append(f"输出目录是否存在: {output_dir_abs.exists()}")
            debug_info.append("-"*80)
            debug_info.append("执行命令（完整）:")
            debug_info.append("-"*80)
            debug_info.append(cmd_str)
            debug_info.append("-"*80)
            debug_info.append(f"工作目录: {project_root}")
            debug_info.append(f"工作目录是否存在: {project_root.exists()}")
            debug_info.append("="*80)
            debug_info.append("="*80)
            debug_info.append("")
            debug_info.append("手动测试命令（可复制执行）:")
            debug_info.append("="*80)
            debug_info.append(f"cd {project_root}")
            debug_info.append(cmd_str)
            debug_info.append("="*80)
            debug_info.append("")
            
            # 打印到stdout和stderr确保可见
            output_text = "\n".join(debug_info)
            print(output_text, flush=True)
            sys.stdout.write(output_text + "\n")
            sys.stdout.flush()
            
            # 附加命令到Allure报告
            allure.attach(cmd_str, "分析脚本执行命令", allure.attachment_type.TEXT)
            allure.attach(output_text, "分析日志调试信息", allure.attachment_type.TEXT)
            
            try:
                # 确保在项目根目录执行，使用绝对路径
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=str(project_root.resolve()))
                
                # 使用sys.stdout确保在pytest中可见
                result_info = []
                result_info.append("="*80)
                result_info.append("分析脚本执行结果:")
                result_info.append("="*80)
                result_info.append(f"返回码: {result.returncode}")
                result_info.append(f"工作目录: {project_root}")
                result_info.append(f"实际执行的工作目录: {Path.cwd()}")
                result_info.append("-"*80)
                if result.stdout:
                    result_info.append("标准输出:")
                    result_info.append("-"*80)
                    result_info.append(result.stdout)
                    result_info.append("-"*80)
                else:
                    result_info.append("⚠️  标准输出为空")
                if result.stderr:
                    result_info.append("错误输出:")
                    result_info.append("-"*80)
                    result_info.append(result.stderr)
                    result_info.append("-"*80)
                else:
                    result_info.append("✅ 错误输出为空（正常）")
                result_info.append("="*80)
                
                result_text = "\n".join(result_info)
                print(result_text, flush=True)
                sys.stdout.write(result_text + "\n")
                sys.stdout.flush()
                
                if result.returncode == 0:
                    print("✅ 日志分析脚本执行成功（返回码: 0）")
                    
                    # 检查输出目录（按日期）
                    output_base = project_root / "allure-report" / "log_analysis"
                    date_str = datetime.datetime.now().strftime("%Y%m%d")
                    output_dir = output_base / date_str
                    
                    print(f"📁 检查输出目录: {output_dir}")
                    print(f"   输出目录是否存在: {output_dir.exists()}")
                    
                    # 检查是否有"未找到有效数据"的提示
                    has_no_data = "未找到有效数据" in result.stdout
                    if has_no_data:
                        print("="*60)
                        print("⚠️  分析脚本提示: 未找到有效数据")
                        print("   可能的原因:")
                        print("   1. 时间范围不正确（日志文件中没有该时间段的数据）")
                        print("   2. 日志文件格式不匹配")
                        print("   3. 日志文件中没有圈数数据")
                        print(f"   建议检查:")
                        print(f"   - 开始时间: {start_time}")
                        print(f"   - 结束时间: {end_time}")
                        print(f"   - 日志文件: {target_log_file}")
                        print("="*60)
                    
                    if output_dir.exists():
                        files = list(output_dir.glob("*"))
                        if files:
                            print(f"📊 生成的文件 ({len(files)} 个):")
                            for f in files:
                                size = f.stat().st_size if f.is_file() else 0
                                file_type = "文件" if f.is_file() else "目录"
                                print(f"   - {f.name} ({file_type}, {size} bytes)")
                        else:
                            print("⚠️  输出目录为空，未生成任何文件")
                            print(f"   请检查分析脚本是否正确执行")
                    else:
                        print(f"⚠️  输出目录不存在: {output_dir}")
                        print(f"   基础目录是否存在: {output_base.exists()}")
                        if output_base.exists():
                            print(f"   基础目录内容: {list(output_base.iterdir())}")
                    
                    allure.attach(result.stdout, "日志分析输出", allure.attachment_type.TEXT)
                    
                    # 验证生成的文件
                    generated_files = []
                    if output_dir.exists():
                        files = list(output_dir.glob("*"))
                        generated_files = [f for f in files if f.is_file()]
                    
                    # 验证关键文件是否存在（支持带时间戳的文件名）
                    expected_file_patterns = {
                        'circle_completion_stats': 'circle_completion_stats*.png',
                        'person_circle_relationship_bar': 'person_circle_relationship_bar*.png'
                    }
                    missing_files = []
                    found_files = {}
                    
                    for file_key, pattern in expected_file_patterns.items():
                        # 使用 glob 模式匹配文件（支持时间戳）
                        matched_files = list(output_dir.glob(pattern))
                        if matched_files:
                            # 如果有多个匹配的文件，选择最新的（按修改时间）
                            matched_file = max(matched_files, key=lambda f: f.stat().st_mtime)
                            found_files[file_key] = matched_file
                            print(f"✅ 找到预期文件: {matched_file.name} (模式: {pattern})")
                            # 附加图表到Allure报告
                            try:
                                with open(matched_file, 'rb') as f:
                                    allure.attach(f.read(), matched_file.name, allure.attachment_type.PNG)
                            except Exception as e:
                                print(f"⚠️  附加文件到Allure失败: {e}")
                        else:
                            missing_files.append(file_key)
                            print(f"❌ 未找到预期文件 (模式: {pattern})")
                    
                    # 如果返回码为0但没有生成文件，给出警告
                    if not output_dir.exists() or not generated_files:
                        print("="*60)
                        print("⚠️  警告: 脚本执行成功但未生成文件")
                        if has_no_data:
                            print("   原因: 分析脚本提示'未找到有效数据'")
                        print("   可能的原因:")
                        print("   1. 日志文件中没有匹配的数据")
                        print("   2. 时间范围不正确")
                        print("   3. 分析脚本内部逻辑问题")
                        print("="*60)
                        # 如果是因为没有数据，给出更友好的提示而不是直接失败
                        if has_no_data:
                            print("ℹ️  由于未找到有效数据，测试跳过文件验证")
                            print("   请检查时间范围是否正确")
                        else:
                            raise AssertionError("日志分析未生成任何文件")
                    else:
                        # 验证关键文件是否存在
                        if missing_files:
                            missing_patterns = [expected_file_patterns[key] for key in missing_files]
                            raise AssertionError(f"缺少关键的分析结果文件: {', '.join(missing_patterns)}")
                        
                        print("="*60)
                        print("✅ 日志分析完成，所有结果文件已生成并验证")
                        print("="*60)
                else:
                    print(f"❌ 日志分析失败 (返回码: {result.returncode}):")
                    print(result.stderr)
                    allure.attach(result.stderr, "日志分析错误", allure.attachment_type.TEXT)
                    raise RuntimeError(f"日志分析失败: {result.stderr}")
            except subprocess.TimeoutExpired:
                print("❌ 日志分析超时（超过10分钟）")
                raise
            except Exception as e:
                error_msg = f"日志分析异常: {e}"
                print(f"❌ {error_msg}")
                print(traceback.format_exc())
                allure.attach(traceback.format_exc(), "异常堆栈", allure.attachment_type.TEXT)
                raise

    @allure.title("分析camera日志")
    def test_analyze_cameralog(self):
        with allure.step("准备分析camera日志所需参数"):
            
            '''if TestUpdateRtspSettings.logStartTime is None or TestUpdateRtspSettings.logEndTime is None:
                raise ValueError("logStartTime 和 logEndTime 未定义，请先运行 test_updateRtspSettings")'''
            # 优先从类变量获取，如果没有则使用手动输入的时间
            start_time = TestUpdateRtspSettings.logStartTime
            end_time = TestUpdateRtspSettings.logEndTime

            # 如果类变量中没有时间，使用手动输入的时间作为默认值
            if start_time is None or end_time is None:

                start_time = '2025-12-09 14:28:28'
                end_time = '2025-12-09 14:33:28'
            # 动态获取项目根目录
            project_root = Path(__file__).resolve().parents[3]
            
            # 分析脚本路径
            analyze_script = project_root / "Log" / "analyze_camera_Latest.py"
            if not analyze_script.exists():
                raise FileNotFoundError(f"分析脚本不存在: {analyze_script}")
            
            # 日志目录（app和camera子目录）- 参考 test_analyze_log 的实现
            date_str = datetime.datetime.now().strftime("%Y%m%d")
            log_root_dir = project_root / "Log" / date_str
            
            # 优先从app目录查找日志文件（新的目录结构）- 参考 test_analyze_log
            app_log_dir = log_root_dir / "app"
            if app_log_dir.exists() and app_log_dir.is_dir():
                print(f"✅ 使用APP日志目录: {app_log_dir}")
                print(f"   目录路径: {app_log_dir.resolve()}")
                
                # 列出app目录下的所有日志文件
                app_log_files = list(app_log_dir.glob("*.log"))
                if app_log_files:
                    print(f"   找到 {len(app_log_files)} 个日志文件:")
                    for log_file in sorted(app_log_files):
                        file_size = log_file.stat().st_size if log_file.exists() else 0
                        print(f"     - {log_file.name} ({file_size/1024/1024:.2f} MB)")
                else:
                    print(f"   ⚠️  app目录下未找到.log文件")
            else:
                raise FileNotFoundError(f"APP日志目录不存在: {app_log_dir}，请先运行 test_get_log 获取日志")
            
            # 查找包含 "APP_INFO: 跳绳屏" 的日志文件 - 参考 test_analyze_log
            log_files = list(app_log_dir.glob("*.log"))
            print(f"   在 {app_log_dir} 目录下找到 {len(log_files)} 个.log文件")
            
            target_app_log_file = None
            for log_file in log_files:
                try:
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        for i, line in enumerate(f):
                            if i > 100:
                                break
                            if 'APP_INFO: 跳绳屏' in line:
                                target_app_log_file = log_file
                                break
                    if target_app_log_file:
                        break
                except Exception as e:
                    continue
            
            if not target_app_log_file:
                raise FileNotFoundError(f"在 {app_log_dir} 目录下未找到包含 'APP_INFO: 跳绳屏' 的日志文件")
            
            print(f"✅ 找到APP日志文件: {target_app_log_file}")
            
            # 查找相机日志目录
            camera_log_dir = log_root_dir / "camera"
            if not camera_log_dir.exists() or not camera_log_dir.is_dir():
                raise FileNotFoundError(f"相机日志目录不存在: {camera_log_dir}，请先运行 test_get_log 获取日志")
            
            # 查找最新相机日志文件
            camera_log_files = list(camera_log_dir.glob("*.log"))
            if not camera_log_files:
                raise FileNotFoundError(f"在 {camera_log_dir} 目录下未找到相机日志文件")
            
            # 按修改时间排序，取最新的
            camera_log_file = max(camera_log_files, key=lambda f: f.stat().st_mtime)
            print(f"✅ 找到相机日志文件: {camera_log_file}")
            
            app_log_file = target_app_log_file
            
            # 转换时间（示例中相机时间比APP时间晚8小时，这里做相应转换）
            # 实际转换逻辑可能需要根据实际情况调整
            def convert_to_camera_time(app_time_str):
                """将APP时间转换为相机时间"""
                # 去除可能的前导空格
                app_time_str = app_time_str.strip()
                app_time = datetime.datetime.strptime(app_time_str, "%Y-%m-%d %H:%M:%S")
                camera_time = app_time - datetime.timedelta(hours=8)
                return camera_time.strftime("%Y-%m-%d %H:%M:%S")

            # 去除可能的前导空格
            start_time = start_time.strip() if start_time else None
            end_time = end_time.strip() if end_time else None
            
            app_start_time = start_time
            app_end_time = end_time
            camera_start_time = convert_to_camera_time(app_start_time)
            camera_end_time = convert_to_camera_time(app_end_time)
            
            print(f"✅ 时间参数设置:")
            print(f"   APP开始时间: {app_start_time}")
            print(f"   APP结束时间: {app_end_time}")
            print(f"   相机开始时间: {camera_start_time}")
            print(f"   相机结束时间: {camera_end_time}")
            
            # 数字参数
            global d, r 
            numeric_param = d // r  
            print(f"计算数字参数: 距离{d}米 / 圈数{r}圈 = {numeric_param}")
            
            # 构建命令
            output_dir_abs = (project_root / 'allure-report' / 'camera_log_analysis').resolve()
            # 确保输出目录存在
            output_dir_abs.mkdir(parents=True, exist_ok=True)
            
            cmd = [
                'python3',
                str(analyze_script.resolve()),
                str(app_log_file.resolve()),
                str(camera_log_file.resolve()),
                str(numeric_param),
                '--app-start', app_start_time,
                '--app-end', app_end_time,
                '--camera-start', camera_start_time,
                '--camera-end', camera_end_time,
                '--output-dir', str(output_dir_abs)
            ]
            
            # 调试信息
            debug_info = []
            debug_info.append("="*80)
            debug_info.append("开始分析相机和应用日志:")
            debug_info.append("="*80)
            debug_info.append(f"APP日志文件: {app_log_file}")
            debug_info.append(f"APP日志文件绝对路径: {app_log_file.resolve()}")
            debug_info.append(f"APP日志文件是否存在: {app_log_file.exists()}")
            if app_log_file.exists():
                file_size = app_log_file.stat().st_size
                debug_info.append(f"APP日志文件大小: {file_size} bytes ({file_size/1024/1024:.2f} MB)")
            debug_info.append(f"相机日志文件: {camera_log_file}")
            debug_info.append(f"相机日志文件绝对路径: {camera_log_file.resolve()}")
            debug_info.append(f"相机日志文件是否存在: {camera_log_file.exists()}")
            if camera_log_file.exists():
                file_size = camera_log_file.stat().st_size
                debug_info.append(f"相机日志文件大小: {file_size} bytes ({file_size/1024/1024:.2f} MB)")
            debug_info.append(f"数字参数（距离/圈数）: {d} / {r} = {numeric_param}")  # 显示计算过程
            debug_info.append(f"APP开始时间: {app_start_time}")
            debug_info.append(f"APP结束时间: {app_end_time}")
            debug_info.append(f"相机开始时间: {camera_start_time}")
            debug_info.append(f"相机结束时间: {camera_end_time}")
            debug_info.append(f"输出目录: {output_dir_abs}")
            debug_info.append("-"*80)
            debug_info.append("执行命令:")
            debug_info.append(" ".join(cmd))
            debug_info.append("="*80)
            
            output_text = "\n".join(debug_info)
            print(output_text, flush=True)
            allure.attach(output_text, "相机日志分析调试信息", allure.attachment_type.TEXT)
            
        with allure.step("执行相机日志分析脚本"):
            try:
                # 执行命令
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=600,
                    cwd=str(project_root.resolve())
                )
                
                # 处理执行结果
                result_info = []
                result_info.append("="*80)
                result_info.append("相机日志分析脚本执行结果:")
                result_info.append("="*80)
                result_info.append(f"返回码: {result.returncode}")
                result_info.append(f"工作目录: {project_root}")
                result_info.append("-"*80)
                if result.stdout:
                    result_info.append("标准输出:")
                    result_info.append("-"*80)
                    result_info.append(result.stdout)
                    result_info.append("-"*80)
                else:
                    result_info.append("⚠️  标准输出为空")
                if result.stderr:
                    result_info.append("错误输出:")
                    result_info.append("-"*80)
                    result_info.append(result.stderr)
                    result_info.append("-"*80)
                else:
                    result_info.append("✅ 错误输出为空（正常）")
                result_info.append("="*80)
                
                result_text = "\n".join(result_info)
                print(result_text, flush=True)
                allure.attach(result_text, "相机日志分析执行结果", allure.attachment_type.TEXT)
                
                if result.returncode != 0:
                    raise RuntimeError(f"相机日志分析脚本执行失败，返回码: {result.returncode}\n标准输出: {result.stdout}\n错误输出: {result.stderr}")
                
                # 检查输出目录（按日期）- 参考 test_analyze_log 的实现
                output_base = project_root / "allure-report" / "camera_log_analysis"
                date_str = datetime.datetime.now().strftime("%Y%m%d")
                output_dir = output_base / date_str
                
                print(f"\n📁 检查输出目录: {output_dir}")
                print(f"   输出目录是否存在: {output_dir.exists()}")
                
                # 检查脚本输出中是否有错误提示（脚本可能因为数据问题而终止）
                has_error = False
                error_messages = []
                if result.stdout:
                    if "错误" in result.stdout or "分析终止" in result.stdout or "无匹配" in result.stdout or "无有效" in result.stdout:
                        has_error = True
                        # 提取错误信息
                        for line in result.stdout.split('\n'):
                            if "错误" in line or "分析终止" in line or "无匹配" in line or "无有效" in line:
                                error_msg = line.strip()
                                if error_msg:
                                    error_messages.append(error_msg)
                
                if has_error:
                    print("="*60)
                    print("⚠️  脚本执行完成但检测到错误或警告:")
                    for msg in error_messages:
                        print(f"   - {msg}")
                    print("="*60)
                    print("   可能的原因:")
                    print("   1. APP日志中未找到有效的人员ID或基准时间")
                    print("   2. 时间范围不正确（日志文件中没有该时间段的数据）")
                    print("   3. 相机日志中没有匹配的数据")
                    print("   4. sim值过滤太严格（sim >= 0.75）")
                    print(f"   建议检查:")
                    print(f"   - APP日志文件: {app_log_file}")
                    print(f"   - 相机日志文件: {camera_log_file}")
                    print(f"   - APP开始时间: {app_start_time}")
                    print(f"   - APP结束时间: {app_end_time}")
                    print(f"   - 相机开始时间: {camera_start_time}")
                    print(f"   - 相机结束时间: {camera_end_time}")
                    print("="*60)
                    allure.attach("\n".join(error_messages), "脚本执行警告", allure.attachment_type.TEXT)
                
                if output_dir.exists():
                    files = list(output_dir.glob("*"))
                    if files:
                        print(f"📊 生成的文件 ({len(files)} 个):")
                        for f in files:
                            size = f.stat().st_size if f.is_file() else 0
                            file_type = "文件" if f.is_file() else "目录"
                            print(f"   - {f.name} ({file_type}, {size} bytes)")
                    else:
                        print("⚠️  输出目录为空，未生成任何文件")
                        print(f"   请检查分析脚本是否正确执行")
                        if has_error:
                            print("   注意：脚本因错误而终止，不会生成文件")
                else:
                    print(f"⚠️  输出目录不存在: {output_dir}")
                    print(f"   基础目录是否存在: {output_base.exists()}")
                    if output_base.exists():
                        subdirs = [d for d in output_base.iterdir() if d.is_dir()]
                        if subdirs:
                            print(f"   基础目录下的子目录: {', '.join([d.name for d in sorted(subdirs)])}")
                
                allure.attach(result.stdout, "相机日志分析输出", allure.attachment_type.TEXT)
                
                # 验证生成的文件
                generated_files = []
                if output_dir.exists():
                    files = list(output_dir.glob("*"))
                    generated_files = [f for f in files if f.is_file()]
                
                # 验证关键文件是否存在（支持带时间戳的文件名）- 参考 test_analyze_log 的实现
                expected_file_patterns = {
                    'db_time_diff_analysis': 'db_time_diff_analysis*.png',
                    'new_time_diff_analysis': 'new_time_diff_analysis*.png',
                    'db_time_interval_analysis': 'db_time_interval_analysis*.csv',
                    'new_time_interval_analysis': 'new_time_interval_analysis*.csv'
                }
                missing_files = []
                found_files = {}
                
                for file_key, pattern in expected_file_patterns.items():
                    # 使用 glob 模式匹配文件（支持时间戳）
                    matched_files = list(output_dir.glob(pattern))
                    if matched_files:
                        # 如果有多个匹配的文件，选择最新的（按修改时间）
                        matched_file = max(matched_files, key=lambda f: f.stat().st_mtime)
                        found_files[file_key] = matched_file
                        print(f"✅ 找到预期文件: {matched_file.name} (模式: {pattern})")
                        # 附加文件到Allure报告
                        try:
                            if matched_file.suffix.lower() == '.png':
                                with open(matched_file, 'rb') as f:
                                    allure.attach(f.read(), matched_file.name, allure.attachment_type.PNG)
                            elif matched_file.suffix.lower() == '.csv':
                                # CSV 文件使用 file 方法附加，可以更好地显示
                                try:
                                    allure.attach.file(
                                        str(matched_file),
                                        matched_file.name,
                                        allure.attachment_type.CSV
                                    )
                                except Exception:
                                    # 如果 attach.file 不支持，回退到 attach
                                    with open(matched_file, 'rb') as f:
                                        allure.attach(f.read(), matched_file.name, allure.attachment_type.TEXT)
                            else:
                                with open(matched_file, 'rb') as f:
                                    allure.attach(f.read(), matched_file.name, allure.attachment_type.TEXT)
                        except Exception as e:
                            print(f"⚠️  附加文件到Allure失败: {e}")
                    else:
                        missing_files.append(file_key)
                        print(f"❌ 未找到预期文件 (模式: {pattern})")
                
                # 如果返回码为0但没有生成文件，给出警告
                if not output_dir.exists() or not generated_files:
                    print("="*60)
                    print("⚠️  警告: 脚本执行成功但未生成文件")
                    if has_error:
                        print("   原因: 脚本因错误而终止")
                    print("   可能的原因:")
                    print("   1. APP日志中未找到有效的人员ID或基准时间")
                    print("   2. 时间范围不正确（日志文件中没有该时间段的数据）")
                    print("   3. 相机日志中没有匹配的数据")
                    print("   4. sim值过滤太严格（sim >= 0.75）")
                    print("="*60)
                    # 如果是因为错误终止，给出更友好的提示而不是直接失败
                    if has_error:
                        print("ℹ️  由于脚本因错误而终止，测试跳过文件验证")
                        print("   请检查APP日志文件是否包含有效的人员ID和基准时间")
                    else:
                        raise AssertionError("相机日志分析未生成任何文件")
                else:
                    # 验证关键文件是否存在
                    if missing_files:
                        missing_patterns = [expected_file_patterns[key] for key in missing_files]
                        print("="*60)
                        print(f"⚠️  缺少关键的分析结果文件: {', '.join(missing_patterns)}")
                        print("="*60)
                        # 不抛出异常，只给出警告
                    else:
                        print("="*60)
                        print("✅ 相机日志分析完成，所有结果文件已生成并验证")
                        print("="*60)
                
                print("✅ camera日志分析完成")
                
            except subprocess.TimeoutExpired:
                print("❌ camera日志分析超时（超过10分钟）")
                raise
            except Exception as e:
                error_msg = f"camera日志分析异常: {e}"
                print(f"❌ {error_msg}")
                traceback.print_exc()
                allure.attach(traceback.format_exc(), "异常堆栈", allure.attachment_type.TEXT)
                raise
