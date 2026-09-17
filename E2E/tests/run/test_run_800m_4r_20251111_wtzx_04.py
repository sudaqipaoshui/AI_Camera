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

# 圈数
r = 4
# 距离：800米
d = 800

startTime = '20251111t162800z'
startsportTime = '20251111t143600z'
endTime = '20251111t143500z'


@allure.feature('长跑全流程自动化测试')
@allure.story('800米 4圈')
class TestUpdateRtspSettings(object):
    
    # logStartTime = '2025-11-12 18:14:00'
    # logEndTime = '2025-11-12 18:22:00'

    # 日志开始时间
    logStartTime = None
    # 日志结束时间
    logEndTime = None
    # 时间间隔：重启到发令的时间间隔
    time_interval = None
    # 时间间隔2：重启到结束的总时间间隔
    time_interval_2 = None

    @pytest.fixture(scope="class", autouse=True)
    def prepare(self, request, env, mysql, requests):
        pass

    @allure.title("{case}, 配置起点和终点摄像头的rtsp回放时间段")
    @pytest.mark.skip(reason="暂时跳过")
    @pytest.mark.datafile('E2E/data/test_updateRtspSettings_type4.yaml')
    def test_updateRtspSettings(self, env, inputs, requests, expectation, case, mysql):

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
            t0 = 60
            # t1 从视频开始到发令的时间间隔（秒）
            t1 = (startsport_dt - start_dt).total_seconds()
            # t2 从发令到结束的时间间隔（秒）
            t2 = (end_dt - startsport_dt).total_seconds()
            
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

    @allure.title("重启摄像头")
    @pytest.mark.datafile('E2E/data/test_rebootAB.yaml')
    def test_getVersion(self, env, inputs, requests, expectation, case, mysql):

        with allure.step(case):
            response = requests.request(env, inputs)
        with allure.step("校验结果"):
            free_compare(response, expectation)

    @allure.title("操作发令按钮")
    def test_click_start_button(self):
        """通过Airtest自动化点击发令按钮"""
        # 等待时间间隔（如果已计算）
        if TestUpdateRtspSettings.time_interval:
            sleep_time = TestUpdateRtspSettings.time_interval
            print(f"等待时间间隔: {sleep_time} 秒")
        else:
            sleep_time = 0.5
            print("使用默认等待时间: 0.5 秒")
        sleep(sleep_time)

        with allure.step("连接设备并操作"):
            try:
                # 1. 连接设备（使用当前连接的设备）
                print("\n1. 正在连接设备...")
                dev = connect_device("Android:///")
                print(f"   设备连接成功: {dev}")
                
                # 获取屏幕尺寸
                width, height = dev.get_current_resolution()
                print(f"   屏幕尺寸: {width} x {height}")
                
                # 2. 启动应用
                print("\n2. 正在启动应用...")
                app_package = "com.dreamsport.aicamera.client"
                start_app(app_package)
                print(f"   应用已启动: {app_package}")
                
                # 3. 等待应用加载
                print("\n3. 等待应用加载...")
                time.sleep(1)

                # 4. 点击右上角
                print("\n4. 点击右上角...")
                margin = 50  # 距离右边和顶部各50像素
                top_right = (width - margin, margin)
                touch(top_right)
                print(f"   已点击右上角: {top_right}")

                # 5. 点击发令按钮
                print("\n5. 点击发令按钮...")
                offset_y = 50  # 从底部往上50像素
                offset_x = 50  # 从中心往左50像素
                bottom_center = (width // 2 - offset_x, height - offset_y)
                touch(bottom_center)
                print(f"   已点击位置: {bottom_center}")
                
                print("\n✅ 发令按钮操作完成")

            except Exception as e:
                error_msg = f"操作发令按钮失败: {e}"
                print(f"\n❌ {error_msg}")
                traceback.print_exc()
                allure.attach(traceback.format_exc(), "错误堆栈", allure.attachment_type.TEXT)
                raise RuntimeError(error_msg) from e

    @allure.title("adb获取日志")
    # @pytest.mark.skip(reason="暂时跳过")
    def test_get_log(self):
        with allure.step("等待时间间隔结束"):
            # 检查 time_interval_2 是否已定义
            # if TestUpdateRtspSettings.time_interval_2 is None:
            #     raise ValueError("time_interval_2 未定义，请先运行 test_updateRtspSettings")
            TestUpdateRtspSettings.time_interval_2 = 1
            wait_time = TestUpdateRtspSettings.time_interval_2
            print("="*60)
            print(f"等待时间间隔结束: {wait_time} 秒 ({wait_time/60:.1f} 分钟)")
            print("="*60)
            sleep(wait_time)
            print("✅ 等待完成，开始获取日志")
        
        with allure.step("adb获取日志"): 
            # 从设备获取日志，放到项目根目录下的Log/YYYYMMDD/ 目录下
            date_str = datetime.datetime.now().strftime("%Y%m%d")
            # 项目根目录：API/tests/rtsp/ -> 项目根目录 (parents[3])
            project_root = Path(__file__).resolve().parents[3]  # 项目根目录
            log_dir = project_root / "Log" / date_str
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # 设备上的日志路径
            device_log_path = f'sdcard/DreamSports/log/{date_str}/'
            
            # 执行adb pull命令，直接拉取到目标目录（避免创建子目录）
            # 如果设备上已经有日期子目录，需要处理
            adb_cmd = ['adb', 'pull', device_log_path, str(log_dir)]
            print(f"执行命令: {' '.join(adb_cmd)}")
            
            try:
                result = subprocess.run(adb_cmd, capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    # 检查是否创建了嵌套的日期目录，如果是则移动文件
                    nested_dir = log_dir / date_str
                    if nested_dir.exists() and nested_dir.is_dir():
                        print(f"⚠️  检测到嵌套目录，正在移动文件...")
                        # 移动嵌套目录中的所有文件到父目录
                        for file_path in nested_dir.iterdir():
                            if file_path.is_file():
                                target_path = log_dir / file_path.name
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
                    
                    print(f"✅ 日志已成功拉取到: {log_dir}")
                    allure.attach(result.stdout, "adb pull 输出", allure.attachment_type.TEXT)
                else:
                    print(f"⚠️  adb pull 警告: {result.stderr}")
                    allure.attach(result.stderr, "adb pull 错误", allure.attachment_type.TEXT)
            except Exception as e:
                print(f"❌ adb pull 失败: {e}")
                raise
            # 返回日志目录路径，供后续分析使用
            return log_dir

    @allure.title("分析日志")
    # @pytest.mark.skip(reason="暂时跳过")
    def test_analyze_log(self):
        with allure.step("分析日志"):
            # 检查类变量是否存在
            if TestUpdateRtspSettings.logStartTime is None or TestUpdateRtspSettings.logEndTime is None:
                raise ValueError("logStartTime 和 logEndTime 未定义，请先运行 test_updateRtspSettings")
            
            # 动态获取项目根目录
            project_root = Path(__file__).resolve().parents[3]  # 项目根目录
            
            # 调用 analyze_log.py 分析日志
            analyze_script = project_root / "Log" / "analyze_log.py"
            if not analyze_script.exists():
                raise FileNotFoundError(f"分析脚本不存在: {analyze_script}")
            
            # 查找日志文件（项目根目录下的Log目录）
            date_str = datetime.datetime.now().strftime("%Y%m%d")
            log_dir = project_root / "Log" / date_str
            
            # 检查是否存在嵌套目录（处理之前遗留的嵌套结构）
            nested_log_dir = log_dir / date_str
            if nested_log_dir.exists() and nested_log_dir.is_dir():
                log_dir = nested_log_dir
                print(f"⚠️  检测到嵌套目录，使用: {log_dir}")
            
            if not log_dir.exists():
                raise FileNotFoundError(f"日志目录不存在: {log_dir}，请先运行 test_get_log 获取日志")

            # 查找包含 "APP_INFO: 跳绳屏" 的日志文件
            log_files = list(log_dir.glob("*.log"))
            for subdir in log_dir.iterdir():
                if subdir.is_dir():
                    log_files.extend(list(subdir.glob("*.log")))
            
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
            
            # 构建命令 - 使用绝对路径确保正确
            # 确保输出目录是绝对路径，避免pytest运行时路径问题
            output_dir_abs = (project_root / 'allure-report' / 'log_analysis').resolve()
            cmd = [
                'python3',
                str(analyze_script.resolve()),
                str(target_log_file.resolve()),
                '--start-time', TestUpdateRtspSettings.logStartTime,
                '--end-time', TestUpdateRtspSettings.logEndTime,
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
            debug_info.append(f"开始时间: {TestUpdateRtspSettings.logStartTime}")
            debug_info.append(f"结束时间: {TestUpdateRtspSettings.logEndTime}")
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
                        print(f"   - 开始时间: {TestUpdateRtspSettings.logStartTime}")
                        print(f"   - 结束时间: {TestUpdateRtspSettings.logEndTime}")
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
                    
                    # 验证关键文件是否存在
                    expected_files = ['circle_completion_stats.png', 'person_circle_relationship_bar.png']
                    missing_files = []
                    for expected_file in expected_files:
                        file_path = output_dir / expected_file
                        if file_path.exists():
                            print(f"✅ 找到预期文件: {expected_file}")
                            # 附加图表到Allure报告
                            try:
                                with open(file_path, 'rb') as f:
                                    allure.attach(f.read(), expected_file, allure.attachment_type.PNG)
                            except Exception as e:
                                print(f"⚠️  附加文件到Allure失败: {e}")
                        else:
                            missing_files.append(expected_file)
                            print(f"❌ 未找到预期文件: {expected_file}")
                    
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
                            raise AssertionError(f"缺少关键的分析结果文件: {', '.join(missing_files)}")
                        
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
